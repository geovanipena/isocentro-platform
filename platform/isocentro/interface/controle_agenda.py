"""A aba Agenda do lado da janela: o que ela pede ao banco, e quando.

O ``agenda_tela.PainelAgenda`` é a TELA; este objeto responde aos sinais dela
— trocar de dia, marcar/desmarcar máquina, trocar de médico — e decide QUANDO
vale a pena voltar ao banco. Mesma divisão do :mod:`controle_virtual`, e pela
mesma razão: o estado (máquinas, médicos, o dia) é só dele.

**Trocar de médico, ou de modo esmaecer↔esconder, não pede nada ao banco.**
``agenda_db.agenda_do_dia`` já trouxe o dia inteiro; os dois são repaint LOCAL
(ver ``PainelAgenda._repintar_colunas``). Este controle só grava a preferência
quando isso acontece.
"""
from __future__ import annotations

import logging
import time
from datetime import date

from PySide6.QtWidgets import QApplication

from isocentro.banco import agenda_db
from isocentro.banco import tratamento_db
from isocentro.dados import preferencias
from isocentro.interface import agenda_tela

_LOG = logging.getLogger(__name__)

# As máquinas marcadas, o médico escolhido e o modo do destaque, por USUÁRIO
# do app — mesma regra do Grupo Médico da Ficha Virtual
# (``controle_virtual.CHAVE_MEDICOS``): a escolha viaja com o login, não com
# a estação.
CHAVE_MAQUINAS = "maquinas_da_agenda"
CHAVE_MEDICOS = "medicos_da_agenda"
CHAVE_MODO_DESTAQUE = "modo_destaque_agenda"
# "Uma máquina só" (pedido do usuário em 28/09/2026) — ligado/desligado,
# independente de QUAL máquina está marcada (essa é ``CHAVE_MAQUINAS``).
CHAVE_MAQUINA_UNICA = "maquina_unica_agenda"

# Por quanto tempo o resumo do mês é reaproveitado sem nova consulta — ver
# ``ControleAgenda._resumo_mensal``.
_VALIDADE_RESUMO_S = 10 * 60


class ControleAgenda:
    """Responde aos sinais do ``PainelAgenda``. A janela só o constrói e liga."""

    def __init__(self, painel, usuario: dict | None = None):
        self.painel = painel
        self._usuario = usuario or {}
        self._maquinas: list = []   # agenda_db.Maquina, lidas uma vez por sessão
        self._medicos: list = []    # tratamento_db.Medico, idem
        # Conta cada chamada de ``_atualizar`` — os ``processEvents()`` entre
        # as consultas "bônus" deixam o Qt processar eventos no MEIO de uma
        # leitura, e um clique nesse intervalo pode disparar uma chamada
        # REENTRANTE que termina primeiro. Sem isto, a chamada de fora
        # retomaria depois e pintaria a tela com o dado da máquina/dia
        # ANTIGO por cima do resultado (mais novo) que o usuário já está
        # vendo. Cada chamada guarda a própria geração e só pinta a tela se
        # ainda for a mais recente quando a resposta do banco finalmente
        # chegar.
        self._geracao_atualizacao = 0
        # O último resumo do mês — ver :meth:`_resumo_mensal`.
        self._cache_resumo: dict = {}

        painel.dia_mudou.connect(self._atualizar)
        painel.maquinas_mudaram.connect(self._maquinas_mudaram)
        painel.medicos_mudaram.connect(self._medicos_mudaram)
        painel.modo_destaque_mudou.connect(self._modo_destaque_mudou)
        painel.maquina_unica_mudou.connect(self._maquina_unica_mudou)

    def ao_abrir(self) -> None:
        """Monta a faixa de máquinas e médicos, e busca o dia em cena.

        As duas listas (máquinas do serviço, médicos da equipe) são lidas
        UMA vez por sessão — mudam por semana, não por troca de aba —, o
        mesmo cache que a Ficha Virtual já faz para pacientes.
        """
        if not agenda_db.disponivel():
            self.painel.mostrar_status(agenda_db.motivo_indisponivel(), erro=True)
            return
        if not self._maquinas:
            self._maquinas = agenda_db.maquinas()
        if not self._maquinas:
            self.painel.mostrar_status(
                "Nenhuma máquina de tratamento ativa encontrada no banco.",
                erro=True)
            return
        # "Uma máquina só" tem de ser lido ANTES de ``definir_maquinas``: é
        # ele quem decide se a primeira montagem da faixa usa
        # ``_montar_pares`` ou ``_montar_individuais`` (ver o docstring de
        # ``PainelAgenda.definir_maquina_unica``).
        unica_guardada = preferencias.ler(
            self._usuario, CHAVE_MAQUINA_UNICA, False)
        self.painel.definir_maquina_unica(bool(unica_guardada))
        marcadas_guardadas = preferencias.ler(self._usuario, CHAVE_MAQUINAS)
        # ``None`` faz o painel marcar o PRIMEIRO par fixo (ver
        # ``PainelAgenda.definir_maquinas`` e ``agenda_tela.PARES_MAQUINA``)
        # — é o estado de quem nunca escolheu, e a tela deve abrir com
        # alguma coisa.
        self.painel.definir_maquinas(self._maquinas, marcadas_guardadas)

        if not self._medicos:
            self._medicos = agenda_db.medicos()
        medicos_guardados = preferencias.ler(self._usuario, CHAVE_MEDICOS) or []
        self.painel.definir_medicos(self._medicos, medicos_guardados)

        modo_guardado = preferencias.ler(
            self._usuario, CHAVE_MODO_DESTAQUE, agenda_tela.MODO_ESMAECER)
        self.painel.definir_modo_destaque(modo_guardado)

        self._atualizar()

    def _atualizar(self, _dia=None) -> None:
        """Relê o banco para o período e as máquinas marcadas AGORA na
        tela — um dia só (o de sempre) ou um INTERVALO (pedido do usuário
        em 25/09/2026: "adicione intervalo de data pra ser possivel ver a
        agenda de multiplos dias"), decidido por :meth:`_atualizar_periodo`.
        """
        if not agenda_db.disponivel():
            return
        self._geracao_atualizacao += 1
        minha_geracao = self._geracao_atualizacao
        dia = self.painel.dia_atual()
        dia_final = self.painel.dia_final_atual()
        marcadas = self.painel.maquinas_marcadas()
        if not marcadas:
            # Nenhuma máquina marcada é um estado válido — quem desmarcou
            # todas quer ver nenhuma, não a mensagem de erro. Sem consultar o
            # banco por um filtro que já se sabe vazio (ver
            # ``agenda_db.agenda_do_dia``).
            self.painel.mostrar_agenda({}, [])
            self.painel.mostrar_status("Nenhuma máquina marcada.")
            return
        if dia_final > dia:
            self._atualizar_periodo(dia, dia_final, marcadas, minha_geracao)
            return
        self.painel.mostrar_status(f"Lendo a agenda de {dia:%d/%m/%Y}…")
        QApplication.processEvents()
        try:
            marcacoes = agenda_db.agenda_do_dia(dia, marcadas)
        except Exception as exc:  # noqa: BLE001 — a aba avisa e segue viva
            _LOG.exception("Agenda: falha ao consultar o dia")
            if minha_geracao != self._geracao_atualizacao:
                return  # uma chamada mais nova já assumiu a tela
            self.painel.mostrar_agenda({}, [])
            self.painel.mostrar_status(f"Não consegui ler a agenda: {exc}",
                                       erro=True)
            return
        if minha_geracao != self._geracao_atualizacao:
            return  # uma chamada mais nova já assumiu a tela
        if marcacoes is None:
            self.painel.mostrar_agenda({}, [])
            self.painel.mostrar_status(
                "Não consegui ler a agenda — veja "
                "%USERPROFILE%\\.isocentro.log.", erro=True)
            return
        por_maquina = agenda_db.por_maquina(marcacoes)
        # A ORDEM das colunas é a das máquinas MARCADAS, na ordem em que a
        # faixa de checkboxes as lista — não a ordem em que o SQL agrupou,
        # que é alfabética por ``MachineId`` e mudaria a posição das colunas
        # toda vez que alguém marcasse uma máquina nova.
        por_ctr = {m.ctr_resource_ser: m.nome for m in self._maquinas}
        ordem = [por_ctr[c] for c in marcadas if c in por_ctr]
        # ``processEvents()`` entre cada consulta "bônus" (fração do dia,
        # resumo do mês — a agenda do dia em si já chegou e não pode mais
        # falhar em travar) — cada uma é um round-trip síncrono ao banco por
        # conta própria; sem isto só o ANTES da primeira consulta (acima)
        # deixava a UI parada da SEGUNDA em diante, sem repintar nem
        # responder a nada até a cadeia inteira terminar.
        QApplication.processEvents()
        fracoes = self._fracoes_do_dia(dia, marcacoes)
        QApplication.processEvents()
        resumo_mensal = self._resumo_mensal(
            dia, marcadas, self.painel.medicos_para_contagem())
        if minha_geracao != self._geracao_atualizacao:
            return  # uma chamada mais nova já assumiu a tela
        self.painel.mostrar_agenda(por_maquina, ordem, fracoes, resumo_mensal)
        n = len(marcacoes)
        self.painel.mostrar_status(
            f"{n} marcação(ões) em {dia:%d/%m/%Y}." if n else
            f"Nenhuma marcação em {dia:%d/%m/%Y}.")

    def _atualizar_periodo(self, dia, dia_final, marcadas: list,
                           minha_geracao: int) -> None:
        """Relê o banco para um INTERVALO de dias — pedido do usuário em
        25/09/2026: "adicione intervalo de data pra ser possivel ver a
        agenda de multiplos dias". A faixa de botões só deixa marcar UMA
        máquina nesse modo ("ao selecionar multiplos dias deixar somente
        uma maquina por vez", mesmo pedido — ver
        ``agenda_tela.PainelAgenda.definir_maquinas``), mas este método não
        depende disso: passa ``marcadas`` inteira para
        ``agenda_db.agenda_do_periodo``, que aceita mais de uma.

        O resumo do MÊS continua aparecendo neste modo — pedido do usuário
        em 25/09/2026: "continuar mostrando informacoes mes pro periodo
        desejado" —, do mês de ``dia`` (o INÍCIO do período, mesma
        convenção de :meth:`_resumo_mensal` no modo dia único). SEM fração
        por paciente, essa sim pensada só para "o dia em cena"
        (:meth:`_fracoes_do_dia`).
        """
        self.painel.mostrar_status(
            f"Lendo a agenda de {dia:%d/%m/%Y} a {dia_final:%d/%m/%Y}…")
        QApplication.processEvents()
        try:
            marcacoes = agenda_db.agenda_do_periodo(dia, dia_final, marcadas)
        except Exception as exc:  # noqa: BLE001 — a aba avisa e segue viva
            _LOG.exception("Agenda: falha ao consultar o período")
            if minha_geracao != self._geracao_atualizacao:
                return  # uma chamada mais nova já assumiu a tela
            self.painel.mostrar_agenda({}, [])
            self.painel.mostrar_status(f"Não consegui ler a agenda: {exc}",
                                       erro=True)
            return
        if minha_geracao != self._geracao_atualizacao:
            return  # uma chamada mais nova já assumiu a tela
        if marcacoes is None:
            self.painel.mostrar_agenda({}, [])
            self.painel.mostrar_status(
                "Não consegui ler a agenda — veja "
                "%USERPROFILE%\\.isocentro.log.", erro=True)
            return
        por_maquina = agenda_db.por_maquina(marcacoes)
        por_ctr = {m.ctr_resource_ser: m.nome for m in self._maquinas}
        ordem = [por_ctr[c] for c in marcadas if c in por_ctr]
        QApplication.processEvents()
        resumo_mensal = self._resumo_mensal(
            dia, marcadas, self.painel.medicos_para_contagem())
        if minha_geracao != self._geracao_atualizacao:
            return  # uma chamada mais nova já assumiu a tela
        self.painel.mostrar_agenda(por_maquina, ordem,
                                   resumo_mensal=resumo_mensal, multiplos_dias=True)
        n = len(marcacoes)
        self.painel.mostrar_status(
            (f"{n} marcação(ões) de {dia:%d/%m/%Y} a {dia_final:%d/%m/%Y}."
            if n else
            f"Nenhuma marcação de {dia:%d/%m/%Y} a {dia_final:%d/%m/%Y}."))

    def _fracoes_do_dia(self, dia, marcacoes: list) -> dict | None:
        """``{registro: (entregues, previstas, inicio, previsao_fim)}`` de
        quem está em ``marcacoes`` — pedido do usuário em 24/09/2026, em duas
        partes: "adicione a fração tratado/total em agenda na linha do nome
        paciente", depois "mostrar também data de início e data prevista de
        término depois da fração". ``inicio``/``previsao_fim`` são
        ``date | None`` — a previsão é sempre calculada a partir de HOJE de
        verdade (``EmTratamento.previsao_de_fim()`` sem argumento), não do
        dia que a agenda está mostrando: navegar para uma data passada não
        pode empurrar a previsão para o passado (ver o docstring do próprio
        método, em ``tratamento_db``).

        A fração mora no :mod:`tratamento_db`, atrás do portão
        ``LISTA_VERIFICADA_EM`` — ainda FECHADO (ver o docstring de
        ``agenda_db``: "juntar sobre um portão fechado seria herdar o 'não
        conferido' em silêncio"). Por isso só consulta quando
        ``tratamento_db.lista_disponivel()`` está de pé — hoje, isso quer
        dizer o modo experimental (``ISOCENTRO_LISTA_EXPERIMENTAL``) ligado —,
        e devolve ``None`` fora disso: sem fração nenhuma na tela, nunca uma
        fração inventada.

        ``em_tratamento`` já existe e já é usado pela Ficha Virtual — uma
        consulta só para TODOS os pacientes recentes, e não uma por paciente
        da agenda (que aqui pode passar de 90 linhas). Falhar aqui não pode
        derrubar a agenda (que já leu e já mostra o dia): vira log e
        ``None``, como qualquer outra pergunta "bônus" desta tela.
        """
        if not marcacoes or not tratamento_db.lista_disponivel():
            return None
        try:
            pacientes = tratamento_db.em_tratamento(
                dias=tratamento_db.DIAS_DA_JANELA, hoje=dia,
                incluir_concluidos=True)
        except Exception:  # noqa: BLE001 — fração é bônus, agenda já é real
            _LOG.exception("Agenda: falha ao consultar frações (experimental)")
            return None
        if not pacientes:
            return {}
        # ``em_tratamento`` devolve UMA linha por CURSO, na ordem de urgência
        # — não por paciente. Quem terminou um curso na janela e começou
        # outro aparece duas vezes, e a última linha lida não é
        # necessariamente o curso de agora. Fica o curso ainda NÃO concluído
        # e, entre iguais, o que começou por último.
        def _atualidade(p):
            return (not p.concluido(), p.inicio or date.min,
                    p.ultima or date.min)

        escolhido = {}
        for p in pacientes:
            atual = escolhido.get(p.registro)
            if atual is None or _atualidade(p) > _atualidade(atual):
                escolhido[p.registro] = p
        return {reg: (p.entregues, p.previstas, p.inicio, p.previsao_de_fim())
               for reg, p in escolhido.items()}

    def _resumo_mensal(self, dia, marcadas: list, medicos_alvo=()) -> dict:
        """``{nome_exibicao: (pacientes, inicios, sessoes, idade_media,
        fracoes_previstas_media, taxa_ocupacao, indice_disponibilidade)}``
        do MÊS de ``dia``, para as máquinas ``marcadas`` e o(s) médico(s)
        ``medicos_alvo`` (nomes BRUTOS, vazio = todos) — pedido do usuário
        em 25/09/2026, em partes: "adicione o acumulado de número de
        pacientes tratados no mês, e o número de sessões executadas",
        depois "os valores devem ser atualizados a depender do filtro de
        tempo e de médico", depois "adicione ... inicios (numero de
        atividades que contenham INICIO)", depois a média de frações virou
        "média do curso inteiro (previstas)" — ver
        ``tratamento_db.resumo_mensal_por_maquina``.

        ``taxa_ocupacao``/``indice_disponibilidade`` entraram em
        28/09/2026 (ver ``agenda_db.minutos_uteis_do_mes``/
        ``minutos_parada_do_mes``): a primeira é
        ``sessoes × agenda_db.MINUTOS_POR_SESSAO`` sobre os minutos úteis do
        mês; a segunda desconta os minutos de parada do mesmo total, mas só
        quando ``agenda_db.MINUTOS_PARADA_VERIFICADO_EM`` está aberto —
        fechado, é ``None`` (nunca "100% disponível" por a parada ter
        voltado vazia). As duas são ``None`` para uma máquina sem horário
        em ``agenda_db.HORAS_MAQUINA`` — nunca uma taxa sobre expediente
        inventado.

        ``medicos_alvo`` chega JÁ FILTRADO por quem chama
        (``PainelAgenda.medicos_para_contagem()``): vazio sempre que "Só os
        meus" não estiver marcado, mesmo com médico escolhido no seletor —
        esta função não sabe nem precisa saber do checkbox, só executa o
        filtro que recebeu.

        ``pacientes``/``inicios`` vêm de
        ``agenda_db.pacientes_do_mes_por_maquina`` (quem esteve MARCADO na
        máquina no mês, e quantas dessas marcações são de início) — pedido
        do mesmo dia: "para saber o número de pacientes tratados é só
        pegar o número distinto de pacientes agendados na máquina no
        período... só isso". ``sessoes``/``idade_media``/
        ``fracoes_previstas_media`` continuam vindo de
        ``tratamento_db.resumo_mensal_por_maquina`` (frações de fato
        entregues, e o tamanho previsto do curso de cada um), pelo
        ``MachineId`` CRU (o que ela precisa para casar com
        ``DWH.DimMachine``). Devolve pelo NOME DE EXIBIÇÃO — a chave que
        ``PainelAgenda`` usa para os cabeçalhos das colunas (mesma
        ordem/nome das colunas, ver ``agenda_db._nome_exibicao``). Uma
        máquina só entra no resultado se AS DUAS consultas trouxerem dado
        dela — nunca um "0 tratados" ou "0 sessões" inventado por a outra
        metade ter falhado.
        """
        por_ctr = {m.ctr_resource_ser: m for m in self._maquinas}
        maquinas_marcadas = [por_ctr[c] for c in marcadas if c in por_ctr]
        if not maquinas_marcadas:
            return {}
        medicos_alvo = list(medicos_alvo or ())
        # O resumo do mês muda devagar, e a atualização automática relê a
        # agenda a cada 2 minutos: sem este cache as quatro consultas do mês
        # rodavam de novo a cada tique. Mesma chave (mês, máquinas, médicos)
        # dentro de :data:`_VALIDADE_RESUMO_S` reaproveita o último
        # resultado; qualquer troca de mês, máquina ou médico consulta de novo.
        chave = (dia.year, dia.month, tuple(marcadas), tuple(medicos_alvo))
        guardado = self._cache_resumo.get(chave)
        if guardado is not None and (
                time.monotonic() - guardado[0] < _VALIDADE_RESUMO_S):
            return guardado[1]
        fora = self._consultar_resumo_mensal(dia, maquinas_marcadas,
                                             medicos_alvo)
        self._cache_resumo = {chave: (time.monotonic(), fora)}
        return fora

    def _consultar_resumo_mensal(self, dia, maquinas_marcadas: list,
                                 medicos_alvo: list) -> dict:
        """A consulta de fato por trás de :meth:`_resumo_mensal`, sem cache."""
        try:
            pacientes_inicios = agenda_db.pacientes_do_mes_por_maquina(
                maquinas_marcadas, dia, medicos_alvo)
        except Exception:  # noqa: BLE001 — bônus, não pode derrubar a agenda
            _LOG.exception("Agenda: falha ao consultar pacientes do mês")
            pacientes_inicios = {}
        ids = [m.machine_id for m in maquinas_marcadas if m.machine_id]
        try:
            sessoes_idade_previstas = (tratamento_db.resumo_mensal_por_maquina(
                ids, dia, medicos_alvo) if ids else {})
        except Exception:  # noqa: BLE001 — bônus, não pode derrubar a agenda
            _LOG.exception("Agenda: falha ao consultar o resumo mensal")
            sessoes_idade_previstas = {}
        try:
            minutos_parada = agenda_db.minutos_parada_do_mes(
                maquinas_marcadas, dia)
        except Exception:  # noqa: BLE001 — bônus, não pode derrubar a agenda
            _LOG.exception("Agenda: falha ao consultar minutos de parada do mês")
            minutos_parada = {}
        fora = {}
        for m in maquinas_marcadas:
            if m.ctr_resource_ser not in pacientes_inicios:
                continue
            if m.machine_id not in sessoes_idade_previstas:
                if sessoes_idade_previstas:
                    # A máquina tinha pacientes/inícios (agenda_db achou),
                    # mas ficou de fora do resumo de sessões — o
                    # ``m.machine_id`` cru (``InSightiveResourceMachine``)
                    # não bateu com nenhum ``MachineId``/``MachineAliasName``/
                    # ``MachineFullName`` de ``DWH.DimMachine`` na consulta de
                    # ``tratamento_db`` (ver o comentário de
                    # ``_SQL_RESUMO_MENSAL_MAQUINA``). Silencioso é PIOR que
                    # errado aqui — melhor o operador ver no log e conferir
                    # o ``DimMachine`` real do que a máquina só sumir do
                    # cartão do mês sem explicação nenhuma.
                    _LOG.warning(
                        "Agenda: %s (MachineId=%r) tinha pacientes/inícios "
                        "no mês, mas não apareceu no resumo de sessões — "
                        "conferir o nome dela em DWH.DimMachine.",
                        m.nome, m.machine_id)
                continue
            pacientes, inicios = pacientes_inicios[m.ctr_resource_ser]
            sessoes, idade, previstas = sessoes_idade_previstas[m.machine_id]
            minutos_uteis = agenda_db.minutos_uteis_do_mes(m.nome, dia)
            # A ocupação divide as sessões JÁ FEITAS pelo expediente que JÁ
            # PASSOU — até hoje, no mês corrente. Dividir pelo mês inteiro
            # punha uma máquina lotada em ~30% no dia 10.
            minutos_ate_hoje = agenda_db.minutos_uteis_do_mes(
                m.nome, dia, ate=date.today())
            taxa_ocupacao = None
            indice_disponibilidade = None
            if minutos_ate_hoje:
                taxa_ocupacao = (
                    sessoes * agenda_db.MINUTOS_POR_SESSAO / minutos_ate_hoje)
            if minutos_uteis:
                if agenda_db.MINUTOS_PARADA_VERIFICADO_EM:
                    parada = minutos_parada.get(m.ctr_resource_ser, 0)
                    indice_disponibilidade = (
                        (minutos_uteis - parada) / minutos_uteis)
            fora[m.nome] = (pacientes, inicios, sessoes, idade, previstas,
                            taxa_ocupacao, indice_disponibilidade)
        return fora

    def _maquinas_mudaram(self, marcadas: list) -> None:
        preferencias.gravar(self._usuario, CHAVE_MAQUINAS, list(marcadas))
        self._atualizar()

    def _medicos_mudaram(self, medicos_brutos: list) -> None:
        preferencias.gravar(self._usuario, CHAVE_MEDICOS, list(medicos_brutos))
        # O acumulado do mês depende de QUEM está em foco, mas só FILTRA de
        # verdade com "Só os meus" marcado (ver
        # ``PainelAgenda.medicos_para_contagem`` — pedido do usuário em
        # 25/09/2026: "se nao tiver ticado somente os meus deve mostrar
        # agenda completa") — repaint LOCAL, sem reler a agenda do dia (que
        # não muda com o médico, ver o docstring do módulo): só o resumo
        # mensal pede o banco de novo.
        self._atualizar_resumo_mensal_local()

    def _modo_destaque_mudou(self, modo: str) -> None:
        preferencias.gravar(self._usuario, CHAVE_MODO_DESTAQUE, modo)
        # Ligar/desligar "Só os meus" muda se o médico em foco FILTRA as
        # contagens ou só destaca (mesmo mecanismo de
        # ``medicos_para_contagem``) — o resumo do mês tem de acompanhar na
        # hora, senão ele fica com o número de ANTES do clique: "tudo deve
        # tá síncrono" (pedido do usuário em 25/09/2026, no mesmo assunto).
        self._atualizar_resumo_mensal_local()

    def _maquina_unica_mudou(self, ligado: bool) -> None:
        """Só grava a preferência do MODO — a releitura do banco já foi
        pedida por ``maquinas_mudaram``, emitido junto (ver o docstring de
        ``PainelAgenda._maquina_unica_alternada``): duas ``preferencias.
        gravar`` de coisas diferentes, uma só ``_atualizar()``."""
        preferencias.gravar(self._usuario, CHAVE_MAQUINA_UNICA, ligado)

    def _atualizar_resumo_mensal_local(self) -> None:
        """Repaint LOCAL do resumo do mês, com o médico/modo ATUAIS da tela
        — sem reler a agenda do dia (que não muda com médico nem modo, ver
        o docstring do módulo). Funciona nos dois modos: em PERÍODO, é o
        mês do INÍCIO do intervalo (mesma convenção de
        :meth:`_atualizar_periodo`)."""
        dia = self.painel.dia_atual()
        marcadas = self.painel.maquinas_marcadas()
        if not marcadas:
            return
        resumo_mensal = self._resumo_mensal(
            dia, marcadas, self.painel.medicos_para_contagem())
        self.painel.atualizar_resumo_mensal(resumo_mensal)
