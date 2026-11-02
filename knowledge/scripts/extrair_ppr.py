"""Extrai do JSON do PPR só os dados TÉCNICOS do serviço (sem pessoas).

Uso: python extrair_ppr.py <ppr.json> <raiz isocentro>
Saída: conhecimento/servico/ppr-tecnico.json e ppr-tecnico.md.
Ficam de fora, de propósito: responsáveis, equipes, ASOs, CPF, registros
profissionais (dados pessoais; ver _restrito/LEIA-ME.md).
"""
import json, os, sys

SECOES = [
    ("equipamentos", "Equipamentos emissores"),
    ("sistemas_planejamento", "Sistemas de planejamento"),
    ("tecnicas_tratamento", "Técnicas de tratamento"),
    ("conjunto_dosimetrico", "Conjunto dosimétrico"),
    ("fontes_referencia", "Fontes de referência (fonte-teste)"),
    ("instrumentos_medicao", "Instrumentos de grandezas de influência"),
    ("outros_detectores", "Outros detectores"),
    ("fantomas", "Fantomas"),
    ("monitores_area", "Monitores de área"),
    ("testes_diarios", "Testes diários — aceleradores"),
    ("testes_mensais", "Testes mensais — aceleradores"),
    ("testes_anuais", "Testes anuais — aceleradores"),
    ("testes_diarios_braqui", "Testes diários — braquiterapia HDR"),
    ("testes_trimestrais_braqui", "Testes trimestrais — braquiterapia HDR"),
    ("testes_mensais_orto", "Testes mensais — ortovoltagem"),
]


def main():
    src, raiz = sys.argv[1], os.path.abspath(sys.argv[2])
    with open(src, encoding="utf-8") as f:
        d = json.load(f)
    out_dir = os.path.join(raiz, "conhecimento", "servico")
    os.makedirs(out_dir, exist_ok=True)
    tec = {"fonte": os.path.basename(src), "data_ppr": f"{d['instalacao']['mes']}/{d['instalacao']['ano']}",
           "grupo": d["instalacao"]["grupo"], "subgrupo": d["instalacao"]["subgrupo"]}
    tec.update({k: d.get(k, []) for k, _ in SECOES})
    with open(os.path.join(out_dir, "ppr-tecnico.json"), "w", encoding="utf-8") as f:
        json.dump(tec, f, ensure_ascii=False, indent=2)

    md = ["---", f'fonte: "{tec["fonte"]}"', f'data_ppr: "{tec["data_ppr"]}"',
          "gerado_por: scripts/extrair_ppr.py", "---", "",
          "# Dados técnicos do serviço (PPR do CLINICA)", "",
          f"Extraído do PPR de {tec['data_ppr']} (grupo {tec['grupo']}, subgrupo {tec['subgrupo']}). "
          "Só equipamento, instrumento e programa de testes: dados de pessoas ficam de fora. "
          "Não editar à mão; corrigir no PPR e rodar o script de novo.", ""]
    for k, titulo in SECOES:
        linhas = tec[k]
        if not linhas:
            continue
        cols = [c for c in linhas[0] if any(r.get(c) for r in linhas)]
        md += [f"## {titulo}", "", "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
        md += ["| " + " | ".join(str(r.get(c, "")).replace("|", "/") for c in cols) + " |" for r in linhas]
        md.append("")
    with open(os.path.join(out_dir, "ppr-tecnico.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(md))
    print("ok", out_dir)


if __name__ == "__main__":
    main()
