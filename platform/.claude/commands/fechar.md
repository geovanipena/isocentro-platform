---
description: Fecha a frente: suíte, checkpoint, commit, push — e diz se é hora do /clear
allowed-tools: Bash, Read, Edit, Write
argument-hint: [assunto da frente]
---

O ritual de **fim de frente**, na ordem. Existe porque "um commit por frente"
só se cumpre se fechar for um gesto único — e trabalho conferido parado na
árvore é trabalho que a queda de conexão leva.

Frente: **$ARGUMENTS**

1. **`/pronto`** — suíte completa e ordem aleatória, com o número de testes e a
   semente no relatório. Se falhar, para aqui: não se fecha frente vermelha.
   Tela ou integração: conferida no **caminho do usuário** (o app como ele
   abre), não só no meu ambiente.
2. **Spec em dia.** Decisão desta frente que contradiz spec, `DESTINO.md` ou
   decisão anterior dele: atualizar o documento NESTE commit (em 28/10/2026 a
   edição do PPR na aba da Documentação ficou contra a CAP-10 por um dia).
3. **`/checkpoint`** — a seção no topo do `NOTAS.md`. Depois,
   `python tools/notas.py descer`: desce sozinho o que passou de 14 dias ou
   não cabe em 400 linhas (move, não resume; índice e "O que está aberto"
   atualizados). Se a frente fechou uma pendência, voltar na seção que a abriu.
4. **`/git`** — commit dividido por frente, mensagem em português dizendo o
   PORQUÊ, e push. Sem perguntar (combinado em 04/09/2026). Dentro dele, o
   `tools/varrer_identidade.py` **aborta** se dado real de paciente estiver
   entrando: saída 1 não se contorna, conserta-se.
5. **Avisar em voz alta** o que ficou para o usuário: `.bat` que só roda na
   clínica, decisão de tela, pergunta para a TI. E dizer, em uma linha, **se é
   hora do `/clear`**: sim se o usuário vai parar mais de uma hora (o cache
   expira e a volta regrava o contexto inteiro), se a próxima frente é de outro
   assunto, ou se o contexto passou de ~150 mil. Não, se a próxima é pequena e
   vizinha: sessão nova grava ~51 mil tokens de partida a 2× (medido em
   15/09/2026), e o contexto que já está em cache se relê a 0,1×.
