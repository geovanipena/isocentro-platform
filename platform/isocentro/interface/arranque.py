"""A porta de entrada do app: o ``main``, a rede de segurança e o modo dev.

Separado de ``gui.py`` em 16/09/2026 (R-06, corte 2 do
``docs/PROPOSTA_GUI.md``). É o que roda ANTES da janela existir — log, caixa de
erro, login —, e nada disso lê ou grava estado da ``JanelaPrincipal``.

O endereço antigo **não** foi reimportado no ``gui.py``, ao contrário das
extrações de agosto. Os testes da rede de segurança trocam ``_avisar_erro``
no módulo: com um apelido em ``gui``, a troca em ``gui._avisar_erro`` passaria
a valer para ninguém, e o teste abriria a caixa MODAL de verdade — a suíte
trava esperando um clique. Um endereço só, e quem troca troca aqui.
"""
from __future__ import annotations

import logging
import os
import sys
import threading

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QDialog

from isocentro.interface.ajustes import ajustes
from isocentro.banco import capa_db
from isocentro.dados import ambiente
from isocentro.dados import auth
from isocentro.dados import historico
from isocentro.dados import log_app
from isocentro.dados import sessao
from isocentro.interface import estilo
from isocentro.interface import ui
from isocentro.interface.administracao import DialogLogin
from isocentro.interface.aparencia import _ESTILO, _icone_app, aplicar_modo
from isocentro.interface.gui import JanelaPrincipal

_LOG = logging.getLogger(__name__)


# A caixa de erro está aberta agora? Ver ``_avisar_erro``.
_avisando = False


def _avisar_erro(texto: str) -> None:
    """A caixa do erro. Separada do registro para o teste poder trocá-la.

    ``QMessageBox`` é MODAL: chamada de dentro da suíte, ela fica esperando um
    clique que nunca vem e a suíte TRAVA — foi o que aconteceu na primeira
    versão desta rede de segurança. O que precisa ser testado é o registro no
    log; a caixa é o enfeite por cima dele.

    E ela **não reentra**. Uma exceção vinda de ``paintEvent`` ou
    ``resizeEvent`` se repete a cada repintura — e como o ``exec`` da caixa modal
    roda o laço de eventos, cada repintura abriria OUTRA caixa por cima. O
    programa ficaria impossível de fechar, que é pior do que o ``abort()`` que
    esta rede veio substituir: ao menos aquele terminava.

    Enquanto uma caixa está de pé, as exceções seguintes só vão para o log — que
    é onde elas serão lidas de qualquer forma.
    """
    global _avisando
    if _avisando or QApplication.instance() is None:
        # Sem ``QApplication``, o Qt não levanta exceção Python: ele chama
        # ``qFatal`` e mata o processo. Por isso a checagem vem ANTES da caixa,
        # e não como ``except`` em volta dela.
        return
    _avisando = True
    try:
        ui.falhar(
            None, "Erro inesperado",
            f"{texto}\n\nO programa continua aberto. O detalhe foi gravado em\n"
            f"{os.path.join(os.path.expanduser('~'), '.isocentro.log')}")
    except Exception:  # noqa: BLE001 — o log já tem o que importa
        _LOG.exception("Falha ao mostrar a caixa de erro")
    finally:
        _avisando = False


def _instalar_rede_de_seguranca() -> None:
    """Exceção que escapa passa a AVISAR, em vez de matar o programa.

    O PyQt5 chama ``abort()`` quando uma exceção escapa de um slot. Na prática:
    a pessoa clica num paciente e a janela SOME — sem log, sem mensagem, sem
    nada para contar ao suporte. Aconteceu exatamente assim na aba
    Ficha Virtual (um ``sum`` sobre campo de dose, que é texto), e o pior não
    foi o defeito: foi ele não ter deixado rastro nenhum.

    Aqui o traceback vai para o log E para uma janela que diz onde ele está. O
    programa continua de pé — o que é quase sempre melhor num app que tem
    trabalho não salvo na tela: quem perdeu a bancada inteira por causa de um
    campo de dose não recupera aquilo.

    O ``KeyboardInterrupt`` passa direto: Ctrl+C no console é pedido de sair, e
    transformá-lo em caixa de diálogo tornaria o app impossível de fechar por ali.
    """
    def _tratar(tipo, valor, tb):
        if issubclass(tipo, KeyboardInterrupt):
            sys.__excepthook__(tipo, valor, tb)
            return
        _LOG.critical("Erro não tratado", exc_info=(tipo, valor, tb))
        _avisar_erro(f"{tipo.__name__}: {valor}")

    sys.excepthook = _tratar


def _usuario_de_dev(valor: str) -> dict:
    """O usuário do modo desenvolvimento, a partir do valor de ``ISOCENTRO_DEV``.

    O VALOR pode ser uma FUNÇÃO (``ISOCENTRO_DEV=medico``): é como se vê o app
    com os olhos de cada uma — as abas são recortadas por papel (ver
    ``fichinha.modos_do_papel``) — sem criar usuário de mentira no
    ``usuarios.json``, que é arquivo do serviço e é lido por todas as estações.

    Qualquer outro valor (``1``, ``sim``, o que for) continua sendo **admin**,
    que é como o modo dev sempre funcionou: quem liga a variável para trabalhar
    quer a bancada inteira, não um recorte.

    O papel entra no NOME que a janela mostra. Sem isso, três janelas abertas
    lado a lado para comparar as funções ficariam idênticas no cabeçalho, e a
    comparação valeria pelo que se lembra de ter clicado.
    """
    papel = str(valor or "").strip().lower()
    if papel not in auth.PAPEIS:
        papel = "admin"
    return {"usuario": "dev", "papel": papel,
            "nome": f"Desenvolvedor — {papel} (modo dev)"}


def _subir_postgres_local() -> None:
    try:
        from isocentro.adaptadores.postgres import local  # noqa: PLC0415
        feito = local.subir_se_preciso()
    except Exception:  # noqa: BLE001 - nunca derruba a abertura do app
        logging.getLogger(__name__).exception("PostgreSQL local: falha ao subir")
        return
    if feito:
        logging.getLogger(__name__).info(feito)


def main():
    log_app.configurar()
    # ANTES de qualquer widget: é o que garante que uma falha na montagem da
    # janela também deixe rastro.
    _instalar_rede_de_seguranca()
    # No Windows, um AppUserModelID próprio faz a barra de tarefas usar o ícone
    # do app (em vez do ícone do python.exe).
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "geovani.isocentro")
        except Exception:  # noqa: BLE001
            pass   # só o ícone da barra de tarefas — puramente cosmético
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    # Modo de cor lembrado da última sessão — a estação costuma ter um dono, e
    # a sala é clara de manhã e escura à tarde. ``aplicar_modo`` já monta a
    # paleta do sistema com o modo escolhido.
    aplicar_modo(ajustes()
                 .value("modo_cor", estilo.MODO_PADRAO, type=str))
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    estilo.pintar(app, lambda: _ESTILO())
    app.setWindowIcon(_icone_app())

    # Abre a conexão com o banco em segundo plano, AGORA — antes do login, que
    # é o tempo morto perfeito: a pessoa digita usuário e senha enquanto o
    # servidor responde. Sem isto, a primeira capa da sessão pagava o
    # ``TEMPO_LIMITE_S`` inteiro com a tela parada, porque a capa é montada na
    # thread da interface. Não muda o que ``conexao()`` devolve a ninguém — só
    # quem paga a espera, e quando.
    capa_db.aquecer()
    # O PostgreSQL local, na estação de desenvolvimento (ver o módulo): no
    # mesmo tempo morto do login, numa thread — a checagem da porta espera
    # até meio segundo, e a abertura do app não paga nem isso.
    threading.Thread(target=_subir_postgres_local, daemon=True).start()

    # Modo desenvolvimento (ISOCENTRO_DEV): pula o login e usa um usuário 'dev'.
    # O F5 relança herdando o ambiente, então continua sem pedir login.
    _dev = str(ambiente.ler("ISOCENTRO_DEV") or "").strip()
    if _dev:
        usuario = _usuario_de_dev(_dev)
    else:
        # Login obrigatório. Semeia o admin inicial (admin/admin, troca no 1º
        # acesso) se ainda não houver nenhum. Sem autenticação, o app não abre.
        try:
            semeou = auth.semear_admin_se_vazio()
        except Exception:  # noqa: BLE001
            semeou = False
        login = DialogLogin()
        if semeou:
            ui.avisar(
                login, "Primeiro acesso",
                "Nenhum usuário cadastrado — criei o administrador inicial:\n\n"
                "Usuário: admin\nSenha: admin\n\n"
                "Você precisará trocar a senha ao entrar.")
        if login.exec() != QDialog.Accepted or login.usuario() is None:
            sys.exit(0)
        usuario = login.usuario()

    historico.definir_usuario(usuario)
    historico.registrar("login")
    # Uma sessão por usuário (ver ``sessao``): ESTE login passa a ser o dono, e
    # a estação onde a conta estava aberta trava no próximo meio minuto. Fica
    # fora do ramo do modo dev de propósito — ele não passa pelo login, e uma
    # sessão de mentira derrubaria a pessoa de verdade que estiver na clínica.
    if not _dev:
        sessao.abrir(usuario)
    janela = JanelaPrincipal(usuario=usuario)
    janela.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
