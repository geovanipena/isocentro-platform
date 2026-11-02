---
title: 'Pesquisa de domínio: catálogo de atividades do físico médico em radioterapia no Brasil'
type: domain
topic: 'Catálogo de atividades do físico médico em radioterapia no Brasil'
decision: 'Construir o catálogo que é a espinha e o denominador de cobertura do SGQ-RT'
source: 'import: imports/catalogo_atividades_fisico_medico_radioterapia_brasil_2026.md (deep research externo, 13/10/2026, a partir de brief.md), verificado em 2 frentes contra texto primário'
status: complete
preset: draft → process
validation: normal (obrigações e prazos de maior peso conferidos no texto da norma)
created: '2026-10-13'
updated: '2026-10-13'
claims: '18 no ledger: 14 verified, 3 disputed, 1 unverified (recon_kit tally)'
---

# Catálogo de atividades do físico médico em radioterapia

**Decisão que esta pesquisa atende:** construir o catálogo que é a espinha
do SGQ-RT e o denominador da cobertura ("quantas das N obrigações têm
verificação ativa").

**Artefato principal:** [`catalogo-v1.csv`](catalogo-v1.csv). São 74 linhas:
58 vêm do relatório sem alteração, 6 do relatório com correção e 10 são
acréscimos verificados. O arquivo usa ponto e vírgula e abre no Excel.

## Resumo executivo

O relatório externo é uma boa **base**, mas não é um catálogo completo. Ele
mesmo diz isso, e a verificação confirma. Três achados orientam o próximo
passo:

1. **O catálogo precisa de dois níveis.** As 64 linhas do relatório são
   obrigações de grão grosso: a linha A07 junta todo o CQ do acelerador, MLC
   e mesa. "Completo" só fica mensurável separando:
   - **obrigação:** linha da norma, estável e contável. É o denominador da
     cobertura normativa;
   - **item de verificação:** gerado da tabela do protocolo que o serviço
     adotou, por exemplo cada teste da Tab. II do TG-142 com tolerância e
     frequência. É o denominador da cobertura técnica.
2. **O relatório deixou de fora obrigações verificadas.** Elas entraram no
   v1 como acréscimos:
   - os testes **diários** do fator de calibração e de segurança e a dose
     absorvida **mensal** (NN 6.10, art. 35) [1];
   - **um radioterapeuta e um físico para cada 600 pacientes novos por
     ano** (art. 15, VI) [1];
   - a comunicação de desligamento de RT, SPR ou físico **em 30 dias** [1];
   - os **indicadores mínimos** da avaliação externa (RDC 20/2006, item
     6.11) [3].
3. **O regulador mudou de nome, a norma não.**
   - A **ANSN** opera desde 28/08/2025 e herdou as normas da CNEN [2], [4].
   - A NN 6.10 vigente é a de 2021, sem revisão na agenda [1], [5].
   - A RDC 20/2006 está vigente e fora da agenda da Anvisa 2026–27 [3],
     [9]. Quem está em revisão é a RDC 657 (software) [9].
   - A NN 3.01 foi substituída em 2025 e saiu uma nova ANSN 3.02 em 2026
     [6], [7].

**Maior ressalva:** **guarda de registros** e **roteiro de inspeção** seguem
como lacunas reais.

- Só há dois prazos firmes: os registros de equipamento e CQ são guardados
  **por toda a vida útil do equipamento** [3], e o prontuário tem 20 anos
  pela lei e guarda permanente do eletrônico pelo CFM [10], [11].
- Não existe roteiro público de inspeção específico de radioterapia.

## O que a verificação mudou no relatório

| Linha | Relatório dizia | Texto da norma | Fonte |
| --- | --- | --- | --- |
| Prioridade 1 / F03 | designação no art. 16, V–VI | **art. 15, V** (o titular designa); art. 15, VI é a regra dos 600 pacientes | [1] |
| Prioridade 7 / G01 | RDC 20/2006, 6.6–6.8 = programa, procedimentos e registros | 6.8 = **protocolos validados**; procedimentos e registros em 6.6(c), 6.7(d) e 8.1(c) | [3] |
| G05 | "conforme prazos da RDC 36" | mensal até o 15º dia útil; **óbito em 72 h**; vale para a radioterapia | [12] |
| G07 | prontuário: 20 anos | conflito: 20 anos (lei, inclui nato-digital) × **permanente** para o eletrônico (CFM, art. 7º) | [10], [11] |
| F08 | "prazos aplicáveis" | investigação **imediata**; **relatório à ANSN em 30 dias**; informar o paciente por escrito | [1], [6] |
| Fiscalizador | "ANSN" sem explicação | ANSN criada pela Lei 14.222/2021, operando desde 08/2025; normas ainda hospedadas em gov.br/cnen | [2], [4] |

Confirmado sem mudança:

- NN 6.10, art. 24 (I, a–f, e VI), art. 49 (calibração em 2 anos, aferição
  trimestral com ±1%) e art. 20, IV–VI [1];
- RDC 20/2006, 6.6, 6.7, 9.3, 9.4 e 6.9 [3];
- RDC 63/2011, art. 23, XVIII [13].

## Os conflitos que o sistema tem de carregar

| Tema | Fonte 1 | Fonte 2 | Como o SGQ-RT trata |
| --- | --- | --- | --- |
| Avaliação externa | RDC 20/2006, 6.9: **4 anos** [3] | NN 6.10, art. 36: **≤ 2 anos** [1] | Duas linhas (G02 e G03), cada uma com o próprio vencimento |
| Prontuário | Lei 13.787, art. 6º: **20 anos** [10] | CFM 1.821, art. 7º: **permanente** se eletrônico [11] | Classe documental com o prazo mais longo até parecer jurídico |
| CQ do acelerador | NN 6.10, art. 24, I, c: programa escrito [1] | TG-142/MPPG 8: frequências e tolerâncias (relatório) | O nível obrigação cita a norma; o nível item cita o protocolo adotado |
| Treinamento | art. 20, VI: **anual** em proteção [1] | art. 24, I, f: física médica **≤ 2 anos** [1] | Dois controles (F05 e F06) |

## Recomendações

| # | Recomendação | Alimenta | Base |
| --- | --- | --- | --- |
| R1 | Adotar o `catalogo-v1.csv` como semente do **nível obrigação** e o físico revisar linha a linha (manter, ajustar, excluir) | PRD, requisito do catálogo | alta nos obrigatórios verificados; média nas demais linhas do relatório |
| R2 | Modelar dois níveis (obrigação → itens de verificação), com uma **política de adoção** que diga qual protocolo gera os itens (TG-142 ou outro, TRS-398 ou TG-51), com data e responsável. O RDC 20/2006, 6.8 exige "protocolos validados" [3] | Arquitetura do núcleo; addendum do brief | alta |
| R3 | Fiscalizador = ANSN (radioproteção) e VISA (sanitário); citar "NN 6.10 (Res. CNEN 277/21)" até sair norma ANSN própria | Vocabulário do PRD | alta |
| R4 | O índice de segurança usa duas coberturas: obrigações cobertas / total de obrigações, e itens cobertos / total de itens do protocolo adotado | Brief (inovação IV), PRD | proposta de modelo |
| R5 | Guarda por classe documental. Equipamento e CQ: vida útil do equipamento [3]. Prontuário: o mais longo entre lei e CFM [10], [11]. Demais classes: "não eliminar" até definição | PRD, requisito do log | alta nos dois prazos verificados |
| R6 | Indicadores (G12) e dimensionamento (G11) ligam o catálogo ao Radioteradados (Fase 5) | PRD do Radioteradados | alta |

## Perguntas em aberto

- **Guarda das demais classes:** incidente, auditoria, treinamento,
  dosimetria pessoal, licenciamento. Fica para uma pesquisa dirigida ou para
  parecer jurídico.
- **Itens de verificação:** extrair as tabelas do TG-142, do MPPG 8 e da
  imagem. Isso é decisão do físico (que protocolo adotar), seguida de uma
  extração.
- **Roteiro de inspeção:** nenhum público específico. Pedir à VISA local ou
  à ANSN o roteiro usado na última inspeção do serviço.
- **Resolução ANSN 1/2025** (absorção das normas da CNEN): o texto no DOU não
  foi localizado.
- **Braquiterapia HDR:** a área E só vale se o serviço tiver HDR. Confirmar.
- **Linhas do relatório não verificadas** (dentre as 58 sem correção): ficam
  com confiança média até a revisão do físico.

## Fontes

| # | Afirmação que sustenta | Publicador | Pub. | Acesso | Confiança |
| --- | --- | --- | --- | --- | --- |
| 1 | NN 6.10: arts. 15, 20, 24, 26, 35, 36 e 49 | [CNEN/ANSN, NN 6.10 consolidada (Res. CNEN 277/21)](https://www.gov.br/cnen/pt-br/acesso-rapido/normas/grupo-6/ansn-6-10-requisitos-de-seguranca-e-protecao-radiologica-para-servicos-de-radioterapia.pdf) | 2021-08 (PDF 2025-12) | 2026-10-13 | alta |
| 2 | ANSN criada por cisão da CNEN | [Lei 14.222/2021](https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2021/lei/L14222.htm) | 2021-10 | 2026-10-13 | alta |
| 3 | RDC 20/2006: 6.6–6.9, 6.11, 8.1, 9.3, 9.4; vigente | [Saúde Legis, RDC 20/2006](https://bvsms.saude.gov.br/bvs/saudelegis/anvisa/2006/rdc0020_02_02_2006.html) + Anvisa Legis | 2006-02 | 2026-10-13 | alta |
| 4 | ANSN operando desde 28/08/2025; normas CNEN absorvidas | Agenda Regulatória ANSN 2026–2027 (gov.br/ansn, versão junho/2026) | 2026-06 | 2026-10-13 | média (Res. ANSN 1/2025 não lida) |
| 5 | NN 6.10 fora das listas de revisão | [CNEN, normas em elaboração/revisão](https://www.gov.br/cnen/pt-br/acesso-rapido/normas/normas-em-elaboracao) (dez/25–abr/26) | 2026-06 | 2026-10-13 | alta |
| 6 | ANSN 3.01: notificação de incidente (arts. 98 e 117) | CNEN, Norma 3.01 (Res. CNEN 344/25), gov.br/cnen grupo 3 | 2025-07 | 2026-10-13 | alta |
| 7 | Nova ANSN 3.02 "Serviços de Radioproteção" | Res. ANSN 19/26, DOU 17/06/2026 (via página da CNEN) | 2026-06 | 2026-10-13 | média |
| 8 | Catálogo-base: 64 linhas e 8 áreas | Relatório externo (imports/) | 2026-10-13 | 2026-10-13 | média |
| 9 | Agenda Anvisa 2026–27: tema 5.11 revisão da RDC 657; nada de radioterapia | [Anvisa, Agenda Regulatória 2026–2027](https://www.gov.br/anvisa/pt-br/assuntos/regulamentacao/agenda-regulatoria/2026-2027) | 2026-08 | 2026-10-13 | alta |
| 10 | Prontuário: 20 anos do último registro | [Lei 13.787/2018](https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13787.htm) | 2018-12 | 2026-10-13 | alta |
| 11 | Prontuário eletrônico: guarda permanente | [CFM, Res. 1.821/2007](https://sistemas.cfm.org.br/normas/arquivos/resolucoes/BR/2007/1821_2007.pdf) | 2007-07 | 2026-10-13 | alta (art. 10 revogado, não lido) |
| 12 | RDC 36/2013: notificação mensal; óbito em 72 h | RDC ANVISA 36/2013, Anvisa Legis | 2013-07 | 2026-10-13 | alta |
| 13 | RDC 63/2011: procedimentos e prontuário | RDC ANVISA 63/2011, Anvisa Legis | 2011-11 | 2026-10-13 | alta |

O relatório externo [8] traz ainda as suas próprias 100+ fontes, em
`imports/`, que não foram reconferidas uma a uma.

## Validade

Para norma, o relógio é a data da conferência de vigência (13/10/2026), não a
de publicação. Janelas: vigência 12 meses, agenda regulatória 6.

| Afirmação | Reconferir em |
| --- | --- |
| Agenda Anvisa 2026–27 (revisão da RDC 657 em andamento) | 2027-04-13 |
| Agenda ANSN e listas de revisão (NN 6.10 sem revisão) | 2027-04-13 |
| NN 6.10, RDC 20/2006, RDC 36/2013 e RDC 63/2011 vigentes | 2027-10-13 |
| ANSN 3.01 e 3.02 | 2027-10-13 |

A primeira reconferência é em **abril de 2027**: a revisão da RDC 657 está
em andamento e afeta diretamente os avaliadores ESAPI do SGQ-RT.
