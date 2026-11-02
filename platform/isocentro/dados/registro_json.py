"""Registro versionado do paciente em JSON, salvo na pasta de origem.

Ao gerar a ficha técnica, tudo o que foi usado para montá-la (dados do
formulário, plano DICOM parseado e parâmetros de renderização) é gravado num
JSON na pasta do paciente, junto de um PNG da 1ª página (cortes + DVH). Cada
geração acrescenta uma **nova versão** ao histórico — assim, um novo
tratamento ou mudança de dose no futuro atualiza e versiona o mesmo arquivo,
mesmo depois de os arquivos DICOM (TC/RP/RS/RD) terem sido apagados.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import zipfile
from pathlib import Path

SCHEMA = "isocentro/registro-paciente"
SCHEMA_VERSAO = 1


def _gravar_json(json_path: Path, registro: dict) -> None:
    """Grava o registro de forma atômica: nunca deixa o JSON do paciente truncado.

    Este arquivo é o único registro que sobra depois de os DICOM serem apagados,
    então uma escrita interrompida (queda de energia, disco cheio) não pode
    destruir o histórico. Escreve num temporário na MESMA pasta — os.replace só
    é atômico dentro do mesmo volume — e troca de nome por cima do original.
    """
    # Varre temporários de um processo anterior que morreu no meio da escrita:
    # o os.replace nunca chegou a rodar, então são lixo — o JSON está íntegro.
    for velho in json_path.parent.glob(json_path.name + ".tmp*"):
        try:
            velho.unlink()
        except OSError:
            pass

    tmp = json_path.with_name(json_path.name + f".tmp{os.getpid()}")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(registro, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, json_path)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


# ── Serialização segura ──────────────────────────────────────────────────────

def _sanitizar(obj):
    """Converte recursivamente tipos não-JSON (numpy, sets, bytes) em nativos."""
    # numpy scalars/arrays expõem .item()/.tolist() sem importar numpy aqui.
    if isinstance(obj, dict):
        return {str(k): _sanitizar(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_sanitizar(v) for v in obj]
    if isinstance(obj, (str, bool, int, float)) or obj is None:
        return obj
    if isinstance(obj, (bytes, bytearray)):
        return None  # dados binários não entram no JSON
    tolist = getattr(obj, "tolist", None)
    if callable(tolist):
        try:
            return _sanitizar(tolist())
        except Exception:  # noqa: BLE001
            pass
    item = getattr(obj, "item", None)
    if callable(item):
        try:
            return _sanitizar(item())
        except Exception:  # noqa: BLE001
            pass
    return str(obj)


def _slug(texto: str) -> str:
    """Higieniza um texto para uso seguro em nome de arquivo (troca espaço por _)."""
    texto = (texto or "").strip()
    texto = re.sub(r"[^\w\-. ]+", "", texto, flags=re.UNICODE)
    texto = re.sub(r"\s+", "_", texto).strip("_.")
    return texto or "PACIENTE"


# Caracteres inválidos em nome de arquivo no Windows (mantém espaços).
_INVALIDOS_FS = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')


def slug_nome(dados: dict) -> str:
    """Nome do paciente para arquivo: MAIÚSCULAS, sem caracteres inválidos."""
    nome = (dados.get("pac_nome") or "PACIENTE").strip().upper()
    return _INVALIDOS_FS.sub("", nome).strip(" .") or "PACIENTE"


def nome_versao(dados: dict, tipo: str, versao, data: str, ext: str) -> str:
    """Nome padronizado de um arquivo de versão: ``TIPO_NOME_vN_DATA.ext``."""
    return f"{tipo}_{slug_nome(dados)}_v{versao}_{data}.{ext}"


def nome_base(dados: dict) -> str:
    """Nome-base do JSON mestre do paciente: ``FICHA_{NOME}_{REGISTRO}``.

    Inclui o nome (legível) e o registro (chave). O registro garante que
    gerações futuras reencontrem o mesmo arquivo mesmo se o nome mudar
    (ver ``_localizar_json``).
    """
    reg = _slug(dados.get("pac_registro") or "")
    nome = slug_nome(dados)
    return f"FICHA_{nome}_{reg}" if reg and reg != "PACIENTE" else f"FICHA_{nome}"


def _localizar_json(pasta: Path, dados: dict) -> Path:
    """Caminho do JSON mestre; se o nome mudou, reencontra pelo registro."""
    alvo = pasta / f"{nome_base(dados)}.json"
    if alvo.exists():
        return alvo
    reg = _slug(dados.get("pac_registro") or "")
    if reg and reg != "PACIENTE" and pasta.exists():
        sufixo = f"_{reg}.json"
        for p in pasta.iterdir():
            if p.is_file() and p.name.startswith("FICHA_") and p.name.endswith(sufixo):
                return p
    return alvo


# ── Empacotamento: JSON mestre + PNGs num único .zip por paciente ─────────────

def nome_zip(dados: dict) -> str:
    """Nome do .zip do paciente: ``ARQUIVOS_{NOME}_{REGISTRO}.zip``."""
    reg = _slug(dados.get("pac_registro") or "")
    nome = slug_nome(dados)
    return (f"ARQUIVOS_{nome}_{reg}.zip"
            if reg and reg != "PACIENTE" else f"ARQUIVOS_{nome}.zip")


def achar_zip(pasta: Path, dados: dict) -> Path | None:
    """Zip do paciente na pasta: nome esperado ou (fallback) pelo registro."""
    pasta = Path(pasta)
    alvo = pasta / nome_zip(dados)
    if alvo.exists():
        return alvo
    reg = _slug(dados.get("pac_registro") or "")
    if reg and reg != "PACIENTE" and pasta.exists():
        sufixo = f"_{reg}.zip"
        for p in pasta.iterdir():
            if (p.is_file() and p.name.startswith("ARQUIVOS_")
                    and p.name.endswith(sufixo)):
                return p
    return None


def registro_na_pasta(pasta) -> dict | None:
    """Registro de ficha ANTERIOR na pasta, SEM saber ainda nome/registro.

    Usado ao abrir uma pasta de DICOM cru: se ela já contém a ficha de um
    tratamento anterior (JSON mestre solto ou dentro do zip do paciente), devolve
    esse registro — assim a janela principal pode perguntar se o usuário quer
    reabrir a ficha ou elaborar uma nova, em vez de misturar as duas coisas.

    Diferente de ``carregar_registro_pasta``, que precisa do nome/registro para
    localizar o arquivo: aqui varre a pasta por QUALQUER ``FICHA_*.json`` /
    ``ARQUIVOS_*.zip``. Devolve o primeiro registro válido, ou ``None``.
    """
    pasta = Path(pasta)
    if not pasta.is_dir():
        return None
    for p in sorted(pasta.iterdir()):
        if p.is_file() and p.name.startswith("FICHA_") and p.suffix == ".json":
            try:
                reg = json.loads(p.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                continue
            if isinstance(reg, dict) and reg.get("versoes"):
                return reg
    for p in sorted(pasta.iterdir()):
        if p.is_file() and p.name.startswith("ARQUIVOS_") and p.suffix == ".zip":
            reg = ler_registro_do_zip(p)
            if isinstance(reg, dict) and reg.get("versoes"):
                return reg
    return None


def _json_interno(zf: zipfile.ZipFile) -> str | None:
    """Nome do membro JSON mestre dentro do zip (``FICHA_*.json``), ou None."""
    return next((n for n in zf.namelist()
                 if n.startswith("FICHA_") and n.endswith(".json")), None)


def ler_registro_do_zip(zip_path: Path) -> dict | None:
    """Lê o JSON mestre de dentro do zip do paciente, ou None se ausente/ilegível."""
    try:
        with zipfile.ZipFile(zip_path) as zf:
            nome = _json_interno(zf)
            if nome:
                return json.loads(zf.read(nome).decode("utf-8"))
    except Exception:  # noqa: BLE001
        return None
    return None


def carregar_registro_pasta(pasta, dados: dict) -> dict | None:
    """JSON mestre do paciente: solto se existir, senão de dentro do zip."""
    pasta = Path(pasta)
    jp = _localizar_json(pasta, dados)
    if jp.exists():
        try:
            reg = json.loads(jp.read_text(encoding="utf-8"))
            return reg if isinstance(reg, dict) else None
        except Exception:  # noqa: BLE001
            return None
    zp = achar_zip(pasta, dados)
    return ler_registro_do_zip(zp) if zp else None


def extrair_zip(pasta, dados: dict, destino) -> Path | None:
    """Extrai o conteúdo do zip do paciente para ``destino``; devolve o Path ou None."""
    zp = achar_zip(Path(pasta), dados)
    if not zp:
        return None
    try:
        with zipfile.ZipFile(zp) as zf:
            zf.extractall(destino)
    except Exception:  # noqa: BLE001
        return None
    return Path(destino)


# ── API principal ────────────────────────────────────────────────────────────

def salvar_versao(pasta, dados: dict, rp: dict | None,
                  render_meta: dict | None, imagem_png: bytes | None,
                  dvh_png: bytes | None = None,
                  pdf_path: str | None = None,
                  imagens: list | None = None,
                  dvhs: list | None = None,
                  modo: str | None = None,
                  planos: list | None = None,
                  agendamento: dict | None = None,
                  autor: dict | None = None,
                  drrs: list | None = None,
                  drrs_titulos: list | None = None,
                  rtplans: list | None = None) -> dict:
    """Acrescenta uma nova versão ao JSON do paciente, se houver mudança.

    Compara o conteúdo da ficha (``dados`` + ``plano_rp``) com a última versão:
    se for idêntico, NÃO cria uma nova versão e retorna ``nova=False``. Caso
    contrário grava a nova versão, com os PNGs de cortes e DVH e o ``pdf_path``.

    Retorna um dict com ``json_path``, ``versao`` e ``nova`` (bool).
    Levanta exceção se não conseguir escrever o JSON — o chamador deve tratar
    e, em caso de falha, NÃO apagar os arquivos DICOM.
    """
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    json_path = _localizar_json(pasta, dados)

    agora = datetime.datetime.now()
    data = agora.strftime("%d-%m-%Y")
    registro = _carregar_ou_novo(json_path, dados, agora, pasta=pasta)
    versoes = registro.setdefault("versoes", [])

    dados_s = _sanitizar(dados)
    rp_s = _sanitizar(rp or {})
    render_s = _sanitizar(render_meta or {})

    # Sem modificações (conteúdo + visualização) → não duplica a versão.
    if _identica_a_ultima(versoes, dados_s, rp_s, render_s):
        ultima = versoes[-1]
        # Só atualiza o caminho do PDF se um novo local foi informado.
        if pdf_path and ultima.get("pdf") != pdf_path:
            ultima["pdf"] = pdf_path
            _gravar_json(json_path, registro)
        return {"json_path": str(json_path),
                "versao": ultima.get("versao"),
                "nova": False, "arquivos": []}

    versao = len(versoes) + 1

    png_nome = None
    if imagem_png:
        png_nome = nome_versao(dados, "CORTES", versao, data, "png")
        (pasta / png_nome).write_bytes(imagem_png)
    dvh_nome = None
    if dvh_png:
        dvh_nome = nome_versao(dados, "DVH", versao, data, "png")
        (pasta / dvh_nome).write_bytes(dvh_png)

    # Multi-plano: um PNG de cortes por plano, no padrão TIPO_NOME_vN_DATA.
    imagens_nomes: list = []
    for k, img in enumerate(imagens or [], start=1):
        if not img:
            continue
        nm = nome_versao(dados, f"CORTES_p{k}", versao, data, "png")
        (pasta / nm).write_bytes(img)
        imagens_nomes.append(nm)

    # DVH por plano (paralelo a 'imagens'), para reusar quando não há mais DICOM.
    # Preserva o alinhamento por índice: plano sem DVH grava "" (placeholder).
    dvhs_nomes: list = []
    for k, img in enumerate(dvhs or [], start=1):
        if not img:
            dvhs_nomes.append("")
            continue
        nm = nome_versao(dados, f"DVH_p{k}", versao, data, "png")
        (pasta / nm).write_bytes(img)
        dvhs_nomes.append(nm)
    while dvhs_nomes and not dvhs_nomes[-1]:
        dvhs_nomes.pop()   # não guarda placeholders finais

    # DRRs de setup (600CD): um PNG por portal, guardados p/ reimprimir a ficha em
    # Histórico sem DICOM. Nomes e títulos são gravados ALINHADOS (pulam juntos os
    # PNGs vazios), para o título não sair no portal errado ao reabrir.
    drr_nomes: list = []
    drr_titulos: list = []
    _tit_in = drrs_titulos or []
    for k, png in enumerate(drrs or [], start=1):
        if not png:
            continue
        nm = nome_versao(dados, f"DRR_p{k}", versao, data, "png")
        (pasta / nm).write_bytes(png)
        drr_nomes.append(nm)
        drr_titulos.append(_tit_in[k - 1] if k - 1 < len(_tit_in) else "")

    # RTPLAN(s) originais (bytes crus do DICOM): arquivados p/ eventual tratamento
    # manual. Um por plano, na ordem dada; planos sem RP (ex.: reaberto) são pulados.
    rtplan_nomes: list = []
    for k, raw in enumerate(rtplans or [], start=1):
        if not raw:
            continue
        nm = nome_versao(dados, f"RTPLAN_p{k}", versao, data, "dcm")
        (pasta / nm).write_bytes(raw)
        rtplan_nomes.append(nm)

    entrada = {
        "versao": versao,
        "gerado_em": agora.isoformat(timespec="seconds"),
        "data": data,
        "imagem": png_nome or (imagens_nomes[0] if imagens_nomes else None),
        "imagens": imagens_nomes or None,
        "dvhs": dvhs_nomes or None,
        "modo": modo,
        "planos": _sanitizar(planos) if planos else None,
        "agendamento": _sanitizar(agendamento) if agendamento else None,
        "dvh": dvh_nome,
        "drrs": drr_nomes or None,
        "drrs_titulos": drr_titulos or None,
        "rtplans": rtplan_nomes or None,
        "pdf": pdf_path or None,
        "autor": _sanitizar(autor) if autor else None,   # trilha de auditoria
        "dados": dados_s,
        "plano_rp": rp_s,
        "render": render_s,
    }
    versoes.append(entrada)
    registro["atualizado_em"] = agora.isoformat(timespec="seconds")
    registro["paciente"] = _bloco_paciente(dados)

    _gravar_json(json_path, registro)
    # 'arquivos': todos os PNGs referenciados pelo registro que estejam soltos na
    # pasta — inclui versões anteriores (migra pacientes antigos por completo ao
    # arquivar), não só a recém-gerada.
    gerados = [str(pasta / nm) for nm in _nomes_imagens(registro)
               if (pasta / nm).is_file()]
    return {"json_path": str(json_path), "versao": versao, "nova": True,
            "arquivos": gerados}


def _nomes_imagens(registro: dict) -> list[str]:
    """Nomes (basename) de todos os arquivos auxiliares (PNGs de cortes/DVH/DRR e
    RTPLANs) referenciados no registro, sem repetição e preservando a ordem —
    usado para arquivar/limpar a pasta."""
    nomes: list[str] = []
    for v in registro.get("versoes", []) or []:
        for chave in ("imagem", "dvh", "drr_ap", "drr_lateral"):  # antigos p/ compat
            nm = v.get(chave)
            if nm:
                nomes.append(nm)
        for chave in ("imagens", "dvhs", "drrs", "rtplans"):
            for nm in (v.get(chave) or []):
                if nm:
                    nomes.append(nm)
    return list(dict.fromkeys(nomes))


def _identica_a_ultima(versoes: list, dados_s, rp_s, render_s) -> bool:
    """True se a última versão tem o mesmo conteúdo e visualização."""
    if not versoes:
        return False
    u = versoes[-1]
    return (u.get("dados") == dados_s and u.get("plano_rp") == rp_s
            and u.get("render") == render_s)


def prever_versao(pasta, dados: dict, rp: dict | None,
                  render_meta: dict | None) -> tuple[int, bool]:
    """Diz qual (versao, nova) uma geração produziria, sem gravar nada.

    Útil para sugerir o nome do arquivo (``..._v2_...``) antes de salvar.
    """
    reg = carregar_registro_pasta(pasta, dados) or {}
    versoes = reg.get("versoes", []) or []
    if _identica_a_ultima(versoes, _sanitizar(dados), _sanitizar(rp or {}),
                          _sanitizar(render_meta or {})):
        return versoes[-1].get("versao", len(versoes)), False
    return len(versoes) + 1, True


def _carregar_ou_novo(json_path: Path, dados: dict, agora, pasta: Path | None = None) -> dict:
    """Lê o JSON existente do paciente; se ausente/ilegível, cria um novo.

    Procura o histórico em duas fontes, nesta ordem: o JSON solto e, se ele não
    existir, o zip do paciente (``ARQUIVOS_*.zip``) — pois após arquivar os
    soltos são apagados e o zip passa a ser a única cópia.

    Um JSON solto ilegível é preservado antes de ser substituído — pode conter o
    histórico recuperável do paciente. Se a preservação falhar, propaga o erro
    em vez de sobrescrever: ``salvar_versao`` aborta e o chamador mantém os
    DICOM na pasta.
    """
    if json_path.exists():
        legivel = False
        try:
            reg = json.loads(json_path.read_text(encoding="utf-8"))
            legivel = isinstance(reg, dict)
        except Exception:  # noqa: BLE001
            legivel = False
        if legivel:
            reg.setdefault("versoes", [])
            return reg
        _preservar_ilegivel(json_path, agora)
    if pasta is not None:
        zp = achar_zip(pasta, dados)
        reg = ler_registro_do_zip(zp) if zp else None
        if isinstance(reg, dict):
            reg.setdefault("versoes", [])
            return reg
    return {
        "schema": SCHEMA,
        "schema_versao": SCHEMA_VERSAO,
        "paciente": _bloco_paciente(dados),
        "criado_em": agora.isoformat(timespec="seconds"),
        "versoes": [],
    }


def _preservar_ilegivel(json_path: Path, agora) -> None:
    """Renomeia um JSON ilegível para ``.corrompido-AAAAMMDD-HHMMSS`` antes de recriá-lo.

    O carimbo de tempo evita colidir com uma preservação anterior: no Windows
    os.rename levanta FileExistsError sobre um destino existente, e engolir esse
    erro deixaria a escrita seguinte destruir o arquivo que se queria preservar.
    """
    base = f"{json_path.name}.corrompido-{agora.strftime('%Y%m%d-%H%M%S')}"
    destino = json_path.with_name(base)
    n = 1
    while destino.exists():
        destino = json_path.with_name(f"{base}-{n}")
        n += 1
    os.rename(json_path, destino)


def _bloco_paciente(dados: dict) -> dict:
    return {
        "nome": dados.get("pac_nome", ""),
        "registro": dados.get("pac_registro", ""),
        "nascimento": dados.get("pac_nascimento", ""),
    }
