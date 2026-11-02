"""Onde o rastro do programa é configurado — e quem dele chega ao admin.

Isto morava no ``gui.py`` até 14/09/2026, e saiu de lá pelo motivo que a
varredura trouxe: a exportação automática passou a ter uma porta de entrada
PRÓPRIA (o executável sem tela, chamado pela Tarefa Agendada da
concentradora), e essa porta não pode importar a interface só para deixar
rastro — o pacote dela exclui o PySide6 inteiro.

A alternativa era o ponto de entrada montar o próprio log. Foi recusada pelo
mesmo argumento que faz o ``DENTRO_DO_PACOTE`` do empacotador ser lista única:
**duas listas se afastam em silêncio**. O módulo novo que loga entraria numa e
não na outra, e as falhas dele desapareceriam justamente do lado que roda
sozinho, sem ninguém olhando a tela.

São dois destinos, e eles servem a pessoas diferentes:

* o ARQUIVO, na home de quem rodou — é o rastro cru, para quem abre chamado;
* o HISTÓRICO compartilhado, só WARNING+ e só dos módulos do app — é onde o
  admin vê de QUAL estação veio a falha, sem ir a cada máquina.
"""
from __future__ import annotations

import logging
from pathlib import Path

from isocentro.dados import historico

ARQUIVO = Path.home() / ".isocentro.log"

# Loggers do próprio app (todos usam logging.getLogger(__name__), = nome do
# módulo). Só as falhas destes vão para o histórico compartilhado — o barulho de
# WARNING de bibliotecas (matplotlib/pydicom/PIL/…) fica de fora.
#
# Esta lista JÁ ENVELHECEU CALADA uma vez: em 27/08/2026 dezesseis módulos com
# logger próprio estavam fora dela, e as falhas deles — inclusive as do banco
# (``capa_db``) e as da leitura do tratamento (``tratamento_db``) — nunca
# chegaram ao admin. Ninguém percebeu porque o sintoma é uma AUSÊNCIA: o
# histórico simplesmente não mostra o que não sabe que existe.
#
# Por isso a lista agora tem guarda: ``tests/test_loggers_app.py`` varre os
# módulos do programa e falha se algum criar logger sem estar aqui. Módulo novo
# que loga é módulo que entra nesta lista — o teste avisa, e é isso que impede
# a lista de envelhecer de novo.
LOGGERS_APP = frozenset({
    # Os que já estavam.
    "gui", "dicom_rt", "ficha_pdf", "ct_series", "registro_json", "indice",
    "empacotar", "backup", "auth", "historico", "agendamento", "dose3d",
    "corpo3d", "cortes", "constantes", "diff_versoes", "__main__",
    # A capa e as suas fontes: banco, espelho, relatórios e correções. É aqui
    # que mora a falha que o admin MAIS precisa ver — a capa que saiu de uma
    # reserva porque o banco não respondeu.
    "capa_db", "capa_espelho", "capa_dados", "capa_pdf", "correcoes",
    # O banco LOCAL gravado. Entra pelo motivo mais forte da lista: é ele que
    # avisa, em WARNING, que o app está lendo um ARQUIVO e não o servidor — e
    # esse aviso não pode ser justamente o que não chega ao histórico.
    "banco_local",
    # O servidor LOCAL de demonstração: o que ele loga é a consulta que a
    # tradução de T-SQL não cobriu — sem isto no histórico, a tela vazia na
    # demonstração não teria rastro nenhum.
    "servidor_local",
    # As atividades do ARIA. Entra pelo mesmo motivo do ``banco_local``: o que
    # ela loga é "não deu para perguntar ao servidor" — e é exatamente esse
    # aviso que não pode faltar, porque do lado de fora ele é indistinguível de
    # "não há nada pendente", e quem lê fecha o programa achando que está em dia.
    "atividades_db",
    # O gatilho da exportação automática. Entra pelo motivo mais forte de
    # todos: ele roda SOZINHO, sem ninguém olhando a tela, e o que ele loga é
    # "não deu para perguntar quais planos estão prontos". Uma automação que
    # para de funcionar é silenciosa por natureza — ninguém percebe a ausência
    # de um arquivo —, e o histórico é o único lugar em que isso apareceria.
    "gatilho_db",
    # E a memória dele. Loga a transição ("Documentação de fulano: Open → In
    # Progress") e a saída de cada plano: é o único registro de que a automação
    # rodou. Sem ele no histórico, "nada foi exportado hoje" e "parou de
    # funcionar na semana passada" ficam idênticos.
    "gatilho_registro",
    # E a rede DICOM. Loga a associação e cada falha de transferência; é o
    # único lugar onde "o ARIA recusou o nosso AE Title" aparece, e essa é a
    # frase que resolve o chamado com a TI.
    "rede",
    # E a varredura que amarra as três. É quem loga "exportei" e "ficou
    # incompleto, tenta na próxima" — as duas linhas que dizem se a automação
    # está viva.
    "gatilho",
    # O quadro de Datas Relevantes (v8). É gravação COMPARTILHADA: o arquivo
    # fica ao lado do índice central e qualquer estação escreve nele. O que ele
    # loga é a falha de escrita — arquivo travado por outra estação, share sem
    # permissão —, e do lado de fora isso aparece como o evento que alguém
    # criou e simplesmente não está lá no dia seguinte.
    "datas_relevantes",
    # Tratamento, agenda e cadastro.
    "tratamento", "tratamento_db", "checklist", "simulacao", "inventario",
    "equipe", "notas_setup", "aprendizado",
    # A agenda por máquina (23/09/2026): mesmo motivo do ``tratamento_db`` — o
    # que ela loga é "não deu para consultar o banco", e sem esta linha aqui a
    # aba mostraria "nenhuma marcação" e ninguém saberia se é porque o dia
    # está vazio ou porque a consulta falhou.
    "agenda_db",
    # Administração e configuração do serviço.
    "administracao", "config_servico",
    # A preferência de cada pessoa e a sessão única (23/09/2026). As duas
    # gravam no compartilhado e engolem a falha de propósito — nenhuma pode
    # impedir de trabalhar. O que sobra é o log: sem estas duas linhas aqui, o
    # "não consegui gravar" fica só no arquivo da estação, e da tela isso
    # aparece como "o programa esqueceu meu grupo médico" ou, pior, como a
    # regra de acesso único calada porque nunca conseguiu registrar ninguém.
    "preferencias", "sessao",
    # Saíram do gui.py em 27/08/2026 e continuam sendo o mesmo programa.
    "aparencia", "agendamento_tela", "visualizador", "formulario",
    "edicao_ficha", "carregadores",
    # E a porta de entrada, que saiu em 16/09/2026: é ela que registra o erro
    # não tratado — justamente o que o admin mais precisa ver.
    "arranque",
    # E a Ficha Virtual, que saiu da janela no mesmo dia: é ela que loga
    # "não consegui ler o tratamento", que da tela parece paciente sem dado.
    "controle_virtual",
    # E a Agenda (23/09/2026): o controle loga "falha ao consultar o dia" —
    # sem esta linha, a aba pareceria mostrar "nenhuma marcação" quando na
    # verdade a consulta caiu.
    "controle_agenda",
    # O Radioteradados (protótipo, 13/10/2026): é ele que loga a consulta do
    # mês que caiu — da tela, isso aparece só como travessão na Operação.
    "controle_radioteradados",
    # E o portão da geração: é ele que loga "falha ao ler o convênio", e da
    # tela isso parece só o popup do SUS voltando a perguntar.
    "portao_ficha",
    # E a capa: é ela que loga "falha ao ler os relatórios da capa", e da tela
    # isso parece paciente sem cadastro.
    "controle_capa",
    # E o visualizador: é ele que loga "faixa de isodose: dose de referência
    # ilegível", e da tela isso parece só a faixa que não acompanhou o plano.
    "controle_viewer",
    # E a montagem da ficha: é ela que loga "falha ao juntar a capa — sai só a
    # ficha" e o arquivamento que não gravou, e da tela os dois parecem ficha
    # gerada normalmente.
    "controle_ficha",
    # E este módulo. Ele não loga nada hoje — está aqui porque a guarda do
    # ``tests/test_loggers_app.py`` vê o ``getLogger()`` da raiz logo abaixo, e
    # porque a exceção seria a pior possível de abrir: o dia em que ESTE
    # módulo tiver algo a dizer é o dia em que o rastro não está funcionando, e
    # o histórico compartilhado é a única saída que ainda sobra.
    "log_app",
})


class HandlerHistorico(logging.Handler):
    """Espelha WARNING+ dos módulos do app no histórico compartilhado, para o
    admin ver as falhas de todas as estações num só lugar (com usuário/data)."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            # O último componente: desde 09/09/2026 o ``__name__`` é
            # ``isocentro.dicom.dicom_rt``, e a lista guarda ``dicom_rt``.
            # Comparando o nome inteiro, NENHUMA falha do app chegou ao
            # histórico de 09/09 a 22/10 — de novo uma ausência, que ninguém vê.
            if record.name.rpartition(".")[2] not in LOGGERS_APP:
                return
            historico.registrar("app_erro", detalhes={
                "nivel": record.levelname,
                "origem": record.name,
                "msg": record.getMessage()[:500],
            })
        except Exception:  # noqa: BLE001 — o histórico é acessório
            pass


def configurar() -> None:
    """Manda os erros engolidos para ~/.isocentro.log e, se WARNING+ e de
    um módulo do app, também para o histórico compartilhado.

    O app é empacotado sem console, então uma exceção tratada com ``pass`` não
    deixa rastro nenhum: o SSD sai vazio na ficha, o corpo 3D não aparece, e não
    há como saber por quê. Falhas que o usuário não precisa ver na hora ainda
    são engolidas — mas ficam gravadas.

    Chamado pelas DUAS portas de entrada: o ``arranque.main`` e o executável da
    varredura. Nesse segundo o arquivo é o da conta que a Tarefa Agendada usa,
    e não a de quem se senta na máquina — vale lembrar disso ao procurar o log
    de uma rodada agendada.
    """
    try:
        logging.basicConfig(
            filename=str(ARQUIVO),
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
            encoding="utf-8",
        )
    except OSError:
        pass   # home sem permissão de escrita: seguir sem log é melhor que não abrir
    # Espelho no histórico compartilhado (só WARNING+; filtro por módulo do app).
    h = HandlerHistorico(level=logging.WARNING)
    logging.getLogger().addHandler(h)
