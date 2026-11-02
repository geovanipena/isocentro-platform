"""Fumaça do gui: garante que helpers de módulo chamados por slots Qt existem
e que a limpeza do tratamento reaberto (que abortava o app quando a função
sumiu) roda de ponta a ponta.

Importa o gui em modo headless (offscreen); pula se PyQt5 não estiver presente.

Rodar:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import datetime
import inspect
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("ISOCENTRO_USERS_DIR", tempfile.mkdtemp())

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    _APP = QApplication.instance() or QApplication([])
    from isocentro.dominio import agendamento as ag  # noqa: E402
    from isocentro.interface import arranque  # noqa: E402
    from isocentro.interface.caso import Caso  # noqa: E402
    from isocentro.interface import controle_capa  # noqa: E402
    from isocentro.interface import controle_viewer  # noqa: E402
    from isocentro.interface import controle_virtual  # noqa: E402
    from isocentro.interface import gui  # noqa: E402
    from isocentro.dados import equipe  # noqa: E402
    from isocentro.dominio import gatilho_registro as _gr  # noqa: E402
    from isocentro.interface import fichinha as _fich  # noqa: E402
except Exception as exc:  # noqa: BLE001
    gui = None
    _MOTIVO = str(exc)


def _pode_imprimir(painel, pasta) -> bool:
    """A Impressão do caso montado — o que era ``fichinha.btn_imprimir``.

    Até a v7 a trilha era uma grade de botões do cartão e bastava perguntar ao
    widget. Na v8 ela é o ícone 🖨 da LINHA da Documentação, e "acesa" passou a
    depender de QUAL linha: a Impressão só vale para a linha do caso que está
    montado. Esta função monta a linha daquela pasta e pergunta o mesmo.
    """
    entrada = {"automacao": {"estado": _gr.PRONTA, "pasta": str(pasta),
                             "avisos": [], "planos": ["P1"], "desde": ""}}
    return _fich.IMPRIMIR in painel._acoes_da_documentacao(entrada)


@unittest.skipIf(gui is None, "gui indisponível (PySide6?)")
class TestPngDaFichaSalva(unittest.TestCase):
    """Os cortes e o DVH que a Ficha Virtual mostra vivem DENTRO do zip.

    O índice central guarda o endereço do arquivo SOLTO mesmo depois de ele ser
    arquivado — é a convenção do módulo, e serve para a reabertura achar a
    pasta. Só que arquivar é o caminho normal: o zip nasce e os soltos somem.
    Lendo apenas o disco, o cartão ficava vazio para toda ficha já salva, que
    são todas exceto as do minuto seguinte à geração (medido com a paciente
    9000001CEL em 21/08/2026).
    """

    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.d, True)

    def test_le_de_dentro_do_zip(self):
        import zipfile
        alvo = self.d / "CORTES_FULANO_v1_21-08-2026.png"
        with zipfile.ZipFile(self.d / "ARQUIVOS_FULANO_1X.zip", "w") as zf:
            zf.writestr(alvo.name, b"conteudo-do-png")
        self.assertFalse(alvo.exists())          # solto NÃO existe: é o caso
        self.assertEqual(controle_virtual.png_do_indice(str(alvo)),
                         b"conteudo-do-png")

    def test_solto_tem_precedencia(self):
        """Ficha recém-gerada, ainda não arquivada: lê o arquivo da pasta."""
        alvo = self.d / "CORTES_FULANO_v2_21-08-2026.png"
        alvo.write_bytes(b"solto")
        self.assertEqual(controle_virtual.png_do_indice(str(alvo)),
                         b"solto")

    def test_sem_ficha_nenhuma_devolve_None(self):
        self.assertIsNone(controle_virtual.png_do_indice(None))
        self.assertIsNone(controle_virtual.png_do_indice(
            str(self.d / "nao_existe.png")))

    def test_zip_corrompido_nao_derruba_a_aba(self):
        alvo = self.d / "CORTES_FULANO_v3_21-08-2026.png"
        (self.d / "ARQUIVOS_FULANO_1X.zip").write_bytes(b"isto nao e um zip")
        self.assertIsNone(controle_virtual.png_do_indice(str(alvo)))


@unittest.skipIf(gui is None, "gui indisponível (PySide6?)")
class TestTratamentoSemDado(unittest.TestCase):
    """Paciente sem tratamento lido não pode DERRUBAR a escolha.

    ``tratamento_do_paciente`` devolve ``None`` quando não há o que mostrar, e
    o painel sabe tratar isso ("não deu para saber"). Quem compõe o quadro na
    janela precisa checar antes de escrever em ``t`` — sem o teste, escrever
    num ``None`` levantava AttributeError no meio do slot e o paciente
    recém-escolhido simplesmente não abria, sem mensagem nenhuma (21/08/2026).
    """

    def test_o_quadro_aceita_None(self):
        import inspect
        fonte = inspect.getsource(controle_virtual.ControleFichaVirtual.buscar)
        # A atribuição de campos em ``t`` tem de estar sob uma guarda de None.
        self.assertIn("if t is not None:", fonte)
        pos_guarda = fonte.index("if t is not None:")
        self.assertLess(pos_guarda, fonte.index("t.respiratorio"),
                        "campo escrito em t antes da guarda de None")


@unittest.skipIf(gui is None, "gui indisponível (PySide6?)")
class TestFichaVirtualSegueOFoco(unittest.TestCase):
    """A aba tem de mostrar o MESMO paciente que as outras três.

    Relatado em 22/08/2026: "aba ficha virtual não está síncrona com as
    outras". A primeira versão seguia só a BANCADA da Ficha Total, e só quando
    o registro dela mudava desde a última vez — então (a) escolher paciente na
    busca da Capa não levava nada para cá, e (b) depois de buscar alguém aqui
    dentro a aba ficava presa a ele. O resultado na tela do usuário foram duas
    identidades ao mesmo tempo: a Ficha Virtual num paciente, o rodapé
    anunciando o tratamento de outro. Numa tela de conferência, isso é o pior
    defeito possível.
    """

    def setUp(self):
        from isocentro.banco import capa_dados
        self.capa_dados = capa_dados
        self.j = gui.JanelaPrincipal(
            usuario={"usuario": "t", "nome": "T", "papel": "fisico"})
        self.addCleanup(self.j.deleteLater)
        # A aba avisa a janela para buscar o tratamento no banco, que não existe
        # aqui. O que se mede é QUEM ela assumiu, não o que o banco responde.
        self.j.ficha_virtual.paciente_escolhido.disconnect()
        self.j.controle_virtual._refs_tratamento = [
            capa_dados.PacienteRef(registro="1111CEL", nome="Antonio de Souza"),
            capa_dados.PacienteRef(registro="2222CEL", nome="Maria Oliveira")]

    def test_o_paciente_escolhido_na_capa_chega_na_ficha_virtual(self):
        """A Capa é a porta de quem vem da tomografia, e tem busca própria.

        Antes só a bancada contava: quem chegasse pela Capa abria a Ficha
        Virtual em branco, com o paciente já na tela ao lado.
        """
        self.j.capa.f_registro.setText("2222CEL")
        self.j.controle_virtual.seguir_o_foco()
        self.assertEqual(self.j.ficha_virtual.registro_na_tela(), "2222CEL")

    def test_voltar_para_a_aba_repoe_o_paciente_da_vez(self):
        """Buscar alguém aqui dentro não pode congelar a aba nele.

        Sair e voltar traz de volta quem está na frente nas outras telas —
        mesmo sendo o mesmo registro de antes, que era exatamente a trava
        anterior ("só quando a bancada MUDA").
        """
        self.j.form.pac_registro.setText("1111CEL")
        self.j.controle_virtual.seguir_o_foco()
        self.assertEqual(self.j.ficha_virtual.registro_na_tela(), "1111CEL")
        # A pessoa consulta outro paciente pela busca da própria aba…
        self.j.ficha_virtual.assumir_paciente(self.j.controle_virtual._refs_tratamento[1])
        self.assertEqual(self.j.ficha_virtual.registro_na_tela(), "2222CEL")
        # …e ao voltar a aba mostra de novo o da bancada.
        self.j.controle_virtual.seguir_o_foco()
        self.assertEqual(self.j.ficha_virtual.registro_na_tela(), "1111CEL")

    def test_campo_limpo_nao_apaga_o_paciente_da_vez(self):
        """Carregar um caso ZERA os campos antes de preenchê-los.

        Tratando a string vazia como "não há paciente", o foco viraria nada no
        meio da carga — e a aba abriria em branco por causa de um estado
        transitório de outra tela.
        """
        self.j.capa.f_registro.setText("2222CEL")
        self.j.form.pac_registro.setText("")
        self.assertEqual(self.j.controle_virtual._paciente_em_foco, "2222CEL")

    def test_paciente_fora_do_banco_deixa_a_aba_como_estava(self):
        """TC de teste e cadastro novo não estão no data warehouse.

        Não é erro: a aba fica como estava e a busca continua ali. Limpar a
        tela aqui apagaria uma consulta legítima por causa de um caso que esta
        aba nem alcança.
        """
        self.j.form.pac_registro.setText("1111CEL")
        self.j.controle_virtual.seguir_o_foco()
        self.j.form.pac_registro.setText("9999XXX")
        self.j.controle_virtual.seguir_o_foco()
        self.assertEqual(self.j.ficha_virtual.registro_na_tela(), "1111CEL")


@unittest.skipIf(gui is None, "gui indisponível (PySide6?)")
class TestFecharPacienteFechaNaFichaVirtual(unittest.TestCase):
    """Fechar em uma tela tem de fechar em TODAS — a Virtual inclusive.

    Relatado em 31/08/2026: "ao fechar paciente em fichinha, total ou capa-up
    precisa fechar em Virtual completamente". As três portas de fechar
    descarregavam a bancada e a Capa e deixavam a Ficha Virtual com o paciente
    inteiro na tela — e, pior, com o FOCO apontando para ele: mesmo limpando a
    aba, a próxima troca de aba o trazia de volta sozinho.
    """

    def setUp(self):
        from isocentro.banco import capa_dados
        self.j = gui.JanelaPrincipal(
            usuario={"usuario": "t", "nome": "T", "papel": "fisico"})
        self.addCleanup(self.j.deleteLater)
        self.j.ficha_virtual.paciente_escolhido.disconnect()
        self.j.controle_virtual._refs_tratamento = [
            capa_dados.PacienteRef(registro="1111CEL", nome="Antonio de Souza")]
        self.j.form.pac_registro.setText("1111CEL")
        self.j.controle_virtual.seguir_o_foco()
        # A régua: o paciente ESTÁ na aba antes de cada teste fechar.
        self.assertEqual(self.j.ficha_virtual.registro_na_tela(), "1111CEL")

    def test_limpar_a_bancada_fecha_na_virtual(self):
        """É a porta do × da Fichinha e a do Limpar da Total: as duas passam
        por ``_executar_limpeza``."""
        self.j._executar_limpeza()
        self.assertEqual(self.j.ficha_virtual.registro_na_tela(), "")

    def test_fechar_na_capa_fecha_na_virtual(self):
        self.j.capa._fechar_paciente()
        self.assertEqual(self.j.ficha_virtual.registro_na_tela(), "")

    def test_o_paciente_fechado_nao_volta_na_troca_de_aba(self):
        """O defeito de verdade não é a tela — é o FOCO.

        ``ControleFichaVirtual.seguir_o_foco`` remonta a aba a cada vez que ela aparece.
        Limpar a tela e deixar o foco fazia o paciente fechado voltar sozinho —
        pior que não ter fechado, porque agora ninguém está esperando por ele.
        """
        self.j._executar_limpeza()
        self.j.controle_virtual.seguir_o_foco()
        self.assertEqual(self.j.ficha_virtual.registro_na_tela(), "")
        self.assertEqual(self.j.controle_virtual._paciente_em_foco, "")

    def test_abrir_outro_paciente_depois_de_fechar(self):
        """Fechar não pode deixar a aba surda: o próximo paciente entra."""
        from isocentro.banco import capa_dados
        self.j._executar_limpeza()
        self.j.controle_virtual._refs_tratamento.append(
            capa_dados.PacienteRef(registro="2222CEL", nome="Maria Oliveira"))
        self.j.form.pac_registro.setText("2222CEL")
        self.j.controle_virtual.seguir_o_foco()
        self.assertEqual(self.j.ficha_virtual.registro_na_tela(), "2222CEL")


@unittest.skipIf(gui is None, "gui indisponível (PySide6?)")
class TestChecklistNaFichaVirtual(unittest.TestCase):
    """A conferência marcada na aba tem de CHEGAR AO DISCO e voltar.

    A janela é quem lê e grava (a tela só pede), e o cartão da fileira é quem
    responde "este paciente já passou pela conferência?". Se a marcação não
    voltasse para ele, a resposta velha ficaria na tela — justo a que alguém
    lê de relance, com o paciente na porta.
    """

    def setUp(self):
        from isocentro.interface import checklist
        from isocentro.banco import tratamento_db
        self.ck = checklist
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self._antes = os.environ.get("ISOCENTRO_CHECKLIST")
        os.environ["ISOCENTRO_CHECKLIST"] = self.d
        self.addCleanup(self._repor)
        self._verificado = tratamento_db.VERIFICADO_EM
        tratamento_db.VERIFICADO_EM = "01/01/2026"
        self.addCleanup(setattr, tratamento_db, "VERIFICADO_EM",
                        self._verificado)
        self.j = gui.JanelaPrincipal(
            usuario={"usuario": "ivone", "nome": "Ivone", "papel": "fisico"})
        self.addCleanup(self.j.deleteLater)
        curso = tratamento_db.Curso(id=7, nome="C1", entregues=2, previstas=5,
                                    atual=True)
        self.j.ficha_virtual._registro = "9000005CEL"
        self.j.ficha_virtual.mostrar(tratamento_db.Tratamento(
            registro="9000005CEL", curso=curso, cursos=[curso],
            entregues=2, previstas=5,
            sessoes=[tratamento_db.Sessao(
                fracao=1, data=datetime.date(2026, 8, 20))]))

    def _repor(self):
        if self._antes is None:
            os.environ.pop("ISOCENTRO_CHECKLIST", None)
        else:
            os.environ["ISOCENTRO_CHECKLIST"] = self._antes

    def test_marcar_grava_e_o_cartao_acompanha(self):
        self.j.controle_virtual.checklist_cartao()
        self.assertEqual(
            self.j.ficha_virtual.btn_checklist.val.text(), "por conferir")
        self.j.controle_virtual.checklist_marcar(self.ck.ITENS[0], "C")
        self.assertEqual(
            self.j.ficha_virtual.btn_checklist.val.text(), "1 de 6")
        for item in self.ck.ITENS[1:]:
            self.j.controle_virtual.checklist_marcar(item, "C")
        self.assertEqual(
            self.j.ficha_virtual.btn_checklist.val.text(), "conferido")
        gravado = self.ck.ler("9000005CEL", 7)
        self.assertEqual(len(gravado), len(self.ck.ITENS))

    def test_assina_com_o_usuario_da_SESSAO(self):
        """Atribuir a conferência a quem não a fez é o mesmo erro de atribuir
        a sessão a quem não tratou — e aqui ninguém percebe pelo resultado."""
        self.j.controle_virtual.checklist_marcar(self.ck.ITENS[0], "C")
        dado = self.ck.ler("9000005CEL", 7)[self.ck.ITENS[0]]
        self.assertEqual(dado["por"], "ivone")

    def test_a_conferencia_e_do_CURSO_que_esta_na_tela(self):
        """Trocar de curso no seletor troca de checklist: um curso concluído
        conferido não pode fazer o replanejamento nascer com aval."""
        self.j.controle_virtual.checklist_marcar(self.ck.ITENS[0], "C")
        self.assertEqual(self.ck.andamento(self.ck.ler("9000005CEL", 7))[0], 1)
        self.assertEqual(self.ck.andamento(self.ck.ler("9000005CEL", 9))[0], 0)

    def test_sem_curso_a_janela_nao_grava_nada(self):
        """A aba mostra o cartão apagado, e o caminho de gravação também
        recusa: uma tela nova amanhã não pode reabrir o buraco em silêncio."""
        self.j.ficha_virtual._curso_na_tela = None
        self.j.controle_virtual.checklist_marcar(self.ck.ITENS[0], "C")
        self.j.controle_virtual.checklist_cartao()
        self.assertFalse(self.j.ficha_virtual.btn_checklist._ativo)
        self.assertEqual(self.ck.ler("9000005CEL", None), {})


@unittest.skipIf(gui is None, "gui indisponível (PySide6?)")
class TestCamposDaFichaVirtual(unittest.TestCase):
    """Os campos da pág. 2 vêm da ficha JÁ ELABORADA, inclusive ARQUIVADA.

    Arquivar é o caminho normal: o zip é criado e os arquivos soltos somem.
    Lendo só o disco solto, o botão ficaria apagado para todo paciente cuja
    ficha já foi salva — que são quase todos.
    """

    def setUp(self):
        from isocentro.dados import indice
        self.indice = indice
        self.original = indice.listar_versoes
        self.addCleanup(setattr, indice, "listar_versoes", self.original)
        self.d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.d, True)
        self.j = gui.JanelaPrincipal(
            usuario={"usuario": "t", "nome": "T", "papel": "fisico"})
        self.addCleanup(self.j.deleteLater)

    def _gravar_ficha(self, dentro_do_zip: bool) -> None:
        import json
        import zipfile
        reg = {"versoes": [{
            "versao": 2, "data": "25-08-2026",
            "dados": {"gating": "Sim", "gating_modalidade": "Breath-Hold"},
            "plano_rp": {"rotulo_plano": "sABD_DIBH", "num_fracoes": 5,
                         "ssd_tp0_g0": 98.4,
                         "feixes": [{"fase": 1, "ssd": 98.4, "colimador": 0,
                                     "gantry": 300, "um": 245.7}]}}]}
        texto = json.dumps(reg, ensure_ascii=False)
        if dentro_do_zip:
            with zipfile.ZipFile(self.d / "ARQUIVOS_X_1X.zip", "w") as zf:
                zf.writestr("FICHA_X_1X.json", texto)
        else:
            (self.d / "FICHA_X_1X.json").write_text(texto, encoding="utf-8")
        self.indice.listar_versoes = lambda r: [
            {"json_path": str(self.d / "FICHA_X_1X.json")}]

    def test_le_a_ficha_ARQUIVADA_dentro_do_zip(self):
        self._gravar_ficha(dentro_do_zip=True)
        versao = self.j.controle_virtual.versao_da_ficha("1X")
        self.assertEqual(versao.get("versao"), 2)
        self.assertTrue(versao["plano_rp"]["feixes"])

    def test_sem_ficha_o_botao_fica_apagado(self):
        """Botão aceso significa pronto: sem ficha salva o clique só teria um
        aviso para dar, e o motivo cabe no tooltip."""
        self.indice.listar_versoes = lambda r: []
        self.assertEqual(self.j.controle_virtual.versao_da_ficha("1X"), {})

    def test_o_resumo_do_plano_omite_campo_SEM_fonte(self):
        """Rótulo com valor vazio promete um dado que a ficha não gravou — e
        esta janela é de conferência."""
        resumo = dict(controle_virtual.resumo_do_plano(
            {"gating": "Sim"}, {"rotulo_plano": "sABD", "num_fracoes": 5}))
        self.assertEqual(resumo["Gating"], "Sim")
        self.assertNotIn("Modalidade", resumo)
        self.assertNotIn("SSD TP0 (cm)", resumo)

    def test_trio_de_ssd_sai_junto_como_UM_dado(self):
        """As três posições de gantry são a mesma medida. Um "— / — / —" na
        tela gastaria um cartão para dizer que a ficha não gravou nada."""
        self.assertEqual(
            controle_virtual.trio({"ssd_tp0_g0": 98.4, "ssd_tp0_g90": 99.1},
                      [("G0", "ssd_tp0_g0"), ("G270", "ssd_tp0_g270"),
                       ("G90", "ssd_tp0_g90")]),
            [("G0", "98,4"), ("G270", ""), ("G90", "99,1")])
        self.assertEqual(
            controle_virtual.trio({}, [("G0", "ssd_tp0_g0"), ("G90", "ssd_tp0_g90")]), [])

    def test_o_trio_leva_o_EIXO_junto_do_numero_e_a_unidade_no_rotulo(self):
        """Era "SSD TP0 G0/G270/G90 → 90,1 / 85,3 / 84,8": para saber de quem
        era o 85,3 contava-se a posição na barra e a posição no rótulo, e a
        unidade não estava escrita em lugar nenhum da tela."""
        resumo = dict(controle_virtual.resumo_do_plano(
            {}, {"ssd_tp0_g0": 90.1, "ssd_tp0_g270": 85.3,
                 "ssd_tp0_g90": 84.8, "desl_long": -7.0}))
        self.assertEqual(resumo["SSD TP0 (cm)"],
                         [("G0", "90,1"), ("G270", "85,3"), ("G90", "84,8")])
        self.assertEqual(resumo["Deslocamento (cm)"],
                         [("Lat.", ""), ("Long.", "-7,0"), ("Vert.", "")])
        self.assertNotIn("SSD Iso (cm)", resumo)


@unittest.skipIf(gui is None, "gui indisponível (PySide6?)")
class TestPastaDaFicha(unittest.TestCase):
    """De onde saem as fotos de posicionamento quando não houve cadastro.

    Elas ficam SOLTAS na pasta do caso, ao lado da nota .docx — e a Ficha
    Virtual não tem pasta aberta nenhuma, só o registro. O endereço vem do
    índice central, o mesmo de onde ela já lê os cortes. Sem este caminho o
    cartão sumia em paciente que TEM posicionamento registrado (9000001CEL,
    21/08/2026).
    """

    def setUp(self):
        from isocentro.dados import indice
        self.indice = indice
        self.original = indice.listar_versoes
        self.addCleanup(setattr, indice, "listar_versoes", self.original)
        self.d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.d, True)

    def test_devolve_a_pasta_do_json(self):
        alvo = self.d / "FICHA_FULANO_1X.json"
        self.indice.listar_versoes = lambda _r: [{"json_path": str(alvo)}]
        self.assertEqual(controle_virtual.pasta_da_ficha("1X"), str(self.d))

    def test_pasta_que_sumiu_nao_vira_endereco(self):
        """O índice é derivado: a pasta de origem pode ter sido movida."""
        self.indice.listar_versoes = lambda _r: [
            {"json_path": r"Z:\nao\existe\FICHA_X.json"}]
        self.assertEqual(controle_virtual.pasta_da_ficha("1X"), "")

    def test_sem_ficha_no_indice_devolve_vazio(self):
        self.indice.listar_versoes = lambda _r: []
        self.assertEqual(controle_virtual.pasta_da_ficha("1X"), "")


@unittest.skipIf(gui is None, "gui indisponível (PySide6?)")
class TestLimparTempZip(unittest.TestCase):
    def test_existe_e_e_modulo(self):
        self.assertTrue(callable(getattr(gui, "_limpar_temp_zip", None)))

    def test_robusto(self):
        gui._limpar_temp_zip(None)                 # não levanta
        gui._limpar_temp_zip("/caminho/inexistente")   # não levanta
        d = tempfile.mkdtemp()
        gui._limpar_temp_zip(d)
        self.assertFalse(os.path.isdir(d))         # removeu de fato


@unittest.skipIf(gui is None, "gui indisponível (PySide6?)")
class TestSessaoTomadaNaJanela(unittest.TestCase):
    """Sessão tomada por outra estação: fechar não pode perguntar nada.

    O ``closeEvent`` pergunta pelo caso carregado, e uma das respostas é
    "Continuar trabalhando" — que manteria de pé, nesta estação, a sessão que
    acabou de ser encerrada na outra. Era a versão anterior deste caminho, que
    travava a tela: o programa ficava DE PÉ onde a pessoa não estava mais, e
    janela travada a que ninguém volta não encerra acesso nenhum.
    """

    def setUp(self):
        # O histórico é COMPARTILHADO e o ``closeEvent`` grava nele: sem
        # desviar, a suíte escreveria "app_fechado" no arquivo do serviço.
        self._d = tempfile.mkdtemp(prefix="gui_sessao_")
        self._antes = os.environ.get("ISOCENTRO_LOG_DIR")
        os.environ["ISOCENTRO_LOG_DIR"] = self._d
        self._confirmar = gui.ui.confirmar
        self.perguntas = []

        def _falsa(*a, **k):
            self.perguntas.append(a[1] if len(a) > 1 else "")
            return False        # "Continuar trabalhando"

        gui.ui.confirmar = _falsa

    def tearDown(self):
        # Devolver a função, nunca ``del``: o ``del`` sumiria com a original.
        gui.ui.confirmar = self._confirmar
        if self._antes is None:
            os.environ.pop("ISOCENTRO_LOG_DIR", None)
        else:
            os.environ["ISOCENTRO_LOG_DIR"] = self._antes
        shutil.rmtree(self._d, ignore_errors=True)

    def _janela_com_caso(self):
        j = gui.JanelaPrincipal(
            usuario={"usuario": "t", "nome": "T", "papel": "fisico"})
        j.caso.dados = {"pac_nome": "Fulano na Bancada"}
        return j

    def test_com_a_sessao_minha_o_caso_ainda_e_perguntado(self):
        j = self._janela_com_caso()
        try:
            self.assertFalse(j.close())          # recusou: a janela fica
            self.assertEqual(len(self.perguntas), 1)
        finally:
            j.deleteLater()

    def test_com_a_sessao_tomada_fecha_sem_perguntar(self):
        j = self._janela_com_caso()
        try:
            j._sessao_perdida = True
            self.assertTrue(j.close())           # fechou, com caso na tela
            self.assertEqual(self.perguntas, [])
        finally:
            j.deleteLater()


@unittest.skipIf(gui is None, "gui indisponível (PySide6?)")
class TestLimpezaNaJanela(unittest.TestCase):
    """_executar_limpeza e closeEvent são slots; um NameError aqui aborta o app."""

    def test_executar_limpeza_nao_aborta(self):
        j = gui.JanelaPrincipal(usuario={"usuario": "t", "nome": "T", "papel": "fisico"})
        try:
            d = tempfile.mkdtemp()
            j.caso.tmp_extraido = d
            j._executar_limpeza()   # exercita _limpar_temp_zip via slot
            self.assertFalse(os.path.isdir(d))
            self.assertIsNone(j.caso.tmp_extraido)
        finally:
            j.deleteLater()

    def test_reabrir_registro_da_pasta_carrega_a_ultima_versao(self):
        # Item 4: abrir uma pasta que já tem a ficha salva → reabre a ficha
        # anterior (a última versão) sem passar pelo scan de DICOM.
        from isocentro.dados import registro_json as rj
        j = gui.JanelaPrincipal(usuario={"usuario": "t", "nome": "T", "papel": "fisico"})
        try:
            pasta = tempfile.mkdtemp()
            dados = {"pac_nome": "Fulano Reaberto", "pac_registro": "R42",
                     "proto_imagem": "CBCT"}
            rj.salvar_versao(pasta, dados, {"maquina": "M", "num_fracoes": 5}, {},
                             imagem_png=b"CORTES", dvh_png=b"DVH")
            reg = rj.registro_na_pasta(pasta)
            self.assertIsNotNone(reg)
            j._reabrir_registro_da_pasta(reg, pasta)
            self.assertEqual(j.form.pac_nome.text(), "Fulano Reaberto")
            self.assertEqual(j.caso.pasta_carregada, pasta)
        finally:
            j.deleteLater()

    def test_pasta_tem_dicom(self):
        # Só com a ficha salva (ARQUIVOS_*.zip + PDFs) NÃO conta como DICOM —
        # senão o app oferece "elaborar nova" sem TC para ler.
        d = tempfile.mkdtemp()
        Path(os.path.join(d, "ARQUIVOS_JOSE_1.zip")).write_bytes(b"PK\x03\x04")
        Path(os.path.join(d, "FICHA_JOSE_v1.pdf")).write_bytes(b"%PDF")
        self.assertFalse(gui._pasta_tem_dicom(d))
        # Um .dcm de verdade → há o que elaborar.
        Path(os.path.join(d, "corte.dcm")).write_bytes(b"DICM")
        self.assertTrue(gui._pasta_tem_dicom(d))

    def test_pasta_tem_dicom_zip_nao_ficha(self):
        # Um .zip que NÃO é o arquivo da ficha (pode conter DICOM) conta.
        d = tempfile.mkdtemp()
        Path(os.path.join(d, "exame.zip")).write_bytes(b"PK\x03\x04")
        self.assertTrue(gui._pasta_tem_dicom(d))

    def test_planos_incompletos_detecta_sem_tc_e_sem_dose(self):
        j = gui.JanelaPrincipal(usuario={"usuario": "t", "nome": "T", "papel": "fisico"})
        try:
            j.caso.ct = object()   # não arquivado
            j.caso.registro_carregado = None
            j.caso.planos = [
                {"rotulo": "1 A", "ct": object(), "rd_ds": object()},   # ok
                {"rotulo": "2 B", "ct": None, "rd_ds": object()},       # sem TC
                {"rotulo": "3 C", "ct": object(), "rd_ds": None},       # sem dose
            ]
            av = j.portao.planos_incompletos()
            self.assertEqual(len(av), 2)
            self.assertTrue(any("2 B" in a and "sem TC" in a for a in av))
            self.assertTrue(any("3 C" in a and "sem dose" in a for a in av))
        finally:
            j.deleteLater()

    def test_planos_incompletos_vazio_quando_arquivada(self):
        # Ficha reaberta (sem CT em memória, com registro): cortes/DVH vêm dos PNGs.
        j = gui.JanelaPrincipal(usuario={"usuario": "t", "nome": "T", "papel": "fisico"})
        try:
            j.caso.ct = None
            j.caso.registro_carregado = {"versoes": [{"versao": 1}]}
            j.caso.planos = [{"rotulo": "1 A", "ct": None, "rd_ds": None}]
            self.assertEqual(j.portao.planos_incompletos(), [])
        finally:
            j.deleteLater()

    def test_scan_ignora_arquivo_da_ficha_salva(self):
        # O scan de DICOM não pode reingerir ARQUIVOS_*.zip (RTPLAN arquivados),
        # senão surgem planos-fantasma. Os DICOM soltos/pacotes de exame entram.
        d = Path(tempfile.mkdtemp())
        (d / "corte.dcm").write_bytes(b"DICM")
        (d / "exame.zip").write_bytes(b"PK\x03\x04")
        (d / "ARQUIVOS_JOSE_123.zip").write_bytes(b"PK\x03\x04")
        nomes = {p.name for p in gui._CarregarTudo._arquivos_dicom(d)}
        self.assertIn("corte.dcm", nomes)
        self.assertIn("exame.zip", nomes)
        self.assertNotIn("ARQUIVOS_JOSE_123.zip", nomes)


@unittest.skipIf(gui is None, "gui indisponível (PySide6?)")
class TestDoseTotalAutomatica(unittest.TestCase):
    """Dose total = dose/fração × nº frações, sem sobrescrever edição manual."""

    def test_prescricao_nasce_em_branco_e_nao_em_zero(self):
        """"0,00 Gy" lê-se como valor conferido, não como campo por preencher.

        É a mesma armadilha do "Nome completo" em cinza dentro do campo do
        nome. Só a pintura muda: ``coletar`` já convertia 0 em ``None``.
        """
        aba = gui._AbaPlano()
        try:
            for w in (aba.rx_dose_total, aba.rx_dose_fracao, aba.rx_fracoes):
                self.assertFalse(w.text().strip(), w.text())
                self.assertEqual(w.value(), 0)
            d = aba.coletar()
            for chave in ("rx_dose_total", "rx_dose_fracao", "rx_fracoes"):
                self.assertIsNone(d[chave], chave)
            # Com valor, volta a escrever normalmente (unidade inclusive).
            aba.rx_dose_fracao.setValue(2.7)
            self.assertIn("Gy", aba.rx_dose_fracao.text())
        finally:
            aba.deleteLater()

    def test_o_texto_de_vazio_nao_pode_ser_string_vazia(self):
        """O Qt entende ``""`` como "não há texto especial" e volta a escrever
        o zero — o truque só vale com um caractere de verdade."""
        self.assertTrue(gui._VAZIO_SPIN)
        self.assertFalse(gui._VAZIO_SPIN.strip())

    def test_modalidade_de_gating_nasce_sem_palpite(self):
        """A primeira da lista aparecendo sozinha é um palpite com cara de
        leitura; quem escreve é o DICOM, por ``_definir_gating``."""
        aba = gui._AbaPlano()
        try:
            self.assertEqual(aba.rx_gating_modal.currentText(), "")
            self.assertEqual(aba.coletar()["gating_modalidade"], "")
        finally:
            aba.deleteLater()

    def test_recalcula_ao_mudar_fracoes_ou_dose_fracao(self):
        aba = gui._AbaPlano()
        try:
            aba.rx_dose_fracao.setValue(2.0)
            aba.rx_fracoes.setValue(25)
            self.assertAlmostEqual(aba.rx_dose_total.value(), 50.0, places=2)
            aba.rx_fracoes.setValue(30)
            self.assertAlmostEqual(aba.rx_dose_total.value(), 60.0, places=2)
        finally:
            aba.deleteLater()

    def test_edicao_manual_do_total_nao_e_sobrescrita(self):
        aba = gui._AbaPlano()
        try:
            aba.rx_dose_fracao.setValue(2.0)
            aba.rx_fracoes.setValue(25)
            aba.rx_dose_total.setValue(66.0)   # usuário digita à mão
            aba.rx_fracoes.setValue(33)        # não deve recalcular
            self.assertAlmostEqual(aba.rx_dose_total.value(), 66.0, places=2)
        finally:
            aba.deleteLater()

    def test_limpar_volta_ao_automatico(self):
        aba = gui._AbaPlano()
        try:
            aba.rx_dose_total.setValue(66.0)   # trava manual
            aba.limpar()
            aba.rx_dose_fracao.setValue(3.0)
            aba.rx_fracoes.setValue(10)
            self.assertAlmostEqual(aba.rx_dose_total.value(), 30.0, places=2)
        finally:
            aba.deleteLater()

    def test_carregar_salvo_divergente_respeita_o_total(self):
        # Registro salvo com total ≠ dose/fração × frações (foi editado à mão):
        # mudar as frações depois NÃO recalcula.
        aba = gui._AbaPlano()
        try:
            aba.aplicar({"rx_dose_total": 45.0, "rx_fracoes": 25,
                         "rx_dose_fracao": 2.0})
            self.assertAlmostEqual(aba.rx_dose_total.value(), 45.0, places=2)
            aba.rx_fracoes.setValue(30)
            self.assertAlmostEqual(aba.rx_dose_total.value(), 45.0, places=2)
        finally:
            aba.deleteLater()

    def test_agendamento_arrastar_reordena_planos(self):
        # Arrastar um chip (via _mover_plano) reordena os planos das págs 2 e 3
        # sem tocar nas abas/cortes; a ordem sai em resultado()["ordem_planos"].
        planos_info = [{"rotulo": "1 A", "num_fracoes": 5, "frame_uid": "u"},
                       {"rotulo": "2 B", "num_fracoes": 5, "frame_uid": "u"}]
        dlg = gui.DialogAgendamento(planos_info)
        try:
            self.assertEqual(dlg._ordem_planos, [0, 1])   # padrão: por número
            dlg._mover_plano(1, 0)                         # arrasta B para antes de A
            self.assertEqual(dlg._ordem_planos, [1, 0])
            _APP.processEvents()                           # roda o rebuild adiado
            self.assertEqual(dlg.resultado()["ordem_planos"], [1, 0])
            # Chips reconstruídos na nova ordem, um por plano, todos presentes.
            self.assertTrue(all(c is not None for c in dlg._chips_ficha))
        finally:
            dlg.deleteLater()

    def test_agendamento_seletor_ficha_botoes_uniformes(self):
        # Ficha (Individual/Soma/Personalizado) vira botões checáveis exclusivos,
        # do mesmo tamanho dos de Modelos (Sequencial/Simultâneo).
        from PySide6.QtWidgets import QPushButton
        planos = [{"rotulo": "1 A", "num_fracoes": 5, "frame_uid": "u"},
                  {"rotulo": "2 B", "num_fracoes": 5, "frame_uid": "u"}]
        dlg = gui.DialogAgendamento(planos, mesma_tc=True)
        try:
            for b in (dlg.rb_indiv, dlg.rb_soma, dlg.rb_person):
                self.assertIsInstance(b, QPushButton)
                self.assertTrue(b.isCheckable())
            self.assertTrue(dlg.rb_indiv.isChecked())     # padrão
            # Todos os botões (Ficha + Modelos) do mesmo tamanho.
            larguras = {b.width() for b in dlg._btns_ag}
            self.assertEqual(len(larguras), 1)
            self.assertGreaterEqual(len(dlg._btns_ag), 5)
            # Exclusivo: marcar Soma desmarca Individual.
            dlg.rb_soma.setChecked(True)
            self.assertFalse(dlg.rb_indiv.isChecked())
            self.assertEqual(dlg.resultado()["modo_ficha"], "soma")
        finally:
            dlg.deleteLater()

    def test_menu_planos_desagenda_e_repoe_o_agendamento(self):
        # Desmarcar um plano no menu "Planos" tira ele de todos os dias (e some
        # o dia que existia só por causa dele); marcar de volta repõe exatamente
        # o agendamento anterior, sem desfazer o que os outros ganharam no meio.
        planos = [{"rotulo": "1 A", "num_fracoes": 2, "frame_uid": "u"},
                  {"rotulo": "2 B", "num_fracoes": 3, "frame_uid": "u"},
                  {"rotulo": "3 C", "num_fracoes": 1, "frame_uid": "u"}]
        dlg = gui.DialogAgendamento(planos)
        try:
            dlg._reconstruir([{"planos": [0, 1], "fracoes": 2},
                              {"planos": [1], "fracoes": 3},
                              {"planos": [2], "fracoes": 1}])
            base = dlg._etapas_dados()

            dlg._modelo_chips[1].setChecked(False)
            self.assertEqual(dlg._etapas_dados(),
                             [{"planos": [0], "fracoes": 2},
                              {"planos": [2], "fracoes": 1}])
            self.assertIn("(2/3)", dlg.btn_planos.text())

            dlg._modelo_chips[1].setChecked(True)
            self.assertEqual(dlg._etapas_dados(), base)
            self.assertEqual(dlg.btn_planos.text(), "Planos ▾")

            # Editar os outros enquanto o plano está fora não é desfeito.
            dlg._modelo_chips[2].setChecked(False)
            dlg._etapas[1]["spin"].setValue(9)
            dlg._modelo_chips[2].setChecked(True)
            self.assertEqual(dlg._etapas_dados(),
                             [{"planos": [0, 1], "fracoes": 2},
                              {"planos": [1], "fracoes": 9},
                              {"planos": [2], "fracoes": 1}])
        finally:
            dlg.deleteLater()

    def test_menu_planos_varios_fora_voltam_todos_na_ordem(self):
        # Vários planos fora ao mesmo tempo: cada um volta para os SEUS dias, na
        # ordem original, não importa a ordem em que saem e voltam. (Guardar
        # posição não bastava: a lista encolhe a cada dia que some.)
        planos = [{"rotulo": "1 A", "num_fracoes": 1, "frame_uid": "u"},
                  {"rotulo": "2 B", "num_fracoes": 5, "frame_uid": "u"},
                  {"rotulo": "3 C", "num_fracoes": 5, "frame_uid": "u"},
                  {"rotulo": "4 D", "num_fracoes": 3, "frame_uid": "u"}]
        for saem, voltam in (((0, 1, 2, 3), (0, 1, 2, 3)),   # todos, mesma ordem
                             ((0, 1, 2, 3), (3, 2, 1, 0)),   # todos, invertido
                             ((0, 2), (0, 2)),               # alternados
                             ((1, 3), (3, 1))):
            with self.subTest(saem=saem, voltam=voltam):
                dlg = gui.DialogAgendamento(planos)
                try:
                    base = dlg._etapas_dados()
                    for k in saem:
                        dlg._modelo_chips[k].setChecked(False)
                    for k in voltam:
                        dlg._modelo_chips[k].setChecked(True)
                    self.assertEqual(dlg._etapas_dados(), base)
                finally:
                    dlg.deleteLater()

    def test_menu_planos_dia_compartilhado_e_dia_novo(self):
        planos = [{"rotulo": "1 A", "num_fracoes": 5, "frame_uid": "u"},
                  {"rotulo": "2 B", "num_fracoes": 5, "frame_uid": "u"},
                  {"rotulo": "3 C", "num_fracoes": 3, "frame_uid": "u"}]
        dlg = gui.DialogAgendamento(planos)
        try:
            # Dois planos dividindo o mesmo dia: os dois fora somem com o dia,
            # e o dia volta inteiro quando eles voltam.
            dlg._reconstruir([{"planos": [0, 1], "fracoes": 5},
                              {"planos": [2], "fracoes": 3}])
            base = dlg._etapas_dados()
            dlg._modelo_chips[0].setChecked(False)
            dlg._modelo_chips[1].setChecked(False)
            self.assertEqual(dlg._etapas_dados(),
                             [{"planos": [2], "fracoes": 3}])
            dlg._modelo_chips[0].setChecked(True)
            dlg._modelo_chips[1].setChecked(True)
            self.assertEqual(dlg._etapas_dados(), base)

            # Dia criado enquanto o plano está fora nasce SEM ele (o ＋ não pode
            # reintroduzir quem saiu) e o dia do plano volta à posição de
            # origem: logo depois do dia que o precedia.
            dlg._modelo_chips[2].setChecked(False)
            dlg._inserir_etapa_apos(dlg._etapas[0])
            dlg._etapas[1]["spin"].setValue(7)
            self.assertEqual([e["planos"] for e in dlg._etapas_dados()],
                             [[0, 1], [0, 1]])
            dlg._modelo_chips[2].setChecked(True)
            self.assertEqual(dlg._etapas_dados(),
                             [{"planos": [0, 1], "fracoes": 5},
                              {"planos": [2], "fracoes": 3},
                              {"planos": [0, 1], "fracoes": 7}])
        finally:
            dlg.deleteLater()

    def test_menu_planos_volta_sempre_com_algum_dia(self):
        # Um modelo aplicado enquanto o plano está fora reescreve os dias em que
        # ele estava. Ao voltar, ele entra com a prescrição dele — plano no
        # agendamento sem dia nenhum confundiria o contador.
        planos = [{"rotulo": "1 A", "num_fracoes": 5, "frame_uid": "u"},
                  {"rotulo": "2 B", "num_fracoes": 4, "frame_uid": "u"}]
        dlg = gui.DialogAgendamento(planos)
        try:
            dlg._reconstruir([{"planos": [0, 1], "fracoes": 5}])
            dlg._modelo_chips[1].setChecked(False)
            dlg._aplicar_modelo(ag.modelo_sequencial)
            dlg._modelo_chips[1].setChecked(True)
            etapas = dlg._etapas_dados()
            self.assertTrue(any(1 in e["planos"] for e in etapas), etapas)
            self.assertEqual(ag.fracoes_por_plano(etapas, 2)[1], 4)
        finally:
            dlg.deleteLater()

    def test_menu_planos_nao_deixa_o_agendamento_sem_nenhuma_linha(self):
        # Sem nenhum plano no ar, todo dia fica sem plano e sai de cena: sobravam
        # ZERO linhas, sem o ＋ de nenhuma delas para recriar uma, e Aplicar
        # salvava sequencia vazia (mapa da pág. 3 em branco). O último não sai.
        planos = [{"rotulo": "1 A", "num_fracoes": 5, "frame_uid": "u"},
                  {"rotulo": "2 B", "num_fracoes": 3, "frame_uid": "u"}]
        dlg = gui.DialogAgendamento(planos)
        try:
            for c in dlg._modelo_chips:
                c.setChecked(False)
            self.assertTrue(dlg._planos_ligados(), "nenhum plano sobrou no ar")
            self.assertTrue(dlg._etapas, "agendamento ficou sem nenhuma linha")
            self.assertTrue(any(e["planos"] for e in dlg._etapas_dados()))
            # E os que saíram voltam com o agendamento deles intacto.
            for c in dlg._modelo_chips:
                c.setChecked(True)
            self.assertEqual(dlg._etapas_dados(),
                             [{"planos": [0], "fracoes": 5},
                              {"planos": [1], "fracoes": 3}])
        finally:
            dlg.deleteLater()

    def test_menu_planos_reordenar_nao_desagenda(self):
        # Reordenar os planos remonta os chips do menu; isso não pode disparar
        # desagendamento nenhum, nem perder quem já estava fora.
        planos = [{"rotulo": "1 A", "num_fracoes": 2, "frame_uid": "u"},
                  {"rotulo": "2 B", "num_fracoes": 3, "frame_uid": "u"},
                  {"rotulo": "3 C", "num_fracoes": 1, "frame_uid": "u"}]
        dlg = gui.DialogAgendamento(planos)
        try:
            dlg._modelo_chips[0].setChecked(False)
            antes = dlg._etapas_dados()
            dlg._mover_plano(2, 1)
            _APP.processEvents()                  # roda o rebuild adiado
            self.assertEqual(dlg._etapas_dados(), antes)
            self.assertFalse(dlg._modelo_chips[0].isChecked())
            self.assertIn("(2/3)", dlg.btn_planos.text())
            # E o plano que estava fora ainda volta com o agendamento dele.
            dlg._modelo_chips[0].setChecked(True)
            self.assertIn([0], [e["planos"] for e in dlg._etapas_dados()])
        finally:
            dlg.deleteLater()

    def test_separar_ficha_guarda_subconjunto_e_reavalia_modos(self):
        # "Separar Ficha" escolhe QUAIS planos entram no documento. Isso muda o
        # conjunto avaliado pelos modos: 4 planos em 2 TCs não permitem Soma,
        # mas separar os 2 de uma delas passa a permitir.
        planos = [{"rotulo": "1 A", "num_fracoes": 5, "frame_uid": "u"},
                  {"rotulo": "2 B", "num_fracoes": 5, "frame_uid": "u"},
                  {"rotulo": "3 C", "num_fracoes": 5, "frame_uid": "v"},
                  {"rotulo": "4 D", "num_fracoes": 5, "frame_uid": "v"}]
        dlg = gui.DialogAgendamento(planos)
        try:
            self.assertFalse(dlg.rb_soma.isEnabled())     # 2 TCs → sem Soma
            self.assertTrue(dlg.rb_person.isEnabled())
            self.assertIsNone(dlg.resultado()["planos_separados"])

            dlg._aplicar_separacao([0, 1])
            self.assertEqual(dlg.resultado()["planos_separados"], [0, 1])
            self.assertTrue(dlg.rb_soma.isEnabled())      # subconjunto na mesma TC
            self.assertTrue(dlg.btn_separar.isChecked())
            self.assertIn("1 A", dlg.lbl_separar.text())

            # Soma escolhida e depois separação que a invalida → cai p/ Individual.
            dlg.rb_soma.setChecked(True)
            dlg._aplicar_separacao([0, 2])
            self.assertFalse(dlg.rb_soma.isEnabled())
            self.assertTrue(dlg.rb_indiv.isChecked())
            self.assertEqual(dlg.resultado()["modo_ficha"], "individual")

            # Marcar todos equivale a não separar.
            dlg._aplicar_separacao([0, 1, 2, 3])
            self.assertIsNone(dlg.resultado()["planos_separados"])
            self.assertFalse(dlg.btn_separar.isChecked())
            self.assertEqual(dlg.lbl_separar.text(), "")
        finally:
            dlg.deleteLater()

    def test_separar_ficha_restringe_chips_do_personalizado(self):
        # Um plano fora da separação não sai no documento: não pode compor a
        # combinação de cortes/DVH do Personalizado.
        planos = [{"rotulo": "1 A", "num_fracoes": 5, "frame_uid": "u"},
                  {"rotulo": "2 B", "num_fracoes": 5, "frame_uid": "u"},
                  {"rotulo": "3 C", "num_fracoes": 5, "frame_uid": "v"},
                  {"rotulo": "4 D", "num_fracoes": 5, "frame_uid": "v"}]
        dlg = gui.DialogAgendamento(planos)
        try:
            dlg._aplicar_separacao([2, 3])
            dlg.rb_person.setChecked(True)
            self.assertEqual(dlg.resultado()["planos_ficha"], [2, 3])
            for i in (0, 1):
                self.assertFalse(dlg._chips_ficha[i].isChecked())
                self.assertFalse(dlg._chips_ficha[i].isEnabled())
        finally:
            dlg.deleteLater()

    def test_separar_ficha_restaura_do_agendamento_salvo(self):
        planos = [{"rotulo": "1 A", "num_fracoes": 5, "frame_uid": "u"},
                  {"rotulo": "2 B", "num_fracoes": 5, "frame_uid": "u"},
                  {"rotulo": "3 C", "num_fracoes": 5, "frame_uid": "u"}]
        dlg = gui.DialogAgendamento(planos, {"planos_separados": [0, 2],
                                             "modo_ficha": "soma"})
        try:
            self.assertEqual(dlg.resultado()["planos_separados"], [0, 2])
            self.assertTrue(dlg.rb_soma.isChecked())
        finally:
            dlg.deleteLater()

    def test_plano_fora_do_agendamento_nao_soma_dose(self):
        # Sem nenhum dia, o plano não tem linha no mapa da pág. 3: não há dose
        # dele para acumular junto com outro. O chip fica travado e o grupo não
        # sai no resultado — mas continua GUARDADO, como os dias.
        planos = [{"rotulo": f"{i + 1} P", "num_fracoes": 5, "frame_uid": "u"}
                  for i in range(4)]
        dlg = gui.DialogAgendamento(planos)
        try:
            dlg._ciclar_grupo_dose(2); dlg._ciclar_grupo_dose(3)   # grupo A: 3 e 4
            self.assertEqual(dlg._grupos_dose_dados(), [[2, 3]])
            self.assertIn("A", dlg.btn_somar.text())

            dlg._modelo_chips[3].setChecked(False)
            self.assertFalse(dlg._dose_chips[3].isEnabled())
            self.assertNotIn("·", dlg._dose_chips[3].text())   # sem a letra
            self.assertEqual(dlg._grupos_dose_dados(), [])     # sobrou 1 → não é grupo
            self.assertNotIn("A", dlg.btn_somar.text())
            self.assertEqual(dlg.resultado()["grupos_dose"], [])
            # Chip travado não cicla nem por chamada direta.
            dlg._ciclar_grupo_dose(3)
            self.assertEqual(dlg._grupos_dose_dados(), [])

            dlg._modelo_chips[3].setChecked(True)
            self.assertTrue(dlg._dose_chips[3].isEnabled())
            self.assertEqual(dlg._grupos_dose_dados(), [[2, 3]])
        finally:
            dlg.deleteLater()

    def test_plano_fora_do_agendamento_nao_compoe_a_ficha(self):
        # "Planos ▾" manda: quem está fora do agendamento não entra no documento.
        planos = [{"rotulo": f"{i + 1} P", "num_fracoes": 5, "frame_uid": "u"}
                  for i in range(4)]
        dlg = gui.DialogAgendamento(planos)
        try:
            self.assertIsNone(dlg.resultado()["planos_separados"])
            dlg._modelo_chips[3].setChecked(False)
            self.assertEqual(dlg._indices_ficha(), [0, 1, 2])
            self.assertEqual(dlg.resultado()["planos_separados"], [0, 1, 2])
            self.assertTrue(dlg.btn_separar.isChecked())
            self.assertIn("4 P", [p["rotulo"] for p in planos])
            self.assertNotIn("4 P", dlg.lbl_separar.text())
            # Sem separação explícita, voltar ao agendamento devolve à ficha.
            dlg._modelo_chips[3].setChecked(True)
            self.assertIsNone(dlg.resultado()["planos_separados"])
            self.assertFalse(dlg.btn_separar.isChecked())
        finally:
            dlg.deleteLater()

    def test_separacao_explicita_sobrevive_a_ida_e_volta_no_planos(self):
        # A escolha do Separar Ficha é guardada como o usuário fez e só cruzada
        # com o agendamento na leitura: o plano que sai e volta do "Planos ▾"
        # volta à ficha se estava marcado lá, e continua fora se não estava.
        planos = [{"rotulo": f"{i + 1} P", "num_fracoes": 5, "frame_uid": "u"}
                  for i in range(4)]
        dlg = gui.DialogAgendamento(planos)
        try:
            dlg._aplicar_separacao([0, 1])
            self.assertEqual(dlg._indices_ficha(), [0, 1])
            dlg._modelo_chips[1].setChecked(False)
            self.assertEqual(dlg._indices_ficha(), [0])
            dlg._modelo_chips[1].setChecked(True)
            self.assertEqual(dlg._indices_ficha(), [0, 1])
            # Plano 3 nunca esteve na separação: ir e voltar não o traz.
            dlg._modelo_chips[2].setChecked(False)
            dlg._modelo_chips[2].setChecked(True)
            self.assertEqual(dlg._indices_ficha(), [0, 1])
        finally:
            dlg.deleteLater()

    def test_separar_todos_os_oferecidos_equivale_a_nao_separar(self):
        # Com um plano fora do agendamento, marcar os outros três no popup NÃO é
        # uma escolha de separação — senão o que voltasse ao "Planos ▾" ficaria
        # congelado fora da ficha.
        planos = [{"rotulo": f"{i + 1} P", "num_fracoes": 5, "frame_uid": "u"}
                  for i in range(4)]
        dlg = gui.DialogAgendamento(planos)
        try:
            dlg._modelo_chips[3].setChecked(False)
            dlg._aplicar_separacao([0, 1, 2])
            self.assertIsNone(dlg._planos_separados)
            dlg._modelo_chips[3].setChecked(True)
            self.assertEqual(dlg._indices_ficha(), [0, 1, 2, 3])
        finally:
            dlg.deleteLater()

    def test_dialog_separar_ficha_trava_quem_esta_fora_do_agendamento(self):
        itens = [(0, "1 A"), (1, "2 B"), (2, "3 C")]
        dlg = gui.DialogSepararFicha(itens, {0, 1, 2},
                                     gui.DialogAgendamento._CORES,
                                     bloqueados={1})
        try:
            travado = dict(dlg._chks)[1]
            self.assertFalse(travado.isEnabled())
            self.assertFalse(travado.isChecked())      # nem começa marcado
            self.assertIn("fora do agendamento", travado.text())
            self.assertEqual(dlg.resultado(), [0, 2])
            dlg._marcar_todos()                        # "Todos" não o alcança
            self.assertEqual(dlg.resultado(), [0, 2])
        finally:
            dlg.deleteLater()

    def test_dialog_separar_ficha_escolhe_varios(self):
        itens = [(0, "1 A"), (1, "2 B"), (2, "3 C")]
        dlg = gui.DialogSepararFicha(itens, {0, 2}, gui.DialogAgendamento._CORES)
        try:
            self.assertEqual(dlg.resultado(), [0, 2])
            dlg._marcar_todos()
            self.assertEqual(dlg.resultado(), [0, 1, 2])
            for _i, c in dlg._chks:      # nenhum marcado: não dá para aplicar
                c.setChecked(False)
            self.assertEqual(dlg.resultado(), [])
            self.assertFalse(dlg._b_ok.isEnabled())
        finally:
            dlg.deleteLater()

    def test_agendamento_da_ficha_remapeia_indices(self):
        # Separada a ficha, o agendamento salvo no registro precisa falar dos
        # planos QUE ESTÃO nela: índices remapeados e dias sem plano descartados.
        from types import SimpleNamespace
        fake = SimpleNamespace(caso=Caso(
            planos=[{"rotulo": "1 A"}, {"rotulo": "2 B"}, {"rotulo": "3 C"}],
            agendamento={
                "etapas": [{"planos": [0], "fracoes": 2},
                           {"planos": [1, 2], "fracoes": 3}],
                "modo_ficha": "personalizado", "planos_ficha": [1, 2],
                "ordem_planos": [0, 1, 2], "planos_separados": [1, 2]}))
        novo = gui.JanelaPrincipal._agendamento_da_ficha(fake, {1: 0, 2: 1})
        self.assertEqual(novo["etapas"], [{"planos": [0, 1], "fracoes": 3}])
        self.assertEqual(novo["sequencia"], [[0, 1]] * 3)
        self.assertEqual(novo["planos_ficha"], [0, 1])
        self.assertEqual(novo["ordem_planos"], [0, 1])
        self.assertIsNone(novo["planos_separados"])
        # Sem separação (pos cobre todos), devolve o próprio agendamento.
        igual = gui.JanelaPrincipal._agendamento_da_ficha(fake, {0: 0, 1: 1, 2: 2})
        self.assertIs(igual, fake.caso.agendamento)

    def test_dose_prescrita_e_o_100_por_cento_da_isodose(self):
        # A prescrição é o 100% do colorwash. O valor do formulário manda (é o
        # que o usuário conferiu e o que sai impresso); sem ele, vale o RT Plan.
        from types import SimpleNamespace

        class _Stub:
            _dose_prescrita = gui.JanelaPrincipal._dose_prescrita
            _dose_prescrita_total = gui.JanelaPrincipal._dose_prescrita_total

        aba = gui._AbaPlano()
        try:
            s = _Stub()
            s.caso = Caso()
            s.caso.planos = [{"rp": {"dose_total": 40.0}}, {"rp": {"dose_total": 20.0}}]
            s.form = SimpleNamespace(abas=SimpleNamespace(widget=lambda i: aba))
            aba.rx_dose_total.setValue(45.0)
            self.assertEqual(s._dose_prescrita(0), 45.0)      # formulário
            aba.rx_dose_total.setValue(0)
            self.assertEqual(s._dose_prescrita(0), 40.0)      # RT Plan
            self.assertEqual(s._dose_prescrita(9), 0.0)       # fora de faixa
            # Combinada sem grupo de "Somar dose": mama e FSC não acumulam dose
            # no mesmo alvo, então o 100% é a MAIOR prescrição — somar as duas
            # fazia o ponto quente real (113%) aparecer como 57%.
            s.form = SimpleNamespace(abas=SimpleNamespace(widget=lambda i: None))
            s.caso.agendamento = None
            self.assertEqual(s._dose_prescrita_total([0, 1]), 40.0)
            # Fase → boost na mesma região (agrupados): aí as prescrições somam.
            s.caso.agendamento = {"grupos_dose": [[0, 1]]}
            self.assertEqual(s._dose_prescrita_total([0, 1]), 60.0)
            s.caso.agendamento = None
            # Sem prescrição nenhuma: 0 = "não sei", e o colorwash cai no máximo.
            s.caso.planos = [{"rp": {}}]
            self.assertEqual(s._dose_prescrita(0), 0.0)
        finally:
            aba.deleteLater()

    def test_indices_da_ficha(self):
        from types import SimpleNamespace
        fn = gui.JanelaPrincipal._indices_ficha
        planos = [{}, {}, {}]
        self.assertEqual(fn(SimpleNamespace(caso=Caso(planos=planos, agendamento=None))),
                         [0, 1, 2])
        self.assertEqual(fn(SimpleNamespace(caso=Caso(planos=planos, agendamento={
            "planos_separados": [2, 0]}))), [0, 2])
        # Índices inválidos (agendamento antigo) caem no conjunto completo.
        self.assertEqual(fn(SimpleNamespace(caso=Caso(planos=planos, agendamento={
            "planos_separados": [7]}))), [0, 1, 2])

    def test_agendamento_mover_plano_invalido_nao_quebra(self):
        planos_info = [{"rotulo": "1 A", "num_fracoes": 5, "frame_uid": "u"},
                       {"rotulo": "2 B", "num_fracoes": 5, "frame_uid": "u"}]
        dlg = gui.DialogAgendamento(planos_info)
        try:
            dlg._mover_plano(0, 0)     # mesmo alvo: no-op
            dlg._mover_plano(0, 9)     # fora de faixa: no-op
            self.assertEqual(dlg._ordem_planos, [0, 1])
        finally:
            dlg.deleteLater()

    def test_e_600cd_so_para_a_600cd(self):
        # Os DRRs de setup só são renderizados/salvos para o 600CD — em outra
        # máquina nada é guardado, mesmo que a pasta traga RT Images de portal.
        from isocentro.interface import portao_ficha
        e = portao_ficha.e_600cd
        self.assertTrue(e({"maquina": "600CD"}))
        for maq in ("6EX", "TrueBeamSN1001", "TBuniverSN1002", "", "Outra"):
            self.assertFalse(e({"maquina": maq}), maq)

    def test_cache_3d_so_vale_para_o_proprio_corpo(self):
        # px_3d é a cópia do que estava NO PAINEL ao sair da aba, que pode ser o
        # 3D de outro plano ainda na tela (render de ~15 s em curso). Só o par
        # png_3d_rs/rs diz de quem é a imagem — sem isso a aba do fígado herdava
        # e cacheava a cabeça do plano anterior.
        class _Px:
            def __init__(self, nulo=False): self._nulo = nulo
            def isNull(self): return self._nulo

        rs_figado, rs_cabeca = object(), object()
        vale = controle_viewer._cache_3d_valido
        self.assertTrue(vale({"px_3d": _Px(), "png_3d_rs": rs_figado}, rs_figado))
        # imagem da cabeça guardada na aba do fígado: não pode ser reexibida
        self.assertFalse(vale({"px_3d": _Px(), "png_3d_rs": rs_cabeca}, rs_figado))
        self.assertFalse(vale({"px_3d": None, "png_3d_rs": rs_figado}, rs_figado))
        self.assertFalse(vale({"px_3d": _Px(nulo=True), "png_3d_rs": rs_figado},
                              rs_figado))
        self.assertFalse(vale({"px_3d": _Px(), "png_3d_rs": None}, rs_figado))
        self.assertFalse(vale({"px_3d": _Px(), "png_3d_rs": rs_figado}, None))

    def test_chave_3d_igual_para_o_mesmo_struct_set(self):
        # Dois planos podem carregar o MESMO struct set como objetos distintos.
        # A chave é por SOP UID, então o segundo plano acha o render no cache em
        # vez de repetir os ~15 s.
        from pydicom.dataset import Dataset

        def _rs(uid):
            d = Dataset(); d.SOPInstanceUID = uid; return d

        chave = controle_viewer._chave_3d
        a, b = _rs("1.2.3"), _rs("1.2.3")
        self.assertIsNot(a, b)
        self.assertEqual(chave(a, 10, -30), chave(b, 10, -30))
        # Corpo diferente e ângulo diferente têm que dar chaves diferentes.
        self.assertNotEqual(chave(a, 10, -30), chave(_rs("9.9.9"), 10, -30))
        self.assertNotEqual(chave(a, 10, -30), chave(a, 20, -30))
        self.assertNotEqual(chave(a, 10, -30), chave(a, 10, 60))
        # Sem SOP UID cai no id() do objeto, que segue distinguindo os corpos.
        s1, s2 = Dataset(), Dataset()
        self.assertNotEqual(chave(s1, 10, -30), chave(s2, 10, -30))

    def test_janela_nasce_inerte_e_so_abre_pasta_e_historico_respondem(self):
        # Sem caso carregado não há ficha para preencher: um combo de médico que
        # abre a lista e um spin de dose que aceita número convidam a digitar
        # algo que o primeiro carregamento vai sobrescrever.
        j = gui.JanelaPrincipal({"usuario": "dev", "papel": "admin"})
        try:
            self.assertFalse(j.form.isEnabled())
            for w in (j.form.eq_medico, j.form.eq_fisico, j.form.pac_nome,
                      j.viewer.cmb_janela, j.viewer.chk_isodose,
                      j.viewer.lst_estruturas, j.viewer.painel_axial.slider):
                self.assertFalse(w.isEnabled(), w)
            # A saída da janela vazia continua de pé.
            self.assertTrue(j.btn_pasta.isEnabled(), "Abrir pasta travou")
            self.assertTrue(j.btn_tratados.isEnabled(), "Histórico travou")

            # Chegou um caso: tudo volta a valer.
            j.caso.planos = [{"rotulo": "1 A"}]
            j._atualizar_edicao_habilitada()
            self.assertTrue(j.form.isEnabled())
            self.assertTrue(j.viewer.lst_estruturas.isEnabled())

            # E a limpeza devolve a janela ao estado inerte.
            j._executar_limpeza()
            self.assertFalse(j.form.isEnabled())
            self.assertFalse(j.viewer.cmb_janela.isEnabled())
            self.assertTrue(j.btn_pasta.isEnabled())
        finally:
            j.deleteLater()

    def test_aviso_de_plano_nao_aprovado_so_quando_falta_o_medico(self):
        # O campo Médico vazio num plano UNAPPROVED não é falha do app: o nome só
        # vai para o DICOM quando o médico aprova. O aviso é o que diz isso.
        from PySide6.QtWidgets import QMessageBox
        vistos = []
        original = QMessageBox.exec
        QMessageBox.exec = lambda self: (vistos.append(self.text()), 0)[1]
        j = gui.JanelaPrincipal({"usuario": "dev", "papel": "admin"})
        try:
            j.caso.planos = [{"rotulo": "1 SRS", "rp": {"aprovacao": "UNAPPROVED"}}]
            j._avisar_medico_sem_aprovacao()
            self.assertEqual(len(vistos), 1)
            self.assertIn("1 SRS", vistos[0])

            vistos.clear()
            j.caso.planos = [{"rotulo": "1 X", "rp": {"aprovacao": "APPROVED"}}]
            j._avisar_medico_sem_aprovacao()
            self.assertEqual(vistos, [], "plano aprovado não deve avisar")

            # Sem aprovação mas com médico digitado: não há o que explicar.
            j.caso.planos = [{"rotulo": "1 X", "rp": {"aprovacao": "UNAPPROVED"}}]
            j.form.eq_medico.setCurrentText("Camila Sampaio")
            j._avisar_medico_sem_aprovacao()
            self.assertEqual(vistos, [])
        finally:
            QMessageBox.exec = original
            j.deleteLater()

    def test_abrir_a_pasta_de_uma_recente_nao_mexe_no_caso_da_tela(self):
        """As ações da lista agem sobre uma ficha ANTIGA.

        Só Carregar troca o caso; as outras três (Versões, PDF, Pasta) abrem
        alguma coisa e devolvem a tela como estava — quem está no meio de uma
        ficha não pode perdê-la por ter conferido outra.
        """
        from isocentro.interface import fichinha as _fichinha

        j = gui.JanelaPrincipal({"usuario": "dev", "papel": "admin"})
        pasta = tempfile.mkdtemp()
        abertos = []
        original = gui.AcoesDeFicha._abrir_arquivo
        gui.AcoesDeFicha._abrir_arquivo = staticmethod(abertos.append)
        try:
            j.fichinha.definir_caminho(pasta)
            j.fichinha.definir_estado(_fichinha.VISTA)
            j.fichinha.definir_previa(True)

            j._fichinha_acao_recente(_fichinha.PASTA, {
                "paciente": "MARIA", "registro": "1", "pasta": pasta})
            self.assertEqual(abertos, [pasta])
            # A trilha do caso em elaboração continua exatamente onde estava.
            self.assertEqual(j.fichinha.estado(), _fichinha.VISTA)
            self.assertTrue(_pode_imprimir(j.fichinha, pasta))
            self.assertIn("MARIA", j.fichinha.lbl_status.text())
        finally:
            gui.AcoesDeFicha._abrir_arquivo = original
            os.rmdir(pasta)
            j.deleteLater()

    def test_lista_de_recentes_e_do_usuario_logado(self):
        """A lista é o recorte de quem está logado, não o log do serviço."""
        from isocentro.dados import historico

        d = tempfile.mkdtemp()
        antes = os.environ.get("ISOCENTRO_LOG_DIR")
        os.environ["ISOCENTRO_LOG_DIR"] = d
        j = gui.JanelaPrincipal({"usuario": "dev", "papel": "admin"})
        try:
            historico.registrar("ficha_gerada", usuario="dev", detalhes={
                "paciente": "MEU PACIENTE", "registro": "1", "pasta": d})
            historico.registrar("ficha_gerada", usuario="outro", detalhes={
                "paciente": "PACIENTE DO COLEGA", "registro": "2"})
            j._fichinha_recentes()
            self.assertEqual(j.fichinha.recentes.count(), 1)
            dados = j.fichinha.recentes.item(0).data(Qt.UserRole)
            # O evento foi gravado em caixa alta (como as fichas de antes de
            # 25/08/2026); a LISTA uniformiza a grafia ao montar.
            self.assertEqual(dados["paciente"], "Meu Paciente")
            # Fora do índice central: só o que depende da pasta fica aceso.
            self.assertEqual(dados["n_versoes"], 0)
        finally:
            # Devolver, não apagar: o ``pop`` desligava o desvio da suíte
            # (``limpeza_de_tela``) e a janela, coletada depois, gravava
            # "app_fechado" no histórico real.
            if antes is None:
                os.environ.pop("ISOCENTRO_LOG_DIR", None)
            else:
                os.environ["ISOCENTRO_LOG_DIR"] = antes
            j.deleteLater()

    def test_a_pasta_da_bancada_nao_segue_o_paciente_da_BUSCA(self):
        """``carregar_da_pasta`` tira as notas e as fotos da pasta apontada.
        Com o caso de A aberto na bancada e B escolhido na busca, a pasta de A
        continuava valendo: a capa de B saía com a nota de A e ainda anunciava
        "da pasta: SETUP_A.txt" — dado de outro paciente com cara de importado
        para este."""
        j = gui.JanelaPrincipal({"usuario": "t", "papel": "fisico"})
        try:
            j.caso.pasta_carregada = r"C:\casos\PACIENTE_A"
            j.form.pac_nome.setText("PACIENTE A")
            j.form.pac_registro.setText("1111111AAA")
            # Da bancada (o botão "Procurar"): é a pasta do próprio paciente.
            self.assertEqual(
                j.controle_capa.pasta_para_a_capa(None, True, "PACIENTE A", "1111111AAA"),
                r"C:\casos\PACIENTE_A")
            # O MESMO paciente escolhido na busca também a mantém.
            self.assertEqual(
                j.controle_capa.pasta_para_a_capa(None, False, "PACIENTE A", "1111111AAA"),
                r"C:\casos\PACIENTE_A")
            # Outro paciente na busca: a pasta de A não vai junto.
            self.assertEqual(
                j.controle_capa.pasta_para_a_capa(None, False, "PACIENTE B", "2222222BBB"),
                "")
            # Quem APONTOU uma pasta ("Da pasta") continua mandando.
            self.assertEqual(
                j.controle_capa.pasta_para_a_capa(r"C:\casos\B", False, "PACIENTE B",
                                     "2222222BBB"),
                r"C:\casos\B")
        finally:
            j.deleteLater()

    def test_sem_registro_dos_dois_lados_a_pasta_casa_pelo_NOME(self):
        """Paciente da TC ainda sem cadastro: o nome é a única chave que resta
        — a mesma regra de ``capa.posicionamento_e_de``."""
        j = gui.JanelaPrincipal({"usuario": "t", "papel": "fisico"})
        try:
            j.caso.pasta_carregada = r"C:\casos\SEM_REGISTRO"
            j.form.pac_nome.setText("Maria de Souza")
            j.form.pac_registro.setText("")
            self.assertEqual(
                j.controle_capa.pasta_para_a_capa(None, False, "MARIA DE SOUZA", ""),
                r"C:\casos\SEM_REGISTRO")
            self.assertEqual(
                j.controle_capa.pasta_para_a_capa(None, False, "PACIENTE SEM CADASTRO", ""), "")
        finally:
            j.deleteLater()

    def test_ISOCENTRO_DEV_aceita_a_FUNCAO_no_lugar_do_1(self):
        """``ISOCENTRO_DEV=medico`` é como se vê o app com os olhos de cada
        função (os .bat ``VER_COMO_*``) sem criar usuário de mentira no
        ``usuarios.json``, que é arquivo do serviço e é lido por todas as
        estações. Valor que não é função continua sendo admin — quem liga a
        variável para trabalhar quer a bancada inteira."""
        self.assertEqual(arranque._usuario_de_dev("medico")["papel"], "medico")
        self.assertEqual(arranque._usuario_de_dev("DOSIMETRISTA")["papel"],
                         "dosimetrista")
        for valor in ("1", "sim", "", "xpto"):
            with self.subTest(valor=valor):
                self.assertEqual(arranque._usuario_de_dev(valor)["papel"], "admin")
        # O papel no NOME: três janelas abertas lado a lado para comparar as
        # funções ficariam idênticas no cabeçalho sem isso.
        self.assertIn("medico", arranque._usuario_de_dev("medico")["nome"])

    def test_o_medico_abre_na_Virtual_e_so_tem_ela_e_a_Agenda(self):
        """A faixa é recortada pela FUNÇÃO (26/08/2026). Abrir numa aba que a
        função não enxerga deixaria a faixa sem botão aceso e o miolo mostrando
        uma tela que ninguém pode escolher de volta.

        A Agenda entrou em 23/09/2026 como a SEGUNDA aba do médico — as duas
        são de consulta, nenhuma monta documento —, então o Ctrl+Tab passou a
        ter para onde ir.
        """
        from isocentro.interface import fichinha as _fichinha

        j = gui.JanelaPrincipal({"usuario": "m", "papel": "medico"})
        try:
            self.assertEqual(list(j._btns_modo),
                             [_fichinha.MODO_FICHA_VIRTUAL,
                              _fichinha.MODO_AGENDA])
            self.assertEqual(j._stack.currentIndex(),
                             _fichinha.MODO_FICHA_VIRTUAL)
            # As SEIS telas continuam empilhadas: tirar uma renumeraria os
            # modos, e ``MODO_CAPA`` passaria a apontar para a Virtual.
            self.assertEqual(j._stack.count(), len(_fichinha.MODOS))
            # No Início (R-23) o Ctrl+Tab não troca nada: ele circula as abas
            # do MÓDULO aberto, e trocar por trás do Início seria invisível.
            j._modo_vizinho(1)
            self.assertEqual(j._stack.currentIndex(),
                             _fichinha.MODO_FICHA_VIRTUAL)
            j._abrir_modulo("radioteraficha")
            # Ctrl+Tab agora tem para onde ir — a Agenda —, e volta.
            j._modo_vizinho(1)
            self.assertEqual(j._stack.currentIndex(), _fichinha.MODO_AGENDA)
            j._modo_vizinho(1)
            self.assertEqual(j._stack.currentIndex(),
                             _fichinha.MODO_FICHA_VIRTUAL)
            # Nem por código: a Total não é uma das duas portas do médico.
            j._ir_para_modo(_fichinha.MODO_TOTAL)
            self.assertEqual(j._stack.currentIndex(),
                             _fichinha.MODO_FICHA_VIRTUAL)
        finally:
            j.deleteLater()

    def test_o_dosimetrista_ve_CapaUp_Virtual_e_Agenda(self):
        """"Restante dos grupos deixar igual dosimetrista" — e o técnico é um
        deles. A Agenda entrou no PADRÃO em 23/09/2026 (informação de
        serviço, não decisão clínica)."""
        from isocentro.interface import fichinha as _fichinha

        for papel in ("dosimetrista", "tecnico"):
            with self.subTest(papel=papel):
                j = gui.JanelaPrincipal({"usuario": "d", "papel": papel})
                try:
                    self.assertEqual(list(j._btns_modo),
                                     [_fichinha.MODO_CAPA,
                                      _fichinha.MODO_FICHA_VIRTUAL,
                                      _fichinha.MODO_AGENDA])
                    self.assertEqual(j._stack.currentIndex(),
                                     _fichinha.MODO_CAPA)
                finally:
                    j.deleteLater()

    def test_a_janela_abre_na_fichinha_e_maximizada(self):
        """A porta de entrada é a tela de dois cliques, na tela inteira —
        mesmo não sendo a primeira da faixa desde 09/10/2026.

        Abrir no último modo usado fazia quem precisou da bancada ontem abrir
        nela hoje — e a tela que serve à maioria dos casos dependia de alguém
        lembrar de voltar para ela.
        """
        from isocentro.interface import fichinha as _fichinha

        j = gui.JanelaPrincipal({"usuario": "dev", "papel": "admin"})
        try:
            self.assertEqual(j._stack.currentIndex(), _fichinha.MODO_FICHINHA)
            marcados = [m for m, b in j._btns_modo.items() if b.isChecked()]
            self.assertEqual(marcados, [_fichinha.MODO_FICHINHA])
            self.assertTrue(j.windowState() & Qt.WindowMaximized)
        finally:
            j.deleteLater()

    def test_a_edicao_da_fichinha_abre_a_bancada(self):
        """Edição virou a porta da Ficha Total, que saiu da faixa (08/09/2026).

        Era um diálogo modal sobre a Fichinha — e por isso não havia teste
        chegando até aqui: ele travaria esperando um clique. Se este voltar a
        travar, é o ``DialogEdicaoFicha`` de volta no caminho.

        ``isHidden`` e não ``isVisible``: a janela do teste nunca é mostrada, e
        com o pai escondido todo botão é invisível — o que se afirma aqui é o
        que foi ESCONDIDO de propósito.
        """
        from isocentro.interface import fichinha as _fichinha

        j = gui.JanelaPrincipal({"usuario": "dev", "papel": "admin"})
        try:
            # A Total está à mostra desde 09/10/2026.
            self.assertFalse(j._btn_modo_total.isHidden())
            j.fichinha.abrir_edicao.emit()
            self.assertEqual(j._stack.currentIndex(), _fichinha.MODO_TOTAL)
            # A faixa acompanha: o botão aparece ACESO e a Fichinha apaga —
            # senão a barra aponta uma tela com outra no miolo.
            self.assertFalse(j._btn_modo_total.isHidden())
            marcados = [m for m, b in j._btns_modo.items() if b.isChecked()]
            self.assertEqual(marcados, [_fichinha.MODO_TOTAL])
            # E continua à mostra na volta.
            j._btns_modo[_fichinha.MODO_FICHINHA].click()
            self.assertEqual(j._stack.currentIndex(), _fichinha.MODO_FICHINHA)
            self.assertFalse(j._btn_modo_total.isHidden())
        finally:
            j.deleteLater()

    def test_ir_para_a_bancada_apaga_a_visualizacao(self):
        """Ir editar derruba a prévia NA IDA, não na volta.

        O PDF em disco é de antes da edição: com a Impressão acesa enquanto o
        caso está sendo mexido do outro lado, quem voltasse e clicasse
        imprimiria o que já não vale. A prévia é refeita ao voltar à Fichinha
        (ver ``_trocar_modo``).
        """
        from isocentro.interface import fichinha as _fichinha

        j = gui.JanelaPrincipal({"usuario": "dev", "papel": "admin"})
        pasta = str(Path(__file__).parent)
        try:
            j.fichinha.definir_caminho(pasta)
            j.fichinha.definir_estado(_fichinha.VISTA)
            j.fichinha.definir_previa(True)
            self.assertTrue(_pode_imprimir(j.fichinha, pasta))
            j.fichinha.abrir_edicao.emit()
            self.assertFalse(j.fichinha.previa_pronta())
            self.assertFalse(_pode_imprimir(j.fichinha, pasta))
        finally:
            j.deleteLater()

    def test_o_modo_nao_e_mais_lembrado_entre_sessoes(self):
        """Trocar de tela não pode decidir onde o programa abre amanhã.

        Compara antes/depois em vez de exigir a chave ausente: as estações que
        já rodaram a versão anterior têm o valor gravado no registro do Windows,
        e ele fica lá — o que não pode é alguém continuar escrevendo nele.
        """
        from isocentro.interface import fichinha as _fichinha

        j = gui.JanelaPrincipal({"usuario": "dev", "papel": "admin"})
        try:
            antes = j._settings.value("modo_tela", None)
            j._ir_para_modo(_fichinha.MODO_TOTAL)
            j._ir_para_modo(_fichinha.MODO_CAPA)
            self.assertEqual(j._settings.value("modo_tela", None), antes)
        finally:
            j.deleteLater()

    def test_janela_principal_e_a_propria_janela_das_acoes_de_ficha(self):
        """``AcoesDeFicha`` num diálogo pergunta ao pai; aqui, a si mesma.

        Sem este gancho, "Carregar" pela lista de recentes só sabia dizer
        "não foi possível acessar a janela principal".
        """
        j = gui.JanelaPrincipal({"usuario": "dev", "papel": "admin"})
        try:
            self.assertIs(j._janela_ficha(), j)
            self.assertTrue(hasattr(j._janela_ficha(), "carregar_registro"))
        finally:
            j.deleteLater()

    def test_janela_vazia_mostra_o_convite_no_lugar_dos_cortes(self):
        j = gui.JanelaPrincipal({"usuario": "dev", "papel": "admin"})
        try:
            self.assertEqual(j.viewer._centro.currentIndex(), 0)   # convite
            j.caso.planos = [{"rotulo": "1 A"}]
            j._atualizar_edicao_habilitada()
            self.assertEqual(j.viewer._centro.currentIndex(), 1)   # cortes
            j._executar_limpeza()
            self.assertEqual(j.viewer._centro.currentIndex(), 0)
        finally:
            j.deleteLater()

    def test_conferencia_lista_o_que_a_ficha_vai_dever(self):
        # Os avisos existiam, mas no carregamento da pasta — minutos antes de
        # gerar. Aqui eles chegam na hora de gerar, que é quando resolvem.
        j = gui.JanelaPrincipal({"usuario": "dev", "papel": "admin"})
        try:
            pend = j.portao.pendencias()
            self.assertTrue(any("Médico" in p for p in pend))
            self.assertTrue(any("Físico" in p for p in pend))
            self.assertTrue(any("Registro" in p for p in pend))

            j.form.eq_medico.setCurrentText("Camila Sampaio")
            j.form.eq_fisico.setCurrentText("Isabela Lacerda")
            j.form.pac_registro.setText("13806")
            j.caso.planos = [{"rotulo": "1 SRS", "rp": {
                "aprovacao": "APPROVED", "iso_pos_mm": [0, 0, 0],
                "desl_lat": 1.0, "desl_long": 2.0, "desl_vert": 3.0,
                "feixes": [{"ssd": 92.1}, {"ssd": 95.0}]}}]
            self.assertEqual(j.portao.pendencias(), [])

            rp = j.caso.planos[0]["rp"]
            rp["aprovacao"] = "UNAPPROVED"
            rp["feixes"][1]["ssd"] = None
            rp["desl_lat"] = rp["desl_long"] = rp["desl_vert"] = None
            pend = j.portao.pendencias()
            self.assertTrue(any("não aprovado" in p and "1 SRS" in p for p in pend))
            self.assertTrue(any("SSD" in p for p in pend))
            self.assertTrue(any("Delta Couch" in p for p in pend))
        finally:
            j.deleteLater()

    def test_conferencia_nao_aparece_quando_esta_tudo_certo(self):
        from PySide6.QtWidgets import QMessageBox
        vistos = []
        original = QMessageBox.exec
        QMessageBox.exec = lambda self: (vistos.append(self.text()), 0)[1]
        j = gui.JanelaPrincipal({"usuario": "dev", "papel": "admin"})
        try:
            j.form.eq_medico.setCurrentText("Camila Sampaio")
            j.form.eq_fisico.setCurrentText("Isabela Lacerda")
            j.form.pac_registro.setText("13806")
            j.caso.planos = [{"rotulo": "1 A", "rp": {"aprovacao": "APPROVED"}}]
            self.assertTrue(j.portao.confirmar_pendencias())
            self.assertEqual(vistos, [], "ficha sem pendência não pode perguntar")
        finally:
            QMessageBox.exec = original
            j.deleteLater()

    def test_faixa_de_isodose_em_cgy(self):
        # O colorwash só entende %, mas quem confere a ficha às vezes quer ler
        # dose absoluta. Trocar a unidade converte; o que sai para o render e
        # para a ficha segue em %.
        v = gui.PainelVisualizador()
        try:
            self.assertEqual(v.cmb_iso_unid.currentText(), "%")   # padrão de hoje
            self.assertEqual(v.faixa_isodose_pct(), (50.0, 100.0))

            v.dose_iso_provider = lambda: (4800.0, 5136.0)   # 48 Gy, quente 107%
            v.cmb_iso_unid.setCurrentText("cGy")
            # Abre na dose de 50% e no PONTO QUENTE (o que o % esconde ao parar
            # na prescrição).
            self.assertEqual(v.spn_iso_min.value(), 2400)
            self.assertEqual(v.spn_iso_max.value(), 5136)
            self.assertEqual(tuple(round(x, 1) for x in v.faixa_isodose_pct()),
                             (50.0, 107.0))

            v.spn_iso_min.setValue(3000)
            self.assertEqual(round(v.faixa_isodose_pct()[0], 1), 62.5)

            v.cmb_iso_unid.setCurrentText("%")
            self.assertEqual(v.spn_iso_min.value(), 62)
            self.assertEqual(v.spn_iso_max.value(), 107)   # acima de 100 cabe
        finally:
            v.deleteLater()

    def test_faixa_vai_ate_a_dose_maxima_e_nao_ate_100(self):
        # Parar em 100% cortava justamente o que se quer olhar: o que passa da
        # prescrição sumia do colorwash como se não existisse.
        v = gui.PainelVisualizador()
        try:
            self.assertEqual((v.spn_iso_min.value(), v.spn_iso_max.value()),
                             (50, 100))            # sem dose, o padrão de sempre
            v.definir_dose_iso(4800.0, 5136.0)     # 48 Gy, ponto quente 107%
            self.assertEqual((v.spn_iso_min.value(), v.spn_iso_max.value()),
                             (50, 107))
            self.assertEqual(v.faixa_isodose_pct(), (50.0, 107.0))
            # Ponto quente bem acima do teto padrão (SRS normalizado) não corta.
            v.definir_dose_iso(1000.0, 2500.0)
            self.assertEqual(v.spn_iso_max.value(), 250)
        finally:
            v.deleteLater()

    def test_piso_escolhido_a_mao_sobrevive_a_troca_de_plano(self):
        v = gui.PainelVisualizador()
        try:
            v.definir_dose_iso(4800.0, 5136.0)
            v.spn_iso_min.setValue(70)
            v.definir_dose_iso(6000.0, 6300.0)     # outro plano: 60 Gy, 105%
            self.assertEqual((v.spn_iso_min.value(), v.spn_iso_max.value()),
                             (70, 105))
        finally:
            v.deleteLater()

    def test_faixa_em_cgy_acompanha_a_troca_de_plano(self):
        # A mesma dose absoluta significa outra coisa em cada prescrição: o piso
        # mantém o % e o topo vai para o ponto quente do plano novo.
        v = gui.PainelVisualizador()
        try:
            v.dose_iso_provider = lambda: (4800.0, 5136.0)
            v.cmb_iso_unid.setCurrentText("cGy")
            v.definir_dose_iso(2000.0, 2200.0)            # outro plano, 20 Gy
            self.assertEqual(v.spn_iso_min.value(), 1000)  # 50% de 20 Gy
            self.assertEqual(v.spn_iso_max.value(), 2200)  # novo ponto quente
        finally:
            v.deleteLater()

    def test_sem_prescricao_a_faixa_nao_vai_para_cgy(self):
        v = gui.PainelVisualizador()
        avisos = []
        v.aviso_isodose.connect(avisos.append)
        try:
            v.cmb_iso_unid.setCurrentText("cGy")
            self.assertEqual(v.cmb_iso_unid.currentText(), "%")
            self.assertEqual(v.faixa_isodose_pct(), (50.0, 100.0))
            self.assertTrue(avisos)
        finally:
            v.deleteLater()

    def test_estado_do_viewer_guarda_a_faixa_em_pct(self):
        # Guardar o que está na tela (cGy) faria a faixa mudar de significado ao
        # restaurar noutro plano.
        j = gui.JanelaPrincipal({"usuario": "dev", "papel": "admin"})
        try:
            v = j.viewer
            v.dose_iso_provider = lambda: (4800.0, 5136.0)
            v.cmb_iso_unid.setCurrentText("cGy")
            estado = j.controle_viewer.capturar_estado()
            self.assertEqual(tuple(round(x, 1) for x in estado["iso_pct"]),
                             (50.0, 107.0))
            v.spn_iso_min.setValue(4000)
            j.controle_viewer.restaurar_estado(estado)
            self.assertEqual(v.spn_iso_min.value(), 2400)   # de volta aos 50%
        finally:
            j.deleteLater()

    def test_dialogos_login_existem(self):
        for nome in ("DialogLogin", "DialogTrocarSenha", "DialogConfiguracoes",
                     "PainelUsuarios", "PainelEquipe", "PainelMaquinas"):
            self.assertTrue(hasattr(gui, nome), nome)

    def test_configuracoes_abas_por_papel(self):
        """Configuração é TODA de admin — inclusive Máquinas.

        Máquinas ficava aberta a todos. Os aceleradores, suas energias e
        apelidos são cadastro que a ficha inteira consome: quem monta ficha usa
        a lista, quem a define é o admin. Quem não é admin não recebe diálogo
        vazio, e sim um recado dizendo a quem pedir — por isso não há
        ``QTabWidget`` nenhum para ele.
        """
        from PySide6.QtWidgets import QTabWidget

        def titulos(usuario):
            dlg = gui.DialogConfiguracoes(usuario)
            tw = dlg.findChild(QTabWidget)
            return {tw.tabText(i) for i in range(tw.count())} if tw else set()
        adm = titulos({"usuario": "a", "papel": "admin"})
        fis = titulos({"usuario": "f", "papel": "fisico"})
        self.assertEqual(adm, {"Serviço", "Usuários", "Equipe", "Máquinas"})
        self.assertEqual(fis, set())

    def test_paineis_populam(self):
        from PySide6.QtWidgets import QTableWidget, QListWidget
        from isocentro.dominio import constantes
        pm = gui.PainelMaquinas()
        self.assertEqual(pm.findChild(QTableWidget).rowCount(), len(constantes.MAQUINAS))
        pe = gui.PainelEquipe()
        self.assertEqual(len(pe.findChildren(QListWidget)), 2)   # médicos + físicos

    def _arquivo_tmp(self, conteudo=None):
        """Caminho de cadastro numa pasta temporária (nunca o ~ do usuário)."""
        import json as _json
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        p = Path(d) / "equipe.json"
        if conteudo is not None:
            p.write_text(_json.dumps(conteudo, ensure_ascii=False),
                         encoding="utf-8")
        return p

    def test_cadastro_antigo_migra_como_acrescimo(self):
        # Formato antigo: a lista inteira. Ela é MAIS VELHA que a canônica, então
        # o que falta nela é nome que ainda não existia — não remoção. Migrar
        # como remoção foi o que fez a equipe do SAT nascer invisível.
        padrao = ("Ana", "Bruno", "Carla")
        arq = self._arquivo_tmp(["Ana", "Zeca"])       # sem Bruno nem Carla
        nomes, _u = gui._cadastro_equipe(arq, padrao)
        self.assertEqual(nomes, ["Ana", "Bruno", "Carla", "Zeca"])

    def test_cadastro_nao_duplica_a_mesma_pessoa_com_outra_grafia(self):
        # O cadastro do serviço traz o nome completo ("Ana Fátima de Paula
        # Brandao Albuquerque") e a lista canônica, a forma curta. A união crua
        # mostrava as duas; fica UMA, a mais completa — de qualquer das listas.
        arq = self._arquivo_tmp(["Ana Fátima de Paula Brandao Albuquerque",
                                 "Lais Toscano Mayer",          # canônica é maior
                                 "Jean Teixeira de Prado"])
        nomes, _u = gui._cadastro_equipe(arq, equipe.MEDICOS)
        self.assertIn("Ana Fátima de Paula Brandao Albuquerque", nomes)
        self.assertNotIn("Ana Fatima Albuquerque", nomes)
        self.assertIn("Lais Toscano Mayer João", nomes)
        self.assertNotIn("Lais Toscano Mayer", nomes)
        self.assertIn("Camila Sampaio", nomes)     # nome novo segue chegando
        self.assertEqual(len(nomes), len(equipe.MEDICOS))
        self.assertEqual(len(nomes), len(set(nomes)))

    def test_nome_novo_da_lista_canonica_chega_a_quem_ja_tem_cadastro(self):
        # O ponto do formato delta: o cadastro do usuário não congela a canônica.
        arq = self._arquivo_tmp()
        gui._salvar_cadastro(arq, ["Ana", "Zeca"], {}, ("Ana", "Bruno"))
        # ...e depois a lista canônica ganha um nome (nova contratação):
        nomes, _u = gui._cadastro_equipe(arq, ("Ana", "Bruno", "Nova Medica"))
        self.assertIn("Nova Medica", nomes)
        self.assertIn("Zeca", nomes)          # o acréscimo do usuário fica
        self.assertNotIn("Bruno", nomes)      # e a remoção dele também

    def test_remocao_de_todos_volta_ao_padrao(self):
        # Combo permanentemente vazio não teria como se recuperar.
        arq = self._arquivo_tmp()
        gui._salvar_cadastro(arq, [], {}, ("Ana", "Bruno"))
        nomes, _u = gui._cadastro_equipe(arq, ("Ana", "Bruno"))
        self.assertEqual(nomes, ["Ana", "Bruno"])

    def test_arquivo_corrompido_nao_derruba_o_cadastro(self):
        arq = self._arquivo_tmp()
        arq.write_text("{lixo", encoding="utf-8")
        nomes, unidades = gui._cadastro_equipe(arq, ("Ana", "Bruno"))
        self.assertEqual(nomes, ["Ana", "Bruno"])
        self.assertEqual(unidades, {})

    def test_unidade_persiste_e_so_grava_o_que_difere_do_padrao(self):
        import json as _json
        arq = self._arquivo_tmp()
        gui._salvar_cadastro(
            arq, list(equipe.MEDICOS) + ["Fulano Novo"],
            {"Jean Teixeira de Prado": "SAT",     # difere do padrão → grava
             "Camila Sampaio": "SAT",               # igual ao padrão → não grava
             "Fulano Novo": "Clinica"},
            equipe.MEDICOS)
        gravado = _json.loads(arq.read_text(encoding="utf-8"))
        self.assertEqual(sorted(gravado["unidades"]),
                         ["Fulano Novo", "Jean Teixeira de Prado"])
        _n, unidades = gui._cadastro_equipe(arq, equipe.MEDICOS)
        self.assertEqual(unidades["Jean Teixeira de Prado"], "SAT")

    def test_duplo_clique_cicla_a_unidade_e_persiste(self):
        salvos = []
        lst = gui._ListaNomes("Médicos", lambda: (["Ana"], {}),
                              lambda nomes, unidades: salvos.append(unidades))
        try:
            item = lst.lst.item(0)
            self.assertEqual(item.text(), "Ana")          # sem unidade: só o nome
            lst._ciclar_unidade(item)
            self.assertEqual(salvos[-1]["Ana"], "Clinica")
            self.assertIn("Clinica", lst.lst.item(0).text())
            self.assertEqual(lst._nomes(), ["Ana"])       # o sufixo não vira nome
            lst._ciclar_unidade(lst.lst.item(0))
            self.assertEqual(salvos[-1]["Ana"], "SAT")
            lst._ciclar_unidade(lst.lst.item(0))
            self.assertEqual(salvos[-1]["Ana"], "")       # volta a Todas
            self.assertEqual(lst.lst.item(0).text(), "Ana")
        finally:
            lst.deleteLater()

    def test_nome_cadastrado_com_unidade_so_aparece_naquela_maquina(self):
        # Fim a fim: cadastrar como SAT e o combo da Clinica não o oferece.
        arq = self._arquivo_tmp()
        gui._salvar_cadastro(arq, list(equipe.MEDICOS) + ["Fulano Novo"],
                             {"Fulano Novo": "SAT"}, equipe.MEDICOS)
        nomes, unidades = gui._cadastro_equipe(arq, equipe.MEDICOS)
        self.assertIn("Fulano Novo",
                      equipe.equipe_da_maquina(nomes, "Synergy01", unidades))
        self.assertNotIn("Fulano Novo",
                         equipe.equipe_da_maquina(nomes, "600CD", unidades))

    def test_nome_apagado_no_cadastro_some_dos_combos(self):
        # Fim a fim da 🗑: apagar em Configurações → Equipe tem de sumir com o
        # nome na ficha, inclusive nas máquinas de unidade conhecida — o filtro
        # repunha o nome canônico e a remoção não surtia efeito.
        arq = self._arquivo_tmp()
        restantes = [n for n in equipe.MEDICOS if n != "Camila Sampaio"]
        gui._salvar_cadastro(arq, restantes, {}, equipe.MEDICOS)
        nomes, unidades = gui._cadastro_equipe(arq, equipe.MEDICOS)
        self.assertNotIn("Camila Sampaio", nomes)
        for maquina in ("Synergy01", "600CD", ""):
            with self.subTest(maquina=maquina):
                self.assertNotIn("Camila Sampaio",
                                 equipe.equipe_da_maquina(nomes, maquina,
                                                                unidades))

    def test_cadastro_do_combo_nao_repete_a_mesma_pessoa(self):
        # Caminho real do combo: cadastro do serviço com o nome completo + lista
        # canônica com a forma curta. Uma entrada só, a mais completa.
        arq = self._arquivo_tmp(["Ana Fátima de Paula Brandao Albuquerque",
                                 "Lais Toscano Mayer"])
        nomes, unidades = gui._cadastro_equipe(arq, equipe.MEDICOS)
        for maquina in ("600CD", "TrueBeamSN1001", ""):
            itens = equipe.equipe_da_maquina(nomes, maquina, unidades)
            with self.subTest(maquina=maquina):
                self.assertEqual(len(itens), len(set(itens)))
                self.assertEqual([n for n in itens if "Albuquerque" in n],
                                 ["Ana Fátima de Paula Brandao Albuquerque"])
                self.assertEqual([n for n in itens if n.startswith("Lais")],
                                 ["Lais Toscano Mayer João"])

    def test_filtro_dos_combos_segue_a_maquina_da_ficha_aplicada(self):
        # Reabrir uma ficha do SAT depois de um caso da Clinica passa por
        # form.aplicar (não por preencher): os combos ficavam presos na equipe
        # da máquina anterior.
        f = gui.PainelFormulario()
        try:
            f.preencher({"RP": {"maquina": "TrueBeamSN1001"}})
            itens = [f.eq_medico.itemText(i) for i in range(f.eq_medico.count())]
            self.assertIn("Jean Teixeira de Prado", itens)
            self.assertNotIn("Camila Sampaio", itens)      # SAT fora da Clinica

            f.aplicar({"maquina": "Synergy01", "eq_medico": "Camila Sampaio"})
            itens = [f.eq_medico.itemText(i) for i in range(f.eq_medico.count())]
            self.assertIn("Camila Sampaio", itens)
            self.assertNotIn("Jean Teixeira de Prado", itens)
            self.assertEqual(f.eq_medico.currentText(), "Camila Sampaio")

            # Ficha sem máquina: volta a oferecer todo mundo, em vez de manter o
            # filtro do caso anterior.
            f.aplicar({"maquina": ""})
            itens = [f.eq_medico.itemText(i) for i in range(f.eq_medico.count())]
            self.assertIn("Camila Sampaio", itens)
            self.assertIn("Jean Teixeira de Prado", itens)

            # Sem a chave "maquina" (quem chama não sabe), o filtro fica como está.
            f.recarregar_equipe("Synergy01")
            f.aplicar({"eq_medico": "Camila Sampaio"})
            itens = [f.eq_medico.itemText(i) for i in range(f.eq_medico.count())]
            self.assertNotIn("Jean Teixeira de Prado", itens)
        finally:
            f.deleteLater()

    def test_rp_sem_maquina_nao_herda_o_filtro_do_caso_anterior(self):
        f = gui.PainelFormulario()
        try:
            f.preencher({"RP": {"maquina": "Synergy01"}})
            f.preencher({"RP": {}})                      # plano sem máquina
            itens = [f.eq_medico.itemText(i) for i in range(f.eq_medico.count())]
            self.assertIn("Jean Teixeira de Prado", itens)
        finally:
            f.deleteLater()

    def test_equipe_em_configuracoes_fica_sempre_em_ordem_alfabetica(self):
        # A lista cresce por acréscimo (o arquivo de uma instalação antiga está na
        # ordem de cadastro): quem abre Configurações → Equipe vê alfabético, e o
        # nome cadastrado agora entra no lugar dele, não no fim.
        salvos = []
        lst = gui._ListaNomes("Médicos",
                              lambda: (["Zuleica Alves", "Ana Fatima Albuquerque",
                                        "Thaís Franco Sartori"], {}),
                              lambda nomes, _u: salvos.append(nomes))
        try:
            self.assertEqual(lst._nomes(),
                             ["Ana Fatima Albuquerque", "Thaís Franco Sartori",
                              "Zuleica Alves"])
            lst.ed.setText("Barbara Fontes Moura Peixoto")
            lst._adicionar()
            esperado = ["Ana Fatima Albuquerque", "Barbara Fontes Moura Peixoto",
                        "Thaís Franco Sartori", "Zuleica Alves"]
            self.assertEqual(lst._nomes(), esperado)
            self.assertEqual(salvos[-1], esperado)     # e é isso que persiste
            # O nome novo fica selecionado — reordenar não pode "esconder" ele.
            self.assertEqual(lst.lst.currentItem().text(),
                             "Barbara Fontes Moura Peixoto")
        finally:
            lst.deleteLater()

    def test_combo_de_equipe_da_ficha_sai_em_ordem(self):
        # Mesmo caminho que recarregar_equipe usa para popular os combos.
        nomes, unidades = gui._carregar_medicos()
        for maquina in ("", "Synergy01", "TrueBeamSN1001"):
            with self.subTest(maquina=maquina):
                itens = equipe.equipe_da_maquina(nomes, maquina, unidades)
                self.assertEqual(itens, gui.dicom_rt.ordem_alfabetica(itens))


@unittest.skipIf(gui is None, "gui indisponível (PySide6?)")
class TestCtrlTabTrocaDeModo(unittest.TestCase):
    """Ctrl+Tab circula Ficha Total → Fichinha → Capa; Ctrl+Shift+Tab volta.

    Shift+Tab sozinho ficou de fora de propósito: é o "voltar um campo" do Qt, e
    a bancada é um formulário denso onde ele faz falta.
    """

    def setUp(self):
        from PySide6.QtTest import QTest
        self.QTest = QTest
        self.j = gui.JanelaPrincipal(
            usuario={"usuario": "t", "nome": "T", "papel": "fisico"})
        self.j.show()
        QTest.qWaitForWindowExposed(self.j)
        # A janela volta no modo lembrado da última sessão (QSettings); o ciclo
        # é o que está sob teste, não de onde ele parte.
        from isocentro.interface import fichinha
        self.j._ir_para_modo(fichinha.MODO_TOTAL)
        _APP.processEvents()

    def tearDown(self):
        self.j.close()
        self.j.deleteLater()
        _APP.processEvents()

    def _adiante(self, vezes=1):
        from PySide6.QtCore import Qt
        for _ in range(vezes):
            self.QTest.keyClick(self.j, Qt.Key_Tab, Qt.ControlModifier)
            _APP.processEvents()

    def _atras(self, vezes=1):
        from PySide6.QtCore import Qt
        for _ in range(vezes):
            self.QTest.keyClick(self.j, Qt.Key_Backtab,
                                Qt.ControlModifier | Qt.ShiftModifier)
            _APP.processEvents()

    def _modo(self) -> int:
        return self.j._stack.currentIndex()

    def test_circula_nos_dois_sentidos_e_da_a_volta(self):
        from isocentro.interface import fichinha
        # O ciclo é o da FAIXA, girado para começar na tela que está na frente
        # agora — dar a volta vale de qualquer ponto de partida.
        ciclo = list(fichinha.MODOS)
        i = ciclo.index(self._modo())
        gira = ciclo[i:] + ciclo[:i]
        for esperado in gira[1:] + gira:        # uma volta inteira e mais um pouco
            self._adiante()
            self.assertEqual(self._modo(), esperado)
        # E para trás, incluindo a volta na ponta: do primeiro vai para o último.
        for esperado in list(reversed(gira)) + [gira[-1]]:
            self.assertEqual(self._modo(), esperado)
            self._atras()

    def test_a_faixa_nao_mente_sobre_a_tela_da_frente(self):
        # O atalho troca por código; o botão precisa acompanhar, senão a faixa
        # mostra um modo e a tela é outra.
        for _ in range(len(gui.fichinha.MODOS) + 1):
            self._adiante()
            marcados = [m for m, b in self.j._btns_modo.items() if b.isChecked()]
            self.assertEqual(marcados, [self._modo()])

    def test_vale_com_o_foco_nas_abas_de_plano(self):
        # QTabWidget trata Ctrl+Tab por conta própria: o atalho da janela tem de
        # ganhar dele, senão o gesto muda de significado conforme o foco.
        from isocentro.interface import fichinha
        ciclo = list(fichinha.MODOS)
        seguinte = ciclo[(ciclo.index(fichinha.MODO_TOTAL) + 1) % len(ciclo)]
        self.j._ir_para_modo(fichinha.MODO_TOTAL)
        self.j.form.abas.setFocus()
        _APP.processEvents()
        self._adiante()
        self.assertEqual(self._modo(), seguinte)


class _JanelaFalsaCarga(object):
    """Só o que a carga da pasta toca, com cada colaborador anotando a chamada.

    A janela de verdade exige DICOM, viewer e worker; o que está sob teste aqui
    é a ORDEM dos passos do fim da carga, e ela cabe num dublê.
    """

    _plano_carregado = gui.JanelaPrincipal._plano_carregado
    _abrir_agendamento_pendente = gui.JanelaPrincipal._abrir_agendamento_pendente
    _perguntar_o_que_a_carga_deixou = (
        gui.JanelaPrincipal._perguntar_o_que_a_carga_deixou)
    _carga_terminou = gui.JanelaPrincipal._carga_terminou
    _remontar_a_aba_aberta = gui.JanelaPrincipal._remontar_a_aba_aberta
    # Entrou na v8 (23/09/2026), e é o ÚLTIMO passo do fim da carga: o ícone
    # «Visualizar»/«Editar» da Documentação monta o caso e só então entrega o
    # resultado, então o destino viaja na entrada e é cumprido aqui. Emprestado
    # do original pelo mesmo motivo dos outros — é a ordem que está sob teste.
    _cumprir_destino_da_documentacao = (
        gui.JanelaPrincipal._cumprir_destino_da_documentacao)

    class _Stack:
        """Nenhuma aba na frente: a remontagem não tem o que fazer.

        O dublê ANOTA o passo mesmo assim — é a ordem do fim da carga que está
        sob teste, e a remontagem entrou nela em 04/09/2026.
        """

        def currentIndex(self):
            return -1

    class _Campo:
        def text(self):
            return "Fulano"

    class _Form:
        def __init__(self, dono):
            self._dono = dono
            self.pac_nome = _JanelaFalsaCarga._Campo()
            self.pac_registro = _JanelaFalsaCarga._Campo()

        def montar_abas(self, planos):
            pass

        def preencher(self, dados):
            pass

        def definir_multiplano(self, *a, **k):
            pass

        def aplicar_fracionamento_prescrito(self, registro, curso=""):
            # A prescrição entra ANTES do pop-up: o que ela responde não é
            # perguntado. O dublê registra o passo para a ordem ser testável.
            self._dono.passos.append("fracionamento_prescrito")
            return ""

        def perguntar_doses_altas(self):
            self._dono.passos.append("doses_altas")

    class _Status:
        def showMessage(self, *a, **k):
            pass

    def __init__(self):
        self.passos = []
        self.caso = Caso()
        self.form = self._Form(self)
        self.status = self._Status()
        self.fichinha = self._Fichinha(self)
        self._stack = self._Stack()
        self.controle_viewer = self._Viewer()
        # Vazio é o caso normal: pasta apontada à mão não pede destino nenhum.
        self._destino_documentacao = ""

    # Colaboradores mudos do _plano_carregado.
    def _atualizar_edicao_habilitada(self):
        pass

    class _Viewer:
        def ativar_plano(self, i):
            pass

    def _avisar_deslocamento_vazio(self, d):
        self.passos.append("deslocamento")

    def _avisar_medico_sem_aprovacao(self):
        self.passos.append("medico")

    def _planos_mesma_tc(self, indices=None):
        return True

    def _set_botoes_pasta(self, habilitado):
        self.passos.append("botoes")

    def _atualizar_btn_pdf(self):
        self.passos.append("btn_pdf")

    def _fichinha_carga_assentou(self):
        self.passos.append("assentou")
        return True

    def _fichinha_previa_e_status(self, nome):
        self.passos.append("previa")
        return True

    def _abrir_agendamento(self, _checked=False, *, suave=False):
        self.passos.append("agendamento")

    def _fichinha_edicao(self):
        self.passos.append("destino_editar")

    def _fichinha_visualizar(self):
        self.passos.append("destino_visualizar")

    class _Fichinha:
        def __init__(self, dono):
            self._dono = dono
            # O destino «Visualizar» só se cumpre com a prévia de pé: sem ela
            # o clique abriria uma visualização vazia.
            self.previa = True

        def mostrar_status(self, msg, erro=False):
            self._dono.passos.append("status")

        def previa_pronta(self):
            return self.previa


def _bundles(n):
    return [{"rp": {"dose_total": 50.0, "dose_fracao": 2.0, "num_fracoes": 25},
             "rotulo": f"Plano {i}"} for i in range(1, n + 1)]


@unittest.skipIf(gui is None, "gui indisponível (PySide6?)")
class TestAberturaDoAgendamentoNaCarga(unittest.TestCase):
    """O agendamento multi-plano abre no FIM da carga, nunca dentro dela.

    Aberto de dentro do slot de ``plano_pronto``, o ``exec_()`` do diálogo rodava
    um laço de eventos com o worker ainda vivo: o ``finished`` já enfileirado era
    entregue DENTRO do modal e a Fichinha montava a prévia com o agendamento
    ainda vazio — apagava a Visualização pedindo "monte o agendamento e volte
    aqui", que era exatamente o diálogo aberto na tela. Ninguém pegou isso porque
    este caminho não tinha teste nenhum.
    """

    def test_com_dois_planos_a_carga_so_marca_o_agendamento(self):
        j = _JanelaFalsaCarga()
        j._plano_carregado(_bundles(2), "ok")
        self.assertTrue(j.caso.agendamento_pendente)
        self.assertNotIn("agendamento", j.passos)   # nada de modal aqui

    def test_com_um_plano_nao_marca_nada(self):
        j = _JanelaFalsaCarga()
        j._plano_carregado(_bundles(1), "ok")
        self.assertFalse(j.caso.agendamento_pendente)

    def test_a_carga_termina_em_tres_tempos_na_ordem(self):
        # Assentar a trilha ANTES do modal (senão o diálogo pede decisão sobre
        # uma tela que ainda se diz ocupada) e montar a prévia DEPOIS dele
        # (senão ela nasce sem o agendamento que está na tela).
        j = _JanelaFalsaCarga()
        j._plano_carregado(_bundles(2), "ok")
        j.passos.clear()
        j._carga_terminou()
        self.assertEqual(
            [p for p in j.passos if p in ("assentou", "agendamento", "previa")],
            ["assentou", "agendamento", "previa"])
        self.assertFalse(j.caso.agendamento_pendente)   # consumido, não repete

    def test_sem_ficha_montada_nao_monta_previa(self):
        # Pasta sem material: a trilha volta ao INICIAL e não há o que prever.
        j = _JanelaFalsaCarga()
        j._fichinha_carga_assentou = lambda: (j.passos.append("assentou"), False)[1]
        j._plano_carregado(_bundles(2), "ok")
        j.passos.clear()
        j._carga_terminou()
        self.assertIn("agendamento", j.passos)   # os planos existem, agenda
        self.assertNotIn("previa", j.passos)

    def test_carga_de_um_plano_nao_abre_agendamento_no_fim(self):
        j = _JanelaFalsaCarga()
        j._plano_carregado(_bundles(1), "ok")
        j.passos.clear()
        j._carga_terminou()
        self.assertNotIn("agendamento", j.passos)

    def test_reentrar_no_fim_da_carga_nao_abre_um_segundo_dialogo(self):
        # A marca é apagada ANTES de abrir: se alguma coisa reentrar no fim da
        # carga com o diálogo na tela, não sobe um segundo por cima do primeiro.
        j = _JanelaFalsaCarga()
        j._plano_carregado(_bundles(2), "ok")
        j.passos.clear()

        def _abrir_reentrante(_checked=False, *, suave=False):
            j.passos.append("agendamento")
            j._carga_terminou()          # o que o modal fazia rodar por baixo

        j._abrir_agendamento = _abrir_reentrante
        j._carga_terminou()
        self.assertEqual(j.passos.count("agendamento"), 1)

    def test_cancelar_o_agendamento_reavalia_a_ficha_tecnica(self):
        # Multi-plano sem agendamento não fecha o documento: o botão da Ficha
        # Técnica tem de ser reexaminado depois do diálogo, não só antes.
        j = _JanelaFalsaCarga()
        j._plano_carregado(_bundles(2), "ok")
        j.passos.clear()
        j._carga_terminou()
        i_ag = j.passos.index("agendamento")
        self.assertIn("btn_pdf", j.passos[i_ag:])


@unittest.skipIf(gui is None, "gui indisponível (PySide6?)")
class TestPerguntasDaCargaForaDoWorker(unittest.TestCase):
    """A tela travava ao abrir o fracionamento da dose alta (01/09/2026).

    Os dois avisos e o diálogo de fracionamento eram disparados de dentro de
    ``_plano_carregado``, o slot de ``plano_pronto``. O ``exec_()`` de cada um
    roda um laço de eventos aninhado com o worker ainda vivo: o ``finished`` já
    enfileirado era entregue ali dentro e o fim da carga inteiro acontecia por
    baixo da pergunta aberta — a prévia é um PDF completo e ainda abre o seu
    próprio modal de progresso, que toma a modalidade do diálogo de baixo. Da
    cadeira: janela do fracionamento parada, sem aceitar clique.

    Havia um segundo estrago, silencioso: o fracionamento era perguntado ANTES
    de ``_agendamento_pendente`` ser marcado, então o fim da carga entregue
    dentro do modal via a marca em falso — o agendamento não abria nunca.
    """

    def test_o_slot_do_worker_nao_pergunta_nada(self):
        j = _JanelaFalsaCarga()
        j._plano_carregado(_bundles(2), "ok")
        for passo in ("deslocamento", "medico", "doses_altas", "agendamento"):
            self.assertNotIn(passo, j.passos)
        self.assertEqual(j.caso.perguntas_pendentes,
                         {"deslocamento", "medico", "doses_altas"})

    def test_as_perguntas_saem_no_fim_e_nesta_ordem(self):
        # Avisos primeiro (só informam), fracionamento depois — é ele que define
        # o dia de início —, e o agendamento por último, que usa esse dia como
        # semente. A prévia fecha a fila, com tudo já respondido.
        j = _JanelaFalsaCarga()
        j._plano_carregado(_bundles(2), "ok")
        j.passos.clear()
        j._carga_terminou()
        interesse = ("assentou", "deslocamento", "medico", "doses_altas",
                     "agendamento", "previa")
        self.assertEqual([p for p in j.passos if p in interesse],
                         list(interesse))
        # A prescrição responde ANTES do pop-up: perguntado depois, o
        # fracionamento já aprovado voltaria a ser escolhido à mão.
        self.assertLess(j.passos.index("fracionamento_prescrito"),
                        j.passos.index("doses_altas"))
        self.assertFalse(j.caso.perguntas_pendentes)   # consumidas, não repetem

    def test_reentrar_com_o_modal_aberto_nao_repete_a_fila(self):
        # O que o ``finished`` fazia rodar por baixo do diálogo: se ele voltar a
        # cair dentro de uma pergunta, nenhuma delas pode ser feita duas vezes.
        j = _JanelaFalsaCarga()
        j._plano_carregado(_bundles(2), "ok")
        j.passos.clear()

        def _perguntar_reentrante():
            j.passos.append("doses_altas")
            j._carga_terminou()

        j.form.perguntar_doses_altas = _perguntar_reentrante
        j._carga_terminou()
        for passo in ("deslocamento", "medico", "doses_altas", "agendamento"):
            self.assertEqual(j.passos.count(passo), 1, passo)

    def test_carga_sem_plano_nenhum_nao_pergunta(self):
        # Pasta que não deu plano: o slot não chegou a marcar nada, e o fim da
        # carga não pode inventar pergunta sobre um caso que não existe.
        j = _JanelaFalsaCarga()
        j._carga_terminou()
        for passo in ("deslocamento", "medico", "doses_altas", "agendamento"):
            self.assertNotIn(passo, j.passos)


@unittest.skipIf(gui is None, "gui indisponível (PySide6?)")
class TestODestinoDaDocumentacao(unittest.TestCase):
    """O ``apos`` que o ícone da Fichinha manda junto com o pedido de carga.

    Entrou na v8 (23/09/2026): «Visualizar» e «Editar» montam o caso quando ele
    ainda não está montado, e só então entregam o resultado — um na prévia, o
    outro na bancada. Montar leva segundos e acontece noutra thread, então não
    há como decidir na Fichinha o que fazer depois: o destino viaja na entrada
    e é cumprido aqui, no último passo do fim da carga.
    """

    def _carregada(self, destino, *, previa=True, assentou=True):
        j = _JanelaFalsaCarga()
        j._destino_documentacao = destino
        j.fichinha.previa = previa
        if not assentou:
            # É o que "a carga não deu em ficha" significa aqui: a pasta pode
            # até ter dado plano, mas a Fichinha não assentou o caso.
            j._fichinha_carga_assentou = lambda: False
        j._plano_carregado(_bundles(1), "ok")
        j.passos.clear()
        j._carga_terminou()
        return j

    def test_editar_abre_a_bancada_no_fim(self):
        j = self._carregada(_fich.EDITAR)
        self.assertIn("destino_editar", j.passos)

    def test_visualizar_abre_a_previa_no_fim(self):
        j = self._carregada(_fich.VISUALIZAR)
        self.assertIn("destino_visualizar", j.passos)

    def test_o_destino_e_o_ULTIMO_passo(self):
        """Antes das perguntas, a bancada abriria por cima de um modal que a
        carga ainda ia levantar — e o agendamento é justamente o que faz a
        prévia existir."""
        j = self._carregada(_fich.VISUALIZAR)
        self.assertEqual(j.passos[-1], "destino_visualizar")

    def test_visualizar_sem_previa_nao_abre_nada(self):
        """Multi-plano esperando agendamento: a visualização abriria vazia."""
        j = self._carregada(_fich.VISUALIZAR, previa=False)
        self.assertNotIn("destino_visualizar", j.passos)

    def test_carga_sem_ficha_nao_cumpre_destino_nenhum(self):
        j = self._carregada(_fich.EDITAR, assentou=False)
        self.assertNotIn("destino_editar", j.passos)

    def test_o_destino_e_consumido_mesmo_quando_nao_se_cumpre(self):
        """Esquecido, ele dispararia na PRÓXIMA carga — que pode ser de outro
        paciente — e abriria a bancada sozinha, sem ninguém ter pedido."""
        j = self._carregada(_fich.EDITAR, assentou=False)
        self.assertEqual(j._destino_documentacao, "")
        # A carga seguinte assenta normalmente, e nada pode sobrar da anterior.
        j._fichinha_carga_assentou = lambda: True
        j.passos.clear()
        j._carga_terminou()
        self.assertNotIn("destino_editar", j.passos)

    def test_pasta_apontada_a_mao_nao_tem_destino(self):
        j = self._carregada("")
        self.assertNotIn("destino_editar", j.passos)
        self.assertNotIn("destino_visualizar", j.passos)


# Esvazia ``estilo._ouvintes`` entre um teste e o seguinte. Sem isto, a lista
# cresce durante o arquivo inteiro e cada repintura percorre tudo o que já se
# acumulou — ver ``tests/limpeza_de_tela.py`` para os números.
from tests.limpeza_de_tela import load_tests  # noqa: E402,F401


@unittest.skipIf(gui is None, "PySide6 indisponível")
class TestUmPacientePorVez(unittest.TestCase):
    """Buscar no servidor traz a pasta para a bancada — 04/09/2026.

    Até então a sincronia era de mão única: bancada e Capa mandavam na Ficha
    Virtual, e escolher NA Virtual não mexia em nada. O resultado era a Virtual
    num paciente e as outras noutro — que o comentário do
    ``_tratamento_seguir_o_foco`` já chamava de "o pior defeito possível" numa
    tela de conferência, mas só evitava numa das direções.

    O que estes testes fixam é o que pode dar errado no conserto: o LAÇO (a
    carga preenche o registro, que reacende o foco) e a carga silenciosa por
    cima de um caso montado.
    """

    def setUp(self):
        self.chamadas = []
        self.recados = []

        class _Campo:
            def __init__(self, txt=""):
                self._t = txt

            def text(self):
                return self._t

        class _Form:
            pass

        class _Status:
            def __init__(self, fora):
                self._fora = fora

            def showMessage(self, msg, *a):
                self._fora.append(msg)

        class _Janela:
            _sincronizar_bancada = gui.JanelaPrincipal._sincronizar_bancada

        self._Campo, self._Form, self._Status, self._Janela = (
            _Campo, _Form, _Status, _Janela)

    def _janela(self, na_bancada="", pasta_achada="", rodando=False):
        j = self._Janela()
        j._sync_recusado = ""
        j.form = self._Form()
        j.form.pac_registro = self._Campo(na_bancada)
        j.status = self._Status(self.recados)
        j._worker_tudo = _WorkerFalso(rodando) if rodando else None
        j._carregar_pasta = lambda p: self.chamadas.append(p)
        from isocentro.interface import simulacao
        self._antes = simulacao.procurar
        simulacao.procurar = lambda nome, registro="": pasta_achada
        self._pasta_antes = controle_virtual.pasta_da_ficha
        controle_virtual.pasta_da_ficha = lambda reg: ""
        return j

    def tearDown(self):
        from isocentro.interface import simulacao
        if getattr(self, "_antes", None) is not None:
            simulacao.procurar = self._antes
        if getattr(self, "_pasta_antes", None) is not None:
            controle_virtual.pasta_da_ficha = self._pasta_antes

    def test_carrega_a_pasta_do_paciente_escolhido(self):
        j = self._janela(na_bancada="", pasta_achada=r"X:\SIM\FULANA")
        j._sincronizar_bancada("9000024ANA", "Fulana de Tal")
        self.assertEqual(self.chamadas, [r"X:\SIM\FULANA"])

    def test_o_paciente_que_JA_esta_na_bancada_nao_recarrega(self):
        """É o que impede o laço: carregar a pasta preenche ``pac_registro``,
        que reacende o foco, que chamaria isto de novo — e de novo."""
        j = self._janela(na_bancada="9000024ANA", pasta_achada=r"X:\SIM")
        j._sincronizar_bancada("9000024ANA", "Fulana de Tal")
        self.assertEqual(self.chamadas, [])

    def test_registro_vazio_nao_faz_nada(self):
        j = self._janela(pasta_achada=r"X:\SIM")
        j._sincronizar_bancada("", "")
        self.assertEqual(self.chamadas, [])

    def test_sem_pasta_a_bancada_fica_e_a_barra_DIZ(self):
        """Paciente do servidor pode não ter pasta ainda — é o caso mais comum
        de quem acabou de sair da tomografia. Quem espera que a bancada
        acompanhe precisa saber por que ela não acompanhou."""
        j = self._janela(pasta_achada="")
        j._sincronizar_bancada("9000024ANA", "Fulana de Tal")
        self.assertEqual(self.chamadas, [])
        self.assertIn("sem pasta", " ".join(self.recados))

    def test_carga_em_curso_nao_e_interrompida_MAS_avisa(self):
        """Uma segunda thread por cima da primeira é o defeito que o
        ``_carregar_pasta`` já recusa — mas calar deixava o pedido cair no
        vazio: quem confirmou B enquanto A carregava ficava com A na tela e
        nenhuma explicação, que é a dupla identidade que o método existe para
        evitar. Achado na segunda revisão de 04/09/2026."""
        j = self._janela(pasta_achada=r"X:\SIM", rodando=True)
        j._sincronizar_bancada("9000024ANA", "Fulana de Tal")
        self.assertEqual(self.chamadas, [])
        self.assertIn("ainda está carregando", " ".join(self.recados))

    def test_a_sincronia_nao_pende_da_NAVEGACAO(self):
        """O achado mais grave da segunda revisão de 04/09/2026.

        As listas da Capa e da Ficha Virtual disparam por
        ``itemSelectionChanged`` — andar com as setas conta como escolher, e é
        por isso que a busca da capa já tinha 260 ms de espera antes de ler o
        banco. Pendurada ali, a sincronia carregaria a pasta DICOM de quem o
        cursor pousou, ou abriria o modal "Substituir paciente atual?" a cada
        nome da lista.

        Agora ela pende do ``paciente_confirmado``, que é duplo clique ou
        Enter — "é este", e não "estou olhando este".
        """
        from isocentro.interface import capa as capa_tela
        from isocentro.interface import tratamento
        self.assertTrue(hasattr(capa_tela.PainelCapa, "paciente_confirmado"))
        self.assertTrue(
            hasattr(tratamento.PainelFichaVirtual, "paciente_confirmado"))
        # E os caminhos da navegação não podem mais chamá-la.
        for metodo in (controle_capa.ControleCapa.buscar_o_escolhido,
                       controle_virtual.ControleFichaVirtual.buscar):
            self.assertNotIn("_sincronizar_bancada",
                             inspect.getsource(metodo))

    def test_recusar_a_troca_nao_faz_a_pergunta_VOLTAR(self):
        """Achado na revisão de 04/09/2026.

        Recusar vale para o PACIENTE, não para o clique: sem esta memória, cada
        mudança de curso na Ficha Virtual chamava a sincronia de novo e a
        pergunta destrutiva reaparecia. Pergunta que volta é como se ensina a
        clicar sem ler — e a que está do outro lado descarta um caso montado.
        """
        j = self._janela(pasta_achada=r"X:\SIM")
        # ``_carregar_pasta`` dublado não inicia worker: é o mesmo estado de
        # quem recusou a substituição.
        j._sincronizar_bancada("9000024ANA", "Fulana")
        self.assertEqual(len(self.chamadas), 1)
        j._sincronizar_bancada("9000024ANA", "Fulana")   # outro curso, mesmo paciente
        self.assertEqual(len(self.chamadas), 1, "a pergunta voltaria")

    def test_a_recusa_esquece_quando_a_bancada_muda(self):
        """Ela é do paciente, não permanente: com ele carregado, a próxima
        recusa daquele registro tem de poder acontecer de novo."""
        j = self._janela(pasta_achada=r"X:\SIM")
        j._sincronizar_bancada("9000024ANA", "Fulana")
        j.form.pac_registro = self._Campo("9000024ANA")   # agora ele está lá
        j._sincronizar_bancada("9000024ANA", "Fulana")
        self.assertEqual(j._sync_recusado, "")

    def test_a_aba_aberta_e_REMONTADA_no_fim_da_carga(self):
        """O buraco que os testes desta classe não podiam ver.

        Eles dublam o ``_carregar_pasta``, então param antes do que importa: a
        carga passa pelo ``_executar_limpeza``, que ZERA a Capa e fecha a Ficha
        Virtual de propósito (eram do paciente anterior). Quem remontava era a
        troca de aba — e no caminho da sincronia a pessoa JÁ está na aba, então
        a troca nunca acontece.

        Resultado, achado na revisão de 04/09/2026: buscava-se o paciente na
        Capa com outro carregado, confirmava-se a troca, e a Capa ficava em
        branco — no exato caso em que a sincronia existe para ajudar.

        O teste é do CÓDIGO porque montar a carga inteira aqui custaria a
        janela de verdade com DICOM: o que se fixa é que o fim da carga chama a
        remontagem, e que ela reusa os mesmos métodos da troca de aba em vez de
        escrever uma segunda montagem.
        """
        fim = inspect.getsource(gui.JanelaPrincipal._carga_terminou)
        self.assertIn("_remontar_a_aba_aberta", fim)
        remonta = inspect.getsource(gui.JanelaPrincipal._remontar_a_aba_aberta)
        for metodo in ("controle_capa.ao_abrir", "controle_virtual.ao_abrir",
                       "_qualidade_ao_abrir"):
            self.assertIn(metodo, remonta)

    def test_a_reserva_do_indice_usa_o_registro_CRU(self):
        """``indice.listar_versoes`` casa por igualdade exata com o que foi
        gravado, e os três chamadores antigos passam o registro cru.
        Normalizado, a reserva erraria em silêncio — e silêncio aqui lê como
        "esse paciente não tem pasta"."""
        fonte = inspect.getsource(gui.JanelaPrincipal._sincronizar_bancada)
        self.assertIn("pasta_da_ficha(registro)", fonte)
        self.assertNotIn("pasta_da_ficha(reg)", fonte)

    def test_quem_confirma_a_troca_e_o_carregar_pasta(self):
        """A pergunta "Substituir paciente atual?" não é refeita aqui: ela mora
        no ``_carregar_pasta`` desde sempre, e duplicá-la daria duas perguntas
        para a mesma decisão."""
        fonte = inspect.getsource(gui.JanelaPrincipal._sincronizar_bancada)
        self.assertNotIn("confirmar", fonte)
        self.assertIn("_carregar_pasta", fonte)


class _WorkerFalso:
    def __init__(self, rodando):
        self._r = rodando

    def isRunning(self):
        return self._r


if __name__ == "__main__":
    unittest.main()
