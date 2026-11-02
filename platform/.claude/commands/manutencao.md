---
description: Confere o ambiente de trabalho (armazenamento, .claude, notas, extensões, skills) — relata, não apaga
allowed-tools: Bash, Read, Edit
---

Roda a manutenção do **ambiente** — a bancada em volta do código, que é a parte
sem ritual. A suíte confere o programa; o `/fechar` confere a frente; ninguém
conferia os 200 MB de `build/`, o gancho que saiu do `settings.json` e ficou em
disco, ou a seção do `NOTAS.md` que devia ter descido há três semanas.

## 1. Rodar

```
PYTHONIOENCODING=utf-8 python tools/manutencao.py
```

Leva uns 15 s (roda cada gancho para ver se ainda sobe). Com `--rede` inclui
`pip list --outdated`, que depende da internet e pode levar 1–2 minutos —
usar só quando a pergunta for sobre dependência.

Para um eixo só: `--eixo armazenamento|claude|notas|externo|skills`, repetível.

## 2. Ler o que ela achou

O relatório separa **`!` para decidir agora** de **`·` para saber**. A
distinção importa:

- **`!`** é coisa que já está quebrada em silêncio — gancho que estoura, comando
  apontando para arquivo que não existe, extensão recomendada ausente,
  pendência declarada aberta há três semanas. Tratar nesta sessão ou registrar
  no `NOTAS.md` por quê não.
- **`·`** é acúmulo. Não exige ação hoje; exige não ser ignorado por três meses.

## 3. A regra que não se quebra

**A ferramenta nunca apaga, e eu também não.** Ela imprime o comando de limpeza
pronto; quem executa é o usuário. O `TCs_Teste/`, os zips de release e os
transcripts das sessões antigas moram no mesmo terreno do lixo regenerável, e um
`rm` esperto acerta o que não devia. Se um achado pedir remoção, **mostrar o
comando e perguntar** — não rodar.

A única exceção é o `--limpar-ctx`, que só toca em `.claude/estado/ctx_*.txt` de
sessão morta, e mesmo esse só sob a flag.

## 4. Fechar o laço

Achado que virou trabalho vira **frente**, não conserto de passagem no meio de
outra coisa — a regra de uma frente por sessão vale aqui igual. Achado que foi
resolvido agora merece a linha no `NOTAS.md`: a manutenção mede o estado, não
guarda a história de por que ele mudou.

E se um achado for **falso positivo**, o defeito é da ferramenta: corrigir o
`tools/manutencao.py`. Relatório que grita à toa é relatório que se aprende a
pular, e aí ele parou de servir para o que foi feito.
