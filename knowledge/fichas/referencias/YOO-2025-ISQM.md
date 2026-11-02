---
codigo: YOO-2025-ISQM
titulo: "Quality management for radiation oncology in-house software products"
ano: 2025
emissor: Duke University (Yoo et al., Bioengineering 12:352)
tipo: artigo (modelo de processo)
vigencia: vigente
atividades: [B06, B08, B10, G19]
refs: [RDC-657, IEC-62304, ISO-14971, FDA-GPSV-2002, FDA-CSA-2026, TG-100]
manuais: ["Eclipse Scripting API Reference Guide"]
repos: []
isocentro: ["docs/qms/", "tests/", "CLAUDE.md"]
texto: "../../texto/08 Software, dispositivo médico e dados/YOO-2025-ISQM.md"
origem: "referencias/08 Software, dispositivo médico e dados/YOO-2025-ISQM - Quality management for radiation oncology in-house software products (2025).pdf"
conferida: 2026-10-16
---

# YOO-2025: gestão da qualidade de software próprio em radio-oncologia (ISQM)

**Em uma frase.** É o programa da Duke para **todo software próprio que influencie decisão clínica**, de script ESAPI e consulta SQL a ferramenta de IA. Tem dois pilares: **QA** (revisão de código independente, aceitação, comissionamento e QA de rotina) e **documentação** (relatório do produto, manual, documentos de QA, release note, controle de versão e log). Nada vai para uso clínico sem os dois completos [p. 1, p. 6].

O PDF tem 10 páginas e o texto saiu limpo.

## Etapas de QA [p. 2–4]

| Etapa | O que é | Detalhe que importa |
| --- | --- | --- |
| **Revisão de código** | Revisor **independente**, que não desenvolveu, avalia algoritmo, código, organização e documentação | Deve ser capaz de **continuar o desenvolvimento se o autor sair**; aponta casos-limite; o que não confirmar vai para a aceitação ou o comissionamento |
| **Aceitação** | Funciona sem erro, conforme a especificação, **no ambiente clínico** | Pode ser fundida ao comissionamento |
| **Comissionamento** | Atende aos requisitos clínicos de operação segura | Cenários típicos **e casos-limite**; testes críticos **repetidos com a mesma entrada**; **todas as faixas de entrada validadas**; **teste fim a fim** do fluxo; casos de teste guardados para recomissionar |
| **QA de rotina** | Versão enxuta do comissionamento | Disparada por **atualização do software** e também por **mudança no ambiente** (plataforma, rede, dados associados, prática clínica), **imediatamente antes e depois** da mudança; mesmo conjunto de testes; define frequência, responsável, limiar, ação corretiva e registro |

Gatilhos do QA de rotina depois da liberação [p. 8]: mudança de plataforma ou rede; mudança nos dados associados ou na prática clínica; bug descoberto; pedido de melhoria; outra mudança significativa. Uma atualização faz o produto voltar ao fluxo **desde a revisão de código**.

## Documentação por produto [p. 4–6]

| Documento | Conteúdo |
| --- | --- |
| **Relatório do produto** | Escopo e objetivos clínicos, fluxo e usuários; especificação técnica, fluxo de dados e **fatores de risco**; pessoas (desenvolvedor, revisor, QA) e recursos; lista de documentos. Modelo em perguntas e respostas (Fig. 2, p. 7) |
| **Manual do produto** | Passo a passo para o usuário operar sozinho |
| **Documentos de QA** | Checklist da revisão de código (Tab. 1, p. 7–8); relatório de comissionamento; relatórios de QA de rotina; sempre com **data e nome** de quem fez |
| **Release note** | Uma por produto, acumulada: versão, data, novidades e correções, comunicadas aos usuários com o QA de rotina |
| **Controle de versão** | Versão, arquivo, motivo, local, data e desenvolvedor, num documento único acumulado |
| **Log** | Uma linha por atividade (atualização, QA, erro resolvido), com data e iniciais |

## Checklist da revisão de código (Tab. 1) [p. 7–8]

Administrativo (código no diretório do programa e executando); requisitos (busca as tabelas certas, ao vivo ou data warehouse; lógica correta); desempenho; nomes legíveis; formatação padronizada; cabeçalho e comentários; **casos-limite para o QA**; **faixas de entrada verificadas**; **arquivos de entrada validados**; **bibliotecas de terceiros usadas** (liga-se à B10).

## Exemplo do artigo

Um **script ESAPI em C#** (AutoSetupFields) que cria os campos de setup (kV, CBCT, MV). A revisão de código achou um erro de digitação nos campos G90/G270 e a ausência do campo de CBCT [p. 6–8]: exatamente o perfil dos scripts do serviço.

## Como se aplica

| Produto do serviço | Situação frente ao ISQM |
| --- | --- |
| **ISOCENTRO** | Já tem git, `tests/` (suíte com mais de 2.300 testes), `CLAUDE.md` e `docs/qms/` (escopo, classe, riscos). Faltam: revisor de código independente, relatório de comissionamento por módulo, manual, release note e log no formato do ISQM |
| **5 Campos FiF, Estruturas-auxiliares, PrePlan** (ESAPI com escrita) | Precisam do ciclo completo **e** da aprovação de script do Eclipse (ver a ficha do manual da ESAPI) |
| **Proprietário de Tarefas e consultas** (leitura) | Ciclo completo, com comissionamento mais leve |
| **`ppr-streamlit`** | Gera documento regulatório (PPR), não decide dose. Mesmo assim, mudanças como a do programa de CQ pedem revisão e registro |

O ISQM é a forma prática de cumprir o art. 5º, §§ 2º a 4º da **RDC-657** (registros completos de validação e histórico de alterações).
