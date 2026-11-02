# Rastreabilidade — Fundação

Liga cada capacidade ao requisito (PRD), à regra (espinha), ao modo de falha a avaliar (PRD §12.2) e à forma de verificação. A coluna **riscos.md** aponta as linhas RF-n que o físico mandou acrescentar em 26/10/2026; efeito no paciente e S, O, D são dele (R-16): este arquivo não inventa risco.

| CAP | FR / NFR | AD | Modo de falha a avaliar | riscos.md | Verificação |
| --- | --- | --- | --- | --- | --- |
| CAP-1 | NFR-10 | AD-10, AD-19, AD-27 | app novo gravando em banco velho | RF-1 | teste em PostgreSQL: versão divergente → somente leitura |
| CAP-2 | FR-7, FR-8 | AD-25 | autoria forjada com a senha do app | RF-2 | teste: `isocentro_app` sem sessão não lê nem grava |
| CAP-3 | FR-7, NFR-6 | AD-8, AD-11, AD-12 | clínica vendo dado de outra; ação sem capacidade | RF-3 | teste de RLS e capacidade em PostgreSQL |
| CAP-4 | FR-3 | AD-3–AD-6, AD-27 | dado sem log; log editável | RF-4 | teste: falha na transação; UPDATE/DELETE negados |
| CAP-5 | FR-3 | AD-32 | log alterado sem detecção (§12.2) | RF-5 | teste: linha alterada é apontada com posição |
| CAP-6 | FR-20 | AD-13, AD-26 | paciente ou pessoa ligados por parecença de nome | RF-6 | teste de arquitetura: sem junção por nome |
| CAP-7 | FR-1 | AD-31 | verificação sem fonte ou tolerância sem origem | RF-7 | teste de esquema |
| CAP-8 | FR-2, FR-39 | AD-14, AD-15, AD-28 | exceção lida como `conforme`; execução duplicada | RF-8 | teste do contrato e de idempotência |
| CAP-9 | FR-2 | AD-15 | resultado ESAPI de plano antigo valendo para o atual | RF-9 | teste com JSON inválido e versão trocada |
| CAP-10 | FR-4 | AD-14 | sombra gerando alerta | RF-10 | teste |
| CAP-11 | FR-6 | AD-14 | semeado contaminando indicador | RF-11 | teste; relatório de sensibilidade |
| CAP-12 | FR-5, FR-41 | AD-29 | alerta gerado e não visto (§12.2) | RF-12 | teste; contramétrica SM-C1 |
| CAP-13 | FR-8 | AD-30 | assinatura vale para versão diferente da conferida (§12.2) | RF-13 | teste com versão alterada → pendente |
| CAP-14 | FR-41 | AD-9, AD-20, AD-28 | prazo vencido com app fechado não alerta | RF-14 | teste: alerta `alta` na abertura seguinte |
| CAP-15 | NFR-3, NFR-7 | AD-16, AD-17 | prazo vira `conforme` por falta de dado | RF-15 | teste com `variandw` fora |
| CAP-16 | — | AD-23 | gravação perdida ou corrente quebrada com banco fora | RF-16 | teste com banco inacessível |
| CAP-17 | FR-3 | AD-21, AD-24 | backup não restaurável; chave perdida | RF-17 | restauração mensal registrada no log |
| CAP-18 | NFR-2 | AD-7, AD-33 | dado identificável em arquivo ou log | RF-18 (controle análogo ao RD-5) | `varrer_identidade`, teste de log |
| CAP-19 | FR-9, NFR-3 | AD-18, AD-36 | tela congelada; degrau não anunciado | RF-19 | teste de padrão visual; caso conferido à mão |
| CAP-20 | — | AD-8, AD-37 | gravação dupla JSON + banco; usuário perdido na migração | RF-20 | conferência por entidade antes do corte |
| CAP-21 | NFR-9 | AD-22, AD-34, AD-39 | dependência proibida entrando sem aviso; mudança revisada com raio menor que o real | RF-21 | teste por `ast` na suíte; `tools/raio.py` |
| CAP-22 | FR-40, FR-6 | AD-35 | uso real sem validação | RF-22 | relatório assinado pelo físico |
| CAP-23 | FR-7 | AD-11 | admin dá a um perfil capacidade que ele não devia ter | RF-23 | teste: as quatro travas resistem a qualquer configuração |
| CAP-24 | — | AD-40, AD-27 | módulo no disco e fora do executável; app e concentradora com conjuntos diferentes | — | teste de arquitetura (regra do manifesto) |
| CAP-25 | PPR vivo | AD-3, AD-26 | função (SPR, RT) desatualizada no PPR | — | teste: troca de SPR → PPR desatualizado |
