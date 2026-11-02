---
title: 'Addendum: ISOCENTRO — detalhe para PRD e arquitetura'
created: '2026-10-13'
updated: '2026-10-16'
---

# Addendum do brief ISOCENTRO

> Desde 16/10/2026 o produto se chama ISOCENTRO (o nome SGQ-RT acabou) e se organiza em módulos. A fonte de verdade de normas, tolerâncias e atividades passou a ser a base de conhecimento (`Documents/isocentro/conhecimento/`); as referências `[n]` abaixo continuam valendo para os números de literatura.

Detalhe do brief técnico v0.5 que pertence ao PRD ou à arquitetura, já com
as correções da pesquisa verificada
(`../research-sgq-rt-referencias-2026-10-13/research.md`). Os números entre
colchetes `[n]` remetem ao apêndice de fontes de lá.

## Os quatro gatilhos

| Gatilho | Disparo | Domínio | Fonte |
| --- | --- | --- | --- |
| evento | plano aprovado, curso alterado | plan check | TG-275 [3], MPPG 11.a [8] |
| calendário | diário, semanal, mensal, semestral, anual, bienal | QA de máquina, auditoria espelhada | CNEN NN 6.10 arts. 35–36 [14], RDC 20/2006 item 6.9 [15]; TG-142 e MPPG-8b conferidos na base (fichas `TG-142`, `MPPG-8b`); itens em `matriz/programa-cq.csv` |
| prazo | vencimento se aproxima | conformidade e PPR | CNEN NN 6.10 [14] |
| estado | objeto parado além do limite | fluxo clínico | ASTRO *Safety is No Accident* (não verificado) |

## Onde os projetos atuais entram (por módulo)

| Hoje | Módulo do ISOCENTRO | Papel | Mudança |
| --- | --- | --- | --- |
| ISOCENTRO (PyQt5): Ficha, Capa, Agenda, Ficha Virtual | Tratamento; shell | Interface única e leitura do `variandw` | O tema e os widgets viram o design system (QSS) |
| `dominio/paralelo.py` (porte do `parallel-mu-check`) | Plano | **Avaliador da segunda checagem** (MVP 1) | Tabelas reais das cinco máquinas; limites do TG-219/TG-114; comissionamento do próprio cálculo |
| `dominio/qualidade.py`, checklist pré-tratamento | Plano | Base da **revisão com segunda assinatura** (MVP 2) | Lista "++" do TG-275; assinatura registrada |
| `scriptsvarian` (constraints, 5 Campos FiF, Proprietário de Tarefas), `preplan`, `Estruturas-auxiliares_API` | Plano; Software e sistemas | Avaliadores ESAPI (contrato JSON) e scripts com escrita | Ciclo ISQM e aprovação de script no Eclipse (B06) |
| `srs-streamlit` (SRS Analysis: avaliação dosimétrica de radiocirurgia) | Plano (I02, C07) | Avaliador de planos de SRS | Porte para o motor |
| `ppr-streamlit` (PPR, vencimentos; programa de CQ no ramo `programa-cq-tg142`) | Documentação e conformidade; Garantia da Qualidade | **Vencimentos** (MVP 5) e programa de CQ (MVP 3) | Vencimentos pelo gatilho de prazo; extração de ASO local (R-15) |
| Spec de incidentes v0.1 | Segurança do paciente | **Incidentes** (MVP 4) | Citar a NN-6.10 pela Res. 277/2021 consolidada (a spec cita "Rev. 2017") e acrescentar o art. 26 (30 dias; aviso escrito ao paciente) |
| Radioteradados (PRD e arquitetura) | Indicadores | Absorvido, não refeito | — |
| `iort-streamlit` | — | **Fora** (IORT fora do projeto) | — |
| SSRS / RDL | (canal de entrega, todos os módulos) | Relatórios | A lógica sai do custom code e vai para o motor |
| Base de conhecimento e mapa | Conhecimento | Proveniência de cada regra | `matriz/vinculos.csv` vira dado do ISOCENTRO |

O v0.5 punha o INTRABEAM / IORT como domínio da Fase 6. Em 13/10/2026 o
usuário tirou a IORT do projeto.

## Reaproveitamento de código externo (`codigo-externo/`, 61 repositórios)

| Módulo | Repositório | Para quê | Cuidado (B10) |
| --- | --- | --- | --- |
| Garantia da Qualidade | `jrkerns/pylinac` | Picket fence, Winston-Lutz, starshot, CBCT, planura e simetria, logs de entrega | **kQ do TRS-398 de 2000** e sem FC65-G/P: passar o kQ da Rev. 1 |
| Garantia da Qualidade | `qatrackplus/qatrackplus` | Modelo de dados (lista de testes, instância, tolerância, ação, frequência) | Só o modelo; o sistema completo fica fora |
| Plano | `pymedphys/pymedphys` | Gama 2D/3D, MU density | API beta: validar contra casos conferidos |
| Plano | `LDClark/PlanCheck`, `jsfrench/uhg-plancheck`, `MAAS-PlanScoreCard` | Regras de plan check em ESAPI | Licença e versão da ESAPI (15.6) |
| Plano | TG263-Toolkit, TG263ComplianceTool, `tg263` | Nomenclatura (C03, I06) | — |
| Plano | VarianESAPI-EQD2Converter, BED_Calc, RadComp | BED/EQD2 e reirradiação (H03, I03) | BED_Calc sem licença |
| Plano / Tratamento | `pydicom`, `pynetdicom`, `dicompyler-core` | DICOM-RT (C11) | Já em uso |
| Segurança do paciente / Software | `pydicom/deid`, dicognito | Pseudonimização (G18) | — |
| Indicadores | DVH-Analytics, EclipseDataMiner | Mineração de dose e indicadores | — |

## Esboço do objeto Verificação (v0.5, ajustado)

```json
{
  "id": "VER_PRESC_FRACOES", "versao": "1.0.0",
  "gatilho": { "tipo": "evento", "evento": "plano.aprovado_medico" },
  "proveniencia": {
    "fontes": ["TG-275 Tab.S1.B.iii", "MPPG 11.a §3.2"],
    "rpn_referencia": 168, "rpn_local": null
  },
  "severidade": "alta",          // alta | atencao | informativo — nunca bloqueia
  "avaliador": "esapi:PrescFracoes",
  "estado": "sombra",            // sombra | ativa | podada
  "cep": null
}
// execução
{ "resultado": "conforme",       // nao_conforme | nao_aplicavel | indeterminado | erro
  "origem": "producao",          // producao | semeado
  "escore_anomalia": null,       // ordena a fila, nunca alarma
  "prazo": { "data_realizacao": null, "data_vencimento": null } }
```

- **`"bloqueante"` virou `"alta"`.** O usuário decidiu em 13/10/2026 que o
  motor é só advisory. O nome definitivo do nível fica para o PRD.
- **A verificação sem proveniência é rejeitada pelo esquema.**
- **Log append-only encadeado, com retenção de pelo menos 10 anos após o
  descarte do software.** É o §3º do art. 5º da RDC 657 [11]. O §4º pede a
  capacidade de discernir registro inválido ou alterado, o que justifica o
  encadeamento por hash.
- **Integridade da transferência de dados:** ponta-a-ponta e checksum pelo
  TG-201, citando a comunicação de 2010 [13] até que o texto completo de 2021
  seja lido.

## As fases (v0.5): superadas pelo MVP de 16/10/2026

O faseamento abaixo previa a v1 nas Fases 0–2, sem tocar decisão de dose. Em 16/10/2026 o usuário escolheu um MVP de cinco itens que traz para a frente parte da Fase 3 (segunda checagem e revisão do plano) e da Fase 4 (programa de CQ), por serem obrigação legal sem processo no serviço. A tabela fica como referência dos critérios de aceite, que continuam válidos.

| Fase | Conteúdo | Aceite |
| --- | --- | --- |
| 0 Núcleo | domínio, contrato, log, CEP, vocabulário TG-263 | regra-piloto ponta a ponta sem o núcleo conhecer radioterapia |
| 1 Shell | padronização visual como design system | duas telas distintas, zero estilo duplicado |
| 2 Vencimentos | PPR pelo gatilho de prazo | item vence e alerta sem código específico de PPR |
| 3 Plan check | ~20 regras de maior RPN do TG-275, sombra por 30 dias | < 30 s/plano · FP < 1/plano · sensibilidade semeada > 0,85 |
| 4 Calendário | NN 6.10, TG-142, auditoria espelhada (GT 2302) | desvio detectado por tendência antes de estourar a tolerância |
| 5 Fluxo e indicadores | aging por estado, TC→1ª sessão (mediana e P90), índice mensal | índice publicado 3 meses seguidos sem intervenção manual |
| 6 Braquiterapia e estatística | braquiterapia no mesmo modelo; escore de anomalia ordenando a fila | ordenação reduz o tempo até achar o plano problemático |

## Base das cinco inovações

| Inovação | Apoio verificado | Ressalva |
| --- | --- | --- |
| Modo sombra | TG-275 [3] (erro despercebido); Stuhr 2022 [6] (falso negativo por nomenclatura) | "inédita em QA de RT" é afirmação do autor, sem busca de anterioridade |
| Erro semeado | TG-201 ponta-a-ponta [13]; TG-100 (FMEA, não verificado); RDC 657 §4º [11] | idem |
| Auditoria espelhada | NN 6.10 art. 36 [14]; GT 2302 [18]; PQRT/INCA [16]; Guia CNEN [19] | "nenhuma ferramenta faz isso" não foi pesquisado |
| Índice de segurança | ASTRO SiNA, ICRP 112, OMS e AIEA SRS 17 (não verificados nesta pesquisa) | a fórmula é proposta do autor |
| Biblioteca citável | TG-263, CodeX (não verificados) | publicar a biblioteca, não o software (RDC 657 §1º) |

## Números de apoio (redação corrigida)

- **Liu et al. 2019 (Stanford, ESAPI + Six Sigma) [5]:**
  - erro de planejamento de 16,1% para 4,1%;
  - RPN médio de 129,2 para 83,7;
  - divergência prescrição/plano −82,7%;
  - instrução de shift −84,4%;
  - o nível sigma subiu (4σ para 5σ) **só** no shift de isocentro;
  - plan check de 21,7 para 11,1 min.
- **Berry et al. 2020 (MSKCC) [7]:** tempo de chart check −20%, e "quase
  meio FTE" como estimativa dos autores.
- **Stuhr et al. 2022 (MSKCC) [6]:** 11 checagens em 1169 planos por cerca de
  3 anos, com melhora sustentada. Sem medida de tempo.
- **Xu et al. 2021 [4]:**
  - tempo de −44% a −98% nos níveis altos de automação;
  - erro residual de −15% a −85%;
  - os 69 itens "não totalmente automatizáveis" do TG-275 foram reavaliados,
    e nem todos mudaram.
- **Huang et al. 2023 [9]:** autoencoder em 576 planos de mama, AUC 0,9985,
  recall 100%, precisão 0,51. É um grupo só, com 19 positivos: serve como
  viabilidade, não como meta.

## Decisões pendentes (do v0.5)

- **Stack:** decidida em 13/10/2026. Python, com ESAPI na fronteira.
- **Banco do log:** PostgreSQL (precisa de servidor; ver R-08) ou SQLite
  local.
- **Hospedagem:** servidor da clínica, máquina dedicada ou o servidor de
  relatórios.
- **Piloto do plan check:** mama (volume e protocolo definidos) ou próstata.
- **Trava da segunda assinatura:** proposta de 16/10/2026 é a aprovação do plano no ARIA (o ISOCENTRO registra, não bloqueia) — a confirmar.
- **Ambição regulatória:** uso interno permanente ou dossiê para registro.
  Liga com a classe ANVISA.

## Detalhe do MVP (16/10/2026)

| Item | Atividades da base | Entrada de dados | Aceite proposto |
| --- | --- | --- | --- |
| 1. Segunda checagem | C05, H01, B10 | RT Plan (DICOM); tabelas TMR/Scp por máquina e energia (`comissionamento/` → `dados_feixe/`, com validação na conversão) | Pontos da Tab. 8 do TG-219 e casos TG-119 medidos × calculados por máquina; limite de ação do TG-219 no composto (3% homogêneo / 5% heterogêneo); planos sem tabela marcados "indeterminado" |
| 2. Revisão com 2ª assinatura | C01, C04, C09, D03 | RT Plan, `variandw` (prescrição, plano, campos), checklist | Itens "++" do TG-275 com automação F checados sem intervenção; assinatura e data registradas; casos de alto risco sinalizados antes da 1ª fração |
| 3. Programa de CQ | A01–A20, E03, E06 | `programa-cq.csv` / `qualidade.json`; exportações do DailyQA 3 e do MapCHECK; pylinac | Cada teste com execução, tolerância e ação; falha visível no mesmo dia; carta de controle do output diário |
| 4. Incidentes | F08, G04, G05, G15 | Formulário próprio + contexto do ARIA (somente leitura) | Prazo de 30 dias contado; aviso ao paciente registrado; Epimed continua o canal oficial |
| 5. Vencimentos | A04, A05, A11, A12, E02, F04–F07, F13, G02 | Cadastro de instrumentos, fontes, certificados, treinamentos | Nada vence sem aviso prévio configurável |

Pendências do serviço que afetam o MVP (`conhecimento/PENDENCIAS.md`): a CEL não tem câmara de 0,03 cm³ ou menos para SRS e a BET não tem câmara menor que 0,1 cm³ para IMRT (NN-6.10 art. 51); dispositivo de QA da DUO não declarado; N_D,w × ICRU 90; FFF e SRS fora do PPR.

## Casos de incidente que motivam o MVP

| Caso (acervo, pasta 11) | Padrão de falha | Onde o ISOCENTRO cobre |
| --- | --- | --- |
| Panamá (IAEA) | Blocos de proteção digitados no TPS de um jeito que ele calculava errado, sem verificação independente | MVP 1 e 2 |
| Glasgow 2006 | Upgrade para o Varis 7 mudou a transferência de dados ao formulário de planejamento | MVP 2; módulo Software e sistemas (B03) |
| Épinal (IRSN) | Inconsistência entre o plano e o modo de filtro | MVP 2 |
| Costa Rica (IAEA) | Erro de calibração de Co-60 | MVP 3 |
| Białystok (IAEA) | Falha de alimentação elétrica do acelerador não detectada | MVP 3 |
| Toulouse (IGAS) | Erro de medida na configuração do TPS para radiocirurgia | Módulo Plano, comissionamento (B01, B02), depois do MVP |
