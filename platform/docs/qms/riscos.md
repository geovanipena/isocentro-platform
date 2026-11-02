# Análise de risco

> **A preencher pelo físico responsável.** Modos de falha, severidade e
> controles são julgamento clínico. Os agentes do BMad leem esta tabela para
> ligar requisito a risco; não inventam linhas nela.

Referências: ISO 14971:2019 (processo de gestão de risco) e AAPM TG-100 (FMEA
aplicado à radioterapia: severidade, ocorrência e detectabilidade).

| ID | Etapa do fluxo | Modo de falha | Efeito no paciente | S | O | D | Controle existente | Verificação |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| RD-1 | Radioteradados — cálculo do indicador | Fórmula ou definição diferente da pretendida | Indireto: gestão ou avaliação decide com número errado; nenhum efeito em dose | | | | Ficha técnica aprovada (FR-17), lista de origem (FR-18), faixa EXPERIMENTAL (FR-20) | SM-2: conjunto de cursos conferidos à mão |
| RD-2 | Radioteradados — interrupção | Interrupção real não detectada (frequência errada ou dado faltando) | Atraso na busca ativa de um paciente que interrompeu | | | | Frequência não identificada fica fora da taxa e listada (FR-6) | Casos manuais com interrupção e frequência semanal |
| RD-3 | Radioteradados — relatório mensal | Paciente reidentificável num recorte pequeno | Privacidade (LGPD) | | | | Supressão de células com menos de 5 casos (FR-19) | Teste automatizado |
| RD-4 | Radioteradados — fechamento do mês | Mês congelado com carga incompleta do data warehouse | Número oficial incompleto | | | | Cálculo só depois da carga cobrir o mês; mês provisório (NFR-1) | Teste com data de carga |
| RD-5 | Radioteradados — classificação de encerramento | Registro com dado de paciente vaza para o repositório ou para log | Privacidade (LGPD) | | | | Fora do repositório e de logs (FR-22) | `varrer_identidade` e teste de log |

> RD-1 a RD-5 aprovadas pelo físico responsável em 13/10/2026 (fechamento do
> PRD do Radioteradados). S, O e D ainda a preencher.

## Fundação (frente R-16)

> Linhas acrescentadas em 26/10/2026 a pedido do físico responsável. Modo de
> falha, controle e verificação vêm da spec da Fundação
> (`spec-isocentro-fundacao/rastreabilidade.md`), já aprovada por ele.
> **Efeito no paciente, S, O e D ficam em branco: são dele.** A R-16 fecha
> quando estiverem preenchidos.

| ID | Etapa do fluxo | Modo de falha | Efeito no paciente | S | O | D | Controle existente | Verificação |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| RF-1 | Fundação — versão do app × banco (CAP-1) | App novo gravando em banco velho | | | | | AD-10, AD-19, AD-27: versão divergente → somente leitura | Teste em PostgreSQL |
| RF-2 | Fundação — sessão (CAP-2) | Autoria forjada com a senha do app | | | | | AD-25: login da pessoa no banco | Teste: `isocentro_app` sem sessão não lê nem grava |
| RF-3 | Fundação — perfis e clínicas (CAP-3) | Clínica vendo dado de outra; ação sem capacidade | | | | | AD-8, AD-11, AD-12: RLS e capacidade conferidas pelo banco | Teste de RLS e capacidade em PostgreSQL |
| RF-4 | Fundação — gravação (CAP-4) | Dado sem log; log editável | | | | | AD-3 a AD-6, AD-27: transação tudo-ou-nada, log só-acrescentar | Teste: falha na transação; UPDATE/DELETE negados |
| RF-5 | Fundação — log encadeado (CAP-5) | Log alterado sem detecção | | | | | AD-32: hash encadeado e âncora diária | Teste: linha alterada é apontada com posição |
| RF-6 | Fundação — identidade (CAP-6) | Paciente ou pessoa ligados por parecença de nome | | | | | AD-13, AD-26: chave `Ser` + clínica; nome só apelido | Teste de arquitetura: sem junção por nome |
| RF-7 | Fundação — catálogo de verificações (CAP-7) | Verificação sem fonte ou tolerância sem origem | | | | | AD-31 | Teste de esquema |
| RF-8 | Fundação — motor (CAP-8) | Exceção lida como `conforme`; execução duplicada | | | | | AD-14, AD-15, AD-28 | Teste do contrato e de idempotência |
| RF-9 | Fundação — importação ESAPI (CAP-9) | Resultado ESAPI de plano antigo valendo para o atual | | | | | AD-15: versão do plano no JSON | Teste com JSON inválido e versão trocada |
| RF-10 | Fundação — sombra (CAP-10) | Verificação em sombra gerando alerta | | | | | AD-14 | Teste |
| RF-11 | Fundação — erro semeado (CAP-11) | Semeado contaminando indicador | | | | | AD-14 | Teste; relatório de sensibilidade |
| RF-12 | Fundação — alerta (CAP-12) | Alerta gerado e não visto | | | | | AD-29 | Teste; contramétrica SM-C1 |
| RF-13 | Fundação — assinatura (CAP-13) | Assinatura vale para versão diferente da conferida | | | | | AD-30; P9: invalida nos quatro casos | Teste com versão alterada → pendente |
| RF-14 | Fundação — prazo (CAP-14) | Prazo vencido com app fechado não alerta | | | | | AD-9, AD-20, AD-28: concentradora | Teste: alerta `alta` na abertura seguinte |
| RF-15 | Fundação — dado faltando (CAP-15) | Prazo vira `conforme` por falta de dado | | | | | AD-16, AD-17: falta de dado → `indeterminado` | Teste com `variandw` fora |
| RF-16 | Fundação — banco fora (CAP-16) | Gravação perdida ou corrente quebrada com banco fora | | | | | AD-23: só leitura com banco fora | Teste com banco inacessível |
| RF-17 | Fundação — backup (CAP-17) | Backup não restaurável; chave perdida | | | | | AD-21, AD-24: AES-256, cópia lacrada com a gestão | Restauração mensal registrada no log |
| RF-18 | Fundação — privacidade (CAP-18) | Dado identificável em arquivo ou log | | | | | AD-7, AD-33 (controle análogo ao RD-5) | `varrer_identidade`, teste de log |
| RF-19 | Fundação — interface (CAP-19) | Tela congelada; degrau não anunciado | | | | | AD-18, AD-36 | Teste de padrão visual; caso conferido à mão |
| RF-20 | Fundação — migração (CAP-20) | Gravação dupla JSON + banco; usuário perdido na migração | | | | | AD-8, AD-37: corte por entidade | Conferência por entidade antes do corte |
| RF-21 | Fundação — dependências (CAP-21) | Dependência proibida entrando sem aviso | | | | | AD-22, AD-34 | Teste por `ast` na suíte (R-24) |
| RF-22 | Fundação — validação (CAP-22) | Uso real sem validação | | | | | AD-35 | Relatório assinado pelo físico |
| RF-23 | Fundação — tabela perfil → capacidades configurável | Admin dá a um perfil capacidade que ele não devia ter | | | | | Travas fora da tabela (escopo.md, "Usuários"); mudança gravada com autor no log | Teste: as travas resistem a qualquer configuração |

## IA no ISOCENTRO (frente R-63, AD-42)

> Linhas acrescentadas em 26/10/2026 a pedido do físico, com o aceite do
> AD-42. Controle e verificação vêm da regra do AD-42. **Efeito no paciente,
> S, O e D ficam em branco: são dele.** Cada módulo que usar IA ganha a sua
> linha de viés de automação quando a frente dele (R-64..R-68) entrar.

| ID | Etapa do fluxo | Modo de falha | Efeito no paciente | S | O | D | Controle existente | Verificação |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| RI-1 | Qualquer módulo com sugestão de IA | Viés de automação: a pessoa aceita a sugestão sem conferir | | | | | AD-42 (1), (2) e (7): sugestão nunca preenche campo, traz a origem e é marcada "sugestão de IA"; aceite gravado com autor e hora | Conjunto de avaliação com sugestões erradas semeadas; taxa de aceite sem alteração acompanhada |
| RI-2 | Qualquer módulo com sugestão de IA | Troca do modelo (SOUP) sem registro: comportamento muda sem ninguém saber | | | | | AD-42 (5) e (6): nome, versão e hash fixados; troca é mudança registrada que roda de novo o conjunto de avaliação | Hash conferido na carga do modelo; resultado da avaliação versionado com cada versão |

## Medidas de controle externas ao software

> Decididas pelo físico responsável em 26/10/2026 (G1): contam para a
> classificação IEC 62304 do núcleo, do Plano e do Radioteraficha.

| Medida | O que controla | Onde está |
| --- | --- | --- |
| Trava de aprovação do ARIA | O ISOCENTRO é advisory: nenhum plano é liberado ou bloqueado por ele | ARIA (sistema clínico) |
| Assinatura em papel | A ficha e a capa impressas continuam conferidas e assinadas pela equipe | Fluxo da sala de tratamento |
