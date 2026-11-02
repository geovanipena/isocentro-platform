---
codigo: TG-263-TEMPLATES
titulo: "Templates de estruturas do Eclipse com nomes TG-263 (University of Michigan): Abdomen, HN, Lung, LungSBRT, Pelvis"
ano: 2018
emissor: University of Michigan (C. Mayo), distribuídos com o material do TG-263
tipo: guia (arquivos de configuração do Eclipse)
vigencia: "criados em março de 2018; template de cabeça e pescoço com descrição de 2015-11-19"
atividades: [C03, I06, B06]
refs: [TG-263, TG-263-PLANILHA]
manuais: ["Eclipse 15.6 MR5 Release Note"]
repos: []
isocentro: []
texto: ""
origem: "referencias/03 Nomenclatura, prescrição e coordenadas/TG-263-TEMPLATES - Eclipse structure templates UM Abdomen HN Lung LungSBRT Pelvis.zip"
conferida: 2026-10-20
---

# Templates de estrutura do Eclipse com nomes TG-263 (Michigan)

**Em uma frase.** São **5 arquivos XML de template de estrutura do Eclipse** (formato `StructureTemplate` versão 1.1) com nomes TG-263, tipo de volume do Eclipse (Organ, PTV, CTV, GTV, Control, Avoidance, BODY), cor e **código de estrutura** (FMA ou código Varian `99VMS_STRUCTCODE`). Prontos para importar no Eclipse como ponto de partida.

Arquivo `.zip` (5 XML); **não convertido para `texto/`**; lido em 20/10/2026 (extraído no scratchpad da sessão).

## Conteúdo

| Template | Estruturas | Destaques |
| --- | --- | --- |
| UM_AAPMTG263_HN | 51 | OAR completos de cabeça e pescoço (cóclea, glândulas lacrimais, constritores, lobo temporal, nervos ópticos e PRVs), três níveis de alvo (High, Mid00, Mid01, Low) com `zOptPTV_*` e `zRingPTV_*` |
| UM_AAPMTG263_Lung | 31 | `Lungs-GTV`, `Lungs-ITV`, ITV, plexos braquiais, grandes vasos, brônquio principal, pericárdio |
| UM_AAPMTG263_LungSBRT | 37 | Até 5 alvos (`GTV01`…`GTV05`, `PTV01`…`PTV05`) com anéis `zRingPTV01`… |
| UM_AAPMTG263_Abdomen | 30 | Fígado, estômago, intestinos, cólon, rins, duodeno, bexiga, esôfago |
| UM_AAPMTG263_Pelvis | 30 | **Igual ao de abdome** (ver abaixo) |

Convenções: prefixo `z` para estruturas de otimização (`zOptPTV_High`, `zRingPTV_Low`), que é do serviço de origem; e `!` em `zOptPTV_Low!`, que segue a regra do TG-263 para **PTV segmentado** (volume de dose baixa sem a sobreposição com o de dose alta, ex. `PTV_Low!`) [TG-263 p. 26].

## Defeitos encontrados

- **O template de Pelve é cópia do de Abdome**: mesmas 30 estruturas, só muda o ID e a data. Não tem reto, próstata, vesículas seminais, cabeças de fêmur, bulbo peniano, canal anal. Não serve para pelve sem completar.
- No de cabeça e pescoço, os PRVs dos nervos ópticos estão inconsistentes: `OpticNrv_PRV_L` e `OpticNrv_PRV03_R`.
- Campos `TreatmentSite` e `Description` vazios em 4 dos 5 templates; status "Unapproved".
- O `!` é do TG-263, mas pouco usado na prática (7% dos serviços na pesquisa do TG-263U1, ver COVINGTON-2024-263U1); conferir se scripts e exportação o aceitam.

## Como se aplica no CLINICA

- C03: usar como base dos templates do Eclipse das três clínicas, **depois de corrigir** pelve e os PRVs ópticos e de decidir a convenção local para estruturas de otimização (prefixo `z`) e para PTV segmentado (`!`).
- B06/I06: o plug-in de estruturas auxiliares do ISOCENTRO deve criar nomes no mesmo padrão dos templates, para o verificador reconhecê-los.
