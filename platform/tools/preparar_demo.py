r"""Deixa o servidor local com o TRABALHO JÁ FEITO: fichas impressas, altas na
pasta, Datas Relevantes — para cada clique da demonstração abrir alguma coisa.

Uso::

    python tools\preparar_demo.py            (só o que falta)
    python tools\preparar_demo.py --refazer  (regera todas as fichas)
    python tools\preparar_demo.py TC8 TC13   (só estes casos)

Roda DEPOIS do ``montar_servidor_local.py`` (precisa do banco simulado e das
simulações) e é chamado pelo ``servidor_local.bat``. Custa ~1 min por caso na
primeira vez; depois só refaz o que ainda não tem ficha.

**A ficha sai pelo botão Impressão do programa**, e não por uma reimplementação:
monta a ``JanelaPrincipal`` invisível, carrega a pasta pelo mesmo worker do
"Abrir pasta" (o ``tools/caso.py``), aceita o agendamento que o próprio diálogo
propõe e chama ``ControleFicha.gerar_pdf``. Sai o que sairia da estação: o
``FICHA_…pdf`` com a capa na frente, o ``ALTA_…pdf`` ao lado, o registro JSON
arquivado no ``.zip`` do paciente, o índice central e a linha no histórico.

As respostas que a tela pediria a uma pessoa, e o que se responde:

* fracionamento de dose alta → o PADRÃO do popup (ver ``caso._responder_dose_alta``);
* agendamento de vários planos → a proposta do próprio diálogo, aceita;
* gating sem modalidade / plano incompleto / 600CD sem portal → "gerar assim";
* SUS → o que o convênio do banco já responde, sem perguntar;
* **"apagar o DICOM da pasta?" → NÃO.** É a pergunta destrutiva do programa, e
  a pasta de TC é o acervo de teste.

Quem fica SEM ficha, de propósito: os pacientes no cenário "vai começar" — são
eles que o gatilho prepara e que a Fichinha mostra como ``● PRONTA``. Uma ficha
já impressa para eles apagaria justamente o fluxo que a demonstração quer
mostrar.

Os arquivos vão para as pastas de ``TCs_Teste`` (é onde o programa grava — ao
lado do DICOM), como numa estação: só ACRESCENTA, nunca apaga.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "tools"))

PASTA_TCS = RAIZ / "TCs_Teste"
SL = PASTA_TCS / "servidor_local"
FEITAS = SL / "fichas_prontas.json"

# O usuário do modo desenvolvimento (``arranque._usuario_de_dev``): é quem abre
# o app pelo ``servidor_local.bat``, e "Suas últimas fichas" filtra por ele.
USUARIO_DEMO = {"usuario": "dev", "papel": "fisico",
                "nome": "Desenvolvedor — demonstração"}

# As janelas já usadas, vivas até o processo acabar — ver ``gerar_ficha``.
_JANELAS: list = []


def ambiente_da_demo() -> None:
    """As MESMAS variáveis do ``servidor_local.bat`` — a ficha tem de nascer do
    mesmo banco e das mesmas simulações que a tela vai mostrar."""
    os.environ.update({
        "ISOCENTRO_BANCO_LOCAL": str(SL / "dw_simulado.sqlite"),
        "ISOCENTRO_LISTA_EXPERIMENTAL": "1",
        "ISOCENTRO_ATIVIDADES_EXPERIMENTAL": "1",
        "ISOCENTRO_GATILHO_EXPERIMENTAL": "1",
        "ISOCENTRO_SIMULACOES": str(SL / "simulacoes"),
        "ISOCENTRO_ESPELHO": str(SL / "espelho"),
        "ISOCENTRO_DATAS_RELEVANTES": str(SL / "datas_relevantes.json"),
        "ISOCENTRO_CHECKLIST": str(SL),        # PASTA: o nome do arquivo é do módulo
        "ISOCENTRO_CAPA_DIR": str(PASTA_TCS / "banco de dados"),
    })
    os.environ.pop("ISOCENTRO_DB_SERVIDOR", None)
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# Quem "criou" os eventos de exemplo — é por esta marca que eles são achados e
# refeitos a cada abertura. Evento cadastrado na demonstração por outra pessoa
# (outro ``por``) nunca é tocado.
POR_DEMO = "demonstração"


def semear_datas() -> int:
    """Os eventos de exemplo das Datas Relevantes, sempre a partir de HOJE.

    Refeitos a cada abertura: semeados uma vez só (até 09/10/2026), dez dias
    depois estavam todos no passado e o quadro parecia abandonado.
    """
    from isocentro.dados import datas_relevantes
    from isocentro.interface import fichinha

    hoje = dt.date.today()
    eventos = [
        (2, "Manutenção preventiva do 6EX", fichinha.TIPO_SERVICO,
         "Máquina parada das 7h às 13h — remarcar os pacientes da manhã."),
        (6, "Auditoria da CQ", fichinha.TIPO_SERVICO,
         "Separar as fichas do mês e os relatórios de dosimetria."),
        (9, "Férias — Helena Amaral", fichinha.TIPO_PESSOAL,
         "Retorno em 15 dias."),
        (14, "Dia do Físico Médico", fichinha.TIPO_COMEMORATIVA, ""),
        (-1, "Calibração do TrueBeam", fichinha.TIPO_SERVICO,
         "Feita — resultado dentro da tolerância."),
    ]
    # Sai o exemplo da abertura anterior: marcado com ``POR_DEMO`` ou — os da
    # primeira versão — com "dev" e um dos títulos de exemplo. Um "dev" com
    # outro título é evento que alguém criou NA TELA da demonstração (o
    # usuário do modo dev se chama "dev"), e fica.
    titulos = {t for _d, t, _tp, _n in eventos}
    for e in datas_relevantes.ler():
        exemplo = (e.get("por") == POR_DEMO
                   or (e.get("por") == "dev" and e.get("titulo") in titulos))
        if exemplo and e.get("id"):
            datas_relevantes.excluir(e["id"])
    for dias, titulo, tipo, nota in eventos:
        datas_relevantes.criar((hoje + dt.timedelta(days=dias)).isoformat(),
                               titulo, tipo, nota, por=POR_DEMO)
    return len(eventos)


def semear_checklists(cenarios: list) -> int:
    """O Checklist Pré-Tratamento do curso atual de cada paciente das pastas.

    Pela função da própria tela (``checklist.marcar``), no arquivo da
    demonstração. Três estados, para o cartão da Ficha Virtual mostrar os três:
    conferido inteiro, conferido com um item NÃO CONFORME ainda sem correção, e
    pela metade (quem começa hoje ainda está sendo conferido).
    """
    import sqlite3

    from isocentro.interface import checklist
    from isocentro.papel import capa_pdf

    if checklist.caminho().exists():
        return 0
    cx = sqlite3.connect(f"file:{(SL / 'dw_simulado.sqlite').as_posix()}?mode=ro",
                         uri=True)
    feitos = 0
    try:
        for n, c in enumerate(cenarios):
            if c["cenario"] == "vai_comecar":
                continue
            linha = cx.execute(
                "SELECT c.DimCourseID FROM DimCourse c JOIN DimPatient p "
                "ON p.DimPatientID = c.DimPatientID WHERE p.PatientId = ? "
                "ORDER BY c.CourseStartDateTime DESC LIMIT 1",
                (c["registro"],)).fetchone()
            if not linha:
                continue
            itens = list(capa_pdf.CHECKLIST_ITENS)
            if c["cenario"] == "primeira":
                itens = itens[:3]
            for i, item in enumerate(itens):
                marca = "C"
                if n % 5 == 2 and i == 4:
                    marca = "N/C"          # a divergência que a tela acusa
                checklist.marcar(c["registro"], linha[0], item, marca, "dev")
            feitos += 1
    finally:
        cx.close()
    return feitos


def aquecer_render_3d() -> tuple:
    """Desenha o corpo 3D de todo RTSTRUCT da demonstração, para o cache.

    É o que tira a espera do clique: a prévia de um caso de quatro planos
    passava 87 s desenhando o corpo, com a janela parada (medido em
    07/10/2026). Com o cache aquecido aqui, o clique na Documentação PRONTA e a
    reabertura de qualquer TC acham o desenho pronto — o MESMO que o app faria,
    pela mesma função (``corpo.renderizar_corpo``, no ângulo da ficha).
    """
    import pydicom

    from isocentro.desenho import corpo

    feitos = ja = 0
    pastas = [p for p in PASTA_TCS.iterdir()
              if p.is_dir() and p.name not in ("banco de dados", "Posicionamento")]
    for pasta in pastas:
        for arq in pasta.rglob("*"):
            if arq.suffix.lower() != ".dcm" or not arq.is_file():
                continue
            nome = arq.name.upper()
            if not (nome.startswith("RS") or "STRCT" in nome or "STRUCT" in nome):
                continue
            try:
                rs = pydicom.dcmread(arq, force=True)
                if getattr(rs, "Modality", "") != "RTSTRUCT":
                    continue
                antes = len(list(corpo._pasta_cache().glob("*.png"))) \
                    if corpo._pasta_cache().is_dir() else 0
                corpo.renderizar_corpo(rs)
                depois = len(list(corpo._pasta_cache().glob("*.png")))
                if depois > antes:
                    feitos += 1
                else:
                    ja += 1
            except Exception:  # noqa: BLE001 — um RTSTRUCT torto não para o resto
                continue
    return feitos, ja


class _Respostas:
    """Liga as respostas automáticas e as DESLIGA no fim (nunca ``del``)."""

    def __init__(self, janela, falar):
        self.janela = janela
        self.falar = falar
        self.recados: list = []
        self._originais: list = []

    def _trocar(self, dono, nome, novo):
        self._originais.append((dono, nome, getattr(dono, nome)))
        setattr(dono, nome, novo)

    def __enter__(self):
        from PySide6.QtWidgets import QDialog

        from isocentro.interface import agendamento_tela, ui

        def anotar(prefixo):
            def _f(_pai, titulo, texto="", *a, **k):
                self.recados.append(f"{prefixo}: {titulo} — {str(texto)[:120]}")
            return _f

        # Só a pergunta de DEPOIS de gerar chega aqui (as de antes vão pelo
        # portão, abaixo) — e a resposta a ela é sempre "não mexer": não apagar
        # o DICOM, não limpar o caso. ``False`` em todo ``confirmar`` garante
        # isso também para uma pergunta que alguém acrescente amanhã.
        self._trocar(ui, "confirmar", lambda *a, **k: False)
        for nome in ("avisar", "alertar", "falhar"):
            self._trocar(ui, nome, anotar(nome))
        self._trocar(os, "startfile", lambda *a, **k: None)
        self._trocar(agendamento_tela.DialogAgendamento, "exec",
                     lambda _self: QDialog.Accepted)
        portao = self.janela.portao
        for nome in ("confirmar_gating_pendente", "confirmar_planos_incompletos"):
            self._trocar(portao, nome, lambda *a, **k: True)
        self._trocar(portao, "confirmar_600cd_sem_portal",
                     lambda *a, **k: True)
        self._trocar(portao, "coletar_sus", lambda dados: True)
        return self

    def __exit__(self, *exc):
        for dono, nome, original in reversed(self._originais):
            setattr(dono, nome, original)
        return False


def gerar_ficha(pasta: Path, medico: str, falar) -> dict:
    """Uma ficha pela Impressão do programa. Devolve o que saiu."""
    import caso as ferramenta
    from PySide6.QtWidgets import QApplication

    from isocentro.dados import historico
    from isocentro.interface import gui

    app = QApplication.instance() or QApplication([])
    gui.aplicar_modo("noite")
    app.setStyleSheet(gui._ESTILO())
    historico.definir_usuario(USUARIO_DEMO)
    janela = gui.JanelaPrincipal(usuario=USUARIO_DEMO)
    antes = {p.name for p in pasta.iterdir()}
    try:
        if not ferramenta._carregar(janela, pasta, lambda m: None):
            return {"ok": False, "motivo": "a pasta não carregou plano nenhum"}
        with _Respostas(janela, falar) as respostas:
            janela._fichinha_carga_assentou()
            janela._abrir_agendamento_pendente()
            # O médico, quando o DICOM não trouxe: o do banco (o mesmo que a
            # Capa mostra). Campo obrigatório da ficha — sem ele a Impressão
            # recusa, como recusaria na estação.
            if not janela.form.eq_medico.currentText().strip() and medico:
                janela.form.eq_medico.setCurrentText(medico)
            janela.controle_ficha.gerar_pdf(preview=False)
        novos = sorted(p.name for p in pasta.iterdir() if p.name not in antes)
        ficha = [n for n in novos if n.upper().startswith("FICHA_")]
        alta = [n for n in novos if n.upper().startswith("ALTA_")]
        return {"ok": bool(ficha), "ficha": ficha, "alta": alta,
                "recados": respostas.recados,
                "motivo": "" if ficha else "a Impressão não gravou a ficha"}
    finally:
        # NÃO ``close()``: o ``closeEvent`` da janela pergunta se pode fechar
        # com caso aberto, e um modal numa janela nunca mostrada derruba o
        # processo inteiro (access violation, sem traceback — medido aqui).
        # Limpar o caso solta a TC da memória, que é o que importa entre um
        # paciente e o próximo; a casca da janela fica viva até o fim.
        try:
            janela._executar_limpeza()
        except Exception:  # noqa: BLE001
            pass
        _JANELAS.append(janela)
        app.processEvents()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("casos", nargs="*", help="só estas pastas (TC8, Elekta/SRS…)")
    ap.add_argument("--refazer", action="store_true",
                    help="gera de novo mesmo quem já tem ficha da demonstração")
    args = ap.parse_args()
    ambiente_da_demo()

    cenarios_arq = SL / "cenarios.json"
    if not cenarios_arq.is_file():
        print("Rode antes: python tools\\montar_servidor_local.py")
        return 1
    cenarios = json.loads(cenarios_arq.read_text(encoding="utf-8"))
    feitas = {}
    if FEITAS.is_file() and not args.refazer:
        feitas = json.loads(FEITAS.read_text(encoding="utf-8"))

    n = semear_datas()
    if n:
        print(f"Datas Relevantes: {n} evento(s) no quadro.")
    n = semear_checklists(cenarios)
    if n:
        print(f"Checklist Pré-Tratamento: {n} curso(s) conferido(s).")
    feitos, ja = aquecer_render_3d()
    print(f"Corpo 3D: {feitos} desenho(s) novo(s) no cache, {ja} já estavam.")
    # Reindexa as fichas das pastas pelo código ATUAL do índice: uma correção
    # nele (como o DVH das fichas de vários planos, 07/10/2026) só chega às
    # fichas já gravadas quando o índice é refeito. Sem remover nada que esteja
    # fora das pastas de TC.
    from isocentro.dados import indice
    n = indice.reconstruir(PASTA_TCS, remover_ausentes=False)
    print(f"Índice central: {n} ficha(s) reindexada(s).")

    falhou = False
    for c in cenarios:
        pasta = PASTA_TCS / c["pasta"]
        if args.casos and c["pasta"] not in args.casos:
            continue
        if c["cenario"] == "vai_comecar":
            print(f"  {c['pasta']:<24} fica SEM ficha — é caso do gatilho "
                  "(● PRONTA na Fichinha)")
            continue
        if c["registro"] in feitas:
            print(f"  {c['pasta']:<24} já tem ficha: {feitas[c['registro']]}")
            continue
        if not pasta.is_dir():
            continue
        print(f"  {c['pasta']:<24} gerando…", flush=True)
        try:
            r = gerar_ficha(pasta, c.get("medico") or "", print)
        except Exception as exc:  # noqa: BLE001 — um caso torto não para o resto
            r = {"ok": False, "motivo": f"{type(exc).__name__}: {exc}"}
        if r["ok"]:
            feitas[c["registro"]] = r["ficha"][0]
            print(f"    ficha: {', '.join(r['ficha'])}")
            print(f"    alta : {', '.join(r['alta']) or '(não saiu)'}")
        else:
            falhou = True
            print(f"    NÃO saiu: {r['motivo']}")
        for recado in r.get("recados") or []:
            print(f"    {recado}")
        FEITAS.write_text(json.dumps(feitas, ensure_ascii=False, indent=1),
                          encoding="utf-8")
    return 1 if falhou else 0


if __name__ == "__main__":
    sys.exit(main())
