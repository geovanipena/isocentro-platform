"""Camadas 3 e 4: matriz e índices a partir do cabeçalho YAML das fichas.

Uso: python gerar_matriz.py <raiz isocentro>
Lê:   matriz/atividades.csv, fichas/**.md (cabeçalho YAML), texto/ (códigos do acervo)
Gera: matriz/vinculos.csv          (atividade;tipo;alvo;origem)
      indices/por-atividade.md     (cada atividade: nível, ficha, fontes, código, manuais, situação)
      indices/cobertura.md         (o que falta, por área)
As fichas são a fonte de verdade; estes arquivos são regenerados, não editados à mão.
"""
import csv, glob, os, re, sys
from collections import defaultdict

import yaml

R = os.path.abspath(sys.argv[1])
K = os.path.join(R, "conhecimento")


def _valor(v):
    v = re.sub(r"\s+#\s.*$", "", v.strip())          # comentário no fim da linha
    if v.startswith("[") and v.endswith("]"):
        itens = next(csv.reader([v[1:-1]], quotechar='"', skipinitialspace=True), [])
        return [i.strip() for i in itens if i.strip()]
    return v.strip('"')


def cabecalho(caminho):
    """Cabeçalho das fichas: 'chave: valor' por linha, valor simples ou lista [a, "b, c"].
    Tolerante a ':' dentro do valor (o YAML estrito recusa); tenta o YAML só se o simples falhar."""
    t = open(caminho, encoding="utf-8").read()
    m = re.match(r"---\n(.*?)\n---\n", t, re.S)
    if not m:
        return {}
    d = {}
    for linha in m.group(1).splitlines():
        k, sep, v = linha.partition(":")
        if sep and re.fullmatch(r"[a-z_]+", k.strip()):
            d[k.strip()] = _valor(v)
    return d or (yaml.safe_load(m.group(1)) or {})


def lista(v):
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


PROGRAMA = os.path.join(R, "programa", "isocentro")


def no_isocentro(meta, atividade, campo):
    """Caminhos de `codigo_isocentro`/`testes_isocentro` que valem para a atividade.
    Relativos a programa/isocentro; em ficha agrupada, 'ID:caminho' vale só para aquele ID."""
    out = []
    for item in lista(meta.get(campo)):
        m = re.match(r"([A-I]\d\d):(.+)$", str(item))
        if not m:
            out.append(str(item))
        elif m.group(1) == atividade:
            out.append(m.group(2))
    return out


def situacao_isocentro(meta, atividade):
    """`isocentro:` da ficha para a atividade: valor único (sim, candidato, nao-se-aplica)
    ou, em ficha agrupada, lista 'ID:valor' (ex.: [H01:sim, H02:candidato])."""
    v = no_isocentro(meta, atividade, "isocentro")
    return v[0].split()[0] if v else ""


def main():
    ativ = list(csv.DictReader(open(os.path.join(K, "matriz", "atividades.csv"), encoding="utf-8"), delimiter=";"))
    ids = [a["id"] for a in ativ]
    acervo = {os.path.splitext(os.path.basename(f))[0] for f in glob.glob(os.path.join(K, "texto", "*", "*.md"))}

    vinc = []                      # (atividade, tipo, alvo, origem)
    ficha_ativ = {}                # atividade -> caminho da ficha
    meta_ativ = {}
    fontes_com_ficha = set()
    for f in sorted(glob.glob(os.path.join(K, "fichas", "**", "*.md"), recursive=True)):
        c = cabecalho(f)
        rel = os.path.relpath(f, K).replace(os.sep, "/")
        tipo = rel.split("/")[1]
        if tipo == "atividades":
            for i in lista(c.get("id")):
                ficha_ativ[i] = rel
                meta_ativ[i] = c
                for r in lista(c.get("refs")):
                    vinc.append((i, "referencia", str(r), rel))
                for m in lista(c.get("manuais")):
                    vinc.append((i, "manual", str(m), rel))
                for p in lista(c.get("repos")):
                    vinc.append((i, "codigo", str(p), rel))
                for p in lista(c.get("pops")):
                    vinc.append((i, "pop", str(p), rel))
        else:
            if tipo == "referencias":
                fontes_com_ficha.add(str(c.get("codigo")))
            alvo = str(c.get("codigo") or c.get("repo") or c.get("manual") or os.path.basename(f))
            for i in lista(c.get("atividades")):
                vinc.append((str(i), {"referencias": "referencia", "manuais": "manual", "codigo": "codigo"}[tipo], alvo, rel))

    os.makedirs(os.path.join(K, "indices"), exist_ok=True)
    vinc = sorted(set(vinc))
    with open(os.path.join(K, "matriz", "vinculos.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["atividade", "tipo", "alvo", "origem"])
        w.writerows(vinc)

    por = defaultdict(lambda: defaultdict(set))
    for a, t, alvo, _ in vinc:
        por[a][t].add(alvo)

    # índice por atividade
    out = ["# Índice por atividade", "",
           "Gerado por `scripts/gerar_matriz.py` a partir das fichas. Não editar à mão.", ""]
    area_atual = None
    for a in ativ:
        if a["area"] != area_atual:
            area_atual = a["area"]
            out += [f"## {a['id'][0]}. {area_atual}", ""]
        i = a["id"]
        f = ficha_ativ.get(i)
        link = f"[{i}](../{f})" if f else f"{i} (sem ficha)"
        refs = ", ".join(sorted(por[i]["referencia"])) or "—"
        cod = ", ".join(sorted(por[i]["codigo"])) or "—"
        man = len(por[i]["manual"])
        m = meta_ativ.get(i, {})
        out += [f"- **{link}**: {a['atividade']} — *{a['nivel']}*",
                f"  - Fontes: {refs}",
                f"  - Código: {cod}; manuais: {man}; ISOCENTRO: {situacao_isocentro(m, i) or '—'}; lacuna no PPR: {m.get('lacuna_ppr', '—')}"]
        cod_iso, tes_iso = no_isocentro(m, i, "codigo_isocentro"), no_isocentro(m, i, "testes_isocentro")
        if cod_iso or tes_iso:
            out.append(f"  - No ISOCENTRO: {', '.join(f'`{c}`' for c in cod_iso) or '—'}; "
                       f"testes: {', '.join(f'`{t}`' for t in tes_iso) or '—'}")
    open(os.path.join(K, "indices", "por-atividade.md"), "w", encoding="utf-8", newline="\n").write("\n".join(out) + "\n")

    # cobertura
    citadas = {alvo for a, t, alvo, _ in vinc if t in ("referencia", "pop")}
    fora_acervo = sorted(c for c in citadas if c not in acervo and not c.startswith("Eclipse-"))
    sem_ficha_fonte = sorted(acervo - fontes_com_ficha - {"_relatorio"})
    nunca_citadas = sorted(acervo - citadas)
    out = ["# Cobertura da base", "", "Gerado por `scripts/gerar_matriz.py`. O que falta, por área.", "",
           "## Por área", "", "| Área | Atividades | Com ficha | Sem ficha | Sem fonte vinculada | Candidatas a item do ISOCENTRO |",
           "| --- | --- | --- | --- | --- | --- |"]
    areas = defaultdict(list)
    for a in ativ:
        areas[a["id"][0] + ". " + a["area"]].append(a["id"])
    for nome, lst in areas.items():
        com = [i for i in lst if i in ficha_ativ]
        sem_fonte = [i for i in lst if not por[i]["referencia"]]
        cand = [i for i in lst if situacao_isocentro(meta_ativ.get(i, {}), i) in ("candidato", "sim")]
        out.append(f"| {nome} | {len(lst)} | {len(com)} | {', '.join(i for i in lst if i not in ficha_ativ) or '—'} | "
                   f"{', '.join(sem_fonte) or '—'} | {len(cand)} |")
    out += ["", f"## Fontes do acervo sem ficha própria ({len(sem_ficha_fonte)} de {len(acervo)})", "",
            "Já convertidas em `texto/`, ainda sem ficha de fonte (o valor delas é citado direto nas fichas de atividade, com página).", "",
            ", ".join(sem_ficha_fonte), "",
            f"## Fontes do acervo nunca vinculadas a uma atividade ({len(nunca_citadas)})", "",
            ", ".join(nunca_citadas) or "—", "",
            f"## Fontes citadas que não estão no acervo ({len(fora_acervo)})", "",
            ", ".join(fora_acervo) or "—", ""]

    # elo ficha -> código -> teste (P5): só o mapeamento, o código do programa não muda
    sim = [i for i in ids if situacao_isocentro(meta_ativ.get(i, {}), i) == "sim"]
    com_cod = [i for i in sim if no_isocentro(meta_ativ[i], i, "codigo_isocentro")]
    sem_teste = [i for i in com_cod if not no_isocentro(meta_ativ[i], i, "testes_isocentro")]
    sumidos = sorted({f"{i}: {c}" for i in sim for campo in ("codigo_isocentro", "testes_isocentro")
                      for c in no_isocentro(meta_ativ[i], i, campo)
                      if not os.path.exists(os.path.join(PROGRAMA, c))})
    out += [f"## Elo ficha → código → teste no ISOCENTRO ({len(com_cod)} de {len(sim)} atividades 'sim')", "",
            "Campos `codigo_isocentro` e `testes_isocentro` do cabeçalho da ficha, relativos a `programa/isocentro`.", "",
            f"- 'sim' sem código registrado: {', '.join(i for i in sim if i not in com_cod) or '—'}",
            f"- Com código e sem teste: {', '.join(sem_teste) or '—'}",
            f"- Caminho que não existe mais no programa: {'; '.join(sumidos) or '—'}", ""]
    for s in sumidos:
        print("aviso: caminho do ISOCENTRO não existe:", s)
    open(os.path.join(K, "indices", "cobertura.md"), "w", encoding="utf-8", newline="\n").write("\n".join(out))
    print(f"{len(vinc)} vínculos; {len(ficha_ativ)} atividades com ficha de {len(ids)}; "
          f"{len(fontes_com_ficha)} fichas de fonte; acervo {len(acervo)}")


if __name__ == "__main__":
    main()
