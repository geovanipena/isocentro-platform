---
title: 'Product Brief: Radioteradados — o painel de indicadores do ISOCENTRO'
status: final
created: '2026-10-13'
updated: '2026-10-13'
inputs:
  - '../research-bi-radioterapia-indicadores-2026-10-13/research.md'
  - '../../brainstorm-funcionalidades-radioteraficha-2026-10-13/.memlog.md'
---

# Product Brief: Radioteradados

## Resumo

O **Radioteradados** é uma aba nova do ISOCENTRO que calcula, a partir do banco do Varian ARIA, os indicadores que um serviço de radioterapia precisa acompanhar e apresentar. Primeiro, os que a regulação brasileira pede; depois, os operacionais que a literatura usa.

A RDC ANVISA 20/2006 manda a avaliação externa considerar seis indicadores (tempo médio do tratamento, abandono, simulação, interrupção, adesão a protocolos e desvio de dose), mas não define como calculá-los. Hoje esses números saem de planilha montada à mão, quando saem. O Radioteradados faz essa conta todo mês sem trabalho manual, mostra a definição de cada número e deixa conferir os pacientes por trás dele.

Nasce para o serviço do próprio autor. Se funcionar, é a base de um produto para outros serviços com ARIA no Brasil, mercado em que a pesquisa não encontrou oferta equivalente.

## O problema

- **A regulação diz o quê, mas não o como.** Os seis indicadores do item 6.11 da RDC 20/2006 não têm fórmula nem meta. Cada serviço inventa a sua definição, e o número muda conforme quem faz a conta.
- **O dado existe, mas está espalhado.** Sessões, cursos, agenda, prescrições e diagnósticos estão no ARIA. Juntá-los exige consulta ao banco ou planilha, e isso fica com o físico, fora do horário.
- **BI genérico tropeça na definição.** O único relato publicado de BI sobre o ARIA, em Zurique, precisou adaptar a maioria dos painéis do fornecedor: as contagens divergiram de 7 a 10% por diferença de definição, e o trabalho consumiu cerca de 50 pessoa-dias.
- **O BI do fornecedor não serve a este serviço.** O ARIA CORE Insights roda só em nuvem, exige ARIA 15.5 ou superior e não tem oferta encontrada no Brasil.

## A solução

Uma aba do ISOCENTRO, ao lado da Agenda e da Ficha Virtual, que lê o mesmo banco que o app já consulta:

- **Núcleo regulatório.** Os indicadores da RDC 20/2006 que saem do banco: tempo médio do tratamento, abandono, interrupção e, se a TC de simulação estiver registrada como atividade, simulação.
- **Camada operacional.** Pacientes novos, cursos iniciados, sessões por máquina, tempo total e prolongamento, faltas, percurso da consulta ao início, e mix por convênio, sítio, diagnóstico e intenção.
- **Cada número com a sua ficha técnica:** fórmula, o que entra, o que sai e a data do dado. Um clique abre a lista de pacientes por trás do número.
- **Período e filtros:** mês atual, mês anterior e 12 meses, por máquina, médico, sítio e convênio. O radioterapeuta vê "só os meus".
- **PDF mensal** para arquivo e para a avaliação externa.
- **Faixa EXPERIMENTAL** até os números serem conferidos contra o ARIA num período de teste, como no painel da Ficha Virtual.

## Para quem

- **Físico médico responsável** (o autor): fecha o mês, prepara a avaliação externa e confere a conformidade sem montar planilha.
- **Gestão / responsável técnico:** acompanha volume, ocupação, convênios e a tendência dos indicadores.
- **Médicos radioterapeutas:** veem os próprios pacientes (interrupção, tempo total, percurso).

## O que o torna diferente

- **Indicadores da regulação brasileira com definição escrita e aprovada pelo físico responsável.** Nenhum produto encontrado oferece isso.
- **Roda no próprio serviço**, sem nuvem, sobre o banco que o ISOCENTRO já lê. Não depende da versão do ARIA exigida pelo fornecedor.
- **Conferível:** todo número mostra de onde veio e quem está por trás dele.
- **Vantagem honesta:** quem escreve é um físico médico, que conhece as tabelas do ARIA e a rotina do serviço. Não há barreira técnica além disso e da velocidade de execução.

## Como saber que deu certo

- Os indicadores da RDC que saem do banco são calculados **todo mês, sem trabalho manual**.
- Numa **conferência por amostragem contra o ARIA**, os números batem e a faixa EXPERIMENTAL pode sair.
- O físico **deixa de montar planilha** para a chefia.
- `[SUPOSIÇÃO]` O PDF mensal é aceito como material da próxima avaliação externa.

## Escopo da v1

**Entra** (apenas com dados do servidor, o banco do ARIA): o núcleo regulatório e a camada operacional acima, as fichas técnicas, a lista de pacientes por número, os filtros, o PDF mensal e a faixa EXPERIMENTAL.

**Fica de fora:**

- desvio da dose absoluta (é medida de controle de qualidade, fora do ARIA);
- adesão a protocolos (exige o protocolo do serviço em forma comparável);
- incidentes e notificações;
- metas do serviço (vêm depois; na v1 só a meta ESGO/ESTRO para colo do útero);
- previsão de demanda;
- comparação entre serviços;
- qualquer escrita no ARIA.

## Riscos e o que ainda não se sabe

- **Definições.** A primeira versão de cada fórmula é proposta e precisa da aprovação do físico. No BI de Zurique, a maioria dos painéis precisou de adaptação, e alinhar as definições ao entendimento clínico foi um dos motivos.
- **Mapeamento do banco.** Simulação, revisão semanal e tempo de acelerador perdido dependem de como o serviço registra essas atividades no ARIA. A atividade de parada ainda nem existe.
- **Portão R-07.** A conferência dos cursos contra o ARIA, pendente no ISOCENTRO, é a mesma que libera este painel.
- **Vigência da RDC 20/2006 em 2026** não foi confirmada no Diário Oficial; apenas não se encontrou revogação.
- **Para vender:** o enquadramento do software pela ANVISA (RDC 657/2022) não verificado; capa e nomes do serviço ainda estão fixos no código.

## Visão

Se a v1 provar que os números batem e poupam trabalho, o Radioteradados ganha:

- as metas do serviço e os indicadores que hoje ficam fora, com lançamento manual do controle de qualidade;
- a ligação com o módulo de Revisão Semanal, que compartilha o mesmo dado;
- o prazo de 60 dias por serviço, que hoje só existe em nível populacional.

Em 2 a 3 anos, é o painel que um serviço brasileiro com ARIA abre para responder à vigilância, à gestão e à operadora: instalado localmente, em português, com definições que um avaliador aceita.
