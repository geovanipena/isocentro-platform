# Rastreabilidade — Módulo Documentação e conformidade

Liga cada capacidade ao requisito (PRD) ou decisão, à regra (espinha), ao modo de falha a avaliar e à forma de verificação. A coluna **riscos.md** fica vazia até o físico escrever as linhas: este arquivo não inventa risco.

| CAP | FR / decisão | AD | Modo de falha a avaliar | riscos.md | Verificação |
| --- | --- | --- | --- | --- | --- |
| CAP-1 | FR-33, V1–V3 | AD-5 | item sem data aparecendo em dia; periodicidade sem fonte; data sem documento | — | teste: "sem data" → informativo; tipo sem fonte recusado; data exige documento |
| CAP-2 | FR-33, NR-7 | AD-28 | modificação da instalação ou retorno do IOE sem disparar o vencimento | — | teste de evento (levantamento e ASO) |
| CAP-3 | FR-33, V1 | AD-11, AD-12 | ASO lido por perfil sem acesso; dado enviado a terceiros | — | teste em PostgreSQL; `varrer_identidade` |
| CAP-4 | art. 20 IV–V | — | mês sem resultado esquecido | — | teste de pendência mensal |
| CAP-5 | FR-34, FR-41 | AD-3, AD-28 | prazo vencido com app fechado sem alerta | — | teste com app fechado; leitura pela fachada da GQ |
| CAP-6 | FR-35, V2 | AD-37 | item perdido, divergência escondida ou gravação dupla na migração | — | relatório conferido item a item; divergência → data mais cedo |
| CAP-7 | FR-9 | AD-18 | painel mostrando clínica não permitida | — | UJ-4 em homologação |
| CAP-8 | FR-40 | AD-35 | uso real sem validação | — | relatório assinado pelo físico |
| CAP-9 | V3 | AD-26, AD-38 | segunda lista de equipe; IOE fora da lista | — | teste: marca IOE no cadastro do núcleo; só SPR altera |
| CAP-10 | FR-35, PPR vivo | AD-3, AD-30, AD-41 | PPR emitido com dado velho ou inventado; mudança sem aviso | — | teste: dado ausente → "sem dado"; mudança após emissão → "PPR desatualizado" |
| CAP-11 | NN-6.10 | AD-30 | texto alterado sem SPR | — | teste: só SPR altera; versão com autor e data |
