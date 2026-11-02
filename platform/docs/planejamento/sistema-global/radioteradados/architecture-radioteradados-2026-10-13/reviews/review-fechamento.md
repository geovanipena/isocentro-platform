---
tipo: conferência de fechamento dos achados de revisão
alvo: ../ARCHITECTURE-SPINE.md (versão nova, com AD-1 a AD-14)
insumos: review-adversario.md, review-rubric.md, review-clinica.md, review-reconcile-prd.md, review-verificacao.md (escritos contra a versão anterior); ../../prd-radioteradados-2026-10-13/prd.md
data: 2026-10-13
código conferido: banco/tratamento_db.py (registro = PatientId, linha 1462 e consultas `WHERE p.PatientId = ?`), dados/indice.py (`REGISTRO_PATH = pasta_do_app()`), dados/config_servico.py (`ISOCENTRO_CONFIG`)
---

# Conferência de fechamento — Architecture Spine Radioteradados

**Graves (39): FECHADO 28 · PARCIAL 11 · ABERTO 0.**

Entram como graves os críticos e altos do adversário (15) e da rubrica (11), os importantes da revisão clínica (11) e os de gravidade alta do reconcile (2). A revisão de verificação não tem gravidade; os três itens dela aparecem ao fim.

---

## 1. Achados graves

### Revisão adversária (6 críticos, 9 altos)

| # | Achado | Situação | O que fecha / o que falta |
| --- | --- | --- | --- |
| B-01 | Retrato guarda a lista de origem com nomes | **PARCIAL** | AD-5 ("nenhum arquivo do estado do serviço contém nome ou registro de paciente: só `ChaveCurso`") e AD-6 (retrato por curso). Mas a `ChaveCurso` do AD-13 é `(PatientId do ARIA, ctrCourseSer)`, e no projeto o **registro do paciente é o `PatientId`** (`tratamento_db`: `registro=capa_db._txt(pid)`, `WHERE p.PatientId = ?`). Retrato, cache e classificações passam a carregar o registro. Ver contradição N-1. |
| B-02 | Duas bases de curso (R-07 atesta uma, indicadores usam outra) | FECHADO | AD-12 (base única do `tratamento_db`, estendida) e AD-9 (chave R-07 válida porque atesta a mesma base). |
| B-03 | Chave de curso indefinida / `DimCourseID` instável | FECHADO | AD-13 (`ChaveCurso` com chaves de origem, nunca `DimCourseID`, tipo único em `dominio/indicadores`). Tensão com o AD-12 em N-3. |
| B-04 | Reclassificação depois do retrato | FECHADO | AD-6, 4º item (retrato não muda; mês "retrato desatualizado"; novo retrato versionado acrescentado). |
| B-05 | Estações com executáveis diferentes gravam o retrato | FECHADO | AD-6, 2º e 3º itens (congelar só com fichas aprovadas e versão de fórmula igual à aprovada; retrato grava versões de ficha, fórmula, programa e impressão digital da configuração) e "Implantação e operação". |
| B-06 | Supressão "< 5" sem público, sem complementar | FECHADO | AD-7 (`suprimir(agregados, publico)`, `Agregado` cru, complementar, gestão sem recorte por médico). |
| B-07 | Máquina com dois identificadores | FECHADO | AD-10 e AD-13 (`ctrResourceSer`; `MachineId` só rótulo). Ressalva já registrada na verificação: em `DWH.DimMachine` sozinha o `ctrResourceSer` veio vazio — o mapeador precisa achar a junção certa. |
| B-08 | `config_servico` só guarda strings | FECHADO | AD-10 (seção tipada, `versao`, leitor que distingue ausente de ilegível → `Ausente`). |
| B-09 | Identidade de pessoa e de médico do curso | FECHADO | AD-8, 3º item (vínculo login → `ctrResourceSer` em `usuarios.json`; "médico do curso" definido uma vez no `indicadores_db`) e AD-13 (pessoa = login + nome de exibição na data). |
| B-10 | Permissão conferida só na tela; papel vazio vê tudo | **PARCIAL** | Gravação fechada (AD-8, 4º item: `indicadores_registro` confere a cada gravação) e papel vazio/desconhecido não recebe a lista (AD-8, 2º item). Falta dizer **qual módulo** faz a entrega filtrada da `ListaOrigem` (domínio, registro ou a própria tela?). "Antes de chegar ao widget" admite que a tela receba a lista inteira e filtre — o mesmo vazamento por outro caminho. |
| B-11 | Configuração muda o número sem mudar a versão | FECHADO | AD-4, última frase (impressão digital da configuração no `Agregado`; "configuração alterada depois da aprovação") e AD-10 (autoria por chave). |
| B-12 | Ficha técnica com dois donos | FECHADO | AD-4 (fichas e parâmetros no código; estado guarda só aprovações). |
| B-13 | Invalidar aprovação: gravar ou derivar | FECHADO | AD-4 ("aprovada" derivada por função única; aprovação nunca editada). |
| B-14 | Frequência: `_marcar_frequencia` impura, padrão diário | FECHADO | AD-2 (`dominio/ritmo.py`; desconhecida = `None`; falha = não identificada; fallback diário só no `prever_fim`). Resto da SQL da frequência em C1. |
| B-15 | Duas funções de dias úteis | FECHADO | AD-2 (todo cálculo de dia útil com calendário único). |

### Revisão por rubrica (3 críticos, 8 altos)

| # | Achado | Situação | O que fecha / o que falta |
| --- | --- | --- | --- |
| C1 | Frequência: função impura, teto silencioso de 400, colapso não ratificado | **PARCIAL** | AD-2 fecha a regra pura, o colapso ("a diária ganha…"), o `None` e a falha. Falta dizer **onde mora a SQL da frequência** e que o teto `_MAX_NA_CONTAGEM = 400` de `_marcar_frequencia` sai: o AD-12 só tira o teto da "base de cursos". Um mês com mais de 400 registros pode continuar sem frequência nenhuma, agora como "não identificada" em massa — a taxa de interrupção some sem erro. |
| C2 | `QThread` na conexão única do `capa_db` com 6 s | FECHADO | AD-14 (conexão própria por thread, tempo-limite próprio, consulta agregada, janela de horário de tratamento). |
| C3 | Retrato não diz o que guarda para recortes e lista | FECHADO | AD-6, 3º item (resultado por curso com atributos de recorte; recorte = filtro sem banco; nomes resolvidos na exibição). |
| A1 | Precedência "variável → serviço → padrão" por arquivo | **PARCIAL** | AD-5 fixa raiz única para aprovações, classificações, conferência, cache, retratos e índice. Mas o `config_servico.json` — onde AD-10 põe feriados, capacidade e **físico responsável** — continua aceitando `ISOCENTRO_CONFIG`, e o AD-5 não o inclui. O AD-8 diz que o físico responsável "nunca vem de variável de ambiente", o que só vale se o caminho do arquivo também não vier. Falta pôr o `config_servico.json` na mesma raiz única. |
| A2 | Contagem de frações sem dono | FECHADO | AD-2 (frações e pausas em `dominio/ritmo`) e AD-12 (frações prescritas = função única). |
| A3 | "Data da carga" sem fonte | FECHADO | Convenção "Ausência" (`Ausente("carga do data warehouse não mapeada")` ao lado da data do cálculo) e Deferred (nenhum mês congelado; NFR-2 pelo cache). A consequência contra o PRD está em N-2. |
| A4 | Papel vazio e identidade do médico | FECHADO | AD-8, 2º e 3º itens. |
| A5 | Recorte sem dono nem regra de atribuição | FECHADO | AD-1 (recorte só em `dominio/indicadores`), AD-4 (regras de atribuição na ficha), AD-3 (atributos de recorte na `ListaOrigem`). |
| A6 | Onde mora a ficha técnica | FECHADO | AD-4. |
| A7 | Versões diferentes do executável | FECHADO | AD-6, 2º item, e "Implantação e operação". Lacuna menor em N-5. |
| A8 | Lista de origem dentro do `Resultado` até o PDF | FECHADO | AD-3 (`Agregado` e `ListaOrigem` separados; PDF só aceita `Agregado`, testado). |

### Revisão clínica (11 importantes)

| # | Achado | Situação | O que fecha / o que falta |
| --- | --- | --- | --- |
| 1 | Data da carga sem fonte; mês além de 3 meses aparece como quê | **PARCIAL** | A exibição está fechada pela convenção "Ausência". Falta o rótulo do mês que passou do teto de 3 meses e não pode ser congelado (sem data da carga, sem aprovação ou sem o físico agir): o enum de estados não tem esse caso, e o PRD manda que ele já seja definitivo (N-2). |
| 2 | AD-6 × FR-17 (retrato congelado contra "a tela recalcula com a versão vigente") | **PARCIAL** | Fechou congelar com definição não aprovada (AD-6, 2º item). Continua aberto: (a) depois que uma versão nova da ficha é aprovada, o mês congelado mostra o retrato (contra o FR-17) ou recalcula (contra o AD-6)? O estado "retrato desatualizado" só é disparado por reclassificação; (b) congelar não exige a saída da faixa EXPERIMENTAL (AD-9), e o retrato não grava o estado da faixa. |
| 3 | Reserva do FR-21 sem fonte | FECHADO | AD-6, 1º item (cache provisório = "última leitura", degrau "cache"), convenção "Degrau". |
| 4 | Classe dos módulos compartilhados e regressão | **PARCIAL** | O teste de regressão da Ficha Virtual e da Capa entrou (AD-2, convenção "Testes", `test_ritmo.py`). A classe IEC 62304 de `tratamento_db`, `capa_dados`, `auth` e `config_servico` continua sem decisão. O impacto cresceu: agora o AD-2 **move** a tradução e o colapso da frequência e a contagem de frações para fora do `tratamento_db`, e a Capa (papel) passa a depender de `dominio/ritmo`. |
| 5 | Origem dos parâmetros iniciais e do mínimo de 5 | FECHADO | AD-4 (parâmetros, inclusive o mínimo de 5, são código versionado da ficha, sem valor oficial antes da aprovação). A referência de cada valor fica com o físico na aprovação. |
| 6 | Testes de RD-2 a RD-5 fora do seed | FECHADO | Convenção "Testes" (RD-3, RD-4, RD-5, pureza, PDF só com `Agregado`); AD-2 liga RD-2. O caso semanal do RD-2 depende da pergunta 5 (Deferred). |
| 7 | `admin` vendo a lista de origem | FECHADO | AD-8, 2º item (`admin` não recebe). |
| 8 | Retrato com nome e registro na pasta da rede | **PARCIAL** | Nome fechado (AD-5). Registro **não**: a `ChaveCurso` leva o `PatientId`, que é o registro (N-1). |
| 9 | Casos conferidos à mão com dado real em `tests/` | FECHADO | Convenção "Testes" (só pseudônimos `900NNNN`, `varrer_identidade`). |
| 10 | Pasta do serviço com "padrão" de reserva | **PARCIAL** | AD-5 tira a variável por arquivo, mas a raiz única é `indice.REGISTRO_PATH`, que no código é `pasta_do_app()`: ao lado do executável ou, **no modo fonte, a raiz do repositório**. Falta a regra "sem pasta do serviço acessível, a gravação é recusada com aviso" e a garantia de que os JSON novos entram no `.gitignore` (a verificação já apontou que precisam entrar). |
| 11 | PDF não sabe se a faixa EXPERIMENTAL vale | FECHADO | AD-3 (estado "experimental" no `Agregado`) e AD-7 ("o PDF carrega o estado de cada `Agregado`, inclusive experimental"). |

### Reconcile PRD → spine (2 de gravidade alta)

| # | Achado | Situação | O que fecha / o que falta |
| --- | --- | --- | --- |
| L-1 | Data do dado sem fonte; mês nunca vira definitivo | **PARCIAL** | (a) fechado pela convenção "Ausência". (b) aberto: rótulo do mês com mais de 3 meses que não congela (igual à clínica 1). (c) aberto: o NFR-1 diz que "um mês só é calculado depois que a última carga cobre o mês inteiro"; o AD-6 barra só o congelamento, e o provisório continua calculado com carga possivelmente incompleta sem aviso próprio (só o `Ausente` da data). |
| L-2 | Lista identificada no retrato, na gestão e no `admin` | **PARCIAL** | (b) retrato sem nome e (c) `admin` fora estão fechados (AD-5, AD-8). (a) a camada que corta a lista por papel continua sem nome (igual a B-10), e o registro entra pelo `PatientId` da `ChaveCurso` (N-1). |

---

## 2. Médios e baixos que continuam abertos

Os demais médios e baixos das cinco revisões estão fechados pela versão nova (B-16 a B-22, M1 a M11, B1 a B6, L-3, L-5, L-6, L-8, L-9, observações clínicas 13 a 17).

| Origem | Achado | Situação |
| --- | --- | --- |
| Reconcile L-4 (média) | Retrato × FR-17 depois de aprovar versão nova | PARCIAL — igual à clínica 2. |
| Reconcile L-7 (média) | "Padrão" da pasta do serviço pode cair na estação ou no repositório | PARCIAL — igual à clínica 10. |
| Clínica 12 (observação) | Somente leitura garantida só pela disciplina do código | ABERTO — nenhum AD exige usuário de banco só com leitura nem limita a `SELECT`. |

---

## 3. Contradições novas introduzidas pela versão nova

| # | Contradição | Onde | Gravidade |
| --- | --- | --- | --- |
| N-1 | A `ChaveCurso = (PatientId do ARIA, ctrCourseSer)` leva o registro do paciente, e o AD-5 diz que nenhum arquivo do estado do serviço contém "registro de paciente: só `ChaveCurso`". No projeto, `registro` **é** o `PatientId` (`tratamento_db.py`, linha 1462 e todas as consultas por registro). Retratos, cache provisório e classificações passam a conter o registro na pasta compartilhada, legível pela estação da gestão. Saída: chave de origem não identificadora (`ctrPatientSer` + `ctrCourseSer`, se o DW os expuser) ou declarar o registro como dado de paciente, com as regras de RD-5. | AD-13 × AD-5 (e AD-6, diagrama "sem nome de paciente") | crítica |
| N-2 | O PRD congela o mês **por regra** ("no máximo até 3 meses depois do fim do mês; depois congela como definitivo", §3; "o definitivo é calculado uma vez e guardado", NFR-1; "junho está DEFINITIVO", UJ-1). O spine torna congelar uma **ação manual** do físico, com pré-condições (data da carga, todas as fichas aprovadas, versão igual), e o Deferred diz que nenhum mês congela na v1. Um mês pode ficar provisório indefinidamente e a v1 não entrega nenhum mês definitivo. A troca precisa ser registrada como mudança do PRD ou ter uma regra para o mês além do teto. | AD-6 + Deferred × PRD §3, NFR-1, UJ-1 | alta |
| N-3 | O AD-12 manda reaproveitar a base de cursos do `tratamento_db`, que hoje identifica o curso por `DimCourseID` e o paciente por `PatientId`. O AD-13 proíbe `DimCourseID`. Reaproveitar exige trocar a chave do `tratamento_db` (mexe na Ficha Virtual) ou mapear `DimCourseID → ctrCourseSer` a cada carga. Além disso, estender a consulta (período, paginação, chave nova) muda a consulta que o R-07 atestou: o AD-9 considera o `LISTA_VERIFICADA_EM` válido "porque atesta a mesma base", e deixa de ser a mesma. | AD-12 × AD-13 × AD-9 | alta |
| N-4 | O enum de degrau do spine (banco, banco local, cache provisório, retrato) substitui o do PRD (banco, espelho ou relatório exportado — Glossário "Degrau da fonte", FR-21, addendum) sem registrar a troca. | Convenção "Degrau" × PRD §3 | média |
| N-5 | Estação com versão de fórmula diferente "calcula como não oficial" (Implantação), mas o AD-6 não a impede de gravar o **cache provisório**, que é a "última leitura" de todas as estações. Um cálculo de executável antigo pode virar a reserva do serviço. | AD-6, 1º item × "Implantação e operação" | média |
| N-6 | "Recorte por médico não é oferecido ao papel `gestao`" (AD-7) restringe o FR-3 ("todos os indicadores respeitam o recorte" por máquina, médico, sítio e convênio, para "o usuário"). O PRD só proíbe o ranking (§5). É restrição defensável, mas não está no PRD. | AD-7 × PRD FR-3 | baixa |
| N-7 | O enum de estados do AD-3 não tem "em andamento" (mês atual, FR-2) nem o caso do mês além do teto sem congelamento (N-2); a convenção diz que tela e PDF só usam estados enumerados. | AD-3 × PRD FR-2, §3 | baixa |

---

## 4. Itens da revisão de verificação (sem gravidade)

| Item | Situação |
| --- | --- |
| AD-2/AD-1: `_marcar_frequencia` não é pura | FECHADO — AD-2 (`dominio/ritmo.py`); resto em C1. |
| AD-10: `config_servico` não guarda valores estruturados | FECHADO — AD-10 (seção tipada). |
| Stack: Qt 5.15 fora do suporte, Python 3.12 só segurança | FECHADO — Stack e Deferred (migração PyQt6). |
