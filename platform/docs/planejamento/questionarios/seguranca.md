# Questionário do físico — módulo Segurança do paciente

> **Rascunho da IA: nada aqui é decisão.** As opções abaixo são as que a spec
> do módulo Segurança e a base de conhecimento já levantam, cada uma com a
> fonte; nenhuma é recomendada. Quem decide é o físico responsável, na frente
> R-44, e a resposta vai para o memlog da spec (e as linhas de risco para o
> `docs/qms/riscos.md`) pelas mãos dele, não por este arquivo.

Frente R-73 (robô, 23/10/2026), que prepara a R-44. Spec:
`docs/planejamento/sistema-global/spec-isocentro-seguranca/SPEC.md` (Open
Questions). A I4 do PRD (§15) junta as duas primeiras perguntas.

**Como ler as fontes.** `[CÓDIGO p. N]` é o documento do acervo
(`conhecimento/matriz/fontes.csv`) e a página do texto integral em
`conhecimento/texto/`, conferida nesta sessão. `CAP-n` é da spec do módulo
Segurança, `FR-n` do PRD (`prd-isocentro-2026-10-16/prd.md`) e `AD-n` da
espinha (`architecture-isocentro-2026-10-19/ARCHITECTURE-SPINE.md`). "v0.1" é
a spec de origem, `incidentes/SPEC - Módulo incidentes v0.1.md`, absorvida
pela spec atual. O que vem de uma ficha da base (`conhecimento/fichas/…`) está
citado pelo arquivo, porque a ficha resume e não é o texto do documento. Onde
a base não tem o que dizer, está escrito "a base não responde" e não há opção
inventada.

Ordem: as duas perguntas da taxonomia primeiro (etapas e escala de desvio,
que definem os campos do registro e os eixos da matriz), depois a retenção.

Fora deste questionário, embora a R-44 os peça: a separação e a
classificação dos 30 incidentes históricos (kappa, CAP-10) e as linhas do
módulo no `riscos.md` (S, O, D são do físico). Também fora, por serem de
outras frentes: I1 (Epimed e NSP) e o calendário de dias úteis, que são da
R-45 (clínica), e a trilha de leitura e o RIPD.

---

## Etapas do Care Path (I4, primeira parte)

**Pergunta.** Qual lista fechada de etapas o registro usa para "onde
ocorreu" e "onde foi detectado" (CAP-1), e é a mesma lista para os dois
campos?

**Estado hoje.** A CAP-1 pede as duas etapas "(Care Path do serviço)", e a
CAP-8 cruza uma com a outra na matriz de calor. A spec deixa a lista em
aberto: "a v0.1 traz 13 etapas; a G15, 5 opções de 'detectado em'" (Open
Questions). O FR-29 fixa só as 5 opções do "detectado em".

**O que a base diz.**

| fato | fonte |
|---|---|
| O mapa de processo serve para dizer onde o incidente **nasce ou é detectado**, não como nem por quê; isso fica com a narrativa e a taxonomia causal | [FORD-2012-ILS p. 5], III.B |
| O consenso traz mapas separados para teleterapia e braquiterapia; o processo começa na consulta e vai até o seguimento; 91 passos em teleterapia e 88 em braquiterapia, nesse nível de detalhe "para permitir a codificação exata" | [FORD-2012-ILS p. 5] |
| Teleterapia em 8 macroetapas: avaliação do paciente, imagem para planejamento, planejamento, revisão e verificação pré-tratamento, entrega, gestão da qualidade durante o tratamento, pós-tratamento, gestão da qualidade de equipamento e software | [FORD-2012-ILS p. 13–14], Apêndice B, seção 1 |
| 35 dos 91 passos de teleterapia são marcados como barreira de segurança ("SB") | [FORD-2012-ILS p. 6] |
| A **mesma** lista de passos alimenta os dois campos: 1.9 "onde foi achado" e 2.42 "onde se originou" | [FORD-2012-ILS p. 6]; elementos 1.9 [p. 17] e 2.42 [p. 19] |
| Os dois campos não estão no mesmo formulário: o 1.9 é da seção 1, a ficha de quem relata, que deve ser o mais simples possível (meta: menos de 1 min); o 2.42 é da seção 2, preenchida pela análise. Quem relata não faz análise | [FORD-2012-ILS p. 8], III.E; [p. 9], IV |
| A taxonomia britânica numera os grupos de etapa de 0 a 20, de infraestrutura a gestão de pessoal (21 grupos pela nossa contagem; a norma não diz o total), e tem 213 subcódigos | grupos: [UK-RT-TAXONOMIA p. 19], Apêndice 2; 213: [p. 11] |
| Nela, o "método de detecção" é um subcódigo da mesma lista, com o prefixo `MD`, e é obrigatório em todo relato | [UK-RT-TAXONOMIA p. 12] |
| Um dos subcódigos novos é o uso de lista eletrônica de tarefas ("care pathway"): tarefa incompleta que impede a etapa seguinte | [UK-RT-TAXONOMIA p. 7], Tabela 3, (6g) |
| Pacote mínimo proposto para o serviço: registro com WHO-ICPS e campo "detectado em" (revisão de plano, 1º dia, semanal, tratamento) | ficha `fichas/atividades/G04-G05-G14-G15-G17.md`, "Pacote mínimo" |
| Do Care Path do ARIA no serviço, a base tem três etapas do físico (Planejamento, Aprovação Física, Duplo Check), da votação de 30/03/2026 | ficha `fichas/referencias/LISTA-VERIF-CAREPATH.md` |

A lista completa de atividades do Care Path do ARIA de cada clínica não está
na base: ela mora no `variandw`, e o `tools/atividades.py` a lista só de
dentro da rede da clínica (`tools/LEIAME_CLINICA.md`). Se as três clínicas
têm o mesmo Care Path, **a base não responde**. Se o serviço trata
braquiterapia no escopo deste módulo, a spec não diz.

| opção | fonte | o que muda adiante |
|---|---|---|
| as 13 etapas da v0.1 (agendamento, simulação/TC, contorno, prescrição, planejamento, revisão física, aprovação médica, transferência ao ARIA, QA pré-tratamento, posicionamento/IGRT, entrega, revisão semanal, encerramento), nos dois campos | v0.1, §4 (`EtapaProcesso`); spec, Open Questions | a matriz da CAP-8 é 13 × 13; a v0.1 diz que a mesma lista serviria à aba Virtual e ao resumo de "quem fez cada etapa". A v0.1 diz que a lista "segue o Care Path real do serviço", mas não cita o documento, e deixa "fechar a enum com o Care Path real" como próximo passo (§8, item 3); o "1º dia" do FR-29 não está entre elas: o FR-29 teria de ser reescrito, ou a lista ganhar a etapa |
| as 5 opções do FR-29 no "detectado em" (revisão do plano, 1º dia, revisão semanal, tratamento, outra), com outra lista para o "onde ocorreu" | FR-29; ficha G04-G05-G14-G15-G17, "Pacote mínimo" | o registro fica curto no campo de detecção (CAP-1 pede quase-incidente em até 90 s); a matriz da CAP-8 deixa de ser quadrada, e a lista do "onde ocorreu" continua em aberto |
| o mapa de processo do Ford 2012: as 8 macroetapas, ou os 91 passos de teleterapia (e os 88 de braquiterapia, se entrar), nos dois campos | [FORD-2012-ILS p. 5–6, p. 13–15] | a lista é de consenso publicado e traz a marca de barreira de segurança, que a CAP-8 usa para mostrar "onde faltam barreiras" (spec, Why); no Ford, o "onde se originou" é da análise e não de quem relata, e a CAP-1 pede as duas etapas no registro de até 90 s; com os 91 passos, a matriz tem 91 × 91 células, e a CAP-8 suprime no relatório as que têm menos de 5 casos; o FR-29 seria reescrito |
| a taxonomia britânica de 2024: os 21 grupos ou os 213 subcódigos, com a detecção como subcódigo `MD` | [UK-RT-TAXONOMIA p. 11–12, p. 19] | mesma lista para os dois campos; vários subcódigos por evento (primário e adicionais [UK-RT-TAXONOMIA p. 13]), o que pede ao registro mais de um campo de etapa; o FR-29 seria reescrito |
| as atividades do Care Path do ARIA de cada clínica | CAP-1 ("Care Path do serviço"); spec, Open Questions ("contra o Care Path real"); FR-16 (`[SUPOSIÇÃO]` do PRD: PSQA e Duplo Check como atividades do Carepath no `variandw`) | a lista vem do `variandw` e não da base; o levantamento precisa de alguém na rede da clínica (`tools/atividades.py`); a lista muda quando o Care Path muda, e a matriz de um trimestre pode não ser comparável à do outro |

Também é parte da resposta: a lista é uma só para as três clínicas, ou uma
por clínica (a CAP-8 sai "por período e clínica").

**Destrava:** R-44 (gravar as etapas); R-47, que depende da R-44
expressamente (matriz ocorrência × detecção, revisão trimestral agrupada por
etapa, e os 30 incidentes do kappa classificados nesta lista). A R-46 grava
os dois campos do registro (CAP-1), mas a dependência dela na R-44 não está
escrita no `DESTINO.md`.

resposta do físico: (26/10/2026, Geova, em sessão) Pela regra geral que ele
fixou nesta sessão (decisão com referência; havendo duas ou mais, a mais
restritiva): **mapa de processo do Ford 2012, a mesma lista nos dois
campos**, com os 91 passos de teleterapia (e os 88 de braquiterapia) e a
marca de barreira de segurança, agrupados nas 8 macroetapas. Quem relata
escolhe a macroetapa (e o passo, se souber) para caber nos 90 s; o "onde
ocorreu" é refinado na análise [FORD-2012-ILS p. 5–6, 8–9]. **Uma lista
para as três clínicas** (a referência é uma só). O FR-29 é reescrito. Vai à
discussão no serviço: Ford × taxonomia britânica não se ordenam por
"restritiva", e o "1º dia" do FR-29 precisa ser casado com um passo.

---

## Escala de desvio dosimétrico (I4, segunda parte)

**Pergunta.** Com que escala, e com que fonte, o registro classifica o
desvio dosimétrico de um incidente ou quase-incidente?

**Estado hoje.** A v0.1 propõe "nenhum / < 5% / 5–20% / > 20% / erro
geométrico" (§4, `GravidadeDose`) e diz que os campos se ancoram no Ford
2012. A spec pede "a confirmação do físico e uma fonte" (Open Questions); o
PRD, "escala de desvio dosimétrico com fonte" (§15, I4). O dano clínico é
outro campo, pela WHO-ICPS (CAP-1), e não é perguntado aqui.

**O que a base diz.**

| fato | fonte |
|---|---|
| Duas escalas complementares e **separadas**, que não se misturam: a gravidade médica e o desvio de dose; incidente sem componente de dose recebe "não se aplica" | [FORD-2012-ILS p. 6–7], III.C |
| Escala de dose do Ford, por curso, em desvio absoluto da prescrição total para **qualquer estrutura**: 1/2 < 5%; 3/4 > 5–10%; 5/6 > 10–25%; 7/8 > 25–100%; 9/10 > 100%; e "não se aplica" | [FORD-2012-ILS p. 15], Apêndice C, seção 2 |
| No Ford, erro geográfico ou atraso não é categoria própria: recebe a nota do desvio de dose de efeito equivalente | [FORD-2012-ILS p. 15], nota da tabela; [p. 6] |
| A gravidade vale também para o quase-incidente, estimada como se tivesse chegado ao paciente | [FORD-2012-ILS p. 6]; nota da escala médica do Apêndice C [p. 15] |
| O Ford separa a sua escala da do TG-100 de propósito: a do TG-100 serve à FMEA, a dele ao banco de incidentes que será minerado | [FORD-2012-ILS p. 6] |
| TG-100, Tabela I: dose errada 5–10% (S 5–8), muito errada cerca de 10–20% (S 9–10); local errado 3–5 mm (S 5–8), muito errado > 5 mm (S 9–10); volume errado, por perda marginal ou geográfica | [TG-100 p. 13], Tabela I |
| TG-35, citado pela ICRP 86: tipo A, superdose de 25% ou mais da dose total; tipo B, de 5% a 25%, e a maior parte das subdoses; subdose não corrigida a tempo vira tipo A com os mesmos percentuais. O 5% vem de uma superdose de 20% numa semana, que equivale a cerca de 5% no curso | [ICRP-86 p. 25], Tabela 2 |
| No TG-35 também são tipo A a dose fora do campo pretendido e a energia ou modalidade errada | [ICRP-86 p. 24], parágrafo 11 |
| Exposição acidental é desvio "substancial" da prescrição; não há norma internacional que quantifique esse "substancial", e a ICRP aponta o TG-35 como uma abordagem para classificar | [ICRP-86 p. 24], parágrafos 8 a 10 |
| As menores diferenças de dose detectadas clinicamente ficam na ordem de 5–10% | [ICRP-86 p. 26], parágrafo 14 |
| A classificação britânica é por desfecho (níveis 1 a 5, de notificável a não conformidade), não por percentual de dose | [UK-RT-TAXONOMIA p. 5–6], Tabela 2 |
| Exposição médica não planejada é dose ou fracionamento "diferente substancialmente" do prescrito; o guia não dá número | [CNEN-GUIA-EXP-NAO-PLANEJADA-2020 p. 6] |

As faixas da v0.1 (5–20% e > 20%) não coincidem com as de nenhuma fonte da
base lida aqui, e a v0.1 não diz de onde vieram. O 20% aparece em outros
papéis: como teto do limiar "muito errada" do TG-100 (cerca de 10–20%) e
como superdose de uma semana no TG-35. Se algum degrau da escala deve marcar
sozinho a "exposição médica não intencional" do art. 26 (CAP-3), as normas
brasileiras não dizem: nem a NN-6.10 [NN-6.10 p. 8], art. 26, nem o guia da
CNEN dão percentual. A ICRP 86 aponta o TG-35 como uma forma de quantificar
o "substancial", dizendo que não há norma internacional para isso; se o
serviço o adota para o art. 26, **a base não responde**.

| opção | fonte | o que muda adiante |
|---|---|---|
| a escala da v0.1: nenhum / < 5% / 5–20% / > 20% / erro geométrico | v0.1, §4; spec, Open Questions | 5 valores no registro; o erro geométrico vira categoria à parte, o que o Ford não faz; as faixas 5–20% e > 20% não são as de nenhuma fonte da base, e a spec exige fonte |
| a escala de dose do Ford 2012 (5 faixas, < 5% a > 100%, mais "não se aplica"), com o erro geométrico pela dose equivalente | [FORD-2012-ILS p. 6–7, p. 15] | é a fonte que a v0.1 diz seguir; o registro ganha o "não se aplica"; classificar um erro geométrico pede ao físico uma estimativa de dose equivalente, e o campo nasce vazio enquanto ela não existe (Constraints, "Campo sem fonte nasce vazio") |
| os termos de gravidade do TG-100 (Tabela I), com dose, local e volume separados | [TG-100 p. 13] | o desvio sai na mesma régua do S da FMEA, que a CAP-6 liga ao `riscos.md`; o erro geométrico tem limiar em mm; o Ford registra que essa escala foi feita para FMEA e não para banco de incidentes [FORD-2012-ILS p. 6] |
| as faixas do TG-35 (tipo A ≥ 25%; tipo B 5–25%) | [ICRP-86 p. 24–25] | só três degraus abaixo de "nenhum"; a dose fora do campo e a energia ou modalidade errada já entram como tipo A, sem estimar dose equivalente; a subdose não corrigida a tempo sobe de tipo; o critério supõe controle semanal que pegue o erro em uma semana (nota da Tabela 2) |

Em qualquer opção, a escala de dose não substitui o dano clínico (WHO-ICPS),
que é campo separado na CAP-1, e o Ford pede as duas notas em todo incidente
[FORD-2012-ILS p. 7].

**Destrava:** R-44 (gravar a escala com a fonte); R-47 (os 30 incidentes do
kappa são classificados nela, e o relatório de validação a cita). A R-46
grava o campo (CAP-1), com a mesma ressalva da seção anterior.

resposta do físico: (26/10/2026, Geova, em sessão) Pela regra da mais
restritiva: **dose pela escala do Ford 2012** (degraus a partir de < 5%,
mais finos que os do TG-100 e do TG-35, e "não se aplica")
[FORD-2012-ILS p. 15]; **local e volume pelos termos do TG-100**, com o
erro geométrico em mm (3–5 mm; > 5 mm) em vez da dose equivalente
[TG-100 p. 13]. A escala da v0.1 sai (sem fonte). O dano clínico continua
no campo WHO-ICPS, separado.

---

## Retenção dos registros de incidente

**Pergunta.** Por quanto tempo o ISOCENTRO guarda os registros de incidente
e quase-incidente (registro, análise, lista do art. 26, envio ao Epimed,
atas), e o que acontece com eles ao fim do prazo?

**Estado hoje.** A espinha não deixa apagar nem editar nada (AD-5: "sem
UPDATE de conteúdo nem DELETE em dado registrado"); a spec repete para o
incidente (Constraints, "Nada se apaga"). O backup conta 10 anos após o
descarte do software (AD-24), e a retenção por tipo de registro ficou para o
épico de Software e GQ (espinha, Deferred). A spec deixa a retenção do
incidente em aberto (Open Questions).

**O que a base diz.**

| fato | fonte |
|---|---|
| As ocorrências radiológicas são registro arquivado do serviço, disponível a IOE e inspetor da CNEN, com cópia de segurança independente; a norma não fixa prazo | [NN-6.10 p. 16], art. 71, VI e parágrafo único |
| A notificação à CNEN anexa a prova de que o acidente foi registrado no livro de ocorrências radiológicas | [CNEN-GUIA-EXP-NAO-PLANEJADA-2020 p. 7], item 1 (c) |
| O NSP mantém sob sua guarda as notificações de eventos adversos, à disposição da autoridade sanitária; sem prazo | [RDC-36-2013 p. 3], art. 7º, XII |
| Os registros de **validação** do SaMD *in house* ficam pelo menos 10 anos após o descarte do SaMD | [RDC-657 p. 3], art. 5º, § 3º |
| Prontuário: depois de no mínimo 20 anos a partir do último registro, ele "poderá ser eliminado" (é mínimo e permissão, não dever de apagar); vale para qualquer forma de guarda, inclusive o prontuário nascido eletrônico | [LEI-13787-2018 p. 1], art. 6º; [p. 2], § 5º |
| CFM: guarda **permanente** do prontuário arquivado eletronicamente (meio óptico, microfilmado ou digitalizado); 20 anos no mínimo para o que ficou só em papel | [CFM-1821-2007 p. 3], arts. 7º e 8º |
| Dado pessoal se elimina ao fim do tratamento, autorizada a conservação para obrigação legal ou regulatória | [LGPD p. 8], arts. 15 e 16, I |

Se o registro de incidente do ISOCENTRO conta como parte do prontuário do
paciente, **a base não responde**: o registro liga ao paciente pela chave
canônica sem copiar dado clínico (CAP-1; AD-26), mas guarda texto livre e
dose estimada (CAP-2). A NN-6.10 e a RDC 36 mandam guardar e não dizem por
quanto tempo: nos dois pontos, **a base não responde**. A resolução do CFM é
de 2007 e o acervo a registra "alterada pela 2218-2018"; se o art. 7º segue
valendo ao lado da Lei 13.787, de 2018, a base também não responde.

| opção | fonte | o que muda adiante |
|---|---|---|
| 10 anos após o descarte do software | AD-24; [RDC-657 p. 3] | um prazo único para todo o banco, como o AD-24 já conta; a RDC 657 fala dos registros de validação, e se alcança o registro de incidente o texto não diz |
| no mínimo 20 anos a partir do último registro, pelo prazo do prontuário | [LEI-13787-2018 p. 1–2], art. 6º e § 5º | o prazo é por paciente e conta do último registro, não do descarte do software; a lei permite eliminar depois, não obriga: guardar além disso cumpre a lei e o AD-5 juntos. Só se o físico quiser eliminar ao fim do prazo é que esbarra no AD-5 (sem DELETE) e no log encadeado (AD-24, Prevents: "retenção menor que a do log"), e a espinha não tem hoje caminho para isso |
| guarda permanente | [CFM-1821-2007 p. 3], art. 7º; AD-5 | nada se descarta, que é o que o AD-5 já faz hoje; o cadastro de prazo por registro não é preciso; o backup do AD-24 passa a ter de durar sem prazo, e a chave de cifra também ("chave perdida em 10 anos" é o que o AD-24 previne) |

Em qualquer opção, o relatório de validação do módulo continua guardado 10
anos após o descarte (CAP-10; [RDC-657 p. 3]); a pergunta é sobre os
registros de incidente.

**Destrava:** R-44 (gravar a retenção); a decisão adiada de retenção por
tipo de registro na espinha (Deferred), que liga ao AD-24 e ao AD-5. A R-46
constrói o registro, e o AD-5 já vale para ela enquanto a retenção não é
gravada.

resposta do físico: (26/10/2026, Geova, em sessão) Pela regra da mais
restritiva: **guarda permanente** [CFM-1821-2007 p. 3], art. 7º — o AD-5 já
faz isso; o backup do AD-24 e a chave de cifra passam a durar sem prazo. Vai
à discussão no serviço: se o registro de incidente conta como prontuário e
se o art. 7º do CFM 1821 segue valendo ao lado da Lei 13.787.
