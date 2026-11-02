---
description: Carrega um caso real de TCs_Teste e gera a ficha, para conferir mudança no papel
allowed-tools: Bash, Read
argument-hint: <TC8 | Elekta | ...> [--modo soma]
---

A régua do `CLAUDE.md` para mudança no PDF: **gerar e medir**. Teste que passa
não prova que o papel está certo — a suíte confirma que a função devolve o que
o teste espera, e nenhuma confere se a dose impressa na célula é a dose do
plano.

```
python tools/caso.py $ARGUMENTS
```

Sem argumento nenhum, ele lista os casos disponíveis — 18 nesta
estação, dos quais `Posicionamento` guarda notas e não gera ficha.

O fluxo é o do **programa**, não uma reimplementação: monta a `JanelaPrincipal`
de verdade (invisível), roda o mesmo `_CarregarTudo` do botão "Abrir pasta" e
chama o mesmo `_montar_planos_pdf`. Uma ficha gerada aqui sai pelo caminho por
onde sai a da sala.

## Como conferir o que saiu

O PDF é gravado e o caminho aparece no fim. Para medir sem abrir:

```
python -c "from pypdf import PdfReader; r=PdfReader('X.pdf'); print(len(r.pages)); print(r.pages[3].extract_text())"
```

Para **comparar antes e depois** de uma mudança, gere os dois com nomes
próprios (`-o antes.pdf`, `-o depois.pdf`) e compare página a página. É isso
que transforma "acho que não mudou nada" em evidência.

## O que ele NÃO faz, de propósito

Agendamento, separação de ficha e capa — são decisões que alguém toma na tela,
e inventá-las aqui daria uma ficha que não corresponde a escolha nenhuma. Com
dois ou mais planos, a folha em branco entre os planos **é intencional**: no
impresso frente-e-verso cada plano ocupa uma folha e a Ficha Técnica cai no
verso da última.

## A regra que não muda

Conferir contra o **SISTEMA**, nunca contra uma ficha arquivada — a do TC8 está
errada no acervo, e validar contra ela "confirmaria" um erro que já existia.
