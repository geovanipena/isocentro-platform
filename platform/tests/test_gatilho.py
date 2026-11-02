"""A varredura inteira: do banco à pasta, falando DICOM de verdade.

Estes são os testes que exercitam a automação como ela vai rodar na clínica —
janela anotada, plano aprovado, C-GET contra um SCP local, arquivos gravados,
marca d'água escrita. As únicas partes fingidas são o data warehouse (que não
existe fora do domínio) e o relógio.

O que eles fixam, e por que cada um importa mais do que parece:

* **conjunto incompleto NÃO é marcado como exportado.** Meio conjunto na pasta
  com a marca de "pronto" é pior que conjunto nenhum: a rodada seguinte não
  volta para terminar, e quem confere vê uma pasta que parece completa;
* **a segunda rodada não reexporta** — senão a pasta enche de cópias e a
  automação vira ruído;
* **falha de REDE para a varredura; plano que falhou, não.** Sem rede, insistir
  nos vinte seguintes enche o histórico de repetição e esconde a linha que
  importa. Um plano específico que falhou não pode impedir os outros dezenove;
* **o portão fechado não deixa nada sair**, e diz qual metade falta — conferir
  a consulta ou cadastrar o AE Title são chamados diferentes;
* **nome de pasta vindo do ARIA é higienizado.** ``CourseId`` com barra
  gravaria em outro lugar, ou falharia com erro que não parece de nome;
* **a preparação REFERENCIA a simulação, não copia** — e "sem cadastro" não se
  confunde com "raiz das simulações fora de alcance" (ver ``Preparo``).

Rodar:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from isocentro.banco import atividades_db  # noqa: E402
from isocentro.banco import capa_db  # noqa: E402
from isocentro.dominio import gatilho  # noqa: E402
from isocentro.banco import gatilho_db  # noqa: E402
from isocentro.dominio import gatilho_registro as gr  # noqa: E402
from isocentro.banco import capa_dados  # noqa: E402
from isocentro.dados import indice  # noqa: E402
from isocentro.interface import simulacao  # noqa: E402
from tests.scp_falso import UID, UID2, Servidor  # noqa: E402


def _ativ(instancia, registro, paciente="Beltrano, Lauro"):
    return atividades_db.Atividade(instancia=instancia, registro=registro,
                                   paciente=paciente, estado="Open",
                                   codigo="Documentação")


def _pronto(uid, registro="9000019ANA", curso="C1 SETEMBRO 2026",
            plano="cCRANIO_20Gy", instancia=1149015):
    return gatilho_db.Pronto(registro=registro, paciente="Beltrano, Lauro",
                             instancia=instancia, dim_curso=30658, curso=curso,
                             plano=plano, plan_uid=uid,
                             estado="Planning Approved", revisao=0, fracoes=5,
                             aprovado_por="clinica\\keiko.nakamura",
                             criado_em=datetime(2026, 9, 2, 8, 50))


class _Bancada:
    """O DW e o registro fingidos; a rede e o disco são de verdade.

    Guardar e DEVOLVER cada função, nunca ``del``: ``modulo.f = falsa`` grava no
    ``__dict__`` do módulo e o ``del`` depois some com a ORIGINAL para o resto
    do processo.
    """

    def __init__(self, atividades=(), prontos=()):
        self.atividades = list(atividades)
        self.prontos = list(prontos)

    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self._tmp.name) / "exportacao"
        self.registro = Path(self._tmp.name) / "registro.json"
        self._antes = {
            "todas": atividades_db.todas,
            "prontos_de": gatilho_db.prontos_de,
            "disponivel": gatilho_db.disponivel,
            "caminho": gr.caminho,
        }
        atividades_db.todas = lambda desde=None: list(self.atividades)
        gatilho_db.prontos_de = lambda por_registro: [
            p for p in self.prontos if p.registro in por_registro]
        # O portão do ``gatilho_db`` está fechado de verdade (VERIFICADO_EM
        # vazio) e é isso que se quer em produção; aqui ele é aberto à mão para
        # que o resto possa ser exercitado.
        gatilho_db.disponivel = lambda: True
        gr.caminho = lambda: self.registro
        # A raiz das simulações também é da bancada. Sem isto, todo plano que
        # sai aqui mandaria a preparação procurar no Documentos DESTA máquina —
        # o teste dependeria de quem roda e varreria disco real.
        self.simulacoes = Path(self._tmp.name) / "simulacoes"
        self.simulacoes.mkdir()
        self._env_sim = os.environ.get(simulacao.PASTA_ENV)
        os.environ[simulacao.PASTA_ENV] = str(self.simulacoes)
        simulacao.definir_raiz("")
        simulacao.esquecer_indice()
        return self

    def __exit__(self, *_):
        atividades_db.todas = self._antes["todas"]
        gatilho_db.prontos_de = self._antes["prontos_de"]
        gatilho_db.disponivel = self._antes["disponivel"]
        gr.caminho = self._antes["caminho"]
        if self._env_sim is None:
            os.environ.pop(simulacao.PASTA_ENV, None)
        else:
            os.environ[simulacao.PASTA_ENV] = self._env_sim
        # O índice das simulações é do MÓDULO: ficando, o próximo teste acharia
        # uma pasta que esta bancada já apagou.
        simulacao.esquecer_indice()
        self._tmp.cleanup()
        return False


class UmaVarreduraPorVez(unittest.TestCase):
    """A segunda rodada não acontece — nem quando vem de OUTRO processo.

    Até 14/09/2026 a exclusão era o ``gatilho_relogio.Relogio.ocupado()``, que
    só enxerga o próprio processo. Com a varredura podendo rodar por Tarefa
    Agendada na concentradora E pelo relógio de um app aberto na mesma máquina,
    as duas perguntariam a mesma coisa ao banco e a segunda baixaria o que a
    primeira está baixando — a trava do ``gatilho_registro`` evita a corrupção
    do arquivo, não o trabalho em dobro contra o ARIA.
    """

    def test_com_a_trava_tomada_a_varredura_nao_roda(self):
        with _Bancada([_ativ(1149015, "9000019ANA")], [_pronto(UID)]) as b, \
                Servidor([UID]):
            alvo = b.raiz / gatilho.ARQUIVO_TRAVA
            with indice.travar_ou_desistir(alvo) as minha:
                self.assertTrue(minha, "a bancada não conseguiu a trava")
                rel = gatilho.rodar(b.raiz)
            # ``portao`` e não ``interrompida``: é o caminho de "nem começou",
            # que a tela já sabe não anunciar. Anunciar de cinco em cinco
            # minutos que a varredura está ocupada ensinaria a ignorar a faixa.
            self.assertEqual(rel.portao, gatilho.MOTIVO_OCUPADA)
            self.assertEqual(rel.exportados, [])

    def test_a_trava_e_devolvida_no_fim_da_rodada(self):
        """Trava que não solta transforma a primeira rodada na única — e o
        sintoma seria a automação parar de funcionar sem nenhuma linha no
        histórico, porque nada FALHOU."""
        with _Bancada([_ativ(1149015, "9000019ANA")], [_pronto(UID)]) as b, \
                Servidor([UID]):
            gatilho.rodar(b.raiz)
            with indice.travar_ou_desistir(b.raiz / gatilho.ARQUIVO_TRAVA) as m:
                self.assertTrue(m, "a varredura ficou com a trava")

    def test_a_trava_nao_atrapalha_a_rodada_seguinte(self):
        """A segunda passada tem de rodar normalmente (e não reexportar)."""
        with _Bancada([_ativ(1149015, "9000019ANA")], [_pronto(UID)]) as b, \
                Servidor([UID]):
            primeira = gatilho.rodar(b.raiz)
            segunda = gatilho.rodar(b.raiz)
            self.assertEqual(len(primeira.exportados), 1)
            self.assertEqual(segunda.portao, "")
            self.assertEqual(segunda.exportados, [])


class PontaAPonta(unittest.TestCase):

    def test_o_plano_sai_e_fica_anotado(self):
        with _Bancada([_ativ(1149015, "9000019ANA")], [_pronto(UID)]) as b, \
                Servidor([UID]):
            rel = gatilho.rodar(b.raiz)
            pasta = gatilho.caminho_do_plano(_pronto(UID), b.raiz)
            arquivos = sorted(p.name for p in pasta.glob("*.dcm"))
            saiu = gr.ja_saiu(_pronto(UID))
            janela = gr.abertas()
        self.assertEqual(len(rel.exportados), 1)
        self.assertEqual(rel.incompletos, [])
        self.assertEqual(arquivos, [f"{UID}.dcm"])
        self.assertTrue(saiu)
        # A janela fecha com o motivo escrito: "exportado" e "venceu sem plano"
        # são desfechos opostos, e só o segundo pede que alguém vá olhar.
        self.assertEqual(janela, {})

    def test_o_recibo_diz_de_onde_o_arquivo_veio(self):
        """A pasta sozinha não diz quem aprovou nem em que estado o plano
        estava. Daqui a três meses o ARIA já mudou de degrau, e é o recibo que
        sobra."""
        with _Bancada([_ativ(1149015, "9000019ANA")], [_pronto(UID)]) as b, \
                Servidor([UID]):
            gatilho.rodar(b.raiz)
            pasta = gatilho.caminho_do_plano(_pronto(UID), b.raiz)
            recibo = json.loads((pasta / "exportacao.json").read_text("utf-8"))
        self.assertEqual(recibo["plan_uid"], UID)
        self.assertEqual(recibo["estado"], "Planning Approved")
        self.assertEqual(recibo["aprovado_por"], "clinica\\keiko.nakamura")
        self.assertEqual(recibo["modo"], "C-GET")

    def test_a_segunda_rodada_nao_reexporta(self):
        with _Bancada([_ativ(1149015, "9000019ANA")], [_pronto(UID)]) as b, \
                Servidor([UID]) as scp:
            gatilho.rodar(b.raiz)
            pedidos = len(scp.pedidos)
            rel = gatilho.rodar(b.raiz)
        self.assertEqual(rel.exportados, [])
        # E nem chegou a perguntar de novo ao servidor.
        self.assertEqual(len(scp.pedidos), pedidos)

    def test_dois_planos_do_mesmo_curso_saem_os_dois(self):
        """Tratamento de fases: primário e boost tratam os dois."""
        prontos = [_pronto(UID, plano="PRIMARIO"),
                   _pronto(UID2, plano="BOOST")]
        with _Bancada([_ativ(1149015, "9000019ANA")], prontos) as b, \
                Servidor([UID, UID2]):
            rel = gatilho.rodar(b.raiz)
            pastas = sorted(p.name for p in (b.raiz / "9000019ANA" /
                                             "C1 SETEMBRO 2026").iterdir())
        self.assertEqual(len(rel.exportados), 2)
        self.assertEqual(pastas, ["BOOST", "PRIMARIO"])


class Incompleto(unittest.TestCase):

    def test_conjunto_incompleto_nao_e_marcado_como_exportado(self):
        """A regra mais importante do arquivo. Marcar antes deixaria meio
        conjunto na pasta com cara de completo, e a rodada seguinte não
        voltaria para terminar."""
        with _Bancada([_ativ(1149015, "9000019ANA")], [_pronto(UID)]) as b, \
                Servidor([UID], aceita_get=False):
            rel = gatilho.rodar(b.raiz)
            saiu = gr.ja_saiu(_pronto(UID))
            ainda_aberta = "9000019ANA" in gr.abertas()
        self.assertEqual(rel.exportados, [])
        self.assertEqual(len(rel.incompletos), 1)
        self.assertFalse(saiu)
        self.assertTrue(ainda_aberta, "a janela tem de ficar para a próxima")

    def test_a_rodada_seguinte_tenta_de_novo(self):
        with _Bancada([_ativ(1149015, "9000019ANA")], [_pronto(UID)]) as b:
            with Servidor([UID], aceita_get=False):
                gatilho.rodar(b.raiz)
            with Servidor([UID]):
                rel = gatilho.rodar(b.raiz)
                saiu = gr.ja_saiu(_pronto(UID))
        self.assertEqual(len(rel.exportados), 1)
        self.assertTrue(saiu)

    def test_o_plano_travado_do_curso_e_tentado_de_novo(self):
        """Primário travou, boost saiu. A janela fechava no primeiro plano
        exportado; fechada, some dos pendentes, e o primário nunca mais era
        tentado — a Fichinha dizia ``⚠ incompleta`` para sempre."""
        prontos = [_pronto(UID, plano="PRIMARIO"),
                   _pronto(UID2, plano="BOOST")]
        with _Bancada([_ativ(1149015, "9000019ANA")], prontos) as b:
            with Servidor([UID2]):
                primeira = gatilho.rodar(b.raiz)
                aberta_no_meio = "9000019ANA" in gr.abertas()
            with Servidor([UID, UID2]) as scp:
                segunda = gatilho.rodar(b.raiz)
                pedidos = len(scp.pedidos)
                aberta_no_fim = "9000019ANA" in gr.abertas()
                estado = gr.estados_da_documentacao()[1149015]["estado"]
        self.assertEqual([p.plano for p in primeira.exportados], ["BOOST"])
        self.assertTrue(aberta_no_meio, "o primário ainda falta")
        self.assertEqual([p.plano for p in segunda.exportados], ["PRIMARIO"])
        # Só o que faltava foi pedido: o boost a marca d'água já tira.
        self.assertEqual(pedidos, 1)
        self.assertFalse(aberta_no_fim)
        self.assertEqual(estado, gr.PRONTA)

    def test_varredura_interrompida_nao_fecha_a_janela(self):
        """Parar entre planos deixa o segundo sem tentar. Com a janela
        fechada pelo primeiro, o segundo não voltaria na rodada seguinte."""
        prontos = [_pronto(UID, plano="P1"), _pronto(UID2, plano="P2")]
        chamadas = []

        def parar():
            chamadas.append(1)
            return len(chamadas) > 1

        with _Bancada([_ativ(1149015, "9000019ANA")], prontos) as b, \
                Servidor([UID, UID2]):
            rel = gatilho.rodar(b.raiz, parar=parar)
            aberta = "9000019ANA" in gr.abertas()
        self.assertEqual([p.plano for p in rel.exportados], ["P1"])
        self.assertTrue(rel.interrompida)
        self.assertTrue(aberta)


class Interrupcao(unittest.TestCase):

    def test_falha_de_rede_para_a_varredura(self):
        """Sem rede, os próximos vão falhar igual — vinte linhas repetidas no
        histórico escondem a única que importa."""
        prontos = [_pronto(UID, plano="P1"), _pronto(UID2, plano="P2")]
        with _Bancada([_ativ(1149015, "9000019ANA")], prontos) as b, \
                Servidor([UID, UID2], derruba=True):
            rel = gatilho.rodar(b.raiz)
        self.assertTrue(rel.interrompida)
        self.assertEqual(rel.exportados, [])
        # Interrompida, não "incompleta": são coisas diferentes e a primeira é
        # a que manda chamar a TI.
        self.assertEqual(rel.incompletos, [])

    def test_um_plano_que_falha_nao_impede_o_outro(self):
        """UID que o servidor não tem: o conjunto vem vazio e vira incompleto,
        e o plano seguinte ainda sai."""
        prontos = [_pronto("1.2.246.352.71.5.404.404.29990101000000",
                           plano="SUMIDO"),
                   _pronto(UID2, plano="BOM")]
        with _Bancada([_ativ(1149015, "9000019ANA")], prontos) as b, \
                Servidor([UID2]):
            rel = gatilho.rodar(b.raiz)
        self.assertEqual([p.plano for p in rel.exportados], ["BOM"])
        self.assertEqual(len(rel.incompletos), 1)
        self.assertFalse(rel.interrompida)


class Portao(unittest.TestCase):

    def test_sem_conferencia_nada_sai(self):
        """O ``VERIFICADO_EM`` do ``gatilho_db`` está vazio: em produção, hoje,
        a varredura não roda — e é assim que tem de ser.

        Os dois degraus de baixo são fixados à mão, e isso não é cerimônia: sem
        eles, o teste passava sozinho e reprovava na suíte inteira, porque o
        ``capa_db.configurado`` desta máquina depende de qual teste rodou antes
        — e aí o portão fechava pelo motivo errado. Foi assim que ele quebrou
        na primeira rodada completa, em 02/09/2026.
        """
        antes = (capa_db.configurado, atividades_db.disponivel,
                 gatilho_db.VERIFICADO_EM)
        capa_db.configurado = lambda: True
        atividades_db.disponivel = lambda: True
        # A data é APAGADA aqui de propósito. Ela foi preenchida em 04/09/2026,
        # e ler a constante entregue faria este teste medir o estado do projeto
        # em vez da regra — passando hoje por acaso e voltando a passar no dia
        # em que alguém a apagasse por engano.
        gatilho_db.VERIFICADO_EM = ""
        try:
            with tempfile.TemporaryDirectory() as pasta:
                rel = gatilho.rodar(Path(pasta))
        finally:
            (capa_db.configurado, atividades_db.disponivel,
             gatilho_db.VERIFICADO_EM) = antes
        self.assertFalse(rel.rodou)
        self.assertIn("não foi conferida", rel.portao)
        self.assertIn("Não rodou", rel.resumo())

    def test_diz_qual_metade_falta(self):
        """Conferir a consulta e cadastrar o AE Title são chamados diferentes,
        e um aviso só para os dois manda abrir o errado."""
        antes = gatilho_db.disponivel
        gatilho_db.disponivel = lambda: True
        try:
            with tempfile.TemporaryDirectory() as pasta:
                rel = gatilho.rodar(Path(pasta))
        finally:
            gatilho_db.disponivel = antes
        self.assertIn("ISOCENTRO_DICOM_SERVIDOR", rel.portao)


class Vencimento(unittest.TestCase):

    def test_janela_vencida_fecha_com_o_motivo(self):
        """"Sumiu" e "venceu sem plano aprovado" são coisas diferentes, e só a
        segunda faz alguém ir olhar o caso."""
        with _Bancada([_ativ(1, "AAA")], []) as b, Servidor([UID]):
            gatilho.rodar(b.raiz)
            futuro = datetime.now() + timedelta(days=gr.DIAS_DE_JANELA + 1)
            rel = gatilho.rodar(b.raiz, agora=futuro)
            entrada = gr.ler()["janela"]["1"]
        self.assertEqual(rel.vencidos, [1])
        self.assertEqual(entrada["motivo"], gatilho.MOTIVO_VENCIDO)


class Limpeza(unittest.TestCase):
    """A temporária depois que o caso serviu — frente 4, 14/09/2026.

    Apagar não se desfaz, e estes testes são a única rede: a varredura roda
    sozinha, num serviço, sobre a pasta que guarda o DICOM de pacientes.
    """

    def _exportar_um(self, b):
        gatilho.rodar(b.raiz)
        destino = gr.ler()["exportados"][f"{UID}|Planning Approved"]["destino"]
        pasta = Path(destino)
        self.assertTrue(pasta.is_dir())
        return pasta

    def test_liberada_ha_mais_de_uma_semana_some_e_fica_anotada(self):
        """O que sobra do caso é o que se escreveu: sem a marca, ninguém
        descobre depois para onde foram os arquivos."""
        with _Bancada([_ativ(1149015, "9000019ANA")], [_pronto(UID)]) as b, \
                Servidor([UID]):
            pasta = self._exportar_um(b)
            gr.anotar_liberada(1149015, "fisico1", "Y:/sim/FULANO_9000019ANA")
            futuro = datetime.now() + timedelta(
                days=gr.DIAS_PARA_LIMPAR_LIBERADA + 1)
            rel = gatilho.rodar(b.raiz, agora=futuro)
            # Conferir DENTRO do ``with``: a bancada apaga o temporário inteiro
            # na saída, e lá fora "a pasta sumiu" seria verdade para qualquer
            # código — inclusive para o que não apagou nada.
            self.assertFalse(pasta.exists())
            self.assertEqual([a["instancia"] for a in rel.limpos], [1149015])
            self.assertIn("liberada em",
                          gr.ler()["limpos"]["1149015"]["motivo"])
            # As mães vazias saem junto, e a raiz NUNCA sai. O que sobra nela é
            # a trava da varredura, que é da PASTA e não do caso: ela nasce na
            # primeira rodada e não é apagada nunca — apagar deixaria o arquivo
            # em *delete pending* no Windows, e a rodada seguinte pegaria
            # ``PermissionError`` em vez de "já existe" (ver
            # ``indice.travar_arquivo``).
            self.assertEqual([p.name for p in b.raiz.iterdir()],
                             [gatilho.ARQUIVO_TRAVA])
            self.assertTrue(b.raiz.is_dir())

    def test_liberada_ontem_continua_la(self):
        """Liberar não encerra o caso: uma correção no dia seguinte reabre o
        mesmo paciente, e apagar na mesma rodada mandaria pedir os 205
        arquivos ao ARIA outra vez."""
        with _Bancada([_ativ(1149015, "9000019ANA")], [_pronto(UID)]) as b, \
                Servidor([UID]):
            pasta = self._exportar_um(b)
            gr.anotar_liberada(1149015, "fisico1", "Y:/sim")
            rel = gatilho.rodar(b.raiz, agora=datetime.now() + timedelta(days=1))
            self.assertTrue(pasta.is_dir())
            self.assertEqual(rel.limpos, [])

    def test_caso_que_ninguem_liberou_some_pelo_prazo_maior(self):
        """Sem este segundo prazo a temporária cresce para sempre: o caso que
        ninguém libera é justamente o que ninguém volta para limpar."""
        with _Bancada([_ativ(1149015, "9000019ANA")], [_pronto(UID)]) as b, \
                Servidor([UID]):
            pasta = self._exportar_um(b)
            meio = datetime.now() + timedelta(
                days=gr.DIAS_PARA_LIMPAR_LIBERADA + 1)
            self.assertEqual(gatilho.rodar(b.raiz, agora=meio).limpos, [],
                             "o prazo do liberado não vale para quem nunca "
                             "foi liberado")
            self.assertTrue(pasta.is_dir())
            futuro = datetime.now() + timedelta(
                days=gr.DIAS_PARA_LIMPAR_PARADA + 1)
            rel = gatilho.rodar(b.raiz, agora=futuro)
            self.assertFalse(pasta.exists())
            self.assertEqual(len(rel.limpos), 1)
            self.assertIn("sem liberação",
                          gr.ler()["limpos"]["1149015"]["motivo"])

    def test_pasta_fora_da_raiz_de_agora_nao_e_apagada(self):
        """Destino anotado quando a exportação apontava para outro lugar. A
        varredura não é dona daquela pasta, e apagar não se desfaz."""
        with _Bancada([_ativ(1149015, "9000019ANA")], [_pronto(UID)]) as b, \
                Servidor([UID]):
            self._exportar_um(b)
            fora = b.raiz.parent / "exportacao_antiga" / "9000019ANA"
            fora.mkdir(parents=True)
            (fora / "RTPLAN.dcm").write_bytes(b"nao me apague")
            dados = gr.ler()
            dados["exportados"][f"{UID}|Planning Approved"]["destino"] = str(fora)
            gr._gravar(dados)
            futuro = datetime.now() + timedelta(
                days=gr.DIAS_PARA_LIMPAR_PARADA + 1)
            rel = gatilho.rodar(b.raiz, agora=futuro)
            self.assertTrue((fora / "RTPLAN.dcm").exists())
            self.assertEqual(rel.limpos, [])
            self.assertNotIn("1149015", gr.ler()["limpos"],
                             "não apagou: anotar limpeza seria mentir")


class NomeDePasta(unittest.TestCase):

    def test_barra_no_nome_do_curso_nao_escapa_da_pasta(self):
        """``CourseId`` e ``PlanSetupId`` vêm do ARIA, e ninguém promete que não
        têm barra — uma bastaria para gravar em outro lugar."""
        p = _pronto(UID, curso="C1/2026", plano="a:b")
        caminho = gatilho.caminho_do_plano(p, Path("/raiz"))
        self.assertEqual(caminho.parts[-2:], ("C1_2026", "a_b"))

    def test_nome_vazio_vira_algo(self):
        p = _pronto(UID, curso="   ", plano="")
        caminho = gatilho.caminho_do_plano(p, Path("/raiz"))
        self.assertEqual(caminho.parts[-2:], ("sem-nome", "sem-nome"))


def _cadastrar_simulacao(registro="9000019ANA") -> str:
    """Um cadastro de verdade, pela gravação da tela de Simulação."""
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (40, 30), (40, 90, 150)).save(buf, format="JPEG")
    sim = simulacao.Simulacao(nome="Beltrano, Lauro", registro=registro)
    sim.setups = [capa_dados.Setup(nome="CRANIO", fotos=[buf.getvalue()])]
    return simulacao.cadastrar(sim)


class Preparo(unittest.TestCase):
    """O que a Fichinha vai ler para dizer ``● PRONTA`` ou ``⚠ incompleta``."""

    def _preparo(self):
        return gr.ler()["exportados"][f"{UID}|Planning Approved"]["preparo"]

    def test_com_cadastro_anota_onde_ele_esta_e_nao_copia(self):
        """Decisão de 11/09/2026: a cópia na pasta do plano passaria na frente
        do cadastro (``setups_da_pasta`` lê a pasta carregada primeiro), e
        fotos refeitas depois da preparação sairiam antigas, sem aviso."""
        with _Bancada([_ativ(1149015, "9000019ANA")], [_pronto(UID)]) as b, \
                Servidor([UID]):
            cadastro = _cadastrar_simulacao()
            gatilho.rodar(b.raiz)
            preparo = self._preparo()
            pasta = gatilho.caminho_do_plano(_pronto(UID), b.raiz)
            recibo = json.loads((pasta / "exportacao.json").read_text("utf-8"))
            copiados = sorted(p.name for p in pasta.iterdir()
                              if not p.name.endswith(".dcm"))
        self.assertEqual(preparo, {"estado": gatilho.ESTADO_PRONTA,
                                   "simulacao": cadastro, "avisos": []})
        self.assertEqual(recibo["preparo"], preparo)
        self.assertEqual(copiados, ["exportacao.json"])

    def test_sem_cadastro_sai_pronta_com_o_aviso(self):
        """Decisão de 11/09/2026: o físico monta o posicionamento à mão, como
        hoje. Travar o caso por falta de foto deixaria o paciente sem ficha."""
        with _Bancada([_ativ(1149015, "9000019ANA")], [_pronto(UID)]) as b, \
                Servidor([UID]):
            rel = gatilho.rodar(b.raiz)
            preparo = self._preparo()
        self.assertEqual(len(rel.exportados), 1)
        self.assertEqual(preparo["estado"], gatilho.ESTADO_PRONTA)
        self.assertEqual(preparo["avisos"], [gatilho.AVISO_SEM_SIMULACAO])

    def test_raiz_fora_de_alcance_nao_vira_sem_cadastro(self):
        """Na concentradora sem ``RAIZ_SIMULACOES`` no ``config_servico``, a
        raiz é o Documentos do usuário. "Sem cadastro" para TODO paciente
        mandaria cadastrar quem já está cadastrado; a providência é configurar
        a máquina."""
        with _Bancada([_ativ(1149015, "9000019ANA")], [_pronto(UID)]) as b, \
                Servidor([UID]):
            os.environ[simulacao.PASTA_ENV] = str(b.simulacoes / "nao-existe")
            gatilho.rodar(b.raiz)
            preparo = self._preparo()
        self.assertEqual(preparo["estado"], gatilho.ESTADO_PRONTA)
        self.assertNotIn(gatilho.AVISO_SEM_SIMULACAO, preparo["avisos"])
        self.assertEqual(len(preparo["avisos"]), 1)
        self.assertIn("não é alcançada", preparo["avisos"][0])

    def test_o_motivo_do_incompleto_fica_e_some_quando_o_plano_sai(self):
        """O ``Relatorio`` morre com a rodada, e mora na concentradora. Sem o
        motivo no registro, a Fichinha de outra estação não teria o que pôr no
        tooltip do ``⚠``; e se ele ficasse depois da saída, o mesmo plano
        apareceria pronto E incompleto."""
        chave = f"{UID}|Planning Approved"
        with _Bancada([_ativ(1149015, "9000019ANA")], [_pronto(UID)]) as b:
            with Servidor([UID], aceita_get=False):
                gatilho.rodar(b.raiz)
                travado = dict(gr.ler()["incompletos"])
            with Servidor([UID]):
                gatilho.rodar(b.raiz)
                depois = gr.ler()["incompletos"]
        self.assertEqual(list(travado), [chave])
        self.assertTrue(travado[chave]["motivo"].startswith(
            "o DICOM chegou pela metade"), travado[chave]["motivo"])
        self.assertEqual(depois, {})

    def test_incompleto_com_o_mesmo_motivo_nao_regrava(self):
        """Uma escrita no share a cada rodada para dizer que nada mudou; e o
        ``desde`` é o que diz há quanto tempo o plano está travado."""
        chave = f"{UID}|Planning Approved"
        with _Bancada():
            gr.anotar_incompleto(_pronto(UID), "motivo A")
            dados = gr.ler()
            dados["incompletos"][chave]["desde"] = "2026-09-01T08:00:00"
            gr._gravar(dados)
            gr.anotar_incompleto(_pronto(UID), "motivo A")
            igual = gr.ler()["incompletos"][chave]
            gr.anotar_incompleto(_pronto(UID), "motivo B")
            mudou = gr.ler()["incompletos"][chave]
        self.assertEqual(igual["desde"], "2026-09-01T08:00:00")
        self.assertEqual(mudou["motivo"], "motivo B")
        self.assertEqual(mudou["desde"], "2026-09-01T08:00:00")


class OndeOsArquivosCaem(unittest.TestCase):
    """A pasta é decisão do ADMIN, e a tela tem de poder dizer qual venceu.

    Pedido em 04/09/2026, e a razão é de administração, não de programação:
    configurada por estação, uma máquina esquecida gravaria os planos na pasta
    do programa — em silêncio, porque gravar dá certo. Quem administra precisa
    poder afirmar que tudo cai no servidor.
    """

    def setUp(self):
        self._antes_env = os.environ.get("ISOCENTRO_EXPORTACAO")
        self._antes_novo = os.environ.get("ISOCENTRO_EXPORTACAO")
        os.environ.pop("ISOCENTRO_EXPORTACAO", None)
        os.environ.pop("ISOCENTRO_EXPORTACAO", None)
        from isocentro.dados import config_servico
        self._cs = config_servico
        self._antes_valor = config_servico.valor

    def tearDown(self):
        self._cs.valor = self._antes_valor
        for nome, valor in (("ISOCENTRO_EXPORTACAO", self._antes_env),
                            ("ISOCENTRO_EXPORTACAO", self._antes_novo)):
            if valor is None:
                os.environ.pop(nome, None)
            else:
                os.environ[nome] = valor

    def _servico(self, caminho):
        self._cs.valor = lambda chave: (
            caminho if chave == self._cs.PASTA_EXPORTACAO else "")

    def test_sem_nada_cai_ao_lado_do_indice(self):
        self._servico("")
        self.assertEqual(gatilho.pasta_destino().name, "exportacao")
        self.assertIn("padrão", gatilho.origem_da_pasta())

    def test_a_configuracao_do_servico_vale_para_todas_as_estacoes(self):
        self._servico(r"\\fileserver\Gerenciamento de Pacientes\exportacao")
        self.assertEqual(str(gatilho.pasta_destino()),
                         r"\\fileserver\Gerenciamento de Pacientes\exportacao")
        self.assertIn("serviço", gatilho.origem_da_pasta())

    def test_a_variavel_da_estacao_vence_a_do_servico(self):
        """Quem montou AQUELA máquina tem de poder mandar nela — e a tela diz
        que é isso que está acontecendo, senão o admin aponta a pasta, não vê
        efeito, e não tem como descobrir por quê."""
        self._servico(r"\\fileserver\exportacao")
        os.environ["ISOCENTRO_EXPORTACAO"] = r"D:\local"
        self.assertEqual(str(gatilho.pasta_destino()), r"D:\local")
        self.assertIn("estação", gatilho.origem_da_pasta())

    def test_config_ilegivel_nao_derruba_a_varredura(self):
        """Ela cai no padrão, que é uma pasta do serviço de qualquer forma —
        exportar noutro lugar é ruim, não exportar é pior."""
        def explode(_chave):
            raise OSError("config corrompida")

        self._cs.valor = explode
        self.assertEqual(gatilho.pasta_destino().name, "exportacao")


class QuemVarre(unittest.TestCase):
    """Só a concentradora varre — a pergunta 1 do roteiro de instalação.

    Decisão do usuário em 18/09/2026. Com a rede DICOM no ``config_servico``,
    que é o MESMO arquivo para todas as estações, o relógio de cada app aberto
    achava o portão aberto: todas pediam C-MOVE, o ARIA entregava só na máquina
    cadastrada, e quem segurava a trava da pasta sem receber nada fazia a rodada
    da concentradora sair PULADA, verde no Agendador.
    """

    _REDE = {"dicom_servidor": "srvariadb:51404", "dicom_ae_remoto": "ARIA",
             "dicom_ae_local": "RADIOTERAFICHA"}

    def setUp(self):
        from isocentro.dados import ambiente, config_servico
        from isocentro.adaptadores.dicom import rede as dicom_rede
        self._cs = config_servico
        self._envs = ["COMPUTERNAME"]
        for base in (dicom_rede.ENV_SERVIDOR, dicom_rede.ENV_AE_REMOTO,
                     dicom_rede.ENV_AE_LOCAL, dicom_rede.ENV_AE_DESTINO):
            self._envs += [base, ambiente.nome_novo(base)]
        self._antes_env = {n: os.environ.get(n) for n in self._envs}
        for n in self._envs:
            os.environ.pop(n, None)
        os.environ["COMPUTERNAME"] = "CLINICA-PYTHON01"
        self._antes = (config_servico.valor, gatilho_db.disponivel)
        gatilho_db.disponivel = lambda: True
        self._servico = {}
        config_servico.valor = lambda chave: self._servico.get(chave, "")

    def tearDown(self):
        self._cs.valor, gatilho_db.disponivel = self._antes
        for nome, valor in self._antes_env.items():
            if valor is None:
                os.environ.pop(nome, None)
            else:
                os.environ[nome] = valor

    def _rede_no_arquivo(self, concentradora=""):
        self._servico = dict(self._REDE)
        if concentradora:
            self._servico[self._cs.CONCENTRADORA] = concentradora

    def _rede_em_variavel(self):
        os.environ["ISOCENTRO_DICOM_SERVIDOR"] = "srvariadb:51404"
        os.environ["ISOCENTRO_DICOM_AE_REMOTO"] = "ARIA"
        os.environ["ISOCENTRO_DICOM_AE_LOCAL"] = "RADIOTERAFICHA"

    def test_a_concentradora_varre(self):
        self._rede_no_arquivo("clinica-python01")
        self.assertTrue(gatilho.disponivel())
        self.assertEqual(gatilho.motivo_indisponivel(), "")

    def test_a_grafia_do_admin_nao_importa(self):
        """Com as barras do caminho de rede, com o domínio, em maiúsculas: o
        admin digita como lembra, e a máquina é a mesma."""
        for grafia in (r"\\CLINICA-PYTHON01", "clinica-python01.clinica.example",
                       "  Clinica-Python01 "):
            with self.subTest(grafia=grafia):
                self._rede_no_arquivo(grafia)
                self.assertTrue(gatilho.disponivel())

    def test_outra_estacao_nao_varre_e_diz_quem_varre(self):
        os.environ["COMPUTERNAME"] = "EST-RT-58"
        self._rede_no_arquivo("clinica-python01")
        self.assertFalse(gatilho.disponivel())
        motivo = gatilho.motivo_indisponivel()
        self.assertIn("EST-RT-58", motivo)
        self.assertIn("clinica-python01", motivo)

    def test_com_a_chave_preenchida_a_variavel_nao_libera_outra_estacao(self):
        """A chave é a decisão do serviço; uma estação que ainda tenha as
        ``ISOCENTRO_DICOM_*`` de algum teste antigo não volta a varrer por isso."""
        os.environ["COMPUTERNAME"] = "EST-RT-58"
        self._rede_em_variavel()
        self._servico = {self._cs.CONCENTRADORA: "clinica-python01"}
        self.assertFalse(gatilho.disponivel())

    def test_ip_na_chave_nao_casa_com_nome_nenhum(self):
        """O nome, não o IP — e o motivo mostra os dois lado a lado, que é
        como o desencontro se vê."""
        self._rede_no_arquivo("192.0.2.20")
        self.assertFalse(gatilho.disponivel())
        self.assertIn("192.0.2.20", gatilho.motivo_indisponivel())

    def test_rede_no_arquivo_sem_a_chave_ninguem_varre(self):
        """Varrer em todas é o defeito; escolher uma sozinho seria adivinhar.
        O motivo manda preencher o campo — pelo nome que a tela mostra."""
        self._rede_no_arquivo()
        self.assertFalse(gatilho.disponivel())
        self.assertIn("Concentradora", gatilho.motivo_indisponivel())

    def test_rede_so_em_variavel_sem_a_chave_varre(self):
        """O regime de 11/09: a rede inteira em variável é decisão de
        instalação de UMA máquina. É também o da bancada de testes."""
        self._rede_em_variavel()
        self.assertTrue(gatilho.disponivel())

    def test_meia_rede_em_variavel_nao_basta(self):
        """Uma das três vindo do arquivo já faz a decisão ser do serviço."""
        self._rede_no_arquivo()
        os.environ["ISOCENTRO_DICOM_AE_LOCAL"] = "RADIOTERAFICHA"
        self.assertFalse(gatilho.disponivel())

    def test_a_rodada_da_outra_estacao_nao_toca_na_pasta(self):
        """Nem a trava: é ela que fazia a rodada da concentradora sair PULADA."""
        os.environ["COMPUTERNAME"] = "EST-RT-58"
        self._rede_no_arquivo("clinica-python01")
        with tempfile.TemporaryDirectory() as pasta:
            rel = gatilho.rodar(Path(pasta))
            self.assertEqual(list(Path(pasta).iterdir()), [])
        self.assertFalse(rel.rodou)
        self.assertIn("concentradora", rel.portao)


if __name__ == "__main__":
    unittest.main()
