---
title: 'PRD: ISOCENTRO — gestão da qualidade em radioterapia, em módulos'
status: final
created: '2026-10-16'
updated: '2026-10-26'
inputs:
  - '../brief-sgq-rt-2026-10-13/brief.md'
  - '../brief-sgq-rt-2026-10-13/addendum.md'
  - 'C:/Users/geova/Documents/isocentro/conhecimento/'
  - 'extrato-entradas.md (extração das entradas, com fonte por fato)'
---

# PRD: ISOCENTRO

## 0. Para que serve este documento

Este PRD é o passo 1 de 4 (PRD → UX → arquitetura → épicos) do ISOCENTRO
como sistema de gestão da qualidade do serviço de radioterapia. É escrito
para o físico responsável, que decide, e para os agentes de UX, arquitetura
e épicos, que constroem a partir dele.

Ele parte do brief final (`../brief-sgq-rt-2026-10-13/brief.md`) e da base
de conhecimento (`Documents/isocentro/conhecimento/`), e não repete o que lá
está: cita. O vocabulário do §3 vale para o documento inteiro. Funcionalidades
agrupam requisitos (FR) numerados globalmente. O que foi inferido sem
confirmação está marcado `[SUPOSIÇÃO]` e indexado no §16. Todo requisito que
toca algo que já existe cita o módulo do código (`isocentro/...`) ou a frente
do `DESTINO.md` (R-NN). Os fatos de código e da base, com arquivo e linha,
estão em `extrato-entradas.md`.

A base clínica (`docs/qms/`) é fato para este documento: o escopo, a
classificação IEC 62304 e a análise de risco. Onde ela está vazia, o PRD
pergunta (§15) em vez de presumir.

## 1. Visão

O ISOCENTRO passa a ser o lugar onde o serviço responde a três perguntas: **o
que está vencido, o que falhou e quem precisa agir**. Hoje a resposta está
espalhada entre o `ppr-streamlit`, planilhas de QA de paciente, scripts
ESAPI, o Epimed e a memória do físico. E duas obrigações legais — o segundo
sistema de cálculo (NN-6.10 art. 15, XI, e) e a segunda assinatura do plano
(NN-6.10 art. 17, IV) — não têm procedimento escrito: o POP-019 vai de "o
físico calcula" para "o RT aprova".

O produto é um **motor único de verificação**, que não conhece radioterapia,
e **oito módulos** que conhecem. Cada verificação nasce com o porquê: a
regra aponta para a ficha da base, que tem a norma, a tolerância e a página
da fonte. O motor é **advisory**: avisa e registra, nunca bloqueia. A trava,
onde a norma exige, fica onde já existe — no ARIA, só o físico dá o
Treatment Approved.

O primeiro corte (MVP) entrega cinco obrigações legais sobre código que já
existe: segunda checagem de cálculo, revisão do plano com segunda assinatura
e acompanhamento da sequência real, registro do programa de CQ, incidentes e
quase-incidentes, e vencimentos. O produto está completo quando cada uma das
74 atividades do catálogo v1 da base tiver verificação ativa (FR-37).

Não há caso local registrado de incidente nem de vencimento perdido. A
motivação é a obrigação legal e o padrão de falha de seis casos do acervo
(Panamá, Glasgow, Épinal, Costa Rica, Białystok e Toulouse), que falharam em
pontos que o MVP cobre (addendum do brief, "Casos de incidente").

Em 2 a 3 anos, o ISOCENTRO responde em uma tela, nas três clínicas, o que
está vencido, o que falhou e quem precisa agir, e chega à inspeção da ANSN e
à avaliação da ANVISA com o histórico pronto.

## 2. Usuários

### 2.1 Trabalhos a fazer

- **Físico médico** (dono das regras): saber, sem montar planilha, que todo
  plano teve segunda checagem e Duplo Check no prazo, que nenhum teste de CQ
  venceu sem registro e que cada incidente está correndo dentro dos 30 dias.
  Chegar à inspeção da ANSN e à avaliação da ANVISA com o histórico pronto.
- **Físico do Duplo Check** (outro físico, nunca o da Aprovação Física):
  conferir o plano com a lista votada, ver o resultado da segunda checagem já
  pronto e deixar a assinatura registrada.
- **Dosimetrista:** ver o resultado da segunda checagem enquanto ainda dá
  para mexer no plano.
- **Radioterapeuta (médico):** ver alertas de prescrição e saber se o plano
  que aprovou passou pelas conferências.
- **Técnico:** registrar o CQ diário e o checklist da sala sem papel paralelo.
- **Enfermeiro e recepcionista:** registrar incidente ou quase-incidente
  visto no próprio trabalho.
- **SPR e gestão:** acompanhar vencimentos, incidentes e indicadores.

São oito trabalhos para sete perfis: médico, físico, dosimetrista, técnico,
enfermeiro, recepcionista e SPR/gestão. O físico médico e o físico do Duplo
Check têm o mesmo perfil (físico). Admin e físico responsável não são
perfis: são atributos dados a uma pessoa (decisão do usuário na UX,
18/10/2026, e na spec da Fundação, 19/10/2026). A tabela de usuários do
`docs/qms/escopo.md` ainda precisa ser preenchida pelo físico (frente R-16).

### 2.2 Quem não usa (MVP)

- Paciente: não acessa o ISOCENTRO. O aviso escrito do art. 26 é um documento
  que o serviço entrega; o ISOCENTRO só registra que foi entregue.
- Pessoas de fora do serviço (auditor, inspetor): recebem relatórios
  exportados, não acesso ao app. `[SUPOSIÇÃO]`
- A unidade SAT (Synergy01, Monaco): fora do MVP por decisão de 16/10/2026.

### 2.3 Jornadas principais

`[SUPOSIÇÃO]` As jornadas abaixo foram escritas pelo PRD a partir do brief, da
lista votada do Carepath e do código, e precisam ser conferidas pelo físico
contra um caso real. Os nomes são ilustrativos.

- **UJ-1. Ana, física do caso, faz a Aprovação Física com a segunda checagem
  já pronta.**
  O médico aprovou o plano (Planning Approved) de uma mama 50 Gy/25 fr no
  6EX. Na mesma leva do PSQA, o ISOCENTRO rodou a segunda checagem com a
  tabela do 6EX. Ana abre o caso na aba do plano: vê a diferença
  calculado × TPS por campo e no composto, o limite usado e de onde ele vem
  (TG-219, literatura, não calibrado para o serviço). Percorre os 8 itens da
  Aprovação Física, marca, e dá o Treatment Approved no ARIA. O ISOCENTRO
  registra a aprovação lida do `variandw`. **Caso de borda:** o plano tem
  campo com filtro físico, que o cálculo não trata; a checagem sai
  `indeterminado` com o motivo, e Ana registra a justificativa.

- **UJ-2. Bruno, segundo físico, faz o Duplo Check antes da 3ª fração.**
  Bruno abre a fila de Duplo Check pendente, ordenada pelo prazo (3ª fração
  ou 10% da dose, o que vier primeiro). Os casos de alto risco aparecem no
  topo com prazo "antes da 1ª fração". Abre o caso: os 8 itens do Duplo
  Check, os itens automáticos já conferidos do RT Plan e do ARIA, e o
  resultado da segunda checagem. Assina. O ISOCENTRO grava quem, quando e
  sobre qual versão do plano. **Caso de borda:** o usuário logado é o mesmo
  que deu a Aprovação Física; o ISOCENTRO avisa que o Duplo Check precisa ser
  de outro físico e não registra a assinatura como Duplo Check.

- **UJ-3. Carla, técnica, registra o CQ diário do VitalBeam.**
  Antes do primeiro paciente, Carla abre a lista do dia da DUO (22 testes
  diários), lança os valores e o resultado do DailyQA 3. Um teste sai da
  tolerância; o ISOCENTRO mostra a ação prevista e avisa o físico no mesmo
  dia. A carta de controle do output diário ganha um ponto.

- **UJ-4. Geovani, físico responsável, abre a semana pelos vencimentos.**
  O painel mostra o que vence nos próximos 60 dias nas três clínicas:
  calibração bienal de um sistema de referência da BET, aferição trimestral
  com fonte-teste, um treinamento anual de PR. Um item não tem data de
  partida: aparece como "sem data", não como em dia.

- **UJ-5. Daniel, dosimetrista, registra um quase-incidente achado na
  revisão.**
  Na revisão, Daniel encontra a energia do plano diferente da prescrição.
  Corrige no TPS e registra no ISOCENTRO um quase-incidente com etapa onde
  ocorreu, etapa onde foi detectado e gravidade. O físico vê o registro na
  revisão trimestral. Se fosse um incidente com exposição não intencional, o
  ISOCENTRO abriria o prazo de 30 dias e a lista do art. 26.

## 3. Glossário

Os termos abaixo valem para todo o documento e para os documentos seguintes.

- **Atividade** — obrigação ou prática do físico médico, vinda da base
  (`matriz/atividades.csv`, 100 linhas: 74 do catálogo v1 e 26 de prática
  acrescentadas em 16/10/2026). Das 100, 60 têm nível que começa com
  "OBRIGATÓRIO" (norma brasileira); as demais são recomendação, boa prática
  ou prática. Cada atividade tem ficha com norma, exigência e fonte, e zero
  ou mais itens de verificação.
- **Item de verificação** — o que é de fato conferido, vindo das tabelas dos
  protocolos (por exemplo, os 103 testes do `programa-cq.csv`), cada um com
  tolerância, fonte e máquina.
- **Verificação** — o objeto do núcleo: regra, proveniência, gatilho,
  responsável, avaliador, severidade e estado. Executa um item de
  verificação.
- **Execução** — uma rodada de uma verificação, com resultado, evidência,
  origem (`producao` ou `semeado`) e data.
- **Resultado** — um de: `conforme`, `nao_conforme`, `nao_aplicavel`,
  `indeterminado`, `erro`.
- **Indeterminado** — resultado de primeira classe: a verificação não pôde
  concluir (falta tabela, falta dado, técnica não tratada) e diz por quê.
  Nunca é contado como conforme.
- **Severidade** — `alta`, `atencao` ou `informativo`. Nenhuma bloqueia.
  `[SUPOSIÇÃO]` Os três nomes são os do esboço do brief; o nome definitivo do
  nível mais alto foi deixado para o PRD.
- **Estado da verificação** — `sombra` (roda e grava, não aparece), `ativa`
  ou `podada`.
- **Avaliador** — a peça que calcula o resultado de uma verificação. Devolve
  o resultado e não grava nada. Pode ser Python (dentro do app) ou ESAPI
  (C#, fala com o núcleo por JSON).
- **Gatilho** — o que dispara uma verificação: `evento`, `calendario`,
  `prazo` ou `estado` (addendum do brief, "Os quatro gatilhos").
- **Proveniência** — as fontes normativas de uma verificação, apontando para
  a ficha da base. Verificação sem proveniência é rejeitada.
- **Log** — o registro append-only encadeado por hash de toda execução,
  assinatura e mudança de regra.
- **Segunda checagem** — cálculo independente da dose ou UM de um plano pelo
  `dominio/paralelo.py`, com a tabela da máquina do plano (atividades C05,
  H01).
- **Tabela de feixe** — TMR e Scp de uma máquina e energia, em `dados_feixe/`,
  com os nomes DICOM da máquina. Sem tabela da máquina, o resultado é
  `indeterminado`.
- **Aprovação médica** — o plano em `Planning Approved` no ARIA.
- **Aprovação Física** — etapa do Carepath em que o físico do caso confere o
  plano (8 itens votados) e dá o `Treatment Approved` no ARIA. No ISOCENTRO,
  a Aprovação Física é a lista conferida e assinada pelo físico do caso (FR-19);
  o `Treatment Approved` e quem o deu são lidos do `variandw` (FR-16).
- **Alerta** — aviso gerado por um resultado ou por um prazo, com severidade,
  destinatário e estado (aberto, visto, resolvido com justificativa). É a
  saída principal do motor (FR-41).
- **Auditoria espelhada** — verificação interna que repete os itens de uma
  auditoria externa (NN-6.10 art. 36), para chegar à auditoria sabendo o
  resultado. Depois do MVP.
- **Duplo Check** — etapa do Carepath em que outro físico confere o plano (8
  itens votados) e assina. É a segunda assinatura do art. 17, IV.
- **Sequência real** — as datas de aprovação médica, PSQA, Treatment
  Approved, Duplo Check e 1ª fração de um plano, lidas do `variandw`.
- **Prazo de verificação** — até a 3ª fração ou até 10% da dose total, o que
  vier primeiro (RDC 20/2006, item 9.7 (c)). Vale para a segunda checagem e
  para o Duplo Check (decisão do usuário, 16/10/2026).
- **Caso de alto risco** — SBRT/hipofracionamento, reirradiação ou campo
  adjacente, ou dispositivo implantado (TG-275 p. 11). O prazo passa a ser
  antes da 1ª fração.
- **Programa de CQ** — o conjunto de itens de verificação de equipamento por
  clínica e máquina (`servico/<CLÍNICA>/qualidade.json`, gerado do
  `programa-cq.csv`).
- **Vencimento** — data em que uma obrigação periódica (calibração,
  aferição, treinamento, auditoria, ASO etc.) deixa de estar em dia.
- **Incidente** — evento que atingiu o paciente ou poderia ter atingido com
  dano, incluindo exposição médica não intencional (NN-6.10 art. 26).
- **Quase-incidente** — erro detectado antes de chegar ao paciente.
- **Clínica** — CEL, BET ou DUO (Anápolis). Cada uma tem CNPJ próprio.
- **Degrau de fonte** — `variandw` → espelho local → relatório exportado. A
  tela anuncia o degrau e a data do dado.

## 4. Núcleo e plataforma

### 4.1 Motor de verificação

**Descrição:** o núcleo guarda verificações e execuções sem saber nada de
radioterapia. Todo módulo do MVP é um conjunto de verificações sobre ele. É
o "objeto Verificação" do addendum do brief.

#### FR-1: Cadastro de verificação com proveniência

O físico pode cadastrar uma verificação com regra, proveniência, gatilho,
responsável (perfil), avaliador, severidade e estado.

**Consequências (testáveis):**

- Verificação sem pelo menos uma fonte na proveniência é recusada pelo
  esquema.
- Cada fonte da proveniência resolve para uma ficha da base
  (`fichas/atividades/<ID>.md`) ou para uma ficha de referência; fonte que não
  resolve é recusada.
- Toda tolerância cadastrada tem origem (`literatura` com a referência, ou
  `servico` com a data e o método da derivação, AAPM TG-218).

#### FR-2: Contrato do avaliador

Um avaliador recebe o contexto da execução e devolve resultado, evidência e
motivo; nunca grava.

**Consequências:**

- Um teste prova que o avaliador Python e o avaliador ESAPI (JSON) produzem o
  mesmo formato de resultado.
- Avaliador que lança exceção gera execução com resultado `erro` e a
  mensagem, nunca `conforme`.
- Avaliador sem dado suficiente devolve `indeterminado` com o motivo.

#### FR-3: Log append-only encadeado

Toda execução, assinatura, promoção de estado e mudança de regra entra no
log, encadeada por hash.

**Consequências:**

- Alterar ou apagar um registro antigo faz a verificação de integridade do
  log apontar o registro e a posição (RDC 657, art. 5º, § 4º).
- O log não tem operação de edição nem de exclusão.
- O log é retido por pelo menos 10 anos após o descarte do software (RDC 657,
  art. 5º, § 3º); a forma de guarda é decisão de arquitetura.

#### FR-4: Modo sombra e promoção

Toda verificação nova nasce em `sombra`: roda e grava, sem aparecer para o
usuário. O físico promove para `ativa` ou poda.

**Consequências:**

- Uma verificação em sombra não gera alerta nem entra em fila.
- A promoção registra quem promoveu, quando e o resumo do período em sombra
  (execuções, `nao_conforme`, `indeterminado`).
- `[SUPOSIÇÃO]` O período mínimo em sombra é de 30 dias por padrão,
  configurável por verificação, e o físico pode encurtá-lo com justificativa
  registrada. Encurtar é necessário para as verificações do MVP que cumprem
  obrigação legal já vencida.
- Uma verificação em sombra que cumpre obrigação legal (segunda checagem,
  prazo do Duplo Check) não substitui o processo manual durante a sombra: o
  processo atual continua até a promoção. É decisão do físico (§15, G4) se a
  sombra em dado de produção conta como uso real antes do relatório de
  validação (FR-40).

#### FR-5: Severidade sem bloqueio

O resultado de uma verificação gera alerta na severidade cadastrada e nunca
impede uma ação no ISOCENTRO ou fora dele.

**Consequências:**

- Nenhuma tela do ISOCENTRO tem botão desabilitado por resultado de
  verificação.
- `[SUPOSIÇÃO]` `nao_conforme` em severidade `alta` pede justificativa
  registrada de quem segue adiante, sem impedir que siga.

#### FR-6: Erro semeado

O físico pode rodar uma verificação contra casos semeados (com erro
conhecido) e obter a sensibilidade medida.

**Consequências:**

- Execuções semeadas ficam com origem `semeado` e nunca entram em indicador
  de produção.
- O relatório de sensibilidade mostra, por verificação, casos semeados,
  detectados e não detectados.
- Rodar a bateria semeada é um item do roteiro após cada upgrade do ARIA ou
  do Eclipse (ver FR-40).
- Caso semeado feito a partir de plano real é anonimizado antes de sair da
  pasta do paciente e nunca entra no repositório com identificação (NFR-2).

#### FR-41: Alerta

Todo resultado `nao_conforme`, `indeterminado` ou `erro` de uma verificação
ativa, e todo prazo que entra no aviso ou vence, gera um alerta para o
responsável da verificação.

**Consequências:**

- O destinatário é o perfil responsável cadastrado na verificação (FR-1),
  na clínica do objeto; o físico responsável vê os alertas das três clínicas.
- O alerta aparece num painel único do shell, "o que precisa de ação",
  ordenado por severidade e prazo, e no módulo de origem.
- Alerta tem estado: aberto, visto (quem e quando), resolvido (com
  justificativa quando a severidade é `alta`). Mudança de estado entra no
  log.
- Os prazos são calculados mesmo com o app fechado: `[SUPOSIÇÃO]` por uma
  varredura agendada na concentradora, como a da exportação (pilar 1 do
  `DESTINO.md`), e o alerta está no painel quando alguém abre o app.
- `[SUPOSIÇÃO]` No MVP o alerta só aparece no app. Canal externo (e-mail,
  mensageiro) fica para depois e, se vier, não leva dado identificável de
  paciente (NFR-2).
- Um teste prova que um prazo vencido com o app fechado aparece como alerta
  `alta` na abertura seguinte.

### 4.2 Shell, identidade e assinatura

**Descrição:** há uma só interface, o shell do ISOCENTRO
(`isocentro/interface/`), com a identidade "Torre de controle" da UX como
design system. A identidade do usuário já existe (`dados/auth.py`,
`equipe.py`, `sessao.py`: login, sessão única, perfis); a segunda assinatura
se apoia nela. A tecnologia do shell é da arquitetura (addendum).

#### FR-7: Perfis

Cada usuário tem um perfil — médico, físico, dosimetrista, técnico,
enfermeiro, recepcionista ou SPR/gestão — e o perfil define o que vê e o que
pode assinar.

**Consequências:**

- Só o perfil físico assina Aprovação Física e Duplo Check.
- Só o perfil físico cadastra, promove ou poda verificação.
- Admin (acesso às Configurações) e físico responsável (vê as três clínicas)
  são atributos dados a uma pessoa, não perfis.
- A capacidade é conferida no ato da ação, não só escondida na tela.
- A tabela perfil → capacidades mora no banco e o admin a ajusta em
  Configurações: que módulos cada perfil vê e que ações faz dentro deles
  (assinar, cadastrar, registrar). Toda mudança é gravação com autor no log
  (FR-3). O valor inicial é a matriz do `docs/qms/escopo.md` (sem referência:
  `decisoes-sem-base.md` #9). Spec Fundação, CAP-23; frente R-78.
- Quatro travas ficam fora da tabela e nenhuma configuração as desliga: só o
  físico assina Aprovação Física e Duplo Check; o físico do Duplo Check nunca
  é o da Aprovação Física (FR-20); ninguém assina em nome de outro (FR-8);
  cada clínica vê só os próprios dados (NFR-6).

#### FR-8: Assinatura registrada

Uma assinatura no ISOCENTRO grava usuário logado, perfil, data e hora, o
objeto assinado e a versão dele (para plano: o `SOPInstanceUID` do RT Plan e
o status no ARIA).

**Consequências:**

- A assinatura entra no log (FR-3).
- Assinar exige o usuário logado na sessão atual; não há assinatura em nome
  de outro.
- Uma assinatura sobre uma versão do plano não vale para outra versão: se o
  RT Plan mudar depois do Duplo Check, o Duplo Check volta a pendente. Conta
  como "outra versão" (físico, 26/10/2026; §15, P9): UID novo com conteúdo
  igual, mudança de status no ARIA, conteúdo mudado sem UID novo e mudança
  menor (campo de setup, nome de campo). O terceiro caso exige detectar
  mudança de conteúdo além do UID.

#### FR-9: Telas de módulo no shell

Cada módulo do MVP aparece como aba ou painel do shell, com o mesmo tema.

**Consequências:**

- Nenhum módulo do MVP abre fora do shell (sem Streamlit no MVP).
- Toda tela que mostra dado do `variandw` anuncia o degrau de fonte e a data
  do dado.

## 5. Módulo Plano — segunda checagem de cálculo (MVP 1)

**Descrição:** cumpre a NN-6.10, art. 15, XI, e (segundo sistema de cálculo)
e o prazo da RDC 20, item 9.7 (c). O avaliador é o `dominio/paralelo.py`
(porte do `parallel-mu-check`, TMR × Scp por ponto), que já tem cálculo e
limites. Hoje, porém, só há tabelas de exemplo (`ELEKTA_SAT`), e por isso todo
resultado sai como demonstração (pilar 3 do `DESTINO.md`; R-09). Planos 3D
usam o cálculo por ponto do `paralelo.py`; planos IMRT/VMAT, o Clarkson
modificado por ponto de controle (decisão do usuário, 19/10/2026; spec do
Plano, CAP-4). A checagem
roda depois da aprovação médica, junto do PSQA, e o resultado aparece na
Aprovação Física e no Duplo Check. Máquinas do MVP: TrueBeam (CEL), 6EX (CEL), 600CD (BET) e
VitalBeam (DUO). Synergy01 (SAT) fica fora. Realiza UJ-1 e UJ-2.

#### FR-10: Tabelas de feixe das quatro máquinas

O físico pode cadastrar a tabela de feixe de cada máquina e energia a partir
do comissionamento (`Documents/isocentro/comissionamento/`), com o registro
da conversão.

**Consequências:**

- Cada tabela tem máquina, energia, origem (relatório e data — TrueBeam e 6EX
  DOSEMED 2020; VitalBeam 2020; 600CD 2010), quem converteu e quando.
- A conversão é validada contra pontos do relatório original, e o resultado
  da validação fica guardado com a tabela.
- Os nomes DICOM de cada máquina são cadastrados explicitamente; o
  ISOCENTRO nunca casa por parecença de nome. (`TrueBeamSN1001` é a
  VitalBeam e `TBuniverSN1002` é a TrueBeam, `dominio/constantes.py`.)
- As energias FFF (6FFF e 10FFF do TrueBeam; 6FFF do VitalBeam) e os
  filtros físicos do VitalBeam e do 600CD têm tabela própria ou ficam
  explicitamente sem tabela. Hoje FFF e filtros estão fora do PPR
  (`PENDENCIAS.md`, pendências 9, 13 e 14).
- Para o cálculo de modulado, a tabela traz também a transmissão do MLC e o
  DLG, com a origem da medida.
- Cada tabela registra quem atesta que ela ainda representa a máquina
  (reparos, troca de componente, recomissionamento desde a medida); a do
  600CD é de 2010.

#### FR-11: Disparo da segunda checagem

A segunda checagem roda quando o plano entra em `Planning Approved` (lido do
`variandw`, como o gatilho de `banco/gatilho_db.py`) e o RT Plan está
disponível.

**Consequências:**

- O resultado está pronto antes de o plano aparecer na fila de Aprovação
  Física. `[SUPOSIÇÃO]` "Junto do PSQA" é lido como: disparo na aprovação
  médica, sem depender do PSQA.
- Plano novo ou modificado (D03, replanejamento) dispara nova checagem com o
  mesmo prazo de verificação contado do novo plano (RDC 20, 9.7 (c)); a
  anterior fica no log e deixa de valer para a versão nova.
- O RT Plan checado é o plano aprovado no ARIA: o `SOPInstanceUID` do arquivo
  é igual ao do registro no `variandw`. Se o RT Plan não chegar ou o UID não
  bater, a checagem sai `indeterminado` com alerta (FR-41); nunca deixa de
  rodar em silêncio.

#### FR-12: Resultado por campo e composto, com limite citado

A checagem mostra a diferença calculado × TPS por campo e no composto, o
limite aplicado e a origem do limite.

**Consequências:**

- Plano 3D convencional: limites do TG-114 (Tab. II p. 8), em três níveis,
  2% / 3,5% / 5% conforme a geometria e a heterogeneidade.
- Plano modulado (Clarkson por ponto de controle, §15, P3): aceitação pelo
  plano composto (TG-219 p. 17), 3% homogêneo / 5% heterogêneo; campo único
  5% / 7%; baixa dose ou alto gradiente 5–10% (TG-219 Tab. 9 p. 12).
- O ponto de cálculo nunca é trocado para fazer o resultado passar (TG-219
  p. 16); trocar o ponto gera nova execução e as duas ficam no log.
- Todo limite aparece com "origem: literatura, não derivado do serviço"
  enquanto não houver derivação local (R-10); `nao_conforme` contra limite de
  literatura é alerta, não reprovação (`docs/qms/revisao-clinica.md`,
  regra 6).
- Os limites do código atual (3% / 5% por campo; 10% / 20% para campo
  modulado, sem fonte citada) são substituídos pelos do TG-114 e do TG-219
  (decisão do usuário, 19/10/2026; §15, P4).
- A tela e o relatório da segunda checagem mudam de texto (sai
  "demonstração", entram `indeterminado` e a origem do limite). Nenhum
  documento impresso mostra o resultado do paralelo (conferido no código em
  19/10/2026: nada em `papel/` usa o paralelo; §15, P10): o papel não muda.

#### FR-13: Máquina sem tabela, técnica não tratada

Plano de máquina sem tabela cadastrada, ou com técnica que o cálculo não
trata, sai `indeterminado` com o motivo.

**Consequências:**

- Campo com filtro físico sai `indeterminado` ("o cálculo não trata filtro")
  enquanto o `paralelo.py` não tratar filtro.
- Campo modulado (IMRT/VMAT) é calculado pelo Clarkson por ponto de controle
  (§15, P3). Enquanto a máquina não tiver o comissionamento de modulado
  aprovado (FR-14), o resultado é `indeterminado` com o motivo, e a
  obrigação do art. 15, XI, e fica cumprida só para 3D naquela máquina
  (§12.3).
- O resultado `demonstracao` do código atual deixa de existir no MVP: sem
  tabela da máquina é `indeterminado`.

#### FR-14: Comissionamento do próprio cálculo

O físico pode registrar o comissionamento da segunda checagem por máquina:
pontos da Tab. 8 do TG-219 e casos TG-119, medido × calculado.

**Consequências:**

- Enquanto a máquina não tiver a conversão da tabela validada (FR-10) e o
  comissionamento registrado e aprovado pelo físico, a checagem mostra o
  valor calculado sem veredito: resultado `indeterminado`, motivo "cálculo
  não comissionado para esta máquina".
- No 3D, pontos da Tab. 8 do TG-219; no modulado, casos TG-119, medido ×
  calculado. O TG-119 está fora do acervo e precisa entrar antes (§15, B1).
- O relatório de comissionamento entra no relatório de validação do módulo
  (FR-40).

#### FR-15: Prazo da segunda checagem

O ISOCENTRO acompanha, por plano, se a segunda checagem foi feita e
conferida dentro do prazo de verificação.

**Consequências:**

- O plano sem segunda checagem conferida é alertado em `alta` ao atingir o
  prazo de verificação (3ª fração ou 10% da dose, o que vier primeiro); no
  caso de alto risco, antes da 1ª fração.
- A contagem de frações vem do tratamento entregue (`banco/tratamento_db.py`)
  e herda o estado da lista (`LISTA_VERIFICADA_EM`): curso sem a data mostra
  "contagem de frações não conferida contra o ARIA". A R-07 fecha antes do
  MVP 2 (§15, P12); o aviso fica como rede de segurança.
- A dose acumulada dos 10% é a registrada no ARIA; os 10% são calculados
  sobre o curso e sobre a fase, e o alerta dispara pelo que vencer primeiro,
  dizendo qual venceu (físico, 26/10/2026; §15, P5). Provisório até a
  discussão no serviço (`decisoes-sem-base.md`, #3).
- Se a contagem passar a usar o `dominio/ritmo` (classe A), a classe dele
  precisa ser revista, porque passa a definir prazo clínico (§15, G2).

**Notas:** a ficha H01 fala em "quatro máquinas Varian"; a atividade H01
está como RECOMENDAÇÃO no `atividades.csv` e como obrigatória na ficha.
Corrigir na base (§15, B1).

#### FR-43: Índices de qualidade do plano

Os índices de qualidade e de complexidade da aba Qualidade (hoje no
Radioteraficha, `dominio/qualidade.py`) passam para o módulo Plano como
verificações dele (decisão do usuário, 19/10/2026; §15, U1).

**Consequências:**

- Conformidade, gradiente, HI (ICRU 83), MCSv, SAS e UM/cGy viram
  verificações, cada uma com tolerância e origem da literatura, marcadas
  provisórias até a derivação TG-218 (R-10).
- "Fora da faixa" é alerta, nunca reprovação.
- A tela Virtual não vem para o Plano.
- O papel não muda: a aba não imprime nem exporta.

## 6. Módulo Plano — revisão com segunda assinatura e sequência real (MVP 2)

**Descrição:** cumpre a NN-6.10, art. 17, IV (segunda assinatura por
conferência) e o prazo da RDC 20, 9.7 (c). O fluxo é o que o serviço faz
hoje, e o ISOCENTRO **mede e alerta a partir do dado**, sem impor ordem:
aprovação médica (`Planning Approved`) → PSQA → Aprovação Física pelo físico
do caso (dá o `Treatment Approved`) → Duplo Check por outro físico → 1ª
fração. As listas de itens são as votadas pelo serviço em 30/03/2026
(`servico/lista-verificacao-carepath.csv`: Planejamento 13, Aprovação Física
8, Duplo Check 8), com os itens "++" do TG-275 automatizáveis (marcados F)
conferidos do RT Plan e do ARIA. O módulo parte do checklist pré-tratamento
(`interface/checklist.py`, 6 itens) e do `dicom/dicom_rt.py`. Realiza UJ-1 e
UJ-2.

#### FR-16: Leitura da sequência real

O ISOCENTRO lê do `variandw`, por plano, as datas de aprovação médica, PSQA,
Treatment Approved, Duplo Check e 1ª fração.

**Consequências:**

- Cada data mostra a fonte (tabela e campo do `variandw`) e o degrau.
- Data que não foi encontrada nasce vazia e a tela diz que falta; nunca é
  inferida de outra.
- `[SUPOSIÇÃO]` O PSQA e o Duplo Check são lidos como atividades do Carepath
  no `variandw`; os códigos reais ainda não foram mapeados (hoje
  `banco/atividades_db.py` só lê `Documentação` e `Verificar Programação`).
  Mapear é pré-requisito (§15, P6).
- O Duplo Check tem duas fontes: a assinatura no ISOCENTRO (FR-20) e a
  atividade do Carepath no `variandw`. `[SUPOSIÇÃO]` A assinatura no
  ISOCENTRO é o registro da segunda assinatura; a data do `variandw` aparece
  ao lado, e a divergência entre as duas (só uma existe, ou datas diferentes)
  gera alerta `atencao`. A lista votada inclui "mudar a data do Duplo Check se
  necessário": a data do `variandw` pode mudar, e a mudança é mostrada.

#### FR-17: Fila de Duplo Check com prazo

O físico vê a fila de planos sem Duplo Check, ordenada pelo prazo.

**Consequências:**

- Plano sem Duplo Check é alertado em `alta` ao atingir o prazo de
  verificação (3ª fração ou 10% da dose, o que vier primeiro).
- Caso de alto risco sem Duplo Check é alertado em `alta` se a 1ª fração
  ocorrer sem ele.
- Plano tratado sem Duplo Check registrado aparece na fila com a contagem de
  frações e a observação do FR-15 sobre a lista não conferida.

#### FR-18: Marcação de alto risco

O ISOCENTRO marca o caso de alto risco a partir do dado e o físico pode
marcar à mão.

**Consequências:**

- SBRT/hipofracionamento é marcado pela prescrição e pelo agendamento, o que
  disparar primeiro: dose por fração ≥ 6 Gy, nº de frações ≤ 5 ou curso em
  menos de 6 dias (TG-101 p. 3; TG-275 p. 4 e p. 14; físico, 26/10/2026; §15,
  P8). A duração vem do agendamento no `variandw`; sem agendamento, esse
  critério fica "não informado". Provisório para a faixa de 3 a 6 Gy por
  fração, que a base não cobre (`decisoes-sem-base.md`, #7).
- Reirradiação e dispositivo implantado não têm campo no ARIA lido hoje:
  nascem como "não informado" e o físico marca. A marcação registra quem e
  quando (C09).
- Enquanto reirradiação (ou campo adjacente) ou dispositivo implantado
  estiver "não informado", o caso é tratado como de alto risco: prazo antes
  da 1ª fração, com alerta próprio "alto risco não avaliado". O prazo comum
  só vale depois de o físico marcar esses critérios como ausentes e de a
  prescrição não indicar SBRT ou hipofracionamento.

#### FR-19: Lista de conferência da Aprovação Física e do Duplo Check

O físico confere o plano pela lista votada da etapa, com os itens
automatizáveis já preenchidos pelo ISOCENTRO. As duas listas são diferentes
(`servico/lista-verificacao-carepath.csv`):

| Aprovação Física (8) | Duplo Check (8) |
| --- | --- |
| Distribuição de dose e DVH | Luz de campo em mama |
| Dose diária e total × prescrição | Dose diária e total × prescrição |
| Máquina correta | Fases diferentes no mesmo isocentro |
| Dias alternados | UM compatíveis com a dose |
| Curva de 4D | Análise do planejamento (DVH) |
| Concluir cursos anteriores | Coordenadas do isocentro e localização |
| Orientações de agendamento | Máquina correta |
| Se dose única, imprimir alta | Mudar a data do Duplo Check, se necessário |

Na Aprovação Física, "UM compatíveis", "normalização e ponto de referência",
"contraste/artefatos" e "zerar origem" foram removidos por maioria e não
entram.

**Consequências:**

- Cada item automatizável mostra o valor lido, a fonte (RT Plan ou campo do
  `variandw`), o valor de referência com a fonte dele e o resultado; o físico
  confirma ou contesta. Item sem valor de referência nasce vazio, nunca
  `conforme`.
- Candidatos a automático no MVP: dose diária e total × prescrição e máquina
  correta (as duas etapas); UM compatíveis (Duplo Check, pela segunda
  checagem); coordenadas do isocentro e fases no mesmo isocentro (Duplo
  Check); cursos anteriores abertos (Aprovação Física, do `variandw`).
  Referências (físico, 26/10/2026; §15, P7): máquina da prescrição e do
  agendamento iguais entre si e à do RT Plan; curso anterior aberto = status
  diferente de concluído; isocentro em quatro conferências (mesmo
  `IsocenterPosition` em todos os campos; isocentro − TP0 = deslocamentos de
  setup; mesmo isocentro entre fases no mesmo `FrameOfReferenceUID`, com
  divergência para o físico confirmar; isocentro dentro do BODY), sem
  veredito até haver tolerância em mm.
- Também entram os itens "++" com "F" da Tab. S1.A.ii do TG-275 (p. 21) e
  os 160 itens nível 2 do MPPG 11.a, como catálogo: automatizáveis em sombra
  até a conferência linha a linha, manuais opcionais e vazios. As listas
  votadas não mudam (spec do Plano, CAP-18).
- O resultado da segunda checagem é um item da Aprovação Física e do Duplo
  Check; `nao_conforme` ou `indeterminado` pede justificativa, sem bloquear.

#### FR-20: Segunda assinatura

O físico do Duplo Check assina no ISOCENTRO ao concluir a lista.

**Consequências:**

- O ISOCENTRO recusa registrar como Duplo Check a assinatura do mesmo
  usuário que deu a Aprovação Física (o Treatment Approved lido do ARIA ou a
  assinatura da Aprovação Física no ISOCENTRO).
- O usuário do ARIA é ligado ao usuário do ISOCENTRO por um mapeamento
  cadastrado e explícito, nunca por parecença de nome. Sem mapeamento, ou no
  degrau de reserva sem o autor do Treatment Approved, a assinatura é
  registrada com a marca "separação entre os físicos não conferida" e gera
  alerta `alta`.
- A assinatura segue o FR-8 e volta a pendente se o RT Plan mudar.
- O ISOCENTRO não grava nada no ARIA; a assinatura vive no ISOCENTRO.

**Fora deste FR:**

- Mudar o papel: o plano impresso com segunda assinatura (art. 17, IV)
  continua como hoje. `[SUPOSIÇÃO]` Se a assinatura registrada passar a
  substituir a do papel, é mudança do que sai impresso e exige aviso (§15, P11).

#### FR-21: Conferência de identificação e prescrição

Na etapa de Planejamento, o ISOCENTRO confronta a prescrição do ARIA com o
RT Plan: dose total, dose por fração, número de frações, energia, técnica.

**Consequências:**

- Divergência gera `nao_conforme` com os dois valores e as fontes.
- A prescrição vem de tabela e campo do `variandw` citados (a nota já vem de
  `DWH.DimPrescription.Notes`, NOTAS 23/09/2026). Energia e técnica do ARIA
  são casadas com as do RT Plan por tabela de equivalência cadastrada (por
  exemplo "6X" ↔ "06 MV"); valor sem equivalência sai `indeterminado`.
- `[SUPOSIÇÃO]` Os itens que a RDC 20, 9.1 pede e o checklist atual não tem
  (gravidez, tratamento anterior, dispositivo implantado, consentimento)
  entram como itens de registro manual, nascendo vazios (C01, C09).

#### FR-42: Lista de Planejamento

O dosimetrista confere o plano pela lista votada da etapa Planejamento (13
itens), antes da aprovação médica, com os itens automatizáveis preenchidos.

**Consequências:**

- Os 13 itens são os do `lista-verificacao-carepath.csv` (nome do plano,
  luz de campo em mama, tolerância de mesa, margem dos PTVs, distribuição de
  dose e DVH, dose diária e total × prescrição, matriz de cálculo, fases no
  mesmo isocentro, contraste e artefatos, zerar origem da imagem, UM
  compatíveis, coordenadas do isocentro, máquina correta).
- A lista conferida registra quem e quando; não é assinatura de segunda
  conferência.
- `[SUPOSIÇÃO]` Os itens automatizáveis seguem a regra do FR-19 (fonte e
  referência explícitas, vazio quando falta).

## 7. Módulo Garantia da Qualidade — registro do programa de CQ (MVP 3)

**Descrição:** cumpre a NN-6.10, art. 35 e art. 71, IX, e a RDC 20, 8.1 (b).
O programa de CQ é o `programa-cq.csv` da base (103 testes: 22 diários, 1
semanal, 31 mensais, 1 semestral, 36 anuais e 12 de ortovoltagem), gerado por
clínica e máquina em `servico/<CLÍNICA>/qualidade.json`, somado aos itens
nível 2 de equipamento da pesquisa de protocolos. Cada teste já tem
tolerância e referência. O modelo de dados segue o do QATrack+ (lista de
testes, instância, tolerância, ação, frequência); o pylinac analisa os testes
de imagem (FR-46). O módulo também é dono dos instrumentos de medida, da
aferição com decaimento (FR-36) e da calibração TRS-398 (FR-45). Realiza
UJ-3.

#### FR-22: Programa de CQ por clínica e máquina

O ISOCENTRO carrega o programa de CQ de cada clínica a partir do
`qualidade.json` gerado da base, sem digitação.

**Consequências:**

- Cada teste aparece com tipo, tolerância, referência e máquina como no
  arquivo.
- Mudar um teste é mudar o `programa-cq.csv` na base e regerar; o ISOCENTRO
  registra a versão do programa em uso.
- `[SUPOSIÇÃO]` O TrueBeam ganha a etiqueta `fff` (comissionado em 6FFF e
  10FFF) antes da carga. Correção na base, a confirmar (§15, B1).
- Entram também os itens nível 2 de equipamento
  (`research-tabelas-protocolos-2026-10-13/digests/itens-nivel2.csv`): MPPG
  8.b, 2.b e 9.b, TRS-398 Rev. 1, adendo TG-51 e TECDOC-1274. Viram teste só os
  que têm tolerância, nível de ação ou constância (cerca de 97). Os
  "recomendado" e "opcional" ficam como referência, ativáveis pelo físico
  (decisão do usuário, 19/10/2026).
- Os itens do MPPG 11.a (revisão de plano e prontuário) vão para o módulo
  Plano e os do MPPG 5.b (comissionamento do TPS) para Software e sistemas.
- Item repetido entre o programa e o nível 2 vira um teste com as duas
  referências, depois de o físico confirmar.
- A instância por máquina sai do cadastro de máquinas cruzado com as
  etiquetas de aplicação do programa (`todas`, `kv`, `epid`, `eletrons`,
  `fff`, `edw`, `srs`, `orto`).

#### FR-23: Registro de execução

O técnico ou o físico registra a execução de um teste: valor, resultado,
equipamento de medida, quem e quando.

**Consequências:**

- O resultado é calculado pela tolerância do teste; o usuário não digita
  "conforme".
- Teste sem tolerância numérica (funcional) é registrado como passa/falha
  com o texto da tolerância.
- Resultado fora da tolerância alerta o físico no mesmo dia (FR-41) e mostra
  a ação prevista, se houver. O `programa-cq.csv` não tem coluna de ação
  hoje: a ação de cada teste nasce vazia e é cadastrada pelo físico.
- As tolerâncias do programa vêm da literatura (TG-142, MPPG-8b, TRS) e da
  NN-6.10. Cada teste mostra a origem.
- Resultado fora da tolerância é `nao_conforme` com alerta `alta`: a
  tolerância de CQ de máquina é limite de aceitação, não índice de plano
  (decisão do usuário, 19/10/2026; §15, C1). Nada é bloqueado.
- A execução dosimétrica cita o instrumento cadastrado (FR-44).

#### FR-24: Teste vencido sem registro

Um teste do programa que passa da frequência sem execução gera alerta.

**Consequências:**

- `[SUPOSIÇÃO]` O diário não registrado até o início do primeiro tratamento
  do dia alerta o físico.
- Semanais, mensais, semestrais e anuais, e as frequências de ortovoltagem
  (diária, mensal e anual do Dermopan), entram no painel de vencimentos
  (FR-34).

#### FR-25: Carta de controle

O físico vê a carta de controle do output diário de cada máquina e energia.

**Consequências:**

- A carta mostra o limite de tolerância com a origem (literatura ou
  serviço); limite de ação só quando cadastrado (FR-23).
- `[SUPOSIÇÃO]` A detecção de tendência antes de estourar a tolerância
  (aceite da Fase 4 do brief) fica para depois do MVP; no MVP, a carta mostra
  os pontos e os limites.

#### FR-26: Importação de exportações de medida

O ISOCENTRO pode importar as exportações do DailyQA 3 e do MapCHECK como
evidência da execução.

**Consequências:**

- O arquivo importado fica guardado com a execução.
- Exportação que traz identificação de paciente (MapCHECK de PSQA) fica na
  pasta do paciente ou é pseudonimizada antes de ir para o registro de CQ
  (NFR-2). `[SUPOSIÇÃO]` No MVP, só exportações de CQ de máquina são
  importadas.
- `[SUPOSIÇÃO]` O formato das exportações ainda não foi levantado; se não
  der para ler, o arquivo entra como anexo e o valor é digitado.

#### FR-27: Braquiterapia HDR no programa

O programa de CQ inclui os testes de HDR da CEL (E03, E06): diários de
segurança, posição da fonte, e os testes por troca de fonte.

**Consequências:**

- A troca de fonte é um evento que gera os testes da troca, incluindo a
  medida de S_K antes do uso, exigida pela NN-6.10 (art. 35, V). A
  tolerância medido × certificado vem do MPPG-HDR (Tab. 4 p. 10: 3% como
  meta, 5% como limite), que é recomendação.
- Os testes de HDR seguem a ficha E03: segurança diária (art. 35, III);
  recolhimento, temporizador, cofre, pinça e cortador (art. 63); posição da
  fonte diária 1 mm (TECDOC Tab. X); atividade no console × tabela 1%;
  bateria, data e hora, kit de emergência.
- Até a medida de S_K ser registrada, a fonte nova aparece como "não
  liberada" — alerta `alta`, sem bloqueio.
- Os testes de HDR entram no `programa-cq.csv` antes da carga (hoje ele só
  cobre acelerador e ortovoltagem).

#### FR-28: Cópia de segurança

Os registros de CQ têm cópia de segurança.

**Consequências:**

- Um teste de restauração prova que os registros voltam íntegros e que o log
  encadeado continua válido depois da restauração.
- A cópia é independente do original (NN-6.10 art. 71, IX) e fica na rede do
  serviço (NFR-2).
- Os registros são guardados pelo mais longo de dois prazos: enquanto o
  equipamento existir (RDC 20, 8.1 (b)) e no mínimo 10 anos após o descarte
  do software; não há caminho de descarte no MVP (físico, 26/10/2026; §15,
  C7).

#### FR-44: Cadastro de instrumentos de medida

O físico cadastra os instrumentos de medida com o certificado, e cada tipo
tem a periodicidade da norma.

**Consequências:**

- Cada instrumento tem modelo, número de série, laboratório, data e N_D,w
  (ou S_K/N_K na câmara poço) do certificado.
- Periodicidades: sistema de referência a cada 2 anos e aferição
  trimestral ±1% (art. 49, III; prevalece sobre os 3 anos do TRS-398);
  barômetro e termômetro 2 anos, régua e nível 5 anos (art. 52); câmara poço
  HDR 2 anos e aferição trimestral (art. 54); monitor de área 2 anos
  (art. 55).
- Conserto, suspeita de dano ou transporte registrados fazem a calibração ou
  a aferição vencer na hora (art. 49 p.ú. I, II, IV; arts. 54, 55).
- Instrumento ausente ou vencido deixa `indeterminado` o teste que depende
  dele.
- Os prazos aparecem no painel de vencimentos (FR-34), que os lê deste
  módulo (decisão do usuário, 19/10/2026).

#### FR-36: Aferição com decaimento

O físico registra a aferição com fonte-teste (sistema de referência) ou com
a fonte de Ir-192 (câmara poço do HDR), e o ISOCENTRO corrige o decaimento e
compara com ±1%. (Movido do §9 para este módulo em 19/10/2026; o ID se
mantém.)

**Consequências:**

- O nuclídeo, a meia-vida (com referência) e o valor e a data de referência
  da fonte vêm do cadastro da fonte; campo vazio deixa a aferição
  `indeterminado`. Para o Sr-90, a ficha A05 cita meia-vida de 28,8 anos.
- O resultado mostra o valor esperado corrigido, o medido, a diferença e a
  tolerância com a fonte (NN-6.10 art. 49, p.ú., III; art. 54, p.ú.).

#### FR-45: Calibração TRS-398 calculada

O ISOCENTRO calcula a dose absorvida em condição de referência pelo TRS-398,
em vez de só registrar o resultado (decisão do usuário, 19/10/2026).
Atualizado em 26/10/2026 pela decisão do físico (§15, C5): k_Q da edição de
2000, não da Rev. 1.

**Consequências:**

- D_w,Q = M × k_TP × k_pol × k_s × k_elec × N_D,w × k_Q, com k_Q do TRS-398
  de 2000 para a câmara cadastrada (Tab. 6.III da V.12 de 2006; FC65-G e
  FC65-P pela atualização IAEA de 2002) e N_D,w do certificado atual
  (FR-44), que é posicionado pela edição de 2000. O conjunto de k_Q e o
  certificado ficam registrados com cada execução.
- O resultado é comparado à saída nominal com 1% (IT0004).
- Cada fator mostra valor e origem; fator sem fonte nasce vazio, e o
  resultado fica `indeterminado`.
- Antes de dar veredito, o cálculo reproduz a planilha atual do serviço em
  casos conferidos à mão.
- O cálculo define a dose de todos os pacientes: é item próprio de classe C
  (`classificacao-62304.md`, 26/10/2026), puro e sem tela; o resto do GQ é
  classe A.

#### FR-46: Análise de imagem pelo pylinac

Os testes de imagem do programa recebem o valor da análise automática do
pylinac (decisão do usuário, 19/10/2026).

**Consequências:**

- Picket fence, Winston-Lutz, fantomas de kV/CBCT e os demais testes de
  imagem do programa; o valor sai da análise, nunca é digitado.
- A versão do pylinac e os parâmetros ficam registrados com a execução; a
  imagem fica guardada com hash.
- Cada análise é comissionada contra imagens de resultado conhecido antes de
  dar veredito; sem isso, o resultado é `indeterminado`.
- Origem das imagens a levantar (§15, C4).

**Notas:** pendências do serviço que afetam o MVP 3 (`PENDENCIAS.md`): câmara
≤ 0,03 cm³ para SRS na CEL, câmara < 0,1 cm³ para IMRT na BET, dispositivo
de QA da DUO não declarado. O ISOCENTRO registra o teste; a falta do
instrumento aparece como `indeterminado` no teste que depende dele.

## 8. Módulo Segurança do paciente — incidentes e quase-incidentes (MVP 4)

**Descrição:** cumpre a NN-6.10, art. 26 (investigação imediata, relatório à
ANSN em 30 dias, aviso escrito ao paciente e ao médico) e a RDC 36/2013
(notificação mensal pelo NSP até o 15º dia útil do mês seguinte; óbito em
72 h). O módulo parte da spec do módulo de incidentes v0.1
(`../incidentes/SPEC - Módulo incidentes v0.1.md`), corrigida para citar a
NN-6.10 pela Res. 277/2021 consolidada. O ISOCENTRO é o sistema próprio de
registro e notificação interna ao NSP, no lugar do Epimed (decisão do
usuário, 26/10/2026). A notificação legal segue no Notivisa (RDC 36, art.
10) e o relatório do art. 26 segue à ANSN por requerimento; o ISOCENTRO
prepara, acompanha prazo e guarda número e protocolo, sem enviar. Realiza
UJ-5.

#### FR-29: Registro de incidente e quase-incidente

Qualquer perfil pode registrar um incidente ou quase-incidente com etapa
onde ocorreu, etapa onde foi detectado, gravidade, descrição e fatores
causais (modelo Ford 2012; taxonomia WHO-ICPS).

**Consequências:**

- "Detectado em" e "onde ocorreu" usam a mesma lista: o mapa de processo do
  Ford 2012 (8 macroetapas; 91 passos de teleterapia e 88 de braquiterapia,
  com a marca de barreira de segurança), uma lista para as três clínicas.
  Quem relata escolhe a macroetapa (e o passo, se souber); a análise refina
  "onde ocorreu" (físico, 26/10/2026; I4).
- Desvio de dose pela escala do Ford 2012 (< 5% a > 100% e "não se
  aplica"); local e volume pelo TG-100 (3–5 mm; > 5 mm); dano clínico pela
  WHO-ICPS, em campo separado (físico, 26/10/2026; I4).
- O registro liga ao paciente e ao plano por identificador do ARIA, sem
  copiar dado clínico além do necessário.
- O texto livre e a dose estimada só são lidos pelo físico, pelo SPR/gestão
  e pelo próprio notificador (decisão do usuário, 19/10/2026; §15, I2); os
  demais perfis veem tipo, etapas e status. O log guarda o hash e a mudança,
  e o relatório exportado sai sem identificação do paciente.
- A notificação é identificada no log, mas tela, triagem, revisão, matriz e
  relatório não mostram quem notificou (decisão do usuário, 19/10/2026).

#### FR-30: Prazos do art. 26 e da RDC 36

Um incidente marcado como exposição médica não intencional abre o prazo de
30 dias e a lista do art. 26.

**Consequências:**

- A data de identificação é obrigatória e o prazo conta dela.
- A lista do art. 26 tem: investigação iniciada (imediata), dose estimada e
  distribuição, medidas corretivas, medidas para prevenir reincidência, aviso
  escrito ao paciente, aviso escrito ao médico solicitante, relatório à ANSN
  (NN-6.10 art. 26; ANSN 3.01 art. 98, II), registro no livro de ocorrências
  radiológicas e ciência de todos os IOEs (guia CNEN 2020); cada item com
  quem e quando.
- Alerta `alta` desde a identificação até "investigação iniciada" (art. 26,
  "imediatamente").
- O relatório sai com os itens a–k do guia CNEN 2020, assinado por titular,
  SPR, responsável técnico e físico; o ISOCENTRO guarda o protocolo.
- `[SUPOSIÇÃO]` Alerta `atencao` aos 20 dias sem relatório; `alta` vencido
  aos 30 (sem base: `decisoes-sem-base.md` #28).
- Os prazos da RDC 36 são acompanhados em paralelo (FR-31).

#### FR-31: Notificação ao NSP e prazos do Notivisa

O ISOCENTRO é o canal interno de notificação ao NSP e organiza o evento nas
10 etapas do formulário Notivisa (NT GVIMS 09/2025).

**Consequências:**

- Etapas 1–4 em todo evento; 5–10 em óbito e never event (lista da Anvisa).
- Prazos: 15º dia útil do mês seguinte; 72 h do ocorrido no óbito; 60 dias
  corridos da notificação para concluir as etapas 5–10 em óbito e never
  event (RDC 36, art. 10; NT GVIMS 09/2025).
- O usuário registra data e número da notificação no Notivisa; evento sem
  número no prazo é alertado.
- O ISOCENTRO não envia ao Notivisa: o envio exige login do usuário
  cadastrado do NSP.
- `[SUPOSIÇÃO]` Só sábado, domingo e feriado nacional deixam de contar como
  dia útil (`decisoes-sem-base.md` #29).

#### FR-32: Revisão periódica

O físico vê os incidentes e quase-incidentes do período agrupados por etapa
onde ocorreu e onde foi detectado.

**Consequências:**

- Triagem semanal dos eventos novos pelo físico e revisão trimestral com a
  ata registrada (decisão do usuário, 19/10/2026; G15).

#### FR-47: Ciclo de análise e vínculo à FMEA

Cada evento é conduzido até o fechamento e ligado ao modo de falha do
`docs/qms/riscos.md` (decisão do usuário, 19/10/2026; vem da spec v0.1 de
incidentes).

**Consequências:**

- Estado aberto → em análise → ação definida → fechado; cada transição com
  quem e quando; ação corretiva e de prevenção com responsável e prazo; ação
  vencida alerta.
- O vínculo é pelo evento iniciador da matriz de risco (FR-49) e pela
  barreira que falhou ou segurou; a contagem por evento propõe o O do
  TG-100. O `riscos.md` é o risco do software: só incidente causado pelo
  próprio ISOCENTRO se liga a uma linha dele, e o ISOCENTRO não escreve
  nele (26/10/2026).

#### FR-48: Matriz ocorrência × detecção e indicadores

O físico vê onde o erro nasce e onde é pego, e indicadores normalizados
(decisão do usuário, 19/10/2026; vem da spec v0.1 de incidentes).

**Consequências:**

- Matriz de calor etapa de ocorrência × etapa de detecção, por período e
  clínica.
- Taxa por 1.000 frações (denominador do `variandw`, com degrau e data),
  razão quase-incidente/evento e tempo até fechar; sem denominador, a taxa
  nasce vazia.
- No relatório exportado, células com menos de 5 casos são suprimidas.
- A taxonomia é validada antes do uso: 30 incidentes históricos
  classificados por dois físicos, kappa ≥ 0,7.

#### FR-49: Matriz de risco em tempo real

O ISOCENTRO mantém a matriz de risco do processo clínico por prática, com o
nível de cada evento iniciador acompanhando o estado medido das barreiras
(decisão do usuário, 26/10/2026). Hoje a análise é o SEVRRA, declarado e
estático (PPR da CEL, jan/2023).

**Consequências:**

- Os dois métodos ligados: eventos iniciadores, barreiras e redutores da
  matriz de risco (SEVRRA) como espinha, com O, S, D do TG-100 em cada
  evento; o catálogo é carregado pelo físico, com fonte por linha.
- O estado de cada barreira vem das verificações da GQ, do Plano e da
  Segurança; o ISOCENTRO propõe a mudança de nível e o físico confirma.
  Barreira sem dado conta como não funcionando.
- Perfil RB/RM/RA/RMA por prática e etapa, atual e de referência, com
  histórico; proposta de subida a RA/RMA alerta o físico.
- O SEVRRA continua sendo feito em paralelo até a CNEN aceitar a matriz
  própria como a análise de risco do PPR.

## 9. Módulo Documentação e conformidade — vencimentos (MVP 5)

**Descrição:** cumpre os prazos da NN-6.10 (arts. 20, 24, 29, 36, 49, 52, 54,
55). Hoje os vencimentos ficam no `ppr-streamlit`; passam para o ISOCENTRO,
pelo gatilho de prazo, sem código específico de PPR (aceite da Fase 2 do
brief). Realiza UJ-4.

#### FR-33: Cadastro de itens com vencimento

O físico ou a SPR cadastra itens com obrigação periódica: treinamento,
auditoria, ASO, levantamento radiométrico, autorização, SEVRRA e monitoração
individual. Instrumentos, certificados de instrumento e aferição são do
módulo Garantia da Qualidade (FR-44, FR-36) e só aparecem no painel
(decisão do usuário, 19/10/2026).

**Consequências:**

- Cada tipo vem com a periodicidade e a fonte: treinamento de PR anual (art.
  20, VI); treinamento de física médica até 2 anos (art. 24, I, f); auditoria
  externa até 2 anos (art. 36); levantamento radiométrico até 2 anos e após
  modificação (art. 29); ASO 1 ano do exame, ou menos se o PCMSO fixar
  (NR-7 7.5.8, II, a), para todo IOE; Autorização para Operação da CNEN e
  alvará sanitário como dois tipos, cada um pela data do documento (SAES
  1399 art. 16, d); SEVRRA sem data até haver fonte (V1, V3; 26/10/2026).
- Cada data de partida é lançada do documento de origem da clínica e o
  cita; item sem documento nasce "sem data" (V2; 26/10/2026).
- Além do calendário, há vencimento por evento: modificação da instalação
  (levantamento, art. 29); retorno ao trabalho após 30 dias ou mais,
  mudança de risco e dose acima do limite anual (ASO, NR-7 7.5.9 e Anexo
  V). O evento registrado faz o item vencer na hora.
- A lista de IOEs é a marca "IOE" por pessoa e clínica no cadastro de
  equipe do núcleo, mantida pelo SPR e conferida contra o PPR a cada
  revisão; IOE é quem trabalha em área controlada ou supervisionada (NN-3.01
  arts. 57 e 60; V3; 26/10/2026).
- `[SUPOSIÇÃO]` PCMSO de cada clínica, chave da autorização no
  `ppr-streamlit`, periodicidade do SEVRRA e IOE por perfil seguem a opção
  provisória de `decisoes-sem-base.md` #18–21.
- Do ASO, o ISOCENTRO guarda só a pessoa, a data do exame e a validade; nem o
  PDF nem o resultado (apto/inapto). Só SPR/gestão e o físico responsável leem
  (decisão do usuário, 19/10/2026).
- Da monitoração individual mensal de cada IOE (art. 20, IV–V), o ISOCENTRO
  guarda só "resultado do mês recebido", com data, sem valor de dose (decisão
  do usuário, 19/10/2026).
- Item sem data de partida nasce "sem data" e aparece no painel como tal,
  nunca como em dia.

#### FR-34: Painel de vencimentos

O usuário vê o que vence, por clínica, numa janela configurável.

**Consequências:**

- Aviso prévio configurável por tipo; `[SUPOSIÇÃO]` padrão de 60 dias
  (proposto na ficha A04).
- Vencido aparece em `alta`; dentro do aviso, em `atencao`.
- O painel inclui os testes de CQ mensais, semestrais e anuais (FR-24) e os
  prazos de instrumentos e aferições (FR-44, FR-36), lidos do módulo Garantia
  da Qualidade.

#### FR-35: Migração do ppr-streamlit

Os vencimentos que estão no `ppr-streamlit` passam para o ISOCENTRO.

**Consequências:**

- O JSON do `ppr-streamlit` entra como conferência, não como fonte (V2).
- A migração gera um relatório item a item: casou com o documento,
  diverge, não importado. Divergência, até resolvida, usa a data que vence
  mais cedo.
- A extração de ASO é local, sem enviar texto a terceiros (R-15); enquanto a
  R-15 não estiver feita, o ASO é cadastrado à mão.
- Os certificados de instrumento migrados vão para o módulo Garantia da
  Qualidade; depois do corte, o `ppr-streamlit` deixa de ser fonte de
  vencimento.

O FR-36 (aferição com decaimento) passou para o §7 em 19/10/2026.

## 10. Módulos fora do MVP e o que o MVP já toca

| Módulo | No MVP | Depois |
| --- | --- | --- |
| Plano | MVP 1 e 2 (com modulado e índices de qualidade) | Itens do MPPG 11.a; plan check com ~20 regras de maior RPN (TG-275), com sensibilidade semeada > 0,85 e menos de 1 falso positivo por plano (aceite da Fase 3 do brief); regras de PlanCheck, uhg-plancheck e PlanScoreCard (ESAPI); SRS (`srs-streamlit`); constraints (área I); nomenclatura TG-263 |
| Tratamento | Leitura da 1ª fração e da contagem (FR-15, FR-16) | Painel de revisão semanal (área D) |
| Garantia da Qualidade | MVP 3 (com pylinac e TRS-398 calculado) | Tendência na carta de controle; derivação TG-218 das tolerâncias |
| Documentação e conformidade | MVP 5 | PPR no ISOCENTRO; POPs com versão; auditoria espelhada |
| Segurança do paciente | MVP 4 (com matriz, indicadores e vínculo à FMEA) | Envio automático ao Notivisa ou à ANSN; notificar de qualquer tela; pseudonimização (deid, dicognito) |
| Indicadores | — | Radioteradados (PRD e arquitetura próprios), absorvido como módulo |
| Software e sistemas | FR-37 a FR-40 | Ciclo ISQM completo; aprovação de script ESAPI no Eclipse (B06); itens do MPPG 5.b (comissionamento do TPS) |
| Conhecimento | Proveniência (FR-1) | Mapa interativo no app; `vinculos.csv` como dado; **biblioteca de regras citável**, separada do software — é o que pode sair do serviço (RDC 657, art. 5º, § 1º) |

O reaproveitamento de código externo, com os cuidados de licença e de versão
(BED_Calc sem licença, pymedphys em beta), está no addendum do brief.

### 10.1 Software e sistemas no MVP

#### FR-37: Cobertura das obrigações

O ISOCENTRO publica a cobertura: a fração das atividades com verificação
ativa.

**Consequências:**

- A conta sai do cadastro de verificações ligado às atividades; não é
  digitada.
- Verificação em sombra não conta como ativa.
- `[SUPOSIÇÃO]` São publicados dois números: sobre as 74 atividades do
  catálogo v1 (a meta do brief) e sobre as 60 de nível obrigatório. Qual é o
  denominador oficial é decisão do físico (§15, G5).

#### FR-38: Inventário de software de terceiros

O ISOCENTRO mantém o inventário dos componentes de terceiros (SOUP) com
versão e licença, gerado das dependências (B10).

**Consequências:**

- O inventário entra no relatório de validação (FR-40).
- Componente com risco conhecido registrado na base (exemplo: o pylinac usa o
  kQ do TRS-398 de 2000) aparece com a ressalva.

#### FR-39: Integridade da transferência

A leitura do RT Plan e do `variandw` registra o que foi lido (identificador e
checksum do arquivo, data da carga do `variandw`).

**Consequências:**

- Uma execução sempre diz de qual versão do dado partiu (TG-201, integridade
  ponta a ponta; o texto de 2021 está fora do acervo).

#### FR-40: Relatório de validação por módulo

Cada módulo do MVP tem relatório de validação antes do primeiro uso real.

**Consequências:**

- O relatório traz: requisitos, testes automatizados, casos conferidos à mão,
  sensibilidade medida por erro semeado (FR-6), comissionamento (FR-14 no
  MVP 1), inventário de SOUP (FR-38) e versão do software.
- O relatório é guardado por pelo menos 10 anos após o descarte (RDC 657,
  art. 5º, § 3º).
- Upgrade do ARIA ou do Eclipse exige rodar de novo a bateria semeada e
  registrar.

## 11. Requisitos não funcionais transversais

- **NFR-1 Somente leitura no ARIA e no Eclipse.** Nenhum módulo grava no
  ARIA, no `variandw` ou nos relatórios exportados (`docs/qms/escopo.md`,
  Fronteiras). Nenhuma escrita no Eclipse no MVP: todo avaliador ESAPI é
  script somente leitura, separado das DLLs graváveis (estruturas,
  field-in-field), e a entrega confere que ele não declara escrita.
- **NFR-2 Dado de paciente.** Nenhum dado de paciente ou de funcionário sai
  da rede do serviço, vai para log, para o repositório ou para serviço de
  terceiros, inclusive modelo de IA. Teste: `varrer_identidade` e teste de
  log, como o controle do risco RD-5 do `docs/qms/riscos.md`. CEL, BET e DUO estão na mesma rede corporativa: passar dado entre elas
  não é sair da rede (decisão do físico, 16/10/2026; §15, G3).
- **NFR-3 Degrau anunciado.** Toda tela com dado do `variandw` mostra o
  degrau e a data do dado.
- **NFR-4 Campo sem fonte nasce vazio.** Nenhum valor é presumido ou
  preenchido por parecença; a tela diz o que falta. Os valores padrão deste
  PRD marcados `[SUPOSIÇÃO]` (30 dias de sombra, 60 dias de aviso, 20 dias no
  incidente) só entram em vigor depois de confirmados pelo físico.
- **NFR-5 Desempenho.** A segunda checagem não tem número fixo de segundos:
  o critério é o do FR-11, resultado pronto antes de o plano aparecer na
  fila de Aprovação Física (físico, 26/10/2026). `[SUPOSIÇÃO]` Painéis abrem
  em menos de 3 s, sem referência (`decisoes-sem-base.md` #33).
- **NFR-6 Uso nas três clínicas.** CEL, BET e DUO veem cada uma os próprios
  dados; o físico responsável vê as três. O uso em rede tem subordinação
  documentada (§12.3; §15, G3).
- **NFR-7 Disponibilidade.** Se o `variandw` estiver fora, o ISOCENTRO
  continua mostrando o último dado com o degrau e a data; nenhuma
  verificação de prazo vira `conforme` por falta de dado.
- **NFR-8 Rastreabilidade.** Todo FR clínico liga a um item do
  `docs/qms/riscos.md` e a uma forma de verificação. O físico escreve as
  linhas novas do risco (§12.2).
- **NFR-9 Base saudável.** A suíte de testes continua verde e rápida a cada
  entrega (pilar 4 do `DESTINO.md`).
- **NFR-10 Onde o ISOCENTRO grava.** O banco central de verificações,
  assinaturas, CQ e incidentes é um destino de gravação novo, fora do que o
  `docs/qms/escopo.md` declara hoje (pasta do paciente e ao lado do app). O
  banco fica num servidor da clínica (decisão do físico, 16/10/2026), nunca
  na infraestrutura do ARIA ou do `variandw`; o tipo e o servidor foram
  decididos na arquitetura (19/10/2026; addendum). O escopo precisa ser
  atualizado antes do 1º épico que grava no banco (§15, G6; frente R-16).

## 12. Segurança clínica, conformidade e riscos

### 12.1 Classe de segurança

`docs/qms/classificacao-62304.md` (físico, 26/10/2026) dá classe A ao
núcleo, à camada `rt`, ao Plano, ao Radioteraficha, ao GQ, à Segurança do
paciente, à Documentação e ao Radioteradados, e classe C ao cálculo TRS-398,
como item próprio dentro do GQ. Os módulos fora do MVP **não têm classe**:
até o físico classificar, vale o rigor C (espinha, AD-35). O TRS-398 (C) grava pelo núcleo (A); a justificativa da
segregação (IEC 62304 §5.3.5) é decisão do físico e espera o texto da norma;
até lá, com o TRS-398 no executável, todo item do processo tem rigor C
(`decisoes-sem-base.md` #34). A
segunda checagem e a revisão do plano influenciam a decisão de tratar: um
falso `conforme` nelas pode levar a erro de dose. A classe ANVISA (RDC
751/2022, fora do acervo) e a IEC 62304 são decisão do físico. Se a classe
passar de II, o art. 5º da RDC 657 deixa de valer para o software *in house*.
Ver §15, G1.

### 12.2 Riscos a analisar

O PRD não escreve linhas no `docs/qms/riscos.md`, que hoje só tem RD-1 a
RD-5, do Radioteradados. Lista os modos de falha que o físico precisa avaliar
para cada FR clínico, cada um com a forma de verificação a definir (teste
automatizado ou caso conferido à mão):

| Requisito | Modo de falha a avaliar |
| --- | --- |
| FR-3 | Log alterado sem detecção |
| FR-8, FR-20 | Assinatura vale para versão do plano diferente da conferida |
| FR-10 | Tabela da máquina errada aplicada ao plano (nome DICOM trocado) |
| FR-11 | Checagem não roda e ninguém percebe |
| FR-12, FR-13 | Checagem dá `conforme` para plano errado (falso negativo) |
| FR-15, FR-17 | Contagem de frações errada adia o alerta do prazo |
| FR-16 | Data da sequência lida do campo errado do `variandw` |
| FR-18 | Caso de alto risco não marcado recebe o prazo comum |
| FR-19, FR-21, FR-42 | Item automático dá `conforme` falso |
| FR-20 | Duplo Check registrado pelo mesmo físico da Aprovação Física |
| FR-23, FR-24 | Tolerância errada ou teste vencido marcado como em dia |
| FR-27 | Fonte HDR usada sem medida de S_K registrada |
| FR-29 | Texto livre lido por perfil sem acesso; notificador exposto |
| FR-30 | Prazo de 30 dias contado de data errada |
| FR-33 | ASO lido por perfil sem acesso; item sem data marcado em dia |
| FR-36 | Aferição com decaimento ou referência errados |
| FR-41 | Alerta gerado e não visto (fadiga de alerta) |
| FR-43 | "Fora da faixa" de literatura lido como reprovação |
| FR-44 | Instrumento vencido usado sem aviso |
| FR-45 | k_Q ou N_D,w errado muda a dose de todos os pacientes |
| FR-46 | Análise mal configurada aceita imagem com erro |
| FR-48 | Paciente reidentificável em recorte pequeno |

### 12.3 Conformidade

| Norma | O que pede | Onde o PRD cumpre |
| --- | --- | --- |
| NN-6.10 art. 15, XI, e | Segundo sistema de cálculo | §5 — 3D e modulado; em cada máquina, só depois do comissionamento (FR-14) |
| NN-6.10 art. 17, IV | Segunda assinatura por conferência | §6, FR-20 |
| RDC 20/2006 9.7 (c) | Verificação até a 3ª fração ou 10% | FR-15, FR-17 |
| NN-6.10 arts. 35, 71 IX; RDC 20 8.1 (b) | Programa de CQ registrado e guardado | §7 |
| NN-6.10 art. 26; RDC 36/2013 | Incidentes: 30 dias; notificação mensal | §8 |
| NN-6.10 arts. 20, 24, 29, 36 | Vencimentos | §9 |
| NN-6.10 arts. 49, 52, 54, 55 | Instrumentos e aferição | §7, FR-44, FR-36 |
| RDC 657/2022 art. 5º | Validação completa guardada 10 anos; discernir registro alterado | FR-3, FR-40 |
| LGPD | Dado sensível de paciente e de funcionário | NFR-2, FR-35 |
| Uso em rede (P&R ANVISA, pergunta 2) | Subordinação administrativa e financeira documentada entre as clínicas | Existe (físico, 16/10/2026); §15, G3 |

## 13. Métricas de sucesso

**Principais**

- **SM-1 Segunda checagem no prazo:** fração dos planos das quatro máquinas
  com segunda checagem conferida até o prazo de verificação (antes da 1ª
  fração no alto risco). Meta 100%; a meta de fundo é antes da 1ª fração.
  Valida FR-11 a FR-15.
- **SM-2 Duplo Check no prazo:** fração dos planos com Duplo Check assinado
  por outro físico até o prazo de verificação; nos casos de alto risco,
  antes da 1ª fração. Meta 100%. Valida FR-16 a FR-20.
- **SM-3 CQ sem vencimento perdido:** nenhum teste do programa vence sem
  registro; falha visível no mesmo dia. Valida FR-22 a FR-24, FR-41.
- **SM-4 Incidentes no prazo:** todo evento com prazo de 30 dias acompanhado
  e fechado no prazo. Valida FR-29 a FR-31.
- **SM-5 Cobertura:** fração das atividades com verificação ativa,
  publicada e crescente. Valida FR-37.

**Secundárias**

- **SM-6 Validação:** cada módulo do MVP com relatório de validação antes do
  uso real e o log íntegro. Valida FR-3, FR-40.
- **SM-7 Sensibilidade:** sensibilidade medida por erro semeado em cada
  verificação do MVP, publicada após cada upgrade. Valida FR-6.
- **SM-8 Fim das planilhas paralelas:** o físico deixa de manter a planilha
  de vencimentos. `[SUPOSIÇÃO]` A planilha de QA de paciente só sai quando o
  resultado do PSQA entrar no ISOCENTRO, o que não está no MVP (o MVP lê só a
  data do PSQA).
- **SM-9 Indeterminado:** fração das execuções da segunda checagem que saem
  `indeterminado`, por motivo. Mostra quanto do art. 15, XI, e ainda não é
  cumprido (modulado, filtro, máquina sem tabela).

**Contramétricas (não otimizar)**

- **SM-C1 Alertas por físico por semana:** cresce se as regras forem
  sensíveis demais; alerta que ninguém lê não protege. Equilibra SM-1, SM-2,
  SM-3.
- **SM-C2 Justificativas por `nao_conforme`:** se quase todo `nao_conforme`
  vira justificativa, a regra ou a tolerância está errada, não o plano.
  Equilibra SM-1.
- **SM-C3 Cobertura sem sensibilidade:** subir a SM-5 com verificações em que
  a SM-7 é baixa é cobertura de fachada. Equilibra SM-5.

## 14. Fora do escopo e riscos do produto

### 14.1 Fora

- **IORT (INTRABEAM).** Fora do projeto (decisão de 13/10/2026, reafirmada em
  16/10/2026). O `iort-streamlit` não entra.
- Bloquear o fluxo clínico dentro do ISOCENTRO; a trava é a do ARIA.
- Escrever no ARIA, no `variandw` ou nos relatórios exportados.
- Escrever no Eclipse, exceto por script ESAPI gravável validado — e nenhum
  no MVP.
- Enviar dado pessoal a terceiros.
- Recálculo de dose 3D próprio. A segunda checagem é por ponto (TMR × Scp);
  a evolução para 2D/3D fica para depois.
- A unidade SAT (Synergy01) no MVP.
- Enviar ao Notivisa ou à ANSN: o ISOCENTRO prepara e acompanha, o envio é
  do usuário cadastrado do NSP e do titular.
- Distribuir o software para fora do serviço: o que pode sair é a biblioteca
  de regras (RDC 657, art. 5º, § 1º). Isso conflita com a ideia de "produto
  para outros serviços" do brief do Radioteradados (§15, G7).

### 14.2 Riscos do produto

- **Manutenção de uma pessoa só.** Não há fornecedor; todo upgrade do ARIA
  ou do Eclipse pode quebrar avaliadores. Mitigação: FR-6 e FR-40 depois de
  cada upgrade.
- **Tabelas de feixe antigas.** 600CD de 2010; Varian de 2020. A segunda
  checagem vale tanto quanto a tabela (FR-10, FR-14).
- **PPR desatualizado.** FFF, filtros e SRS/SBRT estão fora do PPR, e a
  NN-6.10 (art. 15, XIV) exige PPR novo antes de qualquer modificação. O
  programa de CQ do MVP 3 mostra testes que o PPR ainda não declara.
- **Pendências do serviço.** Instrumentos (câmara para SRS na CEL e para IMRT
  na BET, dispositivo de QA da DUO), N_D,w × ICRU 90 e correções do PPR
  (`PENDENCIAS.md`, pendências 1–14) deixam testes `indeterminado`.
- **Classe regulatória.** Se a classe passar de II, o caminho *in house* da
  RDC 657 deixa de valer (G1).

## 15. Questões em aberto

Agrupadas por módulo, para as sessões de detalhe. As marcadas **[bloqueia]**
impedem a arquitetura. Dono de todas: o físico responsável, salvo indicação.

**Geral (G)**

- **G1 [resolvida em parte em 26/10/2026]** Classe A para núcleo, Plano,
  Radioteraficha e GQ, e classe C só para o cálculo TRS-398; ANVISA classe I
  ou II até todos os testes (`classificacao-62304.md`). Classe A também
  para `rt`, Segurança e Documentação (26/10/2026). Falta a segregação do
  TRS-398 (§12.1).
- **G2** Se a contagem de frações usar o `dominio/ritmo`, a classe A dele
  continua valendo?
- **G3 [resolvida em 16/10/2026]** Existe documento de subordinação entre
  CEL, BET e DUO, e as três estão na mesma rede corporativa: passar dado
  entre elas não é sair da rede (NFR-2). Falta só dizer qual é o documento e
  onde fica guardado.
- **G4** Sombra: período mínimo para as verificações do MVP, e se a sombra em
  dado de produção conta como uso real antes do FR-40.
- **G5** Denominador da cobertura: 74 do catálogo v1 ou 60 obrigatórias.
- **G6 [resolvida em 26/10/2026]** Hospedagem no servidor da clínica
  (16/10/2026), banco na arquitetura (19/10/2026) e novo destino de gravação
  registrado no `escopo.md`, "Fronteiras" (26/10/2026).
- **G7** Ambição regulatória: uso interno permanente ou dossiê para registro;
  e o conflito com "produto para outros serviços" do Radioteradados.
- **G8** Preencher o `docs/qms/escopo.md` (perfis, pasta do serviço, critério
  de validação dos scripts graváveis) e as linhas novas do `riscos.md`
  (§12.2).

**Plano — MVP 1 e 2 (P)**

- **P3 [resolvida em 19/10/2026]** IMRT/VMAT entra no MVP pelo Clarkson
  modificado por ponto de controle (FR-12, FR-13, FR-14). Ficam abertos: a
  origem das medidas de transmissão do MLC e do DLG por máquina e o
  tratamento do arco (amostragem angular). O MU density do pymedphys foi
  descartado porque compara fluências e não calcula dose.
- **P4 [resolvida em 19/10/2026]** Os limites do TG-114 e do TG-219
  substituem os do código.
- **P5 [resolvida em 26/10/2026]** Dose registrada no ARIA; curso e fase,
  vence o que disparar primeiro (FR-15).
- **P6 [bloqueia]** Códigos reais das atividades PSQA, Aprovação Física e
  Duplo Check no `variandw` (frente `clinica`).
- **P7 [resolvida em 26/10/2026]** Referências no FR-19; entram os "++"/F do
  TG-275 e o MPPG 11.a como catálogo. Fica aberta a tolerância em mm das
  conferências de isocentro.
- **P8 [resolvida em 26/10/2026]** ≥ 6 Gy/fração, ≤ 5 frações ou < 6 dias
  (FR-18).
- **P9 [resolvida em 26/10/2026]** Invalida nos quatro casos (FR-8).
- **P10 [resolvida em 19/10/2026]** O resultado do paralelo não aparece em
  documento impresso (conferido no código); o papel não muda.
- **P11** A assinatura registrada substitui a do papel (art. 17, IV) ou
  convive com ela?
- **P12 [resolvida em 26/10/2026]** A R-07 fecha antes do MVP 2 e é
  condição de entrada dele (FR-15).

**Garantia da Qualidade — MVP 3 (C)**

- **C1 [resolvida em 19/10/2026]** Fora de tolerância é `nao_conforme` com
  alerta `alta` (FR-23).
- **C2 [resolvida em 26/10/2026]** O físico cadastra a ação e o limite de
  ação antes da carga, num cadastro do banco editado pela tela; ambos nascem
  vazios e a lista cresce com o uso.
- **C3** Formato das exportações do DailyQA 3 e do MapCHECK.
- **C4** Origem das imagens de CQ para o pylinac (EPID/kV exportados pelo
  ARIA ou arquivo da estação), formato e pasta.
- **C5 [resolvida em 26/10/2026]** k_Q da edição de 2000 com o N_D,w do
  certificado atual (FR-45).
- **C6 [resolvida em 26/10/2026]** Ficam em sombra até a conferência linha a
  linha, com registro por item.
- **C7 [resolvida em 26/10/2026]** Vale o mais longo dos dois prazos (FR-28).

**Segurança do paciente — MVP 4 (I)**

- **I1** Quem é o usuário Notivisa do NSP e como entra no ISOCENTRO; se o
  NSP do grupo inclui a radioterapia (G04); campos das 10 etapas (manual
  Notivisa 2025, fora do acervo). O Epimed saiu (26/10/2026).
- **I2 [resolvida em 19/10/2026]** Físico, SPR/gestão e o próprio notificador
  (FR-29).
- **I3 [resolvida em 26/10/2026, provisória]** Só feriado nacional deixa de
  contar (FR-31; `decisoes-sem-base.md` #29).
- **I4 [resolvida em 26/10/2026]** Mapa do Ford 2012; dose pelo Ford, local
  e volume pelo TG-100 (FR-29).
- **I5** Matriz de risco (FR-49): documento do método (Foro Iberoamericano /
  IAEA TECDOC-1685) e catálogo do SEVRRA fora do acervo; casar as 11 etapas
  do SEVRRA com as 8 do Ford; quais barreiras têm dado; ortovoltagem entra?;
  a CNEN aceita a matriz no lugar do SEVRRA?

**Vencimentos — MVP 5 (V)**

- **V1 [resolvida em 26/10/2026, provisória]** ASO 1 ano do exame (NR-7);
  PCMSO de cada clínica em `decisoes-sem-base.md` #18 (FR-33).
- **V2 [resolvida em 26/10/2026]** Datas lançadas do documento de origem;
  JSON do `ppr-streamlit` só confere (FR-33, FR-35). As datas de instrumento
  e certificado são da GQ.
- **V3 [resolvida em 26/10/2026, provisória]** Autorização da CNEN e alvará
  como tipos separados; SEVRRA sem data; lista de IOEs no cadastro do
  núcleo, mantida pelo SPR (FR-33; `decisoes-sem-base.md` #19–21).

**Base de conhecimento (B)**

- **B1** Correções: H01 e F13 com nível divergente entre CSV e ficha; etiqueta
  `fff` no TrueBeam; testes de HDR no `programa-cq.csv`; TG-119 e TG-201 para
  o acervo.

## 16. Índice de suposições

- §2.2 — auditor e inspetor recebem relatório exportado, sem acesso.
- §2.3 — jornadas UJ-1 a UJ-5 escritas pelo PRD, a conferir contra caso real.
- §3 — nomes `alta`, `atencao`, `informativo` para a severidade.
- FR-4 — sombra de 30 dias por padrão, encurtável com justificativa.
- FR-5 — `nao_conforme` em `alta` pede justificativa sem bloquear.
- FR-11 — "junto do PSQA" lido como disparo na aprovação médica.
- FR-16 — PSQA e Duplo Check lidos como atividades do Carepath no `variandw`; a assinatura no ISOCENTRO é o registro do Duplo Check e a divergência com o `variandw` gera alerta.
- FR-20 — o papel não muda no MVP.
- FR-21 — itens da RDC 20, 9.1 que faltam entram como registro manual.
- FR-22 — etiqueta `fff` no TrueBeam.
- FR-24 — CQ diário alertado até o primeiro tratamento do dia.
- FR-25 — tendência na carta fica para depois do MVP.
- FR-26 — formato das exportações não levantado; no MVP só exportações de CQ de máquina.
- FR-30 — `atencao` aos 20 dias do prazo de 30.
- FR-31 — só feriado nacional deixa de contar como dia útil.
- FR-33 — periodicidade do ASO pelo PCMSO.
- FR-34 — aviso prévio padrão de 60 dias.
- FR-37 — cobertura publicada sobre 74 e sobre 60.
- FR-41 — prazos calculados por varredura agendada na concentradora; alerta só no app no MVP.
- FR-42 — itens automatizáveis da lista de Planejamento seguem a regra do FR-19.
- SM-8 — planilha de QA de paciente só sai depois do MVP.
- NFR-5 — 3 s por painel (`decisoes-sem-base.md` #33).
- NFR-6 — visibilidade por clínica depende da forma de uso em rede.
