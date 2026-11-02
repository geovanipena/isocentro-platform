r"""Monta o SERVIDOR LOCAL de demonstração, a partir de ``TCs_Teste``.

Uso::

    python tools\montar_servidor_local.py              (monta e confere)
    python tools\montar_servidor_local.py --sem-deslocar
    python tools\montar_servidor_local.py --figurantes 0

O que sai, em ``TCs_Teste\servidor_local\`` (fora do git, como o resto da
pasta — é dado de paciente):

* ``dw_simulado.sqlite`` — as TABELAS do data warehouse que o app consulta, lidas
  pelo :mod:`isocentro.banco.servidor_local`;
* ``simulacoes\`` — o cadastro de Simulação de cada TC (notas e fotos da pasta),
  gravado pelo PRÓPRIO ``simulacao.cadastrar``;
* ``indice_dicom.json`` — o índice que o ``servidor_dicom_local.py`` serve.

**De onde vem cada coisa, em ordem de confiança:**

1. As RESPOSTAS REAIS que o ``gravar_banco`` deixou em
   ``TCs_Teste\banco de dados\banco_local.sqlite`` (16 pacientes, 24/09/2026):
   cadastro, convênio, CID, médico, prescrições, anatomia, frequência, foto,
   cursos, sessões e doses. As linhas das tabelas são RECONSTRUÍDAS a partir
   delas — o dado de cada paciente é o do servidor.
2. O DICOM das pastas: o ``SOPInstanceUID`` de cada RTPLAN vira o ``PlanUID`` do
   plano de mesmo nome, e é o que o gatilho pede ao servidor DICOM. Paciente
   que o banco não conhece (os da Elekta) nasce inteiro do DICOM.
3. O que NUNCA foi gravado — agenda, atividades, e os FIGURANTES ``900NNNN``
   que enchem a agenda até ela parecer um dia de clínica — é GERADO, de forma
   determinística (mesma semente, mesmo resultado), a partir das sessões acima.

**As datas são DESLOCADAS**, em semanas inteiras (o dia da semana não muda),
para cada paciente cair num momento do tratamento: começando hoje, no meio, na
última sessão, concluído há poucos dias, ou começando na semana que vem — este
último é o que alimenta o gatilho (Documentação aberta, plano "Planning
Approved", nenhuma sessão ainda). Sem o deslocamento, a gravação de setembro
não teria ninguém "em tratamento" num dia de demonstração em outubro.
``--sem-deslocar`` guarda as datas reais.

A tela anuncia tudo isso: o ``banco_local.resumo`` diz "SERVIDOR LOCAL
(demonstração)", com o deslocamento, onde hoje diria o nome do servidor.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import random
import sqlite3
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from isocentro.banco import banco_local, servidor_local  # noqa: E402

PASTA_TCS = RAIZ / "TCs_Teste"
GRAVACAO = PASTA_TCS / "banco de dados" / "banco_local.sqlite"
SAIDA = PASTA_TCS / "servidor_local"
ARQUIVO_DW = SAIDA / "dw_simulado.sqlite"
INDICE_DICOM = SAIDA / "indice_dicom.json"

FMT = "%Y-%m-%d %H:%M:%S"
MINUTOS_POR_SESSAO = 12

# As máquinas da agenda, com os MESMOS ``ctrResourceSer`` dos testes e os nomes
# que o ``agenda_db`` espera: o ``MachineFullName`` é o que vira o nome de
# exibição e é a chave de ``agenda_db.HORAS_MAQUINA``; o ``MachineId`` é o que
# casa com ``DimMachine`` no resumo do mês.
#   (ctr, MachineId, MachineFullName, abre, fecha, trata)
MAQUINAS = [
    (1035, "6EX", "6EX", 8, 18, True),
    (1499, "TBuniverSN1002", "TB Universitario", 7, 20, True),
    (1252, "TrueBeamSN1001", "VitalBeam", 7, 16, True),
    (1046, "600CD", "600CD", 8, 18, True),
    (1600, "GammaMed Plus", "Braquiterapia", 8, 17, False),
    (1400, "Ortovoltagem", "Dermopan", 8, 17, False),
    (1700, "Eclipse CAP", "Eclipse CAP", 8, 17, False),   # a da lista negativa
]
LINACS = [m for m in MAQUINAS if m[5]]

# Os momentos do tratamento em que cada paciente de TC é posto, em rodízio.
CENARIOS = ("meio", "vai_comecar", "meio", "concluido", "primeira", "meio",
            "ultima", "meio", "vai_comecar", "meio", "concluido", "meio",
            "primeira", "meio", "ultima", "vai_comecar", "meio", "meio",
            "concluido", "meio", "meio", "vai_comecar")

SITIOS = [  # (palavras que indicam, token da agenda, CID, título do CID)
    (("MAMA", "BREAST", "FSC", "PAREDE"), "MAMA", "C50.9", "Neoplasia maligna da mama"),
    (("PROST",), "PROSTATA", "C61", "Neoplasia maligna da próstata"),
    (("PULM", "THORAX", "TORAX", "ESOF", "MEDIAST"), "TORAX", "C34.9", "Neoplasia maligna dos brônquios ou pulmões"),
    (("PELV", "RETO", "RECT", "COLO", "UTER", "CERV", "ENDOM", "BEXIGA", "CANAL"), "PELVE", "C53.9", "Neoplasia maligna do colo do útero"),
    (("NEURO", "CSI"), "NEUROEIXO", "C71.9", "Neoplasia maligna do encéfalo"),
    (("CRAN", "BRAIN", "CEREB", "SRS", "ENCEF", "HEAD"), "CRANIO", "C79.3", "Neoplasia maligna secundária do cérebro"),
    (("CP", "CABE", "NECK", "LARIN", "OROF", "BOCA", "PARÓT", "PAROT", "TIREO"), "CP", "C32.9", "Neoplasia maligna da laringe"),
    (("ABDO", "ESTOM", "PANCR", "FIGAD"), "ABDOME", "C16.9", "Neoplasia maligna do estômago"),
    (("PELE", "SKIN"), "PELE", "C44.9", "Neoplasia maligna da pele"),
    (("OSSO", "FEMUR", "UMER", "EXTREM"), "EXTREMIDADE", "C79.5", "Neoplasia maligna secundária dos ossos"),
    (("SBRT",), "SBRT", "C78.0", "Neoplasia maligna secundária do pulmão"),
]

PRIMEIROS_F = ["Ana", "Maria", "Luciana", "Patrícia", "Fabiana", "Juliana",
               "Cláudia", "Regina", "Sandra", "Helena", "Beatriz", "Rosa",
               "Aparecida", "Tereza", "Márcia", "Denise", "Vera", "Lúcia"]
PRIMEIROS_M = ["Ademar", "Wilson", "Carlos", "Paulo", "Antônio", "Francisco",
               "Luiz", "Mauricio", "Plinio", "Roberto", "Sebastião", "Jorge",
               "Reinaldo", "Eduardo", "Sérgio", "Valter", "Osmar", "Nelson"]
SOBRENOMES = ["Almeida", "Barbosa", "Cardoso", "Correia", "Dias", "Farias",
              "Gomes", "Lima", "Peixoto", "Moreira", "Nogueira", "Pinheiro",
              "Queiroz", "Rezende", "Siqueira", "Teixeira", "Vasconcelos",
              "Xavier", "Zanetti", "Brandão", "Campos", "Fonseca", "Leal"]

# (ctrResourceSer, FullName, OwnerName). O ``FullName`` no formato do ARIA —
# "Nome Sobrenome (INICIAIS)", como em ``fichinha._primeiro_nome`` —, e NÃO
# "Sobrenome, Nome": a Documentação mostra a primeira palavra, e saía "Pena,"
# no lugar de "Geovani" (09/10/2026).
DONOS = [
    (5001, "Geovani Pena (GP)", "GP"),
    (5002, "Helena Amaral (HA)", "HA"),   # fictícios: a equipe da demonstração
    (5003, "Tiago Rocha (TR)", "TR"),
]


def _medicos_de_verdade(nomes) -> list:
    """Os médicos para SORTEAR — sem os cadastros de teste do ARIA.

    A lista gravada traz "fisica, fisica" e "Toast, Test", que existem no banco
    real e ficam na tabela (são dado), mas sorteá-los para paciente punha
    "Fisica Fisica" como médico de um terço da agenda na demonstração.
    """
    candidatos = [n for n in nomes
                  if not any(t in n.lower() for t in ("fisica", "test", "toast"))]
    # E só quem está na EQUIPE configurada, pelo MESMO casamento de nome que as
    # listas de médico do app usam (``tratamento_db._medicos_do_banco``).
    # Sorteado fora dela, o médico tem paciente no banco e não aparece em lista
    # nenhuma — "Sarah Barcelos não está na lista de médicos, nem Ricardo
    # Alarcão" (09/10/2026), os dois com dezenas de figurantes.
    try:
        from isocentro.banco import capa_dados, tratamento_db
        from isocentro.dicom import dicom_rt
        equipe = tratamento_db._equipe_configurada()
    except Exception:  # noqa: BLE001 — sem equipe lida, vale o filtro de cima
        equipe = None
    if equipe:
        candidatos = [n for n in candidatos
                      if dicom_rt.mesma_pessoa(capa_dados.de_pessoa(n), equipe)]
    return sorted(candidatos)


def _semente(*partes) -> int:
    return int(hashlib.sha1("|".join(map(str, partes)).encode()).hexdigest()[:8], 16)


def _txt(v) -> str:
    return "" if v is None else str(v).strip()


def _fmt(v):
    if isinstance(v, dt.datetime):
        return v.strftime(FMT)
    if isinstance(v, dt.date):
        return dt.datetime(v.year, v.month, v.day).strftime(FMT)
    return v


def _dias_uteis(inicio: dt.date, n: int, passo: int = 1) -> list:
    """``n`` dias úteis a partir de ``inicio`` (inclusive), andando ``passo``."""
    dias, d = [], inicio
    while len(dias) < n:
        if d.weekday() < 5:
            dias.append(d)
        d += dt.timedelta(days=passo)
    return dias


def _sitio(*textos) -> tuple:
    alvo = " ".join(_txt(t).upper() for t in textos)
    for palavras, token, cid, titulo in SITIOS:
        if any(p in alvo for p in palavras):
            return token, cid, titulo
    return "PALIATIVO", "C80.9", "Neoplasia maligna sem especificação de localização"


# ── 1. O que foi GRAVADO ────────────────────────────────────────────────────

_ASSINATURAS = [  # (nome, trecho do SQL normalizado que identifica a consulta)
    ("cadastro", "LEFT JOIN DWH.FactPatient fp"),
    ("convenio", "FROM DWH.FactPatientPayor"),
    ("curso_capa", "SELECT TOP 1 c.DimCourseID, c.CourseId"),
    ("diagnostico", "FROM DWH.FactPatientDiagnosis"),
    ("medico_paciente", "JOIN DWH.DimPatient p ON p.DimPatientID = pd.DimPatientID"),
    ("medico_capa", "SELECT TOP 1 d.DoctorFullName FROM DWH.DimPatientDoctor pd JOIN DWH.DimDoctor"),
    ("prescricoes", "SELECT DISTINCT rx.PrescriptionName"),
    ("anatomia", "FROM DWH.DimPrescriptionAnatomy"),
    ("frequencia", "SELECT DISTINCT PropertyValue FROM DWH.DimPrescriptionProperty"),
    ("notas", "SELECT TOP 1 Notes"),
    ("foto", "ph.Picture"),
    ("cursos", "SELECT th.DimCourseID, MAX(c.CourseId), COUNT(DISTINCT th.FractionNumber)"),
    ("sessoes", "SELECT th.FractionNumber, MIN(th.TreatmentStartTime)"),
    ("resumo", "SELECT TOP 1 th.FractionsDelivered"),
    ("dose_plano", "SELECT th.DimPlanID, MAX(pl.PlanSetupId)"),
    ("medicos", "SELECT DISTINCT d.DoctorFullName"),
]


def ler_gravacao(caminho: Path) -> tuple:
    """``({consulta: {params: linhas}}, [(registro, pasta, achou)])``."""
    if not caminho.is_file():
        return {}, []
    cx = sqlite3.connect(f"file:{caminho.as_posix()}?mode=ro", uri=True)
    respostas: dict = {}
    for sql, params, linhas in cx.execute(
            "SELECT sql, params, linhas FROM respostas"):
        nome = next((n for n, trecho in _ASSINATURAS if trecho in sql), None)
        if nome is None:
            continue
        chave = tuple(json.loads(params))
        respostas.setdefault(nome, {})[chave] = [
            [banco_local._decodificar(c) for c in linha]
            for linha in json.loads(linhas)]
    pacientes = [(r, p, bool(a)) for r, p, a in cx.execute(
        "SELECT registro, pasta, achou FROM pacientes")]
    cx.close()
    return respostas, pacientes


# ── 2. O DICOM das pastas ───────────────────────────────────────────────────

def indexar_dicom(forcar: bool = False) -> list:
    """Uma entrada por objeto DICOM de ``TCs_Teste``. Reaproveita o índice
    gravado quando nenhuma pasta mudou — ler ~4 mil cabeçalhos custa quase um
    minuto, e o ``.bat`` monta o servidor a cada abertura."""
    import pydicom

    pastas = sorted(p for p in PASTA_TCS.iterdir()
                    if p.is_dir() and p.name not in ("banco de dados",
                                                     "servidor_local",
                                                     "Posicionamento"))
    marca = max((f.stat().st_mtime for p in pastas for f in p.rglob("*")
                 if f.is_file()), default=0)
    if INDICE_DICOM.is_file() and not forcar:
        try:
            antigo = json.loads(INDICE_DICOM.read_text(encoding="utf-8"))
            if antigo.get("marca") == marca:
                return antigo["objetos"]
        except (OSError, ValueError, KeyError):
            pass
    objetos = []
    for pasta in pastas:
        for arq in sorted(pasta.rglob("*")):
            if arq.suffix.lower() != ".dcm":
                continue
            try:
                ds = pydicom.dcmread(arq, stop_before_pixels=True, force=True)
            except Exception:  # noqa: BLE001 — arquivo torto não derruba o índice
                continue
            uid = _txt(getattr(ds, "SOPInstanceUID", ""))
            if not uid:
                continue
            item = {
                "caminho": str(arq.relative_to(PASTA_TCS)),
                "pasta": str(arq.parent.relative_to(PASTA_TCS)).replace("\\", "/"),
                "PatientID": _txt(getattr(ds, "PatientID", "")),
                "PatientName": _txt(getattr(ds, "PatientName", "")),
                "PatientBirthDate": _txt(getattr(ds, "PatientBirthDate", "")),
                "PatientSex": _txt(getattr(ds, "PatientSex", "")),
                "StudyInstanceUID": _txt(getattr(ds, "StudyInstanceUID", "")),
                "SeriesInstanceUID": _txt(getattr(ds, "SeriesInstanceUID", "")),
                "SOPInstanceUID": uid,
                "SOPClassUID": _txt(getattr(ds, "SOPClassUID", "")),
                "Modality": _txt(getattr(ds, "Modality", "")),
                "SeriesDescription": _txt(getattr(ds, "SeriesDescription", "")),
                "StudyDate": _txt(getattr(ds, "StudyDate", "")),
            }
            if item["Modality"] == "RTPLAN":
                item["RTPlanLabel"] = _txt(getattr(ds, "RTPlanLabel", ""))
                fracoes = 0
                for g in getattr(ds, "FractionGroupSequence", None) or []:
                    fracoes = max(fracoes, int(getattr(g, "NumberOfFractionsPlanned", 0) or 0))
                item["fracoes"] = fracoes
                dose = 0.0
                for ref in getattr(ds, "DoseReferenceSequence", None) or []:
                    dose = max(dose, float(getattr(ref, "TargetPrescriptionDose", 0) or 0))
                item["dose_gy"] = dose
                maquinas = {_txt(getattr(b, "TreatmentMachineName", ""))
                            for b in getattr(ds, "BeamSequence", None) or []}
                item["maquina"] = sorted(m for m in maquinas if m)[:1]
            objetos.append(item)
    SAIDA.mkdir(parents=True, exist_ok=True)
    INDICE_DICOM.write_text(json.dumps({"marca": marca, "objetos": objetos},
                                       ensure_ascii=False), encoding="utf-8")
    return objetos


# ── 3. O esquema ────────────────────────────────────────────────────────────

ESQUEMA = """
CREATE TABLE sobre (chave TEXT PRIMARY KEY, valor TEXT);
CREATE TABLE DimPatient (DimPatientID INTEGER PRIMARY KEY, PatientId TEXT,
    PatientFullName TEXT, PatientDateOfBirth TEXT, PatientMobilePhone TEXT,
    PatientHomePhone TEXT, PatientWorkPhone TEXT, IsMOTestPatient INTEGER);
CREATE TABLE FactPatient (DimPatientID INTEGER, DimLookupID_Gender INTEGER);
CREATE TABLE DimLookup (DimLookupID INTEGER PRIMARY KEY,
    LookupDescriptionPTB TEXT, LookupDescriptionENU TEXT);
CREATE TABLE DimPayor (DimPayorID INTEGER PRIMARY KEY, PayorCompanyName TEXT,
    PayorPlanNumber TEXT);
CREATE TABLE FactPatientPayor (FactPatientPayorID INTEGER PRIMARY KEY,
    DimPatientID INTEGER, DimPayorID INTEGER, PayorPolicyNumber TEXT,
    PayorCurrentAccountNumber TEXT, IsPrimaryPayor INTEGER);
CREATE TABLE DimCourse (DimCourseID INTEGER PRIMARY KEY, DimPatientID INTEGER,
    CourseId TEXT, DimLookupID_TreatmentIntentType INTEGER,
    DimLookupID_ClinicalStatus INTEGER, CourseStartDateTime TEXT);
CREATE TABLE DimDiagnosisCode (DimDiagnosisCodeID INTEGER PRIMARY KEY,
    DiagnosisCode TEXT, DiagnosisFullTitlePTB TEXT,
    DiagnosisClinicalDescriptionPTB TEXT);
CREATE TABLE FactPatientDiagnosis (FactPatientDiagnosisID INTEGER PRIMARY KEY,
    DimPatientID INTEGER, DimDiagnosisCodeID INTEGER,
    DiagnosisDescription TEXT, DiagnosisStatusDate TEXT);
CREATE TABLE DimDoctor (ctrResourceSer INTEGER PRIMARY KEY,
    DoctorFullName TEXT);
CREATE TABLE DimPatientDoctor (DimPatientID INTEGER, ctrResourceSer INTEGER,
    OncologistFlag INTEGER, PrimaryFlag INTEGER);
CREATE TABLE DimMachine (DimMachineID INTEGER PRIMARY KEY, MachineId TEXT,
    MachineAliasName TEXT, MachineFullName TEXT);
CREATE TABLE DimPlan (DimPlanID INTEGER PRIMARY KEY, DimCourseID INTEGER,
    PlanSetupId TEXT, PlanUID TEXT, PlanRevision INTEGER,
    NoFractionsPlanned INTEGER, DimLookupID_PlanStatus INTEGER,
    StatusUserName TEXT, CreationDate TEXT);
CREATE TABLE GetPatientPlan (DimPatientID INTEGER, DimPlanID INTEGER);
CREATE TABLE FactTreatmentHistory (DimPatientID INTEGER, DimCourseID INTEGER,
    DimPlanID INTEGER, FractionNumber INTEGER, TreatmentStartTime TEXT,
    DimActualMachineID INTEGER, DimPlanMachineID INTEGER,
    TreatmentSignOffUser1 TEXT, TreatmentSignOffUser2 TEXT,
    FractionsPlanned INTEGER, FractionsDelivered INTEGER,
    CourseDoseDelivered REAL, CourseDosePlanned REAL, PrimaryFlag INTEGER,
    FirstTreatmentDate TEXT, LastTreatmentDate TEXT);
CREATE TABLE DimPrescription (DimPrescriptionID INTEGER PRIMARY KEY,
    ctrPrescriptionSer INTEGER, PrescriptionName TEXT, Site TEXT,
    NumberOfFractions INTEGER, ApprovedOn TEXT, ApprovedBy TEXT, Status TEXT,
    Notes TEXT, HstryDateTime TEXT);
CREATE TABLE FactPatientPrescription (DimPrescriptionID INTEGER,
    DimPatientID INTEGER, DimCourseID INTEGER);
CREATE TABLE DimPrescriptionAnatomy (ctrPrescriptionAnatomySer INTEGER
    PRIMARY KEY, ctrPrescriptionSer INTEGER, ItemType TEXT, ItemValue TEXT,
    ItemValueUnit TEXT);
CREATE TABLE DimPrescriptionProperty (ctrPrescriptionSer INTEGER,
    PropertyType INTEGER, PropertyValue TEXT);
CREATE TABLE DimPatientPhoto (DimPatientPhotoID INTEGER PRIMARY KEY,
    DimPatientID INTEGER, Picture BLOB);
CREATE TABLE InSightiveResourceMachine (ctrResourceSer INTEGER PRIMARY KEY,
    MachineId TEXT, MachineFullName TEXT, ResourceObjectStatus TEXT,
    MachineType TEXT);
CREATE TABLE DimActivity (DimActivityID INTEGER PRIMARY KEY,
    ActivityCode TEXT, ActivityNamePTB TEXT, ActivityCategoryPTB TEXT,
    ActivityCategoryCode TEXT);
CREATE TABLE DimActivityTransaction (ctrActivityInstanceSer INTEGER
    PRIMARY KEY, DimActivityID INTEGER, DimPatientID INTEGER,
    ctrResourceSer INTEGER, AppointmentDateTime TEXT, AppointmentStatus TEXT,
    DerivedAppointmentTaskDate TEXT, IsScheduled INTEGER,
    WaitListedFlag INTEGER);
CREATE TABLE GetTaskOwnerName (ctrActivityInstanceSer INTEGER,
    ctrResourceSer INTEGER, FullName TEXT, OwnerName TEXT,
    ActivityOwnerFlag INTEGER);
CREATE TABLE GetPredeccesorAndCurrentActivityStatus (
    ctrActivityInstanceSer INTEGER, DerivedActivityStatus TEXT,
    PredecessorAppointmentStatus TEXT, ctrPredecessorSer INTEGER,
    IsScheduled INTEGER);
CREATE INDEX ix_th_pac ON FactTreatmentHistory (DimPatientID, DimCourseID);
CREATE INDEX ix_th_ini ON FactTreatmentHistory (TreatmentStartTime);
CREATE INDEX ix_at_data ON DimActivityTransaction (AppointmentDateTime);
CREATE INDEX ix_pac_id ON DimPatient (PatientId);
"""


class Montador:
    """Junta as linhas das tabelas e grava no fim — ver :func:`montar`."""

    def __init__(self, agora: dt.datetime):
        self.agora = agora
        self.hoje = agora.date()
        self.linhas: dict = {}
        self._ids: dict = {}
        self.lookup: dict = {}
        self.doutores: dict = {}
        self.maquina_id: dict = {}   # MachineId -> DimMachineID
        self.atividade_id: dict = {}
        self.avisos: list = []

    def por(self, tabela: str, *valores) -> None:
        self.linhas.setdefault(tabela, []).append(tuple(valores))

    def novo_id(self, serie: str, inicio: int = 900000) -> int:
        self._ids[serie] = self._ids.get(serie, inicio) + 1
        return self._ids[serie]

    def id_lookup(self, ptb: str = "", enu: str = "") -> int:
        chave = (ptb, enu)
        if chave not in self.lookup:
            self.lookup[chave] = self.novo_id("lookup", 100)
            self.por("DimLookup", self.lookup[chave], ptb or None, enu or None)
        return self.lookup[chave]

    def id_doutor(self, nome: str) -> int:
        if nome not in self.doutores:
            self.doutores[nome] = self.novo_id("doutor", 7000)
            self.por("DimDoctor", self.doutores[nome], nome)
        return self.doutores[nome]

    def id_maquina(self, machine_id: str) -> int:
        if machine_id not in self.maquina_id:
            self.maquina_id[machine_id] = self.novo_id("maquina", 10)
            self.por("DimMachine", self.maquina_id[machine_id], machine_id,
                     "NA", "NA")
        return self.maquina_id[machine_id]

    def id_atividade(self, codigo: str, nome: str, categoria: str) -> int:
        if (codigo, nome) not in self.atividade_id:
            self.atividade_id[(codigo, nome)] = self.novo_id("atividade", 300)
            self.por("DimActivity", self.atividade_id[(codigo, nome)], codigo,
                     nome, categoria, categoria.upper().replace(" ", "_"))
        return self.atividade_id[(codigo, nome)]

    def gravar(self, destino: Path, sobre: dict) -> None:
        destino.parent.mkdir(parents=True, exist_ok=True)
        provisorio = destino.with_suffix(".montando")
        provisorio.unlink(missing_ok=True)
        cx = sqlite3.connect(str(provisorio))
        cx.executescript(ESQUEMA)
        for tabela, linhas in self.linhas.items():
            if not linhas:
                continue
            marcas = ",".join("?" * len(linhas[0]))
            cx.executemany(f"INSERT INTO {tabela} VALUES ({marcas})",
                           [tuple(_fmt(v) for v in linha) for linha in linhas])
        cx.executemany("INSERT INTO sobre VALUES (?, ?)",
                       [(k, str(v)) for k, v in sobre.items()])
        cx.commit()
        cx.close()
        # Troca no fim, inteira: o app pode estar aberto lendo o anterior, e um
        # arquivo pela metade responderia consulta com tabela faltando.
        try:
            provisorio.replace(destino)
        except PermissionError:
            # O Windows não troca arquivo aberto. Com o app (ou outro montador)
            # lendo o banco, o novo fica de lado e o antigo continua valendo —
            # dito em voz alta, porque as datas do antigo são de outro dia.
            provisorio.unlink(missing_ok=True)
            raise SystemExit(
                f"O banco {destino} está em uso (o app está aberto?). Feche o "
                "app e monte de novo — o banco antigo continua valendo.") from None


# ── 4. Pacientes: reconstruídos da gravação, ou do DICOM ────────────────────

def _maquina_da_clinica(nome: str) -> str:
    """O nome de máquina gravado → o ``MachineId`` de uma das quatro da agenda.

    A gravação traz nomes de anos diferentes ("600C" em 2019, "600CD" hoje), e a
    agenda só conhece as quatro de :data:`MAQUINAS`. Casar aqui é o que faz o
    resumo do mês contar as sessões de cada paciente na coluna certa.
    """
    alvo = _txt(nome).upper()
    if "UNIVER" in alvo or alvo.startswith("TB"):
        return "TBuniverSN1002"
    if "4199" in alvo or "VITAL" in alvo:
        return "TrueBeamSN1001"
    if "6EX" in alvo:
        return "6EX"
    if "600" in alvo:
        return "600CD"
    if "TRUEBEAM" in alvo:
        return "TBuniverSN1002"
    return "6EX"


def pacientes_gravados(resp: dict, lista: list) -> list:
    """Um dicionário por paciente que o banco CONHECIA na gravação."""
    fora = []
    for registro, pasta, achou in sorted(lista, key=lambda x: x[1]):
        if not achou:
            continue
        cad = (resp.get("cadastro", {}).get((registro,)) or [None])[0]
        if not cad:
            continue
        dim = int(cad[5])
        p = {
            "registro": registro, "pasta": pasta, "dim": dim,
            "nome": _txt(cad[1]), "nascimento": cad[2], "sexo": _txt(cad[3]),
            "telefone": _txt(cad[4]),
            "convenio": (resp.get("convenio", {}).get((str(dim),)) or [None])[0],
            "curso_capa": (resp.get("curso_capa", {}).get((str(dim),)) or [None])[0],
            "diagnostico": (resp.get("diagnostico", {}).get((str(dim),)) or [None])[0],
            "medico": _txt(((resp.get("medico_capa", {}).get((str(dim),)) or [[None]])[0] or [None])[0]),
            "prescricoes": resp.get("prescricoes", {}).get((registro,)) or [],
            "foto": ((resp.get("foto", {}).get((registro,)) or [[None]])[0] or [None])[0],
            "cursos": resp.get("cursos", {}).get((registro,)) or [],
            "sessoes": {}, "resumo": {}, "dose_plano": {},
            "anatomia": {}, "frequencia": {}, "notas": {},
            "origem": "gravacao",
        }
        for curso in p["cursos"]:
            c = str(curso[0])
            p["sessoes"][int(c)] = resp.get("sessoes", {}).get((registro, c)) or []
            p["resumo"][int(c)] = (resp.get("resumo", {}).get((registro, c)) or [None])[0]
            p["dose_plano"][int(c)] = resp.get("dose_plano", {}).get((registro, c)) or []
        for rx in p["prescricoes"]:
            ser = str(rx[6])
            p["anatomia"][ser] = resp.get("anatomia", {}).get((ser,)) or []
            p["frequencia"][ser] = [l[0] for l in resp.get("frequencia", {}).get((ser,)) or []]
            p["notas"][ser] = ((resp.get("notas", {}).get((ser,)) or [[None]])[0] or [None])[0]
        fora.append(p)
    return fora


def _nome_dicom(bruto: str) -> str:
    partes = [x.strip() for x in bruto.split("^") if x.strip()]
    if len(partes) >= 2:
        return f"{partes[0]}, {' '.join(partes[1:])}"
    return bruto


def pacientes_do_dicom(objetos: list, conhecidos: set, montador) -> list:
    """Quem tem RTPLAN nas pastas e o banco não conhecia (os da Elekta)."""
    por_pasta: dict = {}
    for o in objetos:
        if o["Modality"] == "RTPLAN":
            por_pasta.setdefault(o["pasta"], []).append(o)
    fora = []
    for pasta, planos in sorted(por_pasta.items()):
        registro = planos[0]["PatientID"]
        if not registro or registro in conhecidos or any(
                pasta.startswith(p) for p in conhecidos):
            continue
        conhecidos.add(registro)
        nasc = planos[0]["PatientBirthDate"]
        try:
            nascimento = dt.datetime.strptime(nasc, "%Y%m%d") if nasc else None
        except ValueError:
            nascimento = None
        rng = random.Random(_semente(registro))
        dim = montador.novo_id("paciente")
        curso = montador.novo_id("curso")
        inicio = dt.date(2025, 3, 3) + dt.timedelta(days=7 * rng.randint(0, 20))
        maquina = _maquina_da_clinica((planos[0].get("maquina") or [""])[0])
        hora = dt.time(8 + rng.randint(0, 8), rng.choice((0, 12, 24, 36, 48)))
        sessoes, resumo, doses = [], None, []
        for plano in planos:
            plano_id = montador.novo_id("plano")
            n = plano.get("fracoes") or 25
            dose = plano.get("dose_gy") or 2.0 * n
            dias = _dias_uteis(inicio, n)
            for i, d in enumerate(dias, 1):
                sessoes.append([i, dt.datetime.combine(d, hora), maquina,
                                "tecnico.demo", plano_id, n,
                                plano["RTPlanLabel"] or "PLANO", None])
            doses.append([plano_id, plano["RTPlanLabel"], dose, dose])
            resumo = [n, n, dose, dose]
        fora.append({
            "registro": registro, "pasta": pasta, "dim": dim,
            "nome": _nome_dicom(planos[0]["PatientName"]),
            "nascimento": nascimento,
            "sexo": {"M": "Masculino", "F": "Feminino"}.get(planos[0]["PatientSex"], "Desconhecido"),
            "telefone": "", "convenio": None,
            "curso_capa": [curso, "C1", "Curativa"], "diagnostico": None,
            "medico": "", "foto": None, "origem": "dicom",
            "prescricoes": [], "anatomia": {}, "frequencia": {}, "notas": {},
            "cursos": [[curso, "C1", 0, 0, None, None]],
            "sessoes": {curso: sessoes}, "resumo": {curso: resumo},
            "dose_plano": {curso: doses},
        })
    return fora


# ── 5. O deslocamento das datas ─────────────────────────────────────────────

def _deslocamento(dias_tratados: list, cenario: str, hoje: dt.date) -> int:
    """Quantos dias (múltiplo de 7) somar para o curso cair no ``cenario``."""
    if not dias_tratados:
        return 0
    dias = sorted(set(dias_tratados))

    def semanas_para(origem: dt.date, alvo: dt.date) -> int:
        return 7 * round((alvo - origem).days / 7)

    if cenario == "vai_comecar":
        # Primeira sessão entre amanhã e daqui a uma semana.
        d = semanas_para(dias[0], hoje + dt.timedelta(days=4))
        while dias[0] + dt.timedelta(days=d) <= hoje:
            d += 7
        return d
    if cenario == "concluido":
        d = semanas_para(dias[-1], hoje - dt.timedelta(days=4))
        while dias[-1] + dt.timedelta(days=d) >= hoje:
            d -= 7
        return d
    indice = {"primeira": 0, "ultima": len(dias) - 1}.get(cenario, len(dias) // 2)
    # Prefere um dia do MESMO dia da semana de hoje, perto do índice escolhido:
    # é o que faz a sessão cair exatamente hoje, e não "por volta de hoje".
    candidatos = [i for i, d in enumerate(dias) if d.weekday() == hoje.weekday()]
    if candidatos:
        indice = min(candidatos, key=lambda i: abs(i - indice))
        return (hoje - dias[indice]).days
    return semanas_para(dias[indice], hoje)


def _mover(v, dias: int):
    if dias == 0 or v is None:
        return v
    if isinstance(v, dt.datetime):
        return v + dt.timedelta(days=dias)
    if isinstance(v, dt.date):
        return v + dt.timedelta(days=dias)
    return v


# ── 6. Um paciente vira linhas ──────────────────────────────────────────────

def lancar_paciente(m: Montador, p: dict, cenario: str, deslocar: bool,
                    planos_dicom: dict, agenda: list) -> dict:
    """Grava o paciente ``p`` nas tabelas. Devolve o que o resto precisa saber."""
    cursos = sorted(p["cursos"], key=lambda c: c[5] or dt.datetime.min)
    ultimo = int(cursos[-1][0]) if cursos else None
    dias_ultimo = [s[1].date() for s in p["sessoes"].get(ultimo, []) if s[1]]
    desl = _deslocamento(dias_ultimo, cenario, m.hoje) if deslocar else 0

    dim = p["dim"]
    m.por("DimPatient", dim, p["registro"], p["nome"], p["nascimento"],
          p["telefone"] or "NA", "NA", "NA", 0)
    m.por("FactPatient", dim, m.id_lookup(p["sexo"] or "Desconhecido", ""))
    if p["convenio"]:
        payor = m.novo_id("payor", 400)
        m.por("DimPayor", payor, p["convenio"][0], "NA")
        m.por("FactPatientPayor", m.novo_id("fpayor"), dim, payor,
              p["convenio"][1] or "NA", "NA", 1)
    medico = p["medico"]
    sorteaveis = _medicos_de_verdade(m.doutores)
    if not medico and sorteaveis:
        medico = sorteaveis[_semente(p["registro"]) % len(sorteaveis)]
    if medico:
        m.por("DimPatientDoctor", dim, m.id_doutor(medico), 1, 1)

    # Curso a curso. O ÚLTIMO recebe o cenário; os anteriores só andam junto.
    intencao_capa = (p["curso_capa"] or [None, None, None])[2]
    rx_por_curso: dict = {}
    for rx in p["prescricoes"]:
        rx_por_curso.setdefault(_txt(rx[2]), []).append(rx)
    ids_curso = {_txt(c[1]): int(c[0]) for c in cursos}
    for nome_curso in rx_por_curso:
        if nome_curso and nome_curso not in ids_curso:
            # Prescrição de um curso que não tratou (planejado, não iniciado).
            ids_curso[nome_curso] = m.novo_id("curso")
            cursos.append([ids_curso[nome_curso], nome_curso, 0, 0, None, None])

    sitio, cid, titulo = _sitio(*(rx[0] for rx in p["prescricoes"]),
                                *(rx[1] for rx in p["prescricoes"]),
                                p["pasta"])
    info = {"registro": p["registro"], "dim": dim, "cenario": cenario,
            "deslocamento": desl, "sitio": sitio, "medico": medico,
            "curso_ativo": None, "planos_aprovar": [], "fim": None}

    for curso in cursos:
        dim_curso = int(curso[0])
        ativo = dim_curso == ultimo and cenario != "concluido"
        sessoes = p["sessoes"].get(dim_curso, [])
        inicio_curso = min((s[1] for s in sessoes if s[1]), default=None)
        if inicio_curso is None:
            rxs = rx_por_curso.get(_txt(curso[1]), [])
            inicio_curso = min((rx[4] for rx in rxs if rx[4]), default=None)
        inicio_curso = _mover(inicio_curso, desl) or m.agora
        m.por("DimCourse", dim_curso, dim, _txt(curso[1]),
              m.id_lookup(intencao_capa or "Curativa", ""),
              m.id_lookup("", "ACTIVE" if ativo or dim_curso != ultimo and not sessoes else "COMPLETED"),
              inicio_curso - dt.timedelta(days=10))
        if ativo:
            info["curso_ativo"] = dim_curso

        # Planos: das sessões, das doses e do DICOM.
        planos: dict = {}
        for s in sessoes:
            planos.setdefault(int(s[4]), {"id": _txt(s[6]), "fx": int(s[5] or 0),
                                          "maquina": _maquina_da_clinica(s[2])})
        for d in p["dose_plano"].get(dim_curso, []):
            planos.setdefault(int(d[0]), {"id": _txt(d[1]), "fx": 0,
                                          "maquina": "6EX"})
            planos[int(d[0])]["dose"] = (d[2], d[3])
        for plano_id, pl in planos.items():
            uid = planos_dicom.get((p["registro"], pl["id"].upper()))
            tem_dicom = bool(uid)
            if not uid:
                uid = f"1.2.826.0.1.3680043.10.543.{plano_id}"
            estado = "Treatment Approved" if ativo else "Completed"
            if ativo and cenario == "vai_comecar":
                # Só o plano que EXISTE nas pastas é aprovado para o gatilho:
                # os outros não têm arquivo para o servidor DICOM entregar, e
                # a demonstração mostraria "nada chegou" onde o circuito está
                # certo. Eles ficam como rascunho, que é o degrau "plano
                # existe, nenhum aprovado" da conferência.
                estado = "Planning Approved" if tem_dicom else "Unapproved"
                if tem_dicom:
                    info["planos_aprovar"].append(pl["id"])
            m.por("DimPlan", plano_id, dim_curso, pl["id"], uid, 0,
                  pl["fx"] or None, m.id_lookup("", estado), "fisica.demo",
                  inicio_curso - dt.timedelta(days=3))
            m.por("GetPatientPlan", dim, plano_id)

        # O histórico: só o que já ACONTECEU depois do deslocamento. O resto
        # vira marcação futura na agenda — é o curso seguindo.
        feitas, futuras = [], []
        for s in sorted(sessoes, key=lambda s: s[1]):
            quando = _mover(s[1], desl)
            (feitas if quando <= m.agora else futuras).append((quando, s))
        por_plano: dict = {}
        dias_feitos = sorted({q.date() for q, _ in feitas})
        primeiro_feito = feitas[0][0] if feitas else None
        for quando, s in feitas:
            plano_id = int(s[4])
            por_plano[plano_id] = por_plano.get(plano_id, 0) + 1
            fx_plano = int(s[5] or 0)
            dose_plan = (planos.get(plano_id, {}).get("dose") or (None, None))[1]
            entregue_plano = (dose_plan * por_plano[plano_id] / fx_plano
                              if dose_plan and fx_plano else None)
            maq = m.id_maquina(_maquina_da_clinica(s[2]))
            m.por("FactTreatmentHistory", dim, dim_curso, plano_id, int(s[0]),
                  quando, maq, maq, _txt(s[3]) or None, _txt(s[7]) or None,
                  fx_plano, por_plano[plano_id], entregue_plano, dose_plan, 1,
                  primeiro_feito, quando)
        # A linha-resumo do curso (fração 0), que é de onde o
        # ``tratamento_db._SQL_RESUMO`` tira o total do CURSO — as linhas de
        # sessão têm o total do PLANO, como no DW (ver o comentário de
        # "PREVISTAS continua vindo do DW" no ``tratamento_db``).
        resumo = p["resumo"].get(dim_curso)
        if resumo and feitas:
            previstas = int(resumo[1] or 0)
            ent_gravadas = int(resumo[0] or 0)
            ent = len(dias_feitos) if futuras else ent_gravadas
            dose_prev = resumo[3]
            # A dose ENTREGUE parte da gravada, proporcional às frações que
            # sobraram depois do corte em "hoje". Partir da PREVISTA errava
            # quando as duas não andam juntas: curso de 2 planos em sequência
            # (20 + 10) com o DW dizendo 20 previstas e 80 Gy saía com 80 Gy
            # entregues, e a gravação diz 40 (Ficha Virtual, 07/10/2026).
            dose_ent = (resumo[2] * ent / ent_gravadas
                        if resumo[2] and ent_gravadas else resumo[2])
            ultimo_plano = int(feitas[-1][1][4])
            maq = m.id_maquina(_maquina_da_clinica(feitas[-1][1][2]))
            m.por("FactTreatmentHistory", dim, dim_curso, ultimo_plano, 0, None,
                  maq, maq, None, None, previstas, ent, dose_ent, dose_prev, 1,
                  primeiro_feito, feitas[-1][0] + dt.timedelta(seconds=1))
        if dim_curso == ultimo:
            info["fim"] = (futuras[-1][0] if futuras else
                           feitas[-1][0] if feitas else None)
            info["maquina"] = _maquina_da_clinica(sessoes[0][2]) if sessoes else "6EX"

        # A agenda do curso: o que foi feito (Completed) e o que falta (Open).
        primeiro_dia = min([q for q, _ in feitas] + [q for q, _ in futuras],
                           default=None)
        for quando, s in feitas + futuras:
            if abs((quando.date() - m.hoje).days) > 120:
                continue
            agenda.append({
                "dim": dim, "quando": quando.replace(second=0),
                "maquina": _maquina_da_clinica(s[2]),
                "inicio": primeiro_dia is not None and quando == primeiro_dia,
                "sitio": sitio,
            })

    # Prescrições, anatomia e frequência — do que foi gravado.
    for rx in p["prescricoes"]:
        ser = int(rx[6])
        aprovada = _mover(rx[4], desl)
        m.por("DimPrescription", ser, ser, _txt(rx[0]), _txt(rx[1]),
              int(rx[3] or 0), aprovada, _txt(rx[5]) or "NA", "Approved",
              p["notas"].get(str(ser)), aprovada)
        m.por("FactPatientPrescription", ser, dim, ids_curso.get(_txt(rx[2])))
        for item in p["anatomia"].get(str(ser), []):
            m.por("DimPrescriptionAnatomy", m.novo_id("anat"), ser, item[0],
                  item[1], item[2])
        for valor in p["frequencia"].get(str(ser), []):
            m.por("DimPrescriptionProperty", ser, 7, valor)
    if not p["prescricoes"] and ultimo is not None:
        _prescricao_sintetica(m, p, ultimo, desl)

    diag = p["diagnostico"] or [cid, titulo]
    cod = m.novo_id("diag", 800)
    m.por("DimDiagnosisCode", cod, diag[0], diag[1], "NA")
    m.por("FactPatientDiagnosis", m.novo_id("fdiag"), dim, cod, "NA",
          (m.agora - dt.timedelta(days=60)))
    if p["foto"]:
        m.por("DimPatientPhoto", m.novo_id("foto"), dim, p["foto"])
    return info


def _prescricao_sintetica(m: Montador, p: dict, dim_curso: int, desl: int):
    """Prescrição tirada do plano — para quem o banco não conhecia."""
    for d in p["dose_plano"].get(dim_curso, []):
        ser = m.novo_id("rx")
        n = max((int(s[5]) for s in p["sessoes"].get(dim_curso, [])
                 if int(s[4]) == int(d[0])), default=25)
        total = float(d[3] or 0)
        m.por("DimPrescription", ser, ser, _txt(d[1]), _sitio(d[1])[0].title(),
              n, m.agora - dt.timedelta(days=20), "medico.demo", "Approved",
              None, m.agora - dt.timedelta(days=20))
        m.por("FactPatientPrescription", ser, p["dim"], dim_curso)
        for tipo, valor, un in (("DOSE PER FRACTION", f"{total / n:g}", "Gy"),
                                ("TOTAL DOSE", f"{total:g}", "Gy"),
                                ("VOLUME ID", f"PTV_{_txt(d[1])}", None)):
            m.por("DimPrescriptionAnatomy", m.novo_id("anat"), ser, tipo,
                  valor, un)
        m.por("DimPrescriptionProperty", ser, 7, "ONCE DAILY")


# ── 7. Figurantes: a agenda de um dia de clínica ────────────────────────────

# Esquemas de fracionamento dos figurantes — (frações, dose por fração em Gy).
# Pares FECHADOS, e não sorteio independente dos dois: "Pelve 120 Gy em 30
# frações" saiu na Ficha Virtual (07/10/2026) quando 4 Gy por fração caiu num
# curso de 30. Os de verdade: hipofracionado curto, mama moderada, convencional.
_ESQUEMAS = ((5, 5.0), (5, 4.0), (10, 3.0), (15, 2.67), (16, 2.66),
             (20, 2.5), (25, 2.0), (28, 1.8), (30, 2.0), (33, 1.8))


def lancar_figurantes(m: Montador, quantos: int, agenda: list,
                      ocupados: dict, medicos_das_pastas=()) -> list:
    """``quantos`` pacientes ``900NNNN`` em cursos correntes nas quatro linacs.

    Cada um tem hora FIXA na máquina (é assim que a clínica agenda), num bloco
    de 12 minutos ainda livre. Dado inteiramente fictício, com nome de
    fantasia e registro no formato de pseudônimo do projeto.

    **Médicos SEM paciente das pastas.** O figurante existe para encher a
    Agenda e não tem DICOM: na Ficha Virtual sai sem foto, sem ficha, sem
    cortes nem DVH — o que é verdade, mas misturado na lista de um médico que
    tem pacientes completos fazia a aba parecer incompleta (relato de
    07/10/2026). Com os figurantes nos outros médicos, a lista de quem tem
    paciente das pastas é toda de casos completos. Sem médico livre, cai no
    sorteio de sempre.
    """
    rng = random.Random(_semente("figurantes", quantos))
    feitos = []
    todos = _medicos_de_verdade(m.doutores)
    medicos = [d for d in todos if d not in set(medicos_das_pastas)] or todos
    for i in range(quantos):
        registro = f"900{2000 + i:04d}{rng.choice(('CEL', 'CEL', 'ANA', 'BET'))}"
        feminino = rng.random() < 0.55
        nome = (f"{rng.choice(SOBRENOMES).upper()}, "
                f"{rng.choice(PRIMEIROS_F if feminino else PRIMEIROS_M)} "
                f"{rng.choice(SOBRENOMES)}")
        maq = rng.choice(LINACS)
        abre, fecha = maq[3], maq[4]
        blocos = [dt.time(h, mm) for h in range(abre, fecha)
                  for mm in range(0, 60, MINUTOS_POR_SESSAO)]
        livres = [b for b in blocos if b not in ocupados.setdefault(maq[1], set())]
        if not livres:
            continue
        hora = rng.choice(livres)
        ocupados[maq[1]].add(hora)
        palavras, sitio, cid, titulo = rng.choice(SITIOS[:10])
        n, dose_fx = rng.choice(_ESQUEMAS)
        # Começo espalhado: uns já no fim, outros começando nos próximos dias.
        comeco = m.hoje - dt.timedelta(days=rng.randint(-10, int(n * 1.4)))
        dias = _dias_uteis(comeco, n)
        dim = m.novo_id("paciente")
        curso = m.novo_id("curso")
        plano = m.novo_id("plano")
        ser = m.novo_id("rx")
        nasc = dt.datetime(rng.randint(1938, 1996), rng.randint(1, 12),
                           rng.randint(1, 28))
        m.por("DimPatient", dim, registro, nome, nasc,
              f"(62) 9{rng.randint(8000, 9999)}-{rng.randint(1000, 9999)}",
              "NA", "NA", 0)
        m.por("FactPatient", dim,
              m.id_lookup("Feminino" if feminino else "Masculino", ""))
        payor = m.novo_id("payor", 400)
        m.por("DimPayor", payor, rng.choice(("SUS", "Ipasgo", "Unimed",
                                              "Bradesco Saúde")), "NA")
        m.por("FactPatientPayor", m.novo_id("fpayor"), dim, payor,
              str(rng.randint(10**8, 10**9)), "NA", 1)
        medico = rng.choice(medicos) if medicos else ""
        if medico:
            m.por("DimPatientDoctor", dim, m.id_doutor(medico), 1, 1)
        ativo = dias[-1] >= m.hoje
        m.por("DimCourse", curso, dim, f"C1 {dias[0]:%m-%Y}",
              m.id_lookup(rng.choice(("Curativa", "Curativa", "Paliativa")), ""),
              m.id_lookup("", "ACTIVE" if ativo else "COMPLETED"),
              dt.datetime.combine(dias[0], hora) - dt.timedelta(days=10))
        plano_nome = f"{sitio.title()}_{n}fx"
        m.por("DimPlan", plano, curso, plano_nome,
              f"1.2.826.0.1.3680043.10.543.{plano}", 0, n,
              m.id_lookup("", "Treatment Approved" if ativo else "Completed"),
              "fisica.demo", dt.datetime.combine(dias[0], hora) - dt.timedelta(days=3))
        m.por("GetPatientPlan", dim, plano)
        total = round(dose_fx * n, 2)
        aprovada = dt.datetime.combine(dias[0], dt.time(15, 0)) - dt.timedelta(days=5)
        m.por("DimPrescription", ser, ser, f"{sitio.title()} {total:g}Gy@{n}fx",
              palavras[0].title(), n, aprovada, "medico.demo", "Approved",
              None, aprovada)
        m.por("FactPatientPrescription", ser, dim, curso)
        for tipo, valor, un in (("DOSE PER FRACTION", f"{dose_fx:g}", "Gy"),
                                ("TOTAL DOSE", f"{total:g}", "Gy"),
                                ("VOLUME ID", f"PTV_{sitio.title()}", None)):
            m.por("DimPrescriptionAnatomy", m.novo_id("anat"), ser, tipo,
                  valor, un)
        m.por("DimPrescriptionProperty", ser, 7, "ONCE DAILY")
        cod = m.novo_id("diag", 800)
        m.por("DimDiagnosisCode", cod, cid, titulo, "NA")
        m.por("FactPatientDiagnosis", m.novo_id("fdiag"), dim, cod, "NA",
              aprovada - dt.timedelta(days=20))
        maq_id = m.id_maquina(maq[1])
        feitos_n = 0
        primeira = None
        for i_fx, d in enumerate(dias, 1):
            quando = dt.datetime.combine(d, hora) + dt.timedelta(
                minutes=rng.randint(-4, 6))
            agenda.append({"dim": dim, "quando": dt.datetime.combine(d, hora),
                           "maquina": maq[1], "inicio": i_fx == 1,
                           "sitio": sitio})
            if quando > m.agora:
                continue
            feitos_n += 1
            primeira = primeira or quando
            m.por("FactTreatmentHistory", dim, curso, plano, i_fx, quando,
                  maq_id, maq_id, rng.choice(("tecnico.um", "tecnico.dois",
                                              "tecnico.tres")), None,
                  n, feitos_n, dose_fx * feitos_n, total, 1, primeira, quando)
        if feitos_n:
            m.por("FactTreatmentHistory", dim, curso, plano, 0, None, maq_id,
                  maq_id, None, None, n, feitos_n, dose_fx * feitos_n, total, 1,
                  primeira, m.agora)
        feitos.append({"registro": registro, "dim": dim, "fim": dias[-1],
                       "ativo": ativo, "curso": curso})
    return feitos


# ── 8. Agenda e atividades ──────────────────────────────────────────────────

def lancar_agenda(m: Montador, agenda: list) -> None:
    ctr_por_id = {mq[1]: mq[0] for mq in MAQUINAS}
    rng = random.Random(_semente("agenda"))
    for item in agenda:
        quando = item["quando"]
        fim = quando + dt.timedelta(minutes=MINUTOS_POR_SESSAO)
        if fim <= m.agora:
            estado = "Completed" if rng.random() > 0.04 else "Pt. CompltFinish"
        elif quando <= m.agora:
            estado = "In Progress"
        else:
            estado = "Open"
        nome = f"INICIO {item['sitio']}" if item["inicio"] else item["sitio"]
        atividade = m.id_atividade(nome, nome, "Tratamento")
        m.por("DimActivityTransaction", m.novo_id("instancia", 1_000_000),
              atividade, item["dim"], ctr_por_id.get(item["maquina"], 1035),
              quando, estado, quando, 1, 0)
    # Um cancelamento por máquina hoje: o filtro de ``ESTADOS_FORA`` tem de ter
    # o que filtrar, senão a demonstração não mostra que ele existe.
    for ctr, *_ in LINACS:
        quando = dt.datetime.combine(m.hoje, dt.time(12, 0))
        m.por("DimActivityTransaction", m.novo_id("instancia", 1_000_000),
              m.id_atividade("PELVE", "PELVE", "Tratamento"), None, ctr,
              quando, "Cancelled", quando, 1, 0)
    # A parada de máquina — o nome que o ``agenda_db`` procura. O portão dela
    # (``MINUTOS_PARADA_VERIFICADO_EM``) segue fechado; a linha fica pronta para
    # o dia em que abrir.
    parada = m.id_atividade("Parada Não Programada", "Parada Não Programada",
                            "Serviço")
    for dias_atras in (2, 9):
        quando = dt.datetime.combine(m.hoje - dt.timedelta(days=dias_atras),
                                     dt.time(10, 0))
        m.por("DimActivityTransaction", m.novo_id("instancia", 1_000_000),
              parada, None, LINACS[0][0], quando, "Completed", quando, 1, 0)


def _unidade(registro: str) -> str:
    fim = registro[-3:].upper()
    return fim if fim in ("ANA", "BET", "CEL") else "CEL"


# O CÓDIGO das atividades de alta não é o nome — ver ``atividades_db.CODIGOS_ALTA``.
_CODIGO_VERIFICAR = {"ANA": "Verificar Programação ANA",
                     "BET": "Verificar Programação",
                     "CEL": "Verificar Programação UNI"}
_CODIGO_IMPRIMIR = {"ANA": "Imprimir Alta ANA", "BET": "Imprimir Alta BUE",
                    "CEL": "Imprimir Alta UNI"}


def lancar_atividades(m: Montador, infos: list, figurantes: list) -> dict:
    """Documentação (painel de pendências e gatilho) e altas (Fichinha)."""
    conta = {"documentacao": 0, "bloqueadas": 0, "altas": 0}
    doc = m.id_atividade("Documentação", "Documentação", "Planejamento")
    m.id_atividade("Review Patient Document",
                   "Revisar a documentação do paciente",
                   "Atividades especiais de revisão")

    def tarefa(atividade, dim, quando, estado, dono, derivado, pred_estado):
        # Série PRÓPRIA, e não a das marcações: o número da marcação muda todo
        # dia (a janela da agenda anda com a data), e o ``gatilho_registro``
        # guarda o estado "PRONTA" pelo número da Documentação. Na mesma série,
        # a remontagem do dia seguinte trocaria os números, e o caso já
        # preparado voltaria a aparecer como não preparado.
        inst = m.novo_id("tarefa", 5_000_000)
        m.por("DimActivityTransaction", inst, atividade, dim, dono[0], quando,
              estado, quando, 1, 0)
        m.por("GetTaskOwnerName", inst, dono[0], dono[1], dono[2], 1)
        pred = m.novo_id("pred", 2_000_000)
        m.por("GetPredeccesorAndCurrentActivityStatus", inst, derivado,
              pred_estado, pred, 1)
        return inst

    for n, info in enumerate(infos):
        dono = DONOS[n % len(DONOS)]
        unidade = _unidade(info["registro"])
        if info["cenario"] == "vai_comecar":
            # A janela do gatilho: Documentação disponível e plano aprovado.
            tarefa(doc, info["dim"], m.agora - dt.timedelta(days=1), "Open",
                   dono, "Available", "Completed")
            conta["documentacao"] += 1
        elif info["cenario"] in ("ultima", "concluido"):
            nome = f"Verificar Programação {unidade}"
            codigo = _CODIGO_VERIFICAR[unidade]
            # A alta abre no fim do curso — e nunca no futuro: uma tarefa com
            # data de depois de amanhã na lista de hoje não existe no ARIA.
            quando = min(info["fim"] or m.agora, m.agora)
            tarefa(m.id_atividade(codigo, nome, "Alta"), info["dim"],
                   quando, "Open" if n % 2 else "In Progress", dono,
                   "Available", "Completed")
            conta["altas"] += 1
            if info["cenario"] == "concluido":
                nome = f"Imprimir Alta {unidade}"
                tarefa(m.id_atividade(_CODIGO_IMPRIMIR[unidade], nome, "Alta"),
                       info["dim"], quando, "Open", dono, "Pending", "Open")
                conta["altas"] += 1
    # Documentações que ESPERAM a etapa anterior: o painel tem de mostrar que
    # não são trabalho disponível.
    for n, f in enumerate(figurantes[:3]):
        tarefa(doc, f["dim"], m.agora - dt.timedelta(days=2), "Open",
               DONOS[n % len(DONOS)], "Pending", "Open")
        conta["bloqueadas"] += 1
    # E uma já concluída, que não pode aparecer.
    if figurantes:
        tarefa(doc, figurantes[-1]["dim"], m.agora - dt.timedelta(days=5),
               "Completed", DONOS[0], "Completed", "Completed")
    return conta


# ── 9. Simulações ───────────────────────────────────────────────────────────

def gravar_simulacoes(pacientes: list, infos: list) -> int:
    """O cadastro de Simulação dos casos do GATILHO, pelo ``simulacao.cadastrar``.

    **Só dos "vai começar"**, e não de todo TC (era assim até 07/10/2026). Na
    clínica a pasta da simulação é onde a ficha é gravada na liberação; aqui a
    ficha dos pacientes em tratamento mora na pasta do TC. Com simulação para
    todos, escolher um paciente na Ficha Virtual fazia a bancada abrir a pasta
    da simulação — só fotos e nota, sem DICOM nem ficha —, a tela dizia
    "Nenhum arquivo DICOM encontrado" e a Virtual voltava para a lista. Sem a
    simulação, a procura cai na pasta da ficha (o TC), que abre. As fotos de
    posicionamento não se perdem: Capa e Virtual leem a pasta do caso quando
    não há cadastro.

    Simulação que sobrou de uma montagem anterior, de quem não é mais caso do
    gatilho, é APAGADA — a pasta é toda da demonstração.
    """
    import shutil

    from isocentro.banco import capa_dados
    from isocentro.interface import simulacao

    raiz = SAIDA / "simulacoes"
    simulacao.definir_raiz(str(raiz))
    gatilho = {i["registro"] for i in infos if i["cenario"] == "vai_comecar"}
    if raiz.is_dir():
        for pasta_pac in raiz.glob("*/*"):
            if pasta_pac.is_dir() and not any(
                    pasta_pac.name.upper().endswith(r.upper()) for r in gatilho):
                shutil.rmtree(pasta_pac, ignore_errors=True)
    feitas = 0
    for p, info in zip(pacientes, infos):
        if info["registro"] not in gatilho:
            continue
        pasta = PASTA_TCS / p["pasta"]
        if not pasta.is_dir():
            continue
        try:
            setups = capa_dados.setups_da_pasta(str(pasta))
            if not setups:
                continue
            ident = capa_dados.identidade_da_pasta(str(pasta))
            sim = simulacao.Simulacao(
                nome=ident.get("nome") or p["nome"],
                registro=ident.get("registro") or p["registro"],
                nascimento=ident.get("nascimento") or "",
                setups=setups)
            quando = (info["fim"] or dt.datetime.now()).date() - dt.timedelta(days=40)
            simulacao.cadastrar(sim, quando)
            feitas += 1
        except Exception as exc:  # noqa: BLE001 — uma pasta torta não para o resto
            print(f"  simulação de {p['pasta']} ficou de fora: {exc}")
    return feitas


# ── 10. Tudo junto ──────────────────────────────────────────────────────────

def montar(deslocar: bool = True, figurantes: int = 160,
           agora: dt.datetime | None = None, simulacoes: bool = True) -> dict:
    agora = (agora or dt.datetime.now()).replace(microsecond=0)
    m = Montador(agora)
    resp, lista = ler_gravacao(GRAVACAO)
    if not lista:
        print(f"Aviso: sem gravação em {GRAVACAO} — só DICOM e figurantes.")
    for linha in resp.get("medicos", {}).get((), []):
        if _txt(linha[0]):
            m.id_doutor(_txt(linha[0]))
    for mq in MAQUINAS:
        m.por("InSightiveResourceMachine", mq[0], mq[1], mq[2], "Active",
              "Dispositivo de radiação")
        if mq[5]:
            m.id_maquina(mq[1])

    objetos = indexar_dicom()
    planos_dicom = {}
    for o in objetos:
        if o["Modality"] == "RTPLAN" and o.get("RTPlanLabel"):
            planos_dicom[(o["PatientID"], o["RTPlanLabel"].upper())] = o["SOPInstanceUID"]

    pacientes = pacientes_gravados(resp, lista)
    conhecidos = {p["registro"] for p in pacientes} | {p["pasta"] for p in pacientes}
    pacientes += pacientes_do_dicom(objetos, conhecidos, m)
    # O plano do DICOM que não bateu por nome com nenhum plano gravado ainda
    # pode servir ao gatilho: ele vai para o curso mais novo do paciente.
    for p in pacientes:
        if not p["cursos"]:
            continue
        ultimo = int(sorted(p["cursos"], key=lambda c: c[5] or dt.datetime.min)[-1][0])
        nomes = {(_txt(s[6]).upper()) for s in p["sessoes"].get(ultimo, [])}
        for o in objetos:
            if (o["Modality"] == "RTPLAN" and o["PatientID"] == p["registro"]
                    and o.get("RTPlanLabel") and o["RTPlanLabel"].upper() not in nomes
                    and not any(o["RTPlanLabel"].upper() == _txt(s[6]).upper()
                                for ss in p["sessoes"].values() for s in ss)):
                p["dose_plano"].setdefault(ultimo, []).append(
                    [m.novo_id("plano"), o["RTPlanLabel"],
                     o.get("dose_gy") or 0, o.get("dose_gy") or 0])

    agenda: list = []
    infos = []
    for n, p in enumerate(pacientes):
        cenario = CENARIOS[n % len(CENARIOS)]
        if cenario == "vai_comecar" and p["origem"] == "dicom":
            # Plano do Monaco (pasta Elekta) não traz o médico que aprovou: o
            # caso PRONTA abria com "Plano não aprovado — sem médico" e a prévia
            # não fechava. É o app dizendo a verdade sobre esse plano, mas o
            # cenário do gatilho existe para mostrar o caminho que FUNCIONA —
            # então paciente que só existe no DICOM fica em tratamento.
            cenario = "meio"
        infos.append(lancar_paciente(m, p, cenario, deslocar, planos_dicom,
                                     agenda))
    ocupados: dict = {}
    for item in agenda:
        if item["quando"].date() == m.hoje:
            ocupados.setdefault(item["maquina"], set()).add(
                item["quando"].time().replace(
                    minute=item["quando"].minute // MINUTOS_POR_SESSAO * MINUTOS_POR_SESSAO))
    extras = lancar_figurantes(m, figurantes, agenda, ocupados,
                               {i["medico"] for i in infos if i["medico"]})
    lancar_agenda(m, agenda)
    atividades = lancar_atividades(m, infos, extras)

    sobre = {
        "tipo": servidor_local.TIPO, "versao": servidor_local.VERSAO,
        "montado_em": agora.isoformat(timespec="seconds"),
        "origem": "TCs_Teste (gravação de 24/09/2026 + DICOM + figurantes)",
        "deslocamento": ("semanas inteiras, por paciente" if deslocar else ""),
    }
    m.gravar(ARQUIVO_DW, sobre)
    # Quem está em que momento do tratamento — o ``preparar_demo.py`` lê para
    # decidir quem já tem ficha impressa (todos menos os "vai começar", que
    # são os que o gatilho prepara) e quem tem alta.
    (SAIDA / "cenarios.json").write_text(json.dumps(
        [{"registro": i["registro"], "pasta": p["pasta"],
          "cenario": i["cenario"], "medico": i["medico"]}
         for p, i in zip(pacientes, infos)], ensure_ascii=False, indent=1),
        encoding="utf-8")
    feitas = gravar_simulacoes(pacientes, infos) if simulacoes else 0
    return {"pacientes_tc": len(pacientes), "figurantes": len(extras),
            "marcacoes": len(agenda), "simulacoes": feitas,
            "objetos_dicom": len(objetos), "cenarios": [
                (i["registro"], i["cenario"], i["deslocamento"]) for i in infos],
            **atividades}


def conferir(arquivo: Path = ARQUIVO_DW) -> list:
    """Chama as funções DE VERDADE do app contra o servidor montado.

    É a prova de que "todas as telas têm dado": cada linha diz quanto voltou
    de cada consulta que uma tela faz. Zero onde não devia é defeito deste
    montador (ou do tradutor), achado aqui e não na frente de quem assiste.
    """
    import os
    os.environ["ISOCENTRO_BANCO_LOCAL"] = str(arquivo)
    os.environ["ISOCENTRO_LISTA_EXPERIMENTAL"] = "1"
    os.environ["ISOCENTRO_ATIVIDADES_EXPERIMENTAL"] = "1"
    os.environ["ISOCENTRO_GATILHO_EXPERIMENTAL"] = "1"
    os.environ.pop("ISOCENTRO_DB_SERVIDOR", None)
    from isocentro.banco import (agenda_db, atividades_db, capa_db,
                                      gatilho_db, tratamento_db)
    capa_db.esquecer()
    hoje = dt.date.today()
    linhas = []

    def medir(nome, funcao):
        try:
            r = funcao()
            n = len(r) if hasattr(r, "__len__") else (1 if r else 0)
            linhas.append((nome, n, ""))
        except Exception as exc:  # noqa: BLE001
            linhas.append((nome, -1, f"{type(exc).__name__}: {exc}"))

    pacientes = capa_db.pacientes() or []
    medir("capa: pacientes", lambda: pacientes)
    # Um paciente das PASTAS (com foto e prescrição reais), quando houver; só
    # figurante quando o servidor foi montado sem gravação nenhuma.
    alvo = next((p for p in pacientes if not p.registro.startswith("900")
                 and p.registro[-3:].isalpha()), None)
    alvo = alvo or next(iter(pacientes), None)
    reg = alvo.registro if alvo else ""
    medir(f"capa: cadastro {reg}", lambda: capa_db.cadastro_do_paciente(reg))
    medir(f"capa: prescrições {reg}", lambda: capa_db.prescricoes_do_paciente(reg))
    medir(f"capa: foto {reg}", lambda: capa_db.foto_do_paciente(reg))
    medir("virtual: em tratamento", lambda: tratamento_db.em_tratamento())
    medir("virtual: médicos", lambda: tratamento_db.medicos())
    medir(f"virtual: cursos {reg}", lambda: tratamento_db.cursos_do_paciente(reg))
    medir(f"virtual: sessões {reg}", lambda: tratamento_db.sessoes_do_paciente(reg))
    medir(f"virtual: quadro {reg}", lambda: tratamento_db.tratamento_do_paciente(reg))
    medir(f"virtual: médico {reg}", lambda: tratamento_db.medico_do_paciente(reg))
    maquinas = agenda_db.maquinas()
    medir("agenda: máquinas", lambda: maquinas)
    ctrs = [mq.ctr_resource_ser for mq in maquinas]
    medir("agenda: hoje", lambda: agenda_db.agenda_do_dia(hoje, ctrs))
    medir("agenda: semana", lambda: agenda_db.agenda_do_periodo(
        hoje - dt.timedelta(days=hoje.weekday()),
        hoje + dt.timedelta(days=6 - hoje.weekday()), ctrs[:1]))
    medir("agenda: pacientes do mês", lambda: agenda_db.pacientes_do_mes_por_maquina(
        maquinas, hoje, []))
    medir("agenda: resumo do mês (sessões)",
          lambda: tratamento_db.resumo_mensal_por_maquina(
              [mq.machine_id for mq in maquinas], hoje, []))
    medir("atividades: documentação", lambda: atividades_db.todas())
    medir("atividades: altas", lambda: atividades_db.altas())
    medir("gatilho: prontos", lambda: gatilho_db.prontos())
    return linhas


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sem-deslocar", action="store_true",
                    help="guarda as datas reais da gravação")
    ap.add_argument("--figurantes", type=int, default=160,
                    help="pacientes fictícios 900NNNN para encher a agenda")
    ap.add_argument("--sem-simulacoes", action="store_true")
    ap.add_argument("--sem-conferir", action="store_true")
    args = ap.parse_args()
    r = montar(deslocar=not args.sem_deslocar, figurantes=args.figurantes,
               simulacoes=not args.sem_simulacoes)
    print(f"Servidor local montado em {ARQUIVO_DW}")
    print(f"  pacientes das pastas: {r['pacientes_tc']}  figurantes: "
          f"{r['figurantes']}  marcações: {r['marcacoes']}  "
          f"simulações: {r['simulacoes']}  objetos DICOM: {r['objetos_dicom']}")
    print(f"  documentações: {r['documentacao']} disponíveis, "
          f"{r['bloqueadas']} esperando etapa anterior; altas: {r['altas']}")
    for registro, cenario, desl in r["cenarios"]:
        print(f"    {registro:<12} {cenario:<12} datas {desl:+d} dias")
    if args.sem_conferir:
        return 0
    print("\nConferência (as funções do app contra o servidor montado):")
    falhou = False
    for nome, n, erro in conferir():
        marca = "OK " if n > 0 else "!! "
        falhou = falhou or n <= 0
        print(f"  {marca}{nome:<42} {n if n >= 0 else 'FALHOU'} {erro}")
    return 1 if falhou else 0


if __name__ == "__main__":
    sys.exit(main())
