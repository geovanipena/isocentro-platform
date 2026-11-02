# Revisão independente: Update de 22/10/2026 da espinha (rubrica)

- **Objeto:** `ARCHITECTURE-SPINE.md`, diff do Update de 22/10 (AD-38 a AD-41; emendas a AD-2, AD-22, AD-35, semente, mapa, varredura, Deferred) e as últimas entradas do `.memlog.md`.
- **Método:** checklist da rubrica (cada Rule é imponível? previne a divergência declarada? contradiz AD existente? o Deferred deixa dois módulos divergirem? ratifica o código real?), conferida contra o código em `isocentro/dicom/`, `isocentro/papel/`, `isocentro/dominio/`, `isocentro/banco/` e `isocentro/dados/` por grep e leitura de trechos.
- **Data:** 22/10/2026. A espinha não foi editada.

## Veredito

A direção está certa (camada `rt` sem veredito, módulo como unidade de classe, composição estática, ESAPI à parte), mas **o AD-38 como está escrito não ratifica o código que ele manda mover**. A tabela "Hoje → Vai para" leva para `rt/` arquivos que leem disco, guardam cache em disco, têm trava de thread e importam `dominio` e `dados`, e o AD-2 emendado proíbe que adaptador importe `rt`, então o leitor de DICOM fica sem casa. Corrigir os achados A1 a A3 antes de abrir frente de migração; o resto pode entrar na próxima passada.

## Achados

### A1 — ALTA — AD-38, AD-2 e tabela da semente: `rt/` "sem arquivo, sem estado, importa só a si mesmo" contradiz os seis arquivos que a tabela manda para lá

O que o código faz hoje (medido em 22/10):

| Arquivo destinado a `rt/` | Viola o AD-38 em |
| --- | --- |
| `dicom/dicom_rt.py` | **I/O de arquivo**: `carregar_arquivo` (l. 90), `cabecalhos_arquivo` (l. 174), abre `.zip`/`.rar` (l. 141-228), grava `tempfile` (l. 152-153). **Importa o pacote**: `dominio.constantes` (l. 22 e cinco imports tardios), `dados.nomes` (l. 27) |
| `dicom/corpo3d.py` | **Estado e I/O**: cache em memória com `threading.Lock` (l. 359, 453-465), cache em disco com `write_bytes`/`unlink`/`glob` (l. 417-450), importa `isocentro.raiz` e `isocentro.dados.ambiente` (l. 420-421) |
| `dicom/dvh.py`, `cortes.py`, `ct_series.py`, `corpo3d.py` | **Desenham**: PIL e matplotlib para gerar PNG. Não é I/O, mas não é "ler e modelar"; o fluxograma já rotula `interface → rt` como "desenha" |

E o AD-2 emendado diz que núcleo **e adaptadores** não importam `rt`. Hoje `banco/capa_dados.py:1446` e `banco/tratamento_db.py:1372` importam `dicom_rt`; `banco/` é candidato natural a `adaptadores/variandw`. Pior: se `rt` opera sobre "objetos de RT já lidos" e adaptador não pode importar `rt`, então quem lê o arquivo DICOM do disco (a pasta do paciente, que não é `dicom_rede`) não pode devolver o modelo de `rt`. A Rule fica inexequível ou empurra a leitura de arquivo para dentro dos módulos (cada módulo com seu leitor, exatamente a divergência que o AD-38 diz prevenir).

**Correção proposta:**
1. Dividir `dicom_rt` na tabela da semente: leitura de arquivo, zip/rar e `tempfile` → `adaptadores/dicom/arquivo` (porta de leitura, devolve `pydicom.Dataset`); `parse_rtplan`/`parse_rtstruct`/geometria/SSD → `rt/`.
2. Decidir uma de duas e escrever: (a) adaptador devolve só `pydicom.Dataset` e `rt` modela (mantém a proibição); ou (b) adaptadores podem importar `rt` como tipos, como já importam o núcleo. Hoje a espinha não escolhe e o código faz (b).
3. Render (PIL/matplotlib) sai de `rt/` para `interface/` ou `modulos/radioteraficha/` (é o papel que usa o PNG), ou o AD-38 diz explicitamente que `rt` pode rasterizar sem estado. O cache de disco do `corpo3d` vai para quem desenha, com a pasta injetada.
4. As violações atuais entram na lista de exceções do AD-22 com data de saída, e numa linha nova da seção "Contradições com o código atual" (o Update não acrescentou nenhuma linha lá).

### A2 — ALTA — AD-38 e AD-39 contra AD-9/AD-26: a equipe clínica está dentro de `dicom_rt`, e iria para o código de classe C que "revisa a suíte inteira"

`dicom_rt.py` tem as listas `FISICOS` (l. 280), `MEDICOS` (l. 290), `EQUIPE_SAT` (l. 366), `unidade_da_pessoa`, `equipe_da_maquina`, `mesma_pessoa`, `medico_por_extenso`; `dados/equipe.py:18` depende delas ("Depende só de `dicom_rt`"). Também a unidade da máquina (`constantes.unidade_da_maquina`) e o texto de gantry para o papel (`gantry_texto`).

Mover `dicom_rt` inteiro para `rt/` faz de "entrou um físico novo" uma mudança em `rt`, que pelo AD-39(2) tem raio "suíte inteira" e pelo AD-35 emendado rigor de classe C. E contradiz o AD-9 (equipe migra para o PostgreSQL) e o AD-26 (entidades de referência são do núcleo): a mesma equipe ficaria em duas fontes, lista no código e tabela no banco. O AD-38 diz "sem veredito", mas não diz "sem dado da clínica", e é esse o furo.

**Correção proposta:** acrescentar à Rule do AD-38: "`rt` não contém dado do serviço (equipe, unidades, máquinas, tabelas de tolerância, abreviações locais); recebe isso por parâmetro". Na tabela da semente: casamento de nomes e listas → dono da equipe (núcleo/entidades, AD-26, ou módulo dono declarado); formatação para a ficha → `modulos/radioteraficha`.

### A3 — MÉDIA-ALTA — AD-40 contra AD-20: a raiz de composição única arrisca puxar Qt para a concentradora

A Rule diz que `composicao.py` é a lista única, que "app e concentradora montam a partir dela (a concentradora sem telas)", e que a tela "se registra em `interface/modulos/<m>/` pelo nome do manifesto". Não diz **quem** importa as telas. Se `composicao.py` importa `interface/modulos/*`, a concentradora importa Qt (quebra o AD-20, "empacotada sem Qt"); se a tela se registra por efeito colateral de import, é descoberta disfarçada (o AD-1 proíbe). E `composicao.py` não aparece na direção de dependência do AD-2 nem no teste do AD-22: o primeiro teste por `ast` vai acusar `composicao.py → modulos/*` ou precisar de exceção não escrita.

**Correção proposta:** `isocentro/composicao.py` importa só `modulos/*` (sem Qt, e o AD-22 reprova `composicao → interface`); `interface/composicao.py` (ou `run_gui.py`) importa a lista e casa cada tela pelo `MANIFESTO.nome`, com teste de que todo nome tem tela. Pôr os dois no fluxograma e no AD-2.

### A4 — MÉDIA — AD-39(2): o raio de revisão "pelos imports" não cobre o que não é import, e a classe no `MANIFESTO` não tem conferência

1. **Fora do grafo de imports:** `interface/` e `interface/modulos/<m>/`, `composicao.py`, `migracoes/*.sql` (schema muda o banco de todos), arquivos de dado lidos em tempo de execução (tabelas TMR/Scp por máquina, que decidem o 2º cálculo), specs do PyInstaller e `requirements.txt` (pydicom/numpy mudam o `rt`). A Rule só lista módulo, fachada, manifesto, `rt`, `nucleo`, adaptador. Uma ferramenta que "calcula o raio a partir do diff" vai devolver raio vazio para esses arquivos, e raio vazio lê como "não precisa revisar".
2. **Fluxo pelo motor:** pelo AD-3(3) um módulo reage ao resultado de outro pelo motor (verificação → alerta). Mudar uma verificação interna de `plano` muda o que outro módulo recebe sem import nenhum.
3. **Classe declarada pelo código:** o AD-39(1) põe a classe no `MANIFESTO`, que quem escreve é o desenvolvedor (ou a IA); a regra do projeto é que a classificação é do físico (`docs/qms`, AD-35 "até a classificação formal"). Nada impede o manifesto dizer B enquanto o `riscos.md` diz C.

**Correção proposta:** (1) regra de fechamento: "arquivo fora das categorias listadas → suíte inteira", com a lista explícita de dependências não-import (dados por máquina, migrações, dependências fixadas). (2) consumidores de uma verificação pelo motor contam como consumidores da fachada. (3) teste que confere a classe do `MANIFESTO` contra o documento de classificação assinado pelo físico; enquanto não existir, o manifesto só pode repetir o AD-35.

### A5 — MÉDIA — AD-35 emendado: `modulos/radioteraficha` continua classe B, mas é o módulo que imprime o papel da sala

O Update mexeu no AD-35 para pôr `rt` na classe C, e a tabela da semente leva `papel/` (ficha, capa, DRR) para `modulos/radioteraficha`. Esse módulo produz a ficha técnica com SSD, deslocamentos e ângulos que o técnico usa para posicionar o paciente; um número errado ali chega ao paciente (CLAUDE.md do projeto). Pelo AD-35 ele fica no "demais módulos: B [ASSUMPTION]". O AD-39(1) ("`rt` tem a classe do consumidor mais crítico") fica circular: `rt` é C por causa de `plano`, mas o consumidor que imprime não é C.

**Correção proposta:** incluir `modulos/radioteraficha` no rigor C provisório do AD-35, ou registrar no `.memlog.md` o motivo de B como decisão explícita a ser confirmada pelo físico.

### A6 — MÉDIA — AD-38: a fronteira "modelar × cálculo que sustenta veredito" não é imponível pelo teste

O teste do AD-22 confere imports; ele não distingue "geometria" de "cálculo que sustenta veredito". Casos reais na fronteira: o SSD (`dicom_rt`, com limites de sanidade `_SSD_MIN_CM` e `_tolerancia_z`) vai impresso na ficha; `dose3d` e `dvh` são importados por `dominio/qualidade.py:393,765,889` para os índices (veredito em `plano`). A Rule não permite decidir de qual lado ficam.

**Correção proposta:** critério mecânico: `rt` não contém número de corte que mude o resultado de uma verificação (tolerância, faixa, limiar), nem constante clínica; limite de sanidade de leitura que só devolve `None` pode ficar, documentado. Acrescentar ao teste: nenhum `rt/*` referencia `nucleo` nem ids do catálogo (AD-31).

### A7 — BAIXA — AD-41: contrato do JSON ESAPI com uma só ponta conferida

- O esquema mora no ISOCENTRO e o script grava "a versão do esquema que usa"; o AD-15 já reprova JSON inválido. Falta dizer se versões antigas conhecidas continuam aceitas (o script instalado não acompanha a release do ISOCENTRO) e como o `scriptsvarian` obtém o esquema (cópia com hash por versão publicada).
- O AD-15 diz "avaliador ESAPI (C#, somente leitura)"; o AD-41 lembra que o `scriptsvarian` tem scripts que escrevem no Eclipse. Vale dizer que só script marcado "somente leitura" no inventário de `modulos/software` pode produzir JSON aceito.
- `parallel-mu-check` "entra por importador único" sem destino declarado (provavelmente `modulos/plano`, junto com `paralelo.py`).

### A8 — BAIXA — AD-40 e AD-31: pontas soltas que o teste pode fechar barato

- Conferir que todo id em `MANIFESTO.verificacoes` tem prefixo igual a `MANIFESTO.nome` (AD-31) e que nenhum id aparece em dois manifestos.
- "Manifesto sem tela reprova" impede um módulo só de verificações de fundo (rodando só na concentradora). Se isso for intencional (toda verificação tem um lugar na Torre), escrever o motivo.
- O registro tabela → dono (AD-27) é do núcleo, mas passa a ser alimentado pelos manifestos; o núcleo não importa módulos (AD-2), então a injeção é pela composição. Dizer isso no AD-40.

## Deferred: o que deixa dois módulos divergirem

| Item adiado | Risco de divergência | Sugestão |
| --- | --- | --- |
| Q6 — destino de `dominio/constantes` | `rt` (via `dicom_rt`) e `papel` importam `constantes`; o AD-2 emendado proíbe `rt` de importá-la. Sem destino, a tendência é copiar as constantes de RT (técnica, modulação de gating) para dentro de `rt` e deixar o resto em outro lugar: duas fontes | Decidir junto do A1: constantes de RT do DICOM → `rt/`; unidades e máquinas → entidades de referência (AD-26) |
| Q6 — destino de `dados/equipe` | depende de `dicom_rt`; se for para o núcleo, viola "núcleo não importa `rt`" | Fechar com o A2 |
| Campos exatos do `MANIFESTO` | o AD-22 já testa manifesto ↔ tela; sem campos fixos, cada módulo escreve a classe de um jeito (`"C"`, `"classe C"`, `3`) | Fixar ao menos `nome`, `classe` (enum) e `verificacoes` agora; o resto pode esperar |
| Forma do retorno da fachada | (pré-existente) | sem mudança |

## Conferência com os AD existentes

| AD | Situação após o Update |
| --- | --- |
| AD-1 | Coerente: `rt` fora do núcleo, composição estática. Ressalva do A3 (registro de tela por efeito de import) |
| AD-3 | Coerente; o raio do AD-39 ignora o canal pelo motor do AD-3(3) (A4) |
| AD-9 / AD-26 | Contraditos pela ida da equipe para `rt` (A2) |
| AD-15 | Coerente; ver A7 |
| AD-20 | Mantido (uma versão); risco de Qt na concentradora pelo AD-40 (A3) |
| AD-27 | Coerente; injeção do registro pela composição não está escrita (A8) |
| AD-31 | Coerente; falta o teste de prefixo (A8) |
| AD-35 | Emendado para `rt`; deixa `radioteraficha` em B (A5) |
| AD-37 | Coerente com o congelamento dos repositórios a integrar |

## O que o Update ratifica certo

- `papel/` ser do Radioteraficha: confirmado. Fora de `papel/`, só `isocentro/interface/*` (12 arquivos), testes e `tools/caso.py`/`tools/comparar_fontes.py` o importam. Mas `papel/capa_pdf.py:32` importa `banco.capa_dados`: depois da mudança é módulo → adaptador, e a violação já está na lista do AD-22 pelo lado do `capa_dados`; vale acrescentar `capa_pdf` à lista.
- `dicom_rede` → `adaptadores/dicom`: coerente; `dominio/gatilho.py:44` o importa, e já está nas exceções.
- `paralelo`, `qualidade`, `qualidade_metodo` → `modulos/plano`: coerente com o AD-38 (veredito no dono); hoje importam `dicom.dvh`/`dose3d`, o que vira `plano → rt`, permitido.
