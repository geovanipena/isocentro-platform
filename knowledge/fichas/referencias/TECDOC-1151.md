---
codigo: TECDOC-1151
titulo: "Aspectos físicos da garantia da qualidade em radioterapia: protocolo de controle de qualidade (IAEA TECDOC-1151, tradução PQRT/INCA)"
ano: 2000
emissor: IAEA (Projeto ARCAL); tradução brasileira INCA/PQRT
tipo: recomendação (base declarada do programa de testes nos PPRs das três clínicas)
vigencia: histórico (os testes de acelerador derivam do TG-40, de 1994); continua citado nos PPRs
atividades: [A04, A05, A07, A09, A11, A12, A13, A15, A20, B01, E03]
refs: [TG-142, MPPG-8b, NN-6.10, TRS-398-R1]
manuais: []
repos: []
isocentro: []
texto: "../../texto/05 QA de equipamentos, IGRT e dosimetria/TECDOC-1151.md"
origem: "referencias/05 QA de equipamentos, IGRT e dosimetria/TECDOC-1151 - Aspectos físicos da garantia da qualidade em radioterapia (PQRT, PT).pdf"
conferida: 2026-10-16
---

# TECDOC-1151: protocolo de controle de qualidade em radioterapia

**Em uma frase.** É o protocolo ARCAL/IAEA, traduzido pelo INCA, que **os PPRs da CEL, da BET e da DUO declaram seguir** ("os testes realizados no Acelerador Linear seguem as periodicidades e tolerâncias dispostas no TECDOC 1151"). A tabela de acelerador é **adaptada do TG-40 (1994)**: não tem MLC, IMRT, imagem nem FFF.

O PDF tem 162 páginas. O texto foi extraído **por OCR**, porque a fonte do PDF não tem mapa Unicode, e as tabelas perdem a ordem das colunas. **Todos os valores abaixo foram lidos na imagem da página.**

## Tabelas do protocolo

| Tabela | Conteúdo | Página |
| --- | --- | --- |
| I | Unidades de Co-60 | p. 35 |
| **II** | **Aceleradores (adaptada do TG-40)** | **p. 37–38** |
| III | Simuladores | p. 39 |
| **IV** | **Roentgenterapia (ortovoltagem)** | **p. 40** |
| V, VI, VII | Sistema de planejamento; processo de planejamento | p. 41–43 |
| VIII, IX, X, XI | Braquiterapia: fonte, aplicadores, equipamento, sistema | p. 44–46 |
| XII | Execução de um tratamento | p. 47 |
| **XIII** | **Equipamentos de medida** | **p. 48** |
| **XIV** | **Calibrador de fontes de braquiterapia (câmara poço)** | **p. 49** |
| J.1 | Aspectos a auditar | p. 151 |

## Tabela II: aceleradores [p. 37–38]

**Diário.** Segurança: luzes, sistemas de visualização, anticolisão, interruptores de radiação na porta e no painel, programação, interrupção por UM e câmaras monitoras "funcionando e coincidentes". Mecânicos: lasers 2 mm; telêmetro 2 mm na DFI; tamanho de campo 10×10, 2 mm; centro do retículo, 2 mm de diâmetro; centro do campo luminoso 2 mm. Dosimétrico: **constância da dose de referência (fótons e elétrons) 3%**.

**Mensal.**
- Segurança: topo da mesa; travas e códigos de acessórios; pulsadores de corte de energia; colimadores por cone de elétrons; campos permitidos para filtros.
- Mecânicos: angulares de gantry e colimador 1°; telêmetro 2 mm no intervalo de uso; centro do retículo 2 mm de diâmetro; simetria, paralelismo e ortogonalidade do campo luminoso 2 mm; tamanho de campo 2 mm; isocentro mecânico 2 mm de diâmetro; coincidência luz × radiação 2 mm; horizontalidade da mesa 2 mm; filtro 2 mm (ou 2% no fator de transmissão); bandeja 2 mm; cones 2 mm; verticalidade do eixo luminoso 2 mm; escalas da mesa 2 mm/1°.
- Dosimétricos: dose de referência 2%; monitor secundário 2%; qualidade de fótons (PDD20,10 ou TPR20,10) 2%; PDD de elétrons (ou J1/J2) 2 mm (4%) na região terapêutica; **planura de fótons 2%ᵃ, planura de elétrons 3%ᵃ, simetria 3%ᵃ**.

**Anual.**
- Mecânicos: isocentros de rotação do colimador, do gantry e da mesa, coincidência dos eixos e coincidência dos isocentros mecânico e de radiação, todos com 2 mm de diâmetro; deslocamento vertical da mesa 2 mm. Segurança: todas as travas, conforme o fabricante.
- Dosimétricos, **pela ordem das 12 linhas** (na página os rótulos de duas linhas desalinham a coluna de tolerâncias):

| Teste | Tolerância |
| --- | --- |
| Constância da dose de referência | 2% |
| Reprodutibilidade da dose de referência | 1% |
| Constância dos fatores de campo | 2% |
| Constância de parâmetros no eixo central (PDD, TMR) | 2% |
| Constância dos fatores fora do eixo central | 2% |
| Transmissão de todos os acessórios | 2% |
| Transmissão dos filtros | 2% |
| **Linearidade das câmaras monitoras** | **1%** |
| **Dependência da dose de referência com a taxa de dose** | **1%** |
| Dose de referência × angulação do gantry | 2% |
| Fatores fora do eixo × angulação do gantry | 2% |
| Modo rotacional | Funcionando |

ᵃ Dentro das especificações do fabricante, não se admite **incremento absoluto de mais de 2%** em relação ao estado de referência inicial. Exemplo: simetria inicial de 0,5% admite até 2,5% [p. 38].

## Tabela IV: roentgenterapia [p. 40]

| Freq. | Teste | Tolerância |
| --- | --- | --- |
| Diária | Painel, interruptores (porta e painel), visualização, filtros e cones, movimentos e freios | Funcionando |
| Mensal (um cone e uma qualidade por mês) | Constância da dose de referência; qualidade do feixe (CSR); planura e simetria | **3%**; 3%; 3%ᵇ |
| Anual | Protetor de sobrecarga | Funcional |
| Anual | Fuga: < 50 kV, a 5 cm da fonte / 50–500 kV, a 1 m | 0,30 Gy/h / 0,01 Gy/h |
| Anual | Dose de referência; CSR; dose × movimento do braço; fatores de cone; PDD; taxa × mA; estabilidade (ordem das linhas) | 3%; 2%; 3%; 3%; 3%; 2%; 2% |
| Anual | Temporizador: reprodutibilidade; linearidade; correção do tempo efetivo | 1%; 1%; 2% (2 s) |

A **NN-6.10, art. 57, II** fixa a fuga para tubo de até 50 kV em **1 mGy/h a 5 cm**, valor muito mais restritivo que os 0,30 Gy/h do TECDOC. Para o Dermopan, vale a norma.

## Tabela XIII: equipamentos de medida [p. 48]

| Instrumento | Teste | Tolerância | Frequência |
| --- | --- | --- | --- |
| Referência | Calibração em LSCD | Certificado | Bianualᵃ |
| Referência | Linearidade / correção atmosférica | 0,5% / registrada | Bianualᵃ |
| Referência | Sinal extracâmara; fuga; **constância (fonte de referência, ex. Sr-90)**; recombinação; polaridade | 0,5%; 0,1%; **2%**; registrada; 1% | I; em cada uso; em cada uso; I; em cada uso |
| Campo | Comparação com a referência local | 1% | Anual |
| Analisador de feixe | Ajuste mecânico; exatidão posicional | 2 mm; 2 mm | I; em cada uso |
| Termômetro; barômetro; régua | Calibração | 0,2 °C; **1 mmHg, trimestral**; 1 mm | I; trimestral; I |
| Monitor de área | Calibração | Certificado (20%) | Anual |

ᵃ Bianual basta se houver programa de verificações redundantes. I = inicial ou após reparo.

## Tabela XIV: câmara poço [p. 49]

Calibração em LSCD/LPCD na compra e por radionuclídeo; precisão 2%; linearidade 1% (na compra e bianual); checagens redundantes 2% em cada uso; fuga registrada em cada uso.

## TECDOC × norma × prática atual

| Ponto | TECDOC-1151 | Norma / AAPM | PPR das clínicas |
| --- | --- | --- | --- |
| Constância com fonte-teste | 2%, em cada uso | **NN-6.10 art. 49: ±1%, no mínimo trimestral** | "Aferição trimestral" (sem tolerância escrita) |
| Linearidade das câmaras monitoras | **1%** | TG-142: ±2% (≥ 5 UM) | **2%**: provável erro de transcrição causado pelo desalinhamento da tabela |
| Ortovoltagem: dose mensal | 3% | — | **5%** (CEL) |
| Ortovoltagem: fuga ≤ 50 kV | 0,30 Gy/h a 5 cm | **NN-6.10 art. 57: 1 mGy/h a 5 cm** | Não consta |
| MLC, IMRT/VMAT, imagem, FFF | Não existe | TG-142 Tab. V e VI; MPPG-8b MLC1–4 | Não consta (**falha do PPR, a corrigir pelo ISOCENTRO**) |

## Como se aplica

Base histórica e legal do PPR. Para o programa atual, usar como **piso**: tudo o que está aqui continua valendo, e o TG-142 e o MPPG-8b acrescentam o que falta para IMRT, VMAT e IGRT. As fichas de atividade A07, A08, A13 e A20 fazem a comparação teste a teste.
