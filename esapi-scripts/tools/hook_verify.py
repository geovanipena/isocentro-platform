#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hook PostToolUse: ao editar scripts/<pasta>/*.cs, roda verificações rápidas e reporta.

Lê o JSON do hook no stdin, extrai o arquivo editado; se for scripts/<pasta>/*.cs, checa
BOM do arquivo + paridade da #region PADRÃO CLINICA + armadilhas C# 5 + typecheck
(compilação C# 5/net452; pulado se as DLLs Varian não estiverem em lib/).
Sai 0 (informativo) em sucesso; 2 se algo falhar (o stderr volta pro Claude).
"""
import sys, os, re, json, subprocess


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0

    ti = data.get("tool_input") or {}
    fp = (ti.get("file_path") or "").replace("\\", "/")
    # normaliza caminho MSYS (/c/...) -> Windows (C:/...) p/ o Python nativo abrir
    m = re.match(r"^/([a-zA-Z])/(.*)$", fp)
    if m:
        fp = m.group(1).upper() + ":/" + m.group(2)
    if not re.search(r"/scripts/[^/]+/[^/]+\.cs$", fp):
        return 0  # não é um script ESAPI — nada a fazer

    root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    tools = os.path.join(root, "tools")
    py = sys.executable or "python"
    problems = []

    # 1) BOM do arquivo editado (repo é UTF-8 no-BOM). NÃO checamos CRLF aqui: com
    # core.autocrlf=true a working tree é CRLF mas o commit sai LF — checar EOL local
    # daria falso alarme a cada edição. EOL é garantido por .gitattributes + git.
    try:
        with open(fp, "rb") as f:
            raw = f.read()
        if raw.startswith(b"\xef\xbb\xbf"):
            problems.append("BOM UTF-8 presente (repo é no-BOM).")
    except OSError:
        pass

    # 2) paridade da #region PADRÃO CLINICA (todos os arquivos)
    r = subprocess.run([py, os.path.join(tools, "check_region_parity.py")],
                       capture_output=True, text=True)
    if r.returncode != 0:
        problems.append("paridade da #region PADRÃO CLINICA FALHOU:\n" +
                        (r.stdout or "") + (r.stderr or ""))

    # 3) armadilhas C# 5 no arquivo editado
    r = subprocess.run([py, os.path.join(tools, "check_csharp_traps.py"), fp],
                       capture_output=True, text=True)
    if r.returncode != 0:
        problems.append("armadilhas C# 5:\n" + (r.stdout or "") + (r.stderr or ""))

    # 4) typecheck (compila o arquivo editado em C# 5 / net452). exit 3 = DLLs Varian
    # ausentes nesta máquina -> typecheck indisponível, apenas pula (não é falha).
    ps1 = os.path.join(tools, "typecheck.ps1")
    tc = None
    try:
        tc = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                             "-File", ps1, "-Path", fp], capture_output=True, text=True)
    except OSError:
        pass  # powershell indisponível -> pula typecheck
    tc_ran = tc is not None and tc.returncode != 3
    if tc is not None and tc.returncode not in (0, 3):
        problems.append("typecheck (compilação C# 5) FALHOU:\n" +
                        (tc.stdout or "") + (tc.stderr or ""))

    name = os.path.basename(fp)
    checks = "encoding, região, armadilhas C# 5" + (", typecheck" if tc_ran else "")
    if problems:
        sys.stderr.write("Verificação pós-edição de %s FALHOU:\n- %s\n"
                         % (name, "\n- ".join(problems)))
        return 2
    sys.stderr.write("OK: %s passou (%s).\n" % (name, checks))
    return 0


if __name__ == "__main__":
    sys.exit(main())
