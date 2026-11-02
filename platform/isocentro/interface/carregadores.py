"""As duas cargas pesadas que rodam fora da interface: o caso e o corpo 3D.

Separadas de ``gui.py`` em 27/08/2026. São ``QThread`` porque ler um paciente
inteiro (RP, RS, RD, a série de TC) leva segundos e travaria a tela.

O nome do logger é ``__name__``, e ``carregadores`` está em ``LOGGERS_APP``
(``dados/log_app.py``) — a lista de quem chega ao histórico compartilhado. Aqui isso
importa mais que na média: as três chamadas abaixo registram justamente a
falha de carregar o caso do paciente, que é o que o admin precisa ver quando
uma estação não abre um paciente.
"""
from __future__ import annotations

import contextlib
import logging
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from isocentro.dicom import ct_series
from isocentro.dicom import dicom_rt
from isocentro.dicom import dose3d
from isocentro.adaptadores.dicom import leitura
from isocentro.dados import equipe

_LOG = logging.getLogger(__name__)


def _norm_registro(valor) -> str:
    """Normaliza um registro/PatientID para comparação (espaços e caixa)."""
    return str(valor or "").strip().upper()


def _converter_contornos(rs) -> None:
    """Força a conversão do ``ContourData`` de todas as estruturas de ``rs``.

    Só o ACESSO importa: o pydicom troca o elemento cru pelo convertido dentro
    do próprio dataset, e quem ler depois recebe o valor pronto. Falha aqui não
    é falha de carga — a conversão acontece de novo, mais tarde, onde já
    acontecia.
    """
    try:
        for roi in getattr(rs, "ROIContourSequence", None) or []:
            for contorno in getattr(roi, "ContourSequence", None) or []:
                contorno.ContourData  # noqa: B018 — o acesso É a conversão
    except Exception:  # noqa: BLE001
        _LOG.debug("Conversão antecipada dos contornos falhou", exc_info=True)


def _rd_com_fallback(com_pixels, so_cabecalho):
    """RT Dose com os pixels; se eles não abrirem, o dataset só com o cabeçalho.

    ``com_pixels`` e ``so_cabecalho`` são callables que carregam o RD com e sem
    os pixels — um lê do disco (arquivo solto), o outro dos bytes já
    descompactados (membro de .zip/.rar), e esta função vale igual para os dois.

    O gatilho real é falta de memória: o pydicom lê com ``force=True`` e não
    levanta nem em arquivo truncado ou corrompido (a falha só aparece depois, no
    ``pixel_array``). Quem chega aqui é o MemoryError de alocar a grade — num
    paciente de 4 planos são 4 doses de centenas de MB — ou um erro de acesso ao
    arquivo.

    Nesse caso vale guardar o RD sem os pixels: ``agrupar_planos`` liga a dose ao
    plano por tag de cabeçalho (``ReferencedRTPlanSequence``), então o plano
    mantém a sua dose associada e só o DVH/isodose ficam sem dado. Descartar o RD
    faria o plano aparecer sem dose nenhuma e a ficha soma somar um plano a
    menos, em silêncio.

    O ``so_cabecalho`` precisa do cabeçalho COMPLETO, não o da triagem:
    ``cabecalhos_arquivo`` traz só Modality/PatientID/PatientName, e sem a
    referência ao plano o RD não seria ligado a ninguém.
    """
    try:
        return com_pixels()
    except Exception:  # noqa: BLE001
        _LOG.exception("Pixels do RT Dose não puderam ser carregados — "
                       "mantendo só o cabeçalho")
        return so_cabecalho()


# ── Workers (carregamento em background) ────────────────────────────────────


def pacientes_na_pasta(pasta) -> dict:
    """De quem são os DICOM desta pasta. ``{registro: (nome, quantos)}``.

    Existe porque a varredura é RECURSIVA e uma pasta-pai pode conter vários
    pacientes — o ``_excluir_arquivos_pasta`` já sabia disso na hora de APAGAR
    (filtra por PatientID para não levar junto o DICOM de quem nunca foi
    aberto), e a CARGA não sabia. O resultado, medido em 31/08/2026 na pasta
    de teste do Elekta: uma ficha em nome de uma paciente com planos de outras
    duas, e nenhum aviso na tela. Ficha é o que vai grampeado para a sala.

    Tria pelo CABEÇALHO (uns KB por arquivo): 0,1 s numa pasta de paciente e
    3,1 s numa com 1.462 arquivos e sete pacientes. Ler o arquivo inteiro só
    para saber de quem ele é custaria centenas de MB por RT Dose.
    """
    achados: dict[str, list] = {}

    def _somar(ds) -> None:
        registro = _norm_registro(str(getattr(ds, "PatientID", "") or ""))
        if not registro:
            return
        # ``_formatar_nome`` e não ``str(...)``: o DICOM separa os
        # componentes por "^" (FAMÍLIA^NOME), e converter para texto aqui
        # perderia a estrutura — o diálogo mostrava "Balta^elda Garcia" em vez
        # de "Elda Garcia Balta". Aquela função lê family_name/given_name pelo
        # que são, e ainda trata o caso do sistema que repete o sobrenome
        # dentro do componente do nome.
        nome = dicom_rt._formatar_nome(getattr(ds, "PatientName", ""))
        if registro not in achados:
            achados[registro] = [nome, 0]
        achados[registro][1] += 1
        if nome and not achados[registro][0]:
            achados[registro][0] = nome

    for caminho in _CarregarTudo._arquivos_dicom(Path(pasta)):
        try:
            if caminho.suffix.lower() in (".zip", ".rar"):
                # Pacote: os membros só se leem descompactando. São raros e
                # pequenos perto de um RT Dose solto.
                for membro in leitura.iter_dicoms(caminho.read_bytes()):
                    with contextlib.suppress(Exception):
                        _somar(leitura.carregar(membro))
                continue
            cab = next(iter(leitura.cabecalhos_arquivo(caminho)), None)
            if cab is not None:
                _somar(cab)
        except Exception:  # noqa: BLE001 — arquivo ilegível não some com a triagem
            continue

    return {reg: (nome, n) for reg, (nome, n) in achados.items()}


class _CarregarTudo(QThread):
    ct_pronto = Signal(object, str)
    plano_pronto = Signal(list, str)   # lista de bundles de plano (até 5)
    progresso = Signal(str)
    falhou = Signal(str)

    def __init__(self, pasta: str, parent=None, registro: str = ""):
        super().__init__(parent)
        self._pasta = pasta
        self._parar = False
        # Vazio = carrega tudo o que achar (o caso normal: pasta de UM
        # paciente). Preenchido, só entra o DICOM de quem tem este PatientID —
        # é o que impede uma pasta-pai virar ficha com planos de três pessoas.
        self._registro = _norm_registro(registro)

    @staticmethod
    def _arquivos_dicom(pasta: Path) -> list:
        """Arquivos DICOM/pacotes da pasta para varrer, EXCLUINDO o arquivo da
        ficha salva do paciente (``ARQUIVOS_*.zip``).

        Esse zip guarda os RTPLAN ARQUIVADOS (``RTPLAN_p1``…); reingeri-los cria
        planos-fantasma e ainda empurra os planos reais para fora do limite
        (``MAX_PLANOS``). Reabrir a ficha salva usa outro caminho (``extrair_zip``),
        não este scan.
        """
        extensoes = {".dcm", ".zip", ".rar"}
        return sorted(
            p for p in pasta.rglob("*")
            if p.suffix.lower() in extensoes and p.is_file()
            and not p.name.upper().startswith("ARQUIVOS_")
        )

    def _e_do_paciente(self, ds) -> bool:
        """Este DICOM é de quem se pediu? Sem filtro, todo mundo passa.

        Arquivo SEM PatientID passa de propósito: recusá-lo descartaria em
        silêncio um auxiliar legítimo (há RT Image e protocolo de gating com o
        cabeçalho magro), e o preço de deixar passar é bem menor — ele não
        traz plano nem dose para a ficha de ninguém.
        """
        if not self._registro:
            return True
        registro = _norm_registro(str(getattr(ds, "PatientID", "") or ""))
        return not registro or registro == self._registro

    def run(self):
        pasta = Path(self._pasta)
        arquivos = self._arquivos_dicom(pasta)
        if not arquivos:
            self.falhou.emit(f"Nenhum arquivo DICOM encontrado em '{pasta.name}'.")
            return

        ct_membros: list[bytes] = []
        planos_ds: list = []
        planos_raw: dict = {}       # SOPInstanceUID do RP → bytes crus (p/ o zip)
        structs_ds: list = []
        doses_ds: list = []
        mp_protocolos: list = []
        ri_ds: list = []            # RT Images (DRRs de setup) do 600CD
        carregados: list[str] = []

        def _guardar(codigo: str, ds) -> None:
            if codigo == "RP":
                planos_ds.append(ds); carregados.append("RP")
            elif codigo == "RS":
                structs_ds.append(ds); carregados.append("RS")
            elif codigo == "RD":
                doses_ds.append(ds); carregados.append("RD")
            elif codigo == "RI":
                ri_ds.append(ds)           # auxiliar — não conta em 'carregados'
            elif codigo == "MP":
                mp_protocolos.append(ds)   # não conta em 'carregados' (auxiliar)

        def _despachar(codigo, tc_bytes, rd_dataset, meta_dataset) -> None:
            """Regra ÚNICA de para onde cada modalidade vai — igual para arquivo
            solto e membro de pacote, que só diferem em COMO carregam.

            Os argumentos são callables e são chamados aqui mesmo, na hora: a TC
            guarda os bytes crus, o RD o dataset com pixels (e fallback), o
            RP/RS o dataset com o cabeçalho. Só o callable da modalidade que
            chegou é executado — as leituras pesadas das outras não acontecem.
            """
            if codigo == "TC":
                ct_membros.append(tc_bytes())
            elif codigo in ("RD", "RI"):
                # RI (DRR de setup) precisa dos pixels, como o RD.
                _guardar(codigo, rd_dataset())
            elif codigo == "RP":
                # RP: guarda o dataset E os bytes crus (arquivados no zip para
                # eventual tratamento manual).
                ds = meta_dataset()
                _guardar("RP", ds)
                try:
                    planos_raw[dicom_rt.sop_uid(ds)] = tc_bytes()
                except Exception:  # noqa: BLE001 — sem os bytes, a ficha sai igual
                    pass
            elif codigo in ("RS", "MP"):
                # MP (MOTIONMTPROTOCOL): dataset completo — o gating está em
                # tags privadas, fora do cabeçalho de triagem.
                _guardar(codigo, meta_dataset())

        for caminho in arquivos:
            if self._parar:
                return
            self.progresso.emit(f"Lendo {caminho.name}…")
            if caminho.suffix.lower() in (".zip", ".rar"):
                # Pacote: os membros já vêm descompactados em memória e não têm
                # caminho próprio, então carregam dos bytes. São raros e pequenos
                # perto de um RT Dose solto.
                try:
                    raw = caminho.read_bytes()
                except Exception:  # noqa: BLE001
                    continue
                for membro in leitura.iter_dicoms(raw):
                    try:
                        ds = leitura.carregar(membro)
                        codigo = dicom_rt.identificar(ds)
                    except Exception:  # noqa: BLE001
                        continue
                    if not self._e_do_paciente(ds):
                        continue
                    _despachar(
                        codigo,
                        lambda m=membro: m,
                        lambda m=membro, d=ds: _rd_com_fallback(
                            lambda: leitura.carregar(m, stop_before_pixels=False),
                            lambda: d),
                        lambda d=ds: d,
                    )
                del raw
                continue

            # DICOM solto: tria pelo cabeçalho (uns KB) e só então lê do disco o
            # que interessa. Ler o arquivo inteiro para descobrir a modalidade e
            # depois copiá-lo no io.BytesIO custava 890 MB num RT Dose de 445 MB.
            try:
                cab = next(iter(leitura.cabecalhos_arquivo(caminho)), None)
            except Exception:  # noqa: BLE001
                continue
            if cab is None:
                continue
            if not self._e_do_paciente(cab):
                continue
            try:
                # O noqa: B023 nos lambdas abaixo. O ruff avisa que eles não
                # fixam o `caminho` do laço — é verdade, mas aqui não existe a
                # armadilha que a regra procura: o _despachar chama o callable
                # NA HORA, dentro desta mesma iteração (está na docstring
                # dele). Nenhum deles sobrevive para ser chamado depois, quando
                # `caminho` já apontaria para o próximo arquivo.
                _despachar(
                    dicom_rt.identificar(cab),
                    lambda: caminho.read_bytes(),  # noqa: B023
                    lambda: _rd_com_fallback(
                        lambda: leitura.carregar_arquivo(caminho, stop_before_pixels=False),  # noqa: B023
                        lambda: leitura.carregar_arquivo(caminho)),  # noqa: B023
                    lambda: leitura.carregar_arquivo(caminho),  # noqa: B023
                )
            except Exception:  # noqa: BLE001
                _LOG.exception("Falha ao carregar %s", caminho.name)
                continue

        if not ct_membros and not planos_ds and not structs_ds and not doses_ds:
            self.falhou.emit("Nenhum DICOM reconhecido (CT/RP/RS/RD) na pasta.")
            return

        # TC: agrupa em uma ou mais tomografias por FrameOfReferenceUID.
        series: list = []
        if ct_membros:
            try:
                self.progresso.emit(f"Montando volume(s) TC ({len(ct_membros)} cortes)…")
                # Esvazia o ``ct_membros``: os bytes crus saem um a um.
                series = ct_series.montar_series(leitura.cortes_de_tc(ct_membros))
                if series:
                    tc_txt = (f"{len(series)} tomografias" if len(series) > 1
                              else f"{series[0].n_axial} cortes")
                    self.ct_pronto.emit(series[0], f"TC: {tc_txt}")
            except Exception as exc:  # noqa: BLE001
                self.falhou.emit(f"Erro na TC: {exc}")

        # Os contornos dos RT Struct são convertidos AQUI, nesta thread. O
        # pydicom guarda o ``ContourData`` cru e só o converte no primeiro
        # acesso — um milhão de números num caso de quatro planos, validados um
        # a um —, e esse primeiro acesso caía na thread da TELA, na prévia da
        # ficha (SSD, DVH e corpo 3D): ~6 s de janela parada, medido em
        # 07/10/2026. Convertido aqui, o dataset guarda o valor pronto e a
        # prévia só lê.
        if structs_ds:
            self.progresso.emit("Preparando as estruturas…")
            for rs in structs_ds:
                if self._parar:
                    return
                _converter_contornos(rs)

        # Agrupa até 5 planos com seus RS/RD associados por referência DICOM.
        if planos_ds:
            bundles = dicom_rt.agrupar_planos(planos_ds, structs_ds, doses_ds,
                                              fisicos=equipe.FISICOS,
                                              medicos=equipe.MEDICOS)
        elif structs_ds or doses_ds:
            # RS/RD sem plano: ainda permite visualizar estruturas/dose.
            bundles = [{"rp_ds": None, "rp": {},
                        "rs_ds": structs_ds[0] if structs_ds else None,
                        "rd_ds": doses_ds[0] if doses_ds else None,
                        "rotulo": "Sem plano"}]
        else:
            bundles = []

        # Associa a cada plano a sua tomografia (por FrameOfReferenceUID) e o
        # protocolo de movimento (por RT Plan referenciado).
        mapa_ct = {s.frame_uid: s for s in series}
        mp_por_plano = {dicom_rt.mp_ref_plano_uid(mp): mp for mp in mp_protocolos}
        for b in bundles:
            ref = b.get("rd_ds") or b.get("rs_ds")
            fu = dose3d.frame_uid(ref) if ref is not None else ""
            b["ct"] = mapa_ct.get(fu) or (series[0] if len(series) == 1 else None)
            mp = (mp_por_plano.get(dicom_rt.sop_uid(b["rp_ds"]))
                  if b.get("rp_ds") is not None else None)
            if mp is None and len(mp_protocolos) == 1:
                mp = mp_protocolos[0]   # fallback: protocolo único p/ plano único
            # Com TC e protocolo de movimento, deduz modalidade/janela de gating.
            dicom_rt.enriquecer_gating(
                b["rp"], b["ct"].serie_descricao if b["ct"] is not None else "", mp)

        # DRRs de setup (600CD): RT Images dos feixes de SETUP dos planos. São do
        # caso, então a mesma lista vai em todos os bundles.
        drrs_setup = (dicom_rt.selecionar_drrs_setup(ri_ds, planos_ds)
                      if ri_ds else [])
        for b in bundles:
            b["drrs_setup"] = drrs_setup
            b["rp_raw"] = (planos_raw.get(dicom_rt.sop_uid(b["rp_ds"]))
                           if b.get("rp_ds") is not None else None)

        if bundles:
            n = len(bundles)
            extra = (f" (limitado a {dicom_rt.MAX_PLANOS})"
                     if len(planos_ds) > dicom_rt.MAX_PLANOS else "")
            n_tc = len({s.frame_uid for s in series})
            tc_info = f" · {n_tc} TC" if n_tc > 1 else ""
            msg = f"{n} plano(s){extra}{tc_info}: " + ", ".join(sorted(set(carregados)))
            self.plano_pronto.emit(bundles, msg)


class _CarregarCorpo3d(QThread):
    concluido = Signal(bytes)

    def __init__(self, rs, elev: float = 10, azim: float = -30, parent=None):
        super().__init__(parent)
        self._rs = rs
        self._elev = elev
        self._azim = azim

    def run(self):
        try:
            from isocentro.desenho import corpo
            png = corpo.renderizar_corpo(self._rs, elev=self._elev,
                                         azim=self._azim)
            if png:
                self.concluido.emit(png)
        except Exception:  # noqa: BLE001 — thread de fundo: não derruba a GUI
            # O painel 3D fica vazio; sem isto não havia como saber por quê.
            _LOG.exception("Falha ao renderizar o corpo 3D")
