---
codigo: QUANTEC-MARKS-2010
titulo: "Marks LB et al. Use of normal tissue complication probability models in the clinic (QUANTEC introductory paper). Int J Radiat Oncol Biol Phys 76(3 Suppl):S10–S19"
ano: 2010
emissor: QUANTEC (AAPM/ASTRO), Red Journal suplemento
tipo: artigo (consenso de revisão; base das constraints de fracionamento convencional)
vigencia: "vigente como referência; atualizações por órgão em HyTEC (hipofracionamento) e PENTEC (pediatria)"
atividades: [I01, I02, H03, H06, C09]
refs: [CORSAIR-2022, UK-SABR-2022, GRIMM-2011, PENTEC-2023, HYTEC-LUNG, HYTEC-LIVER]
manuais: []
repos: []
isocentro: ["interface/checklist.py"]
texto: "../../texto/04 Constraints, SBRT e reirradiação/QUANTEC-MARKS-2010.md"
origem: "referencias/04 Constraints, SBRT e reirradiação/QUANTEC-MARKS-2010 - QUANTEC Use of NTCP models in the clinic (2010).pdf"
conferida: 2026-10-20
---

# QUANTEC (Marks 2010): uso de modelos de NTCP e tabela-resumo de tolerâncias

**Em uma frase.** É o artigo introdutório do QUANTEC: explica os limites de usar dados de dose-volume e modelos de NTCP na clínica e traz a **Tabela 1, o resumo de tolerâncias por órgão** que substituiu o Emami (1991) como referência de fracionamento convencional.

O PDF tem 10 páginas. Na extração, **"#" é ≤ e "$" é ≥** (conferido na imagem da página 6). A tabela vale para **1,8–2,0 Gy por fração**, salvo indicação, e **não reflete IMRT moderna** [QUANTEC-MARKS-2010 p. 9].

## Tabela 1 (resumo) [QUANTEC-MARKS-2010 p. 6–9]

| Órgão | Desfecho | Parâmetro | Taxa |
| --- | --- | --- | --- |
| Cérebro | Necrose sintomática | Dmax < 60 Gy / = 72 / = 90 | < 3% / 5% / 10% |
| Cérebro (SRS 1 fração) | Necrose | **V12 < 5–10 cm³** | < 20% |
| Tronco encefálico | Neuropatia ou necrose | Dmax < 54 (órgão todo); **D1–10 cm³ ≤ 59**; Dmax < 64 (ponto < 1 cm³) | < 5% |
| Tronco (SRS) | Idem | Dmax < 12,5 (neurinoma) | < 5% |
| Nervo óptico / quiasma | Neuropatia óptica | **Dmax < 55** / 55–60 / > 60 | < 3% / 3–7% / > 7–20% |
| Óptico (SRS) | Idem | Dmax < 12 | < 10% |
| Medula | Mielopatia | **Dmax = 50** / 60 / 69 (secção inteira) | 0,2% / 6% / 50% |
| Medula (SRS) | Idem | Dmax = 13 (1 fração); = 20 (3 frações), secção parcial | 1% |
| Cóclea | Perda auditiva | **Média ≤ 45**; SRS: prescrição ≤ 14 | < 30%; < 25% |
| Parótidas | Saliva < 25% do basal | **Média < 25** (as duas) ou **< 20** (uma); média < 39 (as duas) | < 20%; < 50% |
| Constritores da faringe | Disfagia e aspiração | Média < 50 | < 20% |
| Laringe | Disfunção vocal; aspiração; edema | Dmax < 66 (com quimio); média < 50 (com quimio); média < 44, V50 < 27% (sem quimio) | < 20%; < 30%; < 20% |
| Pulmões | Pneumonite sintomática | **V20 ≤ 30%**; média = 7 / 13 / 20 / 24 / 27 | < 20%; 5 / 10 / 20 / 30 / 40% |
| Esôfago | Esofagite aguda grau ≥ 3; ≥ 2 | Média < 34; V35 < 50%, V50 < 40%, V70 < 20% | 5–20%; < 30% |
| Coração (pericárdio) | Pericardite | Média < 26; V30 < 46% | < 15% |
| Coração (órgão) | Mortalidade cardíaca tardia | V25 < 10% | < 1% |
| Fígado − GTV | RILD clássica | **Média < 30–32**; < 42 (sem doença hepática); Child-Pugh A ou CHC: < 28; < 36 | < 5%; < 50% |
| Fígado − GTV (SBRT) | RILD | Média < 13 (3 fr) / < 18 (6 fr) em primário; < 15 (3 fr) / < 20 (6 fr) em metástase; **> 700 cm³ com < 15 Gy** (3–5 fr) | < 5% |
| Rins (ambos) | Disfunção renal | **Média < 15–18**; < 28; V12 < 55%, V20 < 32%, V23 < 30%, V28 < 20% | < 5%; < 50%; < 5% |
| Estômago | Úlcera | D100 < 45 | < 7% |
| Intestino delgado | Toxicidade aguda grau ≥ 3 (com quimio) | **V15 < 120 cm³** (alças); **V45 < 195 cm³** (cavidade peritoneal) | < 10% |
| Reto (próstata) | Toxicidade tardia grau ≥ 2 / ≥ 3 | **V50 < 50%, V60 < 35%, V65 < 25%, V70 < 20%, V75 < 15%** | < 15% / < 10% |
| Bexiga | Grau ≥ 3 tardio | Dmax < 65 (câncer de bexiga); próstata (RTOG 0415): V65 ≤ 50%, V70 ≤ 35%, V75 ≤ 25%, V80 ≤ 15% | < 6% |
| Bulbo peniano | Disfunção erétil grave | Média em 95% < 50; D90 < 50; D60–70 < 70 | < 35%; < 55% |

Notas: Vx = volume que recebe ≥ x Gy; Dx = menor dose nos x% ou x cm³ mais quentes; xerostomia grave depende também das submandibulares; no nervo óptico, os casos de neuropatia de 55–60 Gy receberam ≥ 59 Gy [QUANTEC-MARKS-2010 p. 9].

## Ressalvas do texto (p. 1–5)

- Dados extraídos da literatura têm viés: DVH de planos, não do entregue; definições de órgão variam; seguimento curto subestima efeitos tardios.
- Modelos de NTCP (Lyman-Kutcher-Burman, redução de DVH, série × paralelo) são aproximações; usar com cautela fora do intervalo de dados.
- **Hipofracionamento**, quimioterapia concomitante, fatores do hospedeiro e **crianças** alteram a tolerância; a tabela não se aplica diretamente.

## Como se aplica no CLINICA

- I01: transcrever estes limites como **objetivos clínicos padrão** de fracionamento convencional no Eclipse e no checklist do ISOCENTRO, **com o nome TG-263 da estrutura** e a fonte ao lado (ex.: `Lungs` V20Gy ≤ 30% [QUANTEC]).
- H03/H06: para frações diferentes de 1,8–2 Gy, converter por EQD2 com o α/β do órgão antes de comparar.
- I02: para SBRT, usar UK-SABR, HyTEC e Grimm, não esta tabela.
