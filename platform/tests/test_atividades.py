"""A descoberta das atividades do ARIA: o relatório que se lê UMA vez, longe.

O ``tools/atividades.py`` roda na estação da clínica, com a identidade de rede
que esta máquina não tem — quem o executa vai lá, roda e volta. Um ``TypeError``
no passo 3 não custa um teste vermelho, custa a viagem: por isso o fluxo inteiro
é exercido aqui contra um banco falso, incluindo os caminhos que na clínica são
o caso comum (a tabela que existe no catálogo e que a conta não pode ler).

O que estes testes fixam é o que faria o relatório MENTIR:

* tabela grande é FATO — amostrar e varrer com ``LIKE`` de dois curingas nela é
  varredura de tabela inteira no servidor clínico em horário de expediente;
* coluna de identidade e de texto livre não sai amostrada: o que se procura é o
  catálogo ("Documentação de tratamento"), nunca o que escreveram sobre alguém;
* consulta que FALHA não pode virar "não achei". É a mesma distinção do
  ``FalhaDeLeitura`` do ``capa_db`` — no relatório, permissão negada tem de
  aparecer como permissão negada, senão quem lê conclui que a atividade não
  existe e vai embora.

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

import atividades  # noqa: E402

# Um DW de brinquedo com o formato do de verdade: uma dimensão pequena (o
# catálogo), um fato grande (uma linha por paciente por atividade) e uma tabela
# que a conta não pode ler.
_COLUNAS = {
    ("DWH", "DimActivity"): [
        ("DimActivityID", "int", None),
        ("ActivityCode", "varchar", 32),
        ("ActivityName", "nvarchar", 100),
        ("ActivityCategory", "nvarchar", 60),
        ("Department", "nvarchar", 60),
        ("PatientComment", "nvarchar", 4000),
        ("LastModifiedDate", "datetime", None),
    ],
    ("DWH", "FactPatientActivity"): [
        ("DimActivityID", "int", None),
        ("DimPatientID", "int", None),
        ("Status", "nvarchar", 40),
    ],
    ("DWH", "DimLookup"): [
        ("DimLookupID", "int", None),
        ("LookupDescriptionPTB", "nvarchar", 120),
    ],
    ("DWH", "DimResource"): [
        ("ResourceLogin", "varchar", 64),
        ("ResourceFullName", "nvarchar", 100),
    ],
}

_VALORES = {
    ("DWH", "DimActivity", "ActivityName"): [
        "Documentação de tratamento", "Conferência de plano", "Simulação"],
    ("DWH", "DimActivity", "ActivityCategory"): ["Documentação", "Física"],
    ("DWH", "DimActivity", "ActivityCode"): ["DOC01", "QA02"],
    ("DWH", "DimActivity", "Department"): ["Física Médica", "Enfermagem"],
    ("DWH", "DimActivity", "PatientComment"): ["não devia sair no relatório"],
    ("DWH", "DimLookup", "LookupDescriptionPTB"): ["Documentação", "Feminino"],
    # O login COM o domínio grudado: é a forma que faria a igualdade dizer
    # "não existe" para quem está lá.
    ("DWH", "DimResource", "ResourceLogin"): [
        "CLINICA\\geovani.pena", "mario.hayashi"],
}

_TAMANHOS = {("DWH", "DimActivity"): 3,
             ("DWH", "FactPatientActivity"): 4_000_000,
             ("DWH", "DimLookup"): 900,
             ("DWH", "DimResource"): 40}

_SEM_PERMISSAO = ("DWH", "TaskProibida")


class _CursorFalso:
    """Responde pelo pedaço de SQL, e ANOTA tudo que foi perguntado.

    Anotar é metade do teste: o que se quer provar de algumas consultas não é a
    resposta, é que elas NÃO foram feitas contra a tabela de milhões de linhas.
    """

    def __init__(self, perguntas: list):
        self._perguntas = perguntas
        self._linhas: list = []

    def execute(self, sql, *params):
        self._perguntas.append((" ".join(sql.split()), params))
        self._linhas = _responder(sql, params)
        return self

    def fetchall(self):
        return self._linhas


def _responder(sql, params):
    achatado = " ".join(sql.split())
    if "INFORMATION_SCHEMA.TABLES" in achatado:
        tudo = list(_COLUNAS) + [_SEM_PERMISSAO]
        pedacos = [str(p).strip("%").lower() for p in params]
        return [(e, t, "BASE TABLE") for e, t in tudo
                if any(p in t.lower() for p in pedacos)]
    if "INFORMATION_SCHEMA.COLUMNS" in achatado and "COLUMN_NAME LIKE" in achatado:
        pedacos = [str(p).strip("%").lower() for p in params]
        return [(e, t, c) for (e, t), cols in _COLUNAS.items()
                for c, _tipo, _larg in cols
                if any(p in c.lower() for p in pedacos)]
    if "INFORMATION_SCHEMA.COLUMNS" in achatado:
        chave = (params[0], params[1])
        if chave == _SEM_PERMISSAO:
            raise RuntimeError("SELECT permission denied on object")
        return _COLUNAS.get(chave, [])
    if "sys.dm_db_partition_stats" in achatado:
        return [(_TAMANHOS.get((params[0], params[1])),)]
    if achatado.startswith("SELECT COUNT(*)"):
        return [(0,)]
    if achatado.startswith("SELECT MAX("):
        return [("2026-08-31 22:10:00",)]
    if achatado.startswith("SELECT DISTINCT TOP"):
        esquema, tabela, coluna = _do_select(achatado)
        if (esquema, tabela) == _SEM_PERMISSAO:
            raise RuntimeError("SELECT permission denied on object")
        valores = _VALORES.get((esquema, tabela, coluna), [])
        if "LIKE ?" in achatado:
            # TODOS os parâmetros, não só o primeiro: a busca de logins manda
            # um LIKE por login na mesma consulta.
            alvos = [str(p).strip("%").lower() for p in params]
            valores = [v for v in valores
                       if any(alvo in v.lower() for alvo in alvos)]
        return [(v,) for v in valores]
    return []


def _do_select(achatado):
    """``[DWH].[DimActivity]`` e ``[ActivityName]`` de volta para nomes."""
    # ``split("]")[0]`` e não ``rstrip("]")``: o pedaço que sobra é
    # "ActivityName] FROM ", com espaço DEPOIS do colchete — o rstrip não tirava
    # nada e a coluna saía com lixo, o que fazia o banco falso responder vazio
    # para tudo e o teste acusar a ferramenta por um erro do próprio teste.
    coluna = achatado.split("[", 2)[1].split("]", 1)[0]
    depois = achatado.split("FROM [", 1)[1]
    esquema, resto = depois.split("].[", 1)
    return esquema, resto.split("]", 1)[0], coluna


class _ConexaoFalsa:
    def __init__(self):
        self.perguntas: list = []
        self.timeout = 0

    def cursor(self):
        return _CursorFalso(self.perguntas)


class Relatorio(unittest.TestCase):

    def setUp(self):
        self.cx = _ConexaoFalsa()
        self.linhas: list = []
        atividades.relatorio(self.cx, atividades.PADROES,
                             atividades.PALAVRA, self.linhas.append)
        self.texto = "\n".join(self.linhas)

    def _perguntas(self):
        return [sql for sql, _ in self.cx.perguntas]

    def test_acha_a_atividade_de_documentacao(self):
        """O que a viagem à clínica foi buscar: o nome e a categoria."""
        self.assertIn("Documentação de tratamento", self.texto)
        self.assertIn("DWH.DimActivity.ActivityCategory", self.texto)

    def test_o_fato_nao_e_varrido(self):
        """LIKE com curinga dos dois lados numa Fact de 4 milhões de linhas é
        varredura de tabela inteira no servidor clínico, em expediente. A
        tabela sai no relatório com contagem e colunas — e nada além disso."""
        self.assertIn("FactPatientActivity", self.texto)
        for sql in self._perguntas():
            self.assertNotIn("FROM [DWH].[FactPatientActivity]", sql,
                             f"consultou o fato: {sql}")

    def test_nao_amostra_texto_de_paciente(self):
        """``PatientComment`` é onde vai parar o que escreveram sobre alguém.
        Ele existe na tabela e TEM de aparecer na lista de colunas — o que não
        pode é o conteúdo dele sair impresso."""
        self.assertIn("PatientComment", self.texto)
        self.assertNotIn("não devia sair no relatório", self.texto)

    def test_permissao_negada_nao_vira_ausencia(self):
        """Tabela que a conta não pode ler tem de dizer isso com todas as
        letras. Silenciar aqui faria quem lê o relatório concluir que a
        atividade não existe — e ir embora sem ela."""
        self.assertIn("TaskProibida", self.texto)
        self.assertIn("PERMISSÃO", self.texto)

    def test_dimlookup_entra_mesmo_sem_casar_o_nome(self):
        """O nome ``DimLookup`` não tem "activity" nenhum, e é lá que o DW
        guarda o vocabulário traduzido — é candidato natural a ter
        "Documentação" como categoria."""
        self.assertIn("DWH.DimLookup.LookupDescriptionPTB", self.texto)


class Frescor(unittest.TestCase):
    """O ``--frescor`` é opt-in porque VARRE, e a defasagem da carga é o que
    decide se dá para mostrar atividade pendente na abertura do app: DW é
    armazém, não o banco vivo do ARIA."""

    def setUp(self):
        self.cx = _ConexaoFalsa()
        self.linhas: list = []

    def _relatorio(self):
        return atividades.relatorio(self.cx, atividades.PADROES,
                                    atividades.PALAVRA, self.linhas.append)

    def test_nao_varre_sem_pedir(self):
        self._relatorio()
        for sql, _ in self.cx.perguntas:
            self.assertNotIn("SELECT MAX(", sql)

    def test_so_coluna_de_data(self):
        """``MAX`` de ``ActivityName`` responderia o último nome em ordem
        alfabética — número sem significado nenhum, com o custo de uma
        varredura."""
        atividades._frescor(self.cx, self._relatorio(), self.linhas.append)
        maximos = [sql for sql, _ in self.cx.perguntas
                   if sql.startswith("SELECT MAX(")]
        self.assertTrue(maximos)
        for sql in maximos:
            self.assertIn("[LastModifiedDate]", sql)

    def test_sem_palavra_nao_procura(self):
        """A passagem pelas tabelas de CARGA reusa o mesmo relatório; procurar
        'Documentação' nelas seria ruído no meio do que se foi ler."""
        atividades.relatorio(self.cx, atividades.PADROES, "",
                             self.linhas.append)
        self.assertNotIn("Onde aparece", "\n".join(self.linhas))


class Logins(unittest.TestCase):
    """O ARIA e o ISOCENTRO usam o MESMO login (dito em 01/09/2026) — o
    que não dispensa conferir. Dois físicos ativos têm login fora do padrão
    ``nome.sobrenome`` (``adriano``, ``isabela``), e é justo para eles que a
    consulta voltaria vazia: vazia se lê como "estou em dia"."""

    def setUp(self):
        self.cx = _ConexaoFalsa()
        self.linhas: list = []

    def _conferir(self, logins):
        atividades._quem_e_quem(self.cx, {}, logins, self.linhas.append)
        return "\n".join(self.linhas)

    def test_acha_login_com_dominio_grudado(self):
        """``CLINICA\\geovani.pena``: por isso a busca é LIKE e não
        igualdade — a igualdade diria "não existe" para quem está lá."""
        texto = self._conferir(["geovani.pena"])
        self.assertIn("CLINICA\\geovani.pena", texto)
        self.assertIn("geovani.pena (DimResource.ResourceLogin)", texto)

    def test_login_ausente_sai_nomeado(self):
        """Não achar tem de sair ESCRITO, com o login. É o que vira o recado
        "não te encontrei no ARIA" em vez de uma lista vazia."""
        texto = self._conferir(["geovani.pena", "adriano"])
        self.assertIn("NÃO encontrados: adriano", texto)

    def test_diz_onde_procurou(self):
        """O primeiro relatório da clínica (01/09/2026) voltou com "Encontrados:
        nenhum" e não deixava distinguir "o DW não guarda login" de "a tabela
        que tem o login foi pulada por ser grande" — conclusões OPOSTAS sobre o
        painel inteiro. Por isso as duas listas saem escritas."""
        atividades._quem_e_quem(self.cx, {("DWH", "FactPatientActivity"):
                                          4_000_000},
                                ["geovani.pena"], self.linhas.append)
        texto = "\n".join(self.linhas)
        self.assertIn("tabelas lidas:", texto)
        self.assertIn("PULADAS por tamanho: FactPatientActivity", texto)

    def test_le_os_fisicos_do_cadastro(self):
        """A lista sai do ``usuarios.json``, não de uma cópia digitada aqui —
        cópia envelhece em silêncio no dia em que alguém entra no serviço.

        Confere a REGRA contra o próprio ``auth.listar()``, e não nomes: o
        cadastro é do serviço e muda, e ``ISOCENTRO_USERS_DIR`` aponta para outro
        arquivo em cada estação. Fixar "geovani.pena" aqui daria um teste que
        passa nesta máquina e reprova na clínica.
        """
        from isocentro.dados import auth
        esperado = {u["usuario"] for u in auth.listar()
                    if u.get("ativo", True) and u.get("papel") == "fisico"}
        self.assertEqual(set(atividades._logins_do_app()), esperado)
        naoe = {u["usuario"] for u in auth.listar()
                if u.get("papel") != "fisico"}
        self.assertFalse(naoe & set(atividades._logins_do_app()))


class ArquivoDeSaida(unittest.TestCase):
    """O `-o` grava mesmo quando NÃO deu para conectar.

    Custou uma ida e volta em 01/09/2026: o `main` devolvia 2 antes do
    `finally`, e o arquivo pedido não nascia. A recusa ficava só no console do
    `runas` — que fecha — e, de fora, "não rodou" e "rodou e o servidor
    recusou" ficavam idênticos. É a mesma distinção do `FalhaDeLeitura`:
    silêncio é o pior desfecho.
    """

    def test_grava_a_recusa_com_o_motivo(self):
        with tempfile.TemporaryDirectory() as pasta:
            destino = Path(pasta) / "saida.txt"
            # Zerar ``ISOCENTRO_DB_SERVIDOR`` NÃO basta: sem a variável, o
            # ``capa_db._config`` cai no ``config_servico.json``, que nesta
            # máquina aponta o SRVINSIGHT — e o teste ia à rede de verdade
            # (medido: saiu a recusa de SSPI). Quem responde "há servidor?" é
            # o ``configurado``, e é ele que se troca.
            #
            # Guardar e DEVOLVER a função, nunca ``del``: ``modulo.f = falsa``
            # grava no ``__dict__`` do módulo e o ``del`` depois some com a
            # ORIGINAL para o resto do processo.
            antes = atividades.capa_db.configurado
            atividades.capa_db.configurado = lambda: False
            try:
                codigo = atividades.main(["-o", str(destino)])
                existe = destino.exists()
                texto = destino.read_text(encoding="utf-8") if existe else ""
            finally:
                atividades.capa_db.configurado = antes
        self.assertEqual(codigo, 2)
        self.assertTrue(existe, "o -o não gravou nada quando não conectou")
        self.assertIn("Nenhum servidor apontado", texto)

    def test_nao_apaga_relatorio_que_ja_existe(self):
        """Em 01/09/2026 o relatório bom das 17:29 (49 KB, o catálogo das 40
        tabelas de atividade) foi APAGADO às 17:50 por uma rodada que só
        conseguiu escrever a recusa de SSPI. O `.bat` fixa o nome do arquivo, e
        quem roda de novo não espera perder o que já tinha."""
        with tempfile.TemporaryDirectory() as pasta:
            destino = Path(pasta) / "saida.txt"
            destino.write_text("o relatório bom", encoding="utf-8")
            antes = atividades.capa_db.configurado
            atividades.capa_db.configurado = lambda: False
            try:
                atividades.main(["-o", str(destino)])
            finally:
                atividades.capa_db.configurado = antes
            self.assertEqual(destino.read_text(encoding="utf-8"),
                             "o relatório bom")
            # E a rodada nova não se perdeu: foi para um irmão com data e hora.
            irmaos = [p for p in Path(pasta).iterdir() if p != destino]
            self.assertEqual(len(irmaos), 1)
            self.assertIn("Nenhum servidor apontado",
                          irmaos[0].read_text(encoding="utf-8"))


class Amostravel(unittest.TestCase):

    def test_max_do_sql_server_fica_de_fora(self):
        """``CHARACTER_MAXIMUM_LENGTH`` negativo é o ``MAX``: campo de texto
        livre. Sem esta linha, um ``nvarchar(MAX)`` passaria por -1 < 200."""
        self.assertFalse(atividades._amostravel("Descricao", "nvarchar", -1))

    def test_a_largura_padrao_do_dw_entra(self):
        """256 é a largura padrão do DW da Varian para descrição. Com o corte
        em 200, o primeiro relatório saiu sem ``ActivityNamePTB`` e sem
        ``ActivityCategoryPTB`` — achou "Documentação" no código da atividade e
        nunca olhou o nome dela em português."""
        self.assertTrue(atividades._amostravel("ActivityNamePTB",
                                               "nvarchar", 256))
        self.assertFalse(atividades._amostravel("ActivityNote",
                                                "nvarchar", 3000))

    def test_name_nao_esta_no_filtro_de_identidade(self):
        """A trava é por PEDAÇO de nome, e "name" não pode entrar nela:
        ``ActivityName`` é exatamente o que se foi buscar."""
        self.assertTrue(atividades._amostravel("ActivityName", "nvarchar", 100))
        self.assertFalse(atividades._amostravel("PatientFullName", "nvarchar", 100))


class AltasSempreSaem(unittest.TestCase):
    """O quadro das Altas roda mesmo quando há Documentações na frente.

    Custou uma ida à clínica em 23/09/2026: havia um ``return`` no meio do
    ``_rodar_consultas``, herdado de quando a Documentação era a única lista.
    Com dez documentações abertas, a função voltava ali e a seção das altas
    NÃO saía no relatório — e de fora isso é idêntico a "rodou e não achou
    alta nenhuma", que era exatamente a pergunta que se foi responder.
    """

    def _rodar(self, quantas_documentacoes):
        # O ``atividades.py`` importa o módulo DENTRO das funções, então
        # não há ``atividades.atividades_db`` para trocar: quem se troca
        # é o módulo de verdade, que as duas pontas veem.
        from isocentro.banco import atividades_db as adb
        linhas = []
        falsas = [_Atividade() for _ in range(quantas_documentacoes)]
        # Guardar e DEVOLVER as CINCO, inclusive a ``porque_vazio``: estas
        # atribuições gravam no ``__dict__`` do módulo, e uma que não volta
        # segue falsa para o resto do processo — os testes do
        # ``test_atividades_db`` rodam depois e conferem justamente ela.
        nomes = ("todas", "altas", "catalogo", "donos", "porque_vazio")
        antes = {n: getattr(adb, n) for n in nomes}
        adb.todas = lambda *a, **k: list(falsas)
        adb.altas = lambda *a, **k: []
        adb.catalogo = lambda *a, **k: []
        adb.donos = lambda *a, **k: []
        adb.porque_vazio = lambda *a, **k: {
            "degraus": [], "estados": [], "desde": "2026-01-01"}
        try:
            atividades._rodar_consultas(0, linhas.append)
        finally:
            for nome, original in antes.items():
                setattr(adb, nome, original)
        return "\n".join(linhas)

    def test_com_documentacoes_a_secao_das_altas_sai(self):
        self.assertIn("Altas Prontas", self._rodar(10))

    def test_sem_documentacoes_tambem(self):
        self.assertIn("Altas Prontas", self._rodar(0))


class _Atividade:
    """O mínimo que o relatório lê de uma atividade."""
    dono = "Fulano de Tal"
    estado = "Open"
    registro = "9000001"
    paciente = "PACIENTE DE TESTE"
    unidade = "CEL"

    def data_br(self):
        return "25/09/2026"

    def titulo(self):
        return "Documentação"


if __name__ == "__main__":
    unittest.main()
