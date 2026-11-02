"""As partes do PPR vivo em PostgreSQL: cada módulo grava as suas (R-85).

Fonte: AD-3, AD-5 e AD-41 da espinha; CAP-10 e CAP-11 da spec Documentação.

Gravar passa pelo ``nucleo.gravar`` com o módulo DONO da parte: a tabela é
``<modulo>.ppr_parte``, e o gatilho do log recusa um módulo gravando na
tabela de outro. Ler é livre — a Documentação lê as cinco para montar.

Vigente é o registro que nenhum outro substitui no log (AD-5). "O último por
id" daria o mesmo enquanto toda correção apontar o anterior, mas deixaria de
dar no dia em que alguém gravasse sem ``substitui``: aí seriam dois textos
vigentes, e o "último" esconderia o conflito em vez de mostrá-lo.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping, Optional

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from isocentro.adaptadores.postgres import esquema as pg_esquema
from isocentro.adaptadores.postgres.porta import PortaPostgres, _motivo
from isocentro.dados import ambiente
from isocentro.dominio import ppr
from isocentro.nucleo.gravacao import GravacaoRecusada, Gravado, gravar

# A migração que criou as tabelas (``0004_ppr.sql``).
VERSAO_COM_PPR = 4

# A Fundação é o núcleo: grava em ``nucleo.*`` como módulo ``nucleo``.
ESQUEMA = {"fundacao": "nucleo", "qualidade": "qualidade", "plano": "plano",
           "seguranca": "seguranca", "documentacao": "documentacao"}

# O dado da GQ que diz que partes condicionais a clínica tem (hoje só a fonte
# radioativa, que traz o capítulo de rejeitos). É da GQ porque é o inventário
# de fontes dela que responde.
CONDICOES = "condicoes"


@dataclass(frozen=True)
class ParteGravada:
    id: str
    modulo: str
    texto: str
    documentos: list
    fonte: str


def _vigentes(tabela: str) -> sql.Composed:
    esquema, nome = tabela.split(".")
    return sql.SQL(
        "SELECT t.id::text, t.chave, {colunas}"
        "  FROM {tabela} t"
        " WHERE t.clinica = %s AND NOT EXISTS ("
        "   SELECT 1 FROM nucleo.log c"
        "    WHERE c.tabela = %s AND c.substitui = t.id::text)"
        " ORDER BY t.id").format(
            colunas=sql.SQL("t.texto, t.documentos, t.fonte"
                            if nome == "ppr_parte" else "t.conteudo, t.fonte"),
            tabela=sql.Identifier(esquema, nome))


class PortaDoPpr:
    """Leitura de todos os módulos; gravação em nome de ``quem``."""

    def __init__(self, conexao: psycopg.Connection, quem: str = ""):
        self._conexao = conexao
        self._porta = PortaPostgres(conexao)
        self._quem = quem

    # ── Leitura ─────────────────────────────────────────────────────────

    def partes(self, clinica: str) -> dict[str, ParteGravada]:
        """``{chave_gravada: ParteGravada}`` vigentes da clínica, de todos os donos."""
        achadas = {}
        for modulo, esquema in ESQUEMA.items():
            tabela = f"{esquema}.ppr_parte"
            for id_, chave, texto, docs, fonte in self._conexao.execute(
                    _vigentes(tabela), (clinica, tabela)).fetchall():
                achadas[chave] = ParteGravada(id_, modulo, texto, docs, fonte)
        return achadas

    def dados(self, clinica: str) -> dict[str, dict[str, tuple[str, Any]]]:
        """``{modulo: {chave: (id, conteudo)}}`` vigentes da clínica."""
        achados: dict = {}
        for modulo, esquema in ESQUEMA.items():
            tabela = f"{esquema}.ppr_dado"
            for id_, chave, conteudo, _fonte in self._conexao.execute(
                    _vigentes(tabela), (clinica, tabela)).fetchall():
                achados.setdefault(modulo, {})[chave] = (id_, conteudo)
        return achados

    def condicoes(self, clinica: str) -> Optional[frozenset]:
        """As condições gravadas pela GQ, ou ``None`` se ela ainda não disse."""
        gravado = self.dados(clinica).get("qualidade", {}).get(CONDICOES)
        return frozenset(gravado[1]) if gravado else None

    def fachadas(self, clinica: str) -> dict[str, ppr.Fachada]:
        """Uma fachada por módulo, todas sobre UMA leitura das partes.

        A tabela pergunta por parte; uma consulta por pergunta seriam ~50
        idas ao banco a cada troca de clínica.
        """
        chaves_por_modulo: dict[str, set] = {m: set() for m in ESQUEMA}
        for chave, parte in self.partes(clinica).items():
            chaves_por_modulo[parte.modulo].add(chave)

        def fachada(chaves):
            # A clínica entra na pergunta: a leitura é de UMA clínica, e
            # responder pela de outra diria que ela tem o que não tem.
            return lambda cl, parte: (cl == clinica
                                      and ppr.chave_gravada(parte) in chaves)
        return {m: fachada(c) for m, c in chaves_por_modulo.items()}

    # ── Gravação ────────────────────────────────────────────────────────

    def _gravar(self, modulo: str, tabela: str, dados: Mapping[str, Any],
                substitui: Optional[str]) -> Gravado:
        esquema = ESQUEMA[modulo]
        return gravar(self._porta, modulo=esquema,
                      tabela=f"{esquema}.{tabela}", dados=dados,
                      quem=self._quem, substitui=substitui)

    def gravar_parte(self, modulo: str, clinica: str, chave: str, texto: str,
                     documentos: list, fonte: str,
                     substitui: Optional[str] = None) -> Gravado:
        return self._gravar(modulo, "ppr_parte", {
            "clinica": clinica, "chave": chave, "texto": texto,
            "documentos": Jsonb(documentos), "fonte": fonte}, substitui)

    def gravar_dado(self, modulo: str, clinica: str, chave: str,
                    conteudo: Any, fonte: str,
                    substitui: Optional[str] = None) -> Gravado:
        return self._gravar(modulo, "ppr_dado", {
            "clinica": clinica, "chave": chave, "conteudo": Jsonb(conteudo),
            "fonte": fonte}, substitui)


def ler(conexao: psycopg.Connection, clinica: str) -> ppr.Leitura:
    situacao = pg_esquema.conferir(conexao)
    if (situacao.versao_do_banco or 0) < VERSAO_COM_PPR:
        return ppr.Leitura({}, None, {}, situacao.aviso or "")
    porta = PortaDoPpr(conexao)
    # Ler com versão MAIS NOVA que a do app é seguro (só SELECT); o aviso
    # vai junto, porque a gravação está parada até a atualização.
    return ppr.Leitura(porta.partes(clinica), porta.condicoes(clinica),
                   porta.fachadas(clinica), situacao.aviso or "")


def ler_do_ambiente(clinica: str) -> ppr.Leitura:
    """A leitura pela conexão da estação (``ISOCENTRO_PG_APP``).

    Provisória até a R-19, que dá a cada pessoa o login dela no banco; até
    lá a estação lê com uma credencial só, como a concentradora faz com a
    ``ISOCENTRO_PG_CONCENTRADORA``. Conexão curta, aberta e fechada a cada
    leitura: a aba fica aberta por horas, e uma conexão parada todo esse
    tempo cai sem avisar.
    """
    conninfo = ambiente.ler("ISOCENTRO_PG_APP").strip()
    if not conninfo:
        return ppr.Leitura({}, None, {},
                       "Banco central não configurado nesta estação "
                       "(ISOCENTRO_PG_APP): nada a ler.")
    try:
        # O tempo-limite curto é o da troca de clínica: sem ele, banco fora
        # deixava a tela congelada pelo padrão do sistema (minutos).
        with psycopg.connect(conninfo, autocommit=True,
                             connect_timeout=3) as c:
            c.execute("SET ROLE isocentro_app")
            return ler(c, clinica)
    except psycopg.Error as erro:
        return ppr.Leitura({}, None, {},
                       f"Banco central inacessível: {_motivo(erro)}")


EDICAO = "edição no ISOCENTRO"


def fonte_da_edicao(anterior: Optional[ParteGravada]) -> str:
    """A fonte de um texto editado na tela, sem perder a citação de origem.

    Quem editou e quando estão na linha de log; a fonte diz de onde o texto
    partiu. Sem o "sobre", a CAP-11 (cada parte cita a origem) se perderia
    na primeira vírgula corrigida; repetido a cada edição, a fonte viraria
    uma cadeia de "sobre edição sobre edição".
    """
    if anterior is None:
        return EDICAO
    if anterior.fonte.startswith(EDICAO):
        return anterior.fonte
    return f"{EDICAO} sobre {anterior.fonte}"


def gravar_texto(porta: PortaDoPpr, clinica: str, modulo: str, chave: str,
                 texto: str, anterior: Optional[ParteGravada]) -> Gravado:
    """O texto novo de uma parte, corrigindo a vigente (AD-5).

    Os documentos de origem seguem os da vigente: a tela edita o texto, e
    perder os PDFs embutidos por ter corrigido uma palavra seria perder o
    anexo inteiro no papel.
    """
    return porta.gravar_parte(
        modulo, clinica, chave, texto,
        anterior.documentos if anterior else [], fonte_da_edicao(anterior),
        substitui=anterior.id if anterior else None)


def gravar_texto_do_ambiente(quem: str, clinica: str, modulo: str,
                             chave: str, texto: str,
                             anterior: Optional[ParteGravada]) -> Gravado:
    """``gravar_texto`` pela conexão da estação; levanta com o motivo."""
    conninfo = ambiente.ler("ISOCENTRO_PG_APP").strip()
    if not conninfo:
        raise GravacaoRecusada("banco central não configurado nesta estação "
                               "(ISOCENTRO_PG_APP)")
    try:
        with psycopg.connect(conninfo, autocommit=True,
                             connect_timeout=3) as c:
            c.execute("SET ROLE isocentro_app")
            situacao = pg_esquema.conferir(c)
            if situacao.somente_leitura:
                raise GravacaoRecusada(situacao.aviso)
            return gravar_texto(PortaDoPpr(c, quem), clinica, modulo, chave,
                                texto, anterior)
    except psycopg.Error as erro:
        raise GravacaoRecusada(f"banco central inacessível: {_motivo(erro)}") \
            from erro


def igual(a: Any, b: Any) -> bool:
    """Mesmo conteúdo JSON, sem depender da ordem das chaves."""
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
