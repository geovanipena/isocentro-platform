# Revisão adversária: ARCHITECTURE-SPINE (ISOCENTRO, 19/10/2026)

**Alvo:** `../ARCHITECTURE-SPINE.md` (lido somente para revisão; contexto em `../.memlog.md` e `../extrato-codigo.md`).
**Método:** em cada par, duas unidades um nível abaixo (módulos, núcleo, concentradora, adaptadores, interface) cumprem cada AD ao pé da letra e mesmo assim saem incompatíveis. Cada par é um buraco, e ao lado vai a AD nova ou apertada que o fecharia.

**Veredito:** a espinha fecha bem a direção de dependência e a mutação dentro de uma transação. Ela **não diz quem é dono das entidades que vêm do ARIA** (paciente, curso, plano, máquina) nem com que identificador e que versão elas entram no ISOCENTRO. Também não diz **quem dispara, quem deduplica e quem encerra** execuções e alertas. Daí saem quase todos os pares abaixo.

Gravidade: **B** = bloqueia a construção dos módulos sem retrabalho; **A** = alta; **M** = média.

---

## 1. Entidades compartilhadas: dono e identificador

### P1 [B]: paciente, curso e plano sem dono nem chave canônica
- **Unidades:** `modulos/plano` × `modulos/tratamento` (e `modulos/radioteraficha`, `adaptadores/esapi_json`).
- **Como divergem cumprindo as ADs:** pela AD-3(1), cada módulo "é dono" do seu dado, mas paciente, curso e plano são dados do ARIA e não pertencem a módulo nenhum. O Plano guarda a Aprovação Física com `PatientId` + `PlanSetupId` (as strings do Eclipse, que é o que o JSON da ESAPI traz, AD-15). O Tratamento guarda frações com `PatientSer` + `PlanSetupSer` (as chaves numéricas do `variandw`, que `tratamento_db` já usa). O Radioteraficha continua com `FICHA_{NOME}_{REG}` (`registro_json.py`). As três fachadas (AD-3(2)) devolvem "o plano", e uma não casa com a outra sem regra de junção. Cada módulo vai inventar a sua.
- **AD nova (AD-26, Entidades de referência):** paciente, curso, plano, campo, máquina e clínica são **entidades de referência do núcleo**, com uma tabela de identidade por tipo. A chave canônica é a chave `Ser` do `variandw` mais a clínica. A tabela também guarda os apelidos (Id do Eclipse, `PatientId`, SOPInstanceUID e REG do Radioteraficha), e só o núcleo grava nela. Os módulos guardam **só a chave canônica**. A tradução Id/UID → `Ser` mora num único lugar, o adaptador. JSON da ESAPI que não casar com uma chave vira `erro` com motivo.

### P2 [A]: a mesma máquina com dois nomes
- **Unidades:** `modulos/plano` (trava `maquina_do_plano`, que compara o nome do ARIA, `paralelo.py:179-194`) × `modulos/qualidade` (CQ de equipamento, cadastrado pelo físico com nome livre, ex.: "Acelerador 1 CEL").
- **Como divergem:** cada um é dono do seu cadastro, como manda a AD-3. A verificação "plano em máquina com CQ vencido" precisa juntar `MachineId` do ARIA com o equipamento da Qualidade, e essa junção acaba sendo por parecença de nome, que é justamente o que a AD-13 proíbe para pessoas.
- **AD:** a AD-26 cobre a máquina como entidade de referência, com o vínculo equipamento-CQ ↔ `MachineSer` cadastrado em tabela. A proibição "nunca por parecença" da AD-13 passa a valer para **toda** entidade de referência, não só para usuários.

### P3 [A]: pessoa com duas identidades na migração
- **Unidades:** `nucleo` (identidade e assinatura no PostgreSQL) × `modulos/radioteraficha` (que ainda usa `equipe.py` por estação e `usuarios.json`).
- **Como divergem:** o núcleo assina com `usuario_id`, e a ficha impressa sai com o nome do físico tirado de `~/.isocentro_fisicos.json` daquela estação (Q7 está em Deferred). Um mesmo ato aparece com dois nomes, e a "quem" do log (AD-4) não bate com o rodapé do papel.
- **AD apertada (AD-13 + Q7 trazida para cá):** pessoa = `usuario_id` do núcleo, e é ele o "quem" de toda linha de log. Nome, conselho e cargo saem só da fachada do núcleo. `equipe.py` passa a ser somente leitura assim que o núcleo existir, sem gravação dupla.

---

## 2. Escrita: quem grava, por qual caminho

### P4 [B]: módulo gravando pelo adaptador × módulo gravando pelo núcleo
- **Unidades:** `modulos/qualidade` × `modulos/seguranca`.
- **Como divergem:** a AD-2 proíbe o **núcleo** de importar adaptador concreto, mas **não proíbe o módulo**. A Qualidade importa `adaptadores/postgres` e grava suas tabelas com transação própria, pondo a linha de log no mesmo `BEGIN` (cumpre a AD-4). A Segurança grava por `nucleo.gravar(...)`, como no diagrama de fluxo. A AD-15 diz que "o único gravador é o código Python do núcleo", e a AD-3(1) diz que "só o módulo dono grava". As duas leituras são literais e incompatíveis: a capacidade (AD-11) é conferida num caminho e não no outro, e o formato da linha de log diverge.
- **AD apertada (AD-2 + AD-3):** **módulo não importa adaptador.** Toda gravação passa por `nucleo.gravar(unidade_de_trabalho, quem, capacidade)`, e a unidade de trabalho carrega o registro do dono. Cada módulo **declara** suas tabelas num mapa de dono (`modulos/<m>/tabelas.py`). Sem esse mapa, o teste da AD-22 ("módulo gravando em tabela de outro dono") não tem como saber quem é dono de qual tabela.

### P5 [A]: um log ou vários
- **Unidades:** `nucleo` (log encadeado) × `modulos/documentacao` (que, por ser "dono do seu dado", cria `documentacao_log` com o seu próprio gatilho de hash).
- **Como divergem:** a AD-4 exige "a linha de log" sem dizer **qual tabela**. A AD-6 diz "o log", no singular, mas não proíbe outro. Com duas correntes, a prova de integridade do FR-3 e a retenção de 10 anos passam a valer só para uma delas.
- **AD apertada (AD-4/AD-6):** existe **uma só tabela de log**, do núcleo, com uma corrente. O campo "o quê" leva `modulo`, `entidade`, `chave` e `payload`. Nenhum módulo cria tabela de log ou de histórico.

### P6 [B]: AD-5 (sem DELETE) × AD-17 (limpeza do espelho em 60 dias)
- **Unidades:** `concentradora` (apaga o espelho vencido, AD-17) × `adaptadores/postgres` (aplica a AD-5: "sem DELETE em dado registrado").
- **Como divergem:** quem implementa a AD-5 nega DELETE nas tabelas de dado. Quem implementa a AD-17 precisa de DELETE no espelho. Fica uma dúvida a mais: o espelho é "dado compartilhado"? Se for, cada resposta do `variandw` gravada no espelho exige linha de log (AD-4), e o log incha com cópia de dado clínico.
- **AD nova (AD-27, Cache × registro):** o espelho é **cache**, não registro. Ele fica fora da AD-4 e da AD-5, só o adaptador `variandw` grava nele, e só a concentradora apaga, por papel de banco próprio com DELETE **só** nas tabelas `espelho_*`. O log recebe **uma** linha por limpeza (quantas linhas, até que data), nunca uma por gravação. A AD-5 passa a citar a exceção.

### P7 [A]: correção de cadastro em dois lugares durante a migração
- **Unidades:** `modulos/radioteraficha` (ainda grava `correcoes_capa.json` no share, AD-5 já cumprida no JSON) × `modulos/tratamento` ou `plano` (lê a correção pela fachada, a partir do PostgreSQL).
- **Como divergem:** a AD-9 manda toda gravação compartilhada ao banco, mas o texto do Paradigma diz que o Radioteraficha "migra aos poucos". Os dois lados são legítimos. No meio da migração há duas fontes da mesma correção, e a capa e a 2ª checagem podem mostrar dados diferentes do mesmo paciente.
- **AD nova (AD-28, Corte de migração):** cada entidade tem **uma** data de corte numa tabela de migração. Antes do corte, a verdade é o JSON e o PostgreSQL não grava aquela entidade. No corte há uma importação única, registrada no log, e depois dela o JSON vira somente leitura e o código que grava nele sai. Gravação dupla é proibida. O teste da AD-22 reprova escrita em JSON de entidade que já passou do corte.

### P8 [A]: a fachada devolve objeto mutável ou "vivo"
- **Unidades:** `modulos/tratamento/consulta.py` × `modulos/indicadores` (ou `interface/modulos/tratamento`).
- **Como divergem:** "somente leitura" (AD-3(2)) pode ser lido como "não grava no banco". O Tratamento devolve `dict`, lista ou objeto com carga preguiçosa que consulta o banco quando é acessado. Os Indicadores normalizam o objeto no lugar e o repassam como "versão da origem" (AD-4) de um registro seu. A tela recebe o objeto preguiçoso, e a consulta acaba rodando na thread de tela, o que fere a AD-18 sem que ninguém tenha chamado o banco ali.
- **AD apertada (AD-3(2)):** a fachada devolve **só valores imutáveis**: `dataclass(frozen=True)` ou tuplas de primitivos. Cada valor traz `chave_canonica`, `versao_origem`, `degrau` e `data_da_fonte`. Ela nunca devolve conexão, cursor, gerador preguiçoso ou objeto do adaptador. O teste da AD-22 confere o tipo de retorno das funções públicas de `consulta.py`.

### P9 [M]: indicadores lendo o log cru
- **Unidades:** `modulos/indicadores` × `modulos/seguranca` (dona dos incidentes).
- **Como divergem:** módulo → núcleo é permitido pela AD-2. Os Indicadores leem o `payload` do log do núcleo e contam incidentes por categoria sem passar pela fachada da Segurança. Isso cumpre a AD-3, porque o log é do núcleo, mas acopla os Indicadores ao formato interno da Segurança, que pode mudar sem aviso.
- **AD apertada (AD-3):** o `payload` do log é opaco para quem não é dono. Os indicadores leem dado de módulo só pela fachada dele, e o log só pela API de auditoria do núcleo, que serve para prova de integridade e não para negócio.

---

## 3. Verificação, execução, alerta e pendência

### P10 [B]: a mesma verificação cadastrada por dois módulos
- **Unidades:** `modulos/plano` (porte Python de `qualidade.py`: índices ICRU/Paddick do plano) × `modulos/qualidade` (Garantia da Qualidade, FR-22 a 28) × `adaptadores/esapi_json` (o plug-in `Plano_Índices_e_Qualidade.cs` produz "as mesmas quatro chaves").
- **Como divergem:** "qualidade" quer dizer duas coisas no código (índice do plano, em `dominio/qualidade.py`) e no PRD (GQ e CQ). Os dois módulos cadastram "índice de conformidade" com nomes próprios, e o JSON da ESAPI entra como uma terceira verificação. As três executam sobre o mesmo plano e geram alertas repetidos ou contraditórios. A AD-14 padroniza o **resultado**, mas não diz quem é dono da **identidade da verificação**.
- **AD nova (AD-29, Catálogo de verificações):** cada verificação tem id estável com espaço de nome `<modulo>.<nome>` (ex.: `plano.indice_conformidade`), e o prefixo diz quem é dono. Uma verificação pode ter **vários avaliadores** (Python e ESAPI) tratados como degraus ou fontes da mesma verificação, nunca como verificações irmãs. O nome do pacote `dominio/qualidade.py` vai para `modulos/plano` no mapa da Q6.

### P11 [B]: estação e concentradora executando a mesma verificação
- **Unidades:** `concentradora` (gatilho `evento` "plano pronto", via `gatilho_db`) × `interface` / app na estação (o físico abre o plano e a 2ª checagem roda na hora; `gatilho_relogio.py` já tem `QTimer` na estação).
- **Como divergem:** a AD-9 dá à concentradora "verificações agendadas e prazos **com o app fechado**", o que deixa implícito que, com o app aberto, a estação também dispara. As duas executam. A estação leu do `variandw` (1º degrau) e a concentradora leu do espelho (2º degrau). Os resultados divergem e saem dois alertas. Nenhuma AD diz qual execução vale.
- **AD nova (AD-30, Execução vigente e dono do tempo):** (a) gatilhos `prazo` e `calendario` **só na concentradora**, e a estação nunca dispara gatilho de tempo (`gatilho_relogio` sai). (b) A execução sob demanda na estação é permitida, mas o alerta só nasce da **execução vigente**: a última por (`verificacao_id`, `chave_canonica`, `versao_origem`), com desempate pelo degrau mais alto. (c) A idempotência é imposta por restrição única no banco, sobre (verificação, objeto, versão, janela).

### P12 [A]: pendência encerrada por dois caminhos
- **Unidades:** `modulos/qualidade` (ao registrar o CQ, encerra a pendência "CQ vencido" chamando o núcleo) × `nucleo/motor` (a próxima execução `conforme` encerra a mesma pendência sozinha).
- **Como divergem:** a AD-1 põe "alerta e pendências" no núcleo, mas nenhuma AD diz **quem cria, quem encerra e como se encerra**. A AD-3(4) proíbe gravar em dado alheio, e o núcleo não é módulo, então chamar `nucleo.encerrar_pendencia` é permitido. Com os dois caminhos ativos, a pendência pode ser encerrada duas vezes, ou encerrada pelo módulo e reaberta pelo motor (porque o espelho ainda não viu o CQ). A AD-5 proíbe UPDATE de estado, mas não diz que o estado é evento.
- **AD nova (AD-31, Ciclo de vida de alerta e pendência):** alerta e pendência são do núcleo. Nascem **só** de execução vigente (AD-30). Encerram **só** por (a) execução vigente `conforme` ou `nao_aplicavel`, ou (b) ato humano com capacidade e motivo. Os estados são eventos acrescentados (aberta → reconhecida → encerrada / reaberta), nunca UPDATE. O módulo não encerra pendência nenhuma: ele grava o seu dado, e o motor reavalia.

### P13 [A]: assinatura × versão do RT Plan
- **Unidades:** `modulos/plano` (Aprovação Física e Duplo Check) × `modulos/tratamento` (confere "plano tratado = plano aprovado").
- **Como divergem:** a AD-4 manda gravar a "versão do dado de origem", mas não define o que é a versão de um RT Plan. O Plano assina com `PlanSetupSer`. Depois o plano é reaberto no Eclipse e alterado: o `Ser` é o mesmo e o SOPInstanceUID muda. O Tratamento compara por `Ser` e acha "aprovado", ou compara por SOPInstanceUID e acha "não aprovado". Cada lado cumpre a AD-4 com a sua noção de versão.
- **AD nova (AD-32, Versão de objeto clínico):** a versão de origem de um plano é a tupla (`PlanSetupSer`, SOPInstanceUID do RT Plan, `HstryDateTime` ou status de aprovação do ARIA), definida **uma vez** no adaptador e exposta pela AD-26. A assinatura liga (objeto, versão). Se a versão muda, a assinatura **não se transfere**: o núcleo registra um evento "assinatura não cobre a versão atual", e a verificação de tratamento compara a versão completa.

### P14 [A]: o prazo calculado em dois lugares
- **Unidades:** `modulos/qualidade/consulta.py` (a fachada calcula "vence em 3 dias" com `date.today()` da estação para a tela) × `concentradora` (a verificação de prazo dispara o alerta com o relógio do servidor e outra regra de borda, `<` contra `<=`, dia útil contra corrido).
- **Como divergem:** a tela mostra "vence amanhã" e o alerta já disparou como vencido. Os dois cumprem a AD-14 e a AD-18.
- **AD apertada (AD-30 + AD-14):** o cálculo de vencimento é **uma função pura** do módulo dono, usada tanto pela verificação quanto pela fachada. A "data de referência" vem sempre do banco, nunca da estação. A regra de borda (inclusive ou exclusive, dia corrido ou útil, feriado por clínica) fica escrita no catálogo da verificação.

### P15 [A]: fuso, relógio e "quando"
- **Unidades:** `nucleo` (log) × `adaptadores/variandw` × qualquer módulo.
- **Como divergem:** a AD-4 manda gravar "quando", mas não diz **de que relógio**. O módulo A passa `datetime.now()` da estação, que pode estar adiantada, e o módulo B deixa o `now()` do PostgreSQL. O `variandw` devolve `datetime` ingênuo, no horário local do servidor ARIA, e um módulo o grava como UTC enquanto outro grava como local. A ordem do log é serializada pelo banco (AD-6), mas o "quando" não é monótono. Em auditoria, um evento aparece antes da sua causa.
- **AD nova (AD-33, Tempo):** o "quando" do log e de todo registro é `now()` do PostgreSQL (`timestamptz`), e o app nunca o informa. Hora vinda do ARIA ou do DICOM é convertida no adaptador para `timestamptz` com `America/Sao_Paulo`. Vencimento e data civil são `date`, nunca `timestamp`. Estação e servidor sincronizam por NTP, e a estação avisa se divergir mais de N minutos do banco.

---

## 4. Clínica, RLS e papéis de banco

### P16 [B]: corrente única × RLS por clínica
- **Unidades:** `adaptadores/postgres` (gatilho de hash da AD-6) × `nucleo` (RLS da AD-12 sobre "toda tabela com dado de clínica", e o log tem clínica).
- **Como divergem:** se o log tem RLS, o gatilho que lê `hash_anterior` roda como o invocador (`isocentro_app`, com sessão CEL) e **não enxerga** a última linha, se ela for de BET. Ou o hash sai errado, ou cada clínica ganha uma corrente própria e a ordem global se perde. Uma estação também não consegue verificar a corrente inteira. As duas leituras cumprem a AD-6 e a AD-12.
- **AD apertada (AD-6 + AD-12):** é **uma corrente global**. O gatilho de hash é `SECURITY DEFINER`, de propriedade do `isocentro_dono`. O RLS do log vale só na **leitura de conteúdo** (por visão). A verificação de integridade roda numa função privilegiada que devolve só ok ou falha e a posição da quebra, sem conteúdo.

### P17 [A]: tabelas sem clínica e "todas as clínicas"
- **Unidades:** `modulos/documentacao` (POP vale para as três unidades) × `modulos/software` (inventário SOUP, que é global) × `nucleo` (catálogo de verificações, capacidades).
- **Como divergem:** a AD-12 só cobre tabela "com dado de clínica". A Documentação usa `clinica = NULL` para dizer "todas", e a política `clinica = ANY(sessao)` esconde a linha de todo mundo. O Software usa `clinica = 'TODAS'`, que fura o domínio da AD-8. O catálogo de verificações nasce sem coluna de clínica, e uma verificação ativada só em CEL não tem onde ficar registrada.
- **AD apertada (AD-12 + AD-8):** toda tabela é de um de dois tipos, declarados no mapa de dono (P4). (a) **De clínica:** `clinica` é `NOT NULL` com domínio `CEL`/`BET`/`DUO` e RLS. (b) **Global:** sem coluna `clinica` e sem RLS. O que vale para várias clínicas é modelado como linhas por clínica ou como tabela de aplicabilidade (`verificacao_clinica`). `NULL` e "TODAS" são proibidos.

### P18 [A]: a concentradora não tem "clínicas da sessão"
- **Unidades:** `concentradora` × `nucleo` (AD-12: "clínicas da sessão definidas pelo núcleo **no login**").
- **Como divergem:** a concentradora não faz login de pessoa. Uma implementação dá ao papel `isocentro_concentradora` o `BYPASSRLS`. Outra define a sessão com as três clínicas. Uma terceira roda uma sessão por clínica, com três passadas. As três obedecem, mas a primeira deixa a concentradora ler e gravar sem a rede de proteção que a AD-12 promete, e a "quem" do log (AD-4) fica sem dono.
- **AD apertada (AD-12 + AD-4):** a concentradora roda **sem BYPASSRLS**, com a sessão definida por execução para a clínica do objeto. A "quem" das suas linhas é um usuário de sistema fixo (`sistema:concentradora`) cadastrado no núcleo, com capacidades próprias e limitadas: executar verificação, importar JSON e limpar o espelho.

### P19 [M]: capacidade sem clínica e nome de capacidade inventado
- **Unidades:** `modulos/plano` (cria `assinar_aprovacao_fisica`) × `modulos/tratamento` (cria `aprovar_plano_fisico` para o mesmo ato, ao conferir no seu comando).
- **Como divergem:** a AD-11 dá exemplos de nome, mas não diz quem declara as capacidades. Ela também não diz se a capacidade vale por clínica: um físico de CEL pode assinar um plano de BET?
- **AD apertada (AD-11):** cada capacidade é declarada em código pelo módulo dono, com prefixo (`plano.assinar_aprovacao_fisica`), e o núcleo recusa capacidade não declarada. A concessão é por (pessoa, capacidade, clínica), conferida contra a clínica do objeto.

---

## 5. Versão, tempo de execução e composição

### P20 [A]: estação e concentradora com versões ou módulos diferentes
- **Unidades:** `concentradora` × app na estação.
- **Como divergem:** a AD-20 diz "mesmo código, mesma versão", mas só a AD-19 tem verificação, e só sobre o **esquema**. As estações rodam o exe do share e a concentradora é atualizada à parte. Na janela entre uma atualização e outra, a concentradora executa a regra v1.3 e a estação a v1.4, o esquema é o mesmo e nada reprova. A seleção de módulos também acontece em dois lugares, `run_gui.py` e `run_varredura.py`, e a concentradora pode registrar um subconjunto das verificações. A AD-2 proíbe o núcleo de importar módulos, mas a espinha não diz **onde os módulos são registrados**.
- **AD nova (AD-34, Raiz de composição e versão de regra):** um único `isocentro/composicao.py`, sem Qt, registra todos os módulos, verificações, leitores e capacidades. `run_gui` e `run_varredura` só o chamam. O banco guarda a **versão do app** além da versão do esquema. Concentradora e estação conferem as duas ao abrir, e se divergirem abrem SOMENTE LEITURA (a concentradora não executa). Cada execução grava `versao_app` e `versao_verificacao`.

### P21 [A]: como o avaliador puro recebe dado de outro módulo
- **Unidades:** `modulos/qualidade` (a verificação "máquina com CQ em dia para o plano" precisa de dado do Plano) × `nucleo/motor` (lê "pelos adaptadores", AD-15).
- **Como divergem:** o motor não pode importar a fachada do Plano (AD-2). A Qualidade lê a fachada do Plano dentro do seu comando e passa os dados prontos ao motor. O Plano, em sentido contrário, expõe uma porta "leitor" que o núcleo chama. São dois padrões de entrada. No primeiro, a concentradora não consegue reexecutar a verificação sozinha, porque a leitura está no comando, que só a tela chama.
- **AD apertada (AD-15):** toda verificação declara as suas **entradas** como leitores nomeados (porta do núcleo). Os leitores são fornecidos pelos módulos donos e ligados na raiz de composição (AD-34). O motor monta a entrada e chama o avaliador puro, e a mesma verificação roda igual na estação e na concentradora.

### P22 [M]: banco fora do ar e prazos perdidos
- **Unidades:** `concentradora` × `nucleo/motor`.
- **Como divergem:** com o banco fora (AD-23), uma concentradora simplesmente pula os gatilhos de prazo e de calendário. Outra os executa ao voltar, todos de uma vez, e gera uma rajada de alertas com hora de execução errada. As duas cumprem a regra "sem fila local".
- **AD apertada (AD-23 + AD-30):** gatilhos de tempo são **por janela**, e ao voltar a concentradora executa uma vez por janela que passou, com a data de referência da janela e não a de agora. A idempotência da AD-30 impede execução dupla. O log registra o período em que o banco esteve fora.

---

## Tabela de fechamento

| # | Par | ADs tocadas | Correção |
| --- | --- | --- | --- |
| P1 | plano × tratamento × radioteraficha × esapi_json | AD-3 | **AD-26** entidades de referência no núcleo, chave `Ser` + clínica |
| P2 | plano × qualidade (máquina) | AD-3, AD-13 | AD-26 + "nunca por parecença" generalizado |
| P3 | núcleo × radioteraficha (pessoa) | AD-13, Q7 | AD-13 apertada; `equipe.py` somente leitura |
| P4 | qualidade × seguranca (caminho de gravação) | AD-2, AD-3, AD-15, AD-22 | módulo não importa adaptador; `nucleo.gravar`; mapa de dono |
| P5 | núcleo × documentacao (log) | AD-4, AD-6 | um só log |
| P6 | concentradora × postgres (espelho) | AD-5, AD-17 | **AD-27** cache × registro |
| P7 | radioteraficha × tratamento (migração) | AD-9 | **AD-28** corte de migração, sem gravação dupla |
| P8 | tratamento.consulta × indicadores/tela | AD-3(2), AD-18 | fachada só com valores imutáveis |
| P9 | indicadores × seguranca (log cru) | AD-2, AD-3 | payload opaco |
| P10 | plano × qualidade × esapi_json (verificação) | AD-14 | **AD-29** catálogo com espaço de nome |
| P11 | concentradora × estação (execução) | AD-9 | **AD-30** execução vigente e dono do tempo |
| P12 | qualidade × motor (pendência) | AD-1, AD-3, AD-5 | **AD-31** ciclo de vida do alerta |
| P13 | plano × tratamento (assinatura × versão) | AD-4 | **AD-32** versão de objeto clínico |
| P14 | qualidade.consulta × concentradora (prazo) | AD-14, AD-18 | uma função de vencimento, data do banco |
| P15 | núcleo × variandw × módulos (relógio) | AD-4, AD-6 | **AD-33** tempo |
| P16 | postgres (hash) × núcleo (RLS) | AD-6, AD-12 | corrente global, gatilho `SECURITY DEFINER` |
| P17 | documentacao × software × núcleo (sem clínica) | AD-8, AD-12 | tabela de clínica ou global; sem NULL ou TODAS |
| P18 | concentradora × núcleo (sessão) | AD-4, AD-12 | sem BYPASSRLS; usuário de sistema |
| P19 | plano × tratamento (capacidade) | AD-11 | capacidade declarada com prefixo, por clínica |
| P20 | concentradora × estação (versão e composição) | AD-19, AD-20 | **AD-34** raiz de composição e versão do app |
| P21 | qualidade × motor (entrada) | AD-2, AD-15 | leitores declarados |
| P22 | concentradora × motor (banco fora) | AD-23 | gatilho por janela, recuperação idempotente |

Bloqueantes (B): P1, P4, P6, P10, P11, P16. Os outros podem ser fechados no épico do núcleo, mas antes do primeiro módulo que grava.
