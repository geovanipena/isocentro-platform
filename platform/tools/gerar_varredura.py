r"""Empacota a **varredura da concentradora** num executável próprio — nunca à mão.

Na concentradora não há Python nem o repositório: só chega executável. E o
`ISOCENTRO.exe` não serve para isto — é `console=False` (rodada agendada
não mostraria nada) e sobe a interface inteira para não abrir janela nenhuma.

**O que esta ferramenta confere, e por que cada conferência existe:**

1. **os imports tardios entraram no pacote.** É a falha que só apareceria na
   clínica, e calada. Aqui ela tem um agravante em relação ao app: o
   `isocentro.interface.simulacao` é importado DENTRO do
   `gatilho._preparar`, e sem ele a preparação responde "sem cadastro de
   simulação" — que é uma resposta legítima do domínio. Ninguém desconfiaria de
   empacotamento; procurariam o cadastro do paciente;
2. **o exe roda e o portão responde.** O smoke test chama `--conferir`, que não
   abre associação nem grava nada, e exige a palavra PORTÃO na saída. Executável
   que abre e fecha sem escrever passaria em qualquer conferência mais fraca;
3. **o console não estoura no acento.** Medido em 10/09/2026 no primeiro
   executável do checkup: console em code page 850, Python escolhendo cp1252, e
   três blocos saíram como `UnicodeEncodeError` — que, lido na estação, se
   parece com defeito de rede;
4. **nada de dado de execução viaja no zip.** Mesma regra dos outros dois
   empacotadores;
5. **o exe sobe com o `_internal` do APP.** É o layout que vai para a clínica,
   e até 14/09/2026 nada o conferia — ver `smoke_test_na_pasta_do_app`.

O build sai em `dist/VarreduraIsocentro/`, com `_internal` e tudo, porque
é assim que o PyInstaller monta um `onedir`. **O zip leva só o executável e o
`LEIAME_VARREDURA.txt`**: na concentradora o exe é COPIADO para dentro da pasta
do app no share e usa o `_internal` que já está lá.

Isso não é economia de bytes. `raiz.pasta_do_app()`, empacotado, é a pasta do
próprio `.exe` — então é a posição do binário que decide de onde saem o
`config_servico.json` e o `gatilho_registro.json`. Numa subpasta própria ele
leria uma configuração vazia (portão fechado, com o admin jurando que apontou
pela tela) e gravaria o estado da automação onde nenhuma estação enxerga. Até
14/09/2026 o `zipar` usava `relative_to(DESTINO.parent)`, quer dizer: o zip
**fabricava** a subpasta que o próprio LEIAME mandava evitar.

Rodar:
    python tools/gerar_varredura.py
    python tools/gerar_varredura.py --sem-zip
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import zipfile
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
# Um nome só: spec, build/, dist/ e exe. O `Isocentro.spec` gera o
# `ISOCENTRO.exe` e o `build/Isocentro/Analysis-00.toc`, e essa divergência
# obriga a lembrar de onde sai o TOC toda vez que se mexe na conferência.
NOME = "VarreduraIsocentro"
SPEC = RAIZ / f"{NOME}.spec"
DESTINO = RAIZ / "dist" / NOME

# Os imports TARDIOS — os que o PyInstaller não vê porque estão dentro de
# função. Levantados no código em 14/09/2026, um a um; cada um está dentro de
# função por um motivo que continua valendo.
DENTRO_DO_PACOTE = (
    # As bibliotecas de campo. Sem elas o exe abre e não fala com ninguém.
    "pyodbc",
    "pydicom",
    "pynetdicom",
    # O produto: a varredura e as três peças que ela amarra.
    "isocentro.raiz",
    "isocentro.dados.ambiente",
    "isocentro.dados.config_servico",
    "isocentro.dados.indice",
    "isocentro.dados.historico",
    "isocentro.dados.log_app",
    "isocentro.dados.registro_json",
    "isocentro.adaptadores.dicom.rede",
    "isocentro.banco.capa_db",
    "isocentro.banco.atividades_db",
    "isocentro.banco.gatilho_db",
    "isocentro.dominio.gatilho",
    "isocentro.dominio.gatilho_registro",
    # O que mais dói se faltar, e o que menos parece defeito: o
    # `gatilho._preparar` importa isto DENTRO da função. Sem ele, todo caso
    # preparado sai "sem cadastro de simulação" — resposta legítima do domínio,
    # e por isso ninguém procuraria o problema aqui.
    "isocentro.interface.simulacao",
    # E a ferramenta em si, que o `run_varredura.py` importa de `tools/`.
    "varredura_cli",
)

LEIAME = "LEIAME_VARREDURA.txt"

# O que PODE estar no topo do pacote. Lista branca pelo mesmo motivo do
# `gerar_checkup`: o que vaza é sempre o arquivo novo, que uma lista negra não
# conhece.
PODE_ESTAR_NO_PACOTE = {f"{NOME}.exe", LEIAME, "_internal"}


def passo(n: int, texto: str) -> None:
    print(f"\n[{n}] {texto}", flush=True)


def compilar() -> None:
    r = subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm",
                        "--clean", str(SPEC)],
                       cwd=RAIZ, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    assert r.returncode == 0, f"PyInstaller falhou:\n{r.stdout[-3000:]}"
    assert (DESTINO / f"{NOME}.exe").exists(), \
        f"o build não produziu {NOME}.exe — o nome mudou no .spec?"


def conferir_modulos() -> None:
    """Os imports tardios entraram? É a falha que só apareceria na clínica."""
    toc = RAIZ / "build" / NOME / "Analysis-00.toc"
    assert toc.exists(), "sem Analysis-00.toc: o build não deixou rastro"
    texto = toc.read_text(encoding="utf-8", errors="replace")
    faltando = [m for m in DENTRO_DO_PACOTE if m not in texto]
    assert not faltando, (
        f"NÃO entraram no pacote: {faltando}. Acrescente em hiddenimports no "
        f"{SPEC.name} — sem isso o exe abre e falha calado na concentradora.")


def smoke_test() -> str:
    """Roda o exe de verdade, no modo que NÃO toca em nada.

    ``--conferir`` não abre associação DICOM, não grava e não apaga: dá para
    rodá-lo aqui, nesta máquina, sem risco nenhum. O código de saída aceito é 0
    (portão aberto) ou 2 (portão fechado) — nesta máquina é 2, porque não há
    ARIA configurado, e isso É a resposta certa. Qualquer outro código quer
    dizer que o binário não subiu inteiro.
    """
    exe = DESTINO / f"{NOME}.exe"
    r = subprocess.run([str(exe), "--conferir"], capture_output=True,
                       text=True, timeout=180, encoding="utf-8",
                       errors="replace")
    saida = (r.stdout or "") + (r.stderr or "")
    assert r.returncode in (0, 2), (
        f"o exe saiu com {r.returncode}, que não é nem portão aberto nem "
        f"fechado — algum import falhou dentro do pacote:\n{saida[-1500:]}")
    assert "PORTÃO" in saida, (
        "o exe rodou e NÃO disse em que pé está o portão — saída:\n"
        + saida[-1500:])
    # O defeito que o PRIMEIRO exe do checkup trouxe, em 10/09/2026. Estas duas
    # linhas são o que impede que o conserto saia do lugar sem ninguém notar.
    assert "UnicodeEncodeError" not in saida, (
        "o console do exe estourou em codificação — ver "
        "varredura_cli._console_em_utf8:\n" + saida[-1500:])
    assert "ModuleNotFoundError" not in saida, (
        "faltou módulo dentro do pacote:\n" + saida[-1500:])
    return saida


def smoke_test_na_pasta_do_app() -> bool:
    """O exe sobe com o ``_internal`` do APP? É o layout que vai para a clínica.

    Na concentradora este binário não roda da pasta em que foi compilado: ele é
    copiado para DENTRO da pasta do app no share, ao lado do
    ``ISOCENTRO.exe``, e usa o ``_internal`` que já está lá. Ver a
    docstring do módulo para o porquê — em resumo, é a posição do ``.exe`` que
    decide de onde sai o ``config_servico.json``.

    Medido em 14/09/2026, no dia em que o layout foi decidido: os binários da
    varredura são subconjunto dos do app, e os dois ``base_library.zip`` têm os
    mesmos 155 módulos. Só que isso vale para o build DAQUELE dia — o app
    recompilado com outro Python, ou com outro PyInstaller, moveria o chão
    debaixo deste exe, e a notícia chegaria como uma Tarefa Agendada que parou
    de exportar. Esta conferência é o que transforma a aposta em medida, e ela
    roda a cada empacotamento.

    Devolve ``False``, sem reprovar, quando não há ``dist/ISOCENTRO/`` para
    testar contra: empacotar a varredura sozinha é legítimo, e exigir o app
    obrigaria a recompilar 1 min de interface para mexer numa linha do LEIAME.
    """
    pasta_app = RAIZ / "dist" / "ISOCENTRO"
    if not (pasta_app / "_internal").exists():
        return False
    convidado = pasta_app / f"{NOME}.exe"
    try:
        shutil.copy2(DESTINO / f"{NOME}.exe", convidado)
        r = subprocess.run([str(convidado), "--conferir"], capture_output=True,
                           text=True, timeout=180, encoding="utf-8",
                           errors="replace")
        saida = (r.stdout or "") + (r.stderr or "")
        assert r.returncode in (0, 2), (
            f"o exe NÃO sobe com o _internal do app (saiu {r.returncode}), e é "
            f"o layout que vai para a concentradora. Os dois builds saíram de "
            f"Pythons diferentes?\n{saida[-1500:]}")
        assert "PORTÃO" in saida, (
            "rodou na pasta do app e não disse em que pé está o portão:\n"
            + saida[-1500:])
    finally:
        # Esquecido ali, ele reprovaria o `conferir_limpeza` do empacotador do
        # app — e, pior, viajaria no zip DELE como dado de execução.
        convidado.unlink(missing_ok=True)
    return True


def conferir_limpeza() -> None:
    """Nada além do executável viaja no zip.

    A varredura grava o log na HOME da conta que roda, não ao lado de si, então
    aqui a lista costuma estar limpa. A conferência fica pelo mesmo motivo dos
    outros dois: dado de execução no pacote faz o ``migrar.ps1`` PULAR o arquivo
    real do serviço, porque ele nunca sobrescreve.
    """
    sobrando = sorted(p.name for p in DESTINO.iterdir()
                      if p.name not in PODE_ESTAR_NO_PACOTE)
    assert not sobrando, (
        f"apareceu no pacote o que não devia: {sobrando}. Se for saída da "
        "rodada do smoke test, apagar antes de zipar; se for recurso novo e "
        "legítimo, acrescentar em PODE_ESTAR_NO_PACOTE — mas conferindo que "
        "não é dado de execução.")


def escrever_leiame() -> Path:
    """O acompanhante, escrito aqui para não envelhecer noutro arquivo."""
    alvo = DESTINO / LEIAME
    alvo.write_text(f"""VARREDURA DA EXPORTACAO AUTOMATICA - ISOCENTRO
Gerado em {date.today():%d/%m/%Y}

O QUE E: uma passada da exportacao automatica, sem abrir o app. Pergunta ao
banco quais planos estao prontos, traz o DICOM do ARIA para a pasta temporaria,
prepara o caso e limpa o que ja serviu. E o mesmo trabalho que o app faz quando
esta aberto - aqui ele acontece com ninguem logado.

COMO INSTALAR: COPIE O {NOME}.exe - so ele, so
este arquivo - para DENTRO DA PASTA DO APP no share, a mesma de onde as
estacoes rodam o ISOCENTRO.exe, AO LADO dele. NAO crie subpasta para
ele. Nao ha _internal neste zip de proposito: o exe usa o do app, que ja
esta la, e isso e conferido a cada empacotamento.

POR QUE ASSIM: o programa le e grava o que e do SERVICO AO LADO DO PROPRIO EXE.
Numa subpasta - ou em C:\\ISOCENTRO\\, como qualquer outro programa - este
binario le um config_servico.json vazio, e as quatro chaves do DICOM que o
admin apontou pela tela NAO chegam nele (portao fechado); e grava o
gatilho_registro.json num canto que NENHUMA estacao enxerga, de modo que a
Fichinha nao mostra caso pronto nenhum. Os dois se parecem com "nao havia nada
para exportar".

QUEM VARRE NAO E A INSTALACAO, E A CHAVE "Concentradora" em Configuracoes ->
Servico. A rede DICOM apontada pela tela vale para TODAS as estacoes; sem a
chave, nenhuma varre (nem esta), e com ela so a maquina com aquele nome varre
- pelo app aberto ou por esta tarefa. Preencha com o NOME desta maquina (nao
o IP): o --conferir, abaixo, mostra os dois nomes lado a lado.

ANTES DE CADASTRAR A TAREFA, rodar uma vez na conta que VAI rodar a tarefa:

    {NOME}.exe --conferir

Ele imprime a pasta da exportacao, QUAL degrau a escolheu, o estado da rede
DICOM, a concentradora apontada e o nome desta maquina, DE ONDE leu a
configuracao, onde cai o estado da automacao e a conta do Windows em uso.
CONFIRA AS DUAS LINHAS DE ARQUIVO: as duas tem de apontar para a PASTA DO
APP - a mesma em que esta o ISOCENTRO.exe. Apontando para qualquer
outro lugar, o exe foi parar fora dela, e este e o unico momento em
que isso aparece. Se disser PORTAO FECHADO, a tarefa nao vai exportar nada, e o
motivo esta na linha seguinte.

ATENCAO A CONTA: variavel de ambiente de USUARIO nao atravessa conta. Se a
rede DICOM estiver configurada so por variavel no seu usuario, a tarefa (que
roda com outra conta) nao a enxerga. Aponte pela tela do app, em
Configuracoes -> Servico: o que vai para la vale para qualquer conta, e chega
ate aqui porque este exe mora na mesma pasta do app.

CADASTRAR A TAREFA (prompt de ADMINISTRADOR, ajustar a conta e o caminho):

    schtasks /Create /TN "ISOCENTRO - varredura" ^
      /TR "\\"\\\\fileserver\\<pasta do app>\\{NOME}.exe\\" --uma-vez" ^
      /SC MINUTE /MO 5 ^
      /RU "DOMINIO\\conta_de_servico" /RP * ^
      /RL LIMITED /F

A conta precisa ser de DOMINIO: o banco conecta por autenticacao Windows
(SSPI). Ela precisa de LEITURA E ESCRITA no share do app: leitura porque e
de la que este exe roda; ESCRITA porque e la que a varredura grava o
gatilho_registro.json, o .lock dele e o historico compartilhado. So com
leitura, o --conferir diz PORTAO ABERTO (ele nao grava nada) e a primeira
rodada falha no meio. Precisa tambem de escrita no share da exportacao e de
leitura na raiz das simulacoes.

O QUE A COLUNA "ultimo resultado" DO AGENDADOR QUER DIZER:

    0   rodou (inclusive sem nada a exportar, e inclusive pulada por outra
        rodada em curso - a trava funcionando nao e erro)
    1   comecou e foi interrompida: rede fora, ou o ARIA recusou
    2   NAO rodou: falta configuracao (banco ou DICOM), ou esta maquina nao
        e a concentradora. Rodar --conferir
    4   excecao inesperada: e defeito nosso, e o traceback esta no log

O LOG fica em %USERPROFILE%\\.isocentro.log DA CONTA QUE RODOU - nao a
sua. Os avisos tambem vao para o historico compartilhado, que o admin le de
qualquer estacao pelo proprio app.
""", encoding="utf-8")
    return alvo


def zipar() -> Path:
    """Só o exe e o LEIAME. O ``_internal`` **não** viaja, e é de propósito.

    Levar o nosso ``_internal`` convidaria a descompactar a pasta inteira em
    cima da pasta do app — e aí o exe rodaria de uma SUBPASTA, que é o defeito
    que o LEIAME manda evitar três parágrafos acima do comando. Levando só o
    binário, o único gesto possível é o certo: copiá-lo para ao lado do
    ``ISOCENTRO.exe``.

    Era ``relative_to(DESTINO.parent)`` até 14/09/2026, quer dizer: o zip
    fabricava a subpasta sozinho, e as três instruções do projeto (a prosa do
    LEIAME, a linha do ``schtasks`` e o zip) diziam três coisas diferentes.
    """
    alvo = RAIZ / "dist" / f"{NOME}_{date.today():%Y%m%d}.zip"
    if alvo.exists():
        alvo.unlink()
    membros = (DESTINO / f"{NOME}.exe", DESTINO / LEIAME)
    with zipfile.ZipFile(alvo, "w", zipfile.ZIP_DEFLATED) as z:
        for arquivo in membros:
            z.write(arquivo, arquivo.name)
    # Conferir DEPOIS de fechado, como no empacotador do app: zip que não abre
    # só se descobre na clínica, e aí já foi.
    with zipfile.ZipFile(alvo) as z:
        ruim = z.testzip()
        assert ruim is None, f"membro corrompido no zip: {ruim}"
        assert sorted(z.namelist()) == sorted(m.name for m in membros), (
            f"o zip saiu com {z.namelist()} — devia ter só o exe e o LEIAME, "
            "sem pasta nenhuma por cima")
    return alvo


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--sem-zip", action="store_true",
                   help="só gera a pasta dist/, sem empacotar")
    args = p.parse_args(argv)

    print("=" * 70)
    print(f"  Gerando a {NOME} — {date.today():%d/%m/%Y}")
    print("=" * 70)

    if DESTINO.exists():
        shutil.rmtree(DESTINO)

    passo(1, "compilando (leva ~1 min)")
    compilar()
    tamanho = (DESTINO / f"{NOME}.exe").stat().st_size / 1024 / 1024
    print(f"    {NOME}.exe — {tamanho:.1f} MB")

    passo(2, "conferindo os imports tardios")
    conferir_modulos()
    print(f"    {len(DENTRO_DO_PACOTE)} módulos — todos no pacote")

    passo(3, "rodando o exe de verdade (--conferir, não toca em nada)")
    saida = smoke_test()
    print(f"    o binário subiu e escreveu {len(saida.splitlines())} linhas")

    passo(4, "rodando o exe com o _internal do APP (o layout da clínica)")
    if smoke_test_na_pasta_do_app():
        print("    sobe ao lado do ISOCENTRO.exe — pode viajar sozinho")
    else:
        print("    PULADO: não há dist/ISOCENTRO/ para testar contra")

    passo(5, "escrevendo o acompanhante")
    print(f"    {escrever_leiame().name}")

    passo(6, "conferindo que nada de execução viaja no pacote")
    conferir_limpeza()
    print("    limpo")

    if args.sem_zip:
        print(f"\nPronto (sem zip): {DESTINO}")
        return 0

    passo(7, "empacotando")
    alvo = zipar()
    print(f"    {alvo.name} — {alvo.stat().st_size / 1024 / 1024:.1f} MB")

    print("\n" + "=" * 70)
    print(f"  PRONTO: {alvo}")
    print("  Levar ESTE zip para a concentradora (clinica-python01).")
    print(f"  Lá: COPIAR só o {NOME}.exe para dentro da pasta do")
    print("  app no share, AO LADO do ISOCENTRO.exe — sem subpasta.")
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
