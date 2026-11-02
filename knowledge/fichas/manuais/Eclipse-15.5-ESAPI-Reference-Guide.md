---
manual: "Eclipse Scripting API Reference Guide"
codigo_documento: P1021698-003-C
produto: Eclipse Scripting API
versao: "15.5"
versao_instalada: "ESAPI 15.6.8.73 / Eclipse 15.6 MR5"
origem: "manuais/Varian/ECLIPSE/Eclipse Scripting API Reference Guide.pdf"
paginas: 69
atividades: [B06, B08, B10, C10, C11, B03]
refs: [IEC-61217, IEC-62304, ISO-14971, FDA-GPSV-2002, DICOM-RT, RDC-657]
manuais: ["ESAPI 15.6 - documentacao oficial (site)", "Eclipse Treatment Planning - Customer Release Note (v15.6 MR5, 2025-12)", "Image Registration and Segmentation Scripting API Reference Guide"]
repos: [VarianAPIs/Varian-Code-Samples, VarianAPIs/PyESAPI, rexcardan/ESAPIX, LDClark/PlanCheck]
isocentro: ["programa/scriptsvarian (5 Campos FiF, Proprietário de Tarefas)", "programa/preplan", "programa/Estruturas-auxiliares_API", "dominio/qualidade.py (porte de plug-in ESAPI)"]
conferida: 2026-10-16
---

# Eclipse Scripting API: guia de referência (15.5)

**Em uma frase.** É o manual que define o que um script pode fazer no Eclipse e, principalmente, **o caminho obrigatório para um script com escrita chegar ao uso clínico**: desenvolvimento em sistema de pesquisa, comissionamento e validação, avaliação, aprovação e aposentadoria.

> **Versão.** O guia é da 15.5 (2017, revisado em 2020). A instalada é a **ESAPI 15.6.8.73**. A Varian "não garante que scripts escritos com esta versão sejam compatíveis com versões futuras" [p. 13]. Para a API da 15.6, use a documentação oficial em `manuais/Varian/ECLIPSE/ESAPI 15.6 - documentacao oficial (site)/` e a release note da 15.6 MR5.

## Índice por tarefa do físico

| Tarefa | Seção | Página |
| --- | --- | --- |
| Saber o que a ESAPI permite (DRR, otimização, cálculo de dose, DVH estimation, estruturas) | Features | 11–12 |
| Requisitos e licenças (clínico × pesquisa; Eclipse Automation para escrita) | System Requirements | 12–13 |
| Escolher o tipo de script (plug-in single-file ou binário × executável; leitura × escrita) | Supported Script Types | 18–19 |
| **Unidades e coordenadas** | Coordinate System and Units of Measurement | 20–21 |
| Mapa do modelo de objetos (Patient → Course → PlanSetup → Beam…) | Overview of the Object Model | 22–27 |
| Tornar um script de escrita (`IsWriteable`, `BeginModifications`) | Changing Scripts to Be Write-enabled | 36–37 |
| Criar e alterar estruturas, planos, campos e prescrições | Creating Scripts for Eclipse Automation | 52–55 |
| Calcular dose, otimizar IMRT/VMAT, leaf motion, evaluation dose | Using Calculation Algorithms | 56–60 |
| **Aprovar script para uso clínico** | Chapter 9 | 61–67 |
| Configurar sistema não clínico (pesquisa) | Configuring a Non-Clinical Development System | 64 |
| Exigir aprovação também dos scripts só de leitura | Configure a Clinical System to Require Approval… | 65 |
| Lançar nova versão de script em uso clínico (aposentar a anterior) | Release a New Version… | 65–66 |
| Rastrear todos os planos e structure sets alterados por um script defeituoso | Find All Plans and Structure Sets Changed by a Script | 66–67 |

## O que o manual exige ou recomenda

| O quê | Detalhe | Nível | Fonte |
| --- | --- | --- | --- |
| Unidades | Distâncias e posições em **mm**, no sistema de coordenadas **DICOM**. A interface do Eclipse mostra **cm** no sistema de planejamento (com origem do usuário, orientação de tratamento e definição de eixos) | Especificação do fabricante | [p. 20] |
| Escalas da máquina | Todas as propriedades de unidade de tratamento e acessórios são retornadas na escala **IEC 61217**, seja qual for a escala configurada na máquina | Especificação | [p. 21] |
| Dose | Sempre como `DoseValue`, com unidade **Gy ou cGy conforme a configuração clínica**, ou % se relativa | Especificação | [p. 21] |
| Direitos e rastreio | O plug-in roda com os direitos de quem fez login. O executável registra log HIPAA para cada paciente aberto | Especificação | [p. 21] |
| Aprovação de script com escrita | **Obrigatória** no sistema clínico. Para script só de leitura é opcional, mas pode ser exigida por configuração | Requisito do fabricante | [p. 61, 65] |
| Ciclo de desenvolvimento | Sistema não clínico → "Approved for Evaluation" (usuários com direito específico, por tempo limitado) → "Approved" → "Retired" | Processo do fabricante | [p. 61] |
| Processo do programador | História de usuário e uso pretendido; requisitos testáveis revisados; **análise de risco e perigos** com mitigadores; projeto; revisão de código; controle de versão; testes unitários com cobertura "perto de 100%" | Recomendação (exemplo) | [p. 62] |
| Papel do físico clínico | Plano de comissionamento e validação; **relatório de validação e comissionamento**; avaliação na sombra de casos reais por dois planejadores sênior; aprovação | Recomendação (exemplo) | [p. 62–63] |
| Nova versão | Aposentar a versão em uso antes de aprovar a nova | Procedimento | [p. 65] |
| Rastreabilidade | `PlanSetup.ApplicationScriptLogs` e `StructureSet.ApplicationScriptLogs` permitem achar tudo o que um script alterou. O Plan Approval Wizard mostra nome, versão e data do script que mudou o plano | Funcionalidade | [p. 66–67] |

## Pontos de atenção

- **Unidade e coordenada são a armadilha clássica**: mm × cm e DICOM × planejamento. Todo script que mostra coordenada ao usuário (isocentro, deslocamento de mesa) precisa converter com os métodos da própria API [p. 21]. Isso é teste obrigatório na validação (atividade C10).
- `Gy` × `cGy` depende da configuração clínica [p. 21]. Script que compara dose com constante numérica precisa ler a unidade do `DoseValue`.
- O exemplo de rastreio abre **todos os pacientes** do banco, e o manual recomenda rodar fora do horário [p. 66].
- O processo do capítulo 9 é exemplo do fabricante, não norma. Em norma, a validação de script próprio é **boa prática** (catálogo B06: não foi confirmada obrigação brasileira específica), e o enquadramento como software dispositivo médico segue a RDC 657/2022 (B07). O processo da p. 62 coincide com o ciclo de vida do IEC 62304 e a gestão de risco da ISO 14971 (atividade B08).

## Como se aplica no CLINICA e no ISOCENTRO

- Scripts **com escrita** do serviço que passam por este capítulo: 5 Campos FiF (`programa/scriptsvarian`, ramo `5-campos`), Estruturas-auxiliares (cria anéis de otimização e grava no banco clínico) e PrePlan (cria plano, campos e isocentro). Cada um precisa de: relatório de validação e comissionamento, registro em Script Approvals, avaliação antes do "Approved" e aposentadoria da versão anterior a cada release.
- Scripts **só de leitura**: Proprietário de Tarefas e as consultas do ISOCENTRO. A aprovação é opcional, a menos que o RT Administration exija [p. 65].
- `dominio/qualidade.py` é porte para Python de um plug-in ESAPI (`Plano_Índices_e_Qualidade`) e herda as mesmas convenções de unidade.

## Relações

- Complementa: documentação oficial da ESAPI 15.6 (site local), Image Registration and Segmentation Scripting API, Eclipse Algorithm API 13.7.
- Normas que dão força ao processo: IEC-62304 (ciclo de vida), ISO-14971 (risco), FDA-GPSV-2002 (validação de software), RDC-657 (SaMD), IEC-61217 (escalas).
- Código: `VarianAPIs/Varian-Code-Samples` (exemplos oficiais), `rexcardan/ESAPIX` (extensões), `VarianAPIs/PyESAPI` (ESAPI em Python, só em ambiente de pesquisa, conforme "Python Support in Development / Research Environments" [p. 18]).
