"""Cópia redundante do registro do paciente (o ``.zip``) para um diretório de
backup, para não depender de uma única cópia na pasta do paciente.

O destino é configurável pela variável de ambiente ``ISOCENTRO_BACKUP_DIR``
(ex.: um caminho de rede); sem ela, usa ``<pasta-do-app>/backup_registros``.
A cópia é best-effort e atômica: uma falha aqui NUNCA bloqueia a geração da
ficha (o zip original na pasta do paciente continua sendo a fonte primária).
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Optional
from isocentro.dados import ambiente


def dir_backup() -> Optional[Path]:
    """Diretório de backup configurado, ou o padrão ao lado do índice central."""
    env = ambiente.ler("ISOCENTRO_BACKUP_DIR")
    if env:
        return Path(env)
    try:
        from isocentro.dados import indice
        return indice._app_dir() / "backup_registros"
    except Exception:  # noqa: BLE001
        return None


def copiar(zip_path: str) -> Optional[str]:
    """Copia o ``.zip`` do paciente para o diretório de backup (best-effort).

    Grava num temporário e troca por cima (atômico), para o backup nunca ficar
    truncado. Devolve o caminho de destino, ou None se desabilitado/falhou.
    """
    origem = Path(zip_path)
    if not origem.is_file():
        return None
    dst_dir = dir_backup()
    if dst_dir is None:
        return None
    try:
        dst_dir.mkdir(parents=True, exist_ok=True)
        destino = dst_dir / origem.name
        tmp = destino.with_name(destino.name + ".tmp")
        shutil.copy2(origem, tmp)
        os.replace(tmp, destino)
        return str(destino)
    except Exception:  # noqa: BLE001
        try:
            tmp.unlink()  # type: ignore[possibly-undefined]
        except Exception:  # noqa: BLE001
            pass
        return None
