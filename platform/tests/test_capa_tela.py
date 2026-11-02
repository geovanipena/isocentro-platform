"""Tela da Capa: o que a escolha de um paciente traz, e o que ela não pode levar.

A Capa tem duas portas. Pela bancada chega um caso já carregado; pela busca
chega quem vem da tomografia, e é essa a porta do dosimetrista. Estes testes
fixam o que já quebrou nas duas: capa impressa em branco porque identificar o
paciente foi confundido com montar a capa dele, e fotos da tomografia apagadas
por uma remontagem — as duas coisas só aparecem depois de impressas.

Rodar:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
for _var in ("ISOCENTRO_SIMULACOES", "ISOCENTRO_INVENTARIO_DIR",
             "ISOCENTRO_NOTAS_DIR", "ISOCENTRO_USERS_DIR"):
    os.environ.setdefault(_var, tempfile.mkdtemp(prefix="capa_tela_"))

try:
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication, QFileDialog
    _APP = QApplication.instance() or QApplication([])
    from PIL import Image

    from isocentro.interface import capa as capa_tela
    from isocentro.banco import capa_dados
    from isocentro.papel import capa_pdf
    from isocentro.interface import fichinha
    from isocentro.interface import gui
except Exception as exc:  # noqa: BLE001
    gui = None
    _MOTIVO = str(exc)

_USUARIO = {"usuario": "t", "nome": "T", "papel": "admin"}


def _jpeg(largura: int, altura: int, cor) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (largura, altura), cor).save(buf, format="JPEG")
    return buf.getvalue()


def _esperar(ms: int = 600) -> None:
    """Deixa a busca adiada da Capa disparar (ver ``_ESPERA_BUSCA_CAPA``)."""
    laco = QEventLoop()
    QTimer.singleShot(ms, laco.quit)
    laco.exec()


class _Ref:
    """O que a lista de pacientes oferece: identificação e nada mais."""

    def __init__(self, nome="PACIENTE DE TESTE", registro="1234567XX"):
        self.nome, self.registro, self.nascimento = nome, registro, "01/01/1970"

    def casa(self, _termo):
        return True

    def rotulo(self):
        return self.nome


def _resultado_cheio() -> "capa_dados.Resultado":
    """Relatório com tudo que a capa imprime — cadastro, foto 3×4 e prescrição."""
    res = capa_dados.Resultado()
    res.achou = True
    c = res.cadastro
    c.nome, c.registro, c.nascimento = "PACIENTE DE TESTE", "1234567XX", "01/01/1970"
    c.sexo, c.convenio, c.contato = "F", "UNIMED", "(11) 90000-0000"
    c.medico, c.maquina = "SILVA", "TrueBeam"
    c.curso, c.intencao, c.cid = "CURSO 1", "CURATIVA", "C50.9"
    res.foto = _jpeg(300, 400, (200, 170, 150))
    res.prescricoes = [capa_dados.Prescricao(
        site="BREAST", descricao="Mama E", fracoes="15", frequencia="diária",
        data_aprovacao="10/07/2026", curso="CURSO 1")]
    return res


@unittest.skipIf(gui is None, "PySide6/Pillow indisponíveis")
class TestEscolhaDePaciente(unittest.TestCase):
    """A porta da tomografia: escolher o paciente é montar a capa dele."""

    def setUp(self):
        self._buscar = capa_dados.buscar
        self.res = _resultado_cheio()
        self.chamadas = []

        def falsa(registro, nome, nascimento=""):
            self.chamadas.append((registro, nome))
            return self.res

        capa_dados.buscar = falsa
        self.j = gui.JanelaPrincipal(usuario=_USUARIO)
        self.j._trocar_modo(fichinha.MODO_CAPA)
        self.j.capa.definir_pacientes([_Ref()])
        self.j.capa.busca.setText("paciente")

    def tearDown(self):
        capa_dados.buscar = self._buscar
        self.j.close()

    def _escolher(self, linha=0):
        self.j.capa.lista_pac.setCurrentRow(linha)
        _esperar()
        # Os 600 ms bastam com a máquina livre; com a suíte inteira e os
        # testes de banco rodando, a busca adiada às vezes ainda não tinha
        # preenchido a capa (29/10/2026: convênio '' em vez de 'UNIMED').
        # Espera pela CONDIÇÃO, com teto, em vez de um tempo maior para todos.
        for _ in range(30):
            if self.j.capa.coletar().convenio:
                break
            _esperar(100)

    def _fotos(self) -> int:
        return sum(len(s.fotos) for s in self.j.capa.posicionamento.setups())

    def _arrastar_foto(self):
        pasta = tempfile.mkdtemp()
        caminho = os.path.join(pasta, "TORAX_1.jpg")
        with open(caminho, "wb") as fh:
            fh.write(_jpeg(900, 700, (30, 80, 140)))
        self.j.capa.posicionamento._soltou_fotos([caminho])

    def test_escolher_traz_a_capa_inteira(self):
        """Nome, registro e nascimento não são uma capa: quem cadastrasse a
        simulação e imprimisse dali levava uma folha em branco assinada."""
        self._escolher()
        capa = self.j.capa.coletar()
        self.assertEqual(capa.convenio, "UNIMED")
        # O seletor guarda o rótulo, não a letra que o relatório trouxe —
        # e é o rótulo que sai impresso na célula de sexo da capa.
        self.assertEqual(capa.sexo, "Feminino")
        self.assertEqual(capa.contato, "(11) 90000-0000")
        self.assertEqual(capa.curso, "CURSO 1")
        self.assertEqual(capa.cid, "C50.9")
        self.assertEqual(capa.maquina, "TrueBeam")
        self.assertIn("Silva", capa.medico)
        self.assertEqual(len(capa.blocos), 1, "a prescrição não entrou")

    def test_escolher_traz_a_foto_3x4(self):
        """É por ela que se confere, na sala, que o paciente é o da folha."""
        self._escolher()
        self.assertTrue(self.j.capa.coletar().foto)
        self.assertTrue(self.j.capa.lbl_foto.tem_imagem())

    def test_navegar_pela_lista_nao_busca_a_cada_tecla(self):
        """Ler os relatórios custa ~0,4 s; uma busca por seta travaria a lista."""
        self.j.capa.definir_pacientes([_Ref(f"PACIENTE {i}", f"{i}X")
                                       for i in range(6)])
        self.j.capa.busca.setText("paciente")
        self.chamadas.clear()
        for linha in range(6):
            self.j.capa.lista_pac.setCurrentRow(linha)
        _esperar()
        self.assertEqual(len(self.chamadas), 1,
                         f"buscou {len(self.chamadas)} vezes ao percorrer 6 nomes")

    def test_busca_adiada_usa_o_paciente_em_que_a_selecao_parou(self):
        """Buscar o nome do agendamento encheria a tela com a capa de quem a
        pessoa já deixou para trás."""
        self.j.capa.definir_pacientes([_Ref(f"PACIENTE {i}", f"{i}X")
                                       for i in range(4)])
        self.j.capa.busca.setText("paciente")
        self.chamadas.clear()
        for linha in range(4):
            self.j.capa.lista_pac.setCurrentRow(linha)
        _esperar()
        self.assertEqual(self.chamadas[-1][0], "3X")

    def test_remontar_o_mesmo_paciente_nao_custa_as_fotos_da_tc(self):
        """Refazê-las exige a pessoa de volta na sala da tomografia."""
        self._escolher()
        self._arrastar_foto()
        antes = self._fotos()
        self.assertTrue(antes)
        self.j.capa.lista_pac.setCurrentRow(-1)
        self._escolher()
        self.assertEqual(self._fotos(), antes)

    def test_posicionamento_reposto_continua_por_cadastrar(self):
        """Repor não é arquivar: some se a tela for fechada sem cadastro."""
        self._escolher()
        self._arrastar_foto()
        self.j.capa.lista_pac.setCurrentRow(-1)
        self._escolher()
        self.assertTrue(self.j.capa.posicionamento_pendente())


@unittest.skipIf(gui is None, "PySide6/Pillow indisponíveis")
@unittest.skipIf(gui is None, "gui indisponível (PySide6?)")
class TestBuscaPeloRegistro(unittest.TestCase):
    """A busca da Capa sempre aceitou o registro; a TELA é que não dizia.

    O campo abria sem dica nenhuma e o convite falava em "2 letras" — e o
    usuário concluiu, em 31/08/2026, que só dava para procurar pelo nome. Ele
    estava certo sobre o que a tela oferecia: afordância que não se anuncia não
    existe. O texto é o MESMO da Ficha Virtual, que já dizia — as duas buscas
    são a mesma pergunta.
    """

    def setUp(self):
        self.c = capa_tela.PainelCapa()
        self.addCleanup(self.c.close)
        # O ``PacienteRef`` de VERDADE, não o ``_Ref`` deste arquivo: o que se
        # testa aqui é o crivo (``casa``), e o dublê responde True para tudo.
        self.c.definir_pacientes([
            capa_dados.PacienteRef(nome="Antonio Carlos de Souza",
                                   registro="9000004CEL"),
            capa_dados.PacienteRef(nome="Maria Oliveira",
                                   registro="9000018ANA")])

    def _achados(self):
        return [self.c.lista_pac.item(i).text()
                for i in range(self.c.lista_pac.count())]

    def test_acha_pelo_registro_inteiro(self):
        self.c.busca.setText("9000004CEL")
        self.assertEqual(len(self._achados()), 1)
        self.assertIn("9000004CEL", self._achados()[0])

    def test_acha_por_um_pedaco_do_registro(self):
        """Quem procura digita os últimos dígitos, não o registro completo."""
        # O pedaço sai do registro da fixture acima. Trocar um sem o outro faz a
        # busca não achar ninguém, e é o que a pseudonimização de 10/09/2026
        # quebrou aqui: nenhuma varredura por `[0-9]{7}` enxerga um teste que
        # depende de TRÊS dígitos do número.
        self.c.busca.setText("018")
        self.assertEqual(len(self._achados()), 1)
        self.assertIn("Maria", self._achados()[0])

    def test_acha_com_o_registro_colado_com_traco(self):
        self.c.busca.setText("9000004-CEL")
        self.assertIn("Antonio", self._achados()[0])

    def test_o_campo_DIZ_que_aceita_o_registro(self):
        self.assertIn("registro", self.c.busca.placeholderText())

    def test_o_convite_nao_fala_so_em_letras(self):
        self.c.busca.setText("")
        convite = self._achados()[0]
        self.assertIn("registro", convite)


class TestFotosNaoVazamEntrePacientes(unittest.TestCase):
    """Foto de posicionamento do paciente A na capa do B.

    Aconteceu: repor o posicionamento ao remontar a capa existe para não perder
    as fotos da tomografia — mas ninguém perguntava DE QUEM elas eram. Com o
    paciente A na tela e as fotos arrastadas, pedir a capa do B trazia as fotos
    de A junto, e elas saíam impressas na capa de B. É o erro que este documento
    existe para evitar: quem confere o posicionamento na sala confere contra a
    folha.

    Chega por duas portas sem passar por ``_escolher_paciente`` (que já tem a
    sua própria pergunta): o botão "Da pasta" e a busca por registro.
    """

    def setUp(self):
        self._buscar = capa_dados.buscar

        def falsa(registro, nome, nascimento=""):
            res = _resultado_cheio()
            res.cadastro.nome = nome or res.cadastro.nome
            res.cadastro.registro = registro or res.cadastro.registro
            return res

        capa_dados.buscar = falsa
        self.j = gui.JanelaPrincipal(usuario=_USUARIO)
        self.j._trocar_modo(fichinha.MODO_CAPA)
        # Sem modal: descartar é o que a pessoa responde ao ver o aviso. O que
        # está em teste é se as fotos SOBREVIVEM à troca, não o diálogo.
        self.j.capa.confirmar_descarte_do_posicionamento = lambda de, para: True

    def tearDown(self):
        capa_dados.buscar = self._buscar
        self.j.close()

    def _fotos(self) -> int:
        return sum(len(s.fotos) for s in self.j.capa.posicionamento.setups())

    def _arrastar_foto(self):
        pasta = tempfile.mkdtemp()
        caminho = os.path.join(pasta, "TORAX_1.jpg")
        with open(caminho, "wb") as fh:
            fh.write(_jpeg(900, 700, (30, 80, 140)))
        self.j.capa.posicionamento._soltou_fotos([caminho])

    def _montar(self, nome, registro):
        self.j.controle_capa.buscar(nome=nome, registro=registro,
                            preservar_posicionamento=True)

    def test_trocar_de_paciente_nao_leva_as_fotos(self):
        self._montar("PACIENTE A", "1111111AAA")
        self._arrastar_foto()
        self.assertEqual(self._fotos(), 1, "as fotos de A entraram")
        self._montar("PACIENTE B", "2222222BBB")
        self.assertEqual(self._fotos(), 0,
                         "as fotos de A ficaram na capa de B")

    def test_o_mesmo_paciente_continua_com_as_dele(self):
        """A outra metade: refazer a capa do mesmo paciente não pode custar as
        fotos, que só se refazem com ele de volta na sala da tomografia."""
        self._montar("PACIENTE A", "1111111AAA")
        self._arrastar_foto()
        self._montar("PACIENTE A", "1111111AAA")
        self.assertEqual(self._fotos(), 1)

    def test_mesmo_paciente_com_o_id_escrito_de_outro_jeito(self):
        """O registro chega com traço, espaço e caixa variando conforme quem
        digitou; comparar cru descartaria fotos do próprio paciente."""
        self._montar("PACIENTE A", "1111111AAA")
        self._arrastar_foto()
        self._montar("PACIENTE A", " 1111111-aaa ")
        self.assertEqual(self._fotos(), 1)

    def test_sem_registro_o_nome_decide(self):
        """Paciente da TC ainda sem cadastro não tem registro dos dois lados."""
        self._montar("PACIENTE SEM ID", "")
        self._arrastar_foto()
        self._montar("OUTRO PACIENTE", "")
        self.assertEqual(self._fotos(), 0)

    def test_a_pasta_do_anterior_nao_fica_valendo(self):
        """``carregar_da_pasta`` cai na pasta guardada quando não recebe uma —
        herdar a do paciente anterior importaria as notas e fotos DELE."""
        self.j.controle_capa.buscar(nome="PACIENTE A", registro="1111111AAA",
                            preservar_posicionamento=True,
                            pasta=tempfile.mkdtemp())
        self.assertTrue(self.j.capa.pasta_do_paciente())
        self._montar("PACIENTE B", "2222222BBB")
        self.assertEqual(self.j.capa.pasta_do_paciente(), "")


@unittest.skipIf(gui is None, "PySide6/Pillow indisponíveis")
class TestDaSimulacaoParaACapa(unittest.TestCase):
    """Cadastrada a simulação, o passo seguinte é a capa DESTE paciente.

    Antes, cadastrar era um beco: a tela ficava no modo Simulação (sem curso,
    sem prescrições e sem impressão) e voltar à capa exigia procurar o paciente
    de novo na lista. Quem acabou de deitar o paciente na TC tem o
    posicionamento na mão — é o momento de montar a folha.
    """

    def setUp(self):
        self._buscar = capa_dados.buscar
        self.res = _resultado_cheio()
        capa_dados.buscar = lambda registro, nome, nascimento="": self.res
        self.j = gui.JanelaPrincipal(usuario=_USUARIO)
        self.j._trocar_modo(fichinha.MODO_CAPA)
        self.j.capa.definir_modo(capa_tela.SIMULACAO)

    def tearDown(self):
        capa_dados.buscar = self._buscar
        self.j.close()

    def _arrastar_foto(self):
        pasta = tempfile.mkdtemp()
        caminho = os.path.join(pasta, "TORAX_1.jpg")
        with open(caminho, "wb") as fh:
            fh.write(_jpeg(900, 700, (30, 80, 140)))
        self.j.capa.posicionamento._soltou_fotos([caminho])

    def _confeccionar(self):
        self.j.controle_capa.confeccionar("PACIENTE DE TESTE", "1234567XX")

    def test_sai_do_modo_simulacao(self):
        """É o modo que esconde curso, prescrições e a impressão."""
        self._confeccionar()
        self.assertEqual(self.j.capa.modo(), capa_tela.COMPLETA)

    def test_traz_a_capa_dos_relatorios(self):
        self._confeccionar()
        capa = self.j.capa.coletar()
        self.assertEqual(capa.convenio, "UNIMED")
        self.assertEqual(capa.curso, "CURSO 1")
        self.assertEqual(len(capa.blocos), 1, "a prescrição não entrou")

    def test_o_posicionamento_recem_cadastrado_continua(self):
        """É dele que sai a folha 2 — e refazê-lo exige o paciente na sala."""
        self._confeccionar()
        self._arrastar_foto()
        fotos = sum(len(s.fotos) for s in self.j.capa.posicionamento.setups())
        self._confeccionar()
        self.assertEqual(
            sum(len(s.fotos) for s in self.j.capa.posicionamento.setups()),
            fotos)

    def test_ir_a_bancada_e_voltar_nao_desfaz(self):
        """``ControleCapa.ao_abrir`` devolvia a tela ao modo Simulação por não haver
        caso na bancada: curso, prescrições e o botão de impressão sumiam, e o
        trabalho parecia desfeito."""
        self._confeccionar()
        self.j.controle_capa.ao_abrir()
        self.assertEqual(self.j.capa.modo(), capa_tela.COMPLETA)


@unittest.skipIf(gui is None, "PySide6/Pillow indisponíveis")
class TestModoDaTela(unittest.TestCase):
    """Na tomografia não existe curso nem prescrição — e a tela não os mostra."""

    def setUp(self):
        self._buscar = capa_dados.buscar
        self.res = _resultado_cheio()
        # Como um paciente recém-simulado chega: sem nada aprovado ainda.
        self.res.prescricoes = []
        self.res.avisos = [capa_dados.AVISO_SEM_PRESCRICAO]
        capa_dados.buscar = lambda registro, nome, nascimento="": self.res
        self.j = gui.JanelaPrincipal(usuario=_USUARIO)

    def tearDown(self):
        capa_dados.buscar = self._buscar
        self.j.close()

    def _abrir_capa(self):
        self.j._trocar_modo(fichinha.MODO_CAPA)
        return self.j.capa

    def test_sem_caso_na_bancada_a_tela_e_o_cadastro_de_simulacao(self):
        c = self._abrir_capa()
        self.assertEqual(c.modo(), capa_tela.SIMULACAO)
        self.assertFalse(c.cartao_curso.isVisibleTo(c))
        self.assertFalse(c.cartao_presc.isVisibleTo(c))

    def test_no_cadastro_nao_ha_o_que_imprimir(self):
        """Visualizar/Salvar/Imprimir são o fim da outra ponta do caminho."""
        c = self._abrir_capa()
        for btn in (c.btn_visualizar, c.btn_salvar, c.btn_imprimir):
            self.assertFalse(btn.isVisibleTo(c), btn.text())
        self.assertTrue(c.btn_cadastrar.isVisibleTo(c))

    def test_o_titulo_diz_o_que_a_tela_e_agora(self):
        c = self._abrir_capa()
        self.assertIn("Simulação", c.lbl_titulo.text())

    def test_falta_de_prescricao_nao_e_aviso_na_tomografia(self):
        """É o esperado, não uma pendência: o caso ainda não foi calculado."""
        c = self._abrir_capa()
        c.definir_pacientes([_Ref()])
        c.busca.setText("paciente")
        c.lista_pac.setCurrentRow(0)
        _esperar()
        self.assertEqual(c.lista_avisos.count(), 0)

    def test_o_que_foi_escondido_continua_carregado(self):
        """A busca não se perde: quando o caso chegar, a capa já tem os dados."""
        self.res.prescricoes = _resultado_cheio().prescricoes
        c = self._abrir_capa()
        c.definir_pacientes([_Ref()])
        c.busca.setText("paciente")
        c.lista_pac.setCurrentRow(0)
        _esperar()
        self.assertEqual(c.coletar().curso, "CURSO 1")
        self.assertEqual(c.coletar().cid, "C50.9")

    def test_com_caso_na_bancada_volta_a_ser_a_capa(self):
        self._abrir_capa()
        self.j.form.pac_nome.setText("PACIENTE DE TESTE")
        self.j.form.pac_registro.setText("1234567XX")
        self.j._trocar_modo(fichinha.MODO_TOTAL)
        c = self._abrir_capa()
        self.assertEqual(c.modo(), capa_tela.COMPLETA)
        self.assertTrue(c.cartao_curso.isVisibleTo(c))
        self.assertTrue(c.cartao_presc.isVisibleTo(c))
        self.assertTrue(c.btn_imprimir.isVisibleTo(c))


@unittest.skipIf(gui is None, "PySide6/Pillow indisponíveis")
class TestCapaMontadaOuApenasIdentificada(unittest.TestCase):
    """A distinção que decide se a janela ainda precisa procurar."""

    def setUp(self):
        self.painel = capa_tela.PainelCapa()

    def tearDown(self):
        self.painel.close()

    def test_tela_zerada_nao_esta_montada(self):
        self.assertFalse(self.painel.montada_dos_relatorios())

    def test_capa_vinda_dos_relatorios_esta_montada(self):
        self.painel.carregar(capa_pdf.Capa(nome="FULANO", registro="1X",
                                           convenio="UNIMED"))
        self.assertTrue(self.painel.montada_dos_relatorios())

    def test_limpar_desfaz(self):
        self.painel.carregar(capa_pdf.Capa(nome="FULANO", registro="1X"))
        self.painel.limpar()
        self.assertFalse(self.painel.montada_dos_relatorios())


@unittest.skipIf(gui is None, "PySide6/Pillow indisponíveis")
class TestImportadoDaPasta(unittest.TestCase):
    """Achar e não sobrescrever não é a mesma coisa que não achar."""

    def test_preservado_conta_como_achado(self):
        imp = capa_tela.Importado(notas=1, preservado=True)
        self.assertTrue(imp.achou())

    def test_preservado_diz_o_que_fazer(self):
        """Dizer "nada encontrado" manda procurar um arquivo que está ali."""
        texto = capa_tela.Importado(notas=1, preservado=True).resumo()
        self.assertIn("limpe o posicionamento", texto)

    def test_pasta_vazia_continua_sendo_nada(self):
        self.assertFalse(capa_tela.Importado().achou())


@unittest.skipIf(gui is None, "PySide6/Pillow indisponíveis")
class TestAbrirPastaVaiNaSimulacaoCadastrada(unittest.TestCase):
    """O botão não pergunta o que o programa já sabe.

    Pedido em 04/09/2026: com todo paciente sendo aberto pelo BANCO, a pasta
    dele é justamente a que o dosimetrista cadastrou ao sair da tomografia. A
    ponte já existia (``simulacao.procurar``, que a Ficha Virtual e o
    ``capa_dados`` usam) — o botão é que não a atravessava, ia direto ao
    diálogo de "escolha a pasta".

    Perguntar à pessoa uma informação que o programa tem não é só incômodo:
    o erro possível é ela apontar a pasta de OUTRO paciente.
    """

    def setUp(self):
        from isocentro.interface import capa as capa_tela
        from isocentro.interface import simulacao
        self.simulacao = simulacao
        self._antes = simulacao.procurar
        self.p = capa_tela.PainelCapa()
        self.p._capa.nome = "FULANA DE TAL"
        self.p._capa.registro = "9000024ANA"
        self.p._pasta_paciente = ""
        self.escolhidas = []
        self.p.pasta_escolhida.connect(self.escolhidas.append)

    def tearDown(self):
        self.simulacao.procurar = self._antes
        self.p.close()

    def test_usa_a_pasta_do_cadastro_sem_perguntar(self):
        self.simulacao.procurar = lambda nome, registro="": r"X:\SIM\FULANA"
        self.p._escolher_fotos()
        self.assertEqual(self.escolhidas, [r"X:\SIM\FULANA"])

    def test_o_caminho_aparece_no_recado(self):
        """Quem clicou precisa ver que foi para o paciente certo sem abrir a
        pasta para conferir."""
        self.simulacao.procurar = lambda nome, registro="": r"X:\SIM\FULANA"
        self.p._escolher_fotos()
        self.assertIn(r"X:\SIM\FULANA", self.p.lbl_status.text())

    def test_procura_por_ESTE_paciente(self):
        """Casar pelo paciente da tela é o que impede abrir a pasta de outro."""
        vistos = []
        self.simulacao.procurar = lambda nome, registro="": (
            vistos.append((nome, registro)) or "")
        self.p._pasta_da_simulacao()
        self.assertEqual(vistos, [("FULANA DE TAL", "9000024ANA")])

    def test_sem_cadastro_a_pergunta_continua(self):
        """Paciente com pasta e sem cadastro é caso real — a 9000001CEL, em
        21/08/2026, tinha fotos e nota soltas e cadastro nenhum."""
        self.simulacao.procurar = lambda nome, registro="": ""
        chamou = []
        from PySide6.QtWidgets import QFileDialog
        antes = QFileDialog.getExistingDirectory
        QFileDialog.getExistingDirectory = staticmethod(
            lambda *a, **k: chamou.append(True) or "")
        try:
            self.p._escolher_fotos()
        finally:
            QFileDialog.getExistingDirectory = antes
        self.assertTrue(chamou, "não perguntou onde fica a pasta")

    def test_falha_ao_procurar_avisa_e_nao_trava(self):
        """Raiz de simulações fora do ar não pode virar tela morta: o recado
        explica por que o programa está perguntando."""
        def explode(nome, registro=""):
            raise OSError("rede fora")

        self.simulacao.procurar = explode
        self.assertEqual(self.p._pasta_da_simulacao(), "")
        self.assertIn("rede fora", self.p.lbl_status.text())
        self.assertTrue(self.p._status_erro, "devia sair como erro")


if __name__ == "__main__":
    unittest.main()


@unittest.skipIf(gui is None, "PySide6/Pillow indisponíveis")
class TestNotaEFotosDoPosicionamento(unittest.TestCase):
    """A nota manda montar o paciente; ela não pode mudar de passagem."""

    def setUp(self):
        from isocentro.dados import notas_setup
        from isocentro.interface import posicionamento as pos
        self.pos, self.notas_setup = pos, notas_setup
        notas_setup.salvar([
            notas_setup.Nota(nome="TORAX PADRAO", acessorios="Rampa 15"),
            notas_setup.Nota(nome="MAMA PADRAO", acessorios="Rampa de mama")])
        self.p = pos.PainelPosicionamento()
        self.p._recarregar_notas()
        self.aba = self.p._aba()

    def tearDown(self):
        self.p.close()

    def _aplicar(self, nome):
        i = self.aba["nota"].findText(nome)
        self.aba["nota"].setCurrentIndex(i)
        self.p._aplicar_nota(i)
        return i

    def test_roda_do_mouse_nao_troca_a_nota(self):
        """Numa tela rolável, rolar com o cursor sobre o seletor trocava o
        valor e ninguém via — e o valor é o que se faz com o paciente."""
        from PySide6.QtCore import QPoint, QPointF, Qt
        from PySide6.QtGui import QWheelEvent

        cmb = self.aba["nota"]
        self.assertIsInstance(cmb, capa_tela.ui.Escolha)
        antes = cmb.currentIndex()
        _APP.sendEvent(cmb, QWheelEvent(
            QPointF(5, 5), QPointF(5, 5), QPoint(0, -120), QPoint(0, -120),
            Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False))
        self.assertEqual(cmb.currentIndex(), antes)

    def test_escolher_de_proposito_aplica(self):
        self._aplicar("TORAX PADRAO")
        self.assertEqual(self.aba["acessorios"].toPlainText(), "Rampa 15")

    def test_sem_ajuste_a_troca_nao_incomoda(self):
        self._aplicar("TORAX PADRAO")
        self.assertFalse(self.p._tem_ajuste_manual(self.aba))

    def test_ajuste_a_mao_e_reconhecido(self):
        self._aplicar("TORAX PADRAO")
        self.aba["acessorios"].setPlainText("Rampa 15 + coxim")
        self.assertTrue(self.p._tem_ajuste_manual(self.aba))

    def test_recusar_a_troca_devolve_o_seletor(self):
        """Seletor apontando uma nota que não foi aplicada é pior que nenhuma:
        quem confere a folha acredita nele."""
        self._aplicar("TORAX PADRAO")
        self.aba["acessorios"].setPlainText("Rampa 15 + coxim")
        self.p._confirmar_troca_de_nota = lambda _para: False
        self._aplicar("MAMA PADRAO")
        self.assertEqual(self.aba["acessorios"].toPlainText(),
                         "Rampa 15 + coxim")
        self.assertEqual(self.aba["nota"].currentText(), "TORAX PADRAO")

    def test_confirmar_a_troca_reescreve(self):
        self._aplicar("TORAX PADRAO")
        self.aba["acessorios"].setPlainText("Rampa 15 + coxim")
        self.p._confirmar_troca_de_nota = lambda _para: True
        self._aplicar("MAMA PADRAO")
        self.assertEqual(self.aba["acessorios"].toPlainText(), "Rampa de mama")

    def test_tres_fotos_por_posicionamento(self):
        self.assertEqual(self.pos.MAX_FOTOS, 3)
        self.assertEqual(len(self.aba["miniaturas"]), 3)

    def test_a_quarta_foto_nao_entra(self):
        pasta = tempfile.mkdtemp()
        caminhos = []
        for k in range(5):
            c = os.path.join(pasta, f"f{k}.jpg")
            with open(c, "wb") as fh:
                fh.write(_jpeg(400, 300, (k * 40, 80, 140)))
            caminhos.append(c)
        self.assertEqual(self.p.acrescentar_fotos(caminhos), 3)
        self.assertEqual(sum(1 for f in self.aba["fotos"] if f), 3)

    def _fotos(self, quantas: int) -> list:
        pasta = tempfile.mkdtemp()
        caminhos = []
        for k in range(quantas):
            c = os.path.join(pasta, f"h{k}.jpg")
            with open(c, "wb") as fh:
                fh.write(_jpeg(400, 300, (k * 30, 70, 130)))
            caminhos.append(c)
        return caminhos

    def _recados(self) -> list:
        """O que a tela recebeu — todos os avisos, na ordem."""
        recebidos = []
        self.p.aviso.connect(lambda msg, erro: recebidos.append((msg, erro)))
        return recebidos

    def test_a_foto_descartada_nao_some_sem_recado(self):
        """O defeito: soltar quatro fotos e receber "3 foto(s)".

        O aviso de "já tem 3 fotos" era emitido dentro do ``acrescentar_fotos``
        e o chamador, vendo que alguma entrou, escrevia a mensagem de sucesso
        POR CIMA dele — ``mostrar_status`` mostra só a última. Quem soltou
        quatro ia embora achando que estavam as quatro, e a foto que faltava só
        apareceria com a folha na sala.
        """
        recebidos = self._recados()
        self.p._soltou_fotos(self._fotos(4))
        self.assertTrue(recebidos, "não avisou nada")
        msg, erro = recebidos[-1]
        self.assertIn("3 foto(s)", msg)
        self.assertIn("não coube", msg)
        self.assertTrue(erro, "sobra de foto é notícia ruim, não sucesso")

    def test_tudo_cheio_avisa_mesmo_sem_nenhuma_entrar(self):
        """Com o posicionamento já cheio, nada entra — e o silêncio aqui seria
        idêntico ao de um arraste que funcionou."""
        self.p.acrescentar_fotos(self._fotos(3))
        recebidos = self._recados()
        self.p._soltou_fotos(self._fotos(1))
        self.assertIn("não coube", recebidos[-1][0])
        self.assertTrue(recebidos[-1][1])

    def test_arquivo_ilegivel_tambem_e_contado(self):
        """Até 04/09/2026 o ``OSError`` era descartado em silêncio absoluto —
        sem nem o aviso que o limite tinha."""
        caminhos = self._fotos(1) + [os.path.join(tempfile.mkdtemp(), "x.jpg")]
        recebidos = self._recados()
        self.p._soltou_fotos(caminhos)
        self.assertIn("não abriu", recebidos[-1][0])

    def test_arraste_que_cabe_inteiro_continua_sendo_sucesso(self):
        """A frase da sobra não pode aparecer quando não houve sobra."""
        recebidos = self._recados()
        self.p._soltou_fotos(self._fotos(2))
        msg, erro = recebidos[-1]
        self.assertIn("2 foto(s)", msg)
        self.assertNotIn("Mas", msg)
        self.assertFalse(erro)

    def test_avisa_a_foto_que_nao_sai_impressa(self):
        """Cada posicionamento a mais divide a faixa: com TRÊS sobram dois
        quadros para cada, e a 3ª foto de cada um deixa de sair. Descobrir isso
        com a folha na sala custa a viagem."""
        pasta = tempfile.mkdtemp()
        caminhos = []
        for k in range(3):
            c = os.path.join(pasta, f"g{k}.jpg")
            with open(c, "wb") as fh:
                fh.write(_jpeg(400, 300, (k * 50, 90, 120)))
            caminhos.append(c)
        self.p.acrescentar_fotos(caminhos)
        # Com dois — o teto —, as três fotos de cada um ainda saem.
        self.p._nova_aba_setup()
        self.p._avisar_setups()
        self.assertNotIn("⚠", self.p.lbl_dica.text())

    def test_o_mais_para_no_teto_da_folha(self):
        """Aceitar um terceiro e descartá-lo na impressão era o pior desfecho:
        a aba existia, recebia fotos, e sumia do PDF sem aviso."""
        avisos = []
        self.p.aviso.connect(lambda msg, erro: avisos.append(msg))
        while len(self.p._setups) < capa_pdf.MAX_SETUPS:
            self.p._pedir_novo_setup()
        self.assertEqual(len(self.p._setups), capa_pdf.MAX_SETUPS)
        self.assertFalse(self.p.btn_add_setup.isEnabled())
        self.p._pedir_novo_setup()
        self.assertEqual(len(self.p._setups), capa_pdf.MAX_SETUPS)
        self.assertTrue(avisos and str(capa_pdf.MAX_SETUPS) in avisos[-1])

    def test_quadros_da_folha_por_numero_de_setups(self):
        # Um ou dois posicionamentos: uma tira de TRÊS para cada. O arranjo de
        # três, que dava dois quadros a cada um, saiu junto com o terceiro setup.
        self.assertEqual(capa_pdf.fotos_impressas(1), 3)
        self.assertEqual(capa_pdf.fotos_impressas(2), 3)

    def test_nome_do_posicionamento_recebe_o_da_nota(self):
        """É o rótulo impresso na folha 2: tem de dizer a mesma montagem que os
        acessórios logo abaixo."""
        self._aplicar("TORAX PADRAO")
        self.assertEqual(self.aba["nome"].text(), "TORAX PADRAO")

    def test_o_nome_continua_editavel(self):
        self._aplicar("TORAX PADRAO")
        self.aba["nome"].setText("TORAX DIREITO")
        self.assertEqual(self.aba["nome"].text(), "TORAX DIREITO")

    def test_trocar_a_nota_renomeia_o_posicionamento(self):
        self._aplicar("TORAX PADRAO")
        self.aba["nome"].setText("TORAX DIREITO")
        self.p._confirmar_troca_de_nota = lambda _para: True
        self._aplicar("MAMA PADRAO")
        self.assertEqual(self.aba["nome"].text(), "MAMA PADRAO")

    def test_biblioteca_tem_criar_editar_e_excluir(self):
        from PySide6.QtWidgets import QPushButton
        rotulos = {b.text() for b in self.p.findChildren(QPushButton)}
        self.assertTrue({"Nova…", "Editar…", "Excluir…"} <= rotulos)

    def _responder(self, rotulo):
        """Responde ao QMessageBox modal do botão Excluir."""
        from PySide6.QtWidgets import QMessageBox, QPushButton

        def falso(caixa):
            for b in caixa.findChildren(QPushButton):
                if rotulo in b.text():
                    caixa._escolhido = b
                    return 0
            raise AssertionError(
                [b.text() for b in caixa.findChildren(QPushButton)])

        self._orig_exec = QMessageBox.exec
        QMessageBox.exec = falso
        QMessageBox.clickedButton = lambda c: getattr(c, "_escolhido", None)
        self.addCleanup(setattr, QMessageBox, "exec", self._orig_exec)

    def test_excluir_tira_a_nota_da_biblioteca(self):
        self._aplicar("MAMA PADRAO")
        self._responder("Excluir")
        self.p._nota_excluir()
        nomes = {n.nome for n in self.notas_setup.carregar()}
        self.assertNotIn("MAMA PADRAO", nomes)
        self.assertIn("TORAX PADRAO", nomes, "levou a nota errada junto")

    def test_recusar_a_exclusao_nao_apaga(self):
        """Excluir não tem desfazer — recusar tem de ser inofensivo.

        A recusa chama-se "Manter a nota", e não "Cancelar", desde o padrão de
        pop-ups de 25/08/2026: o botão diz o que ACONTECE ao clicar nele, e
        "Cancelar" ao lado de "Excluir" obriga a reler o título para saber
        qual dos dois preserva a nota (ver ``ui.confirmar``).
        """
        self._aplicar("MAMA PADRAO")
        self._responder("Manter a nota")
        self.p._nota_excluir()
        nomes = {n.nome for n in self.notas_setup.carregar()}
        self.assertIn("MAMA PADRAO", nomes)

    def test_excluir_sem_nota_escolhida_avisa_em_vez_de_apagar(self):
        avisos = []
        self.p.aviso.connect(lambda msg, erro: avisos.append((msg, erro)))
        self.p._nota_excluir()
        self.assertEqual(len(self.notas_setup.carregar()), 2)
        self.assertTrue(avisos and avisos[-1][1], "não avisou")


@unittest.skipIf(gui is None, "PySide6/Pillow indisponíveis")
class TestCapaDeUmaPasta(unittest.TestCase):
    """A Capa monta a partir de uma PASTA, sem plano na bancada.

    É o caminho de quem chega da tomografia: a pasta do paciente na mão e
    nenhum plano calculado. Antes, o botão "Da pasta" relia a pasta que a
    BANCADA tinha aberto — sem caso lá, ele nascia desligado e a tela não tinha
    por onde começar.
    """

    def setUp(self):
        self._buscar = capa_dados.buscar
        self.pedidos = []

        def falsa(registro, nome, nascimento=""):
            self.pedidos.append((registro, nome))
            res = capa_dados.Resultado()
            res.achou = True
            c = res.cadastro
            c.nome, c.registro = "AMOSTRA DE BELTRANA", "9000016BET"
            c.nascimento, c.sexo = "14/07/1966", "F"
            c.convenio, c.maquina = "Ipasgo", "600CD"
            return res

        # ``addCleanup`` logo depois de cada troca, e não a devolução no
        # ``tearDown``: se a ``JanelaPrincipal`` falhar no ``setUp``, o
        # ``tearDown`` não roda e a falsa ficaria valendo para o resto da suíte.
        capa_dados.buscar = falsa
        self.addCleanup(setattr, capa_dados, "buscar", self._buscar)
        # A lista de pacientes também é falsa. A verdadeira sai da procura
        # automática por relatórios sob a pasta do programa, e na estação do
        # desenvolvedor ela ACHA o CSV (em ``capa/`` ou ``TCs_Teste/``, ambos
        # fora do git). Num checkout limpo a lista vinha vazia, e o "Nenhum
        # paciente na lista" sobrescrevia o "Não identifiquei" que o teste da
        # pasta sem identidade confere: passava lá, falhava no worktree do
        # robô — o teste media o disco, não a tela.
        self._pacientes = capa_dados.pacientes
        capa_dados.pacientes = lambda: [_Ref()]
        self.addCleanup(setattr, capa_dados, "pacientes", self._pacientes)
        self.j = gui.JanelaPrincipal(usuario=_USUARIO)
        self.j._ir_para_modo(fichinha.MODO_CAPA)
        self.pasta = tempfile.mkdtemp(prefix="pac_")

    def tearDown(self):
        self.j.close()

    def _com_ficha_anterior(self):
        import json
        with open(os.path.join(self.pasta, "FICHA_9000016BET.json"), "w",
                  encoding="utf-8") as fh:
            json.dump({"paciente": {"nome": "AMOSTRA DE BELTRANA",
                                    "registro": "9000016BET",
                                    "nascimento": "14/07/1966"},
                       "versoes": [{"versao": 1, "dados": {}, "plano_rp": {}}]},
                      fh)

    def test_o_botao_da_pasta_nasce_ligado(self):
        """Sem ele aceso, quem vem da tomografia não tem por onde começar."""
        self.assertFalse(self.j._tem_caso())
        self.assertTrue(self.j.capa.btn_fotos.isEnabled())

    def test_a_pasta_identifica_o_paciente_e_monta_a_capa(self):
        self._com_ficha_anterior()
        self.j.controle_capa.da_pasta(self.pasta)
        # O que se PEDE à busca é o nome cru da ficha anterior (o casamento
        # ignora acento e caixa); o que se IMPRIME é a grafia do app.
        self.assertEqual(self.pedidos, [("9000016BET", "AMOSTRA DE BELTRANA")])
        capa = self.j.capa.coletar()
        self.assertEqual(capa.nome, "Amostra de Beltrana")
        self.assertEqual(capa.convenio, "Ipasgo")

    def test_a_bancada_nao_e_tocada(self):
        """Carregar o caso lá custa a TC inteira e traz dose e estruturas que
        esta tela não usa."""
        self._com_ficha_anterior()
        self.j.controle_capa.da_pasta(self.pasta)
        self.assertFalse(self.j._tem_caso())
        self.assertEqual(self.j.form.pac_nome.text().strip(), "")

    def test_pasta_sem_identidade_oferece_a_busca(self):
        """Sem DICOM, ficha anterior nem cadastro de simulação, dá para seguir
        à mão — mas quem procura o cadastro precisa saber por que ele não veio."""
        self.j.controle_capa.da_pasta(self.pasta)
        self.assertEqual(self.pedidos, [])
        self.assertIn("não identifiquei", self.j.capa.lbl_status.text().lower())

    def test_pasta_inexistente_avisa(self):
        self.j.controle_capa.da_pasta(os.path.join(self.pasta, "nao-existe"))
        self.assertIn("não encontrada", self.j.capa.lbl_status.text().lower())

    def test_o_proximo_paciente_nao_herda_a_pasta_do_anterior(self):
        """O botão relia a pasta do paciente que JÁ SAIU, calado.

        "Próximo paciente" chama ``capa.limpar()``, que não zerava a pasta.
        No paciente seguinte, "Abrir pasta do paciente" deixava de PERGUNTAR
        qual era: relia a do anterior e punha a nota e as fotos dele na capa
        do novo, com a tela dizendo "Importado: a nota …". É a mesma mistura
        de pacientes que ``ControleCapa.buscar`` já evitava pela outra porta.
        """
        with open(os.path.join(self.pasta, "SETUP_A.txt"), "w",
                  encoding="utf-8") as fh:
            fh.write("Máscara termoplástica\n")
        self._com_ficha_anterior()
        self.j.controle_capa.da_pasta(self.pasta)
        self.assertTrue(self.j.capa.posicionamento.setups(),
                        "a nota do primeiro paciente nem chegou a entrar")

        self.j.capa.limpar()
        self.assertEqual(self.j.capa.pasta_do_paciente(), "")

        # O clique agora tem de PERGUNTAR a pasta em vez de reler a anterior.
        perguntou = []
        original = QFileDialog.getExistingDirectory
        QFileDialog.getExistingDirectory = lambda *a, **k: (
            perguntou.append(a), "")[1]
        try:
            self.j.capa.btn_fotos.click()
        finally:
            QFileDialog.getExistingDirectory = original
        self.assertTrue(perguntou, "não perguntou qual é a pasta")
        self.assertEqual(self.j.capa.posicionamento.setups(), [],
                         "o posicionamento do paciente anterior voltou")


@unittest.skipIf(gui is None, "PySide6/Pillow indisponíveis")
class TestCorrecaoQueDura(unittest.TestCase):
    """Corrigir muda ESTA capa; salvar faz a correção valer nas próximas.

    Sem isso o relatório reescrevia o conserto na abertura seguinte, e alguém
    corrigia o mesmo sexo toda vez que o paciente voltava.
    """

    def setUp(self):
        from isocentro.dados import correcoes
        self.correcoes = correcoes
        self._dir = tempfile.mkdtemp(prefix="corr_tela_")
        os.environ["ISOCENTRO_CORRECOES"] = self._dir
        self.p = capa_tela.PainelCapa()
        self.p.definir_usuario("geovani")

    def tearDown(self):
        os.environ.pop("ISOCENTRO_CORRECOES", None)
        self.p.close()

    def _do_relatorio(self):
        """Como o relatório traz: sexo na letra, e errado."""
        return capa_pdf.Capa(nome="AMOSTRA DE BELTRANA", registro="9000016BET",
                             nascimento="14/07/1966", sexo="M",
                             convenio="Ipasgo", medico="THAIS", maquina="600CD")

    def test_a_correcao_sobrevive_a_reabertura(self):
        self.p.carregar(self._do_relatorio())
        self.p.f_sexo.setCurrentText("Feminino")
        self.p._salvar_correcoes()
        # O relatório continua dizendo "M" — e a tela, "Feminino".
        self.p.carregar(self._do_relatorio())
        self.assertEqual(self.p.f_sexo.currentText(), "Feminino")

    def test_a_correcao_chega_ao_pdf(self):
        """A cor da faixa do nome sai do sexo: corrigir sem chegar ao PDF era
        acertar na tela e imprimir errado."""
        self.p.carregar(self._do_relatorio())
        self.p.f_sexo.setCurrentText("Feminino")
        self.p._salvar_correcoes()
        self.p.carregar(self._do_relatorio())
        self.assertTrue(self.p.coletar().feminino())

    def test_so_o_que_diverge_e_guardado(self):
        """Guardar a linha inteira viraria um segundo cadastro, que
        envelheceria em silêncio."""
        self.p.carregar(self._do_relatorio())
        self.p.f_sexo.setCurrentText("Feminino")
        self.p._salvar_correcoes()
        self.assertEqual(self.correcoes.ler("9000016BET"), {"sexo": "Feminino"})

    def test_devolver_ao_original_desfaz(self):
        """O relatório escreve "M" e o seletor mostra "Masculino": comparando
        as duas grafias, desfazer regravava a correção que se queria apagar."""
        self.p.carregar(self._do_relatorio())
        self.p.f_sexo.setCurrentText("Feminino")
        self.p._salvar_correcoes()
        self.p.carregar(self._do_relatorio())
        self.p.f_sexo.setCurrentText("Masculino")
        self.p._salvar_correcoes()
        self.assertEqual(self.correcoes.ler("9000016BET"), {})
        self.p.carregar(self._do_relatorio())
        self.assertEqual(self.p.f_sexo.currentText(), "Masculino")

    def test_sem_registro_recusa_e_diz_por_que(self):
        self.p.carregar(capa_pdf.Capa(nome="SEM REGISTRO", sexo="F"))
        self.p._salvar_correcoes()
        self.assertIn("registro", self.p.lbl_status.text().lower())

    def test_avisa_a_janela_para_o_historico(self):
        """Correção de cadastro é dado de paciente: fica registrado."""
        vistos = []
        self.p.correcao_salva.connect(lambda r, c: vistos.append((r, sorted(c))))
        self.p.carregar(self._do_relatorio())
        self.p.f_convenio.setText("Unimed")
        self.p._salvar_correcoes()
        self.assertEqual(vistos, [("9000016BET", ["convenio"])])

    def test_o_botao_so_aparece_com_o_painel_aberto(self):
        self.assertTrue(self.p.btn_salvar_id.isHidden())
        self.p._alternar_edicao_id()
        self.assertFalse(self.p.btn_salvar_id.isHidden())
        self.p._alternar_edicao_id()
        self.assertTrue(self.p.btn_salvar_id.isHidden())


@unittest.skipIf(gui is None, "PySide6/Pillow indisponíveis")
class TestSexoNaEdicao(unittest.TestCase):
    """Sexo é seletor, não caixa de texto — é ele que escolhe a cor da faixa."""

    def setUp(self):
        self.p = capa_tela.PainelCapa()

    def tearDown(self):
        self.p.close()

    def _carregar(self, sexo):
        self.p.carregar(capa_pdf.Capa(nome="X", registro="1", sexo=sexo))

    def test_tres_opcoes_e_nada_digitado(self):
        opcoes = [self.p.f_sexo.itemText(i) for i in range(self.p.f_sexo.count())]
        self.assertEqual(opcoes, ["Feminino", "Masculino", "Outro"])
        self.assertFalse(self.p.f_sexo.isEditable())

    def test_traduz_o_que_o_relatorio_trouxe(self):
        """A coluna vem "F", "FEM", "Feminino" — o seletor mostra três."""
        for entrada, esperado in (("F", "Feminino"), ("FEM", "Feminino"),
                                  ("Feminino", "Feminino"), ("M", "Masculino"),
                                  ("MASC", "Masculino"), ("m", "Masculino")):
            self._carregar(entrada)
            self.assertEqual(self.p.f_sexo.currentText(), esperado, entrada)

    def test_valor_irreconhecivel_fica_em_branco_e_nao_vira_outro(self):
        """"Outro" é resposta de alguém que olhou o caso, não tradução de lixo.

        O cadastro traz coisas como "Indeterminado", "I" e "-". Mandar isso para
        "Outro" imprimia na capa uma afirmação que ninguém fez — e ainda apagava
        a pendência, porque campo preenchido não acende aviso. Em branco, a tela
        pede para conferir.
        """
        for bruto in ("Indeterminado", "I", "-", "NAO INFORMADO"):
            with self.subTest(bruto=bruto):
                self._carregar(bruto)
                self.assertEqual(self.p.f_sexo.currentText(), "")

    def test_outro_gravado_volta_como_outro(self):
        """Quem respondeu "Outro" não pode ver a resposta sumir ao reabrir."""
        self._carregar("Outro")
        self.assertEqual(self.p.f_sexo.currentText(), "Outro")

    def test_paciente_sem_sexo_nao_herda_o_do_anterior(self):
        """``setCurrentText("")`` num combo não editável não faz nada: o valor
        anterior ficava, e o paciente novo saía com o sexo de outro."""
        self._carregar("M")
        self._carregar("")
        self.assertEqual(self.p.f_sexo.currentText(), "")

    def test_a_cor_da_faixa_segue_a_escolha(self):
        self._carregar("Feminino")
        self.assertTrue(self.p.coletar().feminino())
        self._carregar("Masculino")
        self.assertTrue(self.p.coletar().masculino())
        self._carregar("Outro")
        self.assertFalse(self.p.coletar().sexo_definido())

    def test_outro_e_resposta_e_nao_pendencia(self):
        """Escolher "Outro" é AFIRMAR; deixar em branco é não ter respondido —
        só o segundo pede providência."""
        self._carregar("")
        self.assertTrue(any("Sexo" in a for a in self.p._avisos_proprios()))
        self.p.f_sexo.setCurrentText("Outro")
        self.assertFalse(any("Sexo" in a for a in self.p._avisos_proprios()))


@unittest.skipIf(gui is None, "PySide6/Pillow indisponíveis")
class TestIdentificacaoEmChips(unittest.TestCase):
    """A identificação se LÊ; corrigir é o caso raro e fica atrás de um botão."""

    def setUp(self):
        self.painel = capa_tela.PainelCapa()
        self.painel.carregar(capa_pdf.Capa(
            nome="PACIENTE DE TESTE", registro="1234567XX",
            nascimento="10/05/1973", sexo="Feminino",
            convenio="Unimed - Nacional Apartamento",
            contato="(62) 90000-0000", medico="DR. FULANO",
            maquina="TBuniverSN1002"))

    def tearDown(self):
        self.painel.close()

    def _chips(self, linha):
        return [linha.itemAt(i).widget().text()
                for i in range(linha.count())
                if isinstance(linha.itemAt(i).widget(), capa_tela.ui.Chip)]

    def test_toda_a_identificacao_vira_chip(self):
        cab = self.painel.cabecalho
        tudo = self._chips(cab.linha_chips) + self._chips(cab.linha_extra)
        for esperado in ("1234567XX", "Feminino", "(62) 90000-0000",
                         "DR. FULANO", "TBuniverSN1002"):
            self.assertIn(esperado, tudo)

    def test_convenio_entra_sem_o_plano(self):
        """"Unimed - Nacional Apartamento" não cabe e não distingue nada."""
        self.assertIn("Unimed", self._chips(self.painel.cabecalho.linha_chips))

    def _pilulas(self, linha):
        return [linha.itemAt(i).widget() for i in range(linha.count())
                if isinstance(linha.itemAt(i).widget(), capa_tela.ui.Chip)]

    def test_as_pilulas_ocupam_a_largura_da_faixa(self):
        """A identidade ocupava um terço da tela; o resto era vão.

        As duas fileiras têm de terminar juntas e rente à borda — não no meio,
        com os dados do paciente amontoados num canto de uma tela vazia.
        """
        self.painel.resize(1600, 900)
        self.painel.show()
        self.painel.repaint()
        cab = self.painel.cabecalho
        for linha in (cab.linha_chips, cab.linha_extra):
            pilulas = self._pilulas(linha)
            self.assertTrue(pilulas)
            # Cada uma cresceu além do próprio texto…
            for p in pilulas:
                self.assertGreater(p.width(), p.sizeHint().width(), p.text())
            # …e a fileira termina perto da borda, não no meio da faixa.
            fim = pilulas[-1].x() + pilulas[-1].width()
            self.assertGreater(fim, cab.width() * 0.7)

    def test_pilula_sozinha_nao_vira_barra(self):
        """Esticar sem teto daria uma faixa da largura da tela — não um dado."""
        painel = capa_tela.PainelCapa()
        try:
            painel.carregar(capa_pdf.Capa(nome="JOSE DA SILVA",
                                          sexo="Masculino"))
            painel.resize(1600, 900)
            painel.show()
            painel.repaint()
            (pilula,) = self._pilulas(painel.cabecalho.linha_chips)
            self.assertLess(pilula.width(), painel.cabecalho.width() * 0.4)
            # Mas cresceu: o teto é para não virar barra, não para não crescer.
            self.assertGreater(pilula.width(), pilula.sizeHint().width())
        finally:
            painel.close()

    def test_a_pilula_cresce_na_proporcao_do_proprio_texto(self):
        """Senão "Feminino" ficaria do tamanho do nome de um médico."""
        self.painel.resize(1600, 900)
        self.painel.show()
        self.painel.repaint()
        largura = {c.text(): c.width()
                   for c in self._pilulas(self.painel.cabecalho.linha_chips)}
        self.assertLess(largura["Unimed"], largura["(62) 90000-0000"])

    def test_campos_comecam_recolhidos(self):
        """Oito caixas de texto na frente de quem só queria conferir quem é."""
        self.assertFalse(self.painel.caixa_edicao.isVisibleTo(self.painel))

    def test_o_botao_abre_e_fecha(self):
        self.painel._alternar_edicao_id()
        self.assertTrue(self.painel.caixa_edicao.isVisibleTo(self.painel))
        self.painel._alternar_edicao_id()
        self.assertFalse(self.painel.caixa_edicao.isVisibleTo(self.painel))

    def test_corrigir_repinta_o_chip(self):
        """Dois retratos do mesmo paciente discordando na tela é pior que um
        só desatualizado."""
        self.painel.f_convenio.setText("SUS")
        self.assertIn("SUS", self._chips(self.painel.cabecalho.linha_chips))

    def test_corrigir_nao_perde_o_dado(self):
        self.painel.f_contato.setText("(11) 91111-1111")
        self.assertEqual(self.painel.coletar().contato, "(11) 91111-1111")


@unittest.skipIf(gui is None, "PySide6/Pillow indisponíveis")
class TestFaixaDeArraste(unittest.TestCase):
    """O alvo de arraste recua depois de cumprido o seu papel."""

    def setUp(self):
        from isocentro.interface import posicionamento as pos
        self.p = pos.PainelPosicionamento()

    def tearDown(self):
        self.p.close()

    def _foto(self):
        pasta = tempfile.mkdtemp()
        caminho = os.path.join(pasta, "a.jpg")
        with open(caminho, "wb") as fh:
            fh.write(_jpeg(400, 300, (20, 90, 140)))
        return caminho

    def test_vazia_e_um_alvo_de_verdade(self):
        self.assertGreaterEqual(self.p.zona.minimumHeight(), 70)

    def test_vazia_mostra_a_saida_de_quem_nao_pode_arrastar(self):
        """Por RDP ou com o app elevado o drag-and-drop não chega."""
        self.assertIn("botão", self.p.zona.sub.text())

    def test_com_foto_recua(self):
        self.p.acrescentar_fotos([self._foto()])
        self.assertLessEqual(self.p.zona.maximumHeight(), 40)

    def test_esvaziar_devolve_o_alvo(self):
        self.p.acrescentar_fotos([self._foto()])
        self.p._remover_foto(0)
        self.assertGreaterEqual(self.p.zona.minimumHeight(), 70)
        self.assertIn("botão", self.p.zona.sub.text())

    def test_a_faixa_segue_a_aba_aberta(self):
        """Ela fala do posicionamento ATIVO, não da soma de todos."""
        self.p.acrescentar_fotos([self._foto()])
        self.p._nova_aba_setup()
        self.assertGreaterEqual(self.p.zona.minimumHeight(), 70)
        self.p.abas.setCurrentIndex(0)
        self.assertLessEqual(self.p.zona.maximumHeight(), 40)


@unittest.skipIf(gui is None, "PySide6/Pillow indisponíveis")
class TestAbaDoImobilizador(unittest.TestCase):
    """O inventário é irmão dos posicionamentos na mesma fileira de abas.

    Ele não é um posicionamento: tudo que anda por índice de aba — arrastar
    foto, remover setup, renomear — tem de saber que a última não conta.
    """

    def setUp(self):
        from isocentro.interface import posicionamento as pos
        self.p = pos.PainelPosicionamento()

    def tearDown(self):
        self.p.close()

    def _foto(self):
        pasta = tempfile.mkdtemp()
        caminho = os.path.join(pasta, "a.jpg")
        with open(caminho, "wb") as fh:
            fh.write(_jpeg(400, 300, (20, 90, 140)))
        return caminho

    def test_e_sempre_a_ultima_aba(self):
        self.assertEqual(self.p._i_aba_imob(), self.p.abas.count() - 1)
        self.p._nova_aba_setup()
        self.assertEqual(self.p._i_aba_imob(), self.p.abas.count() - 1)
        self.assertEqual(len(self.p._setups), 2)

    def test_foto_arrastada_com_ele_aberto_cai_no_posicionamento(self):
        """Soltar não pode virar erro só porque se estava olhando a prateleira."""
        self.p.abas.setCurrentIndex(self.p._i_aba_imob())
        self.assertEqual(self.p.acrescentar_fotos([self._foto()]), 1)
        self.assertTrue(self.p._setups[0]["fotos"][0])

    def test_a_faixa_diz_para_onde_a_foto_vai(self):
        self.p._setups[0]["nome"].setText("CRÂNIO")
        self.p.abas.setCurrentIndex(self.p._i_aba_imob())
        self.assertIn("CRÂNIO", self.p.zona.lbl.text())

    def test_remover_posicionamento_nao_remove_o_inventario(self):
        self.p._nova_aba_setup()
        self.p.abas.setCurrentIndex(self.p._i_aba_imob())
        self.p._remover_setup()
        self.assertEqual(len(self.p._setups), 1)
        self.assertEqual(self.p.abas.tabText(self.p._i_aba_imob()),
                         "Imobilizador")

    def test_carregar_repoe_os_setups_e_mantem_o_inventario(self):
        self.p.carregar([capa_dados.Setup(nome="PELVE"),
                         capa_dados.Setup(nome="TÓRAX")])
        self.assertEqual(self.p.abas.count(), 3)
        self.assertEqual(self.p.abas.tabText(0), "PELVE")
        self.assertEqual(self.p._i_aba_imob(), 2)

    def test_a_aba_diz_quantos_estao_vinculados(self):
        """Fechada, ela é a única coisa dizendo que há máscara vinculada."""
        from PySide6.QtCore import Qt

        for i in range(self.p.lista_imob.count()):
            item = self.p.lista_imob.item(i)
            if item.flags() & Qt.ItemIsUserCheckable:
                item.setCheckState(Qt.Checked)
                break
        self.assertIn("(1)", self.p.abas.tabText(self.p._i_aba_imob()))


@unittest.skipIf(gui is None, "PySide6/Pillow indisponíveis")
class TestPosicionamentoEmChips(unittest.TestCase):
    """O que a nota manda fazer, em cartões de ler de longe."""

    def setUp(self):
        from isocentro.dados import notas_setup
        from isocentro.interface import posicionamento as pos
        self.notas_setup = notas_setup
        notas_setup.salvar([notas_setup.Nota(
            nome="CRÂNIO",
            acessorios="MÁSCARA CURTA\nBASE B COM EXTENSOR\nAPOIO DE JOELHOS",
            preparo={"PARA O GANTRY": "Cabeça", "DECÚBITO": "Dorsal",
                     "BRAÇOS": "Ao lado corpo"})])
        self.p = pos.PainelPosicionamento()
        self.p._recarregar_notas()
        self.aba = self.p._aba()
        i = self.aba["nota"].findText("CRÂNIO")
        self.aba["nota"].setCurrentIndex(i)
        self.p._aplicar_nota(i)

    def tearDown(self):
        self.p.close()

    def _valores(self):
        """Os cartões da aba ativa, como (rótulo, valor)."""
        grade = self.aba["valores"]
        return [(w.rot.text(), w.val.text())
                for w in (grade.itemAt(k).widget()
                          for k in range(grade.count()))
                if isinstance(w, capa_tela.ui.Valor)]

    def test_o_preparo_vira_cartao(self):
        """O rótulo é a coluna: "Cheia" e "Vazio" lado a lado não dizem de quê,
        e é bexiga trocada com reto que põe o paciente errado na mesa."""
        self.assertEqual(
            [v for v in self._valores() if v[0] != "ACESSÓRIOS"],
            [("PARA O GANTRY", "Cabeça"), ("DECÚBITO", "Dorsal"),
             ("BRAÇOS", "Ao lado corpo")])

    def test_na_nao_vira_cartao(self):
        """É a ausência de preparo. Um cartão dizendo isso disputaria atenção
        com "bexiga cheia", que é instrução de verdade."""
        self.assertNotIn(capa_pdf.VAZIO, [v for _r, v in self._valores()])

    def test_os_acessorios_ficam_num_cartao_so(self):
        """Leem-se juntos ("o que vai na mesa"), e um cartão por acessório
        empurraria as fotos para fora da tela."""
        acess = [v for r, v in self._valores() if r == "ACESSÓRIOS"]
        self.assertEqual(acess, ["MÁSCARA CURTA\nBASE B COM EXTENSOR\n"
                                 "APOIO DE JOELHOS"])

    def test_campos_comecam_recolhidos(self):
        pagina = self.aba["pagina"]
        self.assertFalse(self.aba["caixa_edicao"].isVisibleTo(pagina))

    def test_o_botao_abre_e_fecha(self):
        pagina = self.aba["pagina"]
        self.p._alternar_correcao()
        self.assertTrue(self.aba["caixa_edicao"].isVisibleTo(pagina))
        self.p._alternar_correcao()
        self.assertFalse(self.aba["caixa_edicao"].isVisibleTo(pagina))

    def test_o_preparo_se_escolhe_de_uma_lista(self):
        """Combo cru fica sem seta (ver ``ui.Escolha``): as opções de bexiga,
        reto, decúbito, braços e jejum ficariam invisíveis, e o campo passaria
        por caixa de texto livre."""
        for col, w in self.aba["preparo"].items():
            self.assertIsInstance(w, capa_tela.ui.Escolha, col)
            self.assertTrue(w.isEditable(), col)   # a medida do técnico entra
            self.assertGreater(w.count(), 1, col)

    def test_valor_que_nao_cabe_no_campo_vai_para_o_tooltip(self):
        cmb = capa_tela.ui.escolha(["ACIMA DA CABEÇA COM APOIO DE BRAÇO"],
                                   editavel=True)
        cmb.resize(90, 31)
        cmb.setCurrentText("ACIMA DA CABEÇA COM APOIO DE BRAÇO")
        self.assertIn("APOIO DE BRAÇO", cmb.toolTip())
        cmb.resize(600, 31)
        cmb.setCurrentText("CHEIA")
        self.assertEqual(cmb.toolTip(), "")

    def test_corrigir_o_preparo_repinta(self):
        self.aba["preparo"]["BEXIGA"].setCurrentText("Cheia")
        self.assertIn(("BEXIGA", "Cheia"), self._valores())

    def test_o_titulo_acompanha_o_nome(self):
        self.aba["nome"].setText("CRÂNIO DIREITO")
        self.assertEqual(self.aba["titulo"].text(), "CRÂNIO DIREITO")

    def test_a_nota_fica_fora_do_painel_recolhido(self):
        """Escolher o modelo da região abre o posicionamento; não é detalhe."""
        pagina = self.aba["pagina"]
        self.assertTrue(self.aba["nota"].isVisibleTo(pagina))

    def test_nada_do_que_se_le_deixa_de_ser_coletado(self):
        setup = self.p.setups()[0]
        self.assertIn("MÁSCARA CURTA", setup.acessorios)
        self.assertEqual(setup.preparo["DECÚBITO"], "Dorsal")

    def test_cada_aba_abre_e_fecha_a_sua(self):
        """Duas montagens, dois estados: abrir uma não escancara a outra."""
        pagina1 = self.aba["pagina"]
        segunda = self.p._nova_aba_setup()
        self.p._alternar_correcao()
        self.assertTrue(segunda["caixa_edicao"].isVisibleTo(segunda["pagina"]))
        self.assertFalse(self.aba["caixa_edicao"].isVisibleTo(pagina1))


@unittest.skipIf(gui is None, "PySide6/Pillow indisponíveis")
class TestSemJanelasSoltas(unittest.TestCase):
    """Widget criado sem pai é janela de topo até o layout adotá-lo.

    O Qt o exibe nesse intervalo: uma pílula solta piscando sobre a tela a cada
    repinte. Com sete chips por paciente e um repinte por tecla digitada, isso
    aparece como popup no meio do trabalho — foi exatamente o que aconteceu.
    """

    def setUp(self):
        from PySide6.QtCore import QEvent, QObject, Qt
        from PySide6.QtWidgets import QWidget

        self.soltas = []
        vigia = self

        class Vigia(QObject):
            def eventFilter(self, obj, ev):
                if (ev.type() == QEvent.Show and isinstance(obj, QWidget)
                        and (obj.isWindow()
                             or obj.windowFlags() & Qt.Popup)):
                    vigia.soltas.append(type(obj).__name__)
                return False

        self._vigia = Vigia()
        self._buscar = capa_dados.buscar
        capa_dados.buscar = lambda registro, nome, nascimento="": _resultado_cheio()
        self.j = gui.JanelaPrincipal(usuario=_USUARIO)
        self.j._trocar_modo(fichinha.MODO_CAPA)
        self.j.capa.definir_pacientes([_Ref()])
        self.j.capa.busca.setText("paciente")
        _APP.processEvents()
        _APP.installEventFilter(self._vigia)   # só depois da montagem

    def tearDown(self):
        _APP.removeEventFilter(self._vigia)
        capa_dados.buscar = self._buscar
        self.j.close()

    def test_escolher_o_paciente_nao_abre_janela_nenhuma(self):
        self.j.capa.lista_pac.setCurrentRow(0)
        _esperar()
        self.assertEqual(self.soltas, [])

    def test_digitar_acessorios_nao_pisca_pilulas(self):
        aba = self.j.capa.posicionamento._aba()
        aba["acessorios"].setPlainText("RAMPA 15\nAPOIO DE JOELHO\nBASE B")
        _APP.processEvents()
        self.assertEqual(self.soltas, [])

    def test_corrigir_a_identificacao_nao_pisca_pilulas(self):
        self.j.capa.f_convenio.setText("SUS")
        self.j.capa.f_contato.setText("(11) 90000-0000")
        _APP.processEvents()
        self.assertEqual(self.soltas, [])

    def test_trocar_de_arranjo_nao_pisca_cartoes(self):
        """Mudar de coluna reparenta os cartões — e reparentar sem layout que
        os adote os exibe como janela solta no intervalo."""
        c = self.j.capa
        c._arrumar_colunas(False)    # uma coluna só
        _APP.processEvents()
        c._arrumar_colunas(True)     # duas colunas de novo
        _APP.processEvents()
        self.assertEqual(self.soltas, [])


@unittest.skipIf(gui is None, "PySide6/Pillow indisponíveis")
class TestColunasDaCapa(unittest.TestCase):
    """A tela larga põe as fotos ao lado do documento, não abaixo dele.

    Numa coluna só, o cartão do posicionamento ficava fora da primeira tela: as
    fotos do setup — o que o técnico abre a Capa para conferir — só apareciam
    rolando a página.
    """

    def setUp(self):
        from PySide6.QtCore import Qt

        self.painel = capa_tela.PainelCapa()
        # O Qt só entrega o ``resizeEvent`` a widget mostrado; sem isto o
        # arranjo nunca seria recalculado. ``WA_DontShowOnScreen`` dá o ciclo
        # de vida completo sem abrir janela na tela de quem roda os testes.
        self.painel.setAttribute(Qt.WA_DontShowOnScreen, True)
        self.painel.show()

    def tearDown(self):
        self.painel.close()

    def _coluna_de(self, w):
        """Em qual das duas colunas o cartão está agora."""
        for nome, col in (("esq", self.painel._col_esq),
                          ("dir", self.painel._col_dir)):
            if w.parentWidget() is col:
                return nome
        return "?"

    def _com_largura(self, largura):
        """Refaz o arranjo como se a tela tivesse esta largura.

        ``resize`` não serve aqui: sem gerenciador de janelas a fonte de
        fallback impõe à tela um mínimo de mais de mil e setecentos pixels, e
        o pedido de encolher é ignorado. O que se quer testar é a regra, não a
        métrica da fonte da máquina que roda os testes.
        """
        self.painel.width = lambda: largura
        self.painel._arrumar_colunas(self.painel._cabem_duas_colunas())
        _APP.processEvents()

    def test_tela_larga_poe_o_posicionamento_ao_lado(self):
        self.painel.definir_modo(capa_tela.COMPLETA)
        self._com_largura(1600)
        self.assertTrue(self.painel._duas_colunas)
        self.assertEqual(self._coluna_de(self.painel.posicionamento), "dir")
        self.assertEqual(self._coluna_de(self.painel.cartao_curso), "esq")

    def test_tela_estreita_volta_a_uma_coluna(self):
        """Duas colunas de 400 px devolveriam a foto ao tamanho de selo."""
        self.painel.definir_modo(capa_tela.COMPLETA)
        self._com_largura(900)
        self.assertFalse(self.painel._duas_colunas)
        self.assertEqual(self._coluna_de(self.painel.posicionamento), "esq")
        self.assertFalse(self.painel._col_dir.isVisibleTo(self.painel))

    def test_o_cadastro_de_simulacao_nao_usa_duas_colunas(self):
        """Não há duas colunas de conteúdo: curso e prescrições ainda não
        existem, e a identificação sozinha deixaria a esquerda vazia até o
        rodapé. Empilhado, a montagem pega a largura inteira."""
        self.painel.definir_modo(capa_tela.SIMULACAO)
        self._com_largura(1600)
        self.assertFalse(self.painel._duas_colunas)
        self.assertEqual(self._coluna_de(self.painel.posicionamento), "esq")

    def test_o_que_estava_escondido_continua_escondido(self):
        """Trocar de arranjo não pode trazer de volta o cartão que o modo
        Simulação tirou de cena — seria a capa pela metade na tomografia."""
        self.painel.definir_modo(capa_tela.COMPLETA)
        self.painel.definir_modo(capa_tela.SIMULACAO)
        for largura in (1600, 900, 1600):
            self._com_largura(largura)
            self.assertFalse(
                self.painel.cartao_curso.isVisibleTo(self.painel), largura)
            self.assertFalse(
                self.painel.cartao_presc.isVisibleTo(self.painel), largura)


@unittest.skipIf(gui is None, "gui indisponível (PySide6?)")
class TestAvisoDeSexoIndefinido(unittest.TestCase):
    """A cor da faixa do nome na capa impressa É a informação do sexo: vermelha
    (feminino), azul (masculino) ou neutra quando não se sabe. Sem sexo, a tela
    reclama — senão a folha sai cinza e ninguém descobre antes de imprimir."""

    def setUp(self):
        self.painel = capa_tela.PainelCapa()

    def tearDown(self):
        self.painel.close()
        self.painel.deleteLater()
        _APP.processEvents()

    def _avisos(self) -> list[str]:
        lst = self.painel.lista_avisos
        return [lst.item(i).text() for i in range(lst.count())]

    @staticmethod
    def _fala_de_sexo(avisos) -> bool:
        # A lista prefixa com "⚠ " — comparar por trecho, não pelo começo.
        return any("Sexo não informado" in a for a in avisos)

    def test_sem_sexo_avisa(self):
        self.painel.carregar(capa_pdf.Capa(nome="FULANO DE TAL", sexo=""))
        self.assertTrue(self._fala_de_sexo(self._avisos()), self._avisos())

    def test_com_sexo_nao_avisa(self):
        for sexo in ("Feminino", "Masculino", "F", "M"):
            with self.subTest(sexo=sexo):
                self.painel.carregar(capa_pdf.Capa(nome="FULANO", sexo=sexo))
                self.assertFalse(self._fala_de_sexo(self._avisos()))

    def test_sem_paciente_nao_reclama_de_nada(self):
        # Tela em branco não é pendência: ainda não há caso.
        self.painel.carregar(capa_pdf.Capa())
        self.assertFalse(self._fala_de_sexo(self._avisos()))

    def test_acompanha_a_escolha(self):
        # Soltar o seletor acende o aviso na hora, não na próxima busca.
        self.painel.carregar(capa_pdf.Capa(nome="FULANO", sexo="Feminino"))
        self.assertFalse(self._fala_de_sexo(self._avisos()))
        self.painel.f_sexo.setCurrentIndex(-1)
        _APP.processEvents()
        self.assertTrue(self._fala_de_sexo(self._avisos()), self._avisos())
        self.painel.f_sexo.setCurrentText("Masculino")
        _APP.processEvents()
        self.assertFalse(self._fala_de_sexo(self._avisos()))

    def test_nao_engole_os_avisos_da_busca(self):
        # Os da tela entram JUNTO com os dos relatórios, não no lugar deles.
        self.painel.carregar(capa_pdf.Capa(nome="FULANO", sexo=""))
        self.painel.mostrar_avisos(["Sem prescrição aprovada"])
        avisos = self._avisos()
        self.assertTrue(self._fala_de_sexo(avisos), avisos)
        self.assertTrue(any("Sem prescrição" in a for a in avisos), avisos)


@unittest.skipIf(gui is None, "PySide6/Pillow indisponíveis")
class TestNotaDaPrescricaoEmVariasLinhas(unittest.TestCase):
    """A nota do ARIA tem de três a sete linhas, e o campo era de uma só.

    No ``QLineEdit`` as quebras sumiam na edição: a capa saía com a nota
    emendada numa linha, encolhida até caber, ilegível na sala (R-70).
    """

    _NOTA = "T2N0M0\nApós QT\nBoost sequencial"

    def setUp(self):
        self.p = capa_tela.PainelCapa()
        self.p.carregar(capa_pdf.Capa(nome="FULANO", registro="1X", blocos=[
            capa_pdf.Bloco(titulo="Mama", notas=self._NOTA)]))
        self.w = self.p._widgets_blocos[0]

    def tearDown(self):
        self.p.close()

    def test_quebras_voltam_ao_pdf(self):
        self.assertEqual(self.w["notas"].toPlainText(), self._NOTA)
        self.assertEqual(self.p.coletar().blocos[0].notas, self._NOTA)

    def test_passar_do_limite_e_recusado_e_anunciado(self):
        cheia = "x" * (capa_tela.MAX_CARACTERES_NOTA - 1)
        self.w["notas"].setPlainText(cheia)
        self.w["notas"].setPlainText(cheia + "yz")
        self.assertEqual(self.w["notas"].toPlainText(), cheia)
        self.assertIn(str(capa_tela.MAX_CARACTERES_NOTA),
                      self.p.lbl_status.text())

    def test_nota_que_ja_chegou_grande_pode_encolher(self):
        """Recusar toda edição acima do limite travaria a nota: nem apagar daria."""
        grande = "x" * (capa_tela.MAX_CARACTERES_NOTA + 10)
        self.p.carregar(capa_pdf.Capa(nome="FULANO", registro="1X", blocos=[
            capa_pdf.Bloco(titulo="Mama", notas=grande)]))
        notas = self.p._widgets_blocos[0]["notas"]
        self.assertEqual(notas.toPlainText(), grande, "chegou inteira")
        notas.setPlainText(grande[:-5])
        self.assertEqual(len(notas.toPlainText()), len(grande) - 5)

    def test_contador_avisa_quando_a_folha_nao_comporta(self):
        cabem = capa_pdf._MAX_LINHAS_NOTA
        self.w["notas"].setPlainText("\n".join(f"l{i}" for i in range(cabem + 2)))
        texto = self.w["contador"].text()
        self.assertIn(f"{cabem + 2} linhas", texto)
        self.assertIn(f"{cabem} cabem", texto)

    def test_sem_nota_o_contador_some(self):
        self.w["notas"].setPlainText("")
        self.assertTrue(self.w["contador"].isHidden())


# Esvazia ``estilo._ouvintes`` entre um teste e o seguinte. Sem isto, a lista
# cresce durante o arquivo inteiro e cada repintura percorre tudo o que já se
# acumulou — ver ``tests/limpeza_de_tela.py`` para os números.
from tests.limpeza_de_tela import load_tests  # noqa: E402,F401
