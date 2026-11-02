"""A aba **Radioteradados**: os indicadores do serviço — PROTÓTIPO.

O planejamento inteiro (PRD, arquitetura, riscos) mora em
``docs/planejamento/sistema-global/radioteradados/``. Esta tela é o layout que
o usuário aceitou em 13/10/2026, montado para ser VISTO no app antes das
frentes de cálculo: a estrutura está toda aqui, mas só o bloco de Operação tem
número, porque é o único que já existe pronto no código (o mesmo resumo do mês
que a Agenda mostra).

Os cartões do núcleo RDC ficam no lugar, escritos "em construção". Não é
enfeite: a regra do domínio é nunca inventar dado, e um cartão com número de
exemplo numa tela de indicadores é exatamente o número que alguém copia para a
chefia. O que o cartão diz é a verdade — a fórmula ainda não foi escrita nem
aprovada.

A tela só desenha; quem pergunta ao banco é o :mod:`controle_radioteradados`
(mesma divisão da Agenda).
"""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from isocentro.interface import estilo as st
from isocentro.interface import ui

_MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
          "agosto", "setembro", "outubro", "novembro", "dezembro")

# Os seis indicadores do item 6.11 da RDC 20/2006, na ordem da norma, e o que
# cada cartão diz enquanto a fórmula não existe. Os dois últimos não estão no
# banco do ARIA (PRD, FR-8): aparecem marcados, e não somem — sumir faria a
# tela parecer completa para quem prepara a avaliação externa.
NUCLEO_RDC: tuple[tuple[str, str], ...] = (
    ("Tempo médio do tratamento", "Em construção"),
    ("Taxa de abandono", "Em construção"),
    ("Taxa de interrupção", "Em construção"),
    ("Taxa de simulação", "Em construção"),
    ("Adesão a protocolos", "Fora do banco — v2"),
    ("Desvio da dose absoluta", "Fora do banco — v2"),
)

_CABECALHO_OPERACAO = ("Máquina", "Sessões", "Pacientes", "Inícios", "Ocupação")


def nome_do_mes(dia: date) -> str:
    """``Setembro/2026`` — o mês por extenso, como o usuário fala dele."""
    return f"{_MESES[dia.month - 1].capitalize()}/{dia.year}"


def _numero(valor) -> str:
    """``None`` vira travessão, nunca ``0``: zero é afirmação, falta é falta."""
    return "—" if valor is None else str(valor)


def _porcento(fracao) -> str:
    return "—" if fracao is None else f"{fracao * 100:.0f} %"


class PainelRadioteradados(QWidget):
    """A tela. ``mes_pedido(delta)`` pede o mês anterior (-1) ou o seguinte (+1)."""

    mes_pedido = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(12)
        lay.addWidget(self._faixa_experimental())
        lay.addLayout(self._cabecalho())
        lay.addWidget(self._cartao_nucleo())
        lay.addWidget(self._cartao_operacao())
        self.status = QLabel("")
        self.status.setWordWrap(True)
        st.pintar(self.status, lambda: f"color:{st.TEXTO_FRACO}; font-size:12px;")
        lay.addWidget(self.status)
        lay.addStretch(1)
        lay.addLayout(self._rodape())

    # ── Peças ────────────────────────────────────────────────────────────

    def _faixa_experimental(self) -> QLabel:
        """Em primeiro lugar, antes de qualquer número (PRD, FR-20).

        Mesma faixa âmbar da lista da Ficha Virtual: é o mesmo aviso — número
        ainda não conferido contra o ARIA —, e duas caras para o mesmo aviso
        ensinam a ignorar uma delas.
        """
        aviso = QLabel(
            "⚠  PROTÓTIPO · EXPERIMENTAL — números ainda não conferidos contra o "
            "ARIA (faltam o portão R-07 e a conferência do físico responsável). "
            "Não use para decidir nem para a avaliação externa.")
        aviso.setWordWrap(True)
        st.pintar(aviso, lambda: (
            f"background:{st.AMBAR_FUNDO}; color:{st.AMBAR};"
            " border-radius:7px; padding:7px 10px;"
            " font-size:12px; font-weight:600;"))
        return aviso

    def _cabecalho(self) -> QHBoxLayout:
        linha = QHBoxLayout()
        linha.setSpacing(8)
        self.btn_anterior = ui.botao("◀", altura=30)
        self.btn_anterior.setToolTip("Mês anterior")
        self.btn_anterior.clicked.connect(lambda: self.mes_pedido.emit(-1))
        self.lbl_mes = QLabel("")
        st.pintar(self.lbl_mes, lambda: (
            f"color:{st.TEXTO}; font-size:17px; font-weight:bold;"))
        self.btn_seguinte = ui.botao("▶", altura=30)
        self.btn_seguinte.setToolTip("Mês seguinte")
        self.btn_seguinte.clicked.connect(lambda: self.mes_pedido.emit(1))
        self.lbl_estado = QLabel("")
        st.pintar(self.lbl_estado, lambda: (
            f"color:{st.TEXTO_FRACO}; font-size:12px;"))
        linha.addWidget(self.btn_anterior)
        linha.addWidget(self.lbl_mes)
        linha.addWidget(self.btn_seguinte)
        linha.addSpacing(14)
        linha.addWidget(self.lbl_estado, 1)
        return linha

    def _cartao_nucleo(self) -> ui.Cartao:
        cartao = ui.Cartao("Núcleo RDC 20/2006 — avaliação externa (item 6.11)")
        grade = QGridLayout()
        grade.setSpacing(10)
        self.cartoes_rdc: dict[str, ui.Valor] = {}
        for i, (titulo, texto) in enumerate(NUCLEO_RDC):
            valor = ui.Valor(titulo, texto, tom="neutro")
            self.cartoes_rdc[titulo] = valor
            grade.addWidget(valor, i // 4, i % 4)
        cartao.corpo.addLayout(grade)
        nota = QLabel(
            "As fórmulas entram nas próximas frentes, cada uma com ficha técnica "
            "aprovada pelo físico responsável antes de virar número oficial.")
        nota.setWordWrap(True)
        st.pintar(nota, lambda: f"color:{st.TEXTO_APAGADO}; font-size:11.5px;")
        cartao.corpo.addWidget(nota)
        return cartao

    def _cartao_operacao(self) -> ui.Cartao:
        cartao = ui.Cartao("Operação — por máquina")
        self.grade_operacao = QGridLayout()
        self.grade_operacao.setHorizontalSpacing(22)
        self.grade_operacao.setVerticalSpacing(6)
        cartao.corpo.addLayout(self.grade_operacao)
        self.nota_operacao = QLabel(
            "Pacientes e inícios: marcados na agenda da máquina. Sessões: dias de "
            "tratamento entregues. Ocupação: sessões × minutos por sessão ÷ "
            "expediente útil até hoje — as mesmas contas da aba Agenda.")
        self.nota_operacao.setWordWrap(True)
        st.pintar(self.nota_operacao, lambda: (
            f"color:{st.TEXTO_APAGADO}; font-size:11.5px;"))
        cartao.corpo.addWidget(self.nota_operacao)
        return cartao

    def _rodape(self) -> QHBoxLayout:
        """Os dois botões existem e ficam APAGADOS, com o motivo.

        Botão aceso significa pronto (regra do projeto): clicar só para ouvir
        "ainda não" é o botão mentindo. Visíveis, porque mostrar onde eles vão
        morar é metade do que este protótipo existe para mostrar.
        """
        linha = QHBoxLayout()
        linha.addStretch(1)
        self.btn_congelar = ui.botao("Congelar mês", altura=34)
        st.pintar(self.btn_congelar, lambda: st.btn_contorno(12.5))
        self.btn_congelar.setEnabled(False)
        self.btn_congelar.setToolTip(
            "Apagado: a data da carga do data warehouse ainda não foi mapeada, "
            "e as fichas técnicas ainda não foram aprovadas.")
        self.btn_relatorio = ui.botao("Relatório do mês", cor="acao", altura=34)
        self.btn_relatorio.setEnabled(False)
        self.btn_relatorio.setToolTip("Em construção: o relatório mensal em PDF "
                                      "vem numa próxima frente.")
        linha.addWidget(self.btn_congelar)
        linha.addWidget(self.btn_relatorio)
        return linha

    # ── O que o controle chama ───────────────────────────────────────────

    def definir_mes(self, mes: date, estado: str, pode_avancar: bool) -> None:
        """O mês em cena e a linha de estado (provisório, fonte, hora do cálculo)."""
        self.lbl_mes.setText(nome_do_mes(mes))
        self.lbl_estado.setText(estado)
        self.btn_seguinte.setEnabled(pode_avancar)

    def definir_operacao(self, linhas, motivo: str = "") -> None:
        """``linhas``: ``[(maquina, sessoes, pacientes, inicios, ocupacao)]``.

        ``None`` com motivo — nunca lista vazia — quando não deu para
        perguntar: uma tabela vazia afirmaria que nenhuma máquina tratou.
        """
        while self.grade_operacao.count():
            item = self.grade_operacao.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        if linhas is None:
            self.status.setText(motivo)
            return
        self.status.setText(motivo)
        for col, titulo in enumerate(_CABECALHO_OPERACAO):
            cab = ui.rotulo(titulo.upper(), forte=True)
            self.grade_operacao.addWidget(
                cab, 0, col, alignment=Qt.AlignLeft if col == 0 else Qt.AlignRight)
        for lin, (maquina, sessoes, pacientes, inicios, ocupacao) in enumerate(
                linhas, start=1):
            celulas = (maquina, _numero(sessoes), _numero(pacientes),
                       _numero(inicios), _porcento(ocupacao))
            for col, texto in enumerate(celulas):
                rot = QLabel(texto)
                st.pintar(rot, lambda c=col: (
                    f"color:{st.TEXTO}; font-size:{14 if c == 0 else 13.5}px;"
                    f" font-weight:{'bold' if c == 0 else 'normal'};"))
                self.grade_operacao.addWidget(
                    rot, lin, col,
                    alignment=Qt.AlignLeft if col == 0 else Qt.AlignRight)

    def mostrar_status(self, texto: str) -> None:
        self.status.setText(texto)


__all__ = ["PainelRadioteradados", "NUCLEO_RDC", "nome_do_mes"]
