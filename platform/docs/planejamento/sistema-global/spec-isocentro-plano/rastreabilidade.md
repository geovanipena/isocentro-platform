# Rastreabilidade — Módulo Plano

Liga cada capacidade ao requisito (PRD), à regra (espinha), ao modo de falha a avaliar (PRD §12.2) e à forma de verificação. A coluna **riscos.md** fica vazia até o físico escrever as linhas: este arquivo não inventa risco.

| CAP | FR / decisão | AD | Modo de falha a avaliar | riscos.md | Verificação |
| --- | --- | --- | --- | --- | --- |
| CAP-1 | FR-10 | AD-26 | tabela da máquina errada aplicada ao plano (nome DICOM trocado) | — | validação contra pontos do relatório; teste com nome trocado |
| CAP-2 | FR-11 | AD-28, AD-30 | checagem não roda e ninguém percebe | — | teste: sem RT Plan / UID divergente → `indeterminado` + alerta |
| CAP-3 | FR-12, P4 | AD-14 | checagem dá `conforme` para plano errado | — | erro semeado; casos conferidos à mão |
| CAP-4 | P3, FR-12 | AD-14 | falso negativo no modulado | — | comissionamento TG-119; erro semeado |
| CAP-5 | FR-13 | AD-14 | técnica não tratada saindo `conforme` | — | teste com filtro e máquina sem tabela |
| CAP-6 | FR-14 | AD-35 | veredito de cálculo não comissionado | — | relatório de comissionamento aprovado |
| CAP-7 | FR-15 | AD-28 | contagem de frações errada adia o alerta | — | teste com app fechado; casos da R-07 |
| CAP-8 | U1 | AD-14, AD-31 | "fora da faixa" lido como reprovação; tolerância sem origem | — | teste de esquema (origem); caso conferido à mão |
| CAP-9 | FR-16 | AD-16, AD-17 | data lida do campo errado do `variandw` | — | casos conferidos contra o ARIA |
| CAP-10 | FR-18 | — | alto risco não marcado recebe prazo comum | — | teste: "não informado" → prazo antes da 1ª fração |
| CAP-11 | FR-17 | AD-29 | Duplo Check atrasado sem alerta | — | teste de prazo; SM-2 |
| CAP-12 | FR-42 | — | item automático dá `conforme` falso | — | erro semeado |
| CAP-13 | FR-19 | AD-14 | item automático dá `conforme` falso | — | erro semeado; item sem referência nasce vazio |
| CAP-14 | FR-21 | AD-16 | divergência prescrição × plano não detectada | — | erro semeado com dose trocada |
| CAP-15 | FR-20 | AD-13, AD-30 | Duplo Check pelo mesmo físico; assinatura vale para versão diferente | — | teste com mesmo físico e com versão alterada |
| CAP-16 | FR-9, NFR-3 | AD-18 | tela congelada; degrau não anunciado | — | UJ-1 e UJ-2 em homologação |
| CAP-17 | FR-6, FR-40 | — | uso real sem validação | — | relatório assinado pelo físico |
| CAP-18 | P7 (MPPG 11.a) | AD-14, AD-31 | item do catálogo promovido sem conferência; manual lido como `conforme` | — | teste: item automatizável fica em sombra até a conferência; manual nasce vazio |
| CAP-19 | PPR vivo | AD-3, AD-41 | versão do TPS desatualizada no PPR | — | teste: troca de versão → PPR desatualizado |
