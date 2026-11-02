"""Empacota, num único .zip por paciente, os arquivos gerados da ficha.

O .zip guarda o JSON mestre do registro e os PNGs de cortes/DVH de TODAS as
versões — NÃO inclui os DICOM nem os PDFs da Ficha e da Alta. É a única cópia
desses arquivos depois que os soltos são apagados da pasta; por isso a escrita
é atômica (temporário + ``os.replace``) e os membros antigos são preservados a
cada atualização.
"""
from __future__ import annotations

import os
import zipfile


def atualizar(destino_zip: str, arquivos: list[str]) -> str:
    """Cria/atualiza ``destino_zip`` preservando os membros já existentes e
    adicionando (ou substituindo, por nome) cada um de ``arquivos``.

    Caminhos ausentes são ignorados. Grava num temporário e só então substitui
    o destino — nunca deixa um zip corrompido. Devolve o caminho do zip.
    Levanta ``ValueError`` se não houver nada a adicionar e o zip ainda não
    existir.
    """
    novos = {os.path.basename(a): a for a in arquivos if a and os.path.isfile(a)}
    ja_existe = os.path.isfile(destino_zip)
    if not novos and not ja_existe:
        raise ValueError("Nenhum arquivo para empacotar.")

    esperados: set[str] = set(novos)
    tmp = destino_zip + ".tmp"
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
            # Copia membro a membro os que os novos NÃO substituem (por basename),
            # sem carregar o arquivo inteiro na memória — um membro por vez.
            if ja_existe:
                with zipfile.ZipFile(destino_zip) as zin:
                    for nome in zin.namelist():
                        if nome not in novos:
                            zout.writestr(nome, zin.read(nome))
                            esperados.add(nome)
            for nome, caminho in novos.items():
                zout.write(caminho, arcname=nome)
        # Integridade ANTES de substituir o destino: o zip é a única cópia depois
        # que os soltos são apagados, então um tmp corrompido/incompleto nunca
        # pode virar o destino final.
        with zipfile.ZipFile(tmp) as z:
            ruim = z.testzip()
            if ruim is not None:
                raise RuntimeError(f"membro corrompido no zip: {ruim}")
            faltando = [n for n in esperados if n not in z.namelist()]
            if faltando:
                raise RuntimeError(f"zip incompleto, faltam: {faltando}")
        os.replace(tmp, destino_zip)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    return destino_zip
