"""Round-trip do registro do paciente e do arquivamento em .zip.

Cobre registro_json (salvar/carregar, solto e de dentro do zip, prever_versao,
_nomes_imagens) e empacotar (merge, preservação, integridade).

Rodar:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from isocentro.dados import empacotar  # noqa: E402
from isocentro.dados import indice  # noqa: E402
from isocentro.dados import registro_json as rj  # noqa: E402


def _arquivar(pasta, info, dados):
    """Replica o passo de arquivamento do gui: zipa os soltos e os apaga."""
    soltos = [p for p in ([info.get("json_path")] + list(info.get("arquivos") or []))
              if p and os.path.exists(p)]
    if not soltos:
        return None
    destino = os.path.join(pasta, rj.nome_zip(dados))
    empacotar.atualizar(destino, soltos)
    assert rj.ler_registro_do_zip(Path(destino)) is not None
    for p in soltos:
        os.remove(p)
    return destino


class TestNomeZip(unittest.TestCase):
    def test_nome_com_registro(self):
        self.assertEqual(rj.nome_zip({"pac_nome": "Jose Silva", "pac_registro": "123X"}),
                         "ARQUIVOS_JOSE SILVA_123X.zip")

    def test_nome_sem_registro(self):
        self.assertEqual(rj.nome_zip({"pac_nome": "Jose Silva"}),
                         "ARQUIVOS_JOSE SILVA.zip")


class TestEmpacotar(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def _f(self, nome, conteudo):
        p = os.path.join(self.d, nome)
        Path(p).write_bytes(conteudo)
        return p

    def test_cria_e_lista(self):
        z = os.path.join(self.d, "x.zip")
        empacotar.atualizar(z, [self._f("a.txt", b"A"), self._f("b.txt", b"B")])
        self.assertEqual(sorted(zipfile.ZipFile(z).namelist()), ["a.txt", "b.txt"])

    def test_merge_preserva_e_substitui(self):
        z = os.path.join(self.d, "x.zip")
        empacotar.atualizar(z, [self._f("a.txt", b"A"), self._f("b.txt", b"B")])
        empacotar.atualizar(z, [self._f("a.txt", b"A2"), self._f("c.txt", b"C")])
        zf = zipfile.ZipFile(z)
        self.assertEqual(sorted(zf.namelist()), ["a.txt", "b.txt", "c.txt"])
        self.assertEqual(zf.read("a.txt"), b"A2")   # substituído
        self.assertEqual(zf.read("b.txt"), b"B")    # preservado

    def test_ignora_ausentes(self):
        z = os.path.join(self.d, "x.zip")
        empacotar.atualizar(z, [self._f("a.txt", b"A"), os.path.join(self.d, "sumiu.txt")])
        self.assertEqual(zipfile.ZipFile(z).namelist(), ["a.txt"])

    def test_vazio_sem_zip_levanta(self):
        with self.assertRaises(ValueError):
            empacotar.atualizar(os.path.join(self.d, "y.zip"), [])

    def test_nao_deixa_tmp(self):
        z = os.path.join(self.d, "x.zip")
        empacotar.atualizar(z, [self._f("a.txt", b"A")])
        self.assertFalse(os.path.exists(z + ".tmp"))


class TestCicloRegistro(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.dados = {"pac_nome": "Fulano De Tal", "pac_registro": "999"}

    def _salvar(self, tecnica, idx):
        return rj.salvar_versao(
            self.d, self.dados, {"maquina": "M", "tecnica": tecnica}, {"idx_axial": idx},
            imagem_png=f"CORTES{idx}".encode(), dvh_png=f"DVH{idx}".encode())

    def test_ciclo_completo_le_do_zip(self):
        # v1 → arquiva → só o zip sobra
        info1 = self._salvar("IMRT", 10)
        self.assertTrue(info1["nova"])
        z = _arquivar(self.d, info1, self.dados)
        self.assertEqual(sorted(os.listdir(self.d)), [os.path.basename(z)])

        # bootstrap e prever_versao leem o histórico do zip
        reg = rj.carregar_registro_pasta(self.d, self.dados)
        self.assertEqual([v["versao"] for v in reg["versoes"]], [1])
        self.assertEqual(rj.prever_versao(self.d, self.dados,
                                          {"maquina": "M", "tecnica": "VMAT"},
                                          {"idx_axial": 99}), (2, True))

        # v2 (conteúdo diferente) → lê v1 do zip, acrescenta, arquiva
        info2 = self._salvar("VMAT", 99)
        self.assertEqual(info2["versao"], 2)
        z = _arquivar(self.d, info2, self.dados)
        self.assertEqual(sorted(os.listdir(self.d)), [os.path.basename(z)])

        # o zip guarda JSON com v1+v2 e os PNGs de ambas as versões
        with zipfile.ZipFile(z) as zf:
            nomes = zf.namelist()
            jn = next(n for n in nomes if n.endswith(".json"))
            import json
            regz = json.loads(zf.read(jn))
            self.assertEqual([v["versao"] for v in regz["versoes"]], [1, 2])
            self.assertTrue(any("v1" in n for n in nomes))
            self.assertTrue(any("v2" in n for n in nomes))

    def test_registro_na_pasta_json_solto(self):
        # JSON mestre solto → detecta a ficha anterior pelo conteúdo (sem saber
        # nome/registro de antemão).
        self._salvar("IMRT", 10)
        reg = rj.registro_na_pasta(self.d)
        self.assertIsNotNone(reg)
        self.assertEqual([v["versao"] for v in reg["versoes"]], [1])

    def test_registro_na_pasta_dentro_do_zip(self):
        # Só o zip do paciente sobra (arquivado) → ainda detecta.
        info = self._salvar("IMRT", 10)
        _arquivar(self.d, info, self.dados)
        self.assertFalse(any(n.startswith("FICHA_") for n in os.listdir(self.d)))
        reg = rj.registro_na_pasta(self.d)
        self.assertIsNotNone(reg)
        self.assertEqual([v["versao"] for v in reg["versoes"]], [1])

    def test_registro_na_pasta_sem_ficha(self):
        # Pasta só com DICOM/arquivos avulsos → nada a reabrir.
        Path(os.path.join(self.d, "CT.001.dcm")).write_bytes(b"nao e ficha")
        self.assertIsNone(rj.registro_na_pasta(self.d))

    def test_registro_na_pasta_json_corrompido_e_ignorado(self):
        # FICHA_*.json ilegível não deve derrubar a detecção nem contar como ficha.
        Path(os.path.join(self.d, "FICHA_LIXO_1.json")).write_text("{ nao json",
                                                                   encoding="utf-8")
        self.assertIsNone(rj.registro_na_pasta(self.d))

    def test_drrs_de_setup_gravadas_e_arquivadas(self):
        # DRRs do 600CD (N portais) entram na versão e vão para o zip (Histórico).
        info = rj.salvar_versao(
            self.d, self.dados, {"maquina": "600CD"}, {},
            imagem_png=None, dvh_png=None,
            drrs=[b"P0PNG", b"MAMAPNG", b"FSCPNG"],
            drrs_titulos=["PORTAL 0", "PORTAL MAMA", "PORTAL FSC 3"])
        self.assertTrue(info["nova"])
        base = [os.path.basename(a) for a in info["arquivos"]]
        self.assertEqual(sum(n.startswith("DRR_p") for n in base), 3, base)
        reg = rj.carregar_registro_pasta(self.d, self.dados)
        v = reg["versoes"][-1]
        self.assertEqual(len(v.get("drrs") or []), 3)
        self.assertEqual(v.get("drrs_titulos"),
                         ["PORTAL 0", "PORTAL MAMA", "PORTAL FSC 3"])
        # os nomes das DRRs entram na lista de arquivos a arquivar
        nomes = rj._nomes_imagens(reg)
        for nm in v["drrs"]:
            self.assertIn(nm, nomes)
        z = _arquivar(self.d, info, self.dados)
        with zipfile.ZipFile(z) as zf:
            self.assertEqual(sum("DRR_p" in n for n in zf.namelist()), 3)

    def test_rtplans_gravados_e_arquivados(self):
        # RTPLAN(s) crus vão para a versão e para o zip (tratamento manual),
        # byte-idênticos ao original.
        raws = [b"DICOM-RTPLAN-1", b"DICOM-RTPLAN-2"]
        info = rj.salvar_versao(self.d, self.dados, {"maquina": "600CD"}, {},
                                imagem_png=None, dvh_png=None, rtplans=raws)
        base = [os.path.basename(a) for a in info["arquivos"]]
        self.assertEqual(sum(n.startswith("RTPLAN_p") for n in base), 2, base)
        reg = rj.carregar_registro_pasta(self.d, self.dados)
        v = reg["versoes"][-1]
        self.assertEqual(len(v.get("rtplans") or []), 2)
        self.assertEqual(Path(self.d, v["rtplans"][0]).read_bytes(), raws[0])
        self.assertTrue(all(n in rj._nomes_imagens(reg) for n in v["rtplans"]))
        z = _arquivar(self.d, info, self.dados)
        with zipfile.ZipFile(z) as zf:
            self.assertEqual(sum("RTPLAN_p" in n for n in zf.namelist()), 2)

    def test_rtplans_none_sao_pulados(self):
        # Plano sem RP (reaberto) não gera arquivo nem entrada.
        rj.salvar_versao(self.d, self.dados, {"maquina": "M"}, {},
                         imagem_png=b"C", dvh_png=None, rtplans=[None, None])
        reg = rj.carregar_registro_pasta(self.d, self.dados)
        self.assertIsNone(reg["versoes"][-1].get("rtplans"))

    def test_nao_duplica_versao_identica(self):
        info1 = self._salvar("IMRT", 10)
        _arquivar(self.d, info1, self.dados)
        # mesma coisa de novo → nova=False (lido do zip)
        info2 = rj.salvar_versao(self.d, self.dados, {"maquina": "M", "tecnica": "IMRT"},
                                 {"idx_axial": 10}, imagem_png=b"X", dvh_png=b"Y")
        self.assertFalse(info2["nova"])

    def test_extrair_zip_recupera_pngs(self):
        info = rj.salvar_versao(self.d, self.dados, {"maquina": "M"}, {},
                                imagem_png=b"CORTESv1", dvh_png=b"DVHv1")
        _arquivar(self.d, info, self.dados)
        destino = tempfile.mkdtemp()
        self.assertIsNotNone(rj.extrair_zip(self.d, self.dados, destino))
        extraidos = os.listdir(destino)
        self.assertTrue(any(n.startswith("CORTES_") for n in extraidos))
        self.assertTrue(any(n.startswith("FICHA_") and n.endswith(".json")
                            for n in extraidos))


class TestReconstruirPrune(unittest.TestCase):
    """reconstruir remove fantasmas sob a raiz, preserva o resto."""

    def setUp(self):
        self._orig = indice.REGISTRO_PATH
        self._d = tempfile.mkdtemp()
        indice.REGISTRO_PATH = Path(self._d) / "idx.json"
        self.raiz = tempfile.mkdtemp()

    def tearDown(self):
        indice.REGISTRO_PATH = self._orig

    def _cria(self, pasta_base, nome, reg):
        pasta = os.path.join(pasta_base, nome)
        os.makedirs(pasta)
        dados = {"pac_nome": nome, "pac_registro": reg}
        info = rj.salvar_versao(pasta, dados, {"maquina": "M"}, {},
                                imagem_png=b"C", dvh_png=b"D")
        _arquivar(pasta, info, dados)
        return pasta

    def _regs(self):
        return sorted(l["registro"] for l in indice.buscar("", "tudo"))

    def test_remove_fantasma_e_preserva_fora_da_raiz(self):
        import shutil
        self._cria(self.raiz, "ANA", "111")
        pb = self._cria(self.raiz, "BRUNO", "222")
        # paciente fora da raiz
        fora = tempfile.mkdtemp()
        self._cria(fora, "CARLOS", "333")
        indice.reconstruir(fora)          # indexa C
        indice.reconstruir(self.raiz)     # indexa A e B
        self.assertEqual(self._regs(), ["111", "222", "333"])

        shutil.rmtree(pb)                 # B some do disco
        indice.reconstruir(self.raiz)     # deve remover só o fantasma B
        self.assertEqual(self._regs(), ["111", "333"])

    def test_limpar_esvazia_o_indice_sem_apagar_arquivos(self):
        pa = self._cria(self.raiz, "ANA", "111")
        indice.reconstruir(self.raiz)
        self.assertEqual(self._regs(), ["111"])
        self.assertEqual(indice.limpar(), 1)   # devolve quantos havia
        self.assertEqual(self._regs(), [])     # lista vazia
        self.assertTrue(os.path.isdir(pa))     # arquivos do paciente ficam
        self.assertEqual(indice.reconstruir(self.raiz), 1)   # dá p/ trazer de volta
        self.assertEqual(self._regs(), ["111"])


class TestNomesImagens(unittest.TestCase):
    def test_coleta_sem_repetir_preservando_ordem(self):
        registro = {"versoes": [
            {"imagem": "C1.png", "dvh": "D1.png",
             "imagens": ["Cp1.png", "Cp2.png"], "dvhs": ["Dp1.png", ""]},
            {"imagem": "C1.png", "dvh": "D2.png"},   # C1 repetido
        ]}
        self.assertEqual(
            rj._nomes_imagens(registro),
            ["C1.png", "D1.png", "Cp1.png", "Cp2.png", "Dp1.png", "D2.png"])


if __name__ == "__main__":
    unittest.main()
