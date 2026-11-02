---
description: Abre a sessão: declara a frente única, lê o checkpoint e o que NÃO se toca
allowed-tools: Bash, Read, Skill
argument-hint: [a frente desta sessão]
---

O simétrico do `/fechar`. O fechamento já era ritual; a **abertura** era
improvisada — e abertura improvisada é onde se lê arquivo demais: abre-se o
`gui.py` "para entender o contexto" no primeiro turno, e o preço é ~60 mil
tokens multiplicados por todos os turnos da sessão.

Frente pedida: **$ARGUMENTS**

O gancho `abertura.py` já injetou branch, árvore, últimos commits e a seção viva
do `NOTAS.md`. **Não releia esses.** Isto aqui é o que fazer com eles.

1. **Declarar a frente em UMA linha**, e dizer o que ela NÃO inclui. "Uma frente
   por sessão" só se cumpre se a frente tiver borda escrita; sem borda, toda
   descoberta lateral vira trabalho, e a sessão fecha sem fechar nada.
   Se `$ARGUMENTS` estiver vazio, propor a frente a partir do checkpoint vivo e
   **perguntar** antes de começar.

2. **Listar os arquivos que a frente provavelmente toca** — pelo nome, sem abrir.
   Para cada um com mais de mil linhas, o comando de recorte já pronto:
   `python tools/mapa.py <arquivo> --buscar <termo>`. O gancho `ler_grande.py`
   recusa a leitura inteira, mas chegar nele já é ter perdido um turno.

3. **Carregar só o que a frente exige.** Banco, ARIA ou DICOM: `/clinica`.
   Papel: `tools/caso.py`. Tela: `ui.py` e `estilo.py`. Nada "por via das
   dúvidas" — o que entra no contexto fica reenviado até o `/clear`.

4. **Se o checkpoint vivo estiver aberto há tempo, conferir antes de agir.** A
   marca é do dia em que foi escrita: das quatro notas vencidas de 08/09/2026,
   duas diziam aberto o que já tinha fechado. Um "EM ABERTO" resolvido é pior
   que nota nenhuma — ninguém questiona o que está escrito.

5. **Dizer, em uma linha, o primeiro passo concreto.** Não "analisar o código".
