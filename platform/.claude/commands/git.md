---
description: Commita o que está na árvore, dividido por frente, e empurra
allowed-tools: Bash, Read, Write, Edit
---

Fecha o ciclo: o que está conferido vira commit e vai para o `origin`.
Combinado em 04/09/2026 — **commit e push sempre, sem perguntar**. O objetivo é
o repositório estar sempre em dia: esta conexão cai, e trabalho conferido
parado na árvore é trabalho que pode se perder.

## 0. A suíte já passou?

Se a suíte **não** rodou depois da última alteração, rode o `/pronto` primeiro.
Commitar é barato; commitar quebrado custa a bissecção de outra pessoa.

Exceção: mudança que não toca em código (`NOTAS.md`, `CLAUDE.md`, `.gitignore`)
dispensa a suíte. Diga que dispensou e por quê.

## 1. Olhe o que há

```
git status --short
git diff --stat
```

**Antes de `git add`, procure o que não pode entrar**: qualquer arquivo com
nome ou registro de paciente. Já aconteceu — `cru.txt` e `predecessor.txt`
estavam soltos e fora de todo padrão do `.gitignore` em 03/09/2026. Se achar
algum, ignore-o (com o motivo escrito ao lado, como os outros) em vez de só
não adicioná-lo: da próxima vez ninguém vai olhar.

Isso era só o NOME do arquivo. O CONTEÚDO é a varredura, depois do `git add` e
**antes do commit**:

```
python tools/varrer_identidade.py
```

Saída 1 = **pare**. Abra o `arquivo:linha` de cada achado e troque o dado real
pelo pseudônimo (`900NNNN`, e o nome do `.identidades.json`) antes de seguir.
Não commitar "para consertar depois": o que entra no histórico não sai sem
reescrevê-lo, e reescrever histórico já custou uma sessão inteira em 31/08/2026
— e nem assim desfaz o que esteve público.

A ferramenta imprime o achado mascarado de propósito. Ao relatar, **não escreva
o registro nem o nome por extenso** — cite o `arquivo:linha`.

## 2. Divida por FRENTE, não por arquivo

Um commit por assunto, para uma frente poder voltar atrás sem levar as outras.
Se um arquivo encosta em duas frentes (o `gui.py` e o `NOTAS.md` quase sempre
encostam), **fatie-o por bloco** — não jogue tudo num commit só.

A receita que funcionou em 03 e 04/09/2026, e que vale repetir:

1. leia o conteúdo do arquivo no `HEAD` (`git show HEAD:arquivo`);
2. monte, para cada frente, o conteúdo daquela etapa aplicando as trocas
   `(velho, novo)` em ordem, com **`assert` em cada uma**;
3. **ensaie**: aplicando TODAS as frentes, o resultado tem de ser idêntico,
   linha por linha, ao arquivo da árvore. Se bater, a divisão não perdeu nem
   inventou uma linha;
4. só então grave cada etapa no índice — `git hash-object -w --stdin` mais
   `git update-index --add --cacheinfo`, que põem o conteúdo no índice **sem
   tocar na árvore de trabalho**.

## 3. A mensagem

Português, no espírito dos comentários deste projeto: o título diz **o que
mudou**, o corpo diz **por quê** e **o que quebrava antes**. Nada de lista de
arquivos — isso o `git show` já dá.

Termine toda mensagem com:

```
Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
```

## 4. Empurre

```
git fetch origin <branch>
git log --oneline <branch>..origin/<branch>
```

Vazio = avanço limpo, pode empurrar. **Se não estiver vazio, pare e diga**: o
remoto tem coisa que não está aqui, e resolver isso é decisão, não rotina.

```
git push origin <branch>
```

## 5. Relate

Tabela com o SHA curto e o título de cada commit, e a linha do push
(`95e0a34..45b1d20`). Se dividiu um arquivo por bloco, diga que o ensaio bateu
— é o que dá confiança na divisão.
