"""A aba Ficha Virtual do lado da janela: o que ela lê do banco e do índice.

Saiu da ``JanelaPrincipal`` em 16/09/2026 (R-06, corte 3 do
``docs/PROPOSTA_GUI.md``). O ``tratamento.PainelFichaVirtual`` é a TELA; este
objeto é quem responde aos pedidos dela — buscar o paciente, montar o painel de
quem está em tratamento, o checklist, os campos da ficha já elaborada. Era o
tema mais isolado da janela (18 chamadas dentro, uma para fora), e o estado dele
é só dele: a lista de pacientes do banco, os médicos e o paciente em foco.

Composição e não mixin, pela medida de 27/08: num mixin o estado continuaria
espalhado pela janela, e entender um método pediria saber em qual arquivo mora
o atributo. Aqui o ``__init__`` abaixo é a lista inteira do que este tema guarda.

O que continua na janela, e por quê:

- ``_fechar_na_ficha_virtual``: zera também o ``_sync_recusado``, que é da
  janela (é ela quem pergunta antes de trocar o caso da bancada).
- ``_sincronizar_bancada``: o duplo clique aqui carrega DICOM na bancada, e isso
  é fluxo da janela, não leitura desta aba.

Os endereços antigos (``gui.JanelaPrincipal._tratamento_*``, ``gui._trio``…)
**não** foram mantidos: teste que empresta método da janela ou troca nome no
``gui`` continuaria "passando" sobre a peça errada, sem aviso (item 5c da
proposta).
"""
from __future__ import annotations

import logging
import zipfile
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QSettings, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication

from isocentro.interface.ajustes import ajustes
from isocentro.banco import capa_dados
from isocentro.banco import capa_db
from isocentro.banco import tratamento_db
from isocentro.dados import indice
from isocentro.dados import preferencias
from isocentro.dados import registro_json
from isocentro.dominio import constantes
from isocentro.interface import checklist
from isocentro.interface import simulacao
from isocentro.interface import ui
from isocentro.papel import ficha_pdf

_LOG = logging.getLogger(__name__)

# Os médicos do painel da Ficha Virtual, na preferência POR USUÁRIO: a lista de
# nomes BRUTOS com o principal na frente (ver ``tratamento._SeletorMedicos``).
CHAVE_MEDICOS = "medicos_do_painel"
# Onde a mesma escolha morava até 23/09/2026 — por máquina, no registro do
# Windows. A CHAVE diz "radioterapeuta" embora a aba se chame Ficha Virtual
# desde 20/08/2026: renomeá-la teria apagado, em silêncio, a escolha já gravada
# em cada estação. Continua sendo lida uma vez, para migrar (ver
# ``_medicos_lembrados``), e nunca mais escrita.
_CHAVE_QSETTINGS = "radioterapeuta/medicos"


def _qsettings_antigo() -> QSettings:
    """O ``QSettings`` da estação, de onde a escolha antiga é adotada.

    Função, e não a chamada solta, para o teste poder apontá-la a um arquivo
    ``.ini`` descartável: trocar só a CHAVE não bastaria — a suíte gravaria de
    verdade no registro do Windows de quem a roda.
    """
    return ajustes()


def para_numero(texto) -> float:
    """Texto de dose ("4005", "40,05") em número. Lixo vira 0,0.

    Os campos de dose de ``capa_dados`` são STRING — é o que a capa imprime.
    Tratá-los como número sem converter foi o que fechou o app: ``sum`` sobre
    texto levanta ``TypeError``, e exceção que escapa de um slot faz o PyQt5
    abortar o processo, sem log e sem janela de erro.
    """
    try:
        return float(str(texto or "").replace(",", ".").strip() or 0)
    except (TypeError, ValueError):
        return 0.0


def trio(rp: dict, eixos) -> list:
    """``[("G0", "98,4"), ("G270", ""), ("G90", "99,1")]`` — um trio de SSD ou
    de deslocamento, cada valor JUNTO do eixo a que pertence.

    Era um texto corrido, ``"98,4 /  / 99,1"``, com o casamento número↔eixo
    guardado no rótulo do cartão: quem conferia contava a posição na barra e a
    posição no rótulo para saber de quem era o número do meio. Devolvendo os
    pares, quem desenha (``ui.ValorTrio``) escreve o eixo em cima do valor,
    como a folha impressa faz.

    Lista VAZIA quando nenhum dos três tem valor: o trio é um dado só (as três
    posições de gantry da mesma medida), e um cartão de três traços gastaria
    espaço para dizer que a ficha não gravou nada. Com um ou dois presentes o
    trio sai assim mesmo, e a posição que falta se identifica pelo eixo.
    """
    pares = [(eixo, ficha_pdf.br(rp.get(k)) if rp.get(k) is not None else "")
             for eixo, k in eixos]
    return pares if any(v for _e, v in pares) else []


def dose_prescrita(rx) -> float:
    """A dose total prescrita, em cGy, a partir dos volumes da prescrição.

    MAX e não soma: dois alvos de 5000 e 6000 cGy não são um tratamento de
    11000 — num SIB eles são o mesmo tratamento, com dose diferente por alvo.
    Somar inventaria um total que ninguém prescreveu, e este número vira o
    denominador da dose na tela.

    É só a RESERVA de quando o DW não devolve ``CourseDosePlanned``; havendo o
    do banco, ele manda (ver ``tratamento_db.tratamento_do_paciente``).
    """
    return max((para_numero(v.dose_cgy) for v in getattr(rx, "volumes", ())),
               default=0.0)


def texto_da_nota(setup) -> str:
    """A nota de posicionamento como texto, para o ladrilho da Ficha Virtual.

    Acessórios E preparo: a montagem não é só o que se põe na mesa, é também
    bexiga cheia, reto vazio, braços acima da cabeça. Mostrar um sem o outro
    daria uma instrução pela metade — e é com o paciente já deitado que ela é
    lida.
    """
    partes = []
    acessorios = str(getattr(setup, "acessorios", "") or "").strip()
    if acessorios:
        partes.append(acessorios)
    preparo = getattr(setup, "preparo", None) or {}
    itens = [f"{campo}: {valor}" for campo, valor in preparo.items()
             if str(valor or "").strip()]
    if itens:
        partes.append("\n".join(itens))
    return "\n\n".join(partes)


def resumo_do_plano(dados: dict, rp: dict) -> list:
    """O quadro do PLANO da pág. 2, em ``[(rótulo, valor)]``.

    A MESMA ordem e os mesmos rótulos de ``ficha_pdf._tabela_plano`` — quem
    confere alterna entre a tela e o papel, e reordenar aqui obrigaria a
    procurar cada número duas vezes. Campo sem fonte sai de fora: rótulo
    com valor vazio promete um dado que a ficha não gravou.

    O ``valor`` é texto, exceto nos três trios de posição (os dois SSD e o
    deslocamento): esses saem como ``[(eixo, valor)]``, para o cartão poder
    escrever o eixo em cima do número em vez de deixar o casamento
    número↔eixo por conta de quem lê (ver ``trio``).
    """
    def cgy(valor):
        return ficha_pdf.br((valor or 0) * 100) if valor else ""
    pares = [
        ("Gating", dados.get("gating", "")),
        ("Modalidade", dados.get("gating_modalidade", "")),
        ("Posicionamento",
         constantes.rotulo_posicao(rp.get("patient_position"))),
        ("Plano", rp.get("rotulo_plano") or rp.get("nome_plano", "")),
        ("Frações", rp.get("num_fracoes")),
        ("Dose/dia (cGy)", cgy(rp.get("dose_fracao"))),
        ("Dose (cGy)", cgy(rp.get("dose_total"))),
        ("Fracionamento", dados.get("fracionamento", "")),
        # Os três trios com a UNIDADE no rótulo e os eixos ao lado dos
        # números (``ui.ValorTrio``), como o cabeçalho agrupado do papel —
        # é dele que saem "SSD TP0 (cm)" e a ordem Lat./Long./Vert.
        ("SSD TP0 (cm)", trio(rp, [("G0", "ssd_tp0_g0"),
                                    ("G270", "ssd_tp0_g270"),
                                    ("G90", "ssd_tp0_g90")])),
        ("Deslocamento (cm)", trio(rp, [("Lat.", "desl_lat"),
                                         ("Long.", "desl_long"),
                                         ("Vert.", "desl_vert")])),
        ("SSD Iso (cm)", trio(rp, [("G0", "ssd_iso_g0"),
                                    ("G270", "ssd_iso_g270"),
                                    ("G90", "ssd_iso_g90")])),
    ]
    # Trio vazio some como qualquer campo sem fonte; o que tem valor vai
    # como LISTA de pares, e é por ela que a janela sabe desenhar o cartão
    # de três colunas em vez do de um valor só.
    resumo = []
    for rot, val in pares:
        if isinstance(val, list):
            if val:
                resumo.append((rot, val))
        elif str(val or "").strip():
            resumo.append((rot, str(val)))
    return resumo


def respiratorio_da_ficha(registro: str) -> str:
    """DIBH / gating do plano, lido da ficha elaborada. "" quando não há.

    A modalidade vem antes da técnica porque é ela que a equipe fala
    ("DIBH", "gating por fase"); a técnica crua do DICOM ("BREATH_HOLD") é
    a reserva. Sem ficha, sem resposta — e afirmar controle respiratório
    onde não há muda a montagem na mesa e o tempo reservado da máquina.
    """
    try:
        pasta = pasta_da_ficha(registro)
        reg = registro_json.registro_na_pasta(pasta) if pasta else None
        versoes = (reg or {}).get("versoes") or []
        rp = (versoes[-1].get("plano_rp") or {}) if versoes else {}
    except Exception:  # noqa: BLE001 — o quadro vive sem este campo
        _LOG.exception("Ficha Virtual: falha ao ler o gating da ficha")
        return ""
    if not rp.get("gating_plano"):
        return ""
    modal = str(rp.get("gating_modalidade", "") or "").strip()
    fase = str(rp.get("gating_fase", "") or "").strip()
    texto = modal or str(rp.get("gating_tecnica", "") or "").strip()
    return f"{texto}  {fase}".strip() if texto else "Sim"


def pasta_da_ficha(registro: str) -> str:
    """A pasta onde a ficha deste paciente foi elaborada, pelo índice.

    É de lá que saem as fotos de posicionamento quando não houve cadastro
    de simulação — elas ficam soltas na pasta do caso, ao lado da nota.
    """
    for f in indice.listar_versoes(registro):
        caminho = f.get("json_path")
        if caminho and Path(caminho).parent.is_dir():
            return str(Path(caminho).parent)
    return ""


def png_do_indice(caminho) -> Optional[bytes]:
    """Lê um PNG da ficha: solto na pasta ou DENTRO do ``ARQUIVOS_*.zip``.

    O índice guarda o endereço do arquivo SOLTO mesmo quando ele já foi
    arquivado — é a convenção do módulo (ver ``indice.sincronizar_zip``), e
    existe para a reabertura achar a pasta. Só que arquivar é o caminho
    NORMAL: o zip é criado e os soltos somem. Lendo apenas o disco, o cartão
    de cortes e DVH ficava vazio para todo paciente cuja ficha já tinha sido
    salva — que são todos, exceto os do minuto seguinte à geração. Medido
    com a paciente 9000001CEL em 21/08/2026.

    O nome do membro dentro do zip é o mesmo do arquivo solto, então o
    endereço do índice serve para os dois casos — muda só onde se procura.
    """
    if not caminho:
        return None
    try:
        p = Path(caminho)
        if p.is_file():
            return p.read_bytes()
        zips = sorted(p.parent.glob("ARQUIVOS_*.zip")) \
            if p.parent.is_dir() else []
        for z in zips:
            with zipfile.ZipFile(z) as zf:
                if p.name in zf.namelist():
                    return zf.read(p.name)
    except (OSError, zipfile.BadZipFile, KeyError):
        return None
    return None


class ControleFichaVirtual:
    """Responde aos sinais do ``PainelFichaVirtual``. A janela só o constrói e liga."""

    def __init__(self, ficha_virtual, usuario: dict | None = None):
        self.ficha_virtual = ficha_virtual
        # Quem marca o checklist: vai gravado ao lado de cada marcação.
        self._usuario = usuario or {}
        # Lista da aba Ficha Virtual — separada porque a fonte é OUTRA (só o
        # banco). ``None`` = ainda não tentei; ``[]`` = tentei e não veio nada.
        self._refs_tratamento: Optional[list] = None
        # O paciente DA VEZ: o último que qualquer tela pôs na frente, seja a
        # bancada (Ficha Total/Fichinha) ou a busca da Capa. É o que a Ficha
        # Virtual segue ao abrir — ver ``seguir_o_foco``.
        self._paciente_em_foco = ""
        # Lista de médicos do painel: lida uma vez por sessão.
        self._medicos_tratamento: Optional[list] = None

    def ao_abrir(self) -> None:
        """A lista de pacientes é a MESMA da Capa, e é lida uma vez por sessão.

        Sem reaproveitar, abrir esta aba custaria uma segunda leitura de treze
        mil nomes — e o cache já existente ficaria mentindo, porque
        ``ControleCapa.pacientes_carregados`` passaria a valer para uma tela só.
        """
        if not tratamento_db.disponivel():
            # Sem banco (ou sem mapeamento conferido) não há o que buscar: a
            # busca some e sobra o motivo, que é o que a pessoa pode resolver.
            self.ficha_virtual.limpar()
            return
        # A lista vem do BANCO, não de ``capa_dados.pacientes()``. As duas
        # parecem a mesma coisa e não são: aquela cai nos CSV quando o banco não
        # responde, e os CSV cobrem algumas centenas de pacientes contra os
        # milhares do banco. Numa tela cuja única fonte é o banco, oferecer um
        # nome vindo do CSV é oferecer um paciente cujo tratamento ela não vai
        # conseguir ler — e a pessoa culparia o paciente, não a conexão.
        #
        # Foi o que apareceu no primeiro uso: "571 pacientes" na busca, que é a
        # contagem do CSV, com o banco fora do ar sem ninguém perceber.
        if self._refs_tratamento is None:
            self.ficha_virtual.mostrar_status("Lendo a lista de pacientes…")
            QApplication.processEvents()
            try:
                # A grafia saía daqui até 25/08/2026, porque formatar na fonte
                # mudaria o que a Capa IMPRIME. Agora é o impresso que a segue:
                # ``capa_db.pacientes`` já devolve o nome canônico.
                self._refs_tratamento = list(capa_db.pacientes())
            except Exception:  # noqa: BLE001
                _LOG.exception("Ficha Virtual: falha ao listar pacientes")
                self._refs_tratamento = []
        if not self._refs_tratamento:
            self.ficha_virtual.sem_conexao()
            return
        self.ficha_virtual.definir_pacientes(self._refs_tratamento)
        self.painel()
        self.seguir_o_foco()

    def focar_paciente(self, registro: str) -> None:
        """Registra quem é o paciente DA VEZ. Vazio não apaga o anterior.

        Limpar a bancada dispara ``textChanged`` com string vazia, e tratar
        isso como "não há paciente" faria a Ficha Virtual esquecer quem está na
        Capa ao lado — carregar um caso zera os campos antes de preenchê-los, e
        nesse instante o foco viraria nada.
        """
        reg = capa_dados.normalizar_id(registro)
        if reg:
            self._paciente_em_foco = reg

    def seguir_o_foco(self) -> None:
        """Ao abrir, a aba mostra o paciente que está na frente nas OUTRAS.

        Pedido do usuário em 21/08/2026, ampliado em 22/08/2026. Quem está
        montando a ficha de alguém e vem aqui vem por causa dessa pessoa —
        digitar de novo o nome que já está na tela ao lado é trabalho que o
        programa sabe evitar.

        **Sempre**, e de QUALQUER tela — bancada, Fichinha ou a busca da Capa
        (ver ``focar_paciente``). A primeira versão seguia só a bancada e só
        quando o registro dela MUDAVA: quem escolhesse alguém aqui dentro ficava
        preso a ele, e a aba passava a mostrar um paciente enquanto as outras
        três mostravam outro. Foi o que o usuário viu na tela — a Ficha Virtual
        num paciente e o rodapé anunciando o tratamento de outro. Numa tela de
        conferência, duas identidades ao mesmo tempo é o pior defeito possível.

        A comparação é com quem está NA TELA da aba, não com o último foco
        seguido: assim voltar sem ter mudado nada não custa outra consulta ao
        banco nem desfaz o CURSO que a pessoa escolheu no seletor.

        **O caminho inverso existe desde 04/09/2026, e exige um gesto.** Este
        método é o do FOCO: ele segue, sozinho, ao abrir a aba. Trazer o caso
        para a bancada é outra coisa — ``_sincronizar_bancada``, pendurada no
        duplo clique/Enter (``paciente_confirmado``), justamente porque abre
        DICOM e pode descartar o que estiver montado. Navegar continua sendo
        leitura; confirmar é que tem esse poder.
        """
        reg = self._paciente_em_foco
        if not reg or reg == capa_dados.normalizar_id(
                self.ficha_virtual.registro_na_tela()):
            return
        ref = next((p for p in self._refs_tratamento or []
                    if capa_dados.normalizar_id(p.registro) == reg), None)
        if ref is None:
            # O paciente da vez não está no banco (TC de teste, cadastro novo).
            # Não é erro: a aba fica como estava, e a busca continua ali.
            return
        self.ficha_virtual.assumir_paciente(ref)

    def fechar(self) -> None:
        """Tira o paciente da Ficha Virtual — e do FOCO, que a repovoa.

        ``limpar()`` sozinho não fecha nada por muito tempo:
        ``_paciente_em_foco`` guarda quem é o paciente da vez, e é dele que
        ``seguir_o_foco`` remonta a aba na próxima vez que ela
        aparece. Limpar a tela sem limpar o foco faz o paciente fechado voltar
        sozinho na troca de aba — pior que não ter fechado, porque agora
        ninguém está esperando por ele.

        O foco não se apaga em ``focar_paciente``, e é de propósito: lá,
        registro vazio quer dizer "campo zerado no meio de uma carga", não "não
        há paciente". Aqui é o contrário — a intenção de fechar é explícita.

        Chamado das TRÊS portas de fechar (Fichinha, Total e Capa-Up), porque
        fechar em um lugar só não é fechar: o usuário fechou na Capa em
        31/08/2026 e encontrou o paciente inteiro na Virtual ao lado.
        """
        self._paciente_em_foco = ""
        self.ficha_virtual.limpar()

    def _medicos_lembrados(self) -> list:
        """A escolha de médicos guardada para QUEM ESTÁ LOGADO.

        Quem já usava o app antes de 23/09/2026 tem a escolha no ``QSettings``
        da estação e nenhuma preferência gravada: ela é adotada UMA vez, e a
        partir daí a pessoa a carrega para qualquer máquina. Sem esta adoção,
        a mudança apareceria como "o programa esqueceu meu grupo".

        Numa estação que várias pessoas usam, a primeira a entrar depois da
        atualização herda o que estava gravado ali — que pode ter sido escolha
        de outra pessoa. É uma reescolha, uma vez, contra perder a escolha de
        todo mundo; e só acontece enquanto restar ``QSettings`` antigo.
        """
        guardado = preferencias.ler(self._usuario, CHAVE_MEDICOS)
        if isinstance(guardado, list):
            return list(guardado)
        antigo = _qsettings_antigo().value(_CHAVE_QSETTINGS, []) or []
        antigo = [str(m) for m in antigo]
        if antigo:
            preferencias.gravar(self._usuario, CHAVE_MEDICOS, antigo)
        return antigo

    def painel(self, medicos=None) -> None:
        """Repõe o painel "em tratamento" com os médicos escolhidos.

        A escolha — o médico da caixa e, com ele, o Grupo Médico — é lembrada
        POR USUÁRIO DO APP, no ``preferencias.json`` compartilhado. Era
        ``QSettings`` até 23/09/2026, e ali ela ficava presa à máquina: o
        médico montava o grupo na sala de comando e não o encontrava no
        consultório, e duas pessoas que dividem a mesma estação dividiam a
        mesma escolha. Quais médicos alguém acompanha é preferência DA PESSOA,
        e é ela que faz login.
        """
        if not tratamento_db.lista_disponivel():
            return
        primeira = medicos is None
        if primeira:
            medicos = self._medicos_lembrados()
        else:
            preferencias.gravar(self._usuario, CHAVE_MEDICOS, list(medicos))
        self.ficha_virtual.mostrar_status("Lendo quem está em tratamento…")
        QApplication.processEvents()
        try:
            if self._medicos_tratamento is None:
                self._medicos_tratamento = tratamento_db.medicos()
            # Só na PRIMEIRA montagem, e só se ninguém escolheu antes: quem
            # desmarcou todos os médicos de propósito quer ver todos, e repor a
            # escolha padrão por cima disso desfaria a decisão da pessoa a cada
            # abertura da aba.
            if primeira and not medicos:
                padrao = tratamento_db.medico_padrao(self._medicos_tratamento)
                if padrao is not None:
                    medicos = [padrao.bruto]
            linhas = tratamento_db.em_tratamento(
                medicos,
                incluir_concluidos=self.ficha_virtual.incluir_concluidos())
        except Exception as exc:  # noqa: BLE001 — a aba avisa e segue viva
            _LOG.exception("Ficha Virtual: falha ao montar o painel")
            self.ficha_virtual.mostrar_status(
                f"Não consegui ler quem está em tratamento: {exc}", erro=True)
            return
        self.ficha_virtual.definir_medicos(self._medicos_tratamento, medicos)
        if linhas is None:
            # Falha de leitura NÃO é "ninguém em tratamento" — ver o comentário
            # em ``tratamento_db.em_tratamento``.
            self.ficha_virtual.definir_em_tratamento([], falhou=True)
            self.ficha_virtual.mostrar_status(
                "Não consegui ler quem está em tratamento — veja "
                "%USERPROFILE%\\.isocentro.log.", erro=True)
            return
        self.ficha_virtual.definir_em_tratamento(linhas)
        self.ficha_virtual.mostrar_status(
            f"{len(linhas)} em tratamento nos últimos "
            f"{tratamento_db.DIAS_DA_JANELA} dias."
            if linhas else "Ninguém em tratamento nesta janela.")

    def trocar_curso(self, registro: str, curso: int) -> None:
        """Trocar de curso na lista: relê o mesmo paciente naquele curso.

        Passa pelo mesmo caminho da busca de propósito — o curso anterior
        merece a mesma leitura completa que o atual, e duplicar o caminho aqui
        seria a chance de os dois divergirem com o tempo.
        """
        self.buscar(registro, "", curso=curso)

    def buscar(self, registro: str, nome: str, curso=None) -> None:
        """Monta o quadro do paciente escolhido na aba Ficha Virtual.

        O total de frações e a dose prescrita vêm do PLANO (``capa_db``), não do
        que foi entregue: "12" sozinho não diz nada, e é o "de 25" que transforma
        o número em resposta. Quando o plano não é legível, a tela mostra o que
        sabe (as frações entregues) e diz que o total não veio — inventar um
        denominador faria a barra de andamento afirmar um progresso que ninguém
        calculou.
        """
        previstas, prescrita = 0, 0.0
        try:
            rxs = capa_db.prescricoes_do_paciente(registro)
        except capa_db.FalhaDeLeitura:
            rxs = []
        if rxs:
            rx = rxs[0]           # a mais recente: o ORDER BY é por aprovação
            try:
                previstas = int(str(rx.fracoes).strip() or 0)
            except ValueError:
                previstas = 0
            prescrita = dose_prescrita(rx)
        # A 3×4 do banco: conferir de relance que a tela é do paciente certo
        # custa uma consulta e evita o erro mais caro desta aba, que é ler o
        # tratamento de um homônimo e não perceber.
        try:
            self.ficha_virtual.definir_foto(capa_db.foto_do_paciente(registro))
        except Exception:  # noqa: BLE001 — sem foto a aba continua servindo
            _LOG.exception("Ficha Virtual: falha ao ler a foto")
        try:
            t = tratamento_db.tratamento_do_paciente(
                registro, previstas=previstas, prescrita_cgy=prescrita,
                curso=curso)
        except Exception as exc:  # noqa: BLE001 — a aba avisa e segue viva
            _LOG.exception("Ficha Virtual: falha ao ler o tratamento")
            self.ficha_virtual.mostrar_status(
                f"Não consegui ler o tratamento de {nome}: {exc}", erro=True)
            return
        # O controle respiratório NÃO está no data warehouse: ele vem do plano
        # DICOM, e a única cópia dele que esta aba alcança é a da ficha já
        # elaborada. Posto em ``t`` antes de mostrar, porque é o quadro que o
        # desenha — e vazio continua vazio quando não há ficha.
        #
        # O ``if`` não é zelo: ``tratamento_do_paciente`` devolve ``None`` para
        # paciente sem tratamento lido, e ``mostrar`` sabe tratar isso. Sem ele,
        # escrever num ``None`` levantava AttributeError NO MEIO do slot — a
        # tela ficava como estava e o paciente recém-escolhido simplesmente não
        # abria, sem mensagem nenhuma. Relatado em 21/08/2026.
        if t is not None:
            t.respiratorio = respiratorio_da_ficha(registro)
        self.ficha_virtual.mostrar(t)
        self.imagens(registro)
        self.fotos(registro,
                               nome or self.ficha_virtual.nome_na_tela())
        self.ficha_virtual.definir_pdf(self.pdf_da_ficha(registro))
        self.checklist_cartao(registro)
        self.ficha_virtual.definir_campos(
            bool(self.versao_da_ficha(registro)))

    # ── Checklist Pré-Tratamento (o mesmo da contracapa) ─────────────────

    def checklist_cartao(self, registro: str = "") -> None:
        """Repõe o andamento no rosto do cartão.

        Chamado depois de montar o quadro e de novo a cada marcação: o cartão
        responde "este paciente já passou pela conferência?", e uma marcação
        feita na janela que não voltasse para ele deixaria a resposta velha na
        tela — justo a que alguém vai ler de relance.
        """
        registro = registro or self.ficha_virtual.registro_na_tela()
        curso = self.ficha_virtual.curso_na_tela()
        if not registro or curso is None:
            self.ficha_virtual.definir_checklist(disponivel=False)
            return
        try:
            marcas = checklist.ler(registro, curso)
        except Exception:  # noqa: BLE001 — a aba vive sem o checklist
            _LOG.exception("Ficha Virtual: falha ao ler o checklist")
            self.ficha_virtual.definir_checklist(disponivel=False)
            return
        feitos, total = checklist.andamento(marcas)
        self.ficha_virtual.definir_checklist(
            feitos, total, len(checklist.divergencias(marcas)), True)

    def abrir_checklist(self) -> None:
        """Abre a conferência do paciente e do CURSO que estão na tela."""
        registro = self.ficha_virtual.registro_na_tela()
        curso = self.ficha_virtual.curso_na_tela()
        if not registro or curso is None:
            return
        try:
            marcas = checklist.ler(registro, curso)
        except Exception as exc:  # noqa: BLE001
            _LOG.exception("Ficha Virtual: falha ao ler o checklist")
            self.ficha_virtual.mostrar_status(
                f"Não consegui ler o checklist: {exc}", erro=True)
            return
        # O título nomeia o paciente E o curso. A janela é modal e ocupa a
        # tela; sem o nome nela, quem for interrompido no meio volta sem ter
        # como conferir de quem é a lista que está marcando.
        nome = self.ficha_virtual.nome_na_tela()
        self.ficha_virtual.mostrar_checklist(
            marcas, f"Checklist Pré-Tratamento — {nome}".strip(" —"))
        # Ao FECHAR a janela: o cartão já foi atualizado a cada clique, mas a
        # janela pode ter sido fechada sem clique nenhum e o estado do disco
        # pode ter mudado noutra estação enquanto ela estava aberta.
        self.checklist_cartao(registro)

    def checklist_marcar(self, item: str, marca: str) -> None:
        """Grava UMA marcação e devolve à janela o que ficou no disco.

        A volta não é zelo: se a gravação falhar, a marca acesa na tela e
        ausente no arquivo é o pior desfecho possível para uma conferência —
        alguém confia num aval que não existe.
        """
        registro = self.ficha_virtual.registro_na_tela()
        curso = self.ficha_virtual.curso_na_tela()
        if not registro or curso is None:
            return
        usuario = (self._usuario or {}).get("usuario", "")
        try:
            marcas = checklist.marcar(registro, curso, item, marca, usuario)
        except Exception as exc:  # noqa: BLE001
            _LOG.exception("Ficha Virtual: falha ao gravar o checklist")
            self.ficha_virtual.mostrar_status(
                f"Não consegui gravar o checklist: {exc}", erro=True)
            # ``{}`` aqui APAGAVA da janela tudo o que já estava conferido —
            # e o disco continuava com as marcas, então o cartão relido logo
            # abaixo discordava da lista aberta na frente da pessoa. Falha de
            # gravação já é tratada dentro de ``checklist.marcar`` (que devolve
            # o disco); chegar aqui é falha de LEITURA, e a resposta certa é
            # reler. Se nem isso vai, a tela fica como está: o recado de erro
            # já saiu, e desfazer marcação na tela seria pior que não atualizar.
            try:
                marcas = checklist.ler(registro, curso)
            except Exception:  # noqa: BLE001
                _LOG.exception("Ficha Virtual: falha ao reler o checklist")
                return
        self.ficha_virtual.atualizar_checklist(marcas)
        self.checklist_cartao(registro)

    # ── Campos de tratamento (a pág. 2 da ficha já elaborada) ────────────

    def versao_da_ficha(self, registro: str) -> dict:
        """A ÚLTIMA versão salva da ficha deste paciente, ou ``{}``.

        Lê pelo mesmo caminho do gating (``registro_na_pasta``), que já sabe
        procurar o JSON mestre DENTRO do ``ARQUIVOS_*.zip``: arquivar é o
        caminho normal, e lendo só o arquivo solto os campos ficariam vazios
        para todo paciente cuja ficha já foi salva — que são quase todos.
        """
        try:
            pasta = pasta_da_ficha(registro)
            reg = registro_json.registro_na_pasta(pasta) if pasta else None
            versoes = (reg or {}).get("versoes") or []
            return dict(versoes[-1]) if versoes else {}
        except Exception:  # noqa: BLE001 — a aba vive sem os campos
            _LOG.exception("Ficha Virtual: falha ao ler a versão da ficha")
            return {}

    def abrir_campos(self) -> None:
        """Mostra os campos da pág. 2 — leitura, como o resto da aba."""
        registro = self.ficha_virtual.registro_na_tela()
        versao = self.versao_da_ficha(registro) if registro else {}
        rp = versao.get("plano_rp") or {}
        dados = versao.get("dados") or {}
        feixes = list(rp.get("feixes") or [])
        # As LINHAS vêm de ``ficha_pdf``: é ela que troca Tabela por Filtro nos
        # planos da Elekta. Montar a lista aqui faria a janela mostrar "Tabela"
        # numa ficha cujo papel diz "Filtro" — duas versões do mesmo campo.
        linhas = ficha_pdf.linhas_campos(rp)
        quando = str(versao.get("data") or versao.get("gerado_em") or "")[:10]
        origem = ("Da ficha elaborada"
                  + (f" em {quando}" if quando else "")
                  + (f" · versão {versao['versao']}"
                     if versao.get("versao") else ""))
        self.ficha_virtual.mostrar_campos(
            resumo_do_plano(dados, rp), feixes, linhas,
            origem if versao else "")

    def fotos(self, registro: str, nome: str = "") -> None:
        """Fotos do posicionamento — as do CADASTRO DE SIMULAÇÃO do paciente.

        Duas fontes, na ordem em que a CAPA as consulta — e por isso mesmo:
        a montagem que aparece aqui tem de ser a que está impressa na capa que
        anda grampeada com a ficha. Fonte própria seria uma segunda versão da
        mesma montagem, e duas versões divergem.

        1. o **cadastro de simulação** do paciente (``simulacao.procurar``),
           onde os setups já vêm estruturados;
        2. a **pasta do caso**, quando não há cadastro — as fotos ficam soltas
           ali, ao lado da nota ``.docx``. Foi o que apareceu na paciente
           9000001CEL (21/08/2026): fotos e nota na pasta, cadastro nenhum, e o
           cartão sumia como se ela não tivesse posicionamento registrado.

        O endereço da pasta do caso vem do índice central, que é onde esta aba
        já busca os cortes — ela não tem pasta aberta nenhuma.
        """
        try:
            pasta = simulacao.procurar(nome, registro)
            setups = capa_dados.setups_da_pasta(pasta) if pasta else []
            if not setups:
                setups = capa_dados.setups_da_pasta(
                    pasta_da_ficha(registro))
        except Exception:  # noqa: BLE001 — a aba vive sem as fotos
            _LOG.exception("Ficha Virtual: falha ao ler o posicionamento")
            self.ficha_virtual.definir_fotos()
            return
        # CADA setup vai inteiro para a aba, com o seu nome e a sua nota: são
        # eles que o seletor de posicionamento oferece. Achatar as fotos numa
        # lista só — que era como estava — misturava as montagens de quem tem
        # duas (crânio e metástase, por exemplo) e mostrava as duas primeiras
        # como se fossem da mesma.
        self.ficha_virtual.definir_fotos(
            [(s.nome, list(s.fotos or []), texto_da_nota(s))
             for s in setups if s.fotos])

    def imagens(self, registro: str) -> None:
        """Cortes e DVH da ficha JÁ ELABORADA deste paciente, se houver.

        Vêm do índice central (``indice``), que guarda o endereço dos PNG que a
        ficha gravou — esta aba não tem DICOM para recalcular nada, e o que se
        quer conferir é justamente o que foi impresso e foi para a sala.

        A versão é a MAIS RECENTE que tenha imagem: um replanejamento gera
        ficha nova, e o corte de duas versões atrás mostra um alvo que já não é
        o do tratamento em curso. A data viaja junto com as imagens, para a
        tela poder dizer de onde elas vieram.
        """
        try:
            versoes = indice.listar_versoes(registro)
            if not versoes:
                # O registro do DW e o da ficha são o mesmo RGH, mas um pode
                # ter vindo digitado: compara sem pontuação antes de desistir.
                alvo = capa_dados.normalizar_id(registro)
                versoes = [f for f in indice.buscar(registro, "registro")
                           if capa_dados.normalizar_id(
                               f.get("registro", "")) == alvo]
            cortes = dvh = None
            escolhida = None
            for f in versoes:                    # já vêm da mais recente
                cortes = png_do_indice(f.get("imagem_path"))
                dvh = png_do_indice(f.get("dvh_path"))
                if cortes or dvh:
                    escolhida = f
                    break
        except Exception:  # noqa: BLE001 — a aba vive sem as imagens
            _LOG.exception("Ficha Virtual: falha ao ler cortes/DVH do índice")
            self.ficha_virtual.definir_imagens()
            return
        origem = ""
        if escolhida:
            quando = escolhida.get("data") or escolhida.get("gerado_em") or ""
            versao = escolhida.get("versao")
            origem = ("Da ficha elaborada"
                      + (f" em {str(quando)[:10]}" if quando else "")
                      + (f" · versão {versao}" if versao else ""))
        self.ficha_virtual.definir_imagens(cortes, dvh, origem)

    def pdf_da_ficha(self, registro: str) -> str:
        """O PDF da ficha mais recente deste paciente, ou "".

        Só o que EXISTE no disco: o índice é derivado, e apontar para um
        arquivo que sumiu acenderia um botão que falha ao ser clicado.
        """
        try:
            for f in indice.listar_versoes(registro):
                caminho = f.get("pdf_path")
                if caminho and Path(caminho).is_file():
                    return str(caminho)
        except Exception:  # noqa: BLE001 — sem PDF o botão fica apagado
            _LOG.exception("Ficha Virtual: falha ao procurar o PDF da ficha")
        return ""

    def abrir_pdf(self) -> None:
        """Abre o PDF no visualizador do sistema.

        No visualizador do sistema, e não numa janela nossa: quem confere a
        ficha quer as ferramentas que já conhece — zoom, busca, impressão — e
        reimplementá-las aqui seria um leitor de PDF pior que o que a pessoa
        já tem instalado.
        """
        caminho = getattr(self.ficha_virtual, "_pdf", "")
        if not caminho:
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(caminho)):
            ui.alertar(
                self.ficha_virtual, "PDF da ficha",
                f"Não consegui abrir o PDF:\n\n{caminho}")
