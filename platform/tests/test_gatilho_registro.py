"""A memória do gatilho: o que faria a automação perder ou repetir um plano.

Este módulo existe por causa de uma coisa vista no ARIA em 02/09/2026: no
espaço de duas horas, a Documentação do 9000019ANA passou de *disponível* a
*em andamento*. O estado da atividade é passageiro, e derivar a janela do
estado ATUAL a cada sondagem perde o gatilho sempre que a mudança cai entre
duas rodadas — em silêncio, porque não há erro nenhum, só um paciente a menos.

O que estes testes fixam:

* **a janela sobrevive à mudança de estado.** É a razão de o módulo existir;
* **a primeira vista nunca se reescreve** — é ela que marca o começo da janela,
  e reescrevê-la faria o prazo nunca vencer;
* **plano já exportado não sai de novo**, e a chave inclui o estado;
* **arquivo ilegível não vira memória vazia.** Vazio significa "nunca vi nada",
  e sob esse significado a automação reexportaria tudo o que já saiu;
* **a marca só é gravada depois** — quem chama grava quando o arquivo chegou
  inteiro, não antes.

Rodar:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from isocentro.banco import atividades_db  # noqa: E402
from isocentro.banco import gatilho_db  # noqa: E402
from isocentro.dominio import gatilho_registro as gr  # noqa: E402


def _ativ(instancia, registro, paciente="Fulano de Tal", estado="Open"):
    return atividades_db.Atividade(instancia=instancia, registro=registro,
                                   paciente=paciente, estado=estado,
                                   codigo="Documentação")


def _pronto(uid, estado="Planning Approved", registro="AAA", plano="P1"):
    return gatilho_db.Pronto(registro=registro, plan_uid=uid, estado=estado,
                             plano=plano, paciente="Fulano de Tal")


class _Pasta:
    """Aponta o registro para um arquivo temporário.

    Guardar e DEVOLVER a função ``caminho``, nunca ``del``: gravar no
    ``__dict__`` do módulo e apagar depois some com a ORIGINAL para o resto do
    processo — armadilha já paga neste repositório.
    """

    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.arquivo = Path(self._tmp.name) / "registro.json"
        self._antes = gr.caminho
        gr.caminho = lambda: self.arquivo
        return self

    def __exit__(self, *_):
        gr.caminho = self._antes
        self._tmp.cleanup()
        return False


class JanelaSobrevive(unittest.TestCase):
    """O motivo de o módulo existir."""

    def test_continua_aberta_depois_de_sair_de_disponivel(self):
        """O caso real: a Documentação virou "em andamento" e, se a janela
        fosse o estado atual, o plano aprovado depois nunca sairia."""
        with _Pasta():
            a = _ativ(1149015, "9000019ANA", "Beltrano, Lauro")
            gr.anotar([a])
            a.estado = "In Progress"
            gr.anotar([a])
            abertas = gr.abertas()
        self.assertIn("9000019ANA", abertas)
        self.assertEqual(abertas["9000019ANA"]["ultimo_estado"], "In Progress")

    def test_continua_aberta_quando_o_ARIA_para_de_devolver(self):
        """Concluída no ARIA, ela some da consulta — e a janela tem de ficar
        até alguém fechá-la, senão o plano aprovado nesse meio-tempo se perde."""
        with _Pasta():
            gr.anotar([_ativ(1149015, "9000019ANA")])
            gr.anotar([])          # a sondagem seguinte não a devolve mais
            self.assertIn("9000019ANA", gr.abertas())

    def test_so_a_primeira_vista_conta(self):
        """Reescrever a primeira vista a cada sondagem faria o prazo nunca
        vencer: a janela ficaria aberta para sempre."""
        with _Pasta():
            gr.anotar([_ativ(1, "AAA")])
            primeira = gr.abertas()["AAA"]["visto_em"]
            gr.anotar([_ativ(1, "AAA", estado="In Progress")])
            self.assertEqual(gr.abertas()["AAA"]["visto_em"], primeira)

    def test_a_mesma_atividade_nao_e_novidade_duas_vezes(self):
        with _Pasta():
            self.assertEqual(len(gr.anotar([_ativ(1, "AAA")])), 1)
            self.assertEqual(gr.anotar([_ativ(1, "AAA")]), [])


class Prazo(unittest.TestCase):

    def test_janela_velha_sai(self):
        """Sem prazo a lista de espera cresce para sempre e ninguém mais a lê."""
        with _Pasta():
            gr.anotar([_ativ(1, "AAA")])
            futuro = datetime.now() + timedelta(days=gr.DIAS_DE_JANELA + 1)
            self.assertEqual(gr.abertas(futuro), {})

    def test_no_prazo_continua(self):
        with _Pasta():
            gr.anotar([_ativ(1, "AAA")])
            quase = datetime.now() + timedelta(days=gr.DIAS_DE_JANELA - 1)
            self.assertIn("AAA", gr.abertas(quase))


class Fechar(unittest.TestCase):

    def test_fechada_sai_da_janela_com_o_motivo(self):
        """"Exportado" e "expirou sem plano" são desfechos opostos; sem
        distingui-los ninguém descobre que um caso ficou pelo caminho."""
        with _Pasta():
            gr.anotar([_ativ(1, "AAA")])
            gr.fechar(1, "exportado")
            self.assertEqual(gr.abertas(), {})
            entrada = gr.ler()["janela"]["1"]
        self.assertEqual(entrada["motivo"], "exportado")
        self.assertTrue(entrada["fechado_em"])

    def test_fechar_duas_vezes_nao_reescreve_a_primeira(self):
        with _Pasta():
            gr.anotar([_ativ(1, "AAA")])
            gr.fechar(1, "exportado")
            quando = gr.ler()["janela"]["1"]["fechado_em"]
            gr.fechar(1, "outro motivo")
            self.assertEqual(gr.ler()["janela"]["1"]["fechado_em"], quando)
            self.assertEqual(gr.ler()["janela"]["1"]["motivo"], "exportado")


class MarcaDagua(unittest.TestCase):

    def test_plano_exportado_nao_sai_de_novo(self):
        with _Pasta():
            p = _pronto("1.2.3")
            self.assertFalse(gr.ja_saiu(p))
            gr.anotar_saida(p)
            self.assertTrue(gr.ja_saiu(p))

    def test_o_mesmo_plano_em_OUTRO_estado_e_evento_novo(self):
        """Subir de Planning Approved para Treatment Approved é versão nova. Com
        a chave só no UID, a sala receberia a primeira para sempre."""
        with _Pasta():
            gr.anotar_saida(_pronto("1.2.3", "Planning Approved"))
            self.assertFalse(gr.ja_saiu(_pronto("1.2.3", "Treatment Approved")))


def _plano(uid, plano, instancia=7, estado="Planning Approved"):
    return gatilho_db.Pronto(registro="AAA", paciente="Fulano de Tal",
                             instancia=instancia, curso="C1", plano=plano,
                             plan_uid=uid, estado=estado)


class EstadoDaDocumentacao(unittest.TestCase):
    """O que a Fichinha mostra ao lado de cada Documentação."""

    def test_janela_aberta_sem_saida_e_preparando(self):
        with _Pasta():
            gr.anotar([_ativ(7, "AAA")])
            estados = gr.estados_da_documentacao()
        self.assertEqual(estados[7]["estado"], gr.PREPARANDO)

    def test_plano_que_saiu_e_pronta_com_os_avisos_do_preparo(self):
        """O aviso de "sem cadastro" tem de chegar à tela: é ele que diz ao
        físico que o posicionamento vai ser montado à mão."""
        with _Pasta():
            gr.anotar([_ativ(7, "AAA")])
            gr.anotar_saida(_plano("1.1", "P1"), "X:/tmp/AAA/C1/P1",
                            {"estado": "pronta", "simulacao": "",
                             "avisos": ["sem cadastro de simulação"]})
            gr.fechar(7, "exportado")
            estados = gr.estados_da_documentacao()
        self.assertEqual(estados[7]["estado"], gr.PRONTA)
        self.assertEqual(estados[7]["avisos"], ["sem cadastro de simulação"])
        self.assertEqual(estados[7]["planos"], ["P1"])

    def test_um_plano_pronto_e_outro_travado_nao_e_pronta(self):
        """Curso com dois planos: a ficha precisa dos dois. Mostrado como
        pronto, o físico abriria um caso pela metade."""
        with _Pasta():
            gr.anotar_saida(_plano("1.1", "P1"), "d", {"avisos": []})
            gr.anotar_incompleto(_plano("1.2", "P2"),
                                 "o DICOM chegou pela metade: 3 arquivo(s)")
            estados = gr.estados_da_documentacao()
        self.assertEqual(estados[7]["estado"], gr.INCOMPLETA)
        self.assertEqual(estados[7]["motivos"],
                         ["P2: o DICOM chegou pela metade: 3 arquivo(s)"])

    def test_incompleto_superado_por_saida_em_outro_estado_nao_conta(self):
        """O ``anotar_saida`` só apaga o incompleto da MESMA chave. Travou em
        Planning Approved e saiu em Treatment Approved: o caso chegou inteiro,
        e a linha não pode ficar "incompleta" para sempre."""
        with _Pasta():
            gr.anotar_incompleto(_plano("1.1", "P1"), "falhou ao buscar")
            gr.anotar_saida(_plano("1.1", "P1", estado="Treatment Approved"),
                            "d", {"avisos": []})
            estados = gr.estados_da_documentacao()
        self.assertEqual(estados[7]["estado"], gr.PRONTA)

    def test_saida_antiga_sem_preparo_avisa_que_nao_conferiu(self):
        """Pronta sem aviso afirmaria uma conferência da simulação que não
        houve — a saída é de antes de a preparação existir."""
        with _Pasta():
            gr.anotar_saida(_plano("1.1", "P1"))
            estados = gr.estados_da_documentacao()
        self.assertEqual(estados[7]["avisos"], [gr.AVISO_SEM_PREPARO])

    def test_janela_vencida_ou_fechada_sem_saida_nao_tem_estado(self):
        """"Preparando" de um caso que venceu diria que a automação ainda
        trabalha nele — e ninguém procuraria o que ficou pelo caminho."""
        with _Pasta():
            gr.anotar([_ativ(7, "AAA"), _ativ(8, "BBB")])
            gr.fechar(8, "venceu sem plano aprovado")
            futuro = datetime.now() + timedelta(days=gr.DIAS_DE_JANELA + 1)
            self.assertNotIn(8, gr.estados_da_documentacao())
            self.assertEqual(gr.estados_da_documentacao(agora=futuro), {})

    def test_pronta_aponta_a_pasta_do_curso(self):
        """A ficha precisa de TODOS os planos do curso. Abrindo a pasta de um
        plano só, o físico conferiria e liberaria a ficha pela metade."""
        with _Pasta():
            gr.anotar_saida(_plano("1.1", "P1"), "X:/tmp/AAA/C1/P1", {})
            gr.anotar_saida(_plano("1.2", "P2"), "X:/tmp/AAA/C1/P2", {})
            estado = gr.estados_da_documentacao()[7]
        self.assertEqual(estado["pasta"], "X:/tmp/AAA/C1")

    def test_planos_em_pastas_diferentes_nao_escolhem_uma(self):
        """Adivinhar uma das mães abriria só parte dos planos, e em silêncio."""
        with _Pasta():
            gr.anotar_saida(_plano("1.1", "P1"), "X:/tmp/AAA/C1/P1", {})
            gr.anotar_saida(_plano("1.2", "P2"), "X:/tmp/AAA/C2/P2", {})
            estado = gr.estados_da_documentacao()[7]
        self.assertEqual(estado["pasta"], "")
        self.assertIn("pastas diferentes", estado["avisos"][0])


class Liberacao(unittest.TestCase):
    """O que acontece com a linha depois de o físico liberar."""

    def test_liberada_deixa_de_ser_pronta(self):
        """Continuando PRONTA, o próximo físico liberaria de novo: uma v2 da
        ficha sem mudança nenhuma."""
        with _Pasta():
            gr.anotar_saida(_plano("1.1", "P1"), "X:/tmp/AAA/C1/P1", {})
            gr.anotar_liberada(7, "fisico1", "Y:/sim/FULANO_AAA/09-2026")
            estado = gr.estados_da_documentacao()[7]
        self.assertEqual(estado["estado"], gr.LIBERADA)
        self.assertEqual(estado["por"], "fisico1")
        self.assertEqual(estado["pasta"], "Y:/sim/FULANO_AAA/09-2026")

    def test_plano_que_sai_de_novo_depois_volta_a_pronta(self):
        """Reaprovado e trazido depois da liberação é ficha nova para conferir.
        Mantida "liberada", ela ficaria escondida atrás da impressão antiga."""
        with _Pasta():
            gr.anotar_saida(_plano("1.1", "P1"), "X:/tmp/AAA/C1/P1", {})
            gr.anotar_liberada(7, "fisico1", "Y:/sim")
            dados = gr.ler()
            dados["liberados"]["7"]["quando"] = "2000-01-01T00:00:00"
            gr._gravar(dados)
            estado = gr.estados_da_documentacao()[7]
        self.assertEqual(estado["estado"], gr.PRONTA)
        self.assertIn("já liberada", estado["avisos"][0])

    def test_arquivo_de_antes_da_liberacao_existir_se_le(self):
        """Arquivo gravado antes de 11/09/2026 não tem a chave: nada liberado,
        que é a verdade — e não KeyError na Fichinha de todas as estações."""
        with _Pasta() as p:
            p.arquivo.write_text('{"versao": 1, "janela": {}, "exportados": {}}',
                                 encoding="utf-8")
            gr.anotar_liberada(7, "fisico1", "Y:/sim")
            self.assertIn("7", gr.ler()["liberados"])


class AListaDoQueLimpar(unittest.TestCase):
    """O que a varredura vai apagar da temporária — frente 4, 14/09/2026."""

    def _parada(self, dias=None):
        dias = gr.DIAS_PARA_LIMPAR_PARADA + 1 if dias is None else dias
        return datetime.now() + timedelta(days=dias)

    def test_curso_com_um_plano_travado_nao_e_limpo(self):
        """A ficha precisa dos dois planos: apagar o que já veio obrigaria a
        trazer o curso inteiro de novo quando o que falta chegasse."""
        with _Pasta():
            gr.anotar_saida(_plano("1.1", "P1"), "X:/tmp/AAA/C1/P1", {})
            gr.anotar_incompleto(_plano("2.2", "P2"),
                                 "o DICOM chegou pela metade")
            self.assertEqual(gr.a_limpar(agora=self._parada()), [])

    def test_limpo_sai_da_lista_e_volta_se_o_plano_sair_de_novo(self):
        """Sem a marca, a limpeza reconsidera o mesmo caso a cada rodada; com
        ela para sempre, o plano reaprovado e trazido depois ficaria lá."""
        with _Pasta():
            gr.anotar_saida(_plano("1.1", "P1"), "X:/tmp/AAA/C1/P1", {})
            self.assertEqual(len(gr.a_limpar(agora=self._parada())), 1)
            gr.anotar_limpeza(7, ["X:/tmp/AAA/C1/P1"], "parada sem liberação")
            self.assertEqual(gr.a_limpar(agora=self._parada()), [])
            # A marca envelhecida à mão, como no teste da liberação: o carimbo
            # tem resolução de SEGUNDO, e limpeza e saída no mesmo teste caem no
            # mesmo segundo — empate que conta como limpo de propósito.
            dados = gr.ler()
            dados["limpos"]["7"]["quando"] = "2000-01-01T00:00:00"
            gr._gravar(dados)
            gr.anotar_saida(_plano("1.1", "P1"), "X:/tmp/AAA/C1/P1", {})
            self.assertEqual(len(gr.a_limpar(agora=self._parada())), 1)

    def test_saida_sem_destino_anotado_nao_vira_limpeza(self):
        """Saída de antes de o destino existir: não há o que apagar, e marcar
        como limpo afirmaria que se apagou algo."""
        with _Pasta():
            gr.anotar_saida(_plano("1.1", "P1"), "", {})
            self.assertEqual(gr.a_limpar(agora=self._parada()), [])

    def test_pronta_com_a_pasta_apagada_nao_abre_nada(self):
        """Mantida a pasta, o clique diria "não é alcançada desta máquina" —
        recado que manda conferir a REDE, quando o que houve foi a limpeza
        fazendo o que devia."""
        with _Pasta():
            gr.anotar_saida(_plano("1.1", "P1"), "X:/tmp/AAA/C1/P1", {})
            gr.anotar_limpeza(7, ["X:/tmp/AAA/C1/P1"], "parada sem liberação")
            estado = gr.estados_da_documentacao()[7]
        self.assertEqual(estado["estado"], gr.PRONTA)
        self.assertEqual(estado["pasta"], "")
        self.assertIn("apagada", estado["avisos"][0])

    def test_arquivo_de_antes_da_limpeza_existir_se_le(self):
        """Arquivo gravado antes de 14/09/2026 não tem a chave: nada limpo,
        que é a verdade — e não KeyError na varredura da concentradora."""
        with _Pasta() as p:
            p.arquivo.write_text('{"versao": 1, "janela": {}, "exportados": {}}',
                                 encoding="utf-8")
            self.assertEqual(gr.a_limpar(), [])
            gr.anotar_limpeza(7, ["X:/tmp/AAA/C1/P1"], "parada sem liberação")
            self.assertIn("7", gr.ler()["limpos"])


class ArquivoRuim(unittest.TestCase):

    def test_json_truncado_nao_vira_memoria_vazia(self):
        """Vazio significa "nunca vi nada" — e sob esse significado a automação
        reexportaria tudo o que já saiu. Tem de gritar."""
        with _Pasta() as pasta:
            gr.anotar([_ativ(1, "AAA")])
            pasta.arquivo.write_text('{"janela": {"1": ', encoding="utf-8")
            # ``ValueError`` cobre os dois: o ``JSONDecodeError`` do arquivo
            # truncado herda dele, e é o que o ``ler`` levanta quando o JSON
            # está íntegro mas não é um objeto.
            with self.assertRaises(ValueError):
                gr.ler()

    def test_arquivo_que_nao_existe_e_memoria_vazia(self):
        """Diferente de ilegível: nunca ter rodado é um começo legítimo."""
        with _Pasta():
            self.assertEqual(gr.abertas(), {})
            self.assertEqual(gr.resumo()["planos_exportados"], 0)


class Pendentes(unittest.TestCase):
    """A junção: janela anotada × planos aprovados, menos o que já saiu."""

    def _rodar(self, atividades, prontos):
        antes_todas = atividades_db.todas
        antes_prontos = gatilho_db.prontos_de
        atividades_db.todas = lambda desde=None: list(atividades)
        gatilho_db.prontos_de = lambda por_registro: list(prontos)
        try:
            return gr.pendentes()
        finally:
            atividades_db.todas = antes_todas
            gatilho_db.prontos_de = antes_prontos

    def test_o_plano_sai_mesmo_com_a_atividade_ja_em_andamento(self):
        """O caso completo, ponta a ponta: a atividade some da consulta e o
        plano, aprovado depois, ainda assim é exportado."""
        with _Pasta():
            gr.anotar([_ativ(1149015, "9000019ANA")])
            saida = self._rodar([], [_pronto("1.2.3", registro="9000019ANA")])
        self.assertEqual([p.plan_uid for p in saida], ["1.2.3"])

    def test_o_que_ja_saiu_nao_volta(self):
        with _Pasta():
            gr.anotar([_ativ(1149015, "9000019ANA")])
            p = _pronto("1.2.3", registro="9000019ANA")
            gr.anotar_saida(p)
            self.assertEqual(self._rodar([], [p]), [])

    def test_anota_antes_de_perguntar_os_planos(self):
        """A ordem é o que garante que uma Documentação que abriu e mudou de
        estado na MESMA sondagem ainda entre na janela desta vez."""
        with _Pasta():
            saida = self._rodar([_ativ(7, "BBB")],
                                [_pronto("9.9.9", registro="BBB")])
            self.assertIn("BBB", gr.abertas())
        self.assertEqual([p.plan_uid for p in saida], ["9.9.9"])

    def test_sem_janela_nao_pergunta(self):
        with _Pasta():
            self.assertEqual(self._rodar([], [_pronto("1.2.3")]), [])


if __name__ == "__main__":
    unittest.main()
