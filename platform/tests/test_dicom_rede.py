"""A rede DICOM, contra um servidor de verdade — montado aqui dentro.

O ``pynetdicom`` sabe ser servidor, então o cliente não precisa esperar a
clínica para ser exercitado: estes testes sobem um SCP em ``127.0.0.1``, numa
porta livre, e falam DICOM com ele de ponta a ponta — associação, C-ECHO,
C-FIND e C-GET com o arquivo gravado em disco.

Vale a pena porque **o protocolo tem uma armadilha que só aparece falando**. Na
primeira versão o cliente propunha os papéis SCP **e** SCU para as classes de
armazenamento; o servidor aceitou o de SCU, e todas as suboperações do C-GET
falharam com "no presentation context ... for the SCU role" — mensagem que
aponta para o lado errado do problema. Num C-GET quem pede é quem RECEBE, então
o papel proposto tem de ser só o de SCP. Nada disso aparece em teste de unidade
com objeto falso: aparece no acordo de associação.

O que estes testes fixam:

* **a negociação de papel do C-GET**, que é o defeito acima;
* **configuração faltando não vira erro de rede.** "Falta o AE Title" e "o
  servidor recusou" pedem providências opostas — uma é preencher uma variável,
  a outra é chamar a TI;
* **UID que não existe devolve lista vazia, não exceção.** É a distinção do
  ``FalhaDeLeitura`` do ``capa_db``: "não achei" e "não consegui perguntar" não
  podem se confundir;
* **``completo`` exige arquivo E zero falhas.** Uma transferência que não falhou
  e não trouxe nada é tão incompleta quanto uma que falhou, e marcar a segunda
  como pronta deixaria um conjunto pela metade na pasta da sala.

Rodar:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from isocentro.dados import config_servico  # noqa: E402
from isocentro.adaptadores.dicom import rede as dicom_rede  # noqa: E402
from tests.scp_falso import UID, UID_AUSENTE, Servidor  # noqa: E402

# Os dois prefixos, e as quatro variáveis: limpar só o antigo deixaria o teste
# passando numa estação que já migrou para ``ISOCENTRO_*``, e a precedência
# é justamente o que se mede aqui.
_VARS_DICOM = tuple(
    f"{prefixo}DICOM_{sufixo}"
    for prefixo in ("ISOCENTRO_", "RADIOTERAFICHA_", "FICHAPY_")
    for sufixo in ("SERVIDOR", "AE_REMOTO", "AE_LOCAL", "AE_DESTINO"))


class SemConfiguracao(unittest.TestCase):
    """Falta de configuração não pode virar erro de rede."""

    def setUp(self):
        self._antes = dict(os.environ)
        for nome in ("ISOCENTRO_DICOM_SERVIDOR", "ISOCENTRO_DICOM_AE_REMOTO",
                     "ISOCENTRO_DICOM_AE_LOCAL", "ISOCENTRO_DICOM_SERVIDOR",
                     "ISOCENTRO_DICOM_AE_REMOTO",
                     "ISOCENTRO_DICOM_AE_LOCAL"):
            os.environ.pop(nome, None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._antes)

    def test_diz_qual_variavel_falta(self):
        """"Configuração incompleta" não serve: quem lê vai pedir a informação
        para a TI, e o pedido precisa dizer o quê."""
        self.assertFalse(dicom_rede.configurado())
        self.assertIn(dicom_rede.ENV_SERVIDOR, dicom_rede.motivo_indisponivel())

    def test_porta_com_lixo_nao_vira_o_padrao(self):
        """Cair no padrão caladamente faria "não respondeu" numa porta que
        ninguém pediu."""
        os.environ["ISOCENTRO_DICOM_SERVIDOR"] = "srv:porta-errada"
        self.assertEqual(dicom_rede.servidor(), ("srv", 0))
        self.assertIn("não é um número", dicom_rede.motivo_indisponivel())

    def test_sem_porta_usa_a_porta_do_dicom(self):
        os.environ["ISOCENTRO_DICOM_SERVIDOR"] = "srv"
        self.assertEqual(dicom_rede.servidor(),
                         ("srv", dicom_rede.PORTA_PADRAO))

    def test_operacao_sem_configuracao_levanta_com_o_motivo(self):
        with self.assertRaises(dicom_rede.FalhaDeRede) as caixa:
            dicom_rede.verificar()
        self.assertIn(dicom_rede.ENV_SERVIDOR, str(caixa.exception))


class DoisDegraus(unittest.TestCase):
    """Variável da estação → configuração do serviço.

    O segundo degrau entrou em 14/09/2026, e o motivo não se vê da tela: a
    varredura passou a poder rodar por TAREFA AGENDADA na concentradora, e
    tarefa agendada roda com OUTRA conta do Windows. ``ambiente.ler`` é
    ``os.environ`` puro, e variável de usuário não atravessa conta — com a
    configuração só em variável, a tarefa acharia a rede DICOM desconfigurada e
    não exportaria NADA, com o Agendador do Windows verde, porque o processo
    termina sem erro.
    """

    def setUp(self):
        self._dir = tempfile.mkdtemp(prefix="dicom_config_")
        self._antes = {v: os.environ.get(v)
                       for v in ("ISOCENTRO_CONFIG",) + _VARS_DICOM}
        os.environ["ISOCENTRO_CONFIG"] = self._dir
        for nome in _VARS_DICOM:
            os.environ.pop(nome, None)

    def tearDown(self):
        for nome, valor in self._antes.items():
            if valor is None:
                os.environ.pop(nome, None)
            else:
                os.environ[nome] = valor
        shutil.rmtree(self._dir, ignore_errors=True)

    def test_o_servico_configura_quem_nao_tem_variavel(self):
        """É o pedido inteiro: o admin aponta, e a conta da tarefa enxerga."""
        config_servico.definir(config_servico.DICOM_SERVIDOR,
                               "srvariadb:51404", "geovani")
        config_servico.definir(config_servico.DICOM_AE_REMOTO, "ARIA", "geovani")
        config_servico.definir(config_servico.DICOM_AE_LOCAL,
                               "RADIOTERAFICHA", "geovani")
        self.assertTrue(dicom_rede.configurado())
        self.assertEqual(dicom_rede.servidor(), ("srvariadb", 51404))
        self.assertEqual(dicom_rede.ae_remoto(), "ARIA")

    def test_a_variavel_da_estacao_vence(self):
        """Decisão de quem MONTOU a estação não se desfaz à distância — mesma
        regra da pasta de relatórios e da de exportação."""
        config_servico.definir(config_servico.DICOM_SERVIDOR,
                               "do-servico:51404", "geovani")
        os.environ["ISOCENTRO_DICOM_SERVIDOR"] = "da-estacao:104"
        self.assertEqual(dicom_rede.servidor(), ("da-estacao", 104))

    def test_o_destino_do_cmove_tambem_desce_do_servico(self):
        """O AE de destino é o que amarra IP, e é ele que faz UMA concentradora
        servir o serviço inteiro: ficando só em variável, some para a conta da
        tarefa agendada e o C-MOVE volta a não ter para onde mandar."""
        config_servico.definir(config_servico.DICOM_AE_DESTINO,
                               "RADIOTERAFICHA", "geovani")
        self.assertEqual(dicom_rede.ae_destino(), "RADIOTERAFICHA")

    def test_sem_nenhum_dos_dois_diz_qual_falta(self):
        """Continua valendo o que já valia: nada configurado não é erro de
        rede, e o motivo nomeia a peça que falta."""
        self.assertFalse(dicom_rede.configurado())
        self.assertIn(dicom_rede.ENV_SERVIDOR, dicom_rede.motivo_indisponivel())

    def test_configuracao_ilegivel_nao_derruba_a_varredura(self):
        """Config corrompida cai no "não configurado", que a varredura sabe
        tratar — levantar aqui mataria a rodada agendada inteira, e o
        ``portao`` existe justamente para isso não virar exceção."""
        with open(config_servico.caminho(), "w", encoding="utf-8") as fh:
            fh.write("isto nao e json")
        self.assertFalse(dicom_rede.configurado())
        self.assertTrue(dicom_rede.motivo_indisponivel())

    def test_a_tela_sabe_dizer_qual_degrau_venceu(self):
        """Sem isto, quem aponta na tela e não vê efeito não descobre que uma
        variável local manda — e na concentradora o degrau que vale muda com a
        CONTA que roda, que é pior de adivinhar."""
        config_servico.definir(config_servico.DICOM_SERVIDOR, "srv:104", "g")
        config_servico.definir(config_servico.DICOM_AE_REMOTO, "ARIA", "g")
        self.assertIn("serviço", dicom_rede.origem_da_configuracao())
        os.environ["ISOCENTRO_DICOM_SERVIDOR"] = "outro:104"
        self.assertIn("conta do Windows", dicom_rede.origem_da_configuracao())

    def test_o_destino_em_variavel_aparece_na_origem(self):
        """Achado da revisão da R-03 (15/09/2026): só as três primeiras eram
        olhadas, e um ``ISOCENTRO_DICOM_AE_DESTINO`` na conta da tarefa — o que
        decide para onde o ARIA manda os arquivos — deixava o ``--conferir``
        dizendo "configuração do serviço" com o destino vindo de outro lugar."""
        config_servico.definir(config_servico.DICOM_SERVIDOR, "srv:104", "g")
        config_servico.definir(config_servico.DICOM_AE_REMOTO, "ARIA", "g")
        os.environ["ISOCENTRO_DICOM_AE_DESTINO"] = "OUTRO_DESTINO"
        origem = dicom_rede.origem_da_configuracao()
        self.assertIn("ISOCENTRO_DICOM_AE_DESTINO", origem)
        self.assertNotIn("ISOCENTRO_DICOM_SERVIDOR", origem)
        self.assertIn("o resto, da configuração do serviço", origem)

    def test_so_a_rede_inteira_em_variavel_e_decisao_da_estacao(self):
        """É a pergunta do ``gatilho`` para decidir quem varre: basta uma das
        três vir do arquivo compartilhado e a decisão deixa de ser da máquina."""
        os.environ["ISOCENTRO_DICOM_SERVIDOR"] = "srv:104"
        os.environ["ISOCENTRO_DICOM_AE_REMOTO"] = "ARIA"
        self.assertFalse(dicom_rede.configurado_pela_estacao())
        os.environ["ISOCENTRO_DICOM_AE_LOCAL"] = "RADIOTERAFICHA"
        self.assertTrue(dicom_rede.configurado_pela_estacao())


class ContraOServidor(unittest.TestCase):
    """Falando DICOM de verdade com um SCP local."""

    def test_echo(self):
        with Servidor():
            self.assertIn("respondeu ao C-ECHO", dicom_rede.verificar())

    def test_find_acha_pelo_uid(self):
        with Servidor():
            achados = dicom_rede.achar_plano(UID)
        self.assertEqual(len(achados), 1)
        self.assertEqual(achados[0].PatientID, "9000019ANA")

    def test_uid_que_nao_existe_e_lista_vazia(self):
        """"Não achei" e "não consegui perguntar" não podem se confundir: uma
        manda conferir o plano, a outra manda chamar a TI."""
        with Servidor():
            self.assertEqual(dicom_rede.achar_plano(UID_AUSENTE), [])

    def test_get_traz_o_arquivo(self):
        """O teste que só existe porque o protocolo tem acordo de papel: aqui
        é onde a negociação SCP/SCU é exercitada de verdade."""
        with Servidor(), tempfile.TemporaryDirectory() as pasta:
            r = dicom_rede.baixar(UID, pasta)
            gravados = list(Path(pasta).glob("*.dcm"))
        self.assertEqual(r.modo, "C-GET")
        self.assertEqual(r.falhas, 0)
        self.assertTrue(r.completo)
        self.assertEqual(len(gravados), 1)
        # O nome é o UID: nome legível sobrescreveria o segundo objeto da mesma
        # classe, e um conjunto com um arquivo a menos não se distingue de um
        # conjunto completo.
        self.assertEqual(gravados[0].stem, UID)

    def test_transferencia_que_falha_nao_e_completa(self):
        with Servidor(aceita_get=False), tempfile.TemporaryDirectory() as p:
            r = dicom_rede.baixar(UID, p)
        self.assertFalse(r.completo)
        self.assertEqual(r.arquivos, [])

    def test_nada_recebido_nao_e_completo(self):
        """Sem falha e sem arquivo também é incompleto — marcar isso como
        pronto deixaria a pasta da sala vazia com a marca d'água gravada."""
        with Servidor(), tempfile.TemporaryDirectory() as pasta:
            r = dicom_rede.baixar(UID_AUSENTE, pasta)
        self.assertEqual(r.falhas, 0)
        self.assertFalse(r.completo)


class Sondagem(unittest.TestCase):
    """O relatório de o que o servidor implementa."""

    def test_sonda_os_tres_degraus(self):
        with Servidor(), tempfile.TemporaryDirectory() as pasta:
            achados = dicom_rede.sondar(UID, pasta)
        self.assertIn("respondeu ao C-ECHO", achados["echo"])
        self.assertIn("9000019ANA", achados["find"])
        self.assertIn("completo=True", achados["get"])
        # Sem AE de destino, o C-MOVE não é tentado — e diz por quê, em vez de
        # sair como falha.
        self.assertIn("não tentado", achados["move"])

    def test_um_degrau_que_falha_nao_interrompe_os_outros(self):
        """O que se quer é o MAPA do que funciona, não o primeiro erro."""
        with Servidor(aceita_get=False), tempfile.TemporaryDirectory() as p:
            achados = dicom_rede.sondar(UID, p)
        self.assertIn("respondeu ao C-ECHO", achados["echo"])
        self.assertIn("completo=False", achados["get"])

    def test_sem_configuracao_a_sonda_diz_isso_e_para(self):
        antes = dict(os.environ)
        for nome in list(os.environ):
            if "DICOM" in nome:
                os.environ.pop(nome, None)
        try:
            achados = dicom_rede.sondar(UID)
        finally:
            os.environ.clear()
            os.environ.update(antes)
        self.assertFalse(achados["configurado"])
        self.assertTrue(achados["motivo"])
        self.assertEqual(achados["echo"], "")


class _Recusa:
    """O A-ASSOCIATE-RJ como o ``pynetdicom`` o entrega, e só isso.

    Objeto falso porque o que se testa aqui é a LEITURA da recusa, e um SCP de
    verdade que recusasse por AE title exigiria configurar lista de chamadores
    no servidor de teste — muito aparato para exercitar três ``if``.
    """

    def __init__(self, razao, fonte=""):
        self.acceptor = type("A", (), {"primitive": self})()
        self.reason_str = razao
        self.source_str = fonte
        self.is_rejected = True
        self.is_established = False


class MotivoDaRecusa(unittest.TestCase):
    """As duas recusas do DICOM pedem providências OPOSTAS.

    Em 10/09/2026 a TI subiu o serviço novo (`192.0.2.9:51405`, AE
    `radioteraficha`) e a sondagem devolveu "Costuma ser AE Title não
    cadastrado no ARIA, ou porta bloqueada" — as duas metades do problema
    empacotadas num palpite. O servidor tinha dito exatamente qual era:
    reconheceu o AE dele e recusou o NOSSO. Sem esta leitura, o chamado seria
    aberto pedindo a coisa errada.
    """

    def test_calling_aponta_a_nossa_ponta(self):
        """"Calling" é o AE desta estação, e só a Varian/TI cadastra — dizer
        "verifique a configuração" mandaria mexer onde não adianta."""
        texto = dicom_rede.motivo_da_recusa(
            _Recusa("Calling AE title not recognised"))
        self.assertIn("DESTA estação", texto)
        self.assertIn("Varian", texto)

    def test_called_aponta_o_lado_de_la_e_se_resolve_aqui(self):
        """"Called" é o AE do ARIA: foi chute nosso, e se conserta trocando um
        valor — não vira chamado."""
        texto = dicom_rede.motivo_da_recusa(
            _Recusa("Called AE title not recognised"))
        self.assertIn("AE do ARIA", texto)
        self.assertNotIn("Varian", texto)

    def test_sem_motivo_nao_inventa_um(self):
        """Servidor que recusa sem dizer por quê não pode virar um diagnóstico
        plausível: quem lesse iria atrás do AE Title sem nenhuma evidência."""
        self.assertIn("sem motivo",
                      dicom_rede.motivo_da_recusa(_Recusa("")))

    def test_atributo_que_o_pynetdicom_mover_nao_derruba_a_associacao(self):
        """A leitura é de atributo interno da dependência. Perder o motivo é
        ruim; trocar o diagnóstico por um AttributeError é pior."""
        self.assertIn("sem motivo",
                      dicom_rede.motivo_da_recusa(object()))


class PortaQueNaoFalaDicom(unittest.TestCase):
    """Porta aberta que não fala o protocolo NÃO é "AE Title não cadastrado".

    O SRVARIADB tem setenta portas abertas. Chamar todo insucesso de "recusou a
    associação" mandaria procurar cadastro de AE onde o que há é endereço
    errado — e esse é o erro que se resolve aqui, sem chamado nenhum.
    """

    def test_diz_endereco_ou_firewall_e_nao_ae_title(self):
        import socket
        ouvinte = socket.socket()
        ouvinte.bind(("127.0.0.1", 0))
        ouvinte.listen(1)
        porta = ouvinte.getsockname()[1]
        # Ninguém aceita a conexão do outro lado, então o aperto de mão NUNCA
        # responde e este teste espera o ``acse_timeout`` inteiro. Com os 60 s
        # do produto ele sozinho custava 60,1 s dos 270 s da suíte (medido em
        # 14/09/2026) — quase um quarto dela para provar uma mensagem de erro.
        # O que se prova aqui é o TEXTO da falha, não o prazo dela.
        # Guardar e devolver, nunca ``del``: o ``del`` sumiria com a constante
        # do módulo para o resto do processo.
        antes_acse = dicom_rede.ACSE_SEGUNDOS
        dicom_rede.ACSE_SEGUNDOS = 2
        antes = dict(os.environ)
        os.environ["ISOCENTRO_DICOM_SERVIDOR"] = f"127.0.0.1:{porta}"
        os.environ["ISOCENTRO_DICOM_AE_REMOTO"] = "QUALQUER"
        os.environ["ISOCENTRO_DICOM_AE_LOCAL"] = "TESTE"
        try:
            with self.assertRaises(dicom_rede.FalhaDeRede) as caixa:
                dicom_rede.verificar()
        finally:
            ouvinte.close()
            dicom_rede.ACSE_SEGUNDOS = antes_acse
            os.environ.clear()
            os.environ.update(antes)
        texto = str(caixa.exception)
        self.assertIn("não falou DICOM", texto)
        self.assertNotIn("cadastrad", texto)


if __name__ == "__main__":
    unittest.main()
