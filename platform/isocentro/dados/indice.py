"""Registro central de fichas (JSON), para busca global na tela de Histórico.

Os registros por paciente vivem em ``ficha_{registro}.json`` espalhados nas
pastas de origem (a fonte da verdade). Este módulo mantém, na **pasta do app**,
um único ``registro_fichas.json`` derivado desses JSON — atualizado a cada
geração de ficha — que lista todas as fichas com seus metadados e os
**endereços dos arquivos** (JSON, imagem de cortes, DVH e PDF).

É sempre reconstruível a partir dos JSON (ver ``reconstruir``); nunca é a fonte
primária, então falhas de escrita aqui não devem bloquear o salvamento.
"""

from __future__ import annotations

import json
import logging
import os
import time
from contextlib import contextmanager
from pathlib import Path

from isocentro import raiz
from isocentro.dados.nomes import como_nome_proprio

_LOG = logging.getLogger(__name__)


def _app_dir() -> Path:
    """Pasta do app: ao lado do executável empacotado, ou a raiz do projeto.

    Era "a pasta deste módulo", e isso valia enquanto o módulo estava na raiz.
    O ``registro_fichas.json`` é lido por TODAS as estações — nascer um nível
    abaixo seria índice vazio sem nenhuma mensagem. Ver ``isocentro.raiz``.
    """
    return raiz.pasta_do_app()


REGISTRO_PATH = _app_dir() / "registro_fichas.json"

# Campos pesquisáveis por opção de filtro da tela de Histórico.
CAMPOS_BUSCA = {
    "tudo":     ("nome", "registro", "medico", "maquina"),
    "nome":     ("nome",),
    "registro": ("registro",),
    "medico":   ("medico",),
    "maquina":  ("maquina",),
}


def _carregar() -> dict:
    if REGISTRO_PATH.exists():
        try:
            reg = json.loads(REGISTRO_PATH.read_text(encoding="utf-8"))
            if isinstance(reg, dict):
                reg.setdefault("fichas", [])
                return reg
        except Exception:  # noqa: BLE001
            pass
    return {"schema": "isocentro/registro-fichas", "fichas": []}


def _salvar(reg: dict) -> None:
    """Grava o índice de forma ATÔMICA: temporário na mesma pasta + ``os.replace``.

    Escrever direto no arquivo final deixava uma janela em que ele estava pela
    metade — app fechado, máquina desligada ou a rede piscando no meio da
    escrita truncavam o índice, e ``_carregar`` cai em silêncio para índice
    VAZIO: a tela de Histórico abre sem ficha nenhuma, sem erro. ``os.replace``
    é atômico, então o arquivo final ou é o velho inteiro ou o novo inteiro.
    """
    REGISTRO_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = REGISTRO_PATH.with_name(f"{REGISTRO_PATH.name}.{os.getpid()}.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(reg, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())   # o replace só vale se o conteúdo já está no disco
        os.replace(tmp, REGISTRO_PATH)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# Espera máxima pelo lock. Uma seção crítica dura milissegundos; a espera é
# longa porque desistir dela é a única porta que ainda perde entrada, e fila
# legítima (vários gravadores + o fsync de cada gravação em disco de rede) não é
# motivo para isso.
_LOCK_ESPERA_S = 30.0


def _lock_path() -> Path:
    return REGISTRO_PATH.with_name(REGISTRO_PATH.name + ".lock")


def _travar_fd(fd: int) -> bool:
    """Tenta travar ``fd`` sem bloquear. False se outro já o tem."""
    try:
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def _destravar_fd(fd: int) -> None:
    try:
        if os.name == "nt":
            import msvcrt
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_UN)
    except OSError:
        pass


@contextmanager
def _travado(espera: float | None = None):
    """Exclusão mútua entre processos para o índice central."""
    with travar_arquivo(_lock_path(), espera):
        yield


@contextmanager
def travar_arquivo(alvo, espera: float | None = None):
    """Exclusão mútua ENTRE PROCESSOS para o ciclo ler→alterar→gravar.

    Sem isso, dois físicos gerando ficha ao mesmo tempo liam o mesmo índice e
    gravavam por cima um do outro: o último a gravar apagava a ficha do primeiro
    (a escrita atômica sozinha não resolve — cada um grava um arquivo íntegro,
    só que sem o trabalho do outro).

    O lock é do SISTEMA OPERACIONAL sobre um arquivo que nunca é apagado
    (``msvcrt.locking``/``flock``), não a existência do arquivo. Fazer o lock
    "criar e apagar" parece mais simples e não funciona no Windows: apagar deixa
    o arquivo em *delete pending*, e quem tenta criá-lo nesse instante recebe
    ``PermissionError`` em vez de "já existe" — cai no ramo de erro e grava sem
    exclusão. Num teste de 8 gravadores × 200 fichas isso perdia 32 delas.
    Travar o descritor também dispensa heurística de lock abandonado: se o
    processo morre, o próprio SO solta.

    Não obter o lock NÃO impede a gravação: este índice é derivado e sempre
    reconstruível (ver ``reconstruir``), então travar o salvamento da ficha por
    causa dele seria pior que a disputa que ele evita.
    """
    # Lido na CHAMADA, não no default: valor de default congela na definição, e
    # ajustar a constante depois (teste, configuração) não teria efeito nenhum.
    espera = _LOCK_ESPERA_S if espera is None else espera
    alvo = Path(alvo)
    fd = None
    try:
        alvo.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(alvo), os.O_CREAT | os.O_RDWR)
    except OSError:
        fd = None        # pasta somente-leitura: segue sem lock
    travado = False
    if fd is not None:
        inicio = time.monotonic()
        while not (travado := _travar_fd(fd)):
            if time.monotonic() - inicio >= espera:
                _LOG.warning("%s ocupado há %.0f s — gravando sem lock.",
                             alvo.name, espera)
                break
            time.sleep(0.02)
    try:
        yield
    finally:
        if fd is not None:
            if travado:
                _destravar_fd(fd)
            try:
                os.close(fd)
            except OSError:
                pass


@contextmanager
def travar_ou_desistir(alvo):
    """Como :func:`travar_arquivo`, mas DESISTE em vez de seguir sem a trava.

    A diferença não é de gosto. O ``travar_arquivo`` espera e, vencido o prazo,
    grava assim mesmo — certo para o índice, que é derivado e sempre
    reconstruível. Para a varredura da exportação é o contrário: duas rodadas
    ao mesmo tempo (a Tarefa Agendada da concentradora e o relógio de um app
    aberto na mesma máquina) perguntariam a mesma coisa ao banco e a segunda
    baixaria o que a primeira está baixando. A trava do ``gatilho_registro``
    evita a CORRUPÇÃO do arquivo; o desperdício, só esta.

    Devolve ``True`` se a trava é sua e ``False`` se já é de outro — uma
    tentativa só, sem espera: quem chega junto volta na próxima batida, e
    esperar aqui seria segurar a rodada agendada para fazer o trabalho em
    dobro.

    **Pasta somente-leitura devolve ``True``**, com aviso no histórico. Sem
    poder criar o arquivo não há como saber de quem é a vez, e recusar-se a
    varrer por causa disso trocaria uma disputa rara por uma automação que não
    roda nunca — que é o modo de falhar que este projeto inteiro evita.
    """
    alvo = Path(alvo)
    fd = None
    try:
        alvo.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(alvo), os.O_CREAT | os.O_RDWR)
    except OSError:
        _LOG.warning("Não deu para criar a trava em %s — seguindo sem ela.",
                     alvo)
        yield True
        return
    travado = _travar_fd(fd)
    try:
        yield travado
    finally:
        if travado:
            _destravar_fd(fd)
        try:
            os.close(fd)
        except OSError:
            pass


def _linha_de_versao(registro: str, entrada: dict, json_path: Path) -> dict:
    """Extrai metadados + endereços de uma entrada de versão do JSON do paciente."""
    d = entrada.get("dados", {}) or {}
    rp = entrada.get("plano_rp", {}) or {}

    def _caminho(chave):
        nome = entrada.get(chave)
        if not nome:
            # Ficha de VÁRIOS planos guarda uma imagem por plano (``imagens``/
            # ``dvhs``) e o campo único pode vir vazio — o ``dvh`` vinha sempre:
            # a Ficha Virtual mostrava os cortes (o ``imagem`` já caía no 1º
            # plano) e "sem DVH" ao lado, numa ficha que tem DVH impresso
            # (07/10/2026). O primeiro da lista é o do mesmo plano dos cortes.
            lista = entrada.get(chave + "s") or []
            nome = lista[0] if lista else None
        return str(json_path.with_name(nome)) if nome else None

    return {
        "registro":    registro,
        "versao":      entrada.get("versao"),
        "nome":        d.get("pac_nome", ""),
        "nascimento":  d.get("pac_nascimento", ""),
        "data":        entrada.get("data", ""),
        "gerado_em":   entrada.get("gerado_em", ""),
        "dose_total":  d.get("rx_dose_total"),
        "num_fracoes": d.get("rx_fracoes"),
        "dose_fracao": d.get("rx_dose_fracao"),
        "maquina":     d.get("maquina") or rp.get("maquina", ""),
        "medico":      d.get("eq_medico") or rp.get("medico", ""),
        "fisico":      d.get("eq_fisico", ""),
        "tecnica":     rp.get("tecnica", ""),
        "energia":     rp.get("energia", ""),
        "json_path":   str(json_path),
        "imagem_path": _caminho("imagem"),
        "dvh_path":    _caminho("dvh"),
        "pdf_path":    entrada.get("pdf") or None,
    }


def sincronizar_arquivo(json_path) -> int:
    """Lê um ``ficha_{registro}.json`` e substitui suas entradas no registro.

    Devolve o número de versões indexadas.
    """
    json_path = Path(json_path)
    dados = json.loads(json_path.read_text(encoding="utf-8"))
    registro = (dados.get("paciente", {}) or {}).get("registro", "") or ""
    versoes = dados.get("versoes", []) or []

    with _travado():
        reg = _carregar()
        # Remove entradas antigas deste paciente e reinsere todas as versões.
        reg["fichas"] = [f for f in reg["fichas"] if f.get("registro") != registro]
        for entrada in versoes:
            reg["fichas"].append(_linha_de_versao(registro, entrada, json_path))
        _salvar(reg)
    return len(versoes)


def _com_nomes_canonicos(linha: dict) -> dict:
    """A linha do índice pronta para a tela: nome e médico em grafia única.

    Formatado na LEITURA, não na indexação, porque o ``registro_fichas.json``
    já existe nas estações com o que cada ficha gravou na época — "GEUCIMAR
    MARIA NUNES COSTA" ao lado de "Lie Yamanaka" na mesma lista. Formatar só ao
    indexar arrumaria as fichas de amanhã e deixaria a mistura de ontem na tela,
    que é justamente onde ela aparece.

    Cópia rasa: quem chama recebe a linha para exibir, e o dicionário do arquivo
    não deve mudar por causa disso.
    """
    fora = dict(linha)
    for chave in ("nome", "medico", "fisico"):
        if fora.get(chave):
            fora[chave] = como_nome_proprio(fora[chave])
    return fora


def buscar(termo: str = "", campo: str = "tudo", limite: int = 500) -> list[dict]:
    """Última versão de cada paciente que casa com ``termo`` no ``campo`` dado."""
    termo = (termo or "").strip().lower()
    campos = CAMPOS_BUSCA.get(campo, CAMPOS_BUSCA["tudo"])
    reg = _carregar()

    ultimas: dict[str, dict] = {}
    for f in reg["fichas"]:
        r = f.get("registro", "")
        if r not in ultimas or (f.get("versao") or 0) > (ultimas[r].get("versao") or 0):
            ultimas[r] = f
    linhas = list(ultimas.values())

    if termo:
        linhas = [f for f in linhas
                  if any(termo in str(f.get(c, "") or "").lower() for c in campos)]
    linhas.sort(key=lambda f: f.get("gerado_em", "") or "", reverse=True)
    return [_com_nomes_canonicos(f) for f in linhas[:limite]]


def resumo_por_registro(registros=None) -> dict[str, dict]:
    """Por registro: quantas versões existem e a linha da MAIS RECENTE.

    ``{"12345": {"versoes": 3, "ultima": {...}}}``; ``registros=None`` traz
    todos. Uma leitura só do índice para um punhado de pacientes — a
    alternativa (:func:`listar_versoes` paciente a paciente) relê o arquivo
    inteiro a cada nome, e a lista de fichas recentes da Fichinha pede dez de
    uma vez, toda vez que a tela abre.
    """
    alvo = None if registros is None else {str(r) for r in registros if r}
    saida: dict[str, dict] = {}
    for f in _carregar()["fichas"]:
        r = f.get("registro", "")
        if alvo is not None and r not in alvo:
            continue
        atual = saida.get(r)
        if atual is None:
            saida[r] = {"versoes": 1, "ultima": f}
            continue
        atual["versoes"] += 1
        if (f.get("versao") or 0) > (atual["ultima"].get("versao") or 0):
            atual["ultima"] = f
    for item in saida.values():
        item["ultima"] = _com_nomes_canonicos(item["ultima"])
    return saida


def limpar() -> int:
    """Esvazia o índice central do Histórico e devolve quantas entradas havia.

    Só apaga o índice (``registro_fichas.json``); os JSON/.zip dos pacientes
    ficam na pasta e podem ser trazidos de volta por :func:`reconstruir`.
    """
    with _travado():
        reg = _carregar()
        n = len(reg.get("fichas") or [])
        _salvar({"schema": "isocentro/registro-fichas", "fichas": []})
    return n


def listar_versoes(registro: str) -> list[dict]:
    """Todas as versões de um paciente, da mais recente para a mais antiga."""
    reg = _carregar()
    vs = [f for f in reg["fichas"] if f.get("registro") == registro]
    vs.sort(key=lambda f: f.get("versao") or 0, reverse=True)
    return vs


def sincronizar_zip(zip_path) -> int:
    """Reindexa um paciente a partir do JSON mestre dentro do ``ARQUIVOS_*.zip``.

    O endereço registrado (``json_path``) aponta para a posição do JSON solto na
    pasta (mesmo que só exista dentro do zip) — assim a reabertura acha a pasta
    e lê o histórico do zip. Devolve o número de versões indexadas.
    """
    import zipfile
    zip_path = Path(zip_path)
    with zipfile.ZipFile(zip_path) as zf:
        jn = next((n for n in zf.namelist()
                   if n.startswith("FICHA_") and n.endswith(".json")), None)
        if not jn:
            return 0
        dados = json.loads(zf.read(jn).decode("utf-8"))
    registro = (dados.get("paciente", {}) or {}).get("registro", "") or ""
    versoes = dados.get("versoes", []) or []
    json_virtual = zip_path.with_name(jn)   # pasta do zip + nome do JSON interno

    with _travado():
        reg = _carregar()
        reg["fichas"] = [f for f in reg["fichas"] if f.get("registro") != registro]
        for entrada in versoes:
            reg["fichas"].append(_linha_de_versao(registro, entrada, json_virtual))
        _salvar(reg)
    return len(versoes)


def _registro_de_json(jp) -> str:
    try:
        d = json.loads(Path(jp).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return ""
    return (d.get("paciente", {}) or {}).get("registro", "") or ""


def _registro_de_zip(zp) -> str:
    from isocentro.dados import registro_json
    d = registro_json.ler_registro_do_zip(Path(zp)) or {}
    return (d.get("paciente", {}) or {}).get("registro", "") or ""


def _sob_raiz(caminho, raiz_res: Path) -> bool:
    """True se ``caminho`` está dentro de ``raiz_res`` (mesmo volume)."""
    if not caminho:
        return False
    try:
        Path(caminho).resolve().relative_to(raiz_res)
        return True
    except (ValueError, OSError):
        return False


def reconstruir(raiz, remover_ausentes: bool = True) -> int:
    """Varre ``raiz`` por ``FICHA_*.json`` e ``ARQUIVOS_*.zip`` e reindexa tudo.

    Devolve o número de fontes indexadas. Os zips são varridos depois dos JSON
    soltos: quando ambos existem para o mesmo paciente, o zip (fonte final após
    o arquivamento) prevalece. Se ``remover_ausentes``, também REMOVE do índice
    as entradas cujo arquivo está sob ``raiz`` mas não foi mais encontrado
    (pasta apagada/movida); entradas fora de ``raiz`` são preservadas.
    """
    raiz_res = Path(raiz).resolve()
    encontrados: set[str] = set()
    n = 0
    for jp in Path(raiz).rglob("FICHA_*.json"):
        try:
            sincronizar_arquivo(jp)
            n += 1
            encontrados.add(_registro_de_json(jp))
        except Exception:  # noqa: BLE001
            continue
    for zp in Path(raiz).rglob("ARQUIVOS_*.zip"):
        try:
            if sincronizar_zip(zp):
                n += 1
                encontrados.add(_registro_de_zip(zp))
        except Exception:  # noqa: BLE001
            continue
    if remover_ausentes:
        with _travado():
            reg = _carregar()
            antes = len(reg["fichas"])
            reg["fichas"] = [
                f for f in reg["fichas"]
                if f.get("registro") in encontrados
                or not _sob_raiz(f.get("json_path"), raiz_res)
            ]
            if len(reg["fichas"]) != antes:
                _salvar(reg)
    return n
