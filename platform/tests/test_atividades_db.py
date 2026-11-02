"""As atividades do ARIA: o que a consulta promete antes de ter rodado.

Estas consultas **nunca foram feitas contra o banco de verdade** — as colunas
vieram do catálogo do DW em 01/09/2026, não de linhas que voltaram. O que se
pode travar hoje, e é o que está aqui, são as decisões que ficariam erradas em
silêncio quando a conexão existir:

* **portão fechado é tela muda**: com ``VERIFICADO_EM`` vazio, ``disponivel()``
  é falso e o motivo distingue "sem banco apontado" (o admin resolve) de "ainda
  não conferi" (trabalho meu). O mesmo desenho do ``tratamento_db``;
* **estado desconhecido APARECE**: a lista de estados fechados é negativa de
  propósito. Com lista positiva, um estado novo no ARIA sumiria da tela, e
  sumir é o erro que este painel não pode cometer;
* **falha não vira lista vazia**: vazio significa "nada pendente", e é assim que
  alguém fecha o programa achando que está em dia;
* **sem vínculo não se adivinha**: sem ``ctrResourceSer``, nem as de todo mundo
  nem as de ninguém — as duas piores respostas possíveis.

Rodar:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import datetime
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from isocentro.banco import atividades_db  # noqa: E402
from isocentro.banco import capa_db  # noqa: E402


class _CursorFalso:
    """Casa a consulta por um pedaço do texto dela e guarda os parâmetros."""

    def __init__(self, respostas: dict, feitas: list):
        self._respostas = respostas
        self._feitas = feitas
        self._linhas: list = []

    def execute(self, sql, *params):
        self._feitas.append((" ".join(sql.split()), params))
        self._linhas = []
        for marca, linhas in self._respostas.items():
            if marca in " ".join(sql.split()):
                self._linhas = linhas
                break
        return self

    def fetchall(self):
        return self._linhas


class _ConexaoFalsa:
    def __init__(self, respostas: dict):
        self.respostas = respostas
        self.feitas: list = []
        self.timeout = 0

    def cursor(self):
        return _CursorFalso(self.respostas, self.feitas)


class _Base(unittest.TestCase):
    """Troca a conexão do ``capa_db`` — guardando e devolvendo a função.

    ``modulo.f = falsa`` grava no ``__dict__`` do módulo, e um ``del`` depois
    someria com a ORIGINAL para o resto do processo (armadilha já paga neste
    repositório, com o ``capa_db.conexao``).
    """

    respostas: dict = {}

    def setUp(self):
        # CÓPIA, e não a de classe: um teste que troca uma resposta para medir
        # outro caso escrevia no dicionário compartilhado, e o teste seguinte
        # (alfabeticamente, e só ele) recebia a linha alterada. O sintoma é uma
        # reprovação num teste que ninguém tocou.
        self.cx = _ConexaoFalsa(dict(self.respostas))
        self._conexao_real = capa_db.conexao
        capa_db.conexao = lambda: self.cx

    def tearDown(self):
        capa_db.conexao = self._conexao_real


_UMA_LINHA = [(
    880123,                              # ctrActivityInstanceSer
    "Documentação",                      # ActivityCode
    "Documentação de tratamento",        # ActivityNamePTB
    "10 Admin Física",                   # categoria
    "Open",                              # AppointmentStatus
    "9000013CEL",                        # PatientId
    # É assim que o DW grava: sobrenome primeiro, caixa alta, conectivo no fim.
    "SOUZA SANTOS, FULANO DE",           # PatientFullName
    datetime.datetime(2026, 8, 28, 14, 30),
    "Geovani Pena",                      # FullName do dono
)]


class Portao(unittest.TestCase):

    def test_aberto_porque_foi_conferido(self):
        """O portão abriu em 02/09/2026, e o que o abriu está escrito ao lado
        dele: duas Documentações, iguais às que o ARIA mostrava na mesma hora,
        em 0,3 s contra o limite de 6 s.

        Este teste não protege a data — protege o hábito: quem apagar a
        conferência tem de apagar a data junto, e não deixar o portão aberto
        sobre uma medição que não existe mais.
        """
        self.assertTrue(atividades_db.conferido())
        self.assertTrue(atividades_db.VERIFICADO_EM)

    def test_portao_fecha_a_tela_quando_a_data_some(self):
        """Lista de pendências plausível e errada é pior que lista nenhuma:
        quem a lê fecha o programa achando que está em dia."""
        antes = atividades_db.VERIFICADO_EM
        # O ``configurado`` também tem de ser fixado aqui: o
        # ``motivo_indisponivel`` responde "sem banco apontado" ANTES de olhar
        # a conferência, e na suíte completa ele volta falso por causa do
        # ambiente que outro teste deixou. Isolado passava, junto reprovava —
        # a dependência de ordem que o ``discover`` alfabético esconde.
        real = capa_db.configurado
        atividades_db.VERIFICADO_EM = ""
        capa_db.configurado = lambda: True
        try:
            self.assertFalse(atividades_db.conferido())
            self.assertIn("conferida", atividades_db.motivo_indisponivel())
        finally:
            atividades_db.VERIFICADO_EM = antes
            capa_db.configurado = real

    def test_o_motivo_separa_as_duas_causas(self):
        """Sem banco apontado é configuração (o admin resolve); sem conferência
        é trabalho meu que não terminou. Um aviso só para as duas ensina a
        ignorar o aviso."""
        real = capa_db.configurado
        capa_db.configurado = lambda: False
        try:
            self.assertIn("Configurações", atividades_db.motivo_indisponivel())
        finally:
            capa_db.configurado = real
        real = capa_db.configurado
        capa_db.configurado = lambda: True
        try:
            # Com banco apontado E conferência feita, não há motivo nenhum: o
            # painel mostra. Um motivo em branco aqui é a resposta certa.
            self.assertEqual(atividades_db.motivo_indisponivel(), "")
            self.assertTrue(atividades_db.disponivel())
        finally:
            capa_db.configurado = real


class Pendentes(_Base):

    respostas = {"FROM DWH.DimActivityTransaction t": _UMA_LINHA}

    def test_traduz_a_linha_do_banco(self):
        (a,) = atividades_db.pendentes(4321)
        self.assertEqual(a.registro, "9000013CEL")
        self.assertEqual(a.estado, "Open")
        self.assertEqual(a.quando, datetime.date(2026, 8, 28))
        self.assertEqual(a.titulo(), "Documentação de tratamento")

    def test_o_paciente_sai_grafado_como_se_escreve(self):
        """O DW grava "SOUZA SANTOS, FULANO DE" e era assim que o nome ia para
        os quadros de Documentação e de Altas Prontas — em caixa alta e
        invertido, ao lado do dono, que vem gravado como se escreve.

        A ``capa_db`` e a ``tratamento_db`` já passavam esta MESMA coluna pelo
        ``de_pessoa``; este módulo nasceu depois e ficou de fora, então o mesmo
        paciente aparecia de dois jeitos em duas telas do programa.
        """
        (a,) = atividades_db.pendentes(4321)
        self.assertEqual(a.paciente, "Fulano de Souza Santos")

    def test_o_dono_copia_a_grafia_do_banco(self):
        """``GetTaskOwnerName.FullName`` já vem como se escreve e carrega as
        iniciais entre parênteses — "Ana Fatima Albuquerque (AC)". Passado pelo
        formatador de nome próprio, o "(AC)" virava "(Ac)"."""
        self.cx.respostas["FROM DWH.DimActivityTransaction t"] = [
            (*_UMA_LINHA[0][:-1], "Ana Fatima Albuquerque (AC)")]
        (a,) = atividades_db.pendentes(4321)
        self.assertEqual(a.dono, "Ana Fatima Albuquerque (AC)")

    def test_filtra_pelo_ctrresourceser(self):
        """O dono é o número, nunca o nome: o banco tem "Nathalia bittencourt
        Bittencourt" e "Danilelle Teles Teles" cadastrados assim, e casar por nome
        mostraria a lista de outra pessoa."""
        atividades_db.pendentes(4321)
        sql, params = self.cx.feitas[-1]
        self.assertIn("o.ctrResourceSer = ?", sql)
        # ``in``, e não ``params[0]``: a ordem dos parâmetros acompanha a ordem
        # dos pedaços no texto, e ela mudou quando o filtro de dono virou
        # opcional. Prender o teste à POSIÇÃO fazia ele reprovar por uma
        # mudança que não tem nada a ver com o que ele protege.
        self.assertIn(4321, params)

    def test_todas_nao_filtra_por_dono(self):
        """A tela pediu o quadro do serviço inteiro, com o dono ao lado — o que
        dispensa o vínculo entre o login do app e o ctrResourceSer."""
        lista = atividades_db.todas()
        sql, _params = self.cx.feitas[-1]
        self.assertNotIn("o.ctrResourceSer", sql)
        self.assertEqual(lista[0].dono, "Geovani Pena")

    def test_bloqueada_pela_predecessora_fica_de_fora(self):
        """"Não fechada" não é "disponível para fazer".

        Medido em 02/09/2026, e foi o usuário quem viu: a consulta devolvia
        OITO tarefas, todas com ``AppointmentStatus = 'Open'``, e no ARIA só
        DUAS estavam disponíveis — as outras seis esperavam a etapa anterior do
        care path. Quem sabe disso é o ``DerivedActivityStatus`` da view de
        predecessora, com o valor ``Pending``, que não existe no fato.
        """
        atividades_db.todas()
        sql, params = self.cx.feitas[-1]
        self.assertIn("GetPredeccesorAndCurrentActivityStatus", sql)
        self.assertIn("Pending", params)

    def test_basta_UMA_predecessora_pendente_para_bloquear(self):
        """A regra é "todas prontas", não "alguma pronta".

        Medido em 02/09/2026 com o despejo cru: a view dá uma linha POR
        PREDECESSORA e o ``DerivedActivityStatus`` é calculado por par. A
        Documentação do 9000015CEL tem duas — uma ``Completed`` (par ``Open``)
        e uma ``Open`` (par ``Pending``). Com junção e filtro por linha, a
        linha boa passava e a tarefa entrava na lista como disponível.

        Por isso o filtro é ``NOT EXISTS`` sobre a view inteira, e não uma
        junção: junção pergunta "existe predecessora pronta?", e a pergunta é
        "resta alguma pendente?".
        """
        atividades_db.todas()
        sql, _params = self.cx.feitas[-1]
        self.assertIn("NOT EXISTS", sql)
        self.assertNotIn("LEFT JOIN DWH.GetPredeccesorAndCurrentActivityStatus",
                         sql)

    def test_sem_predecessora_nenhuma_continua_na_lista(self):
        """Tarefa que não está na view não tem predecessora — está pronta para
        fazer desde o primeiro dia. O ``NOT EXISTS`` a preserva pela própria
        forma; uma junção interna a apagaria."""
        atividades_db.todas()
        sql, _params = self.cx.feitas[-1]
        self.assertIn("AND NOT EXISTS (SELECT 1", " ".join(sql.split()))

    def test_distinct_com_a_instancia_dentro(self):
        """Medido contra o banco em 02/09/2026: cada tarefa voltava TRÊS vezes
        (a mesma instância tem uma linha por recurso no fato), e três linhas
        iguais são lidas como três tarefas.

        O ``DISTINCT`` sozinho seria remédio pior que a doença — ele juntaria
        também duas tarefas DIFERENTES do mesmo paciente, mesma atividade e
        mesmo dia, que existem. Com o ``ctrActivityInstanceSer`` na lista, o
        que é a mesma instância colapsa e o que é outra sobrevive.
        """
        atividades_db.todas()
        sql, _params = self.cx.feitas[-1]
        self.assertIn("SELECT DISTINCT", sql)
        self.assertIn("t.ctrActivityInstanceSer", sql)
        self.assertEqual(atividades_db.todas()[0].instancia, 880123)

    def test_todas_tambem_bate_as_marcas(self):
        atividades_db.todas()
        sql, params = self.cx.feitas[-1]
        self.assertEqual(sql.count("?"), len(params))

    def test_marcas_e_parametros_batem(self):
        """Um ``?`` a mais ou a menos e o driver recusa a consulta inteira —
        ``The SQL contains 10 parameter markers, but 13 parameters were
        supplied`` (medido em 02/09/2026, ao trocar o LIKE pelo código exato).
        A consulta é montada por concatenação, com duas listas de tamanho
        variável: contar à mão é o que falha."""
        atividades_db.pendentes(4321)
        sql, params = self.cx.feitas[-1]
        self.assertEqual(sql.count("?"), len(params))

    def test_so_os_codigos_escolhidos(self):
        """"documentação" aparece no nome de atividades que são outra coisa —
        "Revisar a documentação do paciente" foi excluída em 02/09/2026. Item
        que não é seu numa lista de pendências ensina a ignorar a lista."""
        atividades_db.pendentes(4321)
        sql, params = self.cx.feitas[-1]
        self.assertIn("a.ActivityCode IN", sql)
        self.assertNotIn("ActivityCode LIKE", sql)
        for codigo in atividades_db.CODIGOS:
            self.assertIn(codigo, params)

    def test_sem_vinculo_nao_adivinha(self):
        """Devolver "as de todo mundo" ou "as de ninguém" seriam as duas piores
        respostas possíveis."""
        with self.assertRaises(ValueError):
            atividades_db.pendentes(0)

    def test_estado_desconhecido_aparece(self):
        """A lista de fechados é NEGATIVA de propósito. Com lista positiva, um
        estado novo no ARIA sumiria da tela — e sumir é o erro que este painel
        não pode cometer."""
        sem_estado = [list(_UMA_LINHA[0])]
        # Índice 4: a coluna do estado andou uma casa quando o
        # ``ctrActivityInstanceSer`` entrou na frente do SELECT.
        sem_estado[0][4] = "Estado Que Ninguém Viu Ainda"
        self.cx.respostas = {"FROM DWH.DimActivityTransaction t": sem_estado}
        (a,) = atividades_db.pendentes(4321)
        self.assertEqual(a.estado, "Estado Que Ninguém Viu Ainda")
        sql, _ = self.cx.feitas[-1]
        # Preso ao ESTADO, e não a um "NOT IN" solto no texto: a consulta
        # também tem um ``ActivityCode IN`` legítimo, e a checagem frouxa
        # confundia os dois — reprovou por causa do filtro de código, que não
        # tem nada a ver com o que este teste protege.
        self.assertIn("AppointmentStatus, '') NOT IN", sql)

    def test_recorta_a_janela_de_tempo(self):
        """1,89 milhão de linhas, e quem consulta é a thread da tela: sem
        recorte de data isto é varredura no servidor clínico em expediente."""
        atividades_db.pendentes(4321)
        _sql, params = self.cx.feitas[-1]
        esperado = atividades_db._dias_atras(atividades_db.DIAS_PARA_TRAS)
        self.assertIn(esperado.strftime("%Y-%m-%d"), params)

    def test_a_data_vai_em_texto(self):
        """O driver "SQL Server" (o de 2000, que é o que está nas estações) não
        conhece o tipo DATE: com um ``date`` do Python ele recusa o parâmetro
        antes de consultar — ``HYC00 ... SQLBindParameter``, medido contra o
        banco em 02/09/2026. ISO em texto o SQL Server converte sozinho."""
        atividades_db.pendentes(4321)
        _sql, params = self.cx.feitas[-1]
        datas = [p for p in params if isinstance(p, datetime.date)]
        self.assertEqual(datas, [], "data foi como objeto, não como texto ISO")

    def test_falha_nao_vira_lista_vazia(self):
        """Vazio significa "nada pendente". Confundir os dois é como alguém
        fecha o programa achando que está em dia."""
        real = capa_db.conexao
        capa_db.conexao = lambda: None
        try:
            with self.assertRaises(capa_db.FalhaDeLeitura):
                atividades_db.pendentes(4321)
        finally:
            capa_db.conexao = real


class Donos(_Base):

    respostas = {"FROM DWH.GetTaskOwnerName o": [
        (4321, "Geovani Pena", "GP"),
        (0, "Ninguém", ""),          # sem ctrResourceSer: não serve de vínculo
    ]}

    def test_so_quem_tem_identificador(self):
        """Linha sem ``ctrResourceSer`` não vira opção de vínculo: escolhê-la
        no cadastro daria um usuário que nunca casa com tarefa nenhuma."""
        lista = atividades_db.donos()
        self.assertEqual([d.ctr_resource_ser for d in lista], [4321])
        self.assertEqual(lista[0].rotulo(), "Geovani Pena (GP)")


class PorqueVazio(_Base):
    """Zero é a resposta mais perigosa deste painel: "não há nada pendente" e
    "o meu filtro apagou tudo" são a mesma tela."""

    respostas = {
        "SELECT COUNT(*)": [(7,)],
        "GROUP BY COALESCE": [("Completed", 3), ("Open", 0)],
    }

    def test_afrouxa_um_filtro_por_vez(self):
        d = atividades_db.porque_vazio(1144)
        rotulos = [r for r, _n in d["degraus"]]
        # Sete desde 23/09/2026: eram quatro, e três entraram com o quadro de
        # Altas vazio — ver ``test_separa_sem_dono_de_fechada_de_bloqueada``.
        self.assertEqual(len(rotulos), 7)
        self.assertIn("qualquer atividade e estado", rotulos[0])
        self.assertIn("QUALQUER pessoa", rotulos[2])
        self.assertIn("o join está de pé", rotulos[-1])
        self.assertEqual([n for _r, n in d["degraus"]], [7] * 7)

    def test_separa_sem_dono_de_fechada_de_bloqueada(self):
        """Os três jeitos de a lista zerar precisam de degraus DIFERENTES.

        Com o quadro de Altas Prontas vazio em 23/09/2026 não havia como saber
        qual dos três apagou tudo: o join do dono é INNER (atividade sem
        responsável some sem deixar rastro), o estado pode estar em
        ``FECHADOS``, e a predecessora do care path pode estar bloqueando. Os
        três davam "0" no mesmo degrau, e um diagnóstico que não distingue
        causas não é diagnóstico.
        """
        d = atividades_db.porque_vazio(0)
        rotulos = [r for r, _n in d["degraus"]]
        self.assertTrue(any("SEM exigir dono" in r for r in rotulos))
        self.assertTrue(any("não fechadas" in r for r in rotulos))
        self.assertTrue(any("NÃO bloqueadas" in r for r in rotulos))

    def test_sem_dono_pula_os_degraus_da_pessoa(self):
        """Com dono zero, "quantas tarefas são da pessoa nenhuma" daria zero
        por construção — degrau que sempre dá zero não diagnostica nada, só faz
        o relatório parecer que investigou."""
        d = atividades_db.porque_vazio(0)
        # Cinco: os dois de sempre mais os três que separam as causas.
        self.assertEqual(len(d["degraus"]), 5)
        for sql, _p in self.cx.feitas:
            self.assertNotIn("o.ctrResourceSer", sql)

    def test_altas_diagnosticam_com_os_codigos_delas(self):
        """O diagnóstico do quadro de Altas não pode perguntar pela
        Documentação: os códigos são outros, e a resposta seria sobre a lista
        errada."""
        atividades_db.porque_vazio(
            0, codigos_alvo=atividades_db.CODIGOS_ALTA)
        params = [p for _sql, p in self.cx.feitas]
        self.assertTrue(
            any("Verificar Programação" in str(p) for p in params))
        self.assertFalse(any("Documentação" in str(p) for p in params))

    def test_mostra_os_estados_encontrados(self):
        """Se aqui aparecer um estado que está em ``FECHADOS`` e não devia,
        é a lista de estados que está errada — e ela é a única parte do módulo
        escrita por leitura de vocabulário, sem ver uma linha real."""
        d = atividades_db.porque_vazio(1144)
        self.assertEqual(d["estados"][0], ("Completed", 3))

    def test_as_marcas_batem_em_todo_degrau(self):
        """Mesmo defeito que derrubou a consulta principal em 02/09/2026: SQL
        montado por concatenação, com lista de tamanho variável."""
        atividades_db.porque_vazio(1144)
        for sql, params in self.cx.feitas:
            self.assertEqual(sql.count("?"), len(params), sql)


class Catalogo(_Base):

    respostas = {"FROM DWH.DimActivity a": [
        ("Documentação", "Documentação", "03 Planejamento"),
        ("Review Patient Document", "Revisar a documentação do paciente",
         "Atividades especiais de revisão"),
    ]}

    def test_pede_distinct(self):
        """``DimActivity`` é dimensão HISTÓRICA — uma linha por revisão. Medido
        contra o banco em 01/09/2026: "Documentação" voltou QUATRO vezes,
        idêntica nas três colunas. Lista de escolha com o mesmo item repetido
        faz quem escolhe procurar a diferença que não existe."""
        atividades_db.catalogo()
        sql, _ = self.cx.feitas[-1]
        self.assertIn("SELECT DISTINCT", sql)

    def test_a_categoria_nao_e_documentacao(self):
        """Medido: a atividade "Documentação" está na categoria "03
        Planejamento". Quem procurasse uma CATEGORIA chamada Documentação não
        acharia nada — e concluiria que ela não existe."""
        cat = atividades_db.catalogo()
        self.assertEqual(cat[0].categoria, "03 Planejamento")


class Titulo(unittest.TestCase):

    def test_nao_repete_codigo_e_nome(self):
        """No ARIA o código de várias atividades É o nome delas — "Documentação
        — Documentação" foi o que saiu do primeiro rascunho."""
        a = atividades_db.Atividade(codigo="Documentação", nome="Documentação")
        self.assertEqual(a.titulo(), "Documentação")

    def test_data_invalida_nao_vira_hoje(self):
        """Pendência datada de hoje por engano sobe para o topo da lista — o
        lugar de mais destaque da tela."""
        self.assertIsNone(atividades_db._data("28/08/2026"))
        self.assertIsNone(atividades_db._data(None))


class UnidadeDaAlta(unittest.TestCase):
    """A unidade sai do NOME, nunca do código.

    No catálogo deste serviço o código carrega a nomenclatura ANTIGA: o de CEL
    termina em "UNI", o de BET em "BUE" ou não tem sufixo nenhum. Lida do
    código, a tela diria "UNI" para um paciente do CEL e nada para todo o BET.
    """

    def _unidade(self, codigo, nome):
        return atividades_db.Atividade(codigo=codigo, nome=nome).unidade

    def test_verificar_programacao_nas_tres_unidades(self):
        self.assertEqual(
            self._unidade("Verificar Programação", "Verificar Programação BET"),
            "BET")
        self.assertEqual(
            self._unidade("Verificar Programação UNI",
                          "Verificar Programação CEL"), "CEL")
        self.assertEqual(
            self._unidade("Verificar Programação ANA",
                          "Verificar Programação ANA"), "ANA")

    def test_imprimir_alta_nas_tres_unidades(self):
        self.assertEqual(self._unidade("Imprimir Alta BUE",
                                       "Imprimir Alta BET"), "BET")
        self.assertEqual(self._unidade("Imprimir Alta UNI",
                                       "Imprimir Alta CEL"), "CEL")
        self.assertEqual(self._unidade("Imprimir Alta ANA",
                                       "Imprimir Alta ANA"), "ANA")

    def test_sufixo_desconhecido_fica_vazio(self):
        """Melhor sem etiqueta que com a etiqueta errada."""
        self.assertEqual(self._unidade("Qualquer", "Atividade Nova XYZ"), "")

    def test_as_duas_familias_estao_no_filtro(self):
        """As duas têm o mesmo valor para este quadro (decisão de 23/09/2026):
        ter a Verificar Programação ou a Imprimir Alta aberta quer dizer a
        mesma coisa — há alta daquele paciente esperando."""
        self.assertIn("Verificar Programação UNI", atividades_db.CODIGOS_ALTA)
        self.assertIn("Imprimir Alta UNI", atividades_db.CODIGOS_ALTA)


class JuncaoDoDono(_Base):
    """A Documentação EXIGE dono; as Altas, não. Medido, não escolhido.

    Em 23/09/2026 o quadro de Altas voltava vazio com o usuário vendo 12
    "Imprimir Alta CEL" disponíveis no ARIA. O diagnóstico por família mostrou
    o porquê, na janela de 180 dias: **720** linhas exigindo dono contra
    **2.732** sem exigir — o ``JOIN`` INNER com ``GetTaskOwnerName`` comia 74%
    delas. Com o filtro real aplicado sobravam **zero** com dono e **quinze**
    sem. Estas atividades não têm responsável de ``ActivityOwnerFlag = 1``.

    O INNER da Documentação fica: aquela consulta foi conferida contra o ARIA
    linha a linha em 02/09/2026, e o dono ali é a informação principal da
    lista — tarefa sem responsável seria uma linha que ninguém reconhece como
    sua.
    """

    def _sql_de(self, chamada):
        chamada()
        return [sql for sql, _p in self.cx.feitas
                if "GetTaskOwnerName" in sql and "COUNT(*)" not in sql]

    def test_documentacao_exige_dono(self):
        for sql in self._sql_de(atividades_db.todas):
            self.assertNotIn("LEFT JOIN DWH.GetTaskOwnerName", sql)

    def test_altas_nao_exigem_dono(self):
        for sql in self._sql_de(atividades_db.altas):
            self.assertIn("LEFT JOIN DWH.GetTaskOwnerName", sql)

    def test_o_marcador_nao_sobra_no_sql(self):
        """Um ``{JUNCAO_DONO}`` que escapasse viraria erro de sintaxe no
        servidor clínico — e só lá, porque aqui o banco é falso."""
        for chamada in (atividades_db.todas, atividades_db.altas):
            for sql in self._sql_de(chamada):
                self.assertNotIn("{JUNCAO_DONO}", sql)


class EstadosDasAltas(_Base):
    """O quadro de Altas usa lista POSITIVA e ignora a predecessora.

    Decisão do usuário em 23/09/2026, comparando a consulta com a aba
    "Disponível" do ARIA: *"status da atividade tem que ser disponível ou em
    andamento — não existe isso de pendente"*.

    Os dois lados disso foram medidos. A lista negativa deixava passar **116**
    atividades de alta contra as 13 que o ARIA mostra — os estados que sobravam
    não eram trabalho nenhum. E o ``DerivedActivityStatus`` marcava como
    ``Pending`` quatro atividades que o ARIA exibia como disponíveis, entre
    elas a Imprimir Alta que espera a Verificar Programação do MESMO paciente.

    A Documentação continua com a régua antiga, e não é incoerência: ela bate
    **10 em 10** com o ARIA desse jeito, medido no mesmo dia.
    """

    def _sql_de(self, chamada):
        chamada()
        return [sql for sql, _p in self.cx.feitas
                if "ActivityCode IN" in sql and "COUNT(*)" not in sql]

    def test_altas_filtram_por_estado_aceito(self):
        for sql in self._sql_de(atividades_db.altas):
            self.assertIn("AppointmentStatus, '') IN", sql)
            self.assertNotIn("NOT IN", sql)

    def test_altas_tambem_olham_a_predecessora(self):
        """A lista positiva SOMA-SE ao filtro de predecessora.

        Tirar a predecessora foi tentado e medido em 23/09/2026: vieram 216
        atividades contra as 16 que o ARIA mostrava, quase todas agendadas para
        outubro e novembro — atividades que existem no care path e ainda não
        venceram.
        """
        for sql in self._sql_de(atividades_db.altas):
            self.assertIn("GetPredeccesorAndCurrentActivityStatus", sql)

    def test_documentacao_mantem_a_regua_medida(self):
        for sql in self._sql_de(atividades_db.todas):
            self.assertIn("NOT IN", sql)
            self.assertIn("GetPredeccesorAndCurrentActivityStatus", sql)

    def test_em_andamento_esta_entre_os_aceitos(self):
        self.assertIn("Open", atividades_db.ESTADOS_ABERTOS)
        self.assertIn("In Progress", atividades_db.ESTADOS_ABERTOS)

    def test_altas_exigem_predecessora(self):
        """Atividade ÓRFÃ não é trabalho de ninguém.

        Medido em 23/09/2026: um paciente ANA tinha a Verificar Programação e a
        Imprimir Alta abertas desde abril, as duas com ``ctrPredecessorSer``
        nulo, e o ARIA não as mostrava em aba nenhuma. Passavam justamente por
        não terem o que bloquear — o ``NOT EXISTS`` não acha linha e deixa
        passar. Eram 6 das 20 que a consulta trazia.
        """
        for sql in self._sql_de(atividades_db.altas):
            # O INNER JOIN com a view agrupada já exclui a órfã: ela não tem
            # linha lá, então não casa o join.
            self.assertIn("JOIN (SELECT", sql)
            self.assertIn("pred.bloqueadas = 0", sql)

    def test_documentacao_nao_exige_predecessora(self):
        """A Documentação PODE ser a primeira etapa, e exigir predecessora ali
        apagaria caso legítimo. Além disso ela bate 10 em 10 como está."""
        for sql in self._sql_de(atividades_db.todas):
            self.assertNotIn("pred.bloqueadas", sql)


class AtePeloMenosConcluir(unittest.TestCase):
    """A alta some da lista quando CONCLUI, não antes.

    Regra dita pelo usuário em 23/09/2026: a atividade vale enquanto estiver
    **disponível ou em andamento**. Era o que o filtro já fazia, e virou teste
    porque passou a ser decisão declarada em vez de coincidência — um estado
    novo do ARIA caindo em ``FECHADOS`` por engano tiraria da tela um paciente
    cuja alta ainda não saiu, e sumir dessa lista é indistinguível de "não há
    alta a imprimir".
    """

    def test_em_andamento_continua_na_lista(self):
        self.assertNotIn("In Progress", atividades_db.FECHADOS)

    def test_disponivel_continua_na_lista(self):
        self.assertNotIn("Open", atividades_db.FECHADOS)

    def test_concluida_sai(self):
        self.assertIn("Completed", atividades_db.FECHADOS)
        self.assertIn("Manually Completed", atividades_db.FECHADOS)

    def test_a_que_espera_a_etapa_anterior_nao_entra(self):
        """"Disponível" é diferente de "não fechada": a que espera a
        predecessora do care path ainda não pode ser feita, e uma lista com
        itens que ninguém pode fazer ensina a ignorar a lista."""
        self.assertIn("Pending", atividades_db.BLOQUEADAS)


class UmaLinhaPorPaciente(unittest.TestCase):
    """Duas atividades abertas do mesmo paciente são UMA linha.

    A linha das Altas não mostra qual atividade é (mostra paciente, unidade e
    data), então o paciente com a Verificar Programação E a Imprimir Alta
    abertas sairia duas vezes, com as duas linhas idênticas — e lista com a
    mesma coisa duas vezes é lida como dois pacientes.
    """

    def _atividade(self, instancia, registro, dia, codigo="Imprimir Alta UNI"):
        return atividades_db.Atividade(
            instancia=instancia, codigo=codigo, nome="Imprimir Alta CEL",
            registro=registro, paciente="PACIENTE DE TESTE",
            quando=datetime.date(2026, 9, dia))

    def test_duas_do_mesmo_paciente_viram_uma(self):
        entradas = [self._atividade(1, "111", 25),
                    self._atividade(2, "111", 20,
                                    "Verificar Programação UNI")]
        self.assertEqual(len(atividades_db._uma_por_paciente(entradas)), 1)

    def test_fica_a_mais_antiga(self):
        """É ela que responde a pergunta do quadro: há quanto tempo espera."""
        entradas = [self._atividade(1, "111", 25),
                    self._atividade(2, "111", 20,
                                    "Verificar Programação UNI")]
        self.assertEqual(
            atividades_db._uma_por_paciente(entradas)[0].data_br(),
            "20/09/2026")

    def test_pacientes_diferentes_continuam_separados(self):
        entradas = [self._atividade(1, "111", 25),
                    self._atividade(2, "222", 22)]
        self.assertEqual(len(atividades_db._uma_por_paciente(entradas)), 2)

    def test_sem_registro_nao_colapsa_tudo_numa_linha(self):
        """Registro vazio em duas atividades diferentes não pode virar uma
        linha só: seriam dois pacientes somindo num."""
        entradas = [self._atividade(1, "", 25), self._atividade(2, "", 22)]
        self.assertEqual(len(atividades_db._uma_por_paciente(entradas)), 2)


if __name__ == "__main__":
    unittest.main()
