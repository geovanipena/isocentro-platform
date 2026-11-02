"""O portão da geração: o que decide se a ficha pode sair, e com o quê.

Saiu da ``JanelaPrincipal`` em 16/09/2026 (R-06, corte 4 do
``docs/PROPOSTA_GUI.md``). São as perguntas feitas entre o clique e o papel —
campos obrigatórios, gating sem modalidade, plano sem TC ou sem dose, 600CD sem
portal, a conferência das pendências — e a resolução do SUS, que decide se as
folhas de Registro de Tratamento entram no maço.

**O que se decide aqui vai para o papel.** A mudança foi só de endereço: as
regras, os textos e a ordem das perguntas são os da janela, e quem a orquestra
continua sendo o ``ControleFicha.gerar_pdf``.

Lê o estado do caso NA JANELA, na hora em que precisa (``janela.caso.planos``,
``janela.form``…), e não uma cópia feita na construção: a limpeza troca o
``janela.caso`` INTEIRO (corte 6a), e um ``Caso`` guardado aqui responderia pelo
paciente anterior. Por isso o portão recebe a janela, e não o caso.

O que continua na janela, e por quê:

- ``caso.sus`` (o SUS lembrado para pré-preencher o popup): é estado do CASO — a
  limpeza o zera e a reabertura de um registro o preenche. Este portão o lê e o
  grava, mas o dono é quem troca de paciente.
- ``_escolher_ficha``, ``_atualizar_btn_pdf``, ``_motivo_sem_previa``: são peça
  de tela que CONSULTA o portão, não parte dele.

Os endereços antigos (``gui.JanelaPrincipal._coletar_sus``…) **não** foram
mantidos, pela mesma razão do corte 3: teste que empresta método da janela
continuaria "passando" sobre a peça errada, sem aviso.
"""
from __future__ import annotations

import logging

from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QLineEdit,
                             QPushButton, QRadioButton, QVBoxLayout)

from isocentro.banco import capa_dados
from isocentro.dados import cadastro_sus
from isocentro.dominio import agendamento as ag
from isocentro.dominio import constantes
from isocentro.interface import estilo
from isocentro.interface import ui

_LOG = logging.getLogger(__name__)

# Quanto tempo o recado do convênio fica na linha de status. Doze segundos, e
# não os seis dos outros avisos: ele conta uma decisão que a ficha tomou SEM
# perguntar, e quem gera a ficha só olha para a barra depois que o PDF aparece.
_MS_RECADO_SUS = 12000


def e_600cd(dados: dict) -> bool:
    """True quando a máquina da ficha é o 600CD — única com páginas de DRR."""
    maq = constantes.identificar_maquina(dados.get("maquina", ""))
    return bool(maq and maq.chave == "600CD")


def recado_do_convenio(is_sus: bool, numero: str, origem: str,
                       convenio: str) -> str:
    """A linha de status que ANUNCIA o que foi decidido sem perguntar.

    Decisão calada vira o normal em duas semanas — e esta muda o que sai no
    papel: as duas folhas de Registro de Tratamento entram ou não entram no
    maço. O recado diz o convênio, a origem e a saída, e aponta a porta de
    correção: convênio errado se conserta na aba Capa, que grava em
    ``correcoes`` — e a correção tem a última palavra aqui.
    """
    fonte = f" ({origem})" if origem else ""
    if is_sus:
        return (f"Convênio {convenio}{fonte}: Cartão SUS {numero} — a ficha "
                "sai com as folhas de Registro de Tratamento, sem perguntar.")
    return (f"Convênio {convenio}{fonte}: a ficha sai SEM as folhas de "
            "Registro de Tratamento (SUS). Convênio errado? Corrija na "
            "aba Capa.")


def recado_do_cadastro_guardado(prev: dict) -> str:
    """O que a barra diz quando a ficha saiu do cadastro guardado.

    Reserva usada é reserva ANUNCIADA — a mesma regra da capa que não veio
    do banco. Três coisas na frase, e cada uma responde uma pergunta de
    quem lê: o QUE valeu, POR QUE não veio do sistema, e ONDE se corrige.
    Sem a terceira o aviso vira notícia ruim sem saída.
    """
    if prev.get("pac_sus"):
        num = str(prev.get("numero_sus", "")).strip() or "sem número"
        o_que = f"SUS {num}"
    else:
        o_que = "NÃO SUS"
    return (f"Convênio {o_que}, do cadastro anterior deste paciente — o "
            "sistema não respondeu agora. Errado? Corrija na aba Capa.")


class PortaoDaFicha:
    """As perguntas entre o clique e o papel. A janela o constrói e o consulta."""

    def __init__(self, janela):
        # A janela é o PAI dos pop-ups e a dona do estado do caso (ver a
        # docstring do módulo para o porquê de não copiar nada dela aqui).
        self.janela = janela
        # Pacientes que já receberam o alerta de "SUS sem número" nesta sessão.
        # Sem isto o modal volta a cada prévia — e a prévia é refeita o tempo
        # todo (ver ``alertar_sus_sem_numero``). Vive o mesmo que a janela: a
        # memória é da SESSÃO, não do paciente carregado.
        self._sus_ja_alertado: set = set()

    # ── Conferência: o que a ficha vai sair devendo ───────────────────────────
    def planos_gating_pendente(self) -> list:
        """Rótulos de planos com gating no RT Plan mas sem modalidade preenchida.

        Breath-Hold é preenchido automaticamente ao carregar; GATING/REALTIME
        (amplitude ou fase) o DICOM não distingue, então o usuário precisa
        escolher — e este método detecta quando ele não escolheu.
        """
        j = self.janela
        pend = []
        planos = j.caso.planos or []
        if planos:
            dados_planos = j.form.coletar_planos()
            for i, p in enumerate(planos):
                if not (p.get("rp") or {}).get("gating_plano"):
                    continue
                d = dados_planos[i] if i < len(dados_planos) else {}
                if not str(d.get("gating_modalidade", "") or "").strip():
                    pend.append(p.get("rotulo") or f"Plano {i + 1}")
        else:
            rp = j.caso.dados.get("RP", {})
            if rp.get("gating_plano") and not str(
                    j.form.coletar().get("gating_modalidade", "") or "").strip():
                pend.append(rp.get("rotulo_plano") or "este plano")
        return pend

    def agendamento_completo(self) -> bool:
        """True se o agendamento cobre todas as frações prescritas de cada plano.

        Plano único não usa agendamento (sempre completo). Multi-plano exige um
        agendamento cujas frações por plano batam com a prescrição — senão a
        página 3 (mapa de frações) sairia incompleta.
        """
        j = self.janela
        if len(j.caso.planos) < 2:
            return True
        ag_info = j.caso.agendamento
        if not ag_info:
            return False
        agendadas = ag.fracoes_por_plano(ag_info.get("etapas") or [], len(j.caso.planos))
        dados_planos = j.form.coletar_planos()
        for i, p in enumerate(j.caso.planos):
            presc = int((dados_planos[i].get("rx_fracoes") if i < len(dados_planos) else 0) or 0)
            if not presc:
                presc = int(p["rp"].get("num_fracoes") or 0)
            if agendadas[i] != presc:
                return False
        return True

    def pendencias(self) -> list:
        """O que a ficha vai sair devendo, em linguagem de quem confere.

        Tudo aqui já era detectado em algum canto — no carregamento da pasta, no
        log, num modal que se dispensa com Enter. O problema é o QUANDO: os
        avisos chegam minutos antes de gerar o documento, e o campo continua
        vazio na hora que ele sai. Esta lista é a mesma informação, na hora certa.
        """
        j = self.janela
        pend = []
        if not j.form.eq_medico.currentText().strip():
            pend.append("Médico responsável não preenchido.")
        if not j.form.eq_fisico.currentText().strip():
            pend.append("Físico responsável não preenchido.")
        if not j.form.pac_registro.text().strip():
            pend.append("Registro do paciente vazio.")

        rps = [(p.get("rotulo") or "plano", p.get("rp") or {})
               for p in j.caso.planos] or [("plano", j.caso.dados.get("RP") or {})]
        def _quais(teste) -> str:
            nomes = [rot for rot, rp in rps if rp and teste(rp)]
            return ", ".join(nomes)

        nao_aprovados = _quais(
            lambda rp: str(rp.get("aprovacao", "")).upper() == "UNAPPROVED")
        if nao_aprovados:
            pend.append(f"Plano não aprovado no TPS ({nao_aprovados}).")

        sem_desl = _quais(lambda rp: rp.get("iso_pos_mm") and all(
            rp.get(k) is None for k in ("desl_lat", "desl_long", "desl_vert")))
        if sem_desl:
            pend.append(f"Sem deslocamento de setup — Delta Couch ({sem_desl}).")

        sem_ssd = _quais(lambda rp: rp.get("feixes") and any(
            f.get("ssd") is None for f in rp["feixes"]))
        if sem_ssd:
            pend.append(f"Campo sem SSD calculado ({sem_ssd}).")

        if len(j.caso.planos) >= 2 and not j.caso.agendamento:
            pend.append("Agendamento não montado — a pág. 3 sai sem o mapa.")
        return pend

    def confirmar_pendencias(self) -> bool:
        """Mostra a conferência e devolve True se é para seguir com a ficha."""
        pend = self.pendencias()
        if not pend:
            return True
        # ``perigo=True`` põe o Enter em "Voltar e corrigir": o documento vai
        # para a sala de tratamento, e gerar com pendência é o passo que não se
        # desfaz depois que o papel está grampeado.
        return ui.confirmar(
            self.janela, "Conferência da ficha",
            "A ficha vai sair com estas pendências:",
            acao="Gerar assim mesmo", recusa="Voltar e corrigir",
            detalhe="\n".join(f"•  {p}" for p in pend), perigo=True)

    # ── Etapas da geração (orquestradas pelo ``ControleFicha.gerar_pdf``) ────────
    def validar_campos_obrigatorios(self, dados: dict) -> bool:
        """True se os campos obrigatórios estão preenchidos; senão avisa e False."""
        erros = []
        if not dados.get("pac_nome", "").strip():
            erros.append("• Nome do paciente")
        if not dados.get("pac_registro", "").strip():
            erros.append("• Registro do paciente")
        if not dados.get("rx_dose_total"):
            erros.append("• Dose total")
        if not dados.get("rx_fracoes"):
            erros.append("• Número de frações")
        if not dados.get("eq_medico", "").strip():
            erros.append("• Médico responsável")
        if erros:
            ui.alertar(
                self.janela, "Dados insuficientes",
                "Preencha os campos obrigatórios antes de gerar a ficha:\n\n"
                + "\n".join(erros))
            return False
        return True

    def confirmar_gating_pendente(self) -> bool:
        """Avisa quando há gating no plano sem modalidade definida. False = voltar."""
        pend_gat = self.planos_gating_pendente()
        if not pend_gat:
            return True
        return ui.confirmar(
            self.janela, "Gating sem modalidade",
            "O plano indica Gating, mas a modalidade não foi definida.",
            acao="Gerar assim mesmo", recusa="Voltar e ajustar",
            detalhe=("\n".join(f"• {r}" for r in pend_gat)
                     + "\n\nDefina a modalidade antes de gerar a ficha."),
            perigo=True)

    def planos_incompletos(self) -> list[str]:
        """Lista de avisos "• Plano X: sem TC…" para planos que sairão com seções
        vazias. Vazia quando está tudo certo, ou na ficha reaberta (arquivada), em
        que os cortes/DVH vêm dos PNGs salvos — CT/RD ausentes ali são esperados.
        """
        j = self.janela
        if j.caso.ct is None and j.caso.registro_carregado is not None:
            return []
        avisos: list[str] = []
        for i, p in enumerate(j.caso.planos):
            faltas = []
            if p.get("ct") is None:
                faltas.append("sem TC (cortes em branco)")
            if p.get("rd_ds") is None:
                faltas.append("sem dose (DVH/isodose vazios)")
            if faltas:
                rot = p.get("rotulo") or f"Plano {i + 1}"
                avisos.append(f"• {rot}: " + ", ".join(faltas))
        return avisos

    def confirmar_planos_incompletos(self) -> bool:
        """Avisa quando algum plano sairá sem cortes (sem TC) ou sem DVH/isodose
        (sem dose). Aviso, não bloqueio. False = voltar e ajustar."""
        avisos = self.planos_incompletos()
        if not avisos:
            return True
        return ui.confirmar(
            self.janela, "Plano incompleto",
            "Estes planos sairão com seções vazias na ficha:",
            acao="Gerar assim mesmo", recusa="Voltar e ajustar",
            detalhe=("\n".join(avisos) + "\n\nConfira se todos os DICOM "
                     "(TC/RD) da pasta foram lidos."),
            perigo=True)

    def confirmar_600cd_sem_portal(self, dados: dict, recursos: dict) -> bool:
        """Avisa quando é 600CD mas não veio nenhuma imagem PORTAL na pasta.

        A ficha do 600CD prevê os DRRs de setup (portais). Sem eles a ficha sai
        sem essas páginas — então avisamos e deixamos o usuário optar por
        adicionar os arquivos antes, ou gerar assim mesmo.
        Devolve True para prosseguir; False para cancelar.
        """
        if not e_600cd(dados):
            return True
        if recursos.get("drrs"):   # datasets dos portais de setup (só há DICOM aqui)
            return True
        return ui.confirmar(
            self.janela, "600CD sem imagem PORTAL",
            "Máquina 600CD, mas nenhuma imagem PORTAL (DRR de setup) foi "
            "encontrada na pasta.",
            acao="Gerar sem os DRR", recusa="Voltar e conferir a pasta",
            detalhe="A ficha sairá SEM as páginas de DRR.",
            perigo=True)

    # ── SUS: se as folhas de Registro de Tratamento entram no maço ────────────
    def maquina_sus_elegivel(self) -> bool:
        """True se alguma máquina do tratamento dispara o fluxo de Registro SUS."""
        j = self.janela
        maqs = ([(p.get("rp") or {}).get("maquina", "") for p in j.caso.planos]
                if j.caso.planos else [j.caso.dados.get("RP", {}).get("maquina", "")])
        return any((_m := constantes.identificar_maquina(m)) is not None
                   and _m.sus_elegivel for m in maqs)

    def perguntar_sus(self, sus_atual: bool = False,
                      numero_atual: str = "") -> tuple | None:
        """Popup 'Este é um paciente SUS?'. Se Sim, habilita o Número SUS.
        Devolve ``(is_sus, numero)`` ou ``None`` se cancelado."""
        dlg = QDialog(self.janela)
        dlg.setWindowTitle("Paciente SUS")
        dlg.setMinimumWidth(380)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(24, 20, 24, 16); lay.setSpacing(12)
        lbl = QLabel("Este é um paciente SUS?")
        lbl.setStyleSheet("font-weight:bold; font-size:13px;")
        lay.addWidget(lbl)
        linha = QHBoxLayout()
        rb_nao = QRadioButton("Não"); rb_sim = QRadioButton("Sim")
        (rb_sim if sus_atual else rb_nao).setChecked(True)
        linha.addWidget(rb_nao); linha.addWidget(rb_sim); linha.addStretch()
        lay.addLayout(linha)
        lin = QHBoxLayout()
        lbl_sus = QLabel("Número SUS:")
        ed_sus = QLineEdit(numero_atual or "")
        lin.addWidget(lbl_sus); lin.addWidget(ed_sus, 1)
        lay.addLayout(lin)

        def _toggle():
            on = rb_sim.isChecked()
            lbl_sus.setEnabled(on); ed_sus.setEnabled(on)
            if on:
                ed_sus.setFocus()
        rb_sim.toggled.connect(lambda _c: _toggle())
        _toggle()

        botoes = QHBoxLayout(); botoes.addStretch()
        ok = QPushButton("Continuar"); ok.setDefault(True)
        ok.setStyleSheet(estilo.btn_solido())
        cancel = QPushButton("Cancelar")
        cancel.setStyleSheet(estilo.btn_fantasma())
        ok.clicked.connect(dlg.accept); cancel.clicked.connect(dlg.reject)
        botoes.addWidget(ok); botoes.addWidget(cancel)
        lay.addLayout(botoes)

        if dlg.exec() != QDialog.Accepted:
            return None
        return (rb_sim.isChecked(), ed_sus.text().strip())

    def coletar_sus(self, dados: dict) -> bool:
        """Resolve se é paciente SUS (só p/ TrueBeamSN1001) e qual o número.
        Mutação em ``dados``/``janela.caso.sus``. False = usuário cancelou (abortar).

        **Não pergunta o que o sistema já respondeu.** Desde que a fonte do
        cadastro é o banco (18/08/2026), o convênio vem de lá com a carteirinha
        — e, para quem é SUS, a carteirinha É o Cartão SUS. Pedir a cada ficha um
        número de quinze dígitos que o sistema já tem é pedir erro de digitação
        num dado que vai impresso.

        O popup ficou para o que o convênio NÃO responde, que é o pedido do
        usuário — "se o campo estiver em branco ou sem o número, perguntar":

        * banco sem resposta, ou paciente que ele não conhece → pergunta tudo;
        * convênio SUS **sem** o número → pergunta SÓ o número, com "Sim" já
          marcado (não há o que decidir sobre o "se");
        * convênio de outro plano → não é ficha SUS, e ninguém é perguntado.

        Sem o convênio, segue valendo o cadastro por paciente: se o MESMO
        paciente (nome + nascimento + registro) já tem cadastro SUS de um
        tratamento anterior, oferece manter o número guardado ou alterá-lo.
        """
        if not self.maquina_sus_elegivel():
            return True
        status = self.janela.status
        nome = dados.get("pac_nome", "")
        nasc = dados.get("pac_nascimento", "")
        reg = dados.get("pac_registro", "")

        e_sus, numero, origem, convenio = self.sus_pelo_convenio(reg)
        if e_sus is False or (e_sus and numero):
            self.aplicar_sus(dados, bool(e_sus), numero)
            # Grava só o que o convênio CONFIRMOU. Gravar o "não é SUS" apagaria
            # o Cartão SUS que uma pessoa digitou e conferiu: bastaria a linha
            # de convênio do banco estar desatualizada num dia para o número
            # sumir da reserva — e, no dia em que o banco não responder, a
            # reserva passaria a responder "não é SUS" com a autoridade de quem
            # foi confirmado. O cadastro local é a memória do que um humano
            # afirmou; o banco decide esta ficha, não aquela memória.
            if e_sus and numero:
                cadastro_sus.registrar(nome, nasc, reg, True, numero)
            status.showMessage(
                recado_do_convenio(bool(e_sus), numero, origem, convenio),
                _MS_RECADO_SUS)
            return True

        prev = None
        try:
            prev = cadastro_sus.consultar(nome, nasc, reg)
        except Exception:  # noqa: BLE001
            prev = None

        # Pré-preenche: cadastro do paciente > lembrado da sessão.
        pref_sus = self.janela.caso.sus.get("pac_sus", False)
        pref_num = self.janela.caso.sus.get("numero_sus", "")
        if e_sus:
            # SUS SEM O NÚMERO: o servidor já respondeu o que decide a ficha —
            # que este paciente é SUS. O número que falta é dado de cadastro
            # DELE, e perguntá-lo a cada ficha é pedir quinze dígitos de cor a
            # quem está montando um paciente. Decidido em 04/09/2026: "todo
            # paciente que for SUS, ou qualquer convênio, vai sair direto do
            # servidor; o que precisa constar é um alerta".
            #
            # Antes de alertar, aproveita o número que ESTE paciente já tem
            # guardado: ele foi digitado e conferido por uma pessoa, e o
            # servidor não o estar devolvendo agora não o torna falso.
            # SÓ o cadastro deste paciente, nunca o ``pref_num`` — que é o
            # número lembrado da SESSÃO, isto é, do último paciente para quem
            # alguém digitou um. Aproveitá-lo aqui gravaria o Cartão SUS de uma
            # pessoa no cadastro de outra, e a barra ainda diria que veio "do
            # cadastro deste paciente". Achado na revisão de 04/09/2026.
            numero_sus = str((prev or {}).get("numero_sus", "")).strip()
            self.aplicar_sus(dados, True, numero_sus)
            if numero_sus:
                cadastro_sus.registrar(nome, nasc, reg, True, numero_sus)
                status.showMessage(
                    f"Convênio SUS {numero_sus} — o número veio do cadastro "
                    "deste paciente; o sistema trouxe o convênio sem ele.",
                    _MS_RECADO_SUS)
            else:
                self.alertar_sus_sem_numero(reg)
            return True
        elif prev is not None:
            # O cadastro guardado VALE, e é anunciado — não perguntado.
            #
            # Esta é a única porta em que o "Manter o cadastro / Alterar"
            # aparecia, e ela só abre quando o BANCO NÃO RESPONDEU: quando ele
            # responde, o convênio decide a ficha e ninguém é perguntado (ver o
            # início desta função). Ou seja, a pergunta chegava justamente na
            # hora em que não havia nada de novo para decidir — só a memória do
            # que uma pessoa já tinha afirmado sobre ESTE paciente.
            #
            # Tirada em 04/09/2026 a pedido do uso ("essa barreira não
            # precisa"). O que fica no lugar é a regra da reserva anunciada,
            # que este projeto já aplica na capa: usar o guardado e DIZER que
            # foi ele, com a origem e o caminho para corrigir. Pergunta que se
            # responde sempre igual vira clique automático, e clique automático
            # não confere nada.
            is_sus = bool(prev.get("pac_sus"))
            numero_sus = str(prev.get("numero_sus", "")) if is_sus else ""
            self.aplicar_sus(dados, is_sus, numero_sus)
            status.showMessage(recado_do_cadastro_guardado(prev),
                               _MS_RECADO_SUS)
            return True

        res = self.perguntar_sus(pref_sus, pref_num)
        if res is None:
            return False
        is_sus, numero_sus = res
        self.aplicar_sus(dados, is_sus, numero_sus)
        # Persiste no cadastro por paciente (falha silenciosa: é conveniência).
        cadastro_sus.registrar(nome, nasc, reg, is_sus, dados["numero_sus"])
        return True

    def aplicar_sus(self, dados: dict, is_sus: bool, numero: str) -> None:
        """Assenta a resposta do SUS em ``dados`` e no lembrado da sessão.

        As duas linhas andavam repetidas em quatro ramos do ``coletar_sus``, e
        as folhas de Registro de Tratamento saem de ``dados["pac_sus"]``: o ramo
        que esquecesse uma delas daria um maço sem as folhas e uma tela dizendo
        que o paciente é SUS. Aqui também mora a regra de que número só existe
        para quem é SUS.
        """
        numero = numero if is_sus else ""
        dados["pac_sus"] = is_sus
        dados["numero_sus"] = numero
        self.janela.caso.sus = {"pac_sus": is_sus, "numero_sus": numero}

    def sus_pelo_convenio(self, registro: str) -> tuple:
        """``(é SUS?, número, origem, convênio)`` — ver ``cadastro_sus``.

        Erro aqui não pode travar a ficha: a resposta vira "não deu para saber",
        e quem pergunta é o popup, como sempre perguntou.

        MÉTODO, e não função do módulo como os recados: é a costura com o banco,
        e o ``tests/test_sus_convenio.py`` a troca por instância para decidir o
        que "o banco respondeu" em cada caso.
        """
        try:
            return cadastro_sus.sus_do_paciente(registro)
        except Exception:  # noqa: BLE001
            _LOG.exception("Falha ao ler o convênio para resolver o SUS")
            return (None, "", "", "")

    def alertar_sus_sem_numero(self, registro: str = "") -> None:
        """Paciente SUS e sem o Cartão SUS — a ficha sai com o campo vazio.

        ``alertar`` e não ``confirmar``: o trabalho segue, e travar a ficha por
        um campo de cadastro seria pior que imprimi-la com ele vazio — quem
        monta o paciente não é quem resolve pendência de cadastro, e a folha é
        precisa para a sala AGORA.

        Mas também não é recado de barra de status: o número vai IMPRESSO, e
        um aviso que some sozinho depois de alguns segundos não chega a quem
        está olhando a mesa.

        **UMA VEZ POR PACIENTE, e é o que o torna aceitável.** O
        ``coletar_sus`` roda dentro da prévia automática, que é refeita a cada
        carga, a cada volta à Fichinha, a cada edição e a cada impressão — sem
        esta memória o modal voltaria em todas, e nada no fluxo o encerraria.
        Antes disso a pergunta antiga fechava o assunto sozinha, gravando o
        cadastro; um alerta não grava nada, então quem tem de lembrar é ele.
        Achado na revisão de 04/09/2026.

        A memória é da SESSÃO, não do disco: o número pode ser preenchido a
        qualquer momento, e reabrir o programa é o gesto de quem quer recomeçar.
        """
        status = self.janela.status
        reg = capa_dados.normalizar_id(registro)
        # Sem registro não há como não repetir — e repetir é pior que calar,
        # porque o aviso que se repete deixa de ser lido. Fica só a barra.
        if reg and reg in self._sus_ja_alertado:
            status.showMessage(
                "Convênio SUS — SEM o número do cartão. Preencha na aba Capa.",
                _MS_RECADO_SUS)
            return
        if reg:
            self._sus_ja_alertado.add(reg)
        ui.alertar(
            self.janela, "SUS sem o número do cartão",
            "O sistema informa que este paciente é SUS, mas não trouxe o "
            "número do Cartão SUS.",
            detalhe="A ficha sai com o campo vazio.\n\nPara preencher: aba "
                    "Capa → campo “Cartão SUS”. O número fica guardado para "
                    "as próximas fichas deste paciente, e este aviso não "
                    "volta nesta sessão.")
        status.showMessage(
            "Convênio SUS — SEM o número do cartão. Preencha na aba Capa.",
            _MS_RECADO_SUS)
