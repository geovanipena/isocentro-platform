"""O robô (`tools/robo.py`) e a trava dele (`tools/robo_trava.py`).

O robô roda sem ninguém olhando, então o que estes testes guardam é o que
ninguém veria quebrar: a fila lida errado (o robô pega uma frente `voce`), a
trava deixando passar uma edição no papel, a mensagem de limite confundida com
fim de sessão (o robô desiste de uma frente que só estava esperando o limite
liberar), e a configuração perdendo a proibição do push.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))
if str(RAIZ / "tools") not in sys.path:
    sys.path.insert(0, str(RAIZ / "tools"))

import robo  # noqa: E402
import robo_trava  # noqa: E402
import suite  # noqa: E402

_FILA = """\
# Destino

## A fila

### R-01 — Primeira
- classe: voce
- estado: pendente
- pronto quando: algo.

### R-02 — Segunda
- classe: robo
- estado: feita (15/09/2026)

### R-03 — Terceira
- classe: robo
- estado: pendente
- pronto quando: medido.
- fora: o papel.

## Esperando você

(vazio)
"""


class TestFila(unittest.TestCase):
    def test_pega_so_robo_pendente(self):
        """A R-01 vem antes na fila, mas é do usuário: pegá-la seria o robô
        mexer no que exige aceite."""
        frente = robo.proxima(robo.ler_fila(_FILA), set())
        self.assertEqual(frente.id, "R-03")

    def test_desistida_nao_volta_na_mesma_rodada(self):
        self.assertIsNone(robo.proxima(robo.ler_fila(_FILA), {"R-03"}))

    def test_bloco_leva_o_contrato_e_nao_a_secao_seguinte(self):
        """O bloco vai inteiro no prompt; se engolisse "Esperando você", a
        sessão leria a caixa do usuário como parte do escopo."""
        bloco = robo.ler_fila(_FILA)[-1].bloco
        self.assertIn("- fora: o papel.", bloco)
        self.assertNotIn("Esperando", bloco)

    def test_o_destino_do_repositorio_se_le(self):
        """O formato é fixo porque o robô lê. Se alguém escrever `classe: 🤖`
        ou esquecer o travessão do título, a frente some da fila CALADA."""
        texto = (RAIZ / "DESTINO.md").read_text(encoding="utf-8")
        fila = robo.ler_fila(texto)
        self.assertTrue(fila)
        self.assertEqual(len(fila), texto.count("\n### R-"))
        ids = [f.id for f in fila]
        self.assertEqual(len(ids), len(set(ids)), "id de frente repetido")
        for f in fila:
            self.assertIn(f.classe, {"robo", "voce", "clinica"}, f.id)
            self.assertRegex(f.estado, r"^(pendente|feita|estacionada)", f.id)

    def test_classe_mudada_ou_frente_robo_nova_reprova(self):
        antes = {"R-01": "voce", "R-03": "robo"}
        self.assertEqual(robo.classes_mudadas(antes, {"R-01": "robo", "R-03": "robo"}), ["R-01"])
        self.assertEqual(robo.classes_mudadas(antes, {**antes, "R-09": "robo"}), ["R-09"])
        self.assertEqual(robo.classes_mudadas(antes, dict(antes)), [])


class TestSaida(unittest.TestCase):
    AGORA = datetime(2026, 9, 15, 14, 0, 0)

    def test_marca_vence_a_palavra_limite(self):
        """Sessão que terminou a frente e cita "rate limit" num comentário não
        pode ser posta para dormir meia hora."""
        s = robo.classificar("mexi no rate limit do cliente\nROBO: FEITA R-03", self.AGORA)
        self.assertEqual((s.tipo, s.marca, s.frente), ("fim", "FEITA", "R-03"))

    def test_marca_dentro_do_json(self):
        bruto = json.dumps({"type": "result", "result": "pronto.\nROBO: ESTACIONADA R-03: precisa da TI"})
        s = robo.classificar(bruto, self.AGORA)
        self.assertEqual((s.marca, s.motivo), ("ESTACIONADA", "precisa da TI"))

    def test_limite_com_hora(self):
        s = robo.classificar(json.dumps({"is_error": True, "result": "You've hit your limit · resets 3pm"}),
                             self.AGORA)
        self.assertEqual(s.tipo, "limite")
        self.assertEqual(s.espera_s, 3600 + 60)

    def test_limite_com_hora_que_ja_passou_e_amanha(self):
        s = robo.espera_do_limite("resets 1pm", self.AGORA)
        self.assertEqual(s, 23 * 3600 + 60)

    def test_limite_em_epoca(self):
        alvo = int(self.AGORA.timestamp()) + 600
        self.assertEqual(robo.espera_do_limite(f"Claude AI usage limit reached|{alvo}", self.AGORA), 660)

    def test_limite_sem_hora_espera_o_padrao(self):
        s = robo.classificar("Claude usage limit reached.", self.AGORA)
        self.assertEqual((s.tipo, s.espera_s), ("limite", robo.ESPERA_LIMITE_S))

    def test_queda_de_conexao(self):
        """A queda de rotina deste projeto: não pode contar tentativa da frente."""
        self.assertEqual(robo.classificar("API Error: Connection refused", self.AGORA).tipo, "queda")

    def test_sessao_que_terminou_e_fala_de_limite_nao_dorme(self):
        """JSON sem `is_error` é sessão que terminou: o "rate limit" é do
        trabalho dela, não o erro dela."""
        bruto = json.dumps({"is_error": False, "result": "o rate limit do servidor ficou igual"})
        self.assertEqual(robo.classificar(bruto, self.AGORA).tipo, "fim")

    def test_sem_marca_e_fim_sem_marca(self):
        s = robo.classificar(json.dumps({"result": "fiz metade"}), self.AGORA)
        self.assertEqual((s.tipo, s.marca), ("fim", ""))

    def test_limite_de_sessao_de_15_09(self):
        """O `result` de verdade das 10:50 de 15/09/2026. "hit your SESSION
        limit" não casava com a regex: virou fim sem marca, a árvore suja
        reprovou e o robô parou em vez de dormir até 14:20."""
        bruto = "\n".join([
            json.dumps({"type": "result", "is_error": True, "api_error_status": 429,
                        "terminal_reason": "api_error",
                        "result": "You've hit your session limit · resets 2:20pm (America/Sao_Paulo)"}),
            "Ignoring 60 permissions.allow entries from .claude/settings.json: this workspace "
            "has not been trusted.",
        ])
        s = robo.classificar(bruto, datetime(2026, 9, 15, 10, 50, 0))
        self.assertEqual((s.tipo, s.espera_s), ("limite", 3.5 * 3600 + 60))

    def test_429_com_frase_nova_ainda_e_limite(self):
        """A frase mudou uma vez sem aviso; o código HTTP não."""
        bruto = json.dumps({"is_error": True, "api_error_status": 429, "result": "Pausa até amanhã."})
        self.assertEqual(robo.classificar(bruto, self.AGORA).tipo, "limite")

    def test_5xx_no_result_e_queda(self):
        bruto = json.dumps({"is_error": True, "api_error_status": 529, "result": "Overloaded"})
        self.assertEqual(robo.classificar(bruto, self.AGORA).tipo, "queda")


class TestPrompt(unittest.TestCase):
    def test_leva_o_contrato_as_marcas_e_a_proibicao_do_push(self):
        frente = robo.ler_fila(_FILA)[-1]
        texto = robo.montar_prompt(frente, False, "15/09/2026")
        self.assertIn("- fora: o papel.", texto)
        self.assertIn("ROBO: FEITA R-03", texto)
        self.assertIn("Não faça push", texto)
        self.assertNotIn("RETOMADA", texto)
        self.assertIn("RETOMADA", robo.montar_prompt(frente, True, "15/09/2026"))

    def test_suite_em_primeiro_plano_pelo_caminho_absoluto(self):
        """A R-01 (15/09/2026) seguiu o `/pronto`: suíte com `run_in_background`
        e `> arquivo`. Os comandos foram recusados, a sessão respondeu "aguardo
        o resultado" e acabou — no `-p` a resposta que termina é a sessão que
        termina. E pelo caminho relativo a sessão chamaria um `tools/suite.py`
        que a branch `robo` ainda não tem."""
        texto = robo.montar_prompt(robo.ler_fila(_FILA)[-1], False, "15/09/2026")
        absoluto = (RAIZ / "tools" / "suite.py").as_posix()
        self.assertIn(f"`python {absoluto}`", texto)
        self.assertIn("run_in_background", texto)
        self.assertTrue(Path(absoluto).is_file())

    def test_recusas_conhecidas_estao_no_prompt(self):
        """As recusas de 15/09/2026 que a lista não deve cobrir: `git -C`
        (não se libera sem liberar `git -C x push`) e `%TEMP%`."""
        prompt = robo.montar_prompt(robo.ler_fila(_FILA)[-1], False, "15/09/2026")
        self.assertIn("sem `-C`", prompt)
        self.assertIn("relatorios_ferramentas/tmp_robo/", prompt)

    def test_aleatoria_so_na_conferencia(self):
        """Até 15/09/2026 eram três passes de suíte por frente (completa e
        aleatória na sessão, completa de novo na conferência): ~8 min, um
        repetido. A sessão que voltasse a pedir a aleatória refaria o passe que
        a conferência já faz."""
        texto = robo.montar_prompt(robo.ler_fila(_FILA)[-1], False, "15/09/2026")
        self.assertNotIn("--aleatoria`", texto)
        self.assertIn("A ordem aleatória NÃO é sua", texto)
        self.assertEqual(robo.SUITE_DA_CONFERENCIA, ["tests/ordem_aleatoria.py"])
        self.assertTrue((RAIZ / robo.SUITE_DA_CONFERENCIA[0]).is_file())

    def test_raio_nenhum_pula_revisao_e_suite_pela_partida(self):
        """Os questionários R-71..R-75 (23/10/2026), só documento, pagaram cada
        um o code-review e a suíte inteira. O raio se mede contra a PARTIDA,
        não contra o HEAD: no fechamento o HEAD já tem os commits da frente."""
        texto = robo.montar_prompt(robo.ler_fila(_FILA)[-1], False, "15/09/2026", "abc123")
        self.assertIn("`python tools/raio.py abc123`", texto)
        self.assertIn("`python tools/testar.py --raio --ref abc123`", texto)
        self.assertTrue((RAIZ / robo.SUITE_DE_DOCUMENTO[0]).is_file())


def _evento(tipo: str, **campos) -> str:
    return json.dumps({"type": tipo, **campos})


def _resposta(ident: str, uso: dict, *blocos: dict) -> str:
    return _evento("assistant", message={"id": ident, "usage": uso, "content": list(blocos)})


class TestStream(unittest.TestCase):
    AGORA = datetime(2026, 9, 15, 14, 0, 0)

    def test_limite_escrito_no_transcript_nao_dorme(self):
        """Com `stream-json` a saída leva o transcript: a resposta do gancho de
        abertura (o NOTAS.md) e cada arquivo lido — o `robo.py` tem "rate
        limit" na regex. Uma sessão que só caiu não pode dormir meia hora por
        isso; tem de ser lida como queda."""
        bruto = "\n".join([
            _evento("system", subtype="hook_response", output="Claude usage limit reached."),
            _resposta("m1", {"output_tokens": 3},
                      {"type": "text", "text": "_LIMITE = re.compile(r'usage limit|rate limit')"}),
            "API Error: Connection refused",
        ])
        self.assertEqual(robo.classificar(bruto, self.AGORA).tipo, "queda")

    def test_result_do_stream_decide(self):
        bruto = "\n".join([
            _resposta("m1", {"output_tokens": 3}, {"type": "text", "text": "rate limit"}),
            _evento("result", is_error=False, result="feito\nROBO: FEITA R-03"),
        ])
        s = robo.classificar(bruto, self.AGORA)
        self.assertEqual((s.tipo, s.marca), ("fim", "FEITA"))

    def test_limite_no_result_do_stream(self):
        bruto = "\n".join([
            _resposta("m1", {"output_tokens": 3}, {"type": "text", "text": "olhando"}),
            _evento("result", is_error=True, result="You've hit your limit · resets 3pm"),
        ])
        self.assertEqual(robo.classificar(bruto, self.AGORA).tipo, "limite")

    def test_custo_repartido_pelas_skills(self):
        """A pergunta de 15/09/2026: é a revisão que pesa? A troca de etapa é a
        chamada da skill, e a resposta repetida em vários eventos (um por bloco)
        conta uma vez."""
        def skill(nome):
            return {"type": "tool_use", "name": "Skill", "input": {"skill": nome}}

        entrada = {"input_tokens": 100}
        bruto = "\n".join([
            _resposta("m1", entrada, {"type": "text", "text": "a frente"}),
            _resposta("m2", entrada, skill("code-review")),
            _resposta("m3", entrada, {"type": "text", "text": "revisando"}),
            _resposta("m3", entrada, {"type": "text", "text": "mesmo id, outro bloco"}),
            _resposta("m4", {"output_tokens": 40}, skill("fechar")),
            _resposta("m5", entrada),
            _evento("result", total_cost_usd=6.0),
        ])
        total, etapas = robo.custo_por_etapa(bruto)
        self.assertEqual(total, 6.0)
        # pesos: frente m1+m2 = 200; code-review m3 + m4 (5×40) = 300; fechar m5 = 100
        self.assertAlmostEqual(etapas["frente"], 2.0)
        self.assertAlmostEqual(etapas["code-review"], 3.0)
        self.assertAlmostEqual(etapas["fechar"], 1.0)

    def test_peso_da_gravacao_de_uma_hora(self):
        """Conferido na sessão vazia de 15/09/2026: 50.944 tokens gravados em
        cache de 1 h custaram o dobro da entrada."""
        uso = {"cache_creation_input_tokens": 50944,
               "cache_creation": {"ephemeral_1h_input_tokens": 50944, "ephemeral_5m_input_tokens": 0}}
        self.assertEqual(robo._peso(uso), 2 * 50944)

    def test_sem_result_nao_inventa_custo(self):
        self.assertEqual(robo.custo_por_etapa(_resposta("m1", {"input_tokens": 9})), (0.0, {}))

    def test_recusas_saem_do_result(self):
        """As 15 recusas de 15/09/2026 só se viam abrindo o JSON à mão. O
        transcript que CITA uma recusa não conta: só o `result` decide."""
        bruto = "\n".join([
            _resposta("m1", {"output_tokens": 3},
                      {"type": "text", "text": '{"permission_denials": [{"tool_name": "Falsa"}]}'}),
            _evento("result", is_error=False, result="ok", permission_denials=[
                {"tool_name": "Bash", "tool_input": {"command": "git  -C C:/x\n diff -U8"}},
                {"tool_name": "Write", "tool_input": {"file_path": "C:\\Temp\\r04_eol.py"}},
            ]),
            "aviso qualquer do stderr",
        ])
        self.assertEqual(robo.recusas(bruto), ["Bash: git -C C:/x diff -U8",
                                               "Write: C:\\Temp\\r04_eol.py"])


class TestSuite(unittest.TestCase):
    def test_veredito_pega_o_que_decide_e_a_semente(self):
        """O que volta para o contexto da sessão tem de bastar para decidir: sem
        a semente, a ordem que quebrou não se repete."""
        texto = ("..F.\nimpressão de teste\n======\n  Ordem aleatória — semente 42\n"
                 "FAIL: test_x (tests.test_a.T.test_x)\nRan 4 tests in 1.0s\n\n"
                 "FAILED (failures=1)\n\n  FALHOU com a semente 42.\n")
        self.assertEqual(suite.veredito(texto), [
            "  Ordem aleatória — semente 42",
            "FAIL: test_x (tests.test_a.T.test_x)",
            "Ran 4 tests in 1.0s",
            "FAILED (failures=1)",
            "  FALHOU com a semente 42.",
        ])

    def test_fora_da_raiz_recusa_sem_rodar(self):
        with tempfile.TemporaryDirectory() as vazia:
            anterior = os.getcwd()
            os.chdir(vazia)
            try:
                self.assertEqual(suite.main([]), 2)
            finally:
                os.chdir(anterior)


class TestTrava(unittest.TestCase):
    RAIZ = Path("C:/repo")

    def _decide(self, caminho, ferramenta="Edit"):
        return robo_trava.decidir(ferramenta, {"file_path": caminho}, self.RAIZ)

    def test_as_tres_pastas_sao_recusadas(self):
        for pasta in ("papel", "interface", "dominio"):
            with self.subTest(pasta=pasta):
                self.assertIsNotNone(self._decide(f"C:/repo/isocentro/{pasta}/x.py"))

    def test_caixa_diferente_nao_passa(self):
        """No Windows é o mesmo arquivo; um prefixo sensível a caixa deixaria."""
        self.assertIsNotNone(self._decide("C:/repo/ISOCENTRO/Papel/ficha_pdf.py"))

    def test_caminho_relativo_tambem(self):
        self.assertIsNotNone(self._decide("isocentro/papel/ficha_pdf.py", "Write"))

    def test_teste_e_banco_passam(self):
        self.assertIsNone(self._decide("C:/repo/tests/test_capa_tela.py"))
        self.assertIsNone(self._decide("C:/repo/isocentro/banco/capa_db.py"))

    def test_fora_do_worktree_e_recusado(self):
        """O checkout do usuário mora ao lado: editar lá é editar a v7."""
        self.assertIsNotNone(self._decide("C:/isocentro/isocentro/banco/capa_db.py"))

    def test_a_propria_coleira(self):
        for alvo in ("tools/robo.py", "tools/robo_trava.py", "tools/robo_settings.json",
                     ".claude/settings.json"):
            with self.subTest(alvo=alvo):
                self.assertIsNotNone(self._decide(f"C:/repo/{alvo}"))

    def test_leitura_passa(self):
        self.assertIsNone(self._decide("C:/repo/isocentro/papel/x.py", "Read"))

    def test_o_robo_confere_o_diff_com_a_mesma_lista(self):
        """A segunda trava (o diff) usa a primeira; se divergissem, um
        `python -c` gravando no papel passaria pela que sobrou."""
        self.assertEqual(robo.travados(["isocentro/papel/a.py", "tests/b.py"]),
                         ["isocentro/papel/a.py"])

    def test_diff_de_verdade_nao_come_letra(self):
        """Num repositório de verdade: modificado, commitado e novo. O recorte
        antigo do `status --porcelain` comia a 1ª letra do 1º arquivo, e
        `isocentro/papel/x.py` passava pela trava como `adioteraficha/…`."""
        with tempfile.TemporaryDirectory() as pasta:
            repo = Path(pasta)

            def g(*args):
                return robo.git(*args, cwd=repo)

            g("init", "-q")
            g("config", "user.email", "robo@teste")
            g("config", "user.name", "robo")
            papel = repo / "isocentro" / "papel"
            papel.mkdir(parents=True)
            (papel / "x.py").write_text("a\n", encoding="utf-8")
            (repo / "leia.md").write_text("a\n", encoding="utf-8")
            g("add", ".")
            g("commit", "-q", "-m", "base")
            antes = g("rev-parse", "HEAD")
            (repo / "leia.md").write_text("b\n", encoding="utf-8")
            g("commit", "-q", "-am", "commitado")
            (papel / "x.py").write_text("b\n", encoding="utf-8")
            (repo / "novo.txt").write_text("c\n", encoding="utf-8")

            tocados = robo.arquivos_tocados(antes, cwd=repo)
        self.assertEqual(tocados, ["isocentro/papel/x.py", "leia.md", "novo.txt"])
        self.assertEqual(robo.travados(tocados), ["isocentro/papel/x.py"])

    def test_gancho_de_verdade(self):
        """Pelo processo, como o claude chama: com o robô ligado recusa, sem
        ele fica mudo — a mesma configuração numa sessão normal não trava o
        usuário."""
        evento = json.dumps({"tool_name": "Edit", "cwd": str(RAIZ),
                             "tool_input": {"file_path": str(RAIZ / "isocentro/papel/x.py")}})
        base = {k: v for k, v in os.environ.items() if not k.endswith("_ROBO")}
        base["CLAUDE_PROJECT_DIR"] = str(RAIZ)
        gancho = [sys.executable, str(RAIZ / "tools" / "robo_trava.py")]

        ligado = subprocess.run(gancho, input=evento, capture_output=True, text=True,
                                env={**base, "ISOCENTRO_ROBO": "1"}, encoding="utf-8")
        decisao = json.loads(ligado.stdout)["hookSpecificOutput"]
        self.assertEqual(decisao["permissionDecision"], "deny")

        desligado = subprocess.run(gancho, input=evento, capture_output=True, text=True,
                                   env=base, encoding="utf-8")
        self.assertEqual(desligado.stdout.strip(), "")


class TestRetomada(unittest.TestCase):
    """A conferência e o ponto de partida num repositório de verdade, com o
    `robo.WORKTREE` apontado para ele."""

    def setUp(self):
        self._pasta = tempfile.TemporaryDirectory()
        self.repo = Path(self._pasta.name)
        self._guardado = (robo.WORKTREE, robo.RAIZ, robo.PARTIDA)
        robo.WORKTREE = robo.RAIZ = self.repo
        robo.PARTIDA = self.repo / "fora" / "partida.json"
        self.g("init", "-q", "-b", robo.BRANCH)
        self.g("config", "user.email", "robo@teste")
        self.g("config", "user.name", "robo")
        (self.repo / ".gitignore").write_text("fora/\n", encoding="utf-8")
        (self.repo / "leia.md").write_text("a\n", encoding="utf-8")
        self.g("add", ".")
        self.g("commit", "-q", "-m", "base")

    def tearDown(self):
        robo.WORKTREE, robo.RAIZ, robo.PARTIDA = self._guardado
        self._pasta.cleanup()

    def g(self, *args):
        return robo.git(*args, cwd=self.repo)

    def commitar(self, texto):
        (self.repo / "leia.md").write_text(texto, encoding="utf-8")
        self.g("commit", "-q", "-am", texto)

    def conferir(self, antes, interrompida):
        # Python que não existe: se a conferência chegar à varredura ou à
        # suíte, o teste quebra com FileNotFoundError em vez de passar calado.
        return robo.conferir(antes, {}, self.g("status", "--porcelain"),
                             str(self.repo / "nao_existe" / "python.exe"), interrompida)

    def test_interrompida_com_arvore_suja_retoma_sem_suite(self):
        """A R-01 de 15/09 cortada no meio parou o robô três vezes; trabalho
        pela metade não é mentira, e não se empurra nem se testa."""
        antes = self.g("rev-parse", "HEAD")
        self.commitar("commit parcial")
        (self.repo / "novo.md").write_text("pela metade\n", encoding="utf-8")
        self.assertEqual(self.conferir(antes, interrompida=True), [])

    def test_feita_com_arvore_suja_reprova(self):
        antes = self.g("rev-parse", "HEAD")
        (self.repo / "novo.md").write_text("esquecido\n", encoding="utf-8")
        falhas = self.conferir(antes, interrompida=False)
        self.assertTrue(any("suja" in f for f in falhas), falhas)

    def test_interrompida_nao_passa_pela_trava(self):
        antes = self.g("rev-parse", "HEAD")
        papel = self.repo / "isocentro" / "papel"
        papel.mkdir(parents=True)
        (papel / "x.py").write_text("b\n", encoding="utf-8")
        falhas = self.conferir(antes, interrompida=True)
        self.assertTrue(any("travado" in f for f in falhas), falhas)

    def test_frente_so_de_documento_confere_pelo_recorte(self):
        """A aleatória inteira (~4 min) numa frente que só escreveu `.md` não
        testa nada que o recorte dos testes que leem o documento não teste."""
        antes = self.g("rev-parse", "HEAD")
        self.commitar("só documento")
        self.assertEqual(robo.suite_da_conferencia(antes),
                         [*robo.SUITE_DE_DOCUMENTO, antes])

    def test_frente_com_codigo_confere_pela_aleatoria(self):
        antes = self.g("rev-parse", "HEAD")
        (self.repo / "tools").mkdir()
        (self.repo / "tools" / "x.py").write_text("a = 1\n", encoding="utf-8")
        self.g("add", ".")
        self.g("commit", "-q", "-m", "código")
        self.assertEqual(robo.suite_da_conferencia(antes), robo.SUITE_DA_CONFERENCIA)

    def test_partida_sobrevive_ao_reinicio(self):
        """Com o HEAD da volta atual, a retomada mediria só os commits DELA: o
        que a sessão cortada commitou antes escaparia da trava do diff."""
        base = robo.ponto_de_partida("R-01")
        self.commitar("parcial da sessão cortada")
        self.assertEqual(robo.ponto_de_partida("R-01"), base)
        robo.encerrar_partida()
        self.assertNotEqual(robo.ponto_de_partida("R-01"), base)

    def test_frente_aberta_e_a_da_partida(self):
        """Depois de um reinício, a árvore suja é da frente que a deixou."""
        self.assertIsNone(robo.frente_aberta())
        robo.ponto_de_partida("R-03")
        self.assertEqual(robo.frente_aberta(), "R-03")
        robo.encerrar_partida()
        self.assertIsNone(robo.frente_aberta())

    def test_partida_de_outra_frente_ou_fora_do_historico_nao_vale(self):
        base = robo.ponto_de_partida("R-01")
        self.commitar("outra")
        self.assertNotEqual(robo.ponto_de_partida("R-03"), base)
        robo.PARTIDA.write_text(json.dumps({"R-03": "0" * 40}), encoding="utf-8")
        self.assertEqual(robo.ponto_de_partida("R-03"), self.g("rev-parse", "HEAD"))


class TestConfiguracao(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((RAIZ / "tools" / "robo_settings.json").read_text(encoding="utf-8"))

    def test_push_so_pelo_robo_py(self):
        """O push da sessão pularia a conferência do diff e da suíte."""
        permissoes = self.config["permissions"]
        self.assertIn("Bash(git push:*)", permissoes["deny"])
        self.assertFalse([a for a in permissoes["allow"] if "push" in a])

    def test_conhecimento_entra_como_diretorio_adicional(self):
        """Sem ele, toda leitura da base de conhecimento pelo Bash era recusada
        (robo.log, R-72 e R-73 de 23/10/2026), e o questionário cita norma."""
        conhecimento = robo.RAIZ.parent.parent / "conhecimento"
        if not conhecimento.is_dir():
            self.skipTest("estação sem a base de conhecimento")
        config = json.loads(robo.configuracao_da_sessao().read_text(encoding="utf-8"))
        self.assertEqual(config["permissions"]["additionalDirectories"],
                         [conhecimento.as_posix()])

    def test_liga_a_trava(self):
        self.assertEqual(self.config["env"]["ISOCENTRO_ROBO"], "1")
        comandos = [g["command"] for grupo in self.config["hooks"]["PreToolUse"] for g in grupo["hooks"]]
        self.assertTrue(any("$CLAUDE_PROJECT_DIR/tools/robo_trava.py" in c for c in comandos))

    def test_ferramenta_de_clinica_negada_existe(self):
        """Negar `tools/x.py` que foi renomeado nega nada: o nome novo passaria
        pelo `Bash(python:*)` sem ninguém notar."""
        for regra in self.config["permissions"]["deny"]:
            if regra.startswith("Bash(python tools/"):
                arquivo = regra[len("Bash(python "):].split(":")[0]
                with self.subTest(arquivo=arquivo):
                    self.assertTrue((RAIZ / arquivo).exists())

    def test_ferramenta_de_clinica_negada_nos_dois_terminais(self):
        """Até 15/09/2026 só o Bash negava: pelo `PowerShell(python:*)` a sessão
        rodava `python tools/checkup_clinica.py` sem ninguém ver — e a R-01 era
        justamente sobre o checkup."""
        negadas = self.config["permissions"]["deny"]
        for regra in negadas:
            if regra.startswith("Bash(python tools/"):
                with self.subTest(regra=regra):
                    self.assertIn("PowerShell" + regra[len("Bash"):], negadas)

    def test_commit_liberado_no_powershell_nao_libera_amend(self):
        """O `PowerShell(git commit:*)` entrou em 15/09/2026 pelas recusas; sem
        a negação espelhada, o `--amend` que o Bash nega passaria por ele."""
        permissoes = self.config["permissions"]
        for terminal in ("Bash", "PowerShell"):
            if f"{terminal}(git commit:*)" in permissoes["allow"]:
                self.assertIn(f"{terminal}(git commit --amend:*)", permissoes["deny"])


if __name__ == "__main__":
    unittest.main()
