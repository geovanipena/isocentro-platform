r"""Grava o banco LOCAL: as respostas do ``variandw`` sobre os pacientes das TC.

Por que existe: fora da clínica não há banco. Esta máquina está fora do domínio
(a rede alcança o servidor, mas a identidade é recusada — SSPI), então a aba
Capa cai no espelho/CSV e a **Ficha Virtual some**, porque ela não tem reserva
nenhuma. Conferir tela com dado inventado é o jeito de não achar o defeito que
só o dado real mostra.

Isto pergunta ao servidor, UMA VEZ, tudo o que o app pergunta sobre os pacientes
que já estão em ``TCs_Teste/`` — e grava as respostas num arquivo que o
:mod:`banco_local` reproduz depois, sem rede.

    REM da máquina fora do domínio, com a identidade de rede:
    runas /netonly /user:CLINICA\geovani.pena "C:\...\isocentro\tools\gravar_banco.bat"

    python tools/gravar_banco.py --lista        # quem seria gravado (não conecta)
    python tools/gravar_banco.py                # grava todos os das pastas de TC
    python tools/gravar_banco.py --registro 9000001CEL
    python tools/gravar_banco.py --conferir     # o que já está no arquivo

Depois, para usar: ``tools/rodar_com_banco_local.bat`` (ou apontar
``ISOCENTRO_BANCO_LOCAL`` para o arquivo).

**Só leitura, como todo o resto.** As consultas são as do próprio app: este
arquivo não escreve SQL nenhum, ele chama ``capa_db.cadastro_do_paciente`` e
companhia com um gravador embrulhando a conexão. É de propósito — o conjunto
gravado passa a ser, por construção, exatamente o que o app pergunta, e não uma
segunda versão das consultas que envelheceria em silêncio.

**O que NÃO é gravado inteiro.** As duas consultas que varrem a clínica toda (a
lista de pacientes da busca e a lista "em tratamento") são gravadas
RESTRITAS aos pacientes das pastas de TC. Guardar 13 mil cadastros reais num
arquivo de trabalho seria despejo de dado clínico sem nenhuma necessidade — o
que se quer simular são estes casos.

O arquivo guarda nome, nascimento, convênio, CID e a foto 3×4 de gente de
verdade. Ele nasce dentro de ``TCs_Teste/``, que está fora do git pelo mesmo
motivo. Não versionar, não copiar para fora da máquina.
"""
from __future__ import annotations

import argparse
import datetime
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from isocentro.banco import banco_local  # noqa: E402
from isocentro.banco import capa_db  # noqa: E402
from isocentro.banco import tratamento_db  # noqa: E402

CASOS = RAIZ / "TCs_Teste"
PADRAO = CASOS / "banco de dados" / "banco_local.sqlite"

# As duas consultas que varrem a clínica inteira, e a coluna do registro em cada
# uma. O que volta delas é cortado aos pacientes das TC — ver ``_so_os_das_tc``.
#
# Casadas por um pedaço que SÓ ELAS têm, e aqui é preciso cuidado: "FROM
# DWH.DimPatient p" aparece também no cadastro de UM paciente, e
# "FactTreatmentHistory" aparece em sete consultas, várias com outra coluna na
# posição 0 — cortá-las por registro esvaziaria a resposta inteira. Foi assim
# que uma armadilha já mordeu nos testes: o banco falso casava "IN (" e passou a
# responder a consulta errada no dia em que outra ganhou um ``IN``.
VARREDURAS = [
    ("FROM DWH.DimPatient p WHERE p.PatientId <> 'NA'", 0, "busca de pacientes"),
    ("GROUP BY p.PatientId, p.PatientFullName, th.DimCourseID", 0,
     "lista em tratamento"),
]


# -- Quem está nas pastas de TC ----------------------------------------------

def _primeiro_dicom_de_cada_pasta():
    """``(registro, nome, pasta)`` de cada pasta que tem DICOM.

    Um arquivo por pasta, e não a varredura inteira: as 19 pastas somam milhares
    de fatias, e o registro é o mesmo em todas elas. As subpastas contam
    separado porque a pasta ``Elekta`` guarda um paciente por técnica — olhar
    só o primeiro nível deixaria seis de fora.

    O preço de ler UM arquivo por pasta: um segundo paciente misturado na mesma
    pasta passa batido. Medido no acervo, o único caso é o fantoma de CQ
    (``CQ-MLC_SIMULA``, registro 13923, nascimento 01/01/2010) dentro de
    ``Elekta/Pelve_3D Filtro`` — que não é gente e não tem o que gravar.
    """
    try:
        import pydicom
    except ImportError:
        print("pydicom não está instalado — não dá para ler os registros.")
        return []
    if not CASOS.is_dir():
        print(f"Não achei {CASOS}.")
        return []
    tags = [pydicom.tag.Tag(0x10, 0x20), pydicom.tag.Tag(0x10, 0x10)]
    achados: dict[str, tuple] = {}
    for pasta in sorted(p for p in CASOS.rglob("*") if p.is_dir()):
        for arq in sorted(pasta.glob("*.dcm")):
            try:
                ds = pydicom.dcmread(str(arq), stop_before_pixels=True,
                                     force=True, specific_tags=tags)
            except Exception:  # noqa: BLE001 — arquivo torto não impede o resto
                continue
            registro = str(getattr(ds, "PatientID", "") or "").strip()
            if not registro:
                continue
            nome = str(getattr(ds, "PatientName", "") or "")
            achados.setdefault(registro,
                               (registro, nome,
                                pasta.relative_to(CASOS).as_posix()))
            break   # um arquivo por pasta basta
    return sorted(achados.values(), key=lambda x: x[2])


# -- Gravação ----------------------------------------------------------------

# Quantos pedaços do nome têm de bater para ser a mesma pessoa. DOIS, e não um:
# um sobrenome coincide o tempo todo ("Silva"), e dois pedaços independentes
# baterem por acaso já é improvável.
_PEDACOS_PARA_SER_A_MESMA = 2


def _mesma_pessoa(do_dicom: str, do_banco: str) -> bool:
    """O nome do DICOM e o do banco são da mesma pessoa?

    Existe porque a numeração do Monaco e a do ARIA são espaços DIFERENTES e
    colidem: o registro ``13870``, que na pasta ``Elekta/Mama_3D`` é uma
    paciente, existe no ``variandw`` como outra pessoa — cadastro vazio, sem
    nascimento, sem convênio, sem prescrição. O ``capa_db`` responde certo (é o
    que o servidor diz), mas o relatório desta ferramenta dizia "OK" na linha, e
    "OK" ali lê como "este caso está coberto".

    Palavra de três letras ou mais, sem acento: "de", "da", "dos" batem em
    qualquer par de nomes brasileiros e não dizem nada.
    """
    from isocentro.banco import capa_dados
    if not str(do_dicom or "").strip():
        return True   # sem nome do DICOM (``--registro``) não há o que conferir
    def pedacos(nome):
        return {p for p in capa_dados.normalizar_nome(nome).split() if len(p) > 2}
    return len(pedacos(do_dicom) & pedacos(do_banco)) >= _PEDACOS_PARA_SER_A_MESMA


def _de_um_paciente(registro: str, nome_do_dicom: str = "") -> tuple[bool, str]:
    """Faz ao servidor todas as perguntas do app sobre um paciente.

    Devolve ``(achou, recado)``. "Não achou" não é erro: os pacientes da pasta
    ``Elekta`` vêm do Monaco e podem não existir no ``variandw``.
    """
    cad = capa_db.cadastro_do_paciente(registro)
    if cad is None:
        return False, "o banco não conhece este registro"
    if not _mesma_pessoa(nome_do_dicom, cad.nome):
        # NÃO é "achou". A gravação da resposta já aconteceu e fica — ela é
        # fiel ao servidor, e o app tem o próprio aviso de nome divergente. O
        # que não pode ficar é a linha "OK" no relatório: o caso não está
        # coberto, está confundido com outra pessoa.
        return False, (f"OUTRA PESSOA: o banco chama {registro} de "
                       f"'{cad.nome}', e o DICOM diz '{nome_do_dicom}'. "
                       "Numeração do Monaco colidindo com a do ARIA.")
    partes = [f"cadastro: {cad.nome or '(sem nome)'}"]

    prescricoes = capa_db.prescricoes_do_paciente(registro)
    partes.append(f"{len(prescricoes)} prescrição(ões)")

    foto = capa_db.foto_do_paciente(registro)
    partes.append("com foto" if foto else "sem foto")

    # A Ficha Virtual. O curso ATUAL é o que a aba abre; os outros existem para
    # serem consultados, e sem gravá-los a troca de curso ficaria muda offline.
    cursos = tratamento_db.cursos_do_paciente(registro)
    partes.append(f"{len(cursos)} curso(s)")
    for curso in [None] + [c.id for c in cursos]:
        try:
            tratamento_db.tratamento_do_paciente(registro, curso=curso)
        except Exception as exc:  # noqa: BLE001 — um curso torto não para o resto
            partes.append(f"curso {curso}: {str(exc)[:60]}")
    return True, "; ".join(partes)


def _so_os_das_tc(permitidos: set):
    """Corta as varreduras da clínica inteira aos pacientes das pastas de TC.

    A CONSULTA é feita inteira, como o app a faz — reescrever o SQL aqui daria
    uma chave que o app nunca vai perguntar. O que se joga fora é o RESULTADO,
    e ele é jogado fora **na leitura**, não depois, já no arquivo: a lista "em
    tratamento" alimenta outras consultas (o ``tratamento_db`` reconta as
    frações passando ESSES registros como parâmetro). Cortando só no fim, as
    auxiliares ficariam gravadas com a lista inteira, e na reprodução a lista
    curta pediria uma pergunta que ninguém gravou — as colunas de recontagem
    sumiriam da tela sem uma linha dizendo por quê.

    Guardar treze mil cadastros reais num arquivo de trabalho seria despejo de
    dado clínico sem necessidade nenhuma; o que se quer simular são estes casos.

    Devolve ``(filtro, contadas)`` — o segundo é para o relatório final poder
    dizer quantas linhas vieram do servidor e quantas ficaram.
    """
    contadas: dict = {}

    def filtrar(sql, linhas):
        achatado = banco_local._normalizar_sql(sql)
        for marca, coluna, o_que in VARREDURAS:
            if marca not in achatado:
                continue
            ficam = [linha for linha in linhas
                     if str(linha[coluna] or "").strip() in permitidos]
            antes, agora = contadas.get(o_que, (0, 0))
            contadas[o_que] = (antes + len(linhas), agora + len(ficam))
            return ficam
        return linhas

    return filtrar, contadas


def _os_medicos_dos_casos(equipe: list, registros: set) -> list:
    """Os radio-oncologistas responsáveis pelos pacientes gravados.

    Casa por ``normalizar_nome``, e não por igualdade de texto: os dois lados
    desinvertem o nome do banco por caminhos diferentes — ``medicos()`` passa
    por ``de_pessoa`` (que ainda arruma a caixa) e ``medico_do_paciente`` só
    por ``desinverter``. Comparando cru, a lista sairia VAZIA e o painel
    ficaria mudo offline sem nenhum erro aparecer.

    O que viaja no filtro é o ``Medico.bruto``: desinverter não tem volta
    confiável (o sobrenome repetido do DW não sobrevive à ida e volta).
    """
    from isocentro.banco import capa_dados
    quero = {capa_dados.normalizar_nome(tratamento_db.medico_do_paciente(r))
             for r in sorted(registros)}
    quero.discard("")
    return [m for m in equipe
            if capa_dados.normalizar_nome(m.nome) in quero]


def gravar(destino: Path, alvos: list) -> int:
    if banco_local.ligado():
        print("ISOCENTRO_BANCO_LOCAL está apontada: eu leria o arquivo gravado "
              "em vez do servidor. Rode sem ela.")
        return 2
    if not capa_db.configurado():
        print("Nenhum servidor apontado (ISOCENTRO_DB_SERVIDOR ou "
              "config_servico.json).")
        return 2
    real = capa_db.conexao()
    if real is None:
        situacao, recado = capa_db.estado()
        print(f"Sem conexão com {capa_db.servidor()} ({situacao}): {recado}")
        print("De máquina fora do domínio, rode pelo gravar_banco.bat com "
              "runas /netonly.")
        return 1

    # O painel "em tratamento" ainda está atrás do portão experimental
    # (``LISTA_VERIFICADA_EM`` vazio). Sem ligar a variável aqui,
    # ``em_tratamento`` devolveria ``None`` sem consultar nada — e a gravação
    # sairia sem a lista, para só se descobrir isso na hora de usar, offline.
    os.environ.setdefault(tratamento_db.ENV_EXPERIMENTAL, "1")

    cx = banco_local.abrir(destino, criar=True)
    banco_local.anotar(cx, "servidor", capa_db.servidor())
    banco_local.anotar(cx, "banco", capa_db.banco())
    banco_local.anotar(cx, "gravado_em",
                       datetime.datetime.now().isoformat(timespec="seconds"))

    # O gravador entra no lugar da conexão: as funções chamadas abaixo são as
    # DO APP, e tudo que elas perguntarem fica no arquivo.
    original = capa_db.conexao
    achados = set()
    filtrar, contadas = _so_os_das_tc(achados)
    capa_db.conexao = lambda: banco_local.Gravador(real, cx, filtrar)
    try:
        for registro, nome, pasta in alvos:
            print(f"\n{pasta}  {registro}  {nome}")
            try:
                achou, recado = _de_um_paciente(registro, nome)
            except Exception as exc:  # noqa: BLE001
                achou, recado = False, f"falhou: {str(exc)[:120]}"
            print(f"  {'OK' if achou else '--'}  {recado}")
            banco_local.anotar_paciente(cx, registro, pasta, achou, recado)
            if achou:
                achados.add(registro)

        # Depois dos pacientes, e não antes: o filtro corta pelo conjunto
        # ``achados``, que só está completo aqui.
        print("\nAs listas da clínica inteira (cortadas aos pacientes das TC):")
        capa_db.pacientes()
        equipe = tratamento_db.medicos()
        deles = _os_medicos_dos_casos(equipe, achados)
        for concluidos in (False, True):
            # As duas variantes do filtro "incluir concluídos": são consultas
            # DIFERENTES (uma tem o ``HAVING``, a outra não), e a caixa está na
            # tela — gravar só uma deixaria metade do painel muda.
            tratamento_db.em_tratamento(incluir_concluidos=concluidos)
            for medico in deles:
                # O painel abre FILTRADO por um médico (``ISOCENTRO_MEDICO``, e a
                # escolha lembrada em QSettings), e o filtro é outro SQL, com o
                # nome do médico como parâmetro. Sem gravar por médico, a aba
                # abriria dizendo "não deu para perguntar" justo no arranque.
                # Só os médicos DESTES casos: varrer os sessenta da clínica
                # seria uma consulta por médico para responder a nenhum caso.
                tratamento_db.em_tratamento([medico.bruto],
                                            incluir_concluidos=concluidos)
        for o_que, (do_servidor, gravadas) in sorted(contadas.items()):
            print(f"  {o_que}: {do_servidor} linha(s) do servidor -> "
                  f"{gravadas} gravada(s)")
    finally:
        capa_db.conexao = original
        cx.commit()

    quantas = cx.execute("SELECT COUNT(*) FROM respostas").fetchone()[0]
    cx.close()
    print(f"\nGravado: {len(achados)} paciente(s), {quantas} consulta(s), em")
    print(f"  {destino}")
    print("\nPara usar, sem rede:  tools\\rodar_com_banco_local.bat")
    return 0


def _reconferir_nomes(cx) -> int:
    """Recompara os nomes do arquivo com os das pastas, sem rede.

    Roda no ``--conferir`` porque a checagem de pessoa trocada nasceu DEPOIS da
    primeira gravação — e a primeira gravação já tinha um caso (o ``13870``).
    Sem isto, corrigir a anotação exigiria gravar tudo de novo, o que só se faz
    na rede da clínica.
    """
    das_pastas = {registro: nome
                  for registro, nome, _pasta in _primeiro_dicom_de_cada_pasta()}
    if not das_pastas:
        return 0
    mudaram, fora = 0, set()
    for registro, achou, recado in cx.execute(
            "SELECT registro, achou, recado FROM pacientes").fetchall():
        if not achou or registro not in das_pastas:
            continue
        # O nome que o banco deu está no começo do recado ("cadastro: Fulano;").
        do_banco = recado.split(";", 1)[0].replace("cadastro:", "").strip()
        if _mesma_pessoa(das_pastas[registro], do_banco):
            continue
        cx.execute("UPDATE pacientes SET achou = 0, recado = ? "
                   "WHERE registro = ?",
                   (f"OUTRA PESSOA: o banco chama {registro} de '{do_banco}', "
                    f"e o DICOM diz '{das_pastas[registro]}'. Numeração do "
                    "Monaco colidindo com a do ARIA.", registro))
        mudaram += 1
    if mudaram:
        cx.commit()
        print(f"({mudaram} anotação(ões) corrigida(s): registro que o banco "
              "conhece, mas de OUTRA pessoa.)")
    # A limpeza das varreduras é feita SEMPRE, a partir de quem está marcado
    # como não-achado, e não só de quem acabou de ser demovido: a demoção pode
    # ter acontecido numa execução anterior, e foi o que aconteceu — o
    # ``13870`` já saía como "OUTRA PESSOA" na lista e continuava aparecendo na
    # busca de pacientes da tela.
    fora = {r for (r,) in cx.execute(
        "SELECT registro FROM pacientes WHERE achou = 0").fetchall()}
    saíram = _tirar_das_varreduras(cx, fora) if fora else 0
    if saíram:
        cx.commit()
        print(f"({saíram} linha(s) tirada(s) das listas gravadas: registro que "
              "não é o paciente de nenhum caso.)")
    if mudaram or saíram:
        print()
    return mudaram


def _tirar_das_varreduras(cx, registros: set) -> int:
    """Apaga estes registros das listas gravadas (busca e em tratamento).

    Quem não é o paciente do caso não tem o que fazer na busca da tela, e é
    dado clínico de terceiro num arquivo de trabalho — a mesma razão que
    restringe a gravação às pastas de TC.
    """
    import json
    saíram = 0
    for marca, coluna, _o_que in VARREDURAS:
        for chave, dados in cx.execute(
                "SELECT chave, linhas FROM respostas WHERE sql LIKE ?",
                (f"%{marca}%",)).fetchall():
            tinha = json.loads(dados)
            ficam = [linha for linha in tinha
                     if str(linha[coluna] or "").strip() not in registros]
            if len(ficam) == len(tinha):
                continue
            saíram += len(tinha) - len(ficam)
            cx.execute("UPDATE respostas SET linhas = ?, quantas = ? "
                       "WHERE chave = ?",
                       (json.dumps(ficam, ensure_ascii=False), len(ficam), chave))
    return saíram


def conferir(destino: Path) -> int:
    if not destino.is_file():
        print(f"Ainda não existe: {destino}")
        return 1
    os.environ["ISOCENTRO_BANCO_LOCAL"] = str(destino)
    cx = banco_local.abrir(destino)
    _reconferir_nomes(cx)
    print(banco_local.resumo())
    print("\nPacientes:")
    for registro, pasta, achou, recado in cx.execute(
            "SELECT registro, pasta, achou, recado FROM pacientes "
            "ORDER BY pasta").fetchall():
        print(f"  {'OK' if achou else '--'}  {pasta:<16} {registro:<14} {recado}")
    print("\nConsultas gravadas (por linhas devolvidas):")
    for sql, quantas in cx.execute(
            "SELECT sql, SUM(quantas) FROM respostas GROUP BY sql "
            "ORDER BY SUM(quantas) DESC").fetchall():
        print(f"  {quantas:>6}  {sql[:90]}")
    cx.close()
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--lista", action="store_true",
                    help="só mostra quem seria gravado (não conecta em nada)")
    ap.add_argument("--conferir", action="store_true",
                    help="mostra o que já está no arquivo")
    ap.add_argument("--registro", action="append", default=[],
                    help="grava só este registro (pode repetir)")
    ap.add_argument("-o", "--saida", default=str(PADRAO),
                    help=f"arquivo do banco local (padrão: {PADRAO})")
    args = ap.parse_args(argv)
    destino = Path(args.saida)

    if args.conferir:
        return conferir(destino)

    if args.registro:
        alvos = [(r, "", "(--registro)") for r in args.registro]
    else:
        alvos = _primeiro_dicom_de_cada_pasta()
    if not alvos:
        print("Nenhum registro encontrado nas pastas de TC.")
        return 1

    if args.lista:
        print(f"{len(alvos)} paciente(s) nas pastas de TC:\n")
        for registro, nome, pasta in alvos:
            print(f"  {pasta:<20} {registro:<14} {nome}")
        print("\n(A pasta Elekta vem do Monaco: esses registros podem não "
              "existir no variandw.)")
        return 0

    return gravar(destino, alvos)


if __name__ == "__main__":
    raise SystemExit(main())
