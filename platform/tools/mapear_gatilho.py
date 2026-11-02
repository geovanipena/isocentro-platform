r"""O GATILHO da exportação automática: o que o DW sabe de curso e de plano.

O desenho de 02/09/2026 quer exportar imagem e plano sozinho quando três coisas
valem ao mesmo tempo — **Documentação disponível**, **último curso ativo** e
**plano aprovado**. A primeira já tem resposta conferida (``atividades_db``, com
``VERIFICADO_EM`` preenchido). As outras duas não têm resposta nenhuma dentro do
código, e o que existe PARECE resposta:

* de curso, o ``capa_db._SQL_CURSO`` traz o mais RECENTE (``CourseStartDateTime
  DESC``), que não é o mesmo que ATIVO — nada ali olha estado nem encerramento;
* de aprovação, o ``capa_db`` traz ``rx.ApprovedOn``/``ApprovedBy``, que são da
  **prescrição** — o ato do médico. Plano aprovado é o da física, no Eclipse, e
  vem depois. Amarrar a exportação na prescrição pegaria plano em rascunho.

Então isto não escreve consulta de curso nem de plano: PERGUNTA ao catálogo que
colunas existem, quais delas estão realmente preenchidas, e que valores elas
tomam. É da saída que sai a consulta definitiva, com os nomes reais — o mesmo
caminho do ``tools/atividades.py``, e pela mesma razão: consulta montada sobre
chute devolve linha plausível e errada, que aqui viraria plano exportado do
curso errado.

A terceira pergunta é a que decide o desenho, e é fácil não fazer: **dá para
chegar num plano que ainda não foi tratado?** Todo caminho até ``DWH.DimPlan``
neste repositório passa por ``FactTreatmentHistory`` (``th.DimPlanID``, ver
``tratamento_db``), que é histórico de sessão APLICADA. Se for o único caminho,
o DW não enxerga plano aprovado e ainda não tratado — que é exatamente o caso
que a automação existe para pegar — e o filtro "plano aprovado" tem de sair do
DW e ir para o ``ApprovalStatus`` do próprio RTPLAN, no C-FIND. O passo do
:func:`passo_alcance_do_plano` responde isso.

**A rodada de 02/09/2026 respondeu, e a hipótese pessimista estava errada:**
``DimPlan`` tem ``DimCourseID``, ``DimLookupID_PlanStatus`` e — o achado que
muda o desenho — ``PlanUID`` (nvarchar 64), que é o SOPInstanceUID do RTPLAN.
O DW consegue, portanto, entregar o UID exato do plano para um C-FIND/C-MOVE
em nível de instância, em vez de casar por paciente e data. O que a rodada
NÃO trouxe foram os valores de estado: ``DimCourse`` (30.677 linhas) e
``DimPlan`` (74.171) passaram do limite de catálogo e saíram sem amostra — é
para isso que serve o ``--amostrar``.

    python tools/mapear_gatilho.py                    # os quatro passos
    python tools/mapear_gatilho.py -o achados.txt     # e grava, para trazer
    python tools/mapear_gatilho.py --paciente 9000019ANA   # o retrato de um caso
    python tools/mapear_gatilho.py --consulta          # o gatilho_db de verdade

De máquina fora do domínio (SSPI recusado), pelo ``mapear_gatilho.bat`` com o
``runas /netonly`` — a mesma exigência do ``atividades.py`` e do
``gravar_banco.py``.

**Só leitura.** As travas são as do ``atividades.py``, importadas de lá em vez
de copiadas: coluna que cheira a identidade ou a texto livre não é amostrada, e
tabela grande sai com contagem e catálogo, sem ser varrida. Sem ``--paciente``
nenhuma linha de paciente é lida; com ele, lê-se UM, que é o que basta para
conferir.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))
# O próprio ``tools``: é de onde vem o ``atividades``. Sem isto, rodar o script
# de outra pasta não acha o irmão e quebra no import.
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import atividades as _at  # noqa: E402

# Pedaços de nome que denunciam ESTADO de curso. "complete"/"end"/"close" estão
# aqui porque num DW o estado costuma ser a data de encerramento e não uma
# palavra: curso sem ``CourseCompletedDateTime`` é curso aberto, e essa é a
# forma mais provável da resposta.
PADROES_ESTADO = ("status", "state", "active", "complete", "closed", "close",
                  "end", "stop", "suspend", "cancel", "intent")

# E de APROVAÇÃO de plano. "review"/"verif" entram porque o Eclipse tem mais de
# um degrau (planning approved, treatment approved) e eles não se chamam
# "approved" em toda versão.
PADROES_APROVACAO = ("approv", "status", "review", "verif", "sign", "lock",
                     "release", "state")

# E de VÍNCULO: é o que responde se a atividade sabe de que curso ela é. "ser"
# entra por causa das chaves cruas do ARIA (``ctrPlanSetupSer``), que são as que
# casam com o DICOM.
PADROES_VINCULO = ("course", "plan", "patient", "ser", "uid")

# As três tabelas, e o que se quer de cada uma. A ordem é a das perguntas.
ALVOS = [
    ("DWH.DimCourse", PADROES_ESTADO,
     "o curso está ATIVO? (hoje só se sabe qual é o mais recente)"),
    ("DWH.DimPlan", PADROES_APROVACAO,
     "o plano está APROVADO? (hoje só se lê o PlanSetupId)"),
    ("DWH.DimActivityTransaction", PADROES_VINCULO,
     "a atividade carrega o curso? (senão, casa só por paciente e data)"),
    # Apareceu na varredura de 02/09/2026 e o nome diz o que se procura. Entra
    # como alvo porque view não é barrada pela trava de tamanho — mas o que ela
    # RESOLVE (paciente → plano sem passar por tratamento) só o catálogo dela
    # dirá.
    ("DWH.GetPatientPlan", PADROES_VINCULO + PADROES_APROVACAO,
     "dá para ir do paciente ao plano sem passar por sessão aplicada?"),
]

# Quantos valores distintos mostrar por coluna candidata.
AMOSTRA = 25


def _partes(tabela: str) -> tuple:
    esquema, _, nome = tabela.partition(".")
    return esquema, nome


def _casa(nome: str, padroes) -> bool:
    baixo = nome.lower()
    return any(p in baixo for p in padroes)


def _preenchimento(cx, esquema, tabela, coluna):
    """Quantas linhas têm valor nesta coluna — e por que isso não dá para pular.

    Coluna que existe no catálogo e está 100% NULA é a armadilha desta busca:
    ela entra na consulta, o SQL roda, e o filtro simplesmente não filtra nada.
    O nome no ``INFORMATION_SCHEMA`` prova que a coluna existe, nunca que ela é
    usada NESTA instalação do ARIA.
    """
    r = _at._linhas(cx, f"SELECT COUNT(*), COUNT([{coluna}]) "
                        f"  FROM [{esquema}].[{tabela}]")
    if not isinstance(r, list) or not r:
        return None
    return int(r[0][0]), int(r[0][1])


def _pelo_lookup(cx, esquema, tabela, coluna):
    """O estado quando ele é uma CHAVE para ``DimLookup``, não uma palavra.

    É assim que o ``capa_db._SQL_CURSO`` lê a intenção do curso, e é a forma que
    o DW da Varian usa para quase todo vocabulário. Amostrar a coluna crua
    devolveria uma lista de inteiros, que não responde nada. O ``<> 0`` é o
    mesmo do ``capa_db``: zero ali é o "não há", não um valor.
    """
    r = _at._linhas(cx, f"SELECT DISTINCT TOP ({AMOSTRA}) "
                        f"       l.LookupDescriptionENU, l.LookupDescriptionPTB "
                        f"  FROM [{esquema}].[{tabela}] t "
                        f"  JOIN DWH.DimLookup l ON l.DimLookupID = t.[{coluna}] "
                        f" WHERE t.[{coluna}] <> 0 "
                        f" ORDER BY l.LookupDescriptionENU")
    if not isinstance(r, list):
        return None
    return [(str(a or "").strip(), str(b or "").strip()) for a, b in r]


def passo_tabela(cx, tabela, padroes, pergunta, saida, amostrar=()):
    """Uma tabela: o catálogo inteiro, e em detalhe só o que casa a pergunta."""
    esquema, nome = _partes(tabela)
    saida(f"\n\n===== {tabela} =====")
    saida(f"  pergunta: {pergunta}")

    colunas = _at._colunas(cx, esquema, nome)
    if not isinstance(colunas, list) or not colunas:
        saida(f"  NÃO LI o catálogo: {str(colunas)[:200]}")
        return
    quantas, como = _at._quantas_linhas(cx, esquema, nome)
    saida(f"  {len(colunas)} coluna(s), {quantas} linha(s) ({como})")

    saida("\n  -- todas as colunas --")
    for col, tipo, largura in colunas:
        marca = "  <<<" if _casa(col, padroes) else ""
        largo = f"({largura})" if largura not in (None, 0) else ""
        saida(f"    {col}  {tipo}{largo}{marca}")

    # Acima do limite a tabela é FATO. A trava é a do ``atividades.py``: um
    # DISTINCT com ORDER BY em tabela de milhões é varredura no servidor da
    # clínica em horário de expediente.
    # A trava de tamanho é a do ``atividades.py``, e ela é boa para o FATO. Foi
    # calibrada para o catálogo de atividades, porém, e na primeira rodada real
    # (02/09/2026) barrou ``DimCourse`` (30.677) e ``DimPlan`` (74.171) — que
    # são dimensões, e são exatamente onde moram os dois estados procurados. Daí
    # o ``--amostrar`` ser por TABELA e não um interruptor: um ``DISTINCT TOP``
    # numa dimensão de 74 mil linhas é barato, no fato de 1,89 milhão não é, e
    # um interruptor único obrigaria a escolher entre não ver nada e varrer o
    # fato.
    grande = quantas is not None and quantas > _at.LIMITE_DE_CATALOGO
    pedida = any(p.lower() in nome.lower() for p in amostrar)
    if grande and not pedida:
        saida(f"\n  -- tabela grande ({quantas} linhas): só o catálogo. "
              f"Para amostrar esta, --amostrar {nome} --")
        return

    saida("\n  -- as candidatas, em detalhe --")
    achou = False
    for col, tipo, largura in colunas:
        if not _casa(col, padroes):
            continue
        achou = True
        cheio = _preenchimento(cx, esquema, nome, col)
        if cheio is None:
            saida(f"    {col}: não deu para contar o preenchimento")
            continue
        total, cheias = cheio
        pct = (100.0 * cheias / total) if total else 0.0
        saida(f"    {col}  [{tipo}]  {cheias}/{total} preenchidas ({pct:.0f}%)")
        if cheias == 0:
            # Vale dizer em voz alta: é a coluna que entraria na consulta e não
            # filtraria coisa nenhuma.
            saida("        VAZIA nesta instalação — não serve de filtro.")
            continue
        if col.lower().startswith("dimlookupid"):
            vistos = _pelo_lookup(cx, esquema, nome, col)
            if vistos:
                for enu, ptb in vistos:
                    saida(f"        {enu}" + (f"  /  {ptb}" if ptb else ""))
                continue
        if _at._amostravel(col, tipo, largura):
            for v in (_at._amostra(cx, esquema, nome, col, AMOSTRA) or []):
                saida(f"        {v}")
        elif tipo.lower() in _at.TIPOS_DE_DATA:
            # Data não se amostra: o que interessa é a FAIXA, e ela diz se a
            # coluna ainda é alimentada ou parou numa migração antiga.
            r = _at._linhas(cx, f"SELECT MIN([{col}]), MAX([{col}]) "
                                f"  FROM [{esquema}].[{nome}]")
            if isinstance(r, list) and r:
                saida(f"        de {r[0][0]} até {r[0][1]}")
    if not achou:
        saida("    nenhuma coluna casou os padrões — ver a lista acima.")


def passo_alcance_do_plano(cx, saida):
    """A pergunta que decide o desenho: dá para chegar num plano NÃO tratado?

    Todo caminho até ``DimPlan`` neste repositório passa por
    ``FactTreatmentHistory``, que é sessão aplicada. Se ``DimPlan`` não tiver
    coluna de paciente nem de curso, e nenhum outro fato ligar plano a paciente
    sem passar por tratamento, então o DW só enxerga o plano DEPOIS da primeira
    sessão — e o filtro "plano aprovado" não pode morar aqui.
    """
    saida("\n\n===== O plano ainda não tratado é alcançável? =====")
    colunas = _at._colunas(cx, "DWH", "DimPlan")
    if not isinstance(colunas, list) or not colunas:
        saida(f"  NÃO LI DWH.DimPlan: {str(colunas)[:200]}")
        return
    diretas = [c for c, _t, _l in colunas
               if c.lower() in ("dimpatientid", "dimcourseid",
                                "ctrpatientser", "ctrcourseser")]
    if diretas:
        saida(f"  DimPlan liga direto por: {', '.join(diretas)}")
        saida("  => o filtro de aprovação PODE morar no DW.")
    else:
        saida("  DimPlan NÃO tem coluna de paciente nem de curso.")
        saida("  => o único caminho conhecido é FactTreatmentHistory.DimPlanID,")
        saida("     que é sessão APLICADA. Plano aprovado e ainda não tratado")
        saida("     não seria visto — o filtro tem de ir para o ApprovalStatus")
        saida("     do RTPLAN, no C-FIND.")

    # E quem MAIS aponta para plano: se existir outro fato ligando plano a
    # paciente, ele é o caminho — e não apareceria olhando só a DimPlan.
    saida("\n  -- quem mais tem coluna de plano --")
    r = _at._linhas(cx,
                    "SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME "
                    "  FROM INFORMATION_SCHEMA.COLUMNS "
                    " WHERE LOWER(COLUMN_NAME) LIKE '%plan%' "
                    " ORDER BY TABLE_NAME, COLUMN_NAME")
    if isinstance(r, list):
        for esquema, tab, col in r:
            saida(f"    {esquema}.{tab}.{col}")
    else:
        saida(f"    não deu: {str(r)[:200]}")


def passo_ponte_atividade_curso(cx, saida):
    """Quem sabe, ao mesmo tempo, de ATIVIDADE e de CURSO.

    A primeira rodada (02/09/2026) mostrou que ``DimActivityTransaction`` não
    tem coluna de curso nenhuma nas 56 — nem ``DimCourseID``, nem
    ``ctrCourseSer``. As de "plan" que ela tem são de MedOnc (quimioterapia),
    não do plano de radioterapia.

    Isso deixa a exportação sem saber de que curso é a Documentação que abriu, e
    num retratamento (curso 2 aberto, curso 1 ainda com pendência) casar os dois
    pelo paciente escolhe o errado, calado. Então a pergunta vira: existe alguma
    tabela que ligue as duas pontas? Se não existir, o filtro tem de ser mais
    estreito — nunca mais esperto.
    """
    saida("\n\n===== Existe ponte entre ATIVIDADE e CURSO? =====")
    r = _at._linhas(cx,
                    "SELECT c1.TABLE_SCHEMA, c1.TABLE_NAME "
                    "  FROM INFORMATION_SCHEMA.COLUMNS c1 "
                    "  JOIN INFORMATION_SCHEMA.COLUMNS c2 "
                    "    ON c2.TABLE_SCHEMA = c1.TABLE_SCHEMA "
                    "   AND c2.TABLE_NAME = c1.TABLE_NAME "
                    " WHERE LOWER(c1.COLUMN_NAME) LIKE '%activit%' "
                    "   AND LOWER(c2.COLUMN_NAME) LIKE '%course%' "
                    " GROUP BY c1.TABLE_SCHEMA, c1.TABLE_NAME "
                    " ORDER BY c1.TABLE_NAME")
    if not isinstance(r, list):
        saida(f"  não deu: {str(r)[:200]}")
        return
    if not r:
        saida("  NENHUMA tabela tem as duas coisas.")
        saida("  => a atividade não sabe de que curso ela é. O filtro tem de")
        saida("     ser mais estreito (paciente + janela de data), nunca mais")
        saida("     esperto.")
        return
    for esquema, tab in r:
        saida(f"    {esquema}.{tab}")


def passo_paciente(cx, registro, saida):
    """O retrato de UM caso: os cursos dele, como o banco os descreve.

    Sem isto o relatório é catálogo — diz que a coluna existe e que valores ela
    toma no serviço inteiro, não o que ela diz sobre um paciente com
    Documentação aberta. É a diferença entre "a coluna existe" e "a coluna
    responde à minha pergunta", e foi essa diferença que pegou os dois defeitos
    do ``atividades_db`` em 02/09/2026.

    ``SELECT *`` de propósito: o que se quer aqui é ver o que um filtro
    escondeu, e escolher colunas seria escolher antes de saber.
    """
    saida(f"\n\n===== O caso {registro} =====")
    r = _at._linhas(cx, "SELECT DimPatientID FROM DWH.DimPatient "
                        " WHERE PatientId = ?", registro)
    if not isinstance(r, list) or not r:
        saida(f"  registro não achado ({str(r)[:160]})")
        return
    dim = int(r[0][0])
    saida(f"  DimPatientID = {dim}")

    cur = cx.cursor()
    try:
        cur.execute("SELECT * FROM DWH.DimCourse WHERE DimPatientID = ? "
                    " ORDER BY CourseStartDateTime DESC", dim)
    except Exception as exc:  # noqa: BLE001
        saida(f"  não deu para ler os cursos: {exc}")
        return
    nomes = [d[0] for d in cur.description]
    for i, linha in enumerate(cur.fetchall(), 1):
        saida(f"\n  -- curso {i} --")
        for nome, valor in zip(nomes, linha):
            if valor is None or str(valor).strip() in ("", "NA"):
                continue
            saida(f"    {nome:<40} {valor}")

    passo_planos_do_paciente(cx, dim, saida)


def passo_planos_do_paciente(cx, dim, saida):
    """Os planos do paciente, com estado e UID — a premissa do desenho inteiro.

    A automação supõe que, quando a Documentação abre, o plano já está aprovado.
    Isso é suposição de FLUXO: a tarefa abrir significa que alguém PODE
    documentar, não que a física aprovou. Só o caso real diz, e é esta consulta
    que o mostra — o estado de cada plano do paciente que tem a Documentação
    aberta agora.

    Ao contrário do resto do arquivo, esta consulta é ESCRITA, não descoberta.
    Pode ser: os nomes saíram do catálogo medido em 02/09/2026 —
    ``DWH.GetPatientPlan`` tem exatamente ``DimPatientID`` e ``DimPlanID``, e é
    o caminho do paciente ao plano que NÃO passa por sessão aplicada.
    """
    saida("\n  -- os planos (via GetPatientPlan, sem passar por tratamento) --")
    r = _at._linhas(cx,
                    "SELECT p.DimCourseID, p.PlanSetupId, p.PlanSetupName, "
                    "       l.LookupDescriptionENU, l.LookupDescriptionPTB, "
                    "       p.PlanRevision, p.NoFractionsPlanned, "
                    "       p.StatusUserName, p.CreationDate, p.PlanUID "
                    "  FROM DWH.GetPatientPlan gp "
                    "  JOIN DWH.DimPlan p ON p.DimPlanID = gp.DimPlanID "
                    "  LEFT JOIN DWH.DimLookup l "
                    "         ON l.DimLookupID = p.DimLookupID_PlanStatus "
                    "        AND l.DimLookupID <> 0 "
                    " WHERE gp.DimPatientID = ? "
                    " ORDER BY p.DimCourseID DESC, p.PlanSetupId", dim)
    if not isinstance(r, list):
        saida(f"    não deu: {str(r)[:200]}")
        return
    if not r:
        saida("    NENHUM plano — e o paciente tem Documentação aberta.")
        saida("    => a premissa do desenho não se sustenta neste caso.")
        return
    for linha in r:
        (curso, setup, nome, enu, ptb, revisao, fracoes,
         quem, criado, uid) = linha
        # ``PlanSetupName`` veio VAZIO nos dois planos do caso real de
        # 02/09/2026 — quem identifica o plano é o ``PlanSetupId``. Imprimir
        # "(None)" ao lado de cada linha só ensinaria a ignorar o campo.
        saida(f"    curso {curso}  {setup}" + (f"  ({nome})" if nome else ""))
        saida(f"        estado    {enu}" + (f"  /  {ptb}" if ptb else ""))
        saida(f"        revisão   {revisao}   frações {fracoes}")
        saida(f"        estado por {quem}, criado {criado}")
        # O UID inteiro, não um pedaço: é ele que vai no C-MOVE, e um UID
        # truncado no relatório vira um C-MOVE que não acha nada.
        saida(f"        PlanUID   {uid}")


def passo_consulta(saida) -> None:
    """Roda o ``gatilho_db`` de verdade — é o teste dele contra o banco.

    Os passos de cima descobrem o que EXISTE no DW; este pergunta o que a
    consulta RESPONDE, que é outra coisa. É a saída daqui que se compara, plano
    a plano, com o que o ARIA mostra para os mesmos pacientes — e é dessa
    comparação que sai a data do ``VERIFICADO_EM``.

    Imprime as constantes valendo antes do resultado. Sem elas a lista não é
    conferível: "faltou o plano do fulano" tem resposta diferente se o filtro
    era ``Planning Approved`` ou ``Treatment Approved``, e quem confere não tem
    como saber qual estava valendo naquela rodada.
    """
    import time

    from isocentro.banco import gatilho_db

    saida("\n\n===== A consulta do gatilho_db =====")
    saida(f"  APROVADOS          {', '.join(gatilho_db.APROVADOS)}")
    saida(f"  CURSO_ATIVO        {gatilho_db.CURSO_ATIVO}")
    saida(f"  UM_PLANO_POR_CURSO {gatilho_db.UM_PLANO_POR_CURSO}")
    saida(f"  VERIFICADO_EM      {gatilho_db.VERIFICADO_EM or '(nunca)'}")
    if not gatilho_db.disponivel():
        # Não impede de rodar — o portão é da TELA. Mas quem lê o relatório
        # precisa saber que o app, hoje, não mostraria nada disto.
        saida(f"  portão FECHADO: {gatilho_db.motivo_indisponivel()}")

    saida("\n  -- onde a lista morre (os degraus) --")
    inicio = time.perf_counter()
    try:
        conta = gatilho_db.porque_vazio()
    except Exception as exc:  # noqa: BLE001
        saida(f"    NÃO deu: {exc}")
        return
    for chave, valor in conta.items():
        saida(f"    {chave:<20} {valor}")

    # A parte que a primeira rodada não tinha, e sem a qual a conferência não
    # fecha: UMA LINHA POR DOCUMENTAÇÃO ABERTA, tenha ela produzido plano ou
    # não. A lista de vencedores responde "estes estão certos?"; a pergunta que
    # decide se a automação pode ser ligada é "faltou alguém?", e ausência não
    # aparece numa lista de quem saiu.
    saida("\n  -- cada Documentação aberta, uma a uma --")
    saida("     (compare ESTA lista com o quadro do ARIA: nome por nome)")
    try:
        dossies = gatilho_db.conferencia()
    except Exception as exc:  # noqa: BLE001
        # NÃO interrompe o relatório: este bloco é diagnóstico, e a lista de
        # planos abaixo é o que se leva para o ARIA. Perder as duas por causa
        # de uma seria trocar meia resposta por nenhuma.
        saida(f"    NÃO deu: {exc}")
        dossies = []
    for d in dossies:
        marca = "SAI " if d.saiu else "--  "
        saida(f"\n    {marca}{d.registro}  {d.paciente}")
        saida(f"        degrau    {d.degrau}   (atividade {d.instancia})")
        # ``aberto``, e não ``inicio``: este laço roda no meio da medição de
        # tempo, e a primeira versão sobrescreveu o ``inicio`` do cronômetro —
        # o relatório morria na última linha, DEPOIS de imprimir tudo.
        for dim, curso, aberto, estado, intencao, escolhido in d.cursos:
            seta = "→" if escolhido else " "
            quando = f"{aberto:%d/%m/%Y}" if aberto else "sem data"
            # A intenção VAZIA é o que marca o curso de QA, e é ela que explica
            # por que um curso perdeu para outro mais antigo. Sem isto no
            # papel, "escolheu o de 03/09" parece a regra da data — e foi assim
            # que o QA passou despercebido na rodada de 04/09/2026.
            fim = intencao or "SEM INTENÇÃO (QA?)"
            saida(f"        {seta} curso  {curso} ({dim}) {estado}, "
                  f"aberto {quando} — {fim}")
        if not d.cursos:
            saida("           curso  NENHUM no banco")
        # O UID inteiro sai no bloco de baixo, dos prontos: aqui ele seria
        # ruído em cima do que se está conferindo, que é o ESTADO de cada plano.
        for setup, _uid, rev, estado, quem, criado, sai in d.planos:
            visto = "sai" if sai else "não"
            quando = f"{criado:%d/%m %H:%M}" if criado else "sem data"
            saida(f"           plano  {setup}  rev {rev}  {estado}  "
                  f"[{visto}]  por {quem}, {quando}")
        if d.cursos and not d.planos:
            saida("           plano  NENHUM no curso escolhido")

    saida("\n  -- os planos prontos --")
    try:
        prontos = gatilho_db.prontos()
    except Exception as exc:  # noqa: BLE001
        saida(f"    NÃO deu: {exc}")
        return
    gasto = time.perf_counter() - inicio
    if not prontos:
        saida("    nenhum. Ver os degraus acima para saber ONDE parou.")
    for p in prontos:
        saida(f"\n    {p.registro}  {p.paciente}")
        saida(f"        curso     {p.curso} (DimCourseID {p.dim_curso})")
        saida(f"        plano     {p.plano}   revisão {p.revisao}   "
              f"frações {p.fracoes}")
        saida(f"        estado    {p.estado}, por {p.aprovado_por}")
        saida(f"        criado    {p.criado_em}")
        saida(f"        atividade {p.instancia}")
        # Inteiro, sempre: é ele que vai no C-MOVE, e UID truncado no relatório
        # vira um C-MOVE que não acha nada.
        saida(f"        PlanUID   {p.plan_uid}")
    # O tempo entra no relatório porque ele é metade do ``VERIFICADO_EM``: uma
    # consulta certa que leva 40 s não cabe na thread da tela, e isso só se
    # descobre medindo contra o banco de verdade.
    saida(f"\n  {len(prontos)} plano(s) pronto(s), em {gasto:.1f} s "
          f"(o limite do capa_db é 6 s).")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="O que o variandw sabe de curso ativo e plano aprovado "
                    "(só leitura).")
    p.add_argument("--paciente", default="",
                   help="o registro de um caso com Documentação aberta, para "
                        "ver os cursos dele por inteiro")
    p.add_argument("--amostrar", action="append", default=None,
                   metavar="TABELA",
                   help="amostra esta tabela mesmo acima do limite de catálogo; "
                        "pode repetir. Vale para DIMENSÃO (DimCourse, DimPlan); "
                        "num FATO de milhões é varredura no servidor clínico")
    p.add_argument("--consulta", action="store_true",
                   help="roda o gatilho_db de verdade (o que a consulta "
                        "RESPONDE) em vez de descobrir o que existe no DW — "
                        "é o teste dela contra o banco")
    p.add_argument("-o", "--saida", default="",
                   help="grava o relatório neste arquivo, além de imprimir")
    a = p.parse_args(argv)

    linhas: list = []

    def saida(texto=""):
        print(texto)
        linhas.append(texto)

    # A gravação embrulha o ``_conectar`` junto, pela razão que custou uma ida e
    # volta em 01/09/2026: sem conexão, o arquivo pedido no ``-o`` não nascia, e
    # a recusa ficava só no console do ``runas`` — que fecha. Arquivo pedido é
    # arquivo entregue, mesmo (ainda mais) quando deu errado.
    codigo = 2
    try:
        cx = _at._conectar(saida, "mapear_gatilho.bat")
        if cx is None:
            return codigo
        saida(f"Servidor : {_at.capa_db.servidor()}")
        if a.consulta:
            passo_consulta(saida)
            if a.paciente:
                passo_paciente(cx, a.paciente.strip(), saida)
            codigo = 0
            return codigo
        for tabela, padroes, pergunta in ALVOS:
            passo_tabela(cx, tabela, padroes, pergunta, saida,
                         tuple(a.amostrar or ()))
        passo_alcance_do_plano(cx, saida)
        passo_ponte_atividade_curso(cx, saida)
        if a.paciente:
            passo_paciente(cx, a.paciente.strip(), saida)
        codigo = 0
    finally:
        if a.saida:
            destino = _at._destino_livre(Path(a.saida))
            destino.write_text("\n".join(linhas) + "\n", encoding="utf-8")
            print(f"\nGravado em {destino}")
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
