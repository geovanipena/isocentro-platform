"""A lista de loggers que chegam ao histórico não pode envelhecer calada.

Em 27/08/2026 descobriu-se que DEZESSEIS módulos com logger próprio estavam
fora da lista. Entre eles o ``capa_db`` e o ``tratamento_db``: quando o banco
caía numa estação, o aviso ia para o log local e o admin — que lê o histórico
compartilhado justamente para saber de que estação veio a falha — não via
nada.

Ninguém tinha percebido porque o sintoma é uma AUSÊNCIA. O histórico não
mostra o que não sabe que existe, então a lista errada parecia uma lista certa
com pouca coisa acontecendo. Um módulo novo que loga entra calado no mesmo
buraco; este teste é o que avisa.

A lista saiu do ``gui.py`` para o ``dados/log_app.py`` em 14/09/2026, quando a
varredura ganhou porta de entrada própria (o executável sem tela da
concentradora, que não pode importar a interface só para deixar rastro). De
graça veio o que este arquivo mais precisava: a conferência deixou de subir o
Qt para perguntar uma coisa que é de texto.
"""
import ast
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

# Não são o programa: cópias empacotadas dele, a venv, os testes e as
# ferramentas de linha de comando (que rodam fora do app e não têm histórico
# compartilhado para alimentar).
FORA_DO_PROGRAMA = {".venv", "build", "dist", "distribuicao", "__pycache__",
                    "tests", "tools"}


_ACHADOS: dict[str, Path] = {}


def _modulos_que_logam() -> dict[str, Path]:
    """Os módulos do programa que criam um logger próprio, pelo CAMINHO.

    Lê o CÓDIGO em vez de importar: importar ``gui`` e companhia levanta
    janela, lê configuração do serviço e tenta o banco — caro e frágil para
    uma pergunta que o texto do arquivo já responde.

    Guarda o ``Path`` e não ``caminho.name`` por causa do que o NOME custava do
    outro lado: o segundo teste redescobria cada arquivo com
    ``fontes.texto(nome)``, e o cache do ``fontes`` é por nome — 30 módulos com
    logger viravam 30 ``rglob`` completos sobre os 6.856 ``.py`` da raiz, 6.674
    deles da ``.venv``, que o filtro só descarta DEPOIS. Medido em 14/09/2026:
    o teste sozinho custava 20,3 s dos 270 s da suíte, e o caminho já estava
    aqui na mão o tempo todo.

    O resultado fica em ``_ACHADOS`` porque os dois testes fazem a MESMA
    varredura e o disco não muda no meio da suíte.
    """
    if _ACHADOS:
        return _ACHADOS
    for caminho in sorted(RAIZ.rglob("*.py")):
        if FORA_DO_PROGRAMA & set(caminho.relative_to(RAIZ).parts):
            continue
        # utf-8-sig porque posicionamento.py tem BOM.
        fonte = caminho.read_text(encoding="utf-8-sig", errors="replace")
        try:
            arvore = ast.parse(fonte)
        except SyntaxError:  # pragma: no cover — outro teste pega isso
            continue
        for no in ast.walk(arvore):
            if (isinstance(no, ast.Call)
                    and isinstance(no.func, ast.Attribute)
                    and no.func.attr == "getLogger"):
                _ACHADOS[caminho.stem] = caminho
                break
    return _ACHADOS


class TestLoggersDoApp(unittest.TestCase):

    def test_todo_modulo_que_loga_chega_ao_historico(self):
        """Módulo com logger fora da lista some do histórico sem avisar.

        Foi o que aconteceu com ``capa_db``: o app registrava "sem conexão com
        o servidor" e o admin nunca ficava sabendo. O sintoma de estar fora é
        NÃO aparecer nada — por isso a lista precisa de um teste e não de
        atenção.
        """
        from isocentro.dados import log_app

        que_logam = _modulos_que_logam()
        self.assertTrue(que_logam, "não achei módulo nenhum com logger — o "
                                   "varredor quebrou, não o programa")

        fora = sorted(m for m in que_logam if m not in log_app.LOGGERS_APP)
        self.assertEqual(
            fora, [],
            "estes módulos criam logger mas NÃO estão em log_app.LOGGERS_APP, "
            "então as falhas deles não chegam ao histórico compartilhado: "
            f"{fora}. Acrescente cada um à lista em dados/log_app.py.")

    def test_a_falha_de_um_modulo_do_pacote_chega_ao_historico(self):
        """Estar na lista não bastava: o filtro comparava o nome INTEIRO.

        Desde a mudança para o pacote ``isocentro/`` (09/09/2026), o logger do
        ``dicom_rt`` se chama ``isocentro.dicom.dicom_rt``, e a lista guarda
        ``dicom_rt``. O teste acima passava — todo módulo estava na lista — e
        nenhuma falha do app chegava ao histórico. Achado em 22/10/2026.
        """
        import logging
        from unittest import mock

        from isocentro.dados import log_app
        from isocentro.dicom import dicom_rt

        registro = logging.LogRecord(dicom_rt._LOG.name, logging.WARNING,
                                     __file__, 1, "falha de teste", None, None)
        with mock.patch.object(log_app.historico, "registrar") as registrar:
            log_app.HandlerHistorico().emit(registro)
        registrar.assert_called_once()
        self.assertEqual(registrar.call_args.kwargs["detalhes"]["origem"],
                         "isocentro.dicom.dicom_rt")

        # E a biblioteca de fora continua de fora.
        de_fora = logging.LogRecord("pydicom.config", logging.WARNING,
                                    __file__, 1, "barulho", None, None)
        with mock.patch.object(log_app.historico, "registrar") as registrar:
            log_app.HandlerHistorico().emit(de_fora)
        registrar.assert_not_called()

    def test_o_logger_tem_o_nome_do_modulo(self):
        """``getLogger("outro_nome")`` faz a origem no histórico mentir.

        Enquanto a lista estava errada, dois módulos recém-separados do gui.py
        contornaram o problema pedindo ``getLogger("gui")`` — funcionava, mas o
        histórico dizia que a falha do visualizador vinha do ``gui``. Com a
        lista correta o contorno não é mais preciso, e este teste impede que
        ele volte.
        """
        for caminho in sorted(_modulos_que_logam().values()):
            # utf-8-sig porque posicionamento.py tem BOM.
            fonte = caminho.read_text(encoding="utf-8-sig", errors="replace")
            for no in ast.walk(ast.parse(fonte)):
                if not (isinstance(no, ast.Call)
                        and isinstance(no.func, ast.Attribute)
                        and no.func.attr == "getLogger"):
                    continue
                if not no.args:
                    continue
                arg = no.args[0]
                # Só o literal de texto é problema. ``getLogger(__name__)`` é
                # um ast.Name e nem tem ``.value`` — ler o atributo antes de
                # saber o tipo foi o primeiro jeito de escrever isto, e o
                # próprio teste morria de AttributeError em vez de acusar.
                if not (isinstance(arg, ast.Constant)
                        and isinstance(arg.value, str)):
                    continue
                self.fail(
                    f"{caminho.name}:{no.lineno} chama getLogger({arg.value!r}) em "
                    "vez de getLogger(__name__) — a origem no histórico vai "
                    "mentir sobre de qual módulo veio a falha.")


if __name__ == "__main__":
    unittest.main()
