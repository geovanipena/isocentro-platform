---
name: ISOCENTRO
status: final
created: 2026-10-16
updated: 2026-10-18
design: ./DESIGN.md
sources:
  - ../prd-isocentro-2026-10-16/prd.md
  - ../prd-isocentro-2026-10-16/addendum.md
  - ./.memlog.md
  - ./mockups/torre-inicio.html
  - ./mockups/torre-modulo.html
  - ./mockups/color-themes-1.html
  - ./review-rubric.md
  - ./.working/extrato-prd.md
  - ./.working/extrato-interface-atual.md
---

# ISOCENTRO — Experiência da estrutura global

Escopo: **estrutura global** — shell, Início, módulos, navegação, perfis, clínica. O detalhe interno de cada módulo fica para sessões próprias; cada módulo aparece aqui em uma linha. As questões abertas do PRD §15 continuam abertas.

Convenções: `§n`, `FR-n`, `NFR-n`, `UJ-n`, `SM-n` = PRD; `Add.` = addendum do PRD; `I`/`P`/`G`/`C` + número = questão do PRD §15; `U` + número = questão desta UX; `ML n` = entrada n do `.memlog.md` desta UX; `arquivo:linha` = código atual. [ASSUMPTION] = não rastreável ao memlog, ao PRD, aos mockups aceitos nem ao código; "[ASSUMPTION: X]" diz o que foi suposto, e "[ASSUMPTION — sem definição: X]" diz o que ainda falta decidir.

Composição de referência: [mockups/torre-inicio.html](./mockups/torre-inicio.html) e [mockups/torre-modulo.html](./mockups/torre-modulo.html) (aceitos, ML 32). **Este documento e o DESIGN.md vencem os mockups em conflito.**

## Foundation

Aplicativo desktop Windows, uma janela maximizada, um só shell PyQt5 (`isocentro/interface/`) que hospeda todos os módulos; nenhum módulo do MVP abre fora dele e não há Streamlit no MVP (§4.2, FR-9). Estações nas três clínicas (CEL, BET, DUO), mesma rede corporativa (Add., G3). Banco central em servidor da clínica, fora do ARIA/`variandw` (G6). O ISOCENTRO só lê o ARIA/Eclipse (NFR-1) e é advisory: avisa e registra, nunca bloqueia (FR-5).

Identidade visual **nova**, "Torre de controle", para o ISOCENTRO inteiro (ML 26–28); a referência é o `DESIGN.md`. **A identidade nova exige migrar o Radioteraficha**: as telas atuais (Capa-Up, Fichinha, Total, CQ Plano, Virtual, Agenda) passam para os tokens e componentes novos; não convivem dois padrões (ML 27; ver Migração abaixo).

### Migração (nota para a arquitetura)

A identidade nova substitui o padrão atual em todo o ISOCENTRO (ML 27). O que terá de mudar, sem detalhar a implementação:

| Arquivo | Muda |
| --- | --- |
| `isocentro/interface/estilo.py` | paletas `DIA`/`NOITE` trocadas pelas 23 chaves do DESIGN.md; o acento verde-azulado e os apelidos `AZUL*`/`VERDE*` saem; o modo padrão continua noite |
| `isocentro/interface/ui.py` | componentes refeitos com os tokens novos: chip de severidade com forma, linhas com borda lateral, botões (o brilho verde de `ui.botao(brilho=True)` sai), abas sublinhadas |
| `tests/test_padrao_visual.py` | o teste passa a conferir contra a paleta nova e a **reprovar verde fora da dose** (o token `dose` só nos arquivos de isodose), inclusive em `QColor(r,g,b)` |

O mapeamento dos botões atuais (`btn_solido`, `btn_contorno`, `btn_fantasma`, `btn_perigo`) para os pesos novos está em DESIGN.md → Components → Ações.

## Information Architecture

```text
login ──► INÍCIO (Torre de controle) ────────────────────────────────────────┐
          ┌ topo: ◎ ISOCENTRO · [clínicas permitidas | Todas*] · relógio · ☾/☀ · usuário
          ├ 1 SITUAÇÃO DO SERVIÇO  coluna por clínica: máquinas (sinal · motivo · agenda)
          │                        + filas (Duplo Check · Aprovação Física · Vencimentos 60d)
          │      máquina com problema / fila ──► MÓDULO filtrado (clínica, máquina, fila)
          ├ 2 O QUE PRECISA DE AÇÃO  5 linhas + "ver mais N" · [Abrir fila]
          │      linha ──► módulo de origem, no item
          └ 3 MÓDULOS  doca de 9, sem contagem ──► MÓDULO em tela cheia
                                                   ◂ Início · nome · abas · contexto · ☾/☀
barra de status (sempre): usuário · perfil · clínica │ degrau do dado · data ───────┘
```

\* "Todas" só para o físico responsável (U6).

| Superfície | Chega por | Para quê |
| --- | --- | --- |
| Login | abrir o app | identidade; troca de senha forçada quando exigida (administracao.py:88-135) |
| Início | após o login; "◂ Início" em qualquer módulo | situação do serviço, o que precisa de ação e porta dos módulos (ML 30) |
| Módulo | bloco da doca; máquina com problema; fila; linha de ação | trabalho do módulo em tela cheia, com a sua faixa de telas e "◂ Início" (ML 12, 32) |
| Configurações | "Configurações" na barra de status, só com permissão admin | Serviço, Usuários, Equipe, Máquinas (administracao.py:944-982) |
| Diálogos | dentro dos módulos | `ui.Dialogo`, no máximo um nível (sem diálogo sobre diálogo) [ASSUMPTION] |

O painel da Zona 2 é o mesmo que o memlog chama de "Pendências" (ML 13, 16); o nome na tela é "O que precisa de ação" (glossário do PRD, FR-41). Nos dois documentos, **topo do módulo** é a linha inteira (◂ Início · nome · abas · contexto) e **faixa de telas** são só as abas.

### Os 9 módulos da doca (ML 17, 18)

| Ordem | Módulo | Uma linha (§10, ML) | Bloco |
| --- | --- | --- | --- |
| 1 | Radioteraficha | ficha, capa e agenda: Capa-Up, Fichinha, Total, Agenda; CQ Plano e Virtual provisórias até a decisão de U1 | sem selo |
| 2 | Plano | segunda checagem (MVP 1); Aprovação Física e Duplo Check com segunda assinatura (MVP 2) | em construção |
| 3 | Tratamento | 1ª fração e contagem de frações no MVP; revisão semanal depois | em construção |
| 4 | Garantia da Qualidade | programa de CQ por clínica e máquina, lista do dia, carta de controle (MVP 3) | em construção [ASSUMPTION, ML 28] |
| 5 | Segurança do paciente | incidentes e quase-incidentes, prazos art. 26 e RDC 36, envio ao Epimed (MVP 4) | em construção |
| 6 | Documentação e conformidade | vencimentos, painel, aferição com decaimento, migração do ppr-streamlit (MVP 5) | em construção |
| 7 | Software e sistemas | cobertura, inventário SOUP, integridade, relatório de validação | em construção |
| 8 | Indicadores | o antigo Radioteradados, saído do Radioteraficha | sem selo (abre a tela atual `radioteradados_tela`) [ASSUMPTION] |
| 9 | Conhecimento | proveniência de cada verificação; mapa e biblioteca de regras depois | em construção |

A ordem é a da lista do memlog e a do mockup. A doca **não tem contagem** (ML 30; substitui "cartões com contagem" da ML 12). Bloco "em construção": ver State Patterns. Busca de paciente existe só dentro dos módulos; o shell não tem busca global (ML 19).

## Perfis e visibilidade

Sete perfis do fluxo da radioterapia (ML 14): **médico radioterapeuta, físico, dosimetrista, técnico, enfermeiro, recepcionista, SPR/gestão**. Admin deixa de ser perfil e vira permissão concedida a uma pessoa (ML 14); dá acesso às Configurações. Cada usuário tem um perfil (FR-7); não há troca de perfil na sessão.

[NOTE FOR UX] Divergência com o PRD: §2.1 e FR-7 fixam cinco perfis (físico, dosimetrista, radioterapeuta, técnico, SPR/gestão). O código (`auth.PAPEIS`, dados/auth.py:45-46) tem admin, fisico, medico, dosimetrista, tecnico, enfermeiro, recepcionista: falta SPR/gestão e admin ainda é papel em `auth.PAPEIS`. A UX segue os 7 (ML 23); ver U2.

"Físico responsável" não é perfil: é o físico que vê as três clínicas (NFR-6, FR-41) [ASSUMPTION: atributo da pessoa, como admin].

### Perfil × módulo visível

S = sustentado pelo PRD ou pelo código; A = [ASSUMPTION]; "sim" = visível; "A: —" = não visível, por suposição.

| Módulo | Médico | Físico | Dosimetrista | Técnico | Enfermeiro | Recepcionista | SPR/gestão |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Radioteraficha | S: Virtual, Agenda (`MODOS_POR_PAPEL`, fichinha.py:2302) | S: todas | S: Capa-Up, Virtual, Agenda (`MODOS_PADRAO`) | S: idem | S: idem | S: idem | A: — |
| Plano | S: ver se o plano passou pelas conferências (§2.1) | S: Aprovação Física, Duplo Check, cadastros (FR-10–20) | S: 2ª checagem, Lista de Planejamento (§2.1, FR-42) | A: — | A: — | A: — | A: — |
| Tratamento | A: sim | S: contagem de frações (FR-15, FR-16) | A: — | A: sim | A: sim | A: — | A: — |
| Garantia da Qualidade | A: — | S: cadastra testes, ações, carta (FR-23, FR-25) | A: — | S: registra execução (FR-23, UJ-3) | A: — | A: — | A: só leitura |
| Segurança do paciente | S: registra (FR-29) | S: registra, revisão periódica (FR-29, FR-32) | S: registra (FR-29, UJ-5) | S: registra | S: registra | S: registra | S: registra; acompanha (§2.1) |
| Documentação e conformidade | A: — | S: vencimentos, aferição (FR-33, FR-36) | A: — | A: — | A: — | A: — | S: cadastra e acompanha (FR-33, §2.1) |
| Software e sistemas | A: — | S: cadastra, promove, poda verificação (FR-7) | A: — | A: — | A: — | A: — | A: — |
| Indicadores | A: — | S: Radioteradados, no app atual visível a admin/físico (fichinha.py:2299-2337) | A: — | A: — | A: — | A: — | S: acompanha (§2.1) |
| Conhecimento | A: sim | A: sim | A: sim | A: sim | A: sim | A: sim | A: sim |

Regras de visibilidade:

- Módulo não visível para o perfil: o bloco da doca **some** (ML 22, U7).
- Segurança do paciente aparece para todos porque qualquer perfil registra incidente (FR-29). Quem lê texto livre e dose estimada é a questão I2, aberta.
- Assinar exige o usuário logado na sessão atual; nunca em nome de outro (FR-8). O segundo físico do Duplo Check não pode ser o da Aprovação Física (FR-20).
- Verificação em `sombra` é invisível: não aparece, não alerta, não entra em fila, contador ou sinal de máquina (FR-4).
- Permissão admin não amplia módulos [ASSUMPTION: a pessoa mantém o perfil e ganha só as Configurações].
- A Zona 1 é a mesma para todos os perfis: máquinas, agenda e as três filas [ASSUMPTION: o memlog não recorta a Zona 1 por perfil]. A Zona 2 é filtrada pelo perfil (ML 13); o conteúdo por perfil é U3.

## Clínica em contexto

| Regra | Fonte |
| --- | --- |
| Seletor de clínica no topo do **Início**, para qualquer pessoa, lembrando a última escolha | ML 15 |
| Lista só as clínicas a que a pessoa tem acesso; o físico responsável tem também "Todas" | ML 21 (U6) |
| A clínica escolhida define as colunas da Zona 1 (uma por clínica; três em "Todas") e filtra a Zona 2 | ML 30 |
| **Dentro do módulo não há seletor de clínica**: vale a clínica do contexto, mostrada no topo do módulo ("DUO · VitalBeam 4199") e na barra de status | ML 32 |
| Aberto pela Zona 1 ou por uma linha de ação, o contexto é a clínica (e a máquina) do elemento clicado | ML 30; mockup torre-modulo |
| Aberto pela doca com "Todas" marcada: o módulo abre em "Todas", com as 3 clínicas juntas e uma coluna ou etiqueta "Clínica" em cada item; a barra de status diz "Todas" | ML 31 |
| Pessoa com uma só clínica: o seletor aparece com um segmento, já marcado, e a Zona 1 tem uma coluna (largura em DESIGN.md → Layout & Spacing) | [ASSUMPTION] |
| Lembrança da última clínica por usuário (noite/dia é por estação) | [ASSUMPTION] |

Assim se mantém a regra de cada clínica ver só os próprios dados (NFR-6). Quem tem acesso a que clínica fica no cadastro de usuários [ASSUMPTION].

## Voice and Tone

Microcopy em pt-BR, com o glossário do PRD §3. A postura visual está no `DESIGN.md`.

| Faça | Não faça |
| --- | --- |
| "Duplo Check pendente — antes da 1ª fração" | "Atenção! Tarefa atrasada!" |
| Motivo escrito na máquina: "CQ diário fora da tolerância", "CQ mensal vence hoje" | sinal sem motivo |
| "normal" para máquina sem problema | "ok!", "tudo certo", "em dia" |
| "`indeterminado`: o cálculo não trata filtro" | "Não foi possível verificar" sem motivo |
| "sem data" | "em dia" para item sem data de partida |
| "origem: literatura, não derivado do serviço" | "demonstração" (o rótulo sai, FR-12, FR-13) |
| "variandw ● ao vivo · 18/10 07:41" | dado sem data e sem degrau |
| "visto · Bruno · 07:12" | "lido" sem quem e quando |
| Planning Approved, Treatment Approved, RT Plan, `SOPInstanceUID` em inglês, como no ARIA | traduzir termo do ARIA |
| verbo no botão: "Abrir fila", "Registrar repetição", "Assinar" | "OK", "Sim" (ui.confirmar exige verbo, ui.py:1200) |
| citar a norma no item: "NN-6.10 art. 17, IV" | regra sem fonte |

Nada de exclamação, emoji ou elogio. "Conforme" nunca é digitado pelo usuário; o resultado vem da tolerância (FR-23).

## Linguagem honesta e segurança do paciente

Regras transversais do PRD, valem para o shell e todo módulo:

| Regra | Fonte | Efeito na tela |
| --- | --- | --- |
| Advisory, nunca bloqueia | FR-5, §1 | nenhum botão desabilitado por resultado de verificação; `nao_conforme` em `alta` pede justificativa a quem prosseguir, sem impedir |
| `indeterminado` nunca vira `conforme` | §3, FR-2, FR-13 | aparece com o motivo (◆ atenção na Zona 2 do mockup); não conta como "normal" |
| `erro` nunca vira `conforme` | FR-2 | mostra a mensagem |
| "sem data" nunca vira em dia | FR-33, UJ-4 | rótulo próprio (○ INFO no mockup) |
| Campo sem fonte nasce vazio | NFR-4, FR-16 | a tela diz o que falta |
| Degrau de fonte anunciado (de onde vem o dado: ● ao vivo do `variandw`, ◌ espelho local ou relatório exportado) | FR-9, NFR-3 | selo ao vivo / espelho hh:mm / relatório + data, na barra de status e no cabeçalho da Zona 1 (agenda); com o `variandw` fora, ver State Patterns |
| Nenhum dado de paciente sai da rede | NFR-2, FR-29 | exportação sem identificação |

Valem também, sem repetir aqui: verificação em `sombra` invisível (FR-4; ver Perfis e visibilidade), verde só em isodose (ML 27; DESIGN.md → Colors) e severidade IEC 60601-1-8 com forma e palavra junto da cor (ML 29; DESIGN.md → Brand & Style).

## Component Patterns

Comportamento. O visual está em `DESIGN.md` → Components.

| Componente | Onde | Regras de comportamento |
| --- | --- | --- |
| Topo do Início | Início | marca · seletor de clínica · relógio · noite/dia · usuário. Usuário sem menu (mockup) [ASSUMPTION — sem definição: o que o clique faz] |
| Seletor de clínica | topo do Início | segmentos exclusivos; trocar refaz as colunas da Zona 1 e refiltra a Zona 2 na hora; a escolha é lembrada |
| Noite/dia | topo do Início e do módulo | alterna e lembra por estação (`modo_cor`); primeira abertura em **noite** (ML 32, U5) |
| Zona 1 — linha de máquina | coluna de clínica | normal: neutra, sem fundo; com problema: realçada com a pior severidade e o motivo (ML 32). Agenda do dia: nº de pacientes hoje e próximo horário, do `variandw` (ML 30). Clique na máquina com problema abre o módulo de origem do motivo, filtrado na clínica e na máquina (mockup torre-modulo) [ASSUMPTION — sem definição: destino do clique na máquina normal] |
| Zona 1 — contador de fila | pé da coluna | Duplo Check, Aprovação Física, Vencimentos 60d (ML 30); clique abre o módulo da fila filtrado pela clínica e pela fila (ML 30); "▲n" diz quantos itens têm severidade alta |
| Zona 2 — painel "O que precisa de ação" | Início | fila do perfil e da clínica; ordem: severidade (alta → atenção → informativo) e, dentro dela, prazo (FR-41); mostra as 5 primeiras e "ver mais N" (ML 30); o rótulo da zona traz o total. Mesmo alerta aparece também no módulo de origem (FR-41) |
| Linha de ação | Zona 2 | clique abre o módulo de origem no item [ASSUMPTION: no item, não só no módulo]. Estados aberto → visto → resolvido; visto grava quem e quando (FR-41); visual do visto decidido (ML 32); **como** marcar visto é U8; resolver um `alta` pede justificativa (FR-41) |
| "ver mais N" | rodapé da Zona 2 | mostra as demais linhas no próprio painel [ASSUMPTION] |
| "Abrir fila" | rodapé da Zona 2 | primário único da tela; abre a lista completa do perfil [ASSUMPTION — sem definição: destino] |
| Chip de severidade | linhas, tabela, cartão de alerta | não clicável |
| Bloco da doca | Zona 3 | clique abre o módulo em tela cheia; sem contagem; bloco "em construção": ver State Patterns |
| Topo do módulo | topo do módulo | "◂ Início" à esquerda; faixa de telas recortada pelo perfil; contexto (clínica · máquina) à direita; sem seletor de clínica (ML 32). Cada tela recarrega ao aparecer (gui.py:821-907) |
| "◂ Início" | topo do módulo | volta ao Início na clínica que estava marcada; Zonas 1 e 2 recarregam [ASSUMPTION: recarga] |
| Selo de degrau | barra de status; cabeçalho da Zona 1; telas com dado do `variandw` | sempre visível quando há dado do `variandw`; diz o degrau e a data (FR-9, NFR-3; ML 30) |
| Barra de status | toda superfície depois do login | esquerda: usuário · perfil · clínica (do contexto, no módulo); direita: degrau e data (mockups); "Configurações" só com permissão admin [ASSUMPTION — sem definição: posição]; mensagens transitórias como no app atual |
| Pop-ups | qualquer | `ui.avisar/alertar/falhar/confirmar/escolher`; botão de confirmar à esquerda, cancelar à direita; em diálogo `perigo`, Enter não confirma (ui.py:1025-1276) |

## State Patterns

| Estado | Superfície | Tratamento |
| --- | --- | --- |
| Primeira abertura da estação | Início | modo **noite** (ML 32) |
| Abertura do dia | Início | direto no Início, na última clínica (ML 13, 15) |
| Prazo venceu com o app fechado | Zona 2 | entra como `alta` na abertura seguinte (FR-41) |
| Tudo normal numa clínica | Zona 1 | máquinas neutras; filas com zero em `{colors.texto-secundario}`; nenhum verde, nenhum selo de OK |
| Nada precisa de ação | Zona 2 | uma frase em `{colors.texto-secundario}`: "Nada precisa de ação nesta clínica." [ASSUMPTION — sem definição: texto]; sem ícone de OK |
| `variandw` fora | Zona 1, barra de status, telas | último dado com degrau e data (NFR-7); agenda da máquina com a data do dado; prazos dependentes ficam `indeterminado`; nenhum prazo vira `conforme` e nenhuma máquina vira "normal" por falta de dado |
| Espelho local / relatório exportado | idem | selo do degrau ◌ espelho hh:mm / relatório, com a data |
| **Banco central inacessível** (servidor da clínica, G6) | arranque, login, Início | o arranque aquece a conexão antes do login (`capa_db.aquecer()`, arranque.py:153-159). Sem o banco: Zonas 1 e 2 não mostram máquina "normal", fila zero nem "Nada precisa de ação"; mostram que o dado não está disponível e desde quando [ASSUMPTION — sem definição: texto e tela]; nada como em dia ou `conforme` por falta de dado. Detalhe fica para a arquitetura (review-rubric 13) |
| Módulo aberto com "Todas" | módulo | abre em "Todas" (ML 31; ver Clínica em contexto) |
| Pessoa com uma só clínica | Início | ver Clínica em contexto |
| Módulo em construção | doca e tela | selo "em construção" no bloco; o bloco abre uma tela que diz só isso, sem dado fictício [ASSUMPTION] |
| Perfil só com Segurança/Conhecimento | doca | só os blocos visíveis [ASSUMPTION] |
| Pendência de módulo ou clínica que a pessoa não vê | Zona 2 | não aparece [ASSUMPTION] |
| Trabalho bloqueante | qualquer | `ui.trabalhando` com mensagem; os painéis carregam em menos de 3 s (NFR-5) |
| Sessão aberta em outra estação | qualquer | este app fecha (sessão única, gui.py:643+) |
| Senha a trocar | login | `DialogTrocarSenha` obrigatório: não fecha sem trocar a senha |
| Senha errada | login | comportamento atual do `DialogLogin` [ASSUMPTION] |
| Exceção não tratada | qualquer | caixa `ui.falhar` da rede de segurança (arranque.py:42-101) |

## Interaction Primitives

Mouse e teclado, desktop. Clicável = hover em `{colors.superficie-elevada}` (linhas com severidade clareiam), cursor de mão, sem ícone de seta (mockup).

Foco de teclado:

| Item | Regra |
| --- | --- |
| Anel | 2 px `{colors.foco}`, afastado 2 px, em todo elemento clicável (DESIGN.md → Foco) |
| Ordem de Tab no Início | topo (seletor de clínica → noite/dia → usuário) → Zona 1 (coluna da esquerda para a direita; em cada coluna, máquinas de cima para baixo e depois as 3 filas) → Zona 2 (linhas na ordem da lista → "ver mais N" → "Abrir fila") → Zona 3 (doca da esquerda para a direita) → barra de status (Configurações, se admin) [ASSUMPTION] |
| Ordem de Tab no módulo | "◂ Início" → faixa de telas → noite/dia → usuário → conteúdo do módulo [ASSUMPTION] |
| Foco inicial no Início | primeira linha da Zona 2 [ASSUMPTION] |
| Atalho para o Início | **Alt+Home**, de qualquer módulo [ASSUMPTION — sem definição: atalho] |
| Enter / Espaço | ativa o elemento com foco (abre a máquina, fila, linha ou módulo) |

Preservado do shell atual:

- **Ctrl+Tab / Ctrl+Shift+Tab** circulam as abas da faixa de telas do módulo aberto, recortadas pelo perfil (gui.py:463-474, 787-800).
- **Ctrl+P / Ctrl+Enter** disparam a ação principal (o primário da tela) (gui.py:759-768). Nenhum atalho em ação destrutiva (ui.py:1260-1276); o atalho aparece no tooltip.
- **Ctrl+O, Ctrl+E, Ctrl+H, Ctrl+G** continuam atalhos do Radioteraficha [ASSUMPTION: escopo do módulo, não globais].
- **Enter** confirma e **Esc** cancela nos diálogos (ui.py:1025).

Proibido: botão desabilitado por resultado de verificação (FR-5); verde como sinal; diálogo sobre diálogo [ASSUMPTION].

## Accessibility Floor

O PRD não trata acessibilidade. Piso [ASSUMPTION, derivado da base científica da ML 29 e da página de paletas ([mockups/color-themes-1.html](./mockups/color-themes-1.html))]:

- Severidade nunca só por cor: forma (▲ ◆ ○) e palavra (ALTA, ATENÇÃO, INFO) sempre juntas. No dia, a distinção entre os sinais depende da forma (DESIGN.md → Daltonismo).
- Contraste: todo texto ≥ 4,5:1 e todo sinal, ícone e foco ≥ 3:1, nos dois modos (DESIGN.md → Contrastes). Atenção e informativo no dia ficam em 3,03:1: não usar o sinal sozinho para informação necessária.
- Todo destino do shell alcançável por teclado, com foco visível (ver Interaction Primitives).
- Nada abaixo de 10 px (`{typography.selo}`).
- Botão nunca sem rótulo de texto; emoji não é ícone; ícones SVG acompanham o nome.
- Números tabulares em toda a janela.

## Key Flows

Percurso **pela Torre**. O que acontece dentro do módulo vem do PRD (§2.3); os nomes das pessoas são ilustrativos.

### UJ-0 — Entrada no shell: Carla (técnica, só DUO) e Geovani (físico responsável, Todas)

1. Carla abre o app; o arranque aquece a conexão com o banco enquanto ela digita usuário e senha.
2. Login; se a senha precisa ser trocada, `DialogTrocarSenha` antes de tudo.
3. O Início abre em noite, na DUO (única clínica dela): uma coluna na Zona 1, a Zona 2 do perfil técnico, a doca com os blocos do perfil.
4. Ela tecla Tab até "Garantia da Qualidade" na doca e Enter: o módulo abre em tela cheia, contexto DUO, sem seletor de clínica.
5. "◂ Início" (ou Alt+Home [ASSUMPTION]) volta ao Início na DUO.
6. Geovani entra em outra estação; o Início abre em "Todas": três colunas.
7. **Clímax:** em 3 segundos ele vê que só o VitalBeam 4199 da DUO está ▲ e que o 6EX 1254 da CEL está ◆; o resto é neutro. Clica em CEL no seletor: a Zona 1 vira uma coluna e a Zona 2 passa a mostrar só a CEL. Volta a "Todas".

Bordas: banco central inacessível → Zonas 1 e 2 dizem que não há dado, sem "normal" nem zero; sessão aberta em outra estação → este app fecha; perfil sem módulo além de Segurança e Conhecimento → doca com dois blocos.

### UJ-1 — Ana, física, faz a Aprovação Física com a segunda checagem já pronta

1. O médico dá Planning Approved no ARIA a uma mama 50 Gy/25 fr no 6EX; o ISOCENTRO roda a segunda checagem na mesma leva do PSQA (FR-11).
2. Ana entra; Início na CEL (última escolha).
3. Na Zona 1, a fila **Aprovação Física** da CEL mostra 2. Ela clica: o módulo **Plano** abre filtrado na CEL e na fila (ML 30).
4. Abre o caso; a barra de status mostra o degrau e a data do dado.
5. **Clímax:** Ana vê a diferença calculado × TPS por campo e no composto, o limite e a origem ("literatura, não derivado do serviço"), percorre os 8 itens e vai ao ARIA dar Treatment Approved. O ISOCENTRO lê a aprovação do `variandw`; a fila cai para 1.
6. "◂ Início" → contador atualizado.

Borda: campo com filtro físico → `indeterminado` com "o cálculo não trata filtro", que aparece como ◆ ATENÇÃO na Zona 2; nada vira `conforme`, nada fica desabilitado.

### UJ-2 — Bruno, segundo físico, faz o Duplo Check antes da 3ª fração

1. Bruno entra; Início.
2. Na Zona 1, a fila Duplo Check da CEL mostra "3 ▲1"; na Zona 2, a primeira linha é "▲ ALTA · Duplo Check · antes da 1ª fração" (alto risco no topo, FR-17).
3. Clica na linha: Plano abre no caso.
4. No caso: os 8 itens do Duplo Check, os automáticos já conferidos do RT Plan e do ARIA, o resultado da segunda checagem.
5. **Clímax:** "Assinar". O ISOCENTRO grava quem, quando e qual versão do plano (`SOPInstanceUID` + status); a linha sai da Zona 2 e o "▲1" some do contador.

Borda: Bruno é o mesmo da Aprovação Física → aviso de que o Duplo Check precisa ser de outro físico; a assinatura não é registrada como Duplo Check (FR-20). O botão não estava desabilitado. Sem mapeamento entre o usuário do ARIA e o do ISOCENTRO → "separação entre os físicos não conferida" + alerta `alta`.

### UJ-3 — Carla, técnica, registra o CQ diário do VitalBeam

1. Antes do primeiro paciente, Carla entra; Início na DUO. O VitalBeam 4199 está neutro, "16 pac. hoje · próx. 08:20".
2. Doca → **Garantia da Qualidade** → Lista do dia da DUO (22 testes).
3. Lança os valores; não digita "conforme" (FR-23). Os testes dentro da tolerância ficam neutros ("dentro").
4. **Clímax:** o output 6 MV dá +3,4% (tol. ±3%). A linha da tabela fica ▲ ALTA, o cartão "Teste fora da tolerância" mostra a ação prevista e o horário do 1º paciente, e a carta de controle ganha um ▲. No Início de todos, o VitalBeam 4199 passa a ▲ "CQ diário fora da tolerância", e a Zona 2 do físico ganha a linha "▲ ALTA · CQ diário VitalBeam".
5. "Registrar repetição" (primário único); "◂ Início".

Borda: rótulo do resultado fora de tolerância de literatura (`nao_conforme` ou só alerta) depende de C1.

### UJ-4 — Geovani, físico responsável, abre a semana pelos vencimentos

1. Geovani entra; Início em **Todas** (U6): três colunas.
2. A fila **Vencimentos 60d** mostra 4 na CEL, 1 na BET, 2 na DUO; a Zona 2 traz "◆ ATENÇÃO · Vencimento · câmara de ionização · 45 dias · BET", já vista por Bruno às 07:12 (borda tracejada).
3. Clica no contador da BET: **Documentação e conformidade** abre filtrado na BET e nos vencimentos.
4. **Clímax:** calibração bienal de um sistema de referência da BET, aferição trimestral com fonte-teste, treinamento anual de PR — e um item sem data de partida, que aparece como "○ INFO · sem data", nunca como em dia.

Prazo que venceu no fim de semana, com o app fechado, já aparece como `alta` na abertura (FR-41).

### UJ-5 — Daniel, dosimetrista, registra um quase-incidente achado na revisão

1. Na revisão, Daniel vê a energia do plano diferente da prescrição e corrige no TPS (fora do ISOCENTRO).
2. "◂ Início" (de qualquer módulo) → doca → **Segurança do paciente**.
3. Registra o quase-incidente: etapa onde ocorreu, etapa onde foi detectado, gravidade (FR-29); liga ao paciente pelo ID do ARIA, sem copiar dado clínico além do necessário.
4. **Clímax:** o registro fica no ISOCENTRO, ligado ao plano, e o físico o vê na revisão trimestral (FR-32).

Variante: incidente com exposição não intencional → prazo de 30 dias e lista do art. 26, que entram na Zona 2 do físico [ASSUMPTION: perfil que recebe].

### Cobertura

| Lacuna | Tipo |
| --- | --- |
| Tratamento, Software e sistemas, Indicadores, Conhecimento | módulo sem jornada |
| Médico, enfermeiro, recepcionista, SPR/gestão | perfil sem jornada |
| Configurações | tela sem jornada |
| Filas Duplo Check, Aprovação Física e Vencimentos 60d apontam para Plano e Documentação, hoje em construção | destino da Zona 1 sem módulo pronto |
| Relatório exportado para auditor/inspetor (FR-40), relatório de sensibilidade (FR-6), consulta ao log (FR-3) | necessidade sem tela no shell |
| Alerta ao físico com o app fechado (canal externo, pós-MVP, FR-41) | sem superfície no MVP |

## Questões em aberto

Do PRD §15, com impacto na UX — todas **ABERTAS**:

| Id | Questão | Impacto na UX |
| --- | --- | --- |
| I2 | Quem lê o texto livre e a dose estimada, por perfil | visibilidade dentro de Segurança do paciente |
| P9 | O que invalida uma assinatura | quando o Duplo Check volta a pendente e reaparece na fila e na Zona 2 |
| P10 | O resultado do paralelo aparece em documento impresso? | se sim, trocar "demonstração" por `indeterminado` muda o documento impresso |
| P11 | A assinatura registrada substitui a do papel ou convive | se o fluxo de assinatura do shell é o único ou corre em paralelo ao papel |
| G4 | Período mínimo de sombra; sombra em produção conta como uso real | quando uma verificação passa a aparecer no sinal, na fila e na Zona 2 |
| G5 | Denominador da cobertura (74 ou 60) | número mostrado em Software e sistemas |
| C1 | Fora de tolerância de literatura no CQ: `nao_conforme` ou só alerta | rótulo e severidade na Garantia da Qualidade, no sinal da máquina e na Zona 2 |
| G8 | Preencher `docs/qms/escopo.md` (perfis, pasta, critério) | tabela de perfis desta UX depende dela |

Desta UX — abertas:

| Id | Questão | Por que importa |
| --- | --- | --- |
| U1 | Destino das telas CQ Plano e Virtual | no app atual ficam no Radioteraficha; candidatas a Plano e Tratamento, sem decisão (ML 18) |
| U3 | Quais pendências cada perfil vê na Zona 2 | o filtro por perfil foi decidido (ML 13), o conteúdo não |
| U8 | Como "visto" é marcado (ação explícita ou ao abrir) | estado do alerta com quem/quando (FR-41); o visual do visto já está decidido (ML 32) |

Desta UX — decididas:

- **U2 decidida:** a UX segue os 7 perfis (ML 23). **Pendente:** atualizar PRD §2.1/FR-7 e `docs/qms/escopo.md` (bmad-prd Update) e o `auth.PAPEIS`.
- **U4–U7 resolvidas** (U4 superada pela doca sem contagem, ML 30; U5 abre em noite, ML 32; U6 só clínicas permitidas, mais "Todas" para o físico responsável, ML 21; U7 bloco sem acesso some, ML 22).
