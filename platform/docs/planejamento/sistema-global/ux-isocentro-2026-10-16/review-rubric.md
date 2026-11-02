# Revisão do par de documentos — ISOCENTRO (estrutura global)

Revisor: rubric walker (validate.md, passagens 1 a 8). Data: 2026-10-16. Somente leitura nos documentos principais.
Escopo considerado: só a estrutura global (shell, Início, módulos, navegação, perfis, clínica). Questões abertas de propósito (PRD §15; U1, U3, U4, U5, U8) e o detalhe de cada módulo **não** contam como falha. Regra da equipe aplicada: o DESIGN.md documenta o padrão visual que já existe e não propõe outro.
Severidade = impacto para quem constrói a partir dos documentos: **bloqueante** / **importante** / **menor**.

## Veredito geral

O par está sólido como contrato do shell. Todos os tokens de cor têm hex com par dia/noite e conferem com `estilo.py`; os contrastes declarados batem com o recálculo. As cinco jornadas do PRD estão cobertas, e as decisões do memlog (opção C, Início único, 7 perfis, cartão que some, seletor só com as clínicas permitidas) estão quase todas refletidas. Nenhum achado é bloqueante. Os problemas importantes são quatro contradições ou atribuições falsas ao memlog (seletor de clínica no DESIGN anterior à U6, "com contagem", barra de status marcada "(ML)" sem estar no memlog, telas CQ Plano/Virtual), dois estados do shell que faltam (banco central fora do ar e "Todas" dentro do módulo), a falta de um percurso do próprio shell e contrastes abaixo de 4,5:1 em informação regulada.

Contagem: **0 bloqueantes · 9 importantes · 10 menores.**

---

## Contradições com o memlog (resumo)

| # | Decisão no memlog | O que o documento diz | Achado |
| --- | --- | --- | --- |
| C1 | U6: seletor lista **só as clínicas permitidas**; físico responsável tem também **Todas** | DESIGN.md → Components ("três botões checáveis exclusivos CEL · BET · DUO") e diagrama da IA em EXPERIENCE.md (`[CEL\|BET\|DUO]`) | 1 |
| C2 | Opção C: "um cartão por módulo, **com contagem**" | EXPERIENCE.md U4: "Contagem nos cartões: **se há**…" | 2 |
| C3 | Nada sobre a barra de status | EXPERIENCE.md atribui ao memlog "usuário · perfil · clínica (ML)" e "degrau de fonte e data do dado (ML)" | 3 |
| C4 | CQ Plano e Virtual: destino **não definido** | Cartão do Radioteraficha lista só Capa-Up, Fichinha, Total, Agenda, mas o texto diz que as duas "continuam onde estão"; a matriz dá ao médico "só Agenda" | 4 |

---

## 1. Cobertura de jornadas — adequada

Conferido: UJ-1 a UJ-5 do PRD (§2.3, extrato §5) contra Key Flows. Todas têm protagonista com nome, passos numerados, clímax marcado e borda quando o PRD traz uma. As lacunas de módulo e de perfil estão declaradas em "Cobertura", o que é coerente com o escopo.

### Achados

5. **importante** — Falta o percurso **do próprio shell**, que é o objeto deste documento: abrir o app → login → Início na última clínica → trocar a clínica → abrir um cartão → faixa do módulo → botão Início. Hoje ele só aparece espalhado entre IA, Component Patterns e as UJ, e a tabela "Cobertura" admite: "troca de clínica, troca dia/noite — tela/ação sem jornada". Quem implementa o shell não tem uma sequência única nem o caso de falha (clínica sem acesso, perfil sem módulo, sessão aberta em outra estação). (EXPERIENCE.md: Key Flows / Cobertura.) *Correção:* acrescentar um fluxo "UJ-0 — entrada no shell" com protagonista (por exemplo, uma técnica com acesso a uma clínica e um físico responsável com Todas), passos numerados e bordas usando os estados que já existem em State Patterns.

6. **menor** — Títulos das jornadas não estão literais: UJ-1 perdeu o "já" ("com a segunda checagem **já** pronta"), e UJ-5 perdeu "achado na revisão". (EXPERIENCE.md: Key Flows.) *Correção:* copiar o título exato do PRD §2.3.

## 2. Completude dos tokens — forte

Conferido: 23 chaves de cor × 2 modos (46 valores, todos hex, conferidos contra extrato §1.1); 15 papéis de tipografia; 8 raios; 16 espaçamentos; todas as referências `{…}` da prosa e dos `components` (todas resolvem, inclusive `{components.selo-em-construcao}`, `{spacing.faixa-margem}`, `{colors.sobre-acao-noite}`). Recalculei os contrastes declarados (3,05; 3,80; 3,74; 3,72; 5,07; 8,02; 5,87; 6,73; 14,99; 15,54) e todos conferem.

### Achados

7. **importante** — Contrastes abaixo de 4,5:1 em informação que o PRD trata como obrigatória e que o documento não lista:
   - `acao` sobre `acao-fundo` no dia = **4,37:1**. É o chip azul e o **estado marcado do seletor de clínica** (`seletor-clinica.checked-*`), ou seja, a clínica ativa.
   - Selo "em construção" = `texto-apagado` sobre `fundo-campo` = **2,94:1**, contra a regra do próprio Accessibility Floor ("não usar `texto-apagado` para informação necessária"). O título do cartão em construção também é `texto-apagado` (3,05:1).
   - Selo de degrau de fonte âmbar (espelho local / relatório exportado) usa o chip âmbar: **3,74:1** no dia. É o anúncio exigido por FR-9/NFR-3.
   Os chips de 15px/600 não contam como texto grande no WCAG.
   (DESIGN.md: Colors, NOTE de contraste; Components → componentes novos. EXPERIENCE.md: Accessibility Floor.) *Correção:* como a paleta não muda (regra da equipe), acrescentar esses três pares à NOTE de contraste e decidir uma das saídas sem token novo: título e selo do cartão em construção em `texto-fraco` (5,87/6,73); selo de degrau com a palavra em `texto` e só a borda ou o fundo em âmbar. Levar a escolha ao usuário.

8. **importante** — Não há especificação do **foco de teclado**. O Accessibility Floor exige "todo destino do shell alcançável por teclado", mas o extrato §1.1 registra que "não há token para cor de foco separada", e nenhum documento diz como o foco aparece hoje (retângulo do Fusion? `Highlight` da paleta Qt, `aparencia._paleta_dark`?). Cartão de módulo e linha de pendência são superfícies clicáveis novas, sem precedente de foco. (DESIGN.md: Components; EXPERIENCE.md: Accessibility Floor.) *Correção:* documentar o foco que existe no código (fonte e cor) e declarar que os componentes novos o seguem; se não existir, registrar como [NOTE FOR UX] em aberto, sem inventar token.

9. **menor** — `seletor-clinica.base: 'estilo._estilo_btn_sel'` aponta para código, não para token, e não segue a sintaxe `{path.to.token}`. (DESIGN.md: frontmatter `components`.) *Correção:* manter o nome do código num comentário e dar ao componente os tokens (`{colors.acao-linha}` na borda, `{typography.botao}`), como os outros componentes.

10. **menor** — Componentes da tabela "existentes" sem entrada no frontmatter: Seletor checável/menu, Valor/ValorTrio, Dialogo, Grade de leitura; e o `botao-fantasma` não leva a tipografia 600 (está só no comentário de `typography.botao`). (DESIGN.md: frontmatter × Components.) *Correção:* acrescentar ao menos `dialogo` e `seletor` (usados pelo shell); `botao-fantasma.typography` com peso 600.

## 3. Cobertura de componentes — adequada

Conferido: componentes com nome em qualquer um dos dois documentos, comparando DESIGN.md → Components (visual) com EXPERIENCE.md → Component Patterns (comportamento).

| Componente | DESIGN (visual) | EXPERIENCE (comportamento) |
| --- | --- | --- |
| Topo do Início | só [ASSUMPTION] em Layout & Spacing | sim |
| Painel "O que precisa de ação" | só como `Cartao` em Layout | sim |
| Linha de pendência | sim | sim |
| Cartão de módulo / em construção | sim | sim (uma linha) |
| Faixa do módulo / botão Início | "Faixa de telas" + "Botão Início" | "Faixa do módulo" |
| Seletor de clínica | sim (desatualizado, ver 1) | sim |
| Chip de severidade | sim | não (sem regra própria) |
| Selo de degrau de fonte | sim | sim |
| Selo "em construção" | sim | dentro de Cartão de módulo |
| Barra de status | sim | sim |
| Tela "em construção" | não | só [ASSUMPTION] |

### Achados

1. **importante — contradição com o memlog (C1).** O seletor de clínica do DESIGN.md ainda descreve "três botões checáveis exclusivos CEL · BET · DUO", e o diagrama da IA mostra `[CEL|BET|DUO]` fixo. O memlog (U6, resolvida) diz que o seletor lista **só as clínicas a que a pessoa tem acesso** e que o físico responsável tem também **Todas**. Quem constrói a partir do DESIGN faz um seletor fixo de três. (DESIGN.md: Components → componentes novos, linha "Seletor de clínica"; EXPERIENCE.md: Information Architecture, diagrama.) *Correção:* "um botão checável por clínica permitida, na ordem CEL · BET · DUO; o físico responsável tem também **Todas** ao fim"; ajustar o diagrama para `[clínicas permitidas | Todas*]`.

11. **menor** — Nomes diferentes para a mesma peça: "Faixa de telas (barra de modo)" (DESIGN) × "Faixa do módulo" (EXPERIENCE); painel "Pendências" (memlog) × "O que precisa de ação" (EXPERIENCE, glossário do PRD). (Os dois documentos.) *Correção:* adotar "faixa do módulo" e "painel O que precisa de ação" nos dois arquivos, com uma linha dizendo que "Pendências" é o mesmo painel.

12. **menor** — O Chip de severidade não tem regra de comportamento (clicável ou não; o que acontece com `informativo`), e a tela "em construção" não tem visual. (EXPERIENCE.md: Component Patterns; DESIGN.md: Components.) *Correção:* uma linha em cada: o chip não é clicável; a tela em construção é `Cartao` com o nome do módulo e uma frase em `texto-fraco`, sem dado.

## 4. Cobertura de estados — fina

Conferido, por superfície: Login, Início (topo, painel, cartões), Módulo (faixa), Configurações, barra de status.

### Achados

13. **importante** — Falta o estado **banco central fora do ar / sem rede até o servidor da clínica** (G6: banco central no servidor da clínica). O documento cobre só o `variandw` fora (NFR-7). Sem o banco não há painel, assinatura nem pendência, e o arranque hoje "aquece conexão do banco" antes do login (extrato §4). (EXPERIENCE.md: State Patterns.) *Correção:* acrescentar uma linha "Banco central inacessível" com o tratamento atual do arranque (citar o código) e a regra mínima: nada é mostrado como em dia ou `conforme` por falta de dado; o detalhe fica para a arquitetura.

14. **importante** — "Todas" dentro do módulo não está definido. O seletor só existe no Início ("troca de clínica só no Início"), mas o físico responsável pode estar em **Todas** e abrir Plano, Garantia da Qualidade etc. Não está dito se o módulo abre com as três clínicas, se pede uma, ou o que a barra de status mostra. (EXPERIENCE.md: Clínica em contexto; State Patterns.) *Correção:* escolher uma regra (por exemplo: o módulo herda "Todas" e mostra a coluna Clínica; a barra de status diz "Todas") ou registrar como questão em aberto U9.

15. **menor** — Estados ainda sem tratamento: pessoa com acesso a **uma só** clínica (o seletor aparece com um botão ou some?); pendência de clínica que a pessoa não pode ver; erro de login (senha errada). (EXPERIENCE.md: State Patterns.) *Correção:* uma linha para cada; o login pode citar o comportamento atual de `DialogLogin`.

16. **menor** — O cartão **Indicadores** está como "protótipo" na tabela dos 9 cartões, mas o memlog só prevê dois estados de cartão (existe / "em construção"). Não está dito se o cartão abre a tela atual do Radioteradados ou o selo. (EXPERIENCE.md: "Os 9 cartões do Início".) *Correção:* decidir com o usuário ou marcar [ASSUMPTION]: "abre a tela atual `radioteradados_tela`, que já diz 'em construção' no núcleo RDC 20".

## 5. Cobertura de referências visuais — forte (não se aplica)

`imports/` está vazio; não há `mockups/` nem `wireframes/`. O esboço ASCII da opção C (memlog, evento) aparece como o diagrama da IA. Nenhum arquivo órfão. Como não há referência visual, a frase "o documento vence em caso de conflito" não é necessária.

## 6. Excesso e especificação demais — adequada

### Achados

17. **menor** — O DESIGN.md traz uma auditoria de código que não muda nenhuma decisão visual do shell: "Escapes da trava visual" (`QDialog(...)` instanciado, folhas sem `pintar`), docstrings defasados, três estilos de seletor. É útil, mas o destino é uma lista de dívida técnica, não o contrato visual. (DESIGN.md: Components, as quatro últimas NOTE FOR UX.) *Correção:* reduzir a uma linha com remissão a `.working/extrato-interface-atual.md` §6, mantendo só as NOTE que afetam componentes do shell (verde no ícone e no brilho; chip "verde"; ausência de `VERMELHO_FUNDO`).

18. **menor** — A tabela "Linguagem honesta e segurança do paciente" repete FRs do PRD. Ela se justifica porque transforma cada FR em efeito na tela, mas parte das linhas (divergência ARIA × RT Plan, marcas textuais de FR-14/15/27) é detalhe de módulo. (EXPERIENCE.md.) *Correção:* manter as regras transversais (advisory, `indeterminado`, "sem data", degrau, sombra, dado de paciente, verde) e mover as outras para os documentos de cada módulo quando forem escritos.

## 7. Disciplina de herança — fina

Conferido: `sources` (todos os caminhos resolvem no disco); `design: ./DESIGN.md`; referências de token do EXPERIENCE (`{colors.texto-fraco}`, `{colors.texto}`, `{colors.fundo-tela}`, `{colors.texto-apagado}`, `{typography.dica}`), que resolvem todas; glossário (Aprovação Física, Duplo Check, `indeterminado`, severidades, degrau de fonte), que confere.

### Achados

3. **importante — atribuição falsa ao memlog (C3).** O EXPERIENCE.md marca como "(ML)" o conteúdo da barra de status ("esquerda: usuário · perfil · clínica (ML); direita: degrau de fonte e data do dado (ML)") e "A clínica ativa aparece sempre na barra de status (ML)". O memlog não tem nenhuma entrada sobre a barra de status; o que ele registra é "seletor de clínica, dia/noite e usuário **no topo**". Num projeto regulado, rastreabilidade falsa é pior que uma suposição declarada. (EXPERIENCE.md: Information Architecture, diagrama; Clínica em contexto; Component Patterns → Barra de status.) *Correção:* trocar "(ML)" por "[ASSUMPTION]" (o degrau pode citar FR-9/NFR-3) ou confirmar com o usuário e registrar no memlog.

2. **importante — contradição com o memlog (C2).** A decisão de navegação diz "capa de módulos (um cartão por módulo, **com contagem**)". A U4 trata a existência da contagem como aberta ("se há"), e o DESIGN escreve "Contagem (se decidida)". O que pode ficar aberto é **o que** se conta e **de que cor**, não **se** há contagem. (EXPERIENCE.md: Questões em aberto U4; Component Patterns → Cartão de módulo; DESIGN.md: Components → Cartão de módulo.) *Correção:* reescrever U4 como "Contagem nos cartões (decidida no memlog): o que conta e como aparece"; no DESIGN, trocar "(se decidida)" por "posição e tom a decidir (U4)". Se o usuário quiser rever a decisão, registrar no memlog.

4. **importante — contradição interna e com o memlog (C4).** O memlog deixa o destino de CQ Plano e Virtual **não definido**. O EXPERIENCE diz que "até decidir, continuam onde estão", mas: (a) a linha do cartão Radioteraficha lista só "Capa-Up, Fichinha, Total, Agenda"; (b) a matriz dá ao médico "S: só Agenda (fichinha.py:2299-2337)", e esse trecho do código dá ao médico **Virtual e Agenda** e ao dosimetrista, técnico, enfermeiro e recepcionista **Capa-Up, Virtual e Agenda**. O "S" cita uma fonte que diz outra coisa. (EXPERIENCE.md: "Os 9 cartões do Início", linha 1; "Perfil × módulo visível", linha Radioteraficha.) *Correção:* coerente com "continuam onde estão": cartão com "Capa-Up, Fichinha, Total, CQ Plano, Virtual, Agenda (CQ Plano e Virtual provisórias, U1)"; matriz igual ao código (médico: Virtual, Agenda; demais: Capa-Up, Virtual, Agenda; físico: todas).

19. **menor** — O DESIGN.md não lista o `.memlog.md` em `sources`, embora os componentes novos do shell (cartão de módulo, seletor de clínica, botão Início) venham de decisões do memlog. (DESIGN.md: frontmatter.) *Correção:* acrescentar `.memlog.md` às fontes.

## 8. Forma — forte

DESIGN.md: as seções seguem a ordem canônica (Brand & Style → Colors → Typography → Layout & Spacing → Elevation & Depth → Shapes → Components → Do's and Don'ts). EXPERIENCE.md: tem todos os padrões obrigatórios (Foundation, IA, Voice and Tone, Component Patterns, State Patterns, Interaction Primitives, Accessibility Floor, Key Flows). As seções inventadas (Perfis e visibilidade; Clínica em contexto; Linguagem honesta; Questões em aberto) se justificam. Inspiration não se aplica (sem produto de referência no memlog). Responsive não é obrigatório (uma janela maximizada), mas a grade de cartões não tem número de colunas nem resolução mínima das estações (DESIGN.md: Layout & Spacing); isso já está declarado como não decidido.

### Achados

- **menor** (sem número) — A U2 está na tabela "Abertas desta UX" marcada "decidido", e U6/U7 aparecem riscadas como "RESOLVIDA". Para quem lê, uma tabela de abertas com itens fechados confunde. *Correção:* mover U2, U6 e U7 para uma linha "Resolvidas" (com o pendente da U2 de atualizar PRD, `escopo.md` e `auth.PAPEIS`).

---

## Observação sobre a regra "documenta, não propõe"

O DESIGN.md respeita a regra na paleta e nos componentes existentes. Os componentes novos do shell trazem quatro escolhas visuais sem precedente, todas marcadas [ASSUMPTION]: hover em linha de pendência (a grade atual **não tem** hover), borda `acao-linha` no hover do cartão, chip `informativo` neutro e selo de degrau âmbar. Estão corretamente sinalizadas, mas pedem confirmação explícita do usuário antes da implementação, porque são as únicas propostas visuais do documento.

## Notas mecânicas

- Os caminhos de `sources` resolvem (`prd.md`, `addendum.md`, `estilo.py`, `ui.py`, `aparencia.py`, `test_padrao_visual.py`, extratos).
- Conferido no código: `MODO_PADRAO = "noite"` (estilo.py:96); `PAPEIS` em auth.py:45; tom "verde" do Chip = ACAO_FUNDO/ACAO (ui.py:483); recorte por papel em fichinha.py:2296-2337 (ver achado 4).
- Contrastes recalculados (WCAG 2.x): os declarados conferem; os novos estão no achado 7.
- Não há Mermaid; o diagrama da IA é texto e está bem formado.
- Nomes inconsistentes: "Faixa de telas" / "Faixa do módulo"; "Pendências" / "O que precisa de ação"; "médico radioterapeuta" (memlog) / "Médico" (matriz) / "radioterapeuta" (PRD): aceitável, mas convém fixar um nome no glossário.
