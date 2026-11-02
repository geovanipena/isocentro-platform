"""Os ganchos do Claude Code (`.claude/hooks/`), versionados desde 29/10/2026.

Rodam sozinhos em toda sessão e ficavam fora do git, sem teste. O que estes
testes guardam, cada um tirado da cascata de 28–29/10/2026 (ARMADILHAS):

- gancho conferido que AGE: o abertura.py rodado pela manutenção rodava a
  manutenção, que o rodava de novo — 80 processos;
- a abertura ESPERANDO a manutenção: ela nunca terminava em 20 s, a marca
  da semana nunca era gravada e toda sessão a disparava de novo;
- espera interna maior que o limite que o Claude Code dá ao gancho: ele
  mata o gancho e o filho fica órfão, rodando;
- gancho que quebra ou demora com o payload real do evento.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parent.parent
GANCHOS = RAIZ / ".claude" / "hooks"
sys.path.insert(0, str(RAIZ / "tools"))

import manutencao  # noqa: E402

SEM_EFEITO = {**os.environ, "PYTHONIOENCODING": "utf-8",
              "ISOCENTRO_GANCHO_SEM_EFEITO": "1",
              "CLAUDE_PROJECT_DIR": str(RAIZ)}


def _abertura():
    spec = importlib.util.spec_from_file_location(
        "abertura_teste", GANCHOS / "abertura.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _limites_do_settings() -> dict:
    """``{gancho.py: segundos}`` do settings.json desta estação (fora do git)."""
    arquivo = RAIZ / ".claude" / "settings.json"
    if not arquivo.is_file():
        return {}
    ajustes = json.loads(arquivo.read_text(encoding="utf-8"))
    limites = {}
    for grupos in (ajustes.get("hooks") or {}).values():
        for grupo in grupos:
            for g in grupo.get("hooks", []):
                m = re.search(r"hooks[/\\]([\w.]+\.py)", g.get("command", ""))
                if m:
                    limites[m.group(1)] = int(g.get("timeout", 60))
    return limites


class TestCadaGancho(unittest.TestCase):

    def test_roda_com_o_payload_real_e_rapido(self):
        for nome, payload in manutencao.PAYLOADS.items():
            caminho = GANCHOS / nome
            if not caminho.is_file():
                continue
            with self.subTest(gancho=nome):
                inicio = time.monotonic()
                r = subprocess.run(
                    [sys.executable, str(caminho)], input=json.dumps(payload),
                    cwd=RAIZ, capture_output=True, text=True, encoding="utf-8",
                    errors="replace", timeout=30, env=SEM_EFEITO)
                self.assertEqual(r.returncode, 0, r.stderr[-500:])
                self.assertLess(time.monotonic() - inicio, 10)

    def test_espera_interna_menor_que_o_limite_do_gancho(self):
        """Com a espera maior, o Claude Code mata o gancho e o filho fica."""
        limites = _limites_do_settings()
        if not limites:
            self.skipTest("sem .claude/settings.json nesta estação")
        for nome, limite in limites.items():
            fonte = (GANCHOS / nome).read_text(encoding="utf-8")
            for espera in re.findall(r"timeout=(\d+)", fonte):
                with self.subTest(gancho=nome, espera=espera):
                    self.assertLess(int(espera), limite)


class TestAbertura(unittest.TestCase):

    def setUp(self):
        self.ab = _abertura()
        tmp = Path(tempfile.mkdtemp())
        self.ab.MANUTENCAO = tmp / "nunca_rodou.tsv"     # semana vencida
        self.ab.RELATORIO = tmp / "manutencao_ultima.md"
        self.ab.ANUNCIADO = tmp / "anunciado.txt"
        self.ab.TRAVA = tmp / "manutencao.trava"

    def test_dispara_a_manutencao_sem_esperar(self):
        self.ab.SEM_EFEITO = False
        with mock.patch.object(self.ab.subprocess, "Popen") as popen, \
                mock.patch.object(self.ab.subprocess, "run") as run:
            aviso = self.ab._manutencao()
        popen.assert_called_once()
        self.assertIn("manutencao.py", " ".join(popen.call_args.args[0]))
        self.assertFalse(any("manutencao.py" in " ".join(map(str, c.args[0]))
                             for c in run.call_args_list),
                         "a abertura voltou a ESPERAR a manutenção")
        self.assertIn("segundo plano", aviso)

    def test_conferido_nao_dispara_nada(self):
        self.ab.SEM_EFEITO = True
        with mock.patch.object(self.ab.subprocess, "Popen") as popen, \
                mock.patch.object(self.ab.subprocess, "run") as run:
            self.assertEqual(self.ab._manutencao(), "")
            self.ab._postgres_local()
        popen.assert_not_called()
        run.assert_not_called()

    def test_variavel_defasada_e_avisada(self):
        """28/10/2026: a ISOCENTRO_PG_APP nova não chegava ao app aberto
        pelo VS Code, e a aba PPR ficou "sem dado" sem explicação."""
        with mock.patch.object(self.ab, "_variaveis_defasadas",
                               return_value=["ISOCENTRO_PG_APP"]), \
                mock.patch.object(self.ab, "_postgres_local", return_value=""):
            aviso = self.ab._ambiente()
        self.assertIn("`ISOCENTRO_PG_APP`", aviso)
        self.assertIn("VS Code", aviso)


if __name__ == "__main__":
    unittest.main()
