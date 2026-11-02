r"""A varredura: pergunta, busca, grava, anota. É a automação em si.

As peças já existiam separadas — o :mod:`gatilho_db` diz quais planos estão
prontos, o :mod:`gatilho_registro` lembra o que já viu e o que já saiu, o
:mod:`dicom_rede` traz os arquivos. Aqui elas viram uma passada só, que é o que
um relógio na tela chama de tempos em tempos.

**A ordem é a regra, e cada passo dela custou alguma coisa:**

1. anotar quem está disponível AGORA — é o log, e vem primeiro para que uma
   Documentação que abre e muda de estado na mesma rodada ainda entre;
2. cruzar a janela ANOTADA (não a de agora) com os planos aprovados;
3. buscar os arquivos de cada plano;
4. anotar a saída **só quando o conjunto chegou inteiro**. Marcar antes deixaria
   um conjunto pela metade na pasta com a marca de "pronto", e a rodada seguinte
   não voltaria para terminar;
5. fechar a janela só quando TODOS os planos dela saíram — fechada, ela some
   dos pendentes, e o plano que travou nunca mais seria tentado;
6. fechar as janelas vencidas, com o motivo escrito;
7. apagar da temporária o que já não serve — ver :func:`_limpar`.

**Falha de rede para a varredura; plano que falhou, não.** São coisas
diferentes: sem rede, insistir nos vinte planos seguintes só enche o log de
repetição; um plano que não veio pode ser um caso específico, e os outros
dezenove ainda têm de sair.

**O portão.** Nada sai enquanto o ``gatilho_db.VERIFICADO_EM`` estiver vazio, a
rede DICOM não estiver configurada ou esta máquina não for a que varre (ver
"Quem varre", abaixo do :func:`motivo_indisponivel`). Não é cautela
decorativa: esta função grava arquivos que alguém vai conferir como se fossem
do paciente certo.
"""
from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from isocentro.dados import ambiente
from isocentro.dados import indice
from isocentro.adaptadores.dicom import rede as dicom_rede
from isocentro.banco import gatilho_db
from isocentro.dominio import gatilho_registro

_LOG = logging.getLogger(__name__)

# Para onde vão os arquivos. Pasta do SERVIÇO, como as outras: quem confere o
# plano não é necessariamente quem rodou a varredura.
ENV_PASTA = "ISOCENTRO_EXPORTACAO"

# Motivos de fechamento de janela. Constantes porque são lidos depois, por
# quem quer saber por que um caso não saiu — e string solta no meio do código
# vira duas grafias da mesma coisa.
MOTIVO_EXPORTADO = "exportado"
MOTIVO_VENCIDO = "venceu sem plano aprovado"

# O que a preparação conclui, pelo mesmo motivo das constantes de cima: quem lê
# é a Fichinha de outra estação, e duas grafias do mesmo estado seriam um item
# que nunca acende.
ESTADO_PRONTA = "pronta"
AVISO_SEM_SIMULACAO = "sem cadastro de simulação"

# A trava de UMA varredura por vez, na raiz da exportação — o recurso disputado
# é aquela pasta, o ARIA e o registro que a acompanha. Nunca é apagada: a trava
# é do SO sobre o descritor, e apagar o arquivo deixaria *delete pending* no
# Windows (ver ``indice.travar_arquivo``).
#
# Ela existe porque a exclusão de antes era o ``gatilho_relogio.ocupado()``, que
# só vale DENTRO de um processo. Com a varredura podendo rodar por Tarefa
# Agendada na concentradora e, ao mesmo tempo, pelo relógio de um app aberto na
# mesma máquina, "uma por vez" deixou de ser verdade. O relógio saiu do app na
# R-21 (AD-28); a trava fica, contra duas rodadas da Tarefa sobrepostas.
ARQUIVO_TRAVA = "varredura.lock"
MOTIVO_OCUPADA = "outra varredura já está rodando nesta pasta"


@dataclass
class Relatorio:
    """O que a passada fez. Serve à tela e ao histórico."""
    exportados: list = field(default_factory=list)   # Pronto
    incompletos: list = field(default_factory=list)  # (Pronto, motivo)
    vencidos: list = field(default_factory=list)     # instância
    limpos: list = field(default_factory=list)       # {instancia, pastas, motivo}
    interrompida: str = ""       # por quê, se parou no meio
    portao: str = ""             # por que nem começou

    @property
    def rodou(self) -> bool:
        return not self.portao

    def resumo(self) -> str:
        if self.portao:
            return f"Não rodou: {self.portao}"
        partes = [f"{len(self.exportados)} plano(s) exportado(s)"]
        if self.incompletos:
            partes.append(f"{len(self.incompletos)} incompleto(s)")
        if self.vencidos:
            partes.append(f"{len(self.vencidos)} janela(s) vencida(s)")
        if self.limpos:
            partes.append(f"{len(self.limpos)} caso(s) limpo(s) da temporária")
        if self.interrompida:
            partes.append(f"INTERROMPIDA: {self.interrompida}")
        return ", ".join(partes)


def pasta_destino() -> Path:
    """Onde os arquivos caem, na mesma escada das outras pastas do serviço.

    Precedência: **variável da estação** → **configuração do serviço** →
    padrão ao lado do índice. É a de :func:`simulacao.pasta_raiz` e a do
    ``capa_dados``, e não por simetria: a variável é decisão de quem montou
    AQUELA máquina e tem de poder vencer; a configuração é decisão do admin e
    vale para todas as estações de uma vez.

    Sem a configuração do serviço isto seria por estação, e uma estação
    esquecida gravaria os planos na pasta do programa em silêncio — quem
    administra não teria como afirmar que tudo cai no servidor.
    """
    escolhida = ambiente.ler(ENV_PASTA)
    if escolhida:
        return Path(escolhida)
    try:
        from isocentro.dados import config_servico
        do_servico = config_servico.valor(config_servico.PASTA_EXPORTACAO)
    except Exception:  # noqa: BLE001
        # Config ilegível não derruba a varredura: ela cai no padrão, que é uma
        # pasta do serviço de qualquer forma. Mas vai para o HISTÓRICO — o
        # ``valor()`` já engole OSError e ValueError sozinho, então o que sobra
        # aqui é ``ImportError``, isto é, o módulo fora do pacote na clínica. A
        # varredura passaria a gravar noutra pasta sem rastro nenhum, e este
        # módulo está em ``log_app.LOGGERS_APP`` justamente por rodar sozinho.
        _LOG.exception("Não deu para ler a pasta de exportação do serviço; "
                       "usando o padrão ao lado do índice")
        do_servico = ""
    if do_servico:
        return Path(do_servico)
    from isocentro.dados import indice

    return Path(indice.REGISTRO_PATH).parent / "exportacao"


def origem_da_pasta() -> str:
    """Qual das três escolhas está valendo — para a tela poder dizer.

    Sem isto, quem aponta a pasta em Configurações e não vê efeito não tem como
    descobrir que uma variável de ambiente local está mandando nela. É a mesma
    razão do ``origem_da_pasta`` da Capa.
    """
    if ambiente.ler(ENV_PASTA):
        return f"variável {ambiente.qual_valeu(ENV_PASTA)} desta estação"
    try:
        from isocentro.dados import config_servico
        if config_servico.valor(config_servico.PASTA_EXPORTACAO):
            return "configuração do serviço"
    except Exception:  # noqa: BLE001
        # Diferente do ramo de cima, aqui o texto vai para a TELA: devolver
        # "padrão" caladamente faria a tela afirmar uma escolha onde houve
        # falha. Ela diz que não conseguiu ler.
        _LOG.exception("Não deu para ler a configuração do serviço")
        return "padrão (não deu para ler a configuração do serviço)"
    return "padrão, ao lado do índice do serviço"


def disponivel() -> bool:
    return (gatilho_db.disponivel() and dicom_rede.configurado()
            and _esta_maquina_varre())


def motivo_indisponivel() -> str:
    """Qual peça falta — o banco, a rede ou a máquina.

    As três dão "não exportou nada" e pedem providências opostas: uma é
    conferir a consulta contra o ARIA, outra é cadastrar o AE Title, a última
    é dizer qual máquina é a concentradora. Um aviso só para todas manda abrir
    o chamado errado.
    """
    if not gatilho_db.disponivel():
        return gatilho_db.motivo_indisponivel()
    if not dicom_rede.configurado():
        return dicom_rede.motivo_indisponivel()
    if not _esta_maquina_varre():
        return motivo_da_maquina()
    return ""


# ── Quem varre ─────────────────────────────────────────────────────────────
#
# Decisão do usuário em 18/09/2026, a pergunta 1 do
# ``docs/INSTALAR_CONCENTRADORA.md``. Com a rede DICOM no ``config_servico``
# (14/09), que é o MESMO arquivo para todas as estações, o relógio de cada app
# aberto achava o portão aberto e varria: C-MOVE a cada cinco minutos de cada
# estação, entregue pelo ARIA só na máquina cadastrada no destino, e a trava
# da pasta segurada por quem não recebe nada — a rodada da concentradora saía
# PULADA, com código 0 no Agendador.
#
# A regra, em três casos:
#
# * a chave ``concentradora`` preenchida → só a máquina com esse nome varre,
#   pelo app ou pela Tarefa Agendada;
# * vazia, com a rede INTEIRA em variável desta conta → varre: é o regime de
#   11/09, decisão de instalação de uma máquina (e o da bancada de testes);
# * vazia, com a rede vindo do arquivo → NINGUÉM varre, e o motivo manda
#   preencher. Varrer em todas seria o defeito que esta regra fecha, e
#   escolher uma sozinho seria adivinhar.


def nome_desta_maquina() -> str:
    """O nome NetBIOS desta máquina, como o admin o vê no Windows."""
    import socket  # noqa: PLC0415
    return (os.environ.get("COMPUTERNAME") or socket.gethostname()
            or "").strip()


def _nome_curto(nome: str) -> str:
    r"""``\\CLINICA-PYTHON01.clinica.example`` e ``clinica-python01`` são a mesma.

    O admin digita como lembra: com as barras do caminho de rede, com o
    domínio, em maiúsculas. Endereço IP não vira nome — fica inteiro, não casa
    com máquina nenhuma, e o motivo mostra os dois lado a lado.
    """
    n = str(nome or "").strip().lstrip("\\/").lower()
    if n.replace(".", "").isdigit():
        return n
    return n.split(".", 1)[0]


def concentradora() -> str:
    """O nome gravado na chave ``concentradora`` ("" se ninguém apontou)."""
    try:
        from isocentro.dados import config_servico  # noqa: PLC0415
        return config_servico.valor(config_servico.CONCENTRADORA).strip()
    except Exception:  # noqa: BLE001
        # Mesma razão do ``pasta_destino``: o que sobra aqui é ``ImportError``
        # (módulo fora do pacote), e cair no "ninguém apontou" fecha o
        # portão — nunca o abre para todas.
        _LOG.exception("Não deu para ler a concentradora do serviço")
        return ""


def _esta_maquina_varre() -> bool:
    alvo = concentradora()
    if alvo:
        return _nome_curto(alvo) == _nome_curto(nome_desta_maquina())
    return dicom_rede.configurado_pela_estacao()


def motivo_da_maquina() -> str:
    """Por que ESTA máquina não varre ("" se varre)."""
    if _esta_maquina_varre():
        return ""
    alvo = concentradora()
    if alvo:
        return (f"Esta máquina ({nome_desta_maquina() or '?'}) não é a "
                f"concentradora ({alvo}): quem varre é ela.")
    return ("A rede DICOM vem da configuração do serviço, que vale para "
            "TODAS as estações, e falta dizer qual máquina varre: preencha "
            "\"Concentradora\" em Configurações → Serviço. Até lá nenhuma "
            "varre — senão todas varreriam.")


def caminho_do_plano(pronto, raiz: Path | None = None) -> Path:
    """``<raiz>/<registro>/<curso>/<plano>``.

    Legível de propósito: quem abre a pasta procurando o plano de um paciente
    tem de achá-lo sem consultar índice nenhum. O UID fica no nome dos arquivos
    lá dentro, onde ele importa e onde não colide.
    """
    raiz = Path(raiz) if raiz is not None else pasta_destino()
    return raiz / _seguro(pronto.registro) / _seguro(pronto.curso) / _seguro(
        pronto.plano)


def _seguro(texto: str) -> str:
    """Nome de pasta a partir de texto do banco.

    ``CourseId`` e ``PlanSetupId`` vêm do ARIA e ninguém promete que não têm
    barra, dois-pontos ou espaço no fim — e um deles bastaria para a gravação
    ir parar em outro lugar, ou falhar com erro que não parece de nome.
    """
    limpo = "".join(c if c.isalnum() or c in " -_." else "_"
                    for c in (texto or "").strip())
    return limpo.strip(" .") or "sem-nome"


def rodar(raiz=None, agora=None, parar=None) -> Relatorio:
    """Uma passada completa. Não levanta: o que deu errado vai no relatório.

    Quem chama isto é um relógio, e exceção que sobe de um relógio ou derruba a
    tela ou é engolida — as duas piores saídas. O relatório é a saída do meio:
    diz o que houve, e quem lê decide.

    ``parar`` é um chamável que responde "pare agora" — quem fecha o programa
    no meio de uma varredura. É consultado ENTRE planos, nunca dentro de um: a
    marca d'água só é anotada com o conjunto inteiro na pasta, então parar
    entre planos não deixa nada pela metade marcado como pronto, e o plano
    interrompido volta na rodada seguinte. Sem este gancho a alternativa era
    destruir a thread em execução, que é ``qFatal`` — a mesma armadilha que o
    ``closeEvent`` já evita para a carga do paciente.

    **Uma por vez, entre PROCESSOS** (14/09/2026): a rodada inteira acontece
    sob a trava de ``ARQUIVO_TRAVA``, e quem chega com outra em curso volta com
    ``portao`` preenchido — que é o mesmo caminho de "não rodou" que a tela já
    sabe não anunciar. Vai para o histórico, porém: varredura sempre pulada por
    estar ocupada quer dizer que o intervalo ficou curto para esta clínica, e
    isso não se descobre olhando a tela.
    """
    rel = Relatorio()
    if not disponivel():
        rel.portao = motivo_indisponivel()
        _LOG.info("Varredura não rodou: %s", rel.portao)
        return rel

    raiz = Path(raiz) if raiz is not None else pasta_destino()
    with indice.travar_ou_desistir(raiz / ARQUIVO_TRAVA) as minha:
        if not minha:
            rel.portao = MOTIVO_OCUPADA
            _LOG.info("Varredura não rodou: %s", rel.portao)
            return rel
        try:
            pendentes = gatilho_registro.pendentes()
        except Exception as exc:  # noqa: BLE001
            rel.interrompida = f"não deu para saber o que está pendente: {exc}"
            _LOG.exception("Varredura interrompida ao consultar o que falta")
            return rel

        for pronto in pendentes:
            if parar is not None and parar():
                rel.interrompida = "encerrado a pedido (o programa está fechando)"
                _LOG.info("Varredura encerrada a pedido, com %s plano(s) ainda "
                          "pendente(s)", len(pendentes) - len(rel.exportados))
                break
            try:
                _buscar_um(pronto, raiz, rel)
            except dicom_rede.FalhaDeRede as exc:
                # Rede fora ou AE recusado: os próximos vão falhar igual. Parar
                # aqui é o que evita vinte linhas repetidas no histórico
                # escondendo a única que importa.
                rel.interrompida = str(exc)
                _LOG.warning("Varredura interrompida: %s", exc)
                break
            except Exception as exc:  # noqa: BLE001
                # Um plano específico que deu errado não impede os outros.
                rel.incompletos.append((pronto, str(exc)))
                _anotar_incompleto(pronto, f"falhou ao buscar: {exc}")
                _LOG.exception("Falhou ao buscar o plano %s de %s",
                               pronto.plano, pronto.registro)

        _fechar_completas(pendentes, rel)
        rel.vencidos = _fechar_vencidas(agora)
        rel.limpos = _limpar(raiz, agora)
    _LOG.info("Varredura: %s", rel.resumo())
    return rel


def _buscar_um(pronto, raiz: Path, rel: Relatorio) -> None:
    destino = caminho_do_plano(pronto, raiz)
    # ``trazer`` e não ``baixar``: o ``baixar`` é o C-GET, e este ARIA não faz
    # C-GET — medido em 10/09/2026. Quem escolhe o caminho pela configuração é
    # o ``dicom_rede``; aqui não se decide protocolo.
    resultado = dicom_rede.trazer(pronto.plan_uid, destino)
    if not resultado.completo:
        # NÃO anota saída: fica pendente para a próxima rodada. É a mesma regra
        # da reserva que se anuncia — meio conjunto na pasta, marcado como
        # pronto, é pior que conjunto nenhum.
        contagem = (f"{len(resultado.arquivos)} arquivo(s), "
                    f"{resultado.falhas} falha(s)")
        rel.incompletos.append((pronto, contagem))
        _anotar_incompleto(pronto, f"o DICOM chegou pela metade: {contagem}")
        _LOG.warning("Conjunto incompleto de %s (%s): %s arquivo(s), "
                     "%s falha(s) — fica para a próxima rodada",
                     pronto.registro, pronto.plano, len(resultado.arquivos),
                     resultado.falhas)
        return
    preparo = _preparar(pronto)
    _recibo(pronto, destino, resultado, preparo)
    gatilho_registro.anotar_saida(pronto, str(destino), preparo)
    # A janela NÃO fecha aqui: ver :func:`_fechar_completas`.
    rel.exportados.append(pronto)


def _fechar_completas(pendentes: list, rel: Relatorio) -> None:
    """Fecha a janela da Documentação cujos planos saíram TODOS nesta rodada.

    Fechava a cada plano exportado, dentro do :func:`_buscar_um`. Num curso de
    dois planos — primário e boost —, o primeiro saía e fechava a janela; o
    segundo, travado no C-MOVE, ficava de fora do :func:`gatilho_registro.
    pendentes`, que só olha janela aberta. Nunca mais era tentado, e a linha da
    Fichinha ficava ``⚠ incompleta`` para sempre (achado em 11/09/2026).

    Basta olhar os pendentes DESTA rodada: o que já saiu antes a marca d'água
    tira da lista, e o ``gatilho_db`` só devolve o curso com todos os planos
    aprovados. Plano não tentado — varredura interrompida no meio — conta como
    não saído, e a janela fica para a próxima.
    """
    if not rel.exportados:
        return
    # Identidade do objeto, não ``chave()``: o ``rel.exportados`` guarda os
    # MESMOS objetos da lista de pendentes, e a comparação não passa a exigir
    # de quem finge um plano (o relógio, nos testes) a interface inteira.
    saiu = {id(p) for p in rel.exportados}
    por_instancia: dict = {}
    for p in pendentes:
        por_instancia.setdefault(p.instancia, []).append(id(p) in saiu)
    for instancia, saidas in por_instancia.items():
        if not all(saidas):
            continue
        try:
            gatilho_registro.fechar(instancia, MOTIVO_EXPORTADO)
        except Exception:  # noqa: BLE001
            # Janela que não fechou só volta a ser consultada: o que já saiu
            # a marca d'água tira da lista. Derrubar a rodada por isso não.
            _LOG.exception("Não deu para fechar a janela da instância %s",
                           instancia)


def _preparar(pronto) -> dict:
    """O que o físico vai precisar ao abrir o caso, conferido agora.

    **Não copia a pasta da simulação**: confere que ela existe e anota onde.
    Decisão do usuário em 11/09/2026. A cópia, gravada na pasta do plano,
    passaria na FRENTE do cadastro — ``capa_dados.setups_da_pasta`` lê a pasta
    carregada primeiro —, e fotos refeitas pelo dosimetrista depois da
    preparação sairiam antigas, sem aviso. Referenciada, a Capa lê no clique o
    cadastro de agora, pela ponte que já existia
    (``capa_dados.simulacao_do_paciente``).

    **Sem cadastro, o caso continua pronto**, com o aviso (também decisão de
    11/09): o físico monta o posicionamento à mão, como hoje. Mas "a raiz das
    simulações não é alcançada desta máquina" é OUTRO aviso. Um pede cadastrar
    o paciente; o outro, configurar a concentradora — e um python01 sem
    ``RAIZ_SIMULACOES`` no ``config_servico`` cairia no Documentos do usuário
    e diria "sem cadastro" para todo paciente, até o aviso virar ruído.

    Não levanta: a preparação não pode derrubar um plano que já chegou
    inteiro, e o que deu errado aqui vira aviso, que é o que a tela mostra.
    """
    preparo = {"estado": ESTADO_PRONTA, "simulacao": "", "avisos": []}
    try:
        # Tardio, como no ``capa_dados``: o ``simulacao`` puxa o ``capa_dados``
        # inteiro no topo, e o gatilho é importado pelo relógio só para saber
        # se está disponível — em toda estação, não só na concentradora.
        from isocentro.interface import simulacao

        raiz = simulacao.raiz()
        if not Path(raiz).is_dir():
            preparo["avisos"].append(
                f"a pasta das simulações ({raiz}) não é alcançada desta "
                "máquina: o cadastro de simulação não foi procurado")
            return preparo
        pasta = simulacao.procurar(pronto.paciente, pronto.registro)
    except Exception as exc:  # noqa: BLE001
        _LOG.exception("Falhou ao procurar a simulação de %s", pronto.registro)
        preparo["avisos"].append(
            f"não deu para procurar o cadastro de simulação: {exc}")
        return preparo
    if pasta:
        preparo["simulacao"] = pasta
    else:
        preparo["avisos"].append(AVISO_SEM_SIMULACAO)
    return preparo


def _anotar_incompleto(pronto, motivo: str) -> None:
    """Anota o motivo sem deixar a anotação derrubar a varredura.

    O registro mora num share; se ele falhar aqui, o plano continua pendente
    de qualquer forma (a marca d'água não foi gravada) e volta na rodada
    seguinte. Perder o MOTIVO é ruim; perder os outros dezenove planos da
    rodada por causa dele seria pior.
    """
    try:
        gatilho_registro.anotar_incompleto(pronto, motivo)
    except Exception:  # noqa: BLE001
        _LOG.exception("Não deu para anotar o incompleto de %s (%s)",
                       pronto.registro, pronto.plano)


def _recibo(pronto, destino: Path, resultado, preparo: dict | None = None) -> None:
    """Um JSON ao lado dos arquivos, dizendo de onde eles vieram.

    A pasta sozinha não diz quem aprovou o plano, quando, nem em que estado ele
    estava na hora — e é isso que alguém vai querer saber daqui a três meses,
    quando o plano no ARIA já tiver mudado de degrau. Mesmo espírito do
    ``registro_json``: o que sobra depois é o que se escreveu.
    """
    from isocentro.dados import registro_json

    registro_json._gravar_json(destino / "exportacao.json", {
        "registro": pronto.registro, "paciente": pronto.paciente,
        "curso": pronto.curso, "plano": pronto.plano,
        "plan_uid": pronto.plan_uid, "estado": pronto.estado,
        "revisao": pronto.revisao, "fracoes": pronto.fracoes,
        "aprovado_por": pronto.aprovado_por,
        "criado_em": str(pronto.criado_em or ""),
        "atividade": pronto.instancia,
        "modo": resultado.modo,
        "arquivos": [Path(a).name for a in resultado.arquivos],
        "preparo": dict(preparo or {}),
        "exportado_em": datetime.now().isoformat(timespec="seconds"),
    })


def _limpar(raiz: Path, agora=None) -> list:
    """Apaga da temporária o que já não serve. Não levanta: quem chama é o relógio.

    **Roda aqui, na concentradora, e não na estação que liberou** (decisão do
    usuário em 14/09/2026): esta é a máquina dona da pasta — a do físico pode
    nem ter escrita no share —, e uma falha de permissão viraria modal em cima
    da impressão que acabou de sair. Aqui ela vira uma linha no histórico.

    A marca só é gravada quando a pasta saiu de fato. Falhar no meio deixa o
    caso para a rodada seguinte, que é o que se quer: arquivo aberto por
    alguém, share fora do ar, e o conjunto ainda está lá.
    """
    feitos: list = []
    try:
        alvos = gatilho_registro.a_limpar(agora=agora)
    except Exception:  # noqa: BLE001
        _LOG.exception("Não deu para saber o que limpar da temporária")
        return feitos
    for alvo in alvos:
        fora = [p for p in alvo["pastas"] if not _dentro_da_raiz(p, raiz)]
        if fora:
            # Destino anotado quando a pasta de exportação era OUTRA (variável
            # de estação trocada, share remontado noutra letra). Apagar fora da
            # raiz de agora é apagar o que esta varredura não é dona de apagar,
            # e apagar não se desfaz. Fica para quem configurou.
            _LOG.warning("Limpeza ignorou a instância %s: pasta fora de %s — %s",
                         alvo["instancia"], raiz, ", ".join(fora))
            continue
        if not _apagar(alvo["pastas"], raiz):
            continue
        try:
            gatilho_registro.anotar_limpeza(alvo["instancia"], alvo["pastas"],
                                            alvo["motivo"])
        except Exception:  # noqa: BLE001
            # Apagou e não anotou: a rodada seguinte volta aqui, não acha mais
            # as pastas (o ``_apagar`` trata ausente como feito) e grava a
            # marca. Errado seria anotar antes de apagar.
            _LOG.exception("Temporária apagada sem anotar a limpeza (%s)",
                           alvo["instancia"])
            continue
        feitos.append(alvo)
    return feitos


def _apagar(pastas: list, raiz: Path) -> bool:
    """Apaga as pastas dos planos, e depois as mães que ficaram vazias.

    A pasta do **plano**, nunca a do curso: a do curso pode guardar o plano que
    ainda não veio inteiro — o incompleto não tem destino anotado, e sairia
    junto sem ninguém saber. As mães vazias saem depois para a temporária não
    virar um cemitério de pastas com nome de paciente.

    Pasta que já não existe conta como feita: apagada à mão, ou anotada numa
    rodada que caiu depois do ``rmtree``. O desfecho é o mesmo.
    """
    inteiro = True
    for pasta in pastas:
        alvo = Path(pasta)
        try:
            if alvo.is_dir():
                shutil.rmtree(alvo)
        except OSError:
            _LOG.exception("Não deu para apagar %s; fica para a próxima rodada",
                           alvo)
            inteiro = False
            continue
        _apagar_maes_vazias(alvo.parent, raiz)
    return inteiro


def _apagar_maes_vazias(pasta: Path, raiz: Path) -> None:
    """Sobe apagando pasta vazia até a raiz — que nunca é apagada."""
    atual = Path(pasta)
    while _dentro_da_raiz(atual, raiz):
        try:
            atual.rmdir()   # OSError se tiver qualquer coisa dentro
        except OSError:
            return
        atual = atual.parent


def _dentro_da_raiz(pasta, raiz) -> bool:
    """A pasta está mesmo DENTRO da temporária de agora?

    A própria raiz responde falso: é a trava que impede uma marca estranha de
    mandar apagar a pasta de exportação inteira.
    """
    try:
        a = os.path.normcase(os.path.abspath(str(pasta)))
        r = os.path.normcase(os.path.abspath(str(raiz)))
        return a != r and os.path.commonpath([a, r]) == r
    except ValueError:   # unidades diferentes no Windows
        return False


def _fechar_vencidas(agora=None) -> list:
    """Fecha as janelas que passaram do prazo, nomeando o motivo.

    Elas já não aparecem em :func:`gatilho_registro.abertas` — o prazo as
    esconde. Fechá-las explicitamente é o que faz a diferença entre "sumiu" e
    "venceu sem plano aprovado", e é a segunda que alguém precisa ler para
    descobrir que um caso ficou pelo caminho.
    """
    agora = agora or datetime.now()
    vivas = {e["instancia"] for e in gatilho_registro.abertas(agora).values()}
    vencidas = []
    for chave, entrada in gatilho_registro.ler()["janela"].items():
        if entrada.get("fechado_em") or int(chave) in vivas:
            continue
        gatilho_registro.fechar(int(chave), MOTIVO_VENCIDO)
        vencidas.append(int(chave))
    return vencidas
