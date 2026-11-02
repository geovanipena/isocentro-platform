---
codigo: NCS-VMAT-2016
titulo: "NCS Report 24: Code of practice for the quality assurance and control for volumetric modulated arc therapy"
ano: 2015
emissor: Netherlands Commission on Radiation Dosimetry (NCS), fev. 2015
tipo: recomendação
vigencia: vigente
atividades: [A07, B02, C06, C11, B04, H01]
refs: [TG-218, TG-142, TG-120, MPPG-5b-TPS, TG-201]
manuais: []
repos: [jrkerns/pylinac]
isocentro: []
texto: "../../texto/02 Plan check e revisão de prontuário/NCS-VMAT-2016.md"
origem: "referencias/02 Plan check e revisão de prontuário/NCS-VMAT-2016 - NCS Report 24 Code of practice for QA and QC of VMAT (2015).pdf"
conferida: 2026-10-20
---

# NCS Report 24 (2015): código de prática para QA e CQ de VMAT

**Em uma frase.** É o roteiro holandês completo para **implantar e manter VMAT**: testes da máquina específicos de arco (velocidade de gantry e lâmina, taxa de dose variável, interrupção), modelagem no TPS, validação de transferência, checagens de plausibilidade e **QA de paciente por "solução de classe"**, com tolerâncias e frequências.

O PDF tem cerca de 70 páginas; o texto saiu limpo.

## Testes da máquina (cap. 2, Tabela 4)

| Teste | Tolerância | Frequência | Página |
| --- | --- | --- | --- |
| Ângulo do gantry, gantry parado | **1°** (0,5° alcançável) | Aceitação, **semestral** | [NCS-VMAT-2016 p. 12, 32] |
| Ângulo do colimador | 1° | Aceitação, semestral | [p. 12–13, 32] |
| Posição das lâminas, gantry parado | **< 1,0 mm**, de preferência < 0,5 mm; reprodutibilidade < 0,5 mm | **Mensal** (ângulos ≠ 0°: anual) | [p. 13, 32] |
| Linearidade / reprodutibilidade do débito | 1% / 0,5% | Aceitação | [p. 14, 32] |
| Planura e simetria, gantry parado | 3% (1,5% alcançável) | Mensal | [p. 15, 32] |
| Velocidade de gantry e de lâmina | Dentro da especificação; **máximos lançados no TPS** | Aceitação | [p. 15–16, 32] |
| **Débito em várias taxas de dose** | **0,5%** da referência | **Semanal** | [p. 17, 32] |
| Planura/simetria na menor taxa | 2% | Aceitação / indicação | [p. 18, 32] |
| Planura/simetria com gantry girando e taxa variando | 2% do perfil de referência; voltar a 2% em 5 UM após troca de taxa | Aceitação / indicação | [p. 19, 32] |
| Débito acima de 1000 UM | 0,5% | Anual | [p. 22, 33] |
| Débito com taxa variável e velocidade constante | Plano integral 0,5%; por segmento 1% | Aceitação / indicação | [p. 22–23, 33] |
| Taxa × velocidade de gantry | Perfis com e sem rotação < 2% | Aceitação / indicação | [p. 24, 33] |
| Débito na taxa e velocidade máximas | Pico angular em 1° | **Trimestral** | [p. 25–27, 33] |
| Lâminas em modo dinâmico | < 1,0 mm (desejável < 0,5 mm) | Aceitação / indicação | [p. 30, 33] |
| **Interrupção do arco** | Plano interrompido × contínuo: **1%** (de preferência 0,5%) | **Anual** | [p. 31, 33] |

Depois da aceitação, um conjunto fixo de **planos clínicos de VMAT** serve para conferir a constância [NCS-VMAT-2016 p. 32].

## TPS e transferência (cap. 3 e 4.4)

- Lançar no TPS os **limites reais** (taxa máxima, velocidade de lâmina e de gantry, tamanho mínimo de segmento) e testar que o TPS os respeita com planos extremos [NCS-VMAT-2016 p. 41–42].
- Máquinas "casadas" só podem dividir o mesmo modelo se todas tiverem o mesmo recurso (ex.: *jaw tracking*); senão, modelo separado [NCS-VMAT-2016 p. 42].
- Na Varian, TPS e R&V usam o mesmo banco; ainda assim testar se o R&V reconhece o arco, o sentido de rotação e os pontos de controle, com **cerca de 5 planos por solução de classe**, e criar procedimento contra **plano errado transferido** ou **plano alterado manualmente** no R&V [NCS-VMAT-2016 p. 54–55].

## QA de paciente (4.5–4.6)

| Item | Recomendação | Página |
| --- | --- | --- |
| Plausibilidade | Detectar erros de **10% ou mais**; usar a **dose prescrita** como referência e os dados **do R&V** (também testa a transferência). Cuidado: cálculo de UM pode usar só a DFS do início do arco | [NCS-VMAT-2016 p. 55–56] |
| γ | **3%/3 mm, aprovação mínima de 90%**, de preferência com dosimetria absoluta; **γ médio > 0,5** pede análise de especialista; excluir regiões de dose baixa | [NCS-VMAT-2016 p. 56–57] |
| Solução de classe nova | *Dummy run*; depois **4 planos a cada 3 meses**, sorteados, em **todas as máquinas** | [NCS-VMAT-2016 p. 57] |
| Número de verificações pré-tratamento (Tab. 6) | Sem experiência em VMAT: **30 pacientes**; classe nova parecida: 5; diferente: 10; com experiência (> 100 pacientes) e classe existente: todos, com equipamento de classe IV; reavaliação: 1 | [NCS-VMAT-2016 p. 58] |
| Depois de experiência | Cálculo de UM pode bastar como verificação pré-tratamento (ainda em debate) | [NCS-VMAT-2016 p. 59] |

## Como se aplica no CLINICA

- A07: os testes específicos de VMAT (taxa variável semanal a 0,5%, interrupção anual, débito acima de 1000 UM) faltam no programa derivado do TG-142/TECDOC-1151; avaliar inclusão no `programa-cq.csv` para o TrueBeam (CEL) e o VitalBeam (DUO).
- C06: o critério 3%/3 mm ≥ 90% do NCS é **mais frouxo** que o do TG-218 (3%/2 mm ≥ 95%, ação < 90%); preferir o TG-218 e usar daqui a lógica de **solução de classe** e a amostragem trimestral.
- B04: o procedimento contra plano errado ou alterado no ARIA se liga ao checksum (SCIC) do TG-201.
