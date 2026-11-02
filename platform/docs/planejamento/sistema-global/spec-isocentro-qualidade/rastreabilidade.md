# Rastreabilidade — Módulo Garantia da Qualidade

Liga cada capacidade ao requisito (PRD) ou decisão, à regra (espinha), ao modo de falha a avaliar e à forma de verificação. A coluna **riscos.md** fica vazia até o físico escrever as linhas: este arquivo não inventa risco.

| CAP | FR / decisão | AD | Modo de falha a avaliar | riscos.md | Verificação |
| --- | --- | --- | --- | --- | --- |
| CAP-1 | FR-22, itens nível 2 | AD-26, AD-31 | teste aplicado à máquina errada; tolerância sem origem | — | teste de carga: etiqueta × máquina; teste de esquema |
| CAP-2 | FR-23 | AD-4 | "conforme" digitado; execução sem autor | — | teste: resultado calculado; log com quem e quando |
| CAP-3 | FR-23, C1, FR-41 | AD-29 | tolerância errada ou fora de tolerância sem alerta (§12.2) | — | erro semeado: valor fora → `alta` no mesmo dia |
| CAP-4 | FR-24 | AD-28 | teste vencido marcado como em dia (§12.2) | — | teste com app fechado e diário sem registro |
| CAP-5 | FR-25 | — | limite exibido sem origem | — | caso conferido à mão |
| CAP-6 | — | AD-26 | instrumento vencido usado sem aviso | — | erro semeado: certificado vencido → `indeterminado` |
| CAP-7 | TRS-398 calculado | AD-14 | k_Q ou N_D,w errado muda a dose de todos | — | reprodução da planilha atual; caso conhecido semeado |
| CAP-8 | pylinac no MVP | AD-14 | análise mal configurada passa imagem com erro | — | imagens de resultado conhecido; erro plantado |
| CAP-9 | FR-26 | AD-33 | arquivo com dado de paciente importado | — | teste: exportação de PSQA recusada |
| CAP-10 | FR-27 | AD-29 | fonte HDR usada sem S_K (§12.2) | — | teste: troca de fonte → "não liberada" |
| CAP-11 | FR-28 | AD-24 | registro não restaurável | — | restauração com log válido |
| CAP-12 | FR-9 | AD-18 | tela congelada na análise | — | UJ-3 em homologação |
| CAP-13 | FR-6, FR-40 | AD-35, AD-39 | uso real sem validação | — | relatório assinado pelo físico |
| CAP-14 | FR-36 | AD-14 | aferição com decaimento ou referência errados (§12.2) | — | casos conferidos à mão; meia-vida e data semeadas erradas |
| CAP-15 | G1 (classe C) | AD-35, AD-38, AD-39 | k_Q ou N_D,w errado muda a dose de todos; GQ calculando por fora do item | — | casos com resposta conhecida; teste de arquitetura |
| CAP-16 | PPR vivo; MLC e imagem ausentes do PPR (falha confirmada, 16/10/2026) | AD-3, AD-26 | recurso da máquina sem CQ; Anexo H diferente do programa executado | — | teste: máquina com MLC sem teste de MLC → alerta; Anexo H = programa versionado |
