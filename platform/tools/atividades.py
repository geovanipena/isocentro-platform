r"""Descobre as ATIVIDADES do ARIA no ``variandw`` — o catálogo, não o paciente.

Por que existe: o ISOCENTRO não lê atividade nenhuma hoje. As consultas do
:mod:`capa_db` e do :mod:`tratamento_db` cobrem paciente, curso, prescrição,
diagnóstico, médico, máquina e histórico de tratamento — nada de ``Activity``.
Então "quais atividades de Documentação existem para o físico" não tem resposta
dentro do código: só o banco sabe, e o nome das tabelas de atividade no DW muda
de versão para versão do ARIA. Chutar ``DWH.DimActivity`` e escrever a consulta
por cima do chute daria uma lista que parece certa e não é — a pior espécie.

Então isto NÃO tem SQL de atividade escrito: ele PERGUNTA ao catálogo do banco
(``INFORMATION_SCHEMA``) que tabelas existem, que colunas elas têm, e só então
procura a palavra. A saída é um relatório para ler — é dela que sai a consulta
definitiva, depois, com os nomes reais.

    python tools/atividades.py                 # o relatório inteiro
    python tools/atividades.py -o achados.txt  # e grava, para trazer de volta
    python tools/atividades.py --tabela DimActivity      # só uma, em detalhe
    python tools/atividades.py --palavra ocumenta        # procurar outra coisa
    python tools/atividades.py --consulta --palavra Alta # o catálogo, PAREADO

De máquina fora do domínio (SSPI recusado), pelo ``atividades.bat`` com o
``runas /netonly`` — a mesma exigência do ``gravar_banco.py``.

**Só leitura, e sem dado de paciente.** Duas travas de propósito, porque isto
roda contra o sistema clínico em horário de expediente:

* coluna que cheira a identidade ou a texto livre não é amostrada (ver
  ``FORA_DA_AMOSTRA``): o que se quer é o catálogo — "Documentação de
  tratamento" —, nunca o que foi escrito sobre alguém;
* a busca pela palavra só varre tabela PEQUENA. Um ``LIKE`` com curinga dos
  dois lados numa Fact de milhões de linhas é varredura de tabela inteira no
  servidor da clínica, e o catálogo de atividades mora na dimensão, não no
  fato.
"""
from __future__ import annotations

import argparse
import datetime
import getpass
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from isocentro.banco import banco_local  # noqa: E402
from isocentro.banco import capa_db  # noqa: E402

# Pedaços de nome que denunciam tabela de atividade no DW do ARIA. Vale para
# TABELA e para COLUNA: se a tabela se chamar outra coisa nesta versão, é a
# coluna ``...ActivityCode`` que aponta onde ela está.
PADROES = ("activit", "task", "carepath")

# Quando o DW foi CARREGADO — a segunda pergunta, e ela decide a ideia inteira
# de mostrar atividade pendente na abertura do app. O ``variandw`` é armazém,
# não o banco vivo do ARIA: se a carga é noturna, uma atividade concluída de
# manhã continua "pendente" até a noite, e o painel mandaria o físico refazer o
# que ele já fez. Achar a tabela de carga é o que responde isso sem cronômetro.
PADROES_CARGA = ("dwload", "etl", "refresh", "loadlog", "audit", "batch")

# Onde o DW guarda GENTE. É aqui que se confere se o login do app existe do
# outro lado — e o ARIA e o ISOCENTRO usarem o mesmo login (dito em
# 01/09/2026) não dispensa a conferência: dois dos físicos cadastrados têm
# login FORA do padrão ``nome.sobrenome`` (``adriano``, ``isabela``), e é
# exatamente para esses que a lista voltaria vazia — que se lê como "estou em
# dia", não como "não te achei".
PADROES_PESSOA = ("resource", "user", "staff", "employee", "login", "doctor")

# Sem o Ç e sem o Ã de propósito: "ocumenta" casa "Documentação", "Documentacao"
# e "Documentation" de uma vez, e não depende do collation do servidor.
PALAVRA = "ocumenta"

# Tipos de data, para o ``--frescor``: o MAX de uma coluna dessas diz até quando
# o DW enxerga.
TIPOS_DE_DATA = ("date", "datetime", "datetime2", "smalldatetime")

# Acima disto a tabela é FATO (uma linha por paciente por atividade): entra no
# relatório com a contagem e as colunas, mas não é amostrada nem varrida.
LIMITE_DE_CATALOGO = 20000

# Quantos valores distintos mostrar por coluna.
AMOSTRA = 40

# Colunas que não são amostradas. "patient"/"birth"/"photo" são identidade;
# "comment"/"note"/"remark" são texto livre, onde vai parar o que alguém
# escreveu sobre um paciente. Repare que o filtro é por PEDAÇO de nome e não
# pode conter "name": ``ActivityName`` é exatamente o que se procura aqui.
FORA_DA_AMOSTRA = ("patient", "birth", "ssn", "photo", "picture", "address",
                   "phone", "mail", "comment", "note", "remark")

# Tipos que valem amostrar. Coluna larga demais é texto livre disfarçado, e
# ``CHARACTER_MAXIMUM_LENGTH`` negativo é o ``MAX`` do SQL Server.
TIPOS_DE_TEXTO = ("char", "varchar", "nchar", "nvarchar")

# 256, e não 200. Medido contra o banco em 01/09/2026: 256 é a largura PADRÃO
# do DW da Varian para descrição, e o corte em 200 excluía justo o que se foi
# buscar — ``ActivityNamePTB``, ``ActivityCategoryPTB`` e as outras oito
# línguas, todas nvarchar(256). O primeiro relatório saiu sem nenhuma delas: o
# passo 4 achou "Documentação" no ``ActivityCode`` e nunca olhou o NOME da
# atividade em português. Texto livre continua fora pelo NOME da coluna
# (``ActivityNote`` é nvarchar(3000) e cai pela largura de qualquer forma).
LARGURA_MAXIMA = 256


def _conectar(saida, bat="atividades.bat"):
    """A conexão do app, com um prazo maior — e por que ele é maior.

    O app corta a consulta em 6 s porque a capa é montada na thread da tela e
    quem está montando a ficha não pode ficar olhando janela travada. Aqui não
    há tela nenhuma esperando, e um ``COUNT(*)`` numa Fact grande passa de 6 s
    com folga: mantendo o prazo do app, uma tabela lenta sairia no relatório
    como se fosse falta de permissão.
    """
    if banco_local.ligado():
        saida("ISOCENTRO_BANCO_LOCAL está apontada: eu leria o arquivo gravado, "
              "que não tem tabela de atividade nenhuma — o gravador só guarda "
              "as consultas que o app faz. Rode sem ela.")
        return None
    if not capa_db.configurado():
        saida("Nenhum servidor apontado (ISOCENTRO_DB_SERVIDOR ou "
              "config_servico.json).")
        return None
    cx = capa_db.conexao()
    if cx is None:
        situacao, recado = capa_db.estado()
        saida(f"Sem conexão com {capa_db.servidor()} ({situacao}): {recado}")
        saida(f"De máquina fora do domínio, rode pelo {bat} com "
              f"runas /netonly.")
        return None
    cx.timeout = 60
    return cx


def _linhas(cx, sql, *params):
    """Executa e devolve as linhas, ou a exceção (não levanta).

    Não usa ``capa_db._consultar`` de propósito: ele SOLTA a conexão a cada
    falha, e aqui a falha é ESPERADA — tabela que existe no catálogo mas que
    esta conta não pode ler. Com ele, o relatório reconectaria dezenas de vezes
    e cada negativa de permissão viraria uma reconexão ao servidor clínico.
    """
    try:
        cur = cx.cursor()
        cur.execute(sql, *params)
        return cur.fetchall()
    except Exception as exc:  # noqa: BLE001
        return exc


def _tabelas_candidatas(cx, padroes):
    """Tabelas e VIEWS cujo nome casa um dos padrões.

    View entra junto: no DW do ARIA boa parte do que se consulta é view, e
    filtrar por ``BASE TABLE`` esconderia justo o que tem nome legível.
    """
    onde = " OR ".join(["LOWER(TABLE_NAME) LIKE ?"] * len(padroes))
    sql = ("SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE "
           "  FROM INFORMATION_SCHEMA.TABLES "
           f" WHERE {onde} ORDER BY TABLE_SCHEMA, TABLE_NAME")
    return _linhas(cx, sql, *[f"%{p}%" for p in padroes])


def _colunas_candidatas(cx, padroes):
    """Onde o nome da COLUNA denuncia a tabela — para o caso de ela se chamar
    outra coisa. É o mesmo caminho pelo qual ``DimLookup`` virou o lugar do
    vocabulário da capa: o nome da tabela não diz nada, o da coluna diz."""
    onde = " OR ".join(["LOWER(COLUMN_NAME) LIKE ?"] * len(padroes))
    sql = ("SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME "
           "  FROM INFORMATION_SCHEMA.COLUMNS "
           f" WHERE {onde} ORDER BY TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME")
    return _linhas(cx, sql, *[f"%{p}%" for p in padroes])


def _colunas(cx, esquema, tabela):
    return _linhas(cx,
                   "SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH "
                   "  FROM INFORMATION_SCHEMA.COLUMNS "
                   " WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ? "
                   " ORDER BY ORDINAL_POSITION", esquema, tabela)


def _quantas_linhas(cx, esquema, tabela):
    """``(linhas, como)`` — sem varrer a tabela quando dá para não varrer.

    ``sys.dm_db_partition_stats`` responde de metadado, na hora. Ele exige
    VIEW DATABASE STATE, que ``db_datareader`` não dá — por isso o ``COUNT(*)``
    fica de reserva, e não o contrário: contar de verdade é o caminho caro, e
    numa Fact de milhões de linhas é trabalho de servidor clínico gasto para
    escrever um número no relatório.
    """
    r = _linhas(cx,
                "SELECT SUM(p.row_count) FROM sys.dm_db_partition_stats p "
                " JOIN sys.objects o ON o.object_id = p.object_id "
                " JOIN sys.schemas s ON s.schema_id = o.schema_id "
                " WHERE s.name = ? AND o.name = ? AND p.index_id IN (0, 1)",
                esquema, tabela)
    if isinstance(r, list) and r and r[0][0] is not None:
        return int(r[0][0]), "metadado"
    r = _linhas(cx, f"SELECT COUNT(*) FROM [{esquema}].[{tabela}]")
    if isinstance(r, list) and r:
        return int(r[0][0]), "contado"
    return None, str(r)[:120]


def _amostravel(nome, tipo, largura):
    """A coluna vale amostrar? Ver ``FORA_DA_AMOSTRA`` para o porquê."""
    if tipo.lower() not in TIPOS_DE_TEXTO:
        return False
    if largura is not None and (largura < 0 or largura > LARGURA_MAXIMA):
        return False
    baixo = nome.lower()
    return not any(p in baixo for p in FORA_DA_AMOSTRA)


def _amostra(cx, esquema, tabela, coluna, quantos):
    r = _linhas(cx, f"SELECT DISTINCT TOP ({quantos}) [{coluna}] "
                    f"  FROM [{esquema}].[{tabela}] "
                    f" WHERE [{coluna}] IS NOT NULL "
                    f"   AND LTRIM(RTRIM([{coluna}])) <> '' "
                    f" ORDER BY [{coluna}]")
    if not isinstance(r, list):
        return None
    return [str(linha[0]).strip() for linha in r]


def _procurar(cx, esquema, tabela, colunas, palavra, saida):
    """A palavra, coluna por coluna. É este passo que responde à pergunta."""
    achou = False
    for nome, tipo, largura in colunas:
        if not _amostravel(nome, tipo, largura):
            continue
        r = _linhas(cx, f"SELECT DISTINCT TOP ({AMOSTRA}) [{nome}] "
                        f"  FROM [{esquema}].[{tabela}] "
                        f" WHERE [{nome}] LIKE ? ORDER BY [{nome}]",
                    f"%{palavra}%")
        if not isinstance(r, list) or not r:
            continue
        achou = True
        saida(f"    {esquema}.{tabela}.{nome} — {len(r)} valor(es):")
        for linha in r:
            saida(f"        {str(linha[0]).strip()}")
    return achou


def _logins_do_app() -> list:
    """Os físicos ATIVOS do ``usuarios.json`` — a lista de verdade, não uma
    digitada à mão aqui. Digitar seria criar uma segunda versão do cadastro,
    que envelhece em silêncio no dia em que alguém entra no serviço."""
    try:
        from isocentro.dados import auth
    except Exception:  # noqa: BLE001
        return []
    return [u["usuario"] for u in auth.listar()
            if u.get("ativo", True) and u.get("papel") == "fisico"]


def _quem_e_quem(cx, tamanhos, logins, saida) -> None:
    """Cada login do app: onde ele aparece no DW, e em que coluna.

    É o passo que impede o pior desfecho do painel. Se o login do app não
    existir do outro lado, a consulta de atividades volta VAZIA — e vazia é
    indistinguível de "não há nada pendente". O físico fecha o programa achando
    que está em dia. Conferir aqui, uma vez, transforma isso num recado
    ("não te encontrei no ARIA") em vez de num silêncio.

    ``LIKE`` com curinga dos dois lados, e não igualdade: o DW pode guardar o
    login com o domínio grudado (``CLINICA\\geovani.pena``), e a igualdade
    diria "não existe" para o que está lá.
    """
    saida("\n== 6. Os logins do app, do lado do ARIA ==")
    if not logins:
        saida("  nenhum login para conferir.")
        return
    saida("  procurando: " + ", ".join(logins))
    achados = {}
    pessoas = _tabelas_candidatas(cx, PADROES_PESSOA)
    alvos = dict(tamanhos)
    if isinstance(pessoas, list):
        for esquema, tabela, _tipo in pessoas:
            if (esquema, tabela) in alvos:
                continue
            n, _ = _quantas_linhas(cx, esquema, tabela)
            alvos[(esquema, tabela)] = n
    # Dizer ONDE se procurou, e não só o que se achou. No primeiro relatório
    # (01/09/2026) nenhum login apareceu, e o relatório não permitia distinguir
    # "o DW não guarda login" de "a tabela que tem o login foi pulada por ser
    # grande" — que são conclusões opostas sobre o painel inteiro.
    saida("  tabelas lidas: " + (", ".join(
        f"{t}({n})" for (_e, t), n in sorted(alvos.items())
        if n is not None and n <= LIMITE_DE_CATALOGO) or "nenhuma"))
    pulados = [f"{t}({n})" for (_e, t), n in sorted(alvos.items())
               if n is None or n > LIMITE_DE_CATALOGO]
    if pulados:
        saida("  PULADAS por tamanho: " + ", ".join(pulados))
    for (esquema, tabela), n in sorted(alvos.items()):
        if n is None or n > LIMITE_DE_CATALOGO:
            continue
        cols = _colunas(cx, esquema, tabela)
        if not isinstance(cols, list):
            continue
        for nome, tipo, largura in cols:
            if not _amostravel(nome, tipo, largura):
                continue
            onde = " OR ".join([f"[{nome}] LIKE ?"] * len(logins))
            r = _linhas(cx, f"SELECT DISTINCT TOP ({AMOSTRA}) [{nome}] "
                            f"  FROM [{esquema}].[{tabela}] "
                            f" WHERE {onde} ORDER BY [{nome}]",
                        *[f"%{u}%" for u in logins])
            if not isinstance(r, list) or not r:
                continue
            saida(f"    {esquema}.{tabela}.{nome}:")
            for linha in r:
                valor = str(linha[0]).strip()
                saida(f"        {valor}")
                for u in logins:
                    if u.lower() in valor.lower():
                        achados.setdefault(u, f"{tabela}.{nome}")
    faltam = [u for u in logins if u not in achados]
    saida("\n  Encontrados: " + (", ".join(
        f"{u} ({onde})" for u, onde in sorted(achados.items())) or "nenhum"))
    if faltam:
        saida("  NÃO encontrados: " + ", ".join(faltam))
        saida("  -- para estes, o painel tem de dizer 'não te encontrei no "
              "ARIA'. Lista vazia aqui seria lida como 'estou em dia'.")


def _frescor(cx, tamanhos, saida) -> None:
    """Até quando o DW enxerga, pelo MAX de cada coluna de data.

    Fora do relatório padrão de propósito: aqui a Fact grande É consultada, e
    ``MAX`` numa coluna sem índice é varredura de tabela inteira no servidor
    clínico. Vale a pena mesmo assim quando a pergunta é a defasagem da carga —
    mas é escolha de quem roda, não do programa.
    """
    saida("\n== 5. Frescor: o MAX de cada coluna de data ==")
    saida("   (varredura: rodado só com --frescor, e de propósito)")
    for esquema, tabela in sorted(tamanhos):
        cols = _colunas(cx, esquema, tabela)
        if not isinstance(cols, list):
            continue
        for nome, tipo, _largura in cols:
            if tipo.lower() not in TIPOS_DE_DATA:
                continue
            r = _linhas(cx, f"SELECT MAX([{nome}]) FROM [{esquema}].[{tabela}]")
            if isinstance(r, list) and r and r[0][0] is not None:
                saida(f"  {esquema}.{tabela}.{nome} = {r[0][0]}")


def relatorio(cx, padroes, palavra, saida) -> dict:
    quem = f"{os.environ.get('USERDOMAIN', '?')}\\{getpass.getuser()}"
    saida(f"Servidor : {capa_db.servidor()}   Banco: {capa_db.banco()}")
    saida(f"Conta    : {quem}")
    saida(f"Procuro  : nome com {', '.join(padroes)}; palavra '{palavra}'")

    saida("\n== 1. Tabelas com esses pedaços no NOME ==")
    tabelas = _tabelas_candidatas(cx, padroes)
    if not isinstance(tabelas, list):
        saida(f"  falhou: {tabelas}")
        return {}
    if not tabelas:
        saida("  nenhuma. (Não conclui que não existe: pode ter outro nome — "
              "olhe o passo 2.)")
    tamanhos = {}
    for esquema, tabela, tipo in tabelas:
        n, como = _quantas_linhas(cx, esquema, tabela)
        tamanhos[(esquema, tabela)] = n
        quantas = f"{n} linha(s), {como}" if n is not None else f"?? ({como})"
        saida(f"  {esquema}.{tabela}  [{tipo}]  {quantas}")

    saida("\n== 2. Tabelas com esses pedaços numa COLUNA ==")
    colunas = _colunas_candidatas(cx, padroes)
    if isinstance(colunas, list):
        conhecidas = {(e, t) for e, t, _ in tabelas}
        novas = [(e, t, c) for e, t, c in colunas if (e, t) not in conhecidas]
        if not novas:
            saida("  nenhuma além das do passo 1.")
        for esquema, tabela, coluna in novas:
            saida(f"  {esquema}.{tabela}.{coluna}")
    else:
        saida(f"  falhou: {colunas}")

    saida("\n== 3. O catálogo de cada tabela ==")
    for esquema, tabela, _tipo in tabelas:
        n = tamanhos[(esquema, tabela)]
        cols = _colunas(cx, esquema, tabela)
        if not isinstance(cols, list):
            saida(f"\n  {esquema}.{tabela}: não deu para ler as colunas "
                  f"({str(cols)[:100]}) — isto é PERMISSÃO, não ausência.")
            continue
        saida(f"\n  {esquema}.{tabela}")
        for nome, tipo, largura in cols:
            larg = f"({largura})" if largura else ""
            saida(f"      {nome}  {tipo}{larg}")
        if n is None or n > LIMITE_DE_CATALOGO:
            saida(f"      -- grande demais ({n}): é FATO, não catálogo. "
                  "Não amostro nem varro.")
            continue
        for nome, tipo, largura in cols:
            if not _amostravel(nome, tipo, largura):
                continue
            valores = _amostra(cx, esquema, tabela, nome, AMOSTRA)
            if not valores:
                continue
            saida(f"      valores de {nome}: " + " | ".join(valores))

    # Passo 4 só quando há palavra: a passagem pelas tabelas de CARGA reusa
    # este mesmo relatório, e procurar "Documentação" nelas seria só ruído.
    if not palavra:
        return tamanhos

    saida(f"\n== 4. Onde aparece '{palavra}' ==")
    algum = False
    for esquema, tabela, _tipo in tabelas:
        n = tamanhos[(esquema, tabela)]
        if n is None or n > LIMITE_DE_CATALOGO:
            continue
        cols = _colunas(cx, esquema, tabela)
        if isinstance(cols, list):
            algum |= _procurar(cx, esquema, tabela, cols, palavra, saida)
    # DimLookup sempre, mesmo que o nome não case padrão nenhum: é onde o DW
    # guarda o vocabulário traduzido (o sexo e a intenção da capa saem de lá),
    # e é o candidato natural a ter "Documentação" como categoria.
    cols = _colunas(cx, "DWH", "DimLookup")
    if isinstance(cols, list) and cols:
        algum |= _procurar(cx, "DWH", "DimLookup", cols, palavra, saida)
    if not algum:
        saida("  em lugar nenhum das tabelas de catálogo lidas acima.")
    return tamanhos


def _despejar_pacientes(registros, saida) -> None:
    """As Documentações CRUAS de cada registro, uma coluna por vez.

    Uma linha por coluna, e não uma linha por registro: são doze colunas e o
    console quebraria a linha em qualquer largura. Lidas em pilha, duas
    instâncias ficam uma ao lado da outra e a diferença salta.
    """
    from isocentro.banco import atividades_db

    for registro in registros:
        saida(f"\n== Cru: {registro} ==")
        # As DUAS famílias de uma vez: as Documentações e as atividades de
        # alta. Quem despeja um paciente está investigando por que ELE não
        # aparece, e perguntar só pelas Documentações responderia sobre a
        # lista errada (23/09/2026).
        try:
            linhas = list(atividades_db.detalhe(registro))
            linhas += list(atividades_db.detalhe(
                registro, codigos_alvo=atividades_db.CODIGOS_ALTA))
        except Exception as exc:  # noqa: BLE001
            saida(f"  falhou: {exc}")
            continue
        if not linhas:
            saida("  nenhuma atividade conhecida para este registro.")
            continue
        for linha in linhas:
            saida("  " + "-" * 40)
            for rotulo, valor in zip(atividades_db.DETALHE_COLUNAS, linha):
                saida(f"    {rotulo:<22} {valor}")


def _rodar_consultas(ctr_resource_ser: int, saida, pacientes=(),
                     palavra: str = "") -> None:
    """Roda as consultas do :mod:`atividades_db` — o teste delas contra o banco.

    Elas nasceram do catálogo do DW, não de linhas que voltaram; enquanto
    ninguém as rodar, o ``VERIFICADO_EM`` fica vazio e o painel não mostra nada.
    Este é o caminho mais curto entre "há conexão agora" e "dá para preencher
    aquela data": uma linha de comando, e o que voltar se compara com o que o
    ARIA mostra para a mesma pessoa.
    """
    from isocentro.banco import atividades_db

    # O despejo cru primeiro, e sozinho: quem passou ``--paciente`` está
    # investigando UM caso, e as cinquenta linhas da lista de donos empurrariam
    # o que ele veio ver para fora da tela.
    if pacientes:
        _despejar_pacientes(pacientes, saida)
        return

    # A palavra do ``--palavra`` vale TAMBÉM aqui desde 22/09/2026. Antes, o
    # ``--consulta`` ignorava a opção e sempre procurava "Documentação": para
    # achar as atividades de ALTA era preciso ou mudar o módulo, ou ler o passo
    # 4 do relatório — que mostra cada coluna numa lista solta, sem parear o
    # código com o nome. É o par que se vem buscar.
    alvo = palavra or atividades_db.PALAVRA
    saida(f"\n== Catálogo: o que casa '{alvo}' ==")
    try:
        cat = atividades_db.catalogo(alvo)
    except Exception as exc:  # noqa: BLE001
        saida(f"  falhou: {exc}")
        return
    saida(f"  {len(cat)} atividade(s) no catálogo:")
    for at in cat:
        saida(f"    {at.codigo}  |  {at.nome}  |  {at.categoria}")

    saida("\n== Donos de tarefa (o ctrResourceSer é o vínculo) ==")
    try:
        pessoas = atividades_db.donos()
    except Exception as exc:  # noqa: BLE001
        saida(f"  falhou: {exc}")
        pessoas = []
    for d in pessoas:
        saida(f"    {d.ctr_resource_ser:>10}  {d.rotulo()}")

    if ctr_resource_ser:
        saida(f"\n== Pendências de {ctr_resource_ser} ==")
    else:
        saida("\n== Documentações abertas do serviço, com o dono ao lado ==")
    # O TEMPO, e não só o resultado: o painel consulta na thread da tela e o
    # ``capa_db`` corta em 6 s. Uma consulta que responde certo em 9 s não
    # serve, e a diferença entre as duas só aparece medindo. É metade do que o
    # ``VERIFICADO_EM`` pede.
    import time
    marca = time.perf_counter()
    try:
        lista = (atividades_db.pendentes(ctr_resource_ser)
                 if ctr_resource_ser else atividades_db.todas())
    except Exception as exc:  # noqa: BLE001
        saida(f"  falhou: {exc}")
        return
    gastou = time.perf_counter() - marca
    limite = " -- ACIMA do limite de 6 s do app" if gastou > 6 else ""
    saida(f"  {len(lista)} pendência(s) em {gastou:.1f} s{limite}")
    for at in lista:
        # O dono PRIMEIRO quando a lista é do serviço inteiro: é por ele que se
        # procura na lista de todo mundo, e coluna de busca no fim da linha
        # obriga a varrer o texto todo para achar a sua.
        quem = f"{at.dono:<28}  " if not ctr_resource_ser else ""
        saida(f"    {quem}{at.data_br():>10}  {at.estado:<22}  {at.titulo()}  "
              f"[{at.registro} {at.paciente}]")
    # Zero não pode ficar sem explicação: "não há nada" e "o filtro apagou
    # tudo" são a mesma tela, e a primeira leitura faz a pessoa ir embora
    # achando que está em dia. Roda aqui, na mesma ida ao servidor.
    #
    # E o quadro das ALTAS roda SEMPRE, no fim — não dentro deste "se deu
    # zero". Havia um ``return`` aqui, herdado de quando as Documentações eram
    # a única lista: com dez delas na tela, a função voltava antes e a seção
    # das altas simplesmente não saía no relatório. Custou uma ida à clínica
    # em 23/09/2026.
    if not lista:
        saida("\n  Zero — afrouxando um filtro por vez para ver quem esvaziou:")
        try:
            d = atividades_db.porque_vazio(ctr_resource_ser)
        except Exception as exc:  # noqa: BLE001
            saida(f"    não deu para diagnosticar: {exc}")
            d = None
        if d is not None:
            saida(f"    (janela: desde {d['desde']})")
            for rotulo, n in d["degraus"]:
                saida(f"    {n!s:>8}  {rotulo}")
            if d["estados"]:
                saida("    estados das SUAS tarefas dessa atividade:")
                for estado, n in d["estados"]:
                    fechado = " (está na lista de FECHADOS)" \
                        if estado in atividades_db.FECHADOS else ""
                    saida(f"        {n:>6}  {estado}{fechado}")
    _rodar_altas(saida)


def _histograma_de_data(lista, saida) -> None:
    """Quantas sobrariam com um TETO de data — sem consultar de novo.

    Existe porque em 23/09/2026, tirado o filtro de predecessora, a lista veio
    com 216 atividades contra as 26 que o ARIA mostra na aba "Disponível": a
    diferença é quase toda de atividades AGENDADAS para outubro e novembro,
    ainda ``Open``. O ARIA parece mostrar as que já estão vencendo, e qual é a
    janela dele ninguém mediu.

    A lista crua já traz o vencimento de cada uma, então isto responde com a
    ida que JÁ aconteceu, em vez de custar outra por palpite. A contagem de
    PACIENTES vem junto porque é ela que se compara com a tela, que mostra uma
    linha por paciente.
    """
    hoje = datetime.date.today()
    saida("\n  Se houvesse teto de data (quantas sobrariam):")
    for dias in (0, 1, 3, 7, 14, 30, 60):
        cabem = [at for at in lista if at.quando is not None
                 and (at.quando - hoje).days <= dias]
        saida(f"    até hoje+{dias:<3} {len(cabem):>5} atividade(s)"
              f"   {len({at.registro for at in cabem}):>4} paciente(s)")
    sem_data = sum(1 for at in lista if at.quando is None)
    if sem_data:
        saida(f"    (e {sem_data} sem data nenhuma — somem em qualquer teto)")


def _rodar_altas(saida) -> None:
    """O quadro Altas Prontas da Fichinha, e por que ele veio vazio.

    Nasceu em 23/09/2026: os três códigos de "Verificar Programação" já
    estavam no módulo, a tela dizia "Nenhuma alta pendente agora" e não havia
    como saber se aquilo era verdade ou um filtro comendo tudo. Mesma pergunta
    das Documentações, e por isso a mesma saída — o que muda é o conjunto de
    códigos.
    """
    import time

    from isocentro.banco import atividades_db

    saida("\n== Altas Prontas (Verificar Programação) ==")
    saida("  códigos: " + " | ".join(atividades_db.CODIGOS_ALTA))
    saida("  estados aceitos: " + " | ".join(atividades_db.ESTADOS_ABERTOS)
          + "  (sem filtro de predecessora)")
    marca = time.perf_counter()
    try:
        # CRU, sem o colapso por paciente que a TELA faz: aqui se vem contar
        # atividade contra o que o ARIA mostra, e a tela mostra uma linha por
        # PACIENTE. Em 23/09/2026 os dois números foram confundidos — o
        # relatório dizia "5 Verificar Programação" com doze abertas no ARIA,
        # porque dez delas tinham virado a linha da Imprimir Alta do mesmo
        # paciente. Ferramenta de diagnóstico não esconde nada.
        lista = atividades_db._pendentes(
            0, None, atividades_db.CODIGOS_ALTA, exigir_dono=False,
            estados_aceitos=atividades_db.ESTADOS_ABERTOS)
        na_tela = atividades_db.altas()
    except Exception as exc:  # noqa: BLE001
        saida(f"  falhou: {exc}")
        return
    gastou = time.perf_counter() - marca
    limite = " -- ACIMA do limite de 6 s do app" if gastou > 6 else ""
    saida(f"  {len(lista)} atividade(s) em {gastou:.1f} s{limite}")
    saida(f"  {len(na_tela)} linha(s) na TELA (uma por paciente)")
    for at in lista:
        # A UNIDADE ao lado, porque é ela que o código NÃO diz (ver
        # ``Atividade.unidade``). Conferir aqui é mais barato que descobrir na
        # tela que todo o BET saiu sem etiqueta.
        saida(f"    {at.dono:<28}  {at.data_br():>10}  {at.estado:<22}  "
              f"[{at.unidade or '??'}]  {at.titulo()}  "
              f"[{at.registro} {at.paciente}]")
    _histograma_de_data(lista, saida)
    # Diagnóstico por FAMÍLIA, não só quando a lista inteira zera.
    #
    # Em 23/09/2026 a lista voltou com duas "Verificar Programação" e nenhuma
    # "Imprimir Alta" — e o usuário sabia de 12 "Imprimir Alta CEL" disponíveis
    # no ARIA. Com o diagnóstico preso ao "se deu zero", uma família inteira
    # pode sumir enquanto a outra responde, e o relatório não diz nada: a lista
    # não está vazia, então parece que funcionou.
    familias = [("Verificar Programação",
                 tuple(c for c in atividades_db.CODIGOS_ALTA
                       if c.startswith("Verificar"))),
                ("Imprimir Alta",
                 tuple(c for c in atividades_db.CODIGOS_ALTA
                       if c.startswith("Imprimir")))]
    for nome, codigos in familias:
        if not codigos:
            continue
        quantas = sum(1 for at in lista if at.codigo in codigos)
        saida(f"\n  {nome}: {quantas} na lista")
        if quantas:
            continue
        saida("    zero — afrouxando um filtro por vez:")
        try:
            d = atividades_db.porque_vazio(0, codigos_alvo=codigos)
        except Exception as exc:  # noqa: BLE001
            saida(f"      não deu para diagnosticar: {exc}")
            continue
        saida(f"      (janela: desde {d['desde']})")
        for rotulo, n in d["degraus"]:
            saida(f"      {n!s:>8}  {rotulo}")
        if d["estados"]:
            saida("      estados dessas atividades no banco:")
            for estado, n in d["estados"]:
                fechado = " (está na lista de FECHADOS)" \
                    if estado in atividades_db.FECHADOS else ""
                saida(f"          {n:>6}  {estado}{fechado}")


# Onde cai relatório de ferramenta. Antes eles nasciam na RAIZ do projeto (o
# ``.bat`` faz ``cd`` para lá e passa só o nome), e em 09/09/2026 havia 24 deles
# misturados com os 61 módulos do programa — a raiz tinha virado a pasta de
# saída de todo mundo. Como o ``_destino_livre`` nunca sobrescreve, eles se
# acumulam por desenho: sem uma pasta própria, a bagunça só cresce.
#
# Ancorado no arquivo, e não no diretório atual: quem roda pelo ``runas``
# começa noutra pasta, e "relatorios_ferramentas" relativo ao ``cwd`` faria o
# relatório cair em qualquer lugar. O nome é comprido de propósito — "capa
# relatórios" já é a pasta dos CSV exportados do Reporting Services, e um
# físico que confundisse as duas despejaria dado clínico aqui.
PASTA_RELATORIOS = RAIZ / "relatorios_ferramentas"


def _destino_livre(caminho: Path) -> Path:
    """Nunca por cima de um relatório que já existe, e sempre na pasta de saída.

    Nome sem pasta (``-o sonda_dicom.txt``, que é como os ``.bat`` chamam) vai
    para ``relatorios_ferramentas/``. Caminho com pasta é respeitado como veio:
    quem escreve ``-o C:/temp/x.txt`` está dizendo onde quer.

    Custou o relatório inteiro em 01/09/2026: a rodada boa das 17:29 (49 KB, o
    catálogo das 40 tabelas de atividade) foi apagada às 17:50 por uma rodada
    que só conseguiu escrever a recusa de SSPI — o ``.bat`` fixa o nome do
    arquivo, e quem roda de novo não espera perder o que já tinha. Uma segunda
    ida ao servidor é barata; o dado que só existia ali, não.

    O nome com data e hora também serve de registro: dois relatórios lado a
    lado dizem o que mudou no banco entre um e outro.
    """
    if caminho.parent == Path("."):
        PASTA_RELATORIOS.mkdir(parents=True, exist_ok=True)
        caminho = PASTA_RELATORIOS / caminho.name
    if not caminho.exists():
        return caminho
    quando = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    return caminho.with_name(f"{caminho.stem}_{quando}{caminho.suffix}")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Descobre as atividades do ARIA no variandw (só leitura).")
    p.add_argument("--palavra", default=PALAVRA,
                   help=f"o que procurar, nas tabelas e também no catálogo do "
                        f"--consulta (padrão: {PALAVRA}). O banco é "
                        f"CASE-SENSITIVE: 'alta' não acha 'Alta Pronta'")
    p.add_argument("--padrao", action="append", default=None,
                   help="pedaço de nome de tabela; pode repetir "
                        f"(padrão: {', '.join(PADROES)})")
    p.add_argument("--tabela", default="",
                   help="só as tabelas cujo nome contenha isto, em detalhe")
    p.add_argument("--frescor", action="store_true",
                   help="o MAX de cada coluna de data — VARRE a tabela grande")
    p.add_argument("--consulta", action="store_true",
                   help="roda as consultas do atividades_db (catálogo e donos) "
                        "em vez de descobrir tabelas — é o teste delas")
    p.add_argument("--paciente", action="append", default=None,
                   help="com --consulta: despeja as Documentações CRUAS destes "
                        "registros, sem filtro — pode repetir, e é para "
                        "comparar um caso que aparece com um que não devia")
    p.add_argument("--dono", type=int, default=0,
                   help="com --consulta: o ctrResourceSer de quem se quer as "
                        "pendências (o número sai da lista de donos)")
    p.add_argument("--logins", default="",
                   help="logins a conferir do lado do ARIA, separados por "
                        "vírgula (padrão: os físicos ativos do usuarios.json)")
    p.add_argument("-o", "--saida", default="",
                   help="grava o relatório neste arquivo, além de imprimir")
    a = p.parse_args(argv)

    linhas: list = []

    def saida(texto=""):
        print(texto)
        linhas.append(texto)

    # A gravação embrulha TAMBÉM o ``_conectar``, e não só o relatório. Custou
    # uma ida e volta em 01/09/2026: sem conexão, o ``main`` devolvia 2 antes
    # do ``finally``, e o arquivo pedido no ``-o`` simplesmente não nascia. A
    # recusa ficava só no console do ``runas`` — que fecha —, e de fora não
    # havia como distinguir "não rodou" de "rodou e o servidor recusou".
    # Arquivo pedido é arquivo entregue, mesmo (ainda mais) quando deu errado.
    codigo = 2
    try:
        cx = _conectar(saida)
        if cx is None:
            return codigo
        if a.consulta:
            _rodar_consultas(a.dono, saida, a.paciente or [], a.palavra)
            codigo = 0
            return codigo
        # ``--tabela`` é o mesmo relatório com um padrão só: pedir uma tabela
        # pelo nome exato daria "não achei" para quem errou o esquema, que é o
        # erro mais fácil de cometer aqui.
        escolhido = bool(a.tabela or a.padrao)
        padroes = (a.tabela.lower(),) if a.tabela else tuple(a.padrao or PADROES)
        tamanhos = relatorio(cx, padroes, a.palavra, saida)
        if a.frescor:
            _frescor(cx, tamanhos, saida)
        if not escolhido:
            logins = ([u.strip() for u in a.logins.split(",") if u.strip()]
                      if a.logins else _logins_do_app())
            _quem_e_quem(cx, tamanhos, logins, saida)
            # A segunda pergunta, na MESMA rodada: ir à clínica duas vezes por
            # falta de um bloco no relatório é o desperdício que esta ferramenta
            # existe para evitar. Sem palavra: o passo 4 não tem o que fazer nas
            # tabelas de carga.
            saida("\n\n===== Quando o DW é carregado =====")
            relatorio(cx, PADROES_CARGA, "", saida)
        codigo = 0
    finally:
        if a.saida:
            destino = _destino_livre(Path(a.saida))
            destino.write_text("\n".join(linhas) + "\n", encoding="utf-8")
            print(f"\nGravado em {destino}")
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
