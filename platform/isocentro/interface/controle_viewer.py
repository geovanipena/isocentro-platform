"""O visualizador do caso: TC, cortes, soma de dose, 3D e o estado por aba.

Saiu da ``JanelaPrincipal`` em 16/09/2026 (R-06, corte 6b do
``docs/PROPOSTA_GUI.md``). Só foi possível depois do 6a: estes métodos liam e
gravavam o estado do paciente espalhado pela janela, e agora é tudo
``janela.caso``.

O que se vê na tela é o que vai para a ficha: o corte escolhido, as estruturas
marcadas, a faixa de isodose e o 3D renderizado entram no PDF. A mudança foi
só de endereço — nenhum cálculo, render ou ordem de passo mudou.

Lê ``janela.caso`` NA HORA, nunca guarda: a limpeza troca o objeto, e um render
de ~15 s que termina depois disso tem de gravar no caso NOVO (e ser descartado
por ``corpo3d_pronto``), não no do paciente anterior.

O que continua na janela, e por quê:

- ``_tc_carregada`` e ``_plano_carregado``: são os slots da CARGA, ligados
  direto ao worker pela janela e pelo ``tools/caso.py``.
- ``_dose_prescrita``, ``_dose_prescrita_total``, ``_indices_ficha``,
  ``_agendamento_da_ficha``, ``_planos_mesma_tc``: são prescrição e agendamento,
  que a ficha também consulta; daqui são chamados pela janela.
- ``resizeEvent``: é da janela Qt; chama ``atualizar_todos_cortes``.

Dono do ``_worker_3d``: só o render 3D o usa.
"""
from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QListWidgetItem

from isocentro.desenho import corte
from isocentro.dicom import ct_series
from isocentro.dicom import dicom_rt
from isocentro.dicom import dose3d
from isocentro.interface.carregadores import _CarregarCorpo3d
from isocentro.interface.visualizador import _PainelCorte
from isocentro.papel import ficha_pdf

_LOG = logging.getLogger(__name__)

# Renders 3D mantidos em memória (5 planos × alguns ângulos). Cada PNG tem
# poucas centenas de kB e evita repetir um render de ~15 s.
_MAX_CACHE_3D = 24


def _px_copia(lbl):
    """Cópia INDEPENDENTE do pixmap de um QLabel, ou None.

    ``QLabel.pixmap()`` devolve um wrapper do pixmap interno do label; se
    guardássemos ele, um ``setPixmap`` posterior (outra aba renderizando)
    libera esse interno e a referência vira ponteiro pendente — restaurá-lo
    depois derruba o programa. ``.copy()`` desacopla e torna seguro guardar.
    """
    px = lbl.pixmap()
    return px.copy() if (px is not None and not px.isNull()) else None


def _cache_3d_valido(estado: dict, rs) -> bool:
    """True quando o 3D guardado no estado da aba é o corpo (RS) ``rs``.

    ``px_3d`` é a cópia do que estava NO PAINEL quando a aba foi deixada, que
    pode ser o 3D de outro plano ainda na tela (render de ~15 s em curso).
    Quem diz de quem é a imagem é ``png_3d_rs``, gravado junto com ela em
    ``_corpo3d_pronto`` — sem esse par, a imagem errada entra no cache da aba
    e passa a ser restaurada como se fosse dela.
    """
    px = estado.get("px_3d")
    return (rs is not None and estado.get("png_3d_rs") is rs
            and px is not None and not px.isNull())


def _chave_3d(rs, elev, azim):
    """Chave do cache de renders: corpo + ângulo (o render depende dos dois).

    Usa o SOP UID da RS quando existe — dois planos podem carregar o MESMO
    struct set como objetos distintos, e comparar por identidade re-renderiza
    à toa. Sem UID, cai para o id() do objeto (que o cache mantém vivo).

    O passo de voxel não entra: ele é função do corpo (ver
    ``corpo3d._passo_adaptativo``), e tela e ficha usam o mesmo — o render
    que está girando é exatamente o que vai para o documento.
    """
    return (dicom_rt.sop_uid(rs) or id(rs), round(elev, 1), round(azim, 1))


class ControleViewer:
    """O visualizador do caso. A janela o constrói e liga os sinais nele."""

    def __init__(self, janela):
        # A janela é o PAI do worker 3D e a dona do caso (ver a docstring do
        # módulo para o porquê de não guardar o ``Caso`` aqui).
        self.janela = janela
        self._worker_3d: Optional[_CarregarCorpo3d] = None

    def configurar_ct(self, serie: ct_series.CTSerie) -> None:
        """Ajusta os sliders dos painéis para a geometria da TC dada e abre os
        cortes no isocentro (ponto médio na soma com vários isocentros)."""
        v = self.janela.viewer
        for plano, painel in (("Axial", v.painel_axial),
                               ("Sagital", v.painel_sagital),
                               ("Coronal", v.painel_coronal)):
            n = serie.n_cortes(plano)
            painel.slider.blockSignals(True)
            painel.slider.setRange(0, max(n - 1, 0))
            painel.slider.blockSignals(False)
        self.centralizar_cortes(serie)

    def ponto_alvo_corte(self):
        """Ponto (x, y, z mm) para centrar os cortes, ou ``None`` se sem isocentro.

        Individual: o isocentro do plano ativo. Soma/personalizado com mais de um
        isocentro distinto: o ponto médio entre eles (os planos partilham a TC).
        """
        def _iso(rp):
            iso = (rp or {}).get("iso_pos_mm")
            return [float(v) for v in iso] if iso else None

        if self.janela.caso.modo_soma and self.janela.caso.indices_soma:
            pts: list = []
            for i in sorted(self.janela.caso.indices_soma):
                p = _iso(self.janela.caso.planos[i].get("rp"))
                if p is not None and not any(
                        all(abs(a - b) < 0.5 for a, b in zip(p, q)) for q in pts):
                    pts.append(p)
            if pts:
                return [sum(c) / len(pts) for c in zip(*pts)]
        return _iso(self.janela.caso.dados.get("RP"))

    def centralizar_cortes(self, serie: ct_series.CTSerie = None) -> None:
        """Posiciona os 3 sliders no ponto-alvo (isocentro / ponto médio na soma);
        sem isocentro, cai no corte central."""
        serie = serie or self.janela.caso.ct
        if serie is None:
            return
        ponto = self.ponto_alvo_corte()
        idx = serie.indices_do_ponto(ponto) if ponto is not None else None
        v = self.janela.viewer
        for plano, painel in (("Axial", v.painel_axial),
                               ("Sagital", v.painel_sagital),
                               ("Coronal", v.painel_coronal)):
            if painel.slider is None:
                continue
            valor = idx[plano] if idx is not None else serie.indice_central(plano)
            painel.slider.blockSignals(True)
            painel.slider.setValue(valor)
            painel.slider.blockSignals(False)

    def limpar_cortes(self) -> None:
        """Limpa os painéis de corte (usado ao ativar um plano sem TC)."""
        v = self.janela.viewer
        for painel in (v.painel_axial, v.painel_sagital, v.painel_coronal):
            painel.lbl_img.clear()
            painel.lbl_img.setText(painel.lbl_titulo.text())
            if painel.slider is not None:
                painel.slider.blockSignals(True)
                painel.slider.setRange(0, 0)
                painel.slider.setValue(0)
                painel.slider.blockSignals(False)

    def dose_iso_cgy(self) -> tuple:
        """``(100%, ponto quente)`` em cGy, para a faixa de isodose em dose absoluta.

        O 100% é a prescrição (a do plano ativo, ou a SOMA delas na visão
        combinada). O ponto quente sai da própria grade já normalizada. É
        chamado só quando a faixa está (ou vai ficar) em cGy: num RT Dose grande
        a primeira leitura da grade decodifica os pixels.
        """
        if self.janela.caso.modo_soma and self.janela.caso.dose_soma is not None:
            ref_gy = self.janela._dose_prescrita_total(sorted(self.janela.caso.indices_soma))
            grade = self.janela.caso.dose_soma
        else:
            ref_gy = self.janela._dose_prescrita(self.janela.caso.plano_ativo)
            grade = (ct_series._dose_pct_grade(self.janela.caso.rd, ref_gy)
                     if self.janela.caso.rd is not None else None)
        ref_cgy = float(ref_gy or 0) * 100.0
        return ref_cgy, ref_cgy * ct_series.maximo_pct(grade) / 100.0

    def sincronizar_dose_iso(self) -> None:
        """Reavalia a faixa de isodose para o plano/modo atual.

        Vale nas duas unidades: o topo da faixa é o ponto quente, e ele muda com
        o plano. Chamado ANTES de restaurar o estado da aba, para a escolha que
        o usuário já tinha feito nela continuar valendo."""
        try:
            self.janela.viewer.definir_dose_iso(*self.dose_iso_cgy())
        except Exception:  # noqa: BLE001 — sem dose legível, a faixa fica como está
            _LOG.exception("Faixa de isodose: dose de referência ilegível")

    def recalcular_soma(self) -> None:
        """Recalcula a dose combinada (soma/personalizado) e reaplica a visão.

        Guarda quais planos entram na combinação (``caso.indices_soma``) e a dose/RS
        combinadas. A visão SOMA só aparece nas abas dos planos que fazem parte
        da combinação; um plano de fora (ex.: em outra TC) mostra a sua própria
        dose. Quem decide isso por aba é ``ativar_plano``.

        Só REPOVOA as estruturas e recentra os cortes quando a combinação muda de
        verdade. Reabrir o agendamento e Aplicar sem mexer nos planos combinados
        recentrava os cortes no isocentro, jogando fora o corte que o usuário
        tinha escolhido — e a ficha saía com o corte do isocentro.
        """
        ant_indices = set(self.janela.caso.indices_soma)
        ant_rs = self.janela.caso.rs_soma
        self.janela.caso.dose_soma = None
        self.janela.caso.rs_soma = None
        self.janela.caso.indices_soma = set()
        ag_info = self.janela.caso.agendamento or {}
        modo = ag_info.get("modo_ficha", "individual")
        # Índices dos planos que compõem a visão combinada: todos (soma) ou o
        # subconjunto escolhido (personalizado). A geometria comum é exigida só
        # do subconjunto — no personalizado dá para combinar os planos de UMA
        # das TCs mesmo quando há mais de uma tomografia carregada.
        if modo == "soma":
            # "Todos" = todos os que ENTRAM na ficha (ver Separar Ficha).
            indices = self.janela._indices_ficha()
        elif modo == "personalizado":
            indices = [i for i in (ag_info.get("planos_ficha") or [])
                       if 0 <= i < len(self.janela.caso.planos)]
        else:
            indices = []
        if len(indices) >= 2 and self.janela._planos_mesma_tc(indices):
            rds = [self.janela.caso.planos[i]["rd_ds"] for i in indices
                   if self.janela.caso.planos[i].get("rd_ds") is not None]
            if len(rds) >= 2:
                try:
                    # 100% da dose combinada = soma das prescrições combinadas.
                    self.janela.caso.dose_soma = ct_series.tupla_dose(
                        dose3d.somar_rds(rds),
                        dose_ref=self.janela._dose_prescrita_total(indices))
                except Exception as exc:  # noqa: BLE001
                    self.janela.status.showMessage(f"Soma de dose falhou: {exc}", 6000)
                if self.janela.caso.dose_soma is not None:
                    self.janela.caso.indices_soma = set(indices)
                    # Estrutura unificada: usa o conjunto mais rico (na mesma TC,
                    # em geral os planos compartilham a mesma RS).
                    rss = [self.janela.caso.planos[i]["rs_ds"] for i in indices
                           if self.janela.caso.planos[i].get("rs_ds") is not None]
                    self.janela.caso.rs_soma = (max(rss, key=lambda r: len(self.nomes_estruturas(r)))
                                     if rss else None)
        # Combinação nova (outros planos ou outro corpo) → ativar_plano repovoa
        # as estruturas e recentra os cortes. Combinação igual → mantém o que
        # está na tela, inclusive os cortes escolhidos.
        if self.janela.caso.indices_soma != ant_indices or self.janela.caso.rs_soma is not ant_rs:
            self.janela.caso.rs_estruturas = None
        # Reaplica a visão do plano ativo (soma se ele entra na combinação,
        # individual caso contrário).
        self.ativar_plano(self.janela.caso.plano_ativo)

    def limpar_painel_3d(self, texto: str = "3D CORPO") -> None:
        """Apaga o 3D do painel — usado quando o que está na tela é de outro corpo."""
        p3d = self.janela.viewer.painel_3d
        p3d.lbl_img.clear()
        p3d.lbl_img.setText(texto)

    def capturar_estado(self) -> dict:
        """Fotografa a escolha atual do viewer (controles + imagens já rendidas).

        Guardado por plano para restaurar sem re-renderizar ao voltar à aba.
        """
        v = self.janela.viewer
        return {
            "janela": v.cmb_janela.currentText(),
            "estruturas_on": v.chk_estruturas.isChecked(),
            "isodose_on": v.chk_isodose.isChecked(),
            # Guardado em % (não no que está na tela): é a unidade canônica, e a
            # mesma dose absoluta significa outra coisa em cada prescrição.
            "iso_pct": v.faixa_isodose_pct(),
            "nomes": [v.lst_estruturas.item(i).text()
                      for i in range(v.lst_estruturas.count())],
            "selecionadas": set(v.estruturas_selecionadas),
            "idx_axial": v.painel_axial.slider.value(),
            "idx_sagital": v.painel_sagital.slider.value(),
            "idx_coronal": v.painel_coronal.slider.value(),
            "px_axial": _px_copia(v.painel_axial.lbl_img),
            "px_sagital": _px_copia(v.painel_sagital.lbl_img),
            "px_coronal": _px_copia(v.painel_coronal.lbl_img),
            "px_3d": _px_copia(v.painel_3d.lbl_img),
            "png_3d": self.janela.caso.png_3d,
            "png_3d_rs": self.janela.caso.png_3d_rs,   # a qual corpo (RS) este 3D corresponde
            "elev": getattr(v.painel_3d, "_elev", 10),
            "azim": getattr(v.painel_3d, "_azim", -30),
        }

    def restaurar_estado(self, e: dict) -> None:
        """Reaplica um estado salvo SEM disparar render — usa as imagens do cache."""
        v = self.janela.viewer
        controles = (v.cmb_janela, v.chk_estruturas, v.chk_isodose,
                     v.spn_iso_min, v.spn_iso_max, v.lst_estruturas)
        for w in controles:
            w.blockSignals(True)
        v.cmb_janela.setCurrentText(e["janela"])
        v.chk_estruturas.setChecked(e["estruturas_on"])
        v.chk_isodose.setChecked(e["isodose_on"])
        v.definir_faixa_pct(*e.get("iso_pct", (50.0, 100.0)))
        v.lst_estruturas.clear()
        for nome in e["nomes"]:
            item = QListWidgetItem(nome)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if nome in e["selecionadas"] else Qt.Unchecked)
            v.lst_estruturas.addItem(item)
        for w in controles:
            w.blockSignals(False)
        for painel, kidx, kpx in (
                (v.painel_axial, "idx_axial", "px_axial"),
                (v.painel_sagital, "idx_sagital", "px_sagital"),
                (v.painel_coronal, "idx_coronal", "px_coronal")):
            painel.slider.blockSignals(True)
            painel.slider.setValue(e[kidx])
            painel.slider.blockSignals(False)
            px = e.get(kpx)
            if px is not None and not px.isNull():
                painel.lbl_img.setPixmap(px)
        v.painel_3d._elev = e["elev"]
        v.painel_3d._azim = e["azim"]
        self.janela.caso.png_3d = e.get("png_3d")
        self.janela.caso.png_3d_rs = e.get("png_3d_rs")
        # 3D: só reexibe o do cache quando ele é DESTE corpo. Não sendo, apaga o
        # painel — deixar o anterior mostraria a anatomia de outro plano (uma
        # cabeça na aba do fígado) como se fosse desta aba.
        if _cache_3d_valido(e, self.janela.caso.rs):
            v.painel_3d.lbl_img.setPixmap(e["px_3d"])
            self.janela.caso.rs_3d = self.janela.caso.rs
        else:
            self.limpar_painel_3d()

    def reordenar_planos_estado(self, de: int, para: int) -> None:
        """Espelha nos estados por ÍNDICE a nova ordem das abas — para dose/RD/RS/
        cortes/alta/PDF seguirem a ordem escolhida. Remapeia self.janela.caso.planos e o plano
        ativo; sem isto, a aba movia mas o PDF pareava a dose de um plano com o
        formulário de outro.

        O agendamento é DESCARTADO: ele guarda índices de plano
        (``etapas[].planos``, ``planos_ficha``), que passam a apontar para outro
        plano depois da troca. Em vez de remapear em silêncio — o que mudaria a
        sequência de frações sem o usuário ver —, o diálogo reabre já na ordem
        nova para ele refazer/conferir. A visão SOMA cai junto e volta quando o
        modo for reescolhido.
        """
        n = len(self.janela.caso.planos)
        if not (0 <= de < n and 0 <= para < n) or de == para:
            return

        def _novo(x: int) -> int:
            """Índice ``x`` depois de mover ``de`` → ``para`` (semântica do Qt)."""
            if x == de:
                return para
            if de < x <= para:
                return x - 1
            if para <= x < de:
                return x + 1
            return x

        self.janela.caso.planos.insert(para, self.janela.caso.planos.pop(de))
        self.janela.caso.plano_ativo = _novo(self.janela.caso.plano_ativo)
        self.janela.caso.agendamento = None
        self.recalcular_soma()     # sem agendamento → individual; refaz a visão
        self.janela._atualizar_btn_pdf()   # multi-plano sem agendamento trava a ficha
        if n >= 2:
            self.janela.status.showMessage(
                "Ordem dos planos alterada — refaça o agendamento.", 6000)
            # Fora do tratamento do arrastar: abrir um modal dentro do slot de
            # tabMoved reentraria no evento do mouse (a aba fica presa ao cursor).
            # O respiro (150 ms) + fade-in dão uma entrada suave, sem o modal
            # saltar no instante em que o usuário solta a aba.
            QTimer.singleShot(150, lambda: self.janela._abrir_agendamento(suave=True))

    def ativar_plano(self, indice: int) -> None:
        """Torna o plano ``indice`` o ativo: sincroniza RP/RS/RD, viewer e form.

        Ponte de compatibilidade: o restante do programa (geração, cortes, SSD)
        continua operando sobre ``self.janela.caso.dados['RP']`` / ``self.janela.caso.rs`` / ``self.janela.caso.rd``,
        que aqui apontam para o plano ativo.

        No modo INDIVIDUAL cada aba tem o seu viewer próprio: ao sair, o estado
        (cortes, estruturas marcadas, 3D, janela, isodose) é guardado; ao voltar,
        é restaurado do cache, sem re-renderizar.
        """
        if not (0 <= indice < len(self.janela.caso.planos)):
            return
        anterior = self.janela.caso.plano_ativo
        if (not self.janela.caso.modo_soma and 0 <= anterior < len(self.janela.caso.planos)
                and anterior != indice):
            self.janela.caso.planos[anterior]["viewer_state"] = self.capturar_estado()
        self.janela.caso.plano_ativo = indice
        p = self.janela.caso.planos[indice]
        self.janela.caso.dados["RP"] = p["rp"]
        self.janela.caso.rs = p["rs_ds"]
        self.janela.caso.rd = p["rd_ds"]
        # A visão combinada vale só se ESTE plano faz parte da combinação. Um
        # plano de fora (ex.: outra TC) volta ao individual e mostra a sua dose.
        self.janela.caso.modo_soma = (self.janela.caso.dose_soma is not None
                           and indice in self.janela.caso.indices_soma)
        # Outro plano, outra dose: reavalia a faixa de isodose ANTES de
        # restaurar a aba — assim o estado salvo dela vence, e uma aba nova
        # nasce com a faixa do plano dela (50% até o ponto quente).
        self.sincronizar_dose_iso()
        # Troca a tomografia ativa (2 TCs no mesmo paciente).
        ct_plano = p.get("ct")
        if ct_plano is not None:
            if ct_plano is not self.janela.caso.ct:
                self.janela.caso.ct = ct_plano
                self.configurar_ct(ct_plano)
        elif self.janela.caso.ct is not None and not self.janela.caso.modo_soma:
            # Plano sem TC associada: não herda a TC do plano anterior.
            self.janela.caso.ct = None
            self.limpar_cortes()
        if self.janela.caso.modo_soma:
            # Visão combinada: dose somada + estruturas unificadas, sincronizada
            # entre as abas combinadas. Só repovoa (resetando a seleção) quando
            # o corpo (RS) muda — igual ao 3D —, senão trocar de aba preservava
            # o 3D mas zerava as estruturas marcadas.
            if self.janela.caso.rs_soma is not None:
                if self.janela.caso.rs_soma is not self.janela.caso.rs_estruturas:
                    self.janela.viewer.popular_estruturas(self.nomes_estruturas(self.janela.caso.rs_soma))
                    self.janela.caso.rs_estruturas = self.janela.caso.rs_soma
                    self.centralizar_cortes()   # visão combinada nova → ponto médio
                self.render_3d_se_mudou(self.janela.caso.rs_soma)
            estado = None
        else:
            # Individual: restaura a escolha desta aba do cache, ou renderiza.
            estado = p.get("viewer_state")
            if estado is not None:
                # restaurar_estado só assume caso.rs_3d quando o 3D do cache
                # é mesmo deste corpo; não sendo, o painel fica vazio e a chamada
                # abaixo renderiza — antes a aba herdava o 3D do plano anterior
                # e nunca re-renderizava, porque caso.rs_3d era atribuído aqui de
                # qualquer jeito.
                self.restaurar_estado(estado)
                self.janela.caso.rs_estruturas = self.janela.caso.rs
                self.render_3d_se_mudou(self.janela.caso.rs)
            else:
                # Primeira vez nesta aba: abre os cortes no isocentro do plano.
                self.centralizar_cortes()
                if self.janela.caso.rs is not None:
                    self.janela.viewer.popular_estruturas(self.nomes_estruturas(self.janela.caso.rs))
                    self.janela.caso.rs_estruturas = self.janela.caso.rs
                    self.render_3d_se_mudou(self.janela.caso.rs)
        # Sincroniza a aba visível sem re-disparar a troca de plano.
        self.janela.form.abas.blockSignals(True)
        self.janela.form.abas.setCurrentIndex(indice)
        self.janela.form.abas.blockSignals(False)
        if self.janela.caso.ct is not None and (self.janela.caso.modo_soma or estado is None):
            self.atualizar_todos_cortes()
        self.recalcular_ssds()

    def recalcular_ssds(self) -> None:
        """Calcula/recalcula os SSDs usando RS e/ou CT e atualiza rp_info."""
        rp = self.janela.caso.dados.get("RP", {})
        if not rp.get("iso_pos_mm"):
            return
        try:
            dicom_rt.aplicar_ssds(rp, rs_ds=self.janela.caso.rs, ct_serie=self.janela.caso.ct)
        except Exception as exc:
            self.janela.status.showMessage(f"Aviso: SSD não calculado ({exc})", 6000)

    def nomes_estruturas(self, rs) -> list:
        """Estruturas que a tela lista (e, por tabela, desenha nos cortes).

        Fora: o contorno externo, o que ``estrutura_oculta`` remove e o que não é
        paciente (mesa e pontos de referência — ver ``TIPOS_NAO_PACIENTE``)."""
        from isocentro.dicom.ct_series import _contornos_por_roi
        return [
            r["nome"] for r in _contornos_por_roi(rs).values()
            if r["tipo"] != "EXTERNAL" and r["contornos"]
            and str(r["tipo"]).upper() not in ficha_pdf.TIPOS_NAO_PACIENTE
            and not ficha_pdf.estrutura_oculta(r["nome"])
        ]

    def render_3d_se_mudou(self, rs) -> None:
        """Re-renderiza o 3D só quando o corpo (RS) muda.

        O 3D é o mesmo para todos os planos que compartilham a RS, então trocar
        de aba entre eles não precisa re-renderizar (o render leva ~15 s). Muda
        só ao passar para um plano de outra tomografia/RS.
        """
        if rs is not None and rs is not self.janela.caso.rs_3d:
            self.renderizar_3d(rs)

    def renderizar_3d(self, rs):
        self.janela.caso.rs_3d = rs
        p3d = self.janela.viewer.painel_3d
        elev = getattr(p3d, "_elev", 10)
        azim = getattr(p3d, "_azim", -30)
        pronto = self.janela.caso.cache_3d.get(_chave_3d(rs, elev, azim))
        if pronto is not None:      # este corpo/ângulo já foi renderizado
            self.corpo3d_pronto(pronto[1], rs)
            return
        p3d.lbl_titulo.setText("3D CORPO  (renderizando…)")
        # Corpo diferente do que está na tela: apaga antes de começar. Os ~15 s de
        # render mostrando o corpo do plano anterior sob o rótulo "renderizando…"
        # passam por 3D deste plano. Em re-render de ÂNGULO o corpo é o mesmo, e
        # aí manter a imagem antiga é melhor que piscar o painel vazio.
        if rs is not self.janela.caso.png_3d_rs:
            self.limpar_painel_3d("renderizando…")
        self._worker_3d = _CarregarCorpo3d(rs, elev=elev, azim=azim, parent=self.janela)
        self._worker_3d.concluido.connect(
            lambda png, rs=rs, e=elev, a=azim: self.corpo3d_pronto(png, rs, e, a))
        self._worker_3d.start()

    def rerender_3d_angulo(self):
        rs = self.janela.caso.rs_soma if self.janela.caso.modo_soma else self.janela.caso.rs
        if rs is not None:
            self.renderizar_3d(rs)

    def corpo3d_pronto(self, png: bytes, rs=None, elev=None, azim=None):
        # GUARDA o render antes de qualquer descarte: ele custou ~15 s e vale
        # para este corpo/ângulo independentemente da aba em que o usuário está
        # agora. Antes, sair da aba durante o render jogava o resultado fora e a
        # volta recomeçava do zero — dava a impressão de renderizar sempre.
        if rs is not None and elev is not None:
            chave = _chave_3d(rs, elev, azim)
            if chave not in self.janela.caso.cache_3d:
                if len(self.janela.caso.cache_3d) >= _MAX_CACHE_3D:
                    self.janela.caso.cache_3d.pop(next(iter(self.janela.caso.cache_3d)))
                self.janela.caso.cache_3d[chave] = (rs, png)   # guarda a RS: mantém id() vivo
        # Só EXIBIR é condicional: um render que terminou depois de o usuário
        # trocar de plano não pode sobrescrever o 3D da aba atual (na tela nem em
        # caso.png_3d, usado na ficha).
        if rs is not None and rs is not self.janela.caso.rs_3d:
            return
        self.janela.caso.png_3d = png
        self.janela.caso.png_3d_rs = rs          # o 3D em cache passa a ser DESTE corpo
        painel = self.janela.viewer.painel_3d
        painel.lbl_titulo.setText("3D CORPO")
        pix = QPixmap()
        pix.loadFromData(png)
        sz = painel.lbl_img.size()
        pix = pix.scaled(sz, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        painel.lbl_img.setPixmap(pix)

    def marcar_estruturas(self, estado) -> None:
        lst = self.janela.viewer.lst_estruturas
        lst.blockSignals(True)
        for i in range(lst.count()):
            lst.item(i).setCheckState(estado)
        lst.blockSignals(False)
        self.atualizar_todos_cortes()

    def renderizar_painel(self, painel: _PainelCorte, plano: str, idx: int):
        if self.janela.caso.ct is None:
            return
        v = self.janela.viewer
        janela = v.cmb_janela.currentText()
        mostrar = v.chk_estruturas.isChecked()
        mostrar_iso = v.chk_isodose.isChecked()
        iso_range = v.faixa_isodose_pct()   # o colorwash sempre em %
        # Visão SOMA: dose combinada (dose_grade) + estruturas unificadas.
        if self.janela.caso.modo_soma and self.janela.caso.dose_soma is not None:
            rs_use, rd_use, dose_grade = self.janela.caso.rs_soma, None, self.janela.caso.dose_soma
        else:
            rs_use, rd_use, dose_grade = self.janela.caso.rs, self.janela.caso.rd, None
        estruturas_vis = v.estruturas_selecionadas if rs_use is not None else None
        try:
            png = corte.renderizar_corte(self.janela.caso.ct, plano, idx, janela=janela, rs=rs_use,
                                         mostrar_estruturas=mostrar,
                                         rd=rd_use, mostrar_isodose=mostrar_iso,
                                         estruturas_visiveis=estruturas_vis,
                                         isodose_range=iso_range, dose_grade=dose_grade,
                                         # 100% = prescrição do plano (a dose_grade da
                                         # soma já vem normalizada pela soma delas).
                                         dose_ref=self.janela._dose_prescrita(self.janela.caso.plano_ativo),
                                         fundo=0)   # preto no app (o PDF usa branco)
            pix = QPixmap()
            pix.loadFromData(png)
            sz = painel.lbl_img.size()
            pix = pix.scaled(sz, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            painel.lbl_img.setPixmap(pix)
        except Exception as exc:  # noqa: BLE001
            self.janela.status.showMessage(f"Erro ao renderizar {plano}: {exc}")

    def atualizar_todos_cortes(self, *_):
        if self.janela.caso.ct is None:
            return
        v = self.janela.viewer
        for plano, painel in (("Axial", v.painel_axial),
                               ("Sagital", v.painel_sagital),
                               ("Coronal", v.painel_coronal)):
            idx = painel.slider.value()
            self.renderizar_painel(painel, plano, idx)
