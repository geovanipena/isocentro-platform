r"""Empacota o **checkup da clínica** num executável próprio — nunca à mão.

Na clínica não há Python nem o repositório: só chega executável. O
``tools\checkup_clinica.bat`` mede esta máquina, que é o ambiente de
desenvolvimento; a medida que decide o pedido à TI é a da estação, e para
chegar lá o checkup precisa virar binário.

**O que esta ferramenta confere, e por que cada conferência existe:**

1. **os imports tardios entraram no pacote.** É a falha que só apareceria na
   clínica, e calada: ``pyodbc``, ``pynetdicom`` e ``pydicom`` são importados
   DENTRO de função — para o programa subir mesmo sem eles —, e import tardio é
   exatamente o que o PyInstaller não enxerga sozinho. Um checkup que abre e
   diz "não deu para carregar o pynetdicom" gastou a ida inteira;
2. **o exe roda, e produz relatório.** O smoke test do app só confere que a
   janela sobe; aqui dá para ler a saída — então ele exige o bloco 12 no texto.
   Executável que abre e fecha sem escrever nada passaria em qualquer
   conferência mais fraca;
3. **nada de dado de execução viaja no zip.** Mesma regra do outro empacotador,
   e aqui é mais direta: o checkup **grava ao lado de si**, então um relatório
   da rodada de teste ficaria no pacote — e relatório traz endereço interno, e
   pode trazer o caminho de uma pasta com DICOM de paciente.

O pacote sai em ``dist/CheckupClinica/`` e vira um zip com o
``LEIAME_CHECKUP.txt`` ao lado: quem roda na clínica não é quem escreveu isto.
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
SPEC = RAIZ / "CheckupClinica.spec"
NOME = "CheckupClinica"
DESTINO = RAIZ / "dist" / NOME

# Os imports TARDIOS — os que o PyInstaller não vê sozinho porque estão dentro
# de função. Cada um está dentro de função por um motivo que continua valendo:
# o checkup precisa subir e RELATAR numa máquina onde a biblioteca falta, em
# vez de morrer no arranque com um traceback que ninguém traduz.
#
# A conferência é feita contra o ``Analysis-00.toc`` depois do build: é o único
# jeito de saber que o nome não caiu no caminho.
DENTRO_DO_PACOTE = (
    # As três bibliotecas de campo. Sem elas o exe abre e não mede nada.
    "pyodbc",
    "pydicom",
    "pynetdicom",
    # O produto: é o ``trazer()`` DELE que se quer medir, e não uma reescrita.
    "isocentro.raiz",
    "isocentro.dados.ambiente",
    "isocentro.adaptadores.dicom.rede",
    "isocentro.banco.gatilho_db",
    "isocentro.banco.capa_dados",
    "isocentro.banco.capa_espelho",
    "isocentro.dados.auth",
    "isocentro.dados.config_servico",
    "isocentro.dados.correcoes",
    "isocentro.dados.historico",
    "isocentro.dominio.gatilho",
    # E a outra ferramenta de ``tools/``, de onde saem a conexão do banco e a
    # lista de drivers bons. Ela é importada dentro de ``_conexao_banco``.
    "diagnostico_db",
)

# O acompanhante. Quem roda na clínica não é quem escreveu isto, e um exe
# sozinho numa pasta não diz o que fazer com o arquivo que ele cospe.
LEIAME = "LEIAME_CHECKUP.txt"


def passo(n: int, texto: str) -> None:
    print(f"\n[{n}] {texto}", flush=True)


def compilar() -> None:
    r = subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm",
                        "--clean", str(SPEC)],
                       cwd=RAIZ, capture_output=True, text=True)
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
        f"{SPEC.name} — sem isso o exe abre e falha calado na clínica.")


def smoke_test() -> str:
    """Roda o exe de verdade e EXIGE relatório.

    Mais forte que o smoke test do app, e dá para ser: aqui a saída é texto.
    ``--sem-padrao`` para a rodada não tentar falar com o ARIA de dentro do
    build, e ``--pular`` porque nesta máquina o banco não responde — o que se
    quer saber é se o binário sobe, importa tudo e escreve.
    """
    exe = DESTINO / f"{NOME}.exe"
    r = subprocess.run([str(exe), "--sem-padrao", "--pular",
                        "banco,dicom,impressao", "-o", ""],
                       capture_output=True, text=True, timeout=180,
                       encoding="utf-8", errors="replace")
    saida = (r.stdout or "") + (r.stderr or "")
    assert "12. O que falta" in saida, (
        "o exe rodou e NÃO produziu o bloco do pedido — saída:\n"
        + saida[-1500:])
    assert "não deu para" not in saida.lower() or "gatilho" in saida.lower(), (
        "algum import falhou dentro do exe:\n" + saida[-1500:])
    # O defeito que o PRIMEIRO exe gerado trouxe, em 10/09/2026: o console do
    # Windows abre em code page 850, o Python escolhe cp1252 para a saída, e
    # "ã" derruba o bloco. Três blocos saíram como "estourou:
    # UnicodeEncodeError" — e, lido na estação, isso se parece com defeito de
    # rede. A correção mora em ``checkup_clinica._console_em_utf8``; estas duas
    # linhas são o que impede que ela saia do lugar sem ninguém perceber.
    assert "UnicodeEncodeError" not in saida, (
        "o console do exe estourou em codificação — ver _console_em_utf8:\n"
        + saida[-1500:])
    assert "estourou:" not in saida, (
        "algum bloco estourou dentro do exe:\n" + saida[-1500:])
    return saida


# O que PODE estar no topo do pacote. Lista branca, e não lista negra de
# arquivos conhecidos: o checkup grava AO LADO de si, e a rodada do smoke test
# passa pelo bloco das pastas — que escreve e apaga em cada uma delas. Uma
# lista negra só pega o que alguém já viu aparecer, e o que vaza é sempre o
# arquivo novo.
PODE_ESTAR_NO_PACOTE = {"CheckupClinica.exe", "LEIAME_CHECKUP.txt", "_internal"}


def conferir_limpeza() -> None:
    """Nada além do executável viaja no zip.

    Relatório traz endereço interno da clínica e, quando o bloco 8 roda, o
    caminho de uma pasta com DICOM de paciente. E é a mesma família da
    armadilha do outro empacotador: dado de execução no pacote faz o
    ``migrar.ps1`` PULAR o arquivo real do serviço, porque ele nunca
    sobrescreve.
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
    alvo.write_text(f"""CHECKUP DA CLINICA - ISOCENTRO
Gerado em {date.today():%d/%m/%Y}

O QUE E: mede, numa rodada so, tudo o que o ISOCENTRO precisa da rede -
rede, banco, pastas, DICOM e impressao - e escreve no fim o pedido a TI.

SO LEITURA. Nao altera firewall, registro, servico nem configuracao. Escreve
em dois lugares, e os dois se apagam: um arquivo de teste em cada pasta que
precisa aceitar escrita, e a pasta temporaria onde o DICOM que chegar e
gravado - essa o relatorio NOMEIA, porque e dado de paciente e alguem precisa
apaga-la depois de conferir.

COMO RODAR
  1. Dois cliques em {NOME}.exe. Ele usa os valores da TI que ja estao
     embutidos, roda, e espera um Enter antes de fechar.
  2. Com um plano especifico (melhor, porque exercita o circuito inteiro):
       {NOME}.exe --uid <SOPInstanceUID do plano>
  3. Os extras, que custam tempo e disco:
       --ct        traz UMA serie de CT e mede objetos, MB e segundos
       --carga 4   quatro associacoes ao mesmo tempo
       --sem-padrao  mede o que ESTA estacao tem configurado, e so

O QUE LER, nesta ordem
  1. o bloco 12: e o chamado, ja escrito e separado por fase;
  2. dentro dele, a secao NOSSO - essas nao sao da TI, sao configuracao da
     instalacao, e abrir chamado para elas gasta uma ida a toa;
  3. o bloco 1, campo "IP de saida": e o numero que a TI cadastra.

RODAR EM MAIS DE UMA ESTACAO, e guardar os dois arquivos. E a comparacao entre
eles que responde a pergunta que decide o custo: o cadastro do nosso AE Title
amarra IP? Se amarrar, e um chamado por estacao, para sempre.

O RELATORIO cai NESTA pasta, com data e hora no nome - nenhuma rodada
sobrescreve a anterior. E ele que vai para o chamado.
""", encoding="utf-8")
    return alvo


def zipar() -> Path:
    alvo = RAIZ / "dist" / f"{NOME}_{date.today():%Y%m%d}.zip"
    if alvo.exists():
        alvo.unlink()
    with zipfile.ZipFile(alvo, "w", zipfile.ZIP_DEFLATED) as z:
        for arquivo in sorted(DESTINO.rglob("*")):
            if arquivo.is_file():
                z.write(arquivo, arquivo.relative_to(DESTINO.parent))
    return alvo


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--sem-zip", action="store_true",
                   help="só gera a pasta dist/, sem empacotar")
    args = p.parse_args(argv)

    print("=" * 70)
    print(f"  Gerando o {NOME} — {date.today():%d/%m/%Y}")
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

    passo(3, "rodando o exe de verdade (exige o bloco do pedido)")
    saida = smoke_test()
    print(f"    o binário subiu e escreveu {len(saida.splitlines())} linhas")

    passo(4, "escrevendo o acompanhante")
    print(f"    {escrever_leiame().name}")

    passo(5, "conferindo que nenhum relatório viaja no pacote")
    conferir_limpeza()
    print("    limpo")

    if args.sem_zip:
        print(f"\nPronto (sem zip): {DESTINO}")
        return 0

    passo(6, "empacotando")
    alvo = zipar()
    print(f"    {alvo.name} — {alvo.stat().st_size / 1024 / 1024:.1f} MB")

    print("\n" + "=" * 70)
    print(f"  PRONTO: {alvo}")
    print("  Levar ESTE zip para a estação da clínica.")
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
