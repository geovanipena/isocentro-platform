"""O shell Torre de controle: Início de 3 zonas, doca e topo do módulo (R-23).

Fonte: DESIGN.md e EXPERIENCE.md da UX
(``docs/planejamento/sistema-global/ux-isocentro-2026-10-16``); CAP-19 da spec
Fundação. Árvore de widgets aceita pelo usuário em 28/10/2026 (``NOTAS.md``).

O que o Início mostra e de onde vem — e o que ele se RECUSA a mostrar:

- **Zona 1** precisa saber em que clínica cada máquina fica. Esse vínculo não
  existe no código (o ``unidade`` de ``constantes.Maquina`` é Clinica/SAT, não
  CEL/BET/DUO), então a coluna diz que ele falta, em vez de distribuir as
  máquinas por palpite. As três filas (Duplo Check, Aprovação Física,
  Vencimentos 60d) são de módulos que ainda não existem: "—" com o motivo,
  nunca 0. Zero por falta de dado é a máquina "normal" que ninguém conferiu
  (EXPERIENCE.md, State Patterns).
- **Zona 2** lê os alertas do núcleo (R-21), que moram no PostgreSQL. Sem a
  conexão (que é da R-19), o painel diz isso; "Nada precisa de ação" só com a
  fonte respondendo e a lista vazia.
- **Zona 3** é a doca de 9, sem contagem, recortada pelo perfil.

Perfil e clínicas vêm do login de hoje (``auth``) até a R-19: todas as clínicas
para todos, e "Todas" para o físico e o admin (decisão de 28/10/2026).

Nenhum ``QTimer`` daqui dispara gatilho: o único é o do relógio do topo, que só
redesenha a hora (AD-28 manda os gatilhos de tempo para a concentradora).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Iterable, Optional, Sequence

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QButtonGroup, QFrame, QGridLayout, QHBoxLayout,
                               QLabel, QPushButton, QSizePolicy, QVBoxLayout,
                               QWidget)

from isocentro.interface import estilo as st

# As clínicas na ordem da UX (CEL · BET · DUO). O código do banco chama a
# DUO de ANA (``atividades_db.UNIDADES``); a tela diz DUO.
CLINICAS = (("CEL", "CEL"), ("BET", "BET"), ("ANA", "DUO"))
TODAS = "Todas"

# Quem vê "Todas" enquanto o "físico responsável" não é atributo da pessoa
# (R-19): o físico e o admin, que hoje já veem tudo no app.
PAPEIS_COM_TODAS = frozenset({"fisico", "admin"})

NOMES_DOS_PAPEIS = {
    "admin": "admin", "fisico": "físico", "medico": "médico",
    "dosimetrista": "dosimetrista", "tecnico": "técnico",
    "enfermeiro": "enfermeiro", "recepcionista": "recepcionista",
    "spr": "SPR/gestão",
}


@dataclass(frozen=True)
class Modulo:
    chave: str
    nome: str
    # Falso = em construção (selo na doca, tela que só diz isso).
    pronto: bool
    papeis: frozenset


_TODOS = frozenset({"admin", "fisico", "medico", "dosimetrista", "tecnico",
                    "enfermeiro", "recepcionista", "spr"})

# A ordem e a visibilidade são as da UX (EXPERIENCE.md, "Os 9 módulos da doca"
# e "Perfil × módulo visível"). O admin vê todos: é o que ele já vê hoje, e a
# UX que faz do admin uma permissão sem módulos próprios depende da R-19.
MODULOS = (
    Modulo("radioteraficha", "Radioteraficha", True,
           _TODOS - {"spr"}),
    Modulo("plano", "Plano", False,
           frozenset({"admin", "medico", "fisico", "dosimetrista"})),
    Modulo("tratamento", "Tratamento", False,
           frozenset({"admin", "medico", "fisico", "tecnico", "enfermeiro"})),
    Modulo("qualidade", "Garantia da Qualidade", False,
           frozenset({"admin", "fisico", "tecnico", "spr"})),
    Modulo("seguranca", "Segurança do paciente", False, _TODOS),
    Modulo("documentacao", "Documentação e conformidade", True,
           frozenset({"admin", "fisico", "spr"})),
    Modulo("software", "Software e sistemas", False,
           frozenset({"admin", "fisico"})),
    Modulo("indicadores", "Indicadores", True,
           frozenset({"admin", "fisico", "spr"})),
    Modulo("conhecimento", "Conhecimento", False, _TODOS),
)


def modulos_do_papel(papel: str) -> list:
    """Os módulos que o perfil vê, na ordem da doca. O que não vê some (U7)."""
    return [m for m in MODULOS if papel in m.papeis]


def clinicas_do_papel(papel: str) -> list:
    """Os segmentos do seletor: as três clínicas, e "Todas" para quem vê tudo."""
    segmentos = [rotulo for _codigo, rotulo in CLINICAS]
    if papel in PAPEIS_COM_TODAS:
        segmentos.append(TODAS)
    return segmentos


def codigos_da_escolha(escolha: str) -> list:
    """O que a escolha do seletor quer dizer em códigos do banco."""
    if escolha == TODAS:
        return [codigo for codigo, _ in CLINICAS]
    return [codigo for codigo, rotulo in CLINICAS if rotulo == escolha]


def rotulo_da_clinica(codigo: str) -> str:
    return dict(CLINICAS).get(codigo, codigo)


# ── Folhas de estilo ─────────────────────────────────────────────────────────
# Foco: anel de 2 px em ``FOCO`` em todo clicável (DESIGN.md, Shell). O Qt não
# tem ``outline-offset``; a borda transparente de 2 px no estado normal é o que
# impede o widget de "pular" quando o anel aparece.

def _foco(seletor: str) -> str:
    return f"{seletor}:focus {{ border:2px solid {st.FOCO}; }}"


def _folha_segmento() -> str:
    return (
        "QPushButton { background:transparent;"
        f" color:{st.TEXTO_SECUNDARIO}; border:2px solid transparent;"
        " border-radius:6px; padding:3px 12px; font-size:12.5px;"
        " font-weight:600; }"
        f"QPushButton:hover {{ background:{st.SUPERFICIE_ELEVADA}; }}"
        # Marcada: fundo de ação e texto de ação, NÃO preenchida — o sólido
        # da tela é o "Abrir fila" (DESIGN.md, Seletor de clínica).
        f"QPushButton:checked {{ background:{st.ACAO_FUNDO}; color:{st.ACAO}; }}"
        + _foco("QPushButton"))


def _folha_discreto() -> str:
    return (
        "QPushButton { background:transparent;"
        f" color:{st.ACAO}; border:2px solid transparent; border-radius:6px;"
        " padding:3px 8px; font-size:12.5px; font-weight:600; }"
        f"QPushButton:hover {{ background:{st.SUPERFICIE_ELEVADA}; }}"
        f"QPushButton:disabled {{ color:{st.TEXTO_SECUNDARIO}; }}"
        + _foco("QPushButton"))


def _folha_primario() -> str:
    return (
        "QPushButton {"
        f" background:{st.ACAO}; color:{st.SOBRE_ACAO};"
        " border:2px solid transparent; border-radius:6px;"
        " padding:6px 16px; font-size:13px; font-weight:600; }"
        f"QPushButton:hover {{ background:{st.ACAO_FORTE}; }}"
        f"QPushButton:disabled {{ background:transparent;"
        f" color:{st.TEXTO_SECUNDARIO}; border:1px solid {st.BORDA}; }}"
        + _foco("QPushButton"))


def _folha_painel() -> str:
    return (f"QFrame#painel {{ background:{st.SUPERFICIE};"
            f" border:1px solid {st.BORDA}; border-radius:8px; }}")


def _rotulo(texto: str, papel: str = "apoio") -> QLabel:
    """QLabel com um papel da tipografia do DESIGN.md."""
    l = QLabel(texto)
    receitas = {
        "zona": lambda: (f"color:{st.TEXTO_SECUNDARIO}; font-size:11.5px;"
                         " font-weight:600; letter-spacing:1px;"),
        "apoio": lambda: f"color:{st.TEXTO_SECUNDARIO}; font-size:12px;",
        "base": lambda: f"color:{st.TEXTO}; font-size:13px;",
        "forte": lambda: f"color:{st.TEXTO}; font-size:13px; font-weight:600;",
        "sigla": lambda: (f"color:{st.TEXTO}; font-size:12.5px;"
                          " font-weight:700; letter-spacing:1px;"),
        "marca": lambda: (f"color:{st.TEXTO}; font-size:14px;"
                          " font-weight:700; letter-spacing:2px;"),
        "nome-modulo": lambda: (f"color:{st.TEXTO}; font-size:15px;"
                                " font-weight:700;"),
        "contador": lambda: (f"color:{st.TEXTO_SECUNDARIO}; font-size:18px;"
                             " font-weight:400;"),
        "selo": lambda: (f"color:{st.TEXTO_SECUNDARIO}; font-size:10px;"
                         " font-weight:500;"),
    }
    st.pintar(l, receitas[papel])
    return l


# ── Ícones de traço único (DESIGN.md: SVG 1,6 px, sem preenchimento) ─────────
# Desenhados com QPainter em vez de arquivo SVG: são nove desenhos de poucas
# linhas, e assim acompanham a cor do modo sem recolorir arquivo nenhum.

def _desenhar(chave: str, p: QPainter, r: QRectF) -> None:
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    cx, cy = r.center().x(), r.center().y()
    if chave in ("marca", "plano"):
        p.drawEllipse(r.adjusted(w * .1, h * .1, -w * .1, -h * .1))
        p.drawEllipse(r.adjusted(w * .32, h * .32, -w * .32, -h * .32))
        p.drawLine(QPointF(cx, y), QPointF(cx, y + h))
        p.drawLine(QPointF(x, cy), QPointF(x + w, cy))
    elif chave == "radioteraficha":
        caminho = QPainterPath(QPointF(x + w * .2, y + h * .1))
        caminho.lineTo(x + w * .62, y + h * .1)
        caminho.lineTo(x + w * .8, y + h * .28)
        caminho.lineTo(x + w * .8, y + h * .9)
        caminho.lineTo(x + w * .2, y + h * .9)
        caminho.closeSubpath()
        p.drawPath(caminho)
        for f in (.45, .6, .75):
            p.drawLine(QPointF(x + w * .32, y + h * f),
                       QPointF(x + w * .68, y + h * f))
    elif chave == "tratamento":
        p.drawRoundedRect(r.adjusted(w * .1, h * .18, -w * .1, -h * .1), 2, 2)
        p.drawLine(QPointF(x + w * .1, y + h * .38), QPointF(x + w * .9, y + h * .38))
        for f in (.32, .68):
            p.drawLine(QPointF(x + w * f, y + h * .08), QPointF(x + w * f, y + h * .26))
    elif chave == "qualidade":
        p.drawRect(r.adjusted(w * .1, h * .3, -w * .1, -h * .3))
        for i in range(1, 6):
            fx = x + w * (.1 + .8 * i / 6)
            p.drawLine(QPointF(fx, y + h * .3), QPointF(fx, y + h * (.45 if i % 2 else .52)))
    elif chave == "seguranca":
        caminho = QPainterPath(QPointF(cx, y + h * .08))
        caminho.lineTo(x + w * .85, y + h * .25)
        caminho.cubicTo(x + w * .85, y + h * .65, cx, y + h * .92, cx, y + h * .92)
        caminho.cubicTo(cx, y + h * .92, x + w * .15, y + h * .65, x + w * .15, y + h * .25)
        caminho.closeSubpath()
        p.drawPath(caminho)
    elif chave == "documentacao":
        caminho = QPainterPath(QPointF(x + w * .1, y + h * .25))
        caminho.lineTo(x + w * .4, y + h * .25)
        caminho.lineTo(x + w * .48, y + h * .35)
        caminho.lineTo(x + w * .9, y + h * .35)
        caminho.lineTo(x + w * .9, y + h * .85)
        caminho.lineTo(x + w * .1, y + h * .85)
        caminho.closeSubpath()
        p.drawPath(caminho)
    elif chave == "software":
        for lado in (-1, 1):
            bx = cx + lado * w * .22
            p.drawLine(QPointF(bx, y + h * .25), QPointF(bx + lado * w * .2, cy))
            p.drawLine(QPointF(bx + lado * w * .2, cy), QPointF(bx, y + h * .75))
    elif chave == "indicadores":
        p.drawLine(QPointF(x + w * .1, y + h * .9), QPointF(x + w * .9, y + h * .9))
        for f, alt in ((.25, .45), (.5, .25), (.75, .6)):
            p.drawLine(QPointF(x + w * f, y + h * .9), QPointF(x + w * f, y + h * alt))
    elif chave == "conhecimento":
        p.drawLine(QPointF(cx, y + h * .2), QPointF(cx, y + h * .88))
        p.drawRoundedRect(QRectF(x + w * .1, y + h * .14, w * .4, h * .7), 2, 2)
        p.drawRoundedRect(QRectF(cx, y + h * .14, w * .4, h * .7), 2, 2)


class Icone(QWidget):
    """Um ícone de traço único na cor de ``cor`` (lida a cada pintura)."""

    def __init__(self, chave: str, tamanho: int = 22,
                 cor: Callable[[], str] = lambda: st.TEXTO_SECUNDARIO,
                 parent=None):
        super().__init__(parent)
        self.chave = chave
        self._cor = cor
        self.setFixedSize(tamanho, tamanho)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def paintEvent(self, _ev):  # noqa: N802 — assinatura do Qt
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        caneta = QPen()
        caneta.setColor(QColor(self._cor()))
        caneta.setWidthF(1.6)
        p.setPen(caneta)
        p.setBrush(Qt.NoBrush)
        _desenhar(self.chave, p, QRectF(self.rect()).adjusted(1, 1, -1, -1))
        p.end()


# ── O topo ───────────────────────────────────────────────────────────────────

class _Relogio(QLabel):
    """"28/10/2026 · 07:43". Só redesenha a hora — não é gatilho (AD-28)."""

    def __init__(self, agora: Callable[[], datetime] = datetime.now, parent=None):
        super().__init__(parent)
        self._agora = agora
        st.pintar(self, lambda: (f"color:{st.TEXTO_SECUNDARIO}; font-size:12.5px;"))
        self._tique()
        self._timer = QTimer(self)
        self._timer.setInterval(20_000)
        self._timer.timeout.connect(self._tique)
        self._timer.start()

    def _tique(self) -> None:
        self.setText(f"{self._agora():%d/%m/%Y · %H:%M}")


class SeletorDeClinica(QWidget):
    """Controle segmentado: um segmento por clínica e "Todas" para quem pode."""

    mudou = Signal(str)

    def __init__(self, segmentos: Sequence[str], escolha: str, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        self._grupo = QButtonGroup(self)
        self._grupo.setExclusive(True)
        self.botoes: dict[str, QPushButton] = {}
        for nome in segmentos:
            b = QPushButton(nome)
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            st.pintar(b, _folha_segmento)
            self._grupo.addButton(b)
            lay.addWidget(b)
            self.botoes[nome] = b
            b.clicked.connect(lambda _c=False, n=nome: self.mudou.emit(n))
        inicial = escolha if escolha in self.botoes else segmentos[0]
        self.botoes[inicial].setChecked(True)

    def escolha(self) -> str:
        for nome, b in self.botoes.items():
            if b.isChecked():
                return nome
        return ""


class TopoDoInicio(QFrame):
    """◎ ISOCENTRO · seletor · ⟷ · relógio · ☾/☀ · usuário."""

    def __init__(self, seletor: SeletorDeClinica, usuario: str,
                 ao_alternar_cor: Optional[Callable[[], None]], parent=None):
        super().__init__(parent)
        self.setFixedHeight(48)
        st.pintar(self, lambda: (f"TopoDoInicio {{ background:{st.SUPERFICIE};"
                                 f" border-bottom:1px solid {st.BORDA}; }}"))
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 6, 16, 6)
        lay.setSpacing(12)
        lay.addWidget(Icone("marca", 20, cor=lambda: st.ACAO))
        lay.addWidget(_rotulo("ISOCENTRO", "marca"))
        lay.addSpacing(16)
        lay.addWidget(seletor)
        lay.addStretch(1)
        self.relogio = _Relogio()
        lay.addWidget(self.relogio)
        self.btn_cor = None
        if ao_alternar_cor is not None:
            self.btn_cor = _botao_cor(ao_alternar_cor)
            lay.addWidget(self.btn_cor)
        self.lbl_usuario = _rotulo(usuario, "base")
        lay.addWidget(self.lbl_usuario)


def _botao_cor(ao_alternar: Callable[[], None]) -> QPushButton:
    """Noite/dia. O texto diz para onde vai, não onde está."""
    b = QPushButton()
    b.setCursor(Qt.PointingHandCursor)
    st.pintar(b, _folha_discreto)

    def _texto():
        b.setText("☀ dia" if st.modo() == "noite" else "☾ noite")
        b.setToolTip("Trocar para o modo "
                     + ("dia" if st.modo() == "noite" else "noite"))
    _texto()
    st.ao_trocar(_texto)
    b.clicked.connect(ao_alternar)
    return b


# ── Zona 1 ───────────────────────────────────────────────────────────────────

# As filas da Zona 1 (EXPERIENCE.md, Component Patterns). Todas dependem de
# módulos que ainda não existem.
FILAS = ("Duplo Check", "Aprovação Física", "Vencimentos 60d")
SEM_FONTE_FILA = "sem fonte: módulo em construção"
SEM_VINCULO_MAQUINA = ("Máquinas: o vínculo máquina → clínica ainda não está "
                       "cadastrado.")


class ColunaDeClinica(QFrame):
    """Sigla, máquinas e as três filas de uma clínica."""

    def __init__(self, codigo: str, parent=None):
        super().__init__(parent)
        self.codigo = codigo
        self.setObjectName("painel")
        st.pintar(self, _folha_painel)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(8)
        lay.addWidget(_rotulo(rotulo_da_clinica(codigo), "sigla"))
        self.lbl_maquinas = _rotulo(SEM_VINCULO_MAQUINA, "apoio")
        self.lbl_maquinas.setWordWrap(True)
        lay.addWidget(self.lbl_maquinas)
        lay.addStretch(1)
        linha = QFrame()
        linha.setFixedHeight(1)
        st.pintar(linha, lambda: f"background:{st.BORDA}; border:none;")
        lay.addWidget(linha)
        filas = QHBoxLayout()
        filas.setSpacing(8)
        self.contadores: dict[str, QLabel] = {}
        for nome in FILAS:
            caixa = QVBoxLayout()
            caixa.setSpacing(0)
            caixa.addWidget(_rotulo(nome, "apoio"))
            numero = _rotulo("—", "contador")
            numero.setToolTip(SEM_FONTE_FILA)
            caixa.addWidget(numero)
            self.contadores[nome] = numero
            filas.addLayout(caixa, 1)
        lay.addLayout(filas)
        self.lbl_sem_fonte = _rotulo(f"Filas: {SEM_FONTE_FILA}.", "selo")
        lay.addWidget(self.lbl_sem_fonte)


# ── Zona 2 ───────────────────────────────────────────────────────────────────

FORMAS = {"alta": "▲", "atencao": "◆", "informativo": "○"}
PALAVRAS = {"alta": "ALTA", "atencao": "ATENÇÃO", "informativo": "INFO"}
_CORES = {
    "alta": (lambda: st.ALTA, lambda: st.ALTA_TEXTO, lambda: st.ALTA_FUNDO),
    "atencao": (lambda: st.ATENCAO, lambda: st.ATENCAO_TEXTO,
                lambda: st.ATENCAO_FUNDO),
    "informativo": (lambda: st.INFO, lambda: st.INFO_TEXTO,
                    lambda: st.INFO_FUNDO),
}
LINHAS_VISIVEIS = 5
SEM_BANCO = ("Banco central não configurado: os alertas não podem ser lidos.")
NADA_A_FAZER = "Nada precisa de ação nesta clínica."
# U+FE0E força o glifo de texto: sem ele o ▲ pode virar emoji colorido.
_TEXTO = "︎"


class LinhaDeAcao(QFrame):
    """Uma linha da fila: severidade · o quê · detalhe · prazo · clínica · estado.

    ``alerta`` é qualquer objeto com ``severidade``, ``objeto``, ``motivo``,
    ``vence_em``, ``clinica`` e ``estado`` (o ``AlertaGravado`` da R-21 serve).
    Vista: mantém forma e cor, perde o fundo, borda lateral tracejada.
    """

    def __init__(self, alerta, parent=None):
        super().__init__(parent)
        self.alerta = alerta
        sev = getattr(alerta, "severidade", "informativo")
        sinal, texto, fundo = _CORES.get(sev, _CORES["informativo"])
        estado = getattr(getattr(alerta, "estado", None), "value",
                         getattr(alerta, "estado", "aberto"))
        visto = estado == "visto"
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)
        st.pintar(self, lambda: (
            f"LinhaDeAcao {{ background:{'transparent' if visto else fundo()};"
            f" border:none; border-left:3px {'dashed' if visto else 'solid'}"
            f" {sinal()}; border-top-right-radius:6px;"
            " border-bottom-right-radius:6px; }"
            f"LinhaDeAcao:focus {{ border:2px solid {st.FOCO};"
            f" border-left:3px solid {sinal()}; }}"))
        grade = QGridLayout(self)
        grade.setContentsMargins(10, 6, 10, 6)
        grade.setHorizontalSpacing(12)
        chip = QLabel(f"{FORMAS.get(sev, '○')}{_TEXTO} {PALAVRAS.get(sev, '')}")
        st.pintar(chip, lambda: (f"color:{texto()}; font-size:11px;"
                                 " font-weight:700;"))
        chip.setFixedWidth(104)
        oque = _rotulo(str(getattr(alerta, "objeto", "")), "forte")
        oque.setFixedWidth(232)
        detalhe = _rotulo(str(getattr(alerta, "motivo", "")), "base")
        vence = getattr(alerta, "vence_em", None)
        prazo = _rotulo(f"{vence:%d/%m %H:%M}" if vence else "sem prazo", "apoio")
        prazo.setFixedWidth(150)
        clinica = _rotulo(rotulo_da_clinica(str(getattr(alerta, "clinica", ""))),
                          "apoio")
        clinica.setFixedWidth(56)
        vistos = getattr(alerta, "vistos", None) or []
        if visto and vistos:
            quem, quando = vistos[-1]
            rot_estado = f"visto · {quem} · {quando:%H:%M}"
        else:
            rot_estado = estado
        estado_lbl = _rotulo(rot_estado, "apoio")
        estado_lbl.setFixedWidth(150)
        for col, w in enumerate((chip, oque, detalhe, prazo, clinica, estado_lbl)):
            grade.addWidget(w, 0, col)
        grade.setColumnStretch(2, 1)


class PainelDeAcao(QFrame):
    """A Zona 2: as 5 primeiras linhas, "ver mais N" e o "Abrir fila"."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("painel")
        st.pintar(self, _folha_painel)
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(14, 12, 14, 12)
        self._lay.setSpacing(6)
        self._linhas = QVBoxLayout()
        self._linhas.setSpacing(6)
        self._lay.addLayout(self._linhas)
        self.lbl_vazio = _rotulo("", "apoio")
        self._lay.addWidget(self.lbl_vazio)
        self._lay.addStretch(1)
        rodape = QHBoxLayout()
        self.btn_ver_mais = QPushButton()
        self.btn_ver_mais.setCursor(Qt.PointingHandCursor)
        st.pintar(self.btn_ver_mais, _folha_discreto)
        self.btn_ver_mais.clicked.connect(self._ver_mais)
        rodape.addWidget(self.btn_ver_mais)
        rodape.addStretch(1)
        self.btn_abrir_fila = QPushButton("Abrir fila")
        self.btn_abrir_fila.setCursor(Qt.PointingHandCursor)
        st.pintar(self.btn_abrir_fila, _folha_primario)
        # Sem destino ainda: a lista completa do perfil é da R-19 (#36 de
        # decisoes-sem-base). Botão aceso é botão pronto (CLAUDE.md).
        self.btn_abrir_fila.setEnabled(False)
        self.btn_abrir_fila.setToolTip(
            "A fila completa chega com o login no banco central (R-19).")
        rodape.addWidget(self.btn_abrir_fila)
        self._lay.addLayout(rodape)
        self._alertas: list = []
        self._todos = False
        self.linhas: list[LinhaDeAcao] = []
        self.mostrar(None)

    def mostrar(self, alertas: Optional[Iterable], *,
                sem_fonte: str = SEM_BANCO) -> None:
        """``None`` = a fonte não respondeu; ``[]`` = respondeu e não há nada."""
        self._alertas = None if alertas is None else list(alertas)
        self._todos = False
        self._redesenhar(sem_fonte)

    def total(self) -> Optional[int]:
        return None if self._alertas is None else len(self._alertas)

    def _ver_mais(self) -> None:
        self._todos = True
        self._redesenhar(SEM_BANCO)

    def _redesenhar(self, sem_fonte: str) -> None:
        while self._linhas.count():
            item = self._linhas.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.linhas = []
        if self._alertas is None:
            # Sem fonte nada se afirma: nem a lista vazia, nem "nada a fazer".
            self.lbl_vazio.setText(sem_fonte)
            self.lbl_vazio.setVisible(True)
            self.btn_ver_mais.setVisible(False)
            return
        if not self._alertas:
            self.lbl_vazio.setText(NADA_A_FAZER)
            self.lbl_vazio.setVisible(True)
            self.btn_ver_mais.setVisible(False)
            return
        self.lbl_vazio.setVisible(False)
        visiveis = (self._alertas if self._todos
                    else self._alertas[:LINHAS_VISIVEIS])
        for a in visiveis:
            linha = LinhaDeAcao(a)
            self._linhas.addWidget(linha)
            self.linhas.append(linha)
        resto = len(self._alertas) - len(visiveis)
        self.btn_ver_mais.setText(f"ver mais {resto}")
        self.btn_ver_mais.setVisible(resto > 0)


# ── Zona 3 ───────────────────────────────────────────────────────────────────

class BlocoDaDoca(QPushButton):
    """Ícone + nome, centrados; sem contagem; selo se em construção."""

    def __init__(self, modulo: Modulo, parent=None):
        super().__init__(parent)
        self.modulo = modulo
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(100)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setAccessibleName(modulo.nome)
        st.pintar(self, lambda: (
            f"BlocoDaDoca {{ background:{st.SUPERFICIE};"
            f" border:1px solid {st.BORDA}; border-radius:8px; }}"
            f"BlocoDaDoca:hover {{ background:{st.SUPERFICIE_ELEVADA};"
            f" border-color:{st.ACAO}; }}"
            f"BlocoDaDoca:focus {{ border:2px solid {st.FOCO}; }}"))
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 10, 6, 8)
        lay.setSpacing(4)
        icone = Icone(modulo.chave, 22)
        lay.addWidget(icone, 0, Qt.AlignHCenter)
        nome = _rotulo(modulo.nome, "apoio" if not modulo.pronto else "forte")
        nome.setAlignment(Qt.AlignCenter)
        nome.setWordWrap(True)
        nome.setAttribute(Qt.WA_TransparentForMouseEvents)
        lay.addWidget(nome)
        self.selo = None
        if not modulo.pronto:
            self.selo = _rotulo("em construção", "selo")
            self.selo.setAlignment(Qt.AlignCenter)
            self.selo.setAttribute(Qt.WA_TransparentForMouseEvents)
            lay.addWidget(self.selo)


# ── O Início ─────────────────────────────────────────────────────────────────

class Inicio(QWidget):
    """As três zonas empilhadas, com o topo acima delas."""

    abrir_modulo = Signal(str)
    clinica_mudou = Signal(str)

    def __init__(self, usuario: dict, *, clinica_inicial: str = "",
                 ao_alternar_cor: Optional[Callable[[], None]] = None,
                 parent=None):
        super().__init__(parent)
        self.papel = str((usuario or {}).get("papel") or "")
        nome = ((usuario or {}).get("nome") or (usuario or {}).get("usuario")
                or "")
        st.pintar(self, lambda: f"Inicio {{ background:{st.FUNDO}; }}")
        self.setAttribute(Qt.WA_StyledBackground, True)
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        segmentos = clinicas_do_papel(self.papel)
        padrao = TODAS if TODAS in segmentos else segmentos[0]
        self.seletor = SeletorDeClinica(segmentos, clinica_inicial or padrao)
        self.seletor.mudou.connect(self._clinica_escolhida)
        self.topo = TopoDoInicio(self.seletor, nome, ao_alternar_cor)
        raiz.addWidget(self.topo)

        corpo = QVBoxLayout()
        corpo.setContentsMargins(16, 14, 16, 14)
        corpo.setSpacing(14)
        raiz.addLayout(corpo, 1)

        self.rot_zona1 = _rotulo("1 · SITUAÇÃO DO SERVIÇO", "zona")
        corpo.addWidget(self.rot_zona1)
        self._colunas_lay = QHBoxLayout()
        self._colunas_lay.setSpacing(12)
        corpo.addLayout(self._colunas_lay, 3)
        self.colunas: list[ColunaDeClinica] = []

        self.rot_zona2 = _rotulo("2 · O QUE PRECISA DE AÇÃO", "zona")
        corpo.addWidget(self.rot_zona2)
        self.painel_acao = PainelDeAcao()
        corpo.addWidget(self.painel_acao, 3)

        corpo.addWidget(_rotulo("3 · MÓDULOS", "zona"))
        doca = QHBoxLayout()
        doca.setSpacing(10)
        self.blocos: list[BlocoDaDoca] = []
        visiveis = modulos_do_papel(self.papel)
        for m in visiveis:
            b = BlocoDaDoca(m)
            b.clicked.connect(lambda _c=False, ch=m.chave: self.abrir_modulo.emit(ch))
            doca.addWidget(b, 1)
            self.blocos.append(b)
        # Menos de 9 visíveis: os blocos mantêm 1/9 da largura e alinham à
        # esquerda (DESIGN.md, Layout & Spacing).
        if len(visiveis) < len(MODULOS):
            doca.addStretch(len(MODULOS) - len(visiveis))
        corpo.addLayout(doca)

        self._montar_colunas()
        self._ordem_de_tab()

    # ── Clínica ─────────────────────────────────────────────────────────────

    def clinica(self) -> str:
        return self.seletor.escolha()

    def _clinica_escolhida(self, escolha: str) -> None:
        self._montar_colunas()
        self.clinica_mudou.emit(escolha)

    def _montar_colunas(self) -> None:
        for c in self.colunas:
            self._colunas_lay.removeWidget(c)
            c.deleteLater()
        self.colunas = [ColunaDeClinica(cod)
                        for cod in codigos_da_escolha(self.clinica())]
        for c in self.colunas:
            self._colunas_lay.addWidget(c, 1)
        self._ordem_de_tab()

    # ── Alertas ─────────────────────────────────────────────────────────────

    def mostrar_alertas(self, alertas: Optional[Iterable],
                        sem_fonte: str = SEM_BANCO) -> None:
        """A Zona 2. ``None`` diz que a fonte não respondeu."""
        self.painel_acao.mostrar(alertas, sem_fonte=sem_fonte)
        total = self.painel_acao.total()
        self.rot_zona2.setText("2 · O QUE PRECISA DE AÇÃO"
                               + (f" · {total}" if total else ""))
        self._ordem_de_tab()

    # ── Teclado ─────────────────────────────────────────────────────────────

    def _ordem_de_tab(self) -> None:
        """Topo → Zona 2 → doca (EXPERIENCE.md, Interaction Primitives).

        A Zona 1 entra quando tiver o que clicar: hoje as colunas não têm
        máquina nem fila com destino.
        """
        ordem: list[QWidget] = list(self.seletor.botoes.values())
        if self.topo.btn_cor is not None:
            ordem.append(self.topo.btn_cor)
        ordem += self.painel_acao.linhas
        ordem += [self.painel_acao.btn_ver_mais, self.painel_acao.btn_abrir_fila]
        ordem += self.blocos
        for a, b in zip(ordem, ordem[1:]):
            QWidget.setTabOrder(a, b)


# ── O módulo ─────────────────────────────────────────────────────────────────

class TopoDoModulo(QFrame):
    """◂ Início │ ícone + nome │ faixa de telas │ contexto. Sem seletor de clínica."""

    voltar = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        st.pintar(self, lambda: (f"TopoDoModulo {{ background:{st.SUPERFICIE};"
                                 f" border-bottom:1px solid {st.BORDA}; }}"))
        self._lay = QHBoxLayout(self)
        self._lay.setContentsMargins(10, 4, 10, 4)
        self._lay.setSpacing(10)
        self.btn_inicio = QPushButton("◂ Início")
        self.btn_inicio.setCursor(Qt.PointingHandCursor)
        self.btn_inicio.setToolTip("Voltar ao Início (Alt+Home)")
        st.pintar(self.btn_inicio, _folha_discreto)
        self.btn_inicio.clicked.connect(self.voltar.emit)
        self._lay.addWidget(self.btn_inicio)
        self._icone: Optional[Icone] = None
        self.lbl_nome = _rotulo("", "nome-modulo")
        self._lay.addWidget(self.lbl_nome)
        sep = QFrame()
        sep.setFixedWidth(1)
        st.pintar(sep, lambda: f"background:{st.BORDA}; border:none;")
        self._lay.addWidget(sep)
        # Uma ÁREA para a faixa, e não um layout solto: com a faixa escondida
        # (módulo de uma tela só), o layout vazio não segurava o espaço, e o
        # ◂ Início, o nome e o contexto se espalhavam pela linha inteira.
        self._area_faixa = QWidget()
        self._area_faixa.setSizePolicy(QSizePolicy.Expanding,
                                       QSizePolicy.Preferred)
        self._faixa_lay = QHBoxLayout(self._area_faixa)
        self._faixa_lay.setContentsMargins(0, 0, 0, 0)
        self._lay.addWidget(self._area_faixa, 1)
        self.lbl_contexto = _rotulo("", "apoio")
        self._lay.addWidget(self.lbl_contexto)

    def definir(self, modulo: Modulo, contexto: str) -> None:
        if self._icone is not None:
            self._lay.removeWidget(self._icone)
            self._icone.deleteLater()
        self._icone = Icone(modulo.chave, 20)
        self._lay.insertWidget(1, self._icone)
        self.lbl_nome.setText(modulo.nome)
        self.lbl_contexto.setText(contexto)

    def definir_faixa(self, faixa: Optional[QWidget]) -> None:
        """Põe (ou tira, com ``None``) a faixa de telas do módulo."""
        while self._faixa_lay.count():
            item = self._faixa_lay.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        if faixa is not None:
            self._faixa_lay.addWidget(faixa, 1)


class TelaEmConstrucao(QWidget):
    """O módulo que ainda não existe: diz só isso, sem dado fictício."""

    def __init__(self, parent=None):
        super().__init__(parent)
        st.pintar(self, lambda: f"TelaEmConstrucao {{ background:{st.FUNDO}; }}")
        self.setAttribute(Qt.WA_StyledBackground, True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        painel = QFrame()
        painel.setObjectName("painel")
        st.pintar(painel, _folha_painel)
        p = QVBoxLayout(painel)
        p.setContentsMargins(18, 16, 18, 16)
        self.lbl_nome = _rotulo("", "nome-modulo")
        p.addWidget(self.lbl_nome)
        self.lbl_frase = _rotulo("", "apoio")
        self.lbl_frase.setWordWrap(True)
        p.addWidget(self.lbl_frase)
        lay.addWidget(painel)
        lay.addStretch(1)

    def definir(self, modulo: Modulo) -> None:
        self.lbl_nome.setText(modulo.nome)
        self.lbl_frase.setText(
            "Este módulo está em construção. Quando estiver pronto, o trabalho "
            "dele acontece aqui.")


def texto_da_barra(usuario: dict, clinica: str) -> str:
    """"Geova · físico · Todas" — à esquerda da barra de status."""
    nome = (usuario or {}).get("nome") or (usuario or {}).get("usuario") or ""
    papel = NOMES_DOS_PAPEIS.get(str((usuario or {}).get("papel") or ""), "")
    return " · ".join(p for p in (nome, papel, clinica) if p)
