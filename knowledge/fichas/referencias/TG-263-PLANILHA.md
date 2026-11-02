---
codigo: TG-263-PLANILHA
titulo: "AAPM TG-263 nomenclature worksheet, versão 2017-08-15 (TG263 v20170815)"
ano: 2017
emissor: AAPM TG-263 (planilha oficial que acompanha o relatório)
tipo: recomendação (tabela de dados)
vigencia: "versão de 2017; o TG-263 tem atualização posterior (ver COVINGTON-2024-263U1)"
atividades: [C03, I06, I01, H05]
refs: [TG-263, TG-263-TEMPLATES, COVINGTON-2024-263U1]
manuais: []
repos: [UAB-RO/TG263-Toolkit, kildealab/TG263ComplianceTool, o3-core/TG263NameChecker, gacou54/tg263]
isocentro: []
texto: ""
origem: "referencias/03 Nomenclatura, prescrição e coordenadas/TG-263-PLANILHA - Nomenclature worksheet (2017-08-15).xls"
conferida: 2026-10-20
---

# Planilha de nomenclatura do TG-263 (2017-08-15)

**Em uma frase.** É a **lista oficial de 717 nomes de estrutura** do TG-263, um por linha, com tipo, categorias, grupo anatômico, número de caracteres, **nome primário**, **nome em ordem reversa**, descrição e o **código FMA** (Foundational Model of Anatomy). É a tabela que um verificador automático de nomes deve carregar.

Arquivo `.xls` com uma aba ("TG263 v20170815", 718 linhas × 10 colunas). **Não foi convertido para `texto/`** (o conversor só trata PDF e DOC); lido com pandas/xlrd em 20/10/2026.

## Conteúdo

| Coluna | Conteúdo |
| --- | --- |
| Target Type | Anatomic (663), PRV (19), Derived (14), Non-Anatomic (16, grafado de dois jeitos), Target (4: GTV, CTV, ITV, PTV), Surgical (1) |
| Major / Minor Category | 59 categorias maiores (Artery, Bone, Bowel, Devices, Bolus…) e 140 menores |
| Anatomic Group | Head and Neck, Thorax, Abdomen, Pelvis, Limb(s), Body |
| N Characters | **máximo 16** (nenhum nome passa disso) |
| TG263-Primary Name | Ex.: `A_Carotid_L`, `Femur_Head_L`, `SpinalCord_PRVxx`, `Bolus_xxmm`, `E-PTV_xxxx` |
| TG-263-Reverse Order Name | Ex.: `L_Carotid_A`, para telas que mostram poucos caracteres |
| Description, FMAID | Nome por extenso e código FMA (579 códigos distintos) |

Padrões com variável: `_PRVxx` (margem em mm, ex. `SpinalCord_PRV05`), `Bolus_xxmm`, `E-PTV_xxxx` (corpo menos PTV de xxxx cGy), `E-PTV_Ev05_xxxx` (corpo menos PTV expandido 5 mm).

## Defeitos da planilha (cuidado ao importar)

- **Espaço no fim** de três nomes: `Spc_Bowel `, `Strct `, `Tendon ` (o próprio TG-263 proíbe espaço).
- Tipo grafado de formas diferentes: `Anatomic` e `Anatomic `; `Non_Anatomic` e `Non-Anatomic`.
- Uma coluna sem cabeçalho com uma única nota ("FMAID for external genetalia").
- Aplicar `strip()` e normalizar o tipo antes de usar como lista de referência.

## Como se aplica no CLINICA

- C03/I06: carregar a coluna de nome primário como **lista de nomes válidos** no verificador do ISOCENTRO (com as variáveis `xx` tratadas como expressão regular) e o FMAID para gravar o código da estrutura nos templates do Eclipse.
- I01: as constraints automáticas por OAR dependem de o nome da estrutura estar nesta lista.
