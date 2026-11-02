"""O relatório do gatilho: o que faria a exportação automática pegar o errado.

O ``tools/mapear_gatilho.py`` roda na estação da clínica, com a identidade de
rede que esta máquina não tem — quem o executa vai lá, roda e volta. Mesma
aposta do ``test_atividades``: o fluxo inteiro é exercido aqui contra um banco
falso, porque um erro no passo do plano não custa um teste vermelho, custa a
viagem.

O que estes testes fixam é o que faria o relatório MENTIR:

* **coluna que existe e está toda NULA** tem de sair marcada como vazia. É a
  armadilha específica desta busca: ela entra na consulta, o SQL roda sem
  reclamar, e o filtro não filtra nada — o que numa exportação automática
  significa mandar plano nenhum, ou mandar todos;
* **o veredito do plano** tem de seguir o catálogo, não a esperança. Se
  ``DimPlan`` não encosta em paciente nem em curso, o DW só vê o plano depois
  da primeira sessão aplicada, e dizer o contrário mandaria o filtro de
  aprovação para o lugar em que ele não funciona;
* **estado que é chave de ``DimLookup``** sai traduzido. Uma lista de inteiros
  não responde "o curso está ativo?", e é o formato que o DW da Varian usa para
  quase todo vocabulário;
* **tabela grande não é amostrada**, e **permissão negada não vira "não achei"**
  — as duas travas herdadas do ``tools/atividades.py``.

Rodar:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "tools"))

import mapear_gatilho  # noqa: E402

# Um DW de brinquedo com o formato do de verdade, e com as três perguntas
# embutidas: a dimensão pequena do curso, a do plano SEM vínculo direto (a
# hipótese pessimista, que é a que decide o desenho) e o fato de milhões.
_COLUNAS = {
    ("DWH", "DimCourse"): [
        ("DimCourseID", "int", None),
        ("DimPatientID", "int", None),
        ("CourseId", "varchar", 32),
        ("CourseStartDateTime", "datetime", None),
        ("CourseCompletedDateTime", "datetime", None),
        ("DimLookupID_CourseStatus", "int", None),
        # Existe no catálogo e nunca foi alimentada nesta instalação: é a
        # coluna que pareceria a resposta e não é.
        ("CourseSuspendReason", "nvarchar", 120),
    ],
    ("DWH", "DimPlan"): [
        ("DimPlanID", "int", None),
        ("PlanSetupId", "varchar", 64),
        ("PlanApprovalStatus", "nvarchar", 64),
    ],
    ("DWH", "DimActivityTransaction"): [
        ("ctrActivityInstanceSer", "bigint", None),
        ("DimPatientID", "int", None),
        ("AppointmentDateTime", "datetime", None),
    ],
}

_TAMANHOS = {("DWH", "DimCourse"): 900,
             ("DWH", "DimPlan"): 5_000,
             ("DWH", "DimActivityTransaction"): 1_890_000}

# ``(total, preenchidas)`` por coluna. O zero da ``CourseSuspendReason`` é o
# ponto do primeiro teste.
_PREENCHIMENTO = {
    ("DWH", "DimCourse", "CourseStartDateTime"): (900, 900),
    ("DWH", "DimCourse", "CourseCompletedDateTime"): (900, 610),
    ("DWH", "DimCourse", "DimLookupID_CourseStatus"): (900, 900),
    ("DWH", "DimCourse", "CourseSuspendReason"): (900, 0),
    ("DWH", "DimPlan", "PlanApprovalStatus"): (5_000, 5_000),
}

_VALORES = {
    ("DWH", "DimPlan", "PlanApprovalStatus"): [
        "Planning Approved", "Treatment Approved", "Unapproved"],
}

# O que o DimLookup responde para a coluna de estado do curso.
_LOOKUP = [("Active", "Ativo"), ("Completed", "Concluído")]

# Os planos do paciente: um aprovado para tratamento e um rascunho. É a forma
# do caso real de 02/09/2026 — curso aberto, nenhuma sessão aplicada.
_PLANOS = [
    (30658, "MAMA D", "Mama direita", "Treatment Approved",
     "Tratamento aprovado", 0, 5, "clinica\\leonardo.quintela",
     "2026-09-01 16:40:00", "1.2.246.352.71.5.1.9876543210.1"),
    (30658, "MAMA D2", "Mama direita rev", "Unapproved", "Não aprovado",
     1, 5, "clinica\\leonardo.quintela", "2026-09-01 18:02:00",
     "1.2.246.352.71.5.1.9876543210.2"),
]

# O que a consulta da ponte devolve. Lista vazia é a resposta real: nenhuma
# tabela do DW sabe de atividade e de curso ao mesmo tempo.
_PONTE: list = []

_SEM_PERMISSAO = ("DWH", "DimPlanProibida")


def _do_select(achatado):
    """``[DWH].[DimCourse]`` e ``[CourseId]`` de volta para nomes."""
    coluna = achatado.split("[", 2)[1].split("]", 1)[0]
    depois = achatado.split("FROM [", 1)[1]
    esquema, resto = depois.split("].[", 1)
    return esquema, resto.split("]", 1)[0], coluna


def _tabela_do_from(achatado):
    depois = achatado.split("FROM [", 1)[1]
    esquema, resto = depois.split("].[", 1)
    return esquema, resto.split("]", 1)[0]


def _responder(sql, params):
    achatado = " ".join(sql.split())
    if "'%activit%'" in achatado:
        # A ponte atividade<->curso: por padrão NÃO existe, que é o que o banco
        # de verdade respondeu em 02/09/2026.
        return list(_PONTE)
    if "INFORMATION_SCHEMA.COLUMNS" in achatado and "COLUMN_NAME LIKE" in achatado:
        return [(e, t, c) for (e, t), cols in _COLUNAS.items()
                for c, _tipo, _larg in cols if "plan" in c.lower()]
    if "INFORMATION_SCHEMA.COLUMNS" in achatado:
        chave = (params[0], params[1])
        if chave == _SEM_PERMISSAO:
            raise RuntimeError("SELECT permission denied on object")
        return _COLUNAS.get(chave, [])
    if "sys.dm_db_partition_stats" in achatado:
        return [(_TAMANHOS.get((params[0], params[1])),)]
    # O preenchimento vem ANTES do COUNT(*) simples: os dois começam igual, e
    # trocar a ordem faria a contagem de linhas responder pela de preenchidas.
    if achatado.startswith("SELECT COUNT(*), COUNT("):
        esquema, tabela, coluna = _do_select(achatado)
        return [_PREENCHIMENTO.get((esquema, tabela, coluna), (0, 0))]
    if achatado.startswith("SELECT COUNT(*)"):
        esquema, tabela = _tabela_do_from(achatado)
        return [(_TAMANHOS.get((esquema, tabela), 0),)]
    if "DWH.GetPatientPlan" in achatado:
        return list(_PLANOS)
    if "DWH.DimLookup l" in achatado:
        return list(_LOOKUP)
    if achatado.startswith("SELECT MIN("):
        return [("2024-01-05 08:00:00", "2026-09-01 19:15:00")]
    if achatado.startswith("SELECT DISTINCT TOP"):
        esquema, tabela, coluna = _do_select(achatado)
        return [(v,) for v in _VALORES.get((esquema, tabela, coluna), [])]
    if "DWH.DimPatient" in achatado:
        return [(4242,)]
    if achatado.startswith("SELECT * FROM DWH.DimCourse"):
        # Dois cursos, e é essa a forma do problema: o retratamento em que
        # casar atividade e curso pelo paciente pega o errado.
        return [(88, 4242, "C2 AGOSTO 26", "2026-08-20 09:00:00", None, 1, None),
                (77, 4242, "C1 MAIO 26", "2026-05-04 09:00:00",
                 "2026-06-11 17:00:00", 2, None)]
    return []


class _CursorFalso:
    """Responde pelo pedaço de SQL, e ANOTA tudo que foi perguntado.

    Anotar é metade do teste: o que se quer provar da tabela de milhões não é a
    resposta, é que ela NÃO foi perguntada.
    """

    def __init__(self, perguntas: list):
        self._perguntas = perguntas
        self._linhas: list = []
        # O ``passo_paciente`` lê ``cursor.description`` para nomear as colunas
        # do ``SELECT *``. Sem isto aqui, o único caminho que roda na clínica
        # com ``--paciente`` ficaria fora do teste — e um ``AttributeError``
        # ali não custa teste vermelho, custa a viagem.
        self.description = None

    def execute(self, sql, *params):
        achatado = " ".join(sql.split())
        self._perguntas.append((achatado, params))
        self._linhas = _responder(sql, params)
        if achatado.startswith("SELECT * FROM"):
            esquema, _, resto = achatado.split("FROM ", 1)[1].partition(".")
            tabela = resto.split(" ", 1)[0]
            self.description = [(c,) + (None,) * 6
                                for c, _t, _l in _COLUNAS[(esquema, tabela)]]
        return self

    def fetchall(self):
        return self._linhas


class _ConexaoFalsa:
    def __init__(self):
        self.perguntas: list = []
        self.timeout = 0

    def cursor(self):
        return _CursorFalso(self.perguntas)


def _rodar(tabela, padroes, **kw):
    cx = _ConexaoFalsa()
    linhas: list = []
    mapear_gatilho.passo_tabela(cx, tabela, padroes, "pergunta de teste",
                                linhas.append, **kw)
    return cx, "\n".join(linhas)


class Curso(unittest.TestCase):
    """A primeira pergunta: dá para saber que o curso está ATIVO?"""

    def setUp(self):
        self.cx, self.texto = _rodar("DWH.DimCourse",
                                     mapear_gatilho.PADROES_ESTADO)

    def test_coluna_toda_nula_sai_marcada(self):
        """A armadilha desta busca inteira.

        ``CourseSuspendReason`` existe no catálogo e nunca foi alimentada. Sem
        o aviso, ela entra na consulta do gatilho, o SQL roda sem reclamar, e o
        filtro não filtra nada — que numa exportação automática é mandar tudo
        ou não mandar nada, calado.
        """
        # ``rsplit``, e não ``split``: a coluna aparece DUAS vezes — na lista do
        # catálogo e depois no detalhe —, e o pedaço que interessa é o segundo.
        # Pegando o primeiro, o teste reprovava a ferramenta por um erro dele.
        detalhe = self.texto.split("-- as candidatas, em detalhe --", 1)[1]
        self.assertIn("CourseSuspendReason", detalhe)
        pedaco = detalhe.split("CourseSuspendReason", 1)[1]
        self.assertIn("VAZIA nesta instalação", pedaco)

    def test_coluna_vazia_nao_e_amostrada(self):
        """Não adianta avisar e perguntar assim mesmo: é ida ao servidor
        clínico para trazer lista vazia."""
        for sql, _p in self.cx.perguntas:
            if sql.startswith("SELECT DISTINCT TOP"):
                self.assertNotIn("CourseSuspendReason", sql)

    def test_estado_por_lookup_sai_traduzido(self):
        """Uma lista de inteiros não responde "o curso está ativo?".

        É a forma que o DW da Varian usa para quase todo vocabulário, e é como
        o ``capa_db._SQL_CURSO`` já lê a intenção do curso.
        """
        self.assertIn("Active", self.texto)
        self.assertIn("Ativo", self.texto)

    def test_data_sai_como_faixa(self):
        """Data não se amostra: o que interessa é se a coluna ainda é
        alimentada ou parou numa migração antiga."""
        self.assertIn("de 2024-01-05 08:00:00 até 2026-09-01 19:15:00",
                      self.texto)

    def test_a_taxa_de_preenchimento_aparece(self):
        # 610 de 900: é o número que diz que "curso encerrado" existe de
        # verdade nesta instalação, e não só no catálogo.
        self.assertIn("610/900", self.texto)


class Plano(unittest.TestCase):
    """A pergunta que decide onde mora o filtro de aprovação."""

    def _alcance(self):
        cx = _ConexaoFalsa()
        linhas: list = []
        mapear_gatilho.passo_alcance_do_plano(cx, linhas.append)
        return "\n".join(linhas)

    def test_sem_vinculo_direto_manda_o_filtro_para_o_dicom(self):
        """``DimPlan`` sem paciente nem curso significa que o único caminho é
        ``FactTreatmentHistory`` — sessão APLICADA. Plano aprovado e ainda não
        tratado, que é o caso que a automação existe para pegar, não seria
        visto."""
        texto = self._alcance()
        self.assertIn("NÃO tem coluna de paciente nem de curso", texto)
        self.assertIn("ApprovalStatus", texto)

    def test_com_vinculo_direto_o_filtro_pode_ficar_no_dw(self):
        """E o contrário tem de ser dito com a mesma clareza: um relatório que
        só sabe dar a má notícia não é diagnóstico, é palpite.

        Guardar e DEVOLVER a lista, nunca ``del``: gravar no ``__dict__`` do
        módulo e apagar depois some com a ORIGINAL para o resto do processo.
        """
        antes = _COLUNAS[("DWH", "DimPlan")]
        _COLUNAS[("DWH", "DimPlan")] = antes + [("DimCourseID", "int", None)]
        try:
            texto = self._alcance()
        finally:
            _COLUNAS[("DWH", "DimPlan")] = antes
        self.assertIn("liga direto por: DimCourseID", texto)
        self.assertIn("PODE morar no DW", texto)

    def test_a_aprovacao_do_plano_sai_com_os_valores(self):
        _cx, texto = _rodar("DWH.DimPlan", mapear_gatilho.PADROES_APROVACAO)
        self.assertIn("PlanApprovalStatus", texto)
        self.assertIn("Treatment Approved", texto)

    def test_permissao_negada_nao_vira_ausencia(self):
        """Mesma distinção do ``FalhaDeLeitura``: no relatório, permissão
        negada tem de aparecer como permissão negada — senão quem lê conclui
        que a tabela não existe e vai embora."""
        _cx, texto = _rodar("DWH.DimPlanProibida",
                            mapear_gatilho.PADROES_APROVACAO)
        self.assertIn("NÃO LI o catálogo", texto)
        self.assertIn("permission denied", texto)


class Atividade(unittest.TestCase):
    """A terceira: a atividade sabe de que curso ela é?"""

    def setUp(self):
        self.cx, self.texto = _rodar("DWH.DimActivityTransaction",
                                     mapear_gatilho.PADROES_VINCULO)

    def test_o_fato_nao_e_amostrado(self):
        """1,89 milhão de linhas. Um ``DISTINCT`` com ``ORDER BY`` aí é
        varredura de tabela inteira no servidor clínico em horário de
        expediente — a trava herdada do ``tools/atividades.py``."""
        for sql, _p in self.cx.perguntas:
            self.assertFalse(sql.startswith("SELECT DISTINCT TOP"), sql)
        self.assertIn("tabela grande", self.texto)

    def test_o_catalogo_sai_mesmo_assim(self):
        """Não amostrar não é não olhar: é do catálogo que se descobre se
        existe coluna de curso, e essa é a pergunta."""
        self.assertIn("ctrActivityInstanceSer", self.texto)
        self.assertIn("DimPatientID", self.texto)

    def test_amostrar_e_por_tabela_nomeada(self):
        """Um interruptor único obrigaria a escolher entre não ver nada e varrer
        o fato de 1,89 milhão.

        Na primeira rodada real (02/09/2026) a trava de 20 mil linhas — boa para
        o fato — barrou ``DimCourse`` (30.677) e ``DimPlan`` (74.171), que são
        dimensões e são onde moram os dois estados procurados.
        """
        cx, _texto = _rodar("DWH.DimActivityTransaction",
                            mapear_gatilho.PADROES_VINCULO,
                            amostrar=("DimActivityTransaction",))
        self.assertTrue(any(sql.startswith("SELECT COUNT(*), COUNT(")
                            for sql, _p in cx.perguntas))

    def test_nomear_outra_tabela_nao_libera_esta(self):
        cx, texto = _rodar("DWH.DimActivityTransaction",
                           mapear_gatilho.PADROES_VINCULO,
                           amostrar=("DimCourse",))
        self.assertIn("tabela grande", texto)
        self.assertFalse(any(sql.startswith("SELECT COUNT(*), COUNT(")
                             for sql, _p in cx.perguntas))


class Caso(unittest.TestCase):
    """O retrato de UM paciente — o passo que só roda na clínica.

    É a diferença entre "a coluna existe" e "a coluna responde à minha
    pergunta". Foi ela que pegou os dois defeitos do ``atividades_db`` em
    02/09/2026, e o caso de dois cursos é exatamente a forma do problema que
    falta resolver: o retratamento em que casar atividade e curso pelo paciente
    escolhe o errado.
    """

    def setUp(self):
        self.cx = _ConexaoFalsa()
        linhas: list = []
        mapear_gatilho.passo_paciente(self.cx, "9000019ANA", linhas.append)
        self.texto = "\n".join(linhas)

    def test_sai_um_bloco_por_curso(self):
        self.assertIn("-- curso 1 --", self.texto)
        self.assertIn("-- curso 2 --", self.texto)
        self.assertIn("C2 AGOSTO 26", self.texto)
        self.assertIn("C1 MAIO 26", self.texto)

    def test_coluna_vazia_nao_polui_o_retrato(self):
        """O curso aberto não tem data de encerramento, e imprimir
        ``CourseCompletedDateTime None`` esconderia o que interessa no meio de
        linhas sem conteúdo."""
        aberto = self.texto.split("-- curso 1 --", 1)[1].split("-- curso 2")[0]
        self.assertNotIn("CourseCompletedDateTime", aberto)
        encerrado = self.texto.split("-- curso 2 --", 1)[1]
        self.assertIn("CourseCompletedDateTime", encerrado)

    def test_o_registro_vira_DimPatientID_antes(self):
        """O ``PatientId`` é o registro do papel; o ``DimPatientID`` é a chave
        do DW. Consultar o curso pelo registro devolveria vazio, calado."""
        self.assertIn("DimPatientID = 4242", self.texto)
        cursos = [sql for sql, _p in self.cx.perguntas
                  if sql.startswith("SELECT * FROM DWH.DimCourse")]
        self.assertEqual(len(cursos), 1)


class PlanosDoCaso(unittest.TestCase):
    """A premissa do desenho: com a Documentação aberta, o plano já está pronto?

    A tarefa abrir significa que alguém PODE documentar, não que a física
    aprovou — é suposição de fluxo, e só o caso real responde. O relatório tem
    de mostrar o estado de CADA plano, e o ``PlanUID`` inteiro: é ele que vai no
    C-MOVE, e truncado no relatório vira um C-MOVE que não acha nada.
    """

    def setUp(self):
        cx = _ConexaoFalsa()
        linhas: list = []
        mapear_gatilho.passo_planos_do_paciente(cx, 18477, linhas.append)
        self.texto = "\n".join(linhas)

    def test_cada_plano_sai_com_o_estado(self):
        self.assertIn("Treatment Approved", self.texto)
        self.assertIn("Unapproved", self.texto)

    def test_o_uid_sai_inteiro(self):
        self.assertIn("1.2.246.352.71.5.1.9876543210.1", self.texto)
        self.assertIn("1.2.246.352.71.5.1.9876543210.2", self.texto)

    def test_paciente_sem_plano_derruba_a_premissa_em_voz_alta(self):
        """Lista vazia aqui não é "nada a relatar": é o caso em que a
        Documentação abriu antes de existir plano, e o gatilho estaria errado.

        Guardar e DEVOLVER o conteúdo, nunca trocar o objeto: o ``_responder``
        fechou sobre ESTA lista.
        """
        guardado = list(_PLANOS)
        _PLANOS.clear()
        try:
            cx = _ConexaoFalsa()
            linhas: list = []
            mapear_gatilho.passo_planos_do_paciente(cx, 18477, linhas.append)
        finally:
            _PLANOS.extend(guardado)
        texto = "\n".join(linhas)
        self.assertIn("NENHUM plano", texto)
        self.assertIn("premissa do desenho não se sustenta", texto)


class Ponte(unittest.TestCase):
    """A atividade sabe de que curso ela é?

    ``DimActivityTransaction`` não tem coluna de curso nenhuma nas 56 (medido
    em 02/09/2026) — as de "plan" que ela tem são de MedOnc, quimioterapia, não
    do plano de radioterapia. Sem ponte, num retratamento (curso 2 aberto,
    curso 1 ainda com pendência) casar atividade e curso pelo paciente escolhe
    o errado, calado.
    """

    def _rodar(self):
        cx = _ConexaoFalsa()
        linhas: list = []
        mapear_gatilho.passo_ponte_atividade_curso(cx, linhas.append)
        return "\n".join(linhas)

    def test_sem_ponte_o_veredito_e_estreitar(self):
        texto = self._rodar()
        self.assertIn("NENHUMA tabela", texto)
        self.assertIn("nunca mais", texto)

    def test_havendo_ponte_ela_e_nomeada(self):
        """Guardar e DEVOLVER o conteúdo da lista, nunca trocar o objeto: o
        ``_responder`` fechou sobre ESTE ``_PONTE``, e reatribuir o nome do
        módulo deixaria o banco falso respondendo pela lista velha."""
        _PONTE.append(("DWH", "GetActivityCourse"))
        try:
            texto = self._rodar()
        finally:
            _PONTE.clear()
        self.assertIn("DWH.GetActivityCourse", texto)
        self.assertNotIn("NENHUMA tabela", texto)


class Consulta(unittest.TestCase):
    """O ``--consulta``: roda o ``gatilho_db`` de verdade.

    É o passo que existe para ser comparado, plano a plano, com o que o ARIA
    mostra — e é dessa comparação que sai a data do ``VERIFICADO_EM``.
    """

    def _rodar(self, prontos=None, conta=None, explode=False, dossies=None,
               explode_dossie=False):
        """Guardar e DEVOLVER as funções do módulo, nunca ``del``."""
        from isocentro.banco import gatilho_db

        antes_p, antes_c = gatilho_db.prontos, gatilho_db.porque_vazio
        antes_d = gatilho_db.conferencia

        def _prontos(desde=None):
            if explode:
                raise capa_db_falha("sem conexão")
            return list(prontos or [])

        def _conferencia(desde=None):
            if explode or explode_dossie:
                raise capa_db_falha("sem conexão")
            return list(dossies or [])

        gatilho_db.prontos = _prontos
        gatilho_db.porque_vazio = lambda desde=None: dict(conta or {})
        gatilho_db.conferencia = _conferencia
        linhas: list = []
        try:
            mapear_gatilho.passo_consulta(linhas.append)
        finally:
            gatilho_db.prontos, gatilho_db.porque_vazio = antes_p, antes_c
            gatilho_db.conferencia = antes_d
        return "\n".join(linhas)

    def test_as_constantes_valendo_saem_antes_do_resultado(self):
        """Sem elas a lista não é conferível: "faltou o plano do fulano" tem
        resposta diferente conforme o filtro que estava valendo na rodada."""
        texto = self._rodar()
        self.assertIn("APROVADOS", texto)
        self.assertIn("Planning Approved", texto)
        self.assertIn("UM_PLANO_POR_CURSO", texto)

    def test_o_uid_sai_inteiro(self):
        from isocentro.banco import gatilho_db

        uid = "1.2.246.352.71.5.642399144380.534255.20260902085106"
        p = gatilho_db.Pronto(registro="9000019ANA", paciente="Fulana",
                              curso="C1", plano="cCRANIO_20Gy",
                              plan_uid=uid, estado="Planning Approved")
        texto = self._rodar(prontos=[p])
        self.assertIn(uid, texto)
        self.assertIn("1 plano(s) pronto(s)", texto)

    def test_lista_vazia_manda_olhar_os_degraus(self):
        """"Nenhum" sozinho é indistinguível de defeito. O relatório tem de
        dizer para onde olhar."""
        texto = self._rodar(conta={"pacientes": 3, "com_curso_ativo": 0})
        self.assertIn("nenhum", texto)
        self.assertIn("degraus", texto)

    def test_quem_nao_saiu_aparece_com_o_degrau(self):
        """A conferência não fecha sem isto.

        A rodada de 02/09/2026 listou os planos que SAÍRAM, e o próprio
        relatório dizia no fim que "ausência não aparece numa lista". Um
        paciente com Documentação aberta e nenhum plano tem de ter linha, com
        o motivo escrito — senão "faltou o fulano" e "o fulano ainda não tem
        plano" são a mesma tela em branco.
        """
        from isocentro.banco import gatilho_db

        d = gatilho_db.Dossie(
            registro="9000026ANA", paciente="Retratamento, Maria",
            instancia=3, degrau="curso ativo, nenhum plano ainda",
            cursos=[(30777, "C2 SETEMBRO 26", None, "ACTIVE", "Curativo",
                     True),
                    (30002, "C1 MARCO 26", None, "ACTIVE", "Curativo",
                     False)])
        texto = self._rodar(dossies=[d])
        self.assertIn("9000026ANA", texto)
        self.assertIn("curso ativo, nenhum plano ainda", texto)
        # O curso que ficou de fora aparece: é o que deixa ver, no papel, que a
        # escolha do curso está certa num retratamento.
        self.assertIn("C1 MARCO 26", texto)
        self.assertIn("NENHUM no curso escolhido", texto)

    def test_o_plano_recusado_aparece_marcado(self):
        """Metade da prova de que o filtro funciona é ver o que ele recusou."""
        from isocentro.banco import gatilho_db

        d = gatilho_db.Dossie(
            registro="9000019ANA", paciente="Beltrano, Lauro", instancia=2,
            degrau="pronto",
            cursos=[(30658, "C1 SETEMBRO 2026", None, "ACTIVE", "Curativo",
                     True)],
            planos=[("cCRANIO_20Gy", "1.2.BOM", 0, "Planning Approved",
                     "keiko.nakamura", None, True),
                    ("1", "1.2.RUIM", 0, "Rejected", "leonardo.quintela",
                     None, False)])
        texto = self._rodar(dossies=[d])
        self.assertIn("Rejected", texto)
        self.assertIn("[não]", texto)
        self.assertIn("[sai]", texto)

    def test_o_relatorio_chega_ao_fim_com_dossie(self):
        """O tempo sai na ÚLTIMA linha, e a primeira versão morria antes dela.

        A variável do laço de cursos se chamava ``inicio`` e sobrescrevia o
        ``inicio`` do cronômetro: o relatório imprimia tudo e estourava no
        cálculo do tempo — que é justamente a metade do ``VERIFICADO_EM`` que
        diz se a consulta cabe na thread da tela.
        """
        from isocentro.banco import gatilho_db

        d = gatilho_db.Dossie(
            registro="AAA", paciente="Um", instancia=1, degrau="pronto",
            cursos=[(1, "C1", None, "ACTIVE", "Curativo", True)])
        texto = self._rodar(dossies=[d])
        self.assertIn("plano(s) pronto(s), em", texto)

    def test_falha_no_dossie_nao_leva_a_lista_de_planos_junto(self):
        """Meia resposta vale mais que nenhuma: o bloco de cima é diagnóstico,
        o de baixo é o que se leva para o ARIA."""
        from isocentro.banco import gatilho_db

        p = gatilho_db.Pronto(registro="AAA", plan_uid="1.2.3",
                              estado="Planning Approved")
        texto = self._rodar(prontos=[p], explode_dossie=True)
        self.assertIn("NÃO deu", texto)
        self.assertIn("1.2.3", texto)
        self.assertIn("1 plano(s) pronto(s)", texto)

    def test_falha_de_leitura_aparece_como_falha(self):
        """Mesma distinção do ``FalhaDeLeitura``: "não consegui perguntar" não
        pode sair como "não há nada pronto"."""
        texto = self._rodar(explode=True)
        self.assertIn("NÃO deu", texto)


def capa_db_falha(msg):
    from isocentro.banco import capa_db

    return capa_db.FalhaDeLeitura(msg)


class ArquivoDeSaida(unittest.TestCase):
    """O ``-o`` grava mesmo quando NÃO deu para conectar.

    Custou uma ida e volta em 01/09/2026 no ``atividades.py``, e valeria de
    novo aqui: sem conexão, a recusa ficaria só no console do ``runas`` — que
    fecha — e, de fora, "não rodou" e "rodou e o servidor recusou" ficariam
    idênticos.
    """

    def test_grava_a_recusa_com_o_motivo(self):
        with tempfile.TemporaryDirectory() as pasta:
            destino = Path(pasta) / "saida.txt"
            # Quem responde "há servidor?" é o ``configurado``, e é ele que se
            # troca: zerar ``ISOCENTRO_DB_SERVIDOR`` não basta, porque o
            # ``capa_db`` cai no ``config_servico.json`` e o teste iria à rede.
            capa_db = mapear_gatilho._at.capa_db
            antes = capa_db.configurado
            capa_db.configurado = lambda: False
            try:
                codigo = mapear_gatilho.main(["-o", str(destino)])
                existe = destino.exists()
                texto = destino.read_text(encoding="utf-8") if existe else ""
            finally:
                capa_db.configurado = antes
        self.assertEqual(codigo, 2)
        self.assertTrue(existe, "o -o não gravou nada quando não conectou")
        self.assertIn("Nenhum servidor apontado", texto)

    def test_o_recado_aponta_o_bat_certo(self):
        """O ``_conectar`` é do ``atividades.py``, compartilhado — e mandava
        quem está fora do domínio rodar o ``atividades.bat``, que responde
        outra pergunta. Recado que aponta a ferramenta errada custa a viagem."""
        linhas: list = []
        capa_db = mapear_gatilho._at.capa_db
        antes_conf, antes_cx = capa_db.configurado, capa_db.conexao
        capa_db.configurado = lambda: True
        capa_db.conexao = lambda: None
        try:
            mapear_gatilho._at._conectar(linhas.append, "mapear_gatilho.bat")
        finally:
            capa_db.configurado, capa_db.conexao = antes_conf, antes_cx
        self.assertIn("mapear_gatilho.bat", "\n".join(linhas))


if __name__ == "__main__":
    unittest.main()
