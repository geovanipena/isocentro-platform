---
description: Grava o estado atual em NOTAS.md, para a queda de conexão custar minutos
allowed-tools: Bash, Read, Edit, Write
argument-hint: [assunto da etapa]
---

Grave o checkpoint da etapa em `NOTAS.md`. A conexão deste projeto cai
(`API Error: Connection refused` é rotina): sem isso a queda custa a sessão
inteira, com isso custa minutos.

Assunto (se o usuário deu um): **$ARGUMENTS**

## O que escrever

Uma seção nova **no topo** do arquivo, logo após o cabeçalho, com a data de
hoje. Quatro coisas, nesta ordem:

1. **O que está feito** — arquivos tocados e o que cada mudança faz. Cite
   `arquivo.py:linha` onde ajudar a retomar.
2. **O que falta** — o próximo passo concreto, não "continuar".
3. **As decisões já tomadas e por quê** — para não se re-litigar a mesma
   escolha na sessão seguinte.
4. **As armadilhas pagas nesta etapa** — o que quebrou quando era de outro
   jeito. Esta parte é a que evita repetir o erro daqui a duas semanas, e é a
   razão de o arquivo existir.

## Como escrever

No mesmo estilo do resto do `NOTAS.md` e dos comentários do projeto: o texto
diz **por quê**, não repete o que o `git diff` já mostra. Português do Brasil.
Datas absolutas, nunca "ontem" ou "semana passada".

Antes de escrever, rode `git status --short` e `git diff --stat` para o
checkpoint refletir o estado real, não a memória da conversa.

Se já existe uma seção desta mesma etapa, **atualize-a** em vez de empilhar uma
segunda.

## O arquivo é curto de propósito

Desde 08/09/2026 são três: `NOTAS.md` (o que está vivo + o índice do resto),
`notas/AAAA-MM.md` (a história congelada, byte a byte) e `ARMADILHAS.md`
(permanente). O arquivo vivo tem de caber numa leitura — meta de umas 400
linhas. Se ele passou disso, **desça** as seções que já não são "o que está em
andamento" para o `notas/AAAA-MM.md` do mês em que foram escritas — mover, não
resumir — e ponha a linha delas no índice.

Antes era um arquivo só, e ele chegou a 7.873 linhas: ninguém o lia inteiro, e
nota que não se lê é nota que envelhece sem ser questionada. Foi assim que
nasceram os quatro registros vencidos de 08/09/2026.
