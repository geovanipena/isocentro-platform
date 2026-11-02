---
title: 'Pesquisa de domínio: BI e indicadores para serviços de radioterapia'
type: 'domain'
topic: 'BI (painel de indicadores) para serviço de radioterapia com Varian ARIA — recomendações, literatura e mercado'
decision: 'O que o módulo de BI do ISOCENTRO deve medir e mostrar para seguir as recomendações, aproveitar o que a literatura validou e ocupar uma lacuna de mercado num serviço brasileiro com ARIA'
source: 'run'
status: complete
preset: 'standard'
validation: 'normal'
created: '2026-10-13'
updated: '2026-10-13'
claims_verified: 3
claims_unverified: 7
---

# Pesquisa de domínio: BI e indicadores para serviços de radioterapia

**Decisão que esta pesquisa serve:** o que o módulo de BI do ISOCENTRO deve medir e mostrar para seguir as recomendações internacionais e nacionais, aproveitar o que a literatura já validou e ocupar uma lacuna de mercado num serviço brasileiro com Varian ARIA.

## Resumo executivo

**Recomendação:** construir o BI em torno de um **núcleo regulatório brasileiro** — os seis indicadores que a RDC ANVISA 20/2006 manda a avaliação externa considerar, mais as exigências contínuas da RDC e da norma CNEN/ANSN 6.10 — com **definições operacionais explícitas e auditáveis**, rodando **dentro do serviço** sobre o banco do ARIA. Os indicadores operacionais da literatura (tempo até o início, prolongamento do tempo total, faltas, tempo de acelerador perdido, pendências de física) entram como segunda camada.

O que sustenta essa resposta:

1. **A regulação brasileira já define o "o quê", mas não o "como".** A RDC 20/2006 lista seis indicadores para a avaliação externa (tempo médio do tratamento, abandono, simulação, interrupção, adesão a protocolos, desvio da dose absoluta) sem fórmula nem meta [1][2]; ela e a norma 6.10 exigem também registros contínuos que viram indicador de conformidade — verificação do cálculo até a 3ª aplicação, notificação de evento grave em 24 h, segunda assinatura, revisão médica semanal [1][5]. Nenhum produto encontrado entrega isso.
2. **O maior risco de um BI não é técnico, é de definição.** O único relato publicado de BI sobre ARIA (Zurique, InSightive + Tableau) precisou adaptar a maioria dos mais de 30 painéis do fornecedor, viu as contagens divergirem 7–10% por definição de evento e gastou ~50 pessoa-dias em 10 meses [15]. Um BI que nasce com definições escritas e conferíveis ataca exatamente essa dor.
3. **O mercado deixa um espaço plausível para um produto local e neutro.** O BI da Varian (ARIA CORE Insights, ex-InSightive) é em nuvem, exige ARIA ≥ 15.5 e "não está à venda em todos os mercados" [30][31]; os concorrentes estão presos ao próprio ecossistema (RaySearch, Elekta) [32][34]; não se achou produto brasileiro nem oferta da Varian no Brasil. *Essa lacuna é inferência a partir da ausência de evidência, não um fato confirmado.*

**Maior ressalva:** a vigência da RDC 20/2006 em 2026 não foi confirmada positivamente no DOU — apenas não se achou revogação [1][3]. E não se verificou se um BI gerencial é enquadrado como dispositivo médico (RDC 657/2022), o que pesa na comercialização.

## F1 — Regras do jogo: o que a regulação e as sociedades pedem

**ANVISA — RDC 20/2006 (regulamento técnico de serviços de radioterapia).** O texto mantido pelo Ministério da Saúde não traz nota de revogação ou alteração [1], e a vigilância do RS a lista como legislação atualizada da área [3]. A vigência positiva no DOU de 2025–2026 não foi consultada (**não verificado**). O que ela pede e que vira dado de BI:

- **Item 6.11:** a avaliação externa do item 6.9 (independente, a cada 4 anos [1][4]) deve considerar, no mínimo, seis indicadores: tempo médio do tratamento radioterápico; taxa de abandono; taxa de simulação no total de pacientes tratados; taxa de interrupção; taxa de adesão da equipe médica aos protocolos do serviço; desvio da dose absoluta no ponto de referência [1][2]. **A norma não define fórmula nem meta.** Nuance: o texto vincula os indicadores à avaliação externa, não a um painel contínuo obrigatório — calculá-los continuamente é preparo para a avaliação.
- **Item 7:** eventos adversos graves (tratamento por equívoco, dose ou fracionamento diferente do prescrito, falha de equipamento) devem ser notificados ao SNVS em até 24 h e investigados [1][2].
- **Item 9.7c:** todo cálculo deve ser verificado até a 3ª aplicação ou 10% da dose total [2] (fonte única lida no texto; confiança média).
- **Itens 8.1 e 9.8:** ficha de tratamento, registro diário (UM por campo, fração, dose acumulada), registros de calibração e CQ por toda a vida útil do equipamento [2]. **Item 9.3:** revisão médica semanal [2].
- **Item 5.2.3.1:** equipe mínima proporcional ao volume (3 h de radioterapeuta e de físico por paciente novo/ano) [2][4].

**CNEN/ANSN — norma 6.10.** Aprovada pela Resolução CNEN 176/2014 [5]; a versão consolidada no site oficial se intitula "ANSN 6.10 (Resolução CNEN 277/21)" [6] — a consolidação aparece só nessa fonte (**fonte única**; o PDF não foi lido). Do texto de 2014 (artigos podem ter sido renumerados; **fonte única**): investigação imediata de todo tratamento ou fração diferente do planejado, com relatório ao regulador; segundo sistema de cálculo para verificar o plano; segunda assinatura no plano; consulta médica semanal; auditoria externa dos parâmetros físicos a cada 2 anos no máximo [5].

**Lei 12.732/2012 (60 dias).** Garante o primeiro tratamento no SUS em até 60 dias do laudo; o cumprimento já tem indicador oficial no Painel-Oncologia (DATASUS) e em fichas estaduais (% tratados em até 60 dias) [7][8] — fontes secundárias; o texto da lei no Planalto não foi lido.

**Internacional.**

- **AAPM TG-275 / MPPG 11.a** definem revisão de plano e prontuário em três momentos (inicial, semanal, fim de tratamento), baseada em risco, e pedem automação aos fornecedores [9] (resumos; texto integral não lido).
- **ASTRO "Safety is No Accident"** (atualização de 2019) é um arcabouço de padrões, não de métricas [10]; o **APEx** traduz padrões em "evidence indicators" com revisão por pares [11] (confiança média-baixa).
- **IAEA QUATRO** (2ª ed., 2022) é auditoria multidisciplinar, não lista de KPIs [12].
- **ESGO/ESTRO 2023 (colo do útero)** é o raro conjunto com **metas numéricas**: início da RT ≤ 6 semanas do encaminhamento (ótimo ≥ 90%, mínimo ≥ 75%) e tempo total ≤ 50 dias (≥ 90%), entre 19 indicadores [13].

## F2 — Literatura: o que já foi medido

**Catálogo.** Harden et al. (2022) reúnem 68 indicadores (26 gerais, 42 por sítio) por Donabedian e domínio; os operacionais gerais incluem tratamentos por acelerador, tempo de acelerador perdido, espera até a 1ª fração, atraso/prolongamento, revisão por pares e dose única em metástase óssea — **sem metas numéricas** — e alertam que o registro sim/não (ex.: "revisão por pares feita") não prova qualidade [14].

**BI sobre ARIA — o único relato.** Bovet et al. (Zurique, *Oncology* 2026) implantaram o InSightive (ARIA 15.5, Tableau, 30+ painéis): a maioria precisou de adaptação, alguns foram feitos do zero; "novos pacientes" divergiu 7–10% por definição do evento de registro e o "início de tarefa" até 5% frente ao log; ~50 pessoa-dias em 10 meses de um informata que conhecia o esquema do ARIA. Os autores apontam a nuvem nos EUA como obstáculo fora dos EUA (CLOUD Act) e recomendam partir de KPIs de negócio, governança de dados e elementos padronizados (ASTRO Minimum Data Elements) [15]. É relato de um centro, **sem medida de resultado**.

**Painel com resultado medido (MOSAIQ, não ARIA).** Chen GP et al. (JACMP 2026), rede de 4 sedes, painel próprio por SQL: status do dia por máquina (agendado, fila, finalizado, falta, cancelado, máquina parada), elegibilidade da checagem semanal pela lógica da ASTRO, pendências de física por prazo. Antes/depois de 21 meses: checagens semanais concluídas de 97,7% para 99,9%; captura de cobrança de 96,1% para 99,4%; tempo mediano até **assumir** a tarefa de prontuário ("chart close"/"chart check") na sede de 36,8 para 6,2 min (até **concluir**, de 46,5 para 9,3 min — lido no texto completo pela pesquisadora, não reconferido) [16]. O ganho é do conjunto "físico do dia + painel", não do painel isolado.

**Tempo até o início e prolongamento.** Uma revisão de escopo (31 estudos) propõe métricas padronizadas de percurso — encaminhamento→consulta, consulta→simulação, simulação→início, dias de interrupção, conclusão — estratificadas por equidade; os estudos pré/pós são majoritariamente sem controle [17]. Projetos de melhoria reduziram simulação→início (18→10 dias) e re-simulação (10%→<1%) [21], e consentimento→tratamento (19,5→14,8 dias) [22]; mas melhorar uma etapa nem sempre melhora o indicador de ponta a ponta [23]. Prolongamento do tempo total associa-se a pior sobrevida em sítios distintos — nasofaringe (interrupção ≥ 7 dias, HR 1,37–1,49) [18], colo do útero (> 56 dias, HR 1,33 câncer-específica) [19] — com limiares que variam por sítio. Um modelo preditivo de interrupção teve discriminação modesta (AUC 0,689) [20].

**Incidentes como indicador.** Taxa de notificação normalizada pelo volume (por 1.000 tarefas ou por paciente simulado) é usada como monitor do sistema de aprendizado [25][26]; um checador automático priorizado pelos incidentes locais reduziu erros de planejamento relatados de 16,1% para 4,1% [24].

**Brasil.** Não há artigo revisado por pares sobre BI em serviço de radioterapia. Os dados são populacionais: a radioterapia tem as piores chances de início em 30/60 dias, com forte gradiente regional [27][28]. O único trabalho operacional é uma dissertação da USP que prevê espera e tempo de tratamento com ML sobre registros do HC-FMUSP (só o resumo foi lido) [29].

**Lacuna da literatura:** nenhum estudo de 2019 em diante mediu a ocupação do acelerador antes e depois de implantar um painel.

## F3 — Mercado: o que já existe

| Produto | Empresa | O que mostra (segundo a empresa) | Lê o ARIA? | Entrega | Brasil |
|---|---|---|---|---|---|
| ARIA CORE Insights (ex-InSightive) | Varian / Siemens Healthineers | tempo de tratamento, uso de recursos, volume, intervalos de Care Path, alertas por limiar [30][31] | sim, ARIA ≥ 15.5 [30] | nuvem ("cloud-native") [30] | "não disponível em todos os mercados" [30]; oferta e registro ANVISA não encontrados |
| RayIntelligence | RaySearch | qualidade e benchmark de plano, uso de máquina, aderência a protocolo [32][33] | não confirmado (fontes citam RayStation/RayCare) | nuvem [33] | não verificado |
| MOSAIQ Oncology Analytics | Elekta | painéis customizáveis de desempenho [34] | não (MOSAIQ) | nuvem Elekta Axis (Azure) [34] | não verificado |
| Relatórios nativos + consultas próprias | Varian | relatórios estatísticos e de QA; a Varian ensina físicos a consultar o banco (curso AR205) [35] | sim | local | quem tem ARIA |
| Philips Tasy, MV | — | nenhum painel de radioterapia encontrado | — | — | — |

Nenhum preço público. Confirmação do ARIA CORE Insights vem só do próprio grupo Varian/Siemens. Oncora, LifeLine, MIM e Aspire não foram pesquisados.

**Lacunas (todas inferência, salvo indicação):** (L1) serviço com ARIA local, versão anterior à 15.5 ou restrição a nuvem pode não ter acesso ao BI do fornecedor; (L2) nenhum fornecedor que não a Varian declara ler o ARIA; (L3) nenhum produto encontrado traz indicadores do contexto brasileiro (RDC 20, norma 6.10, prazo da Lei 12.732, SUS/convênio); (L4, com fonte [35]) a concorrência "faça você mesmo" existe e tem aval do fornecedor.

## Glossário (para o PRD)

| Termo | Significado neste contexto |
|---|---|
| Avaliação externa (RDC 20, 6.9) | avaliação independente da qualidade, a cada 4 anos, que usa os seis indicadores do item 6.11 |
| Evento adverso grave (RDC 20, 4.24/7) | tratamento por equívoco, dose ou fracionamento diferente do prescrito, falha de equipamento; notificação em 24 h |
| Exposição médica acidental (norma 6.10) | tratamento ou fração diferente do planejado; investigação imediata e relatório ao regulador |
| Verificação de cálculo (RDC 20, 9.7c; norma 6.10) | conferência independente do cálculo até a 3ª aplicação ou 10% da dose; segundo sistema de cálculo |
| Revisão semanal / checagem semanal de prontuário (WCC) | revisão física periódica do curso (TG-275); elegibilidade pela lógica da ASTRO (frações entregues, BID, interrupções) |
| Tempo total de tratamento / prolongamento | dias da 1ª à última fração; prolongamento = real menos planejado |
| Tempo de acelerador perdido | tempo perdido por parada não programada, reagendamento ou planejado e não iniciado |
| Percurso (pathway intervals) | encaminhamento→consulta→simulação→início |
| Care Path | fluxo de tarefas do ARIA; seus intervalos são KPI no ARIA CORE Insights |
| Taxa de notificação normalizada | incidentes por 1.000 tarefas ou por paciente simulado; mede a cultura de notificação, não a segurança |
| Painel-Oncologia | indicador oficial do DATASUS para o prazo de 60 dias |

## Insights entre frentes

1. **Regulação + literatura → o diferencial é a definição.** A RDC nomeia os indicadores sem defini-los [1]; a literatura mostra que definição é onde o BI falha (7–10% de divergência) [15]. Um BI com ficha técnica de cada indicador (fórmula, fonte no ARIA, exclusões) resolve as duas pontas de uma vez — e é o que um avaliador externo pediria.
2. **Mercado + literatura → local não é detalhe.** O BI do fornecedor é em nuvem [30], e o único usuário publicado aponta a nuvem nos EUA como obstáculo fora dos EUA [15]. Um produto que roda na rede do serviço tem argumento próprio (a ligação com a LGPD é inferência, não pesquisada).
3. **Literatura + regulação → BI e revisão semanal são o mesmo dado.** O painel com resultado medido [16] gira em torno da checagem semanal — a mesma revisão que TG-275 recomenda [9] e que RDC/norma 6.10 exigem como revisão médica semanal e verificação de cálculo [2][5]. Os indicadores de conformidade (% de cursos com checagem no prazo) saem de graça do módulo de revisão.
4. **O prazo de 60 dias tem indicador oficial, mas populacional** [7][27]. Não se achou ferramenta que o meça por serviço — oportunidade para a camada de percurso.

## Recomendações

| # | Recomendação | Alimenta | Base de confiança |
|---|---|---|---|
| R1 | Núcleo do BI = os seis indicadores do item 6.11 da RDC 20/2006, cada um com ficha técnica (fórmula, fonte no ARIA, exclusões, data do dado) | brief: problema e diferencial; PRD: requisitos | alta para o texto da norma [1][2]; vigência em 2026 não confirmada no DOU |
| R2 | Camada de conformidade contínua: cálculo verificado até a 3ª aplicação [2], evento grave notificado em 24 h [1], segunda assinatura e consulta médica semanal [5], revisão física semanal (recomendação TG-275, não exigência brasileira) [9] | PRD: requisitos; ligação com o módulo Revisão Semanal | média — 9.7c e norma 6.10 com fonte única no texto [2][5]; TG-275 só por resumo [9] |
| R3 | Camada operacional da literatura: percurso (consulta→simulação→início), tempo total e prolongamento, faltas, tempo de acelerador perdido, pendências de física — sem metas importadas; metas do próprio serviço, e ESGO/ESTRO onde houver (colo) | PRD; brief: usuários (gestor, físico) | média — estudos pré/pós sem controle [17][21][22]; associação clínica do prolongamento com 2+ fontes [18][19] |
| R4 | Rodar local sobre o banco do ARIA, sem nuvem; mostrar a fonte e a data de cada número | arquitetura: restrição | média — nuvem do fornecedor confirmada só pelo fornecedor [30]; obstáculo relatado por um centro [15] |
| R5 | Não prometer ganho de ocupação do acelerador como resultado do painel | brief: escopo e promessas | alta pela ausência na literatura (nenhum estudo mediu) |
| R6 | Antes de vender, verificar o enquadramento de software gerencial na RDC 657/2022 e a vigência da RDC 20/2006 | brief: riscos | — (não pesquisado) |

## Perguntas abertas

1. **A RDC 20/2006 está vigente em 2026?** Consultar o DOU/estoque regulatório da ANVISA ou a vigilância sanitária local.
2. **Como operacionalizar os seis indicadores** (ex.: "tempo médio do tratamento" = dias da 1ª à última fração? "abandono" = curso não concluído?) — decisão do físico responsável, idealmente alinhada com a vigilância que faz a avaliação externa.
3. **Um BI gerencial é dispositivo médico pela RDC 657/2022?** Pesquisa regulatória própria.
4. **Que versão do ARIA os serviços brasileiros usam** e se a Siemens Healthineers oferece o ARIA CORE Insights no Brasil — contato comercial ou consulta ao portal da ANVISA.
5. **Concorrentes não cobertos** (Oncora, LifeLine, MIM, Aspire) e a prática "faça você mesmo" com Power BI no Brasil (vagas, fóruns) — rodada de aprofundamento.
6. **Texto integral do TG-275 e da norma 6.10 consolidada** — para os itens exatos da revisão semanal.

## Fontes

| # | Afirmação que sustenta | Publicador | Publicação | Acesso | Confiança |
|---|---|---|---|---|---|
| [1] | RDC 20/2006: texto oficial sem nota de revogação; item 6.11; item 7.2; avaliação externa | [Ministério da Saúde — Saúde Legis](https://bvsms.saude.gov.br/bvs/saudelegis/anvisa/2006/rdc0020_02_02_2006.html) | 2006-02 | 2026-10-13 | alta (texto); média (vigência) |
| [2] | RDC 20/2006: texto literal de 6.11, 7.1–7.3, 8.1, 9.7c, 5.2.3.1 | [NormasBrasil](https://www.normasbrasil.com.br/norma/resolucao-20-2006_104087.html) | 2006-02 | 2026-10-13 | alta (6.11, com [1]); média (demais itens) |
| [3] | RDC 20/2006 listada como legislação atualizada de radiações | [CEVS-SES/RS](https://www.cevs.rs.gov.br/legislacao-sanitaria-atualizada-area-de-radiacoes) | sem data | 2026-10-13 | média |
| [4] | Avaliação externa a cada 4 anos e equipe mínima | [CFM](https://portal.cfm.org.br/noticias/anvisa-publica-novas-regras-para-o-controle-sanitario-de-servicos-de-radioterapia/) | 2006 | 2026-10-13 | alta |
| [5] | Norma CNEN 6.10 (Res. 176/2014): art. 26 investigação, 15 XI e 2º cálculo, 17 IV 2ª assinatura, 17 VIII consulta semanal, 36 auditoria ≤ 2 anos | [Legisweb](https://www.legisweb.com.br/legislacao/?id=278385) | 2014-12 | 2026-10-13 | média (texto de 2014; artigos conferidos pelo verificador) |
| [6] | Versão consolidada "ANSN 6.10 (Res. CNEN 277/21)" | [CNEN/ANSN — gov.br](https://www.gov.br/cnen/pt-br/acesso-rapido/normas/grupo-6/grupo6-nrm610.pdf) | 2021-08 | 2026-10-13 | alta (título/histórico) |
| [7] | Lei 12.732: indicador "% tratados em até 60 dias"; Painel-Oncologia | [SESA-ES — ficha de indicador](https://saude.es.gov.br/Media/sesa/Planejamento/ficha_de_qualificacao/Meta%201.4.2.pdf) | 2021 | 2026-10-13 | média |
| [8] | Lei 12.732 e intervalo diagnóstico→tratamento no Brasil | [Cadernos de Saúde Pública](https://doaj.org/article/f70a69eaa5564756be334aabe6fd9d6c) | 2021 | 2026-10-13 | média |
| [9] | TG-275 / MPPG 11.a: revisão inicial, semanal e final baseada em risco | [AAPM — Report 275](https://www.aapm.org/pubs/reports/detail.asp?docid=198) | 2020 | 2026-10-13 | média |
| [10] | "Safety is No Accident", atualização 2019; arcabouço, não métricas | [ASTRO](https://astro.org/safetyisnoaccident) | 2019-03 | 2026-10-13 | média |
| [11] | APEx: pilares, padrões e evidence indicators | [ASTRO — APEx](https://www.astro.org/practice-support/accreditation/about-apex) | sem data | 2026-10-13 | média-baixa |
| [12] | QUATRO 2ª ed.: auditoria multidisciplinar | [IAEA](https://www-pub.iaea.org/MTCD/Publications/PDF/PUB1990_web.pdf) | 2022 | 2026-10-13 | média |
| [13] | ESGO/ESTRO 2023: 19 indicadores para colo, com metas | [Chargari et al., Int J Gynecol Cancer (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC10313976/) | 2023 | 2026-10-13 | alta |
| [14] | Catálogo de 68 indicadores; operacionais sem meta | [Harden et al., J Med Imaging Radiat Oncol (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC9310822/) | 2022-03 | 2026-10-13 | alta |
| [15] | InSightive sobre ARIA em Zurique: adaptação, divergência 7–10%, ~50 pessoa-dias, nuvem/CLOUD Act | [Bovet et al., Oncology (Karger)](https://doi.org/10.1159/000549896) | 2025-12 | 2026-10-13 | média (fonte única; números lidos no texto completo pela pesquisadora, o verificador só alcançou o resumo) |
| [16] | Painel próprio MOSAIQ: telas; WCC 97,7→99,9%; claim 36,8→6,2 min; conclusão 46,5→9,3 min | [Chen GP et al., JACMP (Wiley/AAPM)](https://doi.org/10.1002/acm2.70792) | 2026-09 | 2026-10-13 | alta (fonte única, texto completo) |
| [17] | Revisão de escopo: métricas de percurso; estudos pré/pós | [Chen D et al., Front Oncol](https://doi.org/10.3389/fonc.2026.1786405) | 2026-06 | 2026-10-13 | média |
| [18] | Interrupção ≥ 7 dias e pior sobrevida (nasofaringe) | [Yao et al., Radiother Oncol](https://doi.org/10.1016/j.radonc.2018.10.018) | 2019 | 2026-10-13 | média |
| [19] | Tempo total > 56 dias e pior sobrevida (colo, Taiwan) | [Oncotarget (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC5689603/) | 2017 | 2026-10-13 | média |
| [20] | Predição de interrupção: 24,6% interromperam; AUC 0,689 | [Zink et al., ESMO Real World Data and Digital Oncology](https://doi.org/10.1016/j.esmorw.2026.100771) | 2026 | 2026-10-13 | média |
| [21] | Simulação→início 18→10 dias; re-simulação 10%→<1% | [Thakur et al., ecancermedicalscience](https://doi.org/10.3332/ecancer.2026.2116) | 2026 | 2026-10-13 | média |
| [22] | Consentimento→tratamento 19,5→14,8 dias | [Etheridge et al., BMJ Open Quality](https://doi.org/10.1136/bmjoq-2025-004056) | 2026 | 2026-10-13 | média |
| [23] | Melhorar uma etapa sem melhorar a espera de ponta a ponta | [Rowsell et al., Pract Radiat Oncol](https://doi.org/10.1016/j.prro.2026.08.009) | 2026 | 2026-10-13 | média |
| [24] | Checador automático priorizado por incidentes: erros 16,1%→4,1% | [Liu et al., JACMP](https://doi.org/10.1002/acm2.12678) | 2019 | 2026-10-13 | média |
| [25] | Notificação por 1.000 tarefas como monitor | [Jacqmin & Crosby, JACMP](https://doi.org/10.1002/acm2.13653) | 2022 | 2026-10-13 | média |
| [26] | Notificação por paciente simulado como monitor | [Steele et al., Tech Innov Patient Support Radiat Oncol](https://doi.org/10.1016/j.tipsro.2026.100397) | 2026 | 2026-10-13 | média |
| [27] | Brasil: radioterapia com piores chances de início em 30 dias; gradiente regional | [Abreu et al., Rev Saúde Pública](https://doi.org/10.11606/s1518-8787.2026060006943) | 2026 | 2026-10-13 | média |
| [28] | Brasil: radioterapia majoritariamente após 60 dias no melanoma (Norte) | [Nogueira et al., Epidemiol Serv Saúde](https://doi.org/10.1590/s2237-96222026v35e20250025.en) | 2026 | 2026-10-13 | média |
| [29] | Dissertação USP: ML para espera e tempo de tratamento no HC-FMUSP | [Emiliozzi, USP/IPEN](https://doi.org/10.11606/D.85.2023.tde-12072023-120018) | 2023-04 | 2026-10-13 | média (só resumo) |
| [30] | ARIA CORE Insights: nuvem, ARIA ≥ 15.5, KPIs, "not available for sale in all markets" | [Siemens Healthineers](https://cancercare.siemens-healthineers.com/products/software/analytics/aria-core-insights) | 2026 | 2026-10-13 | média (fornecedor) |
| [31] | Renomeação InSightive → ARIA CORE Insights | [Varian](https://www.varian.com/en-gb/products/software/analytics/insightive) | 2026 | 2026-10-13 | média (mesmo grupo de [30]) |
| [32] | RayIntelligence: painéis; não nomeia ARIA/MOSAIQ | [RaySearch](https://www.raysearchlabs.com/rayintelligence/) | 2026 | 2026-10-13 | média (fornecedor) |
| [33] | RayIntelligence v2025: em nuvem, integração RayStation/RayCare | [Applied Radiation Oncology](https://www.appliedradiationoncology.com/articles/raysearch-launches-rayintelligence-v2025-to-advance-oncology-data-analytics) | 2025-09 | 2026-10-13 | média |
| [34] | MOSAIQ Oncology Analytics: nuvem Elekta Axis (Azure), integrado ao MOSAIQ | [Elekta](https://elekta.com/software-solutions/knowledge-management/mosaiq-oncology-analytics) | 2026 | 2026-10-13 | média (fornecedor) |
| [35] | Curso AR205: Varian ensina físicos a consultar o banco do ARIA | [Varian](https://www.varian.com/en-gb/ar205-reporting-aria-radiation-oncology-0) | sem data | 2026-10-13 | média (trecho de busca) |

## Mapa de envelhecimento

Calculado pelo `recon_kit.py staleness` (janelas: regulatório 6 meses, adoção de tecnologia 18, panorama de fornecedores 18, literatura 36).

| Afirmação | Classe | Reconferir em |
|---|---|---|
| [7] Painel-Oncologia mede o prazo de 60 dias | regulatório | **já vencida** (fontes de 2021) — reconferir no DATASUS antes de usar |
| [18][19] Prolongamento do tempo total e pior sobrevida | literatura | **já vencida pela janela** (2017–2019) — é evidência clínica, envelhece devagar; vale buscar meta-análise recente |
| [1][2][3][5] RDC 20/2006 e norma 6.10 (texto e vigência) | regulatório | 2027-04 |
| [15] BI sobre ARIA: divergência por definição | adoção de tecnologia | 2027-06 |
| [30]–[34] Panorama de fornecedores | panorama | 2028-04 |
| [16] Painel MOSAIQ com resultado medido | literatura | 2029-09 |

A reconferência mais urgente é a [7]; depois, a vigência da RDC 20/2006 (abril de 2027, ou antes de qualquer material de venda).

## Insumos para o product brief

_Seção para o `bmad-product-brief` consumir direto, sem reprocessar a pesquisa._

- **Problema:** serviços de radioterapia brasileiros precisam apresentar, na avaliação externa, seis indicadores que a RDC 20/2006 nomeia sem definir [1][2], e cumprir exigências contínuas (verificação de cálculo, notificação em 24 h, revisão semanal) [2][5] — sem ferramenta que calcule isso a partir do ARIA. Quem tenta com BI genérico esbarra na definição dos indicadores [15].
- **Usuários:** físico médico responsável (conformidade e revisão), gestor/responsável técnico (avaliação externa, ocupação, prazo de 60 dias), radioterapeuta (revisão semanal, percurso do paciente).
- **Diferencial:** indicadores regulatórios brasileiros com ficha técnica auditável; roda local sobre o ARIA, sem nuvem; mostra fonte e data de cada número; reaproveita o dado do módulo de Revisão Semanal.
- **Concorrência:** ARIA CORE Insights (nuvem, ARIA ≥ 15.5, oferta no Brasil não encontrada) [30]; concorrentes presos a outro ecossistema [32][34]; relatórios próprios com consultas ao banco [35].
- **Restrições:** leitura somente do ARIA; vigência da RDC 20/2006 a confirmar; enquadramento ANVISA de software a verificar; não prometer ganho de ocupação [R5].
- **Vocabulário:** ver o Glossário acima.
