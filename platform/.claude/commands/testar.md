---
description: Roda só os testes da frente aberta (recorte por import), não a suíte
allowed-tools: Bash, Read
argument-hint: [módulo ou arquivo]
---

O teste de DURANTE o trabalho. A suíte completa é do fechamento — ela é o
`/pronto`, custa 2,5 minutos e existe para responder "está pronto?".

```
python tools/testar.py $ARGUMENTS
```

Sem argumento ele pergunta ao git o que mudou e roda os arquivos de teste que
**importam** o módulo mexido. Medido em 08/09/2026: 315 testes em 43 s contra
1742 em 152 s.

## O que relatar

Quantos arquivos, quantos testes, o resultado — e **que isto foi um recorte**.
Recorte verde não é suíte verde: o vizinho que não rodou é exatamente quem
costuma quebrar. Nunca dizer "está pronto" com base nisto; para isso, `/pronto`.

## Se ele acusar algo que a suíte não acusa

**É sinal, não ruído.** Teste que passa na suíte e falha no recorte depende de
outro arquivo ter rodado antes — a família que o `ordem_aleatoria.py` caça, e que
o `discover` alfabético esconde. Foi assim que apareceu o
`test_capa_espelho`, que só passava porque outro arquivo redirecionava a pasta de
configuração antes dele. Investigar antes de culpar a ferramenta.
