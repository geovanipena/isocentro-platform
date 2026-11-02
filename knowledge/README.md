# Conhecimento: a base do ISOCENTRO em forma de uso

Esta pasta transforma o acervo (`referencias/`, `manuais/`, `codigo-externo/`) em Markdown pesquisável e o liga à prática do físico médico. **O acervo original continua sendo a fonte**: aqui só entra o que é derivado dele, e todo número citado aponta para o documento e a página.

| Camada | Pasta | O que tem | Como é gerada |
| --- | --- | --- | --- |
| 1. Texto integral | `texto/` | Cada PDF/DOC convertido para `.md`, com `<!-- p. N -->` antes de cada página | `scripts/converter_referencias.py` (determinístico) |
| 2. Fichas | `fichas/referencias/`, `fichas/manuais/`, `fichas/codigo/` | Um `.md` curto por item: o que exige, com que tolerância, onde está escrito | Leitura do texto integral, conferida no PDF |
| 3. Matriz | `matriz/` | Atividades do físico × referências × manuais × código × ISOCENTRO; lacunas | `scripts/estender_catalogo.py` + `scripts/gerar_matriz.py` (lê o cabeçalho das fichas) |
| 4. Índices | `indices/` | Por atividade, por norma, por equipamento, por repositório | `scripts/gerar_matriz.py` |
| Fichas de atividade | `fichas/atividades/` | **Centro da prática**: uma ficha por atividade (A01…), com exigência, tolerâncias lado a lado, como fazer por máquina, conduta, registro e lacuna no PPR | Escrita a partir das fichas de fonte (o valor mora na ficha de fonte, com página) |
| Dados do serviço | `servico/` | Só dados técnicos dos PPRs (equipamentos, instrumentos, testes), sem pessoas; `servico/<CLÍNICA>/qualidade.json` = programa de CQ proposto, importável no `ppr-streamlit` | `scripts/extrair_ppr.py`, `scripts/extrair_ppr_pdf.py`, `scripts/gerar_programa_cq.py` |

## Espinha da correlação

`matriz/atividades.csv` = as 74 obrigações do catálogo v1 (`programa/isocentro/docs/planejamento/sistema-global/research-catalogo-atividades-fisico-medico-radiot-2026-10-13/catalogo-v1.csv`, IDs inalterados) + itens de **PRÁTICA** (nível `PRÁTICA`, origem `extensão-2026-10-16`). Área nova **I. Avaliação clínica do plano**. Obrigação fiscalizada e boa prática ficam sempre distinguíveis pela coluna `nivel`.

## Regras

- **Fonte de verdade das ligações é o cabeçalho da ficha** (`atividades:`, `refs:`, `repos:`…). A matriz é gerada; não editar à mão.
- **Elo com o ISOCENTRO (P5, 21/10/2026).** `isocentro:` é `sim` só quando o programa já cobre a atividade, `candidato` quando ela poderia entrar nele e `nao-se-aplica` no resto. Toda atividade `sim` registra onde: `codigo_isocentro:` e `testes_isocentro:`, caminhos relativos a `programa/isocentro`. Em ficha agrupada, cada item leva o ID (`[H01:sim, H02:candidato]`, `[H01:isocentro/dominio/paralelo.py]`). O `cobertura.md` lista `sim` sem código, código sem teste e caminho que sumiu.
- **Organização do acervo (P6, 22/10/2026).** As pastas `01`…`11` de `referencias/` ficam como estão; tipo de fonte e etapa da cadeia são colunas da `matriz/fontes.csv` (a `etapas` é calculada pelo `..\acervo.py catalogar` a partir do `vinculos.csv`, por isso ele roda depois do `gerar_matriz.py`). POPs e a lista do CarePath são documentos do serviço: moram em `../servico/pops/` (tabela `../servico/documentos.csv`), mas o texto continua em `texto/10 POPs CLINICA/` e o Mapa os mostra no grupo de sempre.
- Todo limite, tolerância ou frequência numérica traz `[CÓDIGO p. N]`. Valor com símbolo (±, γ, ≤) é conferido na imagem da página, porque o texto extraído pode trocar o símbolo (`±` → `�`, `γ` → `c`).
- `obrigatório` só para norma brasileira vigente (NN, RDC, Lei, NR). TG, MPPG, IAEA, ICRU = `recomendação`.
- Nada identificado de paciente entra aqui (ver `../_restrito/LEIA-ME.md`).
- `texto/` é regenerável; `fichas/` é trabalho intelectual — editar à mão é permitido e esperado.
- `servico/` guarda só dado técnico dos PPRs, **nunca pessoas**. Os PPRs originais têm CPF: ficam em `G:\Meu Drive\2. TRABALHO\CLINICA\1. Outros` e nunca na pasta SKILLS, que é compartilhável. As planilhas `QA_TrueBeam`/`QA_VitalBeam` têm nome de paciente: não copiar.
- A base bibliográfica não é por clínica: nada de filtro ou separação por CEL/BET/DUO no acervo nem no Mapa.
- CSV de `matriz/` se escreve com `csv.writer` do Python, nunca à mão: célula com `;` precisa de aspas.
- `catalogar.py`, `converter_referencias.py` e `gerar_mapa.py` só leem **um nível** de cada pasta temática: documento novo vai direto na pasta `01`…`11`, sem subpasta.
- `.xls` e `.zip` não vão para `texto/`; ler com pandas + xlrd (instalados no `.venv`).
- Outra sessão pode estar escrevendo fichas neste repositório ao mesmo tempo: commitar só os próprios arquivos.
- `PENDENCIAS.md` só ganha linha nova; o que está lá não se cobra.

## Documento novo no acervo

1. Arquivar no Drive (`SKILLS\ISOCENTRO\<pasta temática>`), com o nome `CÓDIGO - Título (ano).ext` e o código da lista de aquisição.
2. Trazer para cá: `python ..\sincronizar.py --aplicar` (ver o README da pasta central).
3. Registrar na tabela: `python ..\acervo.py adicionar <caminho em referencias> --pasta 04` (código, título e ano saem do nome; `--tipo`, `--emissor`, `--doi`, `--url` completam). Item que estava na tabela sem caminho (citado, ainda não adquirido) vira esta linha.
4. `python ..\acervo.py catalogar`, `python ..\acervo.py converter` e `python ..\acervo.py verificar` (0 problema).
5. Outros códigos, cobertura parcial e atividades extras se corrigem na `matriz/fontes.csv` (colunas `outros_codigos`, `cobre_parte_de`, `atividades_extra`), nunca no `aliases.json`; depois regenerar (seção do Mapa, abaixo).

## Modelo: ficha de referência (`fichas/referencias/<CÓDIGO>.md`)

```markdown
---
codigo: TG-218
titulo: "Tolerance limits and methodologies for IMRT measurement-based QA"
ano: 2018
emissor: AAPM
tipo: recomendação            # obrigatório | recomendação | artigo | caso | POP | guia-fornecedor
vigencia: vigente             # vigente | substituído por X | histórico
atividades: [C06, A18]        # IDs de matriz/atividades.csv
refs: [TG-119, MPPG-5b-TPS, TG-219]
manuais: ["Portal Dosimetry 15.5 Reference Guide"]
repos: [pymedphys/pymedphys, cutright/IMRT-QA-Data-Miner]
isocentro: []                 # módulos do programa que implementam algo disto
texto: "../../texto/02 Plan check e revisão de prontuário/TG-218.md"
conferida: 2026-10-16
---

# TG-218: <título>

**Em uma frase.** …

## Quando usar na prática
## Exigências e recomendações (tabela: o quê | valor/limite | frequência | nível | [CÓDIGO p. N])
## Método resumido
## Pontos de atenção e armadilhas
## Como se aplica no CLINICA (equipamento, POP, ISOCENTRO)
## Relações (complementa, substitui, é citado por)
```

## Modelo: ficha de manual (`fichas/manuais/<produto>-<versão>-<tema>.md`)

Cabeçalho: `produto`, `versao`, `versao_instalada` (Eclipse 15.6 MR5, ESAPI 15.6.8.73, VitalBeam 3.0, GammaMedplus iX 1.2.5), `atividades`, `refs`, `repos`. Corpo: **índice por tarefa** (tarefa do físico → seção → página), limitações e avisos de segurança da versão, e o que mudou entre a versão do manual e a instalada.

## Modelo: ficha de repositório (`fichas/codigo/<dono>__<repo>.md`)

Cabeçalho: `repo`, `pasta`, `linguagem`, `licenca`, `ultimo_commit`, `atividades`, `refs`, `isocentro` (usa / poderia usar / não se aplica). Corpo: o que implementa; arquivos e funções-chave (caminho:linha); entradas e saídas; requisitos (ESAPI, versão do pydicom…); qualidade (testes, manutenção); como reaproveitar no ISOCENTRO e cuidados de licença.

## Programa de CQ proposto

`matriz/programa-cq.csv` (separador `|`) é a fonte única dos testes de acelerador e ortovoltagem, com tolerância, referência e etiqueta de aplicabilidade (`todas`, `eletrons`, `imagem`, `fff`, `edw`, `orto`). `scripts/gerar_programa_cq.py` aplica as máquinas de cada clínica e grava `servico/<CLÍNICA>/qualidade.json`. No `ppr-streamlit` (ramo `programa-cq-tg142`), importar esse arquivo substitui só as listas de testes.

Clínicas: **CEL** (TrueBeam 4045, Clinac 6EX 1254, GammaMed IX, Dermopan), **BET** (Clinac 600CD 1196), **DUO** = Anápolis (VitalBeam 4199).

## Estado e navegação (16/10/2026)

- **Comece por** `indices/por-atividade.md` (as 100 atividades, com ficha, fontes, código e situação) e `indices/o-que-falta.md` (profundidade por área e ordem da segunda passada).
- `indices/cobertura.md` e `matriz/vinculos.csv` são gerados por `scripts/gerar_matriz.py`; rodar de novo a cada ficha nova.
- `PENDENCIAS.md`: o que depende do serviço (equipamento, PPR, compras), sem bloquear a base.
- `texto/manuais/`: os 74 manuais em texto (`scripts/converter_manuais.py`).

## Mapa do Conhecimento (20/10/2026)

O Mapa é gerado, nunca editado à mão. A fonte de verdade são os arquivos de `matriz/` e as fichas; a página é a saída.

| Arquivo | O que guarda | Quem edita |
|---|---|---|
| `matriz/atividades.csv`, `matriz/vinculos.csv` | atividades e ligações | `scripts/gerar_matriz.py`, a partir das fichas |
| `matriz/requisitos.csv` | valor, tolerância e periodicidade de cada exigência, com fonte e ponto | à mão, ao ler um documento |
| `matriz/conflitos.json` | onde duas fontes divergem; `regra_adotada` fica `pendente` até o físico decidir | à mão |
| `matriz/vigencia.json` | situação de cada documento (vigente, atualizado, substituído…) | à mão |
| `matriz/aquisicao.json` | o que falta baixar, com links; itens que chegam ao acervo somem sozinhos | à mão |
| `matriz/etapas.json` | as 14 etapas da cadeia da radioterapia e suas atividades | à mão |
| `matriz/genealogia.csv` | quem substitui, atualiza, complementa ou conflita com quem | à mão |
| `matriz/incidentes.json` | acidentes do acervo, etapa da falha e atividades-barreira | à mão |
| `matriz/codigo.csv` | o que cada repositório implementa e se segue a norma vigente | à mão |
| `matriz/fontes.csv` | **o acervo de `referencias/`**: uma linha por documento (código, título, ano, tipo, emissor, vigência, DOI, URL, outros códigos, cobertura parcial, atividades extras, SHA-256, caminho). `emissor` é o órgão que publica; em artigo, o periódico. Vazio quando não há como afirmar. DOI tirado das duas primeiras páginas do texto integral (22/10/2026) | `..\acervo.py adicionar` e à mão (com `csv.writer`) |
| `matriz/aliases.json` | outros códigos do mesmo documento; documentos que cobrem só parte de um item de aquisição | **gerado** da `fontes.csv` por `..\acervo.py catalogar`; não editar |

Para atualizar depois de mudar fichas, `matriz/` ou o acervo:

```
python scripts\gerar_matriz.py ..
python ..\acervo.py catalogar
python scripts\gerar_mapa.py ..
```

Saem `mapa/mapa-conhecimento.html` (página única, para abrir no navegador) e `mapa/publicar/` (`index.html` pequeno + `dados.js`), ambos fora do git. O artefato do Mapa é `https://claude.ai/artifact/C7wJ4LV2Ls4BTD9RH1RSnj` (desde 22/10/2026; o antigo foi apagado). Para atualizar: copiar `mapa/publicar/` para o scratchpad, ler o artefato (a página tem ~65 KB, não os 630 KB de antes) e publicar com `url` e `files: {"dados.js": ...}`; se o `modelo.html` mudou, publicar o `index.html` junto. Nunca remendar o HTML publicado. O que é calculado no gerador, e não deve ser escrito à mão: o que está no acervo, a fila de leitura, os itens já adquiridos, os seis elos da cadeia de sustentação de cada atividade, e a periodicidade e a técnica de cada requisito.
