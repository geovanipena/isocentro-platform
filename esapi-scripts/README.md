# clinica-esapi

Biblioteca de scripts **ESAPI (C#)** para **Varian Eclipse 15.6+** — verificação de planos e QA em
radioterapia, ambiente Citrix. Físico responsável: **Geovani Pena** (Clinica / Rede).

O contrato de comportamento do projeto (invariantes, arquitetura, armadilhas, estado dos scripts) está em
**[`CLAUDE.md`](./CLAUDE.md)** — o Claude Code lê esse arquivo automaticamente ao abrir o repositório.

## Estrutura

```
.
├── CLAUDE.md              # manual operacional (lido pelo Claude Code)
├── scripts/               # uma pasta por script, cada uma com README.md (e NOTAS.md quando há rodadas)
│   ├── _template/         # Template_Clinica.cs — ponto de partida
│   ├── constraints/ … plano-pre-tratamento/     # single-file (somente leitura)
│   └── estruturas-*/ 5-campos-fif/ proprietario-tarefas/ preplan/ aneis-otimizacao/   # DLL (.csproj)
├── lib/                   # DLLs da Varian para compilar (fora do git)
├── vendor/esapi-docs/     # XML de documentação das DLLs Varian (referência de API)
└── tools/                 # verificações (check_all.ps1) e o hook do Claude Code
```

## Setup do repositório

```bash
git init
git add .
git commit -m "Bootstrap: biblioteca ESAPI Clinica + CLAUDE.md + skills + tools"
# repositório privado no GitHub (recomendado — código clínico):
git remote add origin git@github.com:<usuario>/clinica-esapi.git
git push -u origin main
```

## Claude Code

1. Instalar (requer Node.js 18+):
   ```bash
   npm install -g @anthropic-ai/claude-code
   ```
2. Na raiz do repo:
   ```bash
   claude
   ```
   O `CLAUDE.md` e as skills em `.claude/skills/` entram em contexto automaticamente.

> As skills e o `CLAUDE.md` são lidos do repositório. Se a versão do Claude Code em uso não descobrir as
> skills automaticamente, o conteúdo essencial delas continua referenciado no `CLAUDE.md`.

## Verificação (rodar antes de commitar mudanças na região compartilhada)

```bash
python3 tools/check_region_parity.py   # paridade byte-a-byte da #region PADRÃO CLINICA
bash    tools/check_encoding.sh        # BOM, fim-de-linha, balanceamento de chaves
```

## Convenção crítica de fim-de-linha

Os `.cs` são **LF, sem BOM**. O `.gitattributes` **força LF** em checkout/commit em qualquer SO, para o git
nunca converter CRLF↔LF — o que alteraria o hash de referência da `#region PADRÃO CLINICA`. Não desabilite
isso. Ao editar num editor Windows, garanta que ele **não** reconverta para CRLF ao salvar.

## Scripts

A tabela com todos está no [`CLAUDE.md`](./CLAUDE.md) (§11); o detalhe de cada um, no `README.md` da pasta.
