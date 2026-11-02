"""Gera o catálogo v1: extração do relatório + correções e acréscimos verificados.

Uso: python -I catalogo_v1.py <digests_dir>
"""
import csv
import sys
from collections import Counter
from pathlib import Path

d = Path(sys.argv[1])
rows = list(csv.DictReader(open(d / "catalogo-extraido.csv", encoding="utf-8"), delimiter=";"))
for r in rows:
    r["origem"] = "relatório externo"
    r["verificacao"] = ""

by_id = {r["id"]: r for r in rows}
VU = "guarda: toda a vida útil do equipamento (RDC 20/2006, 8.1(b))"


def corr(rid, note, **fields):
    r = by_id[rid]
    r.update(fields)
    r["origem"] = "relatório externo, corrigido"
    r["verificacao"] = note


for rid in ["A01", "A02", "A03", "A04", "A05", "A06", "A07", "A08", "A09", "A10", "B01", "B02"]:
    by_id[rid]["evidencia_guarda"] += f" | {VU}"
    by_id[rid]["verificacao"] = "guarda conferida em V2 (R3)"

corr("F03", "V1/N1: designação é do titular no art. 15, V; art. 16 trata da qualificação do RT",
     documento_item="NN 6.10, art. 15, V (designação pelo titular); arts. 16 e 18 (qualificação); ANSN 7.01")
corr("G01", "V2/R1: o 6.8 exige protocolos validados; procedimentos e registros estão em 6.6(c), 6.7(d) e 8.1(c)",
     documento_item="RDC 20/2006, itens 6.6(c), 6.7(d) e 8.1(c); RDC 63/2011, art. 23, XVIII")
corr("G05", "V2/R5: prazos conferidos no texto",
     gatilho_periodicidade="Mensal, pelo NSP, até o 15º dia útil do mês seguinte; óbito em até 72 h",
     documento_item="RDC 36/2013, art. 10 e parágrafo único; art. 7º, XI")
corr("G07", "V2/R4: conflito — CFM 1.821/2007, art. 7º, manda guarda permanente do prontuário eletrônico ou digitalizado",
     documento_item="Lei 13.787/2018, art. 6º (20 anos do último registro); CFM 1.821/2007, arts. 7º e 8º")
corr("F08", "V1/N7: artigos e prazos conferidos no texto",
     gatilho_periodicidade="Investigação imediata; relatório à ANSN em até 30 dias da identificação",
     documento_item="NN 6.10, art. 26, caput e parágrafo único, IV (relatório em 30 dias) e V (informar por escrito paciente e médico solicitante); ANSN 3.01, art. 98, II")
corr("D02", "V2/R2: conferido; a revisão pode ser feita por médico do serviço supervisionado pelo radioterapeuta",
     documento_item="RDC 20/2006, item 9.3, a–b; NN 6.10, art. 17, VIII")

NEW = [
    ("A13", "Teste diário do fator de calibração dos aceleradores lineares", "Diário", "NN 6.10, art. 35, II", "V1/N6"),
    ("A14", "Testes diários de segurança de todas as fontes de radiação", "Diário", "NN 6.10, art. 35, III", "V1/N6"),
    ("A15", "Determinação da dose absorvida na água em condições de referência (fontes de teleterapia)", "Mensal", "NN 6.10, art. 35, IV", "V1/N6"),
    ("A16", "Armazenar o sistema de medição de referência com temperatura e umidade controladas", "Contínuo", "NN 6.10, art. 49, parágrafo único, V", "V1/N4"),
    ("E06", "Determinar a taxa de kerma no ar antes do uso de nova fonte HDR", "A cada nova fonte", "NN 6.10, art. 35, V", "V1/N6"),
    ("F11", "Comunicar à ANSN o desligamento do RT, do SPR ou do físico médico", "Em até 30 dias", "NN 6.10, arts. 17, VII; 20, XIII; 24, V", "V1/N7"),
    ("F12", "Comunicar imediatamente à ANSN retirada de fonte, emergência, dano, perda ou roubo de fonte", "Imediato, no evento", "NN 6.10, art. 15, III–IV", "V1/N7"),
    ("G11", "Manter um radioterapeuta e um físico médico para cada 600 novos pacientes por ano", "Contínuo; conferir com a contagem anual de pacientes novos", "NN 6.10, art. 15, VI", "V1/N1"),
    ("G12", "Apurar os indicadores mínimos para a avaliação externa (tempo médio, abandono, simulação, interrupção, adesão a protocolos, desvio de dose)", "A cada ciclo de avaliação externa (item 6.9)", "RDC 20/2006, item 6.11", "V2/R3; pesquisa SGQ-RT"),
    ("G13", "Usar protocolos validados nos testes de comissionamento e de CQ (política de adoção)", "Na adoção e a cada revisão do protocolo", "RDC 20/2006, item 6.8", "V2/R1"),
]
for rid, ativ, gat, doc, ver in NEW:
    rows.append({
        "id": rid, "area": rid[0], "secao": "acréscimo verificado", "atividade": ativ,
        "gatilho_periodicidade": gat, "nivel": "OBRIGATÓRIO-BR", "documento_item": doc,
        "executa_aprova": "a definir pelo físico responsável",
        "evidencia_guarda": VU if rid[0] == "A" else "a definir",
        "colunas_originais": "", "origem": "acréscimo da verificação", "verificacao": ver,
    })

rows.sort(key=lambda r: (r["area"], r["id"]))
fields = ["id", "area", "atividade", "gatilho_periodicidade", "nivel", "documento_item",
          "executa_aprova", "evidencia_guarda", "origem", "verificacao", "secao", "colunas_originais"]
with open(d.parent / "catalogo-v1.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields, delimiter=";", extrasaction="ignore")
    w.writeheader(); w.writerows(rows)

print(len(rows), dict(Counter(r["area"] for r in rows)), dict(Counter(r["origem"] for r in rows)))
