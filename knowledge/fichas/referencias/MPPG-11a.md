---
codigo: MPPG-11a
titulo: "AAPM MPPG 11.a: Plan and chart review in external beam radiotherapy and brachytherapy"
ano: 2021
emissor: AAPM (Xia et al., J. Appl. Clin. Med. Phys.)
tipo: recomendação
vigencia: vigente
atividades: [C01, C02, C04, C05, C08, D02, D03, D05, D06, E07, B04]
refs: [TG-275, RDC-20-2006, TG-219, TG-218]
manuais: []
repos: []
isocentro: ["interface/checklist.py", "interface/tratamento.py", "banco/tratamento_db.py"]
texto: "../../texto/02 Plan check e revisão de prontuário/MPPG-11a.md"
origem: "referencias/02 Plan check e revisão de prontuário/MPPG-11a - Plan and chart review in EBRT and brachytherapy (2021).pdf"
conferida: 2026-10-16
---

# MPPG-11a: revisão de plano e prontuário (prática mínima)

**Em uma frase.** É a versão prática e mínima do TG-275. Diz **quem** revisa o quê, em cada etapa (simulação, prescrição, planejador, físico, técnico, semanal, fim de tratamento, HDR), com listas de itens **recomendados** e **opcionais**.

O PDF tem 16 páginas e o texto saiu limpo.

## Listas por etapa

| Etapa | Tabela | Página |
| --- | --- | --- |
| Simulação | §3.1.1 | 4 |
| Prescrição e delineamento | §3.1.2 | 5 |
| Autochecagem do planejador | Tab. 5 | 6 |
| Elementos do relatório do plano | Tab. 6 | 8 |
| **Revisão inicial pelo físico** | **Tab. 8** | 10 |
| Revisão inicial pelo técnico | Tab. 9 | 11 |
| **Revisão semanal** | **Tab. 10** | 11 |
| **Revisão de fim de tratamento** | **Tab. 11** | 12 |
| HDR: prescrição, documentos, revisões inicial, semanal e final | §3.1.8–3.1.14 | 12–14 |
| Comparação com o TG-275 | §5.2 | 15 |

## Pontos práticos

- **Revisão inicial (Tab. 8):** inclui **"diferença do cálculo secundário < 5%"** como item recomendado [p. 10], além da dose de tratamento prévio somada ao plano, da tabela de tolerância correta, das instruções de CBCT/IGRT, do agendamento coerente com a prescrição e do rastreio de dose.
- **Revisão semanal (Tab. 10):** **a cada cinco frações ou antes do próximo bloco de cinco**; mais frequente em BID [p. 9]. Itens: mudança de prescrição ou campo; dose e frações entregues; qualidade do plano e QA de IMRT (na 1ª semanal); frequência e modalidade de imagem conforme a prescrição; rastreio de dose; **overrides comentados**; in vivo; **interrupções documentadas**; **dispositivo especial (marca-passo)**; verificação secundária de setup (DFS, SGRT, separação); deslocamentos de mesa e de IGRT dentro dos limites [p. 11].
- **Fim de tratamento (Tab. 11):** sítio; **dose total e frações entregues**; **dose total = prescrição** (se não, documentado); documentos assinados [p. 12]. Tratamento interrompido: comentário em local muito visível [p. 12].

## Como se aplica

Base das fichas C04, D02, D03, D05 e D06. A Ficha Virtual do ISOCENTRO (tratamento entregue lido do `variandw`) tem os dados para automatizar boa parte da revisão semanal e da final.
