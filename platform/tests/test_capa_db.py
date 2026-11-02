"""Leitura da capa pelo data warehouse — e a queda para os relatórios.

O banco resolve dois problemas que já morderam: o agendador que falha e deixa a
capa vazia, e as janelas de período independentes dos dois CSV (numa exportação
real, 599 pacientes de cadastro contra 13 080 de prescrições).

Mas o banco não pode virar uma dependência dura: se ele cai no meio do
expediente, a capa tem de continuar saindo pelos arquivos. É isso que a maioria
destes testes fixa.

A conexão aqui é de mentira. O mapeamento contra o banco de verdade foi
conferido à mão (ver NOTAS.md) e é reconferido pelo comparador
``tools/comparar_fontes.py``; o que se testa aqui é a TRADUÇÃO das linhas em
campos da capa, que é onde mora o erro silencioso.

Rodar:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from isocentro.dados import ambiente  # noqa: E402
from isocentro.banco import banco_local  # noqa: E402
from isocentro.banco import capa_dados  # noqa: E402
from isocentro.banco import capa_db  # noqa: E402


class _Cursor:
    """Cursor de mentira: casa a consulta por um pedaço do texto dela."""

    def __init__(self, respostas: dict):
        self._respostas = respostas
        self._linhas: list = []

    def execute(self, sql, *params):
        for marca, linhas in self._respostas.items():
            if marca in sql:
                self._linhas = linhas(*params) if callable(linhas) else linhas
                return self
        self._linhas = []
        return self

    def fetchall(self):
        return self._linhas


class _Conexao:
    def __init__(self, respostas: dict):
        self._respostas = respostas
        self.fechada = False

    def cursor(self):
        return _Cursor(self._respostas)

    def close(self):
        self.fechada = True


def _devolver(antes: dict) -> None:
    """Devolve cada variável ao valor que tinha (``None`` = não existia).

    Variável de ambiente é estado do PROCESSO: o que ficar mexido aqui vaza
    para os próximos arquivos da suíte, e é assim que a ordem dos testes passa
    a importar. Mesmo motivo de nunca fazer ``del modulo.funcao``.
    """
    for nome, valor in antes.items():
        if valor is None:
            os.environ.pop(nome, None)
        else:
            os.environ[nome] = valor


class _ComBanco(unittest.TestCase):
    """Aponta o ``capa_db`` para uma conexão de mentira."""

    RESPOSTAS: dict = {}

    def setUp(self):
        self._env = os.environ.get(capa_db.ENV_SERVIDOR)
        # Tirar TAMBÉM o nome NOVO da variável: desde 09/09/2026 o ``capa_db``
        # lê pelo ``ambiente.ler``, e o ``ISOCENTRO_DB_SERVIDOR`` da
        # estação vence o que este ``setUp`` acabou de gravar. Sem isto o teste
        # falharia só na máquina que já migrou o nome — vermelho por motivo
        # ambiental, que é o pior modo de um teste falhar.
        self._env_novo = os.environ.pop(
            ambiente.nome_novo(capa_db.ENV_SERVIDOR), None)
        os.environ[capa_db.ENV_SERVIDOR] = "SERVIDOR-DE-TESTE"
        self._conexao = capa_db.conexao
        capa_db.conexao = lambda: _Conexao(self.RESPOSTAS)

    def tearDown(self):
        capa_db.conexao = self._conexao
        _devolver({capa_db.ENV_SERVIDOR: self._env,
                   ambiente.nome_novo(capa_db.ENV_SERVIDOR): self._env_novo})
        capa_db.esquecer()


class _Data:
    """Um datetime pequeno — o driver devolve objeto, não texto."""

    def __init__(self, texto):
        self._texto = texto

    def strftime(self, _fmt):
        return self._texto


_CADASTRO_OK = {
    "FROM DWH.DimPatient p": [(
        "9000001CEL", "SICRANA, JOANA HELENA FELIPE DE",
        _Data("15/06/1970"), "Feminino", "62 90000-0000", 8711)],
    "DWH.FactPatientPayor": [("Unimed", "0064800000542300")],
    # (DimCourseID, CourseId, intenção) — o ID entrou quando a máquina passou
    # a ser a DO CURSO, e não a da última sessão do paciente.
    "FROM DWH.DimCourse c": [(4242, "C2 JANEIRO 24", "Pós-op.")],
    "DWH.FactPatientDiagnosis fd": [
        ("C34.2", "Neoplasia maligna do lobo médio, brônquio ou pulmão")],
    "DWH.DimPatientDoctor pd": [("Thais de Toledo Lima Saldanha",)],
}


class TestCadastro(_ComBanco):

    RESPOSTAS = _CADASTRO_OK

    def test_traz_a_capa_inteira(self):
        c = capa_db.cadastro_do_paciente("9000001CEL")
        self.assertEqual(c.registro, "9000001CEL")
        self.assertEqual(c.nascimento, "15/06/1970")
        self.assertEqual(c.sexo, "Feminino")
        self.assertEqual(c.contato, "62 90000-0000")
        self.assertEqual(c.convenio, "Unimed - 0064800000542300")
        self.assertEqual(c.curso, "C2 JANEIRO 24")
        self.assertEqual(c.intencao, "Pós-op.")
        self.assertEqual(c.cid, "C34.2")
        self.assertIn("brônquio", c.descricao)
        self.assertIn("Thais", c.medico)

    def test_o_nome_vem_desinvertido_e_na_grafia_do_app(self):
        """O banco guarda "SICRANA, JOANA…" EM CAIXA ALTA; a capa imprime direto.

        Até 25/08/2026 a caixa não se mexia — e a mesma pessoa saía "JOANA
        HELENA…" na capa e "Joana Helena…" na ficha grampeada ao lado, porque
        cada porta de entrada grafa do seu jeito. A partícula, que era o medo
        ("De", "Da"), é justamente o que ``como_nome_proprio`` resolve.
        """
        c = capa_db.cadastro_do_paciente("9000001CEL")
        self.assertEqual(c.nome, "Joana Helena Felipe de Sicrana")

    def test_o_cid_ja_vem_separado_do_diagnostico(self):
        """No CSV os dois vinham colados ("C61 Neoplasia…") e um regex tinha de
        desfazer. No banco são colunas distintas — uma fonte de erro a menos."""
        c = capa_db.cadastro_do_paciente("9000001CEL")
        self.assertEqual(c.cid, "C34.2")
        self.assertNotIn("C34.2", c.descricao)

    def test_registro_vazio_nao_consulta(self):
        self.assertIsNone(capa_db.cadastro_do_paciente(""))
        self.assertIsNone(capa_db.cadastro_do_paciente("   "))


class TestMaquinaDoCurso(_ComBanco):
    """O paciente pode ter mais de um curso ATIVO ao mesmo tempo.

    A consulta por PACIENTE devolvia a máquina da última sessão tratada — a do
    curso antigo, enquanto o curso novo ainda não começou. A capa do curso novo
    saía mandando posicionar no acelerador do outro tratamento, e é a capa que
    vai grampeada na ficha para a sala.
    """

    RESPOSTAS = dict(_CADASTRO_OK, **{
        # A consulta do curso escolhe o mais recente; a máquina passa a ser
        # perguntada COM esse curso no WHERE.
        "th.DimCourseID = ?": lambda _pac, curso: (
            [("TBuniverSN1002",)] if curso == 4242 else [("600CD",)]),
        # A pergunta antiga, sem curso, responderia a máquina do curso VELHO.
        # Vem DEPOIS de propósito: o cursor de mentira casa o primeiro marcador
        # que servir, e os dois SQL começam iguais.
        "DWH.FactTreatmentHistory th": [("6EX",)],
    })

    def test_a_maquina_e_a_do_curso_da_capa(self):
        c = capa_db.cadastro_do_paciente("9000001CEL")
        self.assertEqual(c.curso, "C2 JANEIRO 24")
        self.assertEqual(c.maquina, "TBuniverSN1002")


class TestMaquinaSemCurso(_ComBanco):
    """Curso recém-criado ainda não tem linha de máquina no histórico.

    Aí vale a do paciente: capa sem máquina é pior que capa com a máquina do
    curso anterior — nesta há o que conferir, naquela não há nada.
    """

    RESPOSTAS = dict(_CADASTRO_OK, **{
        "th.DimCourseID = ?": [],
        "FROM DWH.FactTreatmentHistory th": [("6EX",)],
    })

    def test_cai_para_a_maquina_do_paciente(self):
        self.assertEqual(capa_db.cadastro_do_paciente("9000001CEL").maquina,
                         "6EX")


class TestOQueONaoSeSabe(_ComBanco):
    """"NA" é como o data warehouse escreve "não informado"."""

    RESPOSTAS = {
        "FROM DWH.DimPatient p": [(
            "9000026XX", "SEM, Dados", None, None, "NA", 1)],
    }

    def test_na_e_nulo_viram_vazio_nunca_texto(self):
        """Imprimir "NA" ou "None" na capa é pior que deixar o campo em branco:
        parece dado, e ninguém confere o que parece preenchido."""
        c = capa_db.cadastro_do_paciente("9000026XX")
        self.assertEqual(c.sexo, "")
        self.assertEqual(c.contato, "")
        self.assertEqual(c.nascimento, "")
        self.assertEqual(c.convenio, "")
        self.assertEqual(c.cid, "")

    def test_sexo_desconhecido_nao_vira_outro(self):
        """``DimLookupID = 0`` é o "NA" do banco. Sexo sem fonte nasce VAZIO e a
        tela pede que alguém confira — a capa não afirma o que ninguém viu."""
        c = capa_db.cadastro_do_paciente("9000026XX")
        self.assertEqual(c.sexo, "")


class TestPacienteAusente(_ComBanco):

    RESPOSTAS = {}

    def test_sem_linha_devolve_none_e_nao_cadastro_vazio(self):
        """São coisas diferentes: ``None`` é "não deu para saber" e manda o app
        procurar nos CSV; um cadastro vazio diria "achei, e não tem nada"."""
        self.assertIsNone(capa_db.cadastro_do_paciente("0000000XX"))


class TestFoto(_ComBanco):

    _JPEG = b"\xff\xd8\xff\xe0" + b"foto" * 40

    RESPOSTAS = {"DWH.DimPatientPhoto": [(_JPEG,)]}

    def test_traz_o_jpeg(self):
        self.assertEqual(capa_db.foto_do_paciente("9000001CEL"), self._JPEG)

    def test_blob_que_nao_e_imagem_vira_sem_foto(self):
        """Blob truncado viraria um retângulo quebrado na capa impressa."""
        capa_db.conexao = lambda: _Conexao(
            {"DWH.DimPatientPhoto": [(b"isto nao e imagem",)]})
        self.assertIsNone(capa_db.foto_do_paciente("9000001CEL"))


class TestPrescricoes(_ComBanco):

    RESPOSTAS = {
        "FROM (SELECT DISTINCT DimPrescriptionID": [(
            "Mama E 40.05Gy@15fx", "Breast, Left", "C1 JUL 26", "15",
            _Data("10/07/2026"), "medico.exemplo", 555,
            "9000001CEL", "SICRANA, JOANA")],
        "DWH.DimPrescriptionAnatomy": [
            ("VOLUME ID", "PTV mama", None),
            ("VOLUME ID", "PTV FSC", None),
            ("TOTAL DOSE", "40.05", "Gy"),
            ("TOTAL DOSE", "40.05", "Gy"),
            ("DOSE PER FRACTION", "2.67", "Gy"),
            ("DOSE PER FRACTION", "2.67", "Gy"),
        ],
        "DWH.DimPrescriptionProperty": [("ONCE DAILY",)],
        "SELECT TOP 1 Notes": [("Estadiamento IIA — após QT neoadjuvante",)],
    }

    def test_monta_o_bloco_da_capa(self):
        pres = capa_db.prescricoes_do_paciente("9000001CEL")
        self.assertEqual(len(pres), 1)
        p = pres[0]
        self.assertEqual(p.fracoes, "15")
        self.assertEqual(p.data_aprovacao, "10/07/2026")
        self.assertEqual(p.curso, "C1 JUL 26")

    def test_dose_sai_em_cgy(self):
        """A capa imprime cGy; o banco guarda Gy. 40.05 Gy = 4005 cGy."""
        v = capa_db.prescricoes_do_paciente("9000001CEL")[0].volumes
        self.assertEqual(len(v), 2, "os dois alvos entraram")
        self.assertEqual(v[0].nome, "PTV mama")
        self.assertEqual(v[0].dose_cgy, "4005")
        self.assertEqual(v[0].dose_frac_cgy, "267")

    def test_site_e_frequencia_saem_em_portugues(self):
        p = capa_db.prescricoes_do_paciente("9000001CEL")[0]
        self.assertEqual(p.site, "Mama, esquerda")
        self.assertEqual(p.frequencia, "Uma Vez por Dia")

    def test_a_nota_do_radioterapeuta_entra_no_bloco(self):
        """O campo existia na capa e na tela, mas nascia SEMPRE vazio: nem o
        CSV nem o banco a traziam, e só restava redigitar o que o ARIA já
        sabe. Mora em ``DimPrescription.Notes`` (sonda de 23/09/2026)."""
        p = capa_db.prescricoes_do_paciente("9000001CEL")[0]
        self.assertEqual(p.notas, "Estadiamento IIA — após QT neoadjuvante")


class TestPrescricaoSemNota(_ComBanco):
    """Prescrição sem nota é o caso comum: o campo fica vazio, não some."""

    RESPOSTAS = {
        "FROM (SELECT DISTINCT DimPrescriptionID": [(
            "Pelve 25Gy@5fx", "Pelvis", "C1 SET 26", "5",
            _Data("01/09/2026"), "medico.exemplo", 777,
            "9000001CEL", "SICRANA, JOANA")],
    }

    def test_sem_linha_de_nota_o_campo_fica_vazio(self):
        self.assertEqual(
            capa_db.prescricoes_do_paciente("9000001CEL")[0].notas, "")


class TestNotaQueFalha(_ComBanco):
    """A nota é complemento do bloco: perder a capa inteira por causa dela
    seria trocar um campo em branco por nenhuma folha."""

    def test_falha_de_leitura_devolve_vazio(self):
        original = capa_db._consultar

        def _explode(*_a, **_k):
            raise capa_db.FalhaDeLeitura("sem conexão")

        capa_db._consultar = _explode
        try:
            self.assertEqual(capa_db._notas(555), "")
        finally:
            # GUARDA E DEVOLVE — nunca ``del``.
            capa_db._consultar = original


class TestBancoDesligado(unittest.TestCase):
    """Sem servidor apontado, o módulo inteiro fica fora do caminho."""

    def setUp(self):
        # Tirar a variavel NAO basta para "nao ha banco apontado", e essa foi a
        # armadilha: o ``capa_db._config`` cai no ``config_servico.json``, que
        # NESTA estacao aponta o SRVINSIGHT — ``configurado()`` continuava
        # verdadeiro e a classe inteira falhava. Passava em maquina limpa e
        # falhava em maquina usada, que e o pior modo de um teste falhar:
        # vermelho por motivo ambiental e o ``/pronto`` mentindo uma vez por
        # sessao. Pasta de configuracao VAZIA e o idioma ja usado no
        # ``test_capa_espelho.py`` e no ``test_tratamento.py``.
        self._env = os.environ.pop(capa_db.ENV_SERVIDOR, None)
        # A quarta porta, aberta em 09/09/2026 junto com a correção: o
        # ``capa_db`` passou a enxergar o nome NOVO, então tirar só o antigo
        # deixaria o banco apontado numa estação que já migrou.
        self._env_novo = os.environ.pop(
            ambiente.nome_novo(capa_db.ENV_SERVIDOR), None)
        self._cfg = os.environ.get("ISOCENTRO_CONFIG")
        self._cfg_vazia = tempfile.mkdtemp(prefix="cfg_vazia_")
        os.environ["ISOCENTRO_CONFIG"] = self._cfg_vazia
        # O terceiro caminho para ``configurado()``: ``servidor() or
        # banco_local.ligado()``. Uma estacao que rodou o ``gravar_banco.py``
        # tem o arquivo em disco, e sem tirar isto o teste voltaria a falhar
        # so nela — mesmo defeito, outra porta.
        self._env_local = os.environ.pop(banco_local.ENV, None)
        self._env_local_novo = os.environ.pop(
            ambiente.nome_novo(banco_local.ENV), None)
        capa_db.esquecer()

    def tearDown(self):
        # Guardar e DEVOLVER, sempre: variavel de ambiente e estado do
        # PROCESSO, e o que ficar mexido aqui vaza para os proximos arquivos
        # da suite — que e como a ordem dos testes passa a importar.
        for nome, valor in (
                (capa_db.ENV_SERVIDOR, self._env),
                (ambiente.nome_novo(capa_db.ENV_SERVIDOR), self._env_novo),
                ("ISOCENTRO_CONFIG", self._cfg),
                (banco_local.ENV, self._env_local),
                (ambiente.nome_novo(banco_local.ENV), self._env_local_novo)):
            if valor is None:
                os.environ.pop(nome, None)
            else:
                os.environ[nome] = valor
        # O ``test_config_servico`` ja deixou 1240 pastas no %TEMP% desta
        # estacao por nao limpar. ``ignore_errors`` porque pasta temporaria
        # presa no antivirus nao pode reprovar o teste.
        shutil.rmtree(self._cfg_vazia, ignore_errors=True)
        capa_db.esquecer()

    def test_nao_configurado_nao_tenta_conectar(self):
        self.assertFalse(capa_db.configurado())
        self.assertIsNone(capa_db.conexao())
        self.assertIsNone(capa_db.cadastro_do_paciente("9000001CEL"))
        self.assertIsNone(capa_db.foto_do_paciente("9000001CEL"))

    def test_prescricao_que_nao_pode_ser_lida_LEVANTA(self):
        """Lista vazia significaria "este paciente não tem prescrição".

        Não é o mesmo que "não consegui perguntar", e confundir os dois punha
        na capa "Nenhuma prescrição aprovada" para quem tem cinco — e ainda
        gravava essa capa pela metade no espelho, virando a reserva de
        emergência daquele paciente com aparência de dado bom.
        """
        with self.assertRaises(capa_db.FalhaDeLeitura):
            capa_db.prescricoes_do_paciente("9000001CEL")


class TestQuedaParaOsRelatorios(unittest.TestCase):
    """O banco cair não pode impedir a capa de sair.

    É o ponto da coisa toda: ter DUAS fontes, não trocar uma dependência
    frágil por outra. Um documento que vai para a sala de tratamento não pode
    depender de a rede estar boa naquele minuto.
    """

    def setUp(self):
        self._env = os.environ.get(capa_db.ENV_SERVIDOR)
        # Ver ``_ComBanco.setUp``: o nome novo venceria este.
        self._env_novo = os.environ.pop(
            ambiente.nome_novo(capa_db.ENV_SERVIDOR), None)
        os.environ[capa_db.ENV_SERVIDOR] = "SERVIDOR-QUE-NAO-EXISTE"
        self._cadastro = capa_dados.carregar_cadastro
        self._prescricoes = capa_dados.carregar_prescricoes
        cad = capa_dados.Cadastro(registro="1111111AAA", nome="DO RELATORIO",
                                  convenio="SUS")
        capa_dados.carregar_cadastro = lambda: {"1111111AAA": cad}
        capa_dados.carregar_prescricoes = lambda: {}

    def tearDown(self):
        capa_dados.carregar_cadastro = self._cadastro
        capa_dados.carregar_prescricoes = self._prescricoes
        _devolver({capa_db.ENV_SERVIDOR: self._env,
                   ambiente.nome_novo(capa_db.ENV_SERVIDOR): self._env_novo})
        capa_db.esquecer()

    def test_banco_fora_do_ar_cai_nos_csv(self):
        # GUARDA e devolve, nunca ``del``: ``capa_db.conexao = X`` grava no
        # __dict__ do módulo, e apagar depois some com a função ORIGINAL para o
        # resto do processo. Foi o que o teste em ordem aleatória flagrou —
        # oito erros em outro arquivo, e nenhum deles era do código.
        original = capa_db.conexao
        capa_db.conexao = lambda: None
        try:
            res = capa_dados.buscar("1111111AAA", "")
        finally:
            capa_db.conexao = original
        self.assertTrue(res.achou)
        self.assertEqual(res.cadastro.convenio, "SUS")
        self.assertEqual(res.origem, capa_dados.ORIGEM_RELATORIOS)

    def test_consulta_que_explode_tambem_cai_nos_csv(self):
        def explodir(_registro):
            raise RuntimeError("conexão derrubada no meio")

        original = capa_db.cadastro_do_paciente
        # Depois que o ``except`` do ``_do_banco`` engole a explosão, o
        # ``buscar`` ainda pergunta ``_banco_respondeu()`` para decidir se é
        # emergência — e essa pergunta é um ``capa_db.conexao()`` de verdade,
        # contra o ``SERVIDOR-QUE-NAO-EXISTE`` do ``setUp``. Eram 8 s de espera
        # de tempo-limite (medido em 14/09/2026) num teste que só quer saber se
        # a capa saiu pelos CSV. O irmão ``test_banco_fora_do_ar_cai_nos_csv``
        # já fazia isto — era ele o rápido dos dois.
        original_conexao = capa_db.conexao
        capa_db.conexao = lambda: None
        capa_db.cadastro_do_paciente = explodir
        try:
            res = capa_dados.buscar("1111111AAA", "")
        finally:
            capa_db.cadastro_do_paciente = original
            capa_db.conexao = original_conexao
        self.assertTrue(res.achou, "a capa saiu mesmo com o banco quebrado")
        self.assertEqual(res.origem, capa_dados.ORIGEM_RELATORIOS)


class TestOsDoisNomesDaVariavel(unittest.TestCase):
    """A estação aponta o servidor pelo nome NOVO — e isso não fazia nada.

    O app trocou de nome duas vezes (ficha-py → Radioteraficha → ISOCENTRO) e
    as variáveis acompanharam, com o ``ambiente.ler`` atendendo pelos três
    nomes. O ``capa_db`` ficou de fora em 09/09/2026: lia ``os.environ.get``
    direto, só o ``FICHAPY_*``. Quem configurasse a estação pelo nome novo
    apontava o servidor e não acontecia NADA — o app caía no
    ``config_servico.json`` ou nos relatórios exportados, sem erro nenhum na
    tela ligando uma coisa à outra. É a forma de quebrar que o ``ambiente.py``
    existe para impedir.
    """

    NOVO = ambiente.nome_novo(capa_db.ENV_SERVIDOR)          # ISOCENTRO_
    INTERMEDIARIO, ANTIGO = ambiente.nomes_antigos(capa_db.ENV_SERVIDOR)

    def setUp(self):
        self._antes = {n: os.environ.get(n) for n in (
            *ambiente.nomes(capa_db.ENV_SERVIDOR),
            *ambiente.nomes(capa_db.ENV_BANCO), "ISOCENTRO_CONFIG")}
        for nome in self._antes:
            os.environ.pop(nome, None)
        # Sem a variável o ``_config`` cai no ``config_servico.json``, que
        # nesta estação aponta o SRVINSIGHT: sem isolar a pasta, "não há
        # servidor" nunca seria verdade aqui.
        self._cfg_vazia = tempfile.mkdtemp(prefix="cfg_vazia_")
        os.environ["ISOCENTRO_CONFIG"] = self._cfg_vazia
        capa_db.esquecer()

    def tearDown(self):
        _devolver(self._antes)
        shutil.rmtree(self._cfg_vazia, ignore_errors=True)
        capa_db.esquecer()

    def test_o_nome_novo_sozinho_aponta_o_servidor(self):
        os.environ[self.NOVO] = "SRV-NOVO"
        self.assertEqual(capa_db.servidor(), "SRV-NOVO")
        self.assertTrue(capa_db.configurado())

    def test_o_nome_antigo_continua_valendo(self):
        """Estação que a TI configurou há anos não pode parar de funcionar."""
        os.environ[self.ANTIGO] = "SRV-ANTIGO"
        self.assertEqual(capa_db.servidor(), "SRV-ANTIGO")

    def test_o_nome_intermediario_continua_valendo(self):
        """O ``RADIOTERAFICHA_*`` de 09/09 a 15/10/2026 também foi para estação."""
        os.environ[self.INTERMEDIARIO] = "SRV-MEIO"
        self.assertEqual(capa_db.servidor(), "SRV-MEIO")

    def test_com_os_tres_o_mais_novo_vence(self):
        os.environ[self.ANTIGO] = "SRV-ANTIGO"
        os.environ[self.INTERMEDIARIO] = "SRV-MEIO"
        self.assertEqual(capa_db.servidor(), "SRV-MEIO")
        os.environ[self.NOVO] = "SRV-NOVO"
        self.assertEqual(capa_db.servidor(), "SRV-NOVO")

    def test_a_origem_diz_QUAL_nome_venceu(self):
        """Com as duas definidas, dizer o nome antigo manda conferir a errada."""
        os.environ[self.ANTIGO] = "SRV-ANTIGO"
        os.environ[self.NOVO] = "SRV-NOVO"
        origem = capa_db.origem_do_servidor()
        self.assertIn(self.NOVO, origem)
        self.assertNotIn(self.ANTIGO, origem)

    def test_sem_variavel_a_origem_nao_acusa_a_estacao(self):
        """A tela de Serviço só avisa quando há mesmo uma variável mandando."""
        self.assertEqual(capa_db.origem_do_servidor(), "não apontado")

    def test_o_banco_tambem_atende_pelos_tres_nomes(self):
        """Mesma correção, mesmo módulo: não adianta metade da configuração."""
        for nome in ambiente.nomes(capa_db.ENV_BANCO):
            os.environ[nome] = "outrodw"
            try:
                self.assertEqual(capa_db.banco(), "outrodw", nome)
            finally:
                os.environ.pop(nome, None)


if __name__ == "__main__":
    unittest.main()
