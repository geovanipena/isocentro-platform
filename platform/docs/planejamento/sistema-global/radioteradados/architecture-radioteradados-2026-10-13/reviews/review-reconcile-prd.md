---
title: 'Conferência PRD → Architecture Spine — Radioteradados'
created: '2026-10-13'
insumo: '../../prd-radioteradados-2026-10-13/prd.md (+ addendum.md, .memlog.md)'
alvo: '../ARCHITECTURE-SPINE.md (+ .memlog.md)'
---

# Conferência PRD → Architecture Spine

O spine cobre a maior parte do PRD: camadas, um dono para frequência e dias úteis (AD-2), número e lista de origem na mesma passada (AD-3), ficha técnica versionada (AD-4), estado do serviço fora do git (AD-5), relatório versionado (AD-7), papel `gestao` (AD-8), faixa com três chaves (AD-9) e servidor local (AD-11). As lacunas abaixo vêm em ordem de gravidade.

## Alta

### L-1. A data do dado não tem fonte, e o mês nunca vira definitivo

- **PRD:** "Data do dado — a data da última carga do data warehouse que o número usou, mais a data do cálculo" (§3). "Cada indicador mostra a data do dado, o degrau da fonte e se o mês é provisório ou definitivo" (FR-1). "no máximo até 3 meses depois do fim do mês; depois congela como definitivo" (§3). "Um mês só é calculado depois que a última carga do data warehouse cobre o mês inteiro" (NFR-1).
- **Spine:** AD-3 põe a data do dado no `Resultado`, mas o Deferred admite que não se sabe de onde sai a data da carga ("Até lá, o AD-6 não grava retrato definitivo").
- **O que falta:** (a) o que o `Resultado` mostra como data do dado enquanto a data da carga for desconhecida (só a data do cálculo? "carga desconhecida"?), sem fingir que a carga está coberta; (b) como fica o rótulo de um mês com mais de 3 meses quando o retrato não pode ser gravado: o PRD manda congelar, e o spine o deixa recalculando para sempre, sem dizer se ele aparece como "definitivo" ou "provisório"; (c) o portão do NFR-1 vale para o *cálculo* do mês, e o AD-6 só barra a gravação do retrato. O mês corrente e o anterior podem ser calculados com carga incompleta sem aviso.
- **Risco:** RD-4 (mês congelado incompleto) e a regra "data do dado e degrau em todo número".

### L-2. Lista de origem identificada fica onde o PRD não deixa (retrato, gestão, admin)

- **PRD:** "O perfil de gestão não vê a lista de origem" (FR-18). "a lista de origem identifica pacientes e só existe na rede do serviço, para físico e médico (este, só dos próprios)" (§7). Perfis: "administrador mantém a configuração" (§3).
- **Spine:** AD-3 diz que *todo* `Resultado` traz a lista de origem; AD-6 grava "o `Resultado` de cada indicador" como retrato em JSON na pasta do serviço; AD-8 diz que a lista "só é montada" para `fisico/admin` e `medico`; o mapa de capacidades diz "filtrada na tela".
- **O que falta:** (a) contradição interna: se a lista sai sempre na mesma passada (AD-3), ela é montada também para gestão, e o filtro do AD-8 vira filtro de widget, o contrário de "antes de chegar ao widget"; falta dizer em que camada a lista é cortada por papel (no domínio, por parâmetro de papel/médico, ou numa projeção antes da tela); (b) o retrato do mês não pode guardar nome e registro, ou então precisa ser declarado dado de paciente, com as mesmas regras de FR-22/RD-5 (fora do git e do log, acesso); (c) o `admin` ganhou a lista de origem sem respaldo do PRD: ou sai, ou vira decisão registrada do físico responsável.
- **Risco:** RD-3/RD-5 e a regra "gestão sem lista de origem".

## Média

### L-3. FR-21 ("mostra a última leitura") sem armazenamento da última leitura

- **PRD:** "Quando o banco não responde, a aba mostra a última leitura com a data e o degrau da fonte, e o aviso aparece em primeiro lugar" (FR-21; UJ-1, caso de borda). Adendo: três degraus (banco → espelho → relatório).
- **Spine:** só os meses definitivos são guardados (AD-6). A convenção de erros diz "Falha de banco vira `None` + motivo". O mês provisório (justamente o mês aberto por padrão, FR-1) não tem última leitura guardada, e nenhum degrau espelho ou relatório é nomeado.
- **O que falta:** onde fica a última leitura do mês provisório (cache do último `Resultado` por estação ou no serviço), qual degrau ela declara e a regra de que o aviso vem antes dos números.

### L-4. Retrato definitivo "lido, não recalculado" contra FR-17 e FR-3

- **PRD:** "A tela recalcula com a versão vigente e diz qual é; relatórios já emitidos não mudam" (FR-17). "O usuário combina filtros, e todos os indicadores respeitam o recorte" (FR-3).
- **Spine:** AD-6: no mês definitivo, o `Resultado` "passa a ser lido, não recalculado".
- **O que falta:** (a) o que a tela mostra num mês definitivo depois que uma versão nova da ficha é aprovada: a do retrato, contra o FR-17, ou um recálculo, contra o AD-6; e se o recálculo é possível sem a carga original; (b) os recortes de máquina, médico, sítio e convênio são combinatórios, e o retrato guarda um `Resultado` por indicador; falta dizer se o recorte é recalculado sobre o definitivo (e de que dado) ou se só o total é congelado; (c) congelar com definição ainda "não aprovada" ou com encerramento ainda a classificar, quando passam os 3 meses: o retrato precisa carregar essa marca.

### L-5. NFR-1: o cálculo roda na estação, sob demanda, em horário de tratamento

- **PRD:** "as consultas não podem degradar o ARIA em horário de tratamento" e `[SUPOSIÇÃO: o cálculo roda em segundo plano, fora do horário de tratamento]` (NFR-1); "a aba abre em até 3 segundos com os meses já calculados" (NFR-2).
- **Spine:** AD-6 recalcula o mês provisório sob demanda em `QThread`, em cada estação que abre a aba; a concentradora fica adiada.
- **O que falta:** o spine troca a suposição do PRD sem dizer que troca, e não diz como mantém a carga baixa (12 meses × até 3 provisórios × recortes × N estações em horário clínico). Também não diz como cumpre os 3 s, já que os provisórios nunca estão "já calculados". Falta uma decisão explícita: cache compartilhado do provisório com validade, limite de consultas, ou aceitação registrada da troca.

### L-6. Regime semanal fora do `_RITMO` e um só dono do vocabulário

- **PRD:** FR-6 dá limiar próprio ao regime semanal; a pergunta 5 diz que "o vocabulário já traduzido pela Capa não tem 'semanal'".
- **Spine:** AD-2: "Valor de frequência fora do `_RITMO` = frequência não identificada".
- **O que falta:** enquanto o semanal não entra no `_RITMO`, todo curso semanal cai em "não identificada" e o limiar semanal do FR-6 nunca roda. Para pôr o semanal no `_RITMO`, que pertence à Capa e à Ficha Virtual, é preciso dizer como preservar o comportamento delas, como o AD-2 já faz para os feriados. Falta também quem calcula o limiar "7 dias corridos + 3 dias úteis", porque `dias_uteis_entre` só conta dias úteis.

### L-7. A pasta do serviço tem um "padrão" de reserva que pode cair na estação ou no repositório

- **PRD:** "Os registros ficam na pasta do serviço definida pelo administrador, fora do repositório (`.gitignore`)" (FR-22); "pasta e parâmetro do serviço são decisão de administrador, nunca da estação" (FR-23).
- **Spine:** AD-5 herda do `datas_relevantes` a "precedência variável → serviço → padrão".
- **O que falta:** dizer que, para classificações, aprovações, conferência e retratos, não há reserva "padrão" local. Sem a pasta do serviço, a gravação falha e avisa, em vez de gravar na estação ou ao lado do código. O `.gitignore` sozinho não cobre um caminho padrão fora do padrão ignorado.

## Baixa

### L-8. Escopo da supressão "< 5" e campos que o PDF precisa

- **PRD:** "Célula de recorte com menos de 5 casos sai suprimida ('< 5')" no relatório (FR-19), que leva também recorte, estado de aprovação e faixa EXPERIMENTAL.
- **Spine:** AD-7 põe a supressão em `dominio/indicadores` "num lugar só", sem dizer a quem ela se aplica (só ao PDF? também à tela de gestão?) nem se conta pelo numerador ou pelo denominador. O `Resultado` mínimo do AD-3 não traz recorte nem estado da faixa EXPERIMENTAL, mas o AD-7 diz que o PDF é gerado "só a partir de `Resultado`".
- **O que falta:** o alvo da supressão e o critério da contagem; recorte e faixa EXPERIMENTAL no `Resultado`, ou numa entrada explícita do gerador de PDF.

### L-9. Verde reservado à dose nos gráficos matplotlib

- **PRD:** NFR-4 "sem verde como cor de ação (verde é dose)".
- **Spine:** a convenção cita `ui.py` e `estilo.py`. Os gráficos, porém, saem do matplotlib, cujo ciclo de cores padrão inclui verde (`C2`), e o `estilo.py` não os alcança.
- **O que falta:** uma paleta de gráfico tirada do `estilo.py`, sem verde, com modo dia/noite, valendo para a tela e para o PDF.

## Coberto sem ressalva

Somente leitura e sem escrita no ARIA (AD-1/AD-11); frequência não inferida pelas pausas (AD-2); Ficha Virtual preservada nos feriados (AD-2); relatório imutável com versão (AD-7); histórico de reclassificação só acrescenta (AD-5); classificação fora do git e do log (AD-5, convenção de erros); servidor local (AD-11); NFR-6, sem nuvem nem processo novo (Structural Seed); faixa EXPERIMENTAL não automática e ligada ao R-07 (AD-9); configuração por id do ARIA, sem capacidade herdada (AD-10); enfermagem extensível (AD-8).
