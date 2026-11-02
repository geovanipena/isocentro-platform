# CLAUDE.md — base de conhecimento do ISOCENTRO

As regras desta pasta estão no [README.md](README.md). Leia o README antes de mexer em qualquer coisa, e uma ficha de `fichas/atividades/` como modelo antes de escrever ficha nova.

O que mais deu erro até aqui (o detalhe está no README):

- Número de tabela confere-se na imagem da página, não só no texto extraído.
- A matriz e o Mapa são gerados: editar as fichas e `matriz/`, rodar os geradores, nunca remendar o HTML.
- O acervo é a `matriz/fontes.csv`; o `aliases.json` é gerado dela (`python ..\acervo.py catalogar`).
- CSV com `csv.writer`; documento novo sem subpasta; commitar só os próprios arquivos.
- Nada de paciente nem de pessoa entra aqui.

O que depende do serviço vai para `PENDENCIAS.md`. As regras da pasta central (Drive, `_restrito`) estão em `../CLAUDE.md`.
