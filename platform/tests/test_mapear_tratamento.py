"""O relatório da LISTA: o que faria a conferência contra o ARIA mentir.

O ``tools/mapear_tratamento.py --consulta`` roda na estação da clínica, com a
identidade de rede que esta máquina não tem — quem o executa vai lá, roda e
volta. Mesma aposta do ``test_mapear_gatilho``: o fluxo inteiro é exercido aqui
contra um ``tratamento_db`` falso, porque um erro no passo da lista não custa um
teste vermelho, custa a viagem — e esta rodada existe justamente para preencher
o ``LISTA_VERIFICADA_EM``, que está vazio desde 19/08/2026.

O que estes testes fixam é o que faria o relatório MENTIR:

* **o portão fecha a lista na origem.** ``em_tratamento`` devolve ``None`` sem
  perguntar nada ao banco enquanto ``lista_disponivel()`` for falso — e ele é
  falso, é essa a razão da viagem. Sem ligar o experimental durante a rodada, o
  relatório sairia vazio por decisão nossa, que é a pior forma de "não deu";
* **"não deu para perguntar" não é "ninguém em tratamento".** São respostas
  opostas, e a lista vazia já fez a aba afirmar que um médico com agenda cheia
  não tinha paciente nenhum;
* **coluna vazia em TODAS as linhas** tem de sair denunciada. As três
  auxiliares (recontagem, frequência, cursos) falham em silêncio de propósito —
  certo na tela, veneno numa conferência: o número do DW sairia no papel
  parecendo o recontado;
* **acima de ``_MAX_NA_CONTAGEM`` elas nem rodam**, sem erro nenhum. A lista
  larga da estação tinha 406 linhas contra um teto de 400;
* **ausência não aparece numa lista.** Quem o ARIA mostra e a janela não tem de
  estar no papel com o motivo — senão "faltou o fulano" e "o fulano concluiu na
  semana passada" são a mesma tela.

Rodar:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import contextlib
import io
import logging
import os
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "tools"))

import mapear_tratamento  # noqa: E402

from isocentro.banco import tratamento_db as td  # noqa: E402

HOJE = date.today()


@contextlib.contextmanager
def _banco(apontado: bool):
    """Liga e desliga o banco pelo ``capa_db.configurado``, não pela variável.

    Zerar ``ISOCENTRO_DB_SERVIDOR`` NÃO desliga o banco: o ``capa_db`` cai no
    ``config_servico.json`` desta estação, e desde 09/09/2026 o nome novo
    (``ISOCENTRO_DB_SERVIDOR``) ainda tem precedência sobre o antigo. São
    duas armadilhas já pagas, e as duas fazem o teste passar por engano.

    Guarda e DEVOLVE a função — ``del capa_db.configurado`` apagaria a original
    para o resto do processo.
    """
    from isocentro.banco import capa_db

    original = capa_db.configurado
    capa_db.configurado = lambda: apontado
    try:
        yield
    finally:
        capa_db.configurado = original


def _linha(registro="9000001CEL", nome="Amostro, Tadeu", curso=1,
           entregues=5, previstas=25, dias=1, **extra):
    """Uma linha da lista, com o que o painel mostra e nada além."""
    return td.EmTratamento(
        registro=registro, nome=nome, curso_id=curso, entregues=entregues,
        previstas=previstas, ultima=HOJE - timedelta(days=dias),
        frequencia=extra.pop("frequencia", "Uma Vez por Dia"),
        cursos_total=extra.pop("cursos_total", 1), **extra)


class Conferencia(unittest.TestCase):
    """O ``--consulta``: roda o ``tratamento_db`` de verdade.

    É o passo que existe para ser comparado, nome por nome, com o quadro do
    ARIA — e é dessa comparação que sai a data do ``LISTA_VERIFICADA_EM``.
    """

    def _rodar(self, janela=(), todos=None, equipe=None, por_medico=None,
               avisos=(), medico="", verificada=None, recontagem=None,
               planos=None, prescricoes=None):
        """Guardar e DEVOLVER as funções do módulo, nunca ``del``.

        ``prescricoes`` segue a mesma regra de ``planos``: substituída sempre,
        ``{(registro, curso, plano): {...}}`` ou uma exceção.

        ``del modulo.funcao`` apaga a ORIGINAL para o resto do processo — a
        armadilha que o ``checar_py.py`` recusa na hora da edição.

        ``recontagem`` é ``{(registro, curso): entregues}``: o que a contagem
        por dia devolveria. A lista larga é recontada pelo próprio relatório,
        e a função real iria ao banco.

        ``planos`` é o que a consulta plano a plano devolveria — ou uma
        exceção, para o caso de ela falhar. Substituída SEMPRE: a real iria ao
        servidor clínico de dentro da suíte.
        """
        antes_em, antes_med = td.em_tratamento, td.medicos
        antes_recontar = td._corrigir_entregues
        antes_planos = mapear_tratamento._planos_dos_cursos

        def _planos(capa_db, td_, registros):
            if isinstance(planos, Exception):
                raise planos
            return dict(planos or {})

        mapear_tratamento._planos_dos_cursos = _planos
        antes_rx = mapear_tratamento._prescricoes_dos_planos

        def _prescricoes(capa_db, td_, registros):
            if isinstance(prescricoes, Exception):
                raise prescricoes
            return dict(prescricoes or {})

        mapear_tratamento._prescricoes_dos_planos = _prescricoes
        antes_lista = td.LISTA_VERIFICADA_EM
        if verificada is not None:
            td.LISTA_VERIFICADA_EM = verificada
        self.chamadas: list = []
        self.portao_durante: list = []

        def _em_tratamento(medicos_alvo=(), dias=td.DIAS_DA_JANELA, hoje=None,
                           incluir_concluidos=False):
            # O que o portão dizia NA HORA da chamada é o ponto de um dos
            # testes: com ele fechado a função real nem consulta o banco.
            self.portao_durante.append(td.lista_disponivel())
            for texto in avisos:
                logging.getLogger(td.__name__).warning(texto)
            if medicos_alvo:
                self.chamadas.append(("medico", medicos_alvo[0].nome))
                return list((por_medico or {}).get(medicos_alvo[0].nome, []))
            if incluir_concluidos:
                self.chamadas.append(("todos", None))
                return None if todos is None else list(todos)
            self.chamadas.append(("janela", None))
            return None if janela is None else list(janela)

        self.blocos: list = []

        def _recontar(linhas):
            self.blocos.append(len({e.registro for e in linhas}))
            for e in linhas:
                novo = (recontagem or {}).get((e.registro, e.curso_id))
                if novo is not None:
                    e.entregues = novo

        td.em_tratamento = _em_tratamento
        td.medicos = lambda: list(equipe or [])
        td._corrigir_entregues = _recontar
        saida = io.StringIO()
        try:
            with contextlib.redirect_stdout(saida):
                mapear_tratamento.passo_consulta(medico)
        finally:
            td.em_tratamento, td.medicos = antes_em, antes_med
            td._corrigir_entregues = antes_recontar
            td.LISTA_VERIFICADA_EM = antes_lista
            mapear_tratamento._planos_dos_cursos = antes_planos
            mapear_tratamento._prescricoes_dos_planos = antes_rx
        return saida.getvalue()

    # ------------------------------------------------------------------ #

    def test_as_constantes_valendo_saem_antes_do_resultado(self):
        """Sem elas a lista não é conferível: "faltou o fulano" tem resposta
        diferente conforme a janela e o corte de parada da rodada."""
        texto = self._rodar(janela=[_linha()])
        self.assertIn("DIAS_DA_JANELA", texto)
        self.assertIn(str(td.DIAS_DA_JANELA), texto)
        self.assertIn("_DIAS_PARADO", texto)
        self.assertIn("LISTA_VERIFICADA_EM", texto)

    def test_o_portao_e_ligado_durante_a_rodada(self):
        """Sem isto o relatório sai VAZIO, e vazio por decisão nossa.

        ``em_tratamento`` devolve ``None`` sem tocar no banco enquanto
        ``lista_disponivel()`` for falso — e ele é falso: é exatamente o que
        esta viagem existe para destravar.

        O banco apontado daqui não é cerimônia: ``lista_disponivel`` exige
        ANTES o ``disponivel()``, que pede banco. Sem isso, este teste passava
        sozinho e reprovava na suíte — o ambiente fica do jeito que o módulo
        anterior o deixou. E o banco se aponta trocando o ``configurado``, não
        mexendo em ``ISOCENTRO_DB_SERVIDOR``: o ``capa_db`` cai no
        ``config_servico.json`` desta estação, e o nome novo tem precedência.
        """
        antes = os.environ.pop(td.ENV_EXPERIMENTAL, None)
        with _banco(True):
            try:
                self._rodar(janela=[_linha()], verificada="")
                self.assertTrue(all(self.portao_durante),
                                "a consulta rodou com o portão fechado")
                # E a variável não fica ligada depois: quem roda a ferramenta
                # não está pedindo para ligar o painel da estação.
                self.assertIsNone(os.environ.get(td.ENV_EXPERIMENTAL))
            finally:
                if antes is not None:
                    os.environ[td.ENV_EXPERIMENTAL] = antes

    def test_portao_que_nao_abriu_sai_gritado(self):
        """A variável experimental é só METADE do portão.

        Sem banco apontado, ``lista_disponivel`` continua falso mesmo com ela
        ligada, e todo bloco sai vazio. Zero curso lê-se como "ninguém em
        tratamento", que é a resposta OPOSTA — foi o que fez a aba afirmar que
        um médico com agenda cheia não tinha paciente nenhum.
        """
        with _banco(False):
            texto = self._rodar(janela=[_linha()], verificada="")
        self.assertIn("continuou FECHADO", texto)
        self.assertIn("não quer dizer", texto)

    def test_o_portao_fechado_sai_escrito_no_relatorio(self):
        """Quem lê precisa saber que o app, HOJE, não mostraria nada disto."""
        texto = self._rodar(janela=[_linha()], verificada="")
        self.assertIn(td.ENV_EXPERIMENTAL, texto)
        self.assertIn("fechado", texto)

    def test_nao_deu_para_perguntar_nao_vira_ninguem_em_tratamento(self):
        """As duas respostas são OPOSTAS, e confundi-las foi o que fez a aba
        afirmar que um médico com agenda cheia não tinha paciente nenhum."""
        texto = self._rodar(janela=None)
        self.assertIn("NÃO DEU", texto)
        self.assertNotIn("0 curso(s) em", texto)

    def test_a_linha_traz_registro_e_nome(self):
        """A conferência contra o ARIA é nome por nome, com o dedo na tela."""
        texto = self._rodar(janela=[_linha(registro="9000042CEL",
                                           nome="Beltrano, Lauro")])
        self.assertIn("9000042CEL", texto)
        self.assertIn("Beltrano", texto)

    def test_as_marcas_saem_na_linha(self):
        """São o que o painel ACRESCENTA ao quadro do ARIA — e é sobre elas que
        o médico decide. Uma parada de 8 dias úteis conferida no papel é o que
        separa "a marca funciona" de "a marca aparece"."""
        texto = self._rodar(janela=[_linha(dias=12, entregues=3)])
        self.assertIn("parado há", texto)

    def test_coluna_vazia_em_todas_as_linhas_e_denunciada(self):
        """A auxiliar falhou calada, e sem isto o papel mente.

        Frequência vazia em toda a lista não se distingue de "este banco não
        tem esse dado" olhando uma linha — e ela decide se a marca de
        interrupção aparece.
        """
        texto = self._rodar(janela=[_linha(frequencia=""), _linha(
            registro="9000002CEL", curso=2, frequencia="")])
        self.assertIn("COLUNA VAZIA", texto)
        self.assertIn("frequencia", texto)

    def test_uma_linha_preenchida_ja_tira_a_coluna_da_denuncia(self):
        """O que se procura é a coluna INTEIRA vazia. Curso sem frequência
        prescrita existe, e acusar cada um deles encheria o relatório de
        alarme falso — que é o que faz parar de ler os avisos."""
        texto = self._rodar(janela=[_linha(frequencia=""),
                                    _linha(registro="9000002CEL", curso=2)])
        self.assertNotIn("COLUNA VAZIA", texto)

    def test_acima_do_max_na_contagem_o_relatorio_avisa(self):
        """As três auxiliares voltam sem consultar, sem erro nenhum.

        Na estação a lista larga deu 406 linhas contra um teto de 400: as
        frações sairiam as do DW, sem a recontagem por dia, e a divergência
        contra o ARIA seria atribuída ao SQL.
        """
        muitos = [_linha(registro=f"90{i:05d}CEL", curso=i)
                  for i in range(td._MAX_NA_CONTAGEM + 1)]
        texto = self._rodar(janela=muitos)
        self.assertIn("_MAX_NA_CONTAGEM", texto)
        self.assertIn("NEM RODARAM", texto)

    def test_o_aviso_calado_sai_no_relatorio(self):
        """As auxiliares avisam pelo ``logging`` e desistem. Sem alguém
        escutando, o aviso morre no ar e o número do DW sai no papel
        parecendo o recontado."""
        texto = self._rodar(janela=[_linha()],
                            avisos=["Não consegui recontar as frações"])
        self.assertIn("falhou calado", texto)
        self.assertIn("recontar as frações", texto)

    def test_sem_aviso_nenhum_o_relatorio_diz_isso(self):
        """Bloco vazio se lê como "não perguntei", e a diferença importa."""
        texto = self._rodar(janela=[_linha()])
        self.assertIn("nada. As três auxiliares responderam", texto)

    def test_quem_ficou_de_fora_da_janela_aparece_com_o_motivo(self):
        """Ausência não aparece numa lista, e é ela que decide o portão.

        "Faltou o fulano" e "o fulano concluiu na semana passada" são a mesma
        tela em branco sem este bloco.
        """
        dentro = _linha()
        fora = _linha(registro="9000009CEL", nome="Sicrano, Tadeu",
                      curso=9, entregues=25, previstas=25)
        texto = self._rodar(janela=[dentro], todos=[dentro, fora])
        self.assertIn("DEIXOU DE FORA", texto)
        self.assertIn("9000009CEL", texto)
        self.assertIn("concluído", texto)

    def test_fracao_na_maquina_reserva_sai_concluido(self):
        """Sete pacientes na rodada de 10/09/2026 saíram "19/20 — última
        sessão 11/08" no bloco que decide o portão, e tinham terminado: a
        fração da máquina reserva vai para um plano próprio, o DW conta por
        plano, e o MAX pega o do original. O usuário reconheceu cinco pelo
        nome. A recontagem por dia os fecha — mas o app não reconta acima do
        teto, e a lista larga passa dele."""
        dentro = _linha()
        reserva = _linha(registro="9000009CEL", curso=9,
                         entregues=19, previstas=20, dias=30)
        texto = self._rodar(janela=[dentro], todos=[dentro, reserva],
                            recontagem={("9000009CEL", 9): 20})
        linha = next(l for l in texto.splitlines()
                     if "9000009CEL" in l and "curso 9" in l)
        self.assertIn("20/20 — concluído", linha)
        self.assertNotIn("última sessão", linha)

    def test_a_lista_larga_acima_do_teto_e_recontada_em_blocos(self):
        """165 cursos na janela e 414 na larga, contra um teto de 400: sem os
        blocos, a recontagem ou não roda, ou roda estourando o ``IN (...)``.
        Cada bloco tem de caber no teto, e ninguém pode ficar de fora."""
        dentro = _linha()
        # Prefixo 91, e não 90: o gerador com 90 dá 9000001CEL no i=1, o
        # registro da ``dentro`` — e a conta de registros distintos erra por um.
        muitos = [dentro] + [_linha(registro=f"91{i:05d}CEL", curso=i,
                                    entregues=25, previstas=25)
                             for i in range(td._MAX_NA_CONTAGEM + 1)]
        texto = self._rodar(janela=[dentro], todos=muitos)
        self.assertEqual(len(self.blocos), 2)
        self.assertTrue(all(n <= td._MAX_NA_CONTAGEM for n in self.blocos))
        self.assertEqual(sum(self.blocos), td._MAX_NA_CONTAGEM + 2)
        depois = texto.split("DEIXOU DE FORA", 1)[1]
        self.assertIn("recontada por dia em 2 blocos", depois)

    def test_o_retratamento_nao_se_parte_entre_dois_blocos(self):
        """Dois cursos, um registro: é o registro que vai no ``IN (...)`` e é
        ele que o teto conta. Partido entre blocos, o mesmo paciente iria ao
        servidor clínico duas vezes."""
        linhas = ([_linha(registro="9000001CEL", curso=1),
                   _linha(registro="9000002CEL", curso=2),
                   _linha(registro="9000001CEL", curso=3)])
        blocos = mapear_tratamento._em_blocos_de_registro(linhas, 1)
        self.assertEqual([[e.curso_id for e in b] for b in blocos],
                         [[1, 3], [2]])

    def test_a_lista_larga_dentro_do_teto_nao_avisa(self):
        """Aviso que sai sempre é aviso que ninguém lê — e este bloco já é
        longo o bastante para o de verdade se perder no meio. Dentro do teto
        é um bloco só, e ele ainda assim é recontado."""
        dentro = _linha()
        fora = _linha(registro="9000009CEL", curso=9,
                      entregues=25, previstas=25)
        texto = self._rodar(janela=[dentro], todos=[dentro, fora])
        self.assertEqual(len(self.blocos), 1)
        depois = texto.split("DEIXOU DE FORA", 1)[1]
        self.assertNotIn("blocos de até", depois)

    def test_a_lista_larga_que_falha_nao_derruba_o_resto(self):
        """O bloco é diagnóstico; a lista da janela é o que se leva ao ARIA.
        Perder as duas por causa de uma seria trocar meia resposta por
        nenhuma."""
        texto = self._rodar(janela=[_linha()], todos=None)
        self.assertIn("9000001CEL", texto)
        self.assertIn("NÃO DEU para perguntar", texto)

    def test_o_concluido_sai_com_a_data_da_ultima_sessao(self):
        """A fase 2 de um tratamento sequencial sai como "concluído": o total
        da fase 1 já foi alcançado. Até 11/09/2026 o concluído saía sem data,
        e só uma última sessão de ONTEM distingue quem terminou de quem está
        no meio do reforço."""
        dentro = _linha()
        fase2 = _linha(registro="9000009CEL", curso=9,
                       entregues=28, previstas=25, dias=1)
        texto = self._rodar(janela=[dentro], todos=[dentro, fase2])
        linha = next(l for l in texto.splitlines()
                     if "9000009CEL" in l and "— concluído" in l)
        ontem = (HOJE - timedelta(days=1)).strftime("%d/%m")
        self.assertIn(f"concluído · última {ontem}", linha)

    def test_plano_a_plano_mostra_o_total_de_cada_plano(self):
        """Na rodada de 11/09/2026, 48 cursos saíram com "N/M" acima do total
        ("36/10"): a recontagem soma o curso inteiro e o total é o de um plano
        só. A regra por plano depende do total que o plano AVULSO declara (1 ou
        20?), e nenhum relatório imprimia isso. Quem não cobre vem primeiro —
        é quem a regra muda."""
        dentro = _linha(registro="9000001CEL", curso=1,
                        entregues=5, previstas=25)
        mama = _linha(registro="9000002CEL", curso=2,
                      entregues=7, previstas=15)
        boost = _linha(registro="9000003CEL", curso=3,
                       entregues=36, previstas=10)
        planos = {
            ("9000002CEL", 2): [
                {"plano": 21, "nome": "cMAMA_D", "de": "20260901",
                 "ate": "20260910", "fracoes": 7, "previstas": 15, "dw": 7,
                 "primario": 1, "maquina": "TrueBeam"},
                {"plano": 22, "nome": "cFSC_D", "de": "20260901",
                 "ate": "20260910", "fracoes": 7, "previstas": 15, "dw": 7,
                 "primario": 1, "maquina": "TrueBeam"}],
            ("9000003CEL", 3): [
                {"plano": 31, "nome": "cPROSTATA", "de": "20260701",
                 "ate": "20260805", "fracoes": 26, "previstas": 26, "dw": 26,
                 "primario": 1, "maquina": "TrueBeam"},
                {"plano": 32, "nome": "cBOOST", "de": "20260806",
                 "ate": "20260819", "fracoes": 10, "previstas": 10, "dw": 10,
                 "primario": 1, "maquina": "TrueBeam"}],
        }
        texto = self._rodar(janela=[dentro, mama],
                            todos=[dentro, mama, boost], planos=planos)
        bloco = texto.split("plano a plano", 1)[1].split(
            "o filtro por médico", 1)[0]
        self.assertIn("2 curso(s); em 1 o total não cobre", bloco)
        # O de um plano só e que cobre não entra: seria ruído.
        self.assertNotIn("9000001CEL", bloco)
        self.assertLess(bloco.index("9000003CEL"), bloco.index("9000002CEL"))
        self.assertIn("⚠ o total não cobre", bloco)
        self.assertIn("cBOOST", bloco)
        self.assertIn("06/08–19/08", bloco)
        self.assertIn("total do plano 10", bloco)

    def test_plano_a_plano_que_falha_nao_derruba_o_fecho(self):
        """O bloco é para decidir a regra; a conferência (a)–(d) continua
        valendo sem ele. Perder o fecho por causa dele seria voltar da
        estação sem saber o que conferir."""
        dentro = _linha()
        texto = self._rodar(janela=[dentro], todos=[dentro],
                            planos=RuntimeError("DimPlan recusada"))
        self.assertIn("NÃO deu: DimPlan recusada", texto)
        self.assertIn("o que fecha a conferência", texto)
        self.assertIn("(e) plano a plano", texto)

    # O caso que terminou com 20 de 20 no ARIA e que a regra por plano dava
    # 10/11, em curso: o replanejamento não descontou a fração da reserva.
    _PLANOS_DA_RESERVA = {("9000004CEL", 4): [
        {"plano": 41, "nome": "gLEITO", "de": "20260714", "ate": "20260724",
         "fracoes": 9, "previstas": 20, "dw": 9, "primario": 1,
         "maquina": "TrueBeam"},
        {"plano": 42, "nome": "iLEITO_6EX", "de": "20260731",
         "ate": "20260731", "fracoes": 1, "previstas": 1, "dw": 1,
         "primario": 1, "maquina": "6EX"},
        {"plano": 43, "nome": "gLEITO_replan", "de": "20260803",
         "ate": "20260814", "fracoes": 10, "previstas": 11, "dw": 10,
         "primario": 1, "maquina": "TrueBeam"}]}

    def _bloco_da_reserva(self, prescricoes):
        curso = _linha(registro="9000004CEL", curso=4,
                       entregues=20, previstas=11)
        texto = self._rodar(janela=[curso], todos=[curso],
                            planos=self._PLANOS_DA_RESERVA,
                            prescricoes=prescricoes)
        return texto.split("plano a plano", 1)[1].split(
            "o filtro por médico", 1)[0]

    def test_plano_a_plano_mostra_a_prescricao_de_cada_plano(self):
        """O ARIA diz "terminou" pelo total da PRESCRIÇÃO (usuário, 11/09/2026),
        e o total do plano não basta: o serviço desconta a fração da máquina
        reserva do plano seguinte num caso e não no outro. Sem a prescrição ao
        lado de cada plano, a regra seria escrita outra vez por palpite."""
        rx = {"n": 1, "rx": 501, "nome": "Leito prostático", "total": 20,
              "versoes": 1, "sessoes": 20, "sessoes_previstas": 20,
              "concluido": 20260814}
        bloco = self._bloco_da_reserva(
            {("9000004CEL", 4, p): dict(rx) for p in (41, 42, 43)})
        self.assertIn('prescrição 501 "Leito prostático" 20 fr', bloco)
        self.assertIn("sessões do DW 20/20", bloco)
        self.assertIn("curso concluído 14/08/2026", bloco)
        # A soma é a candidata a regra: 9 + 1 + 10, a reserva dentro dos 20.
        self.assertIn("⇒ prescrição 501: 20 fração(ões) nos planos, de 20",
                      bloco)

    def test_prescricao_que_falha_nao_apaga_os_planos(self):
        """A consulta da prescrição é nova e chega à DimPrescription por uma
        chave que só a capa tinha usado. Se ela falhar na estação, o bloco
        plano a plano — já medido e lido — tem de sair inteiro mesmo assim."""
        bloco = self._bloco_da_reserva(RuntimeError("DimPrescription recusada"))
        self.assertIn("prescrição: NÃO deu: DimPrescription recusada", bloco)
        self.assertIn("total do plano 20", bloco)
        self.assertIn("gLEITO_replan", bloco)

    def test_plano_sem_prescricao_ou_com_duas_e_dito(self):
        """Plano da reserva criado sem vínculo, ou um plano que toca duas
        prescrições: nos dois a soma por prescrição mentiria, então a linha
        diz o que houve e a soma não conta aquele plano. E o 18000101 que o
        DW grava no lugar de nulo não pode sair como data de conclusão."""
        base = {"rx": 501, "nome": "Leito", "total": 20, "versoes": 1,
                "sessoes": 20, "sessoes_previstas": 20, "concluido": 18000101}
        bloco = self._bloco_da_reserva({
            ("9000004CEL", 4, 41): dict(base, n=1),
            ("9000004CEL", 4, 42): dict(base, n=0),
            ("9000004CEL", 4, 43): dict(base, n=2)})
        self.assertIn("sem prescrição no DW", bloco)
        self.assertIn("⚠ 2 prescrições no mesmo plano", bloco)
        self.assertIn("curso não concluído", bloco)
        self.assertNotIn("1800", bloco)
        self.assertIn("⇒ prescrição 501: 9 fração(ões) nos planos, de 20",
                      bloco)

    def test_o_filtro_do_medico_que_sai_da_janela_e_marcado(self):
        """A quarta chance de a granularidade campo × fração morder o módulo.

        O ``EXISTS`` do médico não multiplica linhas e a lista dele é
        subconjunto da janela (32 ⊂ 131, medido em 10/09/2026). Se ele virasse
        ``JOIN``, a lista traria curso que a janela não tem — ou o mesmo duas
        vezes.
        """
        m = td.Medico(nome="Monteiro, Paula", bruto="Monteiro, Paula M")
        intrusa = _linha(registro="9000077CEL", curso=77)
        texto = self._rodar(janela=[_linha()], equipe=[m],
                            por_medico={"Monteiro, Paula": [intrusa]})
        self.assertIn("FORA da janela", texto)

    def test_linha_repetida_do_medico_e_marcada(self):
        """Mesma família: o dobro do mesmo curso é como a granularidade
        aparece quando ela aparece."""
        m = td.Medico(nome="Monteiro, Paula", bruto="Monteiro, Paula M")
        dentro = _linha()
        texto = self._rodar(janela=[dentro], equipe=[m],
                            por_medico={"Monteiro, Paula": [dentro, dentro]})
        self.assertIn("REPETIDA", texto)

    def test_curso_sem_medico_nenhum_aparece(self):
        """É o modo silencioso de um paciente sumir do painel sem sumir do
        ARIA: quem não é de médico nenhum é invisível para quem usa o
        seletor."""
        m = td.Medico(nome="Monteiro, Paula", bruto="Monteiro, Paula M")
        dele = _linha()
        orfao = _linha(registro="9000055CEL", nome="Órfão, Caso", curso=55)
        texto = self._rodar(janela=[dele, orfao], equipe=[m],
                            por_medico={"Monteiro, Paula": [dele]})
        self.assertIn("não aparecem em médico nenhum", texto)
        self.assertIn("9000055CEL", texto)

    def test_as_tres_consultas_da_lista_sao_exercidas(self):
        """O tempo medido em 10/09/2026 foi o do SQL colado no prompt, uma
        consulta por vez. O que cabe (ou não) na thread da tela é o da FUNÇÃO,
        e são três chamadas diferentes."""
        m = td.Medico(nome="Monteiro, Paula", bruto="Monteiro, Paula M")
        self._rodar(janela=[_linha()], todos=[_linha()], equipe=[m],
                    por_medico={"Monteiro, Paula": []})
        tipos = [t for t, _ in self.chamadas]
        self.assertEqual(tipos, ["janela", "todos", "medico"])

    def test_o_tempo_sai_com_o_limite_do_capa_db_ao_lado(self):
        """Número solto não se confere. 0,19 s só quer dizer alguma coisa ao
        lado dos 6 s que a tela tolera."""
        texto = self._rodar(janela=[_linha()])
        self.assertIn("limite", texto)
        self.assertIn("6 s", texto)

    def test_medico_pedido_que_nao_existe_diz_isso(self):
        """Silêncio aqui se lê como "este médico não tem paciente", que é
        outra resposta."""
        m = td.Medico(nome="Monteiro, Paula", bruto="Monteiro, Paula M")
        texto = self._rodar(janela=[_linha()], equipe=[m], medico="Zzz")
        self.assertIn("nenhum médico casa", texto)

    def test_com_medico_pedido_o_bloco_de_orfaos_nao_sai(self):
        """Com um médico só, "não aparece em médico nenhum" seria falso: os
        órfãos apurados seriam apenas os pacientes dos OUTROS médicos."""
        m = td.Medico(nome="Monteiro, Paula", bruto="Monteiro, Paula M")
        texto = self._rodar(janela=[_linha()], equipe=[m], medico="Paula",
                            por_medico={"Monteiro, Paula": []})
        self.assertNotIn("não aparecem em médico nenhum", texto)


class Escuta(unittest.TestCase):
    """O ouvinte não pode ficar pendurado no logger depois da rodada."""

    def test_o_ouvinte_sai_do_logger_no_fim(self):
        """Ouvinte que fica é o ``estilo.pintar`` de novo: em teste o efeito é
        cumulativo, e cada rodada repetiria os avisos das anteriores."""
        raiz = logging.getLogger("isocentro")
        antes = list(raiz.handlers)
        antes_em = td.em_tratamento
        td.em_tratamento = lambda *a, **k: []
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                mapear_tratamento.passo_consulta()
        finally:
            td.em_tratamento = antes_em
        self.assertEqual(list(raiz.handlers), antes)


if __name__ == "__main__":
    unittest.main()
