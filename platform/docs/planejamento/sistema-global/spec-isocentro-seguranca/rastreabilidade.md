# Rastreabilidade — Módulo Segurança do paciente

Liga cada capacidade ao requisito (PRD) ou decisão, à regra (espinha), ao modo de falha a avaliar e à forma de verificação. A coluna **riscos.md** fica vazia até o físico escrever as linhas: este arquivo não inventa risco.

| CAP | FR / decisão | AD | Modo de falha a avaliar | riscos.md | Verificação |
| --- | --- | --- | --- | --- | --- |
| CAP-1 | FR-29 (Ford 2012, TG-100) | AD-5, AD-26 | dado clínico copiado; registro apagado; etapa fora do mapa | — | teste: só chave canônica; sem DELETE; lista = mapa do Ford |
| CAP-2 | I2, anonimato, LGPD arts. 11, 37, 46 | AD-11, AD-12, AD-33 | dado sensível lido por perfil sem acesso; notificador exposto; leitura sem trilha | — | teste em PostgreSQL: recusa no banco; relatório sem notificador; leitura gera evento |
| CAP-3 | FR-30, guia CNEN 2020 | AD-28, AD-29 | prazo de 30 dias contado de data errada (§12.2); investigação não iniciada sem alerta | — | casos de borda com app fechado; relatório com itens a–k |
| CAP-4 | FR-30, FR-31, RDC 36 art. 10, NT GVIMS 09/2025 | AD-28 | 15º dia útil calculado errado; 72 h ou 60 dias perdidos | — | casos com feriado nacional e virada de mês; óbito 72 h; never event 60 dias |
| CAP-5 | ciclo de análise | AD-29 | ação vencida sem alerta | — | teste de prazo |
| CAP-6 | FR-47 | — | vínculo a evento ou barreira inexistente | — | teste: ID resolve no catálogo e, se houver, no `riscos.md` |
| CAP-7 | FR-32, revisão | AD-29 | evento sem triagem esquecido | — | teste: 7 dias → alerta |
| CAP-8 | matriz e indicadores | AD-33 | paciente reidentificável em recorte pequeno | RD-3 (controle análogo) | teste de supressão < 5 |
| CAP-9 | FR-9 | AD-18 | alerta no perfil errado | — | UJ-5 em homologação |
| CAP-10 | FR-40, LGPD art. 38 | AD-35 | taxonomia inconsistente entre físicos; matriz que não reproduz o SEVRRA | — | kappa ≥ 0,7; RIPD; perfil do 6EX = SEVRRA jan/2023; relatório assinado |
| CAP-11 | FR-49 | AD-5 | linha do catálogo sem fonte | — | teste: linha sem fonte recusada |
| CAP-12 | FR-49 | AD-3 | barreira sem dado contada como funcionando; nível mudado sem confirmação | — | teste: sem dado → não funcionando; sem confirmação → nível intacto |
| CAP-13 | FR-49 | AD-28, AD-29 | subida a RA/RMA sem alerta | — | teste: proposta → alerta ao físico |
| CAP-14 | FR-47, FR-49 | — | O proposto de contagem errada | — | teste: contagem por evento e período |
| CAP-15 | PPR vivo | AD-3 | perfil de risco do PPR diferente do vigente | — | teste: mudança de perfil → PPR desatualizado |
