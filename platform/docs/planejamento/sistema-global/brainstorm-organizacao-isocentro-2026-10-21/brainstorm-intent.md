---
origem: brainstorm-organizacao-isocentro-2026-10-21 (.memlog.md, 116 ideias)
data: 2026-10-21
destino: bmad-spec
---

# Intenção: organização do acervo, do conhecimento e do código do ISOCENTRO

## Veredito

- **Acervo e `conhecimento/`: acima do usual.** Vale manter e estender o caminho referencias → texto → fichas → matriz/índices/mapa gerados, a citação `[CÓDIGO p. N]` conferida na imagem, o nome padronizado, o isolamento em `_restrito/` e o cabeçalho da ficha como fonte de verdade.
- **Repositório do programa: no usual, com dois pontos a fechar.** As dependências diretas já têm versão exata e os arquivos de execução na raiz são deliberados (`isocentro/raiz.py`) e estão no `.gitignore`. Faltam duas coisas:
  - **D1:** as dependências transitivas não têm versão fixa (29 pacotes no `.venv`, 10 no `requirements.txt`).
  - **D2:** em desenvolvimento, dado de paciente (`registro_fichas.json`, `notas_posicionamento.json`, `correcoes_capa.json`) fica na árvore do repositório, fora de `_restrito/`.
- **Desequilíbrio de tamanho:** `interface/` tem 27 mil das 54 mil linhas, com os maiores arquivos em `ficha_pdf.py` (3.577), `gui.py` (2.913) e `tratamento_db.py` (2.534). Isso já é o pilar 4 do `DESTINO.md`.

## Riscos reais (nenhum é de classificação)

1. Duas fontes de verdade, Drive e local: "documento novo entra nos dois lugares".
2. Regras operacionais que só existem na memória do assistente, como "catalogar só lê 1 nível", "nunca remendar o HTML do mapa" e "raiz do BMad = repositório".
3. Commits e pushes atrasados (`conhecimento/` sem commit, `ppr-streamlit` sem push).
4. Junções invisíveis de `_restrito/` para dentro do repositório.
5. Sete repositórios (isocentro, isocentro-conhecimento, ppr-streamlit, parallel-mu-check, preplan só local, scriptsvarian, Estruturas-auxiliares_API) sem mapa de papel e estado.

## Decisões propostas

| # | Decisão | Por quê |
| --- | --- | --- |
| P1 | Fechar D1 (versão fixa das transitivas) e D2 (pasta de dados de desenvolvimento configurável, apontando para `_restrito/estacao`) | build reproduzível (62304) e LGPD coerente com `_restrito/` |
| P2 | Sentido único entre Drive e local, escolhido pelo usuário, com script e relatório de diferenças no lugar do `robocopy /MIR` manual | acaba com a divergência |
| P3 | Regra operacional mora no README/`CLAUDE.md` da pasta; a memória só aponta. Criar `CLAUDE.md` curto em `Documents\isocentro\` e em `conhecimento\` | sessões novas leem as regras |
| P4 | `fontes.csv` única (código, título, emissor, ano, tipo, vigência, DOI, URL, SHA-256, caminho); `CATALOGO.md` e `aliases.json` gerados dela; um CLI `acervo` (adicionar, catalogar, converter, verificar) | o CÓDIGO já é a citekey; resolve duplicata, vigência, exportação CSL/ABNT e sincronização |
| P5 | Ligação Conhecimento → Programa: preencher `isocentro:` nas fichas, marcar nos testes o requisito coberto e gerar os valores numéricos usados no executável a partir da ficha | rastreabilidade fonte → requisito → código → teste (IEC 62304, RDC 657) |
| P6 | Pastas físicas por TIPO de fonte; tema (01–11) e etapa da cadeia (14) como etiquetas; POPs CLINICA (10) e incidentes internos (11) saem de `referencias/` para documentos do serviço com controle de revisão; `catalogar` recursivo | acaba com o conflito entre as duas classificações; documento interno controlado não é bibliografia |
| P7 | `REPOS.md` na raiz central: função, remoto, ramo ativo e estado (ativo, congelado, a integrar) de cada repositório; `preplan` ganha remoto privado | mapa da teia; nenhum repositório só local |

## Ordem

P1 → P2 → P3 → P4 → P5 → P6. P7 pode entrar a qualquer momento. Um passo por vez, cada um aceito só com a suíte verde e, no acervo, com `gerar_matriz.py` sem órfã nova.

## Fora

- Reorganizar tudo de uma vez.
- Mudar `papel/`, `interface/` ou `dominio/` por causa desta iniciativa (a divisão de arquivos grandes segue nas frentes do pilar 4).
- Levar qualquer coisa de `_restrito/` ao Drive ou ao GitHub.

## Decidido pelo usuário (21/10/2026)

- **P2:** a fonte de verdade é a pasta **local**. Até a base ser finalizada, arquivo novo entra pelo Drive e é sincronizado Drive → local, só copiando o que é novo e nunca apagando nada no local, com relatório do que chegou, das duplicatas por hash e do que existe só no local.
- **Base finalizada = lista de aquisição zerada** (57 itens em 21/10/2026). Item impossível de obter sai com o estado `indisponível — motivo`. A partir daí, o sentido passa a ser local → Drive, e a data da troca fica registrada no README da pasta central.
- **P4:** só a `fontes.csv`, sem Zotero.
- **P5:** a ligação ficha → código → teste fica para quando o módulo GQ for construído. Os números que já estão no código (por exemplo D98 95/90 em `qualidade.py`) não mudam agora.
- **P7:** por enquanto só o `REPOS.md`. Vira meta-repositório à medida que os projetos forem implementados no ISOCENTRO.

## Execução (21/10/2026)

| Passo | Estado | O que ficou | Onde |
|---|---|---|---|
| P1 | feito | R-56: `constraints.txt` + `tools/gerar_constraints.py`, CI instala com `-c` (985a11d). R-57: `ISOCENTRO_PASTA_APP` no `raiz.pasta_do_app()`; nesta estação aponta para `_restrito\estacao`, junto com `ISOCENTRO_DADOS_FEIXE` (addcb89). Suíte 2331 OK com e sem a variável | este repositório |
| P2 | feito | `sincronizar.py` (Drive → local; só relata, ou copia com `--aplicar`; nunca apaga nem sobrescreve; relatório em `sincronizacao.md`). Primeira aplicação: 5 arquivos em `_superadas` | pasta central (fora do git) |
| P3 | feito | `CLAUDE.md` curto na pasta central e em `conhecimento/`; regras que só estavam na memória foram para o README do `conhecimento` (ee31c60) | pasta central; `isocentro-conhecimento` |
| P4 | feito | `conhecimento/matriz/fontes.csv` (234 linhas) é o acervo de `referencias/`; `acervo.py` (verificar, catalogar, adicionar, converter) gera `CATALOGO.md` e `aliases.json`. Mapa idêntico byte a byte (60089fd). Pendente: emissor vazio em 128 linhas, DOI em só 18, ano errado quando o título tem número de resolução | pasta central; `isocentro-conhecimento` |
| P5 | feito, só o mapeamento | Usuário reabriu em 21/10 com escopo reduzido: `codigo_isocentro` e `testes_isocentro` nas fichas `sim`, mostrados no índice, na cobertura e no Mapa (7cead6b). 23 atividades `sim` sem código passaram a `candidato` (2a56017). Números do código e testes não mudaram. Pendente: B10 sem teste; `dados/backup.py` sem teste | `isocentro-conhecimento` |
| P6 | feito (22/10) | Usuário decidiu manter as pastas 01–11; tipo e etapa da cadeia são colunas da `fontes.csv` (`etapas` calculada pelo `acervo.py catalogar`). A pasta 11 só tem relatórios públicos de acidentes, então ficou. Os 11 documentos internos da pasta 10 foram para `servico/pops` com `servico/documentos.csv`; `sincronizar.py`, conversor e Mapa leem o lugar novo (5fd9d84). Mapa sem mudança além da P5 | pasta central; `isocentro-conhecimento` |
| P7 | feito (22/10), só o `REPOS.md` | Oito repositórios com função, remoto, ramo em uso e estado (ativo, a integrar, congelado). Ficou de fora o remoto privado do `preplan`, que publicaria o repositório. Só nesta máquina: `preplan` inteiro (sem remoto, 14 arquivos sem commit), ramo `programa-cq-tg142` do `ppr-streamlit`, ramos `v2`–`v6` e `layout/form-estruturas` do `isocentro` | pasta central (fora do git) |

O Mapa do Conhecimento não foi republicado no artefato depois da P4 e da P5.
