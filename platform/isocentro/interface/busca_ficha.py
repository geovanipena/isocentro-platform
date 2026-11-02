"""Achar um paciente no índice, e o que se faz com a ficha dele.

Separado de ``gui.py`` em 31/08/2026, a última fatia da divisão começada em
27/08. As duas classes andam juntas porque ``AcoesDeFicha`` é mixin das duas
telas que abrem uma ficha pronta: a ``JanelaPrincipal`` e o próprio
``DialogBuscaPacientes``.

Não confundir com o ``DialogEscolherPaciente``, que ficou no ``gui.py``: aquele
pergunta de quem é uma PASTA que acabou de ser apontada, e vive colado ao
``_carregar_pasta``. Este aqui busca no índice central o que já foi gerado.

``_limpar_temp_zip`` veio junto porque ``AcoesDeFicha`` o usa em dois pontos —
a ``JanelaPrincipal`` também, e por isso o ``gui.py`` o reimporta.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QHBoxLayout, QHeaderView,
    QInputDialog, QLabel, QLineEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QTextBrowser, QVBoxLayout)

from isocentro.dominio import constantes
from isocentro.dados import diff_versoes
from isocentro.interface import estilo
from isocentro.papel import ficha_pdf
from isocentro.dados import historico
from isocentro.dados import indice
from isocentro.dados import registro_json
from isocentro.interface import ui


# ── Ações sobre uma ficha já gerada ──────────────────────────────────────────


class AcoesDeFicha:
    """Carregar, comparar versões, abrir o PDF e abrir a pasta de uma ficha.

    Nasceram dentro da tela de **Histórico**, que era o único lugar de onde se
    voltava a uma ficha antiga. Saíram para cá quando a lista "Suas últimas
    fichas" da Fichinha passou a oferecer as mesmas quatro ações: cada uma
    carrega detalhe que não se reescreve por engano — a versão a escolher, o
    JSON que pode estar solto ou dentro do ``.zip``, o PDF que sumiu e precisa
    ser regerado do registro. Duas cópias disso divergiriam no primeiro
    conserto.

    Mistura-se a um ``QWidget`` (é dele que saem as caixas de diálogo) e opera
    sempre sobre uma **linha do índice central** — o dicionário que
    ``indice.buscar``/``listar_versoes`` devolve, com ``registro``, ``versao``,
    ``json_path`` e ``pdf_path``. Quem chama é que sabe como o usuário escolheu
    essa linha; aqui ela já chega escolhida.

    Dois ganchos ajustam o comportamento ao hospedeiro:
    ``_janela_ficha`` (quem sabe carregar um registro) e ``_apos_carregar``
    (o que fazer depois — a tela de Histórico se fecha, a Fichinha fica).
    """

    # ── Ganchos ──────────────────────────────────────────────────────────
    def _janela_ficha(self):
        """A ``JanelaPrincipal``. Num diálogo, é o pai; nela mesma, ela."""
        return self.parent()

    def _apos_carregar(self) -> None:
        """Chamado depois de um carregamento bem-sucedido."""

    # ── Auxiliares ───────────────────────────────────────────────────────
    def _escolher_versao(self, registro: str) -> dict | None:
        """Retorna a linha de índice da versão escolhida (última por padrão)."""
        versoes = indice.listar_versoes(registro)
        if not versoes:
            return None
        if len(versoes) == 1:
            return versoes[0]
        itens = [
            f"v{v['versao']} — {v.get('data', '')} — "
            f"{v.get('dose_total', '')} Gy / {v.get('num_fracoes', '')} fx"
            for v in versoes
        ]
        item, ok = QInputDialog.getItem(
            self, "Escolher versão",
            f"Registro {registro} — qual versão regerar?", itens, 0, False)
        if not ok:
            return None
        return versoes[itens.index(item)]

    @staticmethod
    def _abrir_arquivo(caminho: str):
        try:
            os.startfile(caminho)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Não foi possível abrir '{caminho}': {exc}") from exc

    @staticmethod
    def _dados_min(escolha: dict) -> dict:
        """Mínimo p/ localizar os arquivos do paciente (nome + registro)."""
        return {"pac_nome": escolha.get("nome") or "",
                "pac_registro": escolha.get("registro") or ""}

    def _preparar_leitura(self, escolha: dict) -> tuple[str, str, Optional[str]]:
        """Devolve ``(pasta_real, pasta_leitura, tmp)``.

        Se o JSON/PNGs soltos foram arquivados no zip do paciente, extrai o zip
        para uma pasta temporária NOVA e a usa como ``pasta_leitura`` (os arquivos
        voltam a existir soltos ali); ``tmp`` é essa pasta — quem chamou é dono
        dela e deve limpá-la (ou repassar a posse). Sem zip, ``tmp`` é None e as
        duas pastas coincidem. A ``pasta_real`` é sempre a de origem (destino de
        uma regeração)."""
        jp = escolha.get("json_path") or ""
        pasta_real = os.path.dirname(jp)
        if jp and os.path.exists(jp):
            return pasta_real, pasta_real, None
        import tempfile
        tmp = tempfile.mkdtemp(prefix="ficha_zip_")
        if registro_json.extrair_zip(pasta_real, self._dados_min(escolha), tmp):
            return pasta_real, tmp, tmp
        _limpar_temp_zip(tmp)
        return pasta_real, pasta_real, None

    def _ler_versao(self, escolha: dict) -> dict | None:
        """Devolve a entrada da versão escolhida, lendo o JSON solto ou do zip."""
        pasta = os.path.dirname(escolha.get("json_path") or "")
        reg = registro_json.carregar_registro_pasta(pasta, self._dados_min(escolha))
        if reg is None:
            ui.alertar(
                self, "Registro não encontrado",
                f"Não foi possível ler o registro do paciente em:\n{pasta}\n\n"
                "A pasta pode ter sido movida ou o arquivo .zip removido.")
            return None
        try:
            return next(v for v in reg.get("versoes", [])
                        if v.get("versao") == escolha["versao"])
        except StopIteration:
            ui.falhar(self, "Versão não encontrada",
                                 "A versão selecionada não existe no registro.")
            return None
        except Exception as exc:  # noqa: BLE001 — registro malformado, não derruba
            ui.falhar(self, "Erro ao ler registro", str(exc))
            return None

    @staticmethod
    def ficha_tem_versoes(registro: str) -> int:
        """Quantas versões o paciente tem no índice (0 se não estiver lá).

        É o que decide se "Verificar versão" faz sentido: comparar uma versão
        com ela mesma não é uma ação, é um recado — e botão que só sabe dizer
        "não há o que comparar" gasta um clique para nada.
        """
        try:
            return len(indice.listar_versoes(registro or ""))
        except Exception:  # noqa: BLE001
            return 0

    # ── Ações ────────────────────────────────────────────────────────────
    # Todas devolvem se DERAM CERTO. Quem chama de uma tela com linha de
    # status precisa disso para não anunciar "pasta aberta" logo depois de a
    # ação ter avisado que a pasta sumiu.

    def ficha_abrir_pasta(self, r: dict) -> bool:
        """Abre no Explorer a pasta que contém os arquivos do paciente."""
        pasta = os.path.dirname(r.get("json_path") or "") or (r.get("pasta") or "")
        if not pasta or not os.path.isdir(pasta):
            ui.alertar(
                self, "Pasta não encontrada",
                f"A pasta do paciente não foi localizada:\n{pasta or '(vazio)'}\n\n"
                "Ela pode ter sido movida ou renomeada.")
            return False
        try:
            self._abrir_arquivo(pasta)
        except RuntimeError as exc:
            ui.alertar(self, "Erro ao abrir", str(exc))
            return False
        return True

    def ficha_verificar_versao(self, r: dict) -> bool:
        """Mostra as diferenças entre as versões do paciente selecionado."""
        pasta = os.path.dirname(r.get("json_path") or "")
        reg = registro_json.carregar_registro_pasta(pasta, self._dados_min(r))
        if reg is None:
            ui.alertar(
                self, "Registro não encontrado",
                f"Não foi possível ler o registro do paciente em:\n{pasta}\n\n"
                "A pasta pode ter sido movida ou o arquivo .zip removido.")
            return False
        versoes = sorted((reg.get("versoes") or []),
                         key=lambda v: v.get("versao") or 0)
        if len(versoes) < 2:
            ui.avisar(
                self, "Uma única versão",
                f"{r.get('nome') or 'Este paciente'} tem apenas uma versão — "
                "não há o que comparar.")
            return False

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Diferenças entre versões — {r.get('nome') or ''}".strip())
        dlg.resize(640, 520)
        lay = QVBoxLayout(dlg)
        cab = QLabel(f"<b>{r.get('nome') or ''}</b> &nbsp; (registro {r.get('registro') or '—'}) "
                     f"— {len(versoes)} versões")
        lay.addWidget(cab)
        navegador = QTextBrowser()
        navegador.setHtml(diff_versoes.html_diff(versoes))
        lay.addWidget(navegador, 1)
        btn = QPushButton("Fechar")
        estilo.pintar(btn, lambda: estilo.btn_solido(12.5))
        btn.clicked.connect(dlg.accept)
        linha = QHBoxLayout(); linha.addStretch(); linha.addWidget(btn)
        lay.addLayout(linha)
        dlg.exec()
        return True

    def ficha_carregar(self, r: dict) -> bool:
        """Carrega o registro (JSON) de volta no programa para ver/editar/regerar."""
        escolha = self._escolher_versao(r["registro"])
        if not escolha:
            return False
        ver = self._ler_versao(escolha)
        if ver is None:
            return False
        janela = self._janela_ficha()
        if janela is None or not hasattr(janela, "carregar_registro"):
            ui.alertar(self, "Indisponível",
                                "Não foi possível acessar a janela principal.")
            return False
        # Os PNGs podem estar soltos (pasta real) ou dentro do zip (extraídos p/
        # um temp). A pasta de origem vai como 'pasta' (destino de uma regeração);
        # a posse do temp passa à janela principal (limpo ao trocar/limpar).
        pasta_real, _leitura, tmp = self._preparar_leitura(escolha)

        def _p(nome_ou_caminho: str) -> str:
            base = os.path.basename(nome_ou_caminho)
            return os.path.join(_leitura, base) if base else ""

        imagens_paths = [_p(nm) for nm in (ver.get("imagens") or [])]
        dvhs_paths = [_p(nm) if nm else "" for nm in (ver.get("dvhs") or [])]
        # DRRs: lista nova ('drrs'); registros antigos usam drr_ap/drr_lateral.
        _drr_nomes = ver.get("drrs") or [n for n in (ver.get("drr_ap"),
                                                     ver.get("drr_lateral")) if n]
        drrs_paths = [_p(nm) for nm in _drr_nomes]
        janela.carregar_registro(
            ver.get("dados", {}), ver.get("plano_rp", {}), pasta_real,
            _p(escolha.get("imagem_path") or ""), _p(escolha.get("dvh_path") or ""),
            ver.get("render") or {}, planos=ver.get("planos"),
            imagens_paths=imagens_paths, dvhs_paths=dvhs_paths,
            agendamento=ver.get("agendamento"), tmp_extraido=tmp,
            drrs_paths=drrs_paths, drrs_titulos=ver.get("drrs_titulos") or [])
        historico.registrar("tratamento_reaberto", detalhes={
            "paciente": r.get("nome", ""), "registro": r.get("registro", ""),
            "versao": escolha.get("versao")})
        self._apos_carregar()
        return True

    def ficha_abrir_pdf(self, r: dict) -> bool:
        """Abre o PDF da ficha diretamente; regenera do JSON se o original sumiu."""
        escolha = self._escolher_versao(r["registro"])
        if not escolha:
            return False
        pdf_path = escolha.get("pdf_path")
        if pdf_path and os.path.exists(pdf_path):
            try:
                self._abrir_arquivo(pdf_path)
            except RuntimeError as exc:
                ui.alertar(self, "Erro ao abrir", str(exc))
                return False
            return True
        # Fallback: regenera a ficha a partir do registro JSON.
        ver = self._ler_versao(escolha)
        if ver is None:
            return False
        # PNGs soltos ou dentro do zip (extraídos p/ um temp). Este fluxo usa o
        # temp só para ler os bytes agora, então limpa-o em seguida (não fica
        # carregado na janela como no ficha_carregar).
        _pasta_real, _leitura, tmp = self._preparar_leitura(escolha)

        def _ler(caminho):
            base = os.path.basename(caminho or "")
            p = os.path.join(_leitura, base) if base else ""
            if p and os.path.exists(p):
                try:
                    return Path(p).read_bytes()
                except Exception:  # noqa: BLE001
                    return None
            return None

        try:
            imagem_png = _ler(escolha.get("imagem_path"))
            dvh_png = _ler(escolha.get("dvh_path"))
            # DRRs: lista nova ('drrs'); antigos usam drr_ap/drr_lateral.
            _drr_nomes = ver.get("drrs") or [n for n in (ver.get("drr_ap"),
                                                         ver.get("drr_lateral")) if n]
            drrs_png = [b for b in (_ler(nm) for nm in _drr_nomes) if b]
        finally:
            _limpar_temp_zip(tmp)
        _ag = ver.get("agendamento") or {}
        try:
            pdf = ficha_pdf.gerar_ficha_arquivada(
                ver.get("dados", {}), {"RP": ver.get("plano_rp", {})},
                imagem_png, dvh_png, drrs_png=drrs_png,
                drrs_titulos=ver.get("drrs_titulos") or [],
                replan=_ag.get("replan_fracoes") or 0,
                dose_replan=_ag.get("replan_dose") or 0)
        except Exception as exc:  # noqa: BLE001
            ui.falhar(self, "Erro ao gerar PDF", str(exc))
            return False
        import tempfile
        destino = os.path.join(
            tempfile.gettempdir(),
            f"ficha_{escolha['registro']}_v{escolha['versao']}.pdf")
        try:
            Path(destino).write_bytes(pdf)
            ui.avisar(
                self, "Ficha regerada",
                "O PDF original não foi encontrado; uma cópia foi regerada a "
                "partir do registro JSON.")
            self._abrir_arquivo(destino)
        except (OSError, RuntimeError) as exc:
            ui.falhar(self, "Erro", str(exc))
            return False
        return True


def _limpar_temp_zip(caminho: Optional[str]) -> None:
    """Remove uma pasta de extração temporária, se existir (nunca levanta)."""
    if caminho and os.path.isdir(caminho):
        import shutil
        shutil.rmtree(caminho, ignore_errors=True)


# ── Diálogo de busca de pacientes ────────────────────────────────────────────


class DialogBuscaPacientes(AcoesDeFicha, ui.Dialogo):
    """Busca pacientes no índice central e regera a ficha a partir do JSON."""

    _COLS = ["Nome", "Registro", "Última ficha", "Versões",
             "Máquina", "Médico", "Dose × Fr"]

    def __init__(self, parent=None):
        super().__init__("Histórico", parent, 920, 520)
        lay = self.corpo

        topo = QHBoxLayout()
        topo.addWidget(QLabel("Filtrar por:"))
        self.filtro_campo = QComboBox()
        for rotulo, chave in (("Tudo", "tudo"), ("Nome", "nome"),
                              ("Registro", "registro"), ("Médico", "medico"),
                              ("Máquina", "maquina")):
            self.filtro_campo.addItem(rotulo, chave)
        self.filtro_campo.currentIndexChanged.connect(self._recarregar)
        topo.addWidget(self.filtro_campo)
        self.busca = QLineEdit()
        self.busca.textChanged.connect(self._recarregar)
        topo.addWidget(self.busca, 1)
        btn_reindexar = QPushButton("🔄  Reindexar")
        btn_reindexar.setToolTip(
            "Reconstrói o índice a partir de uma pasta raiz (varre os JSON soltos "
            "e os .zip dos pacientes). Use se o índice ficou desatualizado.")
        estilo.pintar(btn_reindexar, lambda: estilo.btn_contorno(11.5))
        btn_reindexar.clicked.connect(self._reindexar)
        topo.addWidget(btn_reindexar)
        btn_limpar = QPushButton("🧹  Limpar histórico")
        btn_limpar.setToolTip(
            "Esvazia a lista do Histórico (índice). Os arquivos dos pacientes "
            "continuam na pasta e podem voltar com Reindexar.")
        estilo.pintar(btn_limpar, lambda: estilo.btn_perigo(11.5))
        btn_limpar.clicked.connect(self._limpar_historico)
        topo.addWidget(btn_limpar)
        lay.addLayout(topo)

        self.tabela = QTableWidget(0, len(self._COLS))
        self.tabela.setHorizontalHeaderLabels(self._COLS)
        self.tabela.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabela.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabela.setSelectionMode(QTableWidget.SingleSelection)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tabela.doubleClicked.connect(lambda *_: self._abrir_tratamento())
        lay.addWidget(self.tabela, 1)

        self._lbl_status = QLabel("")
        estilo.pintar(self._lbl_status,
                      lambda: f"color:{estilo.VERMELHO}; font-size:11px;")
        lay.addWidget(self._lbl_status)

        # Os cinco botões eram uma fileira de peso IGUAL, esticados pela
        # largura, e o "Fechar" saía de VERMELHO CONTORNADO — a marca do
        # destrutivo posta no botão que não faz nada. ``rodape`` põe o sólido
        # em "Carregar Ficha", as três ações do trabalho à esquerda e a saída
        # onde ela está em toda tela do programa.
        #
        # "Fechar" e não "Cancelar": as outras três agem SEM fechar a busca, e
        # "Cancelar" prometeria desfazer o que elas já fizeram.
        botoes = self.rodape(
            "Carregar Ficha", cancelar="Fechar",
            extras=[("Verificar Versão", self._verificar_versao),
                    ("Abrir PDF Ficha", self._abrir_ficha_pdf),
                    ("📁  Abrir Pasta", self._abrir_pasta)])
        # O sólido NÃO fecha por si. ``_abrir_tratamento`` passa pelo seletor
        # de versão, que pode ser recusado; com o ``accept`` do rodapé ligado,
        # quem desistisse da versão perderia a busca inteira e teria de
        # refazê-la. Quem fecha é ``_apos_carregar``, com a ficha já dentro.
        botoes["Carregar Ficha"].clicked.disconnect()
        botoes["Carregar Ficha"].clicked.connect(self._abrir_tratamento)

        self._linhas: list[dict] = []
        self._recarregar()

    # ── Dados ────────────────────────────────────────────────────────────────
    def _reindexar(self):
        """Reconstrói o índice central a partir de uma pasta raiz escolhida."""
        raiz = QFileDialog.getExistingDirectory(
            self, "Pasta raiz dos pacientes para reindexar")
        if not raiz:
            return
        # A varredura é síncrona (pode demorar numa árvore grande), então o
        # aviso deixa claro que está trabalhando, não travado. O ``alertar`` do
        # erro fica FORA do ``with``: antes ele abria por baixo do aviso e com
        # o cursor de espera, porque o ``finally`` só corria depois dele.
        try:
            with ui.trabalhando(self, "Reindexando… aguarde."):
                n = indice.reconstruir(raiz)
        except Exception as exc:  # noqa: BLE001
            ui.alertar(self, "Erro ao reindexar", str(exc))
            return
        self._recarregar()
        historico.registrar("reindexacao", detalhes={"raiz": raiz, "fontes": n})
        ui.avisar(
            self, "Reindexação concluída",
            f"{n} registro(s) reindexado(s) a partir de:\n{raiz}")

    def _limpar_historico(self):
        """Esvazia a lista do Histórico (índice), com confirmação."""
        n = len(self._linhas)
        if not ui.confirmar(
                self, "Limpar o Histórico",
                f"Isso remove {n} paciente(s) da LISTA do Histórico.",
                acao="Limpar a lista", recusa="Manter a lista",
                detalhe=("Os arquivos (JSON/.zip) dos pacientes NÃO são "
                         "apagados — dá para trazê-los de volta com "
                         "Reindexar."),
                perigo=True):
            return
        try:
            removidos = indice.limpar()
        except Exception as exc:  # noqa: BLE001
            ui.alertar(self, "Erro ao limpar", str(exc))
            return
        historico.registrar("tratados_limpos", detalhes={"removidos": removidos})
        self._recarregar()
        ui.avisar(self, "Histórico limpo",
                                f"{removidos} registro(s) removido(s) da lista.")

    def _recarregar(self):
        campo = self.filtro_campo.currentData() or "tudo"
        try:
            self._linhas = indice.buscar(self.busca.text(), campo)
            self._lbl_status.setText("")
        except Exception as exc:  # noqa: BLE001
            self._linhas = []
            self._lbl_status.setText(f"Erro ao ler o registro de fichas: {exc}")
        self.tabela.setRowCount(len(self._linhas))
        for i, r in enumerate(self._linhas):
            dose = r.get("dose_total")
            fr = r.get("num_fracoes")
            dose_txt = (f"{dose:g} Gy" if isinstance(dose, (int, float)) else "")
            if fr:
                dose_txt = f"{dose_txt} / {fr} fx" if dose_txt else f"{fr} fx"
            valores = [
                r.get("nome", ""), r.get("registro", ""), r.get("data", ""),
                str(r.get("versao", "")),  # versões == última versão (1..N)
                # O registro guarda o nome de fábrica (é a identidade); a
                # coluna mostra o nome pelo qual a máquina é chamada.
                constantes.rotulo_maquina(r.get("maquina", "")),
                r.get("medico", ""), dose_txt,
            ]
            for j, v in enumerate(valores):
                self.tabela.setItem(i, j, QTableWidgetItem(str(v)))

    def _selecionado(self) -> dict | None:
        linha = self.tabela.currentRow()
        if linha < 0 or linha >= len(self._linhas):
            ui.avisar(self, "Selecione", "Selecione um paciente na lista.")
            return None
        return self._linhas[linha]

    # ── Ações ────────────────────────────────────────────────────────────────
    # O trabalho está em ``AcoesDeFicha`` — a mesma que a lista de recentes da
    # Fichinha usa. Aqui só se traduz "o que está selecionado na tabela" para a
    # linha de índice que aquelas ações esperam.

    def _apos_carregar(self) -> None:
        """Carregou: esta tela cumpriu o papel e sai da frente."""
        self.accept()

    def _abrir_pasta(self):
        r = self._selecionado()
        if r:
            self.ficha_abrir_pasta(r)

    def _verificar_versao(self):
        r = self._selecionado()
        if r:
            self.ficha_verificar_versao(r)

    def _abrir_tratamento(self):
        r = self._selecionado()
        if r:
            self.ficha_carregar(r)

    def _abrir_ficha_pdf(self):
        r = self._selecionado()
        if r:
            self.ficha_abrir_pdf(r)
