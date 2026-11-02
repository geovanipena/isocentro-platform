"""Aprendizado por observação: o que as fichas já geradas dizem sobre a nova.

Este módulo NÃO preenche campo nenhum. Numa ficha clínica, um preenchimento
automático silencioso é pior do que um campo vazio: o vazio o conferente vê, o
palpite errado ele assina. O que ele faz é **comparar** a ficha recém-elaborada
com o histórico do próprio serviço e apontar o que destoa — "dose/fração de
5,0 Gy, mas nas 12 fichas de VMAT no TBuniver ela ficou entre 1,8 e 3,0" —
deixando a decisão com quem confere.

A base é o índice central (``indice.buscar``), que sobrevive ao apagamento dos
DICOM e guarda exatamente o que interessa: máquina, técnica, energia, dose
total, nº de frações e dose/fração de cada ficha gerada. Cada ficha nova entra
no índice e, na seguinte, já faz parte do padrão — é nesse sentido que o
programa aprende.

Deliberadamente sem estatística sofisticada: com dezenas de casos, percentil é
teatro. A faixa é o [mínimo, máximo] observado, e o alerta cita quantas fichas
a sustentam, para o conferente pesar sozinho. Um balde com menos de
``MIN_AMOSTRA`` fichas não opina — prefere calar a inventar normalidade.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

_LOG = logging.getLogger(__name__)

# Abaixo disto o balde não tem o que dizer: com 2 ou 3 fichas, qualquer caso
# novo "foge do padrão" e o alerta vira ruído que se aprende a ignorar.
MIN_AMOSTRA = 6

# Folga sobre a faixa observada, para não alertar em arredondamento (uma
# dose/fração de 2,001 Gy contra um máximo histórico de 2,00).
FOLGA = 0.02


@dataclass(frozen=True)
class Alerta:
    """Um desvio do padrão histórico, já em linguagem de quem confere."""
    campo: str        # rótulo curto p/ a interface ("Dose/fração")
    mensagem: str     # frase completa, com a faixa e o tamanho da amostra
    base: int = 0     # nº de fichas que sustentam o alerta (0 = regra fixa)

    def __str__(self) -> str:  # pragma: no cover - conveniência de log
        return f"{self.campo}: {self.mensagem}"


# ── Coleta ───────────────────────────────────────────────────────────────────

def _linhas() -> list[dict]:
    """Fichas já geradas, uma por paciente (a última versão de cada).

    Uma versão por paciente, não todas: regerar a mesma ficha três vezes não
    torna aquele fracionamento três vezes mais normal.
    """
    try:
        from isocentro.dados import indice
        return indice.buscar("", limite=5000)
    except Exception:  # noqa: BLE001 - índice ausente/corrompido não quebra a ficha
        _LOG.exception("aprendizado: não consegui ler o índice de fichas")
        return []


def _num(valor: Any) -> Optional[float]:
    """Converte para float o que veio do índice, ou None se não for número."""
    if valor is None or valor == "":
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def _txt(valor: Any) -> str:
    """Texto normalizado para casar chaves (sem caixa nem espaços nas bordas)."""
    return str(valor or "").strip()


def _chave(maquina: Any, tecnica: Any) -> tuple[str, str]:
    return (_txt(maquina).lower(), _txt(tecnica).lower())


@dataclass
class _Balde:
    """As observações de um contexto (máquina+técnica, ou só máquina)."""
    n: int = 0
    dose_fracao: list[float] = field(default_factory=list)
    num_fracoes: list[float] = field(default_factory=list)
    dose_total: list[float] = field(default_factory=list)
    tecnicas: set[str] = field(default_factory=set)
    energias: set[str] = field(default_factory=set)

    def somar(self, linha: dict) -> None:
        self.n += 1
        for chave, alvo in (("dose_fracao", self.dose_fracao),
                            ("num_fracoes", self.num_fracoes),
                            ("dose_total", self.dose_total)):
            v = _num(linha.get(chave))
            if v is not None and v > 0:
                alvo.append(v)
        if _txt(linha.get("tecnica")):
            self.tecnicas.add(_txt(linha["tecnica"]).lower())
        if _txt(linha.get("energia")):
            self.energias.add(_txt(linha["energia"]).lower())


class Perfil:
    """O que o serviço costuma fazer, destilado das fichas já geradas."""

    def __init__(self, linhas: Iterable[dict]):
        self.total = 0
        self.por_maquina: dict[str, _Balde] = {}
        self.por_contexto: dict[tuple[str, str], _Balde] = {}
        for ln in linhas:
            self.total += 1
            maq = _txt(ln.get("maquina")).lower()
            ctx = _chave(ln.get("maquina"), ln.get("tecnica"))
            self.por_maquina.setdefault(maq, _Balde()).somar(ln)
            self.por_contexto.setdefault(ctx, _Balde()).somar(ln)

    def balde(self, maquina: Any, tecnica: Any) -> tuple[_Balde, str]:
        """Balde mais específico com amostra suficiente, e como descrevê-lo.

        Tenta primeiro máquina+técnica (o contexto que realmente importa) e cai
        para só a máquina quando aquele par ainda tem poucas fichas. Devolve um
        balde vazio quando nem isso basta — quem chama não alerta.
        """
        ctx = self.por_contexto.get(_chave(maquina, tecnica))
        if ctx is not None and ctx.n >= MIN_AMOSTRA:
            return ctx, f"{_txt(tecnica)} no {_txt(maquina)}"
        maq = self.por_maquina.get(_txt(maquina).lower())
        if maq is not None and maq.n >= MIN_AMOSTRA:
            return maq, f"{_txt(maquina)}"
        return _Balde(), ""


_CACHE: dict[str, Any] = {"chave": None, "perfil": None}


def _chave_cache() -> Any:
    """Assinatura do índice: reconstrói o perfil só quando ele muda."""
    try:
        from isocentro.dados import indice
        p = indice.REGISTRO_PATH
        return (p.stat().st_mtime_ns, p.stat().st_size) if p.exists() else None
    except Exception:  # noqa: BLE001
        return None


def perfil(forcar: bool = False) -> Perfil:
    """Perfil atual do serviço, relido só quando o índice mudou."""
    chave = _chave_cache()
    if forcar or _CACHE["perfil"] is None or _CACHE["chave"] != chave:
        _CACHE["perfil"] = Perfil(_linhas())
        _CACHE["chave"] = chave
    return _CACHE["perfil"]


# ── Avaliação ────────────────────────────────────────────────────────────────

def _fmt(v: float) -> str:
    """Número como o serviço escreve: vírgula decimal, sem zero à toa."""
    txt = f"{v:.2f}".rstrip("0").rstrip(".")
    return txt.replace(".", ",") or "0"


def _faixa(valores: list[float]) -> Optional[tuple[float, float]]:
    return (min(valores), max(valores)) if valores else None


def _alerta_faixa(campo: str, unidade: str, valor: Optional[float],
                  valores: list[float], contexto: str, n: int) -> Optional[Alerta]:
    """Alerta quando ``valor`` cai fora do que já se viu neste contexto."""
    faixa = _faixa(valores)
    if valor is None or faixa is None or len(valores) < MIN_AMOSTRA:
        return None
    lo, hi = faixa
    if lo - FOLGA <= valor <= hi + FOLGA:
        return None
    lado = "abaixo" if valor < lo else "acima"
    u = f" {unidade}" if unidade else ""
    return Alerta(
        campo,
        f"{_fmt(valor)}{u} — {lado} do usual. Nas {n} fichas de {contexto} "
        f"este valor ficou entre {_fmt(lo)} e {_fmt(hi)}{u}.",
        base=n,
    )


def avaliar(dados: dict, rp: Optional[dict] = None) -> list[Alerta]:
    """Compara a ficha em elaboração com o histórico e devolve os desvios.

    ``dados`` é o dicionário achatado do formulário (``PainelFormulario.coletar``)
    e ``rp`` o plano parseado, de onde saem técnica/energia quando o formulário
    não os carrega. Lista vazia significa "nada a estranhar" — que é o caso
    normal e, num serviço novo, também o caso de quem ainda não tem histórico.
    """
    rp = rp or {}
    maquina = dados.get("maquina") or rp.get("maquina") or ""
    tecnica = dados.get("tecnica") or rp.get("tecnica") or ""
    energia = dados.get("energia") or rp.get("energia") or ""
    d_frac = _num(dados.get("rx_dose_fracao"))
    n_frac = _num(dados.get("rx_fracoes"))
    d_tot = _num(dados.get("rx_dose_total"))

    alertas: list[Alerta] = []

    # Coerência aritmética: não depende de histórico nenhum e é o erro que mais
    # dói, porque a ficha sai internamente contraditória.
    if d_frac and n_frac and d_tot:
        esperado = d_frac * n_frac
        if abs(esperado - d_tot) > 0.05:
            alertas.append(Alerta(
                "Dose total",
                f"{_fmt(d_tot)} Gy não bate com {_fmt(d_frac)} Gy × "
                f"{int(n_frac)} frações = {_fmt(esperado)} Gy."))

    balde, contexto = perfil().balde(maquina, tecnica)
    if balde.n >= MIN_AMOSTRA:
        for campo, unid, valor, amostras in (
            ("Dose/fração", "Gy", d_frac, balde.dose_fracao),
            ("Nº de frações", "", n_frac, balde.num_fracoes),
            ("Dose total", "Gy", d_tot, balde.dose_total),
        ):
            a = _alerta_faixa(campo, unid, valor, amostras, contexto, balde.n)
            if a is not None:
                alertas.append(a)

    # Categóricos: só a máquina serve de contexto — perguntar se a técnica é
    # incomum dentro do balde da própria técnica não faria sentido.
    bmaq = perfil().por_maquina.get(_txt(maquina).lower())
    if bmaq is not None and bmaq.n >= MIN_AMOSTRA:
        if _txt(tecnica) and _txt(tecnica).lower() not in bmaq.tecnicas:
            alertas.append(Alerta(
                "Técnica",
                f"{_txt(tecnica)} nunca foi usada no {_txt(maquina)} nas "
                f"{bmaq.n} fichas anteriores.", base=bmaq.n))
        if _txt(energia) and _txt(energia).lower() not in bmaq.energias:
            alertas.append(Alerta(
                "Energia",
                f"{_txt(energia)} nunca apareceu no {_txt(maquina)} nas "
                f"{bmaq.n} fichas anteriores.", base=bmaq.n))
    return alertas
