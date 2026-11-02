# Revisão de qualidade do PRD — ISOCENTRO (gestão da qualidade em radioterapia, em módulos)

Rubrica: `bmad-prd/assets/prd-validation-checklist.md`. Documento revisado: `prd.md` (draft, 16/10/2026), sem addendum. Rigor alto: uso interno em 3 clínicas, peso regulatório, PRD no topo da cadeia (UX → arquitetura → épicos). O usuário escolheu o caminho rápido e vai detalhar cada módulo depois. A revisão leva isso em conta: lacuna de detalhe *por módulo* pesa menos que lacuna *transversal*, que todas as sessões seguintes vão herdar.

## Veredito geral — adequado

A tese se sustenta e é específica: motor único, advisory, cada verificação com proveniência; MVP ordenado por obrigação legal sobre código que já existe. O PRD é honesto sobre o que não sabe: 24 suposições, todas indexadas, e 4 bloqueios declarados. Os FRs têm, em quase todos os casos, consequências testáveis e ancoradas em norma e em código. O risco está no que é transversal e ficou sem definição. Primeiro, o **alerta**, que num sistema advisory é o próprio produto, não tem canal, destinatário nem tempo. Depois, faltam métricas de sucesso e contramétricas. Por fim, a promessa do MVP 1 depende da Q3: se todo plano IMRT/VMAT sair `indeterminado`, a obrigação do art. 15 fica de fato sem cumprimento para boa parte dos planos. O PRD já serve de base para UX. Para arquitetura, ainda não: falta fechar o alerta, a Aprovação Física no ISOCENTRO e as Q1, Q2, Q3 e Q5.

## Prontidão para decisão — adequado

As decisões aparecem como decisões, com data e autor: SAT fora do MVP (§2.2), prazo de verificação valendo também para o Duplo Check (§3, "decisão do usuário, 16/10/2026"), cinco perfis confirmados (§2.1), motor que "nunca bloqueia" (§1). As questões em aberto do §13 estão de fato em aberto, e as que travam a arquitetura estão marcadas **[bloqueia]**. O texto não alisa o que é incerto: o §12.1 admite que "os módulos do MVP **não têm classe** e o PRD não a decide".

Falta mostrar o que se perde em cada escolha. O modelo advisory (§1, FR-5) é a aposta central, e o PRD não diz qual é o custo dele: alerta ignorado, fadiga de alerta, a responsabilidade quando alguém segue adiante contra um `nao_conforme`. Não há nenhum `[NOTE FOR PM]`. E a promessa da Visão ("o MVP entrega cinco obrigações legais") convive com a suposição do FR-13, segundo a qual o plano modulado sai `indeterminado`, sem que o texto confronte as duas.

### Achados
- **alta** A promessa do MVP 1 depende da Q3 (§1, FR-13, §13 Q3) — Pela suposição do FR-13, o plano IMRT/VMAT sai `indeterminado` "até haver método validado". Se a maior parte dos planos das quatro máquinas for modulada, o MVP 1 grava `indeterminado` na maioria dos casos e não cumpre o art. 15, XI, e, que a §12.3 dá como cumprido no "§5". *Correção:* estimar a fração de planos modulados por máquina; dizer com todas as letras se o MVP 1 cumpre a obrigação só para 3D/campo aberto ou se precisa de um segundo método já no MVP; ajustar a linha da §12.3 de acordo.
- **média** O custo do modelo advisory não aparece (§1, FR-5) — Fica dito o que se ganha (não interferir no fluxo, a trava continua no ARIA), mas não o que se perde. Também não aparece quem responde quando um `nao_conforme` em `alta` é justificado e o caso segue. *Correção:* um parágrafo de trade-off em §1 ou FR-5, um `[NOTE FOR PM]` e uma contramétrica (ver Coerência estratégica).
- **média** Não há plano para uma Q1 desfavorável (§12.1, §13 Q1) — O §12.1 reconhece que, "se a classe passar de II, o art. 5º da RDC 657 deixa de valer para o software *in house*". FR-3, FR-40 e a §12.3 inteira se apoiam nesse artigo. O PRD não diz quais FRs mudam nesse cenário. *Correção:* listar os FRs que dependem do enquadramento *in house* (FR-3, FR-40, linha RDC 657 da §12.3) e o que muda em cada um se a Q1 sair desfavorável.

## Substância, não encenação — forte

A Visão não serve para outro produto: cita o POP-019, o vão "o físico calcula → o RT aprova" e os dois artigos da NN-6.10 que não têm procedimento. Os NFRs são deste produto (NFR-1 somente leitura no ARIA, NFR-4 campo sem fonte nasce vazio, NFR-7 sem `conforme` por falta de dado), não boilerplate. Não há seção de diferenciação feita só para preencher o modelo. A comparação com o QATrack+ (§7) é usada para decidir o modelo de dados.

### Achados
- **baixa** Perfis sem FR que os atenda (§2.1) — O radioterapeuta deveria "ver alertas de prescrição e saber se o plano que aprovou passou pelas conferências", mas nenhum FR define o que o perfil radioterapeuta vê (o FR-21 é conferência na etapa de Planejamento, sem destinatário). SPR/gestão deveria "acompanhar ... indicadores", e Indicadores está fora do MVP (§10). *Correção:* ligar cada trabalho do §2.1 a FRs ou marcá-lo como fora do MVP.

## Coerência estratégica — adequado

Existe tese, e ela orienta a priorização: primeiro as obrigações legais sem procedimento (art. 15 e art. 17), depois o registro de CQ, os incidentes e os vencimentos. O critério de "completo" (74 obrigações com verificação ativa, §1) aparece como FR mensurável no FR-37. O tipo de MVP também é coerente: resolve um problema de conformidade sobre código existente.

O que falta são métricas que validem a tese. Não há seção de métricas de sucesso, e o FR-37 mede cobertura, não efeito. A tese diz que o serviço vai saber "o que está vencido, o que falhou e quem precisa agir", e nada mede se isso acontece. Também falta dizer se os cinco "MVP n" são uma sequência de entrega e o que justifica a ordem.

### Achados
- **alta** Sem métricas de sucesso e sem contramétricas (documento inteiro) — Não há SM-n. Sem elas, o épico não sabe quando um módulo "deu certo" e a arquitetura não sabe o que precisa medir. *Correção:* uma seção de SMs com valor-alvo, por exemplo: SM-1 % de planos com segunda checagem e Duplo Check registrados dentro do prazo de verificação; SM-2 sensibilidade por erro semeado por verificação (FR-6); SM-3 % de execuções `indeterminado` por máquina; SM-4 % de testes de CQ vencidos sem registro. Contramétricas: % de `alta` seguidos com justificativa, tempo adicional do físico por plano, alertas por dia por usuário (fadiga).
- **média** O MVP tem 40 FRs em cinco módulos, sem ordem de entrega nem corte mínimo (§1, §5–§9, §10) — A numeração MVP 1–5 não diz se é sequência. As dependências estão espalhadas: o MVP 2 depende da Q5; o MVP 1 depende das tabelas e do comissionamento (FR-10, FR-14); o MVP 3 depende de correções na base (FR-22, FR-27). Cabem no "primeiro corte" itens grandes como HDR (FR-27), migração (FR-35) e decaimento do Sr-90 (FR-36). *Correção:* declarar a ordem, a dependência entre módulos e o que é o mínimo liberável de cada módulo. Isso pode ir para as sessões por módulo, mas o critério deve estar aqui.

## Clareza do que é "pronto" — adequado

Este é o ponto forte dos FRs: quase todos trazem "Consequências (testáveis)" concretas, com norma, página e código. Exemplos: FR-8 (o Duplo Check volta a pendente se o `SOPInstanceUID` mudar), FR-12 (limites do TG-219 com tabela e página; ponto de cálculo nunca trocado), FR-20 (recusa do mesmo usuário), FR-33 (periodicidades por artigo). A falha mais grave é transversal: o PRD inteiro fala em "alerta", e nada diz o que é um alerta pronto.

### Achados
- **crítica** O mecanismo de alerta não está definido (FR-5, FR-15, FR-17, FR-23, FR-24, FR-30, FR-31, FR-34, UJ-3) — "Alerta o físico no mesmo dia" (FR-23), "é alertado em `alta`" (FR-15, FR-17), "o ISOCENTRO ... avisa o físico no mesmo dia" (UJ-3): em nenhum lugar está dito por onde o alerta chega (aba, fila, painel, notificação do sistema, e-mail), a quem chega (o físico do caso, o físico responsável, o perfil inteiro, por clínica), em quanto tempo, nem o que acontece se ninguém abrir o app. Como o motor "avisa e registra, nunca bloqueia" (§1), o alerta é o meio pelo qual o produto cumpre o prazo legal. Sem essa definição, os FRs de prazo não têm teste de aceite e a arquitetura não sabe se precisa de serviço em segundo plano. *Correção:* um FR no §4 (por exemplo, "FR-x: Entrega de alerta") com canal, destinatário por severidade e perfil, latência máxima a partir da execução, confirmação de leitura e comportamento com o app fechado. "Alerta" também deve entrar no glossário.
- **alta** A Aprovação Física no ISOCENTRO é ambígua (UJ-1, FR-7, FR-11, FR-15, FR-19, FR-20) — Na UJ-1, o ISOCENTRO "registra a aprovação lida do `variandw`". O FR-7 diz que "só o perfil físico assina Aprovação Física", e o FR-20 fala de "a assinatura da Aprovação Física no ISOCENTRO". Nenhum FR cria essa assinatura. O FR-11 cita uma "fila de Aprovação Física" que nenhum FR define (só existe a do Duplo Check, no FR-17). O FR-15 exige a segunda checagem "conferida" sem dizer o que é conferir nem quem confere. *Correção:* um FR explícito para a Aprovação Física no ISOCENTRO (existe ou não assinatura própria; relação com o Treatment Approved lido; fila e prazo), mais a definição de "segunda checagem conferida" (por exemplo, o item do FR-19 confirmado pelo físico do caso).
- **média** Cópia de segurança sem limites e só para CQ (FR-28) — "Os registros de CQ têm cópia de segurança": sem frequência, perda máxima tolerada, local, retenção nem responsável. Log, assinaturas, incidentes e vencimentos também precisam de cópia, e a retenção de 10 anos (FR-3, FR-40) depende disso. *Correção:* ampliar o FR-28 para todo registro do ISOCENTRO, com frequência, perda máxima e retenção. A forma pode ficar para a arquitetura.
- **média** Escopo do log incompleto (FR-3) — O FR-3 cobre "execução, assinatura, promoção de estado e mudança de regra". Ficam de fora a edição de registro de incidente (FR-29/30), o cadastro e a alteração de vencimento (FR-33), as justificativas (FR-5, FR-19) e a marcação manual de alto risco (FR-18). A exigência da RDC 657 de discernir registro alterado vale para todos eles. *Correção:* "todo registro criado ou alterado por usuário entra no log", ou uma lista fechada.
- **média** Limites que faltam em FRs de integração (FR-7, FR-11, FR-14) — No FR-7, "o perfil define o que vê" não tem matriz de perfil × tela × ação. No FR-11 faltam a frequência de leitura do `variandw` e a origem do RT Plan (exportação DICOM? pasta? consulta?); "pronto antes de aparecer na fila" não tem número. No FR-14, o comissionamento "aprovado pelo físico" não tem critério de aceite (qual diferença medido × calculado aprova a máquina). *Correção:* matriz de perfis (pode remeter ao `escopo.md` com data-limite), latência máxima entre `Planning Approved` e resultado pronto, e o critério de aceite do comissionamento com fonte (TG-219 Tab. 8 / TG-114).
- **baixa** Adjetivos no lugar de limites (NFR-9, FR-29, FR-9) — "verde e rápida" (NFR-9), "sem copiar dado clínico além do necessário" (FR-29), "com o mesmo tema" (FR-9). *Correção:* tempo máximo da suíte; lista dos campos do paciente que o incidente guarda.

## Honestidade de escopo — forte

As suposições estão no texto e o índice do §14 fecha (24 marcadas, 24 indexadas). A tabela do §10 diz o que fica para depois em cada módulo, e trechos como "Fora deste FR" (FR-20) e "fica para depois do MVP" (FR-25, FR-31) fazem o corte de escopo às claras. Há bastante coisa em aberto: 4 bloqueios, 10 questões sem bloqueio e 24 suposições, 38 itens no total. Para um passo 1 de caminho rápido, isso é aceitável. Para dar sinal verde à arquitetura, não.

### Achados
- **média** Bloqueios sem ligação aos FRs afetados (§13) — Q1, Q2, Q3 e Q5 bloqueiam, mas não está dito quais FRs ou módulos travam com cada uma. Do jeito que está, a arquitetura parece travada por inteiro, quando, por exemplo, o MVP 5 (vencimentos) quase não depende delas. *Correção:* em cada questão **[bloqueia]**, listar os FRs afetados e dizer o que pode avançar sem ela.
- **média** A validade jurídica da assinatura registrada não é discutida (FR-8, FR-20, §13 Q8) — A Q8 pergunta se a assinatura do ISOCENTRO substitui a do papel, mas o PRD não diz que tipo de assinatura eletrônica é a do FR-8 (login e sessão), nem se ela é aceita para o art. 17, IV, perante a ANSN. Isso decide se o papel pode sair um dia. *Correção:* incluir na Q8 o tipo de assinatura (simples, avançada, ICP-Brasil) e quem confirma a aceitação, ou declarar `[NON-GOAL for MVP]` a substituição do papel.
- **baixa** Inferências sem marca (UJ-3, FR-36) — Na UJ-3, a "lista do dia da DUO (22 testes diários)" usa o total de diários do programa inteiro (§7: "22 diários" entre os 103), não necessariamente o da DUO. O FR-36 dá a fonte-teste como Sr-90 para todas as clínicas. *Correção:* conferir ou marcar `[SUPOSIÇÃO]`.

## Uso nas etapas seguintes — adequado

O glossário (§3) é bom e funciona: define estados, resultados, gatilhos, prazos e etapas do Carepath, e quase sempre é usado de forma consistente. Os IDs são contíguos (FR-1..40, NFR-1..9, UJ-1..5) e as UJs têm protagonista nomeado, com contexto no próprio texto. Cada módulo pode ser lido isolado, porque a descrição de cada um cita norma, código e UJ. Faltam termos que os agentes de UX e de épicos vão precisar.

### Achados
- **média** Termos usados e não definidos (§3) — "alerta", "fila", "painel", "PSQA", "caso", "ação prevista" e "evidência" aparecem em vários FRs sem definição. "Passa/falha" (FR-23) não corresponde ao enum de **Resultado**. O `demonstracao` (FR-13) aparece como valor que sai, sem ligação com o enum. A "etapa de Planejamento" (FR-21; 13 itens na §6) não tem verbete, ao contrário da Aprovação Física e do Duplo Check. *Correção:* incluir os termos no glossário; dizer que "passa/falha" se grava como `conforme` ou `nao_conforme`.

## Encaixe da forma — forte

A forma combina com o produto: ferramenta interna com vários perfis, peso regulatório, código já existente e PRD no topo da cadeia. A especificação de capacidades por módulo vem com UJs curtas e úteis (cada uma com caso de borda que vira FR), tabela de conformidade (§12.3) e tabela de riscos a analisar (§12.2). As referências a código (`banco/gatilho_db.py`, `dominio/constantes.py`, `banco/atividades_db.py`) mostram de onde vem cada coisa. Não há formalismo demais.

### Achados
- **média** A tabela de riscos deixa de fora modos de falha do próprio modelo (§12.2) — Ficam de fora: verificação de obrigação legal esquecida em `sombra` (FR-4), que não aparece para ninguém; gatilho que não dispara (FR-11), caso em que o plano nunca é checado; dado velho tomado como atual quando o `variandw` cai (NFR-7, FR-9); item automático do FR-19 lido do campo errado e preenchido como conferido; alerta que não chega (ver achado crítico). *Correção:* acrescentar essas linhas à tabela para o físico avaliar.

## Notas mecânicas

- **Referência quebrada:** NFR-2 cita "como no RD-5" sem definir RD-5 neste documento nem dizer em qual está.
- **Contagem de perfis:** o §2.1 lista seis trabalhos e diz "os cinco perfis"; o físico do Duplo Check é o mesmo perfil físico. Vale uma frase dizendo isso.
- **Tensão de redação:** o FR-5 diz que o resultado "nunca impede uma ação", e o FR-20 "recusa registrar" a assinatura. As duas coisas são compatíveis (a recusa vem da identidade, não do resultado), mas o FR-5 deveria dizer isso, para o épico não ler contradição.
- **Ida e volta das suposições:** 24 inline e 24 no índice, todas fecham. A suposição do FR-12 corresponde à Q4, e as dos FR-18, FR-19, FR-20, FR-4 e FR-33 às Q6, Q7, Q8, Q9 e Q13. A F13 aparece só na Q12, sem FR.
- **IDs:** FR, NFR, UJ e Q são contíguos e sem duplicata. Não há série SM (ver achado alto). Os códigos de atividade (C01, C05, C09, D03, E03, E06, G15, H01, A04, B06, B10, F13) e as frentes R-NN remetem à base e ao `DESTINO.md` sem resolução no texto. Aceitável, porque o §0 declara que o documento cita em vez de repetir.
- **Seções exigidas:** faltam Métricas de sucesso e Não-objetivos explícitos. As demais estão presentes para o risco combinado.
