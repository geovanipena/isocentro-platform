"""Telas de **administração e acesso**: entrar, usuários, equipe, serviço.

Saiu do ``gui.py`` em 25/08/2026, com 9.692 linhas. Não é arrumação: era o
único bloco do arquivo COESO e sem laço de volta — login, troca de senha,
cadastro de usuários, listas de equipe e máquinas, pastas do serviço e o
histórico de uso são todos do mesmo assunto (quem pode o quê, e onde estão as
coisas), e nenhum deles é chamado de dentro da bancada.

O resto do ``gui.py`` continua lá: a extração é para ser feita CONFORME as
partes forem tocadas, nunca de uma vez — num arquivo desse tamanho, uma
mudança grande não tem como ser conferida.

As classes continuam alcançáveis por ``gui.DialogLogin`` e companhia: o
``gui`` as reimporta, e nenhum ponto de chamada mudou.
"""
from __future__ import annotations

import logging
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QComboBox,
                             QDialog, QFileDialog, QFormLayout, QGroupBox,
                             QHBoxLayout, QHeaderView, QInputDialog, QLabel,
                             QLineEdit, QListWidget, QListWidgetItem,
                             QPushButton, QScrollArea, QSizePolicy,
                             QTableWidget, QTableWidgetItem, QVBoxLayout,
                             QWidget)

from isocentro.dados import auth
from isocentro.banco import capa_dados
from isocentro.banco import capa_db
from isocentro.dados import config_servico
from isocentro.dominio import constantes
from isocentro.dicom import dicom_rt
from isocentro.interface import estilo
from isocentro.dados import historico
from isocentro.interface import simulacao
from isocentro.interface import ui
from isocentro.dados.equipe import (_carregar_fisicos, _carregar_medicos, _salvar_fisicos,
                    _salvar_medicos, unidade_da_pessoa)

_LOG = logging.getLogger(__name__)

class DialogTrocarSenha(ui.Dialogo):
    """Troca a senha do usuário (voluntária ou forçada no 1º acesso)."""

    def __init__(self, usuario: str, parent=None, forcado: bool = False):
        super().__init__("Trocar senha", parent)
        self._usuario = usuario
        self.setMinimumWidth(340)
        lay = self.corpo
        if forcado:
            av = QLabel("Defina uma nova senha para continuar.")
            estilo.pintar(av, lambda: (
                f"color:{estilo.AMBAR}; font-weight:bold;"))
            av.setWordWrap(True); lay.addWidget(av)
        form = QFormLayout()
        self.ed_nova = QLineEdit(); self.ed_nova.setEchoMode(QLineEdit.Password)
        self.ed_conf = QLineEdit(); self.ed_conf.setEchoMode(QLineEdit.Password)
        form.addRow("Nova senha", self.ed_nova)
        form.addRow("Confirmar", self.ed_conf)
        lay.addLayout(form)
        self._erro = QLabel("")
        estilo.pintar(self._erro, lambda: f"color:{estilo.VERMELHO};")
        lay.addWidget(self._erro)
        # Troca FORÇADA não tem saída: sem senha nova não se entra, e um
        # "Cancelar" ali seria um botão que não faz nada.
        botoes = self.rodape("Salvar", cancelar=None if forcado else "")
        # ``rodape`` liga o confirmar ao ``accept``; aqui ele VALIDA antes —
        # senha curta ou confirmação diferente têm de manter a janela aberta.
        botoes["Salvar"].clicked.disconnect()
        botoes["Salvar"].clicked.connect(self._salvar)

    def _salvar(self):
        nova, conf = self.ed_nova.text(), self.ed_conf.text()
        if len(nova) < 4:
            self._erro.setText("A senha precisa de ao menos 4 caracteres."); return
        if nova != conf:
            self._erro.setText("As senhas não conferem."); return
        try:
            auth.redefinir_senha(self._usuario, nova, trocar_senha=False)
        except Exception as exc:  # noqa: BLE001
            self._erro.setText(str(exc)); return
        self.accept()


class DialogLogin(ui.Dialogo):
    """Login ao abrir o programa. ``usuario()`` traz o usuário autenticado."""

    def __init__(self, parent=None):
        super().__init__("ISOCENTRO — Entrar", parent)
        self._usuario = None
        self.setMinimumWidth(340)
        lay = self.corpo
        tit = QLabel("Acesso ao ISOCENTRO")
        estilo.pintar(tit, lambda: (
            f"font-size:16px; font-weight:bold; color:{estilo.ACAO};"))
        tit.setAlignment(Qt.AlignCenter); lay.addWidget(tit)
        form = QFormLayout()
        self.ed_user = QLineEdit(); self.ed_user.setPlaceholderText("usuário")
        self.ed_pass = QLineEdit(); self.ed_pass.setEchoMode(QLineEdit.Password)
        self.ed_pass.setPlaceholderText("senha")
        form.addRow("Usuário", self.ed_user)
        form.addRow("Senha", self.ed_pass)
        lay.addLayout(form)
        self._erro = QLabel("")
        estilo.pintar(self._erro, lambda: f"color:{estilo.VERMELHO};")
        self._erro.setWordWrap(True); lay.addWidget(self._erro)
        botoes = self.rodape("Entrar", cancelar="Sair")
        # Como na troca de senha: o confirmar AUTENTICA antes de fechar —
        # senha errada tem de manter a janela aberta com o erro na tela.
        botoes["Entrar"].clicked.disconnect()
        botoes["Entrar"].clicked.connect(self._tentar)
        self.ed_pass.returnPressed.connect(self._tentar)
        self.ed_user.returnPressed.connect(lambda: self.ed_pass.setFocus())

    def _tentar(self):
        u = auth.verificar(self.ed_user.text(), self.ed_pass.text())
        if u is None:
            historico.registrar("login_falha",
                                usuario=self.ed_user.text().strip() or "?")
            self._erro.setText("Usuário ou senha inválidos.")
            self.ed_pass.clear(); self.ed_pass.setFocus()
            return
        if u.get("trocar_senha"):
            if DialogTrocarSenha(u["usuario"], self, forcado=True).exec() != QDialog.Accepted:
                self._erro.setText("É preciso trocar a senha para entrar.")
                return
            u = {**u, "trocar_senha": False}
        self._usuario = u
        self.accept()

    def usuario(self):
        return self._usuario


class PainelUsuarios(QWidget):
    """Administração de usuários (aba de Configurações, só para admin)."""

    _COLS = ["Usuário", "Nome", "Função", "Ativo"]
    # Pela POSIÇÃO no _COLS, e não por um 2 escrito à mão: acrescentar uma
    # coluna antes dela passaria a abrir a troca de função no campo errado.
    _COL_FUNCAO = _COLS.index("Função")
    # Rótulo exibido por papel; a CHAVE interna (auth.PAPEIS) permanece a mesma.
    _FUNCAO_LABEL = {"admin": "Administrador", "fisico": "Físico Médico",
                     "medico": "Médico", "dosimetrista": "Dosimetrista",
                     "tecnico": "Técnico", "enfermeiro": "Enfermeiro",
                     "recepcionista": "Recepcionista"}

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.tabela = QTableWidget(0, len(self._COLS))
        self.tabela.setHorizontalHeaderLabels(self._COLS)
        self.tabela.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabela.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabela.setSelectionMode(QTableWidget.SingleSelection)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        # Trocar a função é duplo clique NA CÉLULA da função — não há botão.
        # Restrito a essa coluna de propósito: duplo clique no nome abrindo a
        # troca de função seria mudar uma coisa clicando em outra.
        self.tabela.cellDoubleClicked.connect(self._celula_duplo_clique)
        lay.addWidget(self.tabela, 1)
        linha = QHBoxLayout()
        # Seis cores diferentes aqui viravam um arco-íris em que Remover — a
        # única ação sem volta — não se distinguia de Fechar. O peso separa:
        # Novo é o que se vem fazer, Remover é perigo, o resto é passagem.
        for txt, fn, peso in (("Novo", self._novo, estilo.btn_solido),
                              ("Redefinir senha", self._redefinir, estilo.btn_contorno),
                              ("Ativar/Desativar", self._toggle_ativo, estilo.btn_contorno),
                              ("Remover", self._remover, estilo.btn_perigo),
                              ("📜 Histórico", self._historico, estilo.btn_fantasma),
                              ("Fechar", lambda: self.window().close(),
                               estilo.btn_fantasma)):
            b = QPushButton(txt); b.setStyleSheet(peso())
            b.clicked.connect(fn); linha.addWidget(b)
        lay.addLayout(linha)
        self._recarregar()

    def _recarregar(self):
        self._linhas = auth.listar()
        self.tabela.setRowCount(len(self._linhas))
        for i, u in enumerate(self._linhas):
            vals = [u["usuario"], u["nome"],
                    self._FUNCAO_LABEL.get(u["papel"], u["papel"]),
                    "Sim" if u["ativo"] else "Não"]
            for j, v in enumerate(vals):
                item = QTableWidgetItem(str(v))
                if j == self._COL_FUNCAO:
                    # Sem isto o duplo clique não existe para quem olha a tela.
                    # É a mesma regra dos atalhos: o que não aparece em lugar
                    # nenhum não é descoberto.
                    item.setToolTip("Duplo clique para trocar a função")
                self.tabela.setItem(i, j, item)

    def _celula_duplo_clique(self, linha: int, coluna: int) -> None:
        if coluna == self._COL_FUNCAO:
            self._trocar_funcao()

    def _sel(self):
        i = self.tabela.currentRow()
        if i < 0 or i >= len(self._linhas):
            ui.avisar(self, "Selecione", "Selecione um usuário.")
            return None
        return self._linhas[i]

    def _novo(self):
        user, ok = QInputDialog.getText(self, "Novo usuário", "Usuário (login):")
        if not ok or not user.strip():
            return
        nome, ok = QInputDialog.getText(self, "Novo usuário", "Nome completo:")
        if not ok:
            return
        senha, ok = QInputDialog.getText(self, "Novo usuário",
                                         "Senha inicial:", QLineEdit.Password)
        if not ok or len(senha) < 4:
            ui.alertar(self, "Senha", "Senha de ao menos 4 caracteres.")
            return
        papel = self._escolher_funcao("fisico")
        if not papel:
            return
        try:
            auth.criar(user.strip(), nome.strip(), senha, papel=papel,
                       trocar_senha=True)
        except Exception as exc:  # noqa: BLE001
            ui.alertar(self, "Erro", str(exc)); return
        historico.registrar("usuario_criado",
                            detalhes={"alvo": user.strip(), "papel": papel})
        self._recarregar()

    def _escolher_funcao(self, atual: str) -> str:
        """O diálogo da função, com o papel ATUAL já selecionado. "" = desistiu.

        A ordem da lista é a de ``auth.PAPEIS`` — quem lê a tela duas vezes
        encontra a mesma função no mesmo lugar, e ordenar por alfabeto faria
        "Administrador" e "Auxiliar" trocarem de posição a cada função nova.
        """
        rotulos = [self._FUNCAO_LABEL.get(p, p) for p in auth.PAPEIS]
        atual_rotulo = self._FUNCAO_LABEL.get(atual, atual)
        indice = rotulos.index(atual_rotulo) if atual_rotulo in rotulos else 0
        rotulo, ok = QInputDialog.getItem(self, "Função", "Função:",
                                          rotulos, indice, False)
        if not ok:
            return ""
        # Volta do rótulo exibido para a chave interna do papel.
        return next((p for p in auth.PAPEIS
                     if self._FUNCAO_LABEL.get(p, p) == rotulo), "fisico")

    def _trocar_funcao(self):
        """Muda a função de quem JÁ existe.

        Sem isto, a única forma de corrigir uma função era remover e recriar o
        usuário — o que apaga o rastro dele do histórico de uso e obriga a
        pessoa a trocar de senha de novo. Quem é técnico e vira dosimetrista
        continua sendo a mesma pessoa.
        """
        u = self._sel()
        if not u:
            return
        novo = self._escolher_funcao(u["papel"])
        if not novo or novo == u["papel"]:
            return
        try:
            auth.definir_papel(u["usuario"], novo)
        except auth.SemAdministrador as exc:
            ui.alertar(self, "Último administrador", str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            ui.alertar(self, "Função", str(exc))
            return
        historico.registrar("usuario_funcao",
                            detalhes={"alvo": u["usuario"], "de": u["papel"],
                                      "para": novo})
        self._recarregar()

    def _redefinir(self):
        u = self._sel()
        if not u:
            return
        senha, ok = QInputDialog.getText(self, "Redefinir senha",
                                         f"Nova senha de {u['usuario']}:",
                                         QLineEdit.Password)
        if not ok or len(senha) < 4:
            ui.alertar(self, "Senha", "Senha de ao menos 4 caracteres.")
            return
        auth.redefinir_senha(u["usuario"], senha, trocar_senha=True)
        historico.registrar("senha_redefinida", detalhes={"alvo": u["usuario"]})
        ui.avisar(self, "Senha redefinida",
                                f"{u['usuario']} trocará a senha no próximo acesso.")

    def _toggle_ativo(self):
        u = self._sel()
        if not u:
            return
        try:
            auth.definir_ativo(u["usuario"], not u["ativo"])
        except auth.SemAdministrador as exc:
            ui.alertar(self, "Último administrador", str(exc))
            return
        historico.registrar("usuario_ativado" if not u["ativo"] else "usuario_desativado",
                            detalhes={"alvo": u["usuario"]})
        self._recarregar()

    def _remover(self):
        u = self._sel()
        if not u:
            return
        if not ui.confirmar(
                self, "Remover usuário?", f"Remover {u['usuario']}?",
                acao="Remover", recusa="Manter o usuário",
                detalhe="Ele perde o acesso ao programa imediatamente.",
                perigo=True):
            return
        try:
            auth.remover(u["usuario"])
        except auth.SemAdministrador as exc:
            ui.alertar(self, "Último administrador", str(exc))
            return
        historico.registrar("usuario_removido", detalhes={"alvo": u["usuario"]})
        self._recarregar()

    def _historico(self):
        DialogHistorico(self).exec()


class DialogHistorico(ui.Dialogo):
    """Visualização do histórico de uso do app (eventos, mais recentes no topo)."""

    _COLS = ["Quando", "Usuário", "Evento", "Detalhes"]
    _ROTULOS = {
        "login": "Entrou", "login_falha": "Falha de login",
        "app_reiniciado": "App recarregado (F5)", "app_fechado": "App fechado",
        "pasta_carregada": "Pasta DICOM carregada",
        "tratamento_reaberto": "Tratamento reaberto",
        "ficha_editada": "Ficha editada", "ficha_visualizada": "Ficha visualizada",
        "ficha_gerada": "Ficha gerada", "dicom_excluido": "DICOM excluído",
        "capa_correcao": "Cadastro corrigido na capa",
        "capa_da_pasta": "Capa montada de uma pasta",
        # A chave continua "tratados_*" nos logs já gravados; o rótulo é que
        # acompanha o nome novo da tela.
        "tratados_limpos": "Histórico limpo",
        "reindexacao": "Reindexação", "usuario_criado": "Usuário criado",
        "usuario_removido": "Usuário removido", "senha_redefinida": "Senha redefinida",
        "usuario_ativado": "Usuário ativado", "usuario_desativado": "Usuário desativado",
        "app_erro": "Erro/aviso técnico",
    }

    def __init__(self, parent=None):
        super().__init__("Histórico de uso", parent, 760, 480)
        lay = self.corpo
        self.tabela = QTableWidget(0, len(self._COLS))
        self.tabela.setHorizontalHeaderLabels(self._COLS)
        self.tabela.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabela.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        lay.addWidget(self.tabela, 1)
        # Tela de LEITURA: sem sólido, e a saída chama-se "Fechar". "Atualizar"
        # é ação lateral, à esquerda. Antes, "Fechar" chamava ``accept`` e o
        # Esc chamava ``reject`` — dois caminhos para fechar a mesma janela.
        self.rodape(extras=[("Atualizar", self._recarregar)])
        self._recarregar()

    def _recarregar(self):
        eventos = historico.ler(limite=2000)
        self.tabela.setRowCount(len(eventos))
        for i, e in enumerate(eventos):
            quando = (e.get("em", "") or "").replace("T", " ")
            evt = self._ROTULOS.get(e.get("evento"), e.get("evento", ""))
            det = e.get("detalhes") or {}
            det_txt = "  ".join(f"{k}={v}" for k, v in det.items()) if isinstance(det, dict) else str(det)
            for j, v in enumerate((quando, e.get("usuario", ""), evt, det_txt)):
                self.tabela.setItem(i, j, QTableWidgetItem(str(v)))
        self.tabela.resizeColumnsToContents()


class _ListaNomes(QWidget):
    """Lista editável (adicionar/remover) que persiste a cada mudança.

    Fica SEMPRE em ordem alfabética: um nome cadastrado agora entra no lugar
    dele, não no fim da lista — com 16 médicos, achar quem se quer remover numa
    lista por ordem de cadastro é procurar item por item.
    """

    _TODAS = "Todas"          # rótulo da unidade vazia (atende em qualquer máquina)

    def __init__(self, titulo, carregar, salvar, parent=None):
        super().__init__(parent)
        self._salvar = salvar
        nomes, self._unidades = carregar()
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(6)
        lbl = QLabel(titulo); lbl.setStyleSheet(f"font-weight:bold; color:{estilo.ACAO};")
        lay.addWidget(lbl)
        self.lst = QListWidget()
        self.lst.setToolTip("Duplo clique num nome troca a unidade dele "
                            "(Todas → Clinica → SAT).")
        for nome in dicom_rt.ordem_alfabetica(nomes):
            self.lst.addItem(self._item(nome))
        lay.addWidget(self.lst, 1)
        linha = QHBoxLayout(); linha.setSpacing(6)
        self.ed = QLineEdit()
        self.cb_unidade = QComboBox()
        self.cb_unidade.addItems([self._TODAS, *constantes.UNIDADES])
        self.cb_unidade.setToolTip(
            "Unidade do nome que está sendo cadastrado. A ficha de cada "
            "acelerador só oferece quem atende naquela unidade; \"Todas\" "
            "aparece em qualquer uma.")
        b_add = QPushButton("＋"); b_add.setFixedWidth(34)
        b_add.setStyleSheet(estilo.btn_contorno())
        b_rem = QPushButton("🗑"); b_rem.setFixedWidth(34)
        b_rem.setStyleSheet(estilo.btn_perigo())
        b_rem.setToolTip("Remove o nome selecionado.")
        linha.addWidget(self.ed, 1); linha.addWidget(self.cb_unidade)
        linha.addWidget(b_add); linha.addWidget(b_rem)
        lay.addLayout(linha)
        b_add.clicked.connect(self._adicionar)
        self.ed.returnPressed.connect(self._adicionar)
        b_rem.clicked.connect(self._remover)
        # Duplo clique CICLA a unidade — antes removia o nome, gesto destrutivo
        # sem confirmação nem rótulo que o anunciasse. Remover é o 🗑.
        self.lst.itemDoubleClicked.connect(self._ciclar_unidade)

    def _unidade(self, nome: str) -> str:
        """Unidade gravada para ``nome``, ou a de fábrica (ver dicom_rt)."""
        return unidade_da_pessoa(nome, self._unidades)

    def _item(self, nome: str) -> QListWidgetItem:
        """Item da lista: o nome, e a unidade ao lado quando ele tem uma.

        O nome vai no dado do item, não no texto: o sufixo é enfeite de leitura
        e não pode virar parte do nome ao salvar."""
        u = self._unidade(nome)
        item = QListWidgetItem(f"{nome}   ·  {u}" if u else nome)
        item.setData(Qt.UserRole, nome)
        return item

    def _nomes(self) -> list:
        return [self.lst.item(i).data(Qt.UserRole)
                for i in range(self.lst.count())]

    def _persistir(self):
        try:
            self._salvar(self._nomes(), dict(self._unidades))
        except Exception:  # noqa: BLE001
            _LOG.exception("Falha ao salvar a lista de equipe")

    def _recarregar(self, nomes, selecionar: str = "") -> None:
        self.lst.clear()
        for nome in dicom_rt.ordem_alfabetica(nomes):
            self.lst.addItem(self._item(nome))
        for i in range(self.lst.count()):
            if self.lst.item(i).data(Qt.UserRole) == selecionar:
                self.lst.setCurrentRow(i)
                self.lst.scrollToItem(self.lst.item(i))
                break

    def _adicionar(self):
        nome = self.ed.text().strip()
        if nome and nome not in self._nomes():
            escolhida = self.cb_unidade.currentText()
            self._unidades[nome] = "" if escolhida == self._TODAS else escolhida
            # Deixa o nome novo selecionado e visível: reordenar tira ele de onde
            # o olho estava esperando (o fim da lista).
            self._recarregar(self._nomes() + [nome], selecionar=nome)
            self._persistir()
        self.ed.clear(); self.ed.setFocus()

    def _ciclar_unidade(self, item) -> None:
        """Duplo clique: Todas → Clinica → SAT → Todas, no nome clicado."""
        nome = item.data(Qt.UserRole)
        ciclo = ["", *constantes.UNIDADES]
        atual = self._unidade(nome)
        i = ciclo.index(atual) if atual in ciclo else 0
        self._unidades[nome] = ciclo[(i + 1) % len(ciclo)]
        self._recarregar(self._nomes(), selecionar=nome)
        self._persistir()

    def _remover(self):
        for item in self.lst.selectedItems():
            self._unidades.pop(item.data(Qt.UserRole), None)
            self.lst.takeItem(self.lst.row(item))
        self._persistir()


class PainelEquipe(QWidget):
    """Aba Equipe: listas de Médicos e Físicos (persistidas ao editar)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        raiz = QVBoxLayout(self); raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(8)
        dica = QLabel(
            "A unidade ao lado do nome diz em quais aceleradores ele é "
            "oferecido na ficha — \"Todas\" aparece em qualquer um. Duplo "
            "clique num nome troca a unidade dele.")
        dica.setWordWrap(True)
        dica.setStyleSheet(f"color:{estilo.TEXTO_FRACO};")
        raiz.addWidget(dica)
        lay = QHBoxLayout(); lay.setSpacing(16)
        lay.addWidget(_ListaNomes("Médicos", _carregar_medicos, _salvar_medicos), 1)
        lay.addWidget(_ListaNomes("Físicos", _carregar_fisicos, _salvar_fisicos), 1)
        raiz.addLayout(lay)


class PainelMaquinas(QWidget):
    """Aba Máquinas: aceleradores e propriedades (somente leitura)."""

    _COLS = ["Máquina", "Imagem", "Frequência", "Mesa", "Vert. invert.", "SUS"]

    # A coluna Mesa mostra a CONVENÇÃO de coordenadas da mesa, não a família da
    # máquina. As chaves internas ("TB", "serie_c") continuam as mesmas — elas
    # escolhem o desenho da mesa na ficha e a escala do ângulo, e mexer nelas
    # remexeria ``dicom_rt``, ``ficha_pdf`` e os testes sem ganho nenhum.
    #
    # Os rótulos antigos enganavam: o Synergy01 é ELEKTA e aparecia como "TB".
    # Ele não é um TrueBeam — o que ele tem em comum com o TrueBeam é usar a
    # convenção IEC61217, que é justamente o que a coluna quer dizer. E
    # "serie_c" nomeava a família (600CD/6EX) em vez da escala Varian que elas
    # usam, onde o ângulo da mesa é 360−IEC (315 vira 45).
    _MESA_LABEL = {"TB": "IEC61217", "serie_c": "Varian IEC"}

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0)
        tab = QTableWidget(len(constantes.MAQUINAS), len(self._COLS))
        tab.setHorizontalHeaderLabels(self._COLS)
        tab.setEditTriggers(QTableWidget.NoEditTriggers)
        tab.verticalHeader().setVisible(False)
        for i, m in enumerate(constantes.MAQUINAS):
            vals = [m.chave, m.imagem, m.frequencia,
                    self._MESA_LABEL.get(m.grupo_mesa, m.grupo_mesa),
                    "Sim" if m.mesa_vert_invertida else "Não",
                    "Sim" if m.sus_elegivel else "Não"]
            for j, v in enumerate(vals):
                tab.setItem(i, j, QTableWidgetItem(str(v)))
        # Imagem/Frequência/Mesa/… com a MESMA largura (dividem o espaço), e a
        # coluna Máquina ajustada ao conteúdo (nome inteiro legível). Juntas
        # enchem toda a largura da aba.
        _hdr = tab.horizontalHeader()
        _hdr.setSectionResizeMode(QHeaderView.Stretch)
        _hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        lay.addWidget(tab, 1)


class PainelServico(QWidget):
    """Onde o serviço guarda as coisas — os três endereços, num lugar só.

    Estavam espalhados como botões na aba Capa ("Relatórios…", "Simulações…"),
    onde competiam com o trabalho de montar a folha e ainda apareciam para quem
    não podia usá-los. Aqui é configuração: entra-se de propósito, mexe-se uma
    vez, sai-se.

    Tudo grava em :mod:`config_servico` — vale para TODAS as estações, não para
    a máquina em que foi digitado. Quem escolheu e quando ficam junto.
    """

    def __init__(self, usuario: dict | None = None, parent=None):
        super().__init__(parent)
        self._usuario = (usuario or {}).get("usuario", "")
        # O conteúdo mora dentro de uma área de ROLAGEM, e isso é conserto de
        # uma regressão de 04/09/2026: dar altura aos rótulos que quebram linha
        # (o ``MinimumExpanding`` abaixo) empurrou a altura MÍNIMA do diálogo de
        # 728 para 948 px, e ele deixou de encolher. Em estação 1366x768 a faixa
        # com "Salvar" caía fora da tela — sem rolagem e sem como redimensionar,
        # que é pior que o texto cortado que a mudança consertava.
        #
        # Dentro da rolagem os dois valem juntos: o rótulo pede a altura de que
        # precisa, e o diálogo continua livre para encolher.
        fora = QVBoxLayout(self)
        fora.setContentsMargins(0, 0, 0, 0)
        rolagem = QScrollArea()
        rolagem.setWidgetResizable(True)
        rolagem.setFrameShape(QScrollArea.NoFrame)
        dentro_w = QWidget()
        rolagem.setWidget(dentro_w)
        fora.addWidget(rolagem)
        lay = QVBoxLayout(dentro_w)
        lay.setSpacing(14)

        cabecalho = QLabel(
            "Estes endereços valem para <b>todas as estações</b> que "
            "compartilham a pasta do programa. Uma variável de ambiente na "
            "estação (quando existir) tem precedência — é decisão de quem "
            "montou a máquina, e a tela mostra qual está valendo.")
        cabecalho.setWordWrap(True)
        estilo.pintar(cabecalho, lambda: f"color:{estilo.TEXTO_FRACO};")
        lay.addWidget(cabecalho)

        self._campos = {}
        lay.addWidget(self._bloco(
            "Sistema (banco de dados)", config_servico.DB_SERVIDOR,
            "SRVINSIGHT",
            "Servidor do data warehouse da Varian. É de onde a capa tira "
            "cadastro, prescrição e foto. VAZIO = o app lê os relatórios "
            "exportados, como antes.",
            pasta=False))
        lay.addWidget(self._bloco(
            "Relatórios exportados", config_servico.PASTA_RELATORIOS, "",
            "Pasta dos três relatórios (.csv e .mhtml). Com o banco ligado, "
            "servem só de último recurso — e envelhecem, porque ninguém os "
            "reexporta."))
        lay.addWidget(self._bloco(
            "Simulações", config_servico.RAIZ_SIMULACOES, "",
            "Raiz onde as pastas de simulação são gravadas."))
        lay.addWidget(self._bloco(
            "Exportação automática", config_servico.PASTA_EXPORTACAO, "",
            "Pasta onde os planos trazidos do ARIA são gravados. Apontar "
            "aqui garante que toda estação grave no MESMO lugar. VAZIO = ao "
            "lado do índice do serviço."))
        # A rede DICOM entrou aqui em 14/09/2026, e não por simetria: a
        # varredura passou a poder rodar por TAREFA AGENDADA na concentradora,
        # e tarefa agendada roda com OUTRA conta do Windows — que não enxerga
        # variável de ambiente de usuário. Configurada só por variável, a
        # varredura agendada não exportaria NADA, com o Agendador verde.
        lay.addWidget(self._bloco(
            "ARIA — servidor DICOM", config_servico.DICOM_SERVIDOR,
            "srvariadb.clinica.example:51404",
            "Endereço do DB Daemon do ARIA, no formato servidor:porta. É de "
            "onde a exportação automática traz o plano e as imagens. VAZIO = "
            "a exportação automática não roda nesta instalação.",
            pasta=False))
        lay.addWidget(self._bloco(
            "ARIA — AE Title do servidor", config_servico.DICOM_AE_REMOTO,
            "ARIA",
            "Como o ARIA se chama na rede DICOM. Vem da Varian ou da TI.",
            pasta=False))
        lay.addWidget(self._bloco(
            "ARIA — AE Title desta instalação", config_servico.DICOM_AE_LOCAL,
            "RADIOTERAFICHA",
            "Como NÓS nos chamamos ao pedir. Precisa estar cadastrado no "
            "ARIA, senão a conexão é recusada sem explicação.",
            pasta=False))
        lay.addWidget(self._bloco(
            "ARIA — destino do C-MOVE", config_servico.DICOM_AE_DESTINO,
            "RADIOTERAFICHA",
            "Para onde o ARIA manda os arquivos. O cadastro do destino amarra "
            "IP: quem recebe é a máquina cadastrada, mesmo que o pedido venha "
            "de outra. É isso que deixa UMA concentradora servir o serviço "
            "inteiro.",
            pasta=False))
        # Entrou em 18/09/2026: com a rede DICOM aqui, que vale para todas as
        # estações, alguém tem de dizer QUAL delas varre — senão todas varrem
        # (ver "Quem varre", no ``gatilho``). O nome desta máquina vai na ajuda
        # porque é o que o admin precisa copiar quando está NA concentradora.
        from isocentro.dominio import gatilho
        lay.addWidget(self._bloco(
            "Concentradora — quem varre", config_servico.CONCENTRADORA,
            "clinica-python01",
            "Nome da máquina (não o IP) que traz os planos do ARIA. Só ela "
            "varre, pelo app ou pela Tarefa Agendada; nas outras estações a "
            "exportação automática fica parada. VAZIO com a rede DICOM "
            "preenchida acima = nenhuma varre. Esta máquina se chama "
            f"<b>{gatilho.nome_desta_maquina() or '?'}</b>.",
            pasta=False))

        self.lbl_estado = QLabel("")
        self.lbl_estado.setWordWrap(True)
        lay.addWidget(self.lbl_estado)
        lay.addStretch(1)

        linha = QHBoxLayout()
        linha.addStretch()
        # "Reconectar agora" ao lado do "Testar": são coisas diferentes e a
        # clínica vinha confundindo as duas. TESTAR diagnostica em camadas e não
        # conserta nada; RECONECTAR joga fora a conexão e a espera e tenta
        # limpo. O contorno de antes era entrar aqui e SALVAR a configuração —
        # que só funcionava porque ``_salvar`` chama ``esquecer`` de passagem.
        self.btn_reconectar = QPushButton("🔄  Reconectar agora")
        estilo.pintar(self.btn_reconectar, estilo.btn_contorno)
        self.btn_reconectar.setCursor(Qt.PointingHandCursor)
        self.btn_reconectar.clicked.connect(self._reconectar)
        linha.addWidget(self.btn_reconectar)
        self.btn_testar = QPushButton("🔌  Testar o banco")
        estilo.pintar(self.btn_testar, estilo.btn_contorno)
        self.btn_testar.setCursor(Qt.PointingHandCursor)
        self.btn_testar.clicked.connect(self._testar)
        linha.addWidget(self.btn_testar)
        # O único sólido desta tela: é o que grava para todas as estações.
        self.btn_salvar = QPushButton("💾  Salvar")
        estilo.pintar(self.btn_salvar, estilo.btn_solido)
        self.btn_salvar.setCursor(Qt.PointingHandCursor)
        self.btn_salvar.clicked.connect(self._salvar)
        linha.addWidget(self.btn_salvar)
        lay.addLayout(linha)

        self._recarregar()

    def _bloco(self, titulo: str, chave: str, exemplo: str, ajuda: str,
               pasta: bool = True) -> QWidget:
        caixa = QGroupBox(titulo)
        dentro = QVBoxLayout(caixa)
        texto = QLabel(ajuda)
        texto.setWordWrap(True)
        # A política vertical MinimumExpanding, e ela não é enfeite: um QLabel
        # com quebra de linha responde ao layout a altura de UMA linha, e o
        # QVBoxLayout acredita. O texto saía cortado na segunda linha — o das
        # três caixas, não só o da que entrou em 04/09/2026 (renderizado no
        # tamanho que o próprio diálogo pede, 705x830). Aqui o cortado era
        # justamente a explicação de para onde vai documento de paciente.
        texto.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.MinimumExpanding)
        estilo.pintar(texto, lambda: f"color:{estilo.TEXTO_FRACO};")
        dentro.addWidget(texto)

        linha = QHBoxLayout()
        campo = QLineEdit()
        campo.setPlaceholderText(exemplo)
        linha.addWidget(campo, 1)
        if pasta:
            b = QPushButton("Procurar…")
            estilo.pintar(b, estilo.btn_contorno)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, c=campo: self._escolher(c))
            linha.addWidget(b)
        dentro.addLayout(linha)

        self._autoria = getattr(self, "_autoria", {})
        rotulo = QLabel("")
        # Quebra de linha: aqui cabe "Definido por … em …" MAIS o aviso de que
        # uma variável da estação está mandando neste campo. Medido no painel
        # real, o do servidor dá 1243 px num rótulo de 640 — sem quebrar, o que
        # some é o FIM da frase, que é justamente o endereço que está valendo.
        rotulo.setWordWrap(True)
        estilo.pintar(rotulo, lambda: f"color:{estilo.TEXTO_FRACO};"
                                      "font-size:11px;")
        dentro.addWidget(rotulo)
        self._campos[chave] = (campo, rotulo)
        return caixa

    def _escolher(self, campo) -> None:
        pasta = QFileDialog.getExistingDirectory(
            self, "Escolha a pasta", campo.text().strip() or os.path.expanduser("~"))
        if pasta:
            campo.setText(pasta)

    def _recarregar(self) -> None:
        for chave, (campo, rotulo) in self._campos.items():
            campo.setText(config_servico.valor(chave))
            quem, quando = config_servico.autoria(chave)
            # Quem apontou fica à vista: endereço de onde sai documento de
            # paciente não pode ser decisão anônima.
            texto = (f"Definido por {quem} em {quando[:16].replace('T', ' ')}"
                     if quem or quando else "Ainda não definido.")
            rotulo.setText(texto + self._quem_esta_mandando(chave))
        self._mostrar_estado()

    @staticmethod
    def _quem_esta_mandando(chave: str) -> str:
        """Aviso quando uma variável da ESTAÇÃO vence o que foi salvo aqui.

        Sem isto a tela mente por omissão: o admin aponta a pasta, lê "Salvo.
        Vale para todas as estações", e nesta máquina os planos continuam
        caindo noutro lugar — em silêncio, que é o modo de falhar que este
        campo existe para fechar. É a mesma razão do ``origem_da_pasta`` da
        Capa, e vale para cada campo que tenha variável de ambiente.

        No SERVIDOR o silêncio custa mais que numa pasta: a capa passa a nascer
        de outro banco, e o papel que vai para a sala não diz de qual. Até
        09/09/2026 este campo não avisava nada — nem tinha como, porque o
        ``capa_db`` lia a variável direto e só pelo nome antigo.
        """
        if chave == config_servico.DB_SERVIDOR:
            origem = capa_db.origem_do_servidor()
            # Pelo começo do texto, não por "estação" solta: as outras origens
            # ("configuração do serviço", "não apontado") não são aviso nenhum,
            # e casar por pedaço de palavra é como o alerta apareceria à toa.
            if not origem.startswith("variável"):
                return ""
            return (f"  ⚠ Nesta estação quem manda é a {origem}: "
                    f"{capa_db.servidor()}")
        # As quatro da rede DICOM, pelo mesmo motivo — e aqui o silêncio custa
        # o dobro: na concentradora, o degrau que vale muda com a CONTA que
        # roda. O admin preenche o campo, a estação continua mandando para a
        # conta dele, e a tarefa agendada (outra conta) usa o que está aqui.
        from isocentro.dados import ambiente
        from isocentro.adaptadores.dicom import rede as dicom_rede
        env = {
            config_servico.DICOM_SERVIDOR: dicom_rede.ENV_SERVIDOR,
            config_servico.DICOM_AE_REMOTO: dicom_rede.ENV_AE_REMOTO,
            config_servico.DICOM_AE_LOCAL: dicom_rede.ENV_AE_LOCAL,
            config_servico.DICOM_AE_DESTINO: dicom_rede.ENV_AE_DESTINO,
        }.get(chave, "")
        if env:
            valor = ambiente.ler(env)
            if not valor:
                return ""
            return (f"  ⚠ Nesta estação quem manda é a variável "
                    f"{ambiente.qual_valeu(env)}: {valor}")
        if chave != config_servico.PASTA_EXPORTACAO:
            return ""
        from isocentro.dominio import gatilho
        origem = gatilho.origem_da_pasta()
        if "estação" not in origem:
            return ""
        return (f"  ⚠ Nesta estação quem manda é a {origem}: "
                f"{gatilho.pasta_destino()}")

    def _mostrar_estado(self) -> None:
        origem = capa_dados.origem_da_pasta()
        situacao, recado = capa_db.estado()
        if situacao == "local":
            # ANTES do ramo do banco: com o banco local ligado não há servidor
            # apontado, e a linha saía "Fonte atual: banco ()" — que lê como
            # tela quebrada, não como simulação. Ver ``banco_local.py``.
            fonte = f"Fonte atual: <b>banco LOCAL gravado</b><br>{recado}"
        elif capa_db.configurado():
            fonte = f"Fonte atual: <b>banco</b> ({capa_db.servidor()})"
        else:
            dias = capa_dados.idade_dos_relatorios()
            idade = ("sem relatório" if dias is None else
                     "de hoje" if dias == 0 else
                     "de ontem" if dias == 1 else f"de {dias} dias atrás")
            fonte = f"Fonte atual: <b>relatórios exportados</b> ({idade})"
        try:
            from isocentro.banco import capa_espelho
            reserva = f" · reserva local: {capa_espelho.quantos()} pacientes"
        except Exception:  # noqa: BLE001
            reserva = ""
        self.lbl_estado.setText(
            f"{fonte}{reserva}<br>Relatórios lidos de "
            f"{capa_dados.pasta_dados()} <i>({origem})</i>")

    def _reconectar(self) -> None:
        """Descarta a conexão e a espera, e tenta de novo NA HORA.

        A espera automática (``capa_db.ESPERAS_APOS_FALHA_S``) já devolve o app
        sozinho depois de uma queda passageira. Este botão é para quem acabou
        de consertar a rede e não quer esperar por ela — e é o único caminho
        que também limpa o impedimento de driver, para o diagnóstico não ficar
        preso a uma resposta velha.

        Não confundir com "Testar o banco", ao lado: TESTAR diagnostica em
        camadas e não conserta nada; RECONECTAR tenta de novo, limpo.
        """
        capa_db.esquecer()
        if capa_db.conexao() is not None:
            ui.avisar(self, "Reconectar", "Conectado — o servidor respondeu.",
                      detalhe=capa_db.estado()[1])
            self._recarregar()
            return
        situacao, recado = capa_db.estado()
        # "Impedida" não é falha de rede: mandar tentar de novo seria mandar
        # repetir o que não pode dar certo. O "Testar o banco" ao lado é que
        # diz em qual camada parou.
        extra = ("\n\n" + "Use " + "\"" + "Testar o banco" + "\""
                 + " para ver em qual camada para.") if situacao == "impedida" else ""
        ui.alertar(self, "Reconectar",
                   "Esta estação não consegue conectar."
                   if situacao == "impedida" else "Ainda sem o servidor.",
                   detalhe=recado + extra)
        self._recarregar()

    def _testar(self) -> None:
        """Conecta de verdade antes de salvar, e DIZ o que falhou.

        Salvar um servidor errado faz TODAS as estações pararem de ler o banco
        de uma vez, e a falha só apareceria na próxima capa de alguém.

        Mostra as camadas (driver, rede, identidade, permissão) porque elas dão
        mensagens parecidas no driver ODBC e exigem providências opostas. A
        versão anterior dizia só "não consegui conectar" e mandava rodar
        ``tools/diagnostico_db.py`` — uma pasta que NÃO vai no pacote, ou seja,
        mandava quem está na clínica abrir um arquivo que não existe lá.
        """
        alvo = self._campos[config_servico.DB_SERVIDOR][0].text().strip()
        if not alvo:
            ui.avisar(self, "Testar o banco",
                                    "Preencha o servidor primeiro.")
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            passos = capa_db.diagnosticar(alvo)
        finally:
            QApplication.restoreOverrideCursor()
            capa_db.esquecer()

        quebra = chr(10)
        # ``ok`` é de TRÊS estados (ver ``capa_db.diagnosticar``): ``None`` é
        # "não concluí nada". Lido como falso — que é o que ``if ok`` faz —, o
        # passo inconclusivo da instância nomeada virava "FALHA" e a caixa
        # anunciava "Parou em: Rede" logo acima das camadas que continuaram
        # rodando e responderam.
        def marca(ok) -> str:
            if ok is None:
                return "—    "
            return "OK   " if ok else "FALHA"

        linhas = [f"{marca(ok)}  {nome}{quebra}        {recado}"
                  for nome, ok, recado in passos]
        tudo_bem = all(ok is not False for _n, ok, _r in passos)
        dizer = ui.avisar if tudo_bem else ui.alertar
        dizer(self, "Testar o banco",
              "Conectado — o banco responde e as tabelas da capa foram lidas."
              if tudo_bem else
              "Parou em: " + next(n for n, ok, _r in passos if ok is False),
              detalhe=(quebra * 2).join(linhas),
              # O log continua sendo o lugar do rastro cru, para quem abre
              # chamado — na gaveta, não no meio do que o usuário lê.
              tecnico=("Registro completo em:" + quebra
                       + os.path.join(os.path.expanduser("~"),
                                      ".isocentro.log")))

    def _salvar(self) -> None:
        falhou = []
        for chave, (campo, _) in self._campos.items():
            if not config_servico.definir(chave, campo.text().strip(),
                                          self._usuario):
                falhou.append(chave)
        capa_db.esquecer()
        # E já reabre em segundo plano: o admin pode ter acabado de apontar
        # OUTRO servidor, e sem isto quem pagaria o tempo-limite do primeiro
        # connect seria a próxima capa — na thread da interface, com a tela
        # parada. Mesmo motivo do ``aquecer()`` no arranque.
        capa_db.aquecer()
        capa_dados.definir_pasta_dados("")   # volta a resolver pela precedência
        simulacao.definir_raiz("")
        # A lista de pacientes da busca é lida uma vez por sessão. Trocar a
        # pasta ou o servidor sem invalidá-la deixava a busca oferecendo os
        # pacientes do lugar antigo pelo resto do dia.
        # O dono é o ``ControleCapa`` desde o corte 5 da R-06. Era um
        # ``hasattr(janela, "_pacientes_carregados")``, e com o atributo mudando
        # de dono ele passaria a dar falso sem erro nenhum — a mesma lista velha,
        # pela mesma porta calada. A tela solta (sem janela principal, nos
        # testes) continua sem ter o que invalidar.
        controle = getattr(self.window(), "controle_capa", None)
        if controle is not None:
            controle.pacientes_carregados = False
        self._recarregar()
        if falhou:
            ui.alertar(
                self, "Configuração do serviço",
                f"Não consegui gravar em {config_servico.caminho()}.\n\n"
                "As mudanças valem NESTA sessão e não chegaram às outras "
                "estações. Verifique se a pasta do programa é gravável.")
        else:
            ui.avisar(
                self, "Configuração do serviço",
                "Salvo. Vale para todas as estações que compartilham a pasta "
                "do programa.")


class DialogConfiguracoes(ui.Dialogo):
    """Configurações do app — TODAS as abas são de admin.

    Máquinas ficava aberta a todos, e não devia: os aceleradores do serviço,
    suas energias e apelidos são cadastro que a ficha inteira consome. Quem
    monta ficha usa essa lista; quem a define é o admin. Deixá-la à mão de
    todos era convite a mexer no que parece inofensivo e reaparece errado no
    papel de outra pessoa.

    Com isso não sobra nada para não-admin ver aqui — e o botão que abre esta
    janela já é só de admin. O ramo de não-admin fica como porta trancada, não
    como janela vazia: quem chegar por outro caminho recebe um recado dizendo a
    quem pedir, em vez de um diálogo sem conteúdo e sem explicação.
    """

    def __init__(self, usuario: dict | None = None, parent=None):
        super().__init__("Configurações", parent)
        lay = self.corpo
        if (usuario or {}).get("papel") != "admin":
            self.resize(430, 160)
            aviso = QLabel(
                "As configurações são do administrador.\n\n"
                "Peça a ele para apontar o banco, as pastas do serviço, os "
                "usuários, a equipe e as máquinas.")
            aviso.setWordWrap(True)
            lay.addWidget(aviso, 1)
            # Porta trancada: só há o que ler, então nem sólido nem "Cancelar"
            # — o botão era SÓLIDO aqui, prometendo um passo que não existe.
            self.rodape()
            return
        self.resize(940, 480)
        # "Serviço" primeiro: é o que faz o app achar os dados. Sem ele
        # apontado, as outras abas não têm sobre o que trabalhar.
        abas = ui.abas((PainelServico(usuario), "Serviço"),
                       (PainelUsuarios(), "Usuários"),
                       (PainelEquipe(), "Equipe"),
                       (PainelMaquinas(), "Máquinas"))
        lay.addWidget(abas, 1)
        # A aba Usuários já traz o Fechar ao lado do Histórico.
