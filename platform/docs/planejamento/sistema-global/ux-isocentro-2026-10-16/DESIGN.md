---
name: ISOCENTRO
status: final
created: 2026-10-16
updated: 2026-10-18
description: Identidade visual nova do ISOCENTRO inteiro (shell e todos os módulos; o Radioteraficha migra), direção "Torre de controle", paleta "Sala de controle · azul-ardósia" em noite e dia, para uma aplicação desktop PyQt5 de gestão de qualidade em radioterapia (CEL, BET, DUO).
sources:
  - ../prd-isocentro-2026-10-16/prd.md
  - ../prd-isocentro-2026-10-16/addendum.md
  - ./.memlog.md
  - ./mockups/color-themes-1.html
  - ./mockups/torre-inicio.html
  - ./mockups/torre-modulo.html
colors:
  # Noite = chave simples (o app abre em noite, ML 32). Dia = mesma chave com sufixo -dia.
  # Hex da variação 1 "Sala de controle · azul-ardósia" (comentários do <style> de mockups/color-themes-1.html).
  fundo: '#0E1621'
  superficie: '#152030'
  superficie-elevada: '#1C2A3D'
  borda: '#2B3B52'
  texto: '#E4ECF5'
  texto-secundario: '#9AABC0'
  acao: '#8C9EFF'
  sobre-acao: '#0E1621'
  acao-fundo: '#1E2650'
  foco: '#C9D2FF'
  alta: '#FF5C61'               # sinal: ícone ▲, borda lateral, ponto em gráfico
  alta-texto: '#FF8A8D'         # texto sobre alta-fundo
  alta-fundo: '#3B1519'
  atencao: '#FFC93C'
  atencao-texto: '#FFD466'
  atencao-fundo: '#36290A'
  info: '#2CCFE0'
  info-texto: '#5FDDEA'
  info-fundo: '#0C2E36'
  estado-neutro: '#93A3B6'      # "ok / sem problema": cinza, nunca verde
  dado-ao-vivo: '#B9C4FF'
  dado-espelho: '#8292A5'
  dose: '#3DDC84'               # RESERVADO: só isodose; nunca ação, status, ok ou severidade
  fundo-dia: '#EDF1F6'
  superficie-dia: '#FFFFFF'
  superficie-elevada-dia: '#F5F8FB'
  borda-dia: '#C6D1DE'
  texto-dia: '#111A25'
  texto-secundario-dia: '#4B5A6C'
  acao-dia: '#3A47C9'
  sobre-acao-dia: '#FFFFFF'
  acao-fundo-dia: '#E4E7FB'
  foco-dia: '#1E2A8F'
  alta-dia: '#D7263D'
  alta-texto-dia: '#B0182C'
  alta-fundo-dia: '#FBE2E5'
  atencao-dia: '#BB8D00'
  atencao-texto-dia: '#755000'
  atencao-fundo-dia: '#FFF2C7'
  info-dia: '#0EA3B5'
  info-texto-dia: '#00687A'
  info-fundo-dia: '#DCF4F7'
  estado-neutro-dia: '#566577'
  dado-ao-vivo-dia: '#3A47C9'
  dado-espelho-dia: '#5E6B7B'
  dose-dia: '#1E8E4E'
typography:
  # Uma família, Segoe UI; números tabulares em toda a janela (font-variant-numeric: tabular-nums).
  # Escala medida nos mockups torre-inicio.html e torre-modulo.html. Nomes dos papéis: deste documento.
  base:
    fontFamily: 'Segoe UI'
    fontSize: 13px
    fontWeight: '400'
    lineHeight: '1.35'
  marca:
    fontFamily: 'Segoe UI'
    fontSize: 14px
    fontWeight: '700'
    letterSpacing: 0.14em
  nome-modulo:
    fontFamily: 'Segoe UI'
    fontSize: 15px
    fontWeight: '700'
  rotulo-zona:
    fontFamily: 'Segoe UI'
    fontSize: 11.5px
    fontWeight: '600'
    letterSpacing: 0.09em        # MAIÚSCULAS
  coluna-clinica:
    fontFamily: 'Segoe UI'
    fontSize: 12.5px
    fontWeight: '700'
    letterSpacing: 0.12em
  controle:
    fontFamily: 'Segoe UI'
    fontSize: 12.5px
    fontWeight: '600'            # seletor de clínica, link de texto, relógio (400)
  aba-modulo:
    fontFamily: 'Segoe UI'
    fontSize: 13px
    fontWeight: '600'
  item-forte:
    fontFamily: 'Segoe UI'
    fontSize: 13px
    fontWeight: '600'            # nome da máquina, "o quê" da linha de ação
  apoio:
    fontFamily: 'Segoe UI'
    fontSize: 12px
    fontWeight: '400'            # agenda e motivo da máquina, estado da linha, barra de status, doca (600)
  contador:
    fontFamily: 'Segoe UI'
    fontSize: 18px
    fontWeight: '600'
    lineHeight: '1.2'
  rotulo-contador:
    fontFamily: 'Segoe UI'
    fontSize: 11.5px
    fontWeight: '400'
  severidade:
    fontFamily: 'Segoe UI'
    fontSize: 11px
    fontWeight: '700'
    letterSpacing: 0.05em        # "▲ ALTA", MAIÚSCULAS
  clinica-linha:
    fontFamily: 'Segoe UI'
    fontSize: 12px
    fontWeight: '600'
    letterSpacing: 0.06em
  tabela:
    fontFamily: 'Segoe UI'
    fontSize: 12.5px
    fontWeight: '400'
  cabecalho-tabela:
    fontFamily: 'Segoe UI'
    fontSize: 11px
    fontWeight: '600'
  titulo-alerta:
    fontFamily: 'Segoe UI'
    fontSize: 14px
    fontWeight: '700'
  valor-destaque:
    fontFamily: 'Segoe UI'
    fontSize: 15px
    fontWeight: '700'
  botao:
    fontFamily: 'Segoe UI'
    fontSize: 13px
    fontWeight: '600'
  selo:
    fontFamily: 'Segoe UI'
    fontSize: 10px
    fontWeight: '500'
    lineHeight: 14px
rounded:
  marca-estado: 1px              # quadradinho 7 px da máquina normal
  botao: 5px
  linha: 0 5px 5px 0             # linha de máquina e de ação (borda lateral à esquerda, cantos só à direita)
  controle: 6px                  # seletor de clínica, controle noite/dia
  painel: 8px                    # coluna de clínica, painel de ação, bloco da doca, painel do módulo
  cartao-alerta: 0 8px 8px 0
  selo: 8px
spacing:
  janela-referencia: 1366px × 768px   # mockups; área útil 1366 × 738
  altura-barra-titulo: 30px      # moldura nativa do Windows
  altura-topo: 48px
  altura-barra-status: 26px
  margem-janela: 12px 16px       # conteúdo entre topo e barra de status
  margem-topo: 0 16px
  vao-zonas: 12px
  vao-rotulo-zona: 6px
  vao-topo-inicio: 20px
  vao-topo-modulo: 18px
  vao-colunas: 10px
  coluna-padding: 8px 8px 6px
  maquina-padding: 5px 6px 5px 5px
  fila-padding: 4px 6px
  linha-acao-padding: 6px 10px 6px 8px
  linha-acao-vao: 10px
  linha-acao-entre: 4px
  vao-doca: 8px
  altura-bloco-doca: 92px
  bloco-doca-padding: 10px 6px 6px
  segmento-padding: 5px 14px
  botao-padding: 7px 18px
  aba-modulo-padding: 0 12px
  altura-linha-tabela: 23px
  coluna-lateral-modulo: 430px
  borda-lateral: 3px
  marca-estado: 7px
  icone: 18px
  icone-doca: 22px
  icone-marca: 22px
  icone-nome-modulo: 20px
  traco-icone: 1.6px
  foco-anel: 2px
  foco-afastamento: 2px
components:
  topo:
    background: '{colors.superficie}'
    border-bottom: '1px {colors.borda}'
    height: '{spacing.altura-topo}'
    padding: '{spacing.margem-topo}'
  marca:
    icon-color: '{colors.acao}'
    icon-size: '{spacing.icone-marca}'
    typography: '{typography.marca}'
  seletor-clinica:
    border: '1px {colors.borda}'
    radius: '{rounded.controle}'
    padding: '{spacing.segmento-padding}'
    typography: '{typography.controle}'
    foreground: '{colors.texto-secundario}'
    hover-background: '{colors.superficie-elevada}'
    hover-foreground: '{colors.texto}'
    selected-background: '{colors.acao-fundo}'
    selected-foreground: '{colors.acao}'
  controle-modo:
    border: '1px {colors.borda}'
    radius: '{rounded.controle}'
    selected-background: '{colors.acao-fundo}'
    selected-foreground: '{colors.acao}'
    foreground: '{colors.texto-secundario}'
  rotulo-zona:
    typography: '{typography.rotulo-zona}'
    foreground: '{colors.texto-secundario}'
    count-foreground: '{colors.texto}'
  coluna-clinica:
    background: '{colors.superficie}'
    border: '1px {colors.borda}'
    radius: '{rounded.painel}'
    padding: '{spacing.coluna-padding}'
    title: '{typography.coluna-clinica}'
    title-color: '{colors.texto-secundario}'
  maquina-normal:
    background: transparent
    marker: '{spacing.marca-estado} quadrado {colors.estado-neutro}'
    name: '{typography.item-forte}'
    reason-color: '{colors.texto-secundario}'
    schedule-color: '{colors.texto-secundario}'
    hover-background: '{colors.superficie-elevada}'
    radius: '{rounded.linha}'
  maquina-atencao:
    background: '{colors.atencao-fundo}'
    border-left: '{spacing.borda-lateral} {colors.atencao}'
    icon: '◆ {colors.atencao}'
    reason-color: '{colors.atencao-texto}'
    reason-weight: '600'
  maquina-alta:
    background: '{colors.alta-fundo}'
    border-left: '{spacing.borda-lateral} {colors.alta}'
    icon: '▲ {colors.alta}'
    reason-color: '{colors.alta-texto}'
    reason-weight: '600'
  contador-fila:
    label: '{typography.rotulo-contador}'
    label-color: '{colors.texto-secundario}'
    number: '{typography.contador}'
    number-color: '{colors.texto}'
    zero-color: '{colors.texto-secundario}'
    zero-weight: '400'
    high-marker: '▲n {colors.alta-texto} 12px 700'
    padding: '{spacing.fila-padding}'
    hover-background: '{colors.superficie-elevada}'
    separator: '1px {colors.borda}'
  linha-acao-alta:
    background: '{colors.alta-fundo}'
    border-left: '{spacing.borda-lateral} solid {colors.alta}'
    tag: '▲ ALTA {colors.alta-texto}'
    radius: '{rounded.linha}'
    padding: '{spacing.linha-acao-padding}'
  linha-acao-atencao:
    background: '{colors.atencao-fundo}'
    border-left: '{spacing.borda-lateral} solid {colors.atencao}'
    tag: '◆ ATENÇÃO {colors.atencao-texto}'
  linha-acao-info:
    background: '{colors.info-fundo}'
    border-left: '{spacing.borda-lateral} solid {colors.info}'
    tag: '○ INFO {colors.info-texto}'
  linha-acao-vista:
    background: transparent
    border-left: '{spacing.borda-lateral} dashed (cor da severidade)'
    tag: 'forma e cor da severidade mantidas'
    text-color: '{colors.texto-secundario}'
    text-weight: '500'
  chip-severidade:
    typography: '{typography.severidade}'
    alta: '▲ {colors.alta-texto}'
    atencao: '◆ {colors.atencao-texto}'
    info: '○ {colors.info-texto}'
  bloco-doca:
    background: '{colors.superficie}'
    border: '1px {colors.borda}'
    radius: '{rounded.painel}'
    height: '{spacing.altura-bloco-doca}'
    padding: '{spacing.bloco-doca-padding}'
    icon-size: '{spacing.icone-doca}'
    icon-color: '{colors.texto-secundario}'
    label: '{typography.apoio}'
    label-weight: '600'
    hover-background: '{colors.superficie-elevada}'
    hover-border: '1px {colors.acao}'
  bloco-doca-em-construcao:
    base: '{components.bloco-doca}'
    label-color: '{colors.texto-secundario}'
    label-weight: '500'
    seal: '{components.selo-em-construcao}'
  selo-em-construcao:
    typography: '{typography.selo}'
    foreground: '{colors.texto-secundario}'
    border: '1px {colors.borda}'
    radius: '{rounded.selo}'
    padding: 0 5px
  selo-degrau-ao-vivo:
    text: 'fonte ● ao vivo · dd/mm hh:mm'
    foreground: '{colors.dado-ao-vivo}'
    weight: '600'
  selo-degrau-espelho:
    text: 'fonte ◌ espelho hh:mm · dd/mm hh:mm'
    foreground: '{colors.dado-espelho}'
  selo-degrau-relatorio:
    text: 'relatório · dd/mm hh:mm'       # [ASSUMPTION] sem token próprio na paleta
    foreground: '{colors.dado-espelho}'
  barra-status:
    background: '{colors.superficie}'
    border-top: '1px {colors.borda}'
    height: '{spacing.altura-barra-status}'
    padding: '{spacing.margem-topo}'
    typography: '{typography.apoio}'
    foreground: '{colors.texto-secundario}'
  botao-inicio:
    foreground: '{colors.acao}'
    icon: 'chevron ◂ SVG'
    weight: '600'
    hover-background: '{colors.superficie-elevada}'
  aba-modulo:
    typography: '{typography.aba-modulo}'
    padding: '{spacing.aba-modulo-padding}'
    foreground: '{colors.texto-secundario}'
    hover-foreground: '{colors.texto}'
    hover-background: '{colors.superficie-elevada}'
    selected-foreground: '{colors.texto}'
    selected-border-bottom: '2px {colors.acao}'
  botao-primario:
    background: '{colors.acao}'
    foreground: '{colors.sobre-acao}'
    radius: '{rounded.botao}'
    padding: '{spacing.botao-padding}'
    typography: '{typography.botao}'
  botao-secundario:                      # contorno (ML 32)
    background: transparent
    foreground: '{colors.acao}'
    border: '1px {colors.acao}'
    radius: '{rounded.botao}'
    padding: '{spacing.botao-padding}'
    typography: '{typography.botao}'
  botao-discreto:                        # sem borda (ML 32)
    background: transparent
    foreground: '{colors.acao}'
    radius: '{rounded.botao}'
    padding: '{spacing.botao-padding}'
    typography: '{typography.botao}'
  botao-perigo:                          # contorno vermelho (ML 32)
    background: transparent
    foreground: '{colors.alta-texto}'
    border: '1px {colors.alta}'
    radius: '{rounded.botao}'
    padding: '{spacing.botao-padding}'
    typography: '{typography.botao}'
  link-texto:
    foreground: '{colors.acao}'
    typography: '{typography.controle}'
    hover: sublinhado
  foco:
    outline: '{spacing.foco-anel} solid {colors.foco}'
    offset: '{spacing.foco-afastamento}'
  icone:
    size: '{spacing.icone}'
    stroke: '{spacing.traco-icone} currentColor'
    fill: none
    linecap: round
  painel:
    background: '{colors.superficie}'
    border: '1px {colors.borda}'
    radius: '{rounded.painel}'
  tabela-leitura:
    typography: '{typography.tabela}'
    header: '{typography.cabecalho-tabela}'
    header-color: '{colors.texto-secundario}'
    row-height: '{spacing.altura-linha-tabela}'
    separator: '1px {colors.borda}'
    hover-background: '{colors.superficie-elevada}'
    ok-color: '{colors.texto-secundario}'
  cartao-alerta-alta:
    background: '{colors.alta-fundo}'
    border: '1px {colors.borda}'
    border-left: '{spacing.borda-lateral} {colors.alta}'
    radius: '{rounded.cartao-alerta}'
    title: '{typography.titulo-alerta}'
    value: '{typography.valor-destaque}'
    value-color: '{colors.alta-texto}'
---

## Brand & Style

**Torre de controle** (ML 28; `ML n` = entrada n do `.memlog.md`). O ISOCENTRO mostra a situação do serviço inteiro — clínica, máquina, fila — e a pessoa entende em 3 segundos se algo precisa dela. O fundo é calmo e escuro; a cor só aparece onde há problema; o que está certo fica neutro. A identidade vale para o ISOCENTRO inteiro: shell e todos os módulos, com um só padrão. O Radioteraficha deixa de ter visual próprio e migra (ML 27; EXPERIENCE.md → Migração).

Cada escolha tem um porquê:

| Base | Regra na tela | Por quê |
| --- | --- | --- |
| Carga cognitiva, lei de Hick | Três zonas fixas; 5 linhas de ação e "ver mais"; um botão primário por tela | Menos opções simultâneas encurtam a decisão |
| Atributos pré-atentivos | Problema = cor + forma + borda lateral + fundo; normal sem nenhum deles | O olho acha o diferente antes de ler (< 250 ms); isso só funciona se o resto não competir |
| IEC 60601-1-8 | Alta = vermelho, atenção = amarelo, informativo = ciano | Mesmo código dos equipamentos médicos que a equipe já usa (ML 29) |
| Fadiga de alerta | "ok" neutro; doca sem contagem; nada de cor em estado normal | Sinal que aparece sempre deixa de ser visto (PRD SM-C1) |
| Reconhecer em vez de lembrar | Motivo escrito na máquina; rótulo em cada fila; ícone e nome em cada módulo; severidade por extenso | Ninguém precisa decorar o que um sinal significa |
| Daltonismo | Forma ▲ ◆ ○ sempre junto da cor | A cor sozinha falha para deutan e protan (ver Colors) |
| Números tabulares | `tabular-nums` em toda a janela | Contagens, horários e medidas alinham na coluna e se comparam de relance |
| Luz da sala | Noite para a sala de planejamento ou bunker escuro; dia para corredor claro; abre em noite | O brilho da tela acompanha a sala; noite é o caso mais comum (ML 32) |

Mockups de referência: [mockups/torre-inicio.html](./mockups/torre-inicio.html), [mockups/torre-modulo.html](./mockups/torre-modulo.html) e [mockups/color-themes-1.html](./mockups/color-themes-1.html) (só a variação 1). As decisões dos rodapés dos dois mockups Torre foram aceitas (ML 32). **Em conflito, este documento e o EXPERIENCE.md vencem os mockups.**

## Colors

Duas paletas com as mesmas 23 chaves; muda só o valor. No frontmatter a chave simples é a **noite** e o sufixo `-dia` é o dia. Os nomes dos papéis vêm da página de paletas ([mockups/color-themes-1.html](./mockups/color-themes-1.html)).

| Família | Tokens | Uso | Não é usado para |
| --- | --- | --- | --- |
| Superfícies | `{colors.fundo}` < `{colors.superficie}` < `{colors.superficie-elevada}` | fundo da janela; coluna, painel, topo, barra de status, doca; hover | sinalizar estado |
| Tinta | `{colors.texto}`, `{colors.texto-secundario}` | leitura; rótulo, apoio, o que está certo, zero, item visto | — |
| Régua | `{colors.borda}` | contorno de painel, separador, segmentos | — |
| Ação | `{colors.acao}`, `{colors.sobre-acao}`, `{colors.acao-fundo}` | botão primário, link, opção marcada do seletor, aba ativa, botão Início, marca | severidade, "ok", decoração |
| Foco | `{colors.foco}` | anel de foco do teclado | qualquer outra coisa |
| Severidade alta | `{colors.alta}` (sinal), `{colors.alta-texto}`, `{colors.alta-fundo}` | ▲, borda lateral, ponto fora em gráfico; texto e fundo da linha | botão; decoração |
| Severidade atenção | `{colors.atencao}`, `{colors.atencao-texto}`, `{colors.atencao-fundo}` | ◆ e a linha correspondente | — |
| Severidade informativo | `{colors.info}`, `{colors.info-texto}`, `{colors.info-fundo}` | ○ e a linha correspondente | ação (o primário é índigo, distinto do ciano) |
| Estado | `{colors.estado-neutro}` | "normal", "ok", série de pontos dentro da tolerância | — |
| Degrau de fonte (de onde vem o dado: ● ao vivo do `variandw`, ◌ espelho local ou relatório exportado) | `{colors.dado-ao-vivo}` (●), `{colors.dado-espelho}` (◌) | selo do degrau do dado | severidade |
| Dose | `{colors.dose}` | **só isodose** | ação, status, ok, severidade, ícone, marca |

Cada severidade tem três valores: sinal (ícone e borda lateral), texto (sobre o seu fundo) e fundo.

**Verde é dose.** Nenhum token de ação, status, ok ou severidade é verde. O que está certo fica em `{colors.estado-neutro}` ou `{colors.texto-secundario}`. Não existe token de sucesso, e não deve existir.

### Contrastes (WCAG 2.x, calculados na página de paletas)

Alvo: texto ≥ 4,5:1; sinal, ícone e anel de foco ≥ 3:1 (WCAG 1.4.11). Todos passam.

| Par | Noite | Dia | Alvo |
| --- | --- | --- | --- |
| texto / fundo | 15,25 | 15,45 | 4,5 |
| texto / superfície | 13,75 | 17,52 | 4,5 |
| texto-secundário / fundo | 7,76 | 6,22 | 4,5 |
| texto-secundário / superfície-elevada | 6,19 | 6,62 | 4,5 |
| ação / fundo | 7,31 | 6,33 | 4,5 |
| ação / ação-fundo | 5,83 | 5,85 | 4,5 |
| sobre-ação / ação | 7,31 | 7,18 | 4,5 |
| alta-texto / alta-fundo | 7,09 | 5,68 | 4,5 |
| atenção-texto / atenção-fundo | 10,05 | 6,47 | 4,5 |
| info-texto / info-fundo | 8,92 | 5,62 | 4,5 |
| estado-neutro / superfície | 6,37 | 5,96 | 4,5 |
| dado-ao-vivo / superfície | 9,68 | 7,18 | 4,5 |
| dado-espelho / superfície | 5,15 | 5,43 | 4,5 |
| sinal alta / superfície | 5,43 | 4,96 | 3,0 |
| sinal atenção / superfície | 10,67 | **3,03** | 3,0 |
| sinal info / superfície | 8,67 | **3,03** | 3,0 |
| foco / superfície | 11,04 | 11,78 | 3,0 |

### Daltonismo

Diferença de luminância relativa entre pares de sinais (ΔY, em pontos percentuais), simulada por Machado et al. (2009) com severidade 1,0 (página de paletas).

| Visão | Modo | ▲–◆ | ▲–○ | ◆–○ |
| --- | --- | --- | --- | --- |
| deuteranopia | noite | 31,41 | 10,89 | 20,52 |
| protanopia | noite | 36,57 | 35,82 | **0,75** |
| deuteranopia | dia | 11,15 | 6,70 | **4,45** |
| protanopia | dia | 16,87 | 23,75 | 6,87 |

No dia, os três sinais ficam próximos em luminância e os de atenção e informativo mal passam de 3:1 contra a superfície: **no dia a distinção depende da forma** (▲ ◆ ○), do texto escrito e da borda lateral. Na noite, para protanopia, atenção e informativo têm quase a mesma luminância (ΔY 0,75). Por isso a forma nunca sai de perto da cor.

## Typography

Uma família: **Segoe UI**, base 13 px com entrelinha 1,35 (equivale aos 10 pt da interface atual em 96 dpi). **Números tabulares em toda a janela.** Os glifos de severidade são forçados a texto (VS15) para não virarem emoji. Escala medida nos mockups; quando a linha tem vários papéis, os pesos seguem a ordem dos papéis:

| Papel | Tamanho / peso | Onde |
| --- | --- | --- |
| `{typography.contador}` | 18 / 600 | número da fila |
| `{typography.nome-modulo}` | 15 / 700 | nome do módulo no topo do módulo |
| `{typography.valor-destaque}` | 15 / 700 | valor medido no cartão de alerta |
| `{typography.marca}`, `{typography.titulo-alerta}` | 14 / 700 · 700 | marca ISOCENTRO (espaçamento 0,14 em); título do alerta |
| `{typography.base}`, `{typography.item-forte}`, `{typography.botao}`, `{typography.aba-modulo}` | 13 / 400 · 600 · 600 · 600 | corpo; máquina e "o quê"; botão; aba |
| `{typography.coluna-clinica}`, `{typography.controle}`, `{typography.tabela}` | 12,5 / 700 · 600 · 400 | sigla da clínica; seletor, link, relógio (400); tabela |
| `{typography.apoio}`, `{typography.clinica-linha}` | 12 / 400 · 600 | agenda e motivo, estado, barra de status, doca (600); clínica na linha |
| `{typography.rotulo-zona}`, `{typography.rotulo-contador}` | 11,5 / 600 · 400 | rótulo de zona (MAIÚSCULAS, 0,09 em); rótulo da fila |
| `{typography.severidade}`, `{typography.cabecalho-tabela}` | 11 / 700 · 600 | "▲ ALTA"; cabeçalho de tabela |
| `{typography.selo}` | 10 / 500 | selo "em construção" — menor tamanho permitido |

Hierarquia por peso e tamanho, nunca por cor. Maiúsculas só em rótulo de zona, sigla de clínica e severidade.

## Layout & Spacing

Uma janela maximizada; referência 1366 × 768 (área útil 1366 × 738 sob a barra de título nativa de 30 px). Moldura fixa:

| Região | Altura | Conteúdo |
| --- | --- | --- |
| Barra de título (Windows) | `{spacing.altura-barra-titulo}` | nome da janela, minimizar/maximizar/fechar, em `{colors.superficie}` |
| Topo | `{spacing.altura-topo}` | Início: marca · seletor de clínica · relógio · noite/dia · usuário. Módulo: ◂ Início · nome · abas · contexto · noite/dia · usuário |
| Conteúdo | o resto | margem `{spacing.margem-janela}` |
| Barra de status | `{spacing.altura-barra-status}` | esquerda: usuário · perfil · clínica; direita: selo de degrau e data |

**Início — 3 zonas empilhadas** na ordem 1-2-3, com `{spacing.vao-zonas}` entre elas e rótulo de zona acima de cada uma (ML 30):

| Zona | Grade | Medidas |
| --- | --- | --- |
| 1 · Situação do serviço | uma coluna por clínica permitida (3 em "Todas"), larguras iguais | vão `{spacing.vao-colunas}`; máquinas empilhadas; filas em 3 células no pé da coluna |
| 2 · O que precisa de ação | um painel; linhas em grade de 6 colunas: severidade 104 · o quê 232 · detalhe (resto) · prazo 150 · clínica 56 · estado 150 px | entre linhas `{spacing.linha-acao-entre}`; rodapé com link à esquerda e primário à direita |
| 3 · Módulos | doca de 9 blocos iguais numa linha | vão `{spacing.vao-doca}`; bloco `{spacing.altura-bloco-doca}` |

**Módulo:** topo de uma linha, sem seletor de clínica; conteúdo próprio de cada módulo. No mockup de Garantia da Qualidade: coluna larga + coluna lateral de `{spacing.coluna-lateral-modulo}` (ilustrativo; o layout interno de cada módulo fica para a sessão do módulo).

[ASSUMPTION] Pessoa com acesso a uma só clínica (comportamento em EXPERIENCE.md → Clínica em contexto): a largura da coluna única da Zona 1 não foi decidida. Doca com menos de 9 módulos visíveis (o bloco some, U7): blocos mantêm a largura de 1/9 e alinham à esquerda.

## Elevation & Depth

Chapado. Nenhuma sombra, brilho ou gradiente. A profundidade é tonal: `{colors.fundo}` (janela) → `{colors.superficie}` (topo, coluna, painel, doca, barra de status) → `{colors.superficie-elevada}` (hover). Linhas com severidade clareiam 8–10% no hover em vez de mudar de cor. A aba ativa do módulo não ganha fundo: ganha sublinhado de 2 px em `{colors.acao}`.

## Shapes

Cantos discretos, crescendo com a superfície: marca de estado `{rounded.marca-estado}`, botão `{rounded.botao}`, controles segmentados `{rounded.controle}`, painéis e blocos `{rounded.painel}`. Linha de máquina, linha de ação e cartão de alerta têm borda lateral de 3 px à esquerda e cantos arredondados só à direita (`{rounded.linha}`, `{rounded.cartao-alerta}`). Bordas de 1 px. Tracejado = "já visto" (linha de ação) ou limite de tolerância (gráfico).

Formas de sinal, fixas: ▲ alta · ◆ atenção · ○ informativo · ▪ normal (quadrado 7 px) · ● dado ao vivo · ◌ dado de espelho.

## Components

Regra única de estados: todo elemento clicável ganha hover em `{colors.superficie-elevada}`; linhas e botões com fundo próprio clareiam 8–10% (ver Elevation & Depth); sem ícone de seta; foco do teclado `{components.foco}`. A coluna Estados abaixo traz só o que foge dessa regra.

### Shell

| Componente | Anatomia e tokens | Estados |
| --- | --- | --- |
| Topo do Início | `{components.topo}`; marca = ícone de isocentro (dois círculos + retículo) em `{colors.acao}` + "ISOCENTRO"; seletor de clínica; à direita relógio "18/10/2026 · 07:43", noite/dia, usuário com ícone de pessoa (sem menu) | — |
| Seletor de clínica | controle segmentado `{components.seletor-clinica}`; um segmento por clínica permitida, na ordem CEL · BET · DUO, + "Todas" ao fim para o físico responsável (U6) | marcada: `{colors.acao-fundo}` + `{colors.acao}`, **não preenchida**, para manter um só primário na tela |
| Noite/dia | `{components.controle-modo}`: par de ícones lua/sol em duas posições | posição ativa em `{colors.acao-fundo}` |
| Topo do módulo | uma linha: `{components.botao-inicio}` "◂ Início" · ícone 20 px + nome do módulo, com separador vertical à direita · faixa de telas · contexto "DUO · VitalBeam 4199" à direita · noite/dia · usuário | **sem seletor de clínica** |
| Faixa de telas | abas `{components.aba-modulo}`, recortadas pelo perfil | ativa: `{colors.texto}` + sublinhado 2 px `{colors.acao}` |
| Barra de status | `{components.barra-status}`: "Geova · físico · Todas" à esquerda; selo de degrau à direita. No módulo, a clínica é a do contexto | — |
| Ícones | `{components.icone}`: SVG de traço único 1,6 px, sem preenchimento, cor herdada; um desenho por módulo | — |
| Foco do teclado | `{components.foco}`: anel 2 px `{colors.foco}`, afastado 2 px, em todo elemento clicável | — |

### Início

| Componente | Anatomia e tokens | Estados |
| --- | --- | --- |
| Rótulo de zona | `{components.rotulo-zona}`; número em `{colors.texto}`; à direita, na Zona 1, o selo de degrau da agenda ("agenda: variandw ● ao vivo · 18/10 07:41") | — |
| Coluna de clínica | `{components.coluna-clinica}`: sigla, máquinas, separador, 3 contadores de fila | — |
| Linha de máquina — normal | `{components.maquina-normal}`: ▪ `{colors.estado-neutro}` · nome · agenda à direita na 1ª linha ("14 pac. hoje · próx. 08:10") · "normal" na 2ª linha | sem fundo |
| Linha de máquina — problema | `{components.maquina-alta}` / `{components.maquina-atencao}`: borda lateral + fundo + forma IEC + motivo em peso 600 na cor de texto da severidade ("CQ diário fora da tolerância") | — |
| Contador de fila | `{components.contador-fila}`: rótulo pequeno (Duplo Check · Aprovação Física · Vencimentos 60d) e número 18 px; zero em `{colors.texto-secundario}` peso 400; "▲1" em `{colors.alta-texto}` ao lado do total quando há item alto | clicável |
| Linha de ação — aberto | `{components.linha-acao-alta}` / `-atencao` / `-info`: severidade por extenso · o quê (peso 600) · detalhe · prazo · clínica · estado ("aberto") | — |
| Linha de ação — visto | `{components.linha-acao-vista}`: mantém forma e cor da severidade, perde o fundo, borda lateral tracejada, texto em `{colors.texto-secundario}`; estado "visto · Bruno · 07:12" | — |
| Chip de severidade | `{components.chip-severidade}`: "▲ ALTA", "◆ ATENÇÃO", "○ INFO" em MAIÚSCULAS, cor de texto da severidade | não clicável |
| Rodapé da Zona 2 | `{components.link-texto}` "ver mais N" à esquerda; `{components.botao-primario}` "Abrir fila" à direita | — |
| Bloco da doca | `{components.bloco-doca}`: ícone 22 px em `{colors.texto-secundario}` + nome do módulo, centrados; **sem contagem** | hover também com borda `{colors.acao}` |
| Bloco da doca — em construção | `{components.bloco-doca-em-construcao}`: nome em `{colors.texto-secundario}` 500 + `{components.selo-em-construcao}` no pé. Sem selo: Radioteraficha e Indicadores; a Garantia da Qualidade leva o selo até o módulo ficar pronto [ASSUMPTION, ML 28] | — |

### Ações

| Componente | Anatomia e tokens | Estados |
| --- | --- | --- |
| Botão primário | `{components.botao-primario}`: **um por tela**, verbo no rótulo ("Abrir fila", "Registrar repetição") | — |
| Botão secundário | `{components.botao-secundario}`: contorno em `{colors.acao}` | hover `{colors.acao-fundo}` [ASSUMPTION] |
| Botão discreto | `{components.botao-discreto}`: só texto em `{colors.acao}`, sem borda; para ações de baixa ênfase | — |
| Botão perigo | `{components.botao-perigo}`: contorno `{colors.alta}`, texto `{colors.alta-texto}`; para ação destrutiva; nunca sólido | — |

Os pesos de botão seguem a hierarquia por preenchimento da interface atual, com as cores novas (ML 32): primário sólido, secundário contorno, discreto sem borda, perigo contorno vermelho; um sólido por tela. Na migração, `btn_solido`, `btn_contorno`, `btn_fantasma` e `btn_perigo` mapeiam para eles (ver EXPERIENCE.md → Migração).

### Leitura de dados

| Componente | Anatomia e tokens | Estados |
| --- | --- | --- |
| Selo de degrau | ao vivo `{components.selo-degrau-ao-vivo}` (●); espelho `{components.selo-degrau-espelho}` (◌, com a hora do espelho); relatório `{components.selo-degrau-relatorio}` [ASSUMPTION] — sempre com a data do dado | — |
| Tabela de leitura | `{components.tabela-leitura}`: linhas de 23 px; o valor dentro da tolerância fica em `{colors.texto-secundario}` (rótulo "dentro"); o valor não lançado fica em itálico (rótulo "a lançar"), sem cor; só a linha fora leva fundo, borda e forma | — |
| Cartão de alerta | `{components.cartao-alerta-alta}`: severidade + título; lista rótulo/valor (valor medido em 15/700 `{colors.alta-texto}`); bloco "Ação prevista"; primário único | — |
| Gráfico de controle | série e pontos em `{colors.estado-neutro}`; tolerância tracejada em `{colors.texto-secundario}`; zero em `{colors.borda}`; ponto fora como ▲ em `{colors.alta}` com o valor rotulado | — |

[ASSUMPTION] Tela de módulo "em construção": topo do módulo normal; no conteúdo, um `{components.painel}` com o nome do módulo e uma frase em `{colors.texto-secundario}`, sem dado.

## Do's and Don'ts

| Faça | Não faça |
| --- | --- |
| Verde **só** em isodose (`{colors.dose}`) | Verde em ação, alerta, status, "ok", "em dia", "conforme", ícone ou marca |
| "ok" e "normal" em `{colors.estado-neutro}` / `{colors.texto-secundario}` | Selo, ícone ou fundo de sucesso |
| Cor só onde há problema | Colorir o estado normal "para ficar bonito" |
| Forma sempre junto da cor (▲ ◆ ○ ▪) e a severidade escrita | Severidade só por cor |
| Um botão primário por tela; o resto em link, segmento marcado ou secundário | Dois primários; seletor preenchido em `{colors.acao}` |
| Nada desabilitado por resultado de verificação (advisory) | Botão cinza porque o teste falhou |
| Ícones SVG de traço único | Emoji como ícone |
| Números tabulares em toda contagem, hora e medida | Números proporcionais em coluna |
| Profundidade por tom de superfície | Sombra, brilho, gradiente |
| Degrau e data do dado em toda tela com dado do `variandw` | Dado sem data, ou esconder que é espelho ou relatório |
| Doca sem número | Contagem no bloco do módulo (repete a Zona 1 e cansa) |
