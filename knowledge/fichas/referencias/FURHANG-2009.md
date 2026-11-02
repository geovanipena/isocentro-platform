---
codigo: FURHANG-2009
titulo: "Furhang EE et al. Automating the initial physics chart-checking process. J Appl Clin Med Phys 10(1):129–135"
ano: 2009
emissor: Beth Israel Medical Center (artigo, JACMP)
tipo: artigo
vigencia: histórico (método ainda útil)
atividades: [C04, H05, G19, B04]
refs: [TG-275, TG-201, YANG-2012-ECHART, DEWHURST-2015]
manuais: []
repos: []
isocentro: ["interface/checklist.py"]
texto: "../../texto/02 Plan check e revisão de prontuário/FURHANG-2009.md"
origem: "referencias/02 Plan check e revisão de prontuário/FURHANG-2009 - Automating the initial physics chart-checking process (2009).pdf"
conferida: 2026-10-20
---

# Furhang 2009: automatizar a checagem física inicial do prontuário

**Em uma frase.** Divide a checagem física inicial em **revisão intraplano** (prescrição × plano × R&V, coerência entre campos) e **revisão interplano** (cada parâmetro comparado com casos semelhantes por **controle estatístico de processo**), extraindo os dados do R&V depois das edições manuais. A checagem caiu de **cerca de 1 hora para 2–4 minutos** [FURHANG-2009 p. 1, 5].

PDF de 7 páginas, texto limpo; as fórmulas dos limites não foram extraídas.

## Método

| Parte | O que faz | Página |
| --- | --- | --- |
| Fonte dos dados | Relatório do **R&V** (não do TPS), depois que técnicos e físicos acrescentam mesa, sequência e taxa | [FURHANG-2009 p. 2] |
| Intraplano | Diagnóstico → local e **lateralidade** → modalidade, energia, MLC, filtro, bólus → dose/fração e frações → isodose de prescrição × normalização → comentários da prescrição | [FURHANG-2009 p. 2] |
| Parâmetros "constantes" | Iguais em todos os campos (máquina, energia, **tabela de tolerância**, taxa, mesa); os marcados "v" são **digitados uma vez pelo físico** e comparados, porque podem estar todos iguais e errados | Tab. 1 [FURHANG-2009 p. 2, 4] |
| Parâmetros "únicos" | Variam por campo (gantry, mandíbulas laterais, filtro, bólus); revisão manual; soma das doses por campo × prescrição | Tab. 1 [FURHANG-2009 p. 4] |
| Interplano | Casos agrupados por órgão, posição, técnica e dose; cartas de média e amplitude (n = 1) com limites de 3σ (cerca de 1% de falso alarme); só mostra o que passa do limite | [FURHANG-2009 p. 4–5] |
| Tendência | Regras de Western Electric (1 fora; 2 de 3; 4 de 5; 8 seguidos do mesmo lado) detectam **mudança de protocolo** (margem maior → mandíbulas maiores) | [FURHANG-2009 p. 7] |

## Resultados (45 prontuários)

Encontrou: próstata em decúbito ventral planejada com arranjo de dorsal; ângulos atípicos por prótese de quadril; **3 tabelas de tolerância erradas**; soma das doses dos campos diferente da prescrição; posição de mesa capturada só no primeiro campo [FURHANG-2009 p. 6].

## Pontos de atenção

- Só implementar depois que os protocolos clínicos estiverem comissionados, senão a estatística "valida" um processo errado [FURHANG-2009 p. 7].
- Quando o protocolo muda, reiniciar a série estatística no ponto da mudança.

## Como se aplica no CLINICA

- H05 e C04: a ideia do parâmetro "digitado uma vez e comparado" (tabela de tolerância, máquina, energia) e a comparação com casos semelhantes cabem no `interface/checklist.py` do ISOCENTRO, lendo o plano aprovado por ESAPI.
- G19: as cartas de controle por sítio (UM por Gy, mandíbulas, SSD) são um indicador simples de mudança de prática.
