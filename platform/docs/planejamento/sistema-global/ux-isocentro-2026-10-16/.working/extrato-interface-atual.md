# Extrato da interface atual — ISOCENTRO (16/10/2026)

Fonte: leitura do código em `programa/isocentro` (somente leitura). Caminhos relativos a `isocentro/interface/` salvo indicação. Nada aqui é proposta.

---

## 1. Tokens visuais reais

### 1.1 Cores — paleta de tela (`estilo.py`)

Fonte única: dicionários `DIA` (estilo.py:35-65) e `NOITE` (estilo.py:67-93). Mesmas 23 chaves nos dois. `MODO_PADRAO = "noite"` (estilo.py:96). `_aplicar` reescreve as globais do módulo (estilo.py:129-137).

| Token | DIA | NOITE | Papel (comentário do código) |
|---|---|---|---|
| ACAO | #0F7B7B | #3FBFB6 | acento — verde-azulado do formulário impresso |
| ACAO_FORTE | #0C6262 | #55D2C9 | hover do sólido; hover do link |
| ACAO_CLARA | #12908F | #5AD3C9 | texto de aba selecionada, link |
| ACAO_FUNDO | #E3F1F0 | #123A38 | fundo de hover/seleção/chip azul |
| ACAO_LINHA | #95C4C4 | #2E6E6A | borda do contorno/seletor |
| SOBRE_ACAO | #FFFFFF | #08191A | texto sobre o sólido ("NUNCA branco" na noite, estilo.py:73-75) |
| FUNDO_TELA | #F4F6F8 | #0F1518 | papel/fundo da janela |
| FUNDO_BLOCO | #FFFFFF | #161E22 | cartão, cabeçalho |
| FUNDO_CARTAO | #FFFFFF | #161E22 | página de aba, faixa |
| FUNDO_CAMPO | #FAFBFC | #1D272C | campos, listas |
| FUNDO_FUNDO | #EDEFF2 | #0B1013 | barra de modo, status bar, barra de título nativa |
| TEXTO | #1B2127 | #E6EDEF | tinta |
| TEXTO_FRACO | #5A6672 | #97A6AC | rótulo forte, fantasma |
| TEXTO_APAGADO | #8A95A1 | #6B7A81 | rótulo miúdo, desabilitado |
| BORDA | #D9E0E7 | #26333A | régua padrão |
| BORDA_SUAVE | #E4E9EE | #1F2A30 | borda de cartão/campo |
| BORDA_FORTE | #B9C4CE | #35454E | indicador de checkbox, handle de scroll |
| AMBAR | #B4690E | #E0A63A | semântica — atenção |
| AMBAR_FUNDO | #FBF0DC | #3A2E15 | fundo âmbar; também hover do perigo e fundo do chip vermelho |
| VERMELHO | #B3261E | #E4595E | semântica — erro/perigo |
| VERMELHO_LINHA | #DFA9A5 | #7A3A3D | borda do perigo |
| SELECAO | #0F7B7B | #2E6E6A | realce de seleção do sistema |
| SOBRE_SELECAO | #FFFFFF | #E6EDEF | texto selecionado |

Apelidos legados (estilo.py:117-126), todos para a família ACAO: AZUL→ACAO, AZUL_CLARO→ACAO_CLARA, AZUL_FUNDO→ACAO_FUNDO, VERDE→ACAO, VERDE_ESCURO→ACAO_FORTE, VERDE_CLARO→ACAO_CLARA, VERDE_BRILHO→ACAO_FORTE, VERDE_FUNDO→ACAO_FUNDO. Comentário: "~140 lugares" chamam `st.AZUL`/`st.VERDE`; convenção "azul é estrutura, verde é ação" segue na leitura do código.

Não há token para: sucesso/OK, informação, cor de foco separada, sombra/elevação, superfície de pop-up.

### 1.2 Cores fora da paleta (hex/RGB no código)

- Ícone do app: gradiente #22a35d → #158f89, traço #ffffff (aparencia.py:161-166). Verde.
- Brilho do botão sólido: `QColor(85, 211, 145, 150)` em `ui.botao(..., brilho=True)` (ui.py:417-421) e `QColor(85, 211, 145, 160)` no "Impressão" da bancada (gui.py:385-387). Verde.
- Barra de título nativa via DWM: atributo 20 (escura só no modo noite), atributo 35 = cor FUNDO_FUNDO (aparencia.py:180-208).
- Arquivos liberados para hex (tests/test_padrao_visual.py:48-61): ficha_pdf.py, capa_pdf.py, rodape.py (papel); dvh.py (cor por estrutura); diff_versoes.py (HTML); agendamento_tela.py (cor por plano); visualizador.py (preto do corte, ex.: visualizador.py:68 `#000000`); edicao_ficha.py (tarja amarela); agenda_tela.py (cores de sítio do ARIA).
- Colorwash de isodose: gradiente azul→ciano→**verde**(t=0,50)→amarelo→vermelho, `dicom/ct_series.py:484-493`; opacidade 0,50 (`ct_series.py:38`).

### 1.3 Tipografia

- Fonte do app: `QFont("Segoe UI", 10)` (arranque.py:148); estilo Qt "Fusion" (arranque.py:142).
- Tamanhos em px espalhados por folha de estilo (não há escala centralizada em `estilo.py`):
  - Botões `btn_*`: 13 padrão, peso 650 (sólido/contorno/perigo), 600 (fantasma) (estilo.py:247-296); seletor/menu 13/650 (estilo.py:319, 341).
  - `ui.botao`: 12,5 (ui.py:415); discreto 11,5 (ui.py:212); link 11,5 sublinhado (ui.py:448).
  - Campos/listas/tabela `ui`: 12,5 (ui.py:83, 100, 958); cabeçalho de tabela 11,5/700 (ui.py:966).
  - Abas: fonte posta no widget, 12 px bold (ui.py:199-202).
  - Cartão: título MAIÚSCULO 11 bold, letter-spacing 1px (ui.py:255-262); número de passo 11 bold em círculo 20×20 (ui.py:248-253).
  - Rótulo acima do campo: 10,5/600, ls 0,4 (ui.py:281-283); dica 10 (ui.py:302).
  - Chip: 15/600 (ui.py:490-491). Valor: rótulo 10/600 ls 0,6; valor 14,5 bold (ui.py:522, 552-554).
  - Nome do paciente no cabeçalho: 24 bold (ui.py:750-751).
  - "Trabalhando": 14 bold ACAO (ui.py:1316).
  - Barra de modo: 12/600 (fichinha.py:2164-2175); símbolo ☾/☀ 17 (fichinha.py:2197-2200).
  - Status bar: 11 (aparencia.py:139). Título do login: 16 bold ACAO (administracao.py:96-97).
  - Fichinha tem escala própria: TITULO 25, SECAO 19, CAMPO 17, CORPO 16, MIUDA 14, ETIQUETA 12, ICONE 22 (fichinha.py:83-89).
  - Outras telas: agenda 10–19 (agenda_tela.py:645, 908-922, 1065); qualidade 11,5–14 (qualidade_tela.py:97, 217, 264); radioteradados 11,5–17 (radioteradados_tela.py:78-117).

### 1.4 Espaçamentos, raios, bordas

- Raios: botões `btn_*` 8 (estilo.py:252, 266, 280, 291); seletor/menu 8 (estilo.py:320, 342); botão de modo 7 (fichinha.py:2169); campo `ui` 7 (ui.py:82); campo global 5 (aparencia.py:60); lista/tabela global 5 (aparencia.py:78); lista `ui` 7, item 5 (ui.py:99-101); aba 7 topo, painel 8 (ui.py:119, 126); cartão e cabeçalho 11 (ui.py:235, 739); Valor 9 (ui.py:518); Retrato 9 (ui.py:703-705); zona de arraste 10 (ui.py:863); chip 14 (ui.py:490); QGroupBox 7 (aparencia.py:45); checkbox 3, rádio 7 (aparencia.py:101, 109); scroll global 5 (aparencia.py:130), `ui.barras` 4 (ui.py:930); "trabalhando" 10 (ui.py:1311).
- Paddings: botões 10px 16px (estilo.py:252…); seletor 9,5px 16px (estilo.py:321); modo 2px 14px (fichinha.py:2170); discreto 6px 13px (ui.py:212); campo `ui` 6px 9px (ui.py:83); campo global 3px 6px (aparencia.py:61); aba 7px 18px, margin-right 3 (ui.py:123); chip 6px 16px (ui.py:491).
- Margens de layout: Cartão 16,13,16,14 / espaçamento 10 (ui.py:237-238); Dialogo 18,16,18,14 / 12, corpo 10 (ui.py:1015-1020); faixa 18,10,18,10 / 10 (ui.py:986-987); cabeçalho 18,16,20,16 / 18 (ui.py:741-742); campo rótulo↔widget 3 (ui.py:296); rodapé 8 (ui.py:1051); barra de modo 10,4,10,4 / 8 (fichinha.py:2397-2398).
- Alturas: campo/escolha min 31 (ui.py:311, 400); `ui.botao` 38 padrão (ui.py:408); botões da bancada 46, max largura 360 (gui.py:363-367); barra de modo 38, botão 28, largura mín. 108 (fichinha.py:2392, 2407-2408); zona de arraste 74 / 30 compacta (ui.py:838, 881); retrato do cabeçalho 112×138 (ui.py:744); indicador 14×14 (aparencia.py:99); scroll 10 global (aparencia.py:128-129) / 8 em `ui.barras` (ui.py:937-938).
- Bordas: 1px em quase tudo; aba selecionada border-top 2px ACAO (ui.py:128-130); tracejado 1,5px em Retrato vazio e ZonaArraste (ui.py:705, 863); "trabalhando" 2px ACAO_LINHA (ui.py:1310).

### 1.5 Folha global (`aparencia._ESTILO`, aparencia.py:23-148)

Aplica-se a todo widget sem folha própria: QGroupBox (título ACAO bold), QLineEdit/QComboBox/QSpinBox, QListWidget/QTableWidget/QTextBrowser/QPlainTextEdit, QHeaderView, indicadores de checkbox/rádio/item marcável, QSlider, QScrollBar, QStatusBar, QToolTip. Paleta Qt (`_paleta_dark`, aparencia.py:211-239) mapeia Window/Base/Text/Button/Highlight/Link etc. para os tokens.

---

## 2. Componentes do `ui.py`

Tabela de entrada "Por onde começa uma tela nova" (ui.py:29-48).

| Componente | Função | Variantes / parâmetros | Regras do código |
|---|---|---|---|
| `Dialogo(titulo, pai, largura, altura)` (ui.py:991) | moldura de janela própria; fundo FUNDO_TELA; `corpo` + `rodape()` | tamanho livre por tela | rodapé sempre por último |
| `Dialogo.rodape(confirmar, cancelar, extras, perigo)` (ui.py:1025) | faixa de botões | `confirmar=""` → tela de leitura ("Fechar", sem sólido); `cancelar=None` → sem saída; `extras` à esquerda em contorno; `perigo` → confirmar em contorno vermelho e sem Enter | **Confirmar à esquerda**, cancelar (fantasma) à direita, como o QMessageBox do Windows; Enter confirma, Esc cancela |
| `abas(*(pagina, titulo))` (ui.py:165) | QTabWidget estilizado | vazio para preencher depois | chama `estilizar_abas` + `pagina_de_aba`; aba ativa: mais clara, barra ACAO 2px no topo, funde com o miolo (ui.py:108-131) |
| `estilizar_abas`, `pagina_de_aba`, `transparente` (ui.py:145-202) | apoio de abas e agrupadores sem fundo | — | fonte da aba posta no widget (12 px bold) |
| `avisar` / `alertar` / `falhar` (ui.py:1178-1197) | pop-up de 1 botão (Information/Warning/Critical) | `detalhe` (texto informativo), `tecnico` (gaveta "Mostrar detalhes") | sem sólido; ícone decidido pela função |
| `confirmar(pai, titulo, texto, acao, recusa, detalhe, perigo)` (ui.py:1200) | pergunta de 2 saídas → bool | `perigo` tira o Enter da ação | `acao` obrigatório e verbo; recusa também é palavra |
| `escolher(pai, titulo, texto, opcoes, ...)` (ui.py:1227) | 3+ saídas → rótulo | `cancelar`, `icone` | 1ª opção = padrão e sólido; nada destrutivo primeiro |
| `trabalhando(pai, mensagem)` (ui.py:1279) | modal sem moldura + cursor de espera durante trabalho bloqueante | — | folha direta (não `pintar`) |
| `atalho(seq, dono, acao, botao)` / `anunciar_atalho` (ui.py:1331-1362) | QShortcut com contexto de janela e tecla no tooltip | — | atalho segue o sólido; nenhum atalho em ação destrutiva (ui.py:1260-1276) |
| `Cartao(titulo, passo)` (ui.py:223) | superfície de um assunto (substitui QGroupBox) | número de passo opcional; `juntar()` | título MAIÚSCULO miúdo, não estica |
| `rotulo`, `campo(texto, widget, dica)` (ui.py:278-305) | rótulo **acima** do campo | `forte` | — |
| `entrada`, `area`, `escolha` / `Escolha` (ui.py:308-405) | QLineEdit, QPlainTextEdit, QComboBox | `largura`, `dica`, `editavel` | `Escolha`: seta desenhada à mão; roda do mouse só com popup aberto; mostra o começo do texto + tooltip se cortado |
| `botao(texto, cor, hover, altura, brilho)` (ui.py:408) | botão | com `cor` (qualquer valor) → `btn_solido(12.5)`; sem → `_btn_discreto`; `brilho` → sombra verde | argumentos de cor ignorados quanto ao matiz |
| `link(texto, ao_clicar)` (ui.py:427) | link como QPushButton chapado | — | "peso nenhum"; não é 4º peso |
| `Chip(texto, tom)` (ui.py:468) | pílula de dado curto | tons: neutro, azul, verde (=azul), ambar, vermelho | texto vazio esconde |
| `Valor(rotulo, valor, tom)` / `ValorTrio` (ui.py:500-652) | dado em tamanho de leitura; trio para SSD/deslocamento | tons azul, neutro; `—` apagado para ausente | `definir_tom` repinta as duas folhas |
| `Retrato(larg, alt, vazio, elastico)` (ui.py:655) | moldura de foto | cheia / tracejada | sinal `clicado` |
| `CabecalhoPaciente` (ui.py:726) | faixa de identidade: foto 112×138, nome 24px, duas fileiras de chips, canto livre | — | chips crescem proporcionais ao texto (teto 2,2× + 60px) |
| `ZonaArraste(texto)` (ui.py:822) | alvo de soltar arquivos | `compactar(sim)`, `dizer()` | aceso ACAO ao passar arquivo |
| `barras()`, `grade()` (ui.py:912-970) | folhas de scroll (8px) e tabela de leitura | — | tabela sem zebra e sem hover |
| `divisor()`, `faixa(fundo)` (ui.py:973-988) | linha horizontal; barra de topo/rodapé de tela | — | — |
| Legado `ui.CAMPO/LISTA/ABAS/PAGINA_ABA/BOTAO_DISCRETO` (ui.py:1370-1382) | folhas resolvidas no acesso | — | — |

Pesos de botão em `estilo.py` (estilo.py:235-296): **sólido** (um por tela, passo que não se desfaz), **contorno** (resto do fluxo), **fantasma** (navegação), **perigo** (contorno vermelho, nunca cheio). Mais: `_estilo_btn` (compat → sólido, estilo.py:299), `_estilo_btn_sel` (seletor checável, estilo.py:310), `_estilo_btn_menu` + `_marcar_ativo` (QToolButton de menu, estilo.py:331-359). Pop-ups recebem os mesmos pesos por `_pesar_botoes` (ui.py:1139-1162).

Mecanismo de tema: `estilo.pintar(widget, receita)` guarda a receita e reaplica na troca (estilo.py:195-229); `estilo.ao_trocar(fn)` (estilo.py:186); varredura de ouvintes mortos a partir de 400 (estilo.py:108, 227-228).

---

## 3. Travas de `tests/test_padrao_visual.py` e a regra "verde é dose"

Reprovado (o teste lê o código-fonte de `isocentro/**/*.py`, exceto `ui.py`, `estilo.py`, `aparencia.py` — linhas 33, 66-78):

1. **Classe que herda de `QDialog`** em vez de `ui.Dialogo` (linhas 106-130). Exceção única: `tratamento_pecas.py:_JanelaImagem` (linhas 36-45).
2. **`QTabWidget(` cru** em qualquer linha (linhas 132-149) — usar `ui.abas`.
3. **Hexadecimal `#rgb…#rrggbbaa`** em linha não-comentário (linhas 154-175), fora de `HEX_PERMITIDO` (linhas 48-61).
4. **Repintura divergente**: `self.x.setStyleSheet(...)` com receita diferente da registrada em `pintar` para o mesmo alvo na mesma classe (linhas 178-246).
5. Guardas da guarda: a varredura tem de ver `gui.py`, `capa.py`, `fichinha.py`, `tratamento.py` (linhas 91-94); controle positivo em `estilo.py` (96-101); toda exceção e todo arquivo de HEX_PERMITIDO têm de continuar existindo/usando hex (266-286).

Regra "verde reservado para dose":
- Origem: docstring de `estilo.py:16-18` ("Nada de verde de ação… ali verde significa dose média"); hierarquia de botão por preenchimento, não matiz (estilo.py:20-21).
- Repetida em `CLAUDE.md:259-260` ("Verde é dose… nenhum elemento de interface usa verde como cor de ação") e em `qualidade_tela.py:20-24` ("Nenhum verde… O que está certo fica em tinta fraca").
- Interpretação registrada em `tratamento_pecas.py:598-602`: a barra de andamento usa ACAO e "não fere" a regra porque mostra grandeza, não é clicável.
- **Como é aplicada:** só por convenção/paleta — a família de ação é verde-azulado (#0F7B7B/#3FBFB6) e os apelidos VERDE_* apontam para ela; o tom `"verde"` do Chip é igual ao azul (ui.py:483). **Nenhum teste verifica matiz verde**; a trava de hex só impede cor fora da paleta.
- Base do conflito: o colorwash põe verde puro em 50% da faixa (`dicom/ct_series.py:491`).

---

## 4. O shell hoje

- **Ponto de entrada:** `run_gui.py` → `arranque.main()` (arranque.py:127). Ordem: log → rede de segurança de exceções (caixa `ui.falhar`, arranque.py:42-101) → AppUserModelID → QApplication + Fusion → modo de cor lembrado (`ajustes().value("modo_cor")`, padrão "noite") → fonte Segoe UI 10 → folha global → ícone → aquece conexão do banco → login → sessão → `JanelaPrincipal(usuario).show()`. Outros executáveis sem tela: `run_checkup.py`, `run_varredura.py`.
- **Login:** `administracao.DialogLogin` (administracao.py:88-135), `ui.Dialogo` "ISOCENTRO — Entrar", QFormLayout usuário/senha, rodapé "Entrar"/"Sair"; troca de senha forçada (`DialogTrocarSenha`, sem saída). Primeiro uso semeia admin/admin (arranque.py:169-179). Modo dev `ISOCENTRO_DEV=<papel>` pula login (arranque.py:104-124, 161-165). Sessão única por usuário: outra estação entra → este app fecha (gui.py:643+).
- **Perfis:** `auth.PAPEIS` = admin, fisico, medico, dosimetrista, tecnico, enfermeiro, recepcionista (dados/auth.py:45-46). Rótulos de exibição em administracao.py:146-149.
- **Janela principal:** `gui.JanelaPrincipal(AcoesDeFicha, QMainWindow)` (gui.py:292). Título "ISOCENTRO — <nome>"; abre maximizada. Layout vertical sem margem: **barra de modo** (faixa 38px, FUNDO_FUNDO) + **QStackedWidget** com 7 telas + **QStatusBar**. Sem barra de menus, sem toolbar.
- **Barra de modo** (`fichinha.barra_de_modo`, fichinha.py:2366-2431): botões checáveis exclusivos, ordem fixa `ROTULOS_MODO` (fichinha.py:2253-2283): Capa-Up · Fichinha · Total · CQ Plano · Virtual · Agenda · Radioteradados; à direita o símbolo ☾/☀ (`_AlternarModo`, rótulo clicável, fichinha.py:2183-2216).
- **Recorte por papel** (fichinha.py:2299-2337): admin e fisico → todas; medico → Virtual, Agenda; demais papéis → Capa-Up, Virtual, Agenda; papel vazio → todas. Abre em `modo_inicial`: Fichinha se visível, senão a primeira da faixa (fichinha.py:2242, 2351-2363).
- **Navegação:** clique na faixa; Ctrl+Tab / Ctrl+Shift+Tab circulam os modos do papel (gui.py:463-474, 787-800); trocas por código via `_ir_para_modo` (ex.: Edição da Fichinha leva à Total). Cada tela é recarregada ao aparecer (`ao_abrir` dos controladores, gui.py:821-907). Status bar recebe mensagens transitórias.
- **Atalhos globais** (gui.py:759-768): Ctrl+O abrir pasta, Ctrl+P / Ctrl+Enter ação principal (o sólido do momento), Ctrl+E edição, Ctrl+H histórico, Ctrl+G agendamento.
- **Configurações:** botão "⚙ Configurações" na status bar, só admin (gui.py:493-500) → `DialogConfiguracoes` com `ui.abas`: Serviço, Usuários, Equipe, Máquinas (administracao.py:944-982).
- **Diálogos secundários** a partir das telas: busca/histórico de fichas, edição da ficha, agendamento, separar ficha, checklist, campos, imagem por dias, gerenciar nomes, nota de posicionamento, histórico de eventos.
- **Dia/noite:** `aplicar_modo` (aparencia.py:242-254) troca constantes, paleta Qt e folhas registradas; grava `modo_cor` nas preferências da estação; barra de título nativa acompanha (gui.py:629-630).

---

## 5. Telas / módulos existentes

Telas da faixa (índice no stack, gui.py:431-449):
- **Total** (0, `formulario.PainelFormulario` + `visualizador.PainelVisualizador`): bancada — formulário por plano (abas de plano), cortes Axial/Sagital/Coronal + 3D com isodose, coluna de botões Abrir pasta/Edição/Histórico/Limpar/Agendamento/Impressão.
- **Fichinha** (1, `fichinha.PainelFichinha`): porta de entrada; cinco cartões (Documentação disponível, Suas últimas fichas, Histórico, Altas prontas, Datas relevantes), ações como ícones no hover da linha.
- **Capa-Up** (2, `capa.PainelCapa` + `posicionamento.PainelPosicionamento`): capa da ficha de tratamento, do posicionamento (fotos, nota, preparo) à impressão; cadastro de simulação.
- **Virtual** (3, `tratamento.PainelFichaVirtual`): consulta somente leitura de em que fração o paciente está; checklist e campos em janelas próprias.
- **CQ Plano** (4, `qualidade_tela.PainelQualidade`): índices do alvo (ICRU 83), complexidade dos campos, cálculo paralelo, notas; régua "não calibrada" em primeiro.
- **Agenda** (5, `agenda_tela.PainelAgenda`): agenda do dia por máquina, pares fixos de máquinas em colunas, filtro de médico esmaecer/esconder; leitura.
- **Radioteradados** (6, `radioteradados_tela.PainelRadioteradados`): protótipo de indicadores mensais (núcleo RDC 20/2006 "em construção", operação por máquina, congelar mês, relatório).

Diálogos (`ui.Dialogo`): DialogLogin, DialogTrocarSenha, DialogConfiguracoes (+ PainelServico/Usuarios/Equipe/Maquinas), DialogHistorico (administracao.py); DialogEscolherPaciente (gui.py:140); DialogBuscaPacientes (busca_ficha.py:334); DialogEdicaoFicha (edicao_ficha.py:107); DialogAgendamento, DialogSepararFicha (agendamento_tela.py:118, 195); _JanelaChecklist, _JanelaCampos (tratamento_janelas.py:23, 262); DialogImagemDias, DialogGerenciarNomes (formulario.py:482, 557); _DialogoNota (posicionamento.py:1109). Exceção: _JanelaImagem (tratamento_pecas.py).

---

## 6. Inconsistências e lacunas observadas

1. **Verde em ação, apesar da regra:** ícone do app em gradiente verde (aparencia.py:161); brilho verde `QColor(85,211,145)` no botão Impressão (gui.py:385-387) e no `ui.botao(brilho=True)` (ui.py:419). Comentário obsoleto "Escala de verde do escuro (topo) ao claro" (gui.py:353-354) descreve escala que não existe mais.
2. **Regra "verde é dose" sem trava automática** — só documentada; o teste de hex não pega `QColor(r,g,b)`.
3. **`QDialog(...)` instanciado (não herdado) escapa da trava**: busca_ficha.py:196, formulario.py:267, formulario.py:902, portao_ficha.py:314; e o próprio `ui.trabalhando` (ui.py:1307).
4. **Folhas diretas sem `pintar`** (não acompanham dia/noite se tiverem cor; hoje só tamanho/peso): gui.py:497 (`padding:2px 10px` no botão Configurações, sem peso de botão), agendamento_tela.py:155/262/361/406, portao_ficha.py:320, visualizador.py:255.
5. **Duas folhas de campo diferentes**: global 5px raio, 3px 6px (aparencia.py:58-61) vs `ui._campo` 7px raio, 6px 9px, 12,5px (ui.py:78-92). Scrollbar global 10px/raio 5 vs `ui.barras` 8px/raio 4; Fichinha e Edição da Ficha têm cópias próprias (ui.py:916-920).
6. **Três estilos de botão-seletor**: `_estilo_btn_sel` (raio 8, padding 9,5/16, 13px), `_estilo_modo` da faixa (raio 7, padding 2/14, 12px, fichinha.py:2164) e `_estilo_btn_menu`.
7. **Escala tipográfica não centralizada**: Fichinha tem constantes próprias 12–25 px (fichinha.py:83-89); demais telas usam px soltos (10 a 24) em cada folha; fonte base Segoe UI 10 pt.
8. **Dois padrões de formulário**: `ui.campo` (rótulo acima) vs `QFormLayout`/`QGroupBox` (rótulo à esquerda) no Login (administracao.py:100-105) e no formulário da bancada (`_grupo_form`, formulario.py:39-40) — o docstring do `ui.py` diz que o Cartao substitui o QGroupBox.
9. **Emojis como ícones nos rótulos de botão** (📁 📝 📋 🗑 🖨 📂 📌 👁 💾 ✕ ✎ ⇄ ⚙ ◀ ▶) — gui.py:343-347, capa.py:307-315, 502-522, radioteradados_tela.py:106-112; não há sistema de ícones.
10. **Chip tom "vermelho" usa fundo AMBAR_FUNDO** (ui.py:488) e o hover do `btn_perigo` também (estilo.py:294): não há VERMELHO_FUNDO.
11. **Chip tom "verde"** existe e é idêntico ao azul (ui.py:483) — nome legado.
12. **Ordem da faixa ≠ tela inicial**: faixa começa em Capa-Up, programa abre na Fichinha (fichinha.py:2233-2242, decisão registrada do usuário).
13. **`MODOS_OCULTOS` vazio** mas a lógica de esconder/mostrar a Total e a mensagem "Volte pelo botão Fichinha" / "A bancada não tem mais aba na faixa" continuam (gui.py:833-848, 902-907) — texto de status não corresponde à faixa atual.
14. **Docstrings defasados de contagem**: `barra_de_modo` fala em "três seletores"/"Os dois juntos" (fichinha.py:2369-2376, 2186-2187); `_trocar_modo` fala em "seis telas" (gui.py:824); a faixa tem sete.
15. **Sem barra de menus nem ponto de ajuda/sobre**; Configurações fica na status bar e só para admin; não há indicação visível do papel/usuário além do título da janela.
16. **Pop-ups usam ícones e moldura nativos do QMessageBox** (ui.py:1128-1136) — só os botões recebem peso.
17. **Modo padrão "noite"** (estilo.py:96) com fallback quando `modo_cor` não existe.
18. `docs/PROPOSTA_GUI.md` trata da divisão do código do `gui.py`, não de padrão visual; `docs/qms/*.md` não descreve interface. O padrão visual vive em `estilo.py`, `ui.py`, `CLAUDE.md` (seção "Interface", ~linhas 276-302) e no teste.
