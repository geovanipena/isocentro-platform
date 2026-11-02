---
description: Roda a suíte completa e a ordem aleatória (com vigia), e relata o número de testes
allowed-tools: Bash, Read, Edit
---

O ritual de fechamento deste projeto, que o CLAUDE.md manda cumprir **antes de
dizer que está pronto**. Não pule etapa e não relate por estimativa.

Isto é o **fechamento**, não o teste de cada edição: entre uma mudança e a
seguinte, `/testar` roda só os arquivos que importam o módulo mexido.

## 1. As duas ordens, pelo `tools/suite.py`, em background

```
.venv/Scripts/python.exe tools/suite.py && .venv/Scripts/python.exe tools/suite.py --aleatoria
```

Com `run_in_background: true`. A ferramenta grava a saída inteira em
`relatorios_ferramentas/suite/` e imprime só o veredito. Tem **vigia**: teste
que passa de 180 s vira `TRAVOU em <teste> (… linha)` e o processo sai — em
28–29/10/2026, sem vigia, a suíte ficou 1h40 parada e o usuário teve de
perguntar "1 hora?". Cada ordem leva uns **7,5 min** com os testes de banco.

**Não esperar calado.** Se passar de ~1,5× o tempo previsto sem notificação,
olhar o relatório por conta própria (ele cresce enquanto roda) — nunca
"aguarde" sem prazo.

Falhou ou travou: abrir só o trecho da falha no relatório. Teste de banco
falhando com "o PostgreSQL de teste não responde" é o servidor fora — a
abertura da sessão o sobe; senão, `docs/AMBIENTE.md`, "Não sobe sozinho".

## 2. Relatar

Sempre, e nesta forma:

- **quantos testes rodaram** (o `Ran N tests`), nas duas ordens;
- **o resultado** (`OK`, o que falhou ou onde travou);
- **a semente** da ordem aleatória;
- **o que ficou de fora e por quê**.

"Deve funcionar" não é relatório.

## 3. O que a suíte NÃO prova

- **No caminho do usuário.** Tela ou integração: o app como ELE abre (pelo VS
  Code, com as variáveis que o VS Code dele enxerga). O que depender dele
  fazer vai dito ANTES de "pronto".
- **Visual**: renderizar (`tools/tela.py`) e olhar. **PDF**: gerar e medir. A
  suíte confirma que o código roda; nenhum teste confere se a dose impressa
  na célula é a dose do plano — e é isso que vai grampeado na ficha.
