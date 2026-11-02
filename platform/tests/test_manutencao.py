"""A ferramenta que confere o ambiente (``tools/manutencao.py``).

Um relatório de manutenção só serve enquanto é confiável nas duas direções, e
os dois modos de falhar já apareceram na primeira execução dela, em 09/09/2026:

- **acusar o que está certo** — a primeira versão chamou o
  `.claude/hooks/contexto.py` de "gancho órfão". Não é gancho: é o módulo da
  conta de contexto que a barra de estado importa. Relatório que grita à toa é
  relatório que se aprende a pular, e aí parou de servir;
- **medir errado e parecer preciso** — a medida de transcripts contava os
  arquivos das subpastas de anexo e dizia 150 sessões onde havia 50. Número
  inflado num relatório de manutenção é a própria doença que ele persegue.

E acima de tudo: **ela não apaga**. `TCs_Teste/`, zip de release e transcript
antigo dividem terreno com o lixo regenerável, e a única remoção que existe
(`--limpar-ctx`) tem que acertar só os `ctx_*.txt` de sessão morta.
"""
from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))
if str(RAIZ / "tools") not in sys.path:
    sys.path.insert(0, str(RAIZ / "tools"))

import manutencao  # noqa: E402


def _envelhecer(caminho: Path, dias: int) -> None:
    """Recua a data de modificação do arquivo, que é por onde a idade é lida."""
    import os
    quando = (date.today() - timedelta(days=dias)).toordinal()
    segundos = (quando - date(1970, 1, 1).toordinal()) * 86400
    os.utime(caminho, (segundos, segundos))


class IdadeDaMarca(unittest.TestCase):
    """A data `DD/MM` que marca cada pendência no `NOTAS.md`.

    É ela que decide se um "EM ABERTO" merece ser conferido. Errar aqui não dá
    erro nenhum: dá um relatório calado sobre uma pendência de três semanas, ou
    barulhento sobre uma de ontem.
    """

    def test_dia_e_mes_sem_ano_contam_do_ano_corrente(self):
        ontem = date.today() - timedelta(days=1)
        marca = f"- {ontem.strftime('%d/%m')} — alguma pendência"
        self.assertEqual(manutencao._idade_da_marca(marca), 1)

    def test_data_completa_com_ano(self):
        d = date.today() - timedelta(days=40)
        self.assertEqual(
            manutencao._idade_da_marca(f"## Seção — {d.strftime('%d/%m/%Y')}"), 40
        )

    def test_data_a_frente_de_hoje_e_do_ano_passado_e_nao_do_futuro(self):
        """Dezembro visto em janeiro.

        Sem o ano escrito, `31/12` lido em janeiro casaria com o dezembro que
        ainda vem — e uma pendência de 11 meses apareceria como faltando um mês
        para existir, ou seja, jamais velha.
        """
        amanha = date.today() + timedelta(days=1)
        idade = manutencao._idade_da_marca(f"- {amanha.strftime('%d/%m')} — x")
        self.assertGreater(idade, 300)

    def test_sem_data_e_data_impossivel_nao_viram_idade(self):
        self.assertIsNone(manutencao._idade_da_marca("- pendência sem marca"))
        self.assertIsNone(manutencao._idade_da_marca("- 31/02 — fevereiro que não há"))


class MarcaDeConferencia(unittest.TestCase):
    """`conferida em DD/MM` na linha da pendência, e o que ela reinicia.

    Em 09/09/2026 as duas pendências de 19/08 foram conferidas no código:
    `LISTA_VERIFICADA_EM` continuava vazio, e as duas dependem de consulta com
    identidade de rede — estavam abertas de verdade, não vencidas. A idade
    sozinha não separa essas duas coisas, e o relatório pediria a mesma
    conferência toda semana. Achado que se repete sem motivo é o que se aprende
    a pular, e aí ele parou de servir para o que foi feito.
    """

    def test_a_conferencia_de_hoje_cala_o_achado_de_21_dias(self):
        velha = date.today() - timedelta(days=30)
        hoje = date.today()
        linha = (f"- {velha.strftime('%d/%m')} — [algo](notas/x.md) — "
                 f"**conferida em {hoje.strftime('%d/%m')}, continua aberta**")
        self.assertEqual(manutencao._idade_da_conferencia(linha), 0)

    def test_sem_a_marca_nao_ha_idade_de_conferencia(self):
        """Linha comum não pode virar "conferida hoje" por acidente.

        A primeira data da linha é a da ABERTURA. Devolver ela aqui faria toda
        pendência parecer recém-olhada, que é o modo silencioso de o achado
        morrer.
        """
        velha = date.today() - timedelta(days=30)
        linha = f"- {velha.strftime('%d/%m')} — [algo](notas/x.md)"
        self.assertIsNone(manutencao._idade_da_conferencia(linha))
        self.assertEqual(manutencao._idade_da_marca(linha), 30)

    def test_a_marca_nao_rejuvenesce_a_MEDIDA(self):
        """A pendência continua tendo os 30 dias que tem.

        Zerar a medida junto com o gatilho faria o relatório anunciar "a mais
        velha de 0 dias" para um arquivo com frentes de um mês — mediria a data
        da última conferência achando que mede idade.
        """
        velha = date.today() - timedelta(days=30)
        hoje = date.today()
        linha = (f"- {velha.strftime('%d/%m')} — [algo](notas/x.md) — "
                 f"conferida em {hoje.strftime('%d/%m')}")
        self.assertEqual(manutencao._idade_da_marca(linha), 30)

    def test_o_corte_nao_deixa_negrito_aberto(self):
        """Cortar em 100 caracteres partia o `**` no meio.

        O relatório saía com o resto da linha em negrito e o link pela metade —
        o achado ficava ilegível justamente na linha que pede decisão.
        """
        linha = "- 19/08 — [" + "t" * 90 + "](notas/x.md) — **conferida em 09/09**"
        curto = manutencao._encurtar(linha)
        self.assertLessEqual(len(curto), 101)
        for marca in ("**", "`"):
            self.assertEqual(curto.count(marca) % 2, 0, curto)

    def test_linha_curta_passa_inteira(self):
        self.assertEqual(manutencao._encurtar("- 19/08 — algo"), "- 19/08 — algo")


class Recomendadas(unittest.TestCase):
    """As extensões do `.vscode/extensions.json`, que é JSONC.

    O arquivo é quase todo comentário de propósito: cada extensão tem escrito o
    que quebra sem ela, e há um bloco explicando as que **não** entram. Ler as
    strings sem tirar os comentários faria a ferramenta cobrar a instalação de
    extensões que o projeto decidiu recusar — pior que não checar nada.
    """

    def test_extensao_citada_em_comentario_nao_vira_exigencia(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            (raiz / ".vscode").mkdir()
            (raiz / ".vscode" / "extensions.json").write_text(
                '{\n'
                '  // A extensão de verdade.\n'
                '  "recommendations": [\n'
                '    "charliermarsh.ruff",\n'
                '    // "ms-dotnettools.csharp" — é do projeto ESAPI, não deste.\n'
                '    "ms-python.python"\n'
                '  ]\n'
                '}\n',
                encoding="utf-8",
            )
            original = manutencao.RAIZ
            manutencao.RAIZ = raiz
            try:
                achadas = manutencao._recomendadas()
            finally:
                manutencao.RAIZ = original
        self.assertEqual(achadas, ["charliermarsh.ruff", "ms-python.python"])
        self.assertNotIn("ms-dotnettools.csharp", achadas)

    def test_extensao_citada_so_no_comentario_conta_como_decidida(self):
        """Em 22/10/2026 a markdownlint e a de contêineres estavam instaladas
        sem que o arquivo dissesse nada delas. O achado é esse, "sem decisão" —
        e a que ficou de fora COM motivo no comentário não pode cair nele, ou a
        família `ms-dotnettools.*` gritaria toda semana."""
        texto = ('// Não entram:\n'
                 '//   ms-dotnettools.*  — são do projeto ESAPI\n'
                 '"recommendations": ["charliermarsh.ruff"]')
        self.assertTrue(manutencao._extensao_decidida("charliermarsh.ruff", texto))
        self.assertTrue(manutencao._extensao_decidida("ms-dotnettools.csharp", texto))
        self.assertFalse(manutencao._extensao_decidida(
            "ms-azuretools.vscode-containers", texto))


class CopiaDoRestrito(unittest.TestCase):
    """A marca que o `tools/copiar_restrito.ps1` grava depois da cópia cifrada.

    Os backups do `_restrito/` moravam no mesmo disco que ele (22/10/2026). A
    manutenção só lê a marca: copiar dado de paciente para mídia é decisão de
    quem roda o script, nunca da ferramenta.
    """

    def _eixo(self, marca=None, existe=True):
        with tempfile.TemporaryDirectory() as tmp:
            restrito = Path(tmp) / "_restrito"
            if existe:
                restrito.mkdir()
                if marca is not None:
                    (restrito / "ultima_copia.txt").write_text(marca, encoding="ascii")
            e = manutencao.Eixo("x")
            manutencao._conferir_copia_restrito(e, restrito)
        return e

    def test_sem_restrito_e_silencio(self):
        """Outra estação, ou a CI: não há o que copiar."""
        e = self._eixo(existe=False)
        self.assertEqual((e.achados, e.medidas), ([], []))

    def test_nunca_copiado_e_grave(self):
        self.assertTrue(self._eixo().achados[0].grave)

    def test_copia_recente_vira_medida(self):
        ontem = (date.today() - timedelta(days=1)).isoformat()
        e = self._eixo(f"{ontem}\tE:\\copias\t812.4 MB\n")
        self.assertEqual(e.achados, [])
        self.assertIn("812.4 MB", e.medidas[0])

    def test_copia_velha_e_grave(self):
        velha = (date.today() - timedelta(days=manutencao.DIAS_COPIA_RESTRITO + 1))
        e = self._eixo(f"{velha.isoformat()}\tE:\\copias\t1 MB\n")
        self.assertTrue(e.achados and e.achados[0].grave)


class ExtensoesInstaladas(unittest.TestCase):
    """A pasta de extensão desinstalada fica em disco até o VS Code reiniciar.

    Em 22/10/2026 a python-envs foi desinstalada e o relatório continuou
    dizendo "indesejada está instalada": a pasta estava lá, só anotada no
    `.obsolete`. A versão velha que a atualização substituiu é o mesmo caso.
    """

    def test_obsoleta_nao_conta_e_versao_e_a_viva(self):
        with tempfile.TemporaryDirectory() as tmp:
            pasta = Path(tmp)
            for nome in ("ms-python.python-2026.1.0", "ms-python.python-2026.2.0",
                         "ms-python.vscode-python-envs-1.4.0-win32-x64"):
                (pasta / nome).mkdir()
            (pasta / ".obsolete").write_text(
                '{"ms-python.python-2026.2.0":true,'
                '"ms-python.vscode-python-envs-1.4.0-win32-x64":true}',
                encoding="utf-8")
            achadas = manutencao._extensoes_instaladas(pasta)
        self.assertEqual(achadas, {"ms-python.python": "2026.1.0"})


class EixoSkills(unittest.TestCase):
    """O par das extensões para as skills (`tools/skills.jsonc`).

    Skill de usuário vale para toda sessão e nada avisava quando chegava uma: o
    BMad veio inteiro, a `bmad-build` passou a se oferecer em todo pedido de
    mudança, e uma atualização do BMad reinstala o que foi desligado sem dizer.
    Monta uma raiz e uma casa falsas para o eixo não depender da estação.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.raiz, self.casa = base / "raiz", base / "casa"
        (self.raiz / "tools").mkdir(parents=True)
        (self.raiz / "docs").mkdir()
        (self.raiz / ".claude" / "commands").mkdir(parents=True)
        (self.raiz / ".claude" / "commands" / "abrir.md").write_text("x", encoding="utf-8")
        (self.raiz / "docs" / "AMBIENTE.md").write_text("| `/abrir` | abre |", encoding="utf-8")
        (self.raiz / "tools" / "skills.jsonc").write_text(
            '{\n'
            '  // comentário em linha própria\n'
            '  "usadas": ["bmad-prd"],\n'
            '  "desligadas": ["bmad-build"],\n'
            '  "bloqueadas": ["anthropic-skills:ui-ux-pro-max"],\n'
            '  "obrigatorias": ["bmad-prd"]\n'
            '}\n', encoding="utf-8")
        self._settings({"permissions": {"deny": ["Skill(anthropic-skills:ui-ux-pro-max)"]}})
        self._skill("bmad-prd", "description: 'Create a PRD'")
        self._originais = (manutencao.RAIZ, manutencao.ESTADO, manutencao.SKILLS_ANTES)
        manutencao.RAIZ = self.raiz
        manutencao.ESTADO = base / "estado"
        manutencao.SKILLS_ANTES = base / "estado" / "skills.txt"

    def tearDown(self):
        manutencao.RAIZ, manutencao.ESTADO, manutencao.SKILLS_ANTES = self._originais
        self._tmp.cleanup()

    def _settings(self, dados):
        import json
        (self.raiz / ".claude" / "settings.json").write_text(json.dumps(dados), encoding="utf-8")

    def _skill(self, nome, cabecalho):
        p = self.casa / ".claude" / "skills" / nome
        p.mkdir(parents=True)
        (p / "SKILL.md").write_text(f"---\nname: {nome}\n{cabecalho}\n---\ncorpo\n",
                                    encoding="utf-8")

    def _titulos(self, graves):
        return [a.titulo for a in manutencao.eixo_skills(self.casa).achados
                if a.grave == graves]

    def test_estacao_em_dia_nao_grita(self):
        self.assertEqual(manutencao.eixo_skills(self.casa).achados, [])

    def test_desligada_que_voltou_e_grave(self):
        """É o que uma atualização do BMad faz: reinstala o pacote inteiro."""
        self._skill("bmad-build", "description: 'Turns implementation work into code'")
        self.assertTrue(any("DESLIGADA voltou" in t for t in self._titulos(True)))

    def test_skill_nova_sem_decisao_e_para_saber(self):
        self._skill("bmad-nova", "description: >\n  Faz algo novo\n  em duas linhas")
        eixo = manutencao.eixo_skills(self.casa)
        achado = next(a for a in eixo.achados if "sem decisão" in a.titulo)
        self.assertFalse(achado.grave)
        self.assertIn("Faz algo novo em duas linhas", achado.detalhe,
                      "a descrição em bloco `>` é o que se lê para decidir")

    def test_bloqueada_sem_negacao_e_grave(self):
        """Sincronizada do claude.ai volta sozinha; a negação é a única trava."""
        self._settings({"permissions": {"deny": []}})
        self.assertTrue(any("bloqueada" in t for t in self._titulos(True)))

    def test_comando_sem_linha_no_ambiente(self):
        (self.raiz / ".claude" / "commands" / "novo.md").write_text("x", encoding="utf-8")
        self.assertTrue(any("AMBIENTE" in t for t in self._titulos(False)))


class NumerosDaSuite(unittest.TestCase):
    """A medida da suíte no `CLAUDE.md` contra a contagem de hoje.

    Em 22/10/2026 o `CLAUDE.md` dizia 1.945 testes e eram 2.365: o tempo
    prometido (2,7 min) também tinha vencido, e ninguém tinha como saber se a
    suíte mais lenta era defeito ou só crescimento.
    """

    MEDIDA = "Leva **uns 2,7 minutos** (160 s, 1.945 testes, medido em 14/09/2026)."

    def _achado(self, texto, contados):
        from unittest import mock
        with mock.patch.object(manutencao, "_texto", return_value=texto), \
             mock.patch.object(manutencao, "_contar_testes", return_value=contados):
            return manutencao._conferir_numeros_da_suite()

    def test_dentro_de_dez_por_cento_e_silencio(self):
        self.assertIsNone(self._achado(self.MEDIDA, 2100))

    def test_contagem_que_andou_acusa_os_dois_numeros(self):
        a = self._achado(self.MEDIDA, 2365)
        self.assertIn("1.945", a.titulo)
        self.assertIn("2.365", a.titulo)
        self.assertFalse(a.grave)

    def test_sem_contagem_nao_inventa_achado(self):
        """O `discover` falhou (import quebrado): isso é coisa da suíte acusar."""
        self.assertIsNone(self._achado(self.MEDIDA, None))

    def test_medida_sumida_do_claude_md_avisa(self):
        """Reescrever a frase sem o formato desligaria a conferência calada."""
        a = self._achado("Leva uns minutos.", 2365)
        self.assertIn("formato", a.titulo)


class NaoApaga(unittest.TestCase):
    """A regra que não se quebra: a manutenção relata, quem apaga é o usuário.

    A única remoção da ferramenta é o `--limpar-ctx`, e ela tem que ser cirúrgica.
    Um glob solto em `.claude/estado/` levaria junto o `tamanho_notas.tsv` e o
    `manutencao.tsv` — que são justamente as séries que dão sentido ao próximo
    relatório.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._original = manutencao.ESTADO
        manutencao.ESTADO = Path(self._tmp.name)

    def tearDown(self):
        # Devolver o valor guardado, nunca `del manutencao.ESTADO`: o `del`
        # apagaria o atributo do módulo para o resto do processo.
        manutencao.ESTADO = self._original
        self._tmp.cleanup()

    def test_limpar_ctx_leva_so_o_de_sessao_morta(self):
        estado = Path(self._tmp.name)
        velho = estado / "ctx_aaaa.txt"
        recente = estado / "ctx_bbbb.txt"
        serie = estado / "tamanho_notas.tsv"
        for p in (velho, recente, serie):
            p.write_text("x", encoding="utf-8")
        _envelhecer(velho, manutencao.DIAS_CTX_ORFAO + 3)

        # A ferramenta relata na tela; num teste isso é uma linha solta no meio
        # da suíte, e a suíte deste projeto já tem o veredito disputado com
        # stdout bufferizado.
        with contextlib.redirect_stdout(io.StringIO()):
            manutencao._limpar_ctx()

        self.assertFalse(velho.exists(), "o ctx de sessão morta devia ter saído")
        self.assertTrue(recente.exists(), "o ctx da sessão de hoje é de uma sessão VIVA")
        self.assertTrue(serie.exists(), "a série de tamanhos não é lixo de sessão")


class GanchoImportadoNaoEOrfao(unittest.TestCase):
    """O falso positivo de 09/09/2026, que motivou este arquivo.

    Nem todo `.py` em `.claude/hooks/` é uma entrada do `settings.json`: o
    `contexto.py` é o módulo da conta de contexto, importado pela barra de
    estado — "uma só, porque dois números discordando não seriam consultados por
    ninguém". Acusá-lo de órfão mandaria apagar o que sustenta a barra.
    """

    def test_o_contexto_py_nao_e_acusado_de_orfao(self):
        ganchos = RAIZ / ".claude" / "hooks"
        if not (ganchos / "contexto.py").exists():
            self.skipTest("o `.claude/` é configuração de estação e pode não estar aqui")
        eixo = manutencao.eixo_claude()
        # Nome EXATO: "contexto.py" como trecho também pegava o
        # `limite_de_contexto.py`, que é entrada do settings.json e fica órfão de
        # verdade em máquina sem o settings.json da estação (o CI, por exemplo).
        acusacoes = [a.titulo for a in eixo.achados
                     if a.titulo.startswith("`contexto.py`")]
        self.assertEqual(acusacoes, [], f"módulo importado acusado de órfão: {acusacoes}")

    def test_o_relatorio_separa_o_que_decidir_do_que_saber(self):
        """Sem os dois níveis o relatório vira uma lista plana de 6 itens.

        A distinção é o que impede o acúmulo (`·`) de afogar o que já está
        quebrado em silêncio (`!`) — um gancho que estoura some da abertura sem
        avisar, e é o aviso que some.
        """
        eixo = manutencao.eixo_notas()
        self.assertTrue(
            all(isinstance(a.grave, bool) for a in eixo.achados),
            "todo achado precisa se declarar grave ou não",
        )
        self.assertTrue(eixo.medidas, "eixo sem medida não deixa ver que ele olhou")


class UmaManutencaoPorVez(unittest.TestCase):
    """Em 28–29/10/2026 a manutenção rodava o abertura.py ao testar os
    ganchos, ele rodava a manutenção de novo, e assim por diante: 80
    processos e duas suítes derrubadas. Estes testes guardam o corte."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._antes = manutencao.TRAVA, manutencao.ESTADO
        manutencao.ESTADO = self.tmp
        manutencao.TRAVA = self.tmp / "manutencao.trava"

    def tearDown(self):
        manutencao.TRAVA, manutencao.ESTADO = self._antes

    def test_segunda_trava_e_recusada_e_a_primeira_solta_ao_fechar(self):
        import os
        primeira = manutencao.travar()
        self.assertIsNotNone(primeira)
        self.assertIsNone(manutencao.travar(), "duas manutenções ao mesmo tempo")
        os.close(primeira)
        segunda = manutencao.travar()
        self.assertIsNotNone(segunda, "a trava ficou presa depois de solta")
        os.close(segunda)

    def test_trava_diz_quem_a_tem(self):
        import os
        fd = manutencao.travar()
        try:
            pid = manutencao.TRAVA.read_text(encoding="utf-8").split("\t")[0]
            self.assertEqual(pid, str(os.getpid()))
        finally:
            os.close(fd)

    def test_gancho_testado_pela_manutencao_leva_a_marca(self):
        """É a marca que faz o abertura.py rodado por ela não a disparar."""
        visto = {}

        def falso_run(cmd, **kw):
            visto.update(kw.get("env") or {})
            raise manutencao.subprocess.TimeoutExpired(cmd, 1)
        antes = manutencao.subprocess.run
        manutencao.subprocess.run = falso_run
        try:
            manutencao._rodar_gancho(RAIZ / ".claude" / "hooks" / "abertura.py")
        finally:
            manutencao.subprocess.run = antes
        self.assertEqual(visto.get("ISOCENTRO_GANCHO_SEM_EFEITO"), "1")


if __name__ == "__main__":
    unittest.main()
