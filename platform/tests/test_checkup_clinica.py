"""O checkup que a clínica roda uma vez só — e o que ele não pode mentir.

Os casos aqui nasceram de defeitos de verdade, quase todos do próprio
relatório e não da rede: uma sonda que erra a medida é ruim, mas uma que
**relata errado** é pior, porque manda abrir chamado para consertar o que
estava na mão de quem rodou.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "tools"))

import checkup_clinica as ck  # noqa: E402
from isocentro.adaptadores.dicom import rede as dicom_rede  # noqa: E402
from tests import scp_falso  # noqa: E402


class CensoDoEstudo(unittest.TestCase):
    """Perguntar o tamanho da CT em vez de descobri-lo trazendo."""

    def test_conta_serie_por_modalidade(self):
        """A frente da CT foi orçada no escuro até isto existir.

        Sem o censo, saber quantos objetos a CT tem exigia trazer a CT — quer
        dizer, pagar a transferência inteira para decidir se valia a pena
        fazê-la. E o número muda o desenho: 150 objetos cabem no clique do
        usuário, 900 não.
        """
        series = (("CT", scp_falso.SERIE_CT, 312),
                  ("RTPLAN", "1.2.3.4.6", 1),
                  ("RTSTRUCT", "1.2.3.4.7", 1))
        with scp_falso.Servidor(series=series):
            achados = dicom_rede.censo_do_estudo(scp_falso.ESTUDO)
        por_modalidade = {a["modalidade"]: a["instancias"] for a in achados}
        self.assertEqual(por_modalidade["CT"], 312)
        self.assertEqual(por_modalidade["RTPLAN"], 1)

    def test_servidor_que_nao_conta_devolve_menos_um(self):
        """Zero e "não disse" são coisas diferentes, e confundi-las esconde a CT.

        ``NumberOfSeriesRelatedInstances`` é OPCIONAL no padrão. Servidor que
        não o preenche devolveria 0 se o campo virasse int às cegas — e uma CT
        de 300 cortes apareceria no relatório como série vazia, que é
        exatamente a leitura que faria alguém concluir que não há CT.
        """
        with scp_falso.Servidor(series=(("CT", scp_falso.SERIE_CT, None),)):
            achados = dicom_rede.censo_do_estudo(scp_falso.ESTUDO)
        self.assertEqual(achados[0]["instancias"], -1)

    def test_estudo_vazio_nao_e_erro(self):
        """Sem UID de estudo não se pergunta nada — e isso não é falha."""
        self.assertEqual(dicom_rede.censo_do_estudo(""), [])


class MoverPorSerie(unittest.TestCase):
    """A CT não se pede corte a corte."""

    def test_uma_associacao_traz_a_serie_inteira(self):
        """No nível de instância seriam 300 associações para o mesmo conjunto.

        E não é só lentidão: cada associação é uma chance de o servidor recusar
        por limite de conexões simultâneas — o desfecho que aparece só quando
        duas pessoas exportam ao mesmo tempo.
        """
        cortes = ("1.2.3.4.9.1", "1.2.3.4.9.2", "1.2.3.4.9.3")
        porta = scp_falso.porta_livre()
        with scp_falso.Servidor(escuta=porta, cortes=cortes,
                                series=(("CT", scp_falso.SERIE_CT, 3),)) as srv:
            destino = Path(self.enterContext(__import__("tempfile")
                                             .TemporaryDirectory()))
            with dicom_rede.receber(destino, porta) as recebido:
                concluidas, falhas = dicom_rede._mover_contando(
                    scp_falso.SERIE_CT, srv.ae_destino, nivel="SERIES")
        self.assertEqual(concluidas, 3)
        self.assertEqual(falhas, 0)
        self.assertEqual(len(recebido.arquivos), 3)
        # Um pedido só, e no nível de série: é a diferença que o teste guarda.
        pedidos = [p for p in srv.pedidos if p[0] == "move"]
        self.assertEqual(len(pedidos), 1)
        self.assertEqual(pedidos[0][1], f"serie:{scp_falso.SERIE_CT}")


class RelatorioNaoMente(unittest.TestCase):
    """O bloco final é o que vai para o chamado — e ele já se contradisse."""

    def test_falha_sem_pedido_sai_como_nossa(self):
        """Saía "Nada a pedir" com três FALHA na tela, dez linhas acima.

        Medido na primeira rodada de 10/09/2026: as variáveis de DICOM vazias
        falham e NÃO geram chamado (são configuração desta máquina), e o bloco
        do pedido só olhava para quem tinha texto de chamado. Quem lesse o fim
        do relatório — que é o que se lê — concluiria que estava tudo certo.
        """
        rel = ck.Relatorio()
        rel.medir("ISOCENTRO_DICOM_SERVIDOR", ck.FALHA, "vazio")
        ck.bloco_pedido(rel, ck.Config())
        texto = "\n".join(rel.linhas)
        self.assertIn("NOSSO", texto)
        self.assertIn("ISOCENTRO_DICOM_SERVIDOR", texto)
        # "Nada a pedir à TI" continua CERTO quando o que falhou é nosso — o
        # defeito era o relatório PARAR aí. O que o impede é a seção NOSSO vir
        # antes, e a frase estar qualificada ("que depende deles").
        self.assertLess(texto.index("NOSSO"), texto.index("Nada a pedir"))
        self.assertIn("depende deles", texto)

    def test_pedido_sai_separado_por_fase(self):
        """Pedir tudo junto faz o item caro segurar o barato.

        Cadastrar um AE Title sai no mesmo dia; liberar um banco clínico passa
        por aprovação. Num chamado só, o segundo atrasa o primeiro — e foi
        assim que a exportação automática esperou uma semana por uma linha de
        firewall.
        """
        rel = ck.Relatorio()
        rel.medir("C-ECHO", ck.FALHA, "recusado",
                  pedido="cadastrar o AE", fase=ck.AGORA)
        rel.medir("DWH.FactTreatmentHistory", ck.AVISO, "sem acesso",
                  pedido="dar SELECT", fase=ck.DEPOIS)
        ck.bloco_pedido(rel, ck.Config())
        texto = "\n".join(rel.linhas)
        self.assertIn("[AGORA]", texto)
        self.assertIn("[DEPOIS]", texto)
        self.assertLess(texto.index("[AGORA]"), texto.index("[DEPOIS]"))

    def test_tudo_passando_avisa_o_que_nao_foi_provado(self):
        """Relatório de UMA estação não prova nada sobre as outras.

        É a armadilha da rodada de 10/09/2026: o C-MOVE fechou o circuito
        nesta máquina, e "está funcionando" foi lido como "está funcionando na
        clínica" — quando a pergunta que decide isso (o cadastro amarra IP?)
        nem tinha sido feita.
        """
        rel = ck.Relatorio()
        rel.medir("C-ECHO", ck.OK, "respondeu")
        ck.bloco_pedido(rel, ck.Config())
        texto = "\n".join(rel.linhas)
        self.assertIn("OUTRA estação", texto)


class BlocoDasPastas(unittest.TestCase):
    """Permissão de share não se lê do lado do cliente: escreve-se."""

    def setUp(self):
        # Guardar e DEVOLVER, nunca ``del``: ``modulo.f = falsa`` grava no
        # ``__dict__`` do módulo, e o ``del`` depois some com a original para o
        # resto do processo.
        self._original = ck._pastas_do_app
        self.addCleanup(setattr, ck, "_pastas_do_app", self._original)

    def test_pasta_que_le_e_nao_escreve_vira_pedido(self):
        """Listar e escrever são permissões diferentes, e o share concede uma.

        A pasta abre, lista, parece certa — e recusa a criação do arquivo. O
        primeiro a descobrir seria o físico salvando a ficha com o paciente na
        mesa, e o erro chegaria como "não foi possível salvar".
        """
        import tempfile

        pasta = Path(self.enterContext(tempfile.TemporaryDirectory()))
        somente_leitura = pasta / "trancada"
        somente_leitura.mkdir()

        def _falsa():
            return [("compartilhada (grava)", somente_leitura, True, "")]

        ck._pastas_do_app = _falsa
        rel = ck.Relatorio()

        original_write = Path.write_text

        def _recusa(self, *a, **k):
            if self.parent == somente_leitura:
                raise PermissionError("Acesso negado")
            return original_write(self, *a, **k)

        Path.write_text = _recusa
        try:
            ck.bloco_pastas(rel, ck.Config())
        finally:
            Path.write_text = original_write

        pedidos = [a.pedido for a in rel.achados if a.pedido]
        self.assertTrue(pedidos)
        self.assertIn("ESCRITA", pedidos[0])

    def test_o_arquivo_de_teste_nao_fica_para_tras(self):
        """Sonda que suja a pasta do serviço é sonda que ninguém deixa rodar.

        A pasta medida aqui é a mesma em que o app grava o índice central e as
        correções — um arquivo estranho ali vira dúvida na próxima varredura.
        """
        import tempfile

        pasta = Path(self.enterContext(tempfile.TemporaryDirectory()))

        def _falsa():
            return [("de trabalho (grava)", pasta, True, "")]

        ck._pastas_do_app = _falsa
        ck.bloco_pastas(ck.Relatorio(), ck.Config())
        self.assertEqual(list(pasta.iterdir()), [])


class EscritaAtomicaEmShare(unittest.TestCase):
    """Criar arquivo e SUBSTITUIR arquivo são permissões diferentes em SMB."""

    def test_share_que_cria_mas_nao_substitui_vira_pedido(self):
        """Permissão de criar sem permissão de apagar deixa o índice pela metade.

        O app nunca escreve por cima: grava num temporário ao lado e substitui,
        para que desligar a estação no meio não corrompa o índice central. Num
        share que conceda criar e negue apagar, a escrita do temporário passa e
        a troca falha — e o sintoma é um `.tmp` acumulando ao lado do índice,
        sem erro nenhum na tela. O teste de escrita simples não pega isto: ele
        só cria.
        """
        import os
        import tempfile

        pasta = Path(self.enterContext(tempfile.TemporaryDirectory()))
        rel = ck.Relatorio()
        original = os.replace

        def _recusa(origem, destino):
            raise PermissionError("Acesso negado")

        os.replace = _recusa
        try:
            ck._escrita_de_verdade(rel, "índice (grava)", pasta, unc=True)
        finally:
            os.replace = original

        achado = rel.achados[0]
        self.assertEqual(achado.estado, ck.FALHA)
        self.assertIn("APAGAR", achado.pedido)
        # E não deixa lixo nem quando falha: a pasta medida é a do índice.
        self.assertEqual(list(pasta.iterdir()), [])

    def test_caminho_longo_de_share_avisa_antes_do_nome_do_paciente(self):
        """260 caracteres estouram só para ALGUNS pacientes — e é o pior defeito.

        A pasta de simulação leva nome de paciente, e em UNC o prefixo já come
        dezenas de caracteres antes de o nome começar. O erro é "caminho não
        encontrado" numa pasta que existe, e só para os nomes mais compridos —
        o tipo de coisa em que ninguém acredita na primeira vez que ouve. O
        aviso tem de sair ANTES, com a conta de quantos caracteres sobram.
        """
        import tempfile

        raiz = Path(self.enterContext(tempfile.TemporaryDirectory()))
        # Uma pasta de verdade, funda o bastante para passar do limiar: medir
        # sobre um caminho inventado não provaria que a pasta ainda escreve.
        funda = raiz
        while len(str(funda)) <= 150:
            funda = funda / "pasta_de_simulacao"
        funda.mkdir(parents=True)

        rel = ck.Relatorio()
        ck._escrita_de_verdade(rel, "simulações", funda, unc=True)
        comprimento = [a for a in rel.achados if "comprimento" in a.rotulo]
        self.assertTrue(comprimento, [a.rotulo for a in rel.achados])
        self.assertIn("sobram", comprimento[0].detalhe)

        # Em disco local o limiar não vale a mesma coisa: o caminho é curto por
        # natureza e o aviso viraria ruído em toda rodada de desenvolvimento.
        rel_local = ck.Relatorio()
        ck._escrita_de_verdade(rel_local, "simulações", funda, unc=False)
        self.assertFalse([a for a in rel_local.achados
                          if "comprimento" in a.rotulo])


class BlocoDaAssociacao(unittest.TestCase):
    """'calling' e 'called' pedem providências opostas."""

    def test_ae_chamador_recusado_pede_cadastro_sem_amarrar_ip(self):
        """O pedido precisa dizer "sem amarrar IP", ou volta um chamado por estação.

        Todas as estações abrem o MESMO ``.exe`` de um share — mas ``.exe`` em
        share roda na máquina de quem abre, e cada uma chama do próprio
        endereço. Cadastro amarrado a um IP é um chamado por estação, para
        sempre. Isto já saiu ao contrário duas vezes na documentação.
        """
        rel = ck.Relatorio()
        original = dicom_rede.verificar

        def _recusa():
            raise dicom_rede.FalhaDeRede(
                "associação RECUSADA — Calling AE title not recognised")

        with scp_falso.Servidor():
            dicom_rede.verificar = _recusa
            try:
                ck.bloco_dicom_associacao(rel, ck.Config())
            finally:
                dicom_rede.verificar = original
        pedidos = [a.pedido for a in rel.achados if a.pedido]
        self.assertTrue(any("SEM amarrar" in p for p in pedidos), pedidos)

    def test_ae_chamado_errado_nao_vira_chamado(self):
        """Nome do ARIA errado é NOSSO: resolve-se trocando um parâmetro.

        Abrir chamado para isto gasta uma ida e devolve "está tudo certo do
        nosso lado" — que é verdade, e não ajuda ninguém.
        """
        rel = ck.Relatorio()
        original = dicom_rede.verificar

        def _recusa():
            raise dicom_rede.FalhaDeRede(
                "associação RECUSADA — Called AE title not recognised")

        with scp_falso.Servidor():
            dicom_rede.verificar = _recusa
            try:
                ck.bloco_dicom_associacao(rel, ck.Config())
            finally:
                dicom_rede.verificar = original
        pedidos = [a.pedido for a in rel.achados if a.pedido]
        self.assertTrue(any("confirmar o AE Title" in p for p in pedidos),
                        pedidos)


class BlocoDoCircuito(unittest.TestCase):
    """O que o produto faz, ponta a ponta — e sem identidade no relatório."""

    def test_traz_o_conjunto_e_nao_imprime_paciente(self):
        """O relatório vai para arquivo, e este repositório já esteve público.

        O ``sondar_dicom.py`` imprime o registro do paciente no relatório dele,
        e por isso o ``.gitignore`` tem uma linha só para o arquivo daquela
        ferramenta. Aqui a regra é não gerar o problema: modalidade e contagem
        respondem tudo o que o bloco precisa responder.
        """
        import tempfile

        porta = scp_falso.porta_livre()
        destino = Path(self.enterContext(tempfile.TemporaryDirectory()))
        doses = ((scp_falso.UID_DOSE, scp_falso.UID),)
        with scp_falso.Servidor(escuta=porta, doses=doses):
            rel = ck.Relatorio()
            ck.bloco_dicom_circuito(
                rel, ck.Config(uid=scp_falso.UID, pasta=str(destino)))
        texto = "\n".join(rel.linhas)
        self.assertIn("RTPLAN×1", texto)
        self.assertNotIn("9000019ANA", texto)
        self.assertNotIn("Oliveira", texto)

    def test_nada_chegou_vira_pedido_de_conferir_o_destino(self):
        """"0 objeto(s), 1 falha" depois de 21 s não diz de quem é a culpa.

        Medido em 10/09/2026: o pedido é ACEITO, o ARIA abre a conexão de volta
        e não acha ninguém — e o resumo sai idêntico ao de destino inexistente.
        O relatório tem de dizer o que conferir, na ordem, ou a próxima estação
        repete a mesma manhã.
        """
        import tempfile

        porta = scp_falso.porta_livre()
        destino = Path(self.enterContext(tempfile.TemporaryDirectory()))
        # Destino que o servidor NÃO reconhece: nada chega.
        with scp_falso.Servidor(escuta=porta, ae_destino="OUTRO"):
            os.environ["ISOCENTRO_DICOM_AE_DESTINO"] = "NAO_CADASTRADO"
            rel = ck.Relatorio()
            ck.bloco_dicom_circuito(
                rel, ck.Config(uid=scp_falso.UID, pasta=str(destino)))
        texto = "\n".join(rel.linhas)
        self.assertIn(ck.FALHA, [a.estado for a in rel.achados])
        self.assertTrue(any("AE de destino" in (a.pedido or "")
                            or "destino" in (a.detalhe or "")
                            for a in rel.achados), texto)


class FirewallNaoContradizOCircuito(unittest.TestCase):
    """O bloco 7 lê regras; o bloco 8 mede o resultado. Vale o bloco 8."""

    def test_circuito_que_entrega_retira_o_pedido_de_firewall(self):
        """O relatório pedia liberação de porta ao lado de um C-MOVE que entregou.

        Medido no ensaio de 10/09/2026: a leitura das regras de firewall não
        enxerga regra de política de grupo, regra de domínio, nem o caso em que
        a origem já é confiável — e devolvia "nenhuma regra allow" logo acima
        de três arquivos recebidos. Chamado que pede o que já existe queima a
        credibilidade dos outros itens da mesma lista.
        """
        import tempfile

        porta = scp_falso.porta_livre()
        destino = Path(self.enterContext(tempfile.TemporaryDirectory()))
        rel = ck.Relatorio()
        # O achado como o bloco 7 o deixa quando não acha regra de permissão.
        rel.medir(f"entrada liberada na {porta}", ck.AVISO, "nenhuma regra allow",
                  pedido="liberar a ENTRADA TCP", fase=ck.PRODUCAO)
        with scp_falso.Servidor(escuta=porta):
            ck.bloco_dicom_circuito(
                rel, ck.Config(uid=scp_falso.UID, pasta=str(destino)))
        firewall = [a for a in rel.achados
                    if a.rotulo.startswith("entrada liberada")][0]
        self.assertEqual(firewall.estado, ck.OK)
        self.assertEqual(firewall.pedido, "")


class OQueOPython01Mostrou(unittest.TestCase):
    """Os quatro defeitos que só a primeira rodada de verdade revelou."""

    def test_servidor_que_nao_conta_nao_vira_estudo_vazio(self):
        """O ARIA desta clínica NÃO preenche NumberOfSeriesRelatedInstances.

        Medido no clinica-python01 em 10/09/2026: o censo devolveu sete
        modalidades — CT, RTPLAN, RTSTRUCT, RTDOSE, RTIMAGE, REG e PLAN — e
        "0 objeto(s)" em todas, porque a soma convertia o -1 ("não disse") em
        zero. Lido de fora, um estudo vazio; e a decisão que dependia disso era
        o orçamento da frente da CT.
        """
        series = (("CT", scp_falso.SERIE_CT, None),
                  ("RTPLAN", "1.2.3.4.6", None))
        with scp_falso.Servidor(series=series, cortes=("1.2.3.4.9.1",)):
            rel = ck.Relatorio()
            ck.bloco_dicom_consulta(rel, ck.Config(uid=scp_falso.UID))
        censo = [a for a in rel.achados if a.rotulo == "censo do estudo"][0]
        self.assertNotIn("0 objeto(s)", censo.detalhe)
        self.assertIn("não informou", "\n".join(rel.linhas).lower())

    def test_conta_um_a_um_quando_o_servidor_nao_conta(self):
        """Contar custa uma associação; descobrir trazendo custa a CT inteira."""
        cortes = tuple(f"1.2.3.4.9.{n}" for n in range(1, 8))
        with scp_falso.Servidor(series=(("CT", scp_falso.SERIE_CT, None),),
                                cortes=cortes):
            quantas = dicom_rede.contar_instancias(scp_falso.SERIE_CT)
        self.assertEqual(quantas, 7)

    def test_sem_ae_de_destino_diz_o_que_se_sabe(self):
        """Saía "associação RECUSADA — No reason given", que não diz nada.

        Sem AE de destino, `trazer` cai no C-GET — que este daemon não faz, e
        isso está MEDIDO desde 10/09/2026 com seis variantes de associação. O
        relatório do clinica-python01 gastou o bloco mais importante para
        redescobrir, com uma recusa muda, o que já estava escrito.
        """
        with scp_falso.Servidor():
            rel = ck.Relatorio()
            ck.bloco_dicom_circuito(rel, ck.Config(uid=scp_falso.UID))
        achado = rel.achados[0]
        self.assertEqual(achado.estado, ck.NAO)
        self.assertIn("C-GET", achado.detalhe)
        self.assertIn("--ae-destino", "\n".join(rel.linhas))

    def test_sem_ae_de_destino_nao_pede_a_ti_o_que_ja_existe(self):
        """A rodada sem argumentos pedia à TI para cadastrar o AE de destino.

        Foi no python01, 11/09/2026, 13:44: o "PARA A TI" listava "cadastrar o
        AE de destino" — e o `RADIOTERAFICHA` estava cadastrado desde 10/09. O
        que faltava era `--ae-destino` na linha de comando, e item de chamado
        que a TI já fez faz duvidar dos outros da mesma lista.
        """
        porta = scp_falso.porta_livre()
        originais = (ck._ps, ck._ip_de_saida)
        # O firewall e o IP de saída não interessam aqui, e o PowerShell de
        # verdade custa segundos por chamada.
        ck._ps = lambda *a, **k: ""
        ck._ip_de_saida = lambda *a, **k: ""
        try:
            with scp_falso.Servidor():
                rel = ck.Relatorio()
                ck.bloco_dicom_receptor(rel, ck.Config(porta_escuta=porta))
                ck.bloco_dicom_circuito(rel, ck.Config(uid=scp_falso.UID))
                ck.bloco_pedido(rel, ck.Config())
        finally:
            ck._ps, ck._ip_de_saida = originais
        texto = "\n".join(rel.linhas)
        # A seção existe (o firewall falso gera pedido): sem esta conferência,
        # um relatório sem "PARA A TI" passaria nas duas de baixo por vazio.
        self.assertIn("PARA A TI", texto)
        para_a_ti = texto.partition("PARA A TI")[2]
        self.assertNotIn("cadastrar", para_a_ti.lower(), texto)
        self.assertNotIn("AE de destino", para_a_ti, texto)
        self.assertFalse([a for a in rel.achados
                          if "destino" in a.rotulo.lower() and a.pedido])
        self.assertIn(f"--ae-destino {ck.AE_DESTINO_CADASTRADO}", texto)
        # O destino amarra IP: mandar repetir sem dizer isso é mandar o dado do
        # paciente para a máquina cadastrada, com "NADA chegou" nesta.
        self.assertIn("aponta para UMA máquina", texto)
        self.assertEqual(ck.AE_DESTINO_CADASTRADO, "RADIOTERAFICHA")

    def test_impressora_ausente_nao_vira_chamado_sozinha(self):
        """No clinica-python01 entrou "instalar a impressora da sala" no chamado.

        É máquina de apoio: não imprime ficha nenhuma. Item que a TI lê e não
        entende faz duvidar dos outros da mesma lista — e quem sabe se ESTA
        máquina imprime é quem está rodando, não a sonda.
        """
        rel = ck.Relatorio()
        original = ck._ps
        ck._ps = lambda *a, **k: ""
        try:
            ck.bloco_impressao(rel, ck.Config())
        finally:
            ck._ps = original
        self.assertFalse([a for a in rel.achados if a.pedido])


class ConsoleDaClinica(unittest.TestCase):
    """O executável não tem `.bat` ao lado para arrumar a code page."""

    def test_console_cp1252_nao_derruba_o_relatorio(self):
        """Três blocos morreram assim no primeiro exe gerado, em 10/09/2026.

        O console do Windows abre em code page 850 e o Python escolhe cp1252
        para a saída; "ã" já basta. No `.bat` isso era `chcp 65001` mais
        `PYTHONIOENCODING` — e o `.bat` é justamente o que não existe na
        clínica, que foi o motivo de o checkup virar executável.

        O relatório saía pela metade, e cada bloco morria sozinho com
        `estourou: UnicodeEncodeError` — o que se parece com defeito de rede
        para quem está lendo na estação.
        """
        import io

        cru = io.BytesIO()
        # `strict` de propósito: é o comportamento do console real, e com
        # `replace` aqui o teste passaria mesmo sem a correção.
        console = io.TextIOWrapper(cru, encoding="cp1252", errors="strict")
        original = sys.stdout
        sys.stdout = console
        try:
            codigo = ck.main(["--pular", "banco,dicom,impressao,pastas",
                              "--sem-padrao", "-o", ""])
        finally:
            sys.stdout.flush()
            sys.stdout = original

        texto = cru.getvalue().decode("utf-8", errors="replace")
        self.assertIn("configuração", texto)
        self.assertIn("O que falta", texto)
        self.assertIn(codigo, (0, 1))


class DegrauDeBaixo(unittest.TestCase):
    """Recusa e silêncio são causas diferentes, e o TIPO do erro as separa.

    As duas saíam como "fechada", e a providência de cada uma é oposta: mandar
    procurar firewall onde o serviço está parado custa a ida seguinte inteira.

    A primeira versão separava pelo relógio (recusa = voltou antes de 80% do
    prazo). A recusa no Windows leva 2,04 s, porque a pilha repete o SYN depois
    do RST; a folha era de 0,36 s, e uma VPN a comia. Por isso estes testes não
    vão à pilha: o que se fixa é a leitura do tipo, e com a pilha de verdade o
    teste da recusa pagava os 2 s e o do firewall nem existia.
    """

    def _tentar(self, exc):
        with scp_falso.conexao_que_falha(exc):
            return ck._tcp_aberta("srvariadb", 51404, prazo=3.0)

    def test_recusa_nao_e_firewall_mesmo_devagar(self):
        aberta, jeito = self._tentar(ConnectionRefusedError(10061, "recusou"))
        self.assertFalse(aberta)
        self.assertIn("não há serviço", jeito)
        self.assertNotIn("firewall", jeito)

    def test_silencio_ate_o_prazo_e_assinatura_de_firewall(self):
        aberta, jeito = self._tentar(TimeoutError("timed out"))
        self.assertFalse(aberta)
        self.assertIn("assinatura de firewall", jeito)

    def test_outro_erro_de_rede_nao_vira_palpite(self):
        """Nome que não resolve e rede inalcançável não são recusa nem
        firewall. Enfiá-los numa das duas gavetas mandaria ligar para a pessoa
        errada; o texto do próprio erro diz mais que qualquer palpite."""
        aberta, jeito = self._tentar(OSError(10065, "host inalcançável"))
        self.assertFalse(aberta)
        self.assertNotIn("firewall", jeito)
        self.assertNotIn("não há serviço", jeito)
        self.assertIn("host inalcançável", jeito)

    def test_o_socket_de_verdade_volta_depois(self):
        """O dublê troca ``socket.socket`` do processo inteiro — e o SCP de
        mentira dos outros testes abre socket por ele."""
        import socket
        original = socket.socket
        self._tentar(TimeoutError())
        self.assertIs(socket.socket, original)


if __name__ == "__main__":
    unittest.main()
