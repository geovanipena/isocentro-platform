# docs/qms — a base de segurança clínica

Esta pasta é o que os agentes do BMad carregam como fato em todo planejamento
(os overrides em `_bmad/custom/` apontam para `docs/qms/*.md`). É a camada
clínica que o BMad genérico não traz.

| Arquivo | Quem escreve | Para quê |
| --- | --- | --- |
| `escopo.md` | o físico | o que o sistema faz e não faz, e de onde vem cada dado |
| `classificacao-62304.md` | o físico | classe de segurança por módulo (IEC 62304) |
| `riscos.md` | o físico | modos de falha e controles (ISO 14971, AAPM TG-100) |
| `revisao-clinica.md` | versionado com o projeto | prompt do revisor adversário que roda no fim de cada PRD e arquitetura |

Os três primeiros nasceram **vazios de propósito**: a regra do projeto é não
inventar dado, e um agente que lê uma classe de segurança ou um risco escrito
pela IA o trata como decisão do físico. Enquanto estiverem vazios, os agentes
perguntam em vez de presumir — e o revisor aponta a lacuna.

O `revisao-clinica.md` é a única peça escrita aqui sem o físico, porque não
afirma nada sobre o serviço: ele transforma as regras do domínio do
`CLAUDE.md` em perguntas. Quando uma regra nova entrar no `CLAUDE.md`, ela
entra também ali.
