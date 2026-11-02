---
codigo: HARDCASTLE-2024
titulo: "Hardcastle N et al. Multi-centre evaluation of variation in cumulative dose assessment in reirradiation scenarios. Radiother Oncol 194:110184"
ano: 2024
emissor: estudo multicêntrico internacional (artigo, Radiotherapy and Oncology)
tipo: artigo
vigencia: vigente
atividades: [I03, H03, H06]
refs: [REIRR-SPC-SUPL-B, ESTRO-EANO-GBM-2025, HYTEC-HN-CAROTID, HYTEC-LUNG]
manuais: []
repos: []
isocentro: []
texto: "../../texto/04 Constraints, SBRT e reirradiação/HARDCASTLE-2024.md"
origem: "referencias/04 Constraints, SBRT e reirradiação/HARDCASTLE-2024 - Multi-centre variation in cumulative dose assessment in reirradiation (2024).pdf"
conferida: 2026-10-20
---

# Hardcastle 2024: quanto varia a dose acumulada calculada por centros diferentes na reirradiação

**Em uma frase.** Vinte e quatro centros calcularam a dose acumulada de **dois casos reais de reirradiação** (cabeça e pescoço e pulmão) com os mesmos DICOM e α/β: o **máximo próximo acumulado variou até 41,8 Gy** (cabeça e pescoço) e 33,8 Gy (pulmão) entre centros; métricas de volume em órgão grande (dose média e V20 do pulmão) variaram pouco; **mapear a dose do 1º curso na TC do 2º e somar** de forma padronizada reduziu a variação [HARDCASTLE-2024 p. 1].

PDF de 8 páginas; texto limpo; as figuras são imagem.

## Achados

| Item | Valor | Página |
| --- | --- | --- |
| Métodos usados | Registro rígido e soma 3D (15), deformável e soma 3D (5), inspeção visual de isodoses (1), **soma de métricas sem registro** (3) | [HARDCASTLE-2024 p. 1, 3] |
| Fonte da maior variação | **Fatores de recuperação tecidual** (25–50%, usados por só 3 de 14 que dizem usá-los); sem eles, máximo próximo varia até 24,1 Gy em cabeça e pescoço | [p. 3–4] |
| Conversão para EQD2 | Reduziu a faixa em cabeça e pescoço (23,4 Gy) mas aumentou no pulmão (42,9 Gy) | [p. 4] |
| Local do máximo | Até 3,7 cm (CP) e 4,5 cm (pulmão) de diferença entre centros | [p. 4] |
| Com registro único por observador | Variação caiu para máximo próximo (até 18,8 Gy em CP; 13,5 Gy no pulmão); dose média e V20 do pulmão: 0,6 Gy e 0,7% | [p. 4] |
| Fluxo nos centros | 20 de 24 sinalizam a reirradiação no R&V/prontuário eletrônico; todos importam DICOM do curso anterior quando existe | [p. 3] |

## Pontos de atenção

- O estudo mede **consistência**, não exatidão: não se sabe qual valor é o verdadeiro [p. 5].
- Registro deformável sofre com mudanças grandes de anatomia (bloco de mordida presente em uma TC e não em outra) e deve ser **verificado visualmente**; estimar a incerteza da dose acumulada sempre [p. 5].

## Como se aplica no CLINICA

- I03: padronizar o fluxo de reirradiação nas três clínicas: importar DICOM do curso anterior, **registrar e mapear a dose do 1º curso na TC atual** (registro rígido por região ou deformável, com conferência visual), somar, depois converter para EQD2 e só então aplicar desconto de recuperação, **documentando cada escolha** (ver REIRR-SPC-SUPL-B).
- H03/H06: o cálculo de EQD2 por voxel ou por métrica deve indicar o α/β e se houve desconto, para o número poder ser comparado com a literatura.
