---
description: Esqueleto de um arquivo grande (classes, métodos, intervalos) sem lê-lo inteiro
allowed-tools: Bash
argument-hint: <arquivo.py> [texto a buscar]
---

Antes de abrir um arquivo grande deste projeto, **mapeie**. `gui.py` tem 9 mil
linhas e `ficha_pdf.py` 3,5 mil: lê-los inteiros para achar um método é o maior
desperdício de contexto que existe aqui.

Rode:

```
python tools/mapa.py $ARGUMENTS --metodos
```

O resultado dá o nome de cada classe/método e **o intervalo de linhas**. Com
isso, a leitura seguinte é `sed -n '4067,4179p' gui.py` — 113 linhas em vez de
9 mil.

Se o segundo argumento for um assunto (`capa`, `tratamento`, `agendamento`),
ele já vem como `--buscar` e a lista sai filtrada.

Depois de mapear, **leia só o intervalo que interessa** e diga ao usuário o que
encontrou, citando `arquivo.py:linha`.
