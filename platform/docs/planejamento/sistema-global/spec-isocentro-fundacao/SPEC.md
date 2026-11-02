---
id: SPEC-isocentro-fundacao
companions:
  - ../architecture-isocentro-2026-10-19/ARCHITECTURE-SPINE.md
  - ../prd-isocentro-2026-10-16/prd.md
  - ../ux-isocentro-2026-10-16/EXPERIENCE.md
  - ../ux-isocentro-2026-10-16/DESIGN.md
  - rastreabilidade.md
sources: []
---

> **Contrato canônico.** Esta SPEC e os arquivos em `companions:` são o contrato completo do que construir, testar e validar. A espinha (`AD-n`) é obrigatória; do PRD valem o glossário (§3), FR-1 a FR-9, FR-39 a FR-41 e §11; da UX valem Foundation, IA, Perfis, Clínica, State Patterns e o DESIGN.md inteiro. Fatos de QMS: `docs/qms/escopo.md` (perfis, travas, regra de decisão), `classificacao-62304.md` e `riscos.md`.

# ISOCENTRO — Fundação

## Why

Mandato e visão. Os cinco MVPs do ISOCENTRO (segunda checagem, revisão com segunda assinatura, CQ, incidentes, vencimentos) cumprem obrigações legais (NN-6.10, RDC 20/2006, RDC 36/2013, RDC 657/2022) e todos dependem da mesma base: um motor de verificação sem conhecimento de radioterapia, um log que a inspeção da ANSN e a avaliação da ANVISA aceitem como íntegro, identidade e assinatura que não se forjam, e um banco central compartilhado pelas três clínicas. Hoje nada disso existe: o estado está em JSON no share, o histórico é JSONL sem hash, o perfil só esconde abas e a interface está em Qt 5.15, fora do suporte padrão. Esta spec constrói a base uma vez, para que nenhum módulo invente a sua.

## Capabilities

Cada capacidade diz de onde vem o dado (**fonte**) e se muda o que sai impresso (**papel**). Nenhuma capacidade da Fundação muda o papel. Regra de cada uma: ver `AD-n` na espinha.

- **CAP-1 — Banco central e esquema** (AD-10, AD-19, AD-27)
  - **intent:** O ISOCENTRO guarda todo o seu estado num PostgreSQL 18 em `clinica-python01`, com um schema por módulo e versão de esquema conferida pelo app.
  - **success:** App com versão de esquema diferente da do banco abre somente leitura com o aviso "atualize"; o papel `isocentro_app` não consegue executar DDL; migração só por `.sql` numerado aplicado por `isocentro_dono`.
  - **fonte · papel:** gravado pelo próprio app · não muda.

- **CAP-2 — Login da pessoa no banco** (AD-25)
  - **intent:** A pessoa entra com usuário e senha conferidos dentro do PostgreSQL, e toda leitura e gravação exige a sessão que o banco devolve.
  - **success:** Com só a senha do `isocentro_app` nenhuma tabela de dado é lida nem gravada; conexão sem TLS é recusada; a senha do `isocentro_app` está no keyring da estação e em nenhum arquivo de texto; senha a trocar força `DialogTrocarSenha`; sessão aberta em outra estação fecha esta.
  - **fonte · papel:** cadastro de usuários no banco (migrado, CAP-20) · não muda.

- **CAP-3 — Perfis, capacidades e clínicas** (AD-8, AD-11, AD-12, FR-7, NFR-6)
  - **intent:** Cada pessoa tem um perfil, as clínicas a que tem acesso e, se for o caso, os atributos admin e físico responsável; o núcleo e o banco conferem a capacidade e a clínica no ato.
  - **success:** Teste em PostgreSQL: ação sem a capacidade é recusada pelo banco mesmo chamada fora da tela; consulta sem filtro de clínica devolve só as clínicas da sessão; toda tabela é de clínica (`clinica` ∈ `CEL`/`BET`/`DUO`, com RLS) ou global; a concentradora não tem `BYPASSRLS`.
  - **fonte · papel:** tabela perfil → capacidades no banco (CAP-23) · não muda.

- **CAP-4 — Gravação única com log encadeado** (AD-3, AD-4, AD-5, AD-6, AD-27, FR-3)
  - **intent:** Toda gravação passa por `nucleo.gravar`, que grava o dado e a linha de log na mesma transação, encadeada por hash.
  - **success:** Falha no meio da transação não deixa nem dado nem log; `UPDATE`/`DELETE` no log são negados aos papéis do app e da concentradora; gravação em tabela de outro dono é recusada pelo registro tabela → dono; correção é registro novo que aponta o anterior e o vigente é calculado; a linha de log tem quem, quando, referência e versão da origem, sem texto livre.
  - **fonte · papel:** módulo dono do dado · não muda.

- **CAP-5 — Âncora e verificador de integridade** (AD-32, FR-3)
  - **intent:** O físico consegue provar que o log não foi alterado desde cada âncora diária.
  - **success:** Alterar ou apagar uma linha antiga (mesmo com DDL) faz o verificador apontar o registro e a posição; a âncora diária contém só o hash da ponta e fica na pasta da TI só-acrescentar.
  - **fonte · papel:** log do banco · não muda.

- **CAP-6 — Entidades de referência** (AD-13, AD-26)
  - **intent:** Paciente, curso, plano e máquina têm uma só identidade no sistema, e a pessoa do ARIA é ligada à do ISOCENTRO por cadastro.
  - **success:** A chave canônica é `Ser` do `variandw` + clínica; nome, REG, `PatientId` e SOPInstanceUID só existem como apelidos; não há junção por nome no código; o vínculo ARIA ↔ ISOCENTRO só é gravado com capacidade `admin`.
  - **fonte · papel:** `variandw` (somente leitura) e cadastro do admin · não muda.

- **CAP-7 — Catálogo de verificações com proveniência** (FR-1, AD-31)
  - **intent:** O físico cadastra uma verificação com regra, proveniência, gatilho, responsável, avaliador, severidade e estado, e cada uma aponta para a ficha da base que a justifica.
  - **success:** Cadastro sem fonte, com fonte que não resolve para `fichas/atividades/<ID>.md` ou ficha de referência, ou com tolerância sem origem (`literatura` + referência; `servico` + data e método, TG-218; ou `provisoria` + item de `decisoes-sem-base.md`) é recusado; tolerância `provisoria` aparece marcada "provisório" em toda tela até o físico decidir; o id é `<modulo>.<nome>` e é único.
  - **fonte · papel:** base de conhecimento `Documents/isocentro/conhecimento/` · não muda.

- **CAP-8 — Motor de execução e contrato do avaliador** (FR-2, FR-39, AD-14, AD-15, AD-28)
  - **intent:** O motor lê os dados pelos adaptadores, chama um avaliador puro e registra a execução com a versão exata do que foi lido.
  - **success:** Avaliador que lança exceção gera `erro` com a mensagem; sem dado suficiente gera `indeterminado` com motivo; nenhum dos dois conta como `conforme`; a entrada registrada tem degrau, data, versão e checksum (arquivo ou data da carga do `variandw`); repetir a mesma verificação sobre o mesmo objeto e versão não cria segunda execução vigente.
  - **fonte · papel:** adaptadores `variandw`, `dicom`, `postgres` · não muda.

- **CAP-9 — Resultado ESAPI por JSON** (AD-15, FR-2)
  - **intent:** Um avaliador ESAPI somente leitura entrega o resultado por JSON numa pasta restrita, e a concentradora o importa como execução.
  - **success:** Teste prova o mesmo formato de resultado do avaliador Python; JSON com esquema ou hash inválido vira `erro` com motivo; versão do plano diferente da atual vira `indeterminado`; nenhum código C# grava no banco.
  - **fonte · papel:** pasta ESAPI JSON no share · não muda.

- **CAP-10 — Sombra e promoção** (FR-4)
  - **intent:** Toda verificação nova roda em sombra até o físico promovê-la a ativa ou podá-la.
  - **success:** Verificação em sombra executa e loga, mas não gera alerta nem entra em fila, contador ou sinal de máquina; a promoção grava quem, quando e o resumo do período (execuções, `nao_conforme`, `indeterminado`).
  - **fonte · papel:** catálogo e execuções · não muda.

- **CAP-11 — Erro semeado** (FR-6, AD-14)
  - **intent:** O físico roda uma verificação contra casos com erro conhecido e obtém a sensibilidade medida.
  - **success:** Execução com origem `semeado` nunca aparece em indicador, cobertura ou alerta; o relatório mostra, por verificação, casos semeados, detectados e não detectados; caso feito de plano real é anonimizado antes de sair da pasta do paciente.
  - **fonte · papel:** casos semeados · não muda.

- **CAP-12 — Alerta com ciclo de vida** (FR-5, FR-41, AD-29)
  - **intent:** Todo `nao_conforme`, `indeterminado` ou `erro` de verificação ativa, e todo prazo em aviso ou vencido, vira alerta para o perfil responsável na clínica do objeto, sem bloquear nada.
  - **success:** O alerta aparece em "O que precisa de ação" e no módulo de origem, ordenado por severidade e prazo; o físico responsável vê as três clínicas; aberto → visto (quem, quando) → resolvido são eventos acrescentados; resolver `alta` pede justificativa; nenhuma tela tem botão desabilitado por resultado.
  - **fonte · papel:** execuções e prazos · não muda.

- **CAP-13 — Assinatura presa à versão** (FR-8, AD-30)
  - **intent:** A pessoa logada assina um objeto numa versão, e a assinatura não vale para outra versão.
  - **success:** A assinatura grava pessoa, perfil, data e hora, objeto e versão (`Ser` + SOPInstanceUID + `HstryDateTime`/status); entra no log; não há assinatura em nome de outro; mudar a versão do plano devolve o item a pendente.
  - **fonte · papel:** `variandw` para a versão do plano · não muda.

- **CAP-14 — Concentradora** (AD-9, AD-20, AD-28, FR-41)
  - **intent:** Um processo sem tela em `clinica-python01` roda os gatilhos de tempo e prazo com o app fechado.
  - **success:** Teste: prazo vencido com o app fechado aparece como alerta `alta` na abertura seguinte; a estação não dispara gatilho de tempo (o `QTimer` de `gatilho_relogio` sai); a concentradora sai do mesmo código e versão do app, empacotada sem Qt.
  - **fonte · papel:** catálogo, execuções e `variandw` · não muda.

- **CAP-15 — Leitura do ARIA por degraus** (AD-16, AD-17, NFR-3, NFR-7)
  - **intent:** Todo dado do ARIA chega pelo degrau disponível (`variandw` → espelho → relatório CSV), e a tela diz qual e de quando.
  - **success:** O `variandw` só é lido por `_consultar` com `ApplicationIntent=ReadOnly`; o espelho vive no PostgreSQL com RLS e validade de 60 dias, e a limpeza fica no log; com o `variandw` fora, a tela mostra o último dado com degrau e data e nenhum prazo vira `conforme`; DICOM por C-MOVE.
  - **fonte · papel:** `variandw`, espelho, CSV, DB Daemon · não muda.

- **CAP-16 — Banco central fora: somente leitura** (AD-23)
  - **intent:** Com o PostgreSQL inacessível, a estação continua consultando o ARIA e avisa que nada será gravado.
  - **success:** Aviso "banco central fora — nada será gravado"; nenhuma gravação local nem fila; degraus viram `variandw` → CSV e a tela anuncia; o Início não mostra máquina "normal", fila zero nem "Nada precisa de ação".
  - **fonte · papel:** `variandw` e CSV · não muda.

- **CAP-17 — Backup e restauração** (AD-21, AD-24)
  - **intent:** O banco tem cópia cifrada restaurável por dez anos após o descarte do software.
  - **success:** `pg_dump` diário cifrado AES-256 antes de sair do servidor, em `\\fileserver` restrito por 30 dias; um dump por mês em mídia separada; chave com Geova e cópia lacrada com SPR/gestão; restauração mensal, inclusive de dump antigo, registrada no log; roteiro de manutenção escrito.
  - **fonte · papel:** banco central · não muda.

- **CAP-18 — Exportador único sem identificação** (AD-33, NFR-2)
  - **intent:** Tudo o que sai do ISOCENTRO como arquivo sai por um exportador do núcleo, sem dado identificável.
  - **success:** Nenhum módulo gera arquivo de saída por conta própria (teste de arquitetura); `varrer_identidade` e o teste de log passam; nenhum dado de paciente ou funcionário sai da rede.
  - **fonte · papel:** banco central · não muda.

- **CAP-19 — Shell Torre de controle em PySide6** (AD-18, AD-36, FR-9)
  - **intent:** O usuário entra num shell único com o Início da Torre e chega a qualquer módulo pela doca, pela situação da clínica ou pela linha de ação.
  - **success:** Login → Início em noite na última clínica; Zona 1 por clínica (máquinas com sinal, motivo e agenda; filas), Zona 2 "O que precisa de ação" (5 + "ver mais N"), Zona 3 doca de 9 sem contagem (inexistente "em construção"; sem acesso some); seletor só com as clínicas permitidas e "Todas" para o físico responsável; módulo em tela cheia com "◂ Início" e sem seletor; barra de status com usuário, perfil, clínica, degrau e data; Configurações (Serviço, Usuários, Equipe, Máquinas) só com o atributo admin; nenhuma leitura demorada na thread de tela; o app inteiro roda em PySide6 (telas atuais portadas sem redesenho); `test_padrao_visual` confere a paleta nova e reprova verde fora da dose.
  - **fonte · papel:** fachadas de consulta dos módulos e alertas do núcleo · não muda (nenhum PDF passa pelo Qt).

- **CAP-20 — Migração das entidades do núcleo** (AD-8, AD-37)
  - **intent:** Usuários, sessões, equipe e configuração do serviço saem dos JSON para o PostgreSQL, uma entidade por vez; a equipe ganha cargo e marca IOE.
  - **success:** Para cada entidade: migra, confere contra o JSON, e a partir do corte só o banco grava; o JSON fica somente leitura e depois é arquivado; nunca há gravação dupla; o código usa `CEL`/`BET`/`DUO` (sai `ANA`); a equipe tem cargo além de médico e físico e marca IOE por pessoa e clínica, mantida pelo SPR (spec Documentação, CAP-9).
  - **fonte · papel:** `usuarios.json`, `sessoes.json`, `~/.isocentro_*.json`, `config_servico.json` · não muda.

- **CAP-21 — Vigilância de arquitetura e ambientes** (AD-22, AD-34, AD-39, NFR-9)
  - **intent:** A direção de dependência, o dono de cada tabela e o raio de cada mudança são conferidos por ferramenta, e o que depende do PostgreSQL é testado em PostgreSQL.
  - **success:** Teste por `ast` reprova núcleo → módulo/Qt/adaptador/`rt`, módulo → outro módulo/adaptador/Qt, tela → adaptador/banco, `rt` → outro pacote, adaptador → `rt`, `composicao.py` → `interface`, módulo fora da lista de composição, manifesto sem tela, verificação com prefixo alheio, classe do manifesto diferente do `classificacao-62304.md` e gravação em tabela alheia; as violações atuais ficam numa lista de exceções com data de saída; `tools/raio.py` dá o raio do diff, que só soma (SQL, dependência, tabela de máquina ou arquivo sem dono → suíte inteira; alcance de `papel/` → comparar PDF e avisar); gatilho de hash, papéis e RLS rodam contra PostgreSQL em desenvolvimento e homologação; a suíte segue verde.
  - **fonte · papel:** código do repositório · não muda.

- **CAP-22 — Relatório de validação do núcleo** (FR-40, FR-6)
  - **intent:** O núcleo tem relatório de validação antes do primeiro uso real.
  - **success:** O relatório traz requisitos, testes automatizados, casos conferidos à mão, sensibilidade semeada e versão do software; fica guardado 10 anos após o descarte; upgrade do ARIA ou do Eclipse exige rodar de novo a bateria semeada e registrar.
  - **fonte · papel:** execuções e testes · não muda.

- **CAP-23 — Tabela perfil → capacidades configurável** (AD-11, FR-7; `escopo.md`, "Usuários")
  - **intent:** O admin ajusta, numa tabela de seleção em Configurações, que módulos cada perfil vê e que ações faz dentro deles (assinar, cadastrar, registrar).
  - **success:** A tabela mora no banco e nasce com a matriz do `escopo.md`; cada mudança é gravação por `nucleo.gravar`, com autor no log; a CAP-3 confere a tabela vigente no ato; teste prova que nenhuma configuração desliga as quatro travas (ver Constraints); admin continua sem ganhar módulo por ser admin.
  - **fonte · papel:** cadastro do admin no banco · não muda.

- **CAP-24 — Manifesto e raiz de composição única** (AD-40, AD-27, AD-31)
  - **intent:** Cada módulo declara o que é num `MANIFESTO`, e app e concentradora montam o sistema a partir de uma lista explícita.
  - **success:** O núcleo define o tipo `Manifesto` (dado puro: nome, classe, capacidades, verificações, tabelas, fachada); `isocentro/composicao.py` lista os módulos e é a única fonte de app e concentradora; as tabelas do manifesto alimentam o registro tabela → dono; `interface/composicao.py` lista telas e cartões da Torre pelo nome do manifesto e só o app a importa; não há descoberta por pasta nem registro por efeito de import; o Radioteraficha é o primeiro módulo com manifesto.
  - **fonte · papel:** código do repositório · não muda.

- **CAP-25 — Seções do PPR da Fundação** (PPR vivo, Documentação CAP-10)
  - **intent:** Os capítulos do PPR sobre o que este módulo conhece moram aqui, com dado e texto.
  - **success:** Identificação da instalação (razão social, matrícula CNEN, CNPJ, endereço, horário); classificação da instalação (grupo e subgrupo da NN-6.02); estrutura organizacional (titular, SPR, RT, substitutos, diretor clínico, como função no cadastro de equipe); descrição dos IOEs (equipe com a marca IOE, Documentação CAP-9). Seção do PPR = dado vivo lido do próprio módulo + texto versionado do módulo, exposto pela fachada (Documentação CAP-10); texto com versão, autor e data; dado sem fonte sai vazio. A primeira versão do texto vem do PPR vigente de cada clínica, citado.
  - **fonte · papel:** cadastro da clínica e da equipe (CAP-3, CAP-20) · entra no PPR.

## Constraints

- **Advisory:** nenhum resultado de verificação bloqueia ação no ISOCENTRO ou fora dele; a trava é a do ARIA (FR-5).
- **Somente leitura no ARIA, `variandw`, relatórios exportados e Eclipse.** Nenhuma escrita no Eclipse nesta spec (NFR-1, AD-16).
- **Dado de paciente e de funcionário não sai da rede do serviço** — nem para log, repositório, terceiros ou IA. CEL, BET e DUO são a mesma rede (AD-7, NFR-2).
- **Campo sem fonte nasce vazio** (`None` ou travessão, nunca 0 nem parecença); padrão marcado `[SUPOSIÇÃO]` no PRD só vale depois de confirmado pelo físico (NFR-4).
- **Nada se apaga nem se edita** em dado registrado; única exceção declarada: o espelho, que é cache (AD-5, AD-17).
- **Monólito modular:** um executável, sem plug-in em tempo de execução; `interface → modulos → nucleo ← adaptadores` (AD-1, AD-2).
- **Um só gravador no banco:** o código Python do núcleo; sem fila local; sem serviço ou API entre estação e banco (AD-9, AD-15, AD-23).
- **Classe IEC 62304 A para o núcleo** (`classificacao-62304.md`, 26/10/2026), com a trava do ARIA e a assinatura em papel como medidas externas (`riscos.md`). `rt` também é A; item sem linha no `classificacao-62304.md`: rigor C até o físico classificar (AD-35).
- **Regra de decisão** (`escopo.md`): toda decisão se apoia em referência; duas ou mais → a mais restritiva; sem base → item em `decisoes-sem-base.md` e opção mais conservadora, anunciada como provisória.
- **Quatro travas fora da tabela de capacidades**, no código e no banco: só o físico assina Aprovação Física e Duplo Check; o físico do Duplo Check nunca é o da Aprovação Física (FR-20); ninguém assina em nome de outro (FR-8); cada clínica vê só os próprios dados (NFR-6).
- **Mesmo código e versão** para app e concentradora; PyInstaller 6.21.0 onedir; CI em `windows-2025`; dependências fixadas exatas, atualizar exige revalidar (AD-20).
- **Esquema sem Alembic:** `.sql` numerado + tabela de versão, aplicado por `isocentro_dono`, nunca pelo app (AD-19).
- **Convenções:** nomes em português sem acento; caminhos por `raiz.py`; variáveis por `ambiente.ler`; configuração sessão → estação → serviço → padrão, com a tela dizendo qual venceu; `logging.getLogger(__name__)` sem dado de paciente; `FalhaDeLeitura` cai ao próximo degrau (espinha, Convenções).
- **Retenção:** log, backup e relatório de validação por 10 anos após o descarte do software (RDC 657 art. 5º §3º).

## Non-goals

- Módulos verticais: Plano (MVP 1–2), Garantia da Qualidade (MVP 3), Segurança do paciente (MVP 4), Documentação e conformidade (MVP 5), Tratamento, Indicadores, Conhecimento — cada um tem spec própria sobre esta.
- Redesenho visual das telas atuais do Radioteraficha para a Torre (Capa-Up, Fichinha, Total, Agenda, CQ Plano, Virtual): spec do módulo Radioteraficha.
- Migração de checklist, `registro_json`, `cadastro_sus` e correções para o banco: spec do Radioteraficha.
- Cobertura das obrigações (FR-37) e inventário SOUP (FR-38): módulo Software e sistemas.
- O avaliador ESAPI em C# propriamente dito: só o lado da importação está aqui.
- Canal de alerta externo (e-mail, mensageiro).
- Topologia com serviço ou API próprios (só se a G7 abrir para outros serviços).
- Unidade SAT, IORT, Streamlit no shell, escrita no ARIA ou no Eclipse.
- Busca global de paciente no shell.
- Camada `rt/` comum e a divisão de `dicom/` (AD-38, R-58): segue pela espinha.

## Success signal

- Em homologação, com o PostgreSQL em `clinica-python01` e duas estações de clínicas diferentes: uma verificação de demonstração passa por sombra → ativa, gera alerta `alta` com o app fechado (concentradora), o alerta aparece no Início da clínica certa e não na outra, é visto e resolvido com justificativa, e o verificador de integridade confirma o log contra a âncora do dia — enquanto alterar uma linha antiga do log é apontado com registro e posição.
- O relatório de validação do núcleo (CAP-22) está assinado pelo físico antes do primeiro módulo usar o núcleo em produção.

## Assumptions

- Valor inicial da tabela perfil → capacidades = matriz da UX, sem referência (`decisoes-sem-base.md` #9, físico e gestão).
- Severidade `alta`/`atencao`/`informativo` e justificativa ao seguir ou resolver `nao_conforme` em `alta` seguem as `[SUPOSIÇÃO]` do PRD (§3, FR-5).
- Sombra mínima de 30 dias, encurtável com justificativa (FR-4), só depois de confirmada pelo físico.

## Open Questions

- **Segregação IEC 62304 §5.3.5:** o cálculo TRS-398 (classe C) grava pelo núcleo (classe A), em choque com o AD-35; a decisão espera o texto da norma (lista de aquisição) e, até lá, com o TRS-398 no executável todo item do processo tem rigor C (`decisoes-sem-base.md` #34).
- **G8:** efeito no paciente e S, O, D de RF-1..RF-23 no `riscos.md`, pelo físico (R-16) — antes da 1ª gravação clínica.
- Relógio de referência (banco ou estação), fuso e regra de borda dos prazos; hora do fato × hora do lançamento para registros feitos em papel com o banco fora.
- Concentradora: vigilância da saúde (Q5) e execução dos gatilhos de janelas perdidas quando o banco volta.
- TLS em detalhe (`sslmode`, CA interna, `pg_hba.conf`) e credencial da concentradora; versões exatas de PySide6 e keyring a fixar.
- **U3** conteúdo da Zona 2 por perfil; **U8** como "visto" é marcado; texto da tela de banco inacessível.
- **G4:** sombra em dado de produção conta como uso real antes do relatório de validação?
- Destino do JSON ESAPI depois de importado (apagar ou quarentena).
- Adiados pela espinha para o épico do núcleo: versão do app conferida no banco e campos exatos do `MANIFESTO`; forma do retorno da fachada de consulta e entradas declaradas da verificação; capacidades declaradas pelo módulo dono e concedidas por clínica; dado de referência vindo da base (fichas, `qualidade.json`, versão).
- **NFR-5** `[SUPOSIÇÃO]`: painéis do shell abrem em menos de 3 s — confirmar o número.
