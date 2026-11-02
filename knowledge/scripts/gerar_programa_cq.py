"""Programa de CQ proposto por clínica, no formato que o ppr-streamlit importa.

Uso: python gerar_programa_cq.py <raiz isocentro>
Lê:  conhecimento/matriz/programa-cq.csv (separador |; fonte única dos testes, com referência)
Gera: conhecimento/servico/<CLINICA>/qualidade.json — importar no app pelo upload de JSON
      (o nome "qualidade.json" faz o app substituir só as listas de testes; braquiterapia,
      sistemas e técnicas ficam como estão no PPR).

A coluna "aplica" do CSV tem uma ou mais etiquetas separadas por vírgula (todas, eletrons,
kv, epid, fff, edw, srs, orto); a linha vale para a máquina que tiver qualquer uma delas.
"?" no fim da etiqueta da máquina = não confirmado (sai "(confirmar)" no PDF).
"""
import csv, json, os, sys

# Confirmado pelo usuário em 16/10/2026: 6EX tem EPID; 600CD não tem (usa CR);
# nenhuma clínica usa filtro dinâmico; SRS/SBRT só no TrueBeam e no VitalBeam.
MAQUINAS = {
    "CEL": {"TrueBeam": {"todas", "eletrons", "kv", "epid", "srs"},
            "6EX": {"todas", "epid"},
            "Dermopan": {"orto"}},
    "BET": {"600CD": {"todas"}},
    "DUO": {"VitalBeam": {"todas", "eletrons", "kv", "epid", "fff", "srs"}},
}
ACELERADORES = {"TrueBeam", "6EX", "600CD", "VitalBeam"}


def aplica_a(maquinas, aplica):
    etiquetas = {e.strip() for e in aplica.split(",")}
    nomes = []
    for nome, tags in maquinas.items():
        if etiquetas & tags:
            nomes.append(nome)
        elif etiquetas & {t.rstrip("?") for t in tags if t.endswith("?")}:
            nomes.append(f"{nome} (confirmar)")
    return nomes


def main():
    raiz = os.path.abspath(sys.argv[1])
    with open(os.path.join(raiz, "conhecimento", "matriz", "programa-cq.csv"), encoding="utf-8") as f:
        linhas = list(csv.DictReader(f, delimiter="|"))
    for clinica, maquinas in MAQUINAS.items():
        acel = sorted(n for n in maquinas if n in ACELERADORES)
        prog = {}
        for r in linhas:
            nomes = aplica_a(maquinas, r["aplica"])
            if not nomes:
                continue
            todas = sorted(nomes) == acel and len(acel) > 1
            item = {"tipo": r["tipo"], "teste": r["teste"], "tolerancia": r["tolerancia"],
                    "referencia": r["referencia"],
                    "equipamento": "Todos os aceleradores" if todas else ", ".join(nomes)}
            if r["chave"].endswith("_orto"):
                item.pop("tipo")
                item.pop("equipamento")
            prog.setdefault(r["chave"], []).append(item)
        out = os.path.join(raiz, "conhecimento", "servico", clinica, "qualidade.json")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(prog, f, ensure_ascii=False, indent=2)
        print(clinica, {k: len(v) for k, v in prog.items()})


if __name__ == "__main__":
    main()
