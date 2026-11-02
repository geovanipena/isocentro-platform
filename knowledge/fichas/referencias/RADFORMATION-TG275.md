---
codigo: RADFORMATION-TG275
titulo: "Radformation: TG-275 ClearCheck & ChartCheck comparison (página do fornecedor)"
ano: 2026
emissor: Radformation Inc. (material comercial)
tipo: guia-fornecedor
vigencia: "página web acessada em 14/10/2026"
atividades: [C04, D03, D05, H05, I06]
refs: [TG-275, TG-263]
manuais: []
repos: []
isocentro: ["interface/checklist.py"]
texto: "../../texto/02 Plan check e revisão de prontuário/RADFORMATION-TG275.md"
origem: "referencias/02 Plan check e revisão de prontuário/RADFORMATION-TG275 - Página do fornecedor TG-275 ClearCheck ChartCheck (acesso 2026-10).pdf"
conferida: 2026-10-20
---

# Radformation: itens do TG-275 automatizados por ClearCheck e ChartCheck

**Em uma frase.** É a página comercial que lista, item por item, os modos de falha do **TG-275** e diz qual produto da Radformation automatiza cada um: **ClearCheck** (plano antes do tratamento, dentro do Eclipse) e **ChartCheck** (prontuário semanal e de fim de tratamento). Serve como **lista pronta do que dá para automatizar** e como referência do que um produto comercial entrega.

O PDF tem 20 páginas (impressão da página web). **As marcas de "coberto" por produto são imagens e não foram extraídas**: para saber quem cobre o quê, olhar o PDF.

## Itens listados (seguem as categorias do TG-275)

| Bloco | Itens | Página |
| --- | --- | --- |
| Avaliação do paciente | Aprovação da prescrição; marca-passo, CDI, bombas; **radioterapia prévia**; revisão por pares da decisão | [RADFORMATION-TG275 p. 2] |
| Simulação e movimento | Isocentro; isocentro × marcação e instrução de setup; extensão da TC; orientação da imagem; apneia e gating | [p. 2–3] |
| Contornos | Alvos, OAR, BODY, margens, estruturas de otimização, **override de densidade**, mesa e acessórios | [p. 3–4] |
| Prescrição × plano | Local, **lateralidade**, energia, bólus, dose por fração, número de frações, blindagem, modalidade, técnica | [p. 4–5] |
| Isocentro | Deslocamentos, isocentros múltiplos | [p. 5–6] |
| Otimização e cálculo | Objetivos, normalização, **algoritmo**, **grade de cálculo**, override | [p. 6] |
| Qualidade da dose | DVH, cobertura, OAR, pontos quentes, **soma de planos** | [p. 7] |
| Parâmetros do campo | Entregabilidade, nome do campo, curso e plano, máquina, modificadores, UM, energia, taxa, campo, abertura, **tabela de tolerância**, tempo, bólus, **colisão**, deslocamentos, **modelo de mesa**, pontos de referência, **dose tracking e breakpoints**, avisos do TPS | [p. 7–10] |
| Transferência TPS → OIS | Nome, dose/fração, frações, máquina, arranjo, energia, UM, gantry, colimador, campo, **pontos de controle do MLC**, modificadores, mesa, isocentro | [p. 10–12] |
| IGRT | DRR, isocentro da imagem de referência, técnica de imagem | [p. 12] |
| Replanejamento em TC nova | Isocentro, contornos deformados, DVH, cobertura, OAR | [p. 12–13] |
| Checagens adicionais | Intenção aprovada; plano de verificação do QA de paciente; aprovação final | [p. 13] |
| Revisão semanal (ChartCheck) | Prescrição = plano; **override de parâmetro sem documentação**; posição da mesa; instruções de setup; campos tratados; dose acumulada; tratamentos parciais; **interrupções inesperadas**; **tratamento fora do modo clínico**; dosimetria in vivo; sequência e regime; imagens aprovadas e deslocamentos | [p. 14–17] |
| Fim de tratamento | Resumo presente, documentos aprovados, curso completo ou interrompido documentado, tarefas da física concluídas | [p. 17–18] |

## Como se aplica no CLINICA

- H05 e C04: a lista é um bom **roteiro de requisitos** para estender o `interface/checklist.py` do ISOCENTRO (o que dá para ler por ESAPI: algoritmo, grade, tabela de tolerância, modelo de mesa, breakpoints, override de densidade).
- D03 e D05: os itens do ChartCheck são o conteúdo da revisão semanal e de fim de tratamento.
- É material de venda: o grau de automação real de cada item deve ser conferido no produto, não aqui.
