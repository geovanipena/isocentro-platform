# O ambiente de trabalho: ferramentas, ganchos e configuração

Este arquivo é a **metade sob demanda** do `CLAUDE.md`. Lá ficam os gatilhos —
o nome da ferramenta e quando usá-la, que é o que precisa estar na cabeça de
quem trabalha; aqui fica o detalhe de cada uma, que só interessa na hora de
usá-la.

**Por que a separação, em 08/09/2026:** o `CLAUDE.md` entra em **toda**
requisição da sessão. Medido naquele dia, ele custava ~5.400 tokens por turno,
e um terço disso era detalhe de consulta — a tabela de variáveis de ambiente é
útil talvez numa sessão em dez, e mesmo assim era paga em todas. É a mesma
cirurgia que as ferramentas de clínica receberam no mesmo dia (`tools/LEIAME_CLINICA.md`,
carregado pela skill `/clinica`), pelo mesmo motivo e com o mesmo resultado.

**E por que rastreado pelo git:** parte do que está aqui descreve o `.claude/`,
que é configuração de estação e está no `.gitignore`. Se esta informação
morasse lá dentro, uma reinstalação a levaria junto. Aqui ela sobrevive.

---

## A história das regras do `CLAUDE.md`

Em 15/09/2026 o `CLAUDE.md` perdeu os casos que contavam de onde cada regra
veio — a regra ficou, o caso veio para cá, **sem resumo**. Ele entra em toda
requisição e em toda sessão do robô; o caso só interessa a quem for questionar
a regra, e é para esse leitor que ele está guardado.

**Os três arquivos de nota.** São três arquivos desde 08/09/2026, porque um só
tinha chegado a 7.873 linhas e 409 KB — e nota que ninguém lê inteira é nota
que envelhece sem ser questionada, que é exatamente como nasceram os quatro
registros vencidos daquele dia.

**Voltar na seção que abriu a pendência.** Em 27/08/2026 havia três "EM
ABERTO" vencidos, e uma delas — a reconexão ao banco, marcada "e é sério" —
estava resolvida havia dias. Mesma família do `_LOGGERS_APP`: o sintoma de um
registro vencido é que ele parece certo.

**A conta do contexto, antes do cache.** O texto até 15/09/2026 dizia: "Cada
turno reenvia o contexto inteiro. Abrir o `gui.py` (5,6 mil linhas, ~60 mil
tokens) no quinto turno não custa 60 mil: custa 60 mil **vezes todos os turnos
que vierem depois**. Em 08/09/2026 uma manhã rendeu pouco e gastou muito, e as
duas coisas tinham a mesma causa — contexto inflado, não falta de trabalho." E
a regra era "**Uma frente por sessão.** Quando a frente fecha e a suíte passa:
checkpoint, commit, `/clear`. Retomar de um checkpoint bom custa uns 3 mil
tokens; arrastar a sessão custa o contexto inteiro **a cada turno**." A
manhã de 08/09 continua sendo o caso certo — contexto inflado pesa, e pesa
também na atenção. O que estava errado era a aritmética: com cache, o
reenvio do que não mudou custa ~0,1×, e a sessão nova paga a GRAVAÇÃO do
contexto de partida (51 mil tokens a 2×, medido em 15/09/2026). O "uns 3 mil
tokens" do checkpoint era só o checkpoint, sem o resto do que a sessão nova
carrega. Daí o gatilho do `/clear` ter virado pausa / assunto novo / contexto
grande.

**O tempo da suíte.** Eram 9,5 min até a limpeza de `estilo._ouvintes` (27/08,
ver `tests/limpeza_de_tela.py`), 1,9 depois dela, e 4,6 em 14/09 — e a volta
**não** foi o tamanho da suíte: eram DOIS testes esperando o que não precisavam
esperar (o prazo do aperto de mão DICOM e uma varredura de disco por nome), 30%
do total em dois casos. Depois deles vieram mais CINCO, e os 3,2 min viraram
2,7: todos esperavam tempo-limite de REDE contra um servidor de mentira,
**33 s**, e o remédio não foi otimizar nada — foi o teste parar de ir à rede
perguntar o que ele mesmo acabara de fingir. O número envelheceu calado por
duas semanas.

**A ordem aleatória.** Era "de vez em quando" enquanto custava 9 minutos; hoje
custa o mesmo que a suíte (161 s em 14/09/2026), e não há mais motivo para
pular. Das três vezes que o `discover` alfabético escondeu um teste dependente,
uma era um `del capa_db.conexao` que apagava a função do módulo para o resto do
processo — a MESMA função que os testes da capa trocam para não ir à rede, e é
por isso que toda troca dela guarda e devolve.

**A doc da Varian antes da chamada.** Em 03/09/2026 o `External beam
configuration not found` foi depurado por palpite, com duas idas ao Eclipse do
serviço, e a resposta estava escrita na página do
`ExternalBeamMachineParameters`.

**O `varrer_identidade` antes do commit.** Em 31/08/2026 havia 13 registros
reais versionados, e tirá-los custou fechar o repositório e reescrever o
histórico — o que ainda assim não desfaz o que esteve público.

---

## Ferramentas do projeto

**`python tools/mapa.py <arquivo.py> [--metodos] [--buscar TEXTO]`** — imprime o
esqueleto de um arquivo grande: classe, método e o intervalo de linhas de cada
um. `gui.py` tem 5,4 mil linhas e `ficha_pdf.py` 3,5 mil; abrir o arquivo
inteiro para achar um método é o desperdício mais fácil de evitar aqui. Mapear
primeiro, depois ler só o intervalo: `mapa.py gui.py --buscar trocar_modo`
devolve 70 linhas em vez de 5.654.

O **nome solto basta** — `mapa.py gui.py`, não
`mapa.py isocentro/interface/gui.py`. Desde que os módulos viraram pacote
(09/09/2026), exigir o caminho completo trocaria o custo que esta ferramenta
economiza (contexto) por outro: saber de cabeça em que subpacote cada um dos 60
módulos foi parar. Ela imprime o caminho que escolheu na primeira linha, em
stderr. Nome que existe em mais de um lugar **não é adivinhado**: lista os
candidatos e para, porque mapear o arquivo errado é pior que não mapear — o
intervalo de linhas sairia certo para o arquivo que não é o da vez.

**`python tools/testar.py`** — roda só os testes da frente aberta: pergunta ao
git o que mudou e escolhe os arquivos de teste que **importam** o módulo mexido.
Medido em 08/09/2026: 315 testes em 43 s, contra 1742 em 152 s. Casa por import
e não por nome de arquivo porque `fichinha.py` é coberto também pelo
`test_gui_smoke.py` — a trilha passava e a fumaça da janela quebrava, e o nome só
acha o primeiro. **Não substitui a suíte** e diz isso na saída: recorte verde não
é suíte verde. No primeiro uso ele achou um teste que só passava de carona
(`test_capa_espelho` dependia de outro arquivo da suíte redirecionar a pasta de
configuração antes dele).

**`python tools/raio.py [ref]`** — o raio de revisão do AD-39, lido do diff
contra a `ref` (padrão `HEAD`, mais os arquivos novos): para cada arquivo, o
módulo dono e o raio — o módulo; o módulo e os consumidores da fachada; ou tudo.
O dono vem da tabela de destino da semente enquanto os pacotes de hoje existirem
(`papel/` → Radioteraficha, `paralelo`/`qualidade` → Plano, `dicom/` → `rt`,
equipe e `constantes` → núcleo). O raio **só soma**: `rt`, núcleo, adaptador,
SQL, dependência fixada (`requirements`, `constraints`, `.spec`), tabela de
máquina e arquivo sem dono — o que a Q6 ainda não decidiu — dão "tudo". O que
tem caminho de import até `papel/` (nos dois sentidos) acrescenta "comparar PDF
e avisar". `python tools/testar.py --raio [--ref REF]` usa o raio como recorte (o
módulo dono inteiro, não só o arquivo mexido); raio "tudo" não tem recorte e
ele manda para a suíte. `docs/qms/` vale tudo (é a fonte da classe 62304); outro
documento (`.md` fora do pacote) tem raio nenhum, mas
roda o teste que o cita pelo nome. O que ele não faz: listar quem reage às
verificações pelo motor (o catálogo não existe; a saída avisa) e substituir a
suíte no fechamento.

**`python tools/manutencao.py [--rede] [--eixo …]`** — mede o **ambiente**, que
era a parte sem ritual: a suíte confere o programa e o `/fechar` confere a
frente, mas ninguém conferia a bancada em volta. Cinco eixos: armazenamento
(transcripts, `dist/`, `build/`, `ctx_*.txt` de sessão morta, saída de
ferramenta parada na árvore), saúde do `.claude/` (**roda cada gancho** e vê se
ainda sobe, acha gancho fora do `settings.json`, comando apontando para arquivo
que sumiu, ferramenta fora desta documentação), notas (`NOTAS.md` acima do alvo,
pendência declarada aberta há mais de 21 dias, seção que devia ter descido para
`notas/AAAA-MM.md`, link quebrado no índice), ambiente externo (extensão
recomendada ausente, extensão instalada **sem decisão** no `extensions.json`,
indesejada instalada, diff da lista desde a última execução, e
`pip list --outdated` só com `--rede`) e **skills** (desde 22/10/2026: o par do
`extensions.json` é o `tools/skills.jsonc`, com as skills `usadas`,
`desligadas`, `bloqueadas` e `obrigatorias`, cada grupo com o porquê. Grave:
desligada que **voltou** — atualização do BMad reinstala o pacote inteiro —,
bloqueada sem a negação no `.claude/settings.json`, obrigatória ausente. Para
saber: skill sem decisão, descrições acima de `TETO_DESCRICOES` (elas entram em
todo turno; 19 mil caracteres medidos na criação), comando de sessão sem linha
aqui, e o diff das sincronizadas do claude.ai). As desligadas moram em
`~/.claude/skills-desligadas/`, não apagadas.

Na primeira execução, 09/09/2026: 209 MB de regenerável, 186 MB de transcripts
em 50 sessões, 8 arquivos de saída parados (dois zips de release somando 142 MB),
o `NOTAS.md` 15 linhas acima do alvo e 8 ferramentas fora da
documentação — as sete que sobraram foram escritas ainda em 09/09, cinco no
`tools/LEIAME_CLINICA.md` e duas aqui. Nenhum
deles é bug; todos são o que se acumula quando ninguém mede.

**Ela nunca apaga** — imprime o comando e a decisão é de quem lê, porque
`TCs_Teste/`, zip de release e transcript antigo dividem terreno com o lixo
regenerável. A única exceção é `--limpar-ctx`, que só toca nos `ctx_*.txt` de
sessão morta e só sob a flag. Desde 22/10/2026 o `abertura.py` a **roda sozinho**
quando passa de 7 dias (a sugestão ficou sem resposta de 09/09 a 22/10): o relatório
vai para `.claude/estado/manutencao_ultima.md` e a sessão recebe só o placar e os
títulos do que é para decidir agora.

**`python tools/notas.py descer [--simular]`** — desce do `NOTAS.md` toda seção com
mais de 14 dias e, se ainda passar de 400 linhas, as mais antigas; a primeira nunca
desce, e seção sem data fica. Move byte a byte para o `notas/AAAA-MM.md` (cria o mês),
põe a linha no índice e, se o título se declara aberto, em "O que está aberto".
Existe porque a regra de descer dependia de alguém lembrar: o aviso da abertura
repetiu de 15/10 a 22/10/2026 que o arquivo tinha 1.900 linhas. O `abertura.py` a
chama quando o arquivo passa de 400 linhas, e o `/fechar` no checkpoint.

**`python tools/varredura_cli.py [--conferir] [--pasta X]`** — uma passada da
exportação automática sem abrir o app, e a razão de existir é a decisão de
02/09/2026: o relógio da varredura mora DENTRO do programa aberto, o que na
concentradora exigiria alguém mantendo-o aberto e logado num servidor. O
trabalho continua sendo o do `gatilho.rodar`; aqui só há o que a linha de
comando precisa — console em UTF-8, o rastro no lugar certo e um **código de
saída** que o Agendador saiba mostrar: 0 rodou (inclusive vazia, e inclusive
pulada por outra em curso), 1 interrompida, 2 **não rodou** por falta de
configuração, 4 exceção inesperada.

O `--conferir` é o passo anterior a cadastrar a tarefa: imprime a pasta, **qual
degrau a escolheu**, o estado da rede DICOM e a **conta do Windows** em uso — e
não abre associação, não grava e não apaga. A conta importa mais do que parece:
`ambiente.ler` é `os.environ` puro, e variável de usuário **não atravessa
conta**. Configurada só por variável no usuário interativo, a rede DICOM some
para a conta da Tarefa Agendada, e a varredura não exportaria nada com o
Agendador verde. É por isso que as quatro chaves DICOM também moram no
`config_servico` desde 14/09/2026.

Empacotar é `python tools/gerar_varredura.py`, nunca à mão — mesmas
conferências dos outros dois, e uma a mais que só esta precisa: o
`isocentro.interface.simulacao` é importado DENTRO do `gatilho._preparar`
e **não pode** ficar de fora do pacote. Sem ele, todo caso preparado sairia
"sem cadastro de simulação", que é resposta legítima do domínio — ninguém
procuraria defeito de empacotamento.

**`python tools/caso.py <TC8|Elekta|…>`** — carrega um dos 19 casos reais de
`TCs_Teste/` e gera a ficha, pronta para conferir. É a ferramenta da régua do
papel: monta a `JanelaPrincipal` de verdade (invisível), roda o mesmo
`_CarregarTudo` do botão "Abrir pasta" e chama o mesmo `_montar_planos_pdf` —
a ficha sai pelo caminho por onde sai a da sala. Para comparar antes/depois de
uma mudança no PDF, gerar os dois com `-o` e medir. **Não** monta agendamento
nem capa: são decisões de tela, e inventá-las daria uma ficha que não
corresponde a escolha nenhuma.

**`python tools/comparar_pdf.py <antes.pdf> <depois.pdf>`** — imprime só as
células que mudaram de texto, andaram de lugar, sumiram ou surgiram, com página
e coordenada; as idênticas viram uma contagem. A ficha do TC8 tem 214 células, e
a olho não se vê um 92,3 que virou 91,8 nem uma linha que desceu 3 pontos.

**`python tools/regressao_papel.py [--gravar [CASO]]`** — o `caso.py` e o
`comparar_pdf.py` juntos, contra uma referência APROVADA: gera a ficha dos casos
de `dicom-teste/` (pseudonimizados; TC8 individual e soma, TC6, Elekta) e
compara texto e posição de cada célula com o JSON em `tests/`. Saída 1 se o
papel mudou. `--gravar` é a decisão "mudou de propósito", e o diff do JSON vai
no commit, que é onde o aviso ao usuário fica registrado. O
`tests/test_regressao_papel.py` o roda na suíte (~43 s, subprocessos em
paralelo) e é pulado na CI, onde o acervo não existe. Só "Impresso em <hoje>"
é volátil. Existe porque nenhum teste conferia a ficha INTEIRA: uma mudança no
`dominio/` que deslocasse uma dose passava verde (22/10/2026).

**`python tools/tela.py <alvo> [-o img.png]`** — o equivalente do `caso.py` para
a TELA: monta o widget pela sequência que funciona e grava um PNG **com o texto
desenhado**. Existe porque conferir tela à mão tem duas armadilhas que se
disfarçam de bug de layout, e as duas já custaram tempo: o `offscreen` não
desenha texto (sai tudo com as caixas certas e os rótulos vazios) e a
`JanelaPrincipal` derruba o processo com exit 127 e nenhum traceback se o
`setStyleSheet` não vier antes. `--lista` mostra os alvos. Aceita `--modo
dia|noite` porque metade das regressões de cor só aparece num dos dois.

**`python tools/varrer_identidade.py [--arvore] [--intervalo A..B]`** — varre as
linhas que ENTRAM no commit atrás de identificador real de paciente e devolve
saída 1 se achar. Registro colado a um sufixo de unidade (`CEL`, `BET`, `ANA`)
com prefixo diferente de `900`, mais o registro e o nome reais do
`.identidades.json`, que fica fora do git. Nunca imprime o achado por inteiro —
sai o começo, o tamanho e o `arquivo:linha`, porque relatório que ecoa o
registro vaza o dado no lugar onde ele mais viaja. Sem o mapa na estação, roda
só a primeira verificação e **diz** que foi parcial. Medida da primeira
execução, em 10/09/2026: **25 achados nos últimos 20 commits**, todos reais.

**`tools\copiar_restrito.ps1 -Destino E:\copias`** — cópia **cifrada** do
`_restrito/` para fora deste disco; **quem roda é o usuário**. Até 22/10/2026 os
backups do `_restrito/` moravam no mesmo SSD que ele. Cifra pelo 7-Zip
(AES-256, `-mhe=on` cifra também os nomes, que já entregariam paciente), porque
esta estação é Windows 11 Home e não cria BitLocker To Go. Recusa: sem 7-Zip,
destino no mesmo disco, destino em nuvem, arquivo do dia já existente. Confere
o `.7z` com `7z t` e só então grava `_restrito\ultima_copia.txt` (data,
destino, tamanho), que o eixo armazenamento da manutenção lê: nunca copiado ou
cópia com mais de `DIAS_COPIA_RESTRITO` (30) dias é achado grave.

**As duas que geram ASSET, e por isso quase nunca rodam** — não entram no fluxo
de nenhuma sessão; entram quando o que elas produzem precisa mudar, o que é
raro. Foi por isso que ficaram fora desta lista até 09/09/2026, e é por isso que
precisam estar nela: quem não sabe que existem redesenha à mão o que elas geram.

**`python tools/gerar_diagramas_mesa.py`** — gera `assets/table_TB.png` e
`assets/table_serie_c.png`, os dois diagramas que o `ficha_pdf._cabecalho`
desenha conforme o `grupo_mesa` da máquina (ver `constantes.MAQUINAS`). O
desenho é a **roseta de eixos do console**: os três eixos, o sinal que o console
mostra em cada sentido e a faixa de números, mais o sentido de rotação. A mesa
em si saiu do desenho — num slot de 124×68 pt a caixa em perspectiva só roubava
espaço dos números, que são o que o técnico procura. A série C **inverte o
vertical** e conta de trás para frente, e é essa diferença que justifica os dois
arquivos em vez de um. Mexer aqui é mexer no papel: **avisar o usuário o que
muda**, como em qualquer mudança do impresso.

**`python tools/gerar_notas_modelo.py`** — gera `assets/notas_modelo.json`, a
**semente** da biblioteca de notas. Existe por causa de uma armadilha de
empacotamento: o arquivo de trabalho é `notas_posicionamento.json`, ao lado do
programa, e ele **não pode viajar no zip** — o `migrar.ps1` nunca sobrescreve,
então uma cópia dele no pacote faria a migração PULAR a biblioteca real do
serviço, e as notas que o técnico criou sumiriam sem aviso (erro nº 2 do
`gerar_executavel.py`). Sem nada no pacote, porém, instalação nova abre com o
seletor vazio — foi o que aconteceu na clínica. A semente resolve os dois: nome
diferente, então a migração a ignora e ela pode ser empacotada, e o
`notas_setup.semear()` lê dela quando não há acervo `.docx`.

**Banco, ARIA e DICOM** (`gravar_banco.py`, `atividades.py`, `sondar_dicom.py`,
`descobrir_dicom.bat`) estão em `tools/LEIAME_CLINICA.md`, e a skill `/clinica`
os carrega. Nenhum deles roda da máquina de trabalho — ler aquele arquivo ANTES
de escrever o comando.

O relatório delas cai em `relatorios_ferramentas/`, ao lado do código e fora do
git — ele traz nome e registro de paciente real. A pasta nasceu em 09/09/2026,
quando eram 24 arquivos soltos na raiz, misturados com os módulos do programa:
como nenhuma ferramenta sobrescreve relatório (ver `atividades._destino_livre`),
eles se acumulam por desenho e precisavam de casa.

**O que exige identidade de rede vai SEMPRE pelo `.bat`** (combinado em
04/09/2026). Nunca mandar o usuário digitar `python tools/x.py` dentro de um
`runas`: o console do `runas` fecha ao terminar, e o relatório se perde na hora
exata em que ele importa. O `.bat` já grava em arquivo e já imprime QUEM está
rodando — o `runas /netonly` não valida a senha na hora, e sem essa linha a
falha aparece só depois, como `18452 — untrusted domain`.

### `tools/robo.py` — o robô das frentes `robo` do `DESTINO.md`

```
python tools/robo.py --simular   # a próxima frente e o prompt, sem chamar o claude
python tools/robo.py --uma       # uma frente, conferida, e para
python tools/robo.py             # até a fila acabar ou a conferência reprovar
```

Rodar do checkout do usuário, com o `python` da `.venv` (é ele que o robô
põe no PATH da sessão: o worktree não tem `.venv`). Nasceu em 15/09/2026, a
pedido: o app andando para o `DESTINO.md` sem ninguém na frente, parando no
limite de uso e voltando quando ele libera.

- **Uma sessão `claude -p` por frente**, no worktree `..\isocentro-robo`
  (branch `robo`). A sessão nova é o `/clear`; o `/code-review` e o `/fechar`
  vão dentro dela, pelo prompt.
- **Autorização é lista, não liberação geral**: `--permission-mode dontAsk` com
  o `tools/robo_settings.json`. O que está na lista passa; o resto é recusado
  sem perguntar — a sessão nunca fica pendurada esperando um clique.
- **Limite de uso**: reconhece a mensagem, dorme até a hora dela (ou 30 min) e
  repete a MESMA frente como retomada, a partir do checkpoint. Worktree sujo
  na partida também começa como retomada.
- **Suíte pelo `tools/suite.py`**, nunca como o `/pronto` manda. Numa sessão
  `-p` com `dontAsk`, `> arquivo`, `;` e `run_in_background` são recusados ou
  inúteis — a R-01 (15/09) respondeu "aguardo o resultado" e a sessão acabou
  ali. O `suite.py` roda em primeiro plano, grava a saída e imprime só o
  veredito; roda os testes da pasta ATUAL, e o robô o chama por caminho
  absoluto do checkout do usuário. Serve fora do robô também:
  `python tools/suite.py [--aleatoria]`.
- **Dois passes de suíte por frente, não três** (desde 15/09/2026): a sessão
  roda a completa, a conferência roda a **ordem aleatória**
  (`SUITE_DA_CONFERENCIA`). Antes a sessão rodava as duas e a conferência
  repetia a completa — ~8 min por frente, um passe repetido.
- **Duas travas.** O gancho `tools/robo_trava.py` recusa na hora a edição em
  `papel/`, `interface/`, `dominio/` e na configuração do robô — medido em
  15/09 com uma sessão real: Write em `papel/` negado com a mensagem da trava,
  Write em `tests/` aceito. Mas um `python -c` passa por baixo de gancho de
  Edit, então a segunda trava é o `robo.py` **medir o diff** depois da sessão.
- **O push é do `robo.py`**, nunca da sessão (negado na lista), e só depois de:
  checkout do usuário intacto, árvore limpa, nada travado no diff, nenhuma
  `classe:` mudada, `varrer_identidade --intervalo` limpo e ordem aleatória
  verde no worktree (a semente vai no motivo). Qualquer falha **para o robô
  inteiro**, sem push.
- **Sessão interrompida retoma sozinha** (desde 15/09/2026). Sem marca
  FEITA/ESTACIONADA e com a árvore suja, é trabalho no meio, não mentira:
  passa pelas travas de segurança (checkout do usuário, diff travado,
  classes), mas sem varredura, suíte nem push, e a mesma frente volta como
  retomada. Na 2ª tentativa com a árvore ainda suja, o robô para. O ponto de
  partida da frente fica em `relatorios_ferramentas/robo/partida.json`, porque
  a retomada que mede só a partir do HEAD dela deixaria os commits da sessão
  cortada escaparem da trava. Antes disso, a R-01 parou três vezes e só
  voltou por relançamento à mão.
- **O limite se reconhece pelo 429** do `result`, antes do texto. A frase
  mudou para "hit your *session* limit" sem aviso, e a regex antiga a leu
  como fim sem marca.
- **Recusas no `robo.log`**, uma linha cada, do `permission_denials` do
  `result`. A lista do `robo_settings.json` se ajusta por elas: as 15 de
  15/09 eram quase todas git só-leitura. `git -C` e `%TEMP%` ficam recusados,
  e o prompt diz o caminho certo.
- **Custo medido**: uma sessão vazia grava ~51 mil tokens de contexto em cache
  de 1 h (CLAUDE.md + ganchos + o próprio Claude Code), US$ 0,51 no preço de
  lista em 15/09. Uma frente de verdade custa várias vezes isso.
- **Custo por etapa no `robo.log`**: a sessão sai em `stream-json`, e o
  `custo_por_etapa` reparte o `total_cost_usd` entre frente / `code-review` /
  `fechar` pelo peso dos tokens de cada resposta (a troca de etapa é a chamada
  da skill). É repartição, não fatura. Existe para decidir com número se o
  `code-review` em nível high pesa — e só então cortar. A classificação da
  saída ignora as linhas de evento: o transcript traz o NOTAS.md e arquivos com
  "rate limit" escrito, e procurar o limite ali poria o robô para dormir sem
  motivo.
- **A sessão do robô não recebe o checkpoint vivo** do gancho de abertura
  (`ISOCENTRO_ROBO=1`, posto pelo `robo.py`): o prompt já leva a frente, e
  as 70 linhas eram de outra frente — com o aviso de "`NOTAS.md` acima do
  teto", que convidava a sessão a podar o arquivo fora do escopo dela.

O relatório de cada sessão, a suíte da conferência e o `robo.log` caem em
`relatorios_ferramentas/robo/`. O `.claude/` do usuário é COPIADO para o
worktree a cada rodada (sem o `settings.local.json`, e sem o
`additionalDirectories`, que apontaria para o checkout do usuário).

**O que ele NÃO faz:** juntar a `robo` na `main` (é do usuário), mudar a classe
de frente, pegar frente `voce` ou `clinica`, e sobreviver a desligar a
máquina — o laço mora no processo.

---

## Comandos de sessão

Moram em `.claude/commands/`, que é **ignorado pelo git** por ser configuração
de estação. Se sumirem numa reinstalação, o que cada um faz está aqui.

| comando | o quê |
|---|---|
| `/abrir` | começa a frente: declara a frente única **e o que ela não inclui**, antes de abrir arquivo nenhum |
| `/testar` | recorte da frente (`tools/testar.py`), não a suíte |
| `/pronto` | suíte completa + ordem aleatória, com o número de testes relatado |
| `/checkpoint` | grava o estado no `NOTAS.md` |
| `/caso` | carrega um caso real e gera a ficha |
| `/tela` | PNG de uma tela, pela sequência que não derruba o processo |
| `/mapa` | esqueleto de um arquivo grande |
| `/empacotar` | `tools/gerar_executavel.py`, nunca à mão |
| `/git` | commita dividido por frente, e empurra |
| `/fechar` | o fim de frente na ordem certa: suíte → checkpoint → commit; o `/clear` só pelo gatilho (pausa longa, assunto novo, contexto grande) |
| `/manutencao` | confere o ambiente de trabalho (armazenamento, `.claude/`, notas, extensões) — relata, não apaga |
| `tools/sondar_estacao.ps1` | a estação clínica, onde **nada executa**: PowerShell puro, C-ECHO montado byte a byte, e o teste de autenticação entre domínios |
| `tools/gerar_checkup.py` | empacota o checkup num **executável** — é assim que ele chega à clínica, onde não há Python nem repositório |
| `tools/checkup_clinica.bat` | a ida à clínica quando ela é UMA: rede, banco, pastas, DICOM e impressão numa rodada, e o pedido à TI escrito no fim (bloco 12). Ver `docs/PEDIDO_TI.md` |
| `tools/varredura_cli.py` | uma passada da exportação automática **sem abrir o app** — é o que a Tarefa Agendada da concentradora chama. `--conferir` só olha o portão e não toca em nada |
| `tools/gerar_varredura.py` | empacota a varredura num **terceiro executável** (`VarreduraIsocentro`), que é como ela chega à concentradora. O zip leva o **exe sozinho**, para ser copiado para dentro da pasta do app: é a posição dele que decide de onde sai o `config_servico.json` |
| `tools/manutencao.py` | o ambiente em volta do código, semanal (a abertura roda sozinha) |
| `tools/notas.py` | desce do `NOTAS.md` o que já não está em andamento (a abertura e o `/fechar` chamam sozinhos) |
| `tools/gerar_constraints.py` | gera o `constraints.txt`: versão exata também das dependências transitivas, para o mesmo commit instalar a mesma coisa daqui a um mês |
| `tools/checkup_clinica.py` | o motor do `checkup_clinica.bat`: mede numa rodada tudo o que o ISOCENTRO precisa da rede e devolve o pedido à TI escrito |
| `tools/mapear_agenda.py` | mapeia a AGENDA do ARIA no data warehouse (quem tem hora em qual máquina) — o que a aba Agenda precisa. Identidade de rede: ver `tools/LEIAME_CLINICA.md` |
| `tools/checar_parada.py` | confere as hipóteses 2 e 3 do Índice de Disponibilidade (`agenda_db.py`); a 1 fechou em 28/09/2026 |
| `/clinica` (skill) | carrega `tools/LEIAME_CLINICA.md` |

## Ganchos

Em `.claude/hooks/`, **versionados desde 29/10/2026** (fora do git rodavam
sozinhos sem teste nem revisão — a cascata de 28–29/10 está no
`ARMADILHAS.md`); `tests/test_ganchos.py` roda cada um com o payload real em
modo `ISOCENTRO_GANCHO_SEM_EFEITO` (conferido não age). Cinco, pela mesma razão: regra
que depende de eu **lembrar** dela falha um dia, e aqui a falha de memória é
cara — em 08/09/2026 a manhã rendeu pouco por contexto inflado, não por falta de
trabalho.

| gancho | o que faz |
|---|---|
| `checar_py.py` | `ruff` no arquivo recém-editado em 0,2 s + quatro armadilhas que linter nenhum conhece (`del modulo.funcao` em teste, `setSpecialValueText("")`, `setCurrentText("")`, `ISOCENTRO_DB_SERVIDOR` zerado) |
| `abertura.py` | injeta branch, árvore, a **seção viva** do `NOTAS.md` e os títulos do `ARMADILHAS.md` (~470 tokens, sem turno) no lugar da leitura cega de 25 KB que abria toda sessão; **desce** o `NOTAS.md` acima de 400 linhas (`tools/notas.py`), **roda** a manutenção quando passa de 7 dias e avisa quando o `CLAUDE.md` passa do orçamento (360 linhas). Desde 29/10/2026 a manutenção vai em **segundo plano** (placar na abertura seguinte), a abertura avisa **variável `ISOCENTRO_*` mudada depois que o VS Code abriu** e **sobe o PostgreSQL local** se ele estiver fora. Desde 22/10/2026 avisa também de **outra sessão viva no mesmo checkout** (transcript tocado há menos de 30 min e sem o `cost-state` do fecho), que dividiria o índice do git com esta |
| `ler_grande.py` | **recusa** arquivo >800 linhas sem recorte, já com o comando do `mapa.py` na recusa: esquecer custa ~67 mil tokens **vezes o resto da sessão** |
| `antes_do_resumo.py` | grava o estado cru e pede o checkpoint antes do `/compact` — resumo automático guarda a conclusão e perde o **porquê**, que é o que este projeto anota |
| `limite_de_contexto.py` | avisa **a mim** (uma vez por faixa, 75% e 90%) que passou da hora de propor o `/fechar` — e, desde 10/09/2026, quantos arquivos há na árvore por commitar: saber a hora sem saber o que há a perder não muda decisão nenhuma |

**Barra de estado** (`barra_de_estado.py`): branch, arquivos modificados, quanto
do contexto já foi gasto, e aviso quando a árvore está suja com o `NOTAS.md`
intacto. Em 75% pede `/fechar` — é onde suíte, checkpoint e commit ainda cabem
no que sobra. A hora do `/clear` era adivinhada, e adivinhar erra para o lado
caro. A conta do contexto mora em `.claude/hooks/contexto.py`, uma só, porque
dois números discordando não seriam consultados por ninguém.

**Dois registros medem o que foi escolhido sem medir**: o `ler_grande.py` anota
cada recusa (`--relatorio` mostra a contagem por arquivo — recusa que se repete
é teto apertado demais para ELE) e o `abertura.py` anota o tamanho do `NOTAS.md` a
cada abertura (`.claude/estado/tamanho_notas.tsv`) — e desce o que passou de 400.

## O editor (VS Code)

Quatro arquivos em `.vscode/`. O diretório está no `.gitignore` (`.vscode/*`)
e cada um deles é liberado por uma linha própria (`!.vscode/tasks.json`) — de
propósito: assim arquivo novo ali nasce FORA, e entra quando alguém decide que
vale para todas as estações. O `.claude/` inteiro fica de fora, porque tem
caminho absoluto e UUID de sessão.

| arquivo | o quê |
|---|---|
| `settings.json` | interpretador do `.venv`, ruff como **linter e só** (sem format-on-save, que reescreveria os comentários longos desta base), Pylance como navegação e não como verificador de tipos (819 falsos positivos medidos em 31/08/2026), unittest ligado e pytest **desligado** |
| `launch.json` | o F5: `run_gui.py`, único ponto de entrada do app |
| `extensions.json` | as 13 extensões de que este projeto depende (o `tools/manutencao.py` confere se estão instaladas) e a que atrapalha (`unwantedRecommendations`) |
| `tasks.json` | as ferramentas do `tools/`, alcançáveis pelo editor |

**Por que o `extensions.json` existe** (08/09/2026): o `settings.json` configura
cinco extensões e o `launch.json` chama o `debugpy` pelo nome — e configuração
de extensão **ausente não dá erro**, o VS Code ignora a chave. Numa estação
nova, o ruff pararia de acender avisos e o F5 pararia de depurar, os dois em
silêncio. A lista faz o editor OFERECER a instalação ao abrir a pasta, em vez
de a falta ser descoberta pela ausência. Ficaram de fora, com o motivo escrito
no próprio arquivo: as `ms-dotnettools.*` (são do projeto ESAPI, outro
repositório), a de pull request (o projeto usa o `gh` na linha de comando) e a
de contêineres (não há Docker aqui). A `vscode-python-envs` foi para
`unwantedRecommendations` em 22/10/2026, e o `settings.json` a desliga
(`python.useEnvironmentsExtension`): instalada, ela passa por cima do
interpretador fixado. A markdownlint entrou na mesma data, com as regras no
`.markdownlint.jsonc` da raiz (de ~5 mil avisos para 662).

**As tarefas** (`Ctrl+Shift+P` → *Run Task*, ou os atalhos abaixo). Todas
chamam `.venv/Scripts/python.exe` pelo caminho explícito, igual ao
`launch.json`, e não o `python` do PATH — a estação tem mais de um:

| tarefa | atalho |
|---|---|
| Testes da frente (rápido) — recorte por import | `Ctrl+Shift+B` |
| Suíte completa (~1742 testes, ~2,5 min) | `Ctrl+Alt+T` |
| Suíte em ordem aleatória | — |
| Ficha de um caso (gerar e abrir) | `Ctrl+Alt+F` |
| Ficha de um caso → `antes.pdf` | — |
| Comparar dois PDF | `Ctrl+Alt+D` |
| Tela (PNG da janela principal) | `Ctrl+Alt+V` |
| Ruff no projeto inteiro | `Ctrl+Alt+R` |
| Empacotar (executável + zip) | — |

O `tools/mapa.py` **não** virou tarefa de propósito: ele existe para economizar
contexto de agente, e para uma pessoa no editor o `Ctrl+Shift+O` (estrutura do
arquivo) responde melhor — leva o cursor até lá.

**Os atalhos são de estação**, não do projeto: moram em
`%APPDATA%\Code\User\keybindings.json`, que nenhum repositório versiona, e por
isso valem também na janela do projeto ESAPI. É do formato — o VS Code não tem
chave de contexto para "só nesta pasta". A consequência é branda: numa janela
sem aquela tarefa, o atalho abre o seletor de tarefas em vez de dar erro.

---

## Integração contínua

`.github/workflows/testes.yml`, a cada push. Três jobs: `lint` (ruff no projeto
inteiro, segundos — porque o gancho só vê o que **eu** editei, e arquivo mexido
direto no VS Code não passa por linter nenhum), `suite` (ordem normal **e**
aleatória, no Linux com Qt offscreen) e `empacotar` (Windows, só confere que o
PyInstaller ainda fecha o pacote; o `.exe` de distribuição continua saindo da
estação, com o smoke test à mão).

---

## Configuração

Pastas por variável de ambiente, com padrão ao lado do programa. **Valem três
nomes**: `ISOCENTRO_*` (o atual, tem precedência), `RADIOTERAFICHA_*` e
`FICHAPY_*` (os antigos, continuam funcionando). Ler sempre por `ambiente.ler(...)`, nunca por
`os.environ.get` direto — renomear e pronto quebraria em silêncio as estações
que a TI já configurou, e a tabela abaixo lista o sufixo comum aos três:

| variável | o quê |
|---|---|
| `ISOCENTRO_CAPA_DIR` | relatórios exportados que alimentam a capa |
| `ISOCENTRO_USERS_DIR` | usuários e senhas |
| `ISOCENTRO_BACKUP_DIR` | backups |
| `ISOCENTRO_LOG_DIR` | histórico de uso (compartilhado) |
| `ISOCENTRO_CORRECOES` | correções de cadastro (compartilhado) |
| `ISOCENTRO_SIMULACOES` | raiz das simulações |
| `ISOCENTRO_CONFIG` | configuração do serviço (o que o admin aponta) |
| `ISOCENTRO_DB_SERVIDOR` | servidor do data warehouse (vazio = só relatórios) |
| `ISOCENTRO_ESPELHO` | espelho local do banco (reserva de emergência) |
| `ISOCENTRO_DADOS_FEIXE` | tabelas de TMR/Scp do cálculo paralelo |
| `ISOCENTRO_BANCO_LOCAL` | banco GRAVADO para simular o DW sem rede (`banco_local.py`) — só em máquina de trabalho |
| `ISOCENTRO_DICOM_SERVIDOR` | `host:porta` do DB Daemon do ARIA (exportação automática) — também em `config_servico` (`dicom_servidor`) |
| `ISOCENTRO_DICOM_AE_REMOTO` | AE Title do ARIA — também em `config_servico` (`dicom_ae_remoto`) |
| `ISOCENTRO_DICOM_AE_LOCAL` | AE Title desta estação, cadastrado no ARIA — também em `config_servico` (`dicom_ae_local`) |
| `ISOCENTRO_DICOM_AE_DESTINO` | destino do C-MOVE (só se o C-GET não servir) — também em `config_servico` (`dicom_ae_destino`) |
| `ISOCENTRO_DICOM_PORTA_ESCUTA` | porta em que esta ponta ouve o C-MOVE (padrão 104). **Só variável**, de propósito: 104 é a porta que a TI liberou, e chave que ninguém preenche é campo a mais na tela do admin |
| `ISOCENTRO_EXPORTACAO` | pasta onde a varredura grava os planos — também em `config_servico` (aba Serviço), que é onde o admin aponta para TODAS as estações |
| `ISOCENTRO_PG_TESTE` | conninfo de superusuário do PostgreSQL de **desenvolvimento** (só `localhost`) para o `tests/test_postgres.py`; vazia = esses testes pulados. Nunca o banco da clínica: os testes criam e apagam bancos |
| `ISOCENTRO_PG_APP` | conninfo do banco central para a **estação** ler as partes do PPR vivo (aba Documentação → PPR, R-85). **Provisória até a R-19**, que dá a cada pessoa o login dela; a conexão assume o papel `isocentro_app`. Vazia = a aba diz "Banco central não configurado" e tudo fica "sem dado". No desenvolvimento: `host=localhost port=5433 user=postgres dbname=isocentro` |
| `ISOCENTRO_PG_LOCAL_BIN` / `ISOCENTRO_PG_LOCAL_DADOS` | onde estão o `pg_ctl.exe` e o cluster que o app sobe ao abrir quando a `ISOCENTRO_PG_APP` é local. Padrão: `%LOCALAPPDATA%\Programs\pgsql-18\bin` e `%LOCALAPPDATA%\isocentro-pg\dev` |
| `ISOCENTRO_PG_CONCENTRADORA` | conninfo do banco central com o papel `isocentro_concentradora`. **Só na concentradora**: é ela que faz a `varredura_cli` rodar prazos e âncora (R-21); vazia = não roda, e a saída diz isso |
| `ISOCENTRO_PASTA_ANCORA` | pasta da TI, só-acrescentar, onde a concentradora cria `ancora-AAAA-MM-DD.txt` (AD-32). **Sem padrão**: âncora ao lado do app estaria ao alcance de quem ela vigia; vazia = falha na saída da varredura |

Login inicial `admin`/`admin`, troca obrigatória no primeiro acesso. Escolha de
**pasta do serviço** (relatórios, simulações) é decisão de **admin**, não de
estação: ela é gravada em `config_servico.json`, ao lado do índice central, e
vale para todas as estações que compartilham a pasta do programa. **Não usar
`QSettings` para isso** — no Windows ele é `HKEY_CURRENT_USER`, e a escolha
valeria para um usuário do Windows numa máquina só.

Precedência: escolha da sessão → variável de ambiente da estação → configuração
do serviço → padrão. A tela mostra qual delas está valendo (`origem_da_pasta`);
sem isso, quem aponta a pasta e não vê efeito não tem como descobrir que uma
variável local está mandando nela.

### PostgreSQL de desenvolvimento (R-18, 27/10/2026)

O núcleo grava no banco central (AD-10), e gatilho, papel e GRANT só se
testam em PostgreSQL de verdade (AD-34). Nesta estação ele é **portátil**,
escolha do usuário: o zip oficial da EDB (18.6, sem pgAdmin, StackBuilder e
documentação) em `%LOCALAPPDATA%\Programs\pgsql-18`, sem serviço do Windows
nem admin. O cluster fica em `%LOCALAPPDATA%\isocentro-pg\dev`, escutando só
em `localhost:5433` (a 5432 fica livre para um PostgreSQL de verdade), com
`trust` local e nenhum dado de paciente.

**Não sobe sozinho com o Windows — sobe com o APP** (desde 29/10/2026): ao
abrir, o ISOCENTRO dispara o `pg_ctl start` quando a `ISOCENTRO_PG_APP` aponta
para esta máquina e a porta não responde (`adaptadores/postgres/local.py`; o
que fez vai para o log). Para subir sem abrir o app — antes da suíte, por
exemplo (PowerShell, para o servidor não ficar preso ao terminal):

```powershell
Start-Process -WindowStyle Hidden "$env:LOCALAPPDATA\Programs\pgsql-18\bin\pg_ctl.exe" -ArgumentList '-D',"$env:LOCALAPPDATA\isocentro-pg\dev",'-l',"$env:LOCALAPPDATA\isocentro-pg\dev.log",'start'
```

Com a variável `ISOCENTRO_PG_TESTE` definida e o servidor fora, o
`test_postgres.py` **falha** em vez de pular: quem configurou o banco de teste
quer saber que ele caiu. Recriar do zero (cluster apagado):
`initdb -D ...\dev -U postgres -E UTF8 --locale=C --auth=trust`, e acrescentar
`listen_addresses = 'localhost'` e `port = 5433` ao `postgresql.conf`.

Cada classe do `test_postgres.py` cria o próprio banco (`isocentro_teste_*`),
aplica `migracoes/` e o apaga no fim. Para um banco que fica (ensaio à mão):
`createdb -h localhost -p 5433 -U postgres -O isocentro_dono isocentro` e
`python tools/migrar_banco.py --conexao "host=localhost port=5433 user=postgres dbname=isocentro" --papeis`.

### `tools/servidor_local.bat [funcao|varredura]` — demonstração fora da rede

Saiu do `CLAUDE.md` em 22/10/2026 (só importa quando se prepara demonstração).

demonstração FORA DA REDE: monta o DW simulado a partir de `TCs_Teste` (`montar_servidor_local.py`), sobe o DICOM local (`servidor_dicom_local.py`), deixa o trabalho do dia feito (`preparar_demo.py`: fichas e altas pela Impressão do programa, checklists, datas; o gatilho deixa a Documentação PRONTA) e abre o app. Consulta nova com T-SQL fora do que `banco/servidor_local.traduzir` cobre quebra `tests/test_servidor_local.py`

### `tools/gerar_executavel.py` — o que ele confere (saiu do `CLAUDE.md` em 22/10/2026)

**Empacotar é `python tools/gerar_executavel.py`**, nunca à mão. Ele confere
   o que já deu errado: o `--clean` apagando as instruções de instalação, dado
   de execução viajando no zip (o `migrar.ps1` nunca sobrescreve, então isso faz
   a migração PULAR o arquivo real do serviço) e import tardio que ficou de fora
   do pacote — este último falha **silenciosamente na clínica**.
