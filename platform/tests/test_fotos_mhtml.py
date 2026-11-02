"""Foto do paciente vinda do relatório MHTML.

O relatório de fotos passou de `.xlsx` (imagem ancorada numa linha da planilha)
para `.mhtml` (MIME multipart, uma parte por imagem, referenciada por
``Content-ID``). São ~190 MB e ~4 700 pacientes: ler o arquivo inteiro para
pegar UMA foto despejaria o relatório na memória a cada capa.

O que estes testes fixam é o que erra silenciosamente — foto associada ao
paciente errado é o pior desfecho possível num documento de identificação.

Rodar:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import base64
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from isocentro.banco import capa_dados  # noqa: E402

_LIMITE = "------=_NextPart_01C35DB7.4B204430"

# JPEG mínimo de verdade: o começo importa, porque a capa checa a assinatura.
_JPEG_A = b"\xff\xd8\xff\xe0" + b"FOTO-A" * 20
_JPEG_B = b"\xff\xd8\xff\xe0" + b"FOTO-B" * 20
_PNG_LOGO = b"\x89PNG\r\n\x1a\n" + b"LOGO" * 10


def _parte(content_id: str, tipo: str, corpo: bytes) -> str:
    b64 = base64.b64encode(corpo).decode("ascii")
    linhas = [b64[i:i + 76] for i in range(0, len(b64), 76)]
    return (f"{_LIMITE}\r\n"
            f"Content-ID: <{content_id}>\r\n"
            f"Content-Type: {tipo}\r\n"
            f"Content-Transfer-Encoding: base64\r\n"
            "\r\n" + "\r\n".join(linhas) + "\r\n")


def _mhtml(linhas_tabela: str, cabecalho_logo: bool = True) -> bytes:
    """Monta um MHTML no mesmo formato que o SSRS escreve.

    Tags em MAIÚSCULAS de propósito: é assim que o relatório real vem, e um
    regex em minúsculas não casaria nada.
    """
    logo = ('<TR><TD><IMG SRC="cid:LOGO-1"/></TD>'
            "<TD>Pacientes</TD></TR>") if cabecalho_logo else ""
    html = ("<HTML><BODY><TABLE>"
            + logo
            + "<TR><TD>Foto</TD><TD>ID do Paciente</TD>"
              "<TD>Nome do Paciente</TD></TR>"
            + linhas_tabela
            + "</TABLE></BODY></HTML>")
    partes = [
        "MIME-Version: 1.0\r\n"
        f'Content-Type: multipart/related;\r\n\tboundary="{_LIMITE[6:]}"\r\n'
        "\r\n",
        _parte("Capa_Todos_Foto_ID_Nome", 'text/html;\r\n\tcharset="utf-8"',
               html.encode("utf-8")),
    ]
    if cabecalho_logo:
        partes.append(_parte("LOGO-1", "image/png", _PNG_LOGO))
    partes.append(_parte("FOTO-A", "image/jpeg", _JPEG_A))
    partes.append(_parte("FOTO-B", "image/jpeg", _JPEG_B))
    partes.append(f"{_LIMITE}--\r\n")
    return "".join(partes).encode("utf-8")


def _linha(cid: str, ident: str, nome: str) -> str:
    return (f'<TR><TD><IMG SRC="cid:{cid}"/></TD>'
            f"<TD>{ident}</TD><TD>{nome}</TD></TR>")


class TestFotoMHTML(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="fotos_mhtml_")
        # Restaura pela VARIÁVEL DE AMBIENTE, não por ``definir_pasta_dados``:
        # devolver o valor lido congela a pasta que estava valendo e ela passa a
        # mandar no resto do processo. Rodando este arquivo antes de
        # ``test_capa``, aquele quebrava em 16 casos.
        self._env = os.environ.get(capa_dados.PASTA_ENV)
        os.environ[capa_dados.PASTA_ENV] = self.dir
        capa_dados.definir_pasta_dados(self.dir)
        capa_dados._indice_fotos.clear()

    def tearDown(self):
        if self._env is None:
            os.environ.pop(capa_dados.PASTA_ENV, None)
        else:
            os.environ[capa_dados.PASTA_ENV] = self._env
        capa_dados.definir_pasta_dados("")
        capa_dados._indice_fotos.clear()

    def _escrever(self, conteudo: bytes) -> None:
        with open(os.path.join(self.dir, capa_dados.ARQ_FOTOS), "wb") as fh:
            fh.write(conteudo)

    def _padrao(self) -> None:
        self._escrever(_mhtml(
            _linha("FOTO-A", "9000009CEL", "Amostra, Joana Ramos da")
            + _linha("FOTO-B", "9000008CEL", "Amostro, Roberto")))

    def test_acha_pelo_id(self):
        self._padrao()
        self.assertEqual(capa_dados.foto_do_paciente("9000009CEL"), _JPEG_A)
        self.assertEqual(capa_dados.foto_do_paciente("9000008CEL"), _JPEG_B)

    def test_id_com_traco_ou_espaco_casa(self):
        """O mesmo registro aparece grafado de vários jeitos conforme quem
        digitou; a comparação não pode depender disso."""
        self._padrao()
        self.assertEqual(capa_dados.foto_do_paciente(" 9000009-cel "), _JPEG_A)

    def test_acha_pelo_nome_desinvertido(self):
        """O relatório escreve "Sobrenome, Nome"; o resto do app fala na ordem
        direta — sem desinverter, nenhum nome casaria."""
        self._padrao()
        self.assertEqual(
            capa_dados.foto_do_paciente("", "Joana Ramos da Amostra"),
            _JPEG_A)

    def test_o_id_manda_no_nome(self):
        """Homônimo com a foto errada é pior que capa sem foto."""
        self._padrao()
        self.assertEqual(
            capa_dados.foto_do_paciente("9000008CEL", "Joana Ramos da Amostra"),
            _JPEG_B)

    def test_paciente_ausente_nao_devolve_foto_de_outro(self):
        self._padrao()
        self.assertIsNone(capa_dados.foto_do_paciente("9000026XXX"))
        self.assertIsNone(capa_dados.foto_do_paciente("", "Fulano De Tal"))

    def test_o_logo_do_cabecalho_nao_vira_paciente(self):
        """A 1ª imagem do arquivo é o logo do relatório, não uma foto."""
        self._padrao()
        indice = capa_dados._indice_de_fotos(
            capa_dados._arquivo(capa_dados.ARQ_FOTOS))
        self.assertEqual(len(indice["id"]), 2)
        self.assertNotIn("LOGO-1", indice["id"].values())

    def test_cid_com_quebra_de_linha(self):
        """No relatório real parte dos ``cid`` vem com ``\\n`` no fim — sem o
        strip, esses pacientes ficavam sem foto e ninguém sabia por quê."""
        self._escrever(_mhtml(
            '<TR><TD><IMG SRC="cid:FOTO-A\n\n"/></TD>'
            "<TD>9000009CEL</TD><TD>Amostra, Joana</TD></TR>"))
        self.assertEqual(capa_dados.foto_do_paciente("9000009CEL"), _JPEG_A)

    def test_sem_registro_nem_nome_nao_procura(self):
        self._padrao()
        self.assertIsNone(capa_dados.foto_do_paciente("", ""))

    def test_relatorio_ausente(self):
        self.assertIsNone(capa_dados.foto_do_paciente("9000009CEL"))

    def test_arquivo_corrompido_nao_derruba_a_capa(self):
        """Capa sem foto ainda é uma capa; capa que não abre, não."""
        self._escrever(b"isto nao e um MHTML")
        self.assertIsNone(capa_dados.foto_do_paciente("9000009CEL"))

    def test_relatorio_novo_invalida_o_cache(self):
        """Trocar o arquivo na pasta tem de valer sem reiniciar o programa —
        senão a estação serve a foto do relatório da semana passada."""
        self._padrao()
        self.assertEqual(capa_dados.foto_do_paciente("9000009CEL"), _JPEG_A)
        # Mesmo paciente, agora apontando para a outra imagem.
        self._escrever(_mhtml(
            _linha("FOTO-B", "9000009CEL", "Amostra, Joana Ramos da")))
        os.utime(os.path.join(self.dir, capa_dados.ARQ_FOTOS), (0, 0))
        self.assertEqual(capa_dados.foto_do_paciente("9000009CEL"), _JPEG_B)

    def test_o_relatorio_entra_na_conferencia_de_presenca(self):
        self._padrao()
        self.assertIn(capa_dados.ARQ_FOTOS, capa_dados.relatorios_presentes())


class TestNomesDosRelatorios(unittest.TestCase):
    """Os três arquivos que a capa lê — nomes exportados pelo Reporting."""

    def test_sao_os_tres_do_servico(self):
        self.assertEqual(capa_dados.ARQ_CADASTRO,
                         "Capa_de_Tratamento_Periodo.csv")
        self.assertEqual(capa_dados.ARQ_PRESCRICOES,
                         "Capa_Prescrições por Período.csv")
        self.assertEqual(capa_dados.ARQ_FOTOS,
                         "Capa_Todos_Foto_ID_Nome.mhtml")


if __name__ == "__main__":
    unittest.main()
