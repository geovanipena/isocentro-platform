# Planejamento com o BMad

O BMad entra neste repositório **só no planejamento**: pesquisa, brief, PRD,
arquitetura e spec. A execução continua como estava — a fila do `DESTINO.md`,
as sessões `voce` com `/abrir` e `/fechar`, e o `tools/robo.py` nas frentes
`robo`. Decidido em 13/10/2026, junto com a decisão de que o ISOCENTRO é
o núcleo do sistema global e o PPR e os scripts ESAPI entram nele aos poucos.

## Por que só o planejamento

O projeto já tinha o que o BMad traria para a execução, e mais rígido:

| O BMad traria | Aqui já existe |
| --- | --- |
| `AGENTS.md` (`bmad-project-context`) | `CLAUDE.md` + `ARMADILHAS.md` |
| `tickets.toml` (`bmad-ticket`) | a fila do `DESTINO.md`, que o robô lê |
| `bmad-build-auto` | `tools/robo.py`, com trava em `papel/`, `interface/` e `dominio/` |
| `.memlog.md` | `NOTAS.md` + `notas/AAAA-MM.md` |
| `bmad-retrospective` | a seção da frente no `NOTAS.md` e o `DESTINO.md` |

Instalar os dois em paralelo daria dois processos e nenhum vencendo — o que a
própria documentação do BMad aponta como o erro a evitar em código existente.
O que faltava era o que vem **antes** da fila: decidir o que construir, com
pesquisa citada, requisito ligado a risco e decisão de arquitetura escrita.

## O que usar, e em que ordem

| Ordem | Skill | Para quê | Sai em |
| --- | --- | --- | --- |
| 1 | `bmad-deep-recon` | pesquisa com citação (ANVISA, LGPD, TG-275, bibliotecas) | `docs/planejamento/<iniciativa>/research-*` |
| 2 | `bmad-brainstorming` / `bmad-forge-idea` | testar ideia antes de virar requisito | idem |
| 3 | `bmad-product-brief` | a visão do sistema global | idem |
| 4 | `bmad-prd` | requisitos, citando o que o app já faz | idem |
| 5 | `bmad-architecture` | decisões que os módulos precisam respeitar | idem |
| 6 | `bmad-spec` | uma spec por bloco de trabalho | idem, e depois a fila |

**Não usar aqui:** `bmad-project-context` (o `CLAUDE.md` é o contexto; a
documentação do BMad manda pular quando o repositório já tem um mantido em
dia), `bmad-ticket`, `bmad-build`, `bmad-build-auto` e `bmad-retrospective`.
Os agentes PM e arquiteto tiveram o item `TK` do menu trocado pela ponte
abaixo.

A pasta de saída é `docs/planejamento/` para todas as estações
(`_bmad/custom/config.toml`). Sugestão de iniciativa: `sistema-global` — peça
ao skill `bmad` para ativá-la; ele grava em `_bmad/custom/config.user.toml`,
que é pessoal e fica fora do git.

## Da spec à fila

Quando uma spec fica pronta, o `bmad-spec` (pelo `on_complete`) e o item `TK`
dos agentes **propõem** frentes; o usuário aceita antes de qualquer gravação.

Cada frente segue o formato fixo do `DESTINO.md`:

```
### R-NN — título
- classe: robo | voce | clinica
- estado: pendente
- pilar: 1 a 4, ou "sistema global"
- pronto quando: o critério medível, com o comando ou o caso que prova
- fora: o que a frente não toca
```

Regras da classe, as mesmas do `DESTINO.md`:

- `robo` só quando a frente não toca `papel/`, `interface/` nem `dominio/` e
  não depende de nada fora desta máquina.
- `voce` quando muda o papel (aviso antes), a tela (aceite antes) ou o
  cálculo (chega ao paciente).
- `clinica` quando só se responde na clínica ou na TI: rede, banco, ARIA,
  dado de máquina.
- Na dúvida entre `robo` e `voce`, é `voce`.

O número `R-NN` continua a sequência do `DESTINO.md`. Cada frente cita o
requisito do PRD e, quando houver, o item de `docs/qms/riscos.md`: é assim que
o requisito chega ao teste sem planilha paralela.

## Instalação por estação

As skills do BMad ficam em `.claude/`, que é da estação e está fora do git;
`_bmad/` também, exceto `_bmad/custom/`. Em cada estação nova:

1. No Claude Code: `/plugin marketplace add bmad-code-org/bmad-plugins` e
   instalar `bmad-method` e `bmad-core-tools` (ou `npx skills add
   bmad-code-org/BMAD-METHOD`). Precisa do `uv`.
2. Pedir ao skill `bmad` que rode `bmad setup`. As respostas do instalador
   ficam em `_bmad/config.toml`; a pasta de saída de equipe já vem do
   `_bmad/custom/config.toml` versionado.
3. Conferir o que os agentes recebem:
   `uv run _bmad/scripts/resolve_customization.py --skill <pasta do skill> --project-root . --key agent`.

Os overrides de `_bmad/custom/` foram escritos contra o esquema da versão
6.13.0-next. Override só traz os campos que mudam; nunca copiar o
`customize.toml` inteiro, senão a próxima atualização fica sombreada.
