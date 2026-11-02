"""O esquema v1 do JSON ESAPI e a validação dele (`isocentro/adaptadores/esapi_json/`, R-76).

O que estes testes guardam é o que, quebrado, faz um resultado do Eclipse
valer como evidência sem merecer: esquema que mudou de um lado só entrando
calado, hash malformado aceito, resultado do plano antigo valendo para o novo,
e script fora do inventário ou não validado contando como conferido.

O inventário real é da R-61 e não existe aqui: o padrão dos testes é o
inventário VAZIO. Onde um teste precisa de uma linha (a não validada, ou o
caminho inteiro até o resultado), ela é de um script fictício, ``teste.ficticio``,
com o hash de bytes inventados — nenhum script do ``scriptsvarian`` aparece.
"""
from __future__ import annotations

import ast
import hashlib
import json
import unittest
from pathlib import Path

from isocentro.adaptadores.esapi_json import esquema, validacao
from isocentro.adaptadores.esapi_json.esquema import (
    VERSAO_ESQUEMA, DocumentoInvalido, ler)
from isocentro.adaptadores.esapi_json.validacao import ItemInventario, validar
from isocentro.nucleo.verificacao import (
    Avaliacao, Entrada, Resultado, Verificacao, executar)

HASH = hashlib.sha256(b"dll ficticia").hexdigest()
VAZIO: dict = {}
VALIDADO = {"teste.ficticio": ItemInventario("teste.ficticio", "1.0.0", HASH, True)}


def _doc(**kw):
    doc = {
        "versao_esquema": VERSAO_ESQUEMA,
        "verificacao": "plano.fracoes",
        "script": {"id": "teste.ficticio", "versao": "1.0.0", "hash_dll": HASH},
        "plano": {"paciente": "9000001", "curso": "C1", "id": "Plano1",
                  "versao": "2026-10-23T08:00:00"},
        "resultado": "conforme",
        "evidencia": {"fracoes": 25},
    }
    doc.update(kw)
    return json.dumps(doc)


def _validar(conteudo, versao="2026-10-23T08:00:00", inventario=None):
    return validar(conteudo, versao_plano_atual=versao,
                   inventario=VAZIO if inventario is None else inventario)


class TestEsquemaInvalidoEErro(unittest.TestCase):

    def assertErro(self, conteudo, trecho):
        imp = _validar(conteudo)
        self.assertIs(imp.avaliacao.resultado, Resultado.ERRO)
        self.assertIn(trecho, imp.avaliacao.motivo)
        self.assertIsNone(imp.documento)
        return imp

    def test_versao_de_esquema_desconhecida(self):
        imp = self.assertErro(_doc(versao_esquema=2), "versão de esquema 2 desconhecida")
        self.assertIn("conhecidas: 1", imp.avaliacao.motivo)

    def test_versao_de_esquema_ausente(self):
        doc = json.loads(_doc())
        del doc["versao_esquema"]
        self.assertErro(json.dumps(doc), "versão de esquema None desconhecida")

    def test_true_nao_passa_por_versao_1(self):
        """``True == 1`` em Python: sem excluir ``bool``, entraria como v1."""
        self.assertErro(_doc(versao_esquema=True), "desconhecida")

    def test_versao_como_texto_e_recusada(self):
        self.assertErro(_doc(versao_esquema="1"), "desconhecida")

    def test_esquema_desconhecido_vem_antes_de_campo_faltando(self):
        """No v2 o campo pode só ter mudado de nome: "falta campo" enganaria."""
        self.assertErro(json.dumps({"versao_esquema": 2}), "desconhecida")

    def test_hash_curto(self):
        self.assertErro(_doc(script={"id": "x", "versao": "1", "hash_dll": "abc"}),
                        "não é SHA-256")

    def test_hash_com_separador_do_bitconverter(self):
        hifens = "-".join(HASH[i:i + 2] for i in range(0, 64, 2))
        self.assertErro(_doc(script={"id": "x", "versao": "1", "hash_dll": hifens}),
                        "não é SHA-256")

    def test_hash_nao_hexadecimal(self):
        self.assertErro(_doc(script={"id": "x", "versao": "1", "hash_dll": "g" * 64}),
                        "não é SHA-256")

    def test_hash_ausente(self):
        self.assertErro(_doc(script={"id": "x", "versao": "1"}),
                        "falta campo: script.hash_dll")

    def test_campo_nao_previsto_e_recusado(self):
        """Campo novo sem subir a versão é o esquema mudando de um lado só."""
        self.assertErro(_doc(dose_extra=1), "campo não previsto no v1: dose_extra")

    def test_campo_nao_previsto_dentro_do_bloco(self):
        self.assertErro(
            _doc(plano={"paciente": "9000001", "curso": "C1", "id": "p",
                        "versao": "v", "maquina": "TB"}),
            "campo não previsto no v1: plano.maquina")

    def test_plano_sem_paciente_e_recusado(self):
        """O Id do plano só é único dentro do curso: sem paciente e curso, o
        ``conforme`` de um "PELVE" valeria para o "PELVE" de outro."""
        self.assertErro(_doc(plano={"id": "PELVE", "versao": "v"}),
                        "falta campo: plano.curso, plano.paciente")

    def test_verificacao_fora_do_formato_do_catalogo(self):
        for ruim in ("Plano.Fracoes", "fracoes", "plano.dose.extra"):
            with self.subTest(ruim=ruim):
                self.assertErro(_doc(verificacao=ruim), "fora do formato")

    def test_numero_que_estoura_o_double(self):
        """``1e400`` não passa pelo ``parse_constant``: viraria ``inf``."""
        bruto = _doc().replace('"fracoes": 25', '"fracoes": 1e400')
        self.assertIn("1e400", bruto)
        self.assertErro(bruto, "fora do alcance")

    def test_aninhamento_fundo_vira_erro_e_nao_excecao(self):
        self.assertErro("[" * 100000 + "]" * 100000, "aninhado fundo demais")

    def test_texto_com_surrogate_solto_nao_derruba(self):
        imp = _validar("\udcff" + _doc())
        self.assertIs(imp.avaliacao.resultado, Resultado.ERRO)
        self.assertEqual(len(imp.checksum), 64)

    def test_falta_campo_obrigatorio(self):
        doc = json.loads(_doc())
        del doc["plano"]
        self.assertErro(json.dumps(doc), "falta campo: plano")

    def test_chave_repetida(self):
        bruto = _doc()[:-1] + ', "resultado": "nao_conforme"}'
        self.assertErro(bruto, "chave 'resultado' repetida")

    def test_nan_recusado(self):
        self.assertErro(_doc()[:-1] + ', "motivo": NaN}', "NaN")

    def test_json_ilegivel(self):
        self.assertErro("{nao e json", "JSON ilegível")

    def test_nao_e_objeto(self):
        self.assertErro("[1, 2]", "não é um objeto")

    def test_nao_e_utf8(self):
        self.assertErro(b"\xff\xfe{", "não é UTF-8")

    def test_resultado_fora_dos_cinco(self):
        self.assertErro(_doc(resultado="aprovado"), "fora dos cinco")

    def test_indeterminado_sem_motivo(self):
        self.assertErro(_doc(resultado="indeterminado"), "sem motivo")

    def test_texto_vazio(self):
        self.assertErro(_doc(verificacao="  "), "verificacao ausente, vazio")

    def test_evidencia_que_nao_e_objeto(self):
        self.assertErro(_doc(evidencia=[1, 2]), "evidencia não é objeto")

    def test_erro_ainda_tem_checksum(self):
        """Até o arquivo recusado tem de ser identificável depois."""
        conteudo = b"{nao e json"
        imp = _validar(conteudo)
        self.assertEqual(imp.checksum, hashlib.sha256(conteudo).hexdigest())


class TestIndeterminado(unittest.TestCase):

    def assertIndeterminado(self, imp, trecho):
        self.assertIs(imp.avaliacao.resultado, Resultado.INDETERMINADO)
        self.assertIn(trecho, imp.avaliacao.motivo)
        self.assertIsNotNone(imp.documento)

    def test_versao_do_plano_diferente(self):
        imp = _validar(_doc(), versao="2026-10-24T09:00:00", inventario=VALIDADO)
        self.assertIndeterminado(imp, "a atual é 2026-10-24T09:00:00")
        self.assertIn("avaliou a versão 2026-10-23T08:00:00", imp.avaliacao.motivo)

    def test_sem_versao_atual_do_plano(self):
        for vazia in (None, "", "   "):
            with self.subTest(vazia=vazia):
                self.assertIndeterminado(
                    _validar(_doc(), versao=vazia, inventario=VALIDADO),
                    "sem versão atual do plano")

    def test_script_ausente_do_inventario_vazio(self):
        """O inventário vazio é o estado real até a R-61: nada vale."""
        self.assertIndeterminado(_validar(_doc()),
                                 "script teste.ficticio ausente do inventário")

    def test_script_nao_validado(self):
        inv = {"teste.ficticio": ItemInventario("teste.ficticio", "1.0.0", HASH, False)}
        self.assertIndeterminado(_validar(_doc(), inventario=inv), "não validado")

    def test_validado_que_nao_e_true_nao_conta(self):
        """Um "sim" ou um 1 vindos de planilha não são validação."""
        for valor in ("sim", 1):
            with self.subTest(valor=valor):
                inv = {"teste.ficticio":
                       ItemInventario("teste.ficticio", "1.0.0", HASH, valor)}
                self.assertIndeterminado(_validar(_doc(), inventario=inv),
                                         "não validado")

    def test_hash_diferente_do_inventariado(self):
        """Recompilado sem mudar a versão: não é a DLL que foi validada."""
        outro = hashlib.sha256(b"recompilada").hexdigest()
        inv = {"teste.ficticio": ItemInventario("teste.ficticio", "1.0.0", outro, True)}
        self.assertIndeterminado(_validar(_doc(), inventario=inv),
                                 "não é a versão inventariada")

    def test_versao_do_script_diferente_da_inventariada(self):
        inv = {"teste.ficticio": ItemInventario("teste.ficticio", "0.9.0", HASH, True)}
        self.assertIndeterminado(_validar(_doc(), inventario=inv),
                                 "não é a versão inventariada")

    def test_chave_do_inventario_trocada(self):
        """Indexado com a chave errada, o inventário validaria o script com a
        linha de outro."""
        inv = {"teste.ficticio": ItemInventario("outro.script", "1.0.0", HASH, True)}
        self.assertIndeterminado(_validar(_doc(), inventario=inv),
                                 "aponta para a linha de outro.script")

    def test_linha_do_inventario_com_celula_vazia(self):
        """None ou NaN de planilha: ``indeterminado``, não exceção."""
        for vazio in (None, float("nan")):
            with self.subTest(vazio=vazio):
                inv = {"teste.ficticio":
                       ItemInventario("teste.ficticio", "1.0.0", vazio, True)}
                self.assertIndeterminado(_validar(_doc(), inventario=inv),
                                         "malformada")

    def test_motivos_se_somam(self):
        imp = _validar(_doc(), versao="outra")
        self.assertIndeterminado(imp, "a atual é outra")
        self.assertIn("ausente do inventário", imp.avaliacao.motivo)

    def test_resultado_do_script_nao_vaza_no_indeterminado(self):
        """Um ``conforme`` de script não validado não pode chegar à tela."""
        imp = _validar(_doc(resultado="conforme"))
        self.assertIsNot(imp.avaliacao.resultado, Resultado.CONFORME)


class TestCaminhoInteiro(unittest.TestCase):
    """Com o script fictício validado e o plano na mesma versão."""

    def test_resultado_do_script_passa(self):
        imp = _validar(_doc(), inventario=VALIDADO)
        self.assertEqual(imp.avaliacao,
                         Avaliacao(Resultado.CONFORME, "", {"fracoes": 25}))
        self.assertEqual(imp.documento.objeto, "9000001/C1/Plano1")

    def test_evidencia_nao_e_dividida_com_o_documento(self):
        """Mexer na evidência da execução não pode mudar o documento importado."""
        imp = _validar(_doc(evidencia={"campos": [1, 2]}), inventario=VALIDADO)
        imp.avaliacao.evidencia["campos"].append(3)
        self.assertEqual(imp.documento.evidencia, {"campos": [1, 2]})

    def test_nao_conforme_com_motivo(self):
        imp = _validar(_doc(resultado="nao_conforme", motivo="24 ≠ 25"),
                       inventario=VALIDADO)
        self.assertIs(imp.avaliacao.resultado, Resultado.NAO_CONFORME)
        self.assertEqual(imp.avaliacao.motivo, "24 ≠ 25")

    def test_bom_do_dotnet_e_hash_maiusculo(self):
        """``File.WriteAllText`` com UTF8 põe BOM; ``BitConverter`` escreve
        em maiúscula. Os dois são o C# normal, não erro."""
        conteudo = "\ufeff" + _doc(script={"id": "teste.ficticio", "versao": "1.0.0",
                                           "hash_dll": HASH.upper()})
        for forma in (conteudo, conteudo.encode("utf-8")):
            with self.subTest(tipo=type(forma).__name__):
                imp = _validar(forma, inventario=VALIDADO)
                self.assertIs(imp.avaliacao.resultado, Resultado.CONFORME)
                self.assertEqual(imp.documento.hash_dll, HASH)

    def test_mesmo_formato_do_avaliador_python(self):
        """CAP-9: o que sai daqui entra no motor como a ``Avaliacao`` de um
        avaliador Python, sem tradução."""
        imp = _validar(_doc(), inventario=VALIDADO)
        gravadas = []

        class Porta:
            def gravar_execucao(self, execucao):
                gravadas.append(execucao)

        verif = Verificacao(id="plano.fracoes", versao="1.0.0", regra="r",
                            fontes=("fichas/atividades/C05.md",),
                            gatilho="evento", responsavel="fisico",
                            avaliador=lambda _d: imp.avaliacao,
                            severidade="alta")
        entrada = Entrada(objeto=imp.documento.objeto,
                          versao=imp.documento.plano_versao,
                          dados={"esapi": True}, degrau="esapi_json",
                          checksum=imp.checksum)
        execucao = executar(verif, entrada, Porta())
        self.assertIs(execucao.resultado, Resultado.CONFORME)
        self.assertEqual(execucao.evidencia, {"fracoes": 25})
        self.assertEqual(len(gravadas), 1)

    def test_ler_devolve_o_documento(self):
        doc = ler(_doc())
        self.assertEqual((doc.script_id, doc.script_versao, doc.versao_esquema),
                         ("teste.ficticio", "1.0.0", 1))

    def test_ler_levanta_documento_invalido(self):
        with self.assertRaises(DocumentoInvalido):
            ler(_doc(versao_esquema=99))


class TestPureza(unittest.TestCase):
    """Sem arquivo, banco nem rede: quem lê a pasta é a concentradora."""

    PROIBIDOS = {"os", "pathlib", "io", "socket", "sqlite3", "pyodbc",
                 "psycopg", "psycopg2", "subprocess", "shutil", "urllib",
                 "http", "threading", "logging", "builtins", "PySide6"}

    def test_imports(self):
        for modulo in (esquema, validacao):
            with self.subTest(modulo=modulo.__name__):
                arvore = ast.parse(Path(modulo.__file__).read_text(encoding="utf-8"))
                nomes = set()
                for no in ast.walk(arvore):
                    if isinstance(no, ast.Import):
                        nomes |= {a.name.split(".")[0] for a in no.names}
                    elif isinstance(no, ast.ImportFrom) and no.module:
                        nomes.add(no.module.split(".")[0])
                    elif (isinstance(no, ast.Call) and isinstance(no.func, ast.Name)
                          and no.func.id == "open"):
                        nomes.add("builtins")
                self.assertEqual(nomes & self.PROIBIDOS, set())

    def test_inventario_nao_tem_padrao(self):
        """Um padrão aqui seria o "validado" que ninguém validou."""
        with self.assertRaises(TypeError):
            validar(_doc(), versao_plano_atual="v")   # type: ignore[call-arg]


if __name__ == "__main__":
    unittest.main()
