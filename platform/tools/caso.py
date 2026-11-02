#!/usr/bin/env python
"""Carrega um caso real de ``TCs_Teste/`` e gera a ficha, pronta para conferir.

Por que existe: o `CLAUDE.md` manda, para mudança no PDF, **gerar e medir** — e
esse era o único dos rituais do projeto sem ferramenta nenhuma. Fazer à mão é
abrir o app, navegar até a pasta, carregar, esperar, gerar e comparar; sendo
assim, é o passo que se pula quando o dia aperta. E teste que passa não prova
que o papel está certo: a suíte confirma que a função devolve o que o teste
espera, e nenhuma confere se a dose impressa na célula é a dose do plano.

    python tools/caso.py --lista          # que casos existem
    python tools/caso.py TC8              # gera a ficha do TC8
    python tools/caso.py TC8 --abrir      # e abre o PDF no visualizador
    python tools/caso.py TC8 -o antes.pdf # nomeia a saída, para comparar depois

O fluxo é o do PROGRAMA, não uma reimplementação: monta a ``JanelaPrincipal``
de verdade (invisível), roda o mesmo ``_CarregarTudo`` que o botão "Abrir
pasta" dispara, e chama o mesmo ``ControleFicha.montar_planos_pdf``. Uma ficha gerada aqui
sai pelo caminho por onde sai a da sala — que é a única forma de a conferência
valer alguma coisa.

O que ele NÃO faz de propósito: agendamento, separação de ficha e capa. São
decisões que alguém toma na tela, e inventá-las aqui daria uma ficha que não
corresponde a escolha nenhuma. A página 3 sai como o programa a monta sem
agendamento.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

# ANTES de importar qualquer coisa do PyQt: sem isto a janela aparece de
# verdade na tela, e a ferramenta serve justamente para não precisar dela.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

CASOS = RAIZ / "TCs_Teste"


def _casos_disponiveis() -> list[Path]:
    """As pastas de caso, sem as que não são caso.

    ``banco de dados`` é material de apoio do data warehouse, não um paciente.
    """
    if not CASOS.is_dir():
        return []
    return sorted(p for p in CASOS.iterdir()
                  if p.is_dir() and p.name != "banco de dados")


def _quantos_arquivos(pasta: Path) -> int:
    """Quantos arquivos o worker vai varrer nesta pasta.

    As MESMAS extensões de ``_CarregarTudo._arquivos_dicom`` — e não só
    ``.dcm``. A primeira versão contava apenas os ``.dcm``, e teria mostrado
    ZERO para um caso inteiro que chegasse empacotado em ``.zip``/``.rar``,
    que é como parte do acervo vem.
    """
    extensoes = {".dcm", ".zip", ".rar"}
    return sum(1 for p in pasta.rglob("*")
               if p.suffix.lower() in extensoes and p.is_file())


def _resolver(nome: str) -> Path | None:
    """Aceita ``TC8``, ``tc8`` ou o caminho de uma pasta qualquer."""
    direto = Path(nome)
    if direto.is_dir():
        return direto
    for p in _casos_disponiveis():
        if p.name.lower() == nome.lower():
            return p
    return None


def _responder_dose_alta(falar):
    """Responde, sozinho, o popup de fracionamento de dose alta.

    **O que travava a ferramenta.** ``_carregar`` reaproveita o caminho da
    janela, e ele pergunta o fracionamento quando algum plano passa de 600 cGy
    por fração. Num terminal offscreen esse modal não aparece e ninguém o
    fecha: o ``exec_()`` dele roda um laço aninhado, e nem a rede de 300 s
    salva, porque ela derruba o laço de FORA. TC6, TC7, TC9 e TC11 —
    justamente os casos de hipofracionamento — ficavam pendurados para sempre,
    sem uma linha dizendo o porquê. Era o único ponto do fluxo que ainda
    perguntava algo, e a docstring de ``_carregar`` já dizia que aqui não há
    ninguém para responder.

    Desde 01/09/2026 a pergunta saiu do slot do worker e passou para o fim da
    carga (o modal com o worker vivo travava a janela DE VERDADE, na clínica);
    quem a dispara aqui é o próprio ``_carregar``, depois do laço.

    Responde com o PADRÃO DO PRÓPRIO POPUP (``formulario._frac_inicial``), que é
    o que sairia de um Ok imediato — e não com uma política inventada aqui, que
    envelheceria em silêncio no dia em que a do popup mudasse. E DIZ que
    respondeu: ficha que se monta a partir de uma escolha que ninguém fez tem de
    anunciar a escolha, senão a conferência valida um palpite.

    Devolve a função original para quem chamou REPOR — nunca ``del``: apagar o
    atributo depois de gravar por cima some com a original para o processo todo.
    """
    from isocentro.interface import formulario

    original = formulario.PainelFormulario.perguntar_doses_altas

    def _responder(self):
        abas = [aba for i in range(self.abas.count())
                if (aba := self.abas.widget(i)) is not None]
        altos = [aba for aba in abas
                 if aba.rx_dose_fracao.value() > formulario._DOSE_FRAC_ALTA]
        if not altos:
            return
        # As MESMAS linhas que o popup mostraria: com mais de um plano ele
        # lista todos, porque o dia de início interliga os planos.
        for aba in (abas if len(abas) > 1 else altos):
            eh_alto = aba.rx_dose_fracao.value() > formulario._DOSE_FRAC_ALTA
            escolha = formulario._frac_inicial(
                aba.rx_fracoes.value(), aba.rx_fracionamento.currentText(),
                dose_alta=eh_alto)
            aba.rx_fracionamento.setCurrentText(escolha)
            rot = getattr(aba, "_rotulo", "") or "plano"
            falar(f"  dose alta em {rot} "
                  f"({aba.rx_dose_fracao.value():.2f} Gy/fr): fracionamento "
                  f"'{escolha}' — padrão do popup, ninguém foi perguntado")

    formulario.PainelFormulario.perguntar_doses_altas = _responder
    return original


def _carregar(janela, pasta: Path, falar) -> bool:
    """Roda o worker de leitura e espera, sem travar o loop do Qt.

    Não se chama ``_carregar_pasta``: aquele caminho pergunta coisas — trocar
    de paciente, reabrir ficha salva — e aqui não há ninguém para responder.
    O que se reaproveita é o que interessa, o worker e os slots que assentam o
    estado da janela. A única pergunta que sobra — o fracionamento da dose alta,
    disparada aqui no fim da carga, como na janela — está respondida em
    ``_responder_dose_alta``.
    """
    from PySide6.QtCore import QEventLoop, QTimer

    from isocentro.interface.carregadores import _CarregarTudo

    janela.caso.pasta_carregada = str(pasta)
    worker = _CarregarTudo(str(pasta), janela)
    janela._worker_tudo = worker
    worker.ct_pronto.connect(janela._tc_carregada)
    worker.plano_pronto.connect(janela._plano_carregado)
    worker.progresso.connect(falar)

    falhas: list[str] = []
    worker.falhou.connect(falhas.append)

    loop = QEventLoop()
    worker.finished.connect(loop.quit)
    # Rede: um worker que morre sem emitir ``finished`` deixaria a ferramenta
    # pendurada para sempre num terminal sem ninguém olhando. Ela NÃO cobre
    # modal aberto por um slot — aquele roda um laço aninhado, e derrubar este
    # de fora não o fecha. Ver ``_responder_dose_alta``.
    QTimer.singleShot(300_000, loop.quit)
    from isocentro.interface import formulario
    original = _responder_dose_alta(falar)
    try:
        worker.start()
        loop.exec()
        # Fim da carga: é aqui que a janela pergunta o fracionamento da dose
        # alta (o slot não pergunta mais nada, ver o gui). Só ele — agendamento
        # e capa continuam de fora, que são decisões de tela.
        if janela.caso.planos:
            janela.form.perguntar_doses_altas()
    finally:
        formulario.PainelFormulario.perguntar_doses_altas = original

    if falhas:
        for msg in falhas:
            falar(f"  falha: {msg}")
        return False
    return bool(janela.caso.planos)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("caso", nargs="?", help="TC8, Elekta… ou o caminho da pasta")
    p.add_argument("--lista", action="store_true", help="lista os casos e sai")
    p.add_argument("-o", "--saida", type=Path,
                   help="arquivo do PDF (padrão: <caso>_ficha.pdf ao lado daqui)")
    p.add_argument("--abrir", action="store_true",
                   help="abre o PDF gerado no visualizador do sistema")
    p.add_argument("--modo", default="individual",
                   choices=("individual", "soma"),
                   help="uma página de cortes por plano, ou uma combinando todos")
    args = p.parse_args(argv)

    def falar(msg: str) -> None:
        print(f"  {msg}", flush=True)

    disponiveis = _casos_disponiveis()
    if args.lista or not args.caso:
        if not disponiveis:
            print(f"Nenhum caso em {CASOS}")
            return 1
        print(f"Casos em {CASOS}:\n")
        for c in disponiveis:
            quantos = _quantos_arquivos(c)
            marca = "" if quantos else "   (sem DICOM — não dá ficha)"
            print(f"  {c.name:16s} {quantos:5d} arquivos{marca}")
        return 0

    pasta = _resolver(args.caso)
    if pasta is None:
        print(f"Não achei o caso {args.caso!r}. Os que existem: "
              + ", ".join(c.name for c in disponiveis), file=sys.stderr)
        return 1

    if not _quantos_arquivos(pasta):
        # Recusa AQUI, e não depois de montar a janela e varrer a pasta: a
        # pasta ``Posicionamento`` guarda NOTAS DE POSICIONAMENTO, não um
        # paciente, e "Nada carregado" depois de um minuto de espera não diz
        # isso a ninguém.
        print(f"{pasta.name} não tem DICOM nenhum (.dcm/.zip/.rar) — não é um "
              "caso para gerar ficha.", file=sys.stderr)
        return 1

    from PySide6.QtWidgets import QApplication

    from isocentro.dominio import constantes
    from isocentro.papel import ficha_pdf
    from isocentro.interface import gui

    app = QApplication.instance() or QApplication([])
    gui.aplicar_modo("noite")
    app.setStyleSheet(gui._ESTILO())

    print(f"Caso: {pasta}")
    janela = gui.JanelaPrincipal(
        usuario={"usuario": "caso", "nome": "Conferência",
                 "papel": "fisico"})

    if not _carregar(janela, pasta, falar):
        print("Nada carregado — sem plano nenhum, não há ficha para gerar.",
              file=sys.stderr)
        return 1

    # O mesmo passo que o ``_carga_terminou`` dá, MENOS o agendamento: ele abre
    # um diálogo, e aqui não há ninguém para respondê-lo.
    janela._fichinha_carga_assentou()

    planos = janela.controle_ficha.montar_planos_pdf()
    nome = (janela.form.pac_nome.text().strip() or "(sem nome)")
    print(f"\nPaciente: {nome}")
    print(f"Planos:   {len(planos)}")
    for i, pl in enumerate(planos, 1):
        d = pl["dados"]
        # ``rx_*`` e não ``dose_total``/``num_fracoes``: a primeira versão deste
        # resumo chutou os nomes e imprimiu "? Gy / ? fr" para uma ficha que
        # estava inteira — e um resumo que mente sobre o que gerou é pior que
        # resumo nenhum, porque manda conferir o que não está errado.
        rotulo = (janela.caso.planos[i - 1].get("rotulo")
                  if i - 1 < len(janela.caso.planos) else "") or f"Plano {i}"
        # Nome da máquina como a FICHA a imprime: a listagem existe para
        # conferir contra o papel, e discordar dele aqui é ruído.
        _maq = constantes.rotulo_maquina(d.get("maquina") or "")
        print(f"  {i}. {rotulo:26s} {_maq or '—':10s} "
              f"{d.get('rx_dose_total') or '?'} Gy / "
              f"{d.get('rx_fracoes') or '?'} fr "
              f"({d.get('rx_dose_fracao') or '?'} Gy/fr)")

    faltando = [c for c in ("pac_nome", "pac_registro", "maquina",
                            "rx_dose_total", "rx_fracoes")
                if not planos[0]["dados"].get(c)]
    if faltando:
        # Campo sem fonte nasce vazio e a tela DIZ que está faltando (regra do
        # CLAUDE.md). Aqui não há tela, então quem diz é esta linha — senão a
        # ficha sai incompleta e a conferência não percebe.
        print("\n  ATENÇÃO — campos vazios no 1º plano: "
              + ", ".join(faltando))

    pdf, _cortes, _dvhs = ficha_pdf.gerar_ficha_multiplano(planos,
                                                           modo=args.modo)
    saida = args.saida or (RAIZ / f"{pasta.name}_ficha.pdf")
    saida.write_bytes(pdf)

    print(f"\nFicha: {saida}  ({len(pdf) / 1024:.0f} KB)")
    print("Confira CONTRA O SISTEMA, não contra uma ficha arquivada — a do TC8"
          " está errada no acervo.")

    if args.abrir:
        if sys.platform == "win32":
            os.startfile(saida)  # noqa: S606
        else:
            import subprocess
            subprocess.run(["xdg-open", str(saida)], check=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
