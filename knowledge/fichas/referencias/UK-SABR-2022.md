---
codigo: UK-SABR-2022
titulo: "Diez P et al. UK 2022 consensus on normal tissue dose-volume constraints for oligometastatic, primary lung and hepatocellular carcinoma stereotactic ablative radiotherapy. Clin Oncol 34:288–300"
ano: 2022
emissor: UK SABR Consortium (Clinical Oncology)
tipo: recomendação (consenso nacional)
vigencia: vigente
atividades: [I02, C07, I06, I01]
refs: [GRIMM-2011, HYTEC-LUNG, HYTEC-LIVER, HYTEC-PANCREAS, QUANTEC-MARKS-2010, CORSAIR-2022]
manuais: []
repos: []
isocentro: ["interface/checklist.py"]
texto: "../../texto/04 Constraints, SBRT e reirradiação/UK-SABR-2022.md"
origem: "referencias/04 Constraints, SBRT e reirradiação/UK-SABR-2022 - UK consensus on normal tissue dose-volume constraints for SABR (2022).pdf"
conferida: 2026-10-20
---

# Consenso britânico 2022: constraints de OAR para SABR

**Em uma frase.** Tabela de **limites ótimo e obrigatório** por OAR para SABR em **1, 3, 5 e 8 frações** (e 2 frações para medula), com nomes de estrutura padronizados, para oligometástases, pulmão primário e hepatocarcinoma. **Todas as tabelas foram conferidas na imagem da página** (o texto extraído desalinha as colunas).

O PDF tem 13 páginas. Valores são "≤" salvo indicação [UK-SABR-2022 p. 3].

## Princípios (p. 2–4)

- Máximo próximo em **D0,1cc** para órgãos extracranianos; **D0,035cc** para medula, cauda equina, tronco, vias ópticas e cristalino.
- Órgão paralelo: limite "frio" **D≥xxcc** = dose máxima que pelo menos xx cm³ podem receber (no TPS: D(Vtotal − xx cm³)) — não confundir com Dxxcc "quente".
- **Só para SABR isolado**: com terapia sistêmica recente ou concomitante (antiangiogênico, inibidores, imunoterapia) o risco aumenta; **não vale para reirradiação**.
- Duas lesões no mesmo órgão: avaliar no **plano somado**.
- Próstata primária, rim e pâncreas primários têm protocolos próprios.

## Tórax (Tabela 2) [UK-SABR-2022 p. 4] — ótimo / obrigatório (Gy)

| Estrutura (métrica) | 1 fr | 3 fr | 5 fr | 8 fr |
| --- | --- | --- | --- | --- |
| BrachialPlex (D0,1cc) | — / 15 | — / 24 | 30,5 / 32 | 35 / 39 |
| Bronchus_Prox (D0,1cc) | — / 20,2 | — / 30 | 35 / 38 | — / 40 |
| Chestwall (D0,1cc) | 30 / — | 36,9 / — | 43 / — | — |
| Chestwall (D30cc) | — | 30 / — | — | — |
| Esophagus (D0,1cc) | — / 15,4 | — / 25,2 | — / 35 | — / 40 |
| GreatVes (D0,1cc) | — / 30 | — / 45 | — / 53 | 60 / 65 |
| Heart+A_Pulm (D0,1cc) | — / 22 | 26 / 30 | 29 / 38 | 40 / 46 (senão, prescrição para 50 Gy) |
| Lungs ou Lungs-ITV (V20Gy) | 10% / 15% | 10% / 15% | 10% / 15% | 10% / 15% |
| Lungs ou Lungs-ITV (Dmean) | 8 / — | 8 / — | 8 / — | 8 / — |
| Skin (D0,1cc) | — / 26 | 33 / — | 39,5 / — | 48 / — |
| Skin (D10cc) | — / 23 | 30 / — | 36,5 / — | 44 / — |
| Trachea (D0,1cc) | — / 20,2 | — / 30 | 35 / 38 | — / 40 |

## Abdome (Tabela 3) [UK-SABR-2022 p. 6]

| Estrutura (métrica) | 1 fr | 3 fr | 5 fr |
| --- | --- | --- | --- |
| BileDuct_Common (D0,1cc) | — / 30 | 50 / — | 50 / — |
| Bowel_Small (D0,1cc) | — / 15,4 | — / 25,2 | 30 / 35 |
| Bowel_Small (D5cc) | — / 11,9 | — / 17,7 | — |
| Bowel_Small (D10cc) | — | — | 25 / — |
| Duodenum (D0,1cc) | — / 12,4 | — / 22,2 | 33 / 35 |
| Duodenum (D10cc) | — / 9 | — / 11,4 | 25 / — |
| Kidney_Cortex (Dmean) | — | 8,5 / — | 10 / — |
| Kidney_Cortex combinado (D≥200cc) | — / 8,4 | — / 16 | — / 17,5 |
| Rim único ou Dmean excedido (V10Gy, rim contralateral) | — / 33% | — / 33% | 10% / 45% |
| Liver ou Liver-GTV (D≥700cc) | — / 9,1 | 15 / 17 | 15 / — |
| Liver-GTV (V10Gy) | — | — | 70% / — |
| Liver-GTV (Dmean) | — | 13 / 15 (no CHC, 13 é obrigatório) | 13 / 15,2 |
| Spleen (Dmean) | relatar | relatar | relatar |
| Stomach (D0,1cc) | — / 12,4 | — / 22,2 | 33 / 35 |
| Stomach (D10cc) | — / 11,2 | — / 16,5 | 25 / — |
| Stomach (D50cc) | — | — | 12 / — |

Fígado: válido até **Child-Pugh A6**; várias lesões hepáticas → 5 frações com pelo menos 40 h entre elas [UK-SABR-2022 p. 5].

## Pelve (Tabela 4) [UK-SABR-2022 p. 7]

| Estrutura (métrica) | 1 fr | 3 fr | 5 fr |
| --- | --- | --- | --- |
| Bladder (D0,1cc) | — / 18,4 | — / 28,2 | — / 38 |
| Bowel_Large (D0,1cc) | — / 18,4 | — / 28,2 | — / 38 |
| FemurHeadNeck (D10cc) | 14 / — | 21,9 / — | 30 / — |
| LumbSacPlex (D0,1cc) | 16 / — | 24 / — | 32 / — |
| LumbSacPlex (D5cc) | 14,4 / — | 22,5 / — | 30 / — |
| Rectum (D0,1cc) | — / 18,4 | — / 28,2 | — / 38 |
| Ureter (D0,1cc) | — / 35 | — / 40 | — |
| Urethra (D0,1cc) | relatar | relatar | relatar |

Plexo lombossacral é ótimo na oligometástase *de novo* e **obrigatório na oligoprogressão** [p. 7].

## Coluna (Tabela 5) [UK-SABR-2022 p. 8]

| Estrutura (métrica) | 1 fr | 2 fr | 3 fr | 5 fr | 8 fr |
| --- | --- | --- | --- | --- | --- |
| CaudaEquina / SpinalCanal abaixo da medula (D0,035cc) | — / 16 | — / 17 | — / 24 | — / 32 | — |
| Idem (D5cc) | — / 14 | — | — / 21,9 | — / 30 | — |
| **SpinalCord_PRV** (lesão vertebral) e SpinalCanal (não vertebral) (D0,035cc) | **12,4 / 14** | — / 17 | — / 20,3 | — / 25,3 | — / 32 |

Medula contornada na RM fundida, com PRV de 1–3 mm (lesão vertebral); tecal como substituto da cauda equina (sem PRV); canal ósseo para alvos não vertebrais (sem PRV) [p. 8].

## Crânio (Tabela 6) [UK-SABR-2022 p. 9]

| Estrutura (métrica) | 1 fr | 3 fr | 5 fr |
| --- | --- | --- | --- |
| Brain incluindo alvos (V12Gy) | 10–15 cm³ / — | — | — |
| Brain (D20cc) | — | 20 / — | 24 / — |
| Brainstem, exceto bulbo (D0,035cc) | 10 / 15 | 18 / 23,1 | 23 / 31 |
| Cochlea (Dmean) | 4 / — | 17,1 / — | 25 / — |
| Lens (D0,035cc) | 1,5 / — | — | — |
| OpticPathway (D0,035cc) | 8 / 10 | 15 / 20 | 22,5 / 25 |
| Orbit (D0,1cc) | 8 / — | — | — |

V12Gy de 5, 10 e > 15 cm³ ≈ risco de necrose sintomática de 10, 15 e 20% em metástase cerebral (HyTEC) [p. 9].

## Como se aplica no CLINICA

- I02: tabela pronta para os **objetivos clínicos de SBRT/SRS no TrueBeam (CEL) e no VitalBeam (DUO)**, já com nomes próximos do TG-263; montar um template de objetivos por número de frações.
- Diferenciar no checklist "ótimo" (aviso) de "obrigatório" (bloqueio), como o consenso faz.
