#!/usr/bin/env python
"""Grava o PNG de uma tela do programa, para conferir mudança visual.

É o `tools/caso.py` do papel, mas para a TELA. Existe porque conferir layout à
mão tem duas armadilhas que se disfarçam de bug e as duas já custaram tempo
aqui:

  * **`QT_QPA_PLATFORM=offscreen` não desenha TEXTO.** O `grab()` sai com as
    caixas e as cores certas e todos os rótulos vazios. Parece layout quebrado,
    e não é — é a plataforma. Esta ferramenta GRAVA a plataforma certa antes de
    o PyQt entrar (gravar, não `setdefault`: o `caso.py`, que ela importa para
    carregar um caso, põe `offscreen` no momento em que é importado, e um
    `setdefault` chegaria tarde e perderia).
  * **`JanelaPrincipal(...)` derruba o processo sem `setStyleSheet` antes.**
    Exit 127 e nenhum traceback — não há o que depurar, só a ordem certa:
    `QApplication` → `aplicar_modo` → `app.setStyleSheet(gui._ESTILO())` → só
    então construir a janela.

    python tools/tela.py --lista                    # que alvos existem
    python tools/tela.py principal                  # a janela, bancada vazia
    python tools/tela.py principal --caso TC8       # com um caso real dentro
    python tools/tela.py principal:form --modo dia  # só um painel, no claro
    python tools/tela.py principal -o antes.png     # nomear, para comparar

O widget é capturado **sem `show()`**, de propósito: conferir uma tela não pode
custar uma janela pulando na cara de quem está usando a máquina.

O que ela NÃO faz: diálogos que exigem argumentos de construção (a capa, o
agendamento, o cadastro). Inventar os argumentos daria uma tela que não
corresponde a estado nenhum — é a mesma razão pela qual o `caso.py` não monta
agendamento. Para esses, o caminho continua sendo abrir o app.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

# Tamanho de captura. A janela nunca foi mostrada, então não tem tamanho de
# tela nenhum para herdar: sem isto o `grab()` sai no tamanho mínimo do layout,
# que não é o que ninguém vê. 1600×1000 é a resolução de trabalho da estação.
TAMANHO_PADRAO = (1600, 1000)

ALVOS = {
    "principal": "A janela do programa (`gui.JanelaPrincipal`).",
}


def escolher_plataforma() -> str:
    """Grava a plataforma Qt que DESENHA TEXTO. Devolve a que ficou valendo.

    Chamada do ``main``, e não no topo do módulo, por um motivo que já mordeu
    este projeto por outro caminho: mexer em ``os.environ`` no import faria com
    que **importar** este arquivo — num teste, por exemplo — arrancasse o
    ``offscreen`` de baixo da suíte inteira, e o estrago apareceria noutro
    arquivo de teste, na ordem alfabética do `discover`. Aqui a troca acontece
    dentro do ``main``, que roda antes de qualquer import de PyQt deste
    processo, que é a única garantia de que ela precisa.

    Atribuição, não ``setdefault``: a variável que se quer trocar quase sempre
    JÁ existe (o ``tools/caso.py`` põe ``offscreen`` ao ser importado), e é
    justamente ela que não desenha texto.
    """
    if "PySide6.QtWidgets" in sys.modules:
        # A plataforma é lida quando o QApplication nasce; depois disso, mudar a
        # variável não muda nada e o PNG sairia mudo sem ninguém avisar.
        print("aviso: o PyQt já estava importado — a plataforma pode não ter "
              "mudado, e a captura pode sair sem texto.", file=sys.stderr)
    if sys.platform == "win32":
        os.environ["QT_QPA_PLATFORM"] = "windows"
    elif os.environ.get("QT_QPA_PLATFORM") == "offscreen":
        # Fora do Windows a plataforma com texto é a do sistema
        # (``xcb``/``wayland``) e ela pode simplesmente não existir — num runner
        # de CI, por exemplo. Aqui não se adivinha: tira-se o ``offscreen``
        # explícito e deixa-se o Qt escolher. Sem tela, o Qt falha dizendo isso,
        # que é melhor que um PNG mudo.
        del os.environ["QT_QPA_PLATFORM"]
    return os.environ.get("QT_QPA_PLATFORM", "(a do sistema)")


def _alvo_e_caminho(pedido: str) -> tuple[str, str]:
    """Separa ``principal:form.pac_nome`` em alvo e caminho do filho."""
    alvo, _, caminho = pedido.partition(":")
    return alvo.strip(), caminho.strip()


def _descer(raiz, caminho: str):
    """Desce por atributos (``form.pac_nome``) até o widget pedido.

    Devolve ``None`` em vez de estourar: quem chamou sabe listar o que existe,
    e "não achei `form.pac_nom`" com a lista ao lado resolve o erro de digitação
    na hora, sem um traceback pelo meio.
    """
    atual = raiz
    for parte in caminho.split("."):
        if not parte:
            continue
        atual = getattr(atual, parte, None)
        if atual is None:
            return None
    return atual


def _filhos_nomeados(janela) -> list[str]:
    """Os atributos da janela que são widgets — os caminhos que dá para pedir.

    Serve ao `--lista`: sem isto, descobrir que existe um `form` para capturar
    exigiria abrir o `gui.py`, que é a leitura de 5,6 mil linhas que este
    projeto inteiro tenta evitar.
    """
    from PySide6.QtWidgets import QWidget

    nomes = []
    for nome in sorted(vars(janela)):
        if nome.startswith("__"):
            continue
        valor = getattr(janela, nome, None)
        if isinstance(valor, QWidget):
            nomes.append(f"{nome}  ({type(valor).__name__})")
    return nomes


def _montar(modo: str, falar):
    """A sequência que não derruba o processo. A ordem aqui é o ponto."""
    from PySide6.QtWidgets import QApplication

    from isocentro.interface import estilo
    from isocentro.interface import gui

    app = QApplication.instance() or QApplication([])
    # `aplicar_modo` GRAVA o modo nas preferências da estação (QSettings
    # "modo_cor") e DEVOLVE o modo novo, não o antigo — o anterior tem de ser
    # perguntado antes, ao `estilo`. Sem isso, conferir uma tela no claro
    # deixaria o app do usuário no claro na próxima abertura: uma ferramenta de
    # conferência não pode mudar o que ela veio conferir.
    modo_antes = estilo.modo()
    gui.aplicar_modo(modo)
    app.setStyleSheet(gui._ESTILO())
    falar(f"modo {modo} (antes: {modo_antes})")

    janela = gui.JanelaPrincipal(
        usuario={"usuario": "tela", "nome": "Conferência", "papel": "admin"})
    return app, gui, janela, modo_antes


def _carregar_caso(janela, nome: str, falar) -> bool:
    """Enche a bancada com um caso real, pelo caminho do programa.

    Tela vazia esconde metade das regressões de layout: coluna que não cabe,
    rótulo que elide, linha que estoura a altura — nada disso aparece sem dado
    dentro. Quem sabe carregar é o `caso.py`, e é ele que se chama aqui em vez
    de uma segunda implementação que envelheceria em paralelo.
    """
    import caso as ferramenta

    pasta = ferramenta._resolver(nome)
    if pasta is None:
        disponiveis = ", ".join(p.name for p in ferramenta._casos_disponiveis())
        falar(f"caso '{nome}' não existe. Há: {disponiveis}")
        return False
    falar(f"carregando {pasta.name}…")
    return ferramenta._carregar(janela, pasta, lambda m: None)


def _gravar(widget, saida: Path, tamanho: tuple[int, int], falar) -> bool:
    """Captura SEM `show()` e confere que saiu tela, não um retângulo vazio."""
    widget.resize(*tamanho)
    # O layout de uma janela nunca mostrada só se assenta quando alguém pede:
    # sem isto, filhos ficam na posição (0,0) e o PNG sai com tudo empilhado no
    # canto — que também parece bug de layout e também não é.
    widget.adjustSize()
    widget.resize(*tamanho)

    pix = widget.grab()
    if pix.isNull():
        falar("o grab() não devolveu imagem nenhuma — nada gravado.")
        return False
    if not pix.save(str(saida)):
        falar(f"não consegui gravar {saida}")
        return False
    falar(f"{saida}  ({pix.width()}×{pix.height()})")
    return True


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("alvo", nargs="?",
                   help="`principal`, ou `principal:form` para um filho")
    p.add_argument("--lista", action="store_true",
                   help="lista os alvos (e os filhos da janela) e sai")
    p.add_argument("-o", "--saida", type=Path,
                   help="arquivo PNG (padrão: <alvo>_<modo>.png ao lado daqui)")
    p.add_argument("--modo", default="noite", choices=("dia", "noite"),
                   help="metade das regressões de cor só aparece num dos dois")
    p.add_argument("--caso", help="carrega um caso de TCs_Teste antes (TC8, …)")
    # Desde a R-23 a janela abre no Início: sem isto, nenhum módulo sem caso
    # carregado tinha como sair no PNG.
    p.add_argument("--modulo", help="abre um módulo do shell antes "
                                    "(radioteraficha, plano, indicadores…)")
    p.add_argument("--tamanho", default="x".join(map(str, TAMANHO_PADRAO)),
                   help="LARGURAxALTURA da captura")
    args = p.parse_args(argv)

    def falar(msg: str) -> None:
        print(f"  {msg}", flush=True)

    if args.lista and not args.alvo:
        print("Alvos:")
        for nome, oquee in ALVOS.items():
            print(f"  {nome:12s} {oquee}")
        print("\nPara ver os filhos capturáveis de um alvo: "
              "`tools/tela.py principal --lista`")
        return 0

    if not args.alvo:
        p.print_help()
        return 2

    alvo, caminho = _alvo_e_caminho(args.alvo)
    if alvo not in ALVOS:
        print(f"Alvo '{alvo}' não existe. Há: {', '.join(ALVOS)}",
              file=sys.stderr)
        return 1

    try:
        largura, _, altura = args.tamanho.lower().partition("x")
        tamanho = (int(largura), int(altura))
    except ValueError:
        print(f"--tamanho '{args.tamanho}' não é LARGURAxALTURA (ex.: 1600x1000)",
              file=sys.stderr)
        return 1

    falar(f"QT_QPA_PLATFORM={escolher_plataforma()}")

    app, gui, janela, modo_antes = _montar(args.modo, falar)
    try:
        # A plataforma MEDIDA, não a pedida: o Qt escolhe a dele quando o
        # `QApplication` nasce, e se algo já o tiver criado antes (ou se o
        # pedido não valer nesta máquina) a variável de ambiente não conta a
        # verdade. `offscreen` aqui significa PNG com todos os rótulos vazios —
        # que parece bug de layout e não é. Recusar é melhor que entregar uma
        # conferência que mente. Dentro do `try` porque o modo já foi trocado
        # ali em cima: sair por aqui sem devolvê-lo deixaria a preferência da
        # estação mexida por causa de um erro.
        if app.platformName() == "offscreen":
            print("O Qt subiu em `offscreen`, que NÃO desenha texto: a captura "
                  "sairia com os rótulos vazios. Rode num terminal sem "
                  "QT_QPA_PLATFORM=offscreen no ambiente.", file=sys.stderr)
            return 1
        falar(f"plataforma em uso: {app.platformName()}")

        if args.lista:
            print(f"\nFilhos capturáveis de `{alvo}`:")
            for nome in _filhos_nomeados(janela):
                print(f"  {alvo}:{nome}")
            return 0

        if args.caso and not _carregar_caso(janela, args.caso, falar):
            print("Nada carregado — a tela sairia vazia, que não é o que você "
                  "pediu.", file=sys.stderr)
            return 1

        if args.modulo:
            janela._abrir_modulo(args.modulo)

        widget = _descer(janela, caminho) if caminho else janela
        if widget is None:
            print(f"'{caminho}' não existe na janela. Veja os filhos com "
                  f"`tools/tela.py {alvo} --lista`.", file=sys.stderr)
            return 1

        saida = args.saida or RAIZ / "tools" / f"{alvo}_{args.modo}.png"
        saida.parent.mkdir(parents=True, exist_ok=True)
        return 0 if _gravar(widget, saida, tamanho, falar) else 1
    finally:
        # Devolver o modo ANTES de qualquer saída: a preferência da estação é do
        # usuário, e ele não pediu para trocá-la.
        if modo_antes != args.modo:
            gui.aplicar_modo(modo_antes)
        app.processEvents()


if __name__ == "__main__":
    raise SystemExit(main())
