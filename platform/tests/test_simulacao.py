"""Cadastro da simulação: a pasta padronizada e o reencontro pela Capa.

É o primeiro elo da corrente que termina na capa impressa. O que se testa aqui é
o contrato entre as duas pontas: a Simulação grava, a Capa acha — sem ninguém
copiar arquivo de um lugar para o outro.

Rodar:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from isocentro.banco import capa_dados  # noqa: E402
from isocentro.dados import inventario  # noqa: E402
from isocentro.dados import notas_setup  # noqa: E402
from isocentro.interface import simulacao  # noqa: E402


def _foto(larg=2400, alt=1800, cor=(40, 90, 150)) -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (larg, alt), cor).save(buf, format="JPEG")
    return buf.getvalue()


class _ComRaiz(unittest.TestCase):
    """Base: aponta a raiz das simulações para uma pasta temporária."""

    def setUp(self):
        self.raiz = tempfile.mkdtemp(prefix="sim_teste_")
        self._env = os.environ.get(simulacao.PASTA_ENV)
        os.environ[simulacao.PASTA_ENV] = self.raiz
        simulacao.definir_raiz("")

    def tearDown(self):
        if self._env is None:
            os.environ.pop(simulacao.PASTA_ENV, None)
        else:
            os.environ[simulacao.PASTA_ENV] = self._env

    def _simulacao(self, nome="Antonio Carlos de Souza", registro="1111111AAA",
                   setups=None):
        sim = simulacao.Simulacao(nome=nome, registro=registro,
                                  nascimento="21/04/1947",
                                  cadastrada_por="dosimetrista")
        sim.setups = setups if setups is not None else [
            capa_dados.Setup(nome="TORAX", fotos=[_foto()],
                             acessorios="RAMPA DE TÓRAX\nBASE B",
                             preparo={"PARA O GANTRY": "Cabeça",
                                      "DECÚBITO": "Dorsal"})]
        return sim


class TestValidacao(_ComRaiz):
    def test_sem_paciente_nao_cadastra(self):
        sim = self._simulacao(nome="")
        self.assertIn("Escolha o paciente.", sim.valida())
        with self.assertRaises(ValueError):
            simulacao.cadastrar(sim)

    def test_sem_foto_nao_cadastra(self):
        """A foto é a única coisa que só a simulação produz."""
        sim = self._simulacao(setups=[capa_dados.Setup(nome="TORAX")])
        self.assertTrue(any("foto" in f for f in sim.valida()))

    def test_nota_e_preparo_nao_sao_obrigatorios(self):
        # Travar por causa disso deixaria o dosimetrista esperando no corredor.
        sim = self._simulacao(setups=[capa_dados.Setup(fotos=[_foto()])])
        self.assertEqual(sim.valida(), [])


class TestPastaEArquivos(_ComRaiz):
    def test_arvore_paciente_barra_mes(self):
        pasta = simulacao.cadastrar(self._simulacao(),
                                    quando=date(2026, 8, 8))
        self.assertTrue(pasta.endswith(os.path.join(
            "ANTONIO_CARLOS_DE_SOUZA_1111111AAA", "08-2026")), pasta)

    def test_registro_entra_no_nome_da_pasta(self):
        """Homônimo existe, e pasta trocada aqui contamina tudo o que vem depois."""
        a = simulacao.pasta_do_paciente("Jose da Silva", "1111111AAA")
        b = simulacao.pasta_do_paciente("Jose da Silva", "2222222BBB")
        self.assertNotEqual(a, b)

    def test_grava_json_txt_e_fotos(self):
        pasta = simulacao.cadastrar(self._simulacao())
        arquivos = sorted(os.listdir(pasta))
        self.assertIn(simulacao.ARQ_CADASTRO, arquivos)
        self.assertIn(simulacao.ARQ_NOTA, arquivos)
        self.assertIn("01_TORAX_1.jpg", arquivos)

    def test_foto_e_gravada_no_tamanho_de_impressao(self):
        """O original de 5 MB do celular não serve para nada depois."""
        pasta = simulacao.cadastrar(self._simulacao())
        tam = os.path.getsize(os.path.join(pasta, "01_TORAX_1.jpg"))
        self.assertLess(tam, 400_000, "foto gravada grande demais")
        from PIL import Image
        with Image.open(os.path.join(pasta, "01_TORAX_1.jpg")) as img:
            self.assertLessEqual(max(img.size), simulacao._LADO_MAX)

    def test_txt_e_legivel_por_pessoa(self):
        pasta = simulacao.cadastrar(self._simulacao())
        with open(os.path.join(pasta, simulacao.ARQ_NOTA), encoding="utf-8") as fh:
            texto = fh.read()
        self.assertIn("Antonio Carlos de Souza", texto)
        self.assertIn("TORAX", texto)
        self.assertIn("RAMPA DE TÓRAX", texto)
        self.assertIn("Cabeça", texto)

    def test_recadastrar_no_mesmo_mes_troca_as_fotos(self):
        """Segunda leva de fotos não pode conviver com a primeira: a Capa não
        saberia quais são as atuais."""
        sim = self._simulacao()
        pasta = simulacao.cadastrar(sim)
        sim2 = self._simulacao(setups=[
            capa_dados.Setup(nome="PELVE", fotos=[_foto(), _foto()])])
        simulacao.cadastrar(sim2)
        jpgs = sorted(f for f in os.listdir(pasta) if f.endswith(".jpg"))
        self.assertEqual(jpgs, ["01_PELVE_1.jpg", "01_PELVE_2.jpg"])

    def test_arquivo_posto_a_mao_na_pasta_sobrevive(self):
        pasta = simulacao.cadastrar(self._simulacao())
        extra = os.path.join(pasta, "conferencia do fisico.txt")
        with open(extra, "w", encoding="utf-8") as fh:
            fh.write("ok")
        simulacao.cadastrar(self._simulacao())
        self.assertTrue(os.path.exists(extra))

    def test_nome_com_acento_e_barra_vira_pasta_valida(self):
        p = simulacao.pasta_do_paciente("José D'Ávila / Filho", "1X")
        self.assertNotIn("/", os.path.basename(p))
        self.assertNotIn("'", os.path.basename(p))


class TestReencontro(_ComRaiz):
    """A ponte: a Capa pergunta pelo paciente, não pela pasta."""

    def test_capa_acha_a_simulacao_pelo_registro(self):
        simulacao.cadastrar(self._simulacao())
        setups = capa_dados.simulacao_do_paciente("Antonio Carlos de Souza",
                                                  "1111111AAA")
        self.assertEqual(len(setups), 1)
        self.assertEqual(setups[0].nome, "TORAX")
        self.assertEqual(len(setups[0].fotos), 1)
        self.assertEqual(setups[0].preparo["DECÚBITO"], "Dorsal")

    def test_acha_pelo_nome_quando_nao_ha_registro(self):
        simulacao.cadastrar(self._simulacao(registro=""))
        setups = capa_dados.simulacao_do_paciente("Antonio Carlos de Souza")
        self.assertEqual(len(setups), 1)

    def test_paciente_sem_simulacao_devolve_vazio(self):
        self.assertEqual(capa_dados.simulacao_do_paciente("Ninguem", "0X"), [])

    def test_pega_a_simulacao_mais_recente(self):
        """Replanejamento: vale o último posicionamento, não o primeiro."""
        sim = self._simulacao(setups=[capa_dados.Setup(nome="ANTIGO",
                                                       fotos=[_foto()])])
        simulacao.cadastrar(sim, quando=date(2025, 11, 1))
        sim2 = self._simulacao(setups=[capa_dados.Setup(nome="ATUAL",
                                                        fotos=[_foto()])])
        simulacao.cadastrar(sim2, quando=date(2026, 8, 1))
        setups = capa_dados.simulacao_do_paciente("Antonio Carlos de Souza",
                                                  "1111111AAA")
        self.assertEqual(setups[0].nome, "ATUAL")

    def test_historico_lista_do_mais_novo_ao_mais_antigo(self):
        simulacao.cadastrar(self._simulacao(), quando=date(2025, 11, 1))
        simulacao.cadastrar(self._simulacao(), quando=date(2026, 8, 1))
        meses = [os.path.basename(p) for p in
                 simulacao.historico("Antonio Carlos de Souza", "1111111AAA")]
        self.assertEqual(meses, ["08-2026", "11-2025"])

    def test_cadastro_vence_a_interpretacao_de_docx(self):
        """Com SIMULACAO.json na pasta não há nada a adivinhar."""
        pasta = simulacao.cadastrar(self._simulacao())
        # Uma nota .docx solta na mesma pasta não deve mudar o resultado.
        with open(os.path.join(pasta, "OUTRA.txt"), "w", encoding="utf-8") as fh:
            fh.write("DECUBITO VENTRAL\nBEXIGA CHEIA\n")
        setups = capa_dados.setups_da_pasta(pasta)
        self.assertEqual(len(setups), 1)
        self.assertEqual(setups[0].nome, "TORAX")
        self.assertEqual(setups[0].preparo["DECÚBITO"], "Dorsal")

    def test_json_ilegivel_nao_derruba(self):
        pasta = simulacao.cadastrar(self._simulacao())
        with open(os.path.join(pasta, simulacao.ARQ_CADASTRO), "w",
                  encoding="utf-8") as fh:
            fh.write("{isto nao e json")
        self.assertIsNone(simulacao.carregar(pasta))
        # E a Capa cai no caminho antigo em vez de quebrar.
        self.assertIsInstance(capa_dados.setups_da_pasta(pasta), list)

    def test_foto_citada_e_ausente_nao_derruba(self):
        pasta = simulacao.cadastrar(self._simulacao())
        os.remove(os.path.join(pasta, "01_TORAX_1.jpg"))
        sim = simulacao.carregar(pasta)
        self.assertIsNotNone(sim)
        self.assertEqual(sim.setups[0].fotos, [])


class _ComEnv(unittest.TestCase):
    """Base que devolve a variável de ambiente ao que era.

    Sem isto, a pasta temporária destes testes vazava para o resto do
    ``discover`` — e o próximo arquivo a tocar o inventário lia o daqui.
    """
    VAR = ""
    PREFIXO = "tmp_"

    def setUp(self):
        self._env = os.environ.get(self.VAR)
        os.environ[self.VAR] = tempfile.mkdtemp(prefix=self.PREFIXO)

    def tearDown(self):
        if self._env is None:
            os.environ.pop(self.VAR, None)
        else:
            os.environ[self.VAR] = self._env


class TestIndiceEmMemoria(_ComRaiz):
    """A varredura é guardada por um minuto — 08/09/2026.

    Pedido pelo crescimento das pastas: ``procurar`` abre uma listagem de
    diretório por paciente e faz o parse de um JSON por pasta de mês, e é
    chamada a cada montagem de capa — que acontece ao NAVEGAR na busca. Numa
    raiz de rede com centenas de pacientes isso vira centenas de idas ao
    compartilhamento por nome que o cursor toca.

    O que estes testes fixam é o que um índice pode estragar: mostrar o que já
    não existe, esconder o que acabou de ser gravado, ou responder pela raiz
    errada.
    """

    def _contar_leituras(self):
        """Conta as aberturas de cadastro — é a E/S que o índice existe para
        evitar, e contar chamadas de função é o único jeito de vê-la."""
        chamadas = []
        real = simulacao._identificacao

        def espiao(pasta):
            chamadas.append(pasta)
            return real(pasta)

        simulacao._identificacao = espiao
        self.addCleanup(lambda: setattr(simulacao, "_identificacao", real))
        return chamadas

    def test_a_segunda_busca_nao_toca_no_disco(self):
        simulacao.cadastrar(self._simulacao())
        chamadas = self._contar_leituras()
        simulacao.procurar("Antonio Carlos de Souza", "1111111AAA")
        primeira = len(chamadas)
        self.assertGreater(primeira, 0, "a primeira tinha de ler o disco")
        for _ in range(5):
            simulacao.procurar("Antonio Carlos de Souza", "1111111AAA")
        self.assertEqual(len(chamadas), primeira, "releu o disco com índice")

    def test_o_cadastro_feito_AQUI_aparece_na_hora(self):
        """É o passo seguinte da corrente: quem cadastra vai procurar a pasta em
        seguida, e esperar o minuto seria o programa não achar o que ele mesmo
        acabou de escrever."""
        simulacao.procurar("Antonio Carlos de Souza", "1111111AAA")  # esquenta
        simulacao.cadastrar(self._simulacao())
        self.assertNotEqual(
            simulacao.procurar("Antonio Carlos de Souza", "1111111AAA"), "")

    def test_quem_NAO_e_achado_faz_reler_uma_vez(self):
        """É o único momento em que a varredura tem retorno.

        O paciente pode ter sido cadastrado noutra estação depois da última
        varredura, e a alternativa a reler é afirmar que ele não tem pasta. Não
        havendo achado, relê UMA vez e repete a busca.
        """
        simulacao.cadastrar(self._simulacao())
        simulacao.procurar("Antonio Carlos de Souza", "1111111AAA")  # esquenta
        chamadas = self._contar_leituras()
        # Envelhece à mão em vez de esperar: teste que dorme um minuto é teste
        # que ninguém roda.
        simulacao._indice["em"] -= simulacao.SEGUNDOS_ENTRE_VARREDURAS + 1
        self.assertEqual(simulacao.procurar("Ninguem Disso", "0000000ZZZ"), "")
        self.assertGreater(len(chamadas), 0, "não releu ao falhar")

    def test_quem_ACHA_nunca_faz_reler(self):
        """A releitura é o caminho da falha. No caminho bom ela custaria
        segundos por tecla — medido: 3,8 s com 400 pacientes em disco local."""
        simulacao.cadastrar(self._simulacao())
        simulacao.procurar("Antonio Carlos de Souza", "1111111AAA")
        chamadas = self._contar_leituras()
        simulacao._indice["em"] -= simulacao.SEGUNDOS_ENTRE_VARREDURAS + 1
        simulacao.procurar("Antonio Carlos de Souza", "1111111AAA")
        self.assertEqual(chamadas, [], "releu mesmo tendo achado")

    def test_falha_repetida_nao_varre_a_cada_tecla(self):
        """O paciente que REALMENTE não tem cadastro é o caso perigoso: sem o
        intervalo, cada busca dele refaria a varredura inteira — e a busca
        acontece ao navegar."""
        simulacao.cadastrar(self._simulacao())
        simulacao.procurar("Ninguem Disso", "0000000ZZZ")   # já releu uma vez
        chamadas = self._contar_leituras()
        for _ in range(5):
            simulacao.procurar("Ninguem Disso", "0000000ZZZ")
        self.assertEqual(chamadas, [], "varreu de novo dentro do intervalo")

    def test_trocar_a_raiz_nao_responde_pela_antiga(self):
        """O índice é de UMA raiz. Responder pela anterior seria devolver a
        pasta de outro serviço — ou de outro ambiente de teste."""
        simulacao.cadastrar(self._simulacao())
        achou = simulacao.procurar("Antonio Carlos de Souza", "1111111AAA")
        self.assertNotEqual(achou, "")
        outra = tempfile.mkdtemp(prefix="sim_outra_")
        simulacao.definir_raiz(outra)
        try:
            self.assertEqual(
                simulacao.procurar("Antonio Carlos de Souza", "1111111AAA"), "")
        finally:
            simulacao.definir_raiz("")

    def test_a_REGRA_nao_foi_para_dentro_do_indice(self):
        """O índice guarda a varredura, não a decisão.

        Guardado já resolvido, ele seria uma segunda versão da regra de
        casamento — e as duas divergiriam no primeiro conserto feito só num dos
        lados. O que a varredura devolve são linhas cruas.
        """
        simulacao.cadastrar(self._simulacao())
        linhas = simulacao._varredura(simulacao.raiz())
        self.assertTrue(linhas)
        for reg, nome, pasta, marca in linhas:
            self.assertIsInstance(reg, str)
            self.assertIsInstance(nome, str)
            self.assertTrue(os.path.isdir(pasta))
            # A marca é a hora da pasta do PACIENTE, guardada para revalidar o
            # achado com um stat em vez de uma varredura.
            self.assertIsInstance(marca, float)

    def test_simulacao_NOVA_aparece_com_o_indice_quente(self):
        """O defeito achado na revisão de 08/09/2026, e o mais grave dos dois.

        Com o índice quente, uma simulação cadastrada em OUTRA estação ficava
        invisível pelo resto da sessão: ``procurar`` achava o mês antigo, e um
        achado nunca era revalidado. A Capa montava o posicionamento ANTIGO —
        num replanejamento, é a folha errada indo para a sala.

        Quem enxerga a pasta nova é a hora da pasta do PACIENTE: acrescentar um
        mês muda o pai, e isso custa um ``stat``, não uma varredura.
        """
        antiga = simulacao.cadastrar(self._simulacao(), quando=date(2026, 3, 1))
        self.assertEqual(
            simulacao.procurar("Antonio Carlos de Souza", "1111111AAA"), antiga)
        # "Outra estação": grava sem passar pelo cadastrar desta sessão, que
        # esqueceria o índice e esconderia o defeito.
        # O nome da pasta vem do PRÓPRIO projeto: ``_ordem_mes`` lê o nome
        # para ordenar, e um inventado aqui perderia do antigo por não ser
        # reconhecido — o teste passaria a medir o meu palpite de nome.
        nova = os.path.join(os.path.dirname(antiga),
                            simulacao.pasta_da_data(date(2026, 9, 1)))
        os.makedirs(nova, exist_ok=True)
        io.open(os.path.join(nova, simulacao.ARQ_CADASTRO), "w",
                encoding="utf-8").write(io.open(
                    os.path.join(antiga, simulacao.ARQ_CADASTRO),
                    encoding="utf-8").read())
        self.assertEqual(
            simulacao.procurar("Antonio Carlos de Souza", "1111111AAA"), nova,
            "ficou com o posicionamento antigo")

    def test_pasta_que_SUMIU_nao_e_devolvida(self):
        """O segundo defeito da mesma revisão.

        O caminho guardado saía sem conferir que ainda existe — e ele vai
        direto para o ``pasta_escolhida`` da Capa, escapando da conferência de
        existência que ela faz para a pasta apontada à mão. O usuário recebia
        "nada de posicionamento na pasta", que manda procurar foto que não
        falta em vez de dizer que a pasta é que sumiu.
        """
        import shutil
        achou = simulacao.cadastrar(self._simulacao())
        self.assertEqual(
            simulacao.procurar("Antonio Carlos de Souza", "1111111AAA"), achou)
        shutil.rmtree(achou)
        self.assertEqual(
            simulacao.procurar("Antonio Carlos de Souza", "1111111AAA"), "")

    def test_paciente_recadastrado_COM_registro_nao_fica_no_antigo(self):
        """A revalidação olhava só a pasta do PACIENTE achado — e o cadastro
        novo pode nascer noutra pasta de paciente.

        Acontece de verdade, e é o caminho normal: o paciente que ainda não
        estava no relatório é cadastrado SEM registro, e o nome da pasta sai só
        com o nome. Quando o registro aparece, o cadastro seguinte vai para
        ``NOME_1111111AAA`` — outra pasta, irmã da primeira. A hora da pasta
        antiga não muda, então o achado guardado continuava "válido" e a Capa
        montava o posicionamento VELHO pelo resto da sessão.

        Quem enxerga isso é a hora da RAIZ e das GAVETAS: é lá que uma pasta de
        paciente nova aparece. São ``1 + gavetas`` ``stat``.
        """
        antiga = simulacao.cadastrar(self._simulacao(registro=""),
                                     quando=date(2026, 3, 1))
        self.assertEqual(
            simulacao.procurar("Antonio Carlos de Souza", "1111111AAA"), antiga)
        # "Outra estação": o cadastro é real, mas o índice DAQUI não soube dele.
        # Sem devolver o índice ao que era, o ``esquecer_indice`` do
        # ``cadastrar`` esconderia justamente o defeito que se está medindo.
        guardado = dict(simulacao._indice)
        nova = simulacao.cadastrar(self._simulacao(), quando=date(2026, 9, 1))
        simulacao._indice.clear()
        simulacao._indice.update(guardado)

        self.assertNotEqual(nova, antiga, "o teste precisa de duas pastas")
        self.assertEqual(
            simulacao.procurar("Antonio Carlos de Souza", "1111111AAA"), nova,
            "ficou preso no cadastro sem registro")

    def test_varredura_que_FALHOU_nao_vira_indice(self):
        """Uma piscada do compartilhamento passou a durar um minuto.

        Enquanto a varredura era refeita a cada busca, o erro de leitura se
        curava na navegação seguinte. Guardado, o resultado pela metade fazia
        toda busca responder "sem cadastro" até a próxima varredura — e em
        silêncio, que é o modo de falhar que este projeto não aceita.
        """
        simulacao.cadastrar(self._simulacao())
        original = simulacao._subpastas
        caiu = {"rede": True}

        def instavel(base, erros=None):
            if caiu["rede"]:
                if erros is not None:
                    erros.append(base)
                return []
            return original(base, erros)

        simulacao._subpastas = instavel
        try:
            self.assertEqual(
                simulacao.procurar("Antonio Carlos de Souza", "1111111AAA"), "")
        finally:
            simulacao._subpastas = original
        caiu["rede"] = False
        # A rede voltou: a busca seguinte tem de achar, sem esperar minuto
        # nenhum. O que a falha não pode ter deixado para trás é um índice.
        self.assertNotEqual(
            simulacao.procurar("Antonio Carlos de Souza", "1111111AAA"), "",
            "guardou a varredura que falhou")

    def test_duas_pastas_do_MESMO_mes_desempatam_sempre_igual(self):
        """O desempate existia antes do índice, no ``max`` da tupla inteira.

        Com duas pastas do mesmo mês — o cadastro sem registro e o recadastro
        com ele —, ordenar só pelo mês devolve o PRIMEIRO máximo, isto é, o que
        o ``scandir`` tiver listado primeiro. A escolha passaria a depender da
        ordem do sistema de arquivos, e mudaria calada de uma máquina para
        outra. Aqui a resposta é a mesma nas duas ordens.
        """
        sem = os.path.join(self.raiz, "A", "ANTONIO_CARLOS_DE_SOUZA", "09-2026")
        com = os.path.join(self.raiz, "A",
                           "ANTONIO_CARLOS_DE_SOUZA_1111111AAA", "09-2026")
        linhas = [("", "Antonio Carlos de Souza", sem, 0.0),
                  ("1111111AAA", "Antonio Carlos de Souza", com, 0.0)]
        alvo = capa_dados.normalizar_id("1111111AAA")
        nome = capa_dados.normalizar_nome("Antonio Carlos de Souza")
        for ordem in (linhas, list(reversed(linhas))):
            escolhida = simulacao._casar(alvo, nome, ordem)
            self.assertEqual(escolhida[2], com, "desempate mudou com a ordem")

    def test_com_indice_quente_o_resultado_e_o_MESMO(self):
        """A economia não pode mudar a resposta — nem a do caso que casa por
        nome, que é o mais frágil dos dois caminhos."""
        simulacao.cadastrar(self._simulacao(registro=""))
        primeiro = simulacao.procurar("Antonio Carlos de Souza")
        simulacao.esquecer_indice()
        frio = simulacao.procurar("Antonio Carlos de Souza")
        self.assertEqual(primeiro, frio)
        self.assertNotEqual(frio, "")


class TestInventario(_ComEnv):
    VAR = inventario.PASTA_ENV
    PREFIXO = "inv_"

    def test_semeia_ficticio_na_primeira_vez(self):
        itens = inventario.carregar()
        self.assertTrue(itens)
        self.assertTrue(any(i.disponivel() for i in itens))

    def test_so_mascara_conta_utilizacao(self):
        """VacLok é vinculado ao paciente, mas contar moldagens dele não diz
        nada sobre o estado do saco."""
        antes = {i.codigo: i.usos for i in inventario.carregar()}
        inventario.registrar_uso(["MSK-001", "VAC-100"], "PACIENTE", "1X")
        depois = {i.codigo: i.usos for i in inventario.carregar()}
        self.assertEqual(depois["MSK-001"], antes["MSK-001"] + 1)
        self.assertEqual(depois["VAC-100"], antes["VAC-100"])

    def test_avisa_a_mascara_que_alcanca_o_limite_agora(self):
        # Avaliando antes de contar, a de 19 usos passava calada e só avisava na
        # vez seguinte — com o material já na sala.
        avisos = inventario.registrar_uso(["MSK-030"], "PACIENTE", "1X")
        self.assertTrue(any("MSK-030" in a and "utiliza" in a for a in avisos))

    def test_avisa_item_que_estava_com_outro_paciente(self):
        inventario.registrar_uso(["MSK-002"], "PRIMEIRO", "1X")
        avisos = inventario.registrar_uso(["MSK-002"], "SEGUNDO", "2X")
        self.assertTrue(any("PRIMEIRO" in a for a in avisos))

    def test_vincular_nunca_e_bloqueado(self):
        """A prateleira é a verdade; o app avisa, não impede."""
        inventario.registrar_uso(["MSK-002"], "PRIMEIRO", "1X")
        inventario.registrar_uso(["MSK-002"], "SEGUNDO", "2X")
        item = inventario.por_codigo("MSK-002")
        self.assertEqual(item.paciente, "SEGUNDO")

    def test_liberar_devolve_e_descartar_retira(self):
        inventario.registrar_uso(["VAC-100"], "PACIENTE", "1X")
        inventario.liberar(["VAC-100"])
        self.assertTrue(inventario.por_codigo("VAC-100").disponivel())
        inventario.liberar(["VAC-100"], descartar=True)
        self.assertEqual(inventario.por_codigo("VAC-100").estado,
                         inventario.DESCARTADO)

    def test_disponiveis_esconde_o_que_esta_em_uso(self):
        livres = {i.codigo for i in inventario.disponiveis()}
        inventario.registrar_uso(["MSK-001"], "PACIENTE", "1X")
        self.assertIn("MSK-001", livres)
        self.assertNotIn("MSK-001",
                         {i.codigo for i in inventario.disponiveis()})


class TestBibliotecaDeNotas(_ComEnv):
    VAR = notas_setup.PASTA_ENV
    PREFIXO = "notas_"

    def setUp(self):
        super().setUp()
        # O cache só existe quando a gravação falha, mas se um teste anterior o
        # deixou de pé ele seria a "biblioteca" de todos os seguintes — e o
        # arquivo temporário daqui não seria nem lido.
        notas_setup._cache = None

    def tearDown(self):
        notas_setup._cache = None
        super().tearDown()

    def test_semeia_do_acervo_docx(self):
        """Ninguém precisa redigitar quarenta notas para começar a usar."""
        notas = notas_setup.carregar()
        if not notas_setup.pasta_do_acervo():
            self.skipTest("acervo .docx não disponível neste ambiente")
        self.assertGreater(len(notas), 10)
        self.assertTrue(all(n.modelo for n in notas))
        # A interpretação já separou preparo de acessório.
        self.assertTrue(any(n.preparo for n in notas))

    def test_guardar_substitui_a_de_mesmo_nome(self):
        notas_setup.guardar(notas_setup.Nota(nome="TESTE", acessorios="A"))
        notas_setup.guardar(notas_setup.Nota(nome="teste", acessorios="B"))
        iguais = [n for n in notas_setup.carregar()
                  if capa_dados.normalizar_nome(n.nome) == "TESTE"]
        self.assertEqual(len(iguais), 1)
        self.assertEqual(iguais[0].acessorios, "B")

    def test_nota_sem_nome_nao_entra(self):
        antes = len(notas_setup.carregar())
        notas_setup.guardar(notas_setup.Nota(nome="   ", acessorios="X"))
        self.assertEqual(len(notas_setup.carregar()), antes)

    def test_aplicar_nota_devolve_um_setup(self):
        nota = notas_setup.Nota(nome="PELVE", acessorios="TRAVESSEIRO",
                                preparo={"BEXIGA": "Cheia"})
        setup = nota.como_setup()
        self.assertEqual(setup.nome, "PELVE")
        self.assertEqual(setup.preparo["BEXIGA"], "Cheia")
        # Cópia, não referência: editar o setup não altera a nota da biblioteca.
        setup.preparo["BEXIGA"] = "Vazia"
        self.assertEqual(nota.preparo["BEXIGA"], "Cheia")

    def test_remover(self):
        notas_setup.guardar(notas_setup.Nota(nome="APAGAR", acessorios="X"))
        notas_setup.remover("apagar")
        self.assertIsNone(notas_setup.por_nome("APAGAR"))

    # ── A semente empacotada ─────────────────────────────────────────────
    # Os três testes abaixo são de UM defeito, relatado da clínica: "ao clicar
    # em escolher nota não aparecem as notas". A instalação nova saía sem
    # biblioteca e sem como semear uma — o acervo .docx não é empacotado, e o
    # arquivo de trabalho não pode ser (o migrar.ps1 nunca sobrescreve, então
    # ele no zip faria a migração PULAR as notas reais do serviço). Na máquina
    # de desenvolvimento o acervo existe, e foi por isso que passou meses.

    def test_semente_existe_e_esta_no_repositorio(self):
        self.assertTrue(os.path.exists(notas_setup.caminho_da_semente()),
                        "sem assets/notas_modelo.json a instalação nova abre "
                        "com o seletor de notas vazio")
        self.assertGreater(len(notas_setup.ler_semente()), 10)

    def test_semente_tem_nome_diferente_do_arquivo_de_trabalho(self):
        """É a única coisa que a mantém fora da lista do ``migrar.ps1``.

        Igualar os dois nomes reintroduziria o erro que a semente evita: o
        arquivo viajaria no zip, a migração o encontraria já existente no
        destino e PULARIA a biblioteca que o serviço construiu.
        """
        self.assertNotEqual(notas_setup.ARQUIVO_SEMENTE, notas_setup.ARQUIVO)

    def test_sem_acervo_docx_a_semente_assume(self):
        """O caso da clínica: pacote sem acervo tem de abrir COM notas."""
        original = notas_setup.pasta_do_acervo
        # Guardar e devolver — ``del notas_setup.pasta_do_acervo`` apagaria a
        # função ORIGINAL do módulo para o resto do processo.
        notas_setup.pasta_do_acervo = lambda: ""
        try:
            notas = notas_setup.carregar()
        finally:
            notas_setup.pasta_do_acervo = original
        self.assertGreater(len(notas), 10)
        self.assertTrue(all(n.modelo for n in notas))
        self.assertTrue(any(n.preparo for n in notas),
                        "a semente perdeu o preparo já separado do acessório")

    def test_semente_nao_vira_arquivo_sozinha(self):
        """Senão ela BLOQUEIA a migração da biblioteca real do serviço.

        O MIGRAR.txt manda abrir o programa antes de rodar o ``migrar.ps1``
        (passo 0, apontar o serviço), e o ``migrar.ps1`` nunca sobrescreve. Um
        ``notas_posicionamento.json`` gravado só por ter aberto o programa faria
        a migração PULAR as notas do serviço — e com a semente no lugar delas
        ninguém perceberia, porque as 40 notas são plausíveis.
        """
        original = notas_setup.pasta_do_acervo
        notas_setup.pasta_do_acervo = lambda: ""
        try:
            self.assertGreater(len(notas_setup.carregar()), 10)
            self.assertFalse(os.path.exists(notas_setup.caminho()))
            # E vira arquivo assim que há conteúdo local de verdade.
            notas_setup.guardar(notas_setup.Nota(nome="DAQUI", acessorios="X"))
            self.assertTrue(os.path.exists(notas_setup.caminho()))
            self.assertIsNotNone(notas_setup.por_nome("DAQUI"))
        finally:
            notas_setup.pasta_do_acervo = original

    def test_acervo_docx_ganha_da_semente(self):
        """Quem larga os ``.docx`` na pasta está dizendo "use estes"."""
        if not notas_setup.pasta_do_acervo():
            self.skipTest("acervo .docx não disponível neste ambiente")
        original = notas_setup._semear_do_acervo
        notas_setup._semear_do_acervo = lambda: [
            notas_setup.Nota(nome="SÓ DO ACERVO", acessorios="X")]
        try:
            notas = notas_setup.semear()
        finally:
            notas_setup._semear_do_acervo = original
        self.assertEqual([n.nome for n in notas], ["SÓ DO ACERVO"])


class TestRegressoesDaRevisao(_ComRaiz):
    """Defeitos achados na revisão de código — cada um com o seu caso."""

    def test_pasta_sem_nada_nao_finge_ter_setup(self):
        """A ponte Simulação→Capa dependia disto.

        ``setups_da_pasta`` devolvia ``[Setup(fotos=[])]`` para qualquer pasta
        existente, então o ``if not setups`` da tela nunca disparava e a busca
        pela simulação era código morto — no exato fluxo para o qual foi feita.
        """
        self.assertEqual(capa_dados.setups_da_pasta(tempfile.mkdtemp()), [])
        # Com foto, continua havendo um setup.
        so_fotos = tempfile.mkdtemp()
        with open(os.path.join(so_fotos, "a.jpg"), "wb") as fh:
            fh.write(_foto())
        self.assertEqual(len(capa_dados.setups_da_pasta(so_fotos)), 1)

    def test_txt_gerado_pelo_app_nao_e_lido_como_nota(self):
        """Com o JSON corrompido, o cabeçalho do próprio arquivo ("SIMULAÇÃO —
        Fulano", "IMOBILIZADORES") ia parar na caixa de acessórios da capa."""
        pasta = simulacao.cadastrar(self._simulacao())
        os.remove(os.path.join(pasta, simulacao.ARQ_CADASTRO))
        setups = capa_dados.setups_da_pasta(pasta)
        texto = " ".join(s.acessorios for s in setups)
        self.assertNotIn("SIMULAÇÃO", texto)
        self.assertNotIn("IMOBILIZADORES", texto)

    def test_um_cadastro_conta_como_uma_fonte(self):
        """Dois posicionamentos vêm de UM arquivo; contar dois disparava o aviso
        de "há 2 notas na pasta" — ambiguidade que não existe."""
        sim = self._simulacao(setups=[
            capa_dados.Setup(nome="A", fotos=[_foto()]),
            capa_dados.Setup(nome="B", fotos=[_foto()])])
        pasta = simulacao.cadastrar(sim)
        fontes = {s.arquivo for s in capa_dados.setups_da_pasta(pasta)}
        self.assertEqual(len(fontes), 1)

    def test_conta_uso_ignora_acento(self):
        """Inventário real exportando "MASCARA LONGA" desligava a contagem e o
        aviso de limite em silêncio."""
        self.assertTrue(inventario.Item(tipo="MASCARA LONGA").conta_uso())
        self.assertTrue(inventario.Item(tipo="Máscara Curta").conta_uso())
        self.assertFalse(inventario.Item(tipo="VacLok Corpo").conta_uso())

    def test_png_gerado_pelo_app_nao_e_foto_de_posicionamento(self):
        """O achado mais grave da 2ª revisão.

        ``registro_json`` grava CORTES_*.png e DVH_*.png na MESMA pasta que a
        capa varre. Sem excluí-los, a pasta "tinha fotos": a ponte para o
        cadastro de simulação nunca disparava, e os cortes de dose iam parar nos
        quadros de foto de posicionamento da capa.
        """
        pasta = tempfile.mkdtemp()
        for nome in ("CORTES_FULANO_v1.png", "DVH_FULANO_v1.png",
                     "DRR_p1_v1.png", "FICHA_FULANO.json"):
            with open(os.path.join(pasta, nome), "wb") as fh:
                fh.write(_foto())
        self.assertEqual(capa_dados.setups_da_pasta(pasta), [])
        # Uma foto de verdade na mesma pasta continua valendo.
        with open(os.path.join(pasta, "setup do paciente.jpg"), "wb") as fh:
            fh.write(_foto())
        setups = capa_dados.setups_da_pasta(pasta)
        self.assertEqual(len(setups), 1)
        self.assertEqual(len(setups[0].fotos), 1)

    def test_uma_subpasta_ilegivel_nao_derruba_a_procura(self):
        """Um só OSError descartava TODOS os candidatos: o app respondia
        "sem simulação" para todo mundo."""
        simulacao.cadastrar(self._simulacao())
        original = simulacao._subpastas
        chamadas = {"n": 0}

        def instavel(base, erros=None):
            chamadas["n"] += 1
            if chamadas["n"] == 2:      # falha no meio da varredura
                # Anota o erro como a função REAL anota: é isso que impede a
                # varredura pela metade de virar índice guardado.
                if erros is not None:
                    erros.append(base)
                return []
            return original(base, erros)

        simulacao._subpastas = instavel
        try:
            # Mesmo com uma pasta ilegível, as demais continuam sendo olhadas.
            self.assertIsInstance(
                simulacao.procurar("Antonio Carlos de Souza", "1111111AAA"), str)
        finally:
            simulacao._subpastas = original

    def test_cadastro_sem_registro_e_achavel_por_quem_tem_registro(self):
        """Paciente ainda fora do relatório é cadastrado sem ID; a Capa, que já
        tem o ID do DICOM, precisava achá-lo assim mesmo."""
        simulacao.cadastrar(self._simulacao(registro=""))
        setups = capa_dados.simulacao_do_paciente("Antonio Carlos de Souza",
                                                  "1111111AAA")
        self.assertEqual(len(setups), 1)

    def test_usos_como_texto_nao_derruba_o_cadastro(self):
        """"usos": "3" é o que um export de planilha produz."""
        item = inventario.Item(tipo="Máscara Longa", usos="3")
        self.assertEqual(item.usos, 3)
        self.assertEqual(inventario.Item(tipo="Máscara", usos=None).usos, 0)

    def test_busca_de_paciente_aceita_id_com_separador(self):
        ref = capa_dados.PacienteRef(registro="9000004CEL", nome="Camila Souza")
        for termo in ("9000004-CEL", "9000004 cel", "9000004", "camila"):
            self.assertTrue(ref.casa(termo), termo)
        self.assertFalse(ref.casa("9000026ZZZ"))


class TestRegressoesDaTerceiraRevisao(unittest.TestCase):
    """Defeitos achados ao unificar a Capa com o posicionamento."""

    def setUp(self):
        self._env = {}
        for var, pref in ((inventario.PASTA_ENV, "inv_"),
                          (notas_setup.PASTA_ENV, "notas_")):
            self._env[var] = os.environ.get(var)
            os.environ[var] = tempfile.mkdtemp(prefix=pref)

    def tearDown(self):
        for var, antigo in self._env.items():
            if antigo is None:
                os.environ.pop(var, None)
            else:
                os.environ[var] = antigo

    def test_salvar_notas_devolve_se_conseguiu(self):
        """Sem o retorno, a falha de gravação era engolida e o acervo `.docx`
        era revarrido a cada aba — na thread da interface."""
        self.assertIs(notas_setup.salvar([]), True)

    def test_biblioteca_em_memoria_quando_nao_da_para_gravar(self):
        chamadas = {"n": 0}
        # É o ACERVO que precisa ficar em memória — é ele que custa caro (varre
        # dezenas de .docx na thread da interface). A semente empacotada é um
        # JSON pequeno e é relida à vontade, de propósito: ver
        # ``test_semente_nao_vira_arquivo_sozinha``.
        original_salvar = notas_setup.salvar
        original_semear = notas_setup._semear_do_acervo
        notas_setup.salvar = lambda notas: False
        notas_setup._semear_do_acervo = lambda: (
            chamadas.__setitem__("n", chamadas["n"] + 1)
            or [notas_setup.Nota(nome="X")])
        notas_setup._cache = None
        try:
            notas_setup.carregar()
            notas_setup.carregar()
            self.assertEqual(chamadas["n"], 1, "revarreu o acervo de novo")
        finally:
            notas_setup.salvar = original_salvar
            notas_setup._semear_do_acervo = original_semear
            notas_setup._cache = None

    def test_itens_em_uso_pelo_mesmo_paciente_sao_reconheciveis(self):
        """Recadastrar no mesmo mês regravava o JSON com a lista de
        imobilizadores vazia: o item já estava EM_USO e, por isso, sumia da
        seleção. A tela agora reconhece o que é DESTE paciente pelo registro."""
        inventario.registrar_uso(["MSK-001"], "FULANO", "9X")
        inventario.registrar_uso(["MSK-002"], "OUTRO", "8X")
        do_paciente = {i.codigo for i in inventario.carregar()
                       if i.estado == inventario.EM_USO and i.registro == "9X"}
        self.assertEqual(do_paciente, {"MSK-001"})


class TestRegressoesDaQuartaRevisao(unittest.TestCase):
    """Defeitos de contabilidade e de persistência achados na revisão.

    Isola as DUAS pastas (inventário e notas) — ``_ComEnv`` cuida de uma só.
    """

    def setUp(self):
        self._env = {}
        for var, pref in ((inventario.PASTA_ENV, "inv_"),
                          (notas_setup.PASTA_ENV, "notas_")):
            self._env[var] = os.environ.get(var)
            os.environ[var] = tempfile.mkdtemp(prefix=pref)

    def tearDown(self):
        for var, antigo in self._env.items():
            if antigo is None:
                os.environ.pop(var, None)
            else:
                os.environ[var] = antigo

    def test_recadastrar_o_mesmo_paciente_nao_conta_utilizacao_nova(self):
        """A tela remarca de propósito o que já é deste paciente, e refazer o
        cadastro do mês é fluxo normal. Contar de novo antecipa o aviso de
        limite — e faz descartar máscara boa."""
        inventario.registrar_uso(["MSK-001"], "FULANO", "9X")
        antes = next(i.usos for i in inventario.carregar()
                     if i.codigo == "MSK-001")
        inventario.registrar_uso(["MSK-001"], "FULANO", "9X")
        inventario.registrar_uso(["MSK-001"], "FULANO", "9X")
        depois = next(i.usos for i in inventario.carregar()
                      if i.codigo == "MSK-001")
        self.assertEqual(depois, antes, "recadastro inflou o contador")

    def test_outro_paciente_na_mesma_mascara_conta(self):
        """O contador existe para a moldagem: paciente novo é utilização nova."""
        inventario.registrar_uso(["MSK-001"], "FULANO", "9X")
        antes = next(i.usos for i in inventario.carregar()
                     if i.codigo == "MSK-001")
        inventario.registrar_uso(["MSK-001"], "BELTRANO", "7Z")
        depois = next(i.usos for i in inventario.carregar()
                      if i.codigo == "MSK-001")
        self.assertEqual(depois, antes + 1)

    def test_nota_guardada_sem_disco_diz_que_nao_gravou(self):
        """Anunciar "guardada na biblioteca" para algo que some no fechamento é
        pior do que não guardar: ninguém refaz o que acha que está salvo."""
        original = notas_setup.salvar
        notas_setup.salvar = lambda notas: False
        notas_setup._cache = None
        try:
            self.assertIs(notas_setup.guardar(notas_setup.Nota(nome="Z")), False)
        finally:
            notas_setup.salvar = original
            notas_setup._cache = None

    def test_alteracao_sem_disco_sobrevive_a_carregar(self):
        """Sem o cache alinhado, a nota editada sumia da lista na chamada
        seguinte — a versão velha do arquivo voltava por cima."""
        notas_setup.guardar(notas_setup.Nota(nome="BASE"))
        original = notas_setup.salvar
        notas_setup.salvar = lambda notas: False
        try:
            notas_setup.guardar(notas_setup.Nota(nome="SO NESTA SESSAO"))
            nomes = {n.nome for n in notas_setup.carregar()}
        finally:
            notas_setup.salvar = original
            notas_setup._cache = None
        self.assertIn("SO NESTA SESSAO", nomes)
        self.assertIn("BASE", nomes)


if __name__ == "__main__":
    unittest.main()


class TestAcervoDeNotas(_ComEnv):
    """Semear o acervo ``.docx``: o que é variante e o que é repetição."""

    VAR = notas_setup.PASTA_ENV
    PREFIXO = "acervo_"

    def _n(self, nome, acess="A", preparo=None):
        return notas_setup.Nota(nome=nome, acessorios=acess,
                                preparo=preparo or {})

    def test_deduplicar_tira_a_repetida_de_verdade(self):
        notas = [self._n("PELVE"), self._n("PELVE")]
        self.assertEqual(len(notas_setup.deduplicar(notas)), 1)

    def test_mesmo_nome_com_conteudo_diferente_e_variante(self):
        """A CT-RA deita o paciente de outro jeito: apagar uma delas some com
        uma montagem legítima, e quem procurar acha a errada com o nome certo."""
        notas = [self._n("TÓRAX", "Rampa B altura 4"),
                 self._n("TÓRAX", "Rampa B altura 3, braços elevados")]
        self.assertEqual(len(notas_setup.deduplicar(notas)), 2)

    def test_mesmo_conteudo_com_nome_diferente_e_regiao_diferente(self):
        """PRÓSTATA e COLO DE ÚTERO usam a mesma montagem — fundi-las deixaria
        quem procura pela região sem encontrar nada."""
        notas = [self._n("PRÓSTATA", "Travesseiro, apoio de joelho"),
                 self._n("COLO DE UTERO", "Travesseiro, apoio de joelho")]
        self.assertEqual(len(notas_setup.deduplicar(notas)), 2)

    def test_assinatura_ignora_grafia_mas_nao_conteudo(self):
        a = self._n("X", "  Rampa   15  ")
        b = self._n("X", "rampa 15")
        c = self._n("X", "Rampa 20")
        self.assertEqual(notas_setup._assinatura(a), notas_setup._assinatura(b))
        self.assertNotEqual(notas_setup._assinatura(a), notas_setup._assinatura(c))

    @unittest.skipUnless(notas_setup.pasta_do_acervo(), "acervo .docx ausente")
    def test_acervo_real_nao_perde_nota_por_nome_repetido(self):
        """Antes ficava "a primeira encontrada" e quatro notas da CT-RA sumiam
        em silêncio."""
        notas = notas_setup.semear()
        nomes = [n.nome for n in notas]
        self.assertEqual(len(nomes), len(set(nomes)))
        # As que colidiam ganharam a origem; as demais não foram carimbadas.
        com_origem = [n for n in nomes if n.endswith(")")]
        self.assertTrue(com_origem, "nenhuma variante foi desambiguada")
        self.assertLess(len(com_origem), len(nomes) // 2,
                        "carimbou a origem onde não havia ambiguidade")
