---
codigo: TRS-483-RESUMO
titulo: "Palmans H et al. Dosimetry of small static fields used in external photon beam radiotherapy: Summary of TRS-483, the IAEA–AAPM international Code of Practice for reference and relative dose determination. Med Phys 45(11):e1123–e1145"
ano: 2018
emissor: IAEA–AAPM (resumo publicado do código de prática)
tipo: recomendação (código de prática internacional, versão resumida)
vigencia: "vigente; o TRS-483 completo não está no acervo (pendência de aquisição)"
atividades: [A02, A17, A03, B01, C07]
refs: [TG-155, TRS-398-R1, TG-51-ADD-2014, TG-106]
manuais: []
repos: []
isocentro: []
texto: "../../texto/05 QA de equipamentos, IGRT e dosimetria/TRS-483-RESUMO.md"
origem: "referencias/05 QA de equipamentos, IGRT e dosimetria/TRS-483-RESUMO - Palmans resumo do TRS-483 dosimetria de campos pequenos (2018).pdf"
conferida: 2026-10-20
---

# Resumo do TRS-483 (IAEA–AAPM): dosimetria de campos pequenos estáticos

**Em uma frase.** Resume o código de prática **TRS-483**: quando um campo é "pequeno", como fazer a **dosimetria de referência em campo de referência específico da máquina (msr)** quando o 10×10 não é possível (CyberKnife, TomoTherapy, Gamma Knife) e como medir **fatores de saída de campo** com **fatores de correção** k(Qclin, Qmsr) por detector.

O PDF tem cerca de 23 páginas; texto limpo, mas **as equações não foram extraídas** e alguns símbolos saíram como "�". As tabelas de fatores de correção por detector estão no TRS-483 completo (a lista de aquisição pede o documento integral).

## Conceitos [TRS-483-RESUMO p. 3–5, 14–15]

| Conceito | Definição |
| --- | --- |
| Campo pequeno | Basta uma condição: (a) perda de **equilíbrio lateral de partículas carregadas** no eixo; (b) **oclusão parcial da fonte** (foco ≤ 5 mm nos aceleradores modernos); (c) **detector do tamanho do campo** |
| r_LCPE | Raio mínimo para equilíbrio lateral, função da qualidade do feixe; o semi-campo deve ser ≥ r_LCPE + metade da dimensão do detector |
| Tamanho de campo | Pela **FWHM** medida na profundidade; quadrado equivalente = √(A·B) (válido para 0,7 < A/B < 1,4) ou de área igual ao círculo |
| Fator de saída de campo | Razão de leituras × k(Qclin, Qmsr) do detector |
| Campo intermediário | Câmara até um campo intermediário sem condição de campo pequeno, detector de campo pequeno só abaixo dele (*daisy chain*), minimizando a dependência energética do diodo |

## Requisitos do detector para campos pequenos (Tabela III) [TRS-483-RESUMO p. 16]

Estabilidade < 0,1%; linearidade de dose < 0,1% em 0,01–10 Gy; linearidade de taxa < 0,1% em 0,1–0,4 Gy/s; dose por pulso 0,2–2,0 mGy estável < 0,1%; **média volumétrica ≤ 5%**; orientação < 0,5% até 60°; fundo ≥ 3 ordens abaixo do sinal; influências ambientais < 0,3%. **Radiografar o detector** antes do uso para achar o volume sensível.

Adequados: câmara líquida, diodos de silício, diamante, cintiladores orgânicos, filme radiocrômico, TLD, alanina, OSL — desde que cumpram a tabela e haja fator de correção.

## Como se aplica no CLINICA

- A17/B01: medir FWHM de cada campo pequeno usado no TrueBeam (CEL) e no VitalBeam (DUO) e aplicar o k(Qclin, Qmsr) do detector usado (Razor na DUO; a CEL não tem câmara ≤ 0,03 cm³, ver pendências) — com o TRS-483 completo para os valores.
- A03: campos 10×10 são possíveis em todas as máquinas do CLINICA; a dosimetria de referência continua pelo TRS-398 (o formalismo msr não é necessário).
