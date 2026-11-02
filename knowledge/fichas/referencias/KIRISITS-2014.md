---
codigo: KIRISITS-2014
titulo: "Kirisits C et al. Review of clinical brachytherapy uncertainties: analysis guidelines of GEC-ESTRO and the AAPM. Radiother Oncol 110:199–212"
ano: 2014
emissor: GEC-ESTRO (BRAPHYQS) e AAPM
tipo: recomendação
vigencia: vigente
atividades: [E03, E07, E08, E02, E06]
refs: [HELLEBUST-2010, MPPG-HDR-A, MPPG-HDR-B, TG-138, TG-186]
manuais: []
repos: []
isocentro: []
texto: "../../texto/06 Braquiterapia/KIRISITS-2014.md"
origem: "referencias/06 Braquiterapia/KIRISITS-2014 - Review of clinical brachytherapy uncertainties GEC-ESTRO and AAPM (2014).pdf"
conferida: 2026-10-21
---

# GEC-ESTRO/AAPM (Kirisits 2014): incertezas da braquiterapia clínica

**Em uma frase.** Revisa cada componente de incerteza da braquiterapia (intensidade da fonte, planejamento, meio, entrega, posição e tempo, imagem, variações anatômicas) e dá **orçamentos de incerteza típicos** para cinco cenários, concluindo que as maiores incertezas estão no **paciente** (anatomia e aplicador entre a imagem e a entrega), não no equipamento.

O PDF tem cerca de 14 páginas; texto limpo.

## Componentes [KIRISITS-2014 p. 3–5]

| Componente | Valor típico |
| --- | --- |
| Calibração da intensidade da fonte (TG-138, k = 1) | **1,5% alta energia (Ir-192)**; 1,3% baixa energia |
| Posição da fonte no pós-carregador | Especificação ±1 mm; DP medido 1,0 mm (16 HDR) |
| Tempo de parada | Viés pode passar de 60 ms; 1ª parada diferiu 30 ms |
| Dose de trânsito | Até 0,5% da dose em HDR |
| Arredondamento do tempo ao exportar | < 1% para 5 Gy em plano otimizado |
| Fonte em aplicador curvo | Orientação não tangente ao trajeto; efeito como erro de posição |

## Orçamentos de exemplo (k = 1) [KIRISITS-2014 p. 9–11]

| Cenário | Fonte | Planejamento | Meio | Entrega/registro | Inter/intrafração | **Total** |
| --- | --- | --- | --- | --- | --- | --- |
| HDR cilindro vaginal (Tab. 1) | 2% | 3% | 1% | 5% | 5% | **8%** |
| HDR colo, HR-CTV D90 por fração (Tab. 2) | 2% | 3% | 1% | 4% | 11% (com contorno) | **12%** (< 7% em 4 frações; cerca de 5% com imagem 3D a cada fração) |
| HDR próstata guiada por US (Tab. 5) | 2% | 3% | 1% | 2% | 2% | **5%** |
| LDR I-125 próstata (Tab. 4) | 3% | 4% | 5% | — | 7% | **11%** |

## Prioridades [KIRISITS-2014 p. 10–11]

- Eliminar primeiro os **sistemáticos**: magnificação e reconstrução (1ª parada, cavidade do anel), contorno, parâmetros TG-43 diferentes do consenso, **arredondamento de tempo e offset de posição** dependente da curvatura; desprezar a blindagem do aplicador é **erro**, não incerteza.
- Depois, variações anatômicas, que crescem com o tempo entre imagem e entrega.
- Recomendação de relato: publicar o deslocamento e o **efeito na dose** (D90, D2cc) e a **incerteza total do curso** (fracionamento e nível de imagem).

## Como se aplica no CLINICA

- E03/E07 (CEL, HDR ginecológico): usar o orçamento da Tabela 2 como referência da incerteza esperada; reduzir com reconstrução correta (HELLEBUST-2010), imagem antes de cada fração e CQ de posição da fonte em 1 mm.
- E02/E06: a incerteza de calibração da fonte (cerca de 1,5–2%) justifica o critério de investigação de 3% (MPPG-HDR-A) ou 5% (SSG-46) entre medida e certificado.
