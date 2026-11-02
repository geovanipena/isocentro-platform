---
codigo: NCRP-151
titulo: "NCRP Report No. 151: structural shielding design and evaluation for megavoltage x- and gamma-ray radiotherapy facilities"
ano: 2005
emissor: NCRP (EUA)
tipo: recomendação
vigencia: vigente
atividades: [F13, F01, F02, A02, A12]
refs: [SRS-47, NN-6.02, NN-3.01, PQRT-BLINDAGEM]
manuais: []
repos: []
isocentro: []
texto: "../../texto/01 Regulação e radioproteção/NCRP-151.md"
origem: "referencias/01 Regulação e radioproteção/NCRP-151 - Structural shielding design for megavoltage radiotherapy facilities (2005).pdf"
conferida: 2026-10-20
---

# NCRP 151 (2005): projeto e avaliação de blindagem de salas de megavoltagem

**Em uma frase.** É a referência mais usada no mundo para **calcular e verificar a blindagem** de salas de acelerador (labirinto, porta, nêutrons, skyshine, IMRT, TBI) e para escrever o **relatório de avaliação da blindagem**. O SRS-47 da IAEA segue o mesmo método.

O PDF tem cerca de 250 páginas; texto limpo, mas **as equações não foram extraídas** (ler no PDF).

## Números de projeto

| O quê | Valor ou regra | Fonte |
| --- | --- | --- |
| Meta de projeto, área controlada | **P = 0,1 mSv/semana (5 mSv/ano)** | [NCRP-151 p. 17] |
| Meta de projeto, área livre | **P = 0,02 mSv/semana (1 mSv/ano)** | [NCRP-151 p. 17] |
| Distância ao ponto de interesse | 0,3 m além da barreira | [NCRP-151 p. 18] |
| Conservadorismos embutidos | Sem atenuação pelo paciente (≥ 30%), incidência perpendicular, fuga no máximo da IEC, ocupação alta, regra das duas fontes | [NCRP-151 p. 18–19] |
| Carga W | Dose por semana a 1 m, **incluindo CQ, calibração e física** | [NCRP-151 p. 19–20] |
| W de referência antiga | 1000 Gy/semana (≤ 10 MV) e 500 Gy/semana (> 10 MV); levantamentos medem < 350 Gy/semana a 6 MV e 400–450 Gy/semana em máquinas modernas | [NCRP-151 p. 64–65] |
| Energia alta em máquina de duas energias | 40–70% das UM | [NCRP-151 p. 65] |
| Fator de uso medido (90°) | 0°: 31,0%; 90° e 270°: 21,3% cada; 180°: 26,3% | Tab. 3.1 [NCRP-151 p. 66] |
| Fator de ocupação | Fração do tempo de **feixe ligado** em que o indivíduo mais exposto está presente; área controlada = 1 | [NCRP-151 p. 21] |
| **Fator IMRT (CI)** | UM de IMRT ÷ UM convencional (10×10, 10 cm de profundidade, SAD 100); **2 a 10 ou mais**; aumenta só a carga de **fuga** | [NCRP-151 p. 68–69] |
| CQ de IMRT | Se a verificação de IMRT for parte grande do CQ, usar também um fator CQA | [NCRP-151 p. 69] |
| Ativação (> 10 MV) | Al-28 (2,3 min), Mn-56 (2,6 h), Na-24 (15 h), Sb-122 (2,8 d); volta ao fundo em 48 h. **Física e CQ em alta energia no fim do dia** | [NCRP-151 p. 101–102] |
| Documentação permanente | Relatório de projeto com premissas; **as-built** com local e quantidade de blindagem; relatórios de levantamento; correções; reavaliações quando o uso muda | [NCRP-151 p. 29–30] |

## Levantamento e relatório (seção 6)

- Levantamento preliminar logo que o acelerador funciona; **levantamento completo após a calibração inicial** [NCRP-151 p. 110–111].
- Primeiro, a **fuga do cabeçote**; depois varrer as barreiras com GM ou cintilador (taxa máxima, maior campo); medir com câmara de ionização portátil (faixa até 50 mGy/h); **nêutrons acima de 10 MV**; instrumentos com **calibração rastreável** [NCRP-151 p. 111].
- Barreira secundária: medir **com e sem fantoma** (colimador fechado) para separar fuga e espalhamento [NCRP-151 p. 112–114].
- Relatório: equipamento e série, energias, data e executor; método e parâmetros; **W, U, T** por ponto e tipo de área; planta e cortes com os pontos; instrumentos com modelo, série, data e qualidade de calibração; dose máxima por semana, por ano e em qualquer hora; conclusão e necessidade de novo levantamento [NCRP-151 p. 112–115].

## Pontos de atenção

- As metas de projeto do NCRP (5 mSv/ano controlada, 1 mSv/ano livre) são americanas; no Brasil, os valores de projeto e as restrições vêm do PPR aprovado e da NN-3.01 (restrição do público 0,3 mSv/ano por fonte). Usar o método do NCRP com as metas brasileiras.
- Máquinas com FFF e VMAT mudam W, CI e o fator de uso: a premissa do projeto original da sala pode não valer mais.

## Como se aplica no CLINICA

- F13: cada sala precisa da pasta permanente da seção 1.13 (projeto, as-built, levantamentos, reavaliações). O TrueBeam (CEL) tem 6FFF e 10FFF e o VitalBeam (DUO) faz VMAT: reavaliar o fator CI com dados do ARIA (UM por Gy).
- Na CEL, programar medições em alta energia (6EX e TrueBeam acima de 10 MV, se usados) no fim do dia, pela ativação.
