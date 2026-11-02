"""O módulo Documentação e conformidade: a aba PPR e, por ora, só ela.

A aba PPR é a leitura de :mod:`isocentro.dominio.ppr` — o mapa de que módulo
dá cada capítulo — e não guarda nada dela: o PPR vivo é montado das seções
que cada módulo guarda no banco central (spec Documentação CAP-10). Parte
que o módulo dono não gravou sai "sem dado". Uma tela que mostrasse o PPR
"pronto" com capítulos vazios seria pior que nenhuma: é o documento que vai
à CNEN.

Clicar numa linha abre, embaixo, as partes dela (corpo, subseções, anexo),
uma de cada vez. Físico e admin editam a parte escolhida (pedido de
28/10/2026); a gravação sai em nome do módulo DONO da parte, com a pessoa no
log, e a versão anterior fica guardada como substituída (AD-5). A tela é da
Documentação, mas quem grava continua sendo o dono — é o que impede a GQ de
escrever o texto da Segurança.

O botão de emitir fica apagado mesmo com tudo "com dado": o gerador do PDF e
a assinatura do SPR (R-19) ainda não existem, e botão aceso é botão pronto.

Os Vencimentos (R-49) ganham a aba ao lado só com o aviso de que estão em
construção — a UX dá as duas abas ao módulo, e a segunda aparecer depois
mudaria o lugar da primeira.
"""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QHeaderView,
                               QTableWidget, QTableWidgetItem, QVBoxLayout,
                               QWidget)

from isocentro.dominio import ppr
from isocentro.interface import estilo as st
from isocentro.interface import torre, ui

_SEM_GERADOR = ("A emissão ainda não existe: falta o gerador do PDF e a "
                "assinatura do SPR.")

_COLUNAS = ("#", "Capítulo", "Módulo dono", "Situação")

# "○" é o glifo de informativo da UX (DESIGN.md): sem dado não é em dia nem
# vencido. Forçado a texto (VS15), como os outros glifos de estado.
_ROTULO_DA_SITUACAO = {
    ppr.SEM_DADO: "○︎ sem dado",
    ppr.COM_DADO: "com dado",
}

# Os papéis que veem "Todas" no Início são os que respondem pelo PPR hoje,
# enquanto a capacidade por pessoa não existe (R-19, R-78).
PAPEIS_QUE_EDITAM = torre.PAPEIS_COM_TODAS

Gravador = Callable[[str, str, str, str, str, Optional[object]], None]


def _ler_do_banco(clinica: str) -> ppr.Leitura:
    """A leitura de verdade, com o psycopg importado só aqui.

    O executável ainda não leva o psycopg (NOTAS, R-18): importado no topo,
    o app inteiro morreria ao abrir por causa de uma aba.
    """
    try:
        from isocentro.adaptadores.postgres import ppr as pg_ppr  # noqa: PLC0415
    except ImportError:
        return ppr.Leitura({}, None, {}, "Este ISOCENTRO não traz o acesso "
                           "ao banco central (psycopg): nada a ler.")
    return pg_ppr.ler_do_ambiente(clinica)


def _gravar_no_banco(quem, clinica, modulo, chave, texto, anterior) -> None:
    from isocentro.adaptadores.postgres import ppr as pg_ppr  # noqa: PLC0415
    pg_ppr.gravar_texto_do_ambiente(quem, clinica, modulo, chave, texto,
                                    anterior)


def partes_rotuladas(numero: str, linha_parte: ppr.Parte,
                     planta: ppr.Planta) -> list:
    """``[(parte, curto, titulo)]``: o botão de cada parte e o título dela."""
    rotuladas = []
    for parte in ppr.partes_da_linha(linha_parte, planta):
        if parte == ppr.SEVRRA:
            curto = "SEVRRA"
            titulo = f"Anexo {planta.letra('gq')} — {parte.titulo}"
        elif isinstance(parte, ppr.Anexo):
            curto = f"Anexo {planta.letra(parte.chave)}"
            titulo = f"{curto} — {parte.titulo}"
        elif parte is linha_parte:
            curto = f"Capítulo {numero}"
            titulo = f"{numero} {parte.titulo}"
        else:
            curto = f"{numero}.{linha_parte.subsecoes.index(parte) + 1}"
            titulo = f"{curto} {parte.titulo}"
        rotuladas.append((parte, curto, titulo))
    return rotuladas


def origem_da_parte(gravada) -> str:
    docs = [d.get("titulo", "") + (f" (p. {d['paginas']})"
                                   if d.get("paginas") else "")
            for d in gravada.documentos]
    origem = f"Fonte: {gravada.fonte}"
    return (f"Documentos: {'; '.join(docs)}  ·  " if docs else "") + origem


class PainelDocumentacao(QWidget):
    """As abas do módulo; a clínica vem do seletor do Início."""

    def __init__(self, parent=None,
                 leitor: Optional[Callable[[str], ppr.Leitura]] = None,
                 gravador: Optional[Gravador] = None,
                 usuario: Optional[dict] = None):
        super().__init__(parent)
        self._ler = leitor or _ler_do_banco
        self._gravar = gravador or _gravar_no_banco
        self._usuario = usuario or {}
        self._linhas: list = []
        self._planta = ppr.planta()
        self._partes: dict = {}
        self._linha_atual = -1
        self._rotuladas: list = []
        self._parte_atual: Optional[ppr.Parte] = None
        # O texto como está no banco: "editado" é diferente dele, e não um
        # sinal de "alguém digitou" — digitar e voltar atrás não é edição.
        self._original = ""
        st.pintar(self, lambda: f"background:{st.FUNDO_TELA};")
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)
        self.abas = ui.abas((self._pagina_ppr(), "PPR"),
                            (self._pagina_vencimentos(), "Vencimentos"))
        raiz.addWidget(self.abas, 1)
        # Sem ler o banco aqui: a tela nasce com a janela, e cada abertura do
        # app esperaria a conexão (até 3 s com o banco fora) por uma aba que
        # talvez nem se abra. Quem lê é o ``definir_clinica``, ao abrir.
        self.faixa_aviso.setVisible(False)
        self.btn_emitir.setToolTip(_SEM_GERADOR)
        self._mostrar_parte(None)

    # ── Montagem ────────────────────────────────────────────────────────

    def _pagina_ppr(self) -> QWidget:
        pagina = QWidget()
        lay = QVBoxLayout(pagina)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        faixa, lay_faixa = ui.faixa()
        # Seletor PRÓPRIO da aba (pedido de 28/10/2026): cada PPR é de uma
        # clínica, e com "Todas" no Início a aba ficava sem o que mostrar.
        # Trocar aqui não mexe no Início — ler o PPR de outra unidade não é
        # mudar de unidade no resto do app.
        lay_faixa.addWidget(ui.rotulo("Clínica:", forte=True))
        self.cmb_clinica = ui.escolha([r for _c, r in torre.CLINICAS],
                                      largura=120)
        self._indice_clinica = 0
        self.cmb_clinica.currentIndexChanged.connect(self._clinica_escolhida)
        lay_faixa.addWidget(self.cmb_clinica)
        lay_faixa.addStretch(1)
        # Nenhum PPR saiu do ISOCENTRO ainda: os PPRs vigentes foram feitos
        # fora (ppr-streamlit), e citá-los aqui como "emissão" mentiria a
        # origem.
        self.lbl_emissao = ui.rotulo("Última emissão: nenhuma")
        lay_faixa.addWidget(self.lbl_emissao)
        lay.addWidget(faixa)
        # O motivo de não ter lido o banco, em linha própria: no tooltip, quem
        # vê "sem dado" em tudo não teria por que procurá-lo.
        self.faixa_aviso, lay_aviso = ui.faixa()
        self.lbl_aviso = ui.rotulo("")
        self.lbl_aviso.setWordWrap(True)
        lay_aviso.addWidget(self.lbl_aviso, 1)
        lay.addWidget(self.faixa_aviso)
        lay.addWidget(ui.divisor())

        miolo = ui.transparente(QWidget())
        lay_miolo = QVBoxLayout(miolo)
        lay_miolo.setContentsMargins(18, 14, 18, 14)
        self.tabela = QTableWidget(0, len(_COLUNAS))
        self.tabela.setHorizontalHeaderLabels(_COLUNAS)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabela.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tabela.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabela.currentCellChanged.connect(
            lambda linha, *_: self._linha_escolhida(linha))
        cab = self.tabela.horizontalHeader()
        cab.setSectionResizeMode(QHeaderView.ResizeToContents)
        cab.setSectionResizeMode(1, QHeaderView.Stretch)
        st.pintar(self.tabela, ui.grade)
        lay_miolo.addWidget(self.tabela, 1)

        # Uma parte de cada vez: cada uma é um registro do módulo dono, e
        # uma caixa com todas juntas não teria como saber o que salvar onde.
        topo_parte = ui.transparente(QWidget())
        self.lay_partes = QHBoxLayout(topo_parte)
        self.lay_partes.setContentsMargins(0, 6, 0, 4)
        self.seletor_partes: Optional[torre.SeletorDeClinica] = None
        self.lbl_parte = ui.rotulo("", forte=True)
        self.lay_partes.addWidget(self.lbl_parte, 1)
        lay_miolo.addWidget(topo_parte)
        self.texto = ui.area(10)
        self.texto.textChanged.connect(self._atualizar_botoes)
        lay_miolo.addWidget(self.texto)
        linha_origem = ui.transparente(QWidget())
        lay_origem = QHBoxLayout(linha_origem)
        lay_origem.setContentsMargins(0, 4, 0, 0)
        self.lbl_origem = ui.rotulo("")
        self.lbl_origem.setWordWrap(True)
        lay_origem.addWidget(self.lbl_origem, 1)
        self.btn_desfazer = ui.botao("Desfazer")
        self.btn_desfazer.clicked.connect(
            lambda: self.texto.setPlainText(self._original))
        lay_origem.addWidget(self.btn_desfazer)
        # Contorno, e não sólido: salvar não destrói — a versão anterior
        # fica guardada. O sólido da tela é o "Emitir".
        self.btn_salvar = ui.botao("Salvar")
        self.btn_salvar.clicked.connect(self._salvar)
        lay_origem.addWidget(self.btn_salvar)
        lay_miolo.addWidget(linha_origem)
        lay.addWidget(miolo, 1)

        rodape, lay_rodape = ui.faixa()
        lay_rodape.addStretch(1)
        # O sólido da tela: emitir é o passo que não se desfaz (vai assinado
        # pelo SPR). Apagado até haver dado em todo capítulo — botão aceso é
        # botão pronto (CLAUDE.md).
        self.btn_emitir = ui.botao("Emitir PPR", cor="solido")
        self.btn_emitir.setEnabled(False)
        lay_rodape.addWidget(self.btn_emitir)
        lay.addWidget(rodape)
        return pagina

    def _pagina_vencimentos(self) -> QWidget:
        pagina = QWidget()
        lay = QVBoxLayout(pagina)
        lay.setContentsMargins(18, 16, 18, 16)
        aviso = ui.rotulo("Os vencimentos estão em construção. Quando estiverem "
                          "prontos, o painel do serviço e da GQ fica aqui.")
        aviso.setWordWrap(True)
        lay.addWidget(aviso)
        lay.addStretch(1)
        return pagina

    # ── Estado ──────────────────────────────────────────────────────────

    def pode_editar(self) -> bool:
        return str(self._usuario.get("papel") or "") in PAPEIS_QUE_EDITAM

    def editado(self) -> bool:
        return (self._parte_atual is not None
                and self.texto.toPlainText() != self._original)

    def _pode_sair(self) -> bool:
        """Edição não salva só se perde com a pessoa dizendo que sim."""
        if not self.editado():
            return True
        return ui.confirmar(
            self, "Edição não salva",
            f"O texto de \"{self.lbl_parte.text()}\" foi alterado e não foi "
            "salvo.", acao="Descartar a edição", recusa="Continuar editando",
            perigo=True)

    def definir_clinica(self, clinica: str, rotulo: str = "") -> None:
        """A clínica do Início: o código do banco (``"ANA"``), ou ``""`` com "Todas".

        Com "Todas" a aba abre na primeira unidade, e o seletor dela troca.
        ``rotulo`` fica pela assinatura de quem chama: o que se lê é o do
        seletor.
        """
        codigos = [c for c, _r in torre.CLINICAS]
        indice = codigos.index(clinica) if clinica in codigos else 0
        if self.cmb_clinica.currentIndex() == indice:
            if self._pode_sair():
                self._carregar(codigos[indice])
        else:
            # O sinal do seletor carrega: chamar ``_carregar`` também leria o
            # banco duas vezes.
            self.cmb_clinica.setCurrentIndex(indice)

    def clinica(self) -> str:
        return torre.CLINICAS[self.cmb_clinica.currentIndex()][0]

    def _clinica_escolhida(self, indice: int) -> None:
        if indice < 0:
            return
        if not self._pode_sair():
            self.cmb_clinica.blockSignals(True)
            self.cmb_clinica.setCurrentIndex(self._indice_clinica)
            self.cmb_clinica.blockSignals(False)
            return
        self._indice_clinica = indice
        self._carregar(torre.CLINICAS[indice][0])

    def _carregar(self, clinica: str, linha: int = -1,
                  parte: Optional[ppr.Parte] = None) -> None:
        """Lê do banco as partes de ``clinica`` (código) e remonta a aba.

        O código é o que as fachadas recebem, para a seção de uma clínica
        não valer para outra. ``linha`` e ``parte`` reabrem onde se estava
        (depois de salvar).
        """
        leitura = self._ler(clinica)
        self.lbl_aviso.setText(leitura.aviso)
        self.faixa_aviso.setVisible(bool(leitura.aviso))
        # Sem a resposta da GQ, a planta inclui o condicional (ver
        # ``ppr.planta``): tirar o capítulo de rejeitos afirmaria que a
        # clínica não tem fonte.
        self._planta = (ppr.planta(leitura.condicoes)
                        if leitura.condicoes is not None else ppr.planta())
        self._partes = leitura.partes
        linhas = ppr.situacoes(clinica, leitura.fachadas, self._planta)
        self._linhas = linhas
        self.tabela.blockSignals(True)
        self.tabela.setRowCount(len(linhas))
        for i, (rotulo, p, situacao) in enumerate(linhas):
            celulas = (rotulo, p.titulo, p.nome_do_modulo,
                       _ROTULO_DA_SITUACAO[situacao])
            for j, texto in enumerate(celulas):
                self.tabela.setItem(i, j, QTableWidgetItem(texto))
        self.tabela.setCurrentCell(linha, 0 if linha >= 0 else -1)
        self.tabela.blockSignals(False)
        self.btn_emitir.setEnabled(False)
        self.btn_emitir.setToolTip(
            ppr.motivo_para_nao_emitir(clinica, linhas) or _SEM_GERADOR)
        self._linha_atual = -1
        self._abrir_linha(linha, parte)

    def _linha_escolhida(self, linha: int) -> None:
        if linha == self._linha_atual:
            return
        if not self._pode_sair():
            self.tabela.blockSignals(True)
            self.tabela.setCurrentCell(self._linha_atual, 0)
            self.tabela.blockSignals(False)
            return
        self._abrir_linha(linha)

    def _abrir_linha(self, linha: int,
                     parte: Optional[ppr.Parte] = None) -> None:
        self._linha_atual = linha
        if self.seletor_partes is not None:
            self.seletor_partes.deleteLater()
            self.seletor_partes = None
        if not 0 <= linha < len(self._linhas):
            self._rotuladas = []
            self._mostrar_parte(None)
            return
        numero, linha_parte, _situacao = self._linhas[linha]
        self._rotuladas = partes_rotuladas(numero, linha_parte, self._planta)
        curtos = [c for _p, c, _t in self._rotuladas]
        inicial = next((c for p, c, _t in self._rotuladas if p == parte),
                       curtos[0])
        # O mesmo controle segmentado do Início: as partes de uma linha são
        # poucas (até 5, na GQ) e se escolhem de relance.
        self.seletor_partes = torre.SeletorDeClinica(curtos, inicial)
        self.seletor_partes.mudou.connect(self._parte_escolhida)
        self.lay_partes.insertWidget(0, self.seletor_partes)
        self._mostrar_parte(next(p for p, c, _t in self._rotuladas
                                 if c == inicial))

    def _parte_escolhida(self, curto: str) -> None:
        parte = next(p for p, c, _t in self._rotuladas if c == curto)
        if parte == self._parte_atual:
            return
        if not self._pode_sair():
            anterior = next(c for p, c, _t in self._rotuladas
                            if p == self._parte_atual)
            self.seletor_partes.botoes[anterior].setChecked(True)
            return
        self._mostrar_parte(parte)

    def _mostrar_parte(self, parte: Optional[ppr.Parte]) -> None:
        self._parte_atual = parte
        self.texto.blockSignals(True)
        if parte is None:
            self._original = ""
            self.texto.clear()
            self.texto.setReadOnly(True)
            self.texto.setPlaceholderText(
                "Clique num capítulo para ler o texto vigente.")
            self.lbl_parte.setText("")
            self.lbl_origem.setText("")
        else:
            titulo = next(t for p, _c, t in self._rotuladas if p == parte)
            self.lbl_parte.setText(titulo)
            gravada = self._partes.get(ppr.chave_gravada(parte))
            editar = self.pode_editar()
            texto = gravada.texto if gravada else ""
            # Na edição a menção fica como {anexo:gq}: com a letra escrita,
            # o texto salvo apontaria o anexo errado na clínica sem rejeitos.
            self._original = texto
            self.texto.setPlainText(
                texto if editar else ppr.resolver_mencoes(texto, self._planta))
            self.texto.setReadOnly(not editar)
            if gravada is None:
                vazio = f"sem dado — {parte.nome_do_modulo}"
                if editar:
                    vazio += ". Escreva o texto para criar a primeira versão."
            else:
                # Texto vazio é o capítulo que é só "Vide anexo": o "Vide" é
                # do gerador. Dizer isso evita que o vazio pareça perda.
                vazio = "(sem texto corrido no PPR vigente)"
            self.texto.setPlaceholderText(vazio)
            self.lbl_origem.setText(origem_da_parte(gravada) if gravada
                                    else "")
        self.texto.blockSignals(False)
        self._atualizar_botoes()

    def _atualizar_botoes(self) -> None:
        editado = self.editado()
        self.btn_desfazer.setEnabled(editado)
        self.btn_salvar.setEnabled(editado and self.pode_editar())
        if self._parte_atual is None:
            motivo = "Escolha um capítulo."
        elif not self.pode_editar():
            motivo = "Só o físico e o admin editam o texto do PPR."
        elif not editado:
            motivo = "Nada alterado."
        else:
            motivo = ""
        self.btn_salvar.setToolTip(motivo)

    def _salvar(self) -> None:
        if not (self.editado() and self.pode_editar()):
            return
        parte = self._parte_atual
        clinica = self.clinica()
        quem = str(self._usuario.get("usuario") or "")
        try:
            self._gravar(quem, clinica, parte.modulo, ppr.chave_gravada(parte),
                         self.texto.toPlainText(),
                         self._partes.get(ppr.chave_gravada(parte)))
        except Exception as erro:  # noqa: BLE001 - o motivo vai para a tela
            ui.falhar(self, "Texto não salvo", "O texto não foi gravado e "
                      "continua aqui, como estava.", tecnico=str(erro))
            return
        self._original = self.texto.toPlainText()
        self._carregar(clinica, self._linha_atual, parte)
