---
codigo: SRS-47
titulo: "IAEA Safety Reports Series 47: radiation protection in the design of radiotherapy facilities"
ano: 2006
emissor: IAEA
tipo: recomendação
vigencia: "vigente (método semelhante ao NCRP 151; cita o BSS antigo)"
atividades: [F13, F01, F02, E04, A12]
refs: [NCRP-151, NN-6.02, NN-3.01, NN-2.06, GSR-PART3, SSG-46, PQRT-BLINDAGEM]
manuais: []
repos: []
isocentro: []
texto: "../../texto/01 Regulação e radioproteção/SRS-47.md"
origem: "referencias/01 Regulação e radioproteção/SRS-47 - IAEA Radiation protection in the design of radiotherapy facilities (2006).pdf"
conferida: 2026-10-20
---

# SRS-47 (IAEA, 2006): proteção radiológica no projeto de instalações de radioterapia

**Em uma frase.** É o manual da IAEA para **projetar e verificar a blindagem** de salas de cobalto, acelerador (6 e 18 MV), simulador, ortovoltagem e braquiterapia HDR, com exemplos resolvidos, tabelas de TVL e o roteiro do **levantamento radiométrico** e do seu relatório.

O PDF tem cerca de 145 páginas; texto limpo, mas **as equações não foram extraídas** (ler no PDF). A Tabela 4 (TVL) foi conferida na imagem da página.

## Conceitos e números de projeto

| O quê | Valor ou regra | Fonte |
| --- | --- | --- |
| Carga de trabalho típica (acelerador) | 50 pacientes em 8 h; **W = 1000 Gy/semana** a 1 m (4 Gy por paciente, 5 dias); dupla energia: 500 Gy/semana na energia mais alta | [SRS-47 p. 19] |
| Fator de uso | Piso 1; cada parede e teto 0,25 (técnica convencional) | [SRS-47 p. 20] |
| Fator de ocupação | Fração do tempo da pessoa que fica mais tempo no local (dia de 8 h, ano de 2000 h) | [SRS-47 p. 20] |
| Limite semanal de projeto | 1/50 do limite anual | [SRS-47 p. 20] |
| IDR | Leitura do monitor em dose por hora, média de 1 min, a 0,3 m além da barreira | [SRS-47 p. 20–21] |
| TADR | IDR × tempo de feixe ligado ÷ tempo considerado (R8 em 8 h; Rw por semana; Rh em qualquer hora) | [SRS-47 p. 21–23] |
| Área sem supervisão (guia do Reino Unido) | IDR < 7,5 mSv/h **e** TADR < 0,5 mSv/h, ou TADR2000 < 0,15 mSv/h | [SRS-47 p. 21] |
| Limite "em qualquer hora" (EUA, NRC) | 0,02 mSv em qualquer hora em área livre | [SRS-47 p. 22] |
| **Fator IMRT (CI)** | UM do IMRT ÷ UM convencional para a mesma dose; **2 a 10 ou mais**; multiplica só a carga de **fuga** (primário e espalhamento não mudam) | [SRS-47 p. 125] |
| HDR | Paredes, piso e teto são todos barreiras primárias; Ir-192 ou Co-60 pedem **400–800 mm de concreto**; porta pesada de chumbo se não houver labirinto; **porta intertravada** que recolhe a fonte | [SRS-47 p. 115–116] |
| Nêutrons | Acima de cerca de 10 MV, labirinto e porta precisam de cálculo de nêutrons e gama de captura | [SRS-47 p. 48–] |

## TVL (Tabela 4) [SRS-47 p. 59]

| Material, feixe | Co-60 | 6 MV | 10 MV | 15 MV | 18 MV |
| --- | --- | --- | --- | --- | --- |
| Concreto 2350 kg/m³, primário (mm) | 218 | 343 | 389 | 432 | 445 |
| Concreto, fuga a 90° (mm) | 218 | 279 | 305 | 330 | 330 |
| Chumbo, primário (mm) | 41 | 55 | 56 | 57 | 56 |
| Aço, primário (mm) | 71 | 98 | 105 | 108 | 111 |

## Levantamento radiométrico (seção 10) [SRS-47 p. 137–139]

- Varrer o lado externo de cada barreira com GM ou cintilador, **na maior energia e maior taxa de dose**, para achar falhas.
- Primária: feixe em cada barreira, **campo máximo com colimador a 45°**; atenção à transição primária/secundária e às junções teto–parede.
- Secundária: **com fantoma no isocentro**, gantry em 0°, 90°, 180° e 270°; porta e saída de dutos nos quatro ângulos; **nêutrons** em alta energia; skyshine e prédios vizinhos.
- Registrar energia, taxa, campo, ângulos de gantry e colimador, fantoma e sua posição; repetir nas energias mais baixas.
- HDR: fonte na posição do paciente, sem fantoma.
- **Relatório**: equipamento, local, data, executor; W, U e T usados; **instrumento com modelo, série e data de calibração**; resultados; conclusão; planta com os pontos. Se a blindagem for insuficiente: blindagem adicional, **restrição de ângulo com intertravamento**, ou restrição de acesso.

## Como se aplica no CLINICA

- F13: o relatório de levantamento de cada sala (TrueBeam e 6EX na CEL, 600CD na BET, VitalBeam na DUO, HDR e Dermopan na CEL) deve ter os itens da seção 10.3.
- O **fator IMRT** é o ponto mais sensível: salas projetadas para técnica convencional podem não comportar a carga de fuga do VMAT. Reavaliar W e CI quando a fração de VMAT/IMRT crescer (o TrueBeam e o VitalBeam fazem VMAT e FFF).
