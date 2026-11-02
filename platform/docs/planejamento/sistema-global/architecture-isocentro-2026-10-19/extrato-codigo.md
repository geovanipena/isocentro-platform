# Extrato do código: ISOCENTRO (varredura de 19/10/2026)

Varredura feita somente com leitura do repositório `isocentro` (branch `main`, HEAD `df411c6`). Cada afirmação cita `arquivo:linha`.
Os arquivos com mais de mil linhas foram consultados só pelo `tools/mapa.py`, por grep ou por trechos. O que não foi encontrado
está escrito como "não existe". Nada aqui foi presumido.

---

## 1. Stack real

| Item | Fato | Fonte |
|---|---|---|
| Linguagem | Python 3.12, Windows 11 (validado) | `requirements.txt:8`; `README.md:13`; `ruff.toml` `target-version="py312"` |
| GUI | **PyQt5==5.15.11** (não há PySide) | `requirements.txt:11` |
| DICOM | pydicom==3.0.2; pynetdicom==3.0.4 (opcional) | `requirements.txt:14,31` |
| Numérico/imagem | numpy==2.4.6, matplotlib==3.10.9, pillow==12.2.0 | `requirements.txt:15,18,19` |
| PDF | reportlab==4.5.1, pypdf==6.13.1; PyMuPDF==1.28.2 só para testes e ferramentas, fora do exe | `requirements.txt:22-23,41` |
| Banco | pyodbc==5.3.0 (opcional; exige driver ODBC de SQL Server na estação) | `requirements.txt:36`; `capa_db.py:61` |
| Outros | rarfile==4.2 (exige unrar/7z) | `requirements.txt:26` |
| Política de versão | as versões são fixadas exatas; para atualizar, é preciso revalidar a ficha contra o TPS | `requirements.txt:1-6` |
| Dependências ausentes | não há Pydantic, SQLAlchemy/SQLModel, pyqtgraph, pytest nem pyproject. Ficam como propostas em `docs/BIBLIOTECAS_EXTERNAS.md` §3 e §7 | `requirements.txt` (inteiro) |
| Testes | `unittest` da stdlib (`python -m unittest discover -s tests`), 93 arquivos `.py` em `tests/`. Ordem aleatória em `tests/ordem_aleatoria.py` e recorte por import em `tools/testar.py` | `CLAUDE.md:116-133`; `README.md:337-340` |
| Lint | ruff==0.16.4, só como linter (E4, E7, E9, F, B, PLE) | `ruff.toml:24-31`; `testes.yml:48` |
| CI | GitHub Actions, `.github/workflows/testes.yml`, em todo push e PR, com três jobs: `lint` (ubuntu), `suite` (**windows-latest**, Qt offscreen, ordem normal e depois aleatória) e `empacotar` (windows, `gerar_executavel.py --sem-zip --sem-smoke`) | `testes.yml:21-106` |
| Empacotamento | PyInstaller (instalado só no CI e na estação, fora do requirements). Três specs no modo onedir (`EXE`+`COLLECT`): `Isocentro.spec` (GUI, console=False), `VarreduraIsocentro.spec` (exclui PyQt5 e matplotlib) e `CheckupClinica.spec` (exclui PyQt5 e `isocentro.interface`). `tools/gerar_executavel.py` compila, confere `DENTRO_DO_PACOTE`, faz o smoke test, apaga o que o smoke semeou e zipa | `Isocentro.spec:51-87`; `VarreduraIsocentro.spec:60`; `CheckupClinica.spec:51`; `gerar_executavel.py:1-30,64,149` |
| Distribuição | binários vão como GitHub Release. Todas as estações rodam o mesmo exe a partir do share `\\fileserver.clinica.example\Gerenciamento de Pacientes\` | `README.md:367-369`; `docs/INSTALAR_CONCENTRADORA.md:66-71` |
| Pontos de entrada | `run_gui.py` (app), `run_varredura.py` (concentradora `clinica-python01`, Tarefa Agendada, sem Qt), `run_checkup.py` | `run_varredura.py:1-13`; `DESTINO.md:32-37` |
| Tamanho | 81 módulos no pacote, 54,5 mil linhas. Maiores: `ficha_pdf.py` 3577, `gui.py` 2913, `tratamento_db.py` 2534, `fichinha.py` 2432, `dicom_rt.py` 2217 | `wc -l` |

## 2. Pacotes e camadas de `isocentro/`

A divisão é por papel no fluxo, desde 09/09/2026 (`CLAUDE.md:48-75`; `README.md:273-330`).

| Pacote | Papel | Módulos-chave |
|---|---|---|
| `raiz.py` | onde se grava (`pasta_do_app`, a pasta do exe) e de onde se lê (`pasta_assets`, `_MEIPASS`) | `raiz.py:47,59` |
| `banco/` | origem do dado clínico (três degraus) | `capa_db`, `capa_espelho`, `capa_dados`, `tratamento_db`, `agenda_db`, `atividades_db`, `gatilho_db`, `banco_local`, `servidor_local` |
| `dominio/` | regra e cálculo | `paralelo`, `qualidade`, `qualidade_metodo`, `aprendizado`, `agendamento`, `constantes`, `gatilho`, `gatilho_registro`, `gatilho_relogio` |
| `dicom/` | leitura de DICOM-RT e transformação em imagem | `dicom_rt`, `dicom_rede`, `ct_series`, `cortes`, `corpo3d`, `dose3d`, `dvh` |
| `papel/` | o que sai impresso (diff aqui significa que o papel mudou e o usuário precisa ser avisado) | `ficha_pdf`, `capa_pdf`, `drr`, `rodape` |
| `interface/` | telas. Padrão `ui.py` e `estilo.py`; telas no esquema "controle_*" (pergunta ao banco) + tela (desenha) | `gui`, `fichinha`, `capa`, `tratamento*`, `agenda_tela`, `radioteradados_tela`, `controle_*` |
| `dados/` | o que o app grava e relê dele mesmo | `registro_json`, `indice`, `auth`, `sessao`, `equipe`, `correcoes`, `config_servico`, `historico`, `log_app`, `ambiente`, `preferencias`, `datas_relevantes`, … |

**Regras que já são impostas por mecanismo:**
- Padrão visual: `tests/test_padrao_visual.py` lê o código-fonte com `ast` e reprova `QDialog`/`QTabWidget` crus e cor hexadecimal crua fora de `ui.py`, `estilo.py` e `aparencia.py`. As exceções ficam nomeadas e com motivo em `EXCECOES` (`test_padrao_visual.py:1-40,106,132,154`). A ordem e o comportamento dos botões são cobertos por `tests/test_padrao_ui.py:53-362`.
- Todo módulo que loga usa `logging.getLogger(__name__)` e consta da lista do histórico (`tests/test_loggers_app.py:79,100`; `log_app.py:30-40`).
- Caminhos vêm de `raiz.py`, nunca de `__file__` (regra do `CLAUDE.md:64-68`, sem teste dedicado encontrado).
- Variáveis de ambiente são lidas por `ambiente.ler`, que aceita os três prefixos `ISOCENTRO_`, `RADIOTERAFICHA_` e `FICHAPY_` (`CLAUDE.md:382-385`).
- O robô (`tools/robo.py` e `robo_trava.py`) recusa editar `papel/`, `interface/` e `dominio/` (`DESTINO.md:19-28`).
- `tests/test_varrer_identidade.py` e `tools/varrer_identidade.py` procuram dado real de paciente nas linhas que entram no commit (`CLAUDE.md:364-368`).

**Não existe teste de arquitetura sobre a direção dos imports.** O grafo medido com `ast` sobre o pacote mostra o seguinte:
- Usam `dados`: todos os pacotes. Usam `dominio`: `interface`, `papel`, `dicom` (`dicom_rt.py:22`) e `banco` (`tratamento_db.py:47`).
- **Violações do "domínio sem interface"** (`CLAUDE.md:58`):
  - `dominio/qualidade_metodo.py:26-33` importa PyQt5 e `interface.ui`/`estilo`, ou seja, é widget dentro de `dominio/`;
  - `dominio/gatilho_relogio.py:55` usa `QThread`/`QTimer`;
  - `dominio/gatilho.py:444` faz import tardio de `interface.simulacao`.
- **`banco` importa `interface`:** `capa_dados.py:1349,1413,1522,1540` fazem import tardio de `interface.simulacao`. O `simulacao.py` não importa Qt no topo (`simulacao.py:28-38`), e por isso a Varredura sem PyQt5 funciona.
- **`dados` importa `banco` e `dicom`:** `correcoes.py:87`, `cadastro_sus.py:217-218`, `notas_setup.py:37` e `equipe.py:18`.
- O spine do Radioteradados já previa um teste de pureza para `dominio/indicadores` e `dominio/ritmo` (`radioteradados/architecture-.../ARCHITECTURE-SPINE.md:49,57`). Esse teste não existe, e os dois módulos também não.

## 3. Acesso a dados

**Data warehouse `variandw` (ARIA), somente leitura**
- Conexão por pyodbc, importado tarde (`capa_db.py:358,457`).
- String de conexão (`capa_db.py:371-384`): `Trusted_Connection=yes` (identidade Windows/SSPI), `ApplicationIntent=ReadOnly` (exceto no driver "SQL Server" de 2000) e `pyodbc.connect(..., readonly=True)`.
- Porta 1433; limite de 6 s no login e na consulta (`capa_db.py:56,391`).
- Drivers aceitos, em ordem de preferência: ODBC 18, ODBC 17, SNAC 11, "SQL Server" (`capa_db.py:61`).
- Quando falha, a reconexão espera um recuo crescente (`capa_db.py:64-90`).
- Gargalo único `_consultar`, que levanta `FalhaDeLeitura` (`capa_db.py:571,581-601`).
- Docstrings: "Nunca há INSERT/UPDATE" (`capa_db.py:22-23`), e `tratamento_db`, `atividades_db` e `dicom_rede` repetem "só leitura" (`tratamento_db.py:8`, `atividades_db.py:22`, `dicom_rede.py:7-9`).
- `tratamento_db` reutiliza a conexão do `capa_db` (`tratamento_db.py:8-10`).
- O SQL é T-SQL escrito à mão, com nomes e colunas tirados da Data Lineage Tool 15.6 (`tratamento_db.py:21-24`).
- **Portões `VERIFICADO_EM`:** com o portão vazio, o módulo devolve vazio e a tela avisa.

  | Portão | Data | Fonte |
  |---|---|---|
  | `tratamento_db.VERIFICADO_EM` | 20/08/2026 | `tratamento_db.py:79` |
  | `tratamento_db.LISTA_VERIFICADA_EM` | **vazio** | `tratamento_db.py:92` |
  | `atividades_db` | 02/09/2026 | `atividades_db.py:49` |
  | `gatilho_db` | 04/09/2026 | `gatilho_db.py:56` |
  | `agenda_db` | 23/09/2026 | `agenda_db.py:69` |

- `banco_local.py` (SQLite) **não é o DW**. Ele grava a linha crua respondida para reproduzir sem rede e só entra em jogo se `ISOCENTRO_BANCO_LOCAL` estiver definido (`banco_local.py:1-37,48,200-269`). O SQLite é aberto `mode=ro` na leitura (`banco_local.py:257`).

**Três degraus da capa** (`CLAUDE.md:240-250`)
1. `capa_db` (banco).
2. `capa_espelho`: JSON por paciente, gravado no instante em que o banco respondeu, `VERSAO=1`, com o paciente em claro e expiração em 60 dias (`capa_espelho.py:1-23,45-59`). Fica "ao lado do índice", isto é, na pasta do app no share (`capa_espelho.py:62-71`), e por isso serve às outras estações.
3. `capa_dados`: relatórios exportados (CSV), lidos e nunca escritos, como último recurso.

A tela anuncia o degrau e a data em uso.

**DICOM**
- `dicom_rt` lê TC, RP, RS e RD localmente.
- `dicom_rede` fala com o DB Daemon do ARIA por C-ECHO, C-FIND, C-GET e C-MOVE. A sonda de 10/09/2026 mostrou que este ARIA **não faz C-GET**, e por isso o caminho é C-MOVE, com `receber` ouvindo na porta 104 (`dicom_rede.py:11-31`; `docs/AMBIENTE.md` tabela de variáveis).
- A automação passa por `gatilho_db` (plano pronto), `gatilho` e `gatilho_registro` (memória de janela e de marca d'água, compartilhada por lock do SO) e pela concentradora (`gatilho_registro.py:1-30`).

**Onde mora o estado gravável hoje.** Não há banco próprio: é **JSON**, e quase tudo fica na pasta do app no share.

| Estado | Onde | Fonte |
|---|---|---|
| Registro versionado do paciente `FICHA_{NOME}_{REG}.json` + PNG (e zip) | pasta do paciente | `registro_json.py:236-371`; `README.md:259-271` |
| Índice central `registro_fichas.json` (derivado, reconstruível) | `pasta_do_app()` | `indice.py:1-10,28-38,428` |
| `usuarios.json` | `ISOCENTRO_USERS_DIR` ou ao lado do índice | `auth.py:1-5,51-62` |
| `sessoes.json` | ao lado de `usuarios.json` | `sessao.py:59-66` |
| `historico_uso.jsonl` | `ISOCENTRO_LOG_DIR` ou ao lado do índice | `historico.py:30-41` |
| `correcoes_capa.json`, `config_servico.json`, `checklist_pre_tratamento.json`, `cadastro_sus.json`, `notas_posicionamento.json`, `inventario_imobilizadores.json`, `preferencias.json`, `espelho_capa/` | ao lado do índice (share) | `correcoes.py:10-14,43`; `config_servico.py:11-14`; `checklist.py:20-26`; `notas_setup.py:51`; `inventario.py:45` |
| Equipe (médicos e físicos): `~/.isocentro_medicos.json` e `~/.isocentro_fisicos.json`, **por estação**, guardando só o delta do padrão; migra os antigos `.radioteraficha_*` e `.ficha_py_*` | home do usuário | `equipe.py:8-10,27-35` |
| Log cru `~/.isocentro.log` | home | `log_app.py:28` |
| `~/.ficha_py_pacientes.db` | **nenhuma referência no código** (resíduo) | grep vazio |

**Autenticação, sessão e equipe**
- `auth`: PBKDF2-HMAC-SHA256 com 200 mil iterações e salt por usuário (`auth.py:24,88-96`).
- `PAPEIS` = admin, fisico, medico, dosimetrista, tecnico, enfermeiro, recepcionista (`auth.py:45-46`). O papel só decide as Configurações (admin) e quais abas aparecem (`fichinha.MODOS_POR_PAPEL`, `fichinha.py:2302-2306`). Pelo próprio código, "não é controle de acesso" (`auth.py:34-37`).
- O primeiro admin é semeado como admin/admin, com troca obrigatória (`auth.py:239`; `CLAUDE.md:394`).
- `sessao`: uma sessão por usuário, e o último login vence; o admin fica isento (`sessao.py:1-26,45`).

## 4. Mutação de estado e convenções

**Gravação**
- Gravação atômica com temporário na mesma pasta, `fsync` e `os.replace`: `registro_json.py:24-52`, `indice.py:62-84`, `correcoes.py:107-128`, `config_servico.py:156-224` (com novas tentativas no "acesso negado" do Windows), `capa_espelho.py:118-119`, `auth.py:83`, `cadastro_sus.py:60`.
- Exclusão mútua entre estações por lock do SO (`msvcrt.locking`/`flock`) sobre `.lock` permanente: `indice.travar_arquivo` (`indice.py:133-182`). É reaproveitado por `correcoes.py:61`, `config_servico.py:201`, `datas_relevantes.py:112-144` e `gatilho_registro`. Não obter o lock no índice não impede gravar, porque o índice é derivado (`indice.py:150`).

**Append-only**
- `historico_uso.jsonl` é JSON Lines e só recebe acréscimos (`historico.py:3-6,54-71`). É **best-effort** (engole qualquer exceção, `historico.py:70`) e **não tem hash nem encadeamento**.
- O registro do paciente acrescenta versão só quando há mudança (`registro_json.py:250-256,391-397`).
- **Não existe log com cadeia de hash** em lugar nenhum do código. O único `hashlib` em `dados/` é o da senha.

**Autoria**
- Correção, configuração e checklist gravam `por` e `em`: `correcoes.py:166-170`, `config_servico.py:126-129`, `checklist.py:28-30` (por item).
- `correcoes` grava só o campo que diverge e **apaga a entrada** quando não sobra divergência (`correcoes.py:171-180`). Mutável, não é append-only.

**Erros**
- O banco levanta `FalhaDeLeitura`, e quem chama cai para o espelho ou para a mensagem "não deu para perguntar" (`banco_local.py:28-31`).
- Campo sem fonte vira `None` ou travessão, nunca 0 (`radioteradados_tela.py:52-54`).
- Avisos da preparação são acumulados em vez de lançar exceção (`gatilho.py:436-455`).
- `except Exception: # noqa: BLE001` com comentário do motivo é o padrão da casa.

**Logging** (`log_app.py:168-193`)
- `logging.basicConfig` grava em `~/.isocentro.log` (INFO).
- O `HandlerHistorico` replica WARNING+ dos módulos do app no histórico compartilhado.
- Duas portas de entrada chamam o `configurar`: o app e a varredura.

**Configuração**
- Precedência: sessão, depois variável da estação, depois `config_servico.json`, depois o padrão. A tela mostra qual venceu (`CLAUDE.md:386-393`).
- Sem `QSettings`.

**Concorrência**
- A capa é montada na thread da UI (`capa_db.py:386-391`).
- As cargas pesadas usam `carregadores.py` (QThread). O Radioteradados é síncrono (`controle_radioteradados.py:14-17`).

## 5. ESAPI e C#

**Não há integração em tempo de execução** entre o ISOCENTRO e os scripts ESAPI: nenhum import, JSON trocado ou chamada (grep `esapi` em `isocentro/` só acha comentários).
- O `dominio/qualidade.py` é **porte em Python** do plug-in `Plano_Índices_e_Qualidade.cs` (repositório `scriptsvarian`) e mantém "as mesmas quatro chaves do relatório ESAPI" (`qualidade.py:3-4,41`).
- O "avaliador ESAPI (JSON)" existe só como requisito no PRD (FR-2, `prd.md:252`).
- O escopo põe os scripts ESAPI em repositório próprio, dois deles com escrita (FiF e estruturas) (`docs/qms/escopo.md` tabela, linhas "Scripts ESAPI").

## 6. O que já existe e corresponde ao PRD

| PRD | No código hoje |
|---|---|
| Motor de verificação (FR-1 a FR-6, FR-41): cadastro, proveniência, sombra, log encadeado | **Não existe.** O que se aproxima: `aprendizado.py` (faixa mín–máx do histórico, `MIN_AMOSTRA=6`, `aprendizado.py:31`, nunca preenche) e os status OK, Atenção, Fora da faixa e Sem dado de `qualidade.py:50-58` |
| 2ª checagem (FR-10 a FR-15) | `dominio/paralelo.py` (TMR×Scp, TG-219, porte do `parallel-mu-check`). A trava `maquina_do_plano` compara o nome exato, sem acento e sem caixa (`paralelo.py:179-194`). Não calcula filtro nem usa MLC (IMRT/VMAT fica como rastreio grosseiro) (`paralelo.py:17-36`). Em `dados_feixe/` só há tabelas `ELEKTA_SAT`, então todo resultado sai como DEMONSTRAÇÃO (`DESTINO.md:45-50`) |
| Qualidade e tolerâncias | `qualidade.py`: ICRU 83, RTOG, Paddick, MCSv/SAS. `CALIBRADO = False` (`qualidade.py:64`), com tolerâncias da literatura (`qualidade.py:61-70`) |
| Ritmo (classe A em `classificacao-62304.md`) | **`dominio/ritmo` não existe.** A frequência e a contagem de frações continuam dentro de `tratamento_db` (o spine do Radioteradados propõe extrair). `dominio/agendamento.py` monta a sequência de frações da ficha |
| Radioteradados | Protótipo de tela: `interface/radioteradados_tela.py` e `controle_radioteradados.py`. Os cartões do núcleo RDC aparecem como "Em construção" (`radioteradados_tela.py:35-42`). Só a Operação tem número, e vem das consultas da Agenda (`controle_radioteradados.py:1-17`). Não existem `dominio/indicadores` nem `banco/indicadores_db` |
| Agenda e fila (FR-17, FR-42) | `banco/agenda_db.py` (verificado em 23/09) e `atividades_db.py` (pendências do care path por `ctrResourceSer`) |
| Incidentes (FR-29 a FR-32) | **Nenhum código.** Só `docs/planejamento/sistema-global/incidentes/SPEC - Módulo incidentes v0.1.md` |
| CQ e vencimentos (FR-22 a FR-36) | **Nenhum código** (o Vencimentos está no `ppr-streamlit`, fora do repositório) |
| Identidade e assinatura (FR-7, FR-8) | Login, sessão única e papéis existem (§3). **Não há assinatura registrada** com objeto e versão. O checklist grava quem e quando por item (`checklist.py:28-30`) |

## 7. Fatos do `docs/qms` (resumo fiel)

**escopo.md** (decidido pelo físico em 13/10/2026)
- Módulos: ISOCENTRO (ficha, capa, registro, paralelo, Qualidade, Radioteradados), PPR e Scripts ESAPI (`escopo.md` tabela).
- O que **não faz**:
  - não escreve no ARIA nem no DW;
  - não escreve no Eclipse, exceto por script ESAPI gravável validado em ambiente não clínico;
  - não envia dado pessoal a terceiros (a extração de ASO do PPR passa a ser local, R-15).
- Fronteiras de gravação: "na pasta do paciente (PDF e registro versionado) e ao lado do app (configuração e índices)".
- **A tabela de usuários e perfis está vazia.**
- Em aberto: perfis, pasta do serviço na rede, critério de validação dos scripts graváveis.

**classificacao-62304.md**
- Só duas linhas, as duas **classe A** (13/10/2026, Geovani Pena): o Radioteradados e o `dominio/ritmo`.
- O resto não tem classe.

**riscos.md**
- RD-1 a RD-5, todos do Radioteradados (fórmula, interrupção, reidentificação abaixo de 5, mês com carga incompleta, vazamento para repositório ou log).
- Aprovados em 13/10/2026. **S, O e D estão vazios.**

**revisao-clinica.md**
- Prompt do revisor adversário, com nove checagens: fonte do dado, somente leitura, degrau anunciado, papel com aviso, máquina certa, tolerância com origem, dado de paciente, rastreabilidade e classe.
- A resposta é uma tabela que termina com o número de achados bloqueantes.

**LEIA-ME.md**
- `escopo`, `classificacao` e `riscos` são escritos pelo físico, nunca pela IA. Enquanto vazios, o agente pergunta.

## 8. Contradições

**(a) "Não sai da máquina" contra banco central em servidor da clínica**
- `README.md:8-9`: "Os dados do paciente **não saem da máquina**: tudo roda em processo local, e o que é gravado vai para a pasta do próprio paciente". O `BIBLIOTECAS_EXTERNAS.md:37-38` repete isso como regra, e é com base nela que o Streamlit é recusado (`:267-275`).
- O PRD diz outra coisa. NFR-10 e G6 colocam um banco central de verificações, assinaturas, CQ e incidentes em servidor da clínica (`prd.md:1030-1035,1185-1187`), compartilhado por CEL, BET e DUO. A NFR-2 já troca a "máquina" por "**rede do serviço**" (`prd.md:1004-1008`).
- **O código já não cumpre a frase do README.** Usuários, sessões, histórico, correções de cadastro, checklist e o **espelho com dado clínico em claro por 60 dias** ficam no share `\\fileserver...`, lido por todas as estações (`capa_espelho.py:46-53`; `INSTALAR_CONCENTRADORA.md:70-71`; `gatilho_registro.py:24-26`). A regra real, na prática, é "não sai da rede do serviço".
- O `escopo.md` (Fronteiras: "pasta do paciente e ao lado do app") não cita nem o share nem o banco central. A G6 continua bloqueando até o escopo ser atualizado.
- Não existe hoje nenhum servidor de banco próprio: todo o estado é JSON com lock de arquivo, e o `BIBLIOTECAS_EXTERNAS.md:308-340` já aponta o `.lock` como sintoma.

**(b) Outras contradições**
1. **Perfis em três versões.**
   - Código: 7 papéis com `admin` como papel (`auth.py:45`), e o docstring desatualizado diz "Papéis: admin e fisico" (`auth.py:8`).
   - PRD FR-7: 5 perfis (físico, dosimetrista, radioterapeuta, técnico, SPR/gestão), sem médico, enfermeiro nem recepcionista (`prd.md:352-354`).
   - UX: 7 perfis com "médico radioterapeuta" e "SPR/gestão", e admin como permissão (`EXPERIENCE.md:90`).
   - O `escopo.md`, que o FR-7 indica como fonte, tem a tabela vazia.
   - O papel do código "não é controle de acesso" (`auth.py:34-37`), enquanto o FR-7 manda que só o físico assine.
2. **Clínicas com nomes diferentes.** O PRD usa CEL, BET e DUO. O código usa `atividades_db.UNIDADES = ("ANA","BET","CEL")` (`atividades_db.py:133`) e `constantes.UNIDADES = ("Clinica","SAT")` (`constantes.py:19`). A equivalência entre ANA e DUO não foi encontrada no código.
3. **Classe A atribuída a módulo inexistente.** `classificacao-62304.md` classifica `dominio/ritmo`, que não existe; o cálculo correspondente está em `banco/tratamento_db.py`.
4. **"Domínio sem interface"** (`CLAUDE.md:58`; `README.md:290`) é violado por `qualidade_metodo.py`, `gatilho_relogio.py` e `gatilho.py:444`. `banco` importa `interface` (`capa_dados.py:1349…`). Nenhum teste impede.
5. **Log do FR-3** (append-only, hash encadeado, retenção de 10 anos) contra o histórico atual, que é JSONL sem hash, best-effort e editável por qualquer estação no share.
6. **FR-2 cita um avaliador ESAPI por JSON**, mas não há canal ESAPI → ISOCENTRO. O que existe é um porte em Python.
7. **CI desatualizado na documentação.** `docs/AMBIENTE.md:433-435` diz que a suíte roda "no Linux". O `testes.yml:14-17,52-54` roda em Windows desde 15/10/2026.
8. **Números envelhecidos.**
   - Tamanho do `gui.py`: 5.727 linhas no `DESTINO.md:55`, 5,4 mil no `AMBIENTE.md:86`, 5.654 no `CLAUDE.md:98`; hoje são 2913.
   - "61 módulos" no `CLAUDE.md:51` (hoje são 81 em `isocentro/`).
   - "1.945 testes em 160 s" (`CLAUDE.md:117`), medido em 14/09.
9. **Painel do radioterapeuta "sem faixa EXPERIMENTAL"** (pilar 2): continua bloqueado, porque `LISTA_VERIFICADA_EM = ""` (`tratamento_db.py:92`). O PRD condiciona o MVP 2 à R-07 (`prd.md` P12).
10. **README "Testes"** descreve só os testes de SSD (`README.md:337-356`), mas a suíte cobre o app inteiro. Também diz `unittest -v` sem dependência extra, enquanto três testes usam PyMuPDF (`requirements.txt:38-41`).
