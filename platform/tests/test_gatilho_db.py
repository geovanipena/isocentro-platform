"""O gatilho: o que faria a automação exportar o plano errado.

Este módulo decide, sozinho e sem ninguém olhando, quais arquivos saem do ARIA
para alimentar o controle de qualidade. Um erro aqui não aparece na tela: ele
aparece como um plano a mais, ou a menos, na pasta.

O que estes testes fixam:

* **o portão fechado.** Sem ``VERIFICADO_EM``, nada é exportado — e o motivo
  distingue as três causas, que pedem providências diferentes;
* **o curso mais recente ATIVO, e só ele.** Num retratamento, o curso anterior
  ainda tem plano aprovado pendurado; exportá-lo mandaria para a sala o
  tratamento passado do mesmo paciente;
* **todos os planos aprovados do curso.** Tratamento de fases tem
  primário e boost, os dois tratam, e um plano por curso faria o
  primário sumir em silêncio;
* **a chave da marca d'água inclui o ESTADO.** Só o UID faria a segunda versão
  de um plano ser vista como já exportada, e a sala receberia a primeira para
  sempre;
* **falha de leitura não vira lista vazia.** Vazio significa "nada a exportar",
  e é assim que uma automação para de funcionar sem ninguém perceber.

Rodar:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import sys
import unittest
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from isocentro.banco import atividades_db  # noqa: E402
from isocentro.banco import capa_db  # noqa: E402
from isocentro.banco import gatilho_db  # noqa: E402


def _atividade(registro, paciente, instancia):
    return atividades_db.Atividade(instancia=instancia, codigo="Documentação",
                                   estado="Open", registro=registro,
                                   paciente=paciente)


# Uma linha da consulta, na ordem que o ``prontos`` desempacota.
def _linha(registro, dim_curso, curso, inicio, setup, uid, revisao=0,
           fracoes=5, estado="Planning Approved", quem="clinica\\fulano",
           criado=None):
    return (registro, dim_curso, curso, inicio, setup, uid, revisao, fracoes,
            estado, quem, criado or datetime(2026, 9, 2, 8, 50))


class _Banco:
    """Substitui as duas fontes e ANOTA o que foi perguntado.

    Guardar e DEVOLVER as funções, nunca ``del``: ``modulo.f = falsa`` grava no
    ``__dict__`` do módulo, e o ``del`` depois some com a ORIGINAL para o resto
    do processo — armadilha já paga neste repositório.
    """

    def __init__(self, janela, linhas, falha=False, com_curso_ativo=None,
                 cursos=None):
        self.janela = janela
        self.linhas = linhas
        self.falha = falha
        # A tabela de CURSOS, que desde 04/09/2026 é quem escolhe o curso. Sem
        # ela explícita, deduz-se das linhas de plano e todos saem ATIVOS — que
        # é o que os testes antigos supunham. Quem quer exercitar o curso
        # aberto SEM plano, ou o curso concluído, passa a lista à mão.
        self.cursos = cursos
        # Quem tem curso ativo, independentemente de ter plano. Sem isto, o
        # paciente com curso aberto e nenhum plano ainda — o estado mais comum
        # — não teria como ser representado, porque ele não aparece em linha
        # nenhuma da consulta de planos.
        self.com_curso_ativo = com_curso_ativo
        self.consultas: list = []
        self._antes_todas = None
        self._antes_consultar = None

    def __enter__(self):
        self._antes_todas = atividades_db.todas
        self._antes_consultar = capa_db._consultar
        atividades_db.todas = lambda desde=None: list(self.janela)
        capa_db._consultar = self._consultar
        return self

    def __exit__(self, *_):
        atividades_db.todas = self._antes_todas
        capa_db._consultar = self._antes_consultar
        return False

    def _consultar(self, sql, *params):
        achatado = " ".join(sql.split())
        self.consultas.append((achatado, params))
        if self.falha:
            raise capa_db.FalhaDeLeitura("sem conexão")
        # Três consultas diferentes, e o teste tem de separá-las: a do curso não
        # toca em plano nenhum, e responder por ela com as linhas de plano
        # esconderia justamente o caso que ela existe para enxergar.
        if "DWH.DimPlan" not in achatado:
            # Duas consultas sem plano, e confundi-las esconde o caso que cada
            # uma existe para ver: a de CURSOS traz cinco colunas por curso
            # (com o estado), a do degrau traz só o registro de quem tem algum
            # curso ativo.
            if "c.CourseId" in achatado:
                if self.cursos is not None:
                    return self._ordenar_cursos(self.cursos, achatado)
                vistos, saida = set(), []
                for l in self.linhas:
                    if (l[0], l[1]) in vistos:
                        continue
                    vistos.add((l[0], l[1]))
                    saida.append((l[0], l[1], l[2], l[3], "ACTIVE",
                                  "Curativo"))
                return self._ordenar_cursos(saida, achatado)
            if self.com_curso_ativo is not None:
                return [(reg,) for reg in self.com_curso_ativo]
            return [(reg,) for reg in sorted({l[0] for l in self.linhas})]
        if "lp.LookupDescriptionENU IN" not in achatado:
            return list(self.linhas)
        return [l for l in self.linhas if l[8] in gatilho_db.APROVADOS]

    @staticmethod
    def _ordenar_cursos(cursos: list, sql: str) -> list:
        """Ordena como o BANCO ordenaria — lendo o ``ORDER BY`` que veio.

        Duas armadilhas de dublê, e as duas custam o mesmo: um teste que passa
        sem guardar nada.

        Devolver na ordem em que recebeu faz todo teste de ordenação passar
        sozinho. E ordenar SEMPRE pela intenção deixa o dublê mais correto que
        o código — o teste continuaria passando com a cláusula apagada do SQL,
        que é exatamente o que ele existe para impedir. Por isso a intenção só
        pesa aqui se ela pesar lá.
        """
        import datetime as _dt

        pela_intencao = "LookupDescriptionPTB IS NULL" in sql

        def chave(c):
            # Intenção vazia por último; dentro de cada grupo, o mais recente
            # primeiro (daí o negativo no timestamp).
            inicio = c[3] or _dt.datetime.min
            vazia = 1 if (pela_intencao and not c[5]) else 0
            return (c[0], vazia, -inicio.timestamp())

        return sorted(cursos, key=chave)


class Portao(unittest.TestCase):
    """Nada sai enquanto a consulta não for conferida contra o banco."""

    def test_a_data_da_conferencia_esta_escrita(self):
        """A data é o portão, e ela é apagada junto se a consulta mudar.

        Mesma trava do ``atividades_db``: mexer no SQL sem refazer a
        conferência tem de apagar a data, e não deixar o portão aberto sobre
        uma medição que não existe mais.
        """
        self.assertTrue(gatilho_db.conferido())
        self.assertTrue(gatilho_db.VERIFICADO_EM)

    def test_portao_fecha_quando_a_data_some(self):
        """Sem conferência, nada é exportado: mandar o plano errado para a sala
        é pior que não mandar nada."""
        antes = gatilho_db.VERIFICADO_EM
        # O ``configurado`` também é fixado aqui: o ``motivo_indisponivel``
        # responde "sem banco apontado" ANTES de olhar a conferência, e na
        # suíte completa ele volta falso pelo ambiente que outro teste deixou.
        # Isolado passaria, junto reprovaria — a dependência de ordem que o
        # ``discover`` alfabético esconde.
        real_conf, real_ativ = capa_db.configurado, atividades_db.disponivel
        gatilho_db.VERIFICADO_EM = ""
        capa_db.configurado = lambda: True
        atividades_db.disponivel = lambda: True
        try:
            self.assertFalse(gatilho_db.conferido())
            self.assertFalse(gatilho_db.disponivel())
            self.assertIn("não foi conferida",
                          gatilho_db.motivo_indisponivel())
        finally:
            gatilho_db.VERIFICADO_EM = antes
            capa_db.configurado = real_conf
            atividades_db.disponivel = real_ativ

    def test_o_motivo_diz_qual_degrau_falta(self):
        """Três causas, três providências. Um aviso só para as três ensina a
        ignorar o aviso."""
        antes = capa_db.configurado
        capa_db.configurado = lambda: False
        try:
            self.assertIn("não está apontado", gatilho_db.motivo_indisponivel())
        finally:
            capa_db.configurado = antes
        # Com banco apontado e a conferência feita, não sobra motivo: é o
        # estado de hoje. A data some no teste acima, que é onde a terceira
        # causa se exercita.
        antes_conf, antes_ativ = capa_db.configurado, atividades_db.disponivel
        capa_db.configurado = lambda: True
        atividades_db.disponivel = lambda: True
        try:
            motivo = gatilho_db.motivo_indisponivel()
        finally:
            capa_db.configurado = antes_conf
            atividades_db.disponivel = antes_ativ
        self.assertEqual(motivo, "")


class CursoMaisRecente(unittest.TestCase):
    """O retratamento: o curso anterior ainda tem plano aprovado pendurado."""

    def setUp(self):
        self.janela = [_atividade("9000019ANA", "Fulana de Tal", 1149015)]
        # Duas linhas, do MESMO paciente, cursos diferentes — como a consulta
        # devolve: mais recente primeiro.
        self.linhas = [
            _linha("9000019ANA", 30658, "C1 SETEMBRO 2026",
                   datetime(2026, 9, 1), "cCRANIO_20Gy", "1.2.3.NOVO"),
            _linha("9000019ANA", 22001, "C1 MARÇO 2025",
                   datetime(2025, 3, 4), "MAMA_D", "1.2.3.VELHO"),
        ]

    def test_so_o_curso_mais_recente_entra(self):
        with _Banco(self.janela, self.linhas):
            saida = gatilho_db.prontos()
        self.assertEqual(len(saida), 1)
        self.assertEqual(saida[0].plan_uid, "1.2.3.NOVO")
        self.assertEqual(saida[0].curso, "C1 SETEMBRO 2026")

    def test_o_curso_ativo_vai_por_PARAMETRO(self):
        """``ACTIVE`` não pode estar escrito dentro do texto do SQL: colado ali,
        um dia alguém escreve o valor com outra caixa e o filtro para de casar
        sem erro nenhum."""
        with _Banco(self.janela, self.linhas) as b:
            gatilho_db.prontos()
        # A consulta de PLANOS, não a primeira: desde 04/09/2026 a primeira é a
        # de cursos, que de propósito não filtra estado nenhum — é ela que
        # mostra, no relatório de conferência, o curso que ficou de fora.
        de_plano = [c for c in b.consultas if "DWH.DimPlan" in c[0]]
        self.assertTrue(de_plano, "nenhuma consulta de plano foi feita")
        sql, params = de_plano[0]
        self.assertNotIn("'ACTIVE'", sql)
        self.assertIn(gatilho_db.CURSO_ATIVO, params)


class TodosOsPlanosAprovados(unittest.TestCase):
    """Tratamento de FASES: primário e boost tratam os dois."""

    def setUp(self):
        self.janela = [_atividade("9000019ANA", "Fulana de Tal", 1149015)]
        self.linhas = [
            _linha("9000019ANA", 30658, "C1 SETEMBRO 2026",
                   datetime(2026, 9, 1), "BOOST", "1.2.3.BOOST",
                   criado=datetime(2026, 9, 2, 10, 0)),
            _linha("9000019ANA", 30658, "C1 SETEMBRO 2026",
                   datetime(2026, 9, 1), "PRIMARIO", "1.2.3.PRIMARIO",
                   criado=datetime(2026, 9, 2, 8, 50)),
        ]

    def test_os_dois_planos_do_curso_saem(self):
        """O caso que derrubou a primeira decisão do serviço.

        Com um plano por curso, o boost aprovado DEPOIS faria o primário nunca
        ser exportado — e os dois tratam. O erro seria silencioso: a pasta
        ficaria com um plano, e um plano é o que se espera ver.
        """
        with _Banco(self.janela, self.linhas):
            saida = gatilho_db.prontos()
        self.assertEqual([p.plano for p in saida], ["BOOST", "PRIMARIO"])

    def test_a_constante_ainda_corta_para_um(self):
        """A decisão continua sendo uma linha, e não escolha espalhada pelo
        código."""
        antes = gatilho_db.UM_PLANO_POR_CURSO
        gatilho_db.UM_PLANO_POR_CURSO = True
        try:
            with _Banco(self.janela, self.linhas):
                saida = gatilho_db.prontos()
        finally:
            gatilho_db.UM_PLANO_POR_CURSO = antes
        self.assertEqual([p.plano for p in saida], ["BOOST"])

    def test_plano_repetido_sai_uma_vez_so(self):
        """Um paciente com duas Documentações abertas traria o mesmo plano
        duas vezes. Plano repetido na pasta é do tipo que ninguém confere."""
        linhas = self.linhas + [self.linhas[0]]
        with _Banco(self.janela, linhas):
            saida = gatilho_db.prontos()
        self.assertEqual([p.plano for p in saida], ["BOOST", "PRIMARIO"])


class Janela(unittest.TestCase):
    """A Documentação é a janela — sem ela, o plano aprovado não sai."""

    def test_paciente_sem_documentacao_nao_entra(self):
        janela = [_atividade("9000019ANA", "Fulana", 1149015)]
        linhas = [
            _linha("9000019ANA", 30658, "C1", datetime(2026, 9, 1),
                   "BOM", "1.2.3.BOM"),
            _linha("9000026XXX", 30700, "C1", datetime(2026, 9, 1),
                   "ALHEIO", "1.2.3.ALHEIO"),
        ]
        with _Banco(janela, linhas):
            saida = gatilho_db.prontos()
        self.assertEqual([p.plan_uid for p in saida], ["1.2.3.BOM"])

    def test_sem_documentacao_nenhuma_nao_pergunta_o_plano(self):
        """Consultar planos sem janela é ida ao servidor clínico para nada."""
        with _Banco([], []) as b:
            saida = gatilho_db.prontos()
        self.assertEqual(saida, [])
        self.assertEqual(b.consultas, [])

    def test_a_instancia_da_atividade_acompanha(self):
        janela = [_atividade("9000019ANA", "Fulana de Tal", 1149015)]
        linhas = [_linha("9000019ANA", 30658, "C1", datetime(2026, 9, 1),
                         "BOM", "1.2.3.BOM")]
        with _Banco(janela, linhas):
            saida = gatilho_db.prontos()
        self.assertEqual(saida[0].instancia, 1149015)
        self.assertEqual(saida[0].paciente, "Fulana de Tal")


class Chave(unittest.TestCase):
    """A identidade na marca d'água."""

    def test_o_estado_entra_na_chave(self):
        """Um plano que sobe de degrau é evento NOVO. Com a chave só no UID, a
        segunda versão seria vista como já exportada e a sala receberia a
        primeira para sempre."""
        a = gatilho_db.Pronto(plan_uid="1.2.3", estado="Planning Approved")
        b = gatilho_db.Pronto(plan_uid="1.2.3", estado="Treatment Approved")
        self.assertNotEqual(a.chave(), b.chave())

    def test_o_mesmo_plano_no_mesmo_estado_e_o_mesmo(self):
        a = gatilho_db.Pronto(plan_uid="1.2.3", estado="Planning Approved")
        b = gatilho_db.Pronto(plan_uid="1.2.3", estado="Planning Approved")
        self.assertEqual(a.chave(), b.chave())


class Falha(unittest.TestCase):

    def test_falha_de_leitura_sobe(self):
        """Vazio significa "nada a exportar". Uma falha que virasse vazio faria
        a automação parar de funcionar sem ninguém perceber — ninguém nota a
        ausência de um arquivo."""
        janela = [_atividade("9000019ANA", "Fulana", 1149015)]
        with _Banco(janela, [], falha=True):
            with self.assertRaises(capa_db.FalhaDeLeitura):
                gatilho_db.prontos()


class PorqueVazio(unittest.TestCase):
    """Onde a lista morreu — as duas causas pedem providências opostas."""

    def test_os_tres_degraus_caem_em_lugares_diferentes(self):
        """Três pacientes, três motivos distintos de não sair nada.

        Os três dão lista vazia e pedem providências opostas: esperar, olhar o
        curso, ou aprovar o plano.
        """
        janela = [_atividade("AAA", "Um", 1), _atividade("BBB", "Dois", 2),
                  _atividade("CCC", "Três", 3)]
        # AAA: curso ativo, plano existe mas em rascunho.
        # BBB: curso ativo, NENHUM plano ainda — o estado mais comum.
        # CCC: nem curso ativo (fechou).
        linhas = [_linha("AAA", 30658, "C1", datetime(2026, 9, 1),
                         "RASCUNHO", "1.2.3.A", estado="Unapproved")]
        with _Banco(janela, linhas, com_curso_ativo=["AAA", "BBB"]):
            conta = gatilho_db.porque_vazio()
        self.assertEqual(conta["documentacoes"], 3)
        self.assertEqual(conta["pacientes"], 3)
        self.assertEqual(conta["com_curso_ativo"], 2)
        self.assertEqual(conta["com_algum_plano"], 1)
        self.assertEqual(conta["com_plano_aprovado"], 0)
        self.assertEqual(conta["prontos"], 0)

    def test_curso_ativo_sem_plano_nao_e_contado_como_curso_fechado(self):
        """O defeito que motivou a consulta separada.

        Contando o curso pela consulta grande — que junta o plano por dentro —,
        o paciente com curso aberto e nenhum plano some, e o diagnóstico manda
        procurar no curso quando o que falta é o plano. Foi o estado do
        9000019ANA por doze horas.
        """
        janela = [_atividade("BBB", "Dois", 2)]
        with _Banco(janela, [], com_curso_ativo=["BBB"]):
            conta = gatilho_db.porque_vazio()
        self.assertEqual(conta["com_curso_ativo"], 1)
        self.assertEqual(conta["com_algum_plano"], 0)


class CursoAntigoAbertoNaoRouba(unittest.TestCase):
    """O retratamento em que ninguém CONCLUIU o curso anterior.

    Até 04/09/2026 o curso escolhido saía da primeira linha de PLANO do
    paciente. Como aquela consulta só devolve curso com plano aprovado, o curso
    novo — aberto e ainda sem plano — não aparecia nela, e o "primeiro" passava
    a ser o ANTIGO: a automação exportaria o tratamento passado do paciente,
    calada, e a pasta mostraria um plano, que é o que se espera ver.

    Isto não é hipótese de laboratório: os dois estados de curso do DW são
    ACTIVE e COMPLETED, e concluir o curso anterior é ato de gente.
    """

    def setUp(self):
        self.janela = [_atividade("9000019ANA", "Fulana de Tal", 1149015)]
        # Dois cursos ATIVOS. O novo (30658, setembro) não tem plano nenhum; o
        # velho (30001, março) tem um aprovado, pendurado desde o tratamento
        # anterior.
        self.cursos = [
            ("9000019ANA", 30658, "C2 SETEMBRO 2026", datetime(2026, 9, 1),
             "ACTIVE", "Curativo"),
            ("9000019ANA", 30001, "C1 MARCO 2026", datetime(2026, 3, 1),
             "ACTIVE", "Curativo"),
        ]
        self.linhas = [
            _linha("9000019ANA", 30001, "C1 MARCO 2026", datetime(2026, 3, 1),
                   "cMAMA_VELHO", "1.2.3.VELHO"),
        ]

    def test_nada_sai_quando_o_curso_novo_ainda_nao_tem_plano(self):
        with _Banco(self.janela, self.linhas, cursos=self.cursos):
            saida = gatilho_db.prontos()
        self.assertEqual(saida, [], "exportou o plano do curso ANTERIOR")

    def test_o_dossie_diz_que_o_plano_e_que_falta(self):
        """E diz no degrau, não por omissão: "curso fechou" e "plano ainda não
        existe" pedem providências opostas."""
        with _Banco(self.janela, self.linhas, cursos=self.cursos):
            dossies = gatilho_db.conferencia()
        self.assertEqual(len(dossies), 1)
        self.assertEqual(dossies[0].degrau, "curso ativo, nenhum plano ainda")
        # O curso velho aparece, marcado como NÃO escolhido: é o que permite
        # ver, no papel, que o filtro deixou o certo de fora.
        escolhidos = [c for c in dossies[0].cursos if c[5]]
        self.assertEqual([c[1] for c in escolhidos], ["C2 SETEMBRO 2026"])


class CursoDeQANaoRoubaOLugar(unittest.TestCase):
    """Medido contra o banco em 04/09/2026, e o gatilho estava errando.

    O paciente 9000024ANA tinha DOIS cursos ativos: ``C1 SETEMBRO 2026`` (o
    tratamento, aberto 01/09) e ``QA_C1_SET_2026`` (aberto 03/09). Escolhendo o
    mais recente entre os ativos, o gatilho ficava com o de QA — e os planos
    que sairiam eram os de verificação, de UMA fração.

    Isso inverte o propósito da automação: ela existe para alimentar o controle
    de qualidade, não para sair dele. O curso de QA vem com a intenção de
    tratamento VAZIA, e é por aí que o ``capa_db._SQL_CURSO`` já o mandava para
    o fim desde 18/08/2026 — a cláusula é a mesma.
    """

    def setUp(self):
        self.janela = [_atividade("9000024ANA", "Amostra, Beltrano Sicrano",
                                  1160392)]
        # Na ordem CRUA, com o de QA na frente por ser o mais recente — que é
        # exatamente o que o gatilho escolhia antes. Quem tem de virar o jogo é
        # a cláusula da intenção, e o dublê a aplica como o banco aplicaria.
        self.cursos = [
            ("9000024ANA", 30693, "QA_C1_SET_2026", datetime(2026, 9, 3),
             "ACTIVE", None),
            ("9000024ANA", 30655, "C1 SETEMBRO 2026", datetime(2026, 9, 1),
             "ACTIVE", "Curativo"),
        ]
        self.linhas = [
            _linha("9000024ANA", 30693, "QA_C1_SET_2026", datetime(2026, 9, 3),
                   "1F_gPULMAO_E", "1.2.QA", fracoes=1),
            _linha("9000024ANA", 30655, "C1 SETEMBRO 2026",
                   datetime(2026, 9, 1), "gPULMAO_E", "1.2.REAL", fracoes=15),
        ]

    def test_sai_o_plano_do_TRATAMENTO_e_nao_o_da_verificacao(self):
        with _Banco(self.janela, self.linhas, cursos=self.cursos):
            saida = gatilho_db.prontos()
        self.assertEqual([p.plan_uid for p in saida], ["1.2.REAL"])

    def test_a_clausula_da_intencao_vai_no_SQL_e_nao_no_Python(self):
        """Escrita nos dois lugares, um dia eles discordam — e a discordância
        seria justamente sobre qual plano vai para a sala."""
        with _Banco(self.janela, self.linhas, cursos=self.cursos) as b:
            gatilho_db.prontos()
        de_curso = [c for c in b.consultas
                    if "c.CourseId" in c[0] and "DWH.DimPlan" not in c[0]]
        self.assertTrue(de_curso, "não perguntou pelos cursos")
        self.assertIn("LookupDescriptionPTB IS NULL", de_curso[0][0])

    def test_o_dossie_mostra_a_intencao_dos_dois(self):
        """É ela que explica por que o curso mais NOVO perdeu. Sem isso no
        papel, a escolha parece a regra da data e ninguém questiona."""
        with _Banco(self.janela, self.linhas, cursos=self.cursos):
            d = gatilho_db.conferencia()[0]
        intencoes = {c[1]: c[4] for c in d.cursos}
        self.assertEqual(intencoes["QA_C1_SET_2026"], "")
        self.assertEqual(intencoes["C1 SETEMBRO 2026"], "Curativo")
        escolhido = [c[1] for c in d.cursos if c[5]]
        self.assertEqual(escolhido, ["C1 SETEMBRO 2026"])


class ConferenciaTemUmaLinhaPorPaciente(unittest.TestCase):
    """A saída que se compara com o ARIA — e ela não pode esconder ausência.

    A primeira rodada, em 02/09/2026, listou os planos que SAÍRAM. Uma lista de
    vencedores responde "estes estão certos?" e não responde "faltou alguém?",
    que é a pergunta que decide se a automação pode ser ligada.
    """

    def test_quem_nao_saiu_tambem_tem_linha(self):
        janela = [_atividade("AAA", "Um", 1), _atividade("BBB", "Dois", 2),
                  _atividade("CCC", "Tres", 3)]
        linhas = [
            # AAA: aprovado, sai.
            _linha("AAA", 10, "C1", datetime(2026, 9, 1), "cBOM", "1.2.BOM"),
            # BBB: existe, mas rejeitado.
            _linha("BBB", 20, "C1", datetime(2026, 9, 1), "1", "1.2.RUIM",
                   estado="Rejected"),
        ]
        cursos = [("AAA", 10, "C1", datetime(2026, 9, 1), "ACTIVE",
                   "Curativo"),
                  ("BBB", 20, "C1", datetime(2026, 9, 1), "ACTIVE",
                   "Curativo"),
                  # CCC: o curso fechou.
                  ("CCC", 30, "C1", datetime(2026, 1, 1), "COMPLETED",
                   "Curativo")]
        with _Banco(janela, linhas, cursos=cursos):
            dossies = {d.registro: d for d in gatilho_db.conferencia()}
        self.assertEqual(sorted(dossies), ["AAA", "BBB", "CCC"])
        self.assertTrue(dossies["AAA"].saiu)
        self.assertEqual(dossies["AAA"].degrau, "pronto")
        self.assertFalse(dossies["BBB"].saiu)
        self.assertIn("nenhum em", dossies["BBB"].degrau)
        self.assertEqual(dossies["CCC"].degrau, "nenhum curso ATIVO")

    def test_o_plano_recusado_aparece_com_o_estado(self):
        """Metade da prova de que o filtro funciona é ver o que ele recusou.

        Em 02/09/2026 o curso 30658 tinha um ``Rejected`` ao lado do bom, e só
        o bom saiu — mas isso só foi possível afirmar porque a sonda havia
        listado os dois antes. O relatório passa a listar sozinho.
        """
        janela = [_atividade("BBB", "Dois", 2)]
        linhas = [_linha("BBB", 20, "C1", datetime(2026, 9, 1), "1",
                         "1.2.RUIM", estado="Rejected")]
        with _Banco(janela, linhas):
            dossie = gatilho_db.conferencia()[0]
        self.assertEqual(len(dossie.planos), 1)
        setup, uid, _rev, estado, _quem, _criado, sai = dossie.planos[0]
        self.assertEqual((setup, estado, sai), ("1", "Rejected", False))

    def test_falha_de_leitura_sobe(self):
        """Vazio aqui diria "conferi e não há nada" — que é a mentira que a
        conferência inteira existe para não contar."""
        janela = [_atividade("AAA", "Um", 1)]
        with _Banco(janela, [], falha=True):
            with self.assertRaises(capa_db.FalhaDeLeitura):
                gatilho_db.conferencia()


if __name__ == "__main__":
    unittest.main()
