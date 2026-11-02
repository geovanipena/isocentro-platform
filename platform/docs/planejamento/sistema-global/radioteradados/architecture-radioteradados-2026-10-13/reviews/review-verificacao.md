# Revisão de verificação — ARCHITECTURE-SPINE.md (Radioteradados)

Data: 13/10/2026. Lente: cada decisão foi conferida (projeto, web, ambiente) ou só afirmada?

**Veredito:** a espinha está bem ancorada no projeto. As versões batem com o `requirements.txt` e com o ambiente instalado, e quase todo o código citado existe como descrito. Ficam três pontos: o AD-2 chama de "puras" funções que não são; o AD-10 supõe que o `config_servico` guarda valores estruturados, e hoje ele não guarda; e a Stack não registra que o PyQt5/Qt 5.15 está fora do suporte padrão.

## Stack

| Item | Status | Fonte |
| --- | --- | --- |
| Python 3.12 | confirmado no projeto e na web | `requirements.txt` ("Validado com Python 3.12"); `python --version` = 3.12.10; `.pyc` cpython-312. devguide.python.org/versions: 3.12 em fase **security** (só correções de segurança, sem binários de correção comuns), fim de vida em 10/2028. Ainda suportado, mas não é mais a linha de bugfix (essa é a 3.14). |
| PyQt5 5.15.11 | confirmado no projeto; **desatualizado quanto a suporte** (na web) | `requirements.txt` e versão instalada = 5.15.11. PyPI: 5.15.11 é a última versão, de 19/07/2024 (nada novo em mais de 2 anos), wheels `cp38-abi3` (rodam no 3.12). Qt Company: o suporte padrão do Qt 5.15 acabou em 26/05/2025 (último LTS comercial 5.15.19). Depois disso só há manutenção paga de segurança estendida (ESM); o Qt 5 de código aberto não recebe mais correções. A decisão "sem dependência nova" vale para a v1, mas a espinha não registra esse risco nem um caminho para PyQt6/Qt 6.8 LTS (suporte até 10/2029). |
| matplotlib 3.10.9 | confirmado no projeto; atrás da última versão (na web) | `requirements.txt` e versão instalada = 3.10.9. PyPI: a última é a 3.11.2. A fixação é deliberada (comentário do `requirements.txt`), e a espinha não afirma que seja a mais recente. |
| reportlab 4.5.1 | confirmado no projeto; atrás da última versão (na web) | `requirements.txt` e versão instalada = 4.5.1. PyPI: a última é a 5.0.1 (versão maior). A fixação é deliberada. |
| pyodbc 5.3.0 | confirmado no projeto e na web | `requirements.txt` e versão instalada = 5.3.0. PyPI: 5.3.0 é a última, `requires_python >=3.9`. |
| "Sem dependência nova" | confirmado no projeto | Os cinco itens já estão no `requirements.txt`. O `QThread` vem do PyQt5, que já está lá. |

## Código citado

| Item | Status | Fonte / observação |
| --- | --- | --- |
| `tratamento_db._marcar_frequencia` | confirmado no projeto, com **ressalva** | `banco/tratamento_db.py:1599`. **Não é função pura:** chama `capa_db._consultar` (SQL), altera as linhas no lugar e falha em silêncio (devolve `None`, e toda linha conta como diária). O texto do AD-2 ("ler as funções puras de frequência... do `tratamento_db`") não confere com o código. Importar o `tratamento_db` a partir do `dominio/` também traz o `capa_db` e o `capa_dados`, o que fere o "dominio/ é puro" do AD-1. |
| `_RITMO` | confirmado no projeto, com ressalva | `tratamento_db.py:530`. É privado (`_`). As chaves são textos já traduzidos ("Uma Vez por Dia"...) por `capa_dados.traduzir_frequencia`. O comentário do código diz que a frequência desconhecida **cai em (1, 1)**. O AD-2 pede o contrário ("fora do `_RITMO` = não identificada"), então o Radioteradados não pode reaproveitar esse fallback. |
| `PropertyType = 7` (prescrição) | confirmado no projeto | `tratamento_db.py:1591`. |
| `tratamento_db.dias_uteis_entre` | confirmado no projeto | `tratamento_db.py:667`: conta "ESTRITAMENTE entre" e não tem parâmetro de feriados. A docstring diz que isso é de propósito. Estender a função com o padrão "sem feriados" é compatível. |
| `tratamento_db.LISTA_VERIFICADA_EM` | confirmado no projeto | `tratamento_db.py:92`. Hoje vale `""`. |
| `indicadores_db.VERIFICADO_EM` | não se aplica (módulo novo) | Segue o padrão do `LISTA_VERIFICADA_EM`. |
| `capa_db` (conexão via pyodbc) | confirmado no projeto | `banco/capa_db.py`; `_consultar` é usado pelo `tratamento_db`. |
| `servidor_local.traduzir` | confirmado no projeto | `banco/servidor_local.py:170`. Existe `tests/test_servidor_local.py`. Não foi conferido quais construções de T-SQL ele cobre: o AD-11 já prevê estender a tradução. |
| `datas_relevantes` (precedência variável → serviço → padrão; lock) | confirmado no projeto | `dados/datas_relevantes.py`: `caminho()` usa `ENV_ARQUIVO` e depois o arquivo ao lado de `indice.REGISTRO_PATH`; as gravações passam por `indice.travar_arquivo`. |
| `indice.travar_arquivo` | confirmado no projeto | `dados/indice.py:133`. |
| `auth.PAPEIS` | confirmado no projeto | `dados/auth.py:45`: admin, fisico, medico, dosimetrista, tecnico, enfermeiro, recepcionista. O `enfermeiro` já existe e o `gestao` ainda não existe (é novo, como a espinha diz). |
| `fichinha.MODOS_POR_PAPEL` | confirmado no projeto | `interface/fichinha.py:2296`. Papel desconhecido cai em `MODOS_PADRAO` (linha 2329): o `gestao` precisa entrar explicitamente para não herdar o padrão. |
| `config_servico` (chaves novas) | confirmado no projeto, com **ressalva** | `dados/config_servico.py`: `CHAVES` é uma tupla fechada, `valor()` devolve `str` e `definir(chave, caminho_novo, ...)` grava texto (caminhos de rede). Lista de feriados, capacidade por máquina e códigos de atividade são dados estruturados, e a API atual não os comporta. O `[ASSUMPTION: chaves no mesmo arquivo]` exige estender a API (tipo e validação), e isso não está dito. O arquivo já está no `.gitignore`. |
| `MachineId` / `ctrResourceSer` | confirmado no projeto | `banco/agenda_db.py:19-25`. Ressalva do próprio código: em `DWH.DimMachine` sozinha, o `ctrResourceSer` veio vazio. |
| `agenda_db` com o GammaMed Plus | confirmado no projeto | `agenda_db.py:107,116`. A espinha já deixa como pendência confirmar que é a fonte da última sessão. |
| `papel/rodape.py` | confirmado no projeto | Existe e é carimbado no `showPage` do reportlab. |
| `interface/carregadores.py` (padrão QThread) | confirmado no projeto | `carregadores.py:18,133` (`_CarregarTudo(QThread)`). |
| `ui.py`, `estilo.py`, `log_app` | confirmado no projeto | Existem em `interface/` e `dados/`. |
| `tools/tela.py`, `tools/gerar_executavel.py` | confirmado no projeto | Existem. |
| `.gitignore` para o estado do serviço | confirmado no projeto (padrão) | Arquivos de serviço como `config_servico.json` e `checklist_pre_tratamento.json`, com seus `.lock`, já estão listados. Os novos JSON precisam entrar no mesmo trabalho. |

## Adiados

| Item | Status | Fonte |
| --- | --- | --- |
| SQLModel, pyqtgraph | confirmado no projeto (estudo) | `docs/BIBLIOTECAS_EXTERNAS.md` (linhas 5, 176, 247). As versões não foram conferidas, o que é aceitável para itens adiados. |
| Data da carga do `variandw` | não confirmado | A própria espinha registra como desconhecida. O AD-6 depende dela para gravar o retrato. |

## Itens para corrigir na espinha

1. **AD-2 / AD-1:** `_marcar_frequencia` faz SQL e não é pura. Uma saída: separar no `tratamento_db` uma função pura (valor bruto → ritmo ou "não identificada") e deixar a leitura no `banco/`. Outra: o `indicadores_db` busca a frequência e o `dominio` recebe só o valor.
2. **AD-10:** dizer que o `config_servico` precisa aceitar valores estruturados (hoje só aceita texto) e acrescentar ao `CHAVES`.
3. **Stack:** registrar que o Qt 5.15 / PyQt5 está fora do suporte padrão desde 05/2025 e sem release desde 07/2024, e que o Python 3.12 está só em correções de segurança (fim de vida em 10/2028).

Fontes web: https://pypi.org/pypi/PyQt5/json · https://devguide.python.org/versions/ · https://pypi.org/pypi/matplotlib/json · https://pypi.org/pypi/reportlab/json · https://pypi.org/pypi/pyodbc/json · https://www.qt.io/blog/commercial-lts-qt-5.15.19-released · https://www.qt.io/blog/extended-security-maintenance-for-qt-5.15-begins-may-2025
