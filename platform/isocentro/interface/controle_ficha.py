"""A montagem da ficha: do caso na tela ao PDF, ao registro e ao arquivo.

Saiu da ``JanelaPrincipal`` em 16/09/2026 (R-06, corte 6c do
``docs/PROPOSTA_GUI.md``), o último dos cortes. É o caminho por onde sai o papel
que vai para a sala — Visualização, Impressão, liberação e arquivo versionado
—, e a mudança foi só de endereço: a ordem dos passos, os textos e o que entra
em cada página são os da janela. ``tools/caso.py`` chama o MESMO
``montar_planos_pdf``, e é isso que faz a conferência por ``comparar_pdf`` valer.

Lê ``janela.caso`` NA HORA, nunca guarda — a mesma regra do ``PortaoDaFicha``,
do ``ControleCapa`` e do ``ControleViewer``: a geração abre pop-ups (laço de
eventos aninhado), e a limpeza pode trocar o caso no meio.

O que continua na janela, e por quê:

- ``_escolher_ficha``, ``_abrir_pdf_previa``, ``_descartar_previa``,
  ``_aviso_progresso``, ``_autor``: são peça de tela da bancada, e a Fichinha
  também os usa.
- ``_dose_prescrita``, ``_indices_ficha``, ``_agendamento_da_ficha``: prescrição e
  agendamento, que o viewer e o agendamento também consultam.
- ``_executar_limpeza``, ``_excluir_arquivos_pasta``, ``_anotar_liberacao`` e
  ``_pasta_do_paciente_para_liberar``: são do caso e da liberação, que a
  bancada dispara por outras portas.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import QFileDialog

from isocentro.dados import backup
from isocentro.dados import empacotar
from isocentro.dados import historico
from isocentro.dados import indice
from isocentro.dados import registro_json
from isocentro.dicom import dicom_rt
from isocentro.interface import fichinha
from isocentro.interface import portao_ficha
from isocentro.interface import ui
from isocentro.papel import capa_pdf
from isocentro.papel import ficha_pdf

_LOG = logging.getLogger(__name__)

# O que o app mostra ENQUANTO trabalha na ficha. Era uma frase por etapa — "Lendo os
# DICOM e montando a ficha", "Elaborando a ficha de FULANO", "Refazendo a ficha
# com as alterações" —, e a distinção era interna: de fora são a mesma coisa (o
# programa está ocupado com a ficha) e passavam rápido demais para serem lidas.
# Uma frase só, sempre a mesma — na linha de status da Fichinha e no aviso que
# cobre a tela enquanto o PDF é montado. Estável, em vez de um letreiro
# piscando etapa por etapa.
_FICHA_EM_ANDAMENTO = "Ficha em andamento"


def _render_drrs_png(drrs: list | None, planos: list | None = None) -> tuple:
    """Renderiza os DRRs de setup (lista de datasets) → (pngs, titulos).

    ``planos`` são os RT Plans do caso, e é deles que sai o nome INTEIRO do
    portal: o rótulo da imagem tem dezesseis caracteres e corta o nome que
    está no console (ver ``dicom_rt.rotulo_drr_setup``). Os títulos daqui são
    os que ficam SALVOS no registro, então o que se perder aqui volta
    cortado em toda reimpressão do Histórico.
    """
    pngs: list = []
    titulos: list = []
    for ds in (drrs or []):
        try:
            from isocentro.papel import drr as _drr
            pngs.append(_drr.render_drr(ds))
            titulos.append(dicom_rt.rotulo_drr_setup(ds, planos))
        except Exception:  # noqa: BLE001 — a ficha ainda sai sem esse DRR
            _LOG.exception("Falha ao renderizar um DRR de setup")
    return pngs, titulos


def _montar_render_meta(recursos: dict) -> dict:
    """Parâmetros de visualização persistidos no registro (fluxo com DICOM)."""
    ev = recursos.get("estruturas_visiveis")
    return {
        "idx_axial":   recursos.get("idx_axial"),
        "idx_sagital": recursos.get("idx_sagital"),
        "idx_coronal": recursos.get("idx_coronal"),
        "mostrar_isodose":    recursos.get("mostrar_isodose"),
        "isodose_range":      list(recursos.get("isodose_range") or ()),
        "mostrar_estruturas": recursos.get("mostrar_estruturas"),
        "estruturas_dvh":     recursos.get("estruturas_dvh"),
        "estruturas_visiveis": sorted(ev) if ev else None,
    }


def _ler_bytes_seguro(caminho: Optional[str]) -> Optional[bytes]:
    """Lê os bytes de um arquivo, ou None se ausente/ilegível."""
    if not caminho or not os.path.exists(caminho):
        return None
    try:
        return Path(caminho).read_bytes()
    except Exception:  # noqa: BLE001
        return None


class ControleFicha:
    """Gera a ficha do caso aberto. A janela o constrói e o chama."""

    def __init__(self, janela):
        # A janela é o PAI dos pop-ups e a dona do caso (ver a docstring do
        # módulo para o porquê de não guardar o ``Caso`` aqui).
        self.janela = janela

    def montar_planos_pdf(self) -> list:
        """Monta [{dados, store, recursos}] por plano para a geração multi-plano.

        O plano ativo usa as configurações atuais do viewer (cortes/isodose/
        estruturas); os demais usam padrões (cortes centrais, dose do próprio rd).
        """
        dados_planos = self.janela.form.coletar_planos()
        v = self.janela.viewer
        out = []
        for i, p in enumerate(self.janela.caso.planos):
            dados = dados_planos[i] if i < len(dados_planos) else self.janela.form.coletar()
            rp = p["rp"]
            # Garante SSDs calculados para TODOS os planos (não só o ativo),
            # senão os SSDs dos demais planos saem vazios na página 2.
            if rp.get("iso_pos_mm"):
                try:
                    dicom_rt.aplicar_ssds(rp, rs_ds=p["rs_ds"], ct_serie=p.get("ct"))
                except Exception:  # noqa: BLE001 — a ficha sai sem o SSD, não sem a ficha
                    _LOG.exception("Falha ao calcular os SSDs do plano %r",
                                   p.get("rotulo"))
            if not dados.get("maquina") and rp.get("maquina"):
                dados["maquina"] = rp["maquina"]
            if not dados.get("eq_medico") and rp.get("medico"):
                dados["eq_medico"] = rp["medico"]
            tem_rs = p["rs_ds"] is not None
            if i == self.janela.caso.plano_ativo:
                # Visão combinada (Soma/Personalizado): a tela desenha cortes,
                # estruturas e 3D a partir da RS unificada, não da RS do plano —
                # é contra ELA que o 3D em cache tem de ser conferido, senão o
                # 3D que o usuário está vendo é descartado e a ficha re-renderiza
                # o corpo de um plano só.
                comb = self.janela.caso.modo_soma and self.janela.caso.rs_soma is not None
                rs_vista = self.janela.caso.rs_soma if comb else p["rs_ds"]
                recursos = {
                    "ct": p.get("ct"), "rs": p["rs_ds"], "rd": p["rd_ds"],
                    "estruturas_dvh": list(v.estruturas_selecionadas) if tem_rs else None,
                    "mostrar_isodose": v.chk_isodose.isChecked(),
                    "isodose_range": v.faixa_isodose_pct(),
                    "mostrar_estruturas": v.chk_estruturas.isChecked(),
                    "estruturas_visiveis": v.estruturas_selecionadas if tem_rs else None,
                    "idx_axial": v.painel_axial.slider.value(),
                    "idx_sagital": v.painel_sagital.slider.value(),
                    "idx_coronal": v.painel_coronal.slider.value(),
                    # Só reusa o 3D em cache se ele é DESTE corpo (RS); senão None
                    # → o PDF re-renderiza do rs do plano (evita o 3D de outra TC,
                    # ex.: o crânio na página do fígado quando o render async ainda
                    # não trocou).
                    "png_3d": (self.janela.caso.png_3d if self.janela.caso.png_3d_rs is rs_vista else None),
                    # Esta é a aba que está NA TELA: na página combinada é ela que
                    # dita cortes/estruturas/3D — não o primeiro plano da lista.
                    "_ativo": True,
                    # RS unificada da visão combinada (None fora dela).
                    "rs_soma": self.janela.caso.rs_soma if comb else None,
                }
            else:
                estado = p.get("viewer_state")
                if estado is not None:
                    # Aba já visitada: a ficha usa os cortes/estruturas/isodose
                    # que o usuário escolheu naquela aba (guardados no cache).
                    sel = estado.get("selecionadas") if tem_rs else None
                    recursos = {
                        "ct": p.get("ct"), "rs": p["rs_ds"], "rd": p["rd_ds"],
                        "estruturas_dvh": list(sel) if sel else None,
                        "mostrar_isodose": estado.get("isodose_on", True),
                        "isodose_range": estado.get("iso_pct", (50.0, 100.0)),
                        "mostrar_estruturas": estado.get("estruturas_on", True),
                        "estruturas_visiveis": sel,
                        "idx_axial": estado.get("idx_axial"),
                        "idx_sagital": estado.get("idx_sagital"),
                        "idx_coronal": estado.get("idx_coronal"),
                        # 3D do cache só se for do MESMO corpo (RS) do plano.
                        "png_3d": (estado.get("png_3d")
                                   if estado.get("png_3d_rs") is p["rs_ds"] else None),
                    }
                else:
                    # Nunca visitada: só alvos/OARs (sem anel/CTV/auxiliares) e
                    # cortes no isocentro do plano, como o viewer abre por padrão.
                    padrao = ({n for n in self.janela.controle_viewer.nomes_estruturas(p["rs_ds"])
                               if not ficha_pdf.estrutura_auxiliar(n)}
                              if tem_rs else None)
                    ct_p = p.get("ct"); iso = rp.get("iso_pos_mm")
                    idx = (ct_p.indices_do_ponto([float(x) for x in iso])
                           if (ct_p is not None and iso) else {})
                    recursos = {
                        "ct": ct_p, "rs": p["rs_ds"], "rd": p["rd_ds"],
                        "estruturas_dvh": None, "mostrar_isodose": True,
                        "isodose_range": (50.0, 100.0), "mostrar_estruturas": True,
                        "estruturas_visiveis": padrao,
                        "idx_axial": idx.get("Axial"),
                        "idx_sagital": idx.get("Sagital"),
                        "idx_coronal": idx.get("Coronal"),
                        "png_3d": None,
                    }
            recursos["drrs"] = p.get("drrs_setup") or []
            recursos["planos_ds"] = self.planos_ds()
            recursos["drrs_png"] = self.janela.caso.drrs_png
            recursos["drrs_titulos"] = self.janela.caso.drrs_titulos
            # 100% da isodose = prescrição deste plano (a combinada soma as dos
            # planos que entram nela; ver _pagina1_soma).
            recursos["dose_ref"] = float(dados.get("rx_dose_total")
                                         or rp.get("dose_total") or 0.0)
            out.append({"dados": dados, "store": {"RP": rp}, "recursos": recursos})
        return out

    def planos_ds(self) -> list:
        """Os RT Plans (datasets) do caso — os que existirem."""
        return [p.get("rp_ds") for p in (self.janela.caso.planos or [])
                if p.get("rp_ds") is not None]

    def montar_recursos_ativo(self) -> dict:
        """Recursos (TC/RS/RD + estado do viewer) do plano ATIVO, para a pág. 1."""
        v = self.janela.viewer
        tem_rs = self.janela.caso.rs is not None
        ativo = (self.janela.caso.planos[self.janela.caso.plano_ativo]
                 if 0 <= self.janela.caso.plano_ativo < len(self.janela.caso.planos) else {})
        return {"ct": self.janela.caso.ct, "rs": self.janela.caso.rs, "rd": self.janela.caso.rd,
                "drrs": ativo.get("drrs_setup") or [],
                # Os RT Plans acompanham os portais: é neles que está o nome
                # inteiro do campo (ver ``dicom_rt.rotulo_drr_setup``).
                "planos_ds": self.planos_ds(),
                "estruturas_dvh": list(v.estruturas_selecionadas) if tem_rs else None,
                "mostrar_isodose": v.chk_isodose.isChecked(),
                "isodose_range": v.faixa_isodose_pct(),
                "mostrar_estruturas": v.chk_estruturas.isChecked(),
                "estruturas_visiveis": v.estruturas_selecionadas if tem_rs else None,
                "idx_axial": v.painel_axial.slider.value(),
                "idx_sagital": v.painel_sagital.slider.value(),
                "idx_coronal": v.painel_coronal.slider.value(),
                # 100% da isodose = prescrição do plano (igual à tela).
                "dose_ref": self.janela._dose_prescrita(self.janela.caso.plano_ativo),
                # 3D em cache só se for deste corpo (RS); senão o PDF re-renderiza.
                "png_3d": (self.janela.caso.png_3d if self.janela.caso.png_3d_rs is self.janela.caso.rs else None)}

    def construir_pdf(self, dados, plano_store, recursos, cortes_png, dvh_png,
                       multi, arquivado, modo_ficha) -> dict | None:
        """Gera os bytes do PDF (single/arquivado/multi). None em caso de erro.

        Devolve ``{pdf_bytes, imagens_multi, dvhs_multi, planos_data, planos_pdf}``.
        """
        imagens_multi = dvhs_multi = None
        planos_data = None
        planos_pdf = None
        ag_fic = self.janela.caso.agendamento   # agendamento já restrito aos planos da ficha
        try:
            with self.janela._aviso_progresso(_FICHA_EM_ANDAMENTO):
                # A capa é montada NA TELA (ver ``capa_para_ficha``) e por isso
                # antes, aqui na thread da interface; o PDF dela vai junto com o
                # da ficha, no fundo.
                capa = self._capa_da_tela(dados)
                if multi:
                    planos_pdf = self.montar_planos_pdf()
                    # Propaga o flag SUS (do popup) para todos os planos: a folha
                    # de Registro usa os dados do 1º plano e persiste em cada um.
                    for pp in planos_pdf:
                        pp["dados"]["pac_sus"] = dados.get("pac_sus", False)
                        pp["dados"]["numero_sus"] = dados.get("numero_sus", "")
                    if arquivado:
                        # Reaberto: usa os PNGs de cortes E DVH salvos por plano
                        # (sem DICOM não dá para recalcular o DVH).
                        _paths = (self.janela.caso.registro_carregado or {}).get("imagens_paths") or []
                        _dpaths = (self.janela.caso.registro_carregado or {}).get("dvhs_paths") or []
                        for k, pp in enumerate(planos_pdf):
                            pp["cortes_salvo"] = _ler_bytes_seguro(
                                _paths[k] if k < len(_paths) else None)
                            pp["dvh_salvo"] = _ler_bytes_seguro(
                                _dpaths[k] if k < len(_dpaths) else None)
                    # "Separar Ficha": só os planos escolhidos entram no
                    # documento. Filtra aqui (depois de parear os PNGs salvos,
                    # que vêm por índice original) e reescreve o agendamento
                    # para os que ficaram — daí saem sequência, ordem e
                    # subconjunto do Personalizado já remapeados.
                    idx_fic = self.janela._indices_ficha()
                    pos = {ant: novo for novo, ant in enumerate(idx_fic)}
                    planos_pdf = [planos_pdf[i] for i in idx_fic]
                    ag_fic = self.janela._agendamento_da_ficha(pos)
                    _ag = ag_fic or {}
                    rots_ag = [self.janela.caso.planos[i].get("rotulo", f"Plano {i + 1}")
                               for i in idx_fic]
                    pdf_bytes, imagens_multi, dvhs_multi = self._no_fundo(
                        lambda: ficha_pdf.gerar_ficha_multiplano(
                            planos_pdf, modo_ficha,
                            sequencia=_ag.get("sequencia"), rotulos=rots_ag,
                            planos_ficha=_ag.get("planos_ficha"),
                            replan=_ag.get("replan_fracoes") or 0,
                            dose_replan=_ag.get("replan_dose") or 0,
                            ordem_planos=_ag.get("ordem_planos"),
                            grupos_dose=_ag.get("grupos_dose")))
                    planos_data = [
                        {"dados": pp["dados"],
                         "plano_rp": pp["store"].get("RP", {}),
                         "rotulo": rots_ag[k]}
                        for k, pp in enumerate(planos_pdf)
                    ]
                elif arquivado:
                    _ag = self.janela.caso.agendamento or {}
                    pdf_bytes = self._no_fundo(lambda: ficha_pdf.gerar_ficha_arquivada(
                        dados, plano_store, cortes_png, dvh_png,
                        drrs_png=(recursos or {}).get("drrs_png"),
                        drrs_titulos=(recursos or {}).get("drrs_titulos"),
                        replan=_ag.get("replan_fracoes") or 0,
                        dose_replan=_ag.get("replan_dose") or 0))
                else:
                    _ag = self.janela.caso.agendamento or {}
                    pdf_bytes = self._no_fundo(lambda: ficha_pdf.gerar_ficha(
                        dados, plano_store, recursos=recursos,
                        replan=_ag.get("replan_fracoes") or 0,
                        dose_replan=_ag.get("replan_dose") or 0))
                # A capa vai NA FRENTE da ficha, no mesmo arquivo: é um
                # documento só, e quem confere a ficha confere a capa junto.
                pdf_bytes = self._no_fundo(
                    lambda: self._juntar_capa(pdf_bytes, self._pdf_da_capa(capa)))
        except Exception as exc:  # noqa: BLE001
            ui.falhar(self.janela, "Erro ao gerar PDF", str(exc))
            return None
        return {"pdf_bytes": pdf_bytes, "imagens_multi": imagens_multi,
                "dvhs_multi": dvhs_multi, "planos_data": planos_data,
                "planos_pdf": planos_pdf,
                # Agendamento coerente com os planos que ficaram na ficha —
                # usado pela Alta e persistido no registro.
                "agendamento": ag_fic}

    def com_capa(self, ficha_bytes: bytes, dados: dict) -> bytes:
        """Prende a Capa de Tratamento na frente da ficha, num arquivo só.

        A capa e a ficha sempre andaram grampeadas na prancheta; separá-las em
        dois PDFs só transferia o grampo para quem imprime. Aqui elas saem
        juntas — Visualização, Impressão e o arquivo versionado na pasta.

        A ficha é o documento crítico: se a capa não fechar (relatórios fora do
        ar, foto ilegível), a ficha sai sozinha e o motivo vai para o log. O
        contrário — segurar a ficha por causa da capa — seria trocar o
        importante pelo acessório.
        """
        return self._juntar_capa(ficha_bytes, self.capa_para_ficha(dados))

    @staticmethod
    def _juntar_capa(ficha_bytes: bytes, capa_bytes: Optional[bytes]) -> bytes:
        """A junção em si — sem tela nenhuma, pode rodar no fundo."""
        if not capa_bytes:
            return ficha_bytes
        try:
            import io as _io

            from pypdf import PdfWriter

            escritor = PdfWriter()
            for parte in (capa_bytes, ficha_bytes):
                escritor.append(_io.BytesIO(parte))
            buf = _io.BytesIO()
            escritor.write(buf)
            return buf.getvalue()
        except Exception:  # noqa: BLE001 — a ficha sai sozinha
            _LOG.exception("Capa: falha ao juntar com a ficha — sai só a ficha")
            return ficha_bytes

    def capa_para_ficha(self, dados: dict) -> Optional[bytes]:
        """Bytes da capa deste paciente, montando-a antes se ainda não estiver.

        Monta **na tela**, e não num caminho paralelo: o que vai impresso passa
        a ser exatamente o que a aba Capa mostra, e quem quiser corrigir um
        campo tem onde. Sem nome de paciente não há capa — e aí a ficha segue
        sozinha, sem modal nem interrupção.
        """
        return self._pdf_da_capa(self._capa_da_tela(dados))

    def _capa_da_tela(self, _dados: dict):
        """A capa como a aba Capa a mostra — a parte que PRECISA da tela."""
        try:
            if not self.janela.controle_capa.ja_montada():
                self.janela.controle_capa.buscar()
            capa = self.janela.capa.coletar()
            return capa if capa.nome.strip() else None
        except Exception:  # noqa: BLE001
            _LOG.exception("Capa: falha ao montar para juntar à ficha")
            return None

    @staticmethod
    def _pdf_da_capa(capa) -> Optional[bytes]:
        """O PDF da capa já coletada — sem tela, pode rodar no fundo."""
        if capa is None:
            return None
        try:
            return capa_pdf.gerar(capa)
        except Exception:  # noqa: BLE001
            _LOG.exception("Capa: falha ao gerar o PDF da capa")
            return None

    def _no_fundo(self, funcao):
        """Roda ``funcao`` numa thread e espera com a TELA VIVA.

        A ficha de um caso de quatro planos leva ~20 s de cálculo (cortes com
        isodose, DVH, imagens do PDF). Na thread da interface, isso era a
        janela "Não respondendo" — e da cadeira, travou (relato de 07/10/2026,
        no clique da Documentação PRONTA). Aqui a conta vai para uma thread e
        a interface segue um laço de eventos próprio: repinta, mostra o cursor
        de espera, e o Windows não a dá por morta.

        Para quem chama continua SÍNCRONO — devolve o resultado, ou relança a
        exceção da thread —, então nenhum fluxo em volta (prévia, Impressão,
        liberação) precisou mudar de forma.

        **Nenhum clique entra no meio.** O filtro engole mouse e teclado do
        aplicativo inteiro enquanto a thread trabalha: um paciente trocado, uma
        aba aberta ou um segundo clique no mesmo botão no meio da geração
        mexeriam no caso que a thread está lendo. O que a função recebe tem de
        estar pronto ANTES (dados, recursos, capa coletada) — nada aqui dentro
        pode tocar em widget.
        """
        from PySide6.QtCore import QEvent, QEventLoop, QObject, QThread, QTimer
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            return funcao()
        resultado: dict = {}

        class _Trabalho(QThread):
            def run(self_):  # noqa: N805 — ``self`` é o controle, de fora
                try:
                    resultado["valor"] = funcao()
                except BaseException as exc:  # noqa: BLE001 — relançada abaixo
                    resultado["erro"] = exc

        _ENTRADA = {QEvent.MouseButtonPress, QEvent.MouseButtonRelease,
                    QEvent.MouseButtonDblClick, QEvent.KeyPress,
                    QEvent.KeyRelease, QEvent.Wheel, QEvent.ShortcutOverride}

        class _SemEntrada(QObject):
            def eventFilter(self_, _alvo, evento):  # noqa: N802,N805
                return evento.type() in _ENTRADA

        trabalho = _Trabalho()
        filtro = _SemEntrada()
        laco = QEventLoop()
        # Por consulta, e não pelo ``finished``: a thread pode acabar ANTES de
        # o laço começar, e aí o sinal já teria passado e o laço não sairia
        # nunca.
        vigia = QTimer()
        vigia.setInterval(30)
        vigia.timeout.connect(lambda: trabalho.isFinished() and laco.quit())
        app.installEventFilter(filtro)
        try:
            trabalho.start()
            vigia.start()
            laco.exec()
            trabalho.wait()
        finally:
            vigia.stop()
            app.removeEventFilter(filtro)
        if "erro" in resultado:
            raise resultado["erro"]
        return resultado.get("valor")

    def salvar_alta(self, dados, recursos, planos_pdf, multi, modo_ficha,
                     caminho, nome, sufixo_v, data, planos_ficha=None,
                     arquivado=False, cortes_png=None, dvh_png=None) -> None:
        """Gera e salva o Relatório de Alta ao lado da ficha (falha não bloqueia).

        ``planos_pdf``/``planos_ficha`` já vêm restritos aos planos que compõem
        a ficha (Separar Ficha) — a Alta espelha exatamente o documento.

        ``arquivado`` com um plano só: as imagens são os PNGs do registro, os
        MESMOS que a ficha acabou de usar (``cortes_png``/``dvh_png``). Sem
        isso a Alta tentava desenhar da TC, que numa ficha recarregada do JSON
        não existe, e saía sem imagem nenhuma.
        """
        try:
            if multi and planos_pdf:
                alta_bytes = ficha_pdf.gerar_alta_multiplano(
                    planos_pdf, modo_ficha, planos_ficha=planos_ficha,
                    # Mesmo 100% da tela e da ficha (ver _dose_ref_total).
                    grupos_dose=(self.janela.caso.agendamento or {}).get("grupos_dose"))
            elif arquivado:
                alta_bytes = ficha_pdf.gerar_alta_arquivada(
                    dados, cortes_png, dvh_png)
            else:
                alta_bytes = ficha_pdf.gerar_alta(dados, recursos)
            pasta = os.path.dirname(caminho)
            nome_alta = f"ALTA_{nome}{sufixo_v}_{data}.pdf"
            with open(os.path.join(pasta, nome_alta), "wb") as f:
                f.write(alta_bytes)
            self.janela.status.showMessage(f"PDFs salvos em: {pasta}")
        except Exception as exc:  # noqa: BLE001
            self.janela.status.showMessage(f"Ficha salva. Erro na Alta: {exc}")

    def arquivar_no_zip(self, dados, pasta_paciente, registro_info) -> None:
        """Move os arquivos gerados (JSON + PNGs) para o .zip do paciente e apaga
        os soltos — só depois de confirmar que o JSON lê de volta do zip."""
        try:
            soltos = [p for p in ([registro_info.get("json_path")]
                                  + list(registro_info.get("arquivos") or []))
                      if p and os.path.exists(p)]
            if not soltos:
                return
            destino = os.path.join(pasta_paciente, registro_json.nome_zip(dados))
            empacotar.atualizar(destino, soltos)
            if registro_json.ler_registro_do_zip(destino) is None:
                raise RuntimeError("o registro não pôde ser lido de volta do .zip")
            for p in soltos:
                try:
                    os.remove(p)
                except OSError:
                    _LOG.warning("Não removi o solto %r após arquivar", p)
            # Cópia redundante do registro (best-effort; não bloqueia).
            copia = backup.copiar(destino)
            if copia:
                self.janela.status.showMessage(
                    f"Arquivos arquivados em {os.path.basename(destino)} "
                    "(backup ok)")
            else:
                self.janela.status.showMessage(
                    f"Arquivos arquivados em {os.path.basename(destino)} "
                    "(backup não realizado)")
                _LOG.warning("Backup do registro não realizado para %r", destino)
        except Exception as exc:  # noqa: BLE001 — o arquivamento é acessório
            _LOG.exception("Falha ao arquivar os arquivos no .zip")
            self.janela.status.showMessage(f"Ficha salva. Erro ao arquivar: {exc}")

    def salvar_registro_e_arquivar(self, dados, rp, render_meta, recursos, saida,
                                    cortes_png, dvh_png, multi, arquivado,
                                    modo_ficha, caminho, pasta_paciente) -> tuple:
        """Versiona o registro (JSON), atualiza o índice e arquiva no .zip.
        Devolve ``(registro_ok, registro_info)``."""
        registro_ok = False
        registro_info = None
        try:
            if arquivado:
                img_p1, dvh_save = cortes_png, dvh_png
            elif multi:
                # Imagens/DVHs vão pelas listas 'imagens'/'dvhs' (uma por plano).
                img_p1 = None
                dvh_save = None
            else:
                img_p1 = ficha_pdf.montar_imagem_pagina1(dados, recursos)
                dvh_save = recursos.get("_png_dvh")
            # RTPLAN(s) crus dos planos ativos (um por plano; ausente ao reabrir).
            _rtplans = [p.get("rp_raw") for p in self.janela.caso.planos]
            registro_info = registro_json.salvar_versao(
                pasta_paciente, dados, rp, render_meta, img_p1, dvh_save,
                pdf_path=caminho,
                imagens=(saida["imagens_multi"] if multi else None),
                dvhs=(saida["dvhs_multi"] if multi else None),
                modo=(modo_ficha if multi else None),
                planos=saida["planos_data"],
                # Guarda o agendamento no multi e também no single quando há
                # replanejamento (para reimprimir a página 3 igual no Histórico).
                # No multi vem já restrito aos planos da ficha (Separar Ficha),
                # senão os índices salvos apontariam para planos ausentes.
                agendamento=((saida.get("agendamento") or self.janela.caso.agendamento)
                             if (multi or (self.janela.caso.agendamento or {})
                                 .get("replan_fracoes")) else None),
                autor=self.janela._autor(),
                drrs=(recursos or {}).get("drrs_png") or [],
                drrs_titulos=(recursos or {}).get("drrs_titulos") or [],
                rtplans=_rtplans)
            registro_ok = True
            historico.registrar("ficha_gerada", detalhes={
                "paciente": dados.get("pac_nome", ""),
                "registro": dados.get("pac_registro", ""),
                "versao": registro_info.get("versao"),
                "nova": registro_info.get("nova", True),
                "maquina": dados.get("maquina", ""),
                # A pasta vai junto para "Suas últimas fichas" poder apontar o
                # caso de volta num clique. Sem ela, só sobra procurar o
                # caminho pelo índice — que não existe para tudo.
                "pasta": str(pasta_paciente or ""),
                "sus": bool(dados.get("pac_sus"))})
            # Índice central (derivado; falha aqui não bloqueia).
            try:
                indice.sincronizar_arquivo(registro_info["json_path"])
            except Exception:  # noqa: BLE001
                _LOG.exception("Falha ao sincronizar o índice central")
            if registro_info.get("nova", True):
                self.janela.status.showMessage(
                    f"Registro v{registro_info['versao']} salvo em: {pasta_paciente}")
            else:
                self.janela.status.showMessage(
                    f"Sem modificações: ficha idêntica à versão "
                    f"v{registro_info['versao']} — nenhuma nova versão criada.")
                ui.avisar(
                    self.janela, "Mesma versão anterior",
                    "Nenhuma modificação foi detectada em relação à versão "
                    f"v{registro_info['versao']}.\n\nO PDF foi gerado, mas "
                    "nenhuma nova versão foi criada no registro.")
        except Exception as exc:  # noqa: BLE001
            ui.alertar(
                self.janela, "Registro não salvo",
                "A ficha foi gerada, mas o registro JSON do paciente não pôde "
                f"ser salvo:\n\n{exc}\n\n"
                "Por segurança, os arquivos DICOM NÃO serão apagados.")

        if registro_ok and registro_info:
            self.arquivar_no_zip(dados, pasta_paciente, registro_info)
        return registro_ok, registro_info

    def fluxo_pos_geracao(self, arquivado, registro_ok, registro_info, dados) -> None:
        """Diálogos pós-geração: limpar tratamento reaberto, ou apagar TC/DICOM."""
        if arquivado:
            # Reaberto do JSON: não há DICOM em memória. Só oferece limpar.
            if ui.confirmar(
                    self.janela, "Limpar tratamento carregado?",
                    "Deseja limpar o tratamento carregado da memória?",
                    acao="Limpar", recusa="Manter carregado",
                    detalhe=("O programa será reiniciado para um novo "
                             "paciente.\nOs PDFs e o registro já foram salvos "
                             "e não serão afetados."),
                    perigo=True):
                self.janela._executar_limpeza()
            return

        if not ui.confirmar(
                self.janela, "Apagar dados carregados?",
                "Deseja apagar a TC carregada da memória?",
                acao="Apagar", recusa="Manter carregado",
                detalhe=("O programa será reiniciado para um novo paciente.\n"
                         "Os PDFs já foram salvos e não serão afetados."),
                perigo=True):
            return
        pasta_excluir = self.janela.caso.pasta_carregada
        self.janela._executar_limpeza()
        if pasta_excluir and registro_ok:
            versao = registro_info["versao"]
            # O pop-up mais destrutivo do programa: apaga DICOM do disco, e
            # não há desfazer. ``perigo=True`` mantém o Enter na recusa, que
            # era o que o ``setDefaultButton(btn_nao)` já fazia à mão aqui.
            if ui.confirmar(
                    self.janela, "Excluir arquivos DICOM da pasta?",
                    "Deseja excluir permanentemente os arquivos DICOM "
                    "(TC, RP, RS e RD) da pasta de origem?",
                    acao="Excluir os DICOM", recusa="Manter os arquivos",
                    detalhe=(
                        f"Pasta: {pasta_excluir}\n"
                        f"Paciente: {dados.get('pac_nome') or '—'} "
                        f"(registro {dados.get('pac_registro') or '—'})\n\n"
                        "Serão removidos apenas os TC, RP, RS e RD DESTE "
                        "paciente, incluindo subpastas. Arquivos de outros "
                        "pacientes são mantidos.\n"
                        f"O registro e as imagens (v{versao}) já foram "
                        "arquivados no .zip do paciente nesta pasta e serão "
                        "mantidos.\n"
                        "Esta ação não pode ser desfeita."),
                    perigo=True):
                self.janela._excluir_arquivos_pasta(
                    pasta_excluir, {"TC", "RP", "RS", "RD", "RI", "MP"},
                    registro=dados.get("pac_registro"))
                historico.registrar("dicom_excluido", detalhes={
                    "paciente": dados.get("pac_nome", ""),
                    "registro": dados.get("pac_registro", ""),
                    "pasta": pasta_excluir})
        elif pasta_excluir and not registro_ok:
            ui.avisar(
                self.janela, "Arquivos mantidos",
                "Como o registro JSON não pôde ser salvo, os arquivos "
                "DICOM foram mantidos na pasta de origem.")

    def gerar_pdf(self, preview: bool = False, *, abrir: bool = True):
        dados = self.janela.form.coletar()
        if not self.janela.portao.validar_campos_obrigatorios(dados):
            return
        if not self.janela.portao.confirmar_gating_pendente():
            return
        if not self.janela.portao.confirmar_planos_incompletos():
            return
        if not self.janela.portao.coletar_sus(dados):
            return

        rp = self.janela.caso.dados.get("RP", {})
        if not dados.get("maquina") and rp.get("maquina"):
            dados["maquina"] = rp["maquina"]
        if not dados.get("eq_medico") and rp.get("medico"):
            dados["eq_medico"] = rp["medico"]
        plano_store = {"RP": rp}
        recursos = self.montar_recursos_ativo()

        # Tratamento aberto do JSON (sem DICOM): reusa cortes/DVH salvos p/ pág.1.
        arquivado = self.janela.caso.ct is None and self.janela.caso.registro_carregado is not None
        # O aviso de PORTAL só faz sentido gerando do DICOM: numa reimpressão
        # arquivada não há RT Image, então não incomoda o usuário à toa.
        if not arquivado and not self.janela.portao.confirmar_600cd_sem_portal(dados, recursos):
            return
        # DRRs de setup (600CD) em PNG: gerando do DICOM, renderiza dos datasets;
        # no Histórico, lê os PNGs salvos no registro. Ficam no caso (todas as
        # páginas/planos usam os mesmos) e são persistidos com a versão.
        # Só o 600CD tem páginas de DRR: em outra máquina nada é renderizado nem
        # salvo, mesmo que a pasta traga RT Images de portal.
        if not portao_ficha.e_600cd(dados):
            self.janela.caso.drrs_png = []
            self.janela.caso.drrs_titulos = []
        elif arquivado:
            rc = self.janela.caso.registro_carregado or {}
            self.janela.caso.drrs_png = [b for b in
                                   (_ler_bytes_seguro(p)
                                    for p in (rc.get("drrs_paths") or [])) if b]
            self.janela.caso.drrs_titulos = list(rc.get("drrs_titulos") or [])
        else:
            self.janela.caso.drrs_png, self.janela.caso.drrs_titulos = \
                _render_drrs_png(recursos.get("drrs"), self.planos_ds())
        recursos["drrs_png"] = self.janela.caso.drrs_png
        recursos["drrs_titulos"] = self.janela.caso.drrs_titulos
        cortes_png = dvh_png = None
        if arquivado:
            cortes_png = _ler_bytes_seguro(self.janela.caso.registro_carregado.get("imagem_path"))
            dvh_png = _ler_bytes_seguro(self.janela.caso.registro_carregado.get("dvh_path"))
            # Reusa o render da versão de origem (sliders zerados sem DICOM).
            render_meta = (self.janela.caso.registro_carregado or {}).get("render") or {}
        else:
            render_meta = _montar_render_meta(recursos)

        # Multi-plano: N cortes+DVH (individual) ou 1 combinada (soma).
        # Soma só faz sentido com DICOM; reaberto do JSON usa individual.
        multi = len(self.janela.caso.planos) >= 2
        modo_ficha = ((self.janela.caso.agendamento or {}).get("modo_ficha", "individual")
                      if (multi and not arquivado) else "individual")

        saida = self.construir_pdf(dados, plano_store, recursos, cortes_png,
                                    dvh_png, multi, arquivado, modo_ficha)
        if saida is None:
            return
        pdf_bytes = saida["pdf_bytes"]

        # Visualizar: só abre a ficha para conferência (arquivo temporário),
        # sem salvar na pasta, sem versionar o registro e sem gerar a Alta.
        if preview:
            historico.registrar("ficha_visualizada", detalhes={
                "paciente": dados.get("pac_nome", ""),
                "registro": dados.get("pac_registro", "")})
            self.janela._abrir_pdf_previa(pdf_bytes, dados, abrir=abrir)
            return

        # Caso aberto da temporária: gravar é LIBERAR, e vai para a pasta do
        # paciente. Na pasta carregada, a ficha definitiva, o registro e o
        # RTPLAN ficariam na temporária — que a automação limpa. Aqui, e não só
        # no botão da Fichinha, para valer também na Impressão da bancada.
        liberando = self.janela.caso.origem_temporaria is not None
        pasta_gravacao = self.janela.caso.pasta_carregada
        if liberando:
            if not fichinha.pode_liberar(self.janela._papel):
                ui.alertar(self.janela, "Liberação não permitida",
                           "Liberar para impressão é do físico ou do "
                           "administrador.")
                return
            pasta_gravacao = self.janela._pasta_do_paciente_para_liberar(dados)
            if not pasta_gravacao:
                return

        import datetime
        nome = registro_json.slug_nome(dados)
        data = datetime.date.today().strftime("%d-%m-%Y")
        # Prevê a versão para nomear o arquivo (ex.: ..._v2_...).
        versao_prevista = None
        if pasta_gravacao:
            try:
                versao_prevista, _n = registro_json.prever_versao(
                    pasta_gravacao, dados, rp, render_meta)
            except Exception:  # noqa: BLE001
                versao_prevista = None
        sufixo_v = f"_v{versao_prevista}" if versao_prevista else ""
        nome_arquivo = f"FICHA_{nome}{sufixo_v}_{data}.pdf"
        if pasta_gravacao:
            # Salva DIRETO na pasta do paciente (mesmo lugar do registro/zip), sem
            # diálogo "Salvar em…". A pré-visualização (botão Visualizar) é o
            # caminho para conferir antes de gerar; o nome já traz a versão
            # prevista, então regerar não sobrescreve versões anteriores.
            caminho = os.path.join(pasta_gravacao, nome_arquivo)
        else:
            # Sem pasta de origem (ex.: reaberto sem DICOM): pergunta onde salvar.
            caminho, _ = QFileDialog.getSaveFileName(
                self.janela, "Salvar ficha em PDF", nome_arquivo, "PDF (*.pdf)")
            if not caminho:
                return

        try:
            with open(caminho, "wb") as f:
                f.write(pdf_bytes)
        except OSError as exc:
            # Caminho fixo (salvamento direto): se o PDF dessa versão está aberto
            # num leitor, o arquivo fica travado (WinError 32). Avisa em vez de
            # estourar, e deixa o usuário fechar/escolher outro local.
            if not ui.confirmar(
                    self.janela, "Não foi possível salvar",
                    "A ficha não pôde ser gravada.",
                    acao="Escolher outro local", recusa="Desistir de salvar",
                    detalhe=(f"{caminho}\n\n{exc}\n\nSe o PDF já está aberto "
                             "num leitor, feche-o.")):
                return
            caminho, _ = QFileDialog.getSaveFileName(
                self.janela, "Salvar ficha em PDF", nome_arquivo, "PDF (*.pdf)")
            if not caminho:
                return
            try:
                with open(caminho, "wb") as f:
                    f.write(pdf_bytes)
            except OSError as exc2:
                ui.alertar(self.janela, "Erro ao salvar", str(exc2))
                return
        self.janela.status.showMessage(f"Ficha salva: {caminho}")
        try:
            os.startfile(caminho)
        except OSError:
            pass   # sem visualizador de PDF associado — o arquivo já está salvo

        self.salvar_alta(dados, recursos, saida["planos_pdf"], multi, modo_ficha,
                          caminho, nome, sufixo_v, data,
                          planos_ficha=(saida.get("agendamento") or {}).get("planos_ficha"),
                          arquivado=arquivado, cortes_png=cortes_png,
                          dvh_png=dvh_png)

        # Registro versionado (JSON + PNGs), salvo na pasta de origem e arquivado
        # no .zip. É o que sobra quando os DICOM são apagados.
        pasta_paciente = pasta_gravacao or os.path.dirname(caminho)
        registro_ok, registro_info = self.salvar_registro_e_arquivar(
            dados, rp, render_meta, recursos, saida, cortes_png, dvh_png,
            multi, arquivado, modo_ficha, caminho, pasta_paciente)
        # Só com o registro gravado: sem ele não há o que dizer liberado.
        if liberando and registro_ok:
            self.janela._anotar_liberacao(pasta_paciente, dados)

        # Liberando, o pós-geração é o do reaberto — só limpar da memória. O
        # "Excluir DICOM da pasta de origem" apagaria a TEMPORÁRIA, e limpá-la
        # é da automação (frente 4), não de um modal depois da impressão.
        self.fluxo_pos_geracao(arquivado or liberando, registro_ok,
                                registro_info, dados)
