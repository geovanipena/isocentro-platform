---
alvo: ../ARCHITECTURE-SPINE.md
contexto: ../.memlog.md
lentes:
  - docs/qms/revisao-clinica.md (regras 1 a 9)
  - segurança da informação / LGPD para estágio regulado (IEC 62304, NN-6.10, RDC 657, RDC 20)
data: '2026-10-19'
revisor: agente (revisão adversária, somente leitura)
---

# Revisão clínica e de segurança — Espinha de arquitetura ISOCENTRO

**Veredito:** a espinha é sólida no que diz respeito à leitura do ARIA, ao contrato da
verificação e à transação dado + log. Ainda não serve como base para o estágio regulado:
o backup com dado clínico não tem cifra definida, a autoria e a capacidade dependem só do
cliente, que usa uma credencial de banco compartilhada, e a classe IEC 62304 e a ligação aos
riscos ainda faltam.

Gravidades: **crítico** (bloqueia o início da construção do núcleo e do banco),
**alto** (resolver antes do 1º épico que grava dado clínico),
**médio** (resolver no épico correspondente), **baixo** (observação).
A coluna "regra" usa os números de `docs/qms/revisao-clinica.md`; "S" indica a lente de
segurança/LGPD.

Documentos de base conferidos: `docs/qms/escopo.md`, `docs/qms/riscos.md` (só RD-1 a RD-5),
`docs/qms/classificacao-62304.md` (só Radioteradados e `dominio/ritmo`, ambos classe A),
`prd-isocentro-2026-10-16/prd.md` (NFR-2, FR-3, FR-28, FR-29, §13).

---

## Críticos

### C-1 — Backup com dado clínico sem cifra, sem controle de acesso e sem guarda de chave

- **Local:** AD-24; AD-21; AD-17 ("backup junto").
- **Evidência:** "o `pg_dump` diário vai para outra máquina (`\\fileserver`) e fica 30 dias; um dump
  por mês é guardado 10 anos em mídia separada, fora do servidor." Em nenhum ponto o texto diz
  que o dump é cifrado, quem tem acesso a `\\fileserver`, que mídia é usada ou onde ela fica guardada.
- **Por que é crítico:** o dump contém o banco inteiro: espelho do `variandw`, incidentes com
  texto livre e dose estimada (FR-29), CQ, assinaturas e a tabela de usuários com hashes PBKDF2.
  Por isso fura o RLS (AD-12) e todas as capacidades (AD-11). Se o dump ficar em claro num share
  que já é de uso geral (o mesmo `\\fileserver` que guarda o espelho JSON hoje), qualquer pessoa com
  acesso ao share lê o dado sensível de saúde (LGPD art. 5º II e art. 46). O mesmo vale para uma
  mídia removível guardada 10 anos. A própria espinha recusa "dado clínico em claro em JSON no
  share" (AD-17, Prevents) e depois cria o mesmo problema, em escala maior, no backup.
- **Regra:** 7, S.
- **Correção:** criar uma decisão "Backup cifrado". O dump é cifrado antes de sair do servidor
  (por exemplo, `pg_dump -Fc | age`/`gpg` com chave pública, para que o servidor só cifre e não
  decifre). A pasta de destino em `\\fileserver` aceita escrita só da conta de serviço do backup e
  leitura só do papel de restauração. A chave privada tem guarda dupla (cofre físico + segunda
  pessoa nomeada), porque uma chave perdida em 10 anos deixa o backup ilegível, e o AD-21 põe uma
  só pessoa na operação. A decisão diz que mídia é usada, onde fica guardada (fora do prédio do
  servidor?), como é etiquetada e qual checksum acompanha cada dump. O teste de restauração mensal
  (AD-21) passa a usar o dump cifrado e decifrado por quem tem a guarda.
- **Pergunta ao físico:** quem, além de você, pode decifrar e restaurar o backup? Onde ficam
  fisicamente a mídia de 10 anos e a chave?

### C-2 — Autoria, assinatura e capacidade conferidas só no cliente, com uma credencial de banco compartilhada

- **Local:** AD-6 ("Login das pessoas continua no app (PBKDF2)"); AD-11; AD-12; AD-25; Fluxo de
  gravação.
- **Evidência:** todas as estações conectam como `isocentro_app` (AD-25), com a senha "no cofre de
  credenciais do Windows da estação". O núcleo "confere a capacidade no ato" (AD-11), e as clínicas
  da sessão são "definidas pelo núcleo no login" (AD-12). O campo "quem" da linha de log é preenchido
  pelo app (AD-4). O banco não sabe quem é a pessoa.
- **Por que é crítico:** o cofre do Windows (DPAPI) entrega a senha a qualquer processo que rode na
  sessão do usuário. Com ela, qualquer pessoa que use a estação pode abrir `psql` ou um script e:
  (a) definir a variável de sessão de clínica e ler as três clínicas, passando por cima do RLS;
  (b) fazer INSERT de registro e linha de log com qualquer "quem", forjando uma Aprovação Física ou
  um Duplo Check (NN-6.10 art. 17, IV); (c) se a tabela de capacidades e a de usuários puderem ser
  gravadas por `isocentro_app`, criar um usuário `admin`; (d) ler os hashes PBKDF2 para quebra
  offline. A corrente de hash (AD-6) protege contra UPDATE e DELETE, mas não contra INSERT forjado.
  Uma linha forjada entra na corrente com hash válido e ganha aparência de íntegra. Isso compromete
  o requisito de discernir registro alterado (RDC 657 art. 5º; FR-3) e a validade das assinaturas.
  O AD-12 já diz que protege "contra erro"; isso pode ser aceito para visibilidade, mas não para
  assinatura e autoria.
- **Regra:** 8, S.
- **Correção:** escolher e registrar uma das duas saídas.
  (1) A identidade da pessoa chega ao banco: um papel de banco por pessoa, ou autenticação
  integrada ao domínio (GSSAPI/SSPI, com contas CLINICA) num papel que herda de `isocentro_app`.
  Assim `current_user` e `session_user` são preenchidos pelo banco e o gatilho do log grava "quem"
  a partir deles, não do app. O RLS também passa a usar a pessoa, e não uma variável que o cliente
  define.
  (2) Toda gravação passa por funções `SECURITY DEFINER` que conferem capacidade e assinatura
  (senha conferida no banco). `isocentro_app` só pode `EXECUTE`, sem INSERT direto nas tabelas.
  Nos dois casos, as tabelas de usuários, capacidades e vínculo ARIA (AD-13) não podem ser gravadas
  por `isocentro_app`. A assinatura passa a guardar o hash do conteúdo assinado. Se a escolha for
  manter o risco, ele vira uma linha em `riscos.md` escrita pelo físico, com o controle
  compensatório declarado.
- **Pergunta ao físico:** as estações usam login nominal no domínio ou uma conta genérica? Você
  aceita que uma pessoa com acesso à estação consiga registrar uma assinatura em nome de outra?

---

## Altos

### A-1 — Corrente de hash recomputável pelo dono, sem âncora externa e sem segregação de funções

- **Local:** AD-6; AD-19; AD-21.
- **Evidência:** `isocentro_dono` tem DDL. O físico instala, mantém, aplica migrações e também
  assina. A corrente é `sha256(hash_anterior || registro)` dentro do próprio banco.
- **Problema:** com DDL (ou como superusuário `postgres`), dá para desligar o gatilho, editar uma
  linha e recalcular toda a corrente a partir dela. A verificação continua passando. Nada fora do
  banco guarda o hash da ponta. A mesma pessoa administra o banco e assina registros clínicos.
- **Regra:** 8, S.
- **Correção:** ancorar a ponta da corrente fora do banco: a concentradora grava todo dia o
  `(id, hash)` da ponta num destino só de acréscimo que `isocentro_dono` não controla. Pode ser o
  próprio dump cifrado, um e-mail ao SPR/gestão ou um registro impresso e assinado no mês. Separar o
  superusuário `postgres` (guardado em cofre, uso registrado) do `isocentro_dono`. Registrar no log
  toda migração aplicada, com quem aplicou. Declarar no texto que a segregação é limitada pela
  operação de uma pessoa só (AD-21) e indicar quem audita.

### A-2 — Retenção do backup não atende às exigências do próprio PRD

- **Local:** AD-24, comparado com PRD FR-3 ("log retido por pelo menos 10 anos após o descarte do
  software", RDC 657 art. 5º §3º) e FR-28 ("registros de CQ guardados por toda a vida útil do
  equipamento", RDC 20 8.1(b); "cópia independente", NN-6.10 art. 71, IX).
- **Evidência:** "um dump por mês é guardado 10 anos".
- **Problema:** um dump guardado 10 anos a partir da data em que foi feito não cobre "10 anos após o
  descarte" nem "a vida útil do acelerador". O dump de 2026 vence em 2036, enquanto o software e a
  máquina podem continuar em uso. Também falta a legibilidade em 10 anos: um dump `-Fc` do PG 18
  precisa de um `pg_restore` compatível, que daqui a 10 anos pode não estar disponível. E falta dizer
  como o acesso a esses dumps será controlado durante a guarda.
- **Regra:** 8, S.
- **Correção:** a retenção passa a ser "o mais longo entre 10 anos após o descarte do software e a
  vida útil do equipamento a que o registro se refere". Isso pode ser feito guardando sempre o dump
  mais recente do mês, sem expirar enquanto o sistema existir, mais o dump final do descarte. Guardar
  junto os instaladores do PostgreSQL e do ISOCENTRO da versão, ou uma exportação em formato aberto
  (SQL texto ou CSV + hashes). Fazer o teste de leitura de um dump antigo uma vez por ano.
- **Pergunta ao físico:** você confirma qual retenção vale para cada tipo de registro (log, CQ,
  incidente, espelho)?

### A-3 — JSON do avaliador ESAPI no share sem integridade, sem controle de acesso e com dado em claro

- **Local:** AD-15; topologia ("ECL → grava JSON → ESJ"; "CON → importa e valida").
- **Evidência:** "grava JSON com esquema versionado numa pasta do share; a concentradora importa,
  valida e grava". A validação descrita só confere o esquema.
- **Problema:** (a) integridade clínica: qualquer pessoa com escrita na pasta pode colocar ou alterar
  um JSON bem formado que diga `conforme` para um plano, e a concentradora o importa como resultado
  verdadeiro. (b) privacidade: o JSON leva ID do paciente e dados do plano em claro no share, sem
  prazo de limpeza. É o mesmo padrão que o AD-17 removeu no espelho. (c) não se sabe quem rodou o
  script.
- **Regra:** 1, 7, 8, S.
- **Correção:** dar à pasta uma ACL própria, com escrita só pela conta das estações Eclipse e
  leitura só pela concentradora. Cada JSON leva usuário do Eclipse, estação, versão do script e hash
  do conteúdo. A importação move o arquivo para "importado" e apaga ou cifra o original num prazo
  declarado, registrando no log. Avaliar ainda HMAC com chave da estação Eclipse, ou gravação pelo
  script direto numa pasta local que a concentradora busca.

### A-4 — Resultado ESAPI importado pode estar defasado em relação ao plano atual

- **Local:** AD-14 ("Entrada registrada com degrau, data e versão"); AD-15.
- **Evidência:** a versão da entrada é registrada, mas a espinha não diz que é comparada com o
  estado atual do plano no ARIA/Eclipse antes de o resultado contar.
- **Problema:** se o plano for alterado depois da exportação do JSON, o `conforme` antigo aparece
  como verificação do plano novo na Aprovação Física ou no Duplo Check. É um número errado que chega
  à sala de tratamento.
- **Regra:** 1, 3.
- **Correção:** o JSON leva a identificação da versão do plano (UID do RT Plan, data de modificação
  e estado de aprovação). Antes de exibir ou de assinar, o motor compara esses dados com o
  `variandw`/DICOM. Se forem diferentes ou se não houver como comparar, o resultado é
  `indeterminado`, com o motivo "plano mudou depois da verificação".
- **Pergunta ao físico:** que campo do ARIA identifica, sem ambiguidade, a versão do plano que foi
  aprovada?

### A-5 — Classe IEC 62304 ausente para o núcleo e os módulos novos; a segregação no monólito não está justificada

- **Local:** Deferred (G1); "Varredura das dimensões" ("Classe de segurança… Deferred"); AD-1.
- **Evidência:** `classificacao-62304.md` só classifica Radioteradados e `dominio/ritmo` (A). A
  espinha diz que "a arquitetura permite classificar por módulo", mas todos os módulos rodam no
  mesmo processo e compartilham o núcleo, o log e a assinatura.
- **Problema:** a IEC 62304 (4.3 e 5.3.5) só aceita classe menor para um item se houver segregação
  efetiva e justificada. Num executável único, uma falha do módulo `plano` (provável classe B ou C,
  porque alimenta a Aprovação Física) pode afetar o núcleo, e o contrário também. Se a segregação não
  for demonstrada, o núcleo e tudo o que o compartilha herdam a classe mais alta. Isso muda o esforço
  de verificação de todo o MVP. A regra 9 manda apontar, não decidir.
- **Regra:** 9.
- **Correção:** antes do 1º épico do núcleo (e não só do Plano), o físico classifica `nucleo`,
  `adaptadores/*`, `interface` e cada módulo. A espinha ganha uma decisão de segregação que diz o que
  isola um item do outro (fachada somente leitura, avaliador puro, teste AD-22) e o que não isola
  (mesmo processo e mesma memória). Se não houver segregação, deve declarar que o núcleo tem a classe
  do módulo de classe mais alta.
- **Pergunta ao físico:** que classe tem o núcleo, que guarda a assinatura da Aprovação Física?

### A-6 — Perigos novos da arquitetura sem item em `riscos.md` e sem forma de verificação

- **Local:** todas as AD; `riscos.md` (só RD-1 a RD-5, todos do Radioteradados).
- **Evidência:** nenhuma AD cita item de risco. A espinha cria perigos que não existiam antes: banco
  central fora do ar (AD-23); visibilidade de clínica errada (AD-12); importação de JSON ESAPI
  (AD-15); restauração que traz dado antigo; quebra ou forja da corrente (AD-6); espelho vencido
  apresentado como atual (AD-17); app com esquema diferente do banco (AD-19).
- **Regra:** 8 (e PRD NFR-8).
- **Correção:** a espinha lista esses perigos numa seção "Perigos introduzidos pela arquitetura",
  sem preencher S, O e D, como entrada para o físico escrever as linhas. Cada AD que funciona como
  controle aponta a verificação: teste de corrente após restauração (FR-28), teste RLS por papel,
  teste de esquema divergente → somente leitura, teste de JSON adulterado → `erro`.

---

## Médios

| ID | Local | Evidência | Regra | Correção |
| --- | --- | --- | --- | --- |
| M-1 | AD-25 | "TLS obrigatório", sem dizer como é imposto | S | `sslmode=verify-full` com CA interna distribuída às estações; `pg_hba.conf` só com `hostssl` + `scram-sha-256`, restrito às sub-redes das estações e ao localhost da concentradora; `listen_addresses` restrito; firewall do servidor. Declarar a renovação do certificado no roteiro do AD-21. |
| M-2 | AD-25, AD-9, AD-16 | Não diz onde fica a credencial de `isocentro_concentradora` nem como estações e concentradora autenticam no `variandw` (hoje `runas /netonly` com conta de domínio) | S | Conta de serviço dedicada para a concentradora, com credencial no cofre do serviço e não do usuário; conta de leitura do `variandw` nominal ou de serviço, com menor privilégio; `Encrypt=yes` no ODBC do `variandw`; troca periódica de senha registrada. |
| M-3 | AD-16, AD-17 (CSV "segue como hoje") | Relatórios exportados do 3º degrau ficam em claro no share | 7, S | ACL da pasta CSV restrita aos perfis que usam a Capa; prazo de guarda declarado; avaliar levar o CSV também para o PostgreSQL, como foi feito com o espelho. |
| M-4 | Ausente (PRD FR-29 "relatório exportado sai sem identificação"; RD-3 supressão < 5) | Nenhuma AD diz onde fica a exportação sem identificação, nem quem a impõe | 7, 8, S | Decisão: toda exportação sai por uma única porta do núcleo (`exportar`), que aplica pseudonimização ou supressão e `varrer_identidade` antes de gravar, com teste automatizado. Nenhum módulo gera arquivo de saída por conta própria. |
| M-5 | Convenções ("Logging técnico") | Cobre o logging do Python, mas não o do servidor | 7, S | Configurar o PostgreSQL com `log_statement=none` (ou `ddl`) e `log_min_error_statement` que não registre parâmetros com dado de paciente; rotação e ACL do diretório de log; incluir no roteiro do AD-21. |
| M-6 | AD-4 (log só de gravação) | Não há trilha de leitura de dado sensível | S (LGPD art. 37, 46) | Decidir se a leitura de incidente, dose estimada e dado clínico identificado gera linha de log de acesso (quem viu o quê). Registrar a base legal e um RIPD (LGPD art. 38) para o banco central, com o encarregado indicado. |
| M-7 | AD-17 ("limpeza agendada" em 60 dias) × AD-5 ("Sem … DELETE em dado registrado") × AD-24 (dump de 10 anos) | A limpeza é um DELETE que o AD-5 proíbe, e o espelho de 60 dias continua 10 anos nos dumps | 7, S | Declarar o espelho como exceção explícita do AD-5 (cache, não registro). Decidir se o espelho fica fora do dump de longa guarda (esquema separado, excluído por `--exclude-schema`), por minimização (LGPD art. 6º III). |
| M-8 | AD-23 ("registros feitos em papel e lançados depois") | O "quando" do log passa a ser a hora do lançamento | 1, 8 | O registro ganha "quando ocorreu" (informado, com a origem "papel") separado de "quando foi gravado" (do banco), e a tela anuncia o lançamento tardio. O formulário de papel de contingência deve estar definido e guardado. |
| M-9 | Contradições ("`escopo.md` limita a gravação…"), Q8 em Deferred | A espinha adota a gravação no banco central antes de o `escopo.md` (fato para os agentes) registrar isso | 2, 7 | Atualizar o `escopo.md` (Fronteiras: "Grava o que produz") antes do 1º épico que grava no banco. Até lá, as histórias que gravam no banco contradizem o escopo vigente. |
| M-10 | "O Radioteraficha atual migra para `modulos/radioteraficha` aos poucos"; AD-18 | A espinha não diz que a migração preserva o papel impresso | 4 | Regra: a migração de módulo que gera PDF não muda campo, ordem, texto ou geometria sem aviso explícito; comparar com PDFs de referência (golden) antes e depois de cada passo. |
| M-11 | AD-10 ("PostgreSQL e psycopg entram no inventário SOUP"); Stack | Só dois itens são citados como SOUP, sem requisitos | 8, 9 | Todo item da tabela Stack entra no inventário SOUP (IEC 62304 5.3.3/5.3.4/7.1.2), com versão, função exigida, requisito de hardware/software e anomalias conhecidas consultadas. Incluir também os instaladores e o runtime do Windows/ODBC. |

---

## Baixos

| ID | Local | Evidência | Regra | Correção |
| --- | --- | --- | --- | --- |
| B-1 | AD-15 ("C#, somente leitura") | Não diz como se comprova que o avaliador ESAPI não escreve (PRD NFR-1: "a entrega confere que ele não declara escrita") | 2 | Citar o mecanismo: o script sem `[assembly: ESAPIScript(IsWriteable = true)]`, em DLL separada das graváveis, com conferência automática no empacotamento. |
| B-2 | AD-16 (DICOM por C-MOVE) | O tráfego DICOM na rede vai em claro | 7, S | Registrar como risco aceito na LAN do serviço ou avaliar DICOM TLS; restringir os AE titles aceitos pelo DB Daemon. |
| B-3 | AD-23 × AD-17 | Com o PostgreSQL fora, o 2º degrau (espelho) também fica indisponível; a espinha só cita `variandw`/DICOM | 3 | Dizer que, com o banco fora, a cadeia de degraus vira `variandw` → CSV e que a tela anuncia isso. |
| B-4 | AD-14, módulos | A espinha não trata a máquina certa nem a origem das tolerâncias | 5, 6 | Sem problema nesta altitude. A espinha só registra que a tabela de feixe é da máquina, ligada por ID cadastrado e nunca por nome, e que a tolerância leva a referência e o estado de calibração TG-218. Os detalhes ficam no módulo Plano/Qualidade. |
| B-5 | AD-21 ("teste de restauração mensal registrado no log") | O registro vai para o banco que está sendo testado | 8 | Restaurar numa instância separada e registrar o resultado (contagem, verificação da corrente, hash da ponta comparado com a âncora do A-1) no banco de produção e no roteiro. |
| B-6 | AD-9 / AD-12 ("quem tem acesso ao servidor") | A espinha não diz quem tem login administrativo no servidor da clínica nem quem pode copiar o diretório de dados do PostgreSQL | S | Listar as contas administrativas do servidor (TI do Clinica, físico), exigir disco do servidor cifrado (BitLocker) e registrar o acesso administrativo. Hoje o AD-12 reconhece o limite, mas não diz quem está dentro dele. |

---

## Contagem

- Críticos: 2 (C-1, C-2)
- Altos: 6 (A-1 a A-6)
- Médios: 11
- Baixos: 6
- Bloqueantes pelo critério do `revisao-clinica.md`: os 2 críticos e os altos A-4 e A-5.
  Nenhuma AD grava no ARIA, no `variandw` ou nos relatórios exportados, então a regra 2 não tem
  bloqueante.

## Pontos fortes (não mexer)

- AD-16: `ApplicationIntent=ReadOnly` + `readonly=True` + gargalo único `_consultar`, com degrau e
  data anunciados.
- AD-4 + AD-23: um só gravador, transação dado + log e nenhuma fila local, o que mantém a corrente
  coerente.
- AD-17: o espelho sai do JSON em claro no share.
- AD-19: esquema divergente → somente leitura, sem migração feita pelo app.
- AD-13: vínculo ARIA ↔ ISOCENTRO por tabela, nunca por parecença.
