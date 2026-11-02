#!/usr/bin/env python
"""Confere o arquivo .py recém-editado, na hora, antes que o erro viaje.

Por que existe: o ciclo caro deste projeto é editar, rodar a suíte (3 a 8
minutos) e só então descobrir um nome trocado. O `ruff check` do arquivo custa
0,2s e pega import quebrado, nome inexistente e variável morta imediatamente —
com as MESMAS regras do `ruff.toml` que a extensão do VSCode já mostra, para
que editor e agente nunca discordem.

Além do ruff, confere as armadilhas do CLAUDE.md que nenhum linter conhece
porque são específicas daqui. Todas as três estavam em ZERO ocorrências quando
o gancho foi escrito: se alguma acender, é código novo, não dívida antiga.

Saída 2 devolve o texto do stderr ao agente; saída 0 deixa passar.
"""
from __future__ import annotations

import ast
import contextlib
import json
import subprocess
import sys
from pathlib import Path

# Cópias empacotadas do próprio programa e a venv: apontar aviso nelas é
# apontar duas vezes no mesmo código. Mesma lista do `exclude` do ruff.toml.
IGNORADAS = {".venv", "dist", "build", "distribuicao", "__pycache__"}


def _armadilhas(caminho: Path, fonte: str) -> list[str]:
    """As que o ruff não tem como saber — cada uma custou uma sessão.

    Trabalha em AST, não em regex: o próprio CLAUDE.md CITA duas delas em
    texto, e um grep ingênuo acusaria a docstring que explica a armadilha em
    vez do código que a comete.
    """
    try:
        arvore = ast.parse(fonte)
    except SyntaxError:
        return []  # o ruff já reclamou disso, com linha e coluna.

    achados: list[str] = []
    em_teste = caminho.parent.name == "tests" or caminho.name.startswith("test_")

    for no in ast.walk(arvore):
        # `del modulo.funcao` em teste: `modulo.f = falsa` grava no __dict__ do
        # módulo, e o `del` depois some com a ORIGINAL para o resto do
        # processo. Um `del capa_db.conexao` já apagou a função de verdade e
        # quebrou 16 casos — mas só na ordem alfabética, que é a do discover.
        if em_teste and isinstance(no, ast.Delete):
            for alvo in no.targets:
                if isinstance(alvo, ast.Attribute):
                    achados.append(
                        f"linha {no.lineno}: `del {ast.unparse(alvo)}` apaga a função "
                        "ORIGINAL do módulo para o resto do processo. Guardar o valor "
                        "antigo e devolvê-lo no tearDown."
                    )

        if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute):
            nome = no.func.attr
            primeiro = no.args[0] if no.args else None
            vazio = isinstance(primeiro, ast.Constant) and primeiro.value == ""

            # O Qt lê string vazia como "não há texto especial" e o texto
            # especial simplesmente não aparece. Precisa de um espaço.
            if nome == "setSpecialValueText" and vazio:
                achados.append(
                    f'linha {no.lineno}: `setSpecialValueText("")` não funciona — o Qt '
                    'lê string vazia como "não há texto especial". Usar um espaço: " ".'
                )

            # Em combo NÃO editável o valor anterior fica — e o dado do
            # paciente anterior vaza para a tela do seguinte. Vazio é
            # setCurrentIndex(-1).
            if nome == "setCurrentText" and vazio:
                achados.append(
                    f'linha {no.lineno}: `setCurrentText("")` não limpa combo não '
                    "editável (o valor anterior fica). Vazio é `setCurrentIndex(-1)`."
                )

    # Zerar ``ISOCENTRO_DB_SERVIDOR`` NÃO desliga o banco: sem a variável, o
    # ``capa_db._config`` cai no ``config_servico.json``, que nesta estação
    # aponta o SRVINSIGHT — e ``configurado()`` continua verdadeiro. O teste vai
    # à rede de verdade (medido: sai a recusa de SSPI) ou, pior, passa de carona
    # em outro arquivo da suíte que redirecionou a pasta antes dele. Já custou
    # CINCO arquivos de teste; o último foi o ``test_capa_espelho``, achado em
    # 08/09/2026 porque começou a rodar sozinho.
    if em_teste:
        zera = _zera_o_servidor(arvore)
        if zera and not _isola_a_configuracao(fonte):
            achados.append(
                f"linha {zera}: zerar `ISOCENTRO_DB_SERVIDOR` não desliga o banco — o "
                "`capa_db._config` cai no `config_servico.json` desta estação "
                "(SRVINSIGHT). Apontar `ISOCENTRO_CONFIG` para uma pasta vazia, ou "
                "trocar `capa_db.configurado` por `lambda: False`."
            )

        # A QUARTA porta, aberta em 09/09/2026: o ``capa_db`` passou a ler pelo
        # ``ambiente.ler``, então ``ISOCENTRO_DB_SERVIDOR`` também aponta o
        # banco — e VENCE o nome antigo. Mexer só no antigo virou meia medida
        # nos dois sentidos: não desliga, e não fixa (a variável da estação
        # ganha do ``SERVIDOR-DE-TESTE`` que o ``setUp`` acabou de gravar).
        mexe = zera or _fixa_o_servidor(arvore)
        ja_cobre = ("ISOCENTRO_DB_SERVIDOR" in fonte
                    or "nome_novo" in fonte)
        if mexe and not ja_cobre:
            achados.append(
                f"linha {mexe}: mexer só em `ISOCENTRO_DB_SERVIDOR` não basta desde "
                "09/09/2026 — o `capa_db` lê pelo `ambiente.ler` e o "
                "`ISOCENTRO_DB_SERVIDOR` da estação tem PRECEDÊNCIA. Tirar "
                "os dois: `os.environ.pop(ambiente.nome_novo(capa_db.ENV_SERVIDOR), None)`."
            )

    return achados


def _zera_o_servidor(arvore: ast.AST) -> int:
    """Linha em que o teste tenta desligar o banco pela variável de ambiente."""
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call) or not isinstance(no.func, ast.Attribute):
            continue
        if no.func.attr != "pop" or not no.args:
            continue
        alvo = no.args[0]
        if isinstance(alvo, ast.Constant) and alvo.value == "ISOCENTRO_DB_SERVIDOR":
            return no.lineno
        # ``os.environ.pop(capa_db.ENV_SERVIDOR, None)`` é a forma mais comum
        if isinstance(alvo, ast.Attribute) and alvo.attr == "ENV_SERVIDOR":
            return no.lineno
    return 0


def _fixa_o_servidor(arvore: ast.AST) -> int:
    """Linha em que o teste GRAVA a variável do servidor (``os.environ[...] = ``).

    Desligar e fixar têm o mesmo furo: quem grava só o nome antigo é vencido
    pelo novo, e o teste passa a depender de como ESTA estação está configurada.
    """
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Assign):
            continue
        for alvo in no.targets:
            if not isinstance(alvo, ast.Subscript):
                continue
            chave = alvo.slice
            if isinstance(chave, ast.Constant) and chave.value == "ISOCENTRO_DB_SERVIDOR":
                return no.lineno
            if isinstance(chave, ast.Attribute) and chave.attr == "ENV_SERVIDOR":
                return no.lineno
    return 0


def _isola_a_configuracao(fonte: str) -> bool:
    """O arquivo já se protege do ``config_servico.json`` da estação?

    Aqui é texto e não AST de propósito: um falso "está isolado" só cala o
    aviso, enquanto um falso "não está" acusaria quem fez certo — e aviso que
    erra é aviso que se aprende a ignorar.
    """
    return ("ISOCENTRO_CONFIG" in fonte
            or "configurado = lambda" in fonte
            or "configurado," in fonte)


def main() -> int:
    # O console do Windows abre em cp1252 e engoliria os acentos das mensagens
    # abaixo — que são justamente a explicação de cada armadilha.
    for fluxo in (sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError, ValueError):
            fluxo.reconfigure(encoding="utf-8", errors="replace")

    try:
        evento = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    bruto = (evento.get("tool_input") or {}).get("file_path") or ""
    if not bruto:
        return 0

    caminho = Path(bruto)
    if caminho.suffix != ".py" or not caminho.is_file():
        return 0
    if IGNORADAS & set(caminho.parts):
        return 0

    try:
        fonte = caminho.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return 0  # posicionamento.py tem BOM; o utf-8 puro falharia à toa.

    problemas: list[str] = []

    ruff = subprocess.run(
        # `concise` de propósito: o formato longo repete o trecho de código e o
        # conserto sugerido, e o agente que lê isto JÁ TEM o arquivo aberto —
        # é contexto pago duas vezes. Arquivo, linha e regra bastam.
        [sys.executable, "-m", "ruff", "check", "--no-cache",
         "--output-format=concise", str(caminho)],
        capture_output=True, text=True,
    )
    if ruff.returncode not in (0, 1):
        return 0  # ruff ausente ou quebrado: não travar o trabalho por isso.
    if ruff.returncode == 1 and ruff.stdout.strip():
        problemas.append(ruff.stdout.strip())

    armadilhas = _armadilhas(caminho, fonte)
    if armadilhas:
        problemas.append(
            "Armadilhas já pagas neste repositório (ver CLAUDE.md):\n  - "
            + "\n  - ".join(armadilhas)
        )

    if not problemas:
        return 0

    print(
        f"[checagem de {caminho.name}]\n" + "\n\n".join(problemas)
        + "\n\nCorrigir antes de seguir — isto é o linter do projeto, "
          "não é a suíte de testes.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
