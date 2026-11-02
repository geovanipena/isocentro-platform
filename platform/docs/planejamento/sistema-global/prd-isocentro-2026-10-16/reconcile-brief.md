---
title: 'Conciliação PRD × brief (brief-sgq-rt-2026-10-13)'
created: '2026-10-16'
entrada: '../brief-sgq-rt-2026-10-13/ (brief.md, addendum.md, .memlog.md)'
alvo: 'prd.md (draft, 16/10/2026)'
---

# Conciliação: PRD × brief

O que o brief, o adendo e o memlog decidiram ou propuseram, e como isso aparece no PRD.

Não contam como lacuna, porque foram decisões do usuário em 16/10/2026:

- o Synergy (SAT) saiu do MVP, então são quatro máquinas e não cinco;
- o prazo da 3ª fração ou 10% da dose vale também para o Duplo Check;
- não há escrita no Eclipse no MVP (o PRD é mais restrito que o brief, o que é coerente).

Legenda: **ausente**, **contradito**, **enfraquecido**, **ok**.

## Confirmação pedida: métricas de sucesso e riscos/fora de escopo

- **Métricas de sucesso: é lacuna.** O PRD não tem uma seção para elas. Das sete métricas do brief ("Como saber que deu certo"), só a de cobertura virou requisito (FR-37). As de CQ no mesmo dia e de validação estão implícitas (FR-23, FR-40). As outras não aparecem como meta: 100% de segunda checagem até a 3ª fração, com meta antes da 1ª; 100% de revisão antes da 1ª fração no alto risco; 30 dias acompanhados; o físico deixar de manter planilhas paralelas.
- **Riscos de produto: é lacuna.** O §12.2 lista só modos de falha por FR, para o `riscos.md`. Faltam os riscos de produto do brief: manutenção por uma pessoa só, upgrade quebrando avaliadores, PPR desatualizado e o valor das tabelas antigas.
- **Fora de escopo: é lacuna.** O PRD não tem lista explícita. Bloqueio e escrita no ARIA aparecem espalhados (FR-5, NFR-1), mas a IORT e o recálculo de dose 3D próprio não estão declarados fora em lugar nenhum.

## Tabela

| # | Item da entrada | Onde está na entrada | Situação no PRD | Sugestão de onde entra |
| --- | --- | --- | --- | --- |
| 1 | Métricas de sucesso (as 7 métricas: cobertura, segunda checagem 100% até a 3ª fração com meta antes da 1ª, revisão 100% no alto risco, CQ sem vencimento e falha no mesmo dia, 30 dias acompanhados, validação e log íntegro, fim das planilhas paralelas) | brief, "Como saber que deu certo" | **ausente** como seção; só a cobertura virou FR-37 | PRD: novo §2.4 ou §15 "Métricas de sucesso" |
| 2 | Meta "o físico deixa de manter as planilhas paralelas de vencimentos **e de QA de paciente**" | brief, métricas; memlog (assumption) | **ausente**. No MVP o PSQA é só uma data lida (FR-16) e não há registro de QA de paciente, então a meta não é alcançável com o MVP atual | PRD, seção de métricas, com a nota "QA de paciente depois do MVP", ou um FR novo no §7 |
| 3 | Aceites das fases, que "continuam válidos": FP < 1/plano, sensibilidade semeada > 0,85, regra-piloto ponta a ponta sem o núcleo conhecer RT, "duas telas, zero estilo duplicado" | adendo, "As fases (v0.5)" | **enfraquecido**. Só os 30 s/plano entraram (NFR-5). FR-6 mede a sensibilidade mas não tem meta. A FR-9 diz só "mesmo tema". O §4.1 descreve o núcleo agnóstico sem consequência testável | PRD: FR-6 (meta de sensibilidade), FR-4/FR-5 (FP), FR-9 (zero estilo duplicado), FR-1 ou FR-2 (teste da regra-piloto) |
| 4 | Fora de escopo: IORT/INTRABEAM fora (decisão de 13/10) e `iort-streamlit` fora | brief, "Fora"; memlog | **ausente**. O PRD não cita a IORT | PRD: nova seção "Fora de escopo" (ou §2.2/§10) |
| 5 | Fora de escopo: recálculo de dose 3D próprio; a segunda checagem é por ponto e o 2D/3D fica para depois | brief, "Fora"; memlog (pilar 3) | **ausente** como exclusão. Está só implícito em FR-13 e Q3 | PRD, seção "Fora de escopo" |
| 6 | Fora de escopo: bloquear o fluxo, escrever no ARIA ou no DW, enviar dado a terceiros | brief, "Fora" | **ok**, mas espalhado (FR-5, NFR-1, NFR-2) | Consolidar na seção "Fora de escopo" |
| 7 | Maior risco: a manutenção depende de uma pessoa, sem fornecedor; todo upgrade pode quebrar avaliadores. E a "vantagem honesta": quem escreve é o físico responsável e a base documenta cada decisão | brief, "O que o torna diferente" e "Riscos" | **ausente**. A FR-40 só repete a bateria semeada após upgrade | PRD: nova seção "Riscos de produto" (§12.4) |
| 8 | Risco do PPR desatualizado: FFF e SRS/SBRT fora do PPR, e a NN-6.10 art. 15, XIV exige PPR novo antes de qualquer modificação. O PPR declara CQ pelo TG-40 sem MLC, imagem, SRS e FFF | brief, "O problema" e "Riscos" | **ausente** | PRD §12.4 (riscos) e §13 (questão: o PPR novo precede o MVP 3?) |
| 9 | Risco das tabelas de feixe: dados de 2010 e 2020, e "a segunda checagem vale tanto quanto a tabela" | brief, "Riscos" | **enfraquecido**. FR-10 valida a conversão, mas não registra o risco da idade e da representatividade do dado de origem | PRD §12.4, ou nota na FR-10 |
| 10 | Inovação 1, "cada verificação nasce com o porquê" | brief, "O que o torna diferente" 1 | **ok** (§1, FR-1) | — |
| 11 | Inovação 2, modo sombra de 30 dias para **toda** regra nova | brief 2; adendo (TG-275, Stuhr 2022) | **enfraquecido, com justificativa**. FR-4 põe os 30 dias como `[SUPOSIÇÃO]`, encurtáveis com justificativa, por causa das obrigações já vencidas. É coerente, mas o brief não previa a exceção | Confirmar com o usuário (já está na Q9) |
| 12 | Inovação 3, sensibilidade por erro semeado como o registro de validação que a RDC 657 pede | brief 3; adendo (TG-201, TG-100, §4º) | **ok** no mecanismo (FR-6, FR-40); **enfraquecido** na meta (ver #3) | FR-6 |
| 13 | Inovação 4, auditoria externa espelhada como verificação interna (NN-6.10 art. 36; GT 2302; PQRT/INCA; Guia CNEN), com gatilho de calendário | brief 4; adendo (gatilhos, inovações, Fase 4) | **enfraquecido**. Aparece só numa célula do §10 ("depois") e não está no glossário. A auditoria externa entra apenas como vencimento (FR-33) | PRD: glossário §3 e §10 (linha Documentação ou GQ), com a definição |
| 14 | Inovação 5, biblioteca de regras citável e separada do software; o que sai do serviço é a biblioteca, o software não (RDC 657, art. 5º, § 1º) | brief 5; adendo; memlog (escopo comercial) | **ausente**. Sem isso, a arquitetura não sabe que as regras precisam ficar num artefato separado e versionável | PRD: §1 (visão) e um FR no §4.1 ("regras em biblioteca separada, citável, com versão"); uma linha no §12.3 |
| 15 | Conflito do escopo comercial: só a biblioteca sai do serviço × "produto para outros serviços" do brief do Radioteradados | memlog (decision) | **ausente** | PRD §13 (questão) ou addendum |
| 16 | Ambição regulatória: uso interno permanente ou dossiê para registro, ligado à classe ANVISA | adendo, "Decisões pendentes" | **ausente** do §13. A Q1 trata só da classe | PRD §13, junto da Q1 |
| 17 | Índice de segurança (fórmula proposta pelo autor; ASTRO SiNA, ICRP 112) | adendo, "Base das cinco inovações" | **ausente**. O próprio brief já não o lista entre as 5 | Addendum (registro de ideia depois do MVP, módulo Indicadores) |
| 18 | Visão de 2 a 3 anos: uma tela nas **três clínicas**; chegar à inspeção da ANSN e à avaliação da ANVISA com o histórico pronto; cada número aponta para a norma | brief, "Visão" | **enfraquecido**. O §1 tem as três perguntas, mas sem o horizonte nem "as três clínicas"; a inspeção aparece só no §2.1 | PRD §1, com um parágrafo de horizonte |
| 19 | Casos de incidente que motivam o MVP (Panamá, Glasgow 2006, Épinal, Costa Rica, Białystok, Toulouse), com o mapeamento caso → MVP | brief, "O problema"; adendo, tabela de casos | **ausente** | PRD §1 (uma frase) e addendum (tabela). Também podem servir de fonte para os casos semeados da FR-6 (decisão do usuário) |
| 20 | "Não há caso local registrado"; a motivação é a obrigação legal e o padrão externo | brief; memlog (by user) | **ausente** | PRD §1 |
| 21 | Motivação da RDC 657: o prazo de adequação venceu em 30/03/2024 | brief, "O problema" | **ausente** (o PRD cita a RDC 657 só como requisito) | PRD §1 ou §12.3 |
| 22 | Reaproveitamento externo no Plano: `LDClark/PlanCheck`, `jsfrench/uhg-plancheck` e `MAAS-PlanScoreCard` para as regras de plan check em ESAPI (o brief os lista no MVP 2) | brief, tabela do MVP 2; adendo, código externo | **ausente** no §6 | PRD §6 (descrição) ou addendum |
| 23 | Vocabulário TG-263 no núcleo (Fase 0) e as ferramentas TG263-Toolkit, TG263ComplianceTool e `tg263` (C03, I06) | adendo, Fase 0 e código externo | **ausente**. O núcleo do PRD não tem vocabulário de estruturas | PRD §4.1 ou §10 (Plano, depois) e addendum |
| 24 | Pseudonimização com `pydicom/deid` e dicognito (G18) | adendo, código externo | **ausente**. A NFR-2 proíbe a saída de dados, mas não prevê pseudonimização | Addendum ou NFR-2 |
| 25 | Cuidados de licença e versão: PlanCheck (licença, ESAPI 15.6), BED_Calc sem licença, pymedphys com API beta a validar contra casos conferidos | adendo, coluna "Cuidado (B10)" | **enfraquecido**. A FR-38 trata o SOUP em geral e só cita o kQ do pylinac | FR-38 (licença como campo obrigatório) e addendum |
| 26 | pylinac com o kQ do TRS-398 de 2000: passar o kQ da Rev. 1 | adendo | **ok** (FR-38) | — |
| 27 | QATrack+ só como modelo de dados; pylinac para os testes de imagem | adendo | **ok** (§7) | — |
| 28 | Reaproveitamento interno: `scriptsvarian`, `preplan`, `Estruturas-auxiliares_API` como avaliadores ESAPI; `srs-streamlit` portado; SSRS/RDL como canal de entrega, com a lógica movida para o motor | adendo, "Onde os projetos atuais entram" | **enfraquecido**. O `srs-streamlit` está no §10; o SSRS e os scripts ESAPI não aparecem como canal nem como avaliador | PRD §10 e addendum |
| 29 | `matriz/vinculos.csv` vira dado do ISOCENTRO | adendo | **ok** (§10, "depois") | — |
| 30 | Os quatro gatilhos (evento, calendário, prazo, estado) | adendo | **ok** (glossário §3; FR-11, FR-24, FR-33) | — |
| 31 | Gatilho de **estado** (objeto parado além do limite; aging por estado, Fase 5) | adendo | **enfraquecido**. Está no glossário, mas nenhum FR nem linha do §10 o usa | PRD §10 (Tratamento ou Indicadores, depois) |
| 32 | Campos do objeto Verificação: `versao`, `rpn_referencia` e `rpn_local`, `cep`, `escore_anomalia`, `prazo` | adendo, esboço JSON | **enfraquecido**. A FR-1 lista regra, proveniência, gatilho, responsável, avaliador, severidade e estado, sem versão, RPN nem CEP | FR-1 (pelo menos versão e RPN) e addendum para a arquitetura |
| 33 | Índice com duas coberturas: obrigações e itens de verificação | memlog (change) | **enfraquecido**. A FR-37 só cobre as 74 obrigações | FR-37 |
| 34 | Política de adoção: todos os protocolos candidatos geram itens, cada um marcado com o protocolo de origem | memlog (by user) | **ok** em parte (FR-1, FR-22, com a referência por teste); a regra não está escrita | FR-22 (uma consequência) |
| 35 | Duplo Check remoto entre clínicas, permitido se o uso em rede estiver documentado | memlog (proposta da mesa) | **ausente** (não foi confirmado pelo usuário) | PRD §13, junto da Q2 |
| 36 | Piloto do plan check: mama ou próstata | adendo, "Decisões pendentes" | **ausente** (o plan check fica depois do MVP) | Addendum, ou §10 (Plano, depois) |
| 37 | Pendências do serviço que afetam o MVP: câmaras, dispositivo de QA da DUO, N_D,w × ICRU 90 | brief; adendo | **ok** em parte (nota do §7). O N_D,w × ICRU 90 não está | Nota do §7 ou §13 |
| 38 | Números de apoio (Liu 2019, Berry 2020, Stuhr 2022, Xu 2021, Huang 2023) | adendo | **ausente**. Aceitável num PRD, mas útil para as metas de tempo e de erro | Addendum (citar) |
| 39 | Trava fica no ARIA: só o físico dá o Treatment Approved | brief; memlog (by user) | **ok** (§1, FR-5) | — |
| 40 | MVP 2 acompanha a sequência real do srvariadb e o Duplo Check é sempre por outro físico | brief; memlog | **ok** (FR-16, FR-17, FR-20) | — |
| 41 | MVP 1: comissionamento pela Tab. 8 do TG-219 e TG-119; limites do TG-219/TG-114; sem tabela, `indeterminado` | brief; adendo, aceite | **ok** (FR-12 a FR-14) | — |
| 42 | Incidentes: citar a NN-6.10 pela Res. 277/2021 e acrescentar o art. 26; o Epimed continua o canal oficial | adendo | **ok** (§8) | — |
| 43 | Vencimentos: "nada vence sem aviso prévio configurável"; Fase 2 sem código específico de PPR | adendo | **ok** (FR-33, FR-34, §9) | — |
| 44 | Log com retenção de 10 anos (§ 3º) e hash (§ 4º); TG-201 ponta a ponta | adendo | **ok** (FR-3, FR-39) | — |
| 45 | Fase 6: braquiterapia no mesmo modelo e escore de anomalia ordenando a fila (Huang 2023 só como viabilidade) | adendo; memlog | **ok** em parte (HDR na FR-27); o escore de anomalia está **ausente** | §10 (Plano ou Indicadores, depois) ou addendum |
