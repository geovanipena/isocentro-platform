---
codigo: TECDOC-1583
titulo: "IAEA-TECDOC-1583: Commissioning of radiotherapy treatment planning systems: testing for typical external beam treatment techniques"
ano: 2008
emissor: IAEA
tipo: recomendação
vigencia: "vigente para 3D conformacional; IMRT/VMAT ficam com MPPG-5b e TG-119"
atividades: [B01, B02, B03, B05, A09, B04]
refs: [TRS-430, MPPG-5b-TPS, TG-53, TECDOC-1151]
manuais: []
repos: []
isocentro: []
texto: "../../texto/02 Plan check e revisão de prontuário/TECDOC-1583.md"
origem: "referencias/02 Plan check e revisão de prontuário/TECDOC-1583 - IAEA Commissioning of TPS testing for typical external beam techniques (2008).pdf"
conferida: 2026-10-20
---

# IAEA-TECDOC-1583 (2008): comissionamento clínico do TPS com 8 casos-teste

**Em uma frase.** Complementa o TRS-430 com um **conjunto pequeno e prático de testes "fim a fim" do TPS** num fantoma de tórax heterogêneo (CIRS 002LFC): 2 testes anatômicos e **8 casos dosimétricos** do campo simples ao arranjo não coplanar, cada ponto com **critério de concordância de 2% a 5%**, e um **programa de CQ periódico** que reaproveita esses casos.

O PDF tem cerca de 60 páginas; texto limpo. A Tabela D.1 foi conferida na imagem da página.

## Casos-teste (cap. 2 e Apêndice A)

| Caso | Situação | Critério nos pontos | Página |
| --- | --- | --- | --- |
| Anatômico 1 | Contorno digitalizado (não dosimétrico) | — | [TECDOC-1583 p. 13, 20] |
| Anatômico 2 | **Curva número CT → densidade eletrônica** com os insertos certificados (pulmão 0,207; osso 1,506; músculo 1,042; adiposo 0,949) | — | [TECDOC-1583 p. 12–13, 21] |
| 1 | Campo de referência no TC | 2% (ponto de referência); até 4% em ponto fora | Tab. A.18 [TECDOC-1583 p. 33] |
| 2 | Incidência oblíqua, falta de espalhamento, tangente | 3% | [p. 33] |
| 3 | Bloqueio grande dos cantos | 3% | [p. 33] |
| 4 | Box de 4 campos (com pontos em pulmão e osso) | 2–4% | [p. 33–34] |
| 5 | Expansão automática e bloqueio personalizado | 3–4% | [p. 34] |
| 6 | Campo irregular oblíquo com bloqueio central | 3–5% | [p. 34] |
| 7 | Três campos, dois com filtro, colimação assimétrica | 2–4% | [p. 34] |
| 8 | Não coplanar: rotação de mesa e colimador | conforme tabela | [p. 34] |

Pré-requisito: o **ajuste do modelo de feixe** de cada algoritmo validado em água pelos critérios da Tabela 8 do TRS-430 (campos abertos, irregulares e com filtro) [TECDOC-1583 p. 10–11]. Medições com **câmara de volume pequeno** calibrada e grade de cálculo clínica [TECDOC-1583 p. 12].

## CQ periódico do TPS (Apêndice D, Tabela D.1) [TECDOC-1583 p. 50–54]

| Teste | Frequência | Critério |
| --- | --- | --- |
| CPU | Mensal | — |
| **Recuperação de backup** (apagar um caso-teste e restaurar) | **Trimestral** | Plano restaurado íntegro |
| Transferência de TC (marcas E/D, S/I) | Trimestral | Correto |
| **Densidade e geometria no TC** | Trimestral | Distâncias **2 mm**; densidade eletrônica relativa **0,02** (cerca de ±20 UH) |
| Anatomia do paciente | Trimestral | 2 mm |
| **Revalidação do cálculo** (checksum dos arquivos de feixe; casos-teste refeitos do zero) | **Anual** | **Reprodutibilidade exata**, não exatidão; após upgrade, a nova versão vira referência |
| UM/tempo dos casos-teste | Trimestral | Concordância exata |
| Detalhes impressos do plano | Trimestral | Iguais |
| Transferência eletrônica do plano | Trimestral, e **a cada mudança** de dados, código ou sistema | Igual |

## Como se aplica no CLINICA

- B01/B03: os 8 casos são uma bateria pronta para o fim a fim do Eclipse em 3D (o 600CD da BET e o 6EX da CEL, com filtros físicos) e para repetir após upgrade; para VMAT usar MPPG-5b/TG-119.
- B05: o teste trimestral de **backup e restauração** com um caso-teste é a evidência mais simples para a ficha B05.
- A09: a checagem trimestral de números CT (±20 UH, 2 mm) liga o CQ da TC de simulação ao TPS.
