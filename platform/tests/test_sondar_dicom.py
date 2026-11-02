"""A sonda do DICOM: ela é lida por quem vai abrir chamado com a TI.

O relatório dela não é registro técnico — é o que decide para quem se liga. Um
C-ECHO que falha e um C-GET que falha mandam pedir coisas DIFERENTES a pessoas
diferentes, e um relatório que não separa as duas custa uma semana de ida e
volta.

O que estes testes fixam:

* **os quatro degraus aparecem sempre**, mesmo os que não foram tentados —
  "não tentei" e "tentei e falhou" não podem sair iguais;
* **o veredito muda com o degrau que quebrou**, e nomeia o próximo passo;
* **sem configuração nada é tentado**, e o relatório diz QUAL variável falta,
  em vez de "configuração incompleta";
* **o arquivo que o C-GET trouxer é anunciado**: é dado de paciente fora do
  ARIA, e quem não sabe onde ele caiu não o apaga;
* **o relatório é gravado mesmo quando dá errado** — o console do ``runas``
  fecha, e o da rodada ruim é justamente o que se quer ler.

Rodar:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "tools"))

from isocentro.adaptadores.dicom import rede as dicom_rede  # noqa: E402
import sondar_dicom  # noqa: E402
from tests import scp_falso  # noqa: E402


class _SemConfig:
    """Apaga as quatro variáveis — guardando e devolvendo, nunca ``del``."""

    NOMES = ("ISOCENTRO_DICOM_SERVIDOR", "ISOCENTRO_DICOM_AE_REMOTO",
             "ISOCENTRO_DICOM_AE_LOCAL", "ISOCENTRO_DICOM_AE_DESTINO",
             "ISOCENTRO_DICOM_SERVIDOR", "ISOCENTRO_DICOM_AE_REMOTO",
             "ISOCENTRO_DICOM_AE_LOCAL",
             "ISOCENTRO_DICOM_AE_DESTINO")

    def __enter__(self):
        self._antes = {n: os.environ.get(n) for n in self.NOMES}
        for n in self.NOMES:
            os.environ.pop(n, None)
        return self

    def __exit__(self, *_):
        for n, v in self._antes.items():
            if v is None:
                os.environ.pop(n, None)
            else:
                os.environ[n] = v
        return False


class SemConfiguracao(unittest.TestCase):
    """O estado de hoje na clínica: nada apontado ainda."""

    def test_nomeia_a_variavel_que_falta(self):
        """"Configuração incompleta" manda a pessoa adivinhar o que pedir."""
        with _SemConfig():
            with tempfile.TemporaryDirectory() as pasta:
                alvo = Path(pasta) / "r.txt"
                sondar_dicom.main(["--uid", "1.2.3", "-o", str(alvo)])
                texto = alvo.read_text(encoding="utf-8")
        self.assertIn("ISOCENTRO_DICOM_SERVIDOR", texto)
        self.assertIn("Sondagem NÃO tentada", texto)

    def test_grava_o_relatorio_mesmo_sem_tentar_nada(self):
        """O console do ``runas`` fecha. Arquivo pedido é arquivo entregue,
        mesmo — ainda mais — quando deu errado."""
        with _SemConfig():
            with tempfile.TemporaryDirectory() as pasta:
                alvo = Path(pasta) / "r.txt"
                sondar_dicom.main(["--uid", "1.2.3", "-o", str(alvo)])
                self.assertTrue(alvo.exists())

    def test_o_veredito_entrega_o_comando_que_FUNCIONA_agora(self):
        """Diagnóstico sem saída é meia ajuda, e aqui custa uma ida.

        Em 04/09/2026 o usuário clicou no .bat: sem argumento, a ferramenta
        dizia "falta o ISOCENTRO_DICOM_SERVIDOR" e parava. Só que a varredura
        NÃO precisa de nada do que está faltando — é ela que descobre a porta,
        e responde mesmo sem o AE cadastrado. O comando pronto vai junto do
        diagnóstico.
        """
        with _SemConfig():
            with tempfile.TemporaryDirectory() as pasta:
                alvo = Path(pasta) / "r.txt"
                sondar_dicom.main(["--uid", "1.2.3", "-o", str(alvo)])
                texto = alvo.read_text(encoding="utf-8")
        self.assertIn("--varrer", texto)

    def test_o_veredito_nao_culpa_a_rede(self):
        """Sem configuração, dizer "o servidor não respondeu" mandaria abrir
        chamado para quem não tem nada a ver com isso."""
        with _SemConfig():
            with tempfile.TemporaryDirectory() as pasta:
                alvo = Path(pasta) / "r.txt"
                sondar_dicom.main(["--uid", "1.2.3", "-o", str(alvo)])
                texto = alvo.read_text(encoding="utf-8")
        self.assertIn("configuração está incompleta", texto)


class ContraUmServidorDeVerdade(unittest.TestCase):
    """Fala DICOM com um SCP que sobe em 127.0.0.1 — não com objeto falso."""

    def setUp(self):
        self.srv = scp_falso.Servidor()
        self.srv.__enter__()
        self.pasta = tempfile.mkdtemp()

    def tearDown(self):
        self.srv.__exit__(None, None, None)

    def _relatorio(self, *extra) -> str:
        alvo = Path(self.pasta) / "relatorio.txt"
        sondar_dicom.main(["--uid", scp_falso.UID, "--pasta", self.pasta,
                           "-o", str(alvo), *extra])
        return alvo.read_text(encoding="utf-8")

    def test_os_quatro_degraus_aparecem(self):
        """Inclusive o que não foi tentado: "não tentei" e "tentei e falhou"
        pedem coisas diferentes de quem lê."""
        texto = self._relatorio()
        for degrau in ("C-ECHO", "C-FIND", "C-GET", "C-MOVE"):
            self.assertIn(degrau, texto)

    def test_c_move_sem_destino_diz_que_nao_tentou(self):
        """Sem AE de destino ele não é tentado — e isso não é falha dele."""
        texto = self._relatorio()
        self.assertIn("sem ISOCENTRO_DICOM_AE_DESTINO", texto)

    def test_c_get_funcionando_vira_o_veredito_bom(self):
        """É a resposta que encolhe o pedido à TI para uma frase."""
        texto = self._relatorio()
        self.assertIn("C-GET FUNCIONA", texto)
        self.assertIn("precisa de porta ouvindo", texto)

    def test_o_arquivo_de_paciente_e_anunciado(self):
        """Dado clínico fora do ARIA numa pasta temporária que ninguém revisa.
        Quem não sabe onde ele caiu não o apaga."""
        texto = self._relatorio()
        self.assertIn("dado clínico fora do ARIA", texto)
        self.assertIn(self.pasta, texto)

    def test_uid_que_nao_existe_nao_vira_servidor_quebrado(self):
        """C-FIND com 0 achados é resposta legítima do servidor. Confundir isso
        com falha mandaria procurar defeito onde não há."""
        alvo = Path(self.pasta) / "r2.txt"
        sondar_dicom.main(["--uid", scp_falso.UID_AUSENTE,
                           "--pasta", self.pasta, "-o", str(alvo)])
        texto = alvo.read_text(encoding="utf-8")
        self.assertIn("não tem esse SOPInstanceUID", texto)
        self.assertNotIn("O primeiro degrau já falhou", texto)


class AVarreduraDePortas(unittest.TestCase):
    """Qual das oito portas do servidor é o daemon de CONSULTA.

    O `descobrir_dicom.ps1` respondeu metade no SRVARIADB em 04/09/2026: oito
    portas DICOM, todas do MESMO processo, e o nome do serviço não diz qual é
    qual. Ler mais arquivo não resolveria — a configuração dos serviços DICOM
    da Varian mora no banco do ARIA. Quem responde é perguntar às portas.
    """

    def setUp(self):
        self.srv = scp_falso.Servidor()
        self.srv.__enter__()
        self.porta = int(os.environ["ISOCENTRO_DICOM_SERVIDOR"].split(":")[1])

    def tearDown(self):
        self.srv.__exit__(None, None, None)

    def _varrer(self, portas) -> str:
        linhas = []
        sondar_dicom.varrer(linhas.append, "127.0.0.1", portas,
                            "ARIA_FALSO", "RADIOTERAFICHA")
        return "\n".join(linhas)

    def _varrer_porta_fechada(self) -> str:
        """Porta que recusa, sem pagar os 2 s que a recusa leva no Windows (ver
        ``scp_falso.conexao_que_falha``). A porta livre continua sendo pedida
        ao sistema: se o dublê um dia deixar de valer, o teste cai numa porta
        fechada de verdade — mais lento, mas sem mentir."""
        porta = scp_falso.porta_livre()
        with scp_falso.conexao_que_falha(ConnectionRefusedError(10061, "")):
            return self._varrer([porta])

    def test_acha_a_porta_que_aceita_Find(self):
        """É o contexto de Find que separa o daemon de consulta dos vizinhos —
        armazenamento, worklist e impressão moram no mesmo processo."""
        texto = self._varrer([self.porta])
        self.assertIn("ACEITOU Find", texto)
        self.assertIn(f"--servidor 127.0.0.1:{self.porta}", texto)

    def test_porta_fechada_nao_se_confunde_com_recusa(self):
        """"Não abriu" é firewall ou serviço parado; "abriu e recusou" quer
        dizer que se achou um serviço DICOM. Pedem coisas diferentes.

        A porta livre é pedida ao sistema, não é ``porta + 1``: na primeira
        versão a vizinha estava ocupada por outro programa da máquina, e o
        teste reprovou — de graça, porque foi assim que se descobriu que a
        ferramenta chamava QUALQUER porta aberta de "fala DICOM".
        """
        texto = self._varrer_porta_fechada()
        self.assertIn("fechada", texto)
        self.assertNotIn("ACEITOU Find", texto)

    def test_sem_nenhuma_aceitar_o_relatorio_da_as_TRES_leituras(self):
        """Lista vazia aqui tem três causas, e elas pedem coisas opostas: o AE
        ainda não cadastrado (só volta a responder depois do cadastro), o
        serviço de consulta noutra porta, ou a porta ser de outro programa. Um
        recado só para as três manda esperar quando era para procurar."""
        texto = self._varrer_porta_fechada()
        # Espaços normalizados antes de procurar: o recado é escrito em linhas
        # curtas para caber no console, e duas asserções reprovaram só porque a
        # frase quebra no meio ("ainda não / está cadastrado"). O teste é da
        # MENSAGEM, não da largura em que ela foi quebrada.
        corrido = " ".join(texto.split())
        self.assertIn("Nenhuma aceitou Find", corrido)
        self.assertIn("falta um AE Title", corrido)
        # E o recado passou a dizer COMO descobrir de quem é o AE errado, que
        # foi a lição da rodada contra o SRVARIADB: nove portas recusaram, e
        # "recusou" sozinho não dizia se o chamado era eu quem resolvia.
        self.assertIn("'called' é o do ARIA", corrido)
        self.assertIn("está noutra porta, ou parado", corrido)
        self.assertIn("a porta é de outro programa", corrido)

    def test_a_recusa_diz_de_QUEM_e_o_AE_errado(self):
        """"Recusou" não basta: são duas causas com providências opostas.

        Rodado contra o SRVARIADB em 04/09/2026, NOVE portas recusaram — e o
        relatório não dizia se era o AE do ARIA (que eu tinha chutado como
        `VMSDBD`, e se resolve trocando um parâmetro) ou o nosso (que só a
        Varian cadastra). Sem essa linha, "recusou em todas" mandaria abrir um
        chamado que talvez nem fosse preciso.

        O servidor precisa EXIGIR o AE chamado para a recusa acontecer: por
        padrão o pynetdicom aceita qualquer um, e o teste passaria sem nunca
        ter havido recusa nenhuma.
        """
        self.srv.__exit__(None, None, None)
        self.srv = scp_falso.Servidor(exige_ae=True)
        self.srv.__enter__()
        porta = int(os.environ["ISOCENTRO_DICOM_SERVIDOR"].split(":")[1])
        linhas = []
        sondar_dicom.varrer(linhas.append, "127.0.0.1", [porta],
                            "NAO_EXISTE", "RADIOTERAFICHA")
        corrido = " ".join(" ".join(linhas).split())
        self.assertIn("Called AE title not recognised", corrido)
        self.assertIn("--ae-remoto", corrido)

    def test_varios_AE_numa_rodada_so(self):
        """Nove portas recusando o AE chamado, um nome por rodada, seriam nove
        idas ao servidor.

        Medido em 04/09/2026: as regras de firewall do SRVARIADB nomeiam o
        serviço de cada porta ("Varian DICOM Service ARIA" na 51404), e daí
        saiu uma lista de nomes prováveis. Testá-los de uma vez é o que
        transforma a lista em resposta.
        """
        self.srv.__exit__(None, None, None)
        self.srv = scp_falso.Servidor(exige_ae=True)
        self.srv.__enter__()
        porta = int(os.environ["ISOCENTRO_DICOM_SERVIDOR"].split(":")[1])
        linhas = []
        sondar_dicom.varrer(linhas.append, "127.0.0.1", [porta],
                            ["NAO_EXISTE", "ARIA_FALSO"], "RADIOTERAFICHA")
        corrido = " ".join(" ".join(linhas).split())
        # Achou com o SEGUNDO nome, e o relatório diz com qual.
        self.assertIn("[ARIA_FALSO] ACEITOU Find", corrido)
        self.assertIn("--ae-remoto ARIA_FALSO", corrido)

    def test_nao_pede_dado_nenhum(self):
        """Ela roda contra um servidor clínico: abre e fecha associação, e o
        relatório diz isso a quem for autorizar a execução."""
        texto = self._varrer([self.porta])
        self.assertIn("nenhum dado é pedido nem trazido", texto)


class OsValoresDaLinhaDeComando(unittest.TestCase):
    """Testar o que a TI disse sem gravar nada em estação nenhuma."""

    def test_valem_so_para_esta_execucao(self):
        with _SemConfig():
            sondar_dicom._aplicar_argumentos(
                type("A", (), {"servidor": "SRV:51402",
                               "ae_remoto": "VMSDBD", "ae_local": "RTF",
                               "ae_destino": ""})())
            self.assertEqual(dicom_rede.servidor(), ("SRV", 51402))
            self.assertEqual(dicom_rede.ae_remoto(), "VMSDBD")
        # Fora do bloco, o ambiente voltou ao que era.
        self.assertNotEqual(dicom_rede.servidor(), ("SRV", 51402))


if __name__ == "__main__":
    unittest.main()
