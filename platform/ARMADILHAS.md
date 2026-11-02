# Armadilhas deste repositório

O que já custou tempo aqui, e por quê. Saiu do `NOTAS.md` em 08/09/2026: é a parte
mais consultada do registro e a que menos podia envelhecer no meio de 7 mil
linhas de histórico. **Arquivo permanente** — nada aqui é arquivado por data;
uma entrada só sai quando deixa de ser verdade, e aí sai dizendo por quê.

A mesma lista, resumida, está no `CLAUDE.md`, que entra em **cada** requisição
da sessão — por isso lá é resumo. Quando as duas divergirem, **esta** é a
completa. Nasceu com 6 entradas (as que estavam no `NOTAS.md`) e no mesmo dia
recebeu as que só existiam no `CLAUDE.md`: o cabeçalho afirmava ser a completa
antes de ser, que é a mesma família de registro vencido que este arquivo existe
para evitar.

---


- **Gancho que roda ferramenta que roda o gancho é recursão — e o
  tempo-limite NÃO a para no Windows.** Em 28–29/10/2026 o `abertura.py` rodava
  a `tools/manutencao.py` (semana vencida), que testa os ganchos RODANDO cada
  um, inclusive o `abertura.py`; este via a semana ainda vencida (a marca só é
  gravada no fim) e rodava a manutenção de novo. O `subprocess.run(timeout=)`
  mata o filho direto e deixa os netos vivos: chegou a 80 processos Python,
  derrubou uma suíte (18:03, sem resumo) e travou outra por 1h40 numa fileira
  de `E`. Corte: a manutenção passa `ISOCENTRO_GANCHO_SEM_EFEITO=1` aos
  ganchos que testa, e com ela o `abertura.py` não muda nada nem abre
  processo. Sintoma para
  reconhecer: suíte "demorando" e processos `abertura.py`/`manutencao.py` com
  hora de criação de agora, um a cada meio segundo. Desde 29/10 há mais duas
  travas: a manutenção é de instância única (trava do sistema em
  `.claude/estado/manutencao.trava`, solta sozinha se o processo morre) e o
  `abertura.py` a dispara em SEGUNDO PLANO — esperando por ela (20 s) ela
  nunca terminava, a marca da semana nunca era gravada e toda sessão a
  disparava de novo, que é por que o problema voltava.

- **`psycopg.connect` sem `connect_timeout` fica pendurado PARA SEMPRE no
  Windows quando o servidor está fora** — não dá "connection refused", não
  volta. Medido em 29/10/2026 depois de a máquina reiniciar (o PostgreSQL de
  dev não sobe sozinho): a suíte parou no primeiro teste de banco por 1h40.
  Toda conexão leva `connect_timeout` (o app 3 s, as ferramentas 5 s), e o
  `tests/pg_teste.py` sonda uma vez e faz cada teste de banco FALHAR na hora
  dizendo para subir o servidor. Conexão nova sem tempo-limite é este bug de
  volta. E o servidor subido por código vai com `CREATE_NO_WINDOW` (console
  próprio, invisível), **nunca** `DETACHED_PROCESS`: destacado, ele caiu com
  o Ctrl+C de outro console (`0xC000013A` no `dev.log`) no meio da suíte.

- **O `variandw` é CASE-SENSITIVE, e um `LIKE` com a caixa errada devolve a
  lista errada CALADA.** Medido em 22/09/2026, procurando as atividades de alta
  no catálogo do ARIA: `--palavra alta` voltou com "Malta", "Kaltag", "Gibraltar"
  e "Asma/Falta de Ar" — todas com `alta` minúsculo no miolo — e **não** voltou
  com "Alta Pronta CEL", "Alta de Tratamento" nem "Relatorios de Alta", que
  estavam na mesma tabela. O relatório não diz "não achei": ele diz "achei
  quatro", e as quatro parecem resposta. O `atividades_db.PALAVRA` ("ocumenta")
  escapa por acidente feliz, porque começa no miolo minúsculo de "Documentação".
  Ao escrever a próxima busca, escolher o pedaço com a **caixa certa** — ou
  procurar as duas ("Alta" e "alta").

- **`GetTaskOwnerName` em `JOIN` INNER apaga a atividade que não tem
  responsável — e apaga em silêncio.** Medido em 23/09/2026, com o quadro de
  Altas vazio e o usuário vendo 12 "Imprimir Alta CEL" disponíveis no ARIA: na
  janela de 180 dias eram **720** linhas exigindo dono contra **2.732** sem
  exigir (74% comidas), e com o filtro real aplicado sobravam **zero** com dono
  contra **quinze** sem. Nem toda atividade do care path tem
  `ActivityOwnerFlag = 1`. Antes de culpar o filtro de estado ou o de
  predecessora, comparar os dois números — é o degrau "SEM exigir dono" do
  `porque_vazio`.

- **No ARIA deste serviço, o `ActivityCode` NÃO diz de que unidade é a
  atividade — o `ActivityNamePTB` diz.** Descoberto em 22/09/2026, montando o
  quadro de Altas Prontas: o código de **CEL termina em `UNI`**, o de **BET não
  tem sufixo nenhum** (`Verificar Programação` seco), e o mesmo vale para as
  outras três famílias da categoria ("Alta Pronta UNI"→CEL, "Altas Prontas
  BUE"→BET, "Imprimir Alta UNI"→CEL). É a nomenclatura ANTIGA das unidades
  sobrevivendo no código enquanto o nome em português acompanhou a atual.
  **Filtrar pelo código, exibir pelo nome.** Ler a unidade do código não dá
  erro: dá "UNI" na tela para um paciente do CEL, e nada para todo o BET.

- **A amostra do `tools/atividades.py` são os 40 PRIMEIROS valores em ordem
  alfabética, não os 40 mais representativos.** No mesmo relatório, os valores
  de `ActivityCode` do `DWH.DimActivity` (1.577 linhas) param em "ANA 3D
  Particular Pago": tudo de "B" em diante ficou invisível. Ler aquela lista como
  "o catálogo" é concluir que a atividade não existe porque o alfabeto acabou
  antes dela. Para procurar algo específico, é o passo 4 (`--palavra`) ou o
  `--consulta`, que filtram no servidor em vez de cortar no `TOP 40`.

- **Suíte com saída para arquivo pelo Git Bash: 5 erros falsos sem
  `PYTHONUTF8=1`.** O stdout redirecionado cai em cp1252, e o
  `tools/sondar_dicom.py` morre ao imprimir `→` (`UnicodeEncodeError:
  'charmap'`): 4 erros no `test_sondar_dicom.SemConfiguracao`, mais o
  `test_robo.TestTrava.test_gancho_de_verdade` (JSON `None`). Nada a ver com o
  código da frente — medido em 17/09/2026, falha igual na árvore limpa e passa
  com `PYTHONUTF8=1`. Rodar a suíte assim: `PYTHONUTF8=1 .venv/Scripts/python.exe
  -m unittest discover -s tests > arquivo`.

- **19 arquivos do app são CRLF, e só um tem BOM.** Substituição multilinha
  escrita com `\n` não casa **nenhum** dos 19: devolve zero ocorrências, e sem
  `assert` a edição "passa" sem ter mudado nada. **Sempre usar `assert` na
  substituição** — duas edições falharam em silêncio por não ter, e o teste só
  pegou uma.
  Esta entrada dizia só "`posicionamento.py` tem BOM e CRLF" até 09/09/2026,
  quando a mudança para o pacote `isocentro/` mediu o resto: o
  `posicionamento.py` é o único com **BOM**, mas `capa_pdf`, `ficha_pdf`,
  `capa_db`, `capa_dados`, `tratamento_db`, `agendamento_tela` e mais treze são
  CRLF. A nota parecia certa, e é por isso que ninguém a questionava — esse é o
  sintoma do registro vencido, não a exceção.
  O que funciona é **detectar por arquivo**, não normalizar:
  `eol = "\r\n" if "\r\n" in texto else "\n"`, e aplicar `velho.replace("\n", eol)`
  antes de procurar. Normalizar e regravar reescreveria as 1.172 linhas de um
  arquivo para trocar duas, e o diff esconderia a mudança real.
  **E o script vai por arquivo, nunca por heredoc**: no heredoc o `\n` do texto
  procurado chega ao Python como quebra de linha, e a busca não casa nada.
- **`setSpecialValueText("")` não funciona**: o Qt entende string vazia como
  "não há texto especial". Precisa de um espaço.
- **`setCurrentText("")` em combo não editável não faz nada** — o valor anterior
  fica. Vazio é `setCurrentIndex(-1)`.
- **`estilo.pintar` registra um ouvinte por chamada.** Em método que roda a cada
  mudança de estado, registrar uma vez e reaplicar a folha à mão.
- **`Controle*` sem dono, sem sinal.** Um objeto de controle (`ControleAgenda`
  e semelhantes) NÃO é `QObject` — é classe Python pura só com métodos
  conectados a sinais do painel. Sem uma variável que o segure, o Python o
  recolhe assim que a expressão termina, e a conexão do sinal PARA DE CHAMAR
  NADA, sem erro nenhum: `controle_agenda.ControleAgenda(painel, usuario)`
  solto (sem `controle = ...`) faz o teste que depende do sinal falhar com uma
  lista vazia, calado — achado em 23/09/2026, num teste do modo "Só os meus"
  da Agenda. Em produção o `gui.py` já guarda em `self.controle_agenda`, então
  o bug só mora em teste; mesmo assim, sempre atribuir o retorno a uma
  variável (mesmo `_ = ...`) quando o teste depende de um sinal chegar.
- **`processEvents()` não entrega `DeferredDelete`.** Para destruir widget em
  teste: `sendPostedEvents(None, QEvent.DeferredDelete)`.
- **Ordem dos testes importa**: `test_capa_tela` antes de `test_capa` quebra 16
  testes (vazamento de estado global da pasta de relatórios). O `discover`
  alfabético esconde.
- **Usar `assert` em toda substituição por script.** Duas edições falharam em
  silêncio por não ter — e o teste só pegou uma delas.
- **Script com barra invertida NÃO vai por heredoc, vai por arquivo.** Nem por
  stdin (`python - <<'PY'` come uma camada de escape: `\t` chega como tabulação
  real e estraga a f-string), nem por `cat > x.py <<'PY'` (arquivo de 230 linhas
  morreu no meio, com `unexpected EOF`). Escrever o arquivo direto e só então
  rodá-lo. Em 08/09/2026 as duas formas falharam na mesma tarde, e uma delas
  quebrou um gancho que não está no git — sem `git checkout` para desfazer.
- **Nunca `del modulo.funcao` em teste.** `modulo.f = falsa` grava no `__dict__`
  do módulo; o `del` depois some com a ORIGINAL para o resto do processo. Um
  `del capa_db.conexao` já quebrou 16 casos — e só na ordem alfabética, que é a
  do `discover`. Guardar e devolver no `tearDown`.
- **Zerar `ISOCENTRO_DB_SERVIDOR` não desliga o banco.** Sem a variável, o
  `capa_db._config` cai no `config_servico.json`, que nesta estação aponta o
  SRVINSIGHT: `configurado()` continua verdadeiro e o teste vai à rede (medido:
  sai a recusa de SSPI) — ou passa de carona em outro arquivo que redirecionou a
  pasta antes dele. Isolar apontando `ISOCENTRO_CONFIG` para uma pasta vazia. Já
  cobrou seis vezes; a última foi o `test_capa_espelho`, em 08/09/2026.
  **Desde 09/09/2026 há uma QUARTA porta**: o `capa_db` passou a ler pelo
  `ambiente.ler`, então `ISOCENTRO_DB_SERVIDOR` também aponta o banco —
  e, com precedência sobre o antigo, ele vence até o
  `os.environ[ENV_SERVIDOR] = "SERVIDOR-DE-TESTE"` que o `setUp` acabou de
  gravar. Tirar os DOIS nomes (`ambiente.nome_novo(...)`), tanto para desligar
  quanto para fixar.
- **`estilo.pintar` em teste é cumulativo e caro.** O `unittest` segura as
  instâncias de `TestCase` até o fim da suíte, elas seguram a janela, nenhum
  widget morre — então `estilo._varrer()` não tem o que varrer e a lista de
  ouvintes só cresce. Arquivo de teste que monta tela precisa da linha
  `from tests.limpeza_de_tela import load_tests`; sem ela a suíte volta a levar
  9 minutos em vez de 2,5.
- **Reordenar lista de exibição quebra quem indexa por posição.** A tabela de
  edição de feixes rotulava `Campo {i+1}`; com a ordem do gantry, a 4ª linha
  deixou de ser o "Campo 4" impresso — e o papel é o que vai para a sala.
- **Item MARCÁVEL de lista (`ItemIsUserCheckable`) tem indicador PRÓPRIO no
  QSS — `QCheckBox::indicator` não cobre.** `QAbstractItemView::indicator` é o
  seletor certo; sem ele, o item DESMARCADO cai no tema nativo do Windows
  (claro) e arrasta um retângulo de fundo BRANCO cobrindo a linha inteira —
  mesmo com a paleta escura aplicada em tudo mais. Achado em 24/09/2026, num
  print real da lista de estruturas do DVH (`lst_estruturas`): só as linhas
  DESMARCADAS ficavam brancas, as marcadas (ícone customizado) não. Vale para
  toda lista com `ItemIsUserCheckable` — `capa`, `controle_viewer`,
  `posicionamento`, `tratamento`, `visualizador` — e a regra é global, em
  `aparencia._ESTILO()`.
- **`QT_QPA_PLATFORM=offscreen` não desenha TEXTO.** O `grab()` sai com as caixas
  e as cores certas e todos os rótulos vazios: parece bug de layout e não é. Para
  conferir tela, gravar `QT_QPA_PLATFORM=windows` (gravar, não `setdefault` — o
  `tools/caso.py` já põe offscreen ao ser importado) e chamar `grab()` no widget
  **sem** `show()`, para não abrir janela na cara de quem está usando a máquina.
  Desde 08/09/2026 quem faz isso é o **`tools/tela.py`**, e ele confere a
  plataforma MEDIDA (`app.platformName()`), não a pedida: a variável pode ter
  sido gravada depois de o `QApplication` nascer, e aí não vale nada.
- **E a fonte de fallback do `offscreen` também MEDE diferente, não só deixa de
  desenhar** (achado em 23/09/2026, na Agenda): sem plataforma nativa, o Qt cai
  para "Helvetica" — no Windows real (`windows`), a família é "MS Shell Dlg 2".
  A mesma frase mediu **194px** em `windows` e **407px** em `offscreen`, mais
  que o DOBRO. Um teste que calcula `QFontMetrics.elidedText(...)` contra uma
  largura fixa e roda só em `offscreen` (a suíte inteira) corta texto que sobra
  de largura na tela real — e um teste que confia nisso reprova por medo de
  bug que não existe. Testar a LÓGICA de corte (`_elidir` com uma largura
  generosa ou curta de propósito) e conferir a largura REAL só com
  `tools/tela.py` contra `windows`.
- **`JanelaPrincipal(...)` derruba o processo sem `setStyleSheet` antes.** Exit
  127, nenhum traceback. A sequência que funciona é a do `tools/caso.py` e a do
  `tools/tela.py`: `QApplication` → `gui.aplicar_modo(...)` →
  `app.setStyleSheet(gui._ESTILO())` → só então construir a janela.
- **`aplicar_modo` GRAVA o modo nas preferências da estação** (QSettings
  `modo_cor`) e **devolve o modo NOVO, não o antigo**. Ferramenta que troca para
  dia e "restaura" com o retorno dela não restaura nada — deixa o app do usuário
  no claro na abertura seguinte. O anterior vem do `estilo.modo()`, perguntado
  antes da troca, e a devolução vai num `finally`.
- **Mexer em `os.environ` no import de um módulo de `tools/` estraga a suíte.**
  Um teste que importe o módulo herda a mudança, e o estrago aparece em OUTRO
  arquivo, na ordem alfabética do `discover` — mesma família do `test_capa_tela`
  antes do `test_capa`. Se a troca precisa acontecer antes de algum import (a
  plataforma do Qt, por exemplo), ela mora numa função chamada pelo `main`, que
  já roda antes de tudo neste processo.
- **`| tail` numa suíte perde o veredito.** O `unittest` relata em stderr (sai na
  hora) e os `print` dos testes vão em stdout (bufferizado até o fim do
  processo): o resumo cai no meio, o `tail` corta, e o código de saída que sobra
  é o do `tail` — uma rodada de 08/09/2026 pareceu ter passado sem prova nenhuma.
  Gravar em arquivo e filtrar depois.
- **Caminho estilo Git Bash (`/c/Users/…`) não existe para o Python no Windows.**
  O gancho de checagem descartou um arquivo em silêncio e pareceu quebrado; era o
  `is_file()` dizendo a verdade sobre um caminho que não existe.
- **No C-MOVE, os arquivos NÃO voltam pela conexão que pediu.** O servidor abre
  uma conexão NOVA para o AE de destino cadastrado nele, então esta ponta
  precisa estar ouvindo. Sem receptor de pé o pedido é ACEITO, o servidor tenta
  conectar de volta e a resposta chega **21 s depois** como `0 objeto(s), 1
  falha` — sem traceback, sem erro na tela. E esse resumo é indistinguível do
  de destino não cadastrado, que é outro defeito, resolvido por outra pessoa
  (aquele, sim, falha na hora, com `Move destination unknown`). Em 10/09/2026 a
  causa era o firewall desta estação: duas regras de ENTRADA com ação
  **Bloquear** para `python.exe`, no perfil Público. No Windows **regra de
  bloqueio vence regra de permissão**, então abrir a porta pode não bastar.
- **A subassociação do C-MOVE usa os contextos PEDIDOS, não os suportados.**
  Quem age como Move SCP monta a conexão com o destino por
  `self.ae.associate(...)` (`pynetdicom/service_class.py`), e essa chamada leva
  os `add_requested_context` do AE. Só `add_supported_context` das classes de
  storage e o servidor associa com o receptor sem ter em que contexto mandar —
  o `scp_falso` passou por isso ao aprender C-MOVE.
- **A RTDOSE não é referenciada pelo plano: a seta aponta ao contrário.** Do
  RTDOSE para o RTPLAN, por `ReferencedRTPlanSequence`. Não há como segui-la
  para baixo a partir do plano, então a busca é **por estudo** — e o estudo
  devolve as doses de TODOS os planos dele. Aceitar o que veio é a ficha
  calculada sobre a dose do plano vizinho: os números saem, plausíveis, e não
  há sintoma nenhum. O filtro é depois que o objeto chega, e só descarta o que
  tem certeza — dose sem referência (composição de curso) e dose ilegível
  ficam.
- **Duas sessões no mesmo checkout dividem o índice do git.** Em 15/09/2026 a
  frente do robô e a do `_tcp_aberta` rodaram em paralelo na `v7`. Uma
  preparou os arquivos dela com `git add`; a outra fez `git add` dos seus e
  `update-index` de uma versão parcial do `NOTAS.md` — por cima da entrada que a
  primeira tinha preparado. O commit seguinte da primeira (`7c2baef`, já com
  push) levou o código das DUAS frentes e deixou a própria seção do `NOTAS.md`
  de fora, só no disco. Nenhum erro: o `git status` de cada uma parecia certo
  para ela. Frente paralela vai para **worktree separado** (é o que o robô usa);
  e no mesmo checkout, commit parcial é por índice temporário
  (`GIT_INDEX_FILE`), nunca pelo índice de todos.
- **Conferência desenhada com UM `processEvents()` fotografa o layout no meio
  do caminho.** Em 23/09/2026, medindo a Documentação da Fichinha, as colunas
  "paravam" em 465 px de uma linha de 698, com 233 px vazios no fim e o nome do
  paciente cortado — o retrato exato de um layout ignorando os pesos. Não era:
  o `QListWidget` só alarga o widget da linha **depois** do último evento
  processado, e o script capturava o estado intermediário. Com o laço de
  eventos rodando — que é o caso do app — a mesma linha preenchia 690 de 693 e
  os pesos já valiam. Foram escritos TRÊS consertos para o defeito inexistente
  (`resizeEvent`/`showEvent` reativando o layout, `sizeHint` constante no
  rótulo elidido) e nenhum mudou nada, que era o próprio sinal: **"o conserto
  não mudou nada" quer dizer que a MEDIDA está errada**, não que falta um
  conserto maior. Antes do `grab()`, vários `processEvents()` — e desconfiar de
  qualquer geometria que só o script vê.
