r"""Gera o executável e o .zip de distribuição, conferindo cada etapa.

Não é conveniência: é o lugar onde os erros de empacotamento param de acontecer.
Os quatro que já aconteceram, todos por eu estar fazendo à mão:

1. o ``--clean`` do PyInstaller apaga a pasta inteira e leva o MIGRAR.txt e o
   migrar.ps1 junto — o zip saía sem as instruções de instalação;
2. um smoke test em modo dev semeou ``notas_posicionamento.json`` e
   ``inventario_imobilizadores.json`` na pasta, e o ``migrar.ps1`` NUNCA
   sobrescreve: a biblioteca de notas do serviço seria pulada na migração e
   sumiria sem aviso;
3. o ``pyodbc`` é importado dentro de função e quase ficou de fora do pacote —
   falha silenciosa: o app abriria normal e a capa cairia no espelho na clínica,
   sem ninguém entender por quê;
4. um teste meu sobrescreveu a saída boa de outra ferramenta;
5. e a armadilha que fecha o círculo: o SMOKE TEST semeia dados. Abrir o exe
   uma vez cria ``historico_uso.jsonl``, ``inventario_imobilizadores.json`` e
   ``notas_posicionamento.json`` na pasta. Zipar depois disso põe os três no
   pacote — e cairia no erro nº 2, com a biblioteca de notas do serviço sendo
   PULADA na migração e sumindo sem aviso.

Daí a ordem aqui: compilar, conferir, **abrir o exe**, apagar o que ele semeou,
conferir de novo e só então empacotar. Cada etapa vira um ``assert``. Erro
humano some quando vira script.

Rodar:
    python tools/gerar_executavel.py
    python tools/gerar_executavel.py --sem-zip      (só a pasta)
    python tools/gerar_executavel.py --sem-smoke    (CI: não há tela para abrir)
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import zipfile
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SPEC = RAIZ / "Isocentro.spec"
# Os acompanhantes moram no REPOSITÓRIO, versionados, e são copiados para o
# pacote. Antes viviam só dentro de dist/, que o --clean apaga — foi assim que
# um zip saiu sem as instruções de instalação.
FONTE_DOCS = RAIZ / "distribuicao"
NOME = "ISOCENTRO"
DESTINO = RAIZ / "dist" / NOME

# O que o pacote PRECISA ter para ser instalável. Sem os dois primeiros, quem
# recebe o zip não sabe o que copiar da instalação antiga nem que precisa
# apontar o banco.
ACOMPANHAM = ("MIGRAR.txt", "migrar.ps1")

# Módulos que só são importados DENTRO de funções: o PyInstaller varre bytecode
# e costuma achá-los, mas "costuma" não serve para o que falha em silêncio.
# Os nomes são PONTILHADOS desde 09/09/2026, quando os módulos saíram da raiz
# para o pacote ``isocentro``. O `conferir_modulos` procura cada um destes
# no `Analysis-00.toc`, e é lá que o PyInstaller escreve o nome COMPLETO do
# módulo — um "capa_db" solto nunca mais casaria, e a conferência aprovaria um
# pacote sem ele.
DENTRO_DO_PACOTE = (
    "pyodbc",
    "isocentro.banco.capa_db",
    "isocentro.banco.capa_espelho",
    "isocentro.dados.config_servico",
    "isocentro.dados.ambiente",
    # O ``capa_dados`` o importa DENTRO da função. Sem ele no pacote o
    # ``capa_db`` nem importa, e o app morre no arranque — na clínica, com o
    # paciente na porta.
    "isocentro.banco.banco_local",
    # Saíram do gui.py em 27/08/2026. Entram na conferência pelo mesmo motivo
    # dos de cima: o import deles está no MEIO do gui.py, não no topo, e é
    # assim que um módulo fica de fora do pacote sem ninguém notar até a
    # clínica abrir.
    "isocentro.interface.aparencia",
    "isocentro.interface.agendamento_tela",
    "isocentro.interface.administracao",
    "isocentro.interface.visualizador",
    "isocentro.interface.formulario",
    "isocentro.interface.edicao_ficha",
    "isocentro.interface.carregadores",
    "isocentro.interface.busca_ficha",
    # A rede DICOM. Mesmo caso do ``pyodbc``, e pelo mesmo motivo de estar
    # aqui: o ``dicom_rede`` importa o ``pynetdicom`` DENTRO da função, para o
    # app subir sem ele. Import tardio de biblioteca opcional é exatamente o
    # que sai do pacote sem ninguém notar até a clínica abrir.
    "pynetdicom",
    "isocentro.adaptadores.dicom.rede",
    "isocentro.banco.gatilho_db",
    "isocentro.dominio.gatilho_registro",
    "isocentro.dominio.gatilho",
)

# Arquivos de DADOS que o app cria ao rodar. Nenhum pode viajar no zip: o
# migrar.ps1 pula o que já existe no destino, então um deles aqui faria a
# migração PULAR o arquivo real do serviço.
NUNCA_NO_PACOTE = (
    # O ``gatilho_registro.json`` é dado de execução: ele guarda o que já foi
    # exportado. Viajando no zip, o migrar.ps1 PULARIA o real do serviço e a
    # automação reexportaria tudo, ou nada.
    "gatilho_registro.json",
    "usuarios.json", "registro_fichas.json", "historico_uso.jsonl",
    "cadastro_sus.json", "inventario_imobilizadores.json",
    "notas_posicionamento.json", "correcoes_capa.json", "config_servico.json",
    # A preferência de cada pessoa e quem está logado agora (ver
    # ``dados/preferencias.py`` e ``dados/sessao.py``). O ``sessoes.json`` é o
    # pior deles para viajar: uma sessão de outra instalação derrubaria quem
    # entrasse aqui, por um login que nunca aconteceu nesta pasta.
    "preferencias.json", "sessoes.json",
)

# O contrário da lista acima: recurso que TEM de viajar no zip. A semente da
# biblioteca de notas tem nome diferente do arquivo de trabalho de propósito —
# é o que a mantém fora da lista do migrar.ps1 e permite empacotá-la.
SEMENTE_NOTAS = "notas_modelo.json"


def passo(n, texto: str) -> None:
    print(f"\n[{n}] {texto}", flush=True)


def conferir_docs() -> None:
    """Os acompanhantes existem no repositório? Sem eles não há o que copiar."""
    faltam = [n for n in ACOMPANHAM if not (FONTE_DOCS / n).exists()]
    assert not faltam, f"faltam em {FONTE_DOCS}: {faltam}"


def compilar() -> None:
    r = subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm",
                        "--clean", str(SPEC)],
                       cwd=RAIZ, capture_output=True, text=True)
    assert r.returncode == 0, f"PyInstaller falhou:\n{r.stdout[-3000:]}"
    assert (DESTINO / f"{NOME}.exe").exists(), \
        f"o build não produziu {NOME}.exe — o nome mudou no .spec?"


def conferir_modulos() -> None:
    """Os imports tardios entraram? É a falha que só apareceria na clínica."""
    toc = RAIZ / "build" / "Isocentro" / "Analysis-00.toc"
    assert toc.exists(), "sem Analysis-00.toc: o build não deixou rastro"
    texto = toc.read_text(encoding="utf-8", errors="replace")
    faltando = [m for m in DENTRO_DO_PACOTE if m not in texto]
    assert not faltando, (
        f"NÃO entraram no pacote: {faltando}. Acrescente em hiddenimports no "
        f"{SPEC.name} — sem isso o app abre e falha calado na clínica.")
    interno = DESTINO / "_internal"
    assert any(interno.glob("pyodbc*")), \
        "o binário do pyodbc não está em _internal/ — leitura do banco morta"


def conferir_semente() -> None:
    """A biblioteca de notas veio no pacote?

    O erro nº 6, e o pior deles até aqui porque durou meses: a instalação nova
    abria com o seletor de "Nota de posicionamento" VAZIO. O arquivo de trabalho
    não pode ir no zip (é o erro nº 2, logo acima), o acervo ``.docx`` nunca foi
    empacotado, e ninguém percebeu porque na máquina de desenvolvimento o acervo
    existe. A semente ``assets/notas_modelo.json`` cobre o buraco — e some em
    silêncio se alguém mexer nos ``datas`` do ``.spec``, que é o motivo deste
    assert.
    """
    alvo = DESTINO / "_internal" / "assets" / SEMENTE_NOTAS
    assert alvo.exists(), (
        f"{SEMENTE_NOTAS} não está em _internal/assets/ — a instalação nova "
        "abriria SEM NENHUMA nota de posicionamento. Confira datas= no "
        f"{SPEC.name} e rode tools/gerar_notas_modelo.py.")
    corpo = json.loads(alvo.read_text(encoding="utf-8"))
    quantas = len(corpo.get("notas") or ())
    assert quantas >= 10, \
        f"a semente tem só {quantas} nota(s) — rode tools/gerar_notas_modelo.py"
    print(f"    {SEMENTE_NOTAS} — {quantas} modelos")


def copiar_acompanhantes() -> None:
    for nome in ACOMPANHAM:
        shutil.copy2(FONTE_DOCS / nome, DESTINO / nome)
    faltam = [n for n in ACOMPANHAM if not (DESTINO / n).exists()]
    assert not faltam, f"o pacote sairia sem {faltam}"


# Quanto esperar a janela subir. O app carrega Qt, matplotlib e pydicom; abaixo
# disso o teste acusaria "morreu" numa máquina lenta que só estava carregando.
ESPERA_SMOKE = 25


def smoke_test() -> None:
    """Abre o exe e confere que a janela sobe e FICA de pé.

    É a única etapa que os ``assert`` anteriores não cobrem: o pacote pode estar
    completo e o programa não abrir — um import que só falha empacotado, um
    recurso que ficou de fora. Sem isto, descobre-se na clínica.

    ``ISOCENTRO_DEV`` pula o login: sem ele o processo fica esperando alguém
    digitar, e "esperando" e "vivo" seriam indistinguíveis daqui.
    """
    import subprocess
    import time

    ambiente_dev = dict(os.environ, ISOCENTRO_DEV="1")
    proc = subprocess.Popen([str(DESTINO / f"{NOME}.exe")],
                            cwd=str(DESTINO), env=ambiente_dev)
    try:
        time.sleep(ESPERA_SMOKE)
        assert proc.poll() is None, (
            f"o executável MORREU em {ESPERA_SMOKE}s (código {proc.returncode}). "
            f"Veja ~/.isocentro.log — e não distribua este pacote.")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:  # noqa: BLE001
            proc.kill()


def limpar_semeados() -> list:
    """Apaga o que a abertura do exe criou. Devolve o que saiu.

    Abrir o programa é o que prova que ele funciona — e é também o que suja a
    pasta. As duas coisas são inseparáveis, então a limpeza faz parte do
    empacotamento, não da lembrança de quem empacota.
    """
    saíram = []
    for nome in NUNCA_NO_PACOTE:
        alvo = DESTINO / nome
        if alvo.exists():
            alvo.unlink()
            saíram.append(nome)
    for pasta in ("espelho_capa", "backup_registros"):
        alvo = DESTINO / pasta
        if alvo.exists():
            shutil.rmtree(alvo, ignore_errors=True)
            saíram.append(pasta + "/")
    return saíram


def conferir_limpeza() -> None:
    """Nenhum dado de execução no pacote."""
    sujos = [n for n in NUNCA_NO_PACOTE if (DESTINO / n).exists()]
    assert not sujos, (
        f"dados de execução no pacote: {sujos}. O migrar.ps1 NUNCA sobrescreve, "
        "então estes fariam a migração PULAR os arquivos reais do serviço.")
    for pasta in ("espelho_capa", "backup_registros"):
        assert not (DESTINO / pasta).exists(), \
            f"{pasta}/ no pacote — é dado de paciente, não vai para distribuição"


def zipar() -> Path:
    alvo = RAIZ / f"{NOME}_{date.today():%Y-%m-%d}.zip"
    if alvo.exists():
        alvo.unlink()
    with zipfile.ZipFile(alvo, "w", zipfile.ZIP_DEFLATED) as z:
        for caminho in sorted(DESTINO.rglob("*")):
            if caminho.is_file():
                z.write(caminho, caminho.relative_to(DESTINO))
    # Conferir o zip DEPOIS de fechado: zip que não abre só se descobre na
    # clínica, e aí já foi.
    with zipfile.ZipFile(alvo) as z:
        ruim = z.testzip()
        assert ruim is None, f"membro corrompido no zip: {ruim}"
        nomes = z.namelist()
        assert f"{NOME}.exe" in nomes, "o exe não entrou no zip"
        for nome in ACOMPANHAM:
            assert nome in nomes, f"{nome} não entrou no zip"
        # De novo aqui, e não só na pasta: é o zip que vai para a clínica.
        assert f"_internal/assets/{SEMENTE_NOTAS}" in nomes, \
            f"{SEMENTE_NOTAS} não entrou no zip — instalação nova sem notas"
    arquivos = sum(1 for p in DESTINO.rglob("*") if p.is_file())
    with zipfile.ZipFile(alvo) as z:
        assert len(z.namelist()) == arquivos, (
            f"o zip tem {len(z.namelist())} arquivos e a pasta {arquivos}")
    return alvo


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--sem-zip", action="store_true",
                   help="só gera a pasta dist/, sem empacotar")
    p.add_argument("--sem-smoke", action="store_true",
                   help="não abre o exe (CI headless não tem tela)")
    args = p.parse_args(argv)

    print("=" * 70)
    print(f"  Gerando {NOME} — {date.today():%d/%m/%Y}")
    print("=" * 70)

    passo(1, f"conferindo os acompanhantes em {FONTE_DOCS.name}/")
    conferir_docs()
    print(f"    {', '.join(ACOMPANHAM)}")

    passo(2, "compilando (leva ~1 min)")
    compilar()
    tamanho = (DESTINO / f"{NOME}.exe").stat().st_size / 1024 / 1024
    print(f"    {NOME}.exe — {tamanho:.1f} MB")

    passo(3, "conferindo os imports tardios e os recursos")
    conferir_modulos()
    print(f"    {', '.join(DENTRO_DO_PACOTE)} — todos no pacote")
    conferir_semente()

    passo(4, "copiando os acompanhantes para o pacote")
    copiar_acompanhantes()
    print(f"    {', '.join(ACOMPANHAM)}")

    if args.sem_smoke:
        passo(5, "smoke test PULADO (--sem-smoke)")
    else:
        passo(5, f"abrindo o exe ({ESPERA_SMOKE}s) — vai piscar uma janela")
        smoke_test()
        print("    a janela subiu e ficou de pé")

    passo(6, "apagando o que a abertura semeou")
    saíram = limpar_semeados()
    print(f"    {', '.join(saíram) if saíram else 'nada a apagar'}")

    passo(7, "conferindo que não há dado de execução")
    conferir_limpeza()
    print("    limpo")

    if args.sem_zip:
        print(f"\nPronto (sem zip): {DESTINO}")
        return 0

    passo(8, "empacotando")
    alvo = zipar()
    print(f"    {alvo.name} — {alvo.stat().st_size / 1024 / 1024:.1f} MB")

    print("\n" + "=" * 70)
    print(f"  PRONTO: {alvo}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as erro:
        # Falha de empacotamento é para parar tudo e ser lida, não para virar
        # traceback no meio de mil linhas do PyInstaller.
        print(f"\n{'=' * 70}\n  PAROU: {erro}\n{'=' * 70}")
        sys.exit(1)
