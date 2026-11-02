"""Espinha da correlação: catálogo v1 (74 obrigações) + itens de PRÁTICA.

Uso: python estender_catalogo.py <raiz isocentro>
Saída: conhecimento/matriz/atividades.csv (id;area;atividade;gatilho;nivel;base;origem).
Os IDs do v1 não mudam; os acréscimos têm nivel=PRÁTICA e origem=extensão-2026-10-16,
para não misturar o que é fiscalizado com o que é boa prática.
"""
import csv, os, sys

R = os.path.abspath(sys.argv[1])
V1 = os.path.join(R, "programa", "isocentro", "docs", "planejamento", "sistema-global",
                  "research-catalogo-atividades-fisico-medico-radiot-2026-10-13", "catalogo-v1.csv")
OUT = os.path.join(R, "conhecimento", "matriz", "atividades.csv")

AREAS = {
    "A": "Equipamentos e dosimetria",
    "B": "TPS, sistemas e software",
    "C": "Paciente: simulação, planejamento e QA",
    "D": "Paciente: tratamento e acompanhamento",
    "E": "Braquiterapia HDR",
    "F": "Proteção radiológica e licenciamento",
    "G": "Gestão da qualidade, segurança do paciente e documentação",
    "H": "Ferramentas de rotina",
    "I": "Avaliação clínica do plano",
}

# id, atividade, gatilho, base (referências do acervo que sustentam o item)
EXTENSAO = [
    ("A17", "CQ de técnicas estereotáxicas: Winston-Lutz, coincidência de isocentros, campos pequenos",
     "Conforme programa de SRS/SBRT e antes de cada tratamento estereotáxico quando previsto",
     "MPPG-9a-SRS; TG-142; TG-101; ABFM-SRS"),
    ("A18", "Dosimetria portal e verificação in vivo",
     "Conforme protocolo do serviço", "TG-218; Portal Dosimetry 15.5 RG"),
    ("A19", "Aceitação e comissionamento do sistema de imagem e do movimento de mesa (IGRT)",
     "Na aceitação e após mudança relevante", "MPPG-IGRT-2021; TG-179; TG-142"),
    ("A20", "CQ e dosimetria de ortovoltagem (raios X de baixa energia, Dermopan 50 kV na CEL)",
     "Conforme programa escrito; mensal no PPR da CEL", "TRS-398-R1; TECDOC-1151; NN-6.10"),
    ("B08", "Ciclo de vida de software próprio: requisitos, risco, verificação, liberação e manutenção",
     "A cada versão de software clínico próprio", "IEC-62304; ISO-14971; FDA-GPSV-2002; FDA-CSA-2026; IMDRF-N12-2014"),
    ("B09", "Usabilidade e fatores humanos de software clínico",
     "No projeto e a cada mudança de interface", "FDA-HF-2016; FDA-HF-CONTENT-2026; SUBST-PAGAS"),
    ("B10", "Validação de software de terceiros e de código aberto (OTS/SOUP)",
     "Na adoção e a cada atualização", "FDA-OTS-2023; IEC-62304"),
    ("C10", "Coordenadas, orientação e escalas do equipamento (IEC 61217) na transferência do plano",
     "No comissionamento de interfaces e em cada plano", "IEC-61217; DICOM-RT"),
    ("C11", "Integridade dos objetos DICOM-RT exportados e importados",
     "Em cada transferência entre sistemas", "DICOM-RT; YANG-MOORE-2012; Conformance Statements Varian"),
    ("E07", "Planejamento e verificação do plano HDR do paciente (TG-43, pontos, DVH, tempos)",
     "Em cada plano de braquiterapia", "TG-43U1; TG-59; TG-186; ICRU-89; MPPG-HDR-A; MPPG-11a"),
    ("E08", "Comissionamento de aplicadores HDR (anel e tandem, offsets, reconstrução)",
     "Na entrada de aplicador novo e periodicamente", "TG-56; MPPG-HDR-A; manuais GammaMed"),
    ("E09", "Dosimetria de pele e de órgãos em braquiterapia",
     "Quando o caso clínico indicar", "ACROP-SKIN-BRACHY; ICRU-89"),
    ("F13", "Cálculo de blindagem e levantamento radiométrico das salas",
     "No projeto, em mudança de uso ou carga e na comprovação para licenciamento",
     "PQRT-BLINDAGEM; GUIA-CNEN-RT; NN-6.10"),
    ("G14", "Análise prospectiva de risco do processo (FMEA, árvore de falhas)",
     "Na implantação de técnica nova e periodicamente", "TG-100; WHO-RISK; SAFER-RT-2008"),
    ("G15", "Sistema de aprendizado com incidentes: notificação, taxonomia, análise e retorno",
     "Contínuo", "FORD-2012-ILS; WHO-ICPS-2009; UK-RT-TAXONOMIA; SNA-2019; casos da pasta 11"),
    ("G16", "Revisão por pares em física médica",
     "Conforme programa do serviço", "MPPG-PEER"),
    ("G17", "Checklists de segurança nas etapas críticas",
     "Em cada etapa definida no fluxo", "MPPG-CHECKLIST; TG-275"),
    ("G18", "Pseudonimização e uso secundário de dados clínicos (pesquisa, teste, validação)",
     "A cada extração de dados para fora do prontuário", "LGPD; RDC-657"),
    ("G19", "Indicadores de qualidade e mineração de dados do serviço",
     "Periódico", "YOO-2025-ISQM; G12"),
    ("H06", "Conversão de dose entre fracionamentos para decisão rápida (EQD2/BED por OAR)",
     "Quando necessário", "QUANTEC; HYTEC-2021"),
    ("I01", "Avaliação de constraints de OAR em fracionamento convencional",
     "Em cada plano", "QUANTEC; RECOG-CONSTR; ASTRO-CONSTR-2025"),
    ("I02", "Avaliação de constraints em SBRT/SRS e hipofracionamento",
     "Em cada plano estereotáxico", "TG-101; TIMMERMAN-2021; HYTEC-2021; HYTEC-BRAIN; ICRU-91"),
    ("I03", "Reirradiação: dose acumulada, recuperação de tecido e limites",
     "Em cada caso de reirradiação", "ESTRO-REIRR-2022; REIRR-SPC; REIRR-SPC-IMPL"),
    ("I04", "Prescrição, registro e relato conforme ICRU (D98, D2, D50, índices de conformidade)",
     "Em cada plano", "ICRU-83; ICRU-91; ICRU-89"),
    ("I05", "Qualidade e complexidade do plano (scorecard, modulação, robustez)",
     "Em cada plano modulado", "COVINGTON-2016; WAHLSTEDT-2021; TG-218"),
    ("I06", "Nomenclatura TG-263 aplicada à avaliação automatizada de objetivos clínicos",
     "Em cada plano", "TG-263; TG-263-TEMPLATES"),
]

# Correções de nível ao catálogo v1, com a fonte que as justifica. O v1 não é alterado;
# a correção aparece em matriz/atividades.csv com origem "v1 corrigido".
AJUSTES = {
    "C05": ("OBRIGATÓRIO-BR + RECOMENDAÇÃO",
            "NN-6.10 art. 15, XI, e (segundo sistema de cálculo); RDC 20/2006, item 9.7 (c) (verificação até a 3ª aplicação ou 10% da dose); TG-114; TG-219"),
}


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    linhas = []
    with open(V1, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f, delimiter=";"):
            linhas.append([r["id"], AREAS[r["area"]], r["atividade"], r["gatilho_periodicidade"],
                           r["nivel"], r["documento_item"], "catalogo-v1"])
    for l in linhas:
        if l[0] in AJUSTES:
            l[4], l[5] = AJUSTES[l[0]]
            l[6] = "v1 corrigido 2026-10-16"
    ids = {l[0] for l in linhas}
    for i, ativ, gat, base in EXTENSAO:
        assert i not in ids, i
        linhas.append([i, AREAS[i[0]], ativ, gat, "PRÁTICA", base, "extensão-2026-10-16"])
    linhas.sort(key=lambda l: (l[0][0], int(l[0][1:])))
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["id", "area", "atividade", "gatilho", "nivel", "base", "origem"])
        w.writerows(linhas)
    print(f"{len(linhas)} atividades ({len(EXTENSAO)} de prática) -> {OUT}")


if __name__ == "__main__":
    main()
