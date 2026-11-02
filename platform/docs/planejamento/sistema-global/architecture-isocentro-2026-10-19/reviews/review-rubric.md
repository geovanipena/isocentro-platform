# Revisão — rubric walker (Good-spine checklist)

- Alvo: `../ARCHITECTURE-SPINE.md` (status draft, 19/10/2026)
- Contexto lido: `../.memlog.md`, `../extrato-codigo.md`, trechos do PRD (FR-3, FR-8, NFR-1 a NFR-10, P9)
- Modo: somente leitura; nada na espinha foi alterado.

## Veredito

A espinha é sólida no paradigma, na direção de dependência e no contrato da verificação, mas ainda deixa abertos pontos em que dois módulos podem divergir: chave do paciente/plano, forma da assinatura, corrente de hash, dono de tabela, fronteira do que vai para o banco. Também se cala sobre ambientes e testes contra PostgreSQL. Não está pronta para virar substrato de construção sem os ajustes altos.

## Item a item do checklist

| Item do checklist | Situação | Achados |
| --- | --- | --- |
| Fixa os pontos reais de divergência e não deixa nenhum de fora | parcial | 1, 2, 3, 4, 6, 13, 14, 15, 16, 20 |
| Cada Rule é aplicável e previne o que diz prevenir | parcial | 4, 5, 6, 8, 19 |
| Nada em Deferred deixa dois módulos divergirem | parcial | 3 (P9 nem consta), 17, 18 |
| Tecnologia verificada e atual | quase | 10, 11 |
| Ratifica o código em vez de contradizê-lo; contradições escritas | parcial | 2, 9 |
| Cobre o spec (PRD) | parcial | 3, 16, 19 |
| Espinha-mãe herdada | não se aplica | — |
| Todas as dimensões decididas, deferidas ou abertas, inclusive o envelope operacional | parcial | 7, 16, 20 |
| Mermaid sintaticamente plausível | sim, com ressalvas | 21, 22, 23 |

## Achados

### Críticos

Nenhum.

### Altos

**1. Falta a chave canônica de paciente, plano e curso** (alto)
- Local: AD-3, Convenções de consistência.
- Evidência: o código identifica o paciente por `FICHA_{NOME}_{REG}` (`registro_json.py:236-371`), o `variandw` por `PatientSer`/`PatientId`, e o plano pelo `SOPInstanceUID` (FR-8). A espinha não diz qual chave cada tabela usa para apontar paciente, curso, plano e máquina. Cada módulo (plano, tratamento, qualidade, segurança) vai escolher sozinho, e os módulos não vão conseguir cruzar dados pelas fachadas.
- Correção: criar uma AD "Identificadores", com a chave de paciente (ex.: `PatientSer` do ARIA + `PatientId` exibido), de curso, de plano (`SOPInstanceUID` + versão) e de máquina, e com a regra de nunca usar o nome como chave.

**2. Não diz o que sai do arquivo para o PostgreSQL; o AD-9 contradiz o código sem dizer**
- Local: AD-9 ("toda gravação compartilhada vai a esse banco"), tabela de Contradições.
- Evidência: hoje gravam no share ou na pasta do paciente `registro_json` (FICHA + PNG/zip), PDFs, `usuarios.json`, `sessoes.json`, `checklist_pre_tratamento.json`, `cadastro_sus.json`, `notas_posicionamento.json`, `inventario_imobilizadores.json` e `datas_relevantes` (extrato §3). A tabela de Contradições cita só `indice.py` e `config_servico.py`. O Radioteraficha migrado continuaria gravando JSON enquanto os módulos novos gravariam no banco. São dois destinos para o mesmo tipo de dado.
- Correção: listar, numa tabela da espinha, cada arquivo gravável de hoje com o destino dele (PostgreSQL / continua na pasta do paciente / fica local na estação) e dizer o que significa "dado compartilhado". Os que ficam em arquivo entram como exceção escrita ao AD-9.

**3. Sem decisão sobre a assinatura (FR-8, FR-20)**
- Local: Invariantes (não há AD); Mapa área → arquitetura (FR-7 a FR-9 → AD-11, AD-13, AD-18); Deferred.
- Evidência: o FR-8 manda gravar usuário, perfil, data/hora, objeto assinado e versão dele. Plano (Aprovação Física, Duplo Check), Qualidade (CQ) e Documentação assinam. A espinha põe "assinatura" no núcleo, mas não fixa a forma do registro, quem o grava nem como ele perde a validade. O P9 (o que invalida uma assinatura) também não está em Deferred.
- Correção: criar uma AD dizendo que a assinatura é um serviço único do núcleo, com tabela única de campos (objeto_tipo, objeto_id, versão_do_objeto, capacidade usada, usuário, perfil, quando) e reautenticação na sessão atual. A invalidação por mudança de versão fica a cargo do motor (gatilho `estado`). Pôr o P9 em Deferred com volta "antes do épico do Plano".

**4. Corrente de hash incompleta: âmbito, forma canônica e verificação**
- Local: AD-4, AD-6, diagrama "Fluxo de gravação".
- Evidência: o AD-6 diz `sha256(hash_anterior || registro)`, mas não diz:
  - se há um único log global ou um por módulo ou tabela;
  - o que é "registro" (a linha de log ou o dado; o diagrama mostra o hash calculado depois dos dois INSERTs);
  - qual é a serialização canônica (ordem dos campos, codificação, formato de data);
  - como o banco serializa (lock consultivo, tabela de cabeça da corrente, SERIALIZABLE).

  O FR-3 exige uma verificação de integridade que aponte o registro e a posição. Quem a escrever em Python terá que reproduzir a serialização do gatilho, que não está fixada.
- Correção: no AD-6, fixar o log como uma tabela única do núcleo, uma corrente só, hash da linha de log com a serialização canônica escrita (ou a função SQL de referência nomeada em `migracoes/`) e a serialização por `pg_advisory_xact_lock` ou linha de cabeça com `FOR UPDATE`. Fixar também a rotina de verificação de integridade (quem roda, quando e onde registra; ex.: a concentradora, todo dia).

**5. O AD-5 não é aplicável como está escrito e o AD-17 o contradiz**
- Local: AD-5, AD-6, AD-17.
- Evidência: o AD-5 diz "o anterior fica marcado substituído" e também "sem UPDATE de conteúdo". Marcar exige UPDATE de um campo ou uma tabela de substituição à parte, e cada módulo pode escolher um caminho. Os papéis do AD-6 negam UPDATE/DELETE só no log, não nas tabelas de dado, e por isso nada no banco impõe o AD-5. Já o AD-17 manda apagar o espelho com 60 dias, o que é DELETE em dado registrado.
- Correção: (a) fixar um só mecanismo: "substituído" deriva de existir um registro posterior que aponta este (`substitui_id`), sem UPDATE. (b) Negar UPDATE/DELETE ao `isocentro_app` também nas tabelas de dado registrado. (c) Declarar o espelho cache descartável, fora do AD-5, de forma explícita.

**6. "Só o dono grava" não tem mecanismo; o teste `ast` não enxerga SQL**
- Local: AD-3 (1), AD-22 ("módulo gravando em tabela de outro dono").
- Evidência: o nome da tabela vive em strings SQL ou em argumento de `nucleo.gravar(registro, ...)`, e uma análise `ast` de imports não descobre de quem é a tabela. Também não há convenção de nomes nem de schema por módulo.
- Correção: fixar um schema PostgreSQL por módulo (`plano.*`, `qualidade.*`, ...) ou um prefixo obrigatório, e um registro tabela→dono no núcleo que o `gravar` confira no ato. O teste de arquitetura passa a conferir a convenção, por exemplo varrendo as migrações e as chamadas de `gravar`.

**7. Envelope operacional sem ambientes e sem testes contra PostgreSQL**
- Local: AD-10 ("SQLite só para `banco_local` offline e testes"), Varredura das dimensões.
- Evidência: gatilho de hash (AD-6), papéis (AD-6), RLS (AD-12) e versão do esquema (AD-19) só existem no PostgreSQL. Testá-los em SQLite não prova nada, e cada módulo pode testar de um jeito. Não há dimensão "Ambientes" (desenvolvimento, homologação não clínica, produção), embora o `escopo.md` exija validação em ambiente não clínico e o CI rode em `windows-latest` sem banco.
- Correção: criar uma AD "Ambientes e testes": banco de homologação separado do clínico, testes de integração contra PostgreSQL 18 (serviço no CI ou instância local descartável) para gatilho, RLS e papéis, e SQLite restrito ao cache de leitura. Pôr a linha "Ambientes" na Varredura das dimensões.

**8. O AD-15 recria o problema que o AD-17 resolve: JSON clínico em claro no share**
- Local: AD-15, AD-17 (Prevents).
- Evidência: o AD-17 tira o espelho do share porque ele é "dado clínico em claro em JSON no share, fora do backup e sem RLS". O AD-15 põe o JSON do avaliador ESAPI justamente numa pasta do share, sem dizer quanto tempo ele fica nem quem o apaga.
- Correção: no AD-15, dizer que o JSON é apagado (ou movido para quarentena) logo depois da importação, com registro no log; que a pasta tem ACL restrita; e que o JSON leva só o identificador do plano, não o nome do paciente.

**9. Concentradora: a espinha não ratifica o que já roda**
- Local: AD-9, AD-21, Deferred ("concentradora como serviço Windows ou tarefa agendada"), diagrama de topologia.
- Evidência: o extrato mostra a concentradora em `clinica-python01`, como Tarefa Agendada (`run_varredura.py:1-13`; `DESTINO.md:32-37`; `INSTALAR_CONCENTRADORA.md`). A espinha diz "servidor da clínica" sem nomear a máquina, adia a forma de execução como se nada existisse e não registra isso nas Contradições. Também não fica claro se o PostgreSQL, a concentradora e o `\\fileserver` estão na mesma máquina.
- Correção: ratificar "Tarefa Agendada em `clinica-python01`" como estado atual (ou registrar a mudança nas Contradições), nomear a máquina do PostgreSQL e manter em Deferred só o que muda de fato.

### Médios

**10. Cofre de credenciais e TLS sem tecnologia verificada** (AD-25)
- Ler o Gerenciador de Credenciais do Windows em Python exige `keyring` ou `pywin32`/ctypes, e nenhum deles está na Stack nem no inventário SOUP.
- Faltam o `sslmode` (`verify-full`?), a distribuição do certificado da CA e onde fica a credencial do `isocentro_concentradora` no servidor.
- A variante do psycopg (`psycopg[binary]` com libpq embutida, ou libpq do sistema) não está fixada, e isso pesa no empacotamento PyInstaller.
- Correção: fixar a biblioteca, a versão, o `sslmode` e a variante do psycopg; pôr tudo no SOUP.

**11. Stack com versões não fixadas**
- PyInstaller está sem versão, Python sem patch e o CI em `windows-latest` (flutuante); "PostgreSQL 18.x" é aceitável como linha.
- A Stack diz que o CI roda Windows "na suíte e no empacotamento", mas o lint roda em ubuntu (`testes.yml`). O `lint_spine.py` vai acusar.
- Correção: fixar PyInstaller e Python (ex.: 3.12.x exato do `requirements`), e o runner (ex.: `windows-2025`) ou declarar que é flutuante.

**12. Raiz de composição e acesso de módulo ao adaptador concreto não fixados** (AD-2)
- O AD-2 proíbe núcleo → adaptador concreto, mas não proíbe módulo → adaptador concreto, e não diz quem liga portas a adaptadores (`run_gui.py`/`run_varredura.py`?).
- Correção: "só os pontos de entrada instanciam adaptadores; módulo fala só com portas do núcleo", e incluir isso no teste do AD-22.

**13. Nomes de capacidade em lista aberta** (AD-11)
- As capacidades aparecem como "ex.", e cada módulo pode inventar um nome. Também falta dizer como a concentradora (sem usuário) se autoriza.
- Correção: as capacidades são declaradas num registro do núcleo, com nome `verbo_objeto`, e o módulo não usa capacidade sem declará-la; a concentradora age com identidade de sistema própria, registrada no log.

**14. RLS: mecanismo e perfis transversais não fixados** (AD-12)
- Não diz como a sessão leva as clínicas (GUC `isocentro.clinicas` com `SET LOCAL` em cada transação?), o que é crítico com conexão reaproveitada.
- Também não diz que política o `isocentro_concentradora` usa (vê tudo?) nem como o físico responsável vê as três clínicas (NFR-6).
- Correção: fixar o nome da GUC, `SET LOCAL` por transação e a política de cada papel.

**15. Fonte do relógio** (AD-4, AD-14, gatilho `prazo`)
- O "quando" do log, dos prazos e das assinaturas pode vir do relógio da estação ou do banco; com várias estações, a ordem e os prazos divergem.
- Correção: o tempo de registro vem do banco (`clock_timestamp()`/`now()`), em `timestamptz`, exibido em America/Sao_Paulo.

**16. Desempenho e capacidade sem envelope** (NFR-5)
- O NFR-5 (30 s por plano, 3 s por painel) não está em `binds` nem em AD. Faltam número de estações e conexões simultâneas e limites de consulta ao `variandw`.
- Correção: deferir com volta explícita ou fixar o orçamento por camada (ex.: limite de 6 s no `variandw` já existe em `capa_db.py:56`).

**17. Q7 (equipe por estação) adiado permite divergência de identidade**
- Médicos e físicos gravados em `~/.isocentro_*.json` por estação são a base de quem assina. Adiar isso sem regra provisória deixa duas estações com equipes diferentes enquanto as assinaturas (achado 3) já seriam gravadas no banco.
- Correção: regra provisória "assinatura usa só o usuário do `auth`/banco, nunca a equipe local", ou trazer o Q7 para antes do épico do Plano.

**18. G1 (classe 62304) adiado com afirmação não sustentada**
- "A arquitetura permite classificar por módulo", mas o núcleo é compartilhado: pela IEC 62304 (segregação, 5.3.5), ele herda a classe mais alta dos módulos que o usam, salvo segregação justificada.
- Correção: escrever isso no item de Deferred, porque muda o rigor do núcleo desde o primeiro épico.

**19. Retenção do log diferente da exigida** (AD-24 × FR-3)
- O FR-3 pede retenção de "pelo menos 10 anos após o descarte do software"; o AD-24 guarda o dump mensal por 10 anos, contados a partir do dump.
- Correção: no AD-24, retenção "até 10 anos após o descarte do software", com o log nunca expurgado do banco enquanto o software estiver em uso.

**20. Login e identidade com o banco fora** (AD-23)
- Se `usuarios.json`/`sessoes.json` forem para o PostgreSQL (achado 2), o modo somente leitura não terá como autenticar. Se ficarem no share, há dois destinos de identidade.
- Correção: decidir onde vivem usuários e sessões e o que o modo somente leitura exige (ex.: login local em cache, sem assinatura).

**21. "Dado compartilhado" e "versão do dado de origem" sem definição** (AD-4, Convenções)
- Cada módulo vai preencher "versão da origem" de um jeito (degrau + data? UID? hash do JSON ESAPI?).
- Correção: fixar a forma (degrau, data da leitura, identificador de versão da fonte), alinhada ao AD-14 ("entrada registrada com degrau, data e versão").

**22. Ciclo de vida do alerta e das pendências não fixado**
- O núcleo tem "alerta e pendências", mas não há estados (aberto, reconhecido, resolvido), nem quem reconhece, nem a ligação com a pendência do care path (`atividades_db`).
- Correção: uma linha no AD-14, ou uma AD própria, com os estados e a regra "alerta só nasce do motor".

### Baixos

**23. Diagrama de sequência contradiz o texto em dois pontos**
- `N-->>T` responde à tela pulando o comando do módulo.
- `B->>B: gatilho calcula hash = sha256(hash_anterior || registro)` reforça a ambiguidade do achado 4.
- A sintaxe é válida (`participant X as ...`, `alt/else/end`, `->>`, `-->>`).
- Correção: `N-->>M-->>T`; trocar "registro" por "linha de log".

**24. Diagrama de dependência: plausível, com ressalva de leitura**
- `MOD -. "..." .-x MOD` é válido (link pontilhado com rótulo e ponta `x`) e `UI -. "..." .-x ADP` também, mas o laço de MOD sobre si mesmo fica ilegível na renderização.
- O diagrama não mostra que a fachada é parte do módulo nem a relação módulo → porta → adaptador.
- Correção: nó `MOD2["outro módulo"]` como alvo da proibição.

**25. Diagrama de topologia: plausível, mas incompleto**
- Arestas a partir de subgraph (`EST -->|...| DW`) exigem Mermaid 9.4 ou superior; `C#` dentro do rótulo entre aspas não forma entidade `#...;`, então passa.
- Faltam:
  - backup para `\\fileserver` (AD-24);
  - distribuição do exe pelo share;
  - concentradora → DICOM e CSV;
  - máquina física de cada caixa (achado 9).
- Correção: acrescentar essas arestas e nós.

**26. AD-10 "banco_local offline" pode ser lido como fila local, contra o AD-23**
- Correção: "banco_local = cache de leitura do `variandw`, nunca destino de gravação".

**27. `binds` do frontmatter incompleto**
- Faltam NFR-5 e NFR-8; os FR-10 a FR-42 só aparecem no Mapa. Também falta registrar a contradição "classe A atribuída a `dominio/ritmo`, que não existe" (extrato §8 b.3), que pesa no G1.
- Correção: completar o `binds` ou dizer que o Mapa é a fonte.

**28. AD-7 mistura regra com tarefa**
- "README e `persistent_fact` passam a dizer isso" é tarefa, não regra.
- Correção: mover para Contradições (onde já consta) e deixar no AD só a regra.

## Contagem

- Críticos: 0
- Altos: 9 (achados 1 a 9)
- Médios: 13 (achados 10 a 22)
- Baixos: 6 (achados 23 a 28)

Tecnologia: as versões do memlog (PostgreSQL 18.6 de 13/08/2026, que bate com o calendário trimestral de versões menores; psycopg 3.3.4; PyQt5 5.15.11) foram aceitas como conferidas em 19/10/2026 e não foram reconferidas na web nesta revisão.
