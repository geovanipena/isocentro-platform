---
title: 'Reconciliação: pesquisa de domínio × PRD Radioteradados'
created: '2026-10-13'
insumo: '../research-bi-radioterapia-indicadores-2026-10-13/research.md'
alvo: 'prd.md, addendum.md (decisões do .memlog.md consideradas)'
---

# Reconciliação: pesquisa de domínio × PRD Radioteradados

Conferência das recomendações (R1–R6), insights, perguntas abertas, ressalvas e insumos para o brief da pesquisa contra `prd.md` e `addendum.md`. Divergências que o próprio PRD ou o `.memlog.md` registram como decisão (ex.: camada de conformidade e prazo de 60 dias na v2, metas do serviço fora da v1, notificação de incidentes em outro sistema) **não** contam como lacuna.

## O que foi bem absorvido

- **R1** (núcleo = itens do 6.11 com ficha técnica): FR-4 a FR-8, FR-16, FR-17; os dois indicadores fora do banco aparecem marcados, não omitidos.
- **Vigência da RDC 20/2006**: ressalva mantida em §7 e §10, pergunta 4.
- **Nuance do 6.11** (vínculo com a avaliação externa, não painel obrigatório): §7, "preparam a avaliação externa".
- **R3** (camada operacional sem metas importadas, ESGO/ESTRO no colo): §4.3, FR-15, §5.
- **Pergunta aberta 2** (operacionalização pelo físico): FR-17 e UJ-3; alinhamento com a vigilância parcialmente coberto em §10, pergunta 5.
- **R2, prazo de 60 dias, tempo de acelerador perdido**: adiados para a v2 com justificativa explícita em §6.2 (decisão, não lacuna).

## Lacunas

### L1. Afirmação atribuída à "literatura" sem apoio na pesquisa — gravidade: média

- **PRD, §9, SM-C2:** "o painel não pode virar medição de pessoas, o medo que a literatura aponta como barreira de adesão."
- **Pesquisa:** nenhuma frente fala de medo de medição individual nem de barreira de adesão. O mais próximo é o alerta de Harden et al.: "o registro sim/não (ex.: 'revisão por pares feita') não prova qualidade" [14], que é outra coisa. O brief também não traz essa afirmação.
- **Onde corrigir:** §9, SM-C2. Tirar a atribuição à literatura (manter a contramétrica como decisão do serviço) ou incluir a fonte em nova rodada de pesquisa.

### L2. Exagero e causalidade inventada sobre o caso de Zurique (fonte única) — gravidade: média

- **PRD, §1:** "A divergência por definição foi o que obrigou o único BI publicado sobre o ARIA a refazer a maior parte dos painéis." (frase herdada do brief, §75)
- **Pesquisa:** "a maioria precisou de adaptação, alguns foram feitos do zero; 'novos pacientes' divergiu 7–10% por definição do evento de registro" [15]. São dois achados separados; a pesquisa não diz que a divergência *causou* o retrabalho, e diz "adaptação", não "refazer". A fonte [15] tem confiança **média**, é **fonte única**, e "o verificador só alcançou o resumo"; é "relato de um centro, sem medida de resultado".
- **Onde corrigir:** §1, segundo parágrafo. Sugestão: "No único BI publicado sobre o ARIA (um centro, Zurique), a maioria dos painéis precisou de adaptação e as contagens divergiram 7–10% por definição de evento."

### L3. R5 sumiu: ressalva de que não há evidência de ganho de ocupação — gravidade: média

- **Pesquisa, R5:** "Não prometer ganho de ocupação do acelerador como resultado do painel" (confiança alta pela ausência: "nenhum estudo de 2019 em diante mediu a ocupação do acelerador antes e depois de implantar um painel"). Também nos Insumos para o brief, Restrições: "não prometer ganho de ocupação [R5]". E: o único ganho medido [16] "é do conjunto 'físico do dia + painel', não do painel isolado".
- **PRD:** ocupação aparece como trabalho da gestão (§2.1) e como indicador (FR-10), mas a restrição não aparece em lugar nenhum: nem em §5 (Fora de propósito), nem em §9 (Métricas). Hoje o PRD não promete o ganho, mas também não protege contra a promessa nos fluxos seguintes (UX, material para a chefia).
- **Onde deveria estar:** §5 (ex.: "Não promete aumento de ocupação; mede a ocupação, não a melhora") ou como contramétrica em §9.

### L4. "Data do dado" saiu da ficha técnica e da tela (R1/R4) — gravidade: média

- **Pesquisa, R1:** ficha técnica com "fórmula, fonte no ARIA, exclusões, **data do dado**". **R4:** "mostrar a fonte e a data de cada número". Diferencial nos Insumos: "mostra fonte e data de cada número".
- **PRD:** a ficha técnica (§3 e FR-16) lista fórmula, numerador, denominador, exclusões, origem no banco e aprovação, **sem a data do dado**. A data aparece só no PDF (FR-19) e no dado de reserva (FR-21); na tela, no caso normal, nenhum FR exige mostrar quando o número foi calculado — relevante porque NFR-1 guarda o mês fechado calculado em segundo plano.
- **Onde deveria estar:** §3 (Ficha técnica), FR-16 e uma consequência em FR-1/FR-2 ("cada indicador mostra a data e hora do cálculo").

### L5. Norma CNEN/ANSN 6.10 e parte da camada de conformidade sumiram sem registro — gravidade: baixa

- **Pesquisa, Resumo executivo:** núcleo regulatório = seis indicadores da RDC "mais as exigências contínuas da RDC e da norma CNEN/ANSN 6.10". **R2:** inclui "segunda assinatura e consulta médica semanal [5]" e marca a revisão física semanal como "recomendação TG-275, **não exigência brasileira**". **R3:** inclui "pendências de física".
- **PRD:** a norma 6.10 não é citada em nenhum ponto (nem §7 Conformidade). §6.2 adia cálculo verificado, revisão médica e física semanal e tempo de acelerador perdido, mas **não lista** segunda assinatura nem pendências de física (nem v1, nem v2), e trata revisão médica e física semanal como um bloco só, apagando a distinção exigência × recomendação.
- **Onde deveria estar:** §7 (citar a 6.10 como origem das exigências da v2) e §6.2 (incluir segunda assinatura e pendências de física, separar o que é exigência brasileira do que é recomendação TG-275).

### L6. Enquadramento ANVISA de software (RDC 657/2022) e restrição "sem nuvem" não registrados no PRD — gravidade: baixa

- **Pesquisa, Maior ressalva:** "não se verificou se um BI gerencial é enquadrado como dispositivo médico (RDC 657/2022)". **R6** e Pergunta aberta 3. **R4:** "Rodar local sobre o banco do ARIA, sem nuvem".
- **PRD:** §5 diz que a v1 não é comercial, o que justifica adiar a questão, mas a ressalva não aparece nem como risco herdado (o brief a registra em "Para vender"). A restrição "sem nuvem" está só implícita (aba do ISOCENTRO, §7 "dentro da rede do serviço"), não como requisito de arquitetura no adendo.
- **Onde deveria estar:** §5 ou §10 (uma linha: "antes de qualquer comercialização, verificar RDC 657/2022"); adendo, "Padrões do projeto" (sem nuvem, execução na rede do serviço).

### L7. "A única meta publicada" exagera a pesquisa — gravidade: baixa

- **PRD, §5:** "na v1 mostra tendências e a única meta publicada (colo do útero)".
- **Pesquisa:** ESGO/ESTRO 2023 é "o **raro** conjunto com metas numéricas" [13], não o único; e traz também "início da RT ≤ 6 semanas do encaminhamento (ótimo ≥ 90%, mínimo ≥ 75%)", que o PRD não cita (provavelmente por falta da data de encaminhamento no ARIA, mas isso não está dito).
- **Onde corrigir:** §5 ("a meta ESGO/ESTRO de tempo total no colo do útero") e FR-15 (registrar por que a meta de início ≤ 6 semanas fica fora).

## Resumo

| # | Lacuna | Onde no PRD | Gravidade |
|---|---|---|---|
| L1 | SM-C2 atribui à literatura um "medo/barreira" que a pesquisa não traz | §9 | média |
| L2 | Zurique: "refazer" e causalidade inventada; fonte única tratada como fato | §1 | média |
| L3 | R5 (não prometer ganho de ocupação) ausente | §5 ou §9 | média |
| L4 | "Data do dado" fora da ficha técnica e da tela | §3, FR-16, FR-1/2 | média |
| L5 | Norma 6.10, segunda assinatura, pendências de física e distinção TG-275 ausentes | §7, §6.2 | baixa |
| L6 | RDC 657/2022 e "sem nuvem" não registrados | §5/§10, adendo | baixa |
| L7 | "Única meta publicada"; meta de início ≤ 6 semanas omitida sem motivo | §5, FR-15 | baixa |
