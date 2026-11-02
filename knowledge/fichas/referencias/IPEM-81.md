---
codigo: IPEM-81
titulo: "IPEM Report 81: Physics aspects of quality control in radiotherapy (1ª ed.)"
ano: 1999
emissor: IPEM (Reino Unido)
tipo: recomendação
vigencia: "1ª edição substituída pela 2ª ed. (2018), que a lista de aquisição pede"
atividades: [A07, A08, A09, A20, A04, B01, E01, A18, B06]
refs: [TG-142, TECDOC-1151, TG-61, TG-53, TG-66, TG-58]
manuais: []
repos: []
isocentro: []
texto: "../../texto/05 QA de equipamentos, IGRT e dosimetria/IPEM-81.md"
origem: "referencias/05 QA de equipamentos, IGRT e dosimetria/IPEM-81 - Physics aspects of quality control in radiotherapy 1st ed (1999).pdf"
conferida: 2026-10-21
---

# IPEM Report 81 (1999): aspectos físicos do controle de qualidade em radioterapia

**Em uma frase.** Livro britânico de CQ com **capítulos e tabelas de frequência e tolerância** para simulador e TC (3), TPS (4), **aceleradores** (5, incluindo MLC e estereotaxia), cobalto (6), **raios X de kV** (7), instrumentos de dosimetria (8), braquiterapia (9), in vivo e imagem portal (10) e **software próprio** (11).

O PDF tem 303 páginas; texto limpo ("±" preservado). Esta é a **1ª edição**; a lista de aquisição pede a 2ª (2018).

## Acelerador (Tabela 5.2, resumo) [IPEM-81 p. 134–135]

| Frequência | Testes e tolerâncias |
| --- | --- |
| Diário | Constância do débito ±5%; campo luminoso 10×10 2 mm; retículo × lasers 2 mm; telêmetro 3 mm; intertravamento da porta; áudio e vídeo |
| Semanal | **Calibração ±2%**; telêmetro em várias DFS 3 mm; fator de filtro ±2% |
| Quinzenal | Planura e simetria a 0° ±3% |
| Mensal | Intertravamentos e botões de emergência; escalas de gantry e colimador ±0,5°; isocentro rápido 2 mm; campo luz × radiação 2 mm; mesa 2 mm; calibração em água ±2%; energia (razão) ±2%; arco ±2% |
| Trimestral | Débito × ângulo de gantry ±2%; fator de filtro × ângulo ±3%; planura e simetria em todos os ângulos 3% |
| Semestral | Isocentro de radiação 2 mm; linearidade do sistema dosimétrico 1% |
| Anual | Deflexão da mesa com carga 5 mm; isocentro definitivo 2 mm; calibração definitiva ±2%; PDD e perfis no tanque (> 2% de mudança = ação) |

Elétrons (Tabela 5.3), MLC (Tabela 5.5) e estereotaxia (Tabela 5.6) [p. 140–170].

## Raios X de kV (Tabela 7.1) [IPEM-81 p. 190]

| Frequência | Teste | Tolerância |
| --- | --- | --- |
| Diário | Constância do débito (se > ±5% do último mensal, investigar e medir CSR); intertravamentos e filtros | ±5% |
| Mensal | **Débito ±3%**; erro de extremidade do temporizador ±0,01 min; exatidão do temporizador ±2% ou ±0,02 min; linearidade da câmara monitora ±2%; luz × raio X ±5 mm; **constância da CSR ±10%** | — |
| Anual | Uniformidade ±2 mm e ±5%; CSR ±10%; fatores de aplicador ±3% | — |

## Outros capítulos úteis

- Instrumentos: CQ inicial e contínuo de câmaras, TLD, diodos, tanques e fantomas sólidos (Tabelas 8.1–8.6) [p. 210–240].
- Braquiterapia: frequências para fontes, calibrador e equipamento de pós-carga (Tabelas 9.3–9.6).
- Cap. 11: **controle de software próprio** (útil para B06).
- Apêndice B: pesquisa nacional de 1992 sobre frequências praticadas.

## Como se aplica no CLINICA

- A20 (Dermopan): a Tabela 7.1 é referência direta para o CQ de ortovoltagem; reforça o achado de que o PPR da CEL usa 5% no débito mensal, enquanto aqui é **±3%** (e TECDOC-1151 também 3%).
- A07: comparação útil com o TG-142 e o TECDOC-1151 no `programa-cq.csv`; preferir a 2ª edição quando chegar.
