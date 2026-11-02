---
description: Grava o PNG de uma tela do programa, para conferir mudança visual
---

Conferir mudança de tela é `python tools/tela.py`, nunca `grab()` à mão: as duas
armadilhas daqui se disfarçam de bug de layout (o `offscreen` não desenha texto;
a `JanelaPrincipal` cai com exit 127 e sem traceback se o `setStyleSheet` não
vier antes) e a ferramenta faz a sequência na ordem certa.

Alvo pedido: **$ARGUMENTS** (vazio = `principal`).

1. `python tools/tela.py --lista` se o alvo não estiver claro; para os filhos de
   uma janela, `python tools/tela.py principal --lista`.
2. Capturar: `python tools/tela.py <alvo> -o <arquivo>.png`.
   - `--caso TC8` para encher a bancada — **tela vazia esconde metade das
     regressões de layout** (coluna que não cabe, rótulo que elide, linha que
     estoura a altura: nada disso aparece sem dado dentro).
   - `--modo dia` **e** `--modo noite` quando a mudança for de cor: metade das
     regressões só aparece num dos dois, e `estilo.py` é a única fonte de cor.
3. **Olhar o PNG.** É o ponto todo — teste que passa não prova que a tela está
   certa. Para antes/depois, gravar os dois e comparar olhando; a régua do
   `comparar_pdf.py` é do papel, aqui não há equivalente.
4. Conferir o que o `CLAUDE.md` cobra da interface: um **sólido** por tela e ele
   anda com o trabalho; botão aceso significa pronto; **verde é dose**, nenhum
   elemento de interface o usa como cor de ação; nada de espaço vazio reservado
   "por via das dúvidas".

O PNG é rascunho de conferência: **não commitar**.
