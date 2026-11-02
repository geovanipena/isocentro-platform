---
codigo: AURA-IFU-15.1
titulo: "Varian. ARIA Unified Reporting Application (AURA) Instructions for Use, versão 15.1"
ano: 2017
emissor: Varian Medical Systems
tipo: manual de fabricante
vigencia: "corresponde ao ARIA 15.1; conferir a versão instalada nas clínicas"
atividades: [C04, G18, B03]
refs: [DLT-GUIA]
manuais: []
repos: []
isocentro: []
texto: "../../texto/09 Sistemas Varian (cópias)/AURA-IFU-15.1.md"
origem: "referencias/09 Sistemas Varian (cópias)/AURA-IFU-15.1 - ARIA Unified Reporting Application Instructions for Use (v15.1).pdf"
conferida: 2026-10-21
---

# AURA 15.1: relatórios do ARIA (manual de uso)

**Em uma frase.** O AURA é o espaço de **relatórios** do ARIA OIS: usa o **Microsoft Report Builder** (SQL Server Reporting Services) sobre **modelos de dados desnormalizados** do banco Varian; o manual ensina a usar o espaço de trabalho, criar fonte de dados e *dataset*, desenhar relatórios e lista os **atributos de cada modelo** (cap. 4, cerca de 100 páginas).

O PDF tem 149 páginas (6 só com imagem); texto limpo, tabelas do cap. 4 com colunas quebradas. O ano 2017 é estimado pela versão; o manual não traz data no texto extraído.

## Como funciona

| Item | Conteúdo | Página |
| --- | --- | --- |
| Arquitetura | Espaço de relatórios no ARIA + Report Builder + modelos AURA; o relatório **consulta o banco a cada abertura** (dado sempre atual) | [AURA-IFU-15.1 p. 6] |
| Espaço de trabalho | Painéis de acesso rápido e de relatórios; busca, filtro, modificar modelo, **publicar, exportar e importar** relatórios | [p. 9–17] |
| Modelos Varian | Só membros do grupo de administração do serviço alteram relatórios na pasta *Varian templates* | [p. 26] |
| Fonte de dados | Servidor de relatórios em `https://<servidor>:56300/Reports`; login de usuário válido do ARIA (SF) | [p. 19–23] |
| RDL | Fonte, consulta e leiaute ficam em arquivo RDL | [p. 19] |
| Desenho | Exemplos: relatório de um modelo, de *dataset* compartilhado, com sub-relatório; funções Lookup e LookupSet; tempo limite de processamento | [p. 27–48] |
| Privacidade | Parâmetro nulo devolve **todos os pacientes** com HIPAA desligado; com HIPAA ligado, só os do departamento do usuário | [p. 49 e em cada modelo] |

## Modelos úteis para física [cap. 4]

| Modelo | O que traz | Página |
| --- | --- | --- |
| PrescriptionModel | Uma linha por prescrição RT; status, revisão; filtro "todas ou só aprovadas" | [p. 92] |
| RefPointModel | Por campo e ponto de referência: **dose planejada e real**, sobreposições (*overrides*) | [p. 96] |
| TreatmentModel | Dados de campo planejados | [p. 107] |
| TreatmentHistoryModel | **Valores reais** de cada tratamento (máquina, ângulos, colimador…), por ponto de referência e correções de dose | [p. 117] |
| ToleranceModel | Tabelas de tolerância | [p. 84] |
| PatientInVivoDataModel | Dados de dosimetria in vivo | [p. 80] |
| CheckListItemModel, ChartHistoryModel | Itens de checklist e histórico do prontuário | [p. 129, 134] |
| CarePathTemplateModel, ActivityModel | Modelos de *care path* e atividades | [p. 87, 55] |

## Como se aplica no CLINICA

- C04: relatório AURA de RefPointModel × TreatmentHistoryModel permite a **conferência semanal do prontuário** (dose real acumulada, sobreposições, campos tratados fora do planejado) sem abrir paciente a paciente.
- G18: os modelos expõem nome, foto e diagnóstico; relatório exportado é dado de paciente e fica no servidor da clínica; conferir se o HIPAA (restrição por departamento) está ligado em cada clínica.
- B03: relatórios próprios devem ser retestados a cada atualização do ARIA (o modelo de dados pode mudar entre versões).
