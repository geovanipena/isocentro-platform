---
codigo: MPPG-8b
titulo: "AAPM Medical Physics Practice Guideline 8.b: Linear accelerator performance tests"
ano: 2023
emissor: AAPM (J. Appl. Clin. Med. Phys.)
tipo: recomendação
vigencia: vigente (substitui o MPPG 8.a)
atividades: [A07, A10, A13, A15, B02]
refs: [TG-142, TG-198, TECDOC-1151, TRS-398-R1, MPPG-5b-TPS, MPPG-IGRT-2021, MPPG-9a-SRS, TG-218, TG-100]
manuais: ["VitalBeam - Instructions for Use (v3.0, 2022-05)"]
repos: [jrkerns/pylinac, qatrackplus/qatrackplus]
isocentro: []
texto: "../../texto/05 QA de equipamentos, IGRT e dosimetria/MPPG-8b.md"
origem: "referencias/05 QA de equipamentos, IGRT e dosimetria/MPPG-8b - Linear accelerator performance tests (2023).pdf"
conferida: 2026-10-16
---

# MPPG-8b: testes de desempenho de acelerador linear

**Em uma frase.** É o **conjunto mínimo** de testes de acelerador "de uso geral" (elétrons, 3D, IMRT/VMAT), escolhido por análise de risco (FMEA) a partir do TG-142, com **limites de ação** em vez de tolerâncias. Diferente do TG-142, inclui o **MLC semanal quantitativo de 0,5 mm** e um teste holístico mensal de sliding window/VMAT.

O PDF tem 32 páginas e o texto saiu limpo (a fonte tem mapa Unicode). A página citada é a do PDF.

## Conceitos que mudam a leitura

- **Limite de ação**, e não "tolerância": "dentro de X%" significa ± X% do valor de referência. Percentual "de" um valor é mudança **relativa**: 2% de um PDD10 de 66,0% dá 64,7–67,3%, e não 64,0–68,0% [p. 12].
- **Tolerância** passa a ser a faixa normal de operação, definida pelo físico a partir do comportamento da máquina (§9) [p. 12, p. 23].
- O físico precisa considerar **todos os testes que medem o mesmo parâmetro** (diário, mensal e anual, feitos com equipamentos diferentes) antes de ajustar a máquina ou mudar uma referência [p. 12].
- Para SRS/SBRT, usar o MPPG 9 [p. 13, nota c da Tabela 5]. Para imagem e retículo digital, usar o MPPG 2 [p. 19].

## Testes (Tabelas 3 a 8) [p. 12–14; checklist na p. 29–30]

### Dosimetria (Tabela 4)

| Item | Teste | Frequência | Limite de ação |
| --- | --- | --- | --- |
| D1 | Constância do output de fótons e elétrons | Diária / Mensal / Anual | 3% da referência do dispositivo / 2% da referência do dispositivo / **1% do output nominal pelo protocolo de referência** |
| D2 | Constância do perfil de fótons e elétrons | Diária / Mensal / Anual | 2% / 2% da referência do dispositivo / 2% dos OAFs do TPS |
| D3 | Energia de elétrons | Mensal / Anual | 2 mm de mudança equivalente de R50 / 2 mm medidos |
| D4 | Energia de fótons | Mensal / Anual | 1% do PDD/TPR (mudança relativa) / 1% do PDD/TPR na profundidade de referência |
| D5 | Controle da entrega dinâmica | Mensal | 2% da dose do campo aberto |
| D6, D7 | Linearidade das UM de fótons e de elétrons | Anual | 2% do nominal |
| D8 | Output de fótons × taxa de dose | Anual | 2% |
| D9, D10 | Output e OAF × ângulo de gantry | Anual | 1% em relação a gantry 0° (IEC) |
| D11 | Fator de campo pequeno definido por mandíbula | Anual | 2% do TPS |
| D12 | Modo arco (UM e graus esperados) | Anual | 2% das UM e 2° |
| D13 | Modos especiais (TBI/TSET) | Anual | Igual ao feixe regular |

### Mecânica (Tabela 5)

| Item | Teste | Frequência | Limite de ação |
| --- | --- | --- | --- |
| M1 | Dispositivo de localização (lasers ou equivalente) | Diária / Mensal | 2 mm / 1 mm |
| M2 | Telêmetro (ODI) | Diária / Mensal | 2 mm no isocentro / 2 mm na faixa clínica |
| M3 | Indicadores de posição das mandíbulas | Diária / Mensal | 2 mm por mandíbula num campo / 2 mm na faixa clínica ou < 2% no fator de campo |
| M4 | Posição das mandíbulas × ângulo de gantry | Anual | Dentro da especificação |
| M5 | Coincidência campo luminoso × radiação | **Anual** | 2 mm por mandíbula |
| M6 | Indicadores angulares de gantry e colimador | Mensal | **0,5°** |
| M7 | Retículo físico | Mensal | 2 mm |
| M8 | Centro do retículo | Mensal | 1 mm |
| M9 | Posição absoluta da mesa | Mensal | 2 mm, 1° |
| M10 | Movimento relativo da mesa | Mensal | 1 mm em 10 cm; 0,5° em 3° |
| M11 | Isocentricidade de radiação (mandíbulas; colimador, gantry e mesa) | Anual | 2 mm de diâmetro |
| M12, M13 | Aplicadores de elétrons e travas de acessórios | Anual | Igual ao TPS / funcional |
| M14 | Mesa robótica (6 graus de liberdade) | Diária / Anual | 1 mm e 0,5° (anual sob carga) |

### Segurança (Tabela 6)

| Item | Teste | Frequência | Limite |
| --- | --- | --- | --- |
| S1, S3, S4 | Intertravamento de porta; monitores de áudio e vídeo; indicador de feixe ligado | Diária | Funcional |
| S2 | Segurança no fechamento da porta | Anual | Funcional |
| S4 | Todos os indicadores de feixe ligado | Anual | Todos funcionais |
| S5 | Anticolisão | Diária | Funcional (um sistema por dia, em rodízio) |
| S6 | Procedimentos de segurança | Definido pelo físico | Implantados |
| S7 | Procedimentos de emergência | Anual | Implantados; recursos de emergência funcionais |

### Filtros (Tabela 7) e MLC (Tabela 8)

| Item | Teste | Frequência | Limite de ação |
| --- | --- | --- | --- |
| W1 | Filtro eletrônico (EDW) | Diária / Mensal | Funcional (interno) ou 2% / 2% da referência |
| W2 | Posição do filtro físico | Mensal | 1 mm |
| W3 | Perfil do filtro eletrônico de 60°, todas as energias | Anual | 2% dos OAFs do TPS |
| W4 | Dose de filtro formado pelo colimador | Anual | 2% do TPS |
| MLC1 | Fator de campo pequeno definido por MLC (≤ 2×2 cm²) | Anual | 2% do TPS |
| **MLC2** | **Exatidão da posição das lâminas (quantitativo, várias angulações de gantry)** | **Semanal** | **0,5 mm** |
| MLC3 | Teste holístico de sliding window/VMAT | Mensal | 2% do TPS |
| MLC4 | Isocentricidade de radiação com MLC | Anual | 2 mm de diâmetro |

MLC3: para quem faz sliding window/VMAT, o teste VMAT com câmara do MPPG 5 (Tabela 8) mensal é "fortemente encorajado", com 2% de concordância [p. 22, p. 31].

## Exigências do texto que pesam na prática

- **Output diário em todos os feixes em uso clínico**, dentro de 3% da referência do dispositivo correlacionada ao output de referência. Pode ficar restrito aos feixes usados no dia, a critério do físico [p. 14].
- **Output anual** medido com protocolo de referência (TG-51 "ou protocolo comparável", portanto o **TRS-398** do serviço), em água, com equipamento calibrado em laboratório secundário **nos dois anos anteriores** [p. 15]. Isso coincide com a NN-6.10, art. 49 (calibração bienal).
- O esquema de QA deve usar **equipamentos e pessoas diferentes** em cada frequência para não propagar erro sistemático [p. 10].

## MPPG-8b × TG-142 × PPR do serviço

| Teste | PPR (TECDOC-1151) | TG-142 (IMRT) | MPPG-8b |
| --- | --- | --- | --- |
| Output diário | 3% | 3% | 3% |
| Output mensal | 2% | 2% | 2% |
| Output anual | 2% | ±1% | 1% |
| Simetria mensal | 3% | 1% (perfil) | 2% (perfil) |
| Ângulo de gantry e colimador | 1° | 1,0° | 0,5° |
| Coincidência luz × radiação | 2 mm, mensal | 2 mm ou 1%, mensal | 2 mm, **anual** |
| Isocentro de radiação | 2 mm, anual | ±2 mm, anual | 2 mm de diâmetro, anual |
| MLC posição | — | 1 mm mensal + picket fence semanal qualitativo | **0,5 mm semanal** |
| Sliding window/VMAT | — | Anual (< 0,35 cm RMS) | **Mensal 2%** |
| Anticolisão | — | Imagem: diária | Diária, em rodízio |

## Como se aplica no CLINICA

- As três clínicas fazem IMRT sliding window e VMAT (PPR), então **MLC2 semanal e MLC3 mensal se aplicam**. Hoje eles não constam do PPR (falha registrada; ver as fichas A07 e A08 e o programa de CQ proposto).
- Com o MapCHECK 2 (CEL), o MapCHECK (BET) e o DailyQA 3 (BET, DUO), o D1 e o D2 diários já são cobertos pelo DailyQA 3. Picket fence (MLC2) e VMAT (MLC3) podem usar o EPID com o `pylinac` (`PicketFence`, `DRGS`/`DRMLC`).
- O checklist das p. 29–30 (colunas "aplicável à prática?" e "rubrica do físico") é um modelo pronto para o formulário de CQ do ISOCENTRO.
