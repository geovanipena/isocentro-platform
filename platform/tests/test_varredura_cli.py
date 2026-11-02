"""O código de saída é o que a Tarefa Agendada mostra — e é tudo o que ela mostra.

A varredura passou a ter uma porta de entrada sem tela (14/09/2026), chamada
pelo Agendador do Windows na concentradora. Ninguém olha a saída dela todo dia:
o que alguém olha, quando desconfia, é a coluna "último resultado" da tarefa. Se
"não exportou nada porque o DICOM não está configurado" sair com o mesmo código
de "rodou e não havia nada a fazer", a automação pode passar semanas parada
parecendo saudável — que é exatamente o modo de falhar que este projeto inteiro
tenta fechar.

O que estes testes fixam:

* **portão fechado é diferente de rodada vazia** (2 contra 0);
* **pulada por outra em curso é 0**: a trava funcionando não é erro, e tarefa
  que fica vermelha à toa ensina a ignorar o Agendador;
* **interrompida no meio é 1**: começou, e parou por rede;
* **exceção inesperada é 4, sem traceback na tela** — traceback no "último
  resultado" não é lido por ninguém, e o ``rodar`` promete não levantar;
* **``--conferir`` não exporta nada.** É o que se roda antes de cadastrar a
  tarefa, e um "conferir" que mexesse no ARIA não poderia ser rodado à toa.

Rodar:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import contextlib
import io
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
for _p in (str(RAIZ), str(RAIZ / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import varredura_cli  # noqa: E402
from isocentro.dominio import gatilho  # noqa: E402


def _pronto(plano="cCRANIO_20Gy"):
    return gatilho.gatilho_db.Pronto(
        registro="9000019ANA", paciente="Beltrano, Lauro", instancia=1,
        dim_curso=1, curso="C1", plano=plano, plan_uid="1.2.3",
        estado="Planning Approved", revisao=0, fracoes=5, aprovado_por="x",
        criado_em=None)


class _Bancada:
    """Troca o domínio inteiro por respostas combinadas — e DEVOLVE tudo.

    ``modulo.f = falsa`` grava no ``__dict__`` do módulo; o ``del`` depois some
    com a ORIGINAL para o resto do processo. Guardar e devolver, sempre.

    O ``log_app.configurar`` também entra: sem isto cada teste acrescentaria um
    handler ao logger raiz e escreveria no ``~/.isocentro.log`` de quem
    roda a suíte.
    """

    def __init__(self, relatorio=None, disponivel=True, levanta=False):
        self.relatorio = relatorio
        self.disponivel = disponivel
        self.levanta = levanta
        self.rodou = 0

    def __enter__(self):
        self._antes = {
            "rodar": gatilho.rodar,
            "disponivel": gatilho.disponivel,
            "motivo": gatilho.motivo_indisponivel,
            "destino": gatilho.pasta_destino,
            "origem": gatilho.origem_da_pasta,
            "configurar": varredura_cli.log_app.configurar,
        }

        def _rodar(raiz=None, agora=None, parar=None):
            self.rodou += 1
            if self.levanta:
                raise RuntimeError("defeito nosso")
            return self.relatorio

        gatilho.rodar = _rodar
        gatilho.disponivel = lambda: self.disponivel
        gatilho.motivo_indisponivel = lambda: "falta o AE Title desta estação"
        gatilho.pasta_destino = lambda: Path("Z:/exportacao")
        gatilho.origem_da_pasta = lambda: "configuração do serviço"
        varredura_cli.log_app.configurar = lambda: None
        return self

    def __exit__(self, *_):
        gatilho.rodar = self._antes["rodar"]
        gatilho.disponivel = self._antes["disponivel"]
        gatilho.motivo_indisponivel = self._antes["motivo"]
        gatilho.pasta_destino = self._antes["destino"]
        gatilho.origem_da_pasta = self._antes["origem"]
        varredura_cli.log_app.configurar = self._antes["configurar"]
        return False


def _rodar_cli(*argv):
    """Chama o ``main`` engolindo a saída, e devolve ``(código, texto)``."""
    saida = io.StringIO()
    with contextlib.redirect_stdout(saida):
        codigo = varredura_cli.main(list(argv))
    return codigo, saida.getvalue()


class CodigoDeSaida(unittest.TestCase):

    def test_rodada_normal_e_zero(self):
        rel = gatilho.Relatorio(exportados=[_pronto()])
        with _Bancada(rel):
            codigo, texto = _rodar_cli()
        self.assertEqual(codigo, varredura_cli.SAIU_OK)
        self.assertIn("cCRANIO_20Gy", texto)

    def test_rodada_vazia_tambem_e_zero(self):
        """Não achar nada é o caso comum, de cinco em cinco minutos o dia
        inteiro. Sair diferente de zero pintaria a tarefa de vermelho para
        sempre, e o vermelho deixaria de querer dizer alguma coisa."""
        with _Bancada(gatilho.Relatorio()):
            codigo, _ = _rodar_cli()
        self.assertEqual(codigo, varredura_cli.SAIU_OK)

    def test_portao_fechado_sai_diferente_de_zero(self):
        """É a razão de este arquivo existir: sem isto, "a automação está
        parada há duas semanas" tem a mesma cara de "não havia nada hoje"."""
        rel = gatilho.Relatorio(portao="falta o AE Title desta estação")
        with _Bancada(rel):
            codigo, texto = _rodar_cli()
        self.assertEqual(codigo, varredura_cli.SAIU_PORTAO)
        self.assertIn("NÃO RODOU", texto)
        self.assertIn("AE Title", texto)

    def test_pulada_por_outra_em_curso_e_zero(self):
        """A trava funcionando não é erro — ver a docstring do módulo."""
        rel = gatilho.Relatorio(portao=gatilho.MOTIVO_OCUPADA)
        with _Bancada(rel):
            codigo, texto = _rodar_cli()
        self.assertEqual(codigo, varredura_cli.SAIU_OK)
        self.assertIn("PULADA", texto)

    def test_interrompida_no_meio_sai_um(self):
        rel = gatilho.Relatorio(interrompida="a rede não respondeu")
        with _Bancada(rel):
            codigo, texto = _rodar_cli()
        self.assertEqual(codigo, varredura_cli.SAIU_INTERROMPIDA)
        self.assertIn("a rede não respondeu", texto)

    def test_excecao_inesperada_sai_quatro_e_nao_cospe_traceback(self):
        """O ``rodar`` promete não levantar. Se levantou é defeito nosso — e o
        lugar do traceback é o log, não a coluna do Agendador."""
        with _Bancada(levanta=True):
            codigo, texto = _rodar_cli()
        self.assertEqual(codigo, varredura_cli.SAIU_ERRO)
        self.assertIn("ERRO INESPERADO", texto)
        self.assertNotIn("Traceback", texto)


class Conferir(unittest.TestCase):
    """O ``--conferir`` é o passo anterior a cadastrar a tarefa."""

    def test_conferir_nao_exporta_nada(self):
        with _Bancada(gatilho.Relatorio()) as b:
            codigo, texto = _rodar_cli("--conferir")
        self.assertEqual(b.rodou, 0, "o --conferir chamou a varredura")
        self.assertEqual(codigo, varredura_cli.SAIU_OK)
        self.assertIn("PORTÃO ABERTO", texto)

    def test_conferir_com_portao_fechado_diz_qual_metade_falta(self):
        """Banco e DICOM dão o mesmo "não exportou nada" e pedem providências
        opostas: uma é a tela de Configurações, a outra é a TI."""
        with _Bancada(disponivel=False):
            codigo, texto = _rodar_cli("--conferir")
        self.assertEqual(codigo, varredura_cli.SAIU_PORTAO)
        self.assertIn("PORTÃO FECHADO", texto)
        self.assertIn("AE Title", texto)

    def test_diz_a_conta_e_o_degrau_que_venceu(self):
        """Numa Tarefa Agendada o degrau que vale muda com a CONTA que roda, e
        "não exportou nada" tem cara igual nos dois casos."""
        with _Bancada(gatilho.Relatorio()):
            _codigo, texto = _rodar_cli("--conferir")
        self.assertIn("Conta do Windows", texto)
        self.assertIn("configuração do serviço", texto)

    def test_diz_de_onde_leu_a_configuracao_e_onde_cai_o_estado(self):
        """Os dois arquivos do SERVIÇO saem de ``pasta_do_app()``, que
        empacotado é a pasta do próprio ``.exe``.

        Instalado fora da pasta compartilhada do app, este binário lê um
        ``config_servico.json`` vazio — as quatro chaves do DICOM não chegam,
        e o portão fecha — e grava o ``gatilho_registro.json`` onde nenhuma
        estação enxerga, deixando a Fichinha sem caso pronto nenhum. Os dois
        se parecem com "não havia nada para exportar", e é por isso que os
        caminhos são impressos: sem eles, diagnosticar isso na clínica é
        adivinhação, e quem está lá não tem o código na mão.
        """
        with _Bancada(gatilho.Relatorio()):
            _codigo, texto = _rodar_cli("--conferir")
        self.assertIn("Configuração", texto)
        self.assertIn("config_servico.json", texto)
        self.assertIn("Estado da automação", texto)
        self.assertIn("gatilho_registro.json", texto)

    def test_diz_quem_e_a_concentradora_e_quem_e_esta_maquina(self):
        """Os dois nomes lado a lado (18/09/2026): o desencontro mais provável
        é de GRAFIA — o IP no lugar do nome, a máquina errada —, e ele só se vê
        comparando. Sem a linha, o portão fechado na concentradora parece o
        mesmo "falta configuração" de sempre."""
        antes = (gatilho.concentradora, gatilho.nome_desta_maquina)
        gatilho.concentradora = lambda: "clinica-python01"
        gatilho.nome_desta_maquina = lambda: "EST-RT-58"
        try:
            with _Bancada(gatilho.Relatorio()):
                _codigo, texto = _rodar_cli("--conferir")
        finally:
            gatilho.concentradora, gatilho.nome_desta_maquina = antes
        self.assertIn("Concentradora       : clinica-python01", texto)
        self.assertIn("esta máquina: EST-RT-58", texto)


if __name__ == "__main__":
    unittest.main()
