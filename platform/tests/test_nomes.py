"""Uma grafia só para o nome do paciente, em toda porta de entrada e saída.

Em 25/08/2026 a lista "Suas últimas fichas" mostrava, nas mesmas dez linhas,
"GEUCIMAR MARIA NUNES COSTA" e "Lie Yamanaka": cada TPS, o data warehouse e os
relatórios exportados grafam do seu jeito, e a grafia que aparecia era a da
porta por onde o nome tinha entrado. Numa lista, isso se lê como dado de
origens diferentes — e a origem é justamente o que não deve transparecer para
quem confere a ficha antes de o paciente subir na mesa.

O que se testa aqui é que a regra vale nas DUAS pontas: o nome nasce canônico
(DICOM, banco, CSV) e o que já está gravado cru é uniformizado ao ser lido —
sem isso, as fichas de ontem continuariam destoando na tela de hoje.

Rodar:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import datetime
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pydicom  # noqa: E402
from pydicom.dataset import Dataset  # noqa: E402

from isocentro.banco import capa_dados  # noqa: E402
from isocentro.papel import capa_pdf  # noqa: E402
from isocentro.dados import equipe  # noqa: E402
from isocentro.dicom import dicom_rt  # noqa: E402
from isocentro.dados import historico  # noqa: E402
from isocentro.dados import indice  # noqa: E402
from isocentro.dados import nomes  # noqa: E402


class TestGrafia(unittest.TestCase):
    """A regra em si. Os casos são nomes reais do cadastro do serviço."""

    def test_caixa_alta_vira_nome_proprio(self):
        self.assertEqual(nomes.como_nome_proprio("SANDRA CABRAL DA LUZ"),
                         "Sandra Cabral da Luz")

    def test_conectivo_so_e_rebaixado_no_meio(self):
        # "Da Silva" abrindo o nome é o sobrenome de alguém, não conectivo.
        self.assertEqual(nomes.como_nome_proprio("DA SILVA JUNIOR"),
                         "Da Silva Junior")

    def test_particula_colada_capitaliza_dos_dois_lados(self):
        self.assertEqual(nomes.como_nome_proprio("MARIA D'ALMEIDA SILVA-NETO"),
                         "Maria D'Almeida Silva-Neto")

    def test_de_pessoa_desinverte_antes_de_grafar(self):
        # O banco e os relatórios exportam "Família, Nome" E em caixa alta; as
        # duas correções eram chamadas em par em cada fonte, e era o tipo de par
        # que se esquece de repetir na fonte seguinte.
        self.assertEqual(nomes.de_pessoa("LUZ, SANDRA CABRAL DA"),
                         "Sandra Cabral da Luz")

    def test_vazio_continua_vazio(self):
        # Campo sem fonte nasce vazio — nunca com um nome inventado.
        self.assertEqual(nomes.de_pessoa(""), "")
        self.assertEqual(nomes.de_pessoa(None), "")

    def test_capa_dados_ainda_exporta_os_nomes_antigos(self):
        """Meio repositório chama por ``capa_dados.`` — mudar de casa não pode
        quebrar quem chama pelo endereço velho."""
        self.assertIs(capa_dados.como_nome_proprio, nomes.como_nome_proprio)
        self.assertIs(capa_dados.desinverter, nomes.desinverter)
        self.assertIs(capa_dados.de_pessoa, nomes.de_pessoa)


class TestEntradaDicom(unittest.TestCase):
    """O DICOM é a porta por onde entra o nome da FICHA."""

    @staticmethod
    def _ds(nome_dicom: str) -> Dataset:
        ds = Dataset()
        ds.PatientName = pydicom.valuerep.PersonName(nome_dicom)
        ds.PatientID = "9000022BET"
        ds.PatientBirthDate = "19650101"
        ds.PatientSex = "F"
        return ds

    def test_nome_do_tps_em_caixa_alta_chega_grafado(self):
        pac = dicom_rt.dados_paciente(self._ds("COSTA^GEUCIMAR MARIA NUNES"))
        self.assertEqual(pac["nome"], "Geucimar Maria Nunes Costa")

    def test_nome_ja_grafado_atravessa_intacto(self):
        pac = dicom_rt.dados_paciente(self._ds("Yamanaka^Lie"))
        self.assertEqual(pac["nome"], "Lie Yamanaka")

    def test_registro_nao_e_nome_de_gente(self):
        """O ID do paciente NÃO passa pela regra: "9000022BET" viraria
        "9000022bet" e deixaria de casar com o registro impresso."""
        pac = dicom_rt.dados_paciente(self._ds("COSTA^GEUCIMAR"))
        self.assertEqual(pac["registro"], "9000022BET")

    def test_casamento_com_a_equipe_nao_depende_da_grafia(self):
        """A lista canônica é comparada sem acento e em caixa única — mudar a
        grafia exibida não pode fazer o físico do plano sumir da ficha."""
        alvo = equipe.FISICOS[0]
        self.assertEqual(dicom_rt._casar_nome(alvo.upper(), equipe.FISICOS),
                         alvo)


class TestSaidaImpressa(unittest.TestCase):
    """Capa e ficha andam GRAMPEADAS: até 25/08/2026 a mesma pessoa saía
    "SANDRA CABRAL DA LUZ" numa e "Sandra Cabral da Luz" na outra."""

    def test_capa_nao_sai_mais_em_caixa_alta(self):
        res = capa_dados.Resultado(
            cadastro=capa_dados.Cadastro(registro="1", nome="SANDRA CABRAL DA LUZ",
                                         medico="MEDICO EXEMPLO"))
        capa = capa_pdf.de_resultado(res)
        self.assertEqual(capa.nome, "Sandra Cabral da Luz")
        self.assertEqual(capa.medico, "Medico Exemplo")

    def test_espelho_gravado_antes_da_mudanca_tambem_e_grafado(self):
        """O espelho guarda o que o banco respondeu NAQUELE dia — os arquivos
        anteriores a 25/08/2026 têm o nome em caixa alta, e a capa montada a
        partir deles sairia assim se a formatação só existisse na fonte.

        O caso invertido ("LIMA, BEATRIZ") entra junto porque espelho ainda
        mais antigo pode tê-lo guardado como o banco o entrega."""
        for cru in ("BEATRIZ ALVES DE LIMA", "LIMA, BEATRIZ ALVES DE"):
            res = capa_dados.Resultado(
                cadastro=capa_dados.Cadastro(registro="1", nome=cru))
            self.assertEqual(capa_pdf.de_resultado(res).nome,
                             "Beatriz Alves de Lima", cru)


class TestSaidaListas(unittest.TestCase):
    """As listas do app leem o que JÁ ESTÁ gravado — é nelas que a mistura
    aparecia."""

    def setUp(self):
        self.pasta = tempfile.mkdtemp(prefix="nomes_teste_")
        self.addCleanup(shutil.rmtree, self.pasta, True)
        antes = os.environ.get("ISOCENTRO_LOG_DIR")
        os.environ["ISOCENTRO_LOG_DIR"] = self.pasta
        # Devolver, não apagar: o ``pop`` desligava o desvio da suíte
        # (``limpeza_de_tela``) para todos os testes seguintes.
        if antes is None:
            self.addCleanup(os.environ.pop, "ISOCENTRO_LOG_DIR", None)
        else:
            self.addCleanup(os.environ.__setitem__, "ISOCENTRO_LOG_DIR", antes)
        historico.definir_usuario(None)
        self.addCleanup(historico.definir_usuario, None)
        self._indice_original = indice.REGISTRO_PATH
        indice.REGISTRO_PATH = Path(self.pasta) / "registro_fichas.json"
        self.addCleanup(setattr, indice, "REGISTRO_PATH", self._indice_original)

    def test_ficha_gerada_ontem_nao_destoa_na_lista_de_hoje(self):
        agora = f"{datetime.date.today().isoformat()}T10:00:00"
        linha = {"em": agora, "usuario": "ana", "evento": "ficha_gerada",
                 "detalhes": {"paciente": "GEUCIMAR MARIA NUNES COSTA",
                              "registro": "9000022BET"}}
        with open(historico.caminho_log(), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(linha, ensure_ascii=False) + "\n")
        recentes = historico.fichas_do_usuario("ana")["recentes"]
        self.assertEqual([r["paciente"] for r in recentes],
                         ["Geucimar Maria Nunes Costa"])

    def test_o_evento_gravado_continua_fiel_ao_que_a_ficha_tinha(self):
        """O log é registro de AUDITORIA: quem uniformiza é quem monta a lista,
        não quem grava. Reescrever o evento apagaria o que a ficha dizia."""
        historico.registrar("ficha_gerada", usuario="ana",
                            detalhes={"paciente": "GEUCIMAR MARIA NUNES COSTA",
                                      "registro": "1"})
        self.assertEqual(historico.ler()[0]["detalhes"]["paciente"],
                         "GEUCIMAR MARIA NUNES COSTA")

    def _indice_com(self, nome: str, medico: str = "") -> None:
        indice.REGISTRO_PATH.write_text(json.dumps({
            "schema": "isocentro/registro-fichas",
            "fichas": [{"registro": "1", "versao": 1, "nome": nome,
                        "medico": medico, "gerado_em": "2026-08-20T10:00:00"}],
        }, ensure_ascii=False), encoding="utf-8")

    def test_historico_grafa_o_indice_ja_gravado(self):
        self._indice_com("SANDRA CABRAL DA LUZ", "MEDICO EXEMPLO")
        linha = indice.buscar()[0]
        self.assertEqual(linha["nome"], "Sandra Cabral da Luz")
        self.assertEqual(linha["medico"], "Medico Exemplo")

    def test_resumo_da_fichinha_grafa_o_indice_ja_gravado(self):
        self._indice_com("SANDRA CABRAL DA LUZ")
        ultima = indice.resumo_por_registro({"1"})["1"]["ultima"]
        self.assertEqual(ultima["nome"], "Sandra Cabral da Luz")

    def test_a_busca_do_historico_nao_depende_da_grafia(self):
        """Quem digita "sandra" tem de achar quem foi indexado em caixa alta —
        a formatação é da EXIBIÇÃO, e o filtro roda sobre o dado cru."""
        self._indice_com("SANDRA CABRAL DA LUZ")
        self.assertEqual(len(indice.buscar("sandra", "nome")), 1)
        self.assertEqual(len(indice.buscar("SANDRA", "nome")), 1)

    def test_exibir_nao_reescreve_o_indice_em_disco(self):
        self._indice_com("SANDRA CABRAL DA LUZ")
        indice.buscar()
        gravado = json.loads(indice.REGISTRO_PATH.read_text(encoding="utf-8"))
        self.assertEqual(gravado["fichas"][0]["nome"], "SANDRA CABRAL DA LUZ")


if __name__ == "__main__":
    unittest.main()
