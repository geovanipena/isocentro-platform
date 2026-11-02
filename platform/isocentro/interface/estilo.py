"""Paleta e estilos — fonte única, compartilhada entre as telas.

Viviam dentro do ``gui.py``. Saíram daqui para que a tela Fichinha
(``fichinha.py``) use exatamente a mesma silhueta sem importar o ``gui`` e criar
um ciclo: os dois módulos importam este, e este não importa nenhum dos dois.

**Torre de controle (R-23, 28/10/2026).** Os valores são as 23 chaves do
``DESIGN.md`` da UX (``docs/planejamento/sistema-global/ux-isocentro-2026-10-16``),
paleta "Sala de controle · azul-ardósia": fundo calmo e escuro, cor só onde há
problema, o que está certo fica neutro. Até a R-23 o acento era o
verde-azulado da folha impressa, para a tela e o papel se parecerem; a UX
trocou isso por uma identidade só para o ISOCENTRO inteiro (ML 26-28), e o
PAPEL não mudou (as cores dele moram em ``ficha_pdf``/``capa_pdf``).

**Severidade IEC 60601-1-8:** ``ALTA`` vermelho, ``ATENCAO`` amarelo, ``INFO``
ciano, cada uma com sinal (ícone, borda lateral), texto e fundo — e sempre com a
forma junto (▲ ◆ ○), porque no dia os três sinais quase empatam em luminância.

**Verde é dose.** ``DOSE`` é a única chave verde, e só a isodose a usa. Nenhum
token de ação, status, "ok" ou severidade é verde; o que está certo fica em
``ESTADO_NEUTRO`` ou ``TEXTO_FRACO``. O ``test_padrao_visual`` reprova verde em
qualquer outra chave e ``DOSE`` fora dos arquivos de isodose.

As chaves de antes (``ACAO_FORTE``, ``FUNDO_CAMPO``, ``AMBAR``…) continuam: são
~140 usos espalhados pelas telas do Radioteraficha, cujo redesenho é de outra
frente. Cada uma recebeu o valor da chave Torre que faz o mesmo papel — nenhum
valor novo foi inventado aqui.

Hierarquia de botão é de PREENCHIMENTO, não de matiz — ver ``btn_solido``,
``btn_contorno``, ``btn_fantasma`` e ``btn_perigo``. Um sólido por tela.

**Trocar de modo em tempo de execução.** Toda folha de estilo é montada a partir
destas constantes, mas as folhas viram texto no momento em que o widget nasce —
trocar a constante depois não repinta nada. Quem precisa acompanhar a troca
registra a receita, não o resultado: ver :func:`pintar` e :func:`ao_trocar`.
"""
from __future__ import annotations

from typing import Callable

# ── As 23 chaves da Torre (DESIGN.md → Colors) ───────────────────────────────
# Mesmas chaves nos dois modos: o que troca é só o valor.

_TORRE_NOITE = {
    "FUNDO": "#0E1621",
    "SUPERFICIE": "#152030",
    "SUPERFICIE_ELEVADA": "#1C2A3D",
    "BORDA": "#2B3B52",
    "TEXTO": "#E4ECF5",
    "TEXTO_SECUNDARIO": "#9AABC0",
    "ACAO": "#8C9EFF",
    "SOBRE_ACAO": "#0E1621",
    "ACAO_FUNDO": "#1E2650",
    "FOCO": "#C9D2FF",
    "ALTA": "#FF5C61",
    "ALTA_TEXTO": "#FF8A8D",
    "ALTA_FUNDO": "#3B1519",
    "ATENCAO": "#FFC93C",
    "ATENCAO_TEXTO": "#FFD466",
    "ATENCAO_FUNDO": "#36290A",
    "INFO": "#2CCFE0",
    "INFO_TEXTO": "#5FDDEA",
    "INFO_FUNDO": "#0C2E36",
    "ESTADO_NEUTRO": "#93A3B6",
    "DADO_AO_VIVO": "#B9C4FF",
    "DADO_ESPELHO": "#8292A5",
    "DOSE": "#3DDC84",
}

_TORRE_DIA = {
    "FUNDO": "#EDF1F6",
    "SUPERFICIE": "#FFFFFF",
    "SUPERFICIE_ELEVADA": "#F5F8FB",
    "BORDA": "#C6D1DE",
    "TEXTO": "#111A25",
    "TEXTO_SECUNDARIO": "#4B5A6C",
    "ACAO": "#3A47C9",
    "SOBRE_ACAO": "#FFFFFF",
    "ACAO_FUNDO": "#E4E7FB",
    "FOCO": "#1E2A8F",
    "ALTA": "#D7263D",
    "ALTA_TEXTO": "#B0182C",
    "ALTA_FUNDO": "#FBE2E5",
    "ATENCAO": "#BB8D00",
    "ATENCAO_TEXTO": "#755000",
    "ATENCAO_FUNDO": "#FFF2C7",
    "INFO": "#0EA3B5",
    "INFO_TEXTO": "#00687A",
    "INFO_FUNDO": "#DCF4F7",
    "ESTADO_NEUTRO": "#566577",
    "DADO_AO_VIVO": "#3A47C9",
    "DADO_ESPELHO": "#5E6B7B",
    "DOSE": "#1E8E4E",
}


def _com_chaves_antigas(c: dict, *, selecao: str, sobre_selecao: str) -> dict:
    """As chaves de antes, cada uma com o valor da chave Torre do mesmo papel.

    ``ACAO_FORTE`` (hover do sólido) é o ``FOCO``: o mais claro da família na
    noite e o mais escuro no dia, que é o "mais forte" de cada modo.
    ``ACAO_CLARA`` é o ``DADO_AO_VIVO``, o índigo claro da família.
    ``ACAO_LINHA`` (contorno do secundário) é o próprio ``ACAO``: o DESIGN.md
    pede o contorno do secundário em ``acao``.
    """
    return {
        **c,
        "ACAO_FORTE": c["FOCO"],
        "ACAO_CLARA": c["DADO_AO_VIVO"],
        "ACAO_LINHA": c["ACAO"],
        "FUNDO_TELA": c["FUNDO"],
        "FUNDO_BLOCO": c["SUPERFICIE"],
        "FUNDO_CARTAO": c["SUPERFICIE"],
        "FUNDO_CAMPO": c["SUPERFICIE_ELEVADA"],
        "FUNDO_FUNDO": c["FUNDO"],
        "TEXTO_FRACO": c["TEXTO_SECUNDARIO"],
        "TEXTO_APAGADO": c["DADO_ESPELHO"],
        "BORDA_SUAVE": c["SUPERFICIE_ELEVADA"],
        "BORDA_FORTE": c["DADO_ESPELHO"],
        "AMBAR": c["ATENCAO"],
        "AMBAR_FUNDO": c["ATENCAO_FUNDO"],
        "VERMELHO": c["ALTA"],
        "VERMELHO_LINHA": c["ALTA"],
        "SELECAO": selecao,
        "SOBRE_SELECAO": sobre_selecao,
    }


# Seleção do sistema: no dia, o índigo cheio com texto branco; na noite, o
# fundo de ação com o texto claro — o índigo claro da noite com texto escuro
# leria como botão primário dentro de uma lista.
DIA = _com_chaves_antigas(_TORRE_DIA, selecao=_TORRE_DIA["ACAO"],
                          sobre_selecao=_TORRE_DIA["SOBRE_ACAO"])
NOITE = _com_chaves_antigas(_TORRE_NOITE, selecao=_TORRE_NOITE["ACAO_FUNDO"],
                            sobre_selecao=_TORRE_NOITE["TEXTO"])

MODOS = {"dia": DIA, "noite": NOITE}
MODO_PADRAO = "noite"

_modo_atual = MODO_PADRAO

# Cada item é ``(sonda, repintar)``: a sonda diz se o widget ainda existe SEM
# repintá-lo, e é o que permite varrer a lista fora de uma troca de modo.
_ouvintes: list[tuple[Callable[[], bool], Callable[[], None]]] = []

# A partir daqui, registrar mais um dispara uma varredura. Não é estética: os
# cartões de preparo do posicionamento são refeitos A CADA TECLA digitada nos
# acessórios, três pinturas por cartão — sem varrer fora da troca de modo, uma
# sessão de trabalho normal empilharia dezenas de milhares de mortos.
_LIMITE_VARREDURA = 400


# ── Nomes antigos, papéis novos ──────────────────────────────────────────────
# O código chama ``st.AZUL`` (estrutura) e ``st.VERDE`` (ação) em ~140 lugares.
# Os dois papéis continuam existindo; o que mudou foi que agora são a MESMA
# família — o verde-azulado do formulário. Manter os nomes antigos como apelidos
# evita uma renomeação de 140 pontos sem nada em troca, e a convenção
# "azul é estrutura, verde é ação" segue valendo na leitura do código.
_APELIDOS = {
    "AZUL": "ACAO",
    "AZUL_CLARO": "ACAO_CLARA",
    "AZUL_FUNDO": "ACAO_FUNDO",
    "VERDE": "ACAO",
    "VERDE_ESCURO": "ACAO_FORTE",
    "VERDE_CLARO": "ACAO_CLARA",
    "VERDE_BRILHO": "ACAO_FORTE",
    "VERDE_FUNDO": "ACAO_FUNDO",
}


def _aplicar(nome: str) -> None:
    """Reescreve as constantes do módulo com as do modo ``nome``."""
    global _modo_atual
    _modo_atual = nome if nome in MODOS else MODO_PADRAO
    cores = MODOS[_modo_atual]
    g = globals()
    g.update(cores)
    for velho, novo in _APELIDOS.items():
        g[velho] = cores[novo]


def modo() -> str:
    """"dia" ou "noite"."""
    return _modo_atual


def definir_modo(nome: str) -> str:
    """Troca o modo e repinta quem se registrou. Devolve o modo em vigor.

    Aproveita a passagem para **descartar os ouvintes de widgets já mortos**.
    Sem isso a lista só cresceria: as linhas de "Suas últimas fichas" são
    recriadas a cada atualização da tela, e cada recriação registraria mais três
    pinturas para widgets que não existem mais.
    """
    if nome == _modo_atual:
        return _modo_atual
    _aplicar(nome)
    vivos = []
    for sonda, repintar in list(_ouvintes):
        try:
            if not sonda():
                continue
            repintar()
            vivos.append((sonda, repintar))
        except Exception:  # noqa: BLE001 — um widget morto não derruba a troca
            pass
    _ouvintes[:] = vivos
    return _modo_atual


def _varrer() -> None:
    """Descarta os registros de widgets já destruídos, sem repintar ninguém."""
    vivos = []
    for par in list(_ouvintes):
        try:
            if par[0]():
                vivos.append(par)
        except Exception:  # noqa: BLE001
            pass
    _ouvintes[:] = vivos


def alternar() -> str:
    """Dia ↔ noite."""
    return definir_modo("dia" if _modo_atual == "noite" else "noite")


def ao_trocar(fn: Callable[[], None]) -> None:
    """Registra algo para refazer a cada troca de modo.

    Sem sonda: quem chama é dono do que registrou e vive enquanto o app viver
    (a barra de título, o símbolo da faixa). Widget vai por :func:`pintar`.
    """
    _ouvintes.append((lambda: True, fn))


def pintar(widget, receita: Callable[[], str]) -> None:
    """Aplica a folha de estilo AGORA e a refaz a cada troca de modo.

    Guarda a **receita**, não o resultado: a folha é texto, e o texto congela as
    cores do momento em que o widget nasceu. ``pintar(w, lambda: f"...{st.ACAO}...")``
    é a diferença entre um widget que acompanha a troca e um que fica para trás.

    A referência ao widget é FORTE, e isso é deliberado. Com ``weakref`` o
    registro morria cedo demais: o PyQt coleta o *wrapper* Python de um widget
    que só o C++ referencia — todo campo criado dentro de uma fábrica e entregue
    a um layout —, e a folha desaparecia junto. Numa tela de Capa isso eram 25
    campos que paravam de acompanhar a troca.

    Segurar a referência não vaza no caso que existe: o widget com pai pertence
    ao C++, e quando o pai morre o objeto vai junto. O que sobra é o invólucro,
    e mexer nele levanta ``RuntimeError`` — é assim que o registro se limpa.

    **O custo:** um widget SEM PAI registrado aqui não é coletado enquanto o
    programa viver, porque esta lista é a dona dele. Na prática todo widget
    pintado acaba dentro de um layout; se algum dia houver um solto e
    descartável, ele precisa ser desregistrado à mão ou ganhar um pai.
    """
    widget.setStyleSheet(receita())

    def _vivo() -> bool:
        """O C++ ainda está lá? Uma pergunta barata, que não repinta nada."""
        try:
            widget.objectName()
        except RuntimeError:
            return False
        return True

    if len(_ouvintes) >= _LIMITE_VARREDURA:
        _varrer()
    _ouvintes.append((_vivo, lambda: widget.setStyleSheet(receita())))


_aplicar(MODO_PADRAO)


# ── Os três pesos de botão ───────────────────────────────────────────────────
# A hierarquia é de PREENCHIMENTO, não de matiz. Antes havia uma escala de
# quatro verdes codificando a posição na trilha — regra invisível para quem usa,
# que se lia como decoração; e, com cinco botões cheios na mesma tela, a cor de
# ação parava de significar ação.
#
#   sólido    UM por tela: o passo que não se desfaz (gerar, imprimir)
#   contorno  o resto do fluxo, que se desfaz (editar, visualizar, agendar)
#   fantasma  navegação — levar a outro lugar não é agir sobre o caso
#   perigo    contorno vermelho, NUNCA cheio: preenchido, atrai o clique de
#             que ele avisa

def btn_solido(tam: float = 13.0) -> str:
    return (
        "QPushButton {"
        f" background:{ACAO}; color:{SOBRE_ACAO};"
        f" font-weight:650; font-size:{tam}px; border:none;"
        "  border-radius:8px; padding:10px 16px; text-align:center; }"
        f"QPushButton:hover {{ background:{ACAO_FORTE}; }}"
        f"QPushButton:pressed {{ background:{ACAO};"
        "   padding-top:11px; padding-bottom:9px; }"
        f"QPushButton:disabled {{ background:transparent; color:{TEXTO_APAGADO};"
        f"  border:1px solid {BORDA}; }}"
    )


def btn_contorno(tam: float = 13.0) -> str:
    return (
        "QPushButton {"
        f" background:transparent; color:{ACAO};"
        f" font-weight:650; font-size:{tam}px;"
        f" border:1px solid {ACAO_LINHA}; border-radius:8px;"
        "  padding:10px 16px; text-align:center; }"
        f"QPushButton:hover {{ background:{ACAO_FUNDO}; border-color:{ACAO}; }}"
        f"QPushButton:pressed {{ background:{ACAO}; color:{SOBRE_ACAO}; }}"
        f"QPushButton:disabled {{ background:transparent; color:{TEXTO_APAGADO};"
        f"  border-color:{BORDA}; }}"
    )


def btn_fantasma(tam: float = 13.0) -> str:
    return (
        "QPushButton {"
        f" background:transparent; color:{TEXTO_FRACO};"
        f" font-weight:600; font-size:{tam}px; border:1px solid transparent;"
        "  border-radius:8px; padding:10px 16px; text-align:center; }"
        f"QPushButton:hover {{ background:{FUNDO_CAMPO}; color:{TEXTO}; }}"
        f"QPushButton:disabled {{ color:{TEXTO_APAGADO}; }}"
    )


def btn_perigo(tam: float = 13.0) -> str:
    return (
        "QPushButton {"
        f" background:transparent; color:{VERMELHO};"
        f" font-weight:650; font-size:{tam}px;"
        f" border:1px solid {VERMELHO_LINHA}; border-radius:8px;"
        "  padding:10px 16px; text-align:center; }"
        f"QPushButton:hover {{ border-color:{VERMELHO};"
        f"  background:{AMBAR_FUNDO}; }}"
        f"QPushButton:disabled {{ color:{TEXTO_APAGADO}; border-color:{BORDA}; }}"
    )


def _estilo_btn(cor: str = "", cor_hover: str = "") -> str:
    """Compatibilidade: era o botão de ação preenchido, com a cor vinda de fora.

    As cores dos argumentos são IGNORADAS — a escala de verdes que elas
    escolhiam não existe mais. Cada chamador vai migrando para
    :func:`btn_solido` / :func:`btn_contorno`; enquanto não migra, cai no
    sólido, que é o que ele já era.
    """
    return btn_solido()


def _estilo_btn_sel(cor: str = "", cor_hover: str = "") -> str:
    """Botão SELETOR (checável, grupo exclusivo): contorno quando não escolhido,
    preenchido quando escolhido.

    As cores dos argumentos são IGNORADAS — ver :func:`_estilo_btn`.
    """
    return (
        "QPushButton {"
        f" background:transparent; color:{ACAO};"
        "  font-weight:650; font-size:13px;"
        f" border:1px solid {ACAO_LINHA}; border-radius:8px;"
        "  padding:9.5px 16px; text-align:center; }"
        f"QPushButton:hover {{ border-color:{ACAO}; background:{ACAO_FUNDO}; }}"
        "QPushButton:checked {"
        f" background:{ACAO}; color:{SOBRE_ACAO}; border:1px solid {ACAO};"
        "  padding:9.5px 16px; }"
        f"QPushButton:disabled {{ background:transparent; color:{TEXTO_APAGADO};"
        f"  border-color:{BORDA}; }}"
    )


def _estilo_btn_menu(cor: str = "", cor_hover: str = "") -> str:
    """Botão que abre MENU (``QToolButton``): mesma silhueta do seletor.

    Como o menu não é grupo exclusivo, não há ``:checked`` — quem acende o
    preenchimento é a propriedade dinâmica ``ativo`` (ver :func:`_marcar_ativo`).
    A seta some: o ▾ já vem no texto. Cores dos argumentos ignoradas.
    """
    return (
        "QToolButton {"
        f" background:transparent; color:{ACAO};"
        "  font-weight:650; font-size:13px;"
        f" border:1px solid {ACAO_LINHA}; border-radius:8px;"
        "  padding:9.5px 16px; text-align:center; }"
        f"QToolButton:hover {{ border-color:{ACAO}; background:{ACAO_FUNDO}; }}"
        'QToolButton[ativo="true"] {'
        f" background:{ACAO}; color:{SOBRE_ACAO}; border:1px solid {ACAO};"
        "  padding:9.5px 16px; }"
        f"QToolButton:disabled {{ background:transparent; color:{TEXTO_APAGADO};"
        f"  border-color:{BORDA}; }}"
        "QToolButton::menu-indicator { image:none; width:0; }"
    )


def _marcar_ativo(btn, ativo: bool) -> None:
    """Liga/desliga o preenchimento de um botão de menu. O Qt só reavalia os
    seletores por propriedade depois de repolir o widget."""
    btn.setProperty("ativo", "true" if ativo else "false")
    btn.style().unpolish(btn)
    btn.style().polish(btn)
