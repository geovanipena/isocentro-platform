"""O espelho: a reserva quando o banco não responde.

Depois da migração, os relatórios exportados deixam de servir de reserva —
ninguém vai reexportá-los, e eles envelhecem em bloco. Uma capa de emergência
montada com um retrato de um mês atrás traz convênio que já mudou e prescrição
que já foi revista, e sai impressa com cara de dado bom. Isso é pior que não ter
reserva.

O espelho envelhece POR PACIENTE: quem foi aberto hoje tem reserva de hoje, e a
tela diz a idade dele.

Rodar:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from isocentro.dados import ambiente  # noqa: E402
from isocentro.banco import capa_dados  # noqa: E402
from isocentro.banco import capa_db  # noqa: E402
from isocentro.banco import capa_espelho  # noqa: E402


def _cadastro():
    return capa_dados.Cadastro(
        registro="9000001CEL", nome="JOANA HELENA FELIPE DE SICRANA",
        nascimento="15/06/1970", sexo="Feminino", contato="62 90000-0000",
        convenio="Unimed - 0064800000542300", curso="C2 JANEIRO 24",
        intencao="Pós-op.", cid="C34.2", descricao="Neoplasia do lobo médio",
        medico="THAIS SANTANA", maquina="TrueBeam")


def _prescricoes():
    return [capa_dados.Prescricao(
        site="Mama, esquerda", descricao="Mama E 40.05Gy@15fx", fracoes="15",
        frequencia="Uma Vez por Dia", curso="C2 JANEIRO 24",
        data_aprovacao="10/07/2026",
        volumes=[capa_dados.Volume(nome="PTV mama", dose_cgy="4005",
                                   dose_frac_cgy="267")])]


# O ``_banco_respondeu`` do ``capa_dados`` só olha se ``conexao()`` devolve algo
# diferente de ``None`` — nunca toca no objeto. Um sentinela basta, e deixa
# explícito que ninguém aqui finge ser cursor de banco: quem precisa de resposta
# de consulta troca ``cadastro_do_paciente`` e companhia, logo abaixo.
_CONEXAO_VIVA = object()


class _PastaLimpa(unittest.TestCase):

    def setUp(self):
        self._dir = tempfile.mkdtemp(prefix="espelho_")
        self._env = os.environ.get("ISOCENTRO_ESPELHO")
        os.environ["ISOCENTRO_ESPELHO"] = self._dir

    def tearDown(self):
        if self._env is None:
            os.environ.pop("ISOCENTRO_ESPELHO", None)
        else:
            os.environ["ISOCENTRO_ESPELHO"] = self._env


class TestGuardarELer(_PastaLimpa):

    def test_volta_inteiro(self):
        """Tudo que sai impresso tem de voltar: a capa de emergência é a MESMA
        capa, não uma versão reduzida dela."""
        self.assertTrue(capa_espelho.guardar(
            "9000001CEL", _cadastro(), _prescricoes(), b"\xff\xd8\xff\xe0foto"))
        cad, pres, foto, quando = capa_espelho.ler("9000001CEL")
        self.assertEqual(cad.convenio, "Unimed - 0064800000542300")
        self.assertEqual(cad.cid, "C34.2")
        self.assertEqual(cad.intencao, "Pós-op.")
        self.assertEqual(foto, b"\xff\xd8\xff\xe0foto")
        self.assertIsInstance(quando, datetime.datetime)

    def test_a_prescricao_volta_com_os_volumes(self):
        """Volume e dose são o corpo da capa; sem eles a folha sai com um bloco
        de título e nada dentro."""
        capa_espelho.guardar("9000001CEL", _cadastro(), _prescricoes())
        _, pres, _, _ = capa_espelho.ler("9000001CEL")
        self.assertEqual(len(pres), 1)
        self.assertEqual(pres[0].fracoes, "15")
        self.assertEqual(len(pres[0].volumes), 1)
        self.assertEqual(pres[0].volumes[0].dose_cgy, "4005")
        self.assertEqual(pres[0].volumes[0].nome, "PTV mama")

    def test_o_id_escrito_de_outro_jeito_acha_o_mesmo_espelho(self):
        """O registro chega com traço, espaço e caixa variando conforme quem
        digitou. Cada grafia virando um espelho diferente faria o paciente
        parecer sem reserva justo na emergência."""
        capa_espelho.guardar("9000001CEL", _cadastro())
        self.assertIsNotNone(capa_espelho.ler(" 9000001-cel "))
        self.assertEqual(capa_espelho.quantos(), 1)

    def test_espelhar_de_novo_substitui(self):
        capa_espelho.guardar("9000001CEL", _cadastro())
        novo = _cadastro()
        novo.convenio = "Ipasgo - 999"
        capa_espelho.guardar("9000001CEL", novo)
        cad, _, _, _ = capa_espelho.ler("9000001CEL")
        self.assertEqual(cad.convenio, "Ipasgo - 999")
        self.assertEqual(capa_espelho.quantos(), 1)

    def test_paciente_sem_espelho(self):
        self.assertIsNone(capa_espelho.ler("0000000XX"))
        self.assertIsNone(capa_espelho.idade_em_dias("0000000XX"))

    def test_arquivo_corrompido_nao_derruba_a_capa(self):
        """O espelho é lido justamente quando as coisas já não estão bem."""
        capa_espelho.guardar("9000001CEL", _cadastro())
        with open(capa_espelho.pasta() / "9000001CEL.json", "w") as fh:
            fh.write("{isto nao e json")
        self.assertIsNone(capa_espelho.ler("9000001CEL"))

    def test_versao_diferente_e_descartada(self):
        """Estrutura mudou: melhor não ter reserva que ler dado de paciente
        errado por adivinhação."""
        capa_espelho.guardar("9000001CEL", _cadastro())
        p = capa_espelho.pasta() / "9000001CEL.json"
        dados = json.loads(p.read_text(encoding="utf-8"))
        dados["versao"] = 999
        p.write_text(json.dumps(dados), encoding="utf-8")
        self.assertIsNone(capa_espelho.ler("9000001CEL"))

    def test_espelho_vencido_nao_e_lido_nem_por_emergencia(self):
        """Passado o prazo, o dado clínico já não é confiável o bastante para
        virar papel — nem com aviso. Melhor cair no degrau seguinte."""
        capa_espelho.guardar("9000001CEL", _cadastro())
        p = capa_espelho.pasta() / "9000001CEL.json"
        dados = json.loads(p.read_text(encoding="utf-8"))
        velho = datetime.datetime.now() - datetime.timedelta(
            days=capa_espelho.DIAS_PARA_EXPIRAR + 1)
        dados["em"] = velho.isoformat(timespec="seconds")
        p.write_text(json.dumps(dados), encoding="utf-8")
        self.assertIsNone(capa_espelho.ler("9000001CEL"))

    def test_gravar_faz_a_faxina_dos_vencidos(self):
        """Reserva sem prazo vira arquivo permanente de dado clínico numa pasta
        de rede. A limpeza vai na gravação: é quando já se mexe na pasta."""
        capa_espelho.guardar("1111111AA", _cadastro())
        antigo = capa_espelho.pasta() / "1111111AA.json"
        quando = time.time() - (capa_espelho.DIAS_PARA_EXPIRAR + 1) * 86400
        os.utime(antigo, (quando, quando))
        capa_espelho.guardar("2222222BB", _cadastro())
        self.assertFalse(antigo.exists())
        self.assertEqual(capa_espelho.quantos(), 1)

    def test_campo_que_nao_existe_mais_e_ignorado(self):
        """Espelho gravado por uma versão anterior não pode derrubar a atual."""
        capa_espelho.guardar("9000001CEL", _cadastro())
        p = capa_espelho.pasta() / "9000001CEL.json"
        dados = json.loads(p.read_text(encoding="utf-8"))
        dados["cadastro"]["campo_de_uma_versao_antiga"] = "x"
        p.write_text(json.dumps(dados), encoding="utf-8")
        cad, _, _, _ = capa_espelho.ler("9000001CEL")
        self.assertEqual(cad.registro, "9000001CEL")


class TestOsTresDegraus(_PastaLimpa):
    """Banco → espelho → relatórios, nessa ordem, e cada um se identifica."""

    def setUp(self):
        super().setUp()
        self._env_srv = os.environ.get(capa_db.ENV_SERVIDOR)
        # Tirar TAMBÉM o nome NOVO da variável: desde 09/09/2026 o ``capa_db``
        # lê pelo ``ambiente.ler``, e o ``ISOCENTRO_DB_SERVIDOR`` da
        # estação vence o que este ``setUp`` acabou de gravar. Sem isto o teste
        # falharia só na máquina que já migrou o nome — vermelho por motivo
        # ambiental, que é o pior modo de um teste falhar.
        self._env_srv_novo = os.environ.pop(
            ambiente.nome_novo(capa_db.ENV_SERVIDOR), None)
        os.environ[capa_db.ENV_SERVIDOR] = "SERVIDOR-DE-TESTE"
        # Zerar a variável NÃO basta para "não há banco apontado": sem ela, o
        # ``capa_db._config`` cai no ``config_servico.json``, que nesta estação
        # aponta o SRVINSIGHT — e aí ``configurado()`` continua verdadeiro. O
        # ``test_sem_banco_configurado_nao_ha_emergencia`` passava de carona:
        # outro arquivo da suíte redirecionava a pasta de configuração antes
        # dele. Rodando esta classe sozinha ele falhava, com o aviso de ÚLTIMO
        # RECURSO que o teste existe para negar (achado em 08/09/2026 pelo
        # ``tools/testar.py``, que roda só o recorte da frente). Pasta de
        # configuração vazia é o idioma já usado no ``test_tratamento.py``.
        self._env_cfg = os.environ.get("ISOCENTRO_CONFIG")
        os.environ["ISOCENTRO_CONFIG"] = tempfile.mkdtemp(prefix="cfg_vazia_")
        capa_db.esquecer()
        self._orig = (capa_db.cadastro_do_paciente,
                      capa_db.prescricoes_do_paciente, capa_db.foto_do_paciente,
                      capa_db.conexao)
        self._csv = (capa_dados.carregar_cadastro,
                     capa_dados.carregar_prescricoes)
        capa_dados.carregar_cadastro = lambda: {
            "9000001CEL": capa_dados.Cadastro(registro="9000001CEL",
                                              nome="DO RELATORIO",
                                              convenio="ANTIGO")}
        capa_dados.carregar_prescricoes = lambda: {}

    def tearDown(self):
        (capa_db.cadastro_do_paciente, capa_db.prescricoes_do_paciente,
         capa_db.foto_do_paciente, capa_db.conexao) = self._orig
        capa_dados.carregar_cadastro, capa_dados.carregar_prescricoes = self._csv
        for nome, valor in ((capa_db.ENV_SERVIDOR, self._env_srv),
                            (ambiente.nome_novo(capa_db.ENV_SERVIDOR),
                             self._env_srv_novo)):
            if valor is None:
                os.environ.pop(nome, None)
            else:
                os.environ[nome] = valor
        if self._env_cfg is None:
            os.environ.pop("ISOCENTRO_CONFIG", None)
        else:
            os.environ["ISOCENTRO_CONFIG"] = self._env_cfg
        capa_db.esquecer()
        super().tearDown()

    # O quarto lambda custava 7,5 s POR TESTE enquanto faltava, e a conta foi
    # medida em 14/09/2026: o ``capa_dados.buscar`` decide a emergência por
    # ``_banco_configurado() and not _banco_respondeu()``, e o
    # ``_banco_respondeu`` chama ``capa_db.conexao()`` DE VERDADE. Com o
    # ``SERVIDOR-DE-TESTE`` que o ``setUp`` aponta, isso era um
    # ``pyodbc.connect`` contra um nome que não existe, esperando o
    # ``TEMPO_LIMITE_S`` inteiro — três testes desta classe pagavam o
    # tempo-limite da REDE para provar coisa nenhuma sobre rede.
    #
    # Os outros três lambdas já afirmavam "o banco está fora"; faltava dizer o
    # mesmo à única pergunta que ainda saía da máquina. Sem este, os dois
    # estados mentiam um para o outro: ``_banco_fora`` dizia que o banco caiu e
    # o ``_banco_respondeu`` ia à rede perguntar se era verdade.
    def _banco_responde(self):
        capa_db.cadastro_do_paciente = lambda r: _cadastro()
        capa_db.prescricoes_do_paciente = lambda r: _prescricoes()
        capa_db.foto_do_paciente = lambda r: b"\xff\xd8\xff\xe0foto"
        capa_db.conexao = lambda: _CONEXAO_VIVA

    def _banco_fora(self):
        capa_db.cadastro_do_paciente = lambda r: None
        capa_db.prescricoes_do_paciente = lambda r: []
        capa_db.foto_do_paciente = lambda r: None
        capa_db.conexao = lambda: None

    def test_banco_responde_e_espelha(self):
        self._banco_responde()
        res = capa_dados.buscar("9000001CEL", "")
        self.assertEqual(res.origem, capa_dados.ORIGEM_BANCO)
        self.assertEqual(capa_espelho.quantos(), 1,
                         "a leitura boa tem de virar reserva")

    def test_banco_fora_usa_o_espelho_e_nao_o_relatorio(self):
        """O relatório traria "ANTIGO" no convênio: é o retrato congelado que
        esta mudança existe para não usar."""
        self._banco_responde()
        capa_dados.buscar("9000001CEL", "")
        self._banco_fora()
        res = capa_dados.buscar("9000001CEL", "")
        self.assertEqual(res.origem, capa_dados.ORIGEM_ESPELHO)
        self.assertEqual(res.cadastro.convenio, "Unimed - 0064800000542300")
        self.assertTrue(res.foto, "a 3×4 confere o paciente na sala")

    def test_a_emergencia_e_dita_com_a_data(self):
        """"Está velho" sem dizer QUANTO não muda o que a pessoa faz."""
        self._banco_responde()
        capa_dados.buscar("9000001CEL", "")
        self._banco_fora()
        res = capa_dados.buscar("9000001CEL", "")
        self.assertIn("EMERGÊNCIA", res.avisos[0])
        self.assertIn("hoje", res.avisos[0])

    def test_sem_espelho_cai_no_relatorio_dizendo_que_e_ultimo_recurso(self):
        self._banco_fora()
        res = capa_dados.buscar("9000001CEL", "")
        self.assertEqual(res.origem, capa_dados.ORIGEM_RELATORIOS)
        self.assertIn("ÚLTIMO RECURSO", res.avisos[0])

    def test_sem_banco_configurado_nao_ha_emergencia(self):
        """Instalação que ainda não migrou lê os CSV, e isso é o normal dela."""
        os.environ.pop(capa_db.ENV_SERVIDOR, None)
        capa_db.esquecer()
        res = capa_dados.buscar("9000001CEL", "")
        self.assertEqual(res.origem, capa_dados.ORIGEM_RELATORIOS)
        self.assertFalse([a for a in res.avisos if "EMERG" in a or "RECURSO" in a])

    def test_espelhar_falhando_nao_atrapalha_a_capa(self):
        """O espelho é para depois; a capa é para agora."""
        self._banco_responde()
        os.environ["ISOCENTRO_ESPELHO"] = "Z:\\pasta\\que\\nao\\existe"
        # A falha É registrada no log (é o certo em produção); aqui só evita
        # que o traceback esperado suje a saída da suíte.
        logging.disable(logging.CRITICAL)
        try:
            res = capa_dados.buscar("9000001CEL", "")
        finally:
            logging.disable(logging.NOTSET)
        self.assertEqual(res.origem, capa_dados.ORIGEM_BANCO)
        self.assertEqual(res.cadastro.cid, "C34.2")


if __name__ == "__main__":
    unittest.main()
