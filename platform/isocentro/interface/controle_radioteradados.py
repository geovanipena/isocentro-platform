"""A aba Radioteradados do lado da janela: o que ela pede ao banco — PROTÓTIPO.

Mesma divisão do :mod:`controle_agenda`: a tela desenha, este objeto decide o
mês em cena e pergunta. No protótipo só o bloco de Operação tem fonte, e a
fonte é a MESMA da Agenda (``agenda_db.pacientes_do_mes_por_maquina`` e
``tratamento_db.resumo_mensal_por_maquina``) — nenhuma consulta nova, que é o
que o AD-11 da arquitetura pediria testar no servidor local antes de existir.

**A conta da ocupação é a do** ``controle_agenda._consultar_resumo_mensal``,
repetida aqui de propósito e só aqui, no protótipo: a arquitetura manda a conta
para um dono só no ``dominio/`` (AD-2/AD-3), e é na frente do núcleo que ela se
muda — mudar agora seria mexer na Agenda para servir a uma tela de ver.

Síncrono, como a Agenda. A arquitetura pede ``QThread`` (AD-6) para o cálculo
dos indicadores de verdade; estas duas consultas já são as que a Agenda faz na
thread da tela.
"""
from __future__ import annotations

import logging
from datetime import date, datetime

from isocentro.banco import agenda_db
from isocentro.banco import banco_local
from isocentro.banco import tratamento_db
from isocentro.interface import ui

_LOG = logging.getLogger(__name__)


def mes_anterior(hoje: date) -> date:
    """O dia 1 do mês anterior — o mês que se fecha (PRD, FR-1)."""
    if hoje.month == 1:
        return date(hoje.year - 1, 12, 1)
    return date(hoje.year, hoje.month - 1, 1)


def andar_mes(mes: date, delta: int) -> date:
    """O dia 1 do mês ``delta`` meses depois de ``mes``."""
    total = mes.year * 12 + (mes.month - 1) + delta
    return date(total // 12, total % 12 + 1, 1)


class ControleRadioteradados:
    """Responde aos sinais do ``PainelRadioteradados``. A janela só o constrói e liga."""

    def __init__(self, painel, usuario: dict | None = None):
        self.painel = painel
        self._usuario = usuario or {}
        self._mes = mes_anterior(date.today())
        self._maquinas: list = []   # agenda_db.Maquina, lidas uma vez por sessão
        painel.mes_pedido.connect(self._andar)

    def ao_abrir(self) -> None:
        self._atualizar()

    def _andar(self, delta: int) -> None:
        novo = andar_mes(self._mes, delta)
        # Mês futuro não tem o que mostrar; o atual pode, como "em andamento".
        if novo > date.today().replace(day=1):
            return
        self._mes = novo
        self._atualizar()

    def _estado(self) -> str:
        """Provisório sempre, no protótipo: nenhum mês é congelado ainda (AD-6)."""
        atual = self._mes == date.today().replace(day=1)
        fonte = "banco local (demonstração)" if banco_local.ligado() else "banco"
        partes = ["EM ANDAMENTO" if atual else "PROVISÓRIO",
                  "carga do data warehouse: desconhecida",
                  f"calculado {datetime.now():%d/%m %H:%M}",
                  fonte]
        return " · ".join(partes)

    def _atualizar(self) -> None:
        hoje = date.today()
        self.painel.definir_mes(self._mes, self._estado(),
                                pode_avancar=self._mes < hoje.replace(day=1))
        if not agenda_db.disponivel():
            self.painel.definir_operacao(None, agenda_db.motivo_indisponivel())
            return
        if not self._maquinas:
            self._maquinas = agenda_db.maquinas()
        if not self._maquinas:
            self.painel.definir_operacao(
                None, "Nenhuma máquina de tratamento ativa encontrada no banco.")
            return
        with ui.trabalhando(self.painel, "Calculando o mês…"):
            linhas, motivo = self._operacao(self._maquinas, self._mes)
        self.painel.definir_operacao(linhas, motivo)

    def _operacao(self, maquinas: list, mes: date) -> tuple:
        """``([(nome, sessoes, pacientes, inicios, ocupacao)], motivo)``.

        Uma máquina sem dado numa das duas fontes aparece com travessão nessa
        coluna, e não some nem vira zero: no protótipo o que se quer ver é a
        estrutura inteira, e a falta tem de estar visível.
        """
        try:
            pacientes_inicios = agenda_db.pacientes_do_mes_por_maquina(
                maquinas, mes)
        except Exception:  # noqa: BLE001 — a aba não cai por uma consulta
            _LOG.exception("Radioteradados: falha ao ler pacientes do mês")
            pacientes_inicios = {}
        ids = [m.machine_id for m in maquinas if m.machine_id]
        try:
            sessoes_mes = tratamento_db.resumo_mensal_por_maquina(ids, mes) if ids else {}
        except Exception:  # noqa: BLE001
            _LOG.exception("Radioteradados: falha ao ler o resumo mensal")
            sessoes_mes = {}
        motivos = []
        if not pacientes_inicios:
            motivos.append("pacientes e inícios: a agenda não respondeu")
        if not sessoes_mes:
            motivos.append("sessões: sem resposta do resumo do mês (portão da "
                           "lista de tratamento ainda fechado ou banco fora)")
        linhas = []
        for m in maquinas:
            pac, ini = pacientes_inicios.get(m.ctr_resource_ser, (None, None))
            dado = sessoes_mes.get(m.machine_id)
            sessoes = dado[0] if dado else None
            ocupacao = None
            if sessoes is not None:
                minutos = agenda_db.minutos_uteis_do_mes(m.nome, mes,
                                                         ate=date.today())
                if minutos:
                    ocupacao = sessoes * agenda_db.MINUTOS_POR_SESSAO / minutos
            if pac is None and sessoes is None:
                continue
            linhas.append((m.nome, sessoes, pac, ini, ocupacao))
        if not linhas:
            return None, "Sem dado de operação para este mês. " + "; ".join(motivos)
        return linhas, ("Faltou: " + "; ".join(motivos)) if motivos else ""
