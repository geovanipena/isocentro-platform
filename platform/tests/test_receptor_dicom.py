"""O receptor do C-MOVE: o caminho que a exportação automática usa de verdade.

Em 10/09/2026 mediu-se, contra o ARIA da clínica, que este DB Daemon **não faz
C-GET** — ele aceita os quatro contextos de storage e recusa o contexto do Get.
O produto chamava ``dicom_rede.baixar``, que é o C-GET: estava apontado para
uma operação que nunca ia funcionar naquele servidor, e o sintoma seria uma
recusa de associação sem motivo declarado.

O C-MOVE tem uma diferença que nenhum dublê de objeto reproduz: os arquivos
**não voltam pela conexão que pediu**. O servidor abre uma conexão NOVA para o
AE de destino cadastrado nele, e por isso esta ponta precisa estar ouvindo. Se
não estiver — receptor que não subiu, ou que subiu e foi derrubado cedo demais
—, o pedido é aceito, o servidor tenta conectar e a resposta chega 21 s depois
como ``0 objeto(s), 1 falha``. Não há traceback, não há erro na tela, e o
resumo é indistinguível de destino desconhecido (que, esse sim, falha na hora).

O que estes testes fixam:

* **o conjunto chega inteiro**: plano, o RTSTRUCT que ele aponta e a RTDOSE do
  estudo que aponta de volta para ele. O C-MOVE pelo UID do plano traz UM
  objeto, e quem monta o resto é esta ponta;
* **a CT é a que o RTSTRUCT contorna, e só ela** — pedida por série, pelo fio
  ``ReferencedFrameOfReferenceSequence``. O estudo tem mais de uma CT, e
  conjunto sem CT, ou com CT que não chegou inteira, não é conjunto pronto;
* **a dose do plano VIZINHO não fica na pasta.** A série de dose traz as duas,
  e a ficha calculada sobre a dose do plano ao lado não tem sintoma nenhum: os
  números saem, plausíveis, errados;
* **as doses se pedem por SÉRIE, e nada mais do estudo vem junto.** O ARIA
  ignora ``Modality`` na consulta de instância e devolve o estudo inteiro
  (medido em 11/09/2026: 223 UIDs, e um RTPLAN de outro plano na pasta). O
  que escapar ainda assim — plano, estrutura ou CT que não são do conjunto — o
  descarte tira;
* **nada chegou é conjunto INCOMPLETO**, mesmo com o servidor dizendo que
  concluiu. É o caso do firewall de entrada fechado, e a marca d'água não pode
  registrar como exportado o que não está no disco;
* **sem AE de destino o caminho continua sendo o C-GET** — quem escolhe é a
  configuração, não a conveniência de quem chama.

Rodar:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import pydicom  # noqa: E402

from isocentro.adaptadores.dicom import rede as dicom_rede  # noqa: E402
from tests import scp_falso  # noqa: E402


def _modalidades(pasta: Path):
    """O que ficou na pasta, por modalidade — é o conjunto que a ficha lê."""
    return sorted(pydicom.dcmread(p, stop_before_pixels=True).Modality
                  for p in sorted(pasta.glob("*.dcm")))


# Três cortes: o que se exercita é o pedido por SÉRIE, não o volume.
CORTES = tuple(f"{scp_falso.SERIE_CT}.{n}" for n in range(1, 4))
CONJUNTO = ["CT", "CT", "CT", "RTDOSE", "RTPLAN", "RTSTRUCT"]


def _series_de_ct_pedidas(srv):
    """Os C-MOVE por série, fora a de dose — que agora também vem por série."""
    return [alvo for tipo, alvo in srv.pedidos
            if tipo == "move" and alvo.startswith("serie:")
            and alvo != f"serie:{scp_falso.SERIE_DOSE}"]


class TrazerPorMove(unittest.TestCase):

    def test_conjunto_completo_segue_as_referencias(self):
        """O C-MOVE do plano traz UM objeto; o resto sai das referências.

        Quando o circuito fechou na clínica, o que chegou foi só o RTPLAN — e
        parecia sucesso, porque ``1 objeto, 0 falhas`` é o que se esperava ver.
        A ficha precisa de estrutura, dose e CT, e quem as busca é esta ponta.
        """
        escuta = scp_falso.porta_livre()
        doses = ((scp_falso.UID_DOSE, scp_falso.UID),)
        with scp_falso.Servidor(escuta=escuta, doses=doses, cortes=CORTES), \
                tempfile.TemporaryDirectory() as pasta:
            resultado = dicom_rede.trazer(scp_falso.UID, pasta)
            self.assertEqual(resultado.modo, "C-MOVE")
            self.assertTrue(resultado.completo, resultado.falhas)
            self.assertEqual(_modalidades(Path(pasta)), CONJUNTO)

    def test_so_a_ct_que_a_estrutura_contorna(self):
        """O estudo tem mais de uma CT, e só uma é a do contorno.

        O estudo de um plano real tem 16 séries (``clinica-python01``,
        10/09/2026), com a CT de simulação e as de reposicionamento. Pedir as
        CT do estudo traria todas — e a ficha montada sobre a CT errada abre,
        mostra os cortes e põe as isodoses fora do lugar, sem erro nenhum.
        """
        escuta = scp_falso.porta_livre()
        doses = ((scp_falso.UID_DOSE, scp_falso.UID),)
        series = (("CT", scp_falso.SERIE_CT, None),
                  ("CT", scp_falso.SERIE_CT_OUTRA, None))
        with scp_falso.Servidor(escuta=escuta, doses=doses, cortes=CORTES,
                                series=series) as srv, \
                tempfile.TemporaryDirectory() as pasta:
            dicom_rede.trazer(scp_falso.UID, pasta)
        self.assertEqual(_series_de_ct_pedidas(srv),
                         [f"serie:{scp_falso.SERIE_CT}"])

    def test_ct_que_nao_chega_e_conjunto_incompleto(self):
        """Plano, estrutura e dose na pasta, e a CT não veio.

        É o conjunto que MAIS parece pronto: três dos quatro, todos íntegros.
        A marca d'água não pode registrar como exportado o que a ficha não
        consegue abrir inteiro.
        """
        escuta = scp_falso.porta_livre()
        doses = ((scp_falso.UID_DOSE, scp_falso.UID),)
        with scp_falso.Servidor(escuta=escuta, doses=doses), \
                tempfile.TemporaryDirectory() as pasta:
            resultado = dicom_rede.trazer(scp_falso.UID, pasta)
            self.assertEqual(_modalidades(Path(pasta)),
                             ["RTDOSE", "RTPLAN", "RTSTRUCT"])
            self.assertFalse(resultado.completo)

    def test_estrutura_que_nao_aponta_imagem_e_conjunto_incompleto(self):
        """Sem série apontada, a CT não se adivinha.

        Escolher pela CT do estudo seria escolher entre a de simulação e as de
        reposicionamento no escuro — o receptor não pede nada e diz que o
        conjunto não fechou.
        """
        escuta = scp_falso.porta_livre()
        doses = ((scp_falso.UID_DOSE, scp_falso.UID),)
        with scp_falso.Servidor(escuta=escuta, doses=doses, cortes=CORTES,
                                series_da_estrutura=()) as srv, \
                tempfile.TemporaryDirectory() as pasta:
            resultado = dicom_rede.trazer(scp_falso.UID, pasta)
            self.assertFalse(resultado.completo)
            self.assertNotIn("CT", _modalidades(Path(pasta)))
        self.assertEqual(_series_de_ct_pedidas(srv), [])

    def test_dose_do_plano_vizinho_nao_fica_na_pasta(self):
        """A dose do plano ao lado chega pela consulta de ESTUDO.

        A dose não é referenciada pelo plano: a seta aponta ao contrário. Então
        não há como segui-la para baixo, e a busca é por estudo — que devolve
        as doses de todos os planos dele. Deixar a intrusa na pasta é a ficha
        calculada sobre a dose de outro plano, sem erro nenhum na tela.
        """
        escuta = scp_falso.porta_livre()
        doses = ((scp_falso.UID_DOSE, scp_falso.UID),
                 (scp_falso.UID_DOSE_VIZINHA, scp_falso.UID2))
        with scp_falso.Servidor(escuta=escuta, doses=doses, cortes=CORTES), \
                tempfile.TemporaryDirectory() as pasta:
            resultado = dicom_rede.trazer(scp_falso.UID, pasta)
            self.assertEqual(_modalidades(Path(pasta)), CONJUNTO)
            guardadas = [p for p in resultado.arquivos
                         if scp_falso.UID_DOSE_VIZINHA in p.name]
            self.assertEqual(guardadas, [])
            self.assertTrue(resultado.completo)

    def test_pede_so_o_que_o_conjunto_precisa(self):
        """Quatro pedidos: plano, estrutura, a série de dose e a série de CT.

        Em 11/09/2026, contra o ARIA, o ``trazer`` pediu 223 objetos um a um:
        a consulta de doses era de INSTÂNCIA, o servidor ignorou a modalidade
        e devolveu o estudo inteiro. A CT veio duas vezes, REG e RTIMAGE
        falharam (18 falhas), e um RTPLAN de outro plano ficou na pasta. O
        dublê filtrava pela modalidade, e a suíte não viu.
        """
        escuta = scp_falso.porta_livre()
        doses = ((scp_falso.UID_DOSE, scp_falso.UID),)
        with scp_falso.Servidor(escuta=escuta, doses=doses,
                                cortes=CORTES) as srv, \
                tempfile.TemporaryDirectory() as pasta:
            resultado = dicom_rede.trazer(scp_falso.UID, pasta)
            self.assertTrue(resultado.completo, resultado.falhas)
            self.assertEqual(len(resultado.arquivos), len(CONJUNTO))
        pedidos = [alvo for tipo, alvo in srv.pedidos if tipo == "move"]
        self.assertEqual(pedidos, [scp_falso.UID, scp_falso.UID_STRUCT,
                                   f"serie:{scp_falso.SERIE_DOSE}",
                                   f"serie:{scp_falso.SERIE_CT}"])

    def test_so_a_dose_do_vizinho_e_conjunto_incompleto(self):
        """O estudo tem dose, mas nenhuma é deste plano.

        O descarte tira a do vizinho, e sobram plano, estrutura e CT — o
        conjunto que parece pronto e não serve à ficha. Antes, isso saía como
        ``completo``.
        """
        escuta = scp_falso.porta_livre()
        doses = ((scp_falso.UID_DOSE_VIZINHA, scp_falso.UID2),)
        with scp_falso.Servidor(escuta=escuta, doses=doses, cortes=CORTES), \
                tempfile.TemporaryDirectory() as pasta:
            resultado = dicom_rede.trazer(scp_falso.UID, pasta)
            self.assertNotIn("RTDOSE", _modalidades(Path(pasta)))
            self.assertFalse(resultado.completo)

    def test_estudo_sem_dose_e_conjunto_incompleto(self):
        """Nenhuma série de RTDOSE no estudo: não há o que pedir, e não fecha."""
        escuta = scp_falso.porta_livre()
        with scp_falso.Servidor(escuta=escuta, cortes=CORTES), \
                tempfile.TemporaryDirectory() as pasta:
            resultado = dicom_rede.trazer(scp_falso.UID, pasta)
            self.assertFalse(resultado.completo)

    def test_dose_sem_referencia_fica(self):
        """Dose que não diz de quem é NÃO se apaga.

        É como chega a dose de composição de curso. Descartar o que não se
        conseguiu identificar seria decidir por falta de informação — e nesta
        pasta sobrar um arquivo custa muito menos que faltar um.
        """
        escuta = scp_falso.porta_livre()
        doses = ((scp_falso.UID_DOSE, ""),)
        with scp_falso.Servidor(escuta=escuta, doses=doses), \
                tempfile.TemporaryDirectory() as pasta:
            dicom_rede.trazer(scp_falso.UID, pasta)
            self.assertIn("RTDOSE", _modalidades(Path(pasta)))

    def test_sem_receptor_ouvindo_o_conjunto_e_incompleto(self):
        """Nada chegou não pode sair como pronto.

        Este é o caso do firewall de ENTRADA fechado, que custou a manhã de
        10/09/2026: o servidor aceita o pedido, tenta conectar de volta e não
        acha ninguém. Simulado aqui apontando o destino para uma porta livre
        onde não subiu receptor nenhum.
        """
        import os

        with scp_falso.Servidor(escuta=scp_falso.porta_livre()), \
                tempfile.TemporaryDirectory() as pasta:
            # O receptor sobe numa porta e o ARIA manda para OUTRA — que é o
            # desencontro entre o cadastro no servidor e o que ouve aqui, e dá
            # exatamente o mesmo desfecho que o firewall fechado. Escrito no
            # ambiente, e não por argumento, porque é assim que a estação erra:
            # o ``Servidor`` devolve o ambiente ao sair.
            os.environ["ISOCENTRO_DICOM_PORTA_ESCUTA"] = str(
                scp_falso.porta_livre())
            resultado = dicom_rede.trazer(scp_falso.UID, pasta)
            self.assertEqual(resultado.arquivos, [])
            self.assertFalse(resultado.completo)
            self.assertGreaterEqual(resultado.falhas, 1)
            self.assertEqual(list(Path(pasta).glob("*.dcm")), [])

    def test_destino_desconhecido_falha_na_hora(self):
        """Destino não cadastrado e firewall fechado NÃO são o mesmo defeito.

        Um manda ligar para a TI da Varian, o outro se resolve nesta estação.
        O primeiro falha na hora; o segundo gasta 21 s e devolve o mesmo
        ``0 objeto(s)`` — foi essa confusão que fez a sondagem parecer muda.
        """
        escuta = scp_falso.porta_livre()
        with scp_falso.Servidor(escuta=escuta), \
                tempfile.TemporaryDirectory() as pasta:
            with dicom_rede.receber(pasta, porta=escuta):
                concluidas, _falhas = dicom_rede._mover_contando(
                    scp_falso.UID, "NAO_CADASTRADO")
            self.assertEqual(concluidas, 0)
            self.assertEqual(list(Path(pasta).glob("*.dcm")), [])


class QuemEscolheOCaminho(unittest.TestCase):

    def test_sem_ae_de_destino_e_c_get(self):
        """A configuração escolhe o protocolo, não quem chama.

        Sem ``ISOCENTRO_DICOM_AE_DESTINO`` não há para onde o ARIA mandar, e o
        C-GET é o único caminho possível. O ``gatilho`` não decide isso: ele
        pede o conjunto e pronto.
        """
        with scp_falso.Servidor(), tempfile.TemporaryDirectory() as pasta:
            resultado = dicom_rede.trazer(scp_falso.UID, pasta)
            self.assertEqual(resultado.modo, "C-GET")

    def test_porta_de_escuta_tem_padrao_e_e_configuravel(self):
        """104 é o padrão porque foi a que a TI liberou.

        O número entra em três lugares que equipes diferentes controlam — o
        cadastro do AE no ARIA, a regra de firewall e este processo. Fixá-lo no
        código faria o desencontro entre eles aparecer só como espera de 21 s.
        """
        self.assertEqual(dicom_rede.porta_escuta(), 104)
        escuta = scp_falso.porta_livre()
        with scp_falso.Servidor(escuta=escuta):
            self.assertEqual(dicom_rede.porta_escuta(), escuta)


class DescarteDoQueNaoEDoConjunto(unittest.TestCase):
    """A segunda barreira: o que escapar da consulta não fica na pasta.

    A primeira é pedir só o que o conjunto precisa. Mas o defeito de
    11/09/2026 foi exatamente o servidor devolver mais do que se pediu, e o
    descarte daquele dia só sabia tirar dose — o RTPLAN de outro plano ficou.
    """

    def setUp(self):
        self.pasta = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def _gravar(self, ds, nome):
        caminho = self.pasta / nome
        ds.save_as(caminho, enforce_file_format=True)
        return caminho

    def _fica(self, caminho, series=None):
        return dicom_rede._pertence_ao_conjunto(
            caminho, scp_falso.UID, [scp_falso.UID_STRUCT], series)

    def test_plano_vizinho_sai(self):
        """Pasta com dois planos é a ficha do plano errado, sem sintoma."""
        self.assertTrue(self._fica(self._gravar(scp_falso.plano(), "a.dcm")))
        self.assertFalse(self._fica(self._gravar(
            scp_falso.plano(scp_falso.UID2), "b.dcm")))

    def test_estrutura_que_o_plano_nao_aponta_sai(self):
        """Ela apontaria a CT de outro contorno, e a CT errada viria junto."""
        self.assertTrue(self._fica(self._gravar(scp_falso.estrutura(), "a.dcm")))
        outra = scp_falso.estrutura(uid=scp_falso.UID_DOSE_VIZINHA + ".9")
        self.assertFalse(self._fica(self._gravar(outra, "b.dcm")))

    def test_ct_de_outra_serie_sai_quando_a_serie_ja_e_conhecida(self):
        """Antes de ler a estrutura não se sabe a série: aí a CT fica."""
        ct = self._gravar(scp_falso.imagem_ct("1.2.3.4.10.1",
                                              scp_falso.SERIE_CT_OUTRA), "a.dcm")
        self.assertTrue(self._fica(ct))
        self.assertFalse(self._fica(ct, [scp_falso.SERIE_CT]))

    def test_ilegivel_fica(self):
        """Apagar o que não se leu seria decidir por falta de informação."""
        caminho = self.pasta / "lixo.dcm"
        caminho.write_bytes(b"nao e dicom")
        self.assertTrue(self._fica(caminho))

    def test_repetido_sai_da_lista(self):
        """O mesmo UID recebido duas vezes é um arquivo só no disco.

        A lista dizia 407 onde a pasta tinha 206 (11/09/2026), e o número do
        relatório deixou de ser conferível.
        """
        plano = self._gravar(scp_falso.plano(), "a.dcm")
        recebido = dicom_rede.Resultado(arquivos=[plano, plano])
        dicom_rede._descartar_de_fora(recebido, scp_falso.UID,
                                      [scp_falso.UID_STRUCT])
        self.assertEqual(recebido.arquivos, [plano])


if __name__ == "__main__":
    unittest.main()
