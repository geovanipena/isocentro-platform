# Destino do ISOCENTRO

Para onde o app vai, e a fila de frentes que leva até lá. Escrito em
15/09/2026, com os quatro pilares escolhidos pelo usuário.

Este arquivo é lido por gente **e** pelo `tools/robo.py`. O robô pega a
primeira frente com `classe: robo` e `estado: pendente`, de cima para baixo, e
só essas. O resto espera por alguém, e está aqui para que ninguém confunda
"o robô não fez" com "está pronto".

## Por que o robô não anda em tudo

Quase todo o caminho até o destino passa por gente: a TI (porta, pasta
compartilhada, destino DICOM), a clínica (dado de comissionamento, conferência
contra o ARIA) e o usuário (aceite de tela, aviso de mudança no papel). **Um
robô que precisa avançar e não tem de onde tirar é o que inventa dado**, e a
primeira regra do domínio é não inventar. Então:

| classe | quem anda | por quê |
|---|---|---|
| `robo` 🤖 | o `tools/robo.py`, sozinho | não toca `papel/`, `interface/` nem `dominio/`, e não depende de nada fora desta máquina |
| `voce` 👤 | o usuário, numa sessão normal | muda o papel (exige aviso antes), a tela (exige aceite antes) ou o cálculo (chega ao paciente) |
| `clinica` 🏥 | alguém na clínica ou na TI | só se responde lá: rede, banco, ARIA, dado de máquina |

A trava não depende do robô lembrar: o `tools/robo_trava.py` recusa a edição
nas três pastas, e o `tools/robo.py` confere o diff depois da sessão e **não
empurra** se alguma delas mudou. Mudar a `classe:` de uma frente também
reprova a conferência: reclassificar é decisão do usuário.

## Os quatro pilares

### 1. Fluxo sem papel manual
O plano aprovado no Eclipse vira ficha e capa sem ninguém exportar à mão: a
concentradora (`clinica-python01`) recebe o C-MOVE, a varredura agendada gera
o caso, e a estação só abre e imprime. **Estado:** o código existe e está
verde (exportação, `trazer` com CT e dose por série, varredura sem o app
aberto); falta a instalação na concentradora e o primeiro uso real.

### 2. Painel de tratamento
A aba do radioterapeuta mostra os pacientes em tratamento a partir do banco,
sem faixa de EXPERIMENTAL. **Estado:** SQL escrito, permissão existe, tempo
medido (0,40 s); `LISTA_VERIFICADA_EM` continua `""` até a lista ser conferida
contra o ARIA.

### 3. Verificação independente
O cálculo paralelo dá veredito com a tabela de CADA acelerador do serviço, e a
aba Qualidade tem tolerância derivada da base histórica do serviço (AAPM
TG-218), não da literatura. **Estado:** `qualidade.CALIBRADO = False`; o
`dados_feixe/` só tem tabelas `ELEKTA_SAT`, de outro serviço, então nenhum
plano daqui recebe veredito.

### 4. Base saudável
O código aguenta o resto sem que cada frente pague a dívida das anteriores:
arquivos grandes divididos pelo papel no fluxo, suíte rápida, fim de linha
uniforme. **Estado:** `gui.py` com 5.727 linhas, `ficha_pdf.py` com 3.529,
`tratamento.py` com 3.076; 19 arquivos CRLF.

---

## A fila

Formato fixo, porque o robô lê: `### R-NN — título`, e logo abaixo as linhas
`- classe:` e `- estado:`. Estados: `pendente`, `feita (data, commit)`,
`estacionada (motivo)`. Frente estacionada volta a `pendente` pela mão do
usuário, depois de responder o motivo.

### R-62 — Margem CTV→PTV medida pelo código, sem veredito
- classe: robo
- estado: feita (22/10/2026)
- pilar: 3 (`docs/planejamento/sistema-global/analise-ia-2026-10-22.md`,
  proposta 1; espinha AD-38). Está no topo da fila de propósito, pedido do
  usuário em 22/10/2026: o robô pega a primeira `robo` pendente.
- por que é do robô: módulo novo e puro, fora de `papel/`, `interface/` e
  `dominio/`; nada de fora desta máquina; nenhum cálculo existente muda.
- por que importa: no estudo de hazard do COURT-2026 (JACMP, doi
  10.1002/acm2.70759), 2 de 5 físicos nem avaliaram a margem do PTV, e quem
  avaliou teve especificidade de 13% a 63%. Margem é geometria: o código
  mede, e a pessoa decide.
- pronto quando:
  - `isocentro/rt/__init__.py` e `isocentro/rt/margem.py`, só com numpy
    (scipy NÃO é dependência, e dependência nova é decisão do usuário).
    Sem Qt, banco, rede, arquivo, PIL nem matplotlib, e sem importar nada do
    pacote fora de `rt/` (AD-38). Pode reproduzir o algoritmo de
    rasterização de `dicom/dvh._mascara_estrutura`, mas não importá-lo: a
    junção é da R-58.
  - Entrada: os contornos de duas ROIs (interna e externa), cada uma como
    lista de arrays `(N, 3)` em mm no sistema do paciente DICOM, como vem do
    `ContourData`. Não recebe `Dataset`: ler é de quem chama.
  - Saída: margem por direção (direita, esquerda, anterior, posterior,
    superior, inferior), com a convenção LPS escrita na docstring
    (+x = esquerda do paciente, +y = posterior, +z = superior), a margem
    mínima 3D, a resolução usada e a espessura de corte. A precisão em
    superior/inferior nunca é melhor que a espessura de corte, e a saída diz
    isso. Se a interna não estiver contida na externa, a saída traz a fração
    do volume interno que fica fora, em vez de uma margem negativa calada.
  - O método é escolha do robô, justificada na docstring. O esperado é
    rasterizar numa grade comum de resolução declarada e medir a distância
    ao longo das linhas da grade.
  - Uma função que lista pares candidatos (interna, externa) por contenção
    geométrica (fração do volume interno dentro do externo ≥ limiar). Nunca
    por semelhança de nome: o nome só aparece na saída.
  - `tests/test_rt_margem.py` com casos sintéticos de margem conhecida:
    anisotrópica (7 mm lateral, 5 mm AP, 10 mm SI), isotrópica, interna
    deslocada e parcialmente fora, vários polígonos e buraco no mesmo corte,
    cortes de 2,5 e 3 mm. Erro dentro da resolução declarada. As docstrings
    dizem o que quebraria no uso, no estilo do `CLAUDE.md`.
  - Um teste com um caso de `../../dicom-teste/` que tenha CTV e PTV,
    pulado quando o acervo não existir (como `tests/test_regressao_papel.py`).
    Confere só coerência (contida, margem ≥ 0, pares achados pela
    contenção), sem fixar número que ninguém conferiu no TPS.
  - Suíte verde e ordem aleatória.
- fora: veredito ou comparação com a margem do protocolo (módulo Plano,
  frente `voce`); tela; papel; ler RT Struct de arquivo; mexer em `dicom/`
  (é a R-58); casar CTV↔PTV por nome.

### R-00 — Um teste da Capa só passa nesta estação
- classe: robo
- estado: feita (15/09/2026)
- pilar: 4
- pronto quando: `test_capa_tela.TestCapaDeUmaPasta.test_pasta_sem_identidade_oferece_a_busca`
  passa num worktree limpo, sem nada do que o `.gitignore` deixa de fora.
  Medido em 15/09/2026: no checkout do usuário a suíte dá 1.945 OK; no
  worktree `..\isocentro-robo` dá **1 falha**, com o status dizendo "nenhum
  paciente na lista — os relatórios não estão em ...\capa (procura
  automática)" em vez de "não identifiquei". O teste depende de algo do disco
  da estação (hipótese: `TCs_Teste/`), e é por isso que é a primeira: o robô
  confere cada frente com a suíte VERDE, e com ela vermelha nenhuma outra
  passa.
- fora: `isocentro/interface/capa.py`. Se o conserto for no app e não no
  isolamento do teste, estacionar e descrever.

### R-01 — O texto "PARA A TI" do checkup pede o que já existe
- classe: robo
- estado: feita (15/09/2026)
- pilar: 1
- pronto quando: a rodada SEM argumentos do `tools/checkup_clinica.py` deixa
  de pedir o cadastro do AE de destino `RADIOTERAFICHA`, que existe desde
  10/09, e um teste prova o texto novo.
- fora: qualquer mudança no que o checkup MEDE; só o texto do pedido.

### R-02 — O resíduo de ~2 s em cada teste de `TestDiagnosticoNoApp`
- classe: robo
- estado: feita (15/09/2026, a674b46 — numa sessão com o usuário, antes do robô)
- pilar: 4
- pronto quando: medido o que custa os ~2 s (não é tempo-limite de rede: o
  `test_para_na_primeira_camada_que_falha` não faz `connect`), e ou o custo
  sai do teste sem mudar o que ele prova, ou fica escrito por que não sai.
- fora: produção. Se o custo estiver no código do app, estacionar e descrever.

### R-03 — Roteiro de instalação da concentradora
- classe: robo
- estado: feita (15/09/2026)
- pilar: 1
- pronto quando: `docs/INSTALAR_CONCENTRADORA.md` lista, na ordem, o que
  fazer no `clinica-python01` (as 4 chaves DICOM e a `RAIZ_SIMULACOES` no
  `config_servico.json`, a Tarefa Agendada e a conta dela, o `--conferir`), e
  **cada passo cita a seção do `notas/` ou o código que o sustenta**. Passo sem
  fonte não entra: vira pergunta no fim do documento.
- fora: rodar qualquer coisa contra a clínica; mudar código.

### R-04 — Fim de linha uniforme fora das pastas travadas
- classe: robo
- estado: feita (15/09/2026)
- pilar: 4
- pronto quando: os arquivos CRLF fora de `papel/`, `interface/` e `dominio/`
  viram LF (e o BOM que houver sai), `git diff --ignore-cr-at-eol` do commit é
  vazio, e a suíte passa. A lista dos que ficaram (os das pastas travadas) vai
  para a seção desta frente.
- fora: os arquivos das pastas travadas — ficam para uma frente `voce`.

### R-05 — Proposta de divisão do `gui.py`
- classe: robo
- estado: feita (16/09/2026)
- pilar: 4
- pronto quando: `docs/PROPOSTA_GUI.md` mostra, medido pelo `tools/mapa.py` e
  por grep, os blocos do `gui.py` (quais métodos andam juntos, quem chama quem,
  o que os testes importam dele) e propõe a divisão em módulos com o custo de
  cada corte. **É proposta: nenhuma linha do `gui.py` muda.**
- fora: executar a divisão (é a R-06, do usuário).

### R-06 — Dividir o `gui.py`
- classe: voce
- estado: feita (16/09/2026, cortes 1–6: `gui.py` 5.728 → 2.595 linhas)
- pilar: 4
- por que não é do robô: `interface/` é tela, e tela muda com aceite. Parte da
  proposta da R-05, e cada corte confere a janela pelo `tools/tela.py`.
- andamento: cortes 2 (arranque) e 3 (Ficha Virtual) feitos em 16/09/2026;
  faltam 1, 4, 5 e 6 (ver `NOTAS.md`, seção da R-06).

### R-11 — O checkup separa "recusada" de "firewall" pelo relógio
- classe: voce
- estado: feita (15/09/2026, 7c2baef — já estava no commit que criou esta fila;
  ver "A recusa pelo tipo, não pelo relógio", no `notas/2026-09.md`. Conferido
  em 17/09: `_tcp_aberta` lê o tipo da exceção, e o `DegrauDeBaixo` cobre
  recusa, silêncio e o terceiro `OSError`)
- pilar: 1
- por que não é do robô: é código que vai para a clínica e a seção "A porta
  fechada que não recusa na hora" (15/09) deixou como **decisão do usuário**.
  O `checkup_clinica._tcp_aberta` usa `gasto < prazo * 0.8`; a recusa custa
  2,04 s no Windows contra um limiar de 2,4 s, e em VPN com latência a porta
  sem serviço sairia "assinatura de firewall". A exceção já distingue as duas
  (`ConnectionRefusedError` × `TimeoutError`).

### R-12 — Proposta de divisão do `tratamento.py`
- classe: robo
- estado: feita (17/09/2026)
- pilar: 4
- pronto quando: `docs/PROPOSTA_TRATAMENTO.md` mostra, medido pelo
  `tools/mapa.py` e por AST, os blocos do `tratamento.py` e propõe a divisão
  com o custo de cada corte. **É proposta: nenhuma linha do `tratamento.py`
  muda.**
- fora: executar a divisão (é a R-13, do usuário).

### R-13 — Dividir o `tratamento.py`
- classe: voce
- estado: feita (13/10/2026, os dois cortes: `tratamento.py` 3.321 → 1.771
  linhas, `tratamento_pecas.py` e `tratamento_janelas.py`; o painel NÃO foi
  dividido, decisão do usuário)
- pilar: 4
- por que não é do robô: `interface/` é tela, e tela muda com aceite. Dois
  cortes propostos na R-12 (as 13 peças menores e as duas janelas grandes:
  3.077 → ~1.760 linhas), e a proposta recomenda **não** dissolver o
  `PainelFichaVirtual` agora — o estado dele é compartilhado entre as seções
  (45 dos 69 atributos). Portão: `tools/tela.py` na aba, suíte e ordem
  aleatória; a chave `tratamento.py:_JanelaImagem` das `EXCECOES` do
  `test_padrao_visual` morre no corte e muda no mesmo commit.

### R-07 — Conferir os 165 cursos contra o ARIA
- classe: voce
- estado: pendente
- pilar: 2
- por que não é do robô: é olhar no ARIA, itens (a)/(b)/(c)/(d) de "A
  conferência da LISTA: `--consulta` no `mapear_tratamento`" (10/09, no
  `notas/2026-09.md`). Destrava o `LISTA_VERIFICADA_EM` e o pilar 2.
- pronto quando (26/10/2026, epics.md P-8): os 165 cursos conferidos contra
  o ARIA nos itens (a)–(d), divergências anotadas, e `LISTA_VERIFICADA_EM`
  gravado em cada curso conferido.

### R-08 — Instalar a concentradora no `clinica-python01`
- classe: clinica
- estado: pendente
- pilar: 1
- por que não é do robô: a TI aponta o destino `RADIOTERAFICHA` para
  `192.0.2.20:104`, libera a porta, cria o share e a conta da Tarefa
  Agendada. O roteiro é a R-03.
- pronto quando (26/10/2026, epics.md P-8): o destino `RADIOTERAFICHA`
  aponta para `192.0.2.20:104` com a porta liberada, o share e a conta da
  Tarefa Agendada existem, e a concentradora roda pelo roteiro da R-03, com
  uma execução registrada.

### R-09 — Tabelas de feixe dos aceleradores do serviço
- classe: clinica
- estado: pendente
- pilar: 3
- por que não é do robô: TMR e Scp são medida de comissionamento de cada
  máquina; o `dados_feixe/` de hoje é de outro serviço. Sem elas o paralelo
  é DEMONSTRAÇÃO, e casar por parecença de nome é proibido.
- pronto quando (spec Plano, CAP-1): tabela por máquina e energia com
  origem, conversão validada contra pontos do relatório original, nomes DICOM
  cadastrados um a um, FFF e filtros com tabela ou "sem tabela", transmissão
  do MLC e DLG com origem.

### R-10 — Base histórica para calibrar a Qualidade
- classe: clinica
- estado: pendente
- pilar: 3
- por que não é do robô: o TG-218 manda derivar a tolerância do processo do
  próprio serviço. O dado é da clínica; o método, quando houver dado, muda o
  `dominio/` e é frente `voce`.

### R-14 — Base clínica e brief do sistema global
- classe: voce
- estado: pendente
- pilar: sistema global (o ISOCENTRO como núcleo; PPR e scripts ESAPI
  entram como módulos)
- pronto quando: `docs/qms/escopo.md` preenchido pelo físico, e o brief do
  `bmad-product-brief` gravado em `docs/planejamento/sistema-global/`. A
  classificação 62304 e os riscos podem ficar para depois do PRD, mas o
  revisor clínico vai apontar a lacuna enquanto estiverem vazios.
- por que não é do robô: escopo e classe de segurança são decisão clínica.
  Um agente que lê `docs/qms/` trata o que está escrito como fato — escrito
  pela IA, viraria decisão que ninguém tomou.
- fora: código. A frente termina em documento.

### R-15 — PPR: extração de ASOs sem enviar texto a terceiros
- classe: voce
- estado: feita (28/10/2026)
- andamento (28/10/2026): `aso.py` + `tests/test_aso.py` no ramo
  `r15-aso-local` do `ppr-streamlit`, sem merge: o usuário mantém o
  Streamlit como está, e o PPR passa a ser construído dentro do ISOCENTRO
  (a função vai junto). Lê a planilha de controle (CPF NOME COLABORADOR |
  ANTERIOR VENCIMENTO); no PDF real, 42 registros, todos com 365–366 dias.
  As 19 páginas de ASO digitalizado nunca foram lidas (nem pela IA): só
  imagem.
- pilar: sistema global (módulo PPR, ainda no repositório `ppr-streamlit`)
- pronto quando: `extrair_asos_do_pdf` do `ppr-streamlit/app.py` lê os ASOs
  sem chamar a API da Anthropic, e um teste com PDF de ASO fictício prova
  que nome, data de realização e vencimento saem corretos. Decidido em
  13/10/2026 (`docs/qms/escopo.md`): ASO é dado de saúde de funcionário,
  dado sensível pela LGPD, e o sistema não envia dado pessoal a terceiros.
- por que não é do robô: o código está em outro repositório, e o formato
  dos PDFs de ASO do serviço é dado da clínica — o teste precisa de um
  modelo real anonimizado.
- fora: a outra chamada à API no PPR (leitura dos PDFs por seção), que
  precisa da mesma análise antes de mudar.

### R-16 — Escopo, perfis e riscos da Fundação
- classe: voce
- estado: pendente
- andamento (26/10/2026): `escopo.md` com os 7 perfis, a tabela perfil →
  capacidades configurável pelo admin (valor inicial = matriz da UX) e as
  travas fora dela, e o banco central (G6); núcleo, Plano e Radioteraficha
  em classe A no `classificacao-62304.md`; RF-1..RF-23 no `riscos.md`.
  Falta: o físico preencher efeito e S/O/D das RF.
- pilar: sistema global (spec `docs/planejamento/sistema-global/spec-isocentro-fundacao/`)
- pronto quando: `docs/qms/escopo.md` registra o banco central e a nova
  fronteira de gravação (Q8/G6) e os 7 perfis; tabela perfil → capacidades
  escrita (G8); `riscos.md` com uma linha por modo de falha de
  `rastreabilidade.md`; classe do núcleo em `classificacao-62304.md` ou AD-35
  confirmado (G1).
- fora: código. Termina em documento.

### R-17 — PostgreSQL 18 em `clinica-python01`
- classe: clinica
- estado: pendente
- pilar: sistema global (spec Fundação, CAP-1)
- pronto quando: PostgreSQL 18 em homologação e produção com TLS obrigatório,
  papéis `isocentro_dono`/`isocentro_app`/`isocentro_concentradora`, pasta da
  TI só-acrescentar para a âncora e pasta restrita em `\\fileserver` para backup.
- fora: esquema e código do núcleo (R-18).

### R-18 — Núcleo: esquema, `nucleo.gravar` e log encadeado
- classe: voce
- estado: feita (27/10/2026)
- pilar: sistema global (spec Fundação, CAP-1, CAP-4, CAP-5)
- pronto quando: testes em PostgreSQL provam transação tudo-ou-nada,
  UPDATE/DELETE negados no log e o verificador apontando a linha alterada;
  suíte verde.
- fora: telas, módulos verticais.

### R-19 — Identidade: login no banco, capacidades, RLS e migração do núcleo
- classe: voce
- estado: pendente
- pilar: sistema global (spec Fundação, CAP-2, CAP-3, CAP-20)
- pronto quando: CAP-2, CAP-3 e CAP-20 provados em PostgreSQL; usuários,
  sessões, equipe e configuração migrados por corte de entidade; equipe com
  cargo e marca IOE por pessoa e clínica (spec Documentação, CAP-9); `ANA` →
  `DUO`; `keyring` (WinVaultKeyring) e `pywin32` fixados depois de
  conferidos no PyPI (AR-30, epics.md P-5). Depende de R-16 (perfis) e R-18.
- fora: checklist, `registro_json`, `cadastro_sus`, correções.

### R-78 — Tabela perfil → capacidades configurável
- classe: voce
- estado: pendente
- pilar: sistema global (spec Fundação, CAP-23)
- depende de: R-19
- pronto quando: tabela no banco nascendo com a matriz do `escopo.md`; tela
  de seleção em Configurações (layout aceito antes); mudança gravada por
  `nucleo.gravar` com autor no log; teste em PostgreSQL prova que as quatro
  travas resistem a qualquer configuração; CAP-3 confere a tabela vigente.
- fora: capacidades declaradas pelo módulo e concedidas por clínica.

### R-77 — Motor de verificação: o contrato puro, sem gravação
- classe: robo
- estado: feita (23/10/2026)
- pilar: sistema global (spec Fundação, CAP-7, CAP-8, CAP-10, CAP-11)
- metade de: R-20 (a execução gravada fica lá)
- pronto quando: `isocentro/nucleo/verificacao.py` (sem Qt, banco, rede nem
  arquivo) tem os 5 resultados, o tipo da verificação com id
  `<modulo>.<nome>` e proveniência, e o motor que chama um avaliador puro;
  testes provam: exceção do avaliador → `erro` com a mensagem; sem dado →
  `indeterminado` com motivo; nenhum dos dois conta como `conforme`;
  cadastro sem fonte ou com tolerância sem origem (`literatura` +
  referência, ou `servico` + data e método) é recusado; resultado de
  verificação em sombra não vira alerta; execução `semeado` não entra em
  indicador. A gravação é uma porta (protocolo), com uma implementação em
  memória só para os testes.
- fora: PostgreSQL, `nucleo.gravar`, execução vigente e idempotência no
  banco (R-20); resolver a fonte contra o `conhecimento/`; verificações
  reais dos módulos.

### R-82 — Origem `provisoria` da tolerância no catálogo
- classe: robo
- estado: feita (26/10/2026)
- pilar: sistema global (spec Fundação, CAP-7)
- pronto quando: `isocentro/nucleo/verificacao.py` aceita a origem
  `provisoria` só com o número de um item de `decisoes-sem-base.md` e recusa
  sem ele; testes cobrem aceite e recusa; suíte verde.
- fora: a marca "provisório" na tela (R-23 e telas dos módulos).

### R-20 — Motor de verificação
- classe: voce
- estado: feita (27/10/2026)
- pilar: sistema global (spec Fundação, CAP-6 a CAP-11)
- depende de: R-77 (contrato puro), R-18 (gravação), R-76 (JSON ESAPI)
- pronto quando: a porta de gravação da R-77 tem a implementação no
  PostgreSQL pelo `nucleo.gravar`; testes em PostgreSQL provam a
  idempotência (mesma verificação, objeto e versão → uma execução vigente)
  e a importação do JSON ESAPI como execução; toda execução registra o
  identificador e o checksum do arquivo lido (RT Plan) e a data da carga do
  `variandw`, e execução sem esses campos é recusada (FR-39, epics.md P-2).
- fora: verificações reais dos módulos; avaliador C#.

### R-21 — Alerta, assinatura e concentradora
- classe: voce
- estado: feita (28/10/2026)
- pilar: sistema global (spec Fundação, CAP-12 a CAP-14)
- pronto quando: teste prova prazo vencido com o app fechado como alerta
  `alta` na abertura seguinte; assinatura volta a pendente quando a versão do
  plano muda; `QTimer` de `gatilho_relogio` removido; a concentradora grava
  todo dia o hash da ponta da corrente na pasta da TI só-acrescentar (R-17),
  e o verificador da R-18 compara a corrente com as âncoras, apontando
  registro e posição de uma linha alterada depois da âncora (AD-32, FR-3,
  epics.md P-3). Instalação no servidor segue a R-08.
- fora: canal de alerta externo; a pasta real da âncora e as variáveis
  `ISOCENTRO_PG_CONCENTRADORA` e `ISOCENTRO_PASTA_ANCORA` no servidor (R-17,
  R-08); as fontes de prazo dos módulos (`varredura_cli.FONTES_DE_PRAZO`,
  cada spec de módulo registra a sua).

### R-22 — Degraus no PostgreSQL, banco fora e exportador
- classe: voce
- estado: pendente
- pilar: sistema global (spec Fundação, CAP-15, CAP-16, CAP-18)
- pronto quando: espelho no PostgreSQL com RLS e limpeza registrada no log;
  teste com banco inacessível sem gravação nem fila; `varrer_identidade` e
  teste de log verdes.
- fora: relatórios CSV (seguem como hoje).

### R-23 — Porte PySide6 e shell Torre de controle
- classe: voce
- estado: pendente
- pilar: sistema global (spec Fundação, CAP-19)
- pronto quando: app inteiro em PySide6; login, Início de 3 zonas, doca de 9,
  seletor de clínica e barra de status com degrau; `test_padrao_visual` na
  paleta nova e reprovando verde fora da dose; anel de foco em todo
  clicável, ordem de Tab do EXPERIENCE.md, Alt+Home, Ctrl+Tab e
  Ctrl+P/Ctrl+Enter; contraste conferido nos dois modos (texto ≥ 4,5:1,
  sinal ≥ 3:1); estados "banco central fora", "`variandw` fora" e "nada
  precisa de ação" sem máquina "normal" nem zero por falta de dado; versão
  do PySide6 fixada depois de conferida no PyPI (UX-DR20..22, AR-30,
  epics.md P-4); aceite da tela antes.
- fora: redesenho das telas do Radioteraficha.

### R-24 — Teste de arquitetura
- classe: robo
- estado: feita (23/10/2026)
- pilar: 4 (spec Fundação, CAP-21)
- pronto quando: teste por `ast` em `tests/` reprova as dependências
  proibidas do AD-22, com as 4 violações atuais numa lista de exceções
  datada; as regras de `rt/` (AD-38) e do manifesto (AD-40) entram
  desligadas e acendem quando R-58 e R-60 chegarem; suíte verde.
- fora: corrigir as violações; `papel/`, `interface/`, `dominio/`.

### R-25 — Backup cifrado e restauração
- classe: clinica
- estado: pendente
- pilar: sistema global (spec Fundação, CAP-17)
- pronto quando: `pg_dump` diário AES-256 em `\\fileserver` (30 dias), dump mensal
  em mídia separada, chave lacrada com SPR/gestão, 1ª restauração registrada
  no log e roteiro de manutenção escrito.
- fora: código do app.

### R-26 — Relatório de validação do núcleo
- classe: voce
- estado: pendente
- pilar: sistema global (spec Fundação, CAP-22)
- pronto quando: relatório com requisitos, testes, casos à mão,
  sensibilidade semeada e versão, assinado pelo físico antes do 1º uso em
  produção.
- fora: relatórios dos módulos.

### R-83 — Módulo Software e sistemas: catálogo, promoção, sensibilidade, cobertura e SOUP
- classe: voce
- estado: pendente
- pilar: sistema global (PRD FR-4, FR-6, FR-37, FR-38; EXPERIENCE.md, Software
  e sistemas; epics.md P-1, 26/10/2026)
- pronto quando: a tela do módulo lista o catálogo com estado (sombra, ativa,
  podada) e, para o físico, promove ou poda com o resumo da sombra gravado por
  `nucleo.gravar`; mostra o relatório de sensibilidade por verificação
  (semeados, detectados, não detectados); publica a cobertura (atividades com
  verificação ativa, sombra fora) sobre 74 e sobre 60, calculada do cadastro;
  gera o inventário SOUP com versão e licença a partir do `requirements.txt` +
  `constraints.txt`, com as ressalvas de risco conhecido; aceite da tela antes.
  Depende de R-20, R-21, R-23.
- por quê: nenhuma frente cobria FR-37 e FR-38, e o relatório de validação de
  todo módulo (FR-40) exige o SOUP.
- fora: ciclo ISQM completo; itens do MPPG 5.b.

### R-71 — Questionário do físico para o módulo Plano
- classe: robo
- estado: feita (23/10/2026)
- pilar: 3 (spec Plano, Open Questions)
- prepara: R-27
- pronto quando: `docs/planejamento/questionarios/plano.md` tem, para
  cada pergunta em aberto da R-27 (G1, P5, P7, P8, P9, P12, NFR-5, FFF/filtros), uma seção com a pergunta
  numa frase, as opções que a spec e a base levantam, cada uma com a fonte
  (`[CÓDIGO p. N]` conferido no texto da base, ou o AD/FR da spec), o que
  cada opção muda adiante e quais frentes a resposta destrava; uma linha
  `resposta do físico:` vazia no fim de cada seção; o cabeçalho diz
  "rascunho da IA: nada aqui é decisão". Pergunta sem fonte na base fica
  com "a base não responde" e nenhuma opção inventada.
- fora: escolher ou recomendar opção; escrever em `docs/qms/`, no memlog
  da spec ou no `riscos.md` (é da R-27, pelo físico).

### R-27 — Decisões do físico para o módulo Plano
- classe: voce
- estado: pendente
- andamento (26/10/2026): todas as perguntas respondidas no
  `docs/planejamento/questionarios/plano.md` (commit 66f6962) e levadas à
  spec do Plano (commit f28ec60: memlog, CAP-1..CAP-18). Falta a tolerância
  em mm das conferências de isocentro e as linhas do Plano no `riscos.md`.
- pilar: 3 (spec Plano, Open Questions)
- pronto quando: G1 (classe do Plano), P5, P7, P8, P9, P12, NFR-5 e FFF/filtros
  respondidos e gravados no memlog da spec; linhas do Plano no `riscos.md`
  (S, O, D).
- fora: código.

### R-28 — Códigos das atividades PSQA, Aprovação Física e Duplo Check no `variandw`
- classe: clinica
- estado: pendente
- pilar: 2 (spec Plano, CAP-9; P6)
- pronto quando: códigos e campos mapeados e conferidos em 5 planos reais
  contra o ARIA.
- fora: código.

### R-29 — Comissionamento da segunda checagem por máquina
- classe: clinica
- estado: pendente
- pilar: 3 (spec Plano, CAP-6; FR-14)
- pronto quando: pontos TG-219 Tab. 8 e casos TG-119 medido × calculado nas 4
  máquinas, transmissão do MLC e DLG com origem; tabelas 6FFF e 10FFF
  (TrueBeam) e 6FFF (VitalBeam). Depende de R-09.
- fora: código do cálculo.

### R-30 — Segunda checagem 3D no motor
- classe: voce
- estado: pendente
- pilar: 3 (spec Plano, CAP-1, 2, 3, 5, 7; FR-10 a FR-15)
- pronto quando: `plano.segunda_checagem` roda na concentradora ao Planning
  Approved; testes: UID divergente → `indeterminado` + alerta, nome DICOM
  trocado sem tabela, filtro → `indeterminado`, limites TG-114 com origem,
  prazo vencido com app fechado, prazo dos 10% pela dose registrada no
  curso e na fase disparando pelo que vencer primeiro e dizendo qual venceu.
  Depende de R-09, R-20, R-21.
- fora: modulado (R-31).

### R-31 — Clarkson por ponto de controle para IMRT/VMAT
- classe: voce
- estado: pendente
- pilar: 3 (spec Plano, CAP-4; P3)
- pronto quando: casos TG-119 dentro dos limites TG-219 nas máquinas
  comissionadas; sem comissionamento → `indeterminado`. Depende de R-29 e R-30.
- fora: recálculo 2D/3D.

### R-32 — Índices de qualidade como verificações `plano.*`
- classe: voce
- estado: pendente
- pilar: 3 (spec Plano, CAP-8; U1)
- pronto quando: `qualidade.py` vira verificações com tolerância e origem; a
  aba sai do Radioteraficha; resultados iguais aos de hoje em 10 planos de
  referência.
- fora: calibração TG-218 (R-10); tela Virtual.

### R-33 — Sequência real, alto risco e filas
- classe: voce
- estado: pendente
- pilar: 2 (spec Plano, CAP-9 a CAP-11; FR-16 a FR-18)
- pronto quando: datas com tabela/campo/degrau, ausente vazia; alto risco
  por ≥ 6 Gy/fração, ≤ 5 frações ou curso em menos de 6 dias (duração lida
  do agendamento; sem agendamento → "não informado"); "não informado" →
  prazo antes da 1ª fração; contadores da Zona 1 abrem a fila filtrada.
  Depende de R-28.
- fora: assinatura (R-34).

### R-34 — Listas, conferência da prescrição e segunda assinatura
- classe: voce
- estado: pendente
- pilar: 1 (spec Plano, CAP-12 a CAP-15; FR-19 a FR-21, FR-42)
- pronto quando: 13/8/8 itens com automáticos (valor, fonte, referência);
  máquina da prescrição = agendamento = RT Plan; curso anterior aberto por
  status ≠ concluído; as quatro conferências de isocentro medidas sem
  veredito até haver tolerância em mm; itens "++"/F do TG-275 em sombra;
  divergência prescrição × RT Plan → `nao_conforme`; Duplo Check do mesmo
  físico não registrado; plano alterado → pendente, inclusive conteúdo
  alterado sem UID novo.
- fora: papel (assinatura impressa continua).

### R-35 — Tela do módulo Plano
- classe: voce
- estado: pendente
- pilar: sistema global (spec Plano, CAP-16)
- pronto quando: UJ-1 e UJ-2 de ponta a ponta em homologação; leitura demorada
  em segundo plano; aceite da tela antes. Depende de R-23.
- fora: redesenho do Radioteraficha.

### R-36 — Relatório de validação do Plano
- classe: voce
- estado: pendente
- pilar: 3 (spec Plano, CAP-17; FR-40)
- pronto quando: sensibilidade semeada por verificação `plano.*` (inclui
  conteúdo alterado sem UID novo), comissionamento e casos à mão; assinado
  pelo físico antes do 1º uso real.
- fora: relatório do núcleo (R-26).

### R-79 — Catálogo MPPG 11.a como verificações `plano.*`
- classe: voce
- estado: pendente
- pilar: 3 (spec Plano, CAP-18; P7)
- pronto quando: as 160 linhas do MPPG 11.a (`itens-nivel2.csv`, lote 5)
  carregadas com tabela, item e etapa (inicial, semanal, fim de tratamento,
  HDR); automatizáveis em sombra até a conferência linha a linha; manuais
  opcionais e vazios na lista da etapa; teste prova que as listas votadas
  (13/8/8) não mudam. Depende de R-20 e R-34.
- fora: cálculo e CQ da HDR (MVP 3); onde aparecem as etapas semanal e de
  fim de tratamento (pergunta aberta da spec).

### R-72 — Questionário do físico para o módulo GQ
- classe: robo
- estado: feita (23/10/2026)
- pilar: sistema global (spec GQ, Open Questions)
- prepara: R-37
- pronto quando: `docs/planejamento/questionarios/gq.md` tem, para
  cada pergunta em aberto da R-37 (classe do TRS-398, k_Q/N_D,w × ICRU 90, C2, retenção, sombra dos itens nível 2, Dermopan), uma seção com a pergunta
  numa frase, as opções que a spec e a base levantam, cada uma com a fonte
  (`[CÓDIGO p. N]` conferido no texto da base, ou o AD/FR da spec), o que
  cada opção muda adiante e quais frentes a resposta destrava; uma linha
  `resposta do físico:` vazia no fim de cada seção; o cabeçalho diz
  "rascunho da IA: nada aqui é decisão". Pergunta sem fonte na base fica
  com "a base não responde" e nenhuma opção inventada.
- fora: escolher ou recomendar opção; escrever em `docs/qms/`, no memlog
  da spec ou no `riscos.md` (é da R-37, pelo físico).

### R-37 — Decisões do físico para o módulo GQ
- classe: voce
- estado: pendente
- andamento (26/10/2026): todas as perguntas respondidas no
  `docs/planejamento/questionarios/gq.md` e levadas à spec do GQ (commits
  b231702 e 41d20c6: CAP-1..CAP-15; TRS-398 de 2000 e k_Q das
  Scanditronix-Wellhöfer no acervo). Faltam as linhas do GQ no `riscos.md`
  e a correção B1 na base.
- pilar: sistema global (spec GQ, Open Questions)
- pronto quando: classe do cálculo TRS-398, k_Q/N_D,w × ICRU 90, C2, retenção,
  sombra dos itens nível 2 e Dermopan respondidos no memlog; linhas do GQ no
  `riscos.md` (S, O, D); B1 corrigido na base (`fff`, HDR no
  `programa-cq.csv`).
- fora: código.

### R-38 — Origem das imagens de CQ e das exportações de medida
- classe: clinica
- estado: pendente
- pilar: sistema global (spec GQ, CAP-8, CAP-9; C3)
- pronto quando: pasta e formato das imagens EPID/kV e das exportações do
  DailyQA 3 e do MapCHECK levantados, com um arquivo de exemplo de cada
  máquina.
- fora: código.

### R-39 — Programa de CQ, registro, fora de tolerância e vencidos
- classe: voce
- estado: pendente
- pilar: sistema global (spec GQ, CAP-1 a CAP-5; FR-22 a FR-25)
- pronto quando: carga do `qualidade.json` + itens nível 2 por máquina com
  versão; item nível 2 em sombra até o registro de conferência daquele item;
  Dermopan na CEL com os 12 testes `orto` (dosimétricos `indeterminado` sem
  câmara calibrada em 50 kV); cadastro de ação e limite de ação no banco,
  vazios, com teste sem ação avisado no cartão; resultado calculado; erro
  semeado: valor fora → `nao_conforme` + `alta` no mesmo dia, diário sem
  registro → alerta com app fechado; carta com origem do limite. Depende de
  R-20, R-21.
- fora: pylinac (R-41), TRS-398 (R-40), HDR (R-42).

### R-40 — Instrumentos, aferição e calibração TRS-398 calculada
- classe: voce
- estado: pendente
- pilar: sistema global (spec GQ, CAP-6, CAP-7, CAP-14; FR-36)
- pronto quando: instrumentos com certificado e periodicidade por tipo
  (arts. 49, 52, 54, 55), vencimento na hora por conserto, dano ou
  transporte, prazos expostos na fachada; aferição com decaimento (Sr-90,
  Ir-192) conferida à mão contra ±1%; cálculo TRS-398 no item próprio de
  classe C (CAP-15, puro, sem tela), com k_Q da edição de 2000 (Tab. 6.III
  da V.12; FC65-G e FC65-P pela `TRS-398-KQ-SW`) e N_D,w do certificado
  atual, os dois registrados com cada execução; reproduz a planilha atual
  do serviço em casos conferidos à mão; fator sem fonte → `indeterminado`.
  Depende de R-39.
- fora: TG-51 como cálculo (só checagem cruzada).

### R-41 — Análise de imagem pelo pylinac
- classe: voce
- estado: pendente
- pilar: sistema global (spec GQ, CAP-8)
- pronto quando: picket fence, Winston-Lutz e fantomas de kV/CBCT
  comissionados contra imagens de resultado conhecido; erro plantado
  detectado; versão do pylinac fixada. Depende de R-38 e R-39.
- fora: QA de paciente.

### R-42 — HDR e importação de exportações
- classe: voce
- estado: pendente
- pilar: sistema global (spec GQ, CAP-9, CAP-10; FR-26, FR-27)
- pronto quando: troca de fonte → "não liberada" + `alta` até S_K (3%/5%);
  arquivo importado com hash; formato não lido → anexo + digitado;
  exportação de PSQA recusada. Depende de R-38 e R-39.
- fora: planejamento HDR.

### R-43 — Tela do GQ e relatório de validação
- classe: voce
- estado: pendente
- pilar: sistema global (spec GQ, CAP-11 a CAP-13; FR-28, FR-40)
- pronto quando: UJ-3 de ponta a ponta em homologação com aceite da tela;
  restauração com log válido; nenhum caminho apaga registro de CQ (retenção:
  enquanto o equipamento existir e no mínimo 10 anos após o descarte do
  software); relatório de validação assinado antes do uso real. Depende de
  R-23, R-25.
- fora: painel de vencimentos (módulo Documentação).

### R-73 — Questionário do físico para o módulo Segurança do paciente
- classe: robo
- estado: feita (23/10/2026)
- pilar: sistema global (spec Segurança, Open Questions)
- prepara: R-44
- pronto quando: `docs/planejamento/questionarios/seguranca.md` tem, para
  cada pergunta em aberto da R-44 (etapas do Care Path, escala de desvio dosimétrico, retenção; a classificação dos 30 incidentes fica fora), uma seção com a pergunta
  numa frase, as opções que a spec e a base levantam, cada uma com a fonte
  (`[CÓDIGO p. N]` conferido no texto da base, ou o AD/FR da spec), o que
  cada opção muda adiante e quais frentes a resposta destrava; uma linha
  `resposta do físico:` vazia no fim de cada seção; o cabeçalho diz
  "rascunho da IA: nada aqui é decisão". Pergunta sem fonte na base fica
  com "a base não responde" e nenhuma opção inventada.
- fora: escolher ou recomendar opção; escrever em `docs/qms/`, no memlog
  da spec ou no `riscos.md` (é da R-44, pelo físico).

### R-44 — Decisões e insumos para o módulo Segurança do paciente
- classe: voce
- estado: pendente
- andamento (26/10/2026): respostas da R-73 levadas à spec e ao PRD (Ford 2012 nos dois campos; dose pelo Ford, local/volume pelo TG-100; guarda permanente; Epimed substituído pelo registro próprio, com Notivisa e ANSN como canais legais). O que ficou sem base está em `decisoes-sem-base.md` (#15–17, #28–31). Falta: linhas do módulo no `riscos.md` e os 30 incidentes do kappa.
- pilar: sistema global (spec Segurança, Open Questions)
- pronto quando: linhas do `riscos.md` (S, O, D) gravadas; 30 incidentes
  históricos separados e classificados por dois físicos com kappa ≥ 0,7.
- fora: código.

### R-45 — NSP e Notivisa
- classe: clinica
- estado: pendente
- pilar: sistema global (spec Segurança, CAP-4; I1)
- pronto quando: NSP confirma se cobre a radioterapia e quem é o usuário
  Notivisa (gestor ou técnico) do serviço; manual 2025 dos campos do
  formulário Notivisa (NSP) no acervo. Calendário: só feriado nacional,
  provisório (`decisoes-sem-base.md` #29).
- fora: código.

### R-46 — Registro, leitura restrita, prazos e análise
- classe: voce
- estado: pendente
- pilar: sistema global (spec Segurança, CAP-1 a CAP-7; FR-29 a FR-32)
- pronto quando: teste em PostgreSQL recusa texto livre a perfil sem acesso;
  notificador fora de tela e relatório; leitura de dado sensível gera
  evento; art. 26 → `alta` até investigação iniciada, `atencao` 20 d /
  `alta` 30 d com app fechado; relatório nos itens a–k do guia CNEN; 15º
  dia útil, 72 h e 60 dias certos em casos de borda; ciclo e triagem com
  alertas. Depende de R-20, R-21, R-45.
- fora: matriz e indicadores (R-47).

### R-47 — Matriz, indicadores, tela e validação
- classe: voce
- estado: pendente
- pilar: sistema global (spec Segurança, CAP-8 a CAP-10)
- pronto quando: matriz e taxa por 1.000 frações com degrau; supressão < 5
  no relatório; UJ-5 em homologação com aceite da tela; relatório de
  validação com kappa e RIPD, assinado. Depende de R-23, R-44, R-46.
- fora: envio automático ao Notivisa ou à ANSN; botão global.

### R-80 — Insumos da matriz de risco
- classe: voce
- estado: pendente
- pilar: sistema global (spec Segurança, CAP-11; FR-49; PRD I5)
- pronto quando: documento do método da matriz de risco (Foro
  Iberoamericano / IAEA TECDOC-1685) e catálogo de eventos iniciadores e
  barreiras do SEVRRA por prática no acervo, com a licença de uso
  conferida; correspondência entre as 11 etapas do SEVRRA e as 8 do Ford
  gravada; lista das barreiras com dado no ISOCENTRO e das manuais;
  decidido se a ortovoltagem entra; pergunta à CNEN sobre a matriz no
  lugar do SEVRRA (`decisoes-sem-base.md` #32).
- fora: código.

### R-81 — Matriz de risco em tempo real
- classe: voce
- estado: pendente
- pilar: sistema global (spec Segurança, CAP-6 e CAP-11 a CAP-14; FR-47, FR-49)
- pronto quando: catálogo carregado com fonte por linha; estado de cada
  barreira lido das fachadas da GQ, do Plano e da Segurança; barreira sem
  dado conta como não funcionando; nenhum nível muda sem confirmação do
  físico; proposta de subida a RA/RMA alerta; com as barreiras declaradas
  em jan/2023, o perfil do 6EX reproduz o SEVRRA (61 RM, 68 RB).
  Depende de R-46, R-80 e das fachadas da GQ (R-39) e do Plano (R-33).
- fora: substituir o SEVRRA entregue à CNEN.

### R-74 — Questionário do físico para o módulo Documentação
- classe: robo
- estado: feita (23/10/2026)
- pilar: sistema global (spec Documentação, Open Questions)
- prepara: R-48
- pronto quando: `docs/planejamento/questionarios/documentacao.md` tem, para
  cada pergunta em aberto da R-48 (periodicidade do ASO, da autorização e do SEVRRA, datas de partida, origem da lista de IOEs), uma seção com a pergunta
  numa frase, as opções que a spec e a base levantam, cada uma com a fonte
  (`[CÓDIGO p. N]` conferido no texto da base, ou o AD/FR da spec), o que
  cada opção muda adiante e quais frentes a resposta destrava; uma linha
  `resposta do físico:` vazia no fim de cada seção; o cabeçalho diz
  "rascunho da IA: nada aqui é decisão". Pergunta sem fonte na base fica
  com "a base não responde" e nenhuma opção inventada.
- fora: escolher ou recomendar opção; escrever em `docs/qms/`, no memlog
  da spec ou no `riscos.md` (é da R-48, pelo físico).

### R-48 — Insumos do módulo Documentação
- classe: voce
- estado: pendente
- andamento (26/10/2026): respostas da R-74 levadas à spec e ao PRD (ASO 1 ano pela NR-7; autorização da CNEN e alvará separados; SEVRRA sem data; datas do documento de origem, JSON só confere; marca IOE no cadastro do núcleo, mantida pelo SPR). Sem base: `decisoes-sem-base.md` #18–21. Falta: linhas do módulo no `riscos.md`.
- pilar: sistema global (spec Documentação, Open Questions)
- pronto quando: linhas do `riscos.md` gravadas.
- fora: código.

### R-49 — Vencimentos, ASO, monitoração e painel
- classe: voce
- estado: pendente
- pilar: sistema global (spec Documentação, CAP-1 a CAP-5 e CAP-9; FR-33, FR-34)
- pronto quando: "sem data" nunca em dia; data sem documento recusada;
  evento faz vencer na hora (levantamento e ASO); ASO recusado no banco a
  perfil sem acesso; marca IOE no cadastro do núcleo, só o SPR altera; mês
  sem monitoração vira pendência; painel com prazos da GQ pela fachada;
  vencido com app fechado → `alta` na abertura. Depende de R-19, R-20,
  R-21, R-39.
- fora: instrumentos e aferição (GQ).

### R-50 — Migração do ppr-streamlit, tela e validação
- classe: voce
- estado: pendente
- pilar: sistema global (spec Documentação, CAP-6 a CAP-8; FR-35)
- pronto quando: JSON do PPR importado como conferência, com relatório
  item a item (casou, diverge, não importado; divergência → data mais
  cedo), sem gravação dupla depois do corte; UJ-4 em homologação com aceite da
  tela; relatório de validação assinado; `ppr-streamlit` marcado
  congelado no `REPOS.md` (AD-41). Depende de R-23, R-48, R-49.
- fora: o PPR vivo (R-85).

### R-84 — Inventário técnico dos equipamentos e seções do PPR da GQ
- classe: voce
- estado: pendente
- pilar: sistema global (spec GQ, CAP-16; PPR vivo, decidido em 28/10/2026)
- pronto quando: cada máquina emissora das três clínicas tem ficha técnica
  (energias com FFF, MLC, imagem, técnicas, filtros, fonte HDR, orto) com o
  documento de origem por campo; recurso sem teste no programa vira alerta
  e teste de recurso ausente é recusado; o Anexo H sai do programa
  versionado (CAP-1); capítulos de equipamentos, fontes, instrumentos e
  fantomas, monitores, programa de GQ e rejeitos expostos pela fachada.
  Depende de R-39.
- por que não é do robô: a ficha técnica sai do comissionamento e dos
  manuais, e cada campo é conferido pelo físico.
- fora: montagem do PPR (R-85).

### R-85 — PPR vivo: seções dos módulos e montagem do documento
- classe: voce
- estado: pendente
- andamento (28/10/2026, etapa 2): partes no banco — migração 0004
  (`ppr_parte`/`ppr_dado` em cada esquema de módulo), porta e fachadas em
  `adaptadores/postgres/ppr.py`, `tools/importar_ppr.py` gravando a semente
  das 3 clínicas; a aba lê por `ISOCENTRO_PG_APP` (provisória até a R-19) e
  mostra o texto vigente da linha num painel embaixo da tabela. Falta:
  gerador (etapa 3), emissão assinada, "PPR desatualizado".
- andamento (28/10/2026): esqueleto no app — módulo Documentação aberto na
  Torre com a aba PPR (`dominio/ppr.py` + `interface/documentacao_tela.py`):
  23 capítulos + Anexos com o módulo dono, todos "sem dado" até haver
  fachada; "Emitir PPR" apagado com o motivo.
- pilar: sistema global (spec Documentação, CAP-10 e CAP-11; Fundação
  CAP-25; Plano CAP-19; Segurança CAP-15; mapa em
  `docs/planejamento/sistema-global/ppr-vivo-mapa-2026-10-28.md`)
- pronto quando: cada módulo expõe as suas seções (dado vivo + texto
  versionado, só o dono altera), com a primeira versão do texto tirada do
  PPR vigente de cada clínica e citada; a Documentação monta o PPR só pelas
  fachadas, no leiaute do modelo do serviço; dado ausente sai "sem dado —
  <módulo>"; emissão assinada pelo SPR; mudança depois da emissão gera
  "PPR desatualizado" com a lista do que mudou; o PPR da CEL sai inteiro
  em homologação e é conferido capítulo a capítulo contra o de mai/2026.
  Depende de R-19, R-49, R-84.
- por que não é do robô: texto e leiaute do PPR são do SPR, e o documento
  vai à CNEN.
- fora: o `ppr-streamlit`, que fica como está até o corte.

### R-75 — Questionário do físico para o módulo Radioteraficha
- classe: robo
- estado: feita (23/10/2026)
- pilar: sistema global (spec Radioteraficha, Open Questions)
- prepara: R-51
- pronto quando: `docs/planejamento/questionarios/radioteraficha.md` tem, para
  cada pergunta em aberto da R-51 (classe G1, inventário de imobilizadores, notas por clínica, prazo do vínculo pendente, raízes do share), uma seção com a pergunta
  numa frase, as opções que a spec e a base levantam, cada uma com a fonte
  (`[CÓDIGO p. N]` conferido no texto da base, ou o AD/FR da spec), o que
  cada opção muda adiante e quais frentes a resposta destrava; uma linha
  `resposta do físico:` vazia no fim de cada seção; o cabeçalho diz
  "rascunho da IA: nada aqui é decisão". Pergunta sem fonte na base fica
  com "a base não responde" e nenhuma opção inventada.
- fora: escolher ou recomendar opção; escrever em `docs/qms/`, no memlog
  da spec ou no `riscos.md` (é da R-51, pelo físico).

### R-51 — Insumos do módulo Radioteraficha
- classe: voce
- estado: pendente
- andamento (26/10/2026): G1, inventário, notas, vínculo pendente e raízes da varredura levados à spec do módulo (commit 8e9e690); fora a G1, pela regra do físico, a conferir por ele; sem base em `decisoes-sem-base.md` #22–26. Falta: as linhas do módulo no `riscos.md` e o EXPERIENCE.md (cartão Tratamento abre a Virtual).
- pilar: sistema global (spec Radioteraficha, Open Questions)
- pronto quando: classe G1 do módulo decidida; origem do inventário real de
  imobilizadores e se ele e a biblioteca de notas são por clínica; prazo do
  vínculo pendente; raízes do share para a varredura; linhas do `riscos.md`
  (papel muda na migração, versão perdida, vínculo errado, correção que some)
  gravadas no memlog; EXPERIENCE.md atualizado (cartão Tratamento abre a
  Virtual; sai "envio ao Epimed", porque o ISOCENTRO é o canal interno ao
  NSP desde 26/10/2026; sai "PyQt5", alvo PySide6 pelo AD-36; epics.md P-6).
- fora: código.

### R-52 — PDFs de referência e comparação página a página
- classe: robo
- estado: estacionada (TCs_Teste é paciente real em `_restrito/`, fora do worktree; fonte congelada da capa e formato da referência são decisão sua — ver NOTAS.md)
- pilar: sistema global (spec Radioteraficha, CAP-3)
- pronto quando: PDFs de referência (ficha, capa, alta, imagens, DRR) gerados
  do código atual para `TCs_Teste` e `dicom-teste`, e um teste que compara
  página a página e reprova qualquer diferença; roda verde no código atual.
- fora: `papel/`, `interface/`.

### R-53 — Estado do módulo no PostgreSQL
- classe: voce
- estado: pendente
- pilar: sistema global (spec Radioteraficha, CAP-4 a CAP-10; AD-5, AD-26, AD-37)
- pronto quando: registro versionado, correções, cadastro SUS, simulação,
  notas, inventário, preferências, índice e históricos no banco, entidade por
  entidade, com relatório de migração conferido e sem gravação dupla; ficha
  regerada só do banco; correção que deixa de divergir fica no histórico;
  vínculo pendente liga pelo `PatientId`, sem prazo e sem ligação à mão;
  inventário por clínica com RLS, usos desconhecidos vazios com aviso, nunca
  0; modelos de notas globais e nota do paciente por clínica; banco fora →
  PDF sai, nada gravado; R-52 verde depois de cada corte. Depende de R-18,
  R-19, R-22, R-52.
- fora: telas, papel.

### R-54 — Encaixe Torre, recorte por perfil e retirada
- classe: voce
- estado: pendente
- pilar: sistema global (spec Radioteraficha, CAP-1, CAP-2, CAP-11)
- pronto quando: módulo com Capa, Fichinha, Total e Agenda no cabeçalho Torre,
  aceite da tela antes de editar; print antes/depois com a mesma árvore de
  widgets; `test_padrao_visual` sem exceção nova; recorte por perfil conferido
  no banco; Virtual pelo cartão Tratamento; checklist sem gravação após o
  corte; R-52 verde. Depende de R-23, R-32, R-34.
- fora: layout interno das telas, redesenho da Virtual.

### R-55 — Corte em produção e validação do módulo
- classe: clinica
- estado: pendente
- pilar: sistema global (spec Radioteraficha, CAP-10, CAP-12; FR-40)
- pronto quando: varredura única das `FICHA_*.json` nas três clínicas pela
  união das raízes (raiz das simulações, índice central, `historico_uso` e as
  que a TI apontar), inclusive dentro dos `ARQUIVOS_*.zip`, com relatório do
  que entrou, do que não entrou e da raiz de cada ficha; relatório de validação
  (PDFs, migração, vínculo pendente, banco fora, perfis) assinado pelo físico.
  Depende de R-17, R-51, R-53, R-54.
- fora: a Virtual e o checklist novo.

### R-56 — Versão fixa também para as dependências transitivas
- classe: robo
- estado: feita (21/10/2026)
- pilar: 4 (brainstorm de organização, 21/10/2026, P1/D1)
- pronto quando: um `constraints.txt` na raiz fixa, com versão exata, todos
  os pacotes do `.venv` que o `requirements.txt` puxa (medido em 21/10/2026:
  29 no `.venv` contra 10 diretos), gerado por um script em `tools/` que
  qualquer um roda de novo; o `testes.yml` instala com
  `-r requirements.txt -c constraints.txt` nos dois jobs; o comentário do
  topo do `requirements.txt` diz como atualizar os dois juntos; a suíte passa.
- fora: subir versão de qualquer pacote; `papel/`, `interface/`, `dominio/`.

### R-57 — Dado de paciente de desenvolvimento fora da árvore do repositório
- classe: voce
- estado: feita (21/10/2026)
- pilar: 4 (brainstorm de organização, 21/10/2026, P1/D2)
- por que não é do robô: muda onde o app grava `registro_fichas.json`,
  `correcoes_capa.json` e `notas_posicionamento.json`, e gravar no lugar
  errado é a quebra "com aparência de funcionamento" que o `raiz.py` descreve.
- pronto quando: fora do pacote, `raiz.pasta_do_app()` aceita uma variável
  `ISOCENTRO_PASTA_APP` e, sem ela, devolve o mesmo de hoje (teste prova os
  dois casos e que empacotado nada muda); nesta estação a variável aponta
  para `_restrito\estacao\` e os arquivos de execução com dado de paciente
  saem da raiz do repositório; a suíte passa com e sem a variável;
  `_restrito\LEIA-ME.md` e o README da pasta central dizem onde ficam agora.
- fora: o comportamento do executável; as junções de `TCs_Teste`,
  `espelho_capa` e `backup_registros` (frente própria, se o usuário quiser).

### R-58 — Camada `rt/`: dividir `dicom/` em modelo, leitura e desenho
- classe: voce
- estado: pendente
- pilar: 4 (espinha, AD-38; Update de 22/10/2026)
- por que não é do robô: `dicom_rt`, `dvh` e `cortes` alimentam a ficha e a
  capa; um import trocado que cai num valor padrão muda o papel sem erro.
- pronto quando: o que modela (geometria IEC 61217, cortes e DVH como
  números) está em `isocentro/rt/`, sem Qt, banco, rede, arquivo, cache,
  PIL nem matplotlib; leitura de arquivo, zip/rar e cache em disco vão para
  `adaptadores/dicom/` com `dicom_rede`, devolvendo `pydicom.Dataset`; o
  desenho vai para quem desenha; o sinal da mesa e o ângulo da série C vão
  para o Radioteraficha; listas de equipe e `identificar_maquina` saem de
  `rt/` (ficam em `dados/` até o AD-26 existir); cada caso de limite (SSD,
  `dose3d`, `dvh`) decidido com o físico; nenhum módulo de compatibilidade
  fica para trás; as fichas do TC8 e do Elekta saem idênticas pelo
  `tools/comparar_pdf.py`; a regra de `rt/` do R-24 acende; suíte verde e
  ordem aleatória.
- fora: `papel/`, `dominio/`; mudar qualquer cálculo; trocar o casamento por
  substring da máquina (frente própria, junto do AD-26).

### R-59 — Raio de revisão a partir do diff
- classe: robo
- estado: feita (23/10/2026)
- pilar: 4 (espinha, AD-39)
- pronto quando: `tools/raio.py [ref]` lê o diff e diz, para cada arquivo,
  o módulo dono e o raio (o módulo; o módulo e os consumidores da fachada;
  tudo), usando a tabela de destino da semente enquanto os pacotes atuais
  existirem; o raio só soma: SQL, dependência fixada, tabela de máquina e
  arquivo sem dono dão "tudo", e o que alcança `papel/` acrescenta
  "comparar PDF e avisar"; o `tools/testar.py` aceita o raio como recorte
  durante o trabalho, sem substituir a suíte no fechamento; testes cobrem
  os casos; `docs/AMBIENTE.md` ganha a linha da ferramenta.
- fora: nota de versão automática; mover qualquer arquivo.

### R-60 — `MANIFESTO` e raiz de composição única
- classe: voce
- estado: pendente
- pilar: sistema global (espinha, AD-40; spec Fundação, CAP-24)
- pronto quando: o núcleo define o tipo `Manifesto` (dado puro); a
  `isocentro/composicao.py` lista os módulos; o Radioteraficha é o primeiro
  com manifesto e tela registrada; o shell monta os cartões da Torre só a
  partir da lista; app e concentradora usam a mesma lista; a regra de
  manifesto do R-24 acende. Depende de R-18, R-20 e R-23.
- fora: manifesto dos módulos ainda não construídos; capacidades por clínica.

### R-76 — Contrato ESAPI: esquema v1 e validação, sem inventário
- classe: robo
- estado: feita (23/10/2026)
- pilar: 3 (espinha, AD-15; spec Fundação, CAP-9)
- metade de: R-61 (o inventário fica lá)
- pronto quando: `adaptadores/esapi_json/` tem o esquema v1 (versão do
  esquema, id e versão do script, hash da DLL, versão do plano) e a
  validação dele, pura, sem banco; testes provam: versão de esquema
  desconhecida → `erro` com motivo, hash inválido → `erro`, versão do plano
  diferente → `indeterminado`, script ausente do inventário ou não validado
  → `indeterminado` (o inventário entra como parâmetro, vazio nos testes,
  nunca preenchido pela sessão); o README do `scriptsvarian` não muda.
- fora: o inventário real; gravar no banco; o `classificacao-62304.md` e o
  `riscos.md`; código C#.

### R-61 — Contrato ESAPI: esquema versionado e inventário dos scripts
- classe: voce
- estado: pendente
- pilar: 3 (espinha, AD-15 e AD-41)
- por que não é do robô: o inventário diz quais scripts escrevem no Eclipse
  e em que estado de validação estão; só quem os publicou sabe.
- depende de: R-76 (esquema v1 e validação)
- pronto quando: os scripts que escrevem no Eclipse têm linha no
  `classificacao-62304.md` e no `riscos.md` para o físico preencher; o README do
  `scriptsvarian` aponta para o esquema e diz qual versão cada avaliador
  grava; o inventário (script, versão instalada, escreve no Eclipse sim/não,
  validação em ambiente não clínico) existe como dado do futuro
  `modulos/software`. Nenhum script gravável entra como validado antes de o
  critério de validação sair do "Em aberto" do `escopo.md`.
- fora: tela do módulo Software; executar script a partir do ISOCENTRO.

### R-63 — Aceite do AD-42: o que a IA pode fazer no ISOCENTRO
- classe: voce
- estado: pendente
- andamento (26/10/2026): AD-42 aceito como está; RI-1 (viés de automação)
  e RI-2 (troca do modelo) no `riscos.md`, efeito e S/O/D em branco;
  política em rascunho em
  `docs/planejamento/sistema-global/politica-llm-rascunho-2026-10-26.md`.
  Falta: o físico preencher RI-1/RI-2 e definir a política em `docs/qms/`.
- pilar: sistema global (espinha, AD-42; `analise-ia-2026-10-22.md`)
- por que não é do robô: é política de QMS. Escrita pela IA e lida como
  fato, viraria decisão que ninguém tomou (a mesma razão da R-14).
- pronto quando: o físico aceita ou edita o AD-42 e tira o `[PROPOSTA]`; o
  `riscos.md` tem as linhas "viés de automação" e "troca do modelo (SOUP)",
  preenchidas pelo físico; a política de uso de LLM no serviço (dado de
  paciente, revisão humana, treinamento; NORRIS-2025) existe em `docs/qms/`,
  escrita pelo físico.
- fora: código. As R-64 a R-68 esperam esta.

### R-64 — "Pergunte à base": resposta só com citação conferida por máquina
- classe: voce
- estado: pendente
- pilar: sistema global (`modulos/conhecimento`; AD-42; proposta 2)
- depende de: R-63
- por que não é do robô: escolher o modelo e onde ele roda é decisão do
  usuário; a base mora no repositório `isocentro-conhecimento`.
- pronto quando: a recuperação usa o texto extraído do `conhecimento/`; a
  resposta só sai com citação `[CÓDIGO p. N]` cujo trecho existe no texto
  daquela página (conferência por texto normalizado, não pelo modelo); sem
  citação conferida, a tela diz "a base não responde isso"; o conjunto de
  avaliação é gerado das fichas (norma, tolerância, página), com pelo menos
  200 perguntas, e mede acerto, recusa e citação falsa; modelo e versão
  fixados. Texto de norma não é dado de paciente: pode usar serviço externo
  (AD-42, item 4).
- fora: perguntas sobre caso ou paciente; responder sem fonte.

### R-65 — Pareto de máquina parada a partir do texto livre
- classe: clinica
- estado: pendente
- pilar: 2 e indicadores (proposta 3; UChicago, AAPM 2026)
- por que não é do robô: a fonte do texto das paradas não está decidida. Em
  29/09 a atividade de parada no ARIA "ainda vai ser CRIADA"
  (`notas/2026-09.md`), e o registro da engenharia clínica é dado da clínica.
- pronto quando (parte da clínica): a fonte do registro de parada está
  decidida, e existe uma amostra sem nome de funcionário. Depois, frente
  `voce`: classificação por causa com o trecho de origem, Pareto por máquina
  junto do Índice de Disponibilidade, conferido contra a classificação de uma
  pessoa numa amostra.
- fora: dado de paciente; prever falha.

### R-66 — Texto livre contra campo estruturado: a nota que contradiz o plano
- classe: clinica
- estado: pendente
- pilar: 3 (proposta 4)
- por que não é do robô: o modelo local precisa de máquina na rede do
  serviço (AD-7, AD-42), e o hardware é conversa com a TI.
- pronto quando (parte da clínica): há máquina na rede que roda um modelo
  aberto, com RAM, CPU ou GPU e tempo por nota medidos. Depois, frente
  `voce`: **primeiro as regras determinísticas** (DIBH na nota e plano sem
  gating, como no TC7; bolus na nota e plano sem bolus; lateralidade), e o
  modelo só onde a regra não alcança. Conjunto de avaliação sintético com a
  contradição conhecida, sensibilidade e especificidade medidas, alerta com
  o trecho, nunca corrige campo.
- fora: mudar o papel; preencher campo.

### R-67 — Plano anômalo explicável sobre a base histórica
- classe: voce
- estado: pendente
- pilar: 3 (proposta 5; FAN-2026, HUANG-2023)
- depende de: R-10, R-63
- por que não é do robô: muda o `dominio/` e chega à revisão do plano.
- pronto quando: estatística robusta por sítio (mediana e MAD por
  parâmetro: MU/Gy, número de campos, energia, índices da CQ Plano), e a tela
  mostra o parâmetro que provocou o alerta e o valor dele; aprendizado
  profundo só se a estatística, medida, não bastar; nenhum veredito
  enquanto `qualidade.CALIBRADO` for falso.
- fora: reprovar plano.

### R-68 — Rascunho estruturado de incidente, cada campo com a origem
- classe: voce
- estado: pendente
- pilar: sistema global (`modulos/seguranca`; spec de incidentes; proposta 6)
- depende de: R-63 e o módulo de incidentes
- por que não é do robô: classificação de incidente é decisão do comitê.
- pronto quando: o modelo local propõe os campos HFACS (AI-ILS, IJROBP) a
  partir do relato, cada um com o trecho de origem; a pessoa confirma campo a
  campo; o conjunto de avaliação usa os relatórios públicos da pasta 11 e
  incidentes sintéticos; alucinação medida (WANG-2026: 11% a 61%).
- fora: causa raiz e ações escritas pelo modelo.

### R-69 — pillow e pypdf sem vulnerabilidade conhecida
- classe: voce
- estado: feita (22/10/2026: pillow 13.0.0, pypdf 6.21.2; 4 casos com 0 pixel diferente)
- pilar: 4 (achado do `pip-audit` de 22/10/2026: 49 no pillow 12.2.0, 30 no
  pypdf 6.13.1)
- por que não é do robô: o pillow desenha imagem que vai para o papel.
- pronto quando: as duas em versão sem vulnerabilidade conhecida; o
  `constraints.txt` regenerado; a regressão do papel e o
  `tools/comparar_pdf.py` dão os 4 casos idênticos; o `pip-audit` limpo
  nessas duas; suíte verde e ordem aleatória.
- fora: as outras dependências.

### R-70 — Notas da capa em várias linhas na tela
- classe: voce
- estado: feita (22/10/2026)
- pilar: 1 (sobra da seção "Prescrição manda na ficha", 23/09; decidido pelo
  usuário em 22/10/2026: vira multilinha)
- por que não é do robô: muda a tela da Capa (`interface/`), e layout se
  descreve antes de editar.
- pronto quando: o campo Notas da capa (`capa._novo_bloco`, hoje
  `QLineEdit`) aceita e mostra quebras de linha; o que se edita na tela
  volta ao PDF com as mesmas quebras (`capa_pdf._linhas` já imprime várias);
  o limite de 1024 caracteres da coluna é respeitado e anunciado; layout
  aceito antes de editar; `tools/tela.py` dia e noite; regressão do papel
  idêntica nos casos sem nota.
- fora: mudar o PDF da capa.

---

## Esperando você

O robô escreve aqui o que estacionou e por quê, uma linha por frente, no topo.
Linha respondida sai daqui, e a frente volta a `pendente`.

- 23/10 — **R-52**: (1) onde mora a referência dos `TCs_Teste` (paciente real, `_restrito/`, fora do git e do worktree) e quem a grava; (2) que fonte da capa congelar, já que o banco não responde daqui; (3) pixel com data fixada no gerador, e PDF no git ou só o hash de cada página. Detalhe no `NOTAS.md`.
