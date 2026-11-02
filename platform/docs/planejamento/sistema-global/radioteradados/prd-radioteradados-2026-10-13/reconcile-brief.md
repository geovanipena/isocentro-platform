---
title: 'Reconciliação — brief × PRD do Radioteradados'
created: '2026-10-13'
insumo:
  - '../brief-radioteradados-2026-10-13/brief.md'
  - '../brief-radioteradados-2026-10-13/addendum.md'
  - '../brief-radioteradados-2026-10-13/.memlog.md'
alvo:
  - 'prd.md'
  - 'addendum.md'
  - '.memlog.md'
---

# Reconciliação: brief → PRD do Radioteradados

Conferência do que o brief (e o adendo e o memlog dele) traz e o PRD perdeu ou contradiz. Não entram as divergências que o `.memlog.md` do PRD explica: definição de abandono e "encerramento a classificar" (FR-22), limiar de interrupção em dias úteis, `FractionPattern` como frequência, simulação e percurso entrando na v1 por "TOMO-DUO / TOMO-ANA", braquiterapia lida pela agenda e atividades de conformidade empurradas para a v2.

Gravidade: **alta** = afeta escopo, aceite ou liberação da v1; **média** = requisito ou restrição que some ou fica implícito; **baixa** = contexto, tom ou "por quê" que se perde.

## Lacunas

### L1. Portão R-07 não aparece no PRD — **alta**

- **Insumo (brief, Riscos):** "**Portão R-07.** A conferência dos cursos contra o ARIA, pendente no ISOCENTRO, é a mesma que libera este painel." (o memlog do brief cita o "portão R-07 comum" entre os insights do brainstorm)
- **No PRD:** o FR-20 trata a faixa EXPERIMENTAL só como "conferência dos números contra o ARIA num período de teste", sem dizer que ela depende da conferência R-07, que segue pendente no ISOCENTRO, nem que é a mesma conferência. Nenhuma seção nomeia o R-07.
- **Onde deveria estar:** FR-20 (dependência explícita) e §7 ou uma seção de riscos/dependências. O SM-2 deveria dizer se a amostragem de 20 cursos *é* a conferência R-07 ou outra.

### L2. O PRD não tem seção de riscos: somem dois riscos do brief — **média**

- **Insumo (brief, Riscos):** "**Para vender:** o enquadramento do software pela ANVISA (RDC 657/2022) não verificado; capa e nomes do serviço ainda estão fixos no código." e "**Mapeamento do banco.** [...] A atividade de parada ainda nem existe."
- **No PRD:** a RDC 657/2022 não é citada em lugar nenhum (o §7 Conformidade só traz a RDC 20/2006). Os nomes do serviço fixos no código também não aparecem. O §5 diz "sem configuração de marca", mas não registra o risco. O "tempo de acelerador perdido" está no §6.2 sem a dependência de que a atividade de parada ainda precisa ser **criada no ARIA**, uma ação fora do software. O risco de definição aparece no §1, mas não como risco.
- **Onde deveria estar:** uma seção "Riscos e dependências" (ou o §10), com RDC 657/2022 (enquadramento como software, ou SaMD), nomes fixos no código e a criação da atividade de parada como pré-requisito do indicador da v2.

### L3. Gestão / responsável técnico sem perfil, sem jornada e sem recorte — **média**

- **Insumo (brief, Para quem; memlog):** "**Gestão / responsável técnico:** acompanha volume, ocupação, convênios e a tendência dos indicadores." Memlog: "Usuários: físico e gestão/RT no fechamento do mês e preparo da avaliação externa".
- **No PRD:** o §2.1 lista o trabalho a fazer, mas o §6.1 limita a v1 aos "perfis já existentes no ISOCENTRO (administrador, físico, médico)". Não se diz com que perfil a gestão entra nem o que ela vê (lista de origem com nome de paciente? só agregados?). Também não há jornada (UJ) para a gestão, e as três jornadas são do físico e da médica.
- **Onde deveria estar:** §2.3 (uma jornada da gestão) e §6.1/FR-18 (qual perfil a gestão usa e o que pode ver).

### L4. "Data do dado" em cada número e na ficha técnica — **média**

- **Insumo (brief, A solução):** "**Cada número com a sua ficha técnica:** fórmula, o que entra, o que sai e a data do dado." Adendo do brief: "Cada número mostra fonte e data, seguindo a regra do projeto de que 'reserva usada é reserva anunciada'."
- **No PRD:** o FR-16 lista fórmula, numerador, denominador, exclusões, origem e aprovação, **sem a data do dado**. A data só aparece no PDF (FR-19) e no caso de banco fora do ar (FR-21). Em operação normal a tela não precisa mostrar de quando é o número. Com o NFR-1 (mês fechado calculado e guardado), essa data vira dado relevante.
- **Onde deveria estar:** FR-16 e FR-1/FR-2 (consequência testável: todo número mostra a data da leitura).

### L5. Posicionamento, diferencial e visão de produto descartados — **média**

- **Insumo (brief, Resumo, O que o torna diferente, Visão):** "Se funcionar, é a base de um produto para outros serviços com ARIA no Brasil, mercado em que a pesquisa não encontrou oferta equivalente." "**Roda no próprio serviço**, sem nuvem [...] Não depende da versão do ARIA exigida pelo fornecedor." "O ARIA CORE Insights roda só em nuvem, exige ARIA 15.5 ou superior [...]" "Em 2 a 3 anos, é o painel que um serviço brasileiro com ARIA abre para responder à vigilância, à gestão e à operadora: instalado localmente, em português, com definições que um avaliador aceita."
- **No PRD:** o §1 Visão cobre só a v1. O §5 diz "não é produto comercial na v1" e o FR-7 sugere configuração por serviço, mas some o *porquê*: não há restrição de **rodar localmente, sem nuvem**, nem de **não depender de versão mínima do ARIA**, dois diferenciais que precisam virar NFR para não se perderem na arquitetura. A visão de 2 a 3 anos (vigilância, gestão, **operadora**) também não aparece, e é ela que justifica tirar do código os nomes de atividade.
- **Onde deveria estar:** §1 (um parágrafo de visão de longo prazo) e §8 (NFR "on-premise, sem nuvem; compatível com a versão de ARIA do serviço"). Os nomes de atividade e de serviço vão para a configuração, com a mesma regra do FR-7 estendida ao FR-13 e à capa.

### L6. Médico: percurso some do trabalho a fazer — **baixa**

- **Insumo (brief, Para quem):** "**Médicos radioterapeutas:** veem os próprios pacientes (interrupção, tempo total, percurso)."
- **No PRD:** o §2.1 traz "interrupções, tempo total", sem o percurso. A UJ-2 fala de tempo médio e interrupção. O FR-3 dá "só os meus" para todos os indicadores, então o requisito não se perde, mas a intenção sim. Também não fica claro se o médico pode sair do "só os meus" para ver o serviço inteiro (o brief diz só "vê 'só os meus'"; o PRD diz que a aba "abre em" só os meus, o que sugere que dá para sair).
- **Onde deveria estar:** §2.1 e FR-3 (deixar explícito se o médico pode ou não ver o agregado do serviço).

### L7. Critério de sucesso do PDF aceito saiu das métricas — **baixa**

- **Insumo (brief, Como saber que deu certo):** "`[SUPOSIÇÃO]` O PDF mensal é aceito como material da próxima avaliação externa."
- **No PRD:** virou a pergunta 5 do §10 e uma suposição do §11, mas não está no §9 como métrica (mesmo condicional). O SM-1 valida o FR-19 só pela geração, não pela aceitação.
- **Onde deveria estar:** §9, como métrica secundária condicional ("aceito na próxima avaliação externa").

### L8. O "por quê" do custo: trabalho fora do horário e o esforço de Zurique — **baixa**

- **Insumo (brief, O problema):** "Juntá-los exige consulta ao banco ou planilha, e isso fica com o físico, fora do horário." "[...] contagens divergiram de 7 a 10% por diferença de definição, e o trabalho consumiu cerca de 50 pessoa-dias." "Cada serviço inventa a sua definição, e o número muda conforme quem faz a conta."
- **No PRD:** o §1 guarda a lição da definição, mas perde a dor humana (trabalho fora do horário, número que muda conforme quem calcula) e a ordem de grandeza (7 a 10%, 50 pessoa-dias), que serviria de referência para o SM-2 (que tolerância conta como "bater"?). O SM-2 diz "bate" sem tolerância.
- **Onde deveria estar:** §1 (contexto) e SM-2 (tolerância explícita, por exemplo divergência zero na lista de origem versus o limite aceitável no agregado).

### L9. Ambição declarada de cobrir "todos" os indicadores recomendados — **baixa**

- **Insumo (memlog do brief):** "Ambição declarada pelo usuário: usar as variáveis disponíveis no banco do ARIA e ter TODOS os parâmetros e indicadores recomendados para um serviço de radioterapia".
- **No PRD:** o recorte da v1 está certo, mas a ambição de catálogo completo não aparece como direção. O catálogo do adendo do brief é só referenciado no adendo do PRD. O risco é a v2 ser lida como "lista fechada" e não como caminho para o catálogo inteiro.
- **Onde deveria estar:** §1 ou §6.2 (frase de direção: a v1 é o primeiro corte de um catálogo que pretende cobrir todos os indicadores recomendados que o banco permitir).

## Conferido sem lacuna

Núcleo RDC e camada operacional (FR-4 a FR-15), filtros e períodos (FR-2, FR-3), lista de origem (FR-18), PDF mensal (FR-19), faixa EXPERIMENTAL (FR-20), meta ESGO/ESTRO única (FR-15, §5), itens fora da v1 (§6.2), banco somente leitura, servidor local, padrão de tela e verde reservado à dose (NFR-3, NFR-4, adendo do PRD), vigência da RDC 20/2006 (§10), Revisão Semanal e prazo de 60 dias como evolução (§6.2).
