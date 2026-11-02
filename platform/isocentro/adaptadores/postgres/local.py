"""Sobe o PostgreSQL LOCAL quando o app abre (pedido de 29/10/2026).

O banco de desenvolvimento não sobe sozinho com o Windows (docs/AMBIENTE.md,
"Não sobe sozinho"): depois de reiniciar a máquina, a aba PPR abria dizendo
"banco central inacessível" até alguém lembrar do ``pg_ctl``. Aqui o app
faz isso ao abrir — e SÓ quando a ``ISOCENTRO_PG_APP`` aponta para esta
máquina e o servidor local está instalado. Na clínica, com o banco central
em outro servidor, nada aqui roda: subir o banco central não é papel de uma
estação.

Sem ``psycopg``: o executável ainda não o leva (NOTAS, R-18), e o app não
pode morrer ao abrir por causa disto. A pergunta "está no ar?" é uma porta
TCP aberta, com tempo-limite curto — no Windows, conectar numa porta sem
servidor pode ficar pendurado (ARMADILHAS, 29/10/2026).
"""
from __future__ import annotations

import os
import re
import socket
import subprocess
from pathlib import Path

from isocentro.dados import ambiente

_LOCAIS = {"localhost", "127.0.0.1", "::1"}


def _pasta_padrao(*partes: str) -> Path:
    return Path(os.environ.get("LOCALAPPDATA", ""), *partes)


def _campos(conninfo: str) -> dict:
    """``chave=valor`` da conninfo, sem psycopg. URI (``postgresql://``) não
    é lida: devolve vazio, e então nada sobe — melhor que adivinhar."""
    return dict(re.findall(r"(\w+)\s*=\s*'?([^'\s]+)'?", conninfo))


def no_ar(porta: int, tempo: float = 0.5) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", porta), timeout=tempo):
            return True
    except OSError:
        return False


def subir_se_preciso() -> str:
    """Dispara o ``pg_ctl start`` se for o caso; devolve o que fez (para o log).

    Não espera o servidor: o ``pg_ctl`` vai destacado, e a aba PPR, aberta
    depois, já o encontra no ar (a recuperação depois de uma queda leva uns
    segundos). Ele continua no ar quando o app fecha — é o banco da estação,
    não da sessão.
    """
    campos = _campos(ambiente.ler("ISOCENTRO_PG_APP"))
    if campos.get("host", "") not in _LOCAIS:
        return ""
    porta = int(campos.get("port", "5432"))
    if no_ar(porta):
        return f"PostgreSQL local já no ar (porta {porta})"
    pg_ctl = Path(ambiente.ler("ISOCENTRO_PG_LOCAL_BIN")
                  or _pasta_padrao("Programs", "pgsql-18", "bin")) / "pg_ctl.exe"
    dados = Path(ambiente.ler("ISOCENTRO_PG_LOCAL_DADOS")
                 or _pasta_padrao("isocentro-pg", "dev"))
    if not pg_ctl.is_file() or not (dados / "PG_VERSION").is_file():
        return (f"PostgreSQL local fora (porta {porta}) e não instalado em "
                f"{pg_ctl.parent} / {dados}: nada a subir")
    flags = 0
    if os.name == "nt":
        # Console PRÓPRIO e invisível, e não DETACHED_PROCESS: destacado, o
        # postgres ficou ao alcance do Ctrl+C de outro console e caiu
        # (0xC000013A, 29/10/2026, no meio da suíte). O CREATE_NO_WINDOW é
        # ignorado junto com o DETACHED, por isso os dois não andam juntos.
        flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(
        [str(pg_ctl), "-D", str(dados), "-l", str(dados.with_suffix(".log")),
         "start"],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, creationflags=flags, close_fds=True)
    return f"PostgreSQL local fora (porta {porta}): subindo pelo {pg_ctl}"
