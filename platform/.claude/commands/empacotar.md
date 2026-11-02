---
description: Gera o executável pelo tools/gerar_executavel.py, nunca à mão
allowed-tools: Bash, Read
---

Empacotar é **`python tools/gerar_executavel.py`**, nunca `PyInstaller` na mão.

```
PYTHONIOENCODING=utf-8 python tools/gerar_executavel.py
```

O script existe porque cada uma destas já aconteceu de verdade, e ele confere
as três:

- **o `--clean` apagando as instruções de instalação** — o pacote sai sem o que
  o usuário precisa ler para instalar;
- **dado de execução viajando no zip** — o `migrar.ps1` nunca sobrescreve, então
  um arquivo de dado dentro do pacote faz a migração **PULAR o arquivo real do
  serviço**, e a clínica volta a um estado antigo sem ninguém notar;
- **import tardio que ficou de fora do pacote** — este falha **silenciosamente
  na clínica**, não aqui.

Rodar antes: `/pronto`. Empacotar código que não passou na suíte é empacotar o
erro.

Depois de gerar, relate o **nome e o tamanho** do arquivo produzido. E lembre
ao usuário que **binário (`.exe`, `.rar`, `.zip`) não entra no repositório** —
publicar como asset de Release.
