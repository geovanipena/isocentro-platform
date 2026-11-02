---
title: 'Product Brief: ISOCENTRO — gestão da qualidade em radioterapia, em módulos'
status: final
created: '2026-10-13'
updated: '2026-10-16'
inputs:
  - '../research-sgq-rt-referencias-2026-10-13/research.md'
  - '../research-catalogo-atividades-fisico-medico-radiot-2026-10-13/catalogo-v1.csv'
  - '../incidentes/SPEC - Módulo incidentes v0.1.md'
  - '../radioteradados/brief-radioteradados-2026-10-13/brief.md'
  - '../../../qms/escopo.md'
  - '../../../BIBLIOTECAS_EXTERNAS.md'
  - 'C:/Users/geova/Documents/isocentro/conhecimento/ (base de conhecimento: fichas, matriz, índices, PENDENCIAS.md)'
nota: 'Pasta mantém o nome antigo (sgq-rt) para não quebrar referências; o produto se chama ISOCENTRO desde 16/10/2026.'
---

# Product Brief: ISOCENTRO

## Resumo

O **ISOCENTRO** passa a ser o sistema de gestão da qualidade do serviço de
radioterapia, organizado em **módulos** sobre um **motor único de
verificação**. O nome SGQ-RT deixa de existir (16/10/2026).

A espinha do produto é a **base de conhecimento** construída em 16/10/2026
(`Documents/isocentro/conhecimento/`): 100 atividades do físico médico (74
obrigações e 26 de prática), cada uma com ficha, norma, tolerância conferida
na fonte e lacuna no PPR, e 1.090 ligações a documentos, manuais, código e
POPs.

O produto está completo quando cada uma das **74 obrigações** tiver
verificação ativa. As 26 de prática são meta.

O motor continua **advisory**: avisa e registra. Onde a norma exige
conferência, o ISOCENTRO registra a conferência e a assinatura, e a trava
fica onde já existe: no ARIA, só o físico dá o Treatment Approved.

## O problema

- **Obrigações legais sem processo escrito.** A base mostrou duas
  exigências que o serviço não tem em procedimento, e um prazo que vale
  para todo cálculo:
  - **NN-6.10, art. 15, XI, e:** deve existir **segundo sistema de cálculo
    de dose** para verificar o planejamento.
  - **NN-6.10, art. 17, IV:** todo plano deve ser **conferido com segunda
    assinatura**.
  - **RDC 20/2006, item 9.7 (c):** todo cálculo deve ser verificado **até a
    3ª fração ou 10% da dose**.

  O POP-019 vai de "o físico calcula" para "o RT aprova", sem revisão nem
  segunda checagem. O cálculo paralelo do ISOCENTRO existe, mas só tem
  tabelas de exemplo e ainda não verifica nenhuma máquina do serviço.
- **O PPR declara um programa de CQ baseado no TG-40, de 1994.** Os PPRs da CEL, da BET e da
  DUO seguem o TECDOC-1151, que é adaptado do TG-40. Faltam MLC, imagem,
  SRS e FFF, embora as clínicas façam IMRT, VMAT e SRS. O usuário confirmou
  que isso é falha do PPR.
- **A qualidade está espalhada.** Os vencimentos e o PPR ficam no
  `ppr-streamlit`. O QA de paciente fica em planilhas, algumas com nome de
  paciente. Constraints e escrita no Eclipse ficam em scripts ESAPI. A
  notificação de incidentes vai pelo Epimed, sem taxonomia de radioterapia.
  Não há um lugar que responda "o que está vencido, o que falhou e quem
  precisa agir".
- **Software próprio sem validação registrada.** A RDC 657/2022 (art. 5º)
  isenta o software *in house* das classes I e II, **desde que haja
  validação completa guardada por 10 anos após o descarte**. O prazo de
  adequação venceu em 30/03/2024.
- **Não há caso local registrado** de incidente ou de vencimento perdido.
  A motivação é a obrigação legal e o padrão de falha documentado em
  incidentes de outros serviços: seis casos do acervo (Panamá, Glasgow,
  Toulouse, Costa Rica, Białystok e Épinal) falharam em pontos que o
  ISOCENTRO cobre (detalhe no adendo).

## A solução

Um **núcleo** que não conhece radioterapia:

- o objeto **Verificação**, com regra, fonte normativa, gatilho,
  responsável, avaliador e resultado com evidência;
- o **contrato de avaliador**: devolve o resultado e não grava;
- o **log append-only encadeado**;
- o resultado **`indeterminado`** como resultado de primeira classe.

Sobre esse núcleo, **módulos** que agrupam as áreas da base:

| Módulo | Áreas da base | Ponto de partida |
| --- | --- | --- |
| **Plano** (planejamento e revisão) | C, I, H01 | `dominio/paralelo.py`, aba Qualidade, checklist, scripts ESAPI de constraints |
| **Tratamento** | D | Ficha Virtual, Capa, Agenda (leitura do `variandw`) |
| **Garantia da Qualidade** (equipamentos e dosimetria) | A, E, H02, H05 | Programa de CQ gerado da base (`programa-cq.csv`), pylinac |
| **Documentação e conformidade** | F, G01–G03, G07–G10, B05 | `ppr-streamlit` (PPR, vencimentos), POPs |
| **Segurança do paciente** | G04, G05, G14–G17 | Spec do módulo de incidentes v0.1 |
| **Indicadores** | G12, G19 | Radioteradados (PRD e arquitetura prontos) |
| **Software e sistemas** | B | `docs/qms`, suíte de testes, ciclo ISQM (YOO-2025) |
| **Conhecimento** | todas | A base e o mapa interativo |

O catálogo tem dois níveis. A **atividade** vem da base. O **item de
verificação** vem das tabelas dos protocolos, como os 103 testes do
`programa-cq.csv`, cada um com tolerância, fonte e máquina. Avaliadores em
Python rodam dentro do app; os de ESAPI (C#) falam com o núcleo por JSON. Há
uma só interface, o shell PyQt5 do ISOCENTRO.

## MVP

Os cinco itens escolhidos pelo usuário. Cada um é obrigação legal e
reaproveita código que já existe:

| # | Entrega | Base legal | Reaproveita |
| --- | --- | --- | --- |
| 1 | **Segunda checagem de cálculo** com as tabelas reais do TrueBeam, do 6EX, do 600CD, do VitalBeam e do Synergy, comissionada pelo TG-219 (Tab. 8) e com limites do TG-219 e do TG-114; roda após a aprovação médica, junto do PSQA, e o resultado aparece na Aprovação Física e no Duplo Check | NN-6.10 art. 15, XI, e; RDC 20 9.7 (c) | `paralelo.py` (porte do `parallel-mu-check`), `dados_feixe/`, `comissionamento/`: TrueBeam e 6EX (DOSEMED, 2020), 600CD (2010), VitalBeam (2020) e tabelas do Synergy (2026) |
| 2 | **Revisão do plano com segunda assinatura**: lista "++" do TG-275, itens automatizáveis (marcados F) checados do RT Plan e do ARIA, registro de quem conferiu e quando. **Acompanha a sequência real lida do srvariadb** (aprovação médica do plano → PSQA → Aprovação Física/Treatment Approved pelo físico do caso → Duplo Check por outro físico → 1ª fração) e alerta Duplo Check ausente até a 3ª fração ou 10% da dose, ou antes da 1ª fração nos casos de alto risco | NN-6.10 art. 17, IV; RDC 20 9.7 (c); TG-275; MPPG-11a | Checklist pré-tratamento, lista de verificação do Carepath (votada), `dicom_rt.py`, `tratamento_db.py`, PlanCheck e uhg-plancheck (ESAPI) |
| 3 | **Registro do programa de CQ**: execução por teste, tolerância e ação, carta de controle, cópia de segurança | NN-6.10 art. 35 e art. 71, IX; RDC 20 8.1 (b) | `programa-cq.csv` e `qualidade.json` por clínica; pylinac; modelo de dados do QATrack+ |
| 4 | **Incidentes e quase-incidentes**: taxonomia de RT, prazo de 30 dias, aviso escrito ao paciente; o Epimed continua o canal oficial | NN-6.10 art. 26; RDC 36/2013 | Spec de incidentes v0.1 (SQLModel) |
| 5 | **Vencimentos**: calibrações (2 anos), aferições (trimestral), fonte HDR, levantamento radiométrico, treinamentos, auditoria e ASO | NN-6.10 arts. 29, 49, 52, 54, 55; art. 20 | Vencimentos do `ppr-streamlit` |

## O que o torna diferente

1. **Cada verificação nasce com o porquê.** A regra aponta para a ficha da
   base, que tem a norma, a tolerância e a página da fonte.
2. **Modo sombra.** Toda regra nova roda 30 dias gravando sem aparecer, e
   só depois é promovida.
3. **Sensibilidade medida por erro semeado**, após cada upgrade do ARIA ou
   do Eclipse. É o registro de validação que a RDC 657 pede.
4. **Auditoria externa espelhada** como verificação interna.
5. **Biblioteca de regras citável**, separada do software. O que sai do
   serviço é a biblioteca; o software não (RDC 657, art. 5º, § 1º).

**Vantagem honesta:** quem escreve é o físico responsável, e a base
documenta cada decisão. **Maior risco:** a manutenção depende de uma pessoa,
sem fornecedor.

## Para quem

`[SUPOSIÇÃO]` A tabela de usuários do `docs/qms/escopo.md` ainda está vazia.

- **Físico médico:** dono das regras, segunda checagem, revisão e CQ.
- **Dosimetrista:** resultado da checagem durante o planejamento.
- **Radioterapeuta:** conferência e alertas de prescrição.
- **Técnico:** CQ diário e checklist da sala.
- **SPR e gestão:** vencimentos, incidentes e indicadores.

## Como saber que deu certo

- **Cobertura:** fração das 74 obrigações com verificação ativa, publicada
  e crescente.
- **Segunda checagem:** 100% dos planos verificados até a 3ª fração (a meta
  é antes da 1ª), nas cinco máquinas, com o cálculo comissionado.
- **Revisão:** 100% dos planos com conferência registrada antes da 1ª
  fração nos casos de alto risco (SBRT, reirradiação, dispositivo
  implantado).
- **CQ:** nenhum teste do programa vence sem registro; uma falha aparece no
  mesmo dia.
- **Incidentes:** todo evento com prazo de 30 dias acompanhado.
- **Validação:** cada módulo com relatório de validação (RDC 657) e o log
  íntegro.
- **O físico deixa de manter as planilhas paralelas** de vencimentos e de
  QA de paciente.

## Fora

- Bloquear o fluxo clínico dentro do ISOCENTRO; a trava é a do ARIA.
- Escrever no ARIA ou no data warehouse.
- Escrever no Eclipse, exceto por script ESAPI gravável validado.
- IORT (INTRABEAM), por decisão de 13/10/2026. O `iort-streamlit` não entra.
- Enviar dado pessoal a terceiros.
- Recálculo de dose 3D próprio. A segunda checagem é por ponto (TMR × Scp),
  e a evolução para 2D/3D fica para depois.

## Riscos e o que ainda não se sabe

- **Classe regulatória.** A segunda checagem e a revisão influenciam a
  decisão de tratar. A classe ANVISA (RDC 751/2022, fora do acervo) e a
  classe IEC 62304 de cada módulo precisam ser decididas pelo físico antes
  do PRD. O IMDRF N12 põe um TPS na categoria III. Se a classe passar de
  II, o art. 5º da RDC 657 deixa de valer.
- **Uso nas três clínicas.** CEL, BET e DUO têm CNPJs diferentes. O uso
  *in house* em rede exige subordinação administrativa e financeira
  documentada (P&R ANVISA, pergunta 2).
- **Tabelas de feixe.** São dados de 2010 (600CD) e de 2020 (Varian), e a
  segunda checagem vale tanto quanto a tabela. A conversão precisa ser
  validada.
- **Pendências do serviço afetam o MVP** (instrumentos, dispositivo de QA,
  calibração); lista no adendo e em `conhecimento/PENDENCIAS.md`.
- **PPR desatualizado.** FFF e SRS/SBRT estão fora do PPR, e a NN-6.10
  (art. 15, XIV) exige PPR novo antes de qualquer modificação.
- **Manutenção de uma pessoa só.** Todo upgrade pode quebrar avaliadores.
- **Decisões pendentes:** hospedagem; banco do log (SQLite × PostgreSQL);
  confirmar a trava no ARIA.

## Visão

Em 2 a 3 anos, o ISOCENTRO responde em uma tela o que está vencido, o que
falhou e quem precisa agir, nas três clínicas. Ele chega à inspeção da ANSN
e à avaliação da ANVISA com o histórico pronto, e cada número aponta para a
norma de onde veio.
