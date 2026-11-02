---
title: 'Extrato do PRD ISOCENTRO para a UX da estrutura global'
fonte: '../../prd-isocentro-2026-10-16/ (prd.md status final, addendum.md, .memlog.md)'
created: '2026-10-16'
---

# Extrato do PRD ISOCENTRO — foco UX da estrutura global

Convenção: `§n` = seção do prd.md; `Add.` = addendum.md; `ML` = .memlog.md.
`[SUP]` = marcado `[SUPOSIÇÃO]` no PRD. "Não mencionado" = o PRD não trata.

## 1. Visão, público, stakes, plataforma

- Visão: o lugar onde o serviço responde "**o que está vencido, o que falhou e quem precisa agir**" (§1).
- Hoje espalhado em `ppr-streamlit`, planilhas de QA de paciente, scripts ESAPI, Epimed e memória do físico (§1).
- Produto = **motor único de verificação** (não conhece RT) + **oito módulos** que conhecem (§1).
- Cada verificação nasce com o porquê: regra → ficha da base → norma, tolerância, página da fonte (§1).
- Motor **advisory**: avisa e registra, **nunca bloqueia**; a trava fica no ARIA (só o físico dá Treatment Approved) (§1, FR-5, §14.1).
- MVP: 5 obrigações legais sobre código existente — segunda checagem, revisão do plano com segunda assinatura + sequência real, programa de CQ, incidentes/quase-incidentes, vencimentos (§1).
- Completo quando as 74 atividades do catálogo v1 tiverem verificação ativa (§1, FR-37).
- Horizonte 2–3 anos: responde **em uma tela, nas três clínicas**; chega à inspeção da ANSN e à avaliação da ANVISA com histórico pronto (§1).
- Público do documento: físico responsável (decide) e agentes de UX/arquitetura/épicos (§0). Passo 1 de 4: PRD → UX → arquitetura → épicos (§0).
- Stakes: **regulado e clínico**. Obrigações NN-6.10, RDC 20/2006, RDC 36/2013, RDC 657/2022, LGPD (§12.3). Classe IEC 62304/ANVISA **não decidida** (G1 bloqueia) (§12.1). Falso `conforme` na segunda checagem/revisão pode levar a erro de dose (§12.1).
- Uso interno; 3 clínicas; peso regulatório; rigor alto (ML). Software não é distribuído para fora; só a biblioteca de regras pode sair (§14.1, §10).
- Motivação: obrigação legal + padrão de falha de 6 casos do acervo (Panamá, Glasgow, Épinal, Costa Rica, Białystok, Toulouse); sem caso local registrado (§1).
- Plataforma/form-factor: **desktop**, "há uma só interface, o **shell PyQt5** do ISOCENTRO (`isocentro/interface/`), com o tema e os widgets como design system (**QSS**)" (§4.2). Nenhum módulo do MVP abre fora do shell; **sem Streamlit no MVP** (FR-9).
- Dados/hospedagem: banco central em **servidor da clínica**, nunca na infraestrutura do ARIA/`variandw`; SQLite × PostgreSQL fica para a arquitetura (NFR-10, Add., ML G6).
- Três estações em três clínicas compartilhando assinatura, fila e CQ — forma em aberto para arquitetura; mesma rede corporativa (Add., NFR-6).
- Avaliadores: Python (no app) ou ESAPI (C#, JSON) (§3 Avaliador, FR-2). ESAPI 15.6 (Add.).
- Varredura agendada na "concentradora" calcula prazos com app fechado [SUP] (FR-41).

## 2. Perfis e permissões

Cinco perfis (confirmados pelo usuário 16/10): **físico, dosimetrista, radioterapeuta, técnico, SPR/gestão** (§2.1, FR-7, ML). Seis trabalhos para cinco perfis: físico médico e físico do Duplo Check têm o mesmo perfil (§2.1). Tabela de perfis = `docs/qms/escopo.md`, a preencher pelo físico (FR-7, G8).

| Perfil | Trabalho a fazer (§2.1) | Pode / vê |
| --- | --- | --- |
| Físico médico (dono das regras) | Saber sem planilha que todo plano teve 2ª checagem e Duplo Check no prazo, nenhum CQ venceu sem registro, cada incidente dentro dos 30 dias; chegar à inspeção com histórico | Único que assina Aprovação Física e Duplo Check; único que cadastra, promove ou poda verificação (FR-7); cadastra tabelas de feixe (FR-10), comissionamento (FR-14), marca alto risco à mão (FR-18), cadastra ações de teste (FR-23), cadastra vencimentos (FR-33), registra aferição (FR-36), roda erro semeado (FR-6), encurta sombra com justificativa [SUP] (FR-4); vê carta de controle (FR-25), revisão periódica de incidentes (FR-32); lê texto livre/dose estimada do incidente [SUP] (FR-29) |
| Físico do Duplo Check | Conferir com a lista votada, ver 2ª checagem pronta, deixar assinatura | Fila de Duplo Check (FR-17); assina (FR-20); **não pode ser o mesmo da Aprovação Física** — assinatura recusada como Duplo Check (FR-20, UJ-2) |
| Físico responsável | — | Vê alertas das **três clínicas** (FR-41, NFR-6) |
| Dosimetrista | Ver o resultado da 2ª checagem enquanto ainda dá para mexer no plano | Confere a Lista de Planejamento (13 itens) — registra quem/quando, **não é assinatura** de segunda conferência (FR-42) |
| Radioterapeuta (médico) | Ver alertas de prescrição; saber se o plano que aprovou passou pelas conferências | Aprovação médica = Planning Approved no ARIA (§3) |
| Técnico | Registrar CQ diário e checklist da sala sem papel paralelo | Registra execução de teste de CQ (FR-23) |
| SPR e gestão | Acompanhar vencimentos, incidentes e indicadores | Cadastra itens com vencimento (FR-33); lê texto livre/dose estimada do incidente [SUP] (FR-29) |
| Qualquer perfil | — | Registra incidente/quase-incidente (FR-29) |

Regras de assinatura/aprovação:
- Assinatura grava usuário logado, perfil, data/hora, objeto e versão (plano: `SOPInstanceUID` + status ARIA); entra no log; **sem assinatura em nome de outro**; mudança do RT Plan → Duplo Check volta a pendente (FR-8, FR-20). O que é "outra versão" = P9.
- Usuário ARIA ↔ ISOCENTRO por **mapeamento cadastrado explícito**, nunca parecença de nome; sem mapeamento → assinatura marcada "separação entre os físicos não conferida" + alerta `alta` (FR-20).
- ISOCENTRO não grava nada no ARIA; papel impresso com 2ª assinatura continua como hoje [SUP] (FR-20, P11).
- `nao_conforme` em `alta` pede justificativa de quem segue, sem impedir [SUP] (FR-5). 2ª checagem `nao_conforme`/`indeterminado` na lista pede justificativa (FR-19).
- Promoção de verificação registra quem, quando e resumo da sombra (FR-4).
- Visibilidade por clínica: cada clínica vê os próprios dados; físico responsável vê as três (NFR-6) [SUP §16].

Quem não usa (MVP): paciente (o ISOCENTRO só registra a entrega do aviso do art. 26); auditor/inspetor recebem relatório exportado, sem acesso [SUP]; unidade SAT (Synergy01, Monaco) fora (§2.2).

## 3. Módulos / áreas funcionais

Oito módulos (§1, §10). Núcleo transversal + shell (§4).

| Módulo | MVP | Uma linha | Relações |
| --- | --- | --- | --- |
| Núcleo — Motor de verificação (§4.1) | sim | Guarda verificações/execuções, log encadeado, sombra/promoção, alerta, erro semeado (FR-1–6, FR-41) | Todo módulo do MVP é um conjunto de verificações sobre ele |
| Shell, identidade e assinatura (§4.2) | sim | Interface única PyQt5, perfis, assinatura (FR-7–9) | Hospeda os módulos como aba/painel; painel único de alertas |
| **Plano** — MVP 1 segunda checagem (§5) | sim | Cálculo independente TMR×Scp por ponto, por campo e composto, limite citado (FR-10–15) | Disparo pelo Planning Approved; resultado aparece na Aprovação Física e no Duplo Check; prazo ligado a Tratamento (contagem de frações) |
| **Plano** — MVP 2 revisão com 2ª assinatura e sequência real (§6) | sim | Sequência real do `variandw`, fila de Duplo Check, alto risco, listas votadas, 2ª assinatura, conferência prescrição (FR-16–21, FR-42) | Consome MVP 1; lê Tratamento |
| **Garantia da Qualidade** — MVP 3 (§7) | sim | Programa de CQ por clínica/máquina (103 testes), execução, vencido, carta de controle, importação, HDR, cópia de segurança (FR-22–28) | Mensais/semestrais/anuais alimentam o painel de vencimentos (FR-24, FR-34) |
| **Segurança do paciente** — MVP 4 (§8) | sim | Incidentes e quase-incidentes, prazos art. 26 (30 dias) e RDC 36, registro do envio ao Epimed, revisão periódica (FR-29–32) | Liga a paciente/plano por ID do ARIA; Epimed continua canal oficial |
| **Documentação e conformidade** — MVP 5 (§9) | sim | Vencimentos (instrumento, fonte, certificado, treinamento, auditoria, ASO, levantamento), painel, migração do ppr-streamlit, aferição com decaimento (FR-33–36) | Recebe testes de CQ periódicos; substitui ppr-streamlit nos vencimentos |
| **Software e sistemas** (§10.1) | FR-37–40 | Cobertura, inventário SOUP, integridade da transferência, relatório de validação por módulo | Lê cadastro de verificações × atividades; relatório inclui sensibilidade (FR-6), comissionamento (FR-14) |
| **Tratamento** (§10) | só leitura da 1ª fração e contagem (FR-15, FR-16) | Depois: painel de revisão semanal (área D) | Alimenta prazos do Plano |
| **Indicadores** (§10) | — | Radioteradados absorvido como módulo (PRD/arquitetura próprios) | — |
| **Conhecimento** (§10) | Proveniência (FR-1) | Depois: mapa interativo no app; `vinculos.csv`; biblioteca de regras citável | Toda verificação aponta para ficha da base |

Depois do MVP por módulo (§10): Plano — plan check ~20 regras TG-275, PlanCheck/uhg-plancheck/PlanScoreCard, SRS, constraints, TG-263; GQ — tendência na carta, pylinac; Doc. — PPR no ISOCENTRO, POPs com versão, auditoria espelhada; Segurança — mapeamento Epimed, FMEA, pseudonimização; Software — ciclo ISQM, aprovação de script ESAPI.

Máquinas do MVP (§5, Add.): CEL TrueBeam 4045 (`TBuniverSN1002`), CEL Clinac 6EX 1254 (`6EX`), BET Clinac 600CD 1196 (`600CD`), DUO VitalBeam 4199 (`TrueBeamSN1001`). SAT Synergy01 fora. CEL também tem HDR (FR-27); ortovoltagem Dermopan (FR-24).

## 4. Requisitos que afetam shell/navegação

- **Login / sessão:** identidade já existe (`dados/auth.py`, `equipe.py`, `sessao.py`: login, **sessão única**, perfis) (§4.2). Assinar exige usuário logado na sessão atual (FR-8).
- **Troca de perfil:** não mencionado. Cada usuário tem **um** perfil (FR-7).
- **Clínica em contexto:** dados por clínica (CEL, BET, DUO); físico responsável vê as três (NFR-6, FR-41); painel de vencimentos por clínica (FR-34); UJ-4 mostra as três clínicas.
- **Paciente/plano em contexto:** "Ana abre o caso na **aba do plano**" (UJ-1); "Abre o caso" a partir da fila (UJ-2). Seletor de paciente explícito: não mencionado.
- **Busca:** não mencionada.
- **Notificações/pendências:** alerta é a **saída principal do motor** (§3). Aparece num **painel único do shell, "o que precisa de ação"**, ordenado por severidade e prazo, **e no módulo de origem** (FR-41). Estados: aberto, visto (quem/quando), resolvido (justificativa se `alta`); mudança no log (FR-41). No MVP só no app; canal externo depois, sem dado identificável [SUP] (FR-41). Prazo vencido com app fechado aparece como `alta` na abertura seguinte (FR-41). Risco de fadiga de alerta (§12.2, SM-C1).
- **Filas de tarefas:** fila de Duplo Check ordenada pelo prazo, alto risco no topo (FR-17, UJ-2); fila de Aprovação Física (FR-11 cita "fila de Aprovação Física"); lista do dia de CQ (UJ-3); painel de vencimentos com janela configurável (FR-34); revisão periódica de incidentes (FR-32).
- **Auditoria:** log append-only encadeado por hash de toda execução, assinatura, promoção e mudança de regra; sem edição/exclusão; integridade aponta registro e posição; retenção ≥ 10 anos após descarte (FR-3). Auditor externo recebe relatório exportado (§2.2).
- **Degrau de fonte:** toda tela com dado do `variandw` anuncia o degrau (`variandw` → espelho local → relatório exportado) e a data do dado (FR-9, NFR-3, §3).
- **Sem bloqueio:** nenhuma tela tem botão desabilitado por resultado de verificação (FR-5).
- **Verificação em sombra:** não aparece para o usuário, não gera alerta nem entra em fila (FR-4).
- **Modo dia/noite:** não mencionado (só "o mesmo tema", FR-9; tema/QSS, §4.2).
- **Multi-janela:** não mencionado. Módulos como **aba ou painel** do shell (FR-9).
- **Offline:** se o `variandw` estiver fora, mostra o último dado com degrau e data; nenhum prazo vira `conforme` por falta de dado (NFR-7).
- **Impressão:** papel do Duplo Check continua como hoje (FR-20, P11); texto impresso do paralelo pode mudar (FR-12, P10); relatórios exportados sem identificação de paciente (FR-29); relatório de validação (FR-40), relatório de sensibilidade (FR-6), relatório de migração (FR-35). Função de imprimir do app: não mencionada.
- **Anexos:** arquivo importado (DailyQA 3, MapCHECK) guardado com a execução; se não ler, entra como anexo e valor digitado [SUP] (FR-26).

## 5. Jornadas (§2.3) — [SUP] escritas pelo PRD, nomes ilustrativos, a conferir contra caso real

**UJ-1. Ana, física do caso, faz a Aprovação Física com a segunda checagem já pronta.**
"O médico aprovou o plano (Planning Approved) de uma mama 50 Gy/25 fr no 6EX. Na mesma leva do PSQA, o ISOCENTRO rodou a segunda checagem com a tabela do 6EX. Ana abre o caso na aba do plano: vê a diferença calculado × TPS por campo e no composto, o limite usado e de onde ele vem (TG-219, literatura, não calibrado para o serviço). Percorre os 8 itens da Aprovação Física, marca, e dá o Treatment Approved no ARIA. O ISOCENTRO registra a aprovação lida do `variandw`. Caso de borda: o plano tem campo com filtro físico, que o cálculo não trata; a checagem sai `indeterminado` com o motivo, e Ana registra a justificativa."
Passos: (1) Planning Approved no ARIA → (2) 2ª checagem automática → (3) abre caso na aba do plano → (4) lê diferenças + limite + origem → (5) percorre 8 itens → (6) Treatment Approved no ARIA → (7) ISOCENTRO lê do `variandw`. Borda: `indeterminado` + justificativa.

**UJ-2. Bruno, segundo físico, faz o Duplo Check antes da 3ª fração.**
"Bruno abre a fila de Duplo Check pendente, ordenada pelo prazo (3ª fração ou 10% da dose, o que vier primeiro). Os casos de alto risco aparecem no topo com prazo "antes da 1ª fração". Abre o caso: os 8 itens do Duplo Check, os itens automáticos já conferidos do RT Plan e do ARIA, e o resultado da segunda checagem. Assina. O ISOCENTRO grava quem, quando e sobre qual versão do plano. Caso de borda: o usuário logado é o mesmo que deu a Aprovação Física; o ISOCENTRO avisa que o Duplo Check precisa ser de outro físico e não registra a assinatura como Duplo Check."
Passos: (1) fila por prazo, alto risco no topo → (2) abre caso → (3) 8 itens + automáticos + 2ª checagem → (4) assina → (5) grava quem/quando/versão. Borda: mesmo físico → aviso, não registra.

**UJ-3. Carla, técnica, registra o CQ diário do VitalBeam.**
"Antes do primeiro paciente, Carla abre a lista do dia da DUO (22 testes diários), lança os valores e o resultado do DailyQA 3. Um teste sai da tolerância; o ISOCENTRO mostra a ação prevista e avisa o físico no mesmo dia. A carta de controle do output diário ganha um ponto."
Passos: (1) lista do dia da clínica → (2) lança valores + DailyQA 3 → (3) fora de tolerância → ação prevista + alerta ao físico → (4) ponto na carta.

**UJ-4. Geovani, físico responsável, abre a semana pelos vencimentos.**
"O painel mostra o que vence nos próximos 60 dias nas três clínicas: calibração bienal de um sistema de referência da BET, aferição trimestral com fonte-teste, um treinamento anual de PR. Um item não tem data de partida: aparece como "sem data", não como em dia."
Passos: (1) abre painel de vencimentos → (2) janela 60 dias, três clínicas → (3) item sem data aparece como "sem data".

**UJ-5. Daniel, dosimetrista, registra um quase-incidente achado na revisão.**
"Na revisão, Daniel encontra a energia do plano diferente da prescrição. Corrige no TPS e registra no ISOCENTRO um quase-incidente com etapa onde ocorreu, etapa onde foi detectado e gravidade. O físico vê o registro na revisão trimestral. Se fosse um incidente com exposição não intencional, o ISOCENTRO abriria o prazo de 30 dias e a lista do art. 26."
Passos: (1) acha divergência → (2) corrige no TPS → (3) registra quase-incidente (etapas, gravidade) → (4) físico vê na revisão trimestral. Variante: incidente com exposição → prazo 30 dias + lista art. 26.

## 6. NFR e requisitos relevantes para UX

- **Idioma:** não declarado explicitamente; todo o vocabulário é pt-BR e o glossário do §3 "vale para todo o documento e para os documentos seguintes" (§3).
- **Acessibilidade:** não mencionada.
- **Densidade:** não mencionada explicitamente. Telas carregam valor lido + fonte + referência + fonte da referência + resultado por item (FR-19); limite + origem por campo e composto (FR-12).
- **Desempenho percebido:** 2ª checagem < 30 s por plano; painéis abrem < 3 s [SUP] (NFR-5). Resultado da 2ª checagem pronto antes de o plano aparecer na fila de Aprovação Física (FR-11).
- **Segurança do paciente / linguagem honesta:**
  - `indeterminado` é resultado de primeira classe, diz por quê, **nunca contado como conforme** (§3, FR-2, FR-13).
  - Avaliador com exceção → `erro` com mensagem, nunca `conforme` (FR-2).
  - Campo sem fonte nasce vazio; nada presumido ou preenchido por parecença; tela diz o que falta (NFR-4, FR-16, FR-19).
  - Item sem data de partida = "sem data", nunca em dia (FR-33, UJ-4).
  - Rótulo "demonstração" sai; entram `indeterminado` e a origem do limite (FR-12, FR-13).
  - Todo limite com "origem: literatura, não derivado do serviço" enquanto não houver derivação local; `nao_conforme` contra limite de literatura é alerta, não reprovação (FR-12).
  - Tolerâncias exibem origem `literatura` ou `servico` (FR-1, FR-23, FR-25).
  - Usuário não digita "conforme": resultado calculado pela tolerância; funcional = passa/falha com o texto da tolerância (FR-23).
  - Alto risco "não informado" é tratado como alto risco, com alerta "alto risco não avaliado" (FR-18).
  - Marcas textuais: "contagem de frações não conferida contra o ARIA" (FR-15); "separação entre os físicos não conferida" (FR-20); "cálculo não comissionado para esta máquina" (FR-14); "o cálculo não trata filtro" (FR-13); fonte HDR "não liberada" (FR-27).
  - Divergência ARIA × RT Plan mostra os dois valores e as fontes (FR-21).
  - Ponto de cálculo nunca é trocado para passar; troca gera nova execução, ambas no log (FR-12).
  - Severidades `alta`/`atencao`/`informativo`, nenhuma bloqueia [SUP nomes] (§3, FR-5).
- **Dado de paciente (NFR-2):** nada sai da rede do serviço, nem para log, repositório ou IA; exportação sem identificação (FR-29); importação de PSQA com identificação fica na pasta do paciente ou pseudonimizada (FR-26); caso semeado anonimizado (FR-6). Registro de incidente liga por ID do ARIA sem copiar dado clínico além do necessário (FR-29).
- **Somente leitura no ARIA/Eclipse** (NFR-1).
- **Rastreabilidade:** cada data mostra a fonte (tabela e campo do `variandw`) e o degrau (FR-16); execução diz de qual versão do dado partiu (FR-39); todo FR clínico liga a item de risco (NFR-8); log (FR-3).
- **Degrau anunciado** (NFR-3); **disponibilidade** com último dado (NFR-7).
- **Valores padrão [SUP]** (30 dias de sombra, 60 de aviso, 20 do incidente) só valem após confirmação do físico (NFR-4).
- **Contramétricas** que a UX não deve inflar: alertas por físico por semana; justificativas por `nao_conforme`; cobertura sem sensibilidade (§13 SM-C1–C3).
- **Linguagem regulada:** termos ARIA em inglês preservados (Planning Approved, Treatment Approved); citações de norma nos itens (NN-6.10 art., RDC, TG-n) (§3, §12.3).

## 7. Questões em aberto (§15) — todas ABERTAS salvo indicação; dono: físico responsável

Geral (G)
- ABERTA — **G1 [bloqueia]** Classe IEC 62304 e classe ANVISA do núcleo e de cada módulo do MVP (§12.1).
- ABERTA — **G2** Se a contagem de frações usar o `dominio/ritmo`, a classe A dele continua valendo?
- RESOLVIDA (resíduo aberto) — **G3 [resolvida em 16/10/2026]** Existe documento de subordinação entre CEL, BET e DUO, e as três estão na mesma rede corporativa: passar dado entre elas não é sair da rede (NFR-2). Falta só dizer qual é o documento e onde fica guardado.
- ABERTA — **G4** Sombra: período mínimo para as verificações do MVP, e se a sombra em dado de produção conta como uso real antes do FR-40.
- ABERTA — **G5** Denominador da cobertura: 74 do catálogo v1 ou 60 obrigatórias.
- ABERTA — **G6 [bloqueia]** Hospedagem decidida em 16/10/2026: servidor da clínica. SQLite × PostgreSQL fica para a arquitetura. Ainda bloqueia até o `escopo.md` receber o novo destino de gravação (NFR-10).
- ABERTA — **G7** Ambição regulatória: uso interno permanente ou dossiê para registro; e o conflito com "produto para outros serviços" do Radioteradados.
- ABERTA — **G8** Preencher o `docs/qms/escopo.md` (perfis, pasta do serviço, critério de validação dos scripts graváveis) e as linhas novas do `riscos.md` (§12.2).

Plano — MVP 1 e 2 (P)
- ABERTA — **P3 [bloqueia]** Segunda checagem de IMRT/VMAT: aceitar `indeterminado` no MVP ou trazer outro método (por exemplo MU density do pymedphys)? Hoje o art. 15, XI, e fica parcial.
- ABERTA — **P4** Limites: substituir os do código pelos do TG-114 e do TG-219?
- ABERTA — **P5** Dose acumulada dos 10%: dose registrada no ARIA ou planejada × frações; do curso ou da fase?
- ABERTA — **P6 [bloqueia]** Códigos reais das atividades PSQA, Aprovação Física e Duplo Check no `variandw` (frente `clinica`).
- ABERTA — **P7** Referência de cada item automatizável e lista exata dos itens "F" do TG-275 no MVP.
- ABERTA — **P8** Limiar de dose por fração que marca hipofracionamento.
- ABERTA — **P9** O que invalida uma assinatura: UID novo com conteúdo igual, mudança de status no ARIA, mudança de conteúdo sem UID novo.
- ABERTA — **P10** O resultado do paralelo aparece em algum documento impresso? Se sim, a troca de "demonstração" por `indeterminado` é mudança no papel.
- ABERTA — **P11** A assinatura registrada substitui a do papel (art. 17, IV) ou convive com ela?
- ABERTA — **P12** R-07 (conferir os 165 cursos contra o ARIA) fecha antes do MVP 2?

Garantia da Qualidade — MVP 3 (C)
- ABERTA — **C1** Resultado fora de tolerância de literatura no CQ é `nao_conforme` ou só alerta?
- ABERTA — **C2** Ações por teste: quem cadastra e quando (o `programa-cq.csv` não tem ação).
- ABERTA — **C3** Formato das exportações do DailyQA 3 e do MapCHECK.

Segurança do paciente — MVP 4 (I)
- ABERTA — **I1** Campos do formulário Epimed e se o NSP do grupo inclui a radioterapia (G04).
- ABERTA — **I2** Quem lê o texto livre e a dose estimada, por perfil.

Vencimentos — MVP 5 (V)
- ABERTA — **V1** Periodicidade do ASO (PCMSO).
- ABERTA — **V2** Datas reais de partida dos instrumentos e certificados (a base só tem modelo e número de série).

Base de conhecimento (B)
- ABERTA — **B1** Correções: H01 e F13 com nível divergente entre CSV e ficha; etiqueta `fff` no TrueBeam; testes de HDR no `programa-cq.csv`; TG-119 e TG-201 para o acervo.

Com impacto direto na UX: I2 (visibilidade por perfil), P9/P11 (assinatura e papel), P10 (texto impresso), G4 (sombra), G5 (número de cobertura exibido), C1 (rótulo do resultado de CQ), G8 (tabela de perfis).

## 8. Decisões do .memlog que afetam UX

- (by user) Usuário quer a **estrutura global primeiro**, esmiuçar depois; P3–P12 sem resposta, texto do PRD mantido (ML).
- (by user) Seguir o fechamento; detalhes de cada módulo em sessões seguintes (ML).
- (by user) Perfis confirmados: físico, dosimetrista, radioterapeuta, técnico, SPR/gestão (ML).
- (by user) Duplo Check segue o mesmo prazo do cálculo (3ª fração/10%); antes da 1ª fração só no alto risco (SBRT, reirradiação, dispositivo) (ML).
- (by user) Synergy01/SAT fora do MVP 1; 2ª checagem nas 4 Varian (ML).
- (by user) IORT (INTRABEAM, iort-streamlit) não entra no projeto (ML, §14.1).
- (by user) G3: mesma rede corporativa entre CEL, BET, DUO; dado entre elas não sai da rede (ML).
- (by user) G6: banco central em servidor da clínica, fora do ARIA/variandw; SQLite × PostgreSQL para a arquitetura (ML).
- (by user) G1 sem resposta, continua bloqueante (ML).
- Modulado sai `indeterminado` no plano até método validado (ML; FR-13).
- FR-41 alerta e FR-42 lista de Planejamento acrescentados na revisão (ML).
- Listas da Aprovação Física e do Duplo Check **separadas** conforme votação (ML; FR-19).
- FR-18 "não informado" tratado como alto risco (bloqueante clínico) (ML).
- FR-14 sem veredito antes do comissionamento (ML).
- Pendentes de convenção: crase em Treatment/Planning Approved; "físico responsável" fora do glossário (ML).
- Rigor alto: uso interno, 3 clínicas, peso regulatório (ML).

## 9. Glossário — termos exatos que a UX deve espelhar (§3 salvo indicação)

- **Atividade** (100 linhas: 74 catálogo v1 + 26 de prática; 60 "OBRIGATÓRIO"); **Item de verificação**; **Verificação**; **Execução** (origem `producao` | `semeado`); **Resultado**: `conforme`, `nao_conforme`, `nao_aplicavel`, `indeterminado`, `erro`.
- **Severidade**: `alta`, `atencao`, `informativo` [SUP]. **Estado da verificação**: `sombra`, `ativa`, `podada`. **Estado do alerta**: aberto, visto, resolvido (FR-41).
- **Avaliador** (Python | ESAPI); **Gatilho**: `evento`, `calendario`, `prazo`, `estado`; **Proveniência**; **Log**.
- **Segunda checagem**; **Tabela de feixe** (TMR, Scp); **Aprovação médica** (= `Planning Approved`); **Aprovação Física** (dá `Treatment Approved`); **Duplo Check** (segunda assinatura, art. 17, IV); **Sequência real** (aprovação médica, PSQA, Treatment Approved, Duplo Check, 1ª fração).
- **Prazo de verificação** (3ª fração ou 10% da dose, o que vier primeiro); **Caso de alto risco** (SBRT/hipofracionamento, reirradiação ou campo adjacente, dispositivo implantado); "alto risco não avaliado" (FR-18); "não informado" (FR-18).
- **Alerta**; painel **"o que precisa de ação"** (FR-41); **Auditoria espelhada** (pós-MVP).
- **Programa de CQ**; **Vencimento**; "sem data" (FR-33); "não liberada" (FR-27); **Carta de controle** (FR-25); limite de tolerância / limite de ação (FR-25).
- **Incidente**; **Quase-incidente**; "Detectado em": revisão do plano, 1º dia, revisão semanal, tratamento, outra (FR-29); lista do art. 26 (investigação iniciada, dose estimada e distribuição, medidas corretivas, medidas para prevenir reincidência, aviso escrito ao paciente, aviso escrito ao médico solicitante, relatório à ANSN) (FR-30).
- **Clínica**: CEL, BET, DUO (Anápolis); SAT fora.
- **Degrau de fonte**: `variandw` → espelho local → relatório exportado.
- Etapas Carepath: **Planejamento** (13 itens), **Aprovação Física** (8), **Duplo Check** (8) (§6, FR-19, FR-42). Itens da Aprovação Física: Distribuição de dose e DVH; Dose diária e total × prescrição; Máquina correta; Dias alternados; Curva de 4D; Concluir cursos anteriores; Orientações de agendamento; Se dose única, imprimir alta. Itens do Duplo Check: Luz de campo em mama; Dose diária e total × prescrição; Fases diferentes no mesmo isocentro; UM compatíveis com a dose; Análise do planejamento (DVH); Coordenadas do isocentro e localização; Máquina correta; Mudar a data do Duplo Check, se necessário (FR-19). Itens do Planejamento: nome do plano, luz de campo em mama, tolerância de mesa, margem dos PTVs, distribuição de dose e DVH, dose diária e total × prescrição, matriz de cálculo, fases no mesmo isocentro, contraste e artefatos, zerar origem da imagem, UM compatíveis, coordenadas do isocentro, máquina correta (FR-42).
- Status de plano no `variandw` (10): Unapproved, Planning Approved, Treatment Approved, Reviewed, 3rd Party Approval, Rejected, Retired, Completed, Completed Early, Unplanned Treatment (Add.).
- Sistemas externos citados: ARIA, Eclipse, `variandw`, Epimed (NSP), ANSN, ANVISA, DailyQA 3, MapCHECK, Monaco, TPS, RT Plan (`SOPInstanceUID`), PSQA.
- Módulos: Plano, Tratamento, Garantia da Qualidade, Documentação e conformidade, Segurança do paciente, Indicadores, Software e sistemas, Conhecimento (§10).
- Métricas: Cobertura (FR-37, SM-5); sensibilidade (FR-6, SM-7).
