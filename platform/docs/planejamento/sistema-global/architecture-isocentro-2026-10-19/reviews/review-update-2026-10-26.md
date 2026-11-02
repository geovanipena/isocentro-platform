# Revisão do Update de 26/10/2026 (AD-35)

Escopo: AD-35 (Prevents e Rule), Deferred (G1, segregação), Varredura (classe) e a tabela 3.2 da `renderings/descricao-arquitetura-62304.md`. Lint: 0 achados.

## Clínica (`docs/qms/revisao-clinica.md`)

| Trecho | Regra | Gravidade | Pergunta ao físico |
| --- | --- | --- | --- |
| "Item sem linha … inclusive `rt` — vale rigor C" | 9 | importante | Qual é a classe do `rt`? Precisa ser decidida antes da R-58. |
| "núcleo A servindo ao TRS-398 C sem segregação justificada" | 9 | importante | O que isola o cálculo TRS-398 do núcleo no mesmo processo (§5.3.5)? Precisa ser respondido antes do épico do TRS-398. |

Bloqueantes: 0. As duas perguntas estão no Deferred. A espinha não decide classe: aplica o rigor C até a decisão.

## Adversário

| Achado | Correção |
| --- | --- |
| Item sem linha: um módulo poderia declarar `C` no `MANIFESTO` e outro deixar a classe vazia, e o teste do AD-22 não teria contra o que comparar | AD-35: o `MANIFESTO` declara C, e o teste aceita C onde a linha não existe e reprova qualquer outra. |

## Versões

Nenhuma tecnologia nova; nada a conferir.
