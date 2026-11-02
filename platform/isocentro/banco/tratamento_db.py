"""O tratamento ENTREGUE, lido do data warehouse — a fonte da aba Ficha Virtual.

O :mod:`capa_db` lê o que se PLANEJA: cadastro, prescrição, dose pretendida.
Aqui é a outra metade: o que ACONTECEU. Em que fração o paciente está, quem
tratou cada uma, a que horas, quanta dose já entrou, e onde o tratamento parou
no meio.

Só LEITURA, pela mesma conexão do :mod:`capa_db` — este banco é o sistema
clínico, e abrir uma segunda conexão para o mesmo servidor seria pagar duas
vezes pelo mesmo login.

**O PORTÃO** — ``VERIFICADO_EM``

Enquanto essa constante estiver vazia, tudo aqui devolve ``None``/vazio e a tela
diz que o mapeamento não foi conferido. Isso é deliberado e não é excesso de
zelo: o erro possível neste módulo não é o erro barulhento de nome de coluna
inventado (``PatientId`` × ``PatientID``), que estoura na hora. É o silencioso —
ler "frações PLANEJADAS" achando que são "frações ENTREGUES" devolve um número
plausível, e é justamente o número que o médico lê grande no meio da tela para
decidir sobre o paciente.

O que JÁ está resolvido, e não por adivinhação: os nomes e o significado das
colunas vêm da **Data Lineage Tool 15.6** da Varian, que documenta cada coluna
do DW e de onde ela é derivada. Isso eliminou o risco de coluna parecida com a
certa. Ver o SQL adiante, com as descrições citadas ao lado de cada escolha.

O que FALTA é o que só o banco desta clínica responde: se o filtro de "tratado"
basta, se a soma de dose por fração não conta duas vezes, e se a máquina de
tratamento preenche o nome do operador aqui. Para isso:

    runas /netonly /user:CLINICA\\usuario ^
      "C:\\...\\isocentro\\tools\\mapear_tratamento.bat --paciente <em tratamento>"

Com a saída na mão, ajustar o SQL e pôr a data em ``VERIFICADO_EM``.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from isocentro.dados import ambiente
from isocentro.banco import capa_dados
from isocentro.banco import capa_db
from isocentro.dominio import constantes

_LOG = logging.getLogger(__name__)

# Data em que o SQL deste módulo foi conferido contra o banco real, no formato
# DD/MM/AAAA. VAZIO = nunca foi. Ver o portão no docstring do módulo.
#
# Conferido em DUAS rodadas do ``tools/mapear_tratamento.py`` contra o
# ``variandw``, e as duas acharam defeito — é por isso que o portão existe:
#
#   1ª (paciente com 2 cursos): o ``GROUP BY FractionNumber`` sem curso FUNDIA
#      as frações de cursos diferentes, e o total vinha do curso velho — a tela
#      diria "15 de 15" para quem estava na 2ª de 10.
#   2ª (paciente com 4 cursos, EM tratamento): a soma de dose por fração deu
#      18,0 Gy num curso de 9,0 Gy por fração — o dobro, por haver mais de um
#      RefPoint com ``PrimaryFlag = 1``.
#
#   3ª (paciente REPLANEJADO, 20/08): um curso com TRÊS planos, e a numeração
#      de fração REINICIANDO a cada um. O ``GROUP BY FractionNumber`` fundia a
#      fração 8 do plano novo com a 8 do velho, e o ``MIN`` devolvia a data de
#      julho: duas semanas de tratamento sumiam da tela. Na mesma rodada,
#      ``FractionsDelivered`` veio 0 para quem tinha 21 frações aplicadas, e
#      ``CourseDosePlanned`` veio 334 Gy num curso de 30 × 2 Gy.
#
#   4ª (paciente de MAMA, 20/08 na tela): mama e fossa supraclavicular são dois
#      planos no sistema e UMA sessão na sala. Contando uma fração por linha de
#      plano, a tela mostrou "16 / 15" e declarou "tratamento concluído" numa
#      paciente na 8ª sessão. Ver :func:`fracoes_entregues`.
#
# CONFERIDO NA TELA pelo usuário em 20/08/2026: o paciente 9000011CEL (Lauro,
# 3 planos) mostra 21 de 30 com a última sessão em 20/08. Era ele que aparecia
# como "12 de 30, última em 07/08".
VERIFICADO_EM = "20/08/2026"


# Portão SEPARADO para a LISTA (o painel de "meus pacientes em tratamento").
# As consultas dela são outras: agregam a ``FactTreatmentHistory`` inteira por
# DATA — 2,7 milhões de linhas — e cruzam com ``DimPatientDoctor``. Nada disso
# foi medido, nem o resultado nem o TEMPO, e a tela consulta na thread da
# interface com 6 s de limite.
#
# Portão próprio, e não o mesmo do ``VERIFICADO_EM``, porque as duas partes
# falham de jeitos diferentes: a consulta por paciente já está conferida e não
# pode ficar refém de uma lista que ainda não foi. Sem lista, a aba cai na
# busca — que funciona.
LISTA_VERIFICADA_EM = ""

# Liga o painel ANTES de ele estar conferido, para poder ser olhado. Existe
# porque o portão criou um impasse honesto: sem conferir não se mostra, e sem
# mostrar não dá para conferir contra o que o ARIA diz.
#
# Quem liga isto assume que os números podem estar errados — e a tela ANUNCIA
# isso numa faixa, em vez de deixar a suposição na cabeça de quem ligou. Não vai
# no pacote: é variável de ambiente, e o .bat que a define mora em ``tools/``.
ENV_EXPERIMENTAL = "ISOCENTRO_LISTA_EXPERIMENTAL"

# Qual médico já vem escolhido quando ninguém escolheu ainda. Casa por PEDAÇO do
# nome ("Rubens" acha "Rubens Carvalho de Souza"), porque o nome exato do banco
# vem invertido e com sobrenome repetido — ninguém o digitaria certo.
ENV_MEDICO = "ISOCENTRO_MEDICO"


def lista_conferida() -> bool:
    """A lista foi medida contra o banco? Diferente de estar LIGADA."""
    return bool(LISTA_VERIFICADA_EM)


def lista_disponivel() -> bool:
    """Dá para abrir a aba no painel de pacientes, em vez da busca?"""
    if not disponivel():
        return False
    return lista_conferida() or bool(ambiente.ler(ENV_EXPERIMENTAL))


def medico_padrao(disponiveis: list):
    """O médico de ``ISOCENTRO_MEDICO``, ou ``None``.

    Para simular a tela de um médico sem inventar identidade: o app não sabe
    quem está logado (o login tem papel ``admin``/``fisico``, não médico), e
    fingir que sabe seria pior que a variável — a variável ao menos é visível
    para quem a definiu.
    """
    alvo = capa_dados.normalizar_nome(ambiente.ler(ENV_MEDICO) or "")
    if not alvo:
        return None
    for m in disponiveis:
        if alvo in capa_dados.normalizar_nome(m.nome):
            return m
    return None


def disponivel() -> bool:
    """Dá para mostrar tratamento entregue nesta instalação?

    Duas condições, e as duas dizem coisas diferentes na tela: sem banco
    apontado é configuração (o admin resolve); sem mapeamento conferido é
    trabalho meu que não terminou, e a tela precisa dizer isso em vez de fingir
    que o paciente não tem tratamento.
    """
    return bool(VERIFICADO_EM) and capa_db.configurado()


def motivo_indisponivel() -> str:
    """Por que a aba não mostra nada — em palavras de quem está na frente dela."""
    if not capa_db.configurado():
        return ("O sistema (banco de dados) não está apontado nesta instalação. "
                "Configurações → Serviço, campo “Sistema”.")
    if not VERIFICADO_EM:
        return ("A leitura do tratamento entregue ainda não foi conferida "
                "contra este banco. Enquanto isso, esta aba não mostra números "
                "— um número plausível e errado aqui é pior que nenhum.")
    return ""


# ── O que a tela consome ────────────────────────────────────────────────────

@dataclass
class Sessao:
    """Uma fração aplicada. Campo sem fonte no banco fica VAZIO, nunca chutado."""
    fracao: int = 0            # 0 = o banco não numerou a sessão
    # De qual PLANO é esta fração. Replanejar cria um plano novo dentro do
    # mesmo curso, e a numeração recomeça — sem isto, duas sessões diferentes
    # se chamam "fração 8" e a tela não tem como distingui-las.
    plano: int = 0
    plano_previstas: int = 0     # frações que ESTE plano planejou
    # ``PlanSetupId`` do ARIA — o nome que o físico deu ("MAMA D", "BOOST").
    # Vale mais que "P2" na tela: é como o plano é chamado em toda conversa do
    # serviço, e o ``DimPlanID`` é um número de seis dígitos que não diz nada.
    plano_nome: str = ""
    data: Optional[date] = None
    hora: str = ""             # "HH:MM"; vazio quando o DW não guarda horário
    maquina: str = ""
    quem: str = ""             # quem tratou; vazio = não há fonte, ver o mapeador
    # O SEGUNDO técnico da sessão (``TreatmentSignOffUser2``): na sala são duas
    # pessoas posicionando o paciente, e a folha nomeava uma só. Vazio na maioria
    # das linhas — e vazio fica vazio, sem repetir o primeiro nome.
    ajudante: str = ""
    dose_cgy: float = 0.0

    def data_br(self) -> str:
        return self.data.strftime("%d/%m/%Y") if self.data else ""

    def quem_tratou(self) -> str:
        """Os dois nomes, ou só o que houver.

        O separador é " · ", não vírgula: com vírgula, "Silva, Mauricio · Souza"
        fica com dois níveis de pontuação disputando a mesma linha, e o olho lê
        três pessoas onde há duas.
        """
        nomes = [n for n in (self.quem, self.ajudante) if n]
        # O mesmo login nos dois campos acontece (a máquina copia o operador
        # quando não há segundo), e o nome repetido lado a lado parece erro de
        # tela.
        if len(nomes) == 2 and nomes[0] == nomes[1]:
            nomes.pop()
        return " · ".join(nomes)


@dataclass
class Intervalo:
    """Uma parada no meio do tratamento — o que o médico procura ao abrir a aba.

    Fim de semana não é parada: conta-se em DIAS ÚTEIS. Sem isso toda sexta→
    segunda viraria um "intervalo de 3 dias" e a tela cansaria de avisar coisa
    nenhuma — e aviso que sempre aparece deixa de ser lido.
    """
    de: date
    ate: date
    dias_uteis: int

    def texto(self) -> str:
        return (f"{self.de.strftime('%d/%m')} → {self.ate.strftime('%d/%m')}: "
                f"{self.dias_uteis} dia{'s' if self.dias_uteis > 1 else ''} "
                "útil" + ("eis" if self.dias_uteis > 1 else ""))


@dataclass
class Curso:
    """Um curso de tratamento do paciente — o atual ou um já encerrado.

    O paciente do teste de 19/08/2026 tinha QUATRO (2022, 2022, 2024 e o de
    agora). Ver os anteriores importa para quem decide hoje: dose já dada em
    outro curso muda a conduta. Mas eles não podem competir com o que está em
    andamento — daí ``atual``, e o destaque que a tela dá a ele.
    """
    id: int = 0
    nome: str = ""             # ``CourseId`` do ARIA ("C1"), quando houver
    entregues: int = 0
    previstas: int = 0
    inicio: Optional[date] = None
    fim: Optional[date] = None
    atual: bool = False

    def concluido(self) -> bool:
        """Entregou tudo o que planejou.

        Sem ``previstas`` não dá para afirmar que concluiu — e "concluído" é
        justamente o que faz o médico parar de olhar. Na dúvida, não afirma.
        """
        return self.previstas > 0 and self.entregues >= self.previstas

    def periodo(self) -> str:
        if not self.inicio:
            return ""
        if not self.fim or self.fim == self.inicio:
            return self.inicio.strftime("%d/%m/%Y")
        return (f"{self.inicio.strftime('%d/%m/%Y')} – "
                f"{self.fim.strftime('%d/%m/%Y')}")

    def situacao(self) -> str:
        if self.atual and not self.concluido():
            return "EM TRATAMENTO"
        return "concluído" if self.concluido() else "interrompido"

    def rotulo(self) -> str:
        """Como o curso aparece no seletor.

        SEM a contagem de frações, de propósito. Ela vinha de outra consulta que
        a do número grande logo abaixo, e as duas discordavam: o seletor dizia
        "13/20" com "13 / 28" em corpo 64 dez pixels abaixo. Duas contas para o
        mesmo fato numa tela só é como ela perde a confiança de quem lê — e a
        fração já está ali, grande, sem precisar de eco.
        """
        nome = self.nome or f"Curso {self.id}"
        return f"{nome}   {self.periodo()}   ·   {self.situacao()}"


@dataclass
class Tratamento:
    """O quadro do paciente. ``previstas``/``prescrita_cgy`` vêm do PLANO."""
    registro: str = ""
    nome: str = ""
    curso: Optional[Curso] = None       # o curso que está NA TELA
    cursos: list = field(default_factory=list)   # todos, do mais recente
    entregues: int = 0
    previstas: int = 0
    # O plano em curso, quando o paciente foi replanejado. O número grande fala
    # do CURSO (decidido com o usuário em 20/08/2026); estes campos são a linha
    # abaixo dele, que evita a leitura ambígua — "8 de 17" e "21 de 30" são os
    # dois verdadeiros, e mostrar só um deles esconde metade do tratamento.
    #
    # "Plano" aqui é o GRUPO que trata junto (ver :func:`planos_simultaneos`):
    # mama e FSC são um plano só para quem lê a tela, porque são uma sessão só
    # para quem deita na mesa.
    plano_atual: int = 0
    plano_nome: str = ""       # os nomes do grupo, na ordem em que tratam
    plano_entregues: int = 0
    plano_previstas: int = 0
    juntos: int = 0            # quantos planos tratam JUNTOS no grupo atual
    planos: int = 0            # quantos GRUPOS houve no curso (2+ = replanejou)
    dose_entregue_cgy: float = 0.0
    dose_prescrita_cgy: float = 0.0
    sessoes: list = field(default_factory=list)
    # O radio-oncologista responsável. Vem JUNTO com o resto do quadro, e não
    # no gesto de escolher o paciente: uma consulta a mais aqui não custa nada
    # (já se está falando com o banco), enquanto no clique ela travava a tela
    # inteira até o servidor responder — medido em 8 s com o banco fora do ar.
    medico: str = ""
    # A prescrição aprovada deste curso, com o sítio — o mesmo texto da capa.
    # Vazia quando nenhuma prescrição casa com o curso: ver
    # :func:`prescricao_do_curso`.
    prescricao: str = ""
    # A dose de cada plano do curso. Vazia = número único (ver
    # :func:`doses_por_plano` e :func:`doses_distintas`).
    doses: list = field(default_factory=list)
    # Identificação, para a faixa do topo: as MESMAS pílulas da Capa, do mesmo
    # cadastro (``capa_db.cadastro_do_paciente``). Vazias quando não deu para
    # ler — e vazio some da faixa, porque pílula em branco lê-se como dado
    # faltando.
    nascimento: str = ""
    convenio: str = ""
    # A frequência PRESCRITA, em cartão próprio: dentro da linha corrida da
    # prescrição ela some, e é ela que diz se o paciente vem amanhã.
    frequencia: str = ""
    # A dose por fração PRESCRITA, em cGy e como TEXTO (pode trazer dois
    # valores quando há alvos simultâneos — ver ``_dose_por_fracao``).
    dose_dia: str = ""
    # Controle respiratório (DIBH, gating), quando houver. Vem da FICHA já
    # elaborada, não do data warehouse — ver ``gui._tratamento_extras``. Vazio
    # é vazio: a maioria dos tratamentos não tem, e afirmar que tem muda a
    # montagem na mesa e o tempo reservado da máquina.
    respiratorio: str = ""

    def percentual(self) -> int:
        """Quanto do tratamento já foi, em frações. 0 quando não dá para saber."""
        if self.previstas <= 0:
            return 0
        return max(0, min(100, round(100 * self.entregues / self.previstas)))

    def total_confere(self) -> bool:
        """O total previsto do CURSO cobre as frações dele? Ver :func:`cobre`."""
        return cobre(self.entregues, self.previstas)

    def replanejado(self) -> bool:
        """Houve mais de um GRUPO de planos, um depois do outro.

        Contando planos em vez de grupos, toda paciente de mama com FSC saía
        "replanejada" — dois planos que nunca se substituíram, e um aviso que
        acusa o que não houve some da vista quando houver de verdade.
        """
        return self.planos > 1

    def simultaneos(self) -> bool:
        """Dois ou mais planos na MESMA sessão (mama + FSC, mama + boost)."""
        return self.juntos > 1

    def planos_distintos(self) -> int:
        """Quantos planos diferentes aparecem nas sessões — não quantos grupos.

        É por este número que a lista mostra a coluna do plano: planos
        simultâneos não são replanejamento, mas as duas linhas da mesma fração
        precisam dizer de qual plano cada uma veio.
        """
        return len({s.plano for s in self.sessoes if s.plano})

    def previsao_de_fim(self, hoje: Optional[date] = None):
        """O dia previsto da última fração, ou ``None``.

        ``None`` em curso concluído — prever o fim do que já acabou é ruído — e
        também sem denominador: sem saber quantas frações faltam não há data, e
        chutar uma numa tela de conferência é o que não se faz aqui.
        """
        if not self.previstas or self.entregues >= self.previstas:
            return None
        ultima = self.ultima()
        return prever_fim(ultima.data if ultima else None,
                          self.previstas - self.entregues,
                          self.frequencia, hoje)

    def antes_do_plano_atual(self) -> int:
        return max(0, self.entregues - self.plano_entregues)

    def ultima(self) -> Optional[Sessao]:
        return self.sessoes[0] if self.sessoes else None

    def intervalos(self, minimo: int = 1) -> list:
        """As paradas entre frações consecutivas, da mais recente para trás."""
        return intervalos_das_sessoes(self.sessoes, minimo)


@dataclass
class EmTratamento:
    """Uma linha do painel: um paciente, no curso que ele está recebendo.

    É o que a lista mostra ANTES de alguém clicar. Cada campo aqui existe para
    responder algo de relance; o que exigir abrir o paciente não entra.
    """
    registro: str = ""
    nome: str = ""
    curso_id: int = 0
    entregues: int = 0
    previstas: int = 0
    # A PRIMEIRA sessão do curso (``MIN(TreatmentStartTime)``) — entrou em
    # 24/09/2026 para a Agenda, "data de início". Ver o comentário junto de
    # ``_SQL_EM_TRATAMENTO``: NÃO conferida contra o banco real por conta
    # própria, sob o mesmo portão experimental da fração.
    inicio: Optional[date] = None
    ultima: Optional[date] = None
    maquinas: int = 0
    # A frequência PRESCRITA deste curso, já em português ("Dias Alternados").
    # Vazia = não deu para saber; é o ritmo da previsão de fim.
    frequencia: str = ""
    # Quantos cursos de tratamento este paciente já teve, contando o de agora.
    # Retratamento muda conduta, e a lista não dizia nada sobre isso. Zero =
    # não deu para contar (a consulta é separada, ver ``_contar_cursos``).
    cursos_total: int = 0
    # O radio-oncologista responsável, como o banco o escreve, e quantos há.
    # Entraram em 22/09/2026 com o Grupo Médico: a lista de um médico só não
    # precisa dizer de quem é cada paciente, a de um GRUPO precisa. Vazio =
    # ninguém vinculado, ou a coluna não veio; ``medicos_total`` maior que 1
    # diz que o nome acima é UM dos vinculados (ver o SQL).
    medico: str = ""
    medicos_total: int = 0

    def faltam(self) -> int:
        return max(0, self.previstas - self.entregues) if self.previstas else 0

    def parada_dias(self, hoje: Optional[date] = None) -> int:
        """Dias ÚTEIS desde a última sessão. Zero se terminou o curso.

        Curso concluído não está "parado" — está pronto. Marcar de atenção quem
        acabou de terminar encheria a lista de alarme falso, e alarme falso é o
        que faz o médico parar de olhar as marcas.
        """
        if not self.ultima or self.concluido():
            return 0
        return dias_uteis_entre(self.ultima, hoje or date.today())

    def concluido(self) -> bool:
        return self.previstas > 0 and self.entregues >= self.previstas

    def previsao_de_fim(self, hoje: Optional[date] = None) -> Optional[date]:
        """Em que dia a ÚLTIMA fração deve cair. ``None`` quando não dá.

        Conta dias ÚTEIS e o RITMO do regime — as duas coisas que "faltam N
        frações" não diz. O Tadeu Amostro, em 21/08/2026 (sexta), tinha 2
        frações de 3 e estava em dias alternados: a próxima cai na segunda e a
        última na quarta. Contando só frações, a tela o pôs em "terminam esta
        semana"; sábado e domingo não tratam, e ele não acabava nesta semana
        coisa nenhuma.

        A contagem parte da ÚLTIMA SESSÃO, e não de hoje: o ritmo é entre
        frações, então a próxima do Tadeu cai dois dias úteis depois de 20/08 —
        na segunda —, e não dois dias depois da sexta em que se olha a tela.
        Partindo de hoje, a previsão dele ia para quinta 27/08, um dia a mais.

        O piso é HOJE. Num paciente parado a conta cairia no PASSADO, e uma
        data que já passou lida como "termina esta semana" poria todo mundo que
        interrompeu na faixa de quem está acabando.
        """
        if self.concluido():
            return None
        return prever_fim(self.ultima, self.faltam(), self.frequencia, hoje)

    def urgencia(self, hoje: Optional[date] = None) -> int:
        """Quanto esta linha precisa de atenção. Maior = mais urgente.

        Existe para ORDENAR. Por data, quem está parado há duas semanas cai no
        fim da lista — exatamente onde ele não deveria estar, porque parou de
        tratar e por isso parou de aparecer. A lista ordenada por data mostra
        primeiro quem está indo bem.

        Parada acima de tudo: é a única marca em que o tratamento NÃO está
        acontecendo.
        """
        parado = self.parada_dias(hoje)
        if parado >= _DIAS_PARADO:
            # Dentro das paradas, a mais longa primeiro. O teto mantém a faixa
            # separada das outras marcas mesmo numa parada de meses.
            return 100 + min(parado, 99)
        if self.entregues == 1:
            return 20                       # começou: avaliação inicial
        if self.previstas and not self.concluido() \
                and self.faltam() <= _FALTAM_POUCAS:
            return 10                       # termina: agendar seguimento
        if self.concluido():
            return -10                      # já foi; fica por último
        return 0

    def marcas(self, hoje: Optional[date] = None) -> list:
        """Os sinais de atenção desta linha, do mais urgente para o menos.

        Ordem pensada: o que interrompe o tratamento vem antes do que só
        informa. Um paciente parado há uma semana importa mais que um que
        trocou de máquina.
        """
        fora = []
        parado = self.parada_dias(hoje)
        if parado >= _DIAS_PARADO:
            fora.append(("⚠", f"parado há {parado} dias úteis"))
        # Sem marca de interrupção, por decisão do usuário em 11/09/2026: "se o
        # tratamento foi realizado é o que interessa". O ⚡ de "última sessão
        # interrompida" caía em quem a sala viu tratar normal, e em quatro
        # pacientes em quase toda sessão — o ``TerminationStatus`` do DW não é
        # o que a sala viu. A fração entregue já está na contagem.
        if self.entregues == 1:
            fora.append(("●", "começou"))
        if self.concluido():
            fora.append(("✓", "concluído"))
        elif self.previstas and self.faltam() <= _FALTAM_POUCAS:
            fora.append(("✓", f"faltam {self.faltam()}"))
        if self.maquinas > 1:
            fora.append(("⇄", f"{self.maquinas} máquinas"))
        return fora


# As frequências em que o paciente deita na mesa TODO dia útil — as duas de
# ``capa_dados.FREQUENCIAS_PT`` que não pulam dia. Decidem qual regime vale
# quando o curso tem mais de um (ver ``_marcar_frequencia``), e o texto é o já
# traduzido, o mesmo que a capa imprime — comparar contra o valor cru do banco
# quebraria se a equipe digitasse a frequência em português, que é justamente o
# que o dicionário de tradução existe para tratar.
_FREQUENCIAS_DIARIAS = ("Uma Vez por Dia", "Duas Vezes por Dia")

# O RITMO de cada regime, como ``(dias úteis, por quantas frações)``. É o que
# transforma "faltam 4" numa DATA — e sem data não dá para dizer se o
# tratamento acaba nesta semana ou na outra.
#
# "Duas Vezes por Dia" é (1, 2): duas frações no mesmo dia não gastam dois
# dias. "Dias Alternados" é (2, 1): pula um dia útil entre uma e outra.
# Frequência desconhecida cai em (1, 1) — o ritmo mais rápido dos comuns, que
# erra para MAIS cedo; prometer um fim que não chega é melhor que esconder um
# paciente que termina amanhã da faixa que existe para achá-lo.
_RITMO = {
    "Uma Vez por Dia": (1, 1),
    "Duas Vezes por Dia": (1, 2),
    "Dias Alternados": (2, 1),
    "Duas Vezes por Semana": (3, 1),
    "Aplicação Única": (1, 1),
}

# Quantos dias úteis sem sessão já merecem marca. Três é o que o serviço
# considera parada de verdade: um ou dois dias acontecem por feriado, manutenção
# e remarcação, e marcá-los encheria a lista de ruído.
_DIAS_PARADO = 3

# A partir de quantas frações restantes o fim já é assunto (agendar seguimento,
# avaliar resposta).
_FALTAM_POUCAS = 2

# ── As faixas do painel ─────────────────────────────────────────────────────
# A ordenação por urgência já punha as linhas certas em cima, mas ordem sozinha
# não diz ONDE termina um assunto e começa o outro: quem varre a lista de manhã
# precisa saber quantos casos exigem decisão HOJE, e isso é uma contagem, não
# uma posição. Pedido do usuário em 21/08/2026.
#
# As faixas são exclusivas e cobrem todo mundo — linha sem faixa some da tela,
# que é o pior desfecho possível numa lista de pacientes.
FAIXA_ATENCAO = "atencao"
FAIXA_TERMINA = "termina"
FAIXA_CURSO = "curso"
FAIXA_CONCLUIDO = "concluido"

# A faixa "terminam esta semana" NÃO conta frações que faltam — conta o
# CALENDÁRIO. Contando frações (era "faltam ≤ 5"), a faixa saiu com sete
# pacientes numa sexta-feira, entre eles um de 21/25 e dois de 2/5, que não
# terminam semana nenhuma; e o Tadeu Amostro, 1/3 em DIAS ALTERNADOS, para quem
# a próxima sessão cai na segunda e a última na quarta. Devolvido pelo usuário
# em 21/08/2026: "hoje é sexta, ele não acaba essa semana né, sábado e domingo
# não funciona".
#
# Quem decide agora é ``EmTratamento.previsao_de_fim`` contra
# ``sexta_desta_semana``.

_TITULOS_DE_FAIXA = {
    FAIXA_ATENCAO: "PRECISA DE ATENÇÃO",
    FAIXA_TERMINA: "TERMINAM ESTA SEMANA",
    FAIXA_CURSO: "EM CURSO",
    FAIXA_CONCLUIDO: "CONCLUÍDOS",
}

# A ordem em que as faixas aparecem. Concluídos por último: quando o filtro os
# inclui, eles são consulta, não trabalho do dia.
ORDEM_DAS_FAIXAS = (FAIXA_ATENCAO, FAIXA_TERMINA, FAIXA_CURSO, FAIXA_CONCLUIDO)


def faixa(e, hoje: Optional[date] = None) -> str:
    """Em que faixa do painel esta linha entra.

    Concluído ANTES de tudo: quem terminou não está parado nem "termina esta
    semana" — já terminou, e pô-lo em atenção encheria a faixa que existe
    justamente para ser curta.
    """
    if e.concluido():
        return FAIXA_CONCLUIDO
    if e.parada_dias(hoje) >= _DIAS_PARADO:
        return FAIXA_ATENCAO
    fim = e.previsao_de_fim(hoje)
    if fim and fim <= sexta_desta_semana(hoje):
        return FAIXA_TERMINA
    return FAIXA_CURSO


def por_faixa(linhas: list, hoje: Optional[date] = None) -> list:
    """``[(chave, título, [linhas])]``, na ordem, sem as faixas vazias.

    Faixa vazia com título é espaço reservado por via das dúvidas — e ainda
    promete uma seção que não existe naquele dia.

    A ordem DENTRO da faixa é a que chegou (urgência, ver
    :meth:`EmTratamento.urgencia`): a faixa agrupa, não reordena.
    """
    baldes = {}
    for e in linhas:
        baldes.setdefault(faixa(e, hoje), []).append(e)
    return [(c, _TITULOS_DE_FAIXA[c], baldes[c])
            for c in ORDEM_DAS_FAIXAS if baldes.get(c)]


def _somar_dias_uteis(inicio: date, dias: int) -> date:
    """``inicio`` + ``dias`` dias ÚTEIS, pulando sábado e domingo.

    Feriado não entra, pela mesma razão de :func:`dias_uteis_entre`: a lista do
    serviço não está no app, e inventar um calendário faria a tela prometer um
    fim que o feriado adia. O erro fica para o lado de ANTES, e para "acaba
    nesta semana?" isso basta.
    """
    fora = inicio
    passos = max(0, int(dias))
    while passos:
        fora += timedelta(days=1)
        if fora.weekday() < 5:
            passos -= 1
    return fora


def prever_fim(ultima: Optional[date], faltam: int, frequencia: str = "",
               hoje: Optional[date] = None) -> Optional[date]:
    """Em que dia a ÚLTIMA fração deve cair. ``None`` quando não dá para saber.

    Uma conta, um lugar: a lista usa isto para a faixa "terminam esta semana"
    e o quadro para o cartão de término previsto — e duas contas para a mesma
    data, na mesma tela, é como ela perde a confiança de quem lê.

    A contagem parte da ÚLTIMA SESSÃO, e não de hoje: o ritmo é ENTRE frações,
    então a próxima cai um passo depois da anterior, não um passo depois do
    momento em que se olha a tela. O piso é HOJE, porque num paciente parado a
    conta cairia no passado — e data vencida lida como previsão é pior que
    previsão nenhuma.
    """
    agora = hoje or date.today()
    if faltam <= 0:
        return None
    dias, por = _RITMO.get(frequencia, (1, 1))
    # Teto da divisão, sem ``math``: duas frações no MESMO dia não gastam dois
    # dias, e arredondar para baixo prometeria um fim que não chega.
    passos = -(-int(faltam) * dias // por)
    return max(_somar_dias_uteis(ultima or agora, passos), agora)


def sexta_desta_semana(hoje: Optional[date] = None) -> date:
    """A sexta-feira da semana de ``hoje`` — o fim de "esta semana".

    No fim de semana devolve a sexta que VEM: sábado e domingo pertencem, para
    quem lê a lista, à semana de trabalho seguinte.
    """
    dia = hoje or date.today()
    return dia + timedelta(days=(4 - dia.weekday()) % 7)


def dias_uteis_entre(inicio: date, fim: date) -> int:
    """Dias úteis ESTRITAMENTE entre as duas datas.

    Não conta feriado: a lista de feriados do serviço não está no app, e
    inventar um calendário faria a tela afirmar uma falta que não houve. O
    número sai no máximo um dia maior que o real, e para "houve parada?" isso
    basta — o que não pode é apontar parada onde só houve fim de semana.
    """
    if not inicio or not fim or fim <= inicio:
        return 0
    n = 0
    dia = inicio + timedelta(days=1)
    while dia < fim:
        if dia.weekday() < 5:      # 5 = sábado, 6 = domingo
            n += 1
        dia += timedelta(days=1)
    return n


def intervalos_das_sessoes(sessoes: list, minimo: int = 1) -> list:
    """As paradas, da mais recente para trás.

    ``minimo=1`` já acusa um único dia útil perdido — é o que o serviço quer
    ver; ``minimo`` maior serve para destacar só as paradas longas.

    Duas frações no MESMO dia (dois isocentros, ou um retratamento no mesmo
    turno) não são intervalo, e não podem virar "0 dias" na lista.
    """
    datas = sorted({s.data for s in sessoes if s.data})
    fora = []
    for anterior, seguinte in zip(datas, datas[1:]):
        n = dias_uteis_entre(anterior, seguinte)
        if n >= minimo:
            fora.append(Intervalo(de=anterior, ate=seguinte, dias_uteis=n))
    fora.reverse()
    return fora


# ── Planos que tratam JUNTOS ────────────────────────────────────────────────
# Mama e fossa supraclavicular são DOIS planos no sistema e UMA sessão na sala:
# a paciente deita uma vez, e os campos dos dois planos entram na mesma passagem.
# O banco não diz isso em lugar nenhum — cada plano tem numeração de fração
# própria, e as duas linhas de 20/08/2026 (fração 7 do ``cFSC_D2`` às 10:42,
# fração 7 do ``cMAMA_BOOSTD2`` às 10:37) são a MESMA fração do curso.
#
# Contando uma fração por linha, a tela mostrou "16 / 15" numa paciente na 8ª
# sessão — o número grande passou do total, a barra encheu e o texto embaixo
# declarou "tratamento concluído" no meio do tratamento. A dose entregue, que
# vem pronta do DW, é que denunciou: 2240 cGy de 4800, quase metade.
#
# É a QUARTA vez que a granularidade do ``FactTreatmentHistory`` morde neste
# módulo: campo, ponto de referência, plano replanejado, e agora plano
# SIMULTÂNEO.


def planos_simultaneos(sessoes: list) -> list:
    """Os grupos de planos que tratam JUNTOS, do mais recente para trás.

    O que junta dois planos é o DIA: plano que trata no mesmo dia que outro
    trata junto com ele. Não há coluna no DW que diga isso — nem "grupo", nem
    "sessão"; o que existe é uma linha por plano, cada uma com a sua fração.

    Replanejamento não cai nesta rede porque o plano velho PARA no dia em que o
    novo começa: na paciente de 20/08 o par antigo tratou só 07/08 e o novo de
    12/08 em diante, e os dois pares saíram separados. O caso que enganaria é o
    replanejamento que trata os dois planos no MESMO dia (manhã com o velho,
    tarde com o novo) — aí os quatro viram um grupo só e a tela deixa de dizer
    "replanejado". Preferi esse erro ao contrário: contar duas frações onde
    houve uma é o que estoura o total impresso na ficha.
    """
    por_dia = {}
    for s in sessoes:
        if s.data:
            por_dia.setdefault(s.data, set()).add(s.plano)
    grupos = []
    for planos in por_dia.values():
        junto = set(planos)
        # Fundir todo grupo que já toque algum destes planos: o par mama+FSC
        # aparece uma vez por dia, e sem a fusão sairiam sete grupos iguais.
        for g in [g for g in grupos if g & junto]:
            grupos.remove(g)
            junto |= g
        grupos.append(junto)
    # A ordem é a das SESSÕES (que já vêm da mais recente), não a dos dias: o
    # grupo em curso tem de ser o primeiro, porque é dele que a tela fala.
    fora = []
    for s in sessoes:
        g = next((g for g in grupos if s.plano in g), None)
        if g is not None and g not in fora:
            fora.append(g)
    return fora


def fracoes_entregues(sessoes: list) -> int:
    """Quantas FRAÇÕES do curso — e não quantas linhas de plano.

    Duas linhas do mesmo DIA em planos DIFERENTES são a mesma fração (mama e
    FSC tratam juntas). Duas linhas do MESMO plano no mesmo dia são duas
    frações de verdade — dois turnos no mesmo dia acontecem, e é por isso que
    aqui vai o máximo por plano e não um "uma por dia", que apagaria a segunda.
    """
    por_dia = {}
    soltas = 0
    for s in sessoes:
        if not s.data:
            # Sem data não dá para saber com quem ela anda. Conta sozinha: o
            # filtro do SQL não deixa passar linha sem ``TreatmentStartTime``,
            # então isto é rede de segurança, não caso previsto.
            soltas += 1
            continue
        conta = por_dia.setdefault(s.data, {})
        conta[s.plano] = conta.get(s.plano, 0) + 1
    return somar_por_dia(por_dia) + soltas


def cobre(entregues: int, previstas: int) -> bool:
    """O total previsto COBRE o que já foi aplicado?

    Quando não cobre, ele não é o total daquilo que a tela está contando: é o
    de outra coisa. Foi o que apareceu em 26/08/2026 — 9 frações aplicadas num
    curso cujo ``FractionsPlanned`` dizia 4, porque as outras 5 eram de um
    segundo tratamento dentro do mesmo curso. "9 / 4" não é um andamento; é uma
    conta impossível impressa em corpo 64.

    Função livre, e não só um método do quadro, porque a mesma pergunta se faz
    do CURSO e de cada PLANO dele — e a regra escrita duas vezes é a que fica
    para trás numa das duas na primeira mudança.

    Sem total previsto devolve ``True``: aí não há divisão nenhuma para estar
    errada, e o caso é o outro ("o sistema não informou").
    """
    return int(previstas or 0) <= 0 or int(previstas) >= int(entregues or 0)


def somar_por_dia(por_dia: dict) -> int:
    """A REGRA, separada de onde os dias vieram: ``{dia: {plano: linhas}}``.

    Existe como função própria porque o painel da lista conta as frações de
    OUTRA consulta que o quadro do paciente, e as duas contas discordando é o
    defeito que se está corrigindo — não uma consequência aceitável dele. Uma
    regra, um lugar.
    """
    return sum(max(c.values()) for c in por_dia.values())


def _nomes_do_grupo(sessoes: list) -> str:
    """Os nomes dos planos que tratam juntos, na ordem em que entram na sala.

    A ordem é a do HORÁRIO da última sessão de cada um — "cMAMA_BOOSTD2 às
    10:37 + cFSC_D2 às 10:42" é a ordem em que a técnica os viu na fila do
    acelerador. Alfabética poria o boost antes do plano principal por acaso da
    letra, e o nome do plano é o que o serviço usa para falar do caso.
    """
    ordem = {}
    for s in sessoes:            # já vêm da mais recente para trás
        if s.plano not in ordem:
            ordem[s.plano] = (s.hora or "", s.plano_nome or "")
    nomes = []
    for _, nome in sorted(ordem.values()):
        if nome and nome not in nomes:
            nomes.append(nome)
    return " + ".join(nomes)


@dataclass
class GrupoDePlanos:
    """Um GRUPO de planos que tratam juntos, e o que ele entregou.

    É a unidade que o seletor de plano oferece. Existe porque "curso" e "plano"
    respondem perguntas diferentes e o banco só sabe responder a primeira: a
    paciente de 26/08/2026 tinha UM curso (``C1_JAN_2026``) com uma SBRT de
    pulmão (``sPTV_1`` + ``sPTV_2``, 4 frações) e, depois, uma mandíbula
    (``sMANDIBULA_E``, 5 frações). O curso somou 9 frações; o
    ``FractionsPlanned`` do DW devolveu 4, que é de um plano só. "9 / 4" era o
    resultado de dividir dois fatos verdadeiros que não falam da mesma coisa.

    Grupo, e não plano: mama e FSC são dois planos e uma sessão só (ver
    :func:`planos_simultaneos`). Quem deita na mesa não distingue os dois, e a
    tela também não pode.
    """
    planos: tuple = ()
    nome: str = ""             # os nomes dos planos, na ordem em que tratam
    sessoes: list = field(default_factory=list)
    entregues: int = 0
    previstas: int = 0
    atual: bool = False        # é o grupo em curso (o mais recente)

    def inicio(self) -> Optional[date]:
        datas = [s.data for s in self.sessoes if s.data]
        return min(datas) if datas else None

    def fim(self) -> Optional[date]:
        datas = [s.data for s in self.sessoes if s.data]
        return max(datas) if datas else None

    def periodo(self) -> str:
        de, ate = self.inicio(), self.fim()
        if not de:
            return ""
        if not ate or ate == de:
            return de.strftime("%d/%m/%Y")
        return f"{de.strftime('%d/%m/%Y')} – {ate.strftime('%d/%m/%Y')}"

    def rotulo(self) -> str:
        """Como o grupo aparece no seletor.

        COM a contagem de frações, ao contrário de :meth:`Curso.rotulo` — e a
        diferença não é de gosto: lá o número vinha de outra consulta que a do
        número grande e as duas discordavam; aqui ele sai das MESMAS sessões
        que a tela já tem na mão. Uma conta, um lugar. E é justamente o número
        que faz escolher entre um item e outro da lista.
        """
        fx = (f"{self.entregues} de {self.previstas}" if self.previstas
              else f"{self.entregues} "
                   + ("fração" if self.entregues == 1 else "frações"))
        # Montado pelos pedaços que EXISTEM: com o período vazio (sessão sem
        # data no banco), juntar tudo às cegas deixava um buraco de seis
        # espaços no meio da linha, que se lê como coluna que não carregou.
        cabeca = [p for p in (self.nome or "Plano sem nome", self.periodo())
                  if p]
        return "   ".join(cabeca) + f"   ·   {fx}"


def grupos_do_curso(t) -> list:
    """Os grupos de planos do curso que está na tela, do mais recente para trás.

    Sai das sessões que o quadro JÁ tem — nenhuma consulta a mais. É o que
    permite trocar de plano no seletor sem falar com o banco: o curso precisa
    de outra leitura (as sessões são de lá), o plano não.
    """
    fora = []
    for i, planos in enumerate(planos_simultaneos(t.sessoes or [])):
        do_grupo = [s for s in t.sessoes if s.plano in planos]
        fora.append(GrupoDePlanos(
            planos=tuple(sorted(planos)),
            nome=_nomes_do_grupo(do_grupo),
            sessoes=do_grupo,
            entregues=fracoes_entregues(do_grupo),
            # MÁXIMO, e não o do primeiro: mama e FSC declaram as mesmas 15
            # frações, mas basta um vir zerado para o grupo virar "7 de ?".
            previstas=max([s.plano_previstas for s in do_grupo] or [0]),
            atual=(i == 0),
        ))
    return fora


# ── SQL — colunas DOCUMENTADAS, agregação ainda por conferir ────────────────
# As colunas abaixo saem da Data Lineage Tool 15.6 da Varian (o
# ``FactTreatmentHistory_Schema.csv` que acompanha a ferramenta), não de
# adivinhação. Vale citar as descrições que decidiram cada escolha:
#
#   TreatmentSignOffUser1  "The name of the operator who performed the
#                           treatment. This will be set by the delivery
#                           machine."  → é QUEM TRATOU, em texto, sem join.
#                           User2/User3 são ajudantes ("Additional system user
#                           helping therapist to treat a Patient").
#   FractionNumber         "Fraction number for a field which was treated."
#   TreatmentStartTime     "Date and Time when the treatment has started."
#   FractionsDelivered     "Number of fraction are delivered"  (≠ FractionsPlanned)
#   DoseDeliveredPerFraction  "Actual dose applied to a RefPoint by a treatment."
#   TerminationStatus      "NORMAL, OPERATOR, MACHINE, UNKNOWN" — como a sessão
#                           terminou.
#
# DUAS ARMADILHAS que a documentação denuncia e que mudam tudo:
#
# 1. A tabela tem UMA LINHA POR CAMPO TRATADO, não por fração. Um paciente com
#    cinco campos por sessão gera cinco linhas por fração; contar linhas daria
#    5× o número de frações. Daí o ``GROUP BY th.FractionNumber``.
#
# 2. ``FactTreatmentHistory`` "can have treated and non-treated data also like
#    only Course created or only course plan created" (TableDescription.csv).
#    Ou seja: há linhas de plano que NUNCA foram tratadas. Sem filtro, elas
#    virariam frações fantasmas na tela. Daí o ``TreatmentStartTime IS NOT NULL``
#    e o ``FractionNumber > 0``.
#
# O que AINDA não está conferido — e é o que mantém o portão fechado:
#   a. se esse filtro basta para separar tratado de não-tratado neste banco;
#   b. se ``DoseDeliveredPerFraction`` somado por fração dá a dose do dia ou
#      repete o mesmo valor em cada campo (é dose a um RefPoint, não ao campo);
#   c. se ``TreatmentSignOffUser1`` está preenchido nesta clínica — a coluna
#      existe, mas quem a preenche é a máquina de tratamento.
#
# ``DimTreatmentTransaction`` é a alternativa para (a): a documentação diz que
# ela "contains only treated records". Se o filtro daqui não bastar, o caminho
# é passar por ela.

# Os CURSOS do paciente, do mais recente para trás. É a consulta do passo 1b do
# mapeador, que rodou contra o banco em 19/08/2026 e devolveu os quatro cursos
# do paciente de teste — daqui saiu a prova de que o filtro por curso era
# obrigatório. O ``LEFT JOIN DimCourse`` é o único acréscimo: traz o nome ("C1")
# e, se o join falhar, o nome vem vazio em vez de a consulta inteira sumir.
_SQL_CURSOS = """
SELECT th.DimCourseID,
       MAX(c.CourseId),
       COUNT(DISTINCT th.FractionNumber),
       MAX(th.FractionsPlanned),
       MIN(th.TreatmentStartTime),
       MAX(th.TreatmentStartTime)
  FROM DWH.FactTreatmentHistory th
  JOIN DWH.DimPatient p ON p.DimPatientID = th.DimPatientID
  LEFT JOIN DWH.DimCourse c ON c.DimCourseID = th.DimCourseID
 WHERE p.PatientId = ?
   AND th.TreatmentStartTime IS NOT NULL
   AND th.FractionNumber > 0
 GROUP BY th.DimCourseID
 ORDER BY MAX(th.TreatmentStartTime) DESC
"""

# ``DimCourseID`` no WHERE e ``PrimaryFlag`` no filtro — os dois vieram da
# rodada de 19/08/2026 contra o paciente 9000001CEL, e nenhum dos dois eu teria
# adivinhado:
#
# * o paciente tinha DOIS cursos, um de 2024 e um de 2026. Sem o curso no
#   WHERE, o ``GROUP BY FractionNumber`` FUNDIA a fração 2 de um com a fração 2
#   do outro: o ``MIN(TreatmentStartTime)`` devolvia a data de 2024 para uma
#   sessão de 2026, e a tela mostrava "15 de 15" para quem estava na 2ª de 10.
#   Foi assim que apareceu na saída — as oito frações "mais recentes" estavam
#   todas em 2024, com o curso de 2026 escondido dentro delas.
# * ``PrimaryFlag`` separa o ponto de referência PRINCIPAL. Sem ele, a soma de
#   dose percorre todos os RefPoints do plano e multiplica a dose do dia.
# ``GROUP BY DimPlanID, FractionNumber`` — e o ``DimPlanID`` é obrigatório.
# Medido em 20/08/2026 no paciente 9000011CEL: UM curso com TRÊS planos, e a
# numeração de fração REINICIA a cada plano (o plano 72312 estava na fração 8
# enquanto o 72311 já tinha chegado à 12). Agrupando só por ``FractionNumber``,
# a fração 8 do plano novo se fundia com a 8 do velho e o ``MIN`` devolvia a
# data de JULHO — duas semanas de tratamento sumiam da tela, e a última sessão
# aparecia como 07/08 num paciente que tratou hoje.
#
# É a mesma fusão que o ``DimCourseID`` resolveu um nível acima. Aqui embaixo
# ela voltou porque plano e curso são coisas diferentes: replanejar cria um
# plano novo DENTRO do mesmo curso.
#
# E o ``PrimaryFlag`` SAIU daqui: ele entrou para não somar dose de vários
# pontos de referência, e a sessão não tem mais dose própria. Deixá-lo custava
# as linhas em que ele vem nulo — a de 31/07 deste paciente era uma delas.
#
# SEM dose por sessão, e isso é uma decisão, não um esquecimento. A rodada de
# 19/08/2026 mediu: ``SUM(DoseDeliveredPerFraction)`` devolveu **18,0 Gy** por
# fração num curso cuja dose por fração é **9,0 Gy** — o dobro. O paciente tinha
# mais de um ponto de referência com ``PrimaryFlag = 1`` (``PTV COST 4mm`` e
# ``PTV 3mm``), e a soma percorre todos.
#
# Dava para caçar um RefPoint só, mas a dose ACUMULADA — que é a que a tela
# mostra — já vem pronta e conferida em ``CourseDoseDelivered`` (18,0 de 27,0,
# batendo com 2 de 3 frações × 9 Gy). Somar campo a campo para chegar ao mesmo
# lugar seria refazer, com risco, uma conta que o banco já fez certo.
#
# A sessão fica então sem dose própria, e a tela não a mostra. Regra do projeto:
# campo sem fonte confiável nasce vazio.
_SQL_SESSOES = """
SELECT th.FractionNumber,
       MIN(th.TreatmentStartTime),
       MAX(m.MachineId),
       MAX(th.TreatmentSignOffUser1),
       th.DimPlanID,
       MAX(th.FractionsPlanned),
       MAX(pl.PlanSetupId),
       -- O SEGUNDO técnico da sessão. A Data Lineage Tool descreve User2/User3
       -- como "Additional system user helping therapist to treat a Patient":
       -- na sala são duas pessoas posicionando, e a folha só nomeava uma. Vem
       -- vazio na maioria das linhas, e vazio aqui é vazio na tela — nunca o
       -- primeiro nome repetido.
       MAX(th.TreatmentSignOffUser2)
  FROM DWH.FactTreatmentHistory th
  JOIN DWH.DimPatient p ON p.DimPatientID = th.DimPatientID
  LEFT JOIN DWH.DimMachine m ON m.DimMachineID = th.DimActualMachineID
  LEFT JOIN DWH.DimPlan pl ON pl.DimPlanID = th.DimPlanID
 WHERE p.PatientId = ? AND th.DimCourseID = ?
   AND th.TreatmentStartTime IS NOT NULL
   AND th.FractionNumber > 0
 GROUP BY th.DimPlanID, th.FractionNumber
 ORDER BY MIN(th.TreatmentStartTime) DESC
"""

# O resumo do curso. Vem das colunas CALCULADAS do DW (função
# ``vf_syDoseFiguresAppSum``), que é o mesmo número que o ARIA mostra — melhor
# que recontar as linhas do lado de cá e arriscar discordar da tela do sistema.
# Também por curso: ``MAX(FractionsPlanned)`` sobre o paciente inteiro devolvia
# as 15 do curso velho no lugar das 10 do que está em andamento.
_SQL_RESUMO = """
SELECT TOP 1 th.FractionsDelivered, th.FractionsPlanned,
       th.CourseDoseDelivered, th.CourseDosePlanned
  FROM DWH.FactTreatmentHistory th
  JOIN DWH.DimPatient p ON p.DimPatientID = th.DimPatientID
 WHERE p.PatientId = ? AND th.DimCourseID = ?
   AND th.FractionsPlanned > 0 AND th.PrimaryFlag = 1
 ORDER BY th.LastTreatmentDate DESC
"""

# A dose de CADA plano do curso. Com dois planos tratando juntos, um número só
# de "dose entregue" não quer dizer nada: ``sMEDIAST_DB`` e ``sHILO-D_DIB`` são
# alvos DIFERENTES, e dose a alvos diferentes não se soma — somar seria afirmar
# uma dose que ninguém recebeu. Pedido do usuário em 21/08/2026, olhando o
# paciente 9000010CEL.
#
# MESMOS filtros do ``_SQL_RESUMO``, que está conferido: o que muda é o
# ``GROUP BY th.DimPlanID`` no lugar do ``TOP 1``. Assim o total do curso
# continua vindo de onde vinha, e os dois números não podem discordar por
# critérios diferentes — duas contas para o mesmo fato na mesma tela é como ela
# perde a confiança de quem lê.
#
# ``MAX``, nunca ``SUM``: mais de um ponto de referência por plano já devolveu
# o DOBRO da dose (18 Gy num curso de 9 Gy por fração, medido em 19/08/2026).
_SQL_DOSE_POR_PLANO = """
SELECT th.DimPlanID,
       MAX(pl.PlanSetupId),
       MAX(th.CourseDoseDelivered),
       MAX(th.CourseDosePlanned)
  FROM DWH.FactTreatmentHistory th
  JOIN DWH.DimPatient p ON p.DimPatientID = th.DimPatientID
  LEFT JOIN DWH.DimPlan pl ON pl.DimPlanID = th.DimPlanID
 WHERE p.PatientId = ? AND th.DimCourseID = ?
   AND th.FractionsPlanned > 0 AND th.PrimaryFlag = 1
 GROUP BY th.DimPlanID
"""


@dataclass
class DoseDoPlano:
    """Quanto UM plano entregou, e de quanto."""
    plano: int = 0
    nome: str = ""
    entregue_cgy: float = 0.0
    prescrita_cgy: float = 0.0

    def texto(self) -> str:
        if not self.entregue_cgy:
            return ""
        de = f"  de {self.prescrita_cgy:.0f}" if self.prescrita_cgy else ""
        return f"{self.entregue_cgy:.0f} cGy{de}"


def doses_por_plano(registro: str, curso=None) -> list:
    """A dose de cada plano do curso, do maior entregue para o menor.

    Lista VAZIA quando não deu para ler — e vazia aqui devolve a tela ao número
    único do curso, que é o comportamento conferido em 20/08/2026.
    """
    if not disponivel() or curso is None:
        return []
    try:
        linhas = capa_db._consultar(_SQL_DOSE_POR_PLANO, registro, curso)
    except capa_db.FalhaDeLeitura:
        _LOG.warning("Não consegui ler a dose por plano de %s", registro)
        return []
    fora = [DoseDoPlano(plano=int(pid or 0),
                        nome=capa_db._txt(nome),
                        entregue_cgy=float(ent or 0) * _GY_PARA_CGY,
                        prescrita_cgy=float(plan or 0) * _GY_PARA_CGY)
            for pid, nome, ent, plan in linhas]
    return sorted(fora, key=lambda d: -d.entregue_cgy)


def doses_distintas(doses: list) -> bool:
    """Vale a pena quebrar a dose por plano?

    Só quando os planos declaram doses DIFERENTES. Se o DW devolve o mesmo
    número para todos, esse número é do CURSO — repeti-lo uma vez por plano
    faria a tela afirmar que cada alvo recebeu o total, que é o erro oposto ao
    que se está corrigindo.

    É a granularidade sendo DESCOBERTA em vez de suposta: não está conferido se
    ``CourseDoseDelivered`` é por curso ou por plano neste banco, e este teste
    responde certo nos dois casos.
    """
    entregues = {round(d.entregue_cgy, 1) for d in doses if d.entregue_cgy}
    return len(doses) > 1 and len(entregues) > 1


# O DW guarda dose em GRAY (medido: ``DosePerFraction 4.0``,
# ``CourseDoseDelivered 40.0`` para um curso de 10 × 4 Gy). O resto do app fala
# cGy — a capa e a ficha imprimem cGy —, e duas unidades na mesma tela é como se
# perde uma casa decimal na leitura de quem confere.
_GY_PARA_CGY = 100.0


def sessoes_do_paciente(registro: str, curso=None) -> list:
    """As frações aplicadas NAQUELE curso, da mais recente para a mais antiga.

    Sem ``curso``, o atual. Lista vazia significa "não deu para saber" OU "não
    há sessões" — e é por isso que a tela pergunta antes por :func:`disponivel`:
    sem essa checagem, um paciente em tratamento apareceria como "0 de 25" por
    causa de rede ruim.
    """
    if not disponivel():
        return []
    alvo = str(registro or "").strip()
    if not alvo:
        return []
    if curso is None:
        curso = curso_atual(alvo)
    if curso is None:
        return []
    try:
        linhas = capa_db._consultar(_SQL_SESSOES, alvo, curso)
    except capa_db.FalhaDeLeitura:
        return []
    fora = []
    for (fracao, quando, maquina, quem, plano, planejadas, nome_plano,
         ajudante) in linhas:
        fora.append(Sessao(
            fracao=int(fracao or 0),
            plano=int(plano or 0),
            plano_previstas=int(planejadas or 0),
            plano_nome=capa_db._txt(nome_plano),
            data=quando.date() if hasattr(quando, "date") else None,
            hora=quando.strftime("%H:%M") if hasattr(quando, "strftime") else "",
            maquina=capa_db._txt(maquina),
            # Vazio quando a máquina de tratamento não assinou. ``_txt`` já
            # transforma o "NA" do DW em vazio, e a tela diz "(não informado)"
            # — nunca outro nome no lugar. Medido em 19/08/2026: 35 de 35
            # linhas assinadas (``wagner.sousa``, ``elaine.costa``).
            quem=_quem_legivel(capa_db._txt(quem)),
            ajudante=_quem_legivel(capa_db._txt(ajudante)),
        ))
    return fora


# ── O painel: quem está em tratamento ───────────────────────────────────────
# NÃO CONFERIDAS. Ver ``LISTA_VERIFICADA_EM`` no topo — as duas agregam a
# ``FactTreatmentHistory`` por data (2,7 milhões de linhas) e a segunda ainda
# cruza com ``DimPatientDoctor``.
#
# O join do médico é por ``ctrResourceSer``, NÃO por ``DimDoctorID``: essa
# coluna não existe em ``DimPatientDoctor``, e supor que existia foi o único
# erro de join do mapeamento da capa (ver ``capa_db._SQL_MEDICO``). Repetir o
# mesmo erro aqui seria imperdoável.
#
# O MÉDICO DE CADA LINHA entrou em 22/09/2026, com o Grupo Médico: vendo a
# agenda de vários médicos junto, a lista precisa dizer de quem é cada
# paciente. Ele vem por SUBCONSULTA JÁ AGRUPADA (``md``), não por join direto,
# pela mesma razão do ``EXISTS`` abaixo: o paciente pode ter mais de um
# vínculo, e o join multiplicaria as linhas antes do ``GROUP BY``. Agrupada por
# paciente, ela devolve no máximo uma linha, e o ``LEFT`` mantém na lista quem
# não tem médico vinculado — sumir da lista seria o pior desfecho possível.
#
# ``MIN(DoctorFullName)`` com ``COUNT(DISTINCT …)`` ao lado: com dois
# oncologistas vinculados, o nome sozinho mentiria por omissão, e a tela mostra
# "+1" para dizer que há outro. Também não medido — nem o resultado, nem o
# tempo (o cronômetro de 10/09 é ANTERIOR a esta coluna).
#
# O ``TerminationStatus`` NÃO é lido, desde 11/09/2026. Ele alimentava o ⚡ de
# "última sessão interrompida", e a marca saiu por decisão do usuário: se o
# tratamento foi realizado é o que interessa. Na rodada de 10/09 ela caiu em
# quem a sala viu tratar normal, e em quatro pacientes em quase toda sessão.
# Se um dia voltar, lembrar da granularidade: a tabela tem uma linha por CAMPO,
# e somar linhas deu "17 frações interrompidas" num curso de 20 com 13
# entregues — o certo era ``COUNT(DISTINCT FractionNumber)``.
#
# ``MIN(th.TreatmentStartTime)`` entrou em 24/09/2026, ao lado do ``MAX`` que
# já existia (vira ``ultima`` — a ÚLTIMA sessão): pedido da Agenda, "mostrar
# também data de início e data prevista de término". Mesma coluna, mesmo
# agrupamento, MIN em vez de MAX — a PRIMEIRA sessão do curso. NÃO CONFERIDA
# contra o banco real por conta própria (ninguém abriu o ARIA para comparar
# esta data ainda): entra sob o mesmo portão experimental da fração
# (``lista_disponivel()``), não sob ``VERIFICADO_EM``.

_SQL_EM_TRATAMENTO = """
SELECT p.PatientId,
       p.PatientFullName,
       th.DimCourseID,
       MAX(th.FractionsDelivered),
       MAX(th.FractionsPlanned),
       MIN(th.TreatmentStartTime),
       MAX(th.TreatmentStartTime),
       COUNT(DISTINCT th.DimActualMachineID),
       md.DoctorFullName,
       md.Quantos
  FROM DWH.FactTreatmentHistory th
  JOIN DWH.DimPatient p ON p.DimPatientID = th.DimPatientID
  LEFT JOIN (SELECT pd.DimPatientID,
                    MIN(d.DoctorFullName) AS DoctorFullName,
                    COUNT(DISTINCT d.DoctorFullName) AS Quantos
               FROM DWH.DimPatientDoctor pd
               JOIN DWH.DimDoctor d
                 ON d.ctrResourceSer = pd.ctrResourceSer
              -- ``pd``, não ``d``: OncologistFlag é do VÍNCULO
              -- paciente↔médico (DimPatientDoctor), não do médico. Com o
              -- alias errado o SQL Server recusa a consulta inteira
              -- ("Invalid column name 'OncologistFlag'", 207) e a aba
              -- Virtual não lista NINGUÉM — o erro só aparece contra o banco
              -- real, porque o banco local só devolve o que já foi gravado.
              -- As outras três consultas de médico já usavam ``pd``
              -- (``_SQL_MEDICOS``, ``_SQL_MEDICO_DO_PACIENTE``,
              -- ``capa_db._SQL_MEDICO``); esta ficou para trás.
              WHERE pd.OncologistFlag = 1
              GROUP BY pd.DimPatientID) md
         ON md.DimPatientID = th.DimPatientID
 WHERE th.TreatmentStartTime >= ?
   AND th.FractionNumber > 0
   AND th.PrimaryFlag = 1
   AND ISNULL(p.IsMOTestPatient, 0) = 0
 GROUP BY p.PatientId, p.PatientFullName, th.DimCourseID,
          md.DoctorFullName, md.Quantos
 HAVING MAX(th.FractionsDelivered) < MAX(th.FractionsPlanned)
     OR MAX(th.FractionsPlanned) IS NULL OR MAX(th.FractionsPlanned) = 0
 ORDER BY MAX(th.TreatmentStartTime) DESC
"""

# A mesma, SEM o corte de concluídos. Serve ao caso oposto: "quem terminou nos
# últimos dias" é a lista de quem precisa de seguimento agendado.
_SQL_EM_TRATAMENTO_TODOS = _SQL_EM_TRATAMENTO.replace(
    """ HAVING MAX(th.FractionsDelivered) < MAX(th.FractionsPlanned)
     OR MAX(th.FractionsPlanned) IS NULL OR MAX(th.FractionsPlanned) = 0
""", "")

# Mesma consulta, restrita aos pacientes de um ou mais médicos. ``EXISTS`` em
# vez de ``JOIN``: o paciente pode ter vários vínculos de médico, e o join
# multiplicaria as linhas antes do ``GROUP BY`` — o que estragaria justamente o
# ``COUNT(DISTINCT máquina)``.
def _com_medico(sql: str) -> str:
    """Enxerta o filtro de médico no SQL base.

    ``EXISTS`` em vez de ``JOIN``: o paciente pode ter vários vínculos de
    médico, e o join multiplicaria as linhas ANTES do ``GROUP BY`` — o que
    estragaria justamente o ``COUNT(DISTINCT máquina)``.

    A marca é o ``GROUP BY`` da consulta PRINCIPAL, com o nome da primeira
    coluna junto. ``" GROUP BY "`` sozinho não serve desde 22/09/2026: a
    subconsulta que traz o médico de cada linha tem um ``GROUP BY`` próprio, e
    ``str.replace`` troca TODAS as ocorrências — o filtro entraria dentro dela
    e o SQL sairia inválido.
    """
    marca = "\n GROUP BY p.PatientId"
    assert sql.count(marca) == 1, "o GROUP BY principal deixou de ser único"
    return sql.replace(
        marca,
        """
   AND EXISTS (SELECT 1
                 FROM DWH.DimPatientDoctor pd2
                 JOIN DWH.DimDoctor d2
                   ON d2.ctrResourceSer = pd2.ctrResourceSer
                WHERE pd2.DimPatientID = th.DimPatientID
                  AND d2.DoctorFullName IN ({}))
 GROUP BY p.PatientId""")


_SQL_EM_TRATAMENTO_MEDICO = _com_medico(_SQL_EM_TRATAMENTO)
_SQL_TODOS_MEDICO = _com_medico(_SQL_EM_TRATAMENTO_TODOS)

# Os radio-oncologistas que têm paciente vinculado. ``OncologistFlag`` separa o
# médico do resto da equipe — sem ele a lista traz dosimetrista e físico, e quem
# procura o próprio nome não o encontra no meio de sessenta.
_SQL_MEDICOS = """
SELECT DISTINCT d.DoctorFullName
  FROM DWH.DimPatientDoctor pd
  JOIN DWH.DimDoctor d ON d.ctrResourceSer = pd.ctrResourceSer
 WHERE pd.OncologistFlag = 1 AND d.DoctorFullName <> 'NA'
   AND d.DoctorFullName IS NOT NULL
 ORDER BY d.DoctorFullName
"""

# Janela do painel. 30 dias cobre o curso inteiro da maioria e ainda deixa ver
# quem parou — o objetivo é justamente encontrar quem NÃO tratou esta semana, e
# uma janela de 7 dias esconderia exatamente essa pessoa.
DIAS_DA_JANELA = 30


@dataclass
class Medico:
    """Um radio-oncologista: como se lê, e como o banco o chama.

    Os dois nomes são diferentes e os dois fazem falta. O DW guarda invertido
    ("Monteiro, Paula Monteiro Aragao") e a tela mostra desinvertido — mas o
    FILTRO tem de voltar ao formato do banco. Desinverter não tem volta
    confiável (o sobrenome repetido do DW não sobrevive à ida e volta), então o
    original viaja junto em vez de ser reconstruído.
    """
    nome: str = ""      # como aparece na tela
    bruto: str = ""     # exatamente como está no banco — é o que vai no WHERE


def _equipe_configurada() -> list:
    """Os médicos que o serviço mantém em Configurações → Equipe.

    Import local, como no ``capa_pdf.medico_completo``: ``dados.equipe`` puxa
    o ``dicom_rt``, e importá-los no topo de um módulo de banco fecharia o
    ciclo. Lista VAZIA quando não dá para ler — e aí não se filtra nada, que é
    o comportamento de antes deste filtro existir: perder a lista inteira de
    médicos por causa de um arquivo de apoio seria pior do que mostrá-la
    inteira.
    """
    try:
        from isocentro.dados.equipe import _carregar_medicos

        nomes, _unidades = _carregar_medicos()
        return list(nomes or ())
    except Exception:  # noqa: BLE001
        _LOG.exception("Não consegui ler a equipe configurada")
        return []


def _medicos_do_banco() -> list:
    """A consulta em si, sem portão — quem chama decide QUAL portão vale.

    Extraída de :func:`medicos` em 23/09/2026 para a aba Agenda poder pedir a
    MESMA lista (mesma equipe, mesmo casamento de nome) atrás do PRÓPRIO
    portão (``agenda_db.disponivel()``) — o da Virtual (``LISTA_VERIFICADA
    _EM``) pode estar fechado sem que isso deva esvaziar o filtro de médico de
    uma tela que não depende dele.
    """
    try:
        linhas = capa_db._consultar(_SQL_MEDICOS)
    except capa_db.FalhaDeLeitura:
        return []
    from isocentro.dicom import dicom_rt

    equipe = _equipe_configurada()
    fora = []
    for (bruto,) in linhas:
        bruto = capa_db._txt(bruto)
        if not bruto:
            continue
        nome = capa_dados.de_pessoa(bruto)
        if equipe and not dicom_rt.mesma_pessoa(nome, equipe):
            continue
        fora.append(Medico(nome=nome, bruto=bruto))
    return sorted(fora, key=lambda m: m.nome.upper())


def medicos() -> list:
    """Os radio-oncologistas com paciente, em ordem de nome.

    Só quem está na EQUIPE configurada. A consulta pergunta ao DW quem tem
    paciente vinculado com ``OncologistFlag``, e ali entram o usuário de teste
    do ARIA ("Test Toast"), o cadastro do físico ("Fisica Fisica") e quem já
    saiu do serviço: quem procura o próprio nome nesta lista procura entre
    médicos, e o vínculo do banco não é a lista da equipe.

    O casamento é o ``mesma_pessoa`` da reconciliação de nomes, porque as duas
    listas grafam a mesma pessoa de jeitos diferentes — "Keiko Nakamura" no
    banco, "Keiko Harumi Sato Nakamura" na equipe. Comparar texto igual apagaria
    catorze dos dezoito nomes.

    Médico novo aparece na lista assim que for cadastrado em Configurações →
    Equipe; antes disso não aparece, o que é o preço de a lista ser a do
    serviço e não a do banco.
    """
    if not lista_disponivel():
        return []
    return _medicos_do_banco()


def em_tratamento(medicos_alvo=(), dias: int = DIAS_DA_JANELA,
                  hoje: Optional[date] = None,
                  incluir_concluidos: bool = False) -> Optional[list]:
    """Quem recebeu tratamento nos últimos ``dias``, um por curso.

    ``medicos_alvo``: :class:`Medico` (ou os nomes BRUTOS do banco). Vazio =
    todos.

    Devolve ``None`` quando NÃO DEU para perguntar, e ``[]`` quando o banco
    respondeu que não há ninguém. São respostas opostas para quem está na
    frente da tela.
    """
    if not lista_disponivel():
        return None
    # STRING, não ``date``. O tipo SQL ``DATE`` só existe a partir do SQL Server
    # 2008, e a estação tem apenas o driver ODBC antigo ("SQL Server", de 2000)
    # — ele não sabe enviar um ``datetime.date`` e a consulta falha. Como a
    # falha vinha embrulhada em ``FalhaDeLeitura``, a lista voltava VAZIA e a
    # tela dizia "ninguém em tratamento nesta janela" para um médico com agenda
    # cheia. Foi o que apareceu no primeiro uso.
    #
    # ISO em texto o SQL Server converte sozinho, em qualquer driver.
    corte = (hoje or date.today()) - timedelta(days=int(dias or DIAS_DA_JANELA))
    desde = corte.strftime("%Y-%m-%d")
    nomes = [m.bruto if isinstance(m, Medico) else str(m or "")
             for m in medicos_alvo]
    nomes = [n for n in nomes if n.strip()]
    # Sem ``incluir_concluidos``, quem já entregou tudo fica FORA. O cartão se
    # chama "em tratamento" e listava, na maioria das linhas, gente que terminou
    # semanas antes — quem olhava lia aquilo como agenda do dia e não era.
    # Terminados continuam alcançáveis: são o outro caso de uso (agendar
    # seguimento), e por isso viram um filtro em vez de sumirem.
    base = _SQL_EM_TRATAMENTO_TODOS if incluir_concluidos else _SQL_EM_TRATAMENTO
    com_medico = _SQL_TODOS_MEDICO if incluir_concluidos \
        else _SQL_EM_TRATAMENTO_MEDICO
    try:
        if nomes:
            marcas = ", ".join("?" for _ in nomes)
            linhas = capa_db._consultar(
                com_medico.format(marcas), desde, *nomes)
        else:
            linhas = capa_db._consultar(base, desde)
    except capa_db.FalhaDeLeitura:
        # ``None``, não ``[]``: "não consegui perguntar" e "ninguém em
        # tratamento" são respostas OPOSTAS para quem está na frente da tela, e
        # devolver as duas como lista vazia foi exatamente o que fez a aba
        # afirmar que o médico não tinha paciente nenhum.
        return None
    fora = []
    for (pid, nome, curso, entregues, previstas, inicio, ultima, maqs,
         medico, quantos_medicos) in linhas:
        fora.append(EmTratamento(
            registro=capa_db._txt(pid),
            nome=capa_dados.de_pessoa(capa_db._txt(nome)),
            curso_id=int(curso or 0),
            entregues=int(entregues or 0),
            previstas=int(previstas or 0),
            inicio=inicio.date() if hasattr(inicio, "date") else None,
            ultima=ultima.date() if hasattr(ultima, "date") else None,
            maquinas=int(maqs or 0),
            # ``de_pessoa`` aqui e não na tela: é a mesma passagem de
            # "SOBRENOME, Nome" para "Nome Sobrenome" que o resto do painel já
            # faz, e deixá-la para o widget faria duas grafias do mesmo médico
            # aparecerem na mesma janela.
            medico=capa_dados.de_pessoa(capa_db._txt(medico)),
            medicos_total=int(quantos_medicos or 0),
        ))
    # A recontagem vem ANTES do corte e da ordenação: as duas dependem de
    # ``entregues``. Ordenar pelo número do DW e corrigir depois deixaria a
    # lista na ordem de uma verdade que a própria tela já não mostra.
    _corrigir_entregues(fora)
    if not incluir_concluidos:
        # O ``HAVING`` do SQL cortou pelo número do DW; a recontagem descobre
        # quem já terminou apesar dele — foi ela que tirou da lista a paciente
        # de 21/08, que aparecia "parada há 14 dias úteis" duas semanas depois
        # de concluir. O cartão se chama "em tratamento".
        fora = [e for e in fora if not e.concluido()]
    _contar_cursos(fora)
    # Antes da ordenação também: a frequência decide se a marca de interrupção
    # existe, e a interrupção pesa na urgência.
    _marcar_frequencia(fora)
    # Ordenado por URGÊNCIA aqui, e não no ORDER BY: a urgência depende de
    # "hoje" (dias úteis parados), e data corrente dentro de SQL amarraria o
    # resultado ao relógio do servidor. Desempate pela sessão mais recente.
    hoje = hoje or date.today()
    fora.sort(key=lambda e: (-e.urgencia(hoje), -(e.ultima or date.min).toordinal()))
    return fora


# As frações de cada curso da lista, contadas como o QUADRO as conta.
#
# O ``MAX(FractionsDelivered)`` da consulta principal é por PLANO, e a numeração
# de fração REINICIA a cada replanejamento. Visto na tela em 21/08/2026, com a
# paciente 9000012CEL: três planos (13 frações no ``cMAMA_E_DIBH``, 1 no
# ``cMAMA_E_6EX``, 1 no ``cMAMA_E_6EX2``), o MAX devolveu 13, e a lista mostrou
# "13/15 · faltam 2 · parado há 14 dias úteis" para quem TERMINOU em 31/07 — o
# quadro dela, na mesma tela, dizia "15 / 15 · tratamento concluído".
#
# Alarme falso é o que faz parar de olhar a lista: mandar procurar quem já
# acabou custa a atenção de quem realmente parou no meio.
#
# Somar ``FractionsDelivered`` por plano seria a correção ÓBVIA e erraria pelo
# outro lado: mama e FSC tratam JUNTAS, e 7 + 7 daria 14 sessões onde houve 7.
# Por isso as linhas vêm cruas e a conta é a de :func:`somar_por_dia`, a mesma
# do quadro.
#
# O agrupamento imita o do ``_SQL_SESSOES``: uma linha por (plano, fração), com
# o ``MIN`` decidindo o dia dela. Sem o MIN, uma fração que atravessasse a
# meia-noite contaria em dois dias.
#
# Sem ``PrimaryFlag = 1``, ao contrário da consulta principal, e de propósito: o
# filtro existe lá para não somar a dose de dois RefPoints (foi o que deu 18 Gy
# num curso de 9 Gy por fração). Aqui não se soma dose nenhuma, e o próprio
# ``GROUP BY`` por fração já funde os RefPoints numa linha só — pôr o filtro
# faria a recontagem discordar do quadro, que também não o tem.
#
# ``CONVERT(..., 112)`` devolve "AAAAMMDD" em TEXTO, e não o tipo ``DATE``: o
# driver ODBC antigo da estação não conhece esse tipo (ver o comentário do
# ``desde`` em :func:`em_tratamento`), e aqui só se precisa comparar dias.
_SQL_FRACOES_DO_CURSO = """
SELECT p.PatientId,
       th.DimCourseID,
       th.DimPlanID,
       CONVERT(char(8), MIN(th.TreatmentStartTime), 112)
  FROM DWH.FactTreatmentHistory th
  JOIN DWH.DimPatient p ON p.DimPatientID = th.DimPatientID
 WHERE p.PatientId IN ({})
   AND th.TreatmentStartTime IS NOT NULL
   AND th.FractionNumber > 0
 GROUP BY p.PatientId, th.DimCourseID, th.DimPlanID, th.FractionNumber
"""


def _corrigir_entregues(linhas: list) -> None:
    """Troca o ``entregues`` do DW pela contagem por dia, no lugar.

    Falha em silêncio, como :func:`_contar_cursos`: sem a correção a lista
    continua a que sempre foi, com o número do banco — e o painel já anuncia,
    em faixa, que não está conferido. Derrubar a lista inteira por causa desta
    consulta seria trocar um número discutível por tela nenhuma.
    """
    registros = sorted({e.registro for e in linhas if e.registro})
    if not registros or len(registros) > _MAX_NA_CONTAGEM:
        return
    marcas = ", ".join("?" for _ in registros)
    try:
        achado = capa_db._consultar(
            _SQL_FRACOES_DO_CURSO.format(marcas), *registros)
    except capa_db.FalhaDeLeitura:
        _LOG.warning("Não consegui recontar as frações dos pacientes da lista")
        return
    por_curso = {}
    for pid, curso, plano, dia in achado:
        dias = por_curso.setdefault((capa_db._txt(pid), int(curso or 0)), {})
        conta = dias.setdefault(capa_db._txt(dia), {})
        conta[plano] = conta.get(plano, 0) + 1
    for e in linhas:
        dias = por_curso.get((e.registro, e.curso_id))
        if dias:
            e.entregues = somar_por_dia(dias)


# A FREQUÊNCIA prescrita de cada curso da lista — "Dias Alternados", "Uma Vez
# por Dia". É o ritmo que transforma "faltam N" em data (ver ``prever_fim``).
#
# É a mesma fonte da capa (``capa_db._SQL_PRESCRICOES`` + ``_SQL_FREQUENCIA``),
# refeita aqui como UMA consulta para a lista inteira. Chamar
# ``prescricoes_do_paciente`` num laço custaria três consultas POR PACIENTE —
# vinte e cinco pacientes, setenta e cinco idas ao servidor, na thread da
# interface.
#
# Casa por ``DimCourseID``, e não pelo nome do curso: o número é o que a linha
# da lista já tem na mão, e nome de curso é texto digitado.
_SQL_FREQUENCIA_DOS_CURSOS = """
SELECT DISTINCT pac.PatientId, f.DimCourseID, pp.PropertyValue
  FROM (SELECT DISTINCT DimPrescriptionID, DimPatientID, DimCourseID
          FROM DWH.FactPatientPrescription) f
  JOIN DWH.DimPrescription rx ON rx.DimPrescriptionID = f.DimPrescriptionID
  JOIN DWH.DimPatient pac ON pac.DimPatientID = f.DimPatientID
  JOIN DWH.DimPrescriptionProperty pp
    ON pp.ctrPrescriptionSer = rx.ctrPrescriptionSer
   AND pp.PropertyType = 7 AND pp.PropertyValue <> 'NA'
 WHERE pac.PatientId IN ({})
   AND rx.Status <> 'NA'
   AND rx.ApprovedOn IS NOT NULL AND rx.ApprovedOn < '99990101'
 ORDER BY pac.PatientId, f.DimCourseID, pp.PropertyValue
"""


def _marcar_frequencia(linhas: list) -> None:
    """Preenche ``frequencia`` de cada linha, no lugar.

    Falha em silêncio como as outras auxiliares: sem ela toda linha conta como
    diária, que é exatamente o comportamento de antes desta consulta existir.
    """
    registros = sorted({e.registro for e in linhas if e.registro})
    if not registros or len(registros) > _MAX_NA_CONTAGEM:
        return
    marcas = ", ".join("?" for _ in registros)
    try:
        achado = capa_db._consultar(
            _SQL_FREQUENCIA_DOS_CURSOS.format(marcas), *registros)
    except capa_db.FalhaDeLeitura:
        _LOG.warning("Não consegui ler a frequência dos cursos da lista")
        return
    # UM curso pode ter mais de uma prescrição aprovada com frequências
    # diferentes (mama diária + boost em dias alternados é o caso do serviço).
    # O dict direto ficava com a ÚLTIMA linha que o banco mandasse — e sem
    # ``ORDER BY`` essa ordem não é estável: o mesmo paciente pulava de faixa
    # ("EM CURSO" ↔ "TERMINAM ESTA SEMANA") entre dois refreshes, sem nada ter
    # mudado no tratamento.
    por_curso: dict = {}
    for pid, curso, valor in achado:
        chave = (capa_db._txt(pid), int(curso or 0))
        por_curso.setdefault(chave, set()).add(
            capa_dados.traduzir_frequencia(capa_db._txt(valor)))
    freq = {}
    for chave, valores in por_curso.items():
        # A DIÁRIA ganha: quem tem um plano diário deita na mesa todo dia
        # útil. Sem nenhuma diária, o menor em ordem alfabética — arbitrário,
        # mas o mesmo em toda leitura, que é o que faltava.
        diarias = sorted(v for v in valores if v in _FREQUENCIAS_DIARIAS)
        freq[chave] = diarias[0] if diarias else sorted(valores)[0]
    for e in linhas:
        e.frequencia = freq.get((e.registro, e.curso_id), "")


# Quantos cursos cada paciente da lista já teve. Consulta SEPARADA, e não uma
# subconsulta correlacionada dentro da lista: correlacionada, ela varreria a
# ``FactTreatmentHistory`` (2,7 milhões de linhas) uma vez POR PACIENTE, e o
# tempo desta tela ainda nem foi medido. Aqui é uma varredura só, restrita aos
# vinte e poucos registros que já estão na tela.
_SQL_CONTAR_CURSOS = """
SELECT p.PatientId, COUNT(DISTINCT th.DimCourseID)
  FROM DWH.FactTreatmentHistory th
  JOIN DWH.DimPatient p ON p.DimPatientID = th.DimPatientID
 WHERE p.PatientId IN ({})
   AND th.TreatmentStartTime IS NOT NULL
   AND th.FractionNumber > 0
 GROUP BY p.PatientId
"""

# Teto de registros por consulta. O SQL Server aceita muitos parâmetros, mas um
# IN gigante é plano de execução ruim; acima disto a contagem simplesmente não
# é feita, e a tela deixa a coluna vazia em vez de travar.
_MAX_NA_CONTAGEM = 400


def _contar_cursos(linhas: list) -> None:
    """Preenche ``cursos_total`` de cada linha, no lugar.

    Falha silenciosa de propósito: sem a contagem a lista continua inteira e
    útil, e um erro aqui não pode custar o painel — este dado é contexto, não a
    razão de a tela existir.
    """
    registros = sorted({e.registro for e in linhas if e.registro})
    if not registros or len(registros) > _MAX_NA_CONTAGEM:
        return
    marcas = ", ".join("?" for _ in registros)
    try:
        # A chave passa pelo MESMO ``_txt`` que montou ``e.registro`` (linha da
        # lista): o ``PatientId`` é ``char`` no DW e volta com espaços à direita
        # em algumas linhas. Comparando o cru com o aparado, o ``get`` abaixo
        # errava TODAS as linhas de uma vez e a coluna sumia inteira — sem erro
        # nenhum, que é como um dado silencioso vira "o banco não tem isso".
        achado = {capa_db._txt(pid): n for pid, n in capa_db._consultar(
            _SQL_CONTAR_CURSOS.format(marcas), *registros)}
    except capa_db.FalhaDeLeitura:
        _LOG.warning("Não consegui contar os cursos dos pacientes da lista")
        return
    for e in linhas:
        e.cursos_total = int(achado.get(e.registro) or 0)


# O resumo do MÊS, por máquina — pedido do usuário em 25/09/2026, para a
# Agenda: "adicione o acumulado de número de pacientes tratados no mês, e o
# número de sessões executadas", depois "adicione também idade média dos
# pacientes". A contagem de PACIENTES saiu daqui em 25/09/2026 — pedido do
# mesmo dia: "para saber o número de pacientes tratados é só pegar o
# número distinto de pacientes agendados na máquina no período... só
# isso" — e foi para ``agenda_db.pacientes_do_mes_por_maquina``, pela agenda
# (``DimActivityTransaction``/``ctrResourceSer``), que também ganhou
# ``inicios`` no mesmo pedido. Esta consulta agora só soma SESSÕES e tira a
# MÉDIA DE IDADE, que continuam vindo do que de fato foi tratado
# (``FactTreatmentHistory``).
#
# O NOME da máquina, em ``DimMachine``, NÃO é sempre ``MachineId`` puro — o
# mesmo problema que ``capa_db._SQL_MAQUINA_DO_CURSO``/``_SQL_MAQUINA`` já
# documentam e resolvem com ``capa_db.SQL_NOME_MAQUINA`` (o fragmento ÚNICO,
# reaproveitado aqui em vez de colado de novo): várias linhas de
# ``DimMachine`` têm ``MachineId = 'NA'``, e o nome de verdade só está em
# ``MachineAliasName`` ou ``MachineFullName``. Filtrar só por
# ``m.MachineId`` (a primeira versão desta consulta, 25/09/2026) perdia a
# maioria das sessões — achado pelo usuário vendo a tela real: "20 tratados
# no mês, com 44 pacientes na máquina [num dia só]?", impossível.
#
# TRÊS níveis de subconsulta — achado também em 25/09/2026, antes deste:
# "70 frações/paciente? isso não é radioterapia certo?" (cursos de verdade
# vão de 5 a 40 frações, não 70). ``PrimaryFlag = 1`` e ``FractionNumber > 0``
# (o par que ``_SQL_EM_TRATAMENTO``/``_SQL_RESUMO`` usam) NÃO bastam aqui:
# eles tiram os RefPoints extras de uma mesma linha, mas a tabela ainda tem
# uma linha por CAMPO — dois ou mais campos na MESMA fração, cada um com seu
# próprio RefPoint primário, continuam contando como duas sessões. O
# comentário sobre isso perto de ``_SQL_EM_TRATAMENTO`` já avisava: "o certo
# era ``COUNT(DISTINCT FractionNumber)``" — só que aqui, por MÁQUINA e não
# por curso já conhecido, tem de ser por (paciente, curso, fração), porque o
# número da fração RECOMEÇA a cada curso e um paciente com dois cursos no
# mês colidiria fração 1 com fração 1.
#
#   x: uma linha por (máquina, paciente, CURSO, DIA) — a SESSÃO de
#      verdade, sem repetir por causa dos campos (por dia e não por fração:
#      ver o comentário logo depois da consulta).
#   y: uma linha por (máquina, paciente) — quantas sessões (``x`` contadas)
#      e a idade, prontas para a média não pesar por quem tratou mais.
#   fora: soma/conta entre PACIENTES da máquina.
#
# A idade é ``DATEDIFF(YEAR, …)`` corrigido pelo aniversário ainda não
# chegado neste ano — a conta exata de idade em SQL Server, contra
# ``GETDATE()`` (a idade de HOJE, não do dia em cena na Agenda: envelhecer
# não depende de qual mês se está olhando).
#
# O vínculo de médico — pedido do usuário em 25/09/2026: "os valores devem
# ser atualizados a depender do filtro de tempo e de médico" — é o
# ``{filtro_medico}`` OPCIONAL injetado no fim do WHERE de ``x`` (vazio sem
# médico escolhido): ``EXISTS`` contra ``DimPatientDoctor``/``DimDoctor``, o
# MESMO desenho do filtro de médico de ``agenda_db._SQL_AGENDA_DO_DIA`` — não
# um ``JOIN``, que multiplicaria a linha de quem tem mais de um médico
# vinculado e estragaria o ``COUNT(DISTINCT …)``/a média de idade. Uma query-
# base só (em vez de duas cópias quase idênticas, com/sem médico) para uma
# correção na parte comum não poder ficar só numa das duas.
#
# NÃO CONFERIDA contra o banco real por conta própria (mesma ressalva de
# :data:`EmTratamento.inicio`): ninguém abriu o ARIA para comparar estes
# números ainda — só os dois problemas óbvios (frações e máquina) é que já
# foram pegos, olhando a tela.
_FILTRO_MEDICO = """
                   AND EXISTS (SELECT 1
                                 FROM DWH.DimPatientDoctor pd
                                 JOIN DWH.DimDoctor d
                                   ON d.ctrResourceSer = pd.ctrResourceSer
                                WHERE pd.DimPatientID = th.DimPatientID
                                  AND d.DoctorFullName IN ({marcas_medico}))"""

_SQL_RESUMO_MENSAL_MAQUINA = f"""
SELECT y.MachineId,
       SUM(y.Sessoes),
       AVG(y.Idade)
  FROM (SELECT x.MachineId, x.DimPatientID,
               COUNT(*) AS Sessoes,
               DATEDIFF(YEAR, x.PatientDateOfBirth, GETDATE())
                 - CASE WHEN DATEADD(YEAR,
                     DATEDIFF(YEAR, x.PatientDateOfBirth, GETDATE()),
                     x.PatientDateOfBirth) > GETDATE() THEN 1 ELSE 0 END
                 AS Idade
          FROM (SELECT DISTINCT {capa_db.SQL_NOME_MAQUINA} AS MachineId,
                       th.DimPatientID, th.DimCourseID,
                       CONVERT(char(8), th.TreatmentStartTime, 112) AS Dia,
                       p.PatientDateOfBirth
                  FROM DWH.FactTreatmentHistory th
                  JOIN DWH.DimMachine m ON m.DimMachineID = th.DimActualMachineID
                  JOIN DWH.DimPatient p ON p.DimPatientID = th.DimPatientID
                 WHERE {capa_db.SQL_NOME_MAQUINA}
                         IN ({{marcas_maquina}})
                   AND th.TreatmentStartTime >= ? AND th.TreatmentStartTime < ?
                   AND th.FractionNumber > 0
                   AND th.PrimaryFlag = 1
                   AND ISNULL(p.IsMOTestPatient, 0) = 0{{filtro_medico}}) x
         GROUP BY x.MachineId, x.DimPatientID, x.PatientDateOfBirth) y
 GROUP BY y.MachineId
"""
# A sessão, em ``x``, é o DIA de tratamento (``CONVERT(..., 112)``, mesmo
# formato de :data:`_SQL_FRACOES_DO_CURSO`), e não o ``FractionNumber``: a
# numeração da fração RECOMEÇA a cada replanejamento, e a paciente de
# 21/08/2026 (13 frações num plano, 1 e 1 nos dois novos) contava 13 sessões
# em vez de 15 — as frações 1 dos planos novos colidiam com a fração 1 do
# velho. Por dia também funde planos SIMULTÂNEOS (mama + FSC na mesma
# sessão), a mesma conta de :func:`somar_por_dia`.

# Frações PREVISTAS médias — pedido do usuário em 25/09/2026, depois de ver
# "7,7 frações/paciente" no 6EX: "esse fracoes/paciente ta correto? o
# numero de fracoes no 6ex costuma ser maior". A conta de antes (sessões
# ENTREGUES este mês ÷ pacientes AGENDADOS este mês) ficava baixa no meio
# do mês, porque o denominador conta quem ainda vai tratar em setembro e o
# numerador só tem o que já aconteceu até hoje. O CONCEITO CERTO, do
# usuário: não quantas frações já saíram este mês, mas quanto CADA CURSO
# prevê ao todo — "o numero medio de fracoes eh importante pra ver
# ocupacao da maquina": um curso de 30 frações ocupa a máquina por muito
# mais tempo que um SBRT de 5, e é isso que o número deve mostrar.
#
# Por paciente, não por curso (quem tem dois cursos na máquina no mês não
# pode entrar duas vezes na média) — o curso DOMINANTE (mais sessões
# ENTREGUES este mês nesta máquina) representa o paciente, via
# ``ROW_NUMBER() OVER (PARTITION BY … ORDER BY SessoesCurso DESC)``. E, DE
# PROPÓSITO, diferente de ``_SQL_DOSE_POR_PLANO`` (onde ``MAX``, nunca
# ``SUM``, porque dois planos concorrentes tratam ALVOS diferentes e dose a
# alvos diferentes não se soma): aqui as frações de planos DIFERENTES do
# MESMO curso SOMAM — pedido explícito do usuário, "se tiver multiplas
# prescricoes num curso todas devem ser consideradas". ``planos`` isola
# cada ``DimPlanID`` com ``MAX(FractionsPlanned)`` (o mesmo cuidado de
# ``_SQL_DOSE_POR_PLANO``: uma linha por PLANO, não por fração), e
# ``cursos`` soma os planos do mesmo curso.
#
# Duas leituras SEPARADAS da mesma janela (``sess``/``cur``, cada uma com
# seu próprio filtro de máquina/data/médico) porque pedem NÍVEIS de
# agrupamento diferentes — sessão conta fração DISTINTA sem se importar com
# o plano, previsão soma por PLANO antes de somar por curso — e juntar os
# dois níveis numa passada só embaralharia (``SUM`` sobre fração repetida
# por plano concorrente dobraria a previsão).
#
# ``FractionsPlanned > 0`` (mesmo filtro de ``_SQL_RESUMO``/
# ``_SQL_DOSE_POR_PLANO``) só no lado ``cur``: cursos sem plano de fração
# cadastrado somem da MÉDIA (não contam como previsto zero), mas ainda
# podem "vencer" a disputa de curso dominante do lado ``sess`` — nesse caso
# o paciente inteiro fica de fora da média (nenhum curso dele tem previsão
# utilizável), o mesmo "nunca um número inventado" de sempre.
#
# NÃO CONFERIDA contra o banco real (mesma ressalva de
# ``_SQL_RESUMO_MENSAL_MAQUINA``, logo acima) — em particular, a soma por
# MÚLTIPLAS prescrições/planos do mesmo curso é a interpretação que o
# usuário descreveu, não algo visto num curso real de dois planos ainda.
# Mesmo ``{filtro_medico}`` OPCIONAL de ``_SQL_RESUMO_MENSAL_MAQUINA``,
# repetido nos DOIS lados (``sess``/``cur``): filtrar só um lado deixaria os
# dois fora de sincronia e o ``JOIN`` perderia cursos que deveriam bater.
_SQL_FRACOES_PREVISTAS_MAQUINA = f"""
SELECT dom.MachineId, AVG(CAST(dom.PrevistasCurso AS float))
  FROM (SELECT sess.MachineId, sess.DimPatientID, cur.PrevistasCurso,
               ROW_NUMBER() OVER (PARTITION BY sess.MachineId, sess.DimPatientID
                                   ORDER BY sess.SessoesCurso DESC) AS Rn
          FROM (SELECT x.MachineId, x.DimPatientID, x.DimCourseID,
                       COUNT(DISTINCT x.FractionNumber) AS SessoesCurso
                  FROM (SELECT DISTINCT {capa_db.SQL_NOME_MAQUINA} AS MachineId,
                               th.DimPatientID, th.DimCourseID, th.FractionNumber
                          FROM DWH.FactTreatmentHistory th
                          JOIN DWH.DimMachine m ON m.DimMachineID = th.DimActualMachineID
                          JOIN DWH.DimPatient p ON p.DimPatientID = th.DimPatientID
                         WHERE {capa_db.SQL_NOME_MAQUINA}
                                 IN ({{marcas_maquina}})
                           AND th.TreatmentStartTime >= ? AND th.TreatmentStartTime < ?
                           AND th.FractionNumber > 0
                           AND th.PrimaryFlag = 1
                           AND ISNULL(p.IsMOTestPatient, 0) = 0{{filtro_medico}}) x
                 GROUP BY x.MachineId, x.DimPatientID, x.DimCourseID) sess
          JOIN (SELECT planos.MachineId, planos.DimPatientID, planos.DimCourseID,
                       SUM(planos.PrevistasPlano) AS PrevistasCurso
                  FROM (SELECT x2.MachineId, x2.DimPatientID, x2.DimCourseID,
                               x2.DimPlanID, MAX(x2.FractionsPlanned) AS PrevistasPlano
                          FROM (SELECT DISTINCT {capa_db.SQL_NOME_MAQUINA} AS MachineId,
                                       th.DimPatientID, th.DimCourseID, th.DimPlanID,
                                       th.FractionsPlanned
                                  FROM DWH.FactTreatmentHistory th
                                  JOIN DWH.DimMachine m ON m.DimMachineID = th.DimActualMachineID
                                  JOIN DWH.DimPatient p ON p.DimPatientID = th.DimPatientID
                                 WHERE {capa_db.SQL_NOME_MAQUINA}
                                         IN ({{marcas_maquina}})
                                   AND th.TreatmentStartTime >= ? AND th.TreatmentStartTime < ?
                                   AND th.FractionNumber > 0
                                   AND th.PrimaryFlag = 1
                                   AND th.FractionsPlanned > 0
                                   AND ISNULL(p.IsMOTestPatient, 0) = 0{{filtro_medico}}) x2
                         GROUP BY x2.MachineId, x2.DimPatientID, x2.DimCourseID,
                                  x2.DimPlanID) planos
                 GROUP BY planos.MachineId, planos.DimPatientID,
                          planos.DimCourseID) cur
            ON cur.MachineId = sess.MachineId
               AND cur.DimPatientID = sess.DimPatientID
               AND cur.DimCourseID = sess.DimCourseID) dom
 WHERE dom.Rn = 1
 GROUP BY dom.MachineId
"""


def resumo_mensal_por_maquina(machine_ids: list, referencia: date,
                              medicos_alvo: list = ()) -> dict:
    """``{MachineId: (sessoes, idade_media, fracoes_previstas_media)}`` do
    MÊS de ``referencia`` (do dia 1 ao último, pelo calendário do mês de
    ``referencia`` — não uma janela de 30 dias corridos). ``idade_media`` e
    ``fracoes_previstas_media`` são ``float | None`` — ``None`` quando
    ninguém do grupo tem, respectivamente, data de nascimento ou
    ``FractionsPlanned`` cadastrado (``AVG`` de zero linhas é ``NULL``).

    ``fracoes_previstas_media``: a média de quanto o CURSO INTEIRO de cada
    paciente prevê — SOMANDO as prescrições/planos do curso, quando houver
    mais de uma — não quanto já foi entregue este mês; serve para medir
    ocupação da máquina (ver o comentário de
    :data:`_SQL_FRACOES_PREVISTAS_MAQUINA`). Por paciente com mais de um
    CURSO na máquina no mês (não confundir com mais de um PLANO do mesmo
    curso, que soma), conta o curso DOMINANTE (mais sessões entregues este
    mês), não os dois.

    Os PACIENTES distintos (e os INÍCIOS) não vêm mais daqui — ver
    ``agenda_db.pacientes_do_mes_por_maquina``.

    ``machine_ids``: os ``MachineId`` crus (``agenda_db.Maquina.machine_id``,
    não o nome de exibição). ``medicos_alvo``: nomes BRUTOS, vazio = todos os
    pacientes da máquina (o padrão) — com médico(s), só quem está vinculado a
    algum deles entra na conta. Devolve ``{}`` quando ``machine_ids`` vier
    vazio, quando o resumo não estiver liberado (:func:`lista_disponivel` —
    mesmo portão experimental do resto do que ainda não foi conferido contra
    o banco real, ver o "NÃO CONFERIDA" acima) ou quando a consulta principal
    falhar — nunca um número inventado. Se só a consulta de previsão falhar,
    ``sessoes``/``idade_media`` ainda voltam, com
    ``fracoes_previstas_media=None`` — ela é bônus, não pode derrubar o
    resto do resumo.
    """
    if not machine_ids or not lista_disponivel():
        return {}
    inicio_mes, fim_mes = capa_dados.limites_do_mes(referencia)
    marcas_maquina = ", ".join("?" for _ in machine_ids)
    datas = (inicio_mes.strftime("%Y-%m-%d"), fim_mes.strftime("%Y-%m-%d"))
    nomes_medico = [n for n in (medicos_alvo or []) if n]
    if nomes_medico:
        marcas_medico = ", ".join("?" for _ in nomes_medico)
        filtro_medico = _FILTRO_MEDICO.format(marcas_medico=marcas_medico)
        parametros_medico = tuple(nomes_medico)
    else:
        filtro_medico = ""
        parametros_medico = ()
    sql = _SQL_RESUMO_MENSAL_MAQUINA.format(
        marcas_maquina=marcas_maquina, filtro_medico=filtro_medico)
    parametros = (*machine_ids, *datas, *parametros_medico)
    sql_previstas = _SQL_FRACOES_PREVISTAS_MAQUINA.format(
        marcas_maquina=marcas_maquina, filtro_medico=filtro_medico)
    parametros_previstas = (*machine_ids, *datas, *parametros_medico,
                            *machine_ids, *datas, *parametros_medico)
    try:
        linhas = capa_db._consultar(sql, *parametros)
    except capa_db.FalhaDeLeitura:
        return {}
    try:
        linhas_previstas = capa_db._consultar(sql_previstas, *parametros_previstas)
    except capa_db.FalhaDeLeitura:
        _LOG.warning("Não consegui calcular a média de frações previstas")
        linhas_previstas = []
    previstas = {capa_db._txt(mid): float(media)
                for mid, media in linhas_previstas if media is not None}
    return {capa_db._txt(mid): (int(ses or 0),
                                float(idade) if idade is not None else None,
                                previstas.get(capa_db._txt(mid)))
           for mid, ses, idade in linhas}


def cursos_do_paciente(registro: str) -> list:
    """Todos os cursos com tratamento aplicado, do mais recente para trás.

    O primeiro é o ATUAL — "atual" aqui é "o que tem a sessão mais recente",
    não "o que está aberto no ARIA": um curso pode estar aberto e sem nenhuma
    fração, e um curso desses no topo da tela esconderia o que o paciente está
    de fato recebendo.
    """
    if not disponivel():
        return []
    try:
        linhas = capa_db._consultar(_SQL_CURSOS, str(registro or "").strip())
    except capa_db.FalhaDeLeitura:
        return []
    fora = []
    for i, (cid, nome, entregues, previstas, ini, fim) in enumerate(linhas):
        fora.append(Curso(
            id=int(cid or 0),
            nome=capa_db._txt(nome),
            entregues=int(entregues or 0),
            previstas=int(previstas or 0),
            inicio=ini.date() if hasattr(ini, "date") else None,
            fim=fim.date() if hasattr(fim, "date") else None,
            atual=(i == 0),
        ))
    return fora


# ── Quem tratou: o que o banco assina vira o nome da pessoa ─────────────────
# Trocar ponto por espaço acertava a APARÊNCIA e errava a PESSOA:
# "washington.drangel" saía "Washington Drangel" (é Washington de Souza Rocha),
# "vanessa.dias" saía "Vanessa Dias" (é Vanessa Carneiro Marques) e
# "waleska.santos" saía "Waleska Santos" (é Waleska de Sousa Medeiros — e há
# uma Vanessa e uma Waleska no mesmo turno). Sobrenome trocado na coluna de quem
# tratou é atribuir a sessão a outra pessoa: é o erro que esta tela existe para
# não cometer.
#
# DUAS FONTES, e foi a segunda que explicou a mistura vista no banco
# ("wagner.sousa" e "elaine.costa" ao lado de "Rangel", "Soares", "Santos"):
#
#   * **ARIA**, Administração → Usuários, grupo Therapist (cópia de 20/08/2026):
#     os logins de rede, com o nome inteiro de cada pessoa.
#   * **4D Console Administration** da máquina, Gerenciamento de usuários (foto
#     de 20/08/2026): as contas com que se entra no console — e são elas que
#     assinam. Ali convivem as contas antigas, feitas à mão, com ID curto
#     ("michele") e SOBRENOME de gente ("Soares"), e as "Criado por TreatApp",
#     sincronizadas do ARIA, cujo sobrenome é o próprio login.
#
# É o que decifra o "Rangel" do banco: não existe login "Rangel" em lugar
# nenhum — é o sobrenome cadastrado de ``milton``. Ou seja, o que o DW grava é o
# SOBRENOME do console. Por isso cada pessoa lista TODAS as chaves com que pode
# aparecer (ID curto, login do ARIA, ID colado, sobrenome): custa uma linha e não
# depende dessa leitura estar certa.
#
# A grafia é a do cadastro, COPIADA e não reformatada: "RPA103" e "Clinica
# Física" não são nomes de gente e qualquer normalização os estraga ("Rpa103").
#
# Chave que não estiver aqui — contratação nova, conta de outra unidade — cai na
# heurística de sempre. A tabela serve para acertar o nome, nunca para calar quem
# falta nela: sessão sem nome é pior que sessão com o login cru.
_CONTAS = (
    # ── Radioterapeutas, com o nome inteiro do ARIA ─────────────────────────
    ("Amanda Fernandes Dias", ("amanda", "amanda.dias")),
    ("Cintia Lisboa Cabral", ("cintia.cabral",)),
    ("Debora Teles de Gouveia", ("debora", "debora.gouveia", "teles")),
    # "Camargo" é dele: a ``josiane`` divide o sobrenome no console do 600CD,
    # mas tem o Nome preenchido e chega como "Camargo Josiane Fernandes".
    ("Diego José Camargo Costa", ("diego", "diego.costa", "camargo")),
    ("Elaine Luiza dos Soares", ("elaine", "elaine.costa", "costa")),
    ("Fabiana Maria Dos Santos", ("fabiana.dsantos",)),
    # TRÊS contas da MESMA pessoa: ``gisele`` (console, "Gisele Kelly silva"),
    # ``gisele.silva`` e ``gisele.silveira`` — os dois últimos são a mesma
    # pessoa, dito pelo usuário em 20/08/2026. Sem as três aqui, a mesma
    # radioterapeuta apareceria com dois ou três nomes na lista de quem tratou o
    # paciente, e o serviço leria isso como gente diferente.
    ("Gisele Kelly Pinheiro Silva",
     ("gisele", "gisele.silva", "gisele.silveira", "pinheiro")),
    # "Lucia" é o sobrenome dela no console do 600CD; no do 6EX é "Silva", e o
    # "Silva" NU é dela pelo mesmo motivo do "Soares" da Michele: a conta
    # ``ivone`` tem o Nome vazio, e a ``gisele``, que divide o sobrenome lá,
    # chega como "silva Gisele Kelly".
    ("Ivone Lúcia da Silva", ("ivone", "ivone.silva", "lucia", "silva")),
    ("Jonas Souza Santos", ("jonas.santos", "jonas.souza", "santos")),
    ("Josiane Fernandes Camargo",
     ("josiane", "josiane.camargo", "ju.camargo", "fernandes camargo")),
    ("Kelvin Cordova Gonçalves Barreto", ("kelvin.barreto",)),
    ("Leandro Carvalhal dos Santos", ("leandro", "leandro.carvalhal", "carvalhal")),
    ("Mauricio Henrique Soares", ("mauricio", "mauricio.soares", "henrique")),
    # "Soares" NU é ela — dito pelo usuário em 20/08/2026, e o cadastro explica
    # por quê: a conta ``michele`` tem o campo Nome VAZIO nos dois consoles, então
    # o banco só tem o sobrenome para gravar. O Mauricio, que divide o sobrenome,
    # tem "Mauricio" no Nome e chega como "Soares Mauricio".
    ("Michele Soares", ("michele", "michele.soares", "michelesoares", "soares")),
    ("Reinaldo Nunes Alves", ("reinaldo.alves",)),
    # "Souza" SAIU: no 600CD é o sobrenome da ``waleska`` também, e as duas
    # contas com esse sobrenome têm o Nome vazio. A dela vem "Souza Renata
    # Carneiro de" quando é a conta do 600CD, e aí o "renata" desempata.
    ("Renata Carneiro de Souza", ("renata", "renata.souza")),
    ("Ronaldo Castilho", ("ronaldo.castilho", "ronaldocastilho", "castilho")),
    ("Tatiane da Costa Ferraz", ("tatiane.ferraz",)),
    ("Vanessa Carneiro Marques",
     ("vanessa", "vanessa.dias", "vanessacarneiro", "carneiro")),
    ("Washington de Souza Rocha", ("washington.drangel",)),
    ("Wagner Cesar de Sousa", ("wagner", "wagner.sousa", "wagnercesar")),
    ("Waleska de Sousa Medeiros", ("waleska", "waleska.santos", "sousa")),
    ("Yara de Sousa Frota", ("yara", "yara.frota", "frota")),

    # ── Console do 600CD: gente que só aparece lá ───────────────────────────
    # Nome do próprio cadastro (Nome + Nome do meio + Sobrenome), que nesse
    # console está preenchido em quase todas as contas antigas.
    ("Arthur Crispim", ("arthur", "arthur.nascimento", "crispim")),
    ("Bianca Campelo", ("bianca", "bianca.campelo", "campelo")),
    ("Edson Neto", ("edsonneto",)),
    ("Fatima Batista", ("fatima", "fatima.batista", "batista")),
    ("Jaqueline Martins", ("jaque", "jaquemartins", "martins")),
    ("Jussara de Sousa Pereira", ("jussara", "pereira")),
    ("Moacir Colombo", ("moacircolombo",)),
    # O sobrenome muda de conta para conta ("Vieira" em ``roque``,
    # "Fernandes" em ``roque.fernand``), e o console não diz o nome inteiro.
    # "Fernandes" ficou FORA de propósito, apesar de ser o sobrenome da conta
    # ``roque.fernand``: é o Nome do meio da Josiane no 600CD, e casá-lo
    # daria a sessão dela para ele.
    ("Roque Vieira",
     ("roque", "roque.fernand", "rei.fernandes", "vieira")),
    ("Sandra Sarmento", ("sandra", "sarmento")),

    # ── Contas do console que o ARIA não nomeia ─────────────────────────────
    # Nome CURTO, e de propósito: a lista de therapists do ARIA não traz estas
    # pessoas, então o nome inteiro não tem fonte. O que está aqui é o que o
    # console mostra — o ID e o sobrenome do mesmo cadastro, só separados. Vale
    # completar quando alguém abrir o cadastro delas.
    # ``milton``, ``miltonrangel`` e ``milton.fernandes`` são a MESMA pessoa
    # (dito pelo usuário em 20/08/2026) — o console tem "Rangel" no sobrenome e
    # o ARIA, "fernandes" no login, o que sugere um nome inteiro maior que este.
    ("Milton Rangel",
     ("milton", "miltonrangel", "rangel", "milton.fernandes")),
    ("Plinio Coelho", ("pliniocoelho", "plinio.coelho")),
    ("Rita Melo", ("ritamelo", "rita.melo")),
    ("Tereza Soares", ("tereza.soares", "terezasoares")),
    ("Telma Almeida", ("telma", "telma.almeida", "almeida")),

    # ── Físicos: a grafia canônica da equipe (``equipe.FISICOS``) ─────────
    # Eles assinam sessão — teste de máquina, controle de qualidade — e o nome
    # tem de ser o MESMO que a ficha imprime, senão a mesma pessoa aparece de
    # dois jeitos em dois documentos do mesmo paciente.
    ("Geovani Pires Pena", ("geovani", "geovani.pena", "pena")),
    ("Marcelo Assef Valadares", ("marcelo", "marcelo.valadares", "valadares")),
    ("Nathalia Bittencourt", ("nathalia", "bittencourt")),
    # ``mario``, ``mariohenrique`` e ``mario.hayashi`` são o MESMO físico
    # (dito pelo usuário em 20/08/2026). O nome é o da lista canônica, não o que
    # o login ``mario.hayashi`` sugeriria: a ficha imprime "Mario Sergio", e
    # a mesma pessoa com dois nomes em dois documentos do mesmo paciente é
    # exatamente o que esta tabela existe para evitar.
    # "Hayashi" é o sobrenome dele no console do 600CD — o que fecha a conta:
    # ``mariohenrique`` e ``mario.hayashi`` são a mesma pessoa e o nome inteiro
    # deve ser Mario Sergio Hayashi. Sai como a ficha imprime.
    ("Mario Sergio",
     ("mario", "mariohenrique", "mario.hayashi", "hayashi")),

    # ── Contas que não são gente ────────────────────────────────────────────
    ("Clinica Física", ("clinicafisica",)),
    ("RPA103", ("rpa103",)),
)

# O ÚNICO sobrenome que esta tabela não traduz — e o critério que decide isso.
#
# Duas voltas erradas antes de chegar aqui, as duas registradas porque o próximo
# leitor vai ter as mesmas ideias:
#
# 1. Contar homônimo pelo NOME COMPLETO da equipe. Deixei "Santos", "Sousa",
#    "Costa", "Camargo", "Carneiro" e "henrique" de fora porque cada um aparece
#    no nome inteiro de duas ou três pessoas — e a tela ficou mostrando "Santos"
#    e "Carneiro" solto, que foi o que o usuário viu e devolveu. O que conta é o
#    CADASTRO: "Santos" está numa conta só (``jonas.santos``), e a Fabiana ter
#    "Dos Santos" no nome não cria ambiguidade, porque conta ela não tem.
#
# 2. Contar as contas e parar aí. Duas contas com o mesmo sobrenome só disputam
#    o sobrenome NU se as DUAS tiverem o campo Nome vazio — porque o banco grava
#    sobrenome e nome juntos, e a conta que tem nome preenchido nunca chega nua.
#    "Soares" é da Michele (``michele``, Nome vazio); o Mauricio divide o sobrenome
#    mas tem "Mauricio" no Nome e chega como "Soares Mauricio". Mesma coisa em
#    "Silva" (Ivone × Gisele) e "Camargo" (Diego × Josiane). O usuário
#    confirmou a Michele em 20/08/2026; o cadastro confirma o resto.
#
# Sobra UM, e esse é ambíguo de verdade — duas contas, mesmo sobrenome, as duas
# sem nome preenchido:
#
#   "Souza" → ``renata.souza`` (console do 6EX) E ``waleska`` (do 600CD)
#
# Escolher uma seria atribuir a sessão por sorteio. Quando a Renata entra pela
# conta ``renata`` do 600CD, que tem nome, o "renata" desempata; nua, a
# sessão fica com o "Souza" que o banco mandou. A saída definitiva é no console:
# pôr o nome numa das duas contas.
SOBRENOMES_AMBIGUOS = ("souza",)

RADIOTERAPEUTAS = {chave: nome for nome, chaves in _CONTAS for chave in chaves}

# "Criado por TreatApp" é o que o console escreve no campo NOME das contas que
# ele sincronizou do ARIA — é etiqueta de sistema, não gente. E o banco entrega
# nome e sobrenome COLADOS: a sessão de 10/08/2026 chegou como
# "tatiane.ferraz Criado por TreatApp", e a tela imprimiu isso inteiro, com a
# etiqueta virando nome próprio ("Tatiane.ferraz Criado Por Treatapp"). Sai antes de
# qualquer busca.
_ETIQUETA_DO_CONSOLE = re.compile(r"criado\s+por\s+treatapp", re.IGNORECASE)


# O médico DO PACIENTE aberto. Mesmo desempate da capa
# (``capa_db._SQL_MEDICO``): ``OncologistFlag`` na frente separa o
# radio-oncologista do resto da equipe, e ``PrimaryFlag`` escolhe o titular
# quando há mais de um vínculo. Os dois documentos do mesmo paciente têm de
# nomear o MESMO médico — divergir aí manda quem confere procurar erro onde não
# há. O join por ``PatientId`` é o que muda: a capa já tem a chave interna na
# mão, aqui se entra pelo registro.
_SQL_MEDICO_DO_PACIENTE = """
SELECT TOP 1 d.DoctorFullName
  FROM DWH.DimPatientDoctor pd
  JOIN DWH.DimPatient p ON p.DimPatientID = pd.DimPatientID
  JOIN DWH.DimDoctor d ON d.ctrResourceSer = pd.ctrResourceSer
 WHERE p.PatientId = ?
 ORDER BY pd.OncologistFlag DESC, pd.PrimaryFlag DESC
"""


def identificacao_do_paciente(registro: str) -> tuple:
    """``(nascimento, convenio)`` para a faixa do topo, ou dois vazios.

    Do MESMO cadastro que a Capa lê, e não de uma consulta própria: a faixa de
    identidade dos dois documentos tem de dizer a mesma coisa sobre a mesma
    pessoa, e uma segunda fonte é uma segunda chance de divergir.

    O convênio vem cortado no " - " como na Capa — o banco traz o plano inteiro
    ("Unimed - Nacional Apartamento"), que não cabe na pílula e não distingue
    nada.
    """
    if not disponivel():
        return "", ""
    try:
        cad = capa_db.cadastro_do_paciente(registro)
    except Exception:  # noqa: BLE001 — a faixa vive sem estes campos
        _LOG.exception("Não consegui ler o cadastro de %s", registro)
        return "", ""
    if cad is None:
        return "", ""
    convenio = str(getattr(cad, "convenio", "") or "").split(" - ")[0]
    return str(getattr(cad, "nascimento", "") or ""), convenio


def prescricao_do_curso(registro: str, curso_nome: str) -> str:
    """A prescrição aprovada DESTE curso, como a capa a escreve.

    ``"Mama, esquerda: Mama + FSC E 40,05Gy@15fx · 15 frações - diária"``.

    O texto é o mesmo da capa (``capa_db.prescricoes_do_paciente``) e isso é o
    ponto: a aba mostra o que ACONTECEU, e ter ao lado o que foi PRESCRITO
    permite comparar os dois sem abrir outro documento. Dois textos diferentes
    para a mesma prescrição, em duas telas do mesmo programa, é o que faz
    duvidar das duas.

    **Casada pelo CURSO** — mas o vínculo prescrição↔curso vem VAZIO em parte
    das linhas (o ``DimCourseID`` da ``FactPatientPrescription`` é opcional, e o
    ``LEFT JOIN`` devolve curso nulo). Casando só por ele, a linha ficava vazia
    em pacientes que TÊM prescrição aprovada — foi o que o usuário viu em
    21/08/2026, e campo que some sem motivo aparente é pior que campo ausente:
    quem lê conclui que o dado não existe no sistema.

    Por isso o segundo caminho, e só ele: **prescrição única**. Com uma só
    aprovada no prontuário não há o que confundir — ela é a do curso que estiver
    na tela, porque não existe outra. Com duas ou mais e nenhuma casando, fica
    VAZIO: num retratamento, herdar a prescrição do curso antigo poria o sítio
    errado ao lado das frações certas, e sítio errado é o pior campo desta tela
    — é ele que faz quem lê acreditar que está olhando o paciente certo.
    """
    if not disponivel():
        return ""
    try:
        prescricoes = capa_db.prescricoes_do_paciente(registro)
    except Exception:  # noqa: BLE001 — o quadro vive sem a prescrição
        _LOG.exception("Não consegui ler a prescrição de %s", registro)
        return ""
    escolhida = _prescricao_escolhida(prescricoes, curso_nome)
    if escolhida is None:
        return ""
    linha = escolhida.titulo()
    freq = escolhida.linha_frequencia()
    return f"{linha}  ·  {freq}" if linha and freq else (linha or freq)


def fracionamento_prescrito(registro: str, curso_nome: str = "") -> dict:
    """O fracionamento da FICHA a partir da prescrição aprovada do paciente.

    ``{"fracionamento", "frequencia", "quantas", "escolhida"}``. O
    fracionamento era digitado à mão em toda ficha — e a prescrição já diz o
    ritmo, aprovada e assinada pelo radioterapeuta. Repetir à mão o que o
    sistema afirma é uma chance por ficha de divergir dele.

    ``escolhida`` é falso quando o paciente tem MAIS DE UMA prescrição
    aprovada e nenhuma casa com o curso: aí quem escolhe é a pessoa, pela mesma
    regra de ``_prescricao_escolhida`` — num retratamento, herdar o ritmo do
    curso antigo poria na ficha um fracionamento que ninguém prescreveu para o
    tratamento que vai começar.

    Banco fora do ar, paciente sem prescrição ou frequência sem correspondência
    na ficha devolvem ``fracionamento`` vazio, e o campo continua como estava.
    """
    vazio = {"fracionamento": "", "frequencia": "", "quantas": 0,
             "escolhida": False}
    if not disponivel():
        return vazio
    try:
        prescricoes = capa_db.prescricoes_do_paciente(registro)
    except Exception:  # noqa: BLE001 — a ficha vive sem a prescrição
        _LOG.exception("Não consegui ler a prescrição de %s", registro)
        return vazio
    escolhida = _prescricao_escolhida(prescricoes, curso_nome)
    if escolhida is None:
        return dict(vazio, quantas=len(prescricoes))
    freq = escolhida.frequencia
    return {"fracionamento": constantes.fracionamento_da_frequencia(freq),
            "frequencia": freq, "quantas": len(prescricoes), "escolhida": True}


def _prescricao_escolhida(prescricoes: list, curso_nome: str):
    """A prescrição deste curso entre as do paciente, ou ``None``.

    A ordem do SQL é por aprovação, da mais recente para trás: com mais de uma
    do mesmo curso, a que vale é a última aprovada.
    """
    alvo = str(curso_nome or "").strip().upper()
    casadas = [p for p in prescricoes
               if alvo and str(p.curso or "").strip().upper() == alvo]
    if casadas:
        return casadas[0]
    return prescricoes[0] if len(prescricoes) == 1 else None


def prescricao_e_frequencia(registro: str, curso_nome: str) -> dict:
    """``{"prescricao", "frequencia", "dose_dia"}`` — numa consulta só.

    Os três saem da MESMA prescrição, e buscá-los em três chamadas custaria
    seis idas ao servidor a mais por paciente, todas na thread da interface.
    Saem separados porque cada um ganhou cartão próprio: dentro da linha
    corrida da prescrição, a frequência e a dose por fração somem — e são elas
    que respondem "o paciente vem amanhã?" e "quanto ele leva hoje?".
    """
    vazio = {"prescricao": "", "frequencia": "", "dose_dia": ""}
    if not disponivel():
        return vazio
    try:
        prescricoes = capa_db.prescricoes_do_paciente(registro)
    except Exception:  # noqa: BLE001 — o quadro vive sem a prescrição
        _LOG.exception("Não consegui ler a prescrição de %s", registro)
        return vazio
    escolhida = _prescricao_escolhida(prescricoes, curso_nome)
    if escolhida is None:
        return vazio
    linha, freq = escolhida.titulo(), escolhida.linha_frequencia()
    texto = f"{linha}  ·  {freq}" if linha and freq else (linha or freq)
    return {"prescricao": texto, "frequencia": escolhida.frequencia,
            "dose_dia": _dose_por_fracao(escolhida)}


def _dose_por_fracao(prescricao) -> str:
    """A dose por fração PRESCRITA, em cGy, como texto.

    Com mais de um alvo (mama + boost simultâneo), os valores DIFERENTES saem
    todos, separados por " / ". Escolher um seria afirmar que o paciente recebe
    aquela dose por dia — e ele recebe as duas, em volumes diferentes. Valores
    iguais colapsam num só, porque repetir "200 / 200" não informa nada.
    """
    vistos = []
    for v in getattr(prescricao, "volumes", None) or []:
        d = str(getattr(v, "dose_frac_cgy", "") or "").strip()
        if d and d not in vistos:
            vistos.append(d)
    return " / ".join(vistos)


def medico_do_paciente(registro: str) -> str:
    """O radio-oncologista responsável, ou "" quando não deu para saber.

    Vazio é vazio: sem fonte, a faixa não mostra médico nenhum — nunca o
    último que apareceu na tela, que é o erro que uma tela de consulta pode
    cometer sem ninguém notar.
    """
    if not disponivel():
        return ""
    alvo = str(registro or "").strip()
    if not alvo:
        return ""
    try:
        linhas = capa_db._consultar(_SQL_MEDICO_DO_PACIENTE, alvo)
    except capa_db.FalhaDeLeitura:
        return ""
    if not linhas:
        return ""
    # ``DoctorFullName`` vem INVERTIDO ("Monteiro, Paula Monteiro Aragao"),
    # como o nome do paciente — 200 de 200 divergiram do CSV por isto quando a
    # capa foi comparada, e era o mesmo médico em todas.
    return capa_dados.desinverter(capa_db._txt(linhas[0][0]))


def _combinam(pedaco: str, nome: str) -> bool:
    """O ``pedaco`` do que o banco gravou pode ser desta pessoa?

    Duas maneiras de bater, e as duas são precisas:

    * o pedaço é **conta da mesma pessoa** — é o caso do físico que tem
      sobrenome diferente em cada console ("Hayashi Mario": as duas chaves
      levam a "Mario Sergio", e o nome inteiro não contém "Hayashi");
    * o pedaço é **palavra do nome inteiro** — "Soares Mauricio" é o Mauricio
      porque "Soares" está em "Mauricio Henrique Soares", ainda que o "Soares" nu
      seja da Michele.

    A comparação é por PALAVRA, e não por trecho: "silva" dentro de "silveira"
    casaria duas pessoas que a tabela separa de propósito.
    """
    if RADIOTERAPEUTAS.get(pedaco) == nome:
        return True
    return pedaco.upper() in capa_dados.normalizar_nome(nome).split()


def _quem_legivel(usuario: str) -> str:
    """``"tatiane.ferraz Criado por TreatApp"`` → ``"Tatiane da Costa Ferraz"``.

    A máquina assina com a conta do CONSOLE, e o que o banco grava é o cadastro
    dela — SOBRENOME e NOME juntos. Daí as três caras do mesmo campo, todas
    vistas neste banco: "Santos" (conta antiga, sem nome preenchido),
    "tatiane.ferraz Criado por TreatApp" (conta sincronizada, cujo sobrenome é o
    login e cujo nome é a etiqueta do console) e "silva Gisele Kelly" (conta
    antiga com o nome preenchido). Numa coluna só, isso parece dado de origens
    diferentes — e uma delas nem nome de gente é.

    A busca é pelo texto inteiro; não achando, e só quando o PRIMEIRO pedaço é
    sobrenome conhecido, pelo SEGUNDO — que é o nome, e que manda no sobrenome:
    "Soares" nu é a Michele, mas "Soares Mauricio" é o Mauricio.

    As duas amarras — primeiro pedaço conhecido, e só o segundo desempatando —
    são o que impede o sequestro nos dois sentidos: sem a primeira, "Maria
    Santos" viraria "Jonas Souza Santos" e "J. Santos" também; sem a segunda, o
    nome do MEIO decidiria, e o "Carneiro" de "Souza Renata Carneiro de" daria
    a sessão da Renata para a Vanessa.

    E os dois pedaços têm de FALAR DA MESMA PESSOA (``_combinam``). Sem essa
    terceira amarra, quem está fora da tabela e divide o sobrenome — ou o nome —
    com quem está dentro dela era atribuído a essa pessoa: "Pereira Leandro
    Andrade" saía "Leandro Carvalhal dos Santos" (o "leandro" é chave dele, o
    "pereira" é da Jussara, e o texto não é de nenhum dos dois), e "Silva
    Maria José" saía "Ivone Lúcia da Silva". Numa coluna que existe para dizer
    QUEM tratou o paciente, isso é o defeito que ela deveria impedir.

    Fora da tabela, o ponto vira espaço, e só quando o texto é claramente um
    login (sem espaço nenhum): "J. Santos" já é nome escrito e não pode virar
    "J Santos".

    O domínio some antes de tudo: a assinatura medida vem sem ele
    ("wagner.sousa"), mas uma que venha qualificada não pode escapar da tabela
    e ainda sair como "Clinica\\wagner sousa" na tela.
    """
    bruto = str(usuario or "").strip().rsplit("\\", 1)[-1]
    bruto = " ".join(_ETIQUETA_DO_CONSOLE.sub(" ", bruto).split())
    nome = RADIOTERAPEUTAS.get(bruto.lower())
    if nome:
        return nome
    pedacos = bruto.lower().split()
    if len(pedacos) > 1 and (pedacos[0] in RADIOTERAPEUTAS
                             or pedacos[0] in SOBRENOMES_AMBIGUOS):
        # O NOME manda no sobrenome, e é só o segundo pedaço que se olha. Sem
        # essa ordem, "Soares Mauricio" viraria a Michele (dona do "Soares" nu); e
        # olhar TODOS os pedaços erra pelo outro lado, porque o terceiro é o
        # nome do meio: o "Carneiro" de "Souza Renata Carneiro de" é chave da
        # Vanessa, e o "Fernandes" de "Camargo Josiane Fernandes" quase virou
        # sobrenome de outra pessoa.
        nome = RADIOTERAPEUTAS.get(pedacos[1])
        if nome and _combinam(pedacos[0], nome):
            return nome
        # O caminho inverso: o SOBRENOME é que está na tabela e o nome não —
        # "Castilho Ronaldo" ("ronaldo" sozinho não é chave de ninguém). Só vale
        # com o nome batendo, pela mesma razão de cima: sem essa conferência,
        # "Silva Maria José" e "Costa Bruno" viravam a dona do sobrenome nu.
        dono = RADIOTERAPEUTAS.get(pedacos[0])
        if dono and _combinam(pedacos[1], dono):
            return dono
    if bruto and " " not in bruto and "." in bruto:
        bruto = bruto.replace(".", " ")
    return capa_dados.como_nome_proprio(bruto)


def curso_atual(registro: str):
    """O ``DimCourseID`` do curso em andamento, ou ``None``."""
    cursos = cursos_do_paciente(registro)
    return cursos[0].id if cursos else None


def resumo_do_curso(registro: str, curso=None) -> tuple:
    """``(entregues, previstas, dose_entregue, dose_prescrita)`` do DW.

    Os quatro são colunas calculadas pelo próprio data warehouse. Preferi-las a
    recontar aqui não é preguiça: é o que faz a tela dizer o MESMO número que o
    ARIA mostra ao médico. Duas contagens que discordam por uma fração viram
    meia hora de conferência no meio do expediente.
    """
    if not disponivel():
        return (0, 0, 0.0, 0.0)
    alvo = str(registro or "").strip()
    if curso is None:
        curso = curso_atual(alvo)
    if curso is None:
        return (0, 0, 0.0, 0.0)
    try:
        linhas = capa_db._consultar(_SQL_RESUMO, alvo, curso)
    except capa_db.FalhaDeLeitura:
        return (0, 0, 0.0, 0.0)
    if not linhas:
        return (0, 0, 0.0, 0.0)
    entregues, previstas, dose_ent, dose_plan = linhas[0]
    return (int(entregues or 0), int(previstas or 0),
            float(dose_ent or 0) * _GY_PARA_CGY,
            float(dose_plan or 0) * _GY_PARA_CGY)


def tratamento_do_paciente(registro: str, previstas: int = 0,
                           prescrita_cgy: float = 0.0,
                           curso=None) -> Optional[Tratamento]:
    """O quadro completo, ou ``None`` quando não dá para saber.

    ``previstas`` e ``prescrita_cgy`` entram de fora, do PLANO (``capa_db``): o
    que se entregou só tem sentido ao lado do que se pretendia entregar.

    ``curso`` vazio = o ATUAL, que é o que a tela abre. Os anteriores existem
    para serem consultados, não para disputarem a abertura: quem abre a aba
    quer saber o que está acontecendo agora, e ter de escolher entre quatro
    cursos antes de ver isso é uma pergunta cuja resposta o programa já sabe.
    """
    if not disponivel():
        return None
    cursos = cursos_do_paciente(registro)
    if not cursos:
        return None
    escolhido = next((c for c in cursos if c.id == curso), None) or cursos[0]
    sessoes = sessoes_do_paciente(registro, escolhido.id)
    if not sessoes:
        return None
    # ENTREGUES vem da CONTAGEM DE SESSÕES, não do DW. Eu tinha decidido o
    # contrário ("o DW manda, é o mesmo número do ARIA") e estava errado: medido
    # em 20/08/2026, o paciente 9000011CEL tinha ``FractionsDelivered = 0`` com
    # 21 frações aplicadas. A coluna é calculada por função do DW e não sobrevive
    # a replanejamento. As sessões, essas, são linhas de tratamento que
    # aconteceram — e agora estão agrupadas por plano E fração, que era o outro
    # defeito.
    #
    # PREVISTAS continua vindo do DW: ``FractionsPlanned = 30`` bateu com
    # 13 já entregues nos planos antigos + 17 do plano atual. É a única fonte
    # que sabe que o replanejamento SUBSTITUI o que restava, em vez de somar.
    ent_dw, prev_dw, dose_ent, dose_plan = resumo_do_curso(registro, escolhido.id)
    grupos = planos_simultaneos(sessoes)
    atual = grupos[0] if grupos else {sessoes[0].plano}
    do_plano = [s for s in sessoes if s.plano in atual]
    return Tratamento(
        registro=str(registro or "").strip(),
        curso=escolhido,
        cursos=cursos,
        entregues=fracoes_entregues(sessoes),
        previstas=prev_dw or escolhido.previstas or int(previstas or 0),
        plano_atual=sessoes[0].plano,
        plano_nome=_nomes_do_grupo(do_plano),
        plano_entregues=fracoes_entregues(do_plano),
        # MÁXIMO, e não o do primeiro: mama e FSC declaram as mesmas 15 frações,
        # mas basta um dos dois vir com ``FractionsPlanned`` zerado para a linha
        # virar "7 de ?" num plano cujo total o banco sabe.
        plano_previstas=max([s.plano_previstas for s in do_plano] or [0]),
        juntos=len(atual),
        planos=len(grupos),
        dose_entregue_cgy=dose_ent,
        # A dose PRESCRITA vem da prescrição, não do ``CourseDosePlanned``: esse
        # devolveu 334 Gy num curso de 30 × 2 Gy (a tela mostrou "de 33400 cGy").
        # Ele soma planos e pontos de referência, e não é dose de curso nenhum.
        dose_prescrita_cgy=float(prescrita_cgy or 0) or dose_plan,
        sessoes=sessoes,
        medico=medico_do_paciente(registro),
        **prescricao_e_frequencia(registro, escolhido.nome),
        doses=doses_por_plano(registro, escolhido.id),
        **dict(zip(("nascimento", "convenio"),
                   identificacao_do_paciente(registro))),
    )
