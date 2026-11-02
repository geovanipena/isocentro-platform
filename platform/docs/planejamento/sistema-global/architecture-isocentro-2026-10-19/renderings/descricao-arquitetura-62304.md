# Descrição da arquitetura de software — ISOCENTRO

| Campo | Valor |
| --- | --- |
| Documento | Descrição da arquitetura de software para o dossiê regulatório |
| Referência normativa | IEC 62304:2006 + A1:2015, §5.3 (projeto arquitetural); RDC ANVISA 657/2022; CNEN NN-6.10; Lei 13.709/2018 (LGPD) |
| Produto | ISOCENTRO (sistema global de radioterapia do serviço) |
| Data | 19/10/2026; revisão de 22/10/2026 (AD-38 a AD-41: camada `rt`, classe e revisão por módulo, manifesto, repositórios vizinhos); classes de 26/10/2026 (G1, AD-35) |
| Estado | Rascunho, derivado da espinha de arquitetura em estado `draft` |
| Fontes | `ARCHITECTURE-SPINE.md`, `.memlog.md`, `reviews/review-clinica-seguranca.md` (pasta `architecture-isocentro-2026-10-19`); `docs/qms/classificacao-62304.md`, `escopo.md`, `riscos.md`, `revisao-clinica.md` |
| Responsável pelas decisões clínicas | Físico responsável (Geovani Pena) |

Convenções: "AD-n" é uma decisão de arquitetura da espinha. "PENDENTE" marca um item que o dossiê exige e que ainda não foi decidido; ao lado vem o item da seção Deferred da espinha (ou o achado da revisão) que o encerra, e "Volta" indica quando o item será decidido. Nada neste documento substitui a classificação de segurança e a análise de risco, que são do físico responsável.

---

## 1. Identificação e escopo

### 1.1 Objeto

Este documento descreve a arquitetura do ISOCENTRO inteiro: o núcleo (motor de verificação), a interface (shell) e os 9 módulos verticais, os adaptadores para sistemas externos e a concentradora (processo sem tela). Atende à IEC 62304 §5.3: identificação dos itens de software (§5.3.1), interfaces entre itens e com sistemas externos (§5.3.2), requisitos de SOUP (§5.3.3, §5.3.4) e segregação necessária ao controle de risco (§5.3.5).

### 1.2 Finalidade do sistema

O ISOCENTRO monta documentos que vão para a sala de tratamento (ficha técnica, capa, mapa de frações, alta e página de imagens, em PDF), executa verificações sobre o plano e o tratamento e registra assinaturas (Aprovação Física, Duplo Check), controle de qualidade, incidentes e indicadores do serviço (`escopo.md`; espinha, "Mapa área → arquitetura").

### 1.3 Fronteiras

| Fronteira | Regra | Fonte |
| --- | --- | --- |
| ARIA, `variandw` e DICOM | Somente leitura; nenhum módulo grava no sistema clínico de registro | AD-16; `escopo.md` |
| Eclipse | O avaliador ESAPI usado pelo ISOCENTRO (C#) é somente leitura e grava apenas um JSON numa pasta do share | AD-15 |
| Dado de paciente | Não sai da rede do serviço (nem para log, repositório, terceiros ou IA) | AD-7 [ADOPTED], NFR-2 |
| Unidades | `CEL`, `BET`, `DUO`; SAT fora do MVP | AD-8 [ADOPTED] |
| Gravação | Todo estado no PostgreSQL central; PDFs e imagens na pasta do paciente, com hash e caminho no banco | AD-9, AD-10 |

**PENDENTE (Q8 / M-9):** o `escopo.md` vigente ainda limita a gravação "à pasta do paciente e ao lado do app" e não registra o banco central. Volta com o Update do PRD / G8, antes do 1º épico que grava no banco.

**PENDENTE (Q1 / G8):** perfis de usuário. O `escopo.md` tem a tabela de usuários vazia; o código tem 7 papéis, o PRD (FR-7) 5 perfis e a UX 7 perfis. Volta no Update do PRD.

---

## 2. Visão geral e paradigma

### 2.1 Paradigma

Monólito modular com portas e adaptadores (AD-1). Um só executável e um só código. O núcleo não tem conhecimento de radioterapia; cada módulo é um conjunto de verificações sobre o núcleo. Não há carregamento de plug-in em tempo de execução. Alternativas rejeitadas: camadas horizontais e plug-ins em tempo de execução.

### 2.2 Camadas

| Camada | Pacote | Conteúdo |
| --- | --- | --- |
| Núcleo | `isocentro/nucleo/` | motor de verificação, catálogo, execução, log encadeado, alerta, assinatura, identidade, entidades de referência, exportador, portas |
| Radioterapia comum | `isocentro/rt/` | lê e modela objetos de RT já lidos (geometria IEC 61217, cortes, DVH como números); sem veredito, sem estado, sem I/O, sem dado do serviço (AD-38) |
| Módulos verticais | `isocentro/modulos/<modulo>/` | 9 módulos; cada um com verificações, comandos, fachada de consulta (`consulta.py`) e `MANIFESTO` (AD-40) |
| Raiz de composição | `isocentro/composicao.py` e `interface/composicao.py` | lista explícita dos módulos (a primeira, usada pelo app e pela concentradora) e das telas (a segunda, só no app) (AD-40) |
| Adaptadores | `isocentro/adaptadores/` | `variandw`, `dicom`, `postgres`, `esapi_json`; implementam as portas do núcleo |
| Interface | `isocentro/interface/` e `isocentro/interface/modulos/<modulo>/` | shell Qt e telas de módulo |
| Concentradora | `run_varredura.py` | mesmo código, empacotada sem Qt; Tarefa Agendada em `clinica-python01` |
| Migrações | `migracoes/` | arquivos `.sql` numerados, aplicados pelo papel `isocentro_dono` |

### 2.3 Direção de dependência

Regra (AD-2): `interface → modulos → nucleo ← adaptadores`, e `modulos → rt`, `interface → rt` (AD-38).

| De | Pode depender de | Proibido |
| --- | --- | --- |
| Núcleo | portas próprias | Qt, `interface`, `modulos`, `rt`, adaptador concreto |
| `rt` | só bibliotecas externas (pydicom, numpy) | qualquer outro pacote do ISOCENTRO, Qt, banco, rede, arquivo, PIL, matplotlib |
| Módulo | núcleo; `rt`; fachada de consulta de outro módulo | Qt (PyQt5 ou PySide6), adaptador, outro módulo |
| Interface (tela) | comandos do módulo; fachada de consulta; `rt` | adaptador, banco |
| Adaptador | portas do núcleo | `rt` (devolve o dado cru, ex.: `pydicom.Dataset`) |

A regra é imposta por teste de arquitetura (AD-22, ver §5.2).

### 2.4 Topologia de implantação

| Nó | Papel | Ligação |
| --- | --- | --- |
| Estações CEL, BET, DUO | mesmo executável (app desktop) | TLS + login da pessoa → PostgreSQL; pyodbc ReadOnly → `variandw`; C-MOVE → DB Daemon; grava PDF na pasta do paciente; lê CSV |
| Servidor da clínica `clinica-python01` | PostgreSQL 18 e concentradora | — |
| Concentradora | Tarefa Agendada, sem tela | TLS + usuário de sistema → PostgreSQL; pyodbc ReadOnly; C-MOVE; importa JSON ESAPI; grava âncora diária |
| Share `\\fileserver` | pasta ESAPI JSON restrita; CSV (3º degrau); backup cifrado (30 dias); pasta do paciente | — |
| Pasta da TI só-acrescentar | âncora do hash da corrente | — |
| Mídia separada | dump mensal cifrado | — |
| ARIA / `variandw` / DB Daemon DICOM | sistemas externos, somente leitura | — |
| Eclipse | avaliador ESAPI (C#, somente leitura) | grava JSON na pasta restrita |

Todos os nós estão dentro da rede corporativa do serviço (AD-7). Não há serviço ou API próprios entre estação e banco (AD-9; topologia B só se a G7 abrir para outros serviços).

---

## 3. Decomposição em itens de software (IEC 62304 §5.3.1)

### 3.1 Itens e responsabilidades

| ID | Item | Responsabilidade | Decisões |
| --- | --- | --- | --- |
| IS-01 | `nucleo` | motor de verificação (gatilhos `evento`/`estado`/`prazo`/`calendario` → verificação → alerta → log); catálogo com id `<modulo>.<nome>`; execução com `origem` `producao`/`semeado` e execução vigente; log único encadeado; alerta com ciclo de vida; assinatura presa à versão do RT Plan; identidade e capacidades; entidades de referência (paciente, curso, plano, máquina); exportador único; `nucleo.gravar`; portas | AD-1, AD-3, AD-4, AD-11, AD-14, AD-15, AD-26, AD-27, AD-28, AD-29, AD-30, AD-31, AD-33 |
| IS-02 | `modulos/plano` | segunda checagem, Aprovação Física, Duplo Check (FR-10 a FR-21, FR-42) | AD-3, AD-14, AD-16, AD-26, AD-30, AD-35 |
| IS-03 | `modulos/tratamento` | dados de tratamento (doca da UX) | AD-1, AD-3, AD-18, AD-26 |
| IS-04 | `modulos/qualidade` | Garantia da Qualidade (FR-22 a FR-28) | AD-3, AD-5, AD-12, AD-24 |
| IS-05 | `modulos/seguranca` | Segurança do paciente, incidentes (FR-29 a FR-32) | AD-3, AD-5, AD-12, AD-33 |
| IS-06 | `modulos/documentacao` | Documentação e conformidade (FR-33 a FR-36) | AD-3, AD-12 |
| IS-07 | `modulos/software` | Software e sistemas (FR-37 a FR-40) | AD-3, AD-20, AD-34 |
| IS-08 | `modulos/indicadores` | indicadores do serviço (doca da UX) | AD-1, AD-3, AD-18, AD-26 |
| IS-09 | `modulos/conhecimento` | base de conhecimento (doca da UX) | AD-1, AD-3, AD-18, AD-26 |
| IS-10 | `modulos/radioteraficha` | documentos em PDF do Radioteraficha atual (ficha, capa, DRR, que vão para a sala), incluindo a convenção de console da série C; migra aos poucos | AD-1, AD-3, AD-18, AD-26, AD-35, AD-37, AD-38 |
| IS-11 | `adaptadores/variandw` | leitura do `variandw` por pyodbc ReadOnly, gargalo único `_consultar`, `FalhaDeLeitura`; degraus | AD-16, AD-17, AD-23 |
| IS-12 | `adaptadores/dicom` | pydicom e pynetdicom, C-MOVE | AD-16 |
| IS-13 | `adaptadores/postgres` | psycopg; transação dado + log; sessão da pessoa | AD-4, AD-6, AD-10, AD-19, AD-25 |
| IS-14 | `adaptadores/esapi_json` | esquema versionado e validação do JSON do avaliador ESAPI (versão do esquema, id e versão do script, hash da DLL) | AD-15, AD-41 |
| IS-15 | `interface` (shell + telas de módulo) | navegação (lista fixa dos 9 cartões), telas, segundo plano para leituras demoradas, identidade visual Torre de controle (`ui.py`) | AD-18, AD-36 |
| IS-16 | Concentradora (`run_varredura.py`) | gatilhos de tempo e prazo; importação ESAPI; limpeza do espelho; âncora diária | AD-9, AD-15, AD-17, AD-20, AD-28, AD-32 |
| IS-18 | `rt` | leitura e modelo de objetos de RT comuns aos módulos; sem veredito nem convenção de impressão | AD-2, AD-38, AD-39 |
| IS-19 | Raiz de composição (`composicao.py`, `interface/composicao.py`) e `MANIFESTO` de cada módulo | lista explícita do que vai no executável; classe de cada módulo repetida do `classificacao-62304.md` | AD-39, AD-40 |
| IS-17 | Migrações (`migracoes/*.sql`) e objetos do banco (gatilho de hash, funções `SECURITY DEFINER`, políticas RLS, papéis) | esquema versionado | AD-6, AD-12, AD-19, AD-25, AD-27 |

Itens externos ao executável, porém parte do fluxo e do QMS (AD-41): os scripts ESAPI em C# do repositório `scriptsvarian`, com versão própria. Os avaliadores (somente leitura) gravam JSON (AD-15); a concentradora cruza cada JSON com o inventário do módulo Software, e script fora dele ou não validado dá `indeterminado`. Os scripts que escrevem no Eclipse não são executados pelo ISOCENTRO e têm linha própria no `classificacao-62304.md` e no `riscos.md`.

### 3.2 Classe de segurança

| Item | Classe | Situação |
| --- | --- | --- |
| IS-01 `nucleo` | A | Decidida em 26/10/2026 (`classificacao-62304.md`, G1): trava do ARIA e assinatura em papel como medidas externas |
| IS-02 `modulos/plano` | A | Decidida em 26/10/2026 (G1) |
| IS-04 `modulos/qualidade` (exceto o cálculo TRS-398) | A | Decidida em 26/10/2026 (G1 do GQ) |
| Cálculo da calibração TRS-398 (item próprio em `modulos/qualidade`, ex.: `modulos/qualidade/calibracao`) | C | Decidida em 26/10/2026 (G1 do GQ). **PENDENTE:** segregação em relação ao núcleo A (§5.3) |
| IS-10 `modulos/radioteraficha` | A | Decidida em 26/10/2026 (G1) |
| IS-18 `rt` | A | Decidida em 26/10/2026: acompanha o consumidor mais crítico (AD-39) |
| IS-05 `modulos/seguranca` | A | Decidida em 26/10/2026 |
| IS-06 `modulos/documentacao` | A | Decidida em 26/10/2026 |
| IS-03, IS-07 a IS-09 (demais módulos) | C | Sem linha: rigor C até o físico classificar (AD-35) |
| Scripts ESAPI que escrevem no Eclipse (externos) | — | **PENDENTE (G1):** linha própria por script (AD-41) |
| Radioteradados (aba de indicadores) | A | Decidida em 13/10/2026 (`classificacao-62304.md`). **PENDENTE (G1):** correspondência com `modulos/indicadores` |
| `dominio/ritmo` | A | Decidida em 13/10/2026; a espinha registra que o pacote não existe na árvore atual. **PENDENTE (G1):** reclassificar ou retirar |
| IS-11 a IS-14 (adaptadores) | C | Sem linha: rigor C. **PENDENTE (G1 / A-5)** |
| IS-15 (interface) | C | **PENDENTE (G1 / A-5)** |
| IS-16 (concentradora) | C | **PENDENTE (G1 / A-5)** |
| IS-17 (migrações e objetos do banco) | C | **PENDENTE (G1 / A-5)** |

**PENDENTE (G1):** classe dos itens ainda sem linha no `classificacao-62304.md`, feita pelo físico responsável, antes do 1º épico de cada item (`rt` antes da R-58). Até lá vale o rigor C (AD-35).

Fonte da classe e unidade de revisão (AD-39): a classe de cada item está neste documento e no `classificacao-62304.md` assinado pelo físico; o `MANIFESTO` do módulo só a repete, e um teste reprova divergência. Módulo sem classe atribuída segue rigor C. O raio de revisão de uma mudança só soma revisão: interno de um módulo → o módulo; fachada ou manifesto → o módulo e quem o consome, inclusive pelo motor; `rt`, núcleo, adaptador, migração SQL, dependência fixada, tabela de máquina ou arquivo sem dono → a suíte inteira; o que alcança o papel impresso → comparação com os PDFs de referência e aviso ao usuário. A versão do executável é uma só (AD-20).

---

## 4. Interfaces (IEC 62304 §5.3.2)

### 4.1 Interfaces internas

| ID | Interface | Entre | Contrato | Decisões |
| --- | --- | --- | --- | --- |
| II-1 | Fachada de consulta | módulo/tela → outro módulo | somente leitura (ex.: `modulos/tratamento/consulta.py`); única forma de ler dado alheio | AD-3, AD-18 |
| II-2 | Comandos do módulo | tela → módulo dono | a tela age só pelos comandos; não acessa banco nem adaptador | AD-18 |
| II-3 | `nucleo.gravar` | módulo → núcleo | única porta de gravação; confere capacidade e registro tabela → dono; grava dado e linha de log na mesma transação; tudo ou nada | AD-4, AD-27 |
| II-4 | Motor e gatilhos | núcleo → verificações dos módulos | gatilho `evento`/`estado`/`prazo`/`calendario` → verificação → alerta → log; gatilhos de tempo e prazo só na concentradora; execução idempotente | AD-3, AD-28 |
| II-5 | Avaliador | motor → verificação | função pura: recebe os dados lidos e devolve resultado; sem banco, arquivo ou ARIA | AD-15 |
| II-6 | Resultado da verificação | verificação → núcleo | 5 resultados (`conforme`, `nao_conforme`, `nao_aplicavel`, `indeterminado`, `erro`; os dois últimos com motivo; exceção → `erro`); 3 severidades, nenhuma bloqueia; proveniência obrigatória; entrada com degrau, data e versão; estados `sombra`/`ativa`/`podada` | AD-14 |
| II-7 | Portas | núcleo ← adaptadores | os adaptadores implementam as portas; o motor lê por eles | AD-2, AD-15 |
| II-9 | `MANIFESTO` | módulo → raiz de composição | dado puro: nome, classe, capacidades, verificações `<modulo>.<nome>`, tabelas, fachada; sem descoberta por pasta | AD-40 |
| II-10 | Modelo de RT | `rt` → módulo/tela | funções puras sobre `pydicom.Dataset` recebido; dado do serviço (equipe, máquinas) chega por parâmetro | AD-38 |
| II-8 | Exportador | módulo → núcleo | toda exportação sai pelo exportador único, sem identificação | AD-33 |

Pendências:

- **PENDENTE (Deferred: "Forma do retorno da fachada de consulta" e "entradas declaradas da verificação"):** volta no épico do núcleo.
- **PENDENTE (Deferred: "campos exatos do `MANIFESTO`"):** volta no épico do núcleo. A raiz de composição em si foi decidida no AD-40.

### 4.2 Interfaces externas

| ID | Sistema externo | Direção | Mecanismo | Controles | Decisões |
| --- | --- | --- | --- | --- | --- |
| IE-1 | `variandw` (ARIA) | leitura | pyodbc, `ApplicationIntent=ReadOnly`, `readonly=True`, gargalo `_consultar` | `FalhaDeLeitura` → próximo degrau; degraus `variandw` → espelho → CSV, com degrau e data anunciados na tela | AD-16, AD-17 |
| IE-2 | DB Daemon DICOM (ARIA) | leitura | C-MOVE (o ARIA não faz C-GET) | somente leitura | AD-16 |
| IE-3 | PostgreSQL 18 central | leitura e gravação | psycopg[binary] 3.3; TLS obrigatório; scram para `isocentro_app`, senha no cofre do Windows (`keyring`) | login da pessoa por função `SECURITY DEFINER`; RLS por sessão; versão do esquema conferida ao abrir | AD-10, AD-19, AD-25 |
| IE-4 | JSON do avaliador ESAPI | leitura (pela concentradora) | pasta restrita no share; esquema versionado, hash do conteúdo e versão do plano | JSON inválido → `erro` com motivo; versão do plano diferente da atual → `indeterminado` | AD-15 |
| IE-5 | Pasta do paciente | gravação (PDF, imagens) | arquivo no share | hash e caminho registrados no banco | AD-9 |
| IE-6 | Pasta da TI só-acrescentar | gravação (concentradora) | arquivo diário com o hash da ponta da corrente, sem dado de paciente | o dono do banco não apaga nem edita | AD-32 |
| IE-7 | Relatórios CSV exportados | leitura | arquivo no share (3º degrau) | "seguem como hoje" | AD-16, AD-17 |
| IE-8 | Destino do backup (`\\fileserver`, mídia separada) | gravação (servidor) | `pg_dump` cifrado AES-256 | pasta restrita; guarda dupla da chave | AD-24 |

Pendências:

- **PENDENTE (Deferred: "TLS em detalhe"):** `sslmode`, CA interna, `pg_hba.conf`, credencial da concentradora, conta e `Encrypt` do `variandw`. Volta no épico do núcleo, antes da instalação do banco.
- **PENDENTE (Deferred: "Destino do JSON ESAPI depois de importado" e "comprovação de que o script não declara escrita"):** volta no épico do avaliador ESAPI.
- **PENDENTE (Deferred: "Anexos binários, ACL da pasta CSV, DICOM em claro na LAN"):** volta no detalhe de cada módulo.

---

## 5. Segregação (IEC 62304 §5.3.5)

### 5.1 Objetivo

A segregação é o que permitiria classificar itens com classes diferentes dentro do mesmo produto. A revisão clínica (A-5) registra que a norma só aceita classe menor para um item se houver segregação efetiva e justificada.

### 5.2 Mecanismos que sustentam a separação

| Mecanismo | O que separa | Como é verificado | Decisão |
| --- | --- | --- | --- |
| Direção de dependência | núcleo de Qt e de adaptador concreto; módulos entre si; tela do banco | teste de arquitetura | AD-2 |
| Teste de arquitetura por `ast` | reprova núcleo → módulo/Qt/adaptador concreto; módulo → outro módulo (fora da fachada), adaptador ou Qt; tela → adaptador/banco; módulo gravando em tabela de outro dono | teste automatizado no estilo de `test_padrao_visual`, sem biblioteca nova; violações atuais (`qualidade_metodo.py`, `gatilho.py`, `gatilho_relogio.py`, `capa_dados.py`) em lista de exceções com data de saída | AD-22 |
| Dono único do dado | cada tabela tem um só gravador; leitura alheia só pela fachada somente leitura | registro tabela → dono conferido por `nucleo.gravar` e pelo AD-22 | AD-3, AD-27 |
| Schema PostgreSQL por módulo | dados de cada módulo em schema próprio | migrações; testes em PostgreSQL | AD-27, AD-34 |
| Avaliador puro | verificação sem acesso a banco, arquivo ou ARIA | contrato do motor | AD-15 |
| RLS por clínica | linhas de uma clínica das de outra | testes de RLS contra PostgreSQL | AD-12, AD-34 |
| Papéis de banco | `isocentro_app`/`isocentro_concentradora` só INSERT/SELECT no log; DDL só em `isocentro_dono` | testes de papéis contra PostgreSQL | AD-6, AD-34 |

### 5.3 Limites da segregação

- Todos os itens IS-01 a IS-16, IS-18 e IS-19 rodam no mesmo executável, no mesmo processo e na mesma memória (AD-1). A separação acima é lógica e de dados; não há isolamento de processo entre módulos.
- Uma falha de um módulo pode afetar o núcleo, e o contrário também (A-5).
- O RLS protege contra erro, não contra quem tem acesso administrativo ao servidor (AD-12).
- A operação depende de uma só pessoa (AD-21): o físico instala, mantém, aplica migrações e também assina. A âncora externa (AD-32) é o controle compensatório adotado.

**PENDENTE (G1 / A-5):** decisão formal de segregação que diga o que isola um item do outro e o que não isola. Sem segregação demonstrada, a revisão (A-5) aponta que o núcleo e tudo o que o compartilha herdam a classe do módulo de classe mais alta. Desde 26/10/2026 o núcleo é classe A por decisão do físico, e o cálculo TRS-398 é classe C e grava pelo núcleo: a justificativa da segregação (§5.3.5) é decisão do físico e volta antes do épico do TRS-398. O `rt` é classe A desde 26/10/2026 e não abriga o cálculo TRS-398.

---

## 6. Integridade e rastreabilidade dos registros

| Controle | Descrição | Decisão |
| --- | --- | --- |
| Log único | uma só tabela de log, do núcleo; nenhum módulo cria log próprio | AD-4 |
| Mesma transação | dado e linha de log (quem, quando, o quê, versão do dado de origem) na mesma transação; tudo ou nada | AD-4, AD-27 |
| Log sem texto livre | a linha guarda referência ao registro | AD-4, AD-33 |
| Append-only | correção = novo registro que aponta o anterior; vigente calculado; sem UPDATE de conteúdo nem DELETE. Exceção declarada: espelho do `variandw` (cache) | AD-5, AD-17 |
| Corrente de hash | global às três clínicas; gatilho `SECURITY DEFINER` calcula `sha256(hash_anterior || linha de log)` com ordem serializada pelo banco | AD-6 |
| Âncora externa | a concentradora grava todo dia o hash da ponta numa pasta da TI só-acrescentar | AD-32 |
| Verificador de integridade | compara a corrente com as âncoras e aponta o registro e a posição alterados | AD-32 |
| Alerta como eventos | aberto, visto, resolvido com justificativa; cada mudança é evento acrescentado | AD-29 |
| Assinatura presa à versão | versão do plano = `Ser` + SOPInstanceUID + `HstryDateTime`/status de aprovação; se o plano muda, a assinatura não se transfere e o item volta a pendente | AD-30 |
| Execução vigente | execução idempotente; alerta e resultado em tela só da execução vigente | AD-28 |
| Origem da execução | `semeado` nunca entra em indicador, cobertura ou alerta | AD-14 |
| Versão do esquema | o app confere ao abrir; se não bate, abre somente leitura com aviso "atualize" | AD-19 |
| Versão do software | app e concentradora do mesmo código e da mesma versão; PyInstaller 6.21.0; runner `windows-2025` | AD-20 |

Pendências:

- **PENDENTE (Deferred: "Raiz de composição única e versão do app conferida no banco"):** registro da versão do software em cada execução. Volta no épico do núcleo.
- **PENDENTE (Deferred: "Relógio de referência", "Hora do fato × hora do lançamento"):** volta no épico do núcleo.

---

## 7. Segurança da informação e privacidade

| Controle | Descrição | Decisão |
| --- | --- | --- |
| Login da pessoa no banco | conferido no PostgreSQL por função `SECURITY DEFINER`, que devolve a sessão; PBKDF2 migra do app para o banco | AD-25 |
| Credencial do app sem poder próprio | a senha do `isocentro_app` sozinha não lê nem grava dado; tabelas de usuários e capacidades fora do alcance dele | AD-25 |
| Capacidade no ato | perfil → capacidades numa tabela única; núcleo e banco conferem; ocultar na tela é só conveniência | AD-11 |
| Vínculo ARIA ↔ ISOCENTRO | por tabela, nunca por semelhança de nome; só `admin` cadastra | AD-13 |
| RLS por clínica | toda tabela é de clínica (coluna obrigatória + política) ou global; a concentradora sem `BYPASSRLS` | AD-12 |
| TLS | conexão com TLS obrigatório; scram; senha no cofre de credenciais do Windows | AD-25 |
| Backup cifrado | AES-256 antes de sair do servidor; pasta restrita; chave com o dono e cópia lacrada com SPR/gestão (guarda dupla) | AD-24 |
| Não sai da rede | dado de paciente ou de funcionário não sai da rede do serviço | AD-7 |
| Exportador sem identificação | toda exportação pelo exportador único do núcleo | AD-33 |
| Logging técnico | nunca leva dado de paciente | Convenções; NFR-2 |
| Espelho no banco | o espelho sai do JSON em claro no share para tabelas com RLS | AD-17 |

Pendências:

- **PENDENTE (Deferred: "Tabela perfil → capacidades preenchida"):** depende da G8. Volta no épico do núcleo.
- **PENDENTE (Deferred: "Campo sensível por perfil e trilha de leitura de dado sensível / RIPD"):** volta no épico de Segurança do paciente (MVP 4). Revisão M-6 (LGPD art. 37, 38, 46).
- **PENDENTE (Deferred: "Contas administrativas do servidor, cifra de disco, log do próprio PostgreSQL sem dado de paciente"):** volta no roteiro de manutenção (AD-21). Revisão M-5, B-6.

---

## 8. Disponibilidade e contingência

| Situação | Comportamento | Decisão |
| --- | --- | --- |
| PostgreSQL central fora | estações abrem somente leitura (`variandw`/DICOM) com aviso "banco central fora — nada será gravado"; degraus passam a `variandw` → CSV e a tela anuncia; registros em papel, lançados depois; sem fila local | AD-23 |
| `variandw` indisponível | `FalhaDeLeitura` → próximo degrau ou "não deu para perguntar" | AD-16; Convenções |
| Esquema divergente | somente leitura com aviso "atualize" | AD-19 |
| Leitura demorada | segundo plano com "carregando" + degrau + data; nunca na thread de tela | AD-18 |
| Backup e restauração | `pg_dump` diário cifrado (30 dias em `\\fileserver`); um dump mensal em mídia separada; retenção de 10 anos após o descarte do software; restauração mensal testada e registrada, incluindo leitura de dump antigo | AD-21, AD-24 |

Pendências:

- **PENDENTE (Deferred: "Execução de gatilhos de janelas perdidas quando o banco volta"):** volta na construção da concentradora.
- **PENDENTE (Q5):** vigilância da saúde da concentradora. Volta na construção da concentradora.
- **PENDENTE (Deferred: "Retenção por tipo de registro"):** retenção pela vida útil do equipamento no CQ (FR-28; revisão A-2). Volta nos épicos de Garantia da Qualidade (MVP 3) e de Software.
- **PENDENTE (Deferred: "Desempenho NFR-5"):** 30 s por plano, 3 s por painel. Volta no épico do Plano (MVP 1).

---

## 9. SOUP conhecido (IEC 62304 §5.3.3, §5.3.4)

Versões conforme a tabela Stack da espinha, verificada em 19/10/2026. Licenças apenas onde as fontes as registram.

| SOUP | Versão | Licença | Função no sistema | Item que usa | Situação |
| --- | --- | --- | --- | --- | --- |
| Python | 3.12 (fim de vida 31/10/2028) | PENDENTE | runtime | todos | requisitos e anomalias PENDENTES |
| PySide6 | PENDENTE (mirror mostra 6.11.0; confirmar no PyPI antes do 1º épico) | LGPL | interface Qt 6 (alvo) | IS-15 | AD-36 |
| PyQt5 | 5.15.11 (sai na migração) | PENDENTE | interface atual | IS-15 | Qt 5.15 fora do suporte padrão desde 26/05/2025 |
| PostgreSQL | 18.x (18.6 em 19/10/2026; 18.7 em 12/11/2026) | PostgreSQL License | banco central | IS-13, IS-17 | AD-10 |
| psycopg[binary] | 3.3 (3.3.4) | LGPL | driver do PostgreSQL | IS-13 | AD-10 |
| pyodbc | 5.3.0 | PENDENTE | leitura do `variandw` | IS-11 | — |
| pydicom | 3.0.2 | PENDENTE | leitura DICOM | IS-12 | — |
| pynetdicom | 3.0.4 | PENDENTE | C-MOVE | IS-12 | — |
| numpy | 2.4.6 | PENDENTE | cálculo | PENDENTE | — |
| reportlab | 4.5.1 | PENDENTE | geração de PDF | PENDENTE | — |
| pypdf | PENDENTE (fora da tabela Stack da espinha) | PENDENTE | PDF | PENDENTE | — |
| PyInstaller | 6.21.0 (onedir, 3 specs) | PENDENTE | empacotamento | entrega | AD-20 |
| keyring (WinVaultKeyring; requer pywin32) | PENDENTE (confirmar no PyPI antes do 1º épico do núcleo) | PENDENTE | senha do `isocentro_app` no cofre do Windows | IS-13 | AD-25 |
| pywin32 | PENDENTE | PENDENTE | dependência do keyring | IS-13 | — |
| unittest | stdlib do Python 3.12 | — | testes | ferramenta | — |
| ruff | 0.16.4 | PENDENTE | lint | ferramenta | — |
| CI GitHub Actions, runner `windows-2025` | — | — | construção | ferramenta | AD-20 |

**PENDENTE (Deferred: "Inventário SOUP completo da Stack (inclui keyring, pywin32, PySide6)"; revisão M-11):** para cada item, função exigida (§5.3.3), requisitos de hardware e software (§5.3.4), anomalias conhecidas consultadas (§7.1.2), licença; incluir instaladores e runtime do Windows/ODBC. Volta no módulo Software e sistemas. Regra vigente: dependências fixadas exatas; atualizar exige revalidar contra o TPS (Convenções).

---

## 10. Rastreabilidade AD → requisitos do PRD

Apenas os vínculos que a espinha declara no campo "Binds" de cada AD ou no "Mapa área → arquitetura".

| AD | Requisitos (FR/NFR) |
| --- | --- |
| AD-4 | FR-3, FR-8 |
| AD-6 | FR-3 |
| AD-7 | NFR-2 |
| AD-8 | NFR-6 |
| AD-10 | NFR-10 |
| AD-11 | FR-7, FR-8 |
| AD-12 | NFR-6 |
| AD-13 | FR-20 |
| AD-14 | FR-1, FR-2, FR-4, FR-5, FR-6, FR-41 |
| AD-15 | FR-2, FR-39 |
| AD-16 | NFR-1, NFR-3, NFR-7 |
| AD-17 | NFR-3, NFR-7 |
| AD-18 | FR-9 |
| AD-22 | NFR-9 |
| AD-24 | FR-3, FR-28 |
| AD-25 | FR-7, FR-8 |
| AD-28 | FR-11, FR-15, FR-41 |
| AD-29 | FR-41 |
| AD-30 | FR-8, FR-20 |
| AD-31 | FR-1 |
| AD-32 | FR-3, FR-28 |
| AD-33 | NFR-2, FR-29 |
| AD-34 | NFR-9 |
| AD-1, AD-2, AD-3, AD-5, AD-9, AD-19, AD-20, AD-21, AD-23, AD-26, AD-27, AD-35, AD-36, AD-37 | sem FR/NFR citado (binds por camada, operação ou entrega) |

Áreas do PRD por item: motor (FR-1 a FR-6, FR-41) → IS-01; shell, perfis, assinatura (FR-7 a FR-9) → IS-01 + IS-15; Plano (FR-10 a FR-21, FR-42) → IS-02; Qualidade (FR-22 a FR-28) → IS-04; Segurança do paciente (FR-29 a FR-32) → IS-05; Documentação (FR-33 a FR-36) → IS-06; Software (FR-37 a FR-40) → IS-07; dado clínico do ARIA (NFR-1, NFR-3, NFR-7) → IS-11, IS-12.

**PENDENTE (Deferred: "Perigos introduzidos pela arquitetura em `riscos.md`"; revisão A-6):** ligação AD → item de risco → verificação. O `riscos.md` tem só RD-1 a RD-5 (Radioteradados), com S, O e D a preencher. Perigos apontados pela revisão, sem S/O/D: banco central fora (AD-23); visibilidade de clínica errada (AD-12); importação de JSON ESAPI (AD-15); restauração com dado antigo; quebra ou forja da corrente (AD-6); espelho vencido apresentado como atual (AD-17); esquema divergente (AD-19). Volta antes do 1º épico que grava dado clínico.

---

## 11. Pontos de interesse regulatório

### 11.1 RDC ANVISA 657/2022

| Ponto | Onde a arquitetura responde |
| --- | --- |
| Discernir registro alterado (art. 5º, citado em FR-3) | log append-only, corrente de hash, âncora externa e verificador (AD-4, AD-5, AD-6, AD-32) |
| Retenção do log 10 anos após o descarte do software (art. 5º §3º, citado em FR-3) | AD-24 |
| Classificação do software | **PENDENTE (G1)**; AD-35 provisório |

### 11.2 CNEN NN-6.10

| Ponto | Onde a arquitetura responde |
| --- | --- |
| Registro e autoria da Aprovação Física e do Duplo Check (art. 17, IV, citado na revisão C-2) | login da pessoa no banco, capacidade no ato, assinatura presa à versão do plano (AD-11, AD-25, AD-30) |
| Cópia independente dos registros de CQ (art. 71, IX, citado em FR-28) | backup cifrado em outra máquina e mídia separada (AD-24) |

### 11.3 LGPD

| Ponto | Onde a arquitetura responde |
| --- | --- |
| Dado sensível de saúde (art. 5º II) e segurança (art. 46) | não sai da rede (AD-7); RLS (AD-12); TLS (AD-25); backup cifrado (AD-24); espelho fora do share em claro (AD-17) |
| Minimização (art. 6º III) | exportador sem identificação (AD-33); log sem texto livre (AD-4, AD-33) |
| Registro de operações e RIPD (art. 37, 38) | **PENDENTE (Deferred: trilha de leitura / RIPD, MVP 4)** |
| Espelho de 60 dias presente em dumps de longa guarda | **PENDENTE (revisão M-7):** decidir exclusão do espelho do dump de longa guarda |

### 11.4 RDC 20/2006

Registros de CQ guardados pela vida útil do equipamento (8.1(b), citado em FR-28): **PENDENTE (Deferred: "Retenção por tipo de registro")**.

---

## 12. Pendências consolidadas

| # | Pendência | Item Deferred / achado | Volta quando |
| --- | --- | --- | --- |
| 1 | Classificação formal IEC 62304/ANVISA por item | G1 / A-5 | antes do 1º épico do Plano (MVP 1) |
| 2 | Decisão formal de segregação | G1 / A-5 | com a G1 |
| 3 | Perigos da arquitetura em `riscos.md` (S, O, D) | Deferred / A-6 | antes do 1º épico que grava dado clínico |
| 4 | Inventário SOUP completo (função, requisitos, anomalias, licenças) | Deferred / M-11 | módulo Software e sistemas |
| 5 | Versões de PySide6, keyring, pywin32 e pypdf | Deferred (Stack) | antes do 1º épico de interface / do núcleo |
| 6 | Registro do banco central no `escopo.md` | Q8 / M-9 | Update do PRD / G8 |
| 7 | Perfis de usuário | Q1 / G8 | Update do PRD |
| 8 | Tabela perfil → capacidades | Deferred | épico do núcleo |
| 9 | Versão do app conferida no banco; campos exatos do `MANIFESTO` | Deferred | épico do núcleo |
| 10 | Forma do retorno da fachada; entradas declaradas da verificação | Deferred | épico do núcleo |
| 11 | Relógio de referência; hora do fato × lançamento | Deferred / M-8 | épico do núcleo |
| 12 | TLS em detalhe; credenciais da concentradora e do `variandw` | Deferred / M-1, M-2 | antes da instalação do banco |
| 13 | Destino do JSON ESAPI e prova de que o script não declara escrita | Deferred / A-3, B-1 | épico do avaliador ESAPI |
| 14 | Contas administrativas, cifra de disco, log do PostgreSQL | Deferred / M-5, B-6 | roteiro de manutenção (AD-21) |
| 15 | Campo sensível por perfil; trilha de leitura; RIPD | Deferred / M-6 | MVP 4 |
| 16 | Retenção por tipo de registro; guarda dos relatórios de validação (FR-40) | Deferred / A-2 | MVP 3 e épico de Software |
| 17 | Gatilhos de janelas perdidas; vigilância da concentradora | Deferred / Q5 | construção da concentradora |
| 18 | Desempenho (NFR-5) | Deferred | MVP 1 |
| 19 | Anexos binários, ACL da pasta CSV, DICOM em claro | Deferred / M-3, B-2 | detalhe de cada módulo |
| 20 | PDF impresso preservado na migração | Deferred / M-10 | épico de migração do Radioteraficha |
| 21 | Resto do mapa dos pacotes atuais para a árvore-alvo (`dicom/`, `papel/` e parte de `dominio/` já decididos) | Q6 | épico de migração |
| 22 | Espelho fora do dump de longa guarda | M-7 | não consta do Deferred da espinha |
| 23 | P3 (IMRT/VMAT), P6 (códigos do `variandw`), G4, G7 | Deferred | detalhe do Plano; Update do PRD |
| 24 | Critério de validação dos scripts ESAPI que escrevem no Eclipse | Deferred / revisão de 22/10 | antes de o 1º script gravável entrar como validado (R-61) |
| 25 | Fronteira modelar × cálculo que sustenta veredito em SSD, `dose3d`, `dvh` | Deferred / revisão de 22/10 | na divisão de `dicom/` (R-58), com o físico |
