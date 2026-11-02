"""Esvazia ``estilo._ouvintes`` entre um teste e o seguinte.

**Por que existe.** Medido em 27/08/2026: os 46 arquivos de teste somam 183 s
rodando um a um, mas a suíte inteira leva 560 s. Os 377 s de diferença não são
teste executando — é ``estilo._ouvintes`` crescendo e nunca encolhendo. Cada
``estilo.pintar`` acrescenta um par à lista, e cada repintura percorre tudo o
que já se acumulou: ao fim do ``test_capa_tela`` são 14 mil registros, e o
arquivo passa de 24 s para 96 s por causa disso.

**Por que não basta varrer.** ``estilo._varrer()`` descarta o registro de quem
já morreu no C++ — em produção isso é suficiente, e é o que mantém a lista
curta numa sessão de trabalho. Em teste não adianta: o ``unittest`` segura as
instâncias de ``TestCase`` até o fim da suíte, elas seguram a janela, e a
janela segura cada widget. Ninguém morre, então não há o que varrer. Medido no
``test_capa_tela``:

    nada                96,1 s   13.979 ouvintes
    _varrer()           85,6 s   13.979
    gc + _varrer()      90,0 s   13.979
    destruir + varrer   83,0 s   13.459
    _ouvintes.clear()   23,6 s        0

**Por que limpar é seguro aqui.** A lista é um registro de "repinte quando o
modo trocar". Cada teste monta a tela de que precisa, e é durante o teste que
os widgets dele se registram — nenhum depende de registro deixado pelo teste
anterior. O que se perde ao limpar é a repintura de widgets que o teste
seguinte não vai olhar.

**Como usar.** No fim de um arquivo de teste que monta tela:

    from tests.limpeza_de_tela import load_tests  # noqa: F401

``load_tests`` é o protocolo do próprio ``unittest``: ele o procura no módulo e
o chama com os testes daquele arquivo, o que deixa envolver cada um sem tocar
nas classes. ``tests`` não é pacote (não tem ``__init__.py``, e isso é
deliberado — ver ``ordem_aleatoria.py``), mas ``import tests.x`` funciona
assim mesmo: o Python trata a pasta como *namespace package*, e a raiz do
projeto já está no ``sys.path`` de todo arquivo de teste.
"""
from __future__ import annotations

import atexit
import os
import shutil
import tempfile
import unittest

# O histórico de uso da SUÍTE vai para uma pasta temporária, desviado aqui, no
# import, uma vez por processo. Medido em 13/10/2026: das 47.928 linhas do
# ``historico_uso.jsonl`` da estação de desenvolvimento, ~46 mil eram da suíte
# (usuário vazio, picos de 115 eventos por minuto) — "app_fechado" e
# "capa_montada" de quatro arquivos de tela, ~74 por rodada. O uso real eram
# menos de 2 mil eventos, e nenhuma conta tirada do arquivo valia nada.
#
# Por que no import e não no ``setUp`` de cada teste: o ``closeEvent`` grava
# quando a janela é COLETADA, e isso acontece depois do teste que a criou — o
# ``test_gui_smoke`` desviava no ``setUp``, devolvia no ``tearDown``, e ainda
# assim escrevia três "app_fechado" no arquivo real. O ``discover`` importa
# todos os arquivos antes de rodar o primeiro teste, então o desvio já vale
# para a suíte inteira, inclusive para quem não monta tela.
#
# O nome NOVO sai do ambiente do processo: ele tem precedência
# (``ambiente.ler``), e numa estação onde a TI o definiu os testes que desviam
# pelo nome antigo escreveriam no log de REDE do serviço.
PASTA_HISTORICO = tempfile.mkdtemp(prefix="historico_suite_")
os.environ.pop("ISOCENTRO_LOG_DIR", None)
os.environ["ISOCENTRO_LOG_DIR"] = PASTA_HISTORICO
atexit.register(shutil.rmtree, PASTA_HISTORICO, True)


def _historico_desviado() -> None:
    """Volta o desvio se um teste o desfez (o ``pop`` no ``tearDown``)."""
    if not os.environ.get("ISOCENTRO_LOG_DIR"):
        os.environ["ISOCENTRO_LOG_DIR"] = PASTA_HISTORICO


def limpar_ouvintes() -> None:
    """Zera a lista de repinturas registradas.

    Importa ``estilo`` aqui dentro, e não no topo: um arquivo de teste que não
    conseguiu montar o Qt (o ``except`` que define ``gui = None``) ainda assim
    importa este módulo, e falhar no import derrubaria o arquivo inteiro por
    uma limpeza que ele nem precisa.
    """
    try:
        from isocentro.interface import estilo
    except Exception:  # noqa: BLE001 — sem estilo não há o que limpar
        return
    estilo._ouvintes.clear()


def _envolver(suite: unittest.TestSuite) -> None:
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            _envolver(item)
            continue
        original = item.tearDown

        def _com_limpeza(_original=original):
            try:
                _original()
            finally:
                # No ``finally``: teste que falha no tearDown é justamente o
                # que mais deixa widget para trás.
                limpar_ouvintes()
                _historico_desviado()

        item.tearDown = _com_limpeza


def load_tests(loader, standard_tests, pattern):  # noqa: ARG001 — assinatura do unittest
    """Protocolo do unittest: devolve os testes do módulo, já envolvidos."""
    _envolver(standard_tests)
    return standard_tests
