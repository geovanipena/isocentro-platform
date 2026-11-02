"""O banco LOCAL: gravar o que o servidor respondeu e reproduzir sem rede.

Fora da clínica não há banco — esta máquina está fora do domínio e a identidade
é recusada (SSPI). A Capa cai no espelho/CSV e a Ficha Virtual some, porque ela
não tem reserva nenhuma; conferir tela com dado inventado é o jeito de não achar
o defeito que só o dado real mostra.

O que estes testes fixam é o CICLO — gravar, reproduzir, e receber de volta o
mesmo objeto — e as três coisas que, erradas, fariam a simulação mentir:

* consulta não gravada tem de FALHAR, nunca devolver lista vazia (lista vazia é
  "o banco respondeu e não há nada", e é assim que uma capa afirma "nenhuma
  prescrição aprovada" para quem tem cinco);
* o tipo tem de voltar como saiu — data é objeto com ``strftime``, a foto é
  BLOB, dose é ``Decimal``;
* a capa que sai do arquivo gravado tem de sair ANUNCIADA, pela mesma razão da
  capa que sai do espelho: depois de impressa ela é indistinguível de uma boa.

Rodar:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import datetime
import decimal
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from isocentro.banco import banco_local  # noqa: E402
from isocentro.banco import capa_dados  # noqa: E402
from isocentro.banco import capa_db  # noqa: E402


class _CursorFalso:
    """Casa a consulta por um pedaço do texto dela — como o banco de verdade
    não faz, mas é o suficiente para ter o que gravar."""

    def __init__(self, respostas: dict):
        self._respostas = respostas
        self._linhas: list = []

    def execute(self, sql, *params):
        for marca, linhas in self._respostas.items():
            if marca in sql:
                self._linhas = linhas
                return self
        self._linhas = []
        return self

    def fetchall(self):
        return self._linhas


class _ConexaoFalsa:
    def __init__(self, respostas: dict):
        self._respostas = respostas

    def cursor(self):
        return _CursorFalso(self._respostas)

    def close(self):
        pass


_JPEG = b"\xff\xd8\xff\xe0" + b"foto" * 40

# Um cadastro inteiro, com os tipos que o driver devolve de verdade: a data é
# ``datetime``, a foto é ``bytes``, a dose vem em ``Decimal``.
_RESPOSTAS = {
    "FROM DWH.DimPatient p": [(
        "9000001CEL", "SICRANA, JOANA HELENA FELIPE DE",
        datetime.datetime(1970, 6, 15), "Feminino", "62 90000-0000", 8711)],
    "DWH.FactPatientPayor": [("Unimed", "0064800000542300")],
    "FROM DWH.DimCourse c": [(4242, "C2 JANEIRO 24", "Pós-op.")],
    "DWH.FactPatientDiagnosis fd": [
        ("C34.2", "Neoplasia maligna do lobo médio, brônquio ou pulmão")],
    "DWH.DimPatientDoctor pd": [("Thais de Toledo Lima Saldanha",)],
    "DWH.DimPatientPhoto": [(_JPEG,)],
    "FROM (SELECT DISTINCT DimPrescriptionID": [(
        "Mama E 40.05Gy@15fx", "Breast, Left", "C1 JUL 26", "15",
        datetime.datetime(2026, 7, 10), "medico.exemplo", 555,
        "9000001CEL", "SICRANA, JOANA")],
    "DWH.DimPrescriptionAnatomy": [
        ("VOLUME ID", "PTV mama", None),
        ("TOTAL DOSE", decimal.Decimal("40.05"), "Gy"),
        ("DOSE PER FRACTION", decimal.Decimal("2.67"), "Gy"),
    ],
    "DWH.DimPrescriptionProperty": [("ONCE DAILY",)],
}


class _ComBancoLocal(unittest.TestCase):
    """Grava um arquivo do banco de mentira e liga o banco local nele."""

    RESPOSTAS: dict = _RESPOSTAS

    def setUp(self):
        self._pasta = tempfile.TemporaryDirectory()
        self.arquivo = Path(self._pasta.name) / "banco_local.sqlite"
        self._guardar_ambiente()
        # GUARDA e devolve, nunca ``del``: ``capa_db.conexao = X`` grava no
        # ``__dict__`` do módulo, e apagar depois some com a função ORIGINAL
        # para o resto do processo — já custou oito erros em outro arquivo.
        self._conexao = capa_db.conexao
        self.gravar()

    def gravar(self):
        """Faz as perguntas do app ao banco de mentira, gravando as respostas."""
        cx = banco_local.abrir(self.arquivo, criar=True)
        banco_local.anotar(cx, "servidor", "SERVIDOR-DE-TESTE")
        banco_local.anotar(cx, "gravado_em",
                           datetime.datetime.now().isoformat(timespec="seconds"))
        banco_local.anotar_paciente(cx, "9000001CEL", "TC-teste", True)
        falsa = _ConexaoFalsa(self.RESPOSTAS)
        capa_db.conexao = lambda: banco_local.Gravador(falsa, cx)
        try:
            os.environ[capa_db.ENV_SERVIDOR] = "SERVIDOR-DE-TESTE"
            capa_db.cadastro_do_paciente("9000001CEL")
            capa_db.prescricoes_do_paciente("9000001CEL")
            capa_db.foto_do_paciente("9000001CEL")
        finally:
            capa_db.conexao = self._conexao
            cx.commit()
            cx.close()
        # E agora o app passa a ler o ARQUIVO, sem servidor nenhum apontado.
        os.environ.pop(capa_db.ENV_SERVIDOR, None)
        os.environ.pop("ISOCENTRO_DB_SERVIDOR", None)
        os.environ["ISOCENTRO_BANCO_LOCAL"] = str(self.arquivo)
        banco_local.esquecer()
        capa_db.esquecer()

    def _guardar_ambiente(self):
        self._env = {k: os.environ.get(k)
                     for k in ("ISOCENTRO_BANCO_LOCAL",
                               "ISOCENTRO_BANCO_LOCAL",
                               capa_db.ENV_SERVIDOR,
                               "ISOCENTRO_DB_SERVIDOR")}
        for k in self._env:
            os.environ.pop(k, None)

    def tearDown(self):
        capa_db.conexao = self._conexao
        for chave, valor in self._env.items():
            if valor is None:
                os.environ.pop(chave, None)
            else:
                os.environ[chave] = valor
        banco_local.esquecer()
        capa_db.esquecer()
        self._pasta.cleanup()


class TestOCiclo(_ComBancoLocal):
    """Gravar e reproduzir tem de devolver o MESMO cadastro."""

    def test_o_cadastro_volta_inteiro_sem_servidor(self):
        """Sem servidor apontado e sem rede, a capa continua nascendo.

        É o ponto da coisa toda: o que trava o trabalho fora da clínica não é o
        app, é o banco não responder.
        """
        # Quem responde é o ARQUIVO, e não o ODBC. A asserção é sobre o objeto
        # e não sobre ``servidor()`` estar vazio: a estação de trabalho tem um
        # ``config_servico.json`` apontando o SRVINSIGHT, e o ponto é
        # justamente que o banco local VENCE dele — sem isso, quem tem a
        # configuração da clínica na máquina pagaria o tempo-limite do connect
        # em cada consulta antes de cair no arquivo.
        self.assertIsInstance(capa_db.conexao(), banco_local.Conexao)
        c = capa_db.cadastro_do_paciente("9000001CEL")
        self.assertIsNotNone(c)
        self.assertEqual(c.nome, "Joana Helena Felipe de Sicrana")
        self.assertEqual(c.convenio, "Unimed - 0064800000542300")
        self.assertEqual(c.curso, "C2 JANEIRO 24")
        self.assertEqual(c.cid, "C34.2")
        self.assertIn("Thais", c.medico)

    def test_a_data_volta_como_data_e_nao_como_texto(self):
        """``capa_db._data`` chama ``strftime`` no valor.

        Gravar a data como string faria a reprodução devolver o ISO cru
        ("1968-04-28T00:00:00") no lugar de 15/06/1970 — plausível na tela e
        errado no papel.
        """
        c = capa_db.cadastro_do_paciente("9000001CEL")
        self.assertEqual(c.nascimento, "15/06/1970")

    def test_a_foto_volta_como_bytes(self):
        """A 3×4 é BLOB. Em base64 mal desfeito ela vira retângulo quebrado."""
        self.assertEqual(capa_db.foto_do_paciente("9000001CEL"), _JPEG)

    def test_a_dose_em_decimal_nao_passa_por_float(self):
        """40.05 Gy = 4005 cGy. Passando por float, 40.05 já não é 40.05."""
        v = capa_db.prescricoes_do_paciente("9000001CEL")[0].volumes
        self.assertEqual(v[0].dose_cgy, "4005")
        self.assertEqual(v[0].dose_frac_cgy, "267")


class TestOQueNaoFoiGravado(_ComBancoLocal):
    """A pergunta que não está no arquivo tem de FALHAR."""

    def test_outro_paciente_levanta_em_vez_de_devolver_vazio(self):
        """Lista vazia quer dizer "o banco respondeu e não há nada".

        Devolver isso para uma pergunta que nunca foi feita é o erro caro: a
        capa afirmaria "nenhuma prescrição aprovada" para quem tem cinco, e
        essa capa ainda seria gravada no espelho como se fosse dado bom.
        """
        with self.assertRaises(capa_db.FalhaDeLeitura):
            capa_db.prescricoes_do_paciente("9000026ZZZ")
        self.assertIsNone(capa_db.cadastro_do_paciente("9000026ZZZ"))

    def test_sql_mudado_invalida_a_gravacao(self):
        """Mexer no SQL tem de invalidar — a linha gravada responde à pergunta
        ANTIGA, e servi-la para a nova é a definição de resposta plausível e
        errada."""
        original = capa_db._SQL_FOTO
        capa_db._SQL_FOTO = original.replace("Picture", "PictureThumbnail")
        try:
            self.assertIsNone(capa_db.foto_do_paciente("9000001CEL"))
        finally:
            capa_db._SQL_FOTO = original


class TestOQueNaoPodeInvalidar(_ComBancoLocal):
    """Reescrever COMENTÁRIO não pode jogar a gravação fora.

    O SQL deste projeto carrega comentário longo dentro da consulta (o
    ``_SQL_EM_TRATAMENTO`` chegou a gastar quinze linhas explicando por que só
    dois ``TerminationStatus`` contavam), e esses comentários são reescritos com
    frequência. Casar pelo texto cru faria toda revisão de comentário exigir
    uma regravação — e regravação exige ir até a rede da clínica.
    """

    def test_comentario_reescrito_continua_casando(self):
        original = capa_db._SQL_FOTO
        capa_db._SQL_FOTO = original + "\n-- comentário novo, escrito hoje\n"
        try:
            self.assertEqual(capa_db.foto_do_paciente("9000001CEL"), _JPEG)
        finally:
            capa_db._SQL_FOTO = original

    def test_indentacao_diferente_continua_casando(self):
        original = capa_db._SQL_FOTO
        capa_db._SQL_FOTO = "\n".join("    " + linha
                                      for linha in original.splitlines())
        try:
            self.assertEqual(capa_db.foto_do_paciente("9000001CEL"), _JPEG)
        finally:
            capa_db._SQL_FOTO = original

    def test_parametro_com_cara_de_data_e_curinga(self):
        """O ``desde`` do ``em_tratamento`` é ``hoje - 30 dias``.

        Gravado numa terça, a chave exata só casaria naquela terça: no dia
        seguinte a lista de "em tratamento" voltaria VAZIA, sem uma linha
        dizendo por quê. O dado é congelado de qualquer forma, e é isso que o
        ``resumo()`` anuncia na tela.
        """
        self.assertEqual(banco_local._chave("X ?", ("2026-09-01",)),
                         banco_local._chave("X ?", ("2026-09-02",)))
        # E um registro NÃO é data: casar por engano faria dois pacientes
        # dividirem a mesma resposta.
        self.assertNotEqual(banco_local._chave("X ?", ("9000001CEL",)),
                            banco_local._chave("X ?", ("9000002CEL",)))


class TestAnuncio(_ComBancoLocal):
    """Simulação silenciosa vira o normal em duas semanas."""

    def test_a_tela_diz_que_e_banco_local_e_nao_o_servidor(self):
        situacao, recado = capa_db.estado()
        self.assertEqual(situacao, "local")
        self.assertIn("SIMULA", recado.upper())
        self.assertIn("1 paciente", recado)

    def test_o_banco_local_conta_como_configurado(self):
        """Sem isto a Ficha Virtual diria "o sistema não está apontado" numa
        máquina que tem o dado gravado na mão."""
        self.assertTrue(capa_db.configurado())

    def test_a_capa_sai_com_o_aviso_em_primeiro_lugar(self):
        """Depois de impressa, uma capa de simulação é indistinguível de uma
        boa — o aviso vai à frente de qualquer outro, como o do espelho."""
        cadastro, prescricoes = capa_dados.carregar_cadastro, \
            capa_dados.carregar_prescricoes
        capa_dados.carregar_cadastro = lambda: {}
        capa_dados.carregar_prescricoes = lambda: {}
        try:
            res = capa_dados.buscar("9000001CEL", "")
        finally:
            capa_dados.carregar_cadastro = cadastro
            capa_dados.carregar_prescricoes = prescricoes
        self.assertTrue(res.achou)
        self.assertEqual(res.origem, capa_dados.ORIGEM_BANCO_LOCAL)
        self.assertTrue(res.avisos)
        self.assertIn("SIMULAÇÃO", res.avisos[0])

    def test_a_simulacao_nao_semeia_o_espelho_de_emergencia(self):
        """O espelho grava "em: agora", e é essa data que a tela mostra para
        decidir se a reserva ainda vale.

        Uma leitura do arquivo gravado semana passada entraria ali como espelho
        DE HOJE: a reserva de emergência passaria a mentir a própria idade, que
        é a única informação que ela tem além do dado.
        """
        from isocentro.banco import capa_espelho
        with tempfile.TemporaryDirectory() as pasta:
            anterior = os.environ.get("ISOCENTRO_ESPELHO")
            os.environ["ISOCENTRO_ESPELHO"] = pasta
            cadastro, prescricoes = capa_dados.carregar_cadastro, \
                capa_dados.carregar_prescricoes
            capa_dados.carregar_cadastro = lambda: {}
            capa_dados.carregar_prescricoes = lambda: {}
            try:
                res = capa_dados.buscar("9000001CEL", "")
                self.assertEqual(res.origem, capa_dados.ORIGEM_BANCO_LOCAL)
                self.assertEqual(capa_espelho.quantos(), 0)
            finally:
                capa_dados.carregar_cadastro = cadastro
                capa_dados.carregar_prescricoes = prescricoes
                if anterior is None:
                    os.environ.pop("ISOCENTRO_ESPELHO", None)
                else:
                    os.environ["ISOCENTRO_ESPELHO"] = anterior


class TestVarreduraRestrita(_ComBancoLocal):
    """As consultas que varrem a clínica inteira são cortadas NA LEITURA.

    Cortar depois, já no arquivo, parece equivalente e não é: a lista "em
    tratamento" ALIMENTA outras consultas — o ``tratamento_db`` reconta as
    frações passando aqueles registros como parâmetro. Gravada com a lista
    inteira, a auxiliar ficaria com uma chave que a reprodução (lista curta)
    nunca pergunta, e as colunas de recontagem sumiriam da tela sem uma linha
    dizendo por quê.

    E há o outro lado: guardar treze mil cadastros reais num arquivo de
    trabalho seria despejo de dado clínico sem necessidade nenhuma.
    """

    RESPOSTAS = {
        "FROM DWH.DimPatient p": [
            ("9000001CEL", "SICRANA, JOANA", datetime.datetime(1970, 6, 15)),
            ("9000002CEL", "AMOSTRO, TADEU", datetime.datetime(1955, 3, 1)),
            ("1234567XXX", "DE FORA, FULANO", datetime.datetime(1970, 1, 1)),
        ],
    }

    def gravar(self):
        cx = banco_local.abrir(self.arquivo, criar=True)
        banco_local.anotar(cx, "servidor", "SERVIDOR-DE-TESTE")
        banco_local.anotar(cx, "gravado_em",
                           datetime.datetime.now().isoformat(timespec="seconds"))
        so_estes = {"9000001CEL", "9000002CEL"}

        def filtrar(sql, linhas):
            if "DWH.DimPatient p" not in sql:
                return linhas
            return [linha for linha in linhas if linha[0] in so_estes]

        falsa = _ConexaoFalsa(self.RESPOSTAS)
        capa_db.conexao = lambda: banco_local.Gravador(falsa, cx, filtrar)
        try:
            os.environ[capa_db.ENV_SERVIDOR] = "SERVIDOR-DE-TESTE"
            self.na_gravacao = capa_db.pacientes()
        finally:
            capa_db.conexao = self._conexao
            cx.commit()
            cx.close()
        os.environ.pop(capa_db.ENV_SERVIDOR, None)
        os.environ.pop("ISOCENTRO_DB_SERVIDOR", None)
        os.environ["ISOCENTRO_BANCO_LOCAL"] = str(self.arquivo)
        banco_local.esquecer()
        capa_db.esquecer()

    def test_quem_gravou_ja_recebeu_a_lista_curta(self):
        """O corte tem de valer para quem PERGUNTOU, não só para o arquivo."""
        self.assertEqual([p.registro for p in self.na_gravacao],
                         ["9000001CEL", "9000002CEL"])

    def test_a_reproducao_devolve_a_mesma_lista_curta(self):
        lista = capa_db.pacientes()
        self.assertEqual([p.registro for p in lista],
                         ["9000001CEL", "9000002CEL"])

    def test_o_de_fora_nao_esta_no_arquivo(self):
        """O paciente que não é de nenhum caso não pode ter ficado gravado."""
        cx = banco_local.abrir(self.arquivo)
        try:
            tudo = "".join(l[0] for l in
                           cx.execute("SELECT linhas FROM respostas").fetchall())
        finally:
            cx.close()
        self.assertNotIn("1234567XXX", tudo)
        self.assertNotIn("FULANO", tudo)


class TestAsMarcasDaVarredura(unittest.TestCase):
    """A marca que identifica cada varredura só pode casar com ELA.

    É a armadilha que já mordeu no banco falso dos testes: ele reconhecia as
    consultas auxiliares por ``"IN ("``, a principal ganhou
    ``IN ('OPERATOR', 'MACHINE')`` e passou a ser respondida como se fosse
    auxiliar — a lista voltava vazia e quatro testes acusaram um defeito que
    não existia no código.

    Aqui o estrago seria maior e mudo: o corte é POR REGISTRO na coluna 0, e
    sete consultas tocam ``FactTreatmentHistory`` com outra coisa na coluna 0
    (``th.DimCourseID``, ``th.DimPlanID``, ``th.FractionNumber``). Casar uma
    delas por engano esvaziaria a resposta inteira, e o sintoma seria uma tela
    em branco no dia em que alguém fosse usar a gravação.
    """

    def _sqls(self) -> dict:
        from isocentro.banco import tratamento_db
        fora = {}
        for modulo in (capa_db, tratamento_db):
            # Só a última parte do ``__name__``: desde o pacote ele é
            # ``isocentro.banco.capa_db``, e o que a lista de esperados
            # abaixo precisa dizer é QUAL CONSULTA, não em que subpacote ela
            # mora. Guardar o nome completo faria o próximo remanejo de pasta
            # reprovar um teste que não tem nada a ver com pasta.
            curto = modulo.__name__.rsplit(".", 1)[-1]
            for nome in dir(modulo):
                if nome.startswith("_SQL"):
                    fora[f"{curto}.{nome}"] = banco_local._normalizar_sql(
                        getattr(modulo, nome))
        return fora

    def test_cada_marca_casa_so_com_a_propria_varredura(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
        import gravar_banco

        sqls = self._sqls()
        esperado = {
            "FROM DWH.DimPatient p WHERE p.PatientId <> 'NA'":
                {"capa_db._SQL_PACIENTES"},
            "GROUP BY p.PatientId, p.PatientFullName, th.DimCourseID":
                {"tratamento_db._SQL_EM_TRATAMENTO",
                 "tratamento_db._SQL_EM_TRATAMENTO_TODOS",
                 "tratamento_db._SQL_EM_TRATAMENTO_MEDICO",
                 "tratamento_db._SQL_TODOS_MEDICO"},
        }
        for marca, _coluna, o_que in gravar_banco.VARREDURAS:
            casaram = {nome for nome, sql in sqls.items() if marca in sql}
            self.assertEqual(
                casaram, esperado[marca],
                f"a marca da varredura '{o_que}' passou a casar com outra "
                f"consulta: {sorted(casaram)}")

    def test_a_coluna_zero_das_varreduras_e_o_registro(self):
        """Se ela deixar de ser, o corte joga fora a resposta inteira."""
        from isocentro.banco import tratamento_db
        for sql in (capa_db._SQL_PACIENTES, tratamento_db._SQL_EM_TRATAMENTO):
            primeira = banco_local._normalizar_sql(sql).split("SELECT ", 1)[1]
            self.assertTrue(primeira.startswith("p.PatientId"),
                            f"a coluna 0 deixou de ser o registro: {primeira[:40]}")


class TestDesligado(unittest.TestCase):
    """Sem a variável, nada disto existe."""

    def setUp(self):
        self._env = {k: os.environ.get(k)
                     for k in ("ISOCENTRO_BANCO_LOCAL",
                               "ISOCENTRO_BANCO_LOCAL")}
        for k in self._env:
            os.environ.pop(k, None)

    def tearDown(self):
        for chave, valor in self._env.items():
            if valor is None:
                os.environ.pop(chave, None)
            else:
                os.environ[chave] = valor
        banco_local.esquecer()

    def test_sem_variavel_o_modulo_fica_fora_do_caminho(self):
        self.assertFalse(banco_local.ligado())
        self.assertIsNone(banco_local.conexao())
        self.assertEqual(banco_local.resumo(), "")

    def test_variavel_apontando_para_arquivo_que_nao_existe_nao_liga(self):
        """É o caso de quem copiou o ``.bat`` de outra estação. Ligar aqui faria
        o app anunciar "banco local" e não responder consulta nenhuma."""
        os.environ["ISOCENTRO_BANCO_LOCAL"] = str(
            Path(tempfile.gettempdir()) / "nao_existe_banco_local.sqlite")
        self.assertFalse(banco_local.ligado())
        self.assertIsNone(banco_local.conexao())


if __name__ == "__main__":
    unittest.main()
