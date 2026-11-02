---
codigo: HELLEBUST-2010
titulo: "Hellebust TP et al. Recommendations from Gynaecological (GYN) GEC-ESTRO Working Group: considerations and pitfalls in commissioning and applicator reconstruction in 3D image-based treatment planning of cervix cancer brachytherapy. Radiother Oncol 96:153–160"
ano: 2010
emissor: GEC-ESTRO (grupo ginecológico)
tipo: recomendação
vigencia: vigente
atividades: [E08, E07, E01]
refs: [MPPG-HDR-A, MPPG-HDR-B, KIRISITS-2014]
manuais: ["GammaMed - IFU Guidelines for Commissioning Ring and Tandem Applicators (2021-09)"]
repos: []
isocentro: []
texto: "../../texto/06 Braquiterapia/HELLEBUST-2010.md"
origem: "referencias/06 Braquiterapia/HELLEBUST-2010 - GYN GEC-ESTRO commissioning and applicator reconstruction (2010).pdf"
conferida: 2026-10-21
---

# GEC-ESTRO (Hellebust 2010): comissionamento e reconstrução de aplicadores em braquiterapia de colo guiada por imagem

**Em uma frase.** Mostra como **comissionar aplicadores** (posição real das paradas da fonte em relação ao aplicador, com autorradiografia e TC) e como **reconstruí-los** em TC ou RM (biblioteca × reconstrução direta), com as armadilhas que geram **erro sistemático em todos os pacientes**.

O PDF tem 8 páginas; texto limpo ("≤" saiu como "6"/"�").

## Pontos-chave

| Tema | Recomendação | Página |
| --- | --- | --- |
| Comissionamento | Medir distância da ponta do tandem/agulha à 1ª parada, da superfície do anel ao canal da fonte; **autorradiografia + TC**; o resultado vira **biblioteca** do TPS | [HELLEBUST-2010 p. 2–3] |
| Aplicador curvo (anel, ovoides) | A fonte corre **encostada na parede externa**: trajeto não circular e diferença entre marcador e posição real; corrigir no comissionamento | [p. 2] |
| Titânio na RM | Artefato de suscetibilidade depende da sequência: comissionar com as **mesmas sequências clínicas**, fundindo RM e TC do fantoma | [p. 2] |
| Biblioteca (LIB) | Só para aplicador rígido; ≥ 3 pontos para casar coordenadas; erro na biblioteca = **erro sistemático** | [p. 2–3] |
| Reconstrução direta (DR) | Identificar bem a **1ª parada**; usar reconstrução multiplanar; aplicador reto com só 2 pontos; conferir com carga padrão e **tempos e dose no ponto A tabelados** | [p. 3–4] |
| TC | Sem inclinação do gantry; **corte ≤ 3 mm** | [p. 4] |
| RM | T2 para contorno e reconstrução na mesma série; para-transversal; marcadores de líquido (CuSO₄, água, glicerina) ou ajuste do contorno do aplicador; distorção central < 2 mm | [p. 4–5] |
| Fusão | Registrar **pelo aplicador**, não pelo osso | [p. 5] |

## Magnitude dos erros [HELLEBUST-2010 p. 6–7]

- Gradiente de dose **5–12% por mm** a 1–3 cm do canal.
- D2cc de bexiga e reto muda **5–6% por mm** de erro anteroposterior (até 7%).
- Erro sistemático de 2 mm caudal (espessura do anel errada) → **até 10%** nos parâmetros de DVH; folga de 4 mm do cabo no anel → 2 ± 6%; fontes vaginais 3 mm fora → +20% em bexiga/reto.
- Variação entre observadores na reconstrução < 0,5–1 mm (1 DP), menor que a de contorno (cerca de 2 mm).

## Como se aplica no CLINICA

- E08 (CEL, GammaMed IX com anel e tandem): base do comissionamento dos aplicadores junto com o IFU da Varian; registrar offsets do anel e da ponta do tandem, autorradiografia e a biblioteca validada; refazer ao trocar lote ou modelo de aplicador.
- E07: checar em cada plano a carga padrão × tempos e dose no ponto A tabelados, como teste rápido de reconstrução.
