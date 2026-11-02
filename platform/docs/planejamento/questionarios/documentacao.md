# Questionário do físico — módulo Documentação e conformidade

> **Rascunho da IA: nada aqui é decisão.** As opções abaixo são as que a spec
> do módulo Documentação e a base de conhecimento já levantam, cada uma com a
> fonte; nenhuma é recomendada. Quem decide é o físico responsável, na frente
> R-48, e a resposta vai para o memlog da spec (e as linhas de risco para o
> `docs/qms/riscos.md`) pelas mãos dele, não por este arquivo.

Frente R-74 (robô, 23/10/2026), que prepara a R-48. Spec:
`docs/planejamento/sistema-global/spec-isocentro-documentacao/SPEC.md` (Open
Questions). No PRD (§15) as perguntas são a V1 (ASO), a V2 (datas de partida)
e a V3 (autorização, SEVRRA e lista de IOEs).

**Como ler as fontes.** `[CÓDIGO p. N]` é o documento do acervo
(`conhecimento/matriz/fontes.csv`) e a página do texto integral em
`conhecimento/texto/`, conferida nesta sessão. `CAP-n` é da spec do módulo
Documentação, `FR-n` do PRD (`prd-isocentro-2026-10-16/prd.md`) e `AD-n` da
espinha (`architecture-isocentro-2026-10-19/ARCHITECTURE-SPINE.md`). O que
vem do `ppr-streamlit` está citado pelo arquivo e pela linha
(`programa/ppr-streamlit/app.py`), porque é código e não texto da base.
`[PPR-CLINICA]` é o PPR da CEL de março de 2024, que o acervo guarda como
modelo de formatação: diz o que **uma** clínica escreveu em 2024, não o que
vale hoje para as três. Onde a base não tem o que dizer, está escrito "a base
não responde" e não há opção inventada.

**Sobre o "Destrava".** A R-50 depende da R-48 expressamente no
`DESTINO.md`. A R-49 constrói o que estas respostas definem (CAP-1, CAP-3,
CAP-4, CAP-5), mas lá a dependência dela está escrita só para R-20, R-21 e
R-39, não para a R-48: onde a R-49 aparece abaixo, é por usar a resposta,
não por dependência registrada.

Ordem: as três periodicidades (ASO, autorização, SEVRRA), depois as datas de
partida, que dependem delas, e por fim a lista de IOEs, que diz **de quem** é
cada ASO e cada mês de monitoração.

Fora deste questionário, embora a R-48 os peça: as linhas do módulo no
`riscos.md` (S, O, D são do físico). Também fora, por não estarem na lista
da R-74: o "resto do ppr-streamlit" (geração do PDF do PPR), que a spec deixa
em aberto e põe em Non-goals.

---

## Periodicidade do ASO (V1)

**Pergunta.** Com que periodicidade, e com que fonte, o ISOCENTRO calcula
quando vence o ASO de cada IOE?

**Estado hoje.** A CAP-3 guarda só a pessoa, a data do exame e a validade, e
diz que "a periodicidade vem do PCMSO, informada pelo físico"; o FR-33 marca
isso como `[SUPOSIÇÃO]`. A CAP-1 não aceita tipo sem fonte de periodicidade.
No `ppr-streamlit`, a tabela `asos` tem nome, "Último ASO" e "Validade"
(`app.py:1222-1223`), preenchidos a partir do PDF por IA externa
(`extrair_asos_do_pdf`, `app.py:737`), que é o que a R-15 tira.

**O que a base diz.**

| fato | fonte |
|---|---|
| O PCMSO inclui exame admissional, periódico, de retorno ao trabalho, de mudança de risco e demissional | [NR-7 p. 3–4], 7.5.6 |
| Exame clínico periódico: para quem está exposto a risco identificado e classificado no PGR, "a cada ano ou a intervalos menores, a critério do médico responsável"; para os demais, a cada dois anos | [NR-7 p. 4], 7.5.8, II |
| Retorno ao trabalho: exame antes de reassumir, depois de ausência de 30 dias ou mais por doença ou acidente | [NR-7 p. 4], 7.5.9 |
| Cada exame clínico gera um ASO. O conteúdo mínimo traz a data dos exames e o apto/inapto, e **não** traz data de validade | [NR-7 p. 5], 7.5.19 e 7.5.19.1 |
| O médico do PCMSO registra as funções com exposição a radiação ionizante classificadas no PGR | [NR-7 p. 36], Anexo V, 3.1 |
| Radiação ionizante: a aptidão para área controlada ou supervisionada é avaliada no admissional, no retorno e na mudança de risco, e vai no ASO; dose acima do limite anual exige nova avaliação e novo ASO | [NR-7 p. 37], Anexo V, 5.1, 5.1.1 e 5.2 |
| O PPR faz parte do PGR e é considerado no PCMSO | [NR-32 p. 12], 32.4.2.1, c) e d) |
| A CNEN pede exame periódico "de acordo com a natureza da instalação e com as doses recebidas", sem número | [NN-3.02 p. 9], 6.1.3.6, b) |
| O PPR descreve o controle médico dos IOE, "incluindo periodicidade do ASO, data do último ASO de cada IOE" | [GUIA-CNEN-RT p. 17], Anexo I, item 22 |
| PPR da CEL: controle médico pelo SESMT, "dos IOE contratados no regime CLT com periodicidade anual" | [PPR-CLINICA p. 15], seção 19 |
| Na tabela O.1 do mesmo PPR (IOE, último, validade), a validade de várias linhas não é a data do exame mais um ano: exames de meses diferentes vencem no mesmo dia; há linhas com o último exame "N/D" e validade preenchida, linhas com validade **anterior** ao exame (exame em 29/03/2023, validade 14/03/23) ou igual a ele, e uma validade que não existe no calendário (31/02/24) | [PPR-CLINICA p. 281–282], Anexo O |
| IOE terceirizado: o titular obtém o ASO do empregador antes do trabalho | [NN-3.01 p. 20], art. 65 |

O PCMSO do serviço não está no acervo (`fontes.csv` só tem a NR-7): qual
periodicidade ele fixa, **a base não responde**. O PPR fala só dos IOE CLT;
para médico, físico ou técnico com outro vínculo (terceirizado, pessoa
jurídica), **a base não responde**. Se as três clínicas têm o mesmo PCMSO,
também não.

| opção | fonte | o que muda adiante |
|---|---|---|
| um ano a partir da data do exame, ou menos se o PCMSO fixar | [NR-7 p. 4], 7.5.8, II, a), 1; [NR-32 p. 12] (o PPR faz parte do PGR) | o ISOCENTRO calcula a validade (exame + 12 meses); o físico informa o intervalo menor quando o PCMSO o tiver; o cálculo não bate com as validades da tabela O.1 do PPR; a CAP-6 importa do `ppr-streamlit` "só a pessoa e as datas" e não diz o que fazer quando a validade importada diverge do cálculo |
| dois anos a partir da data do exame | [NR-7 p. 4], 7.5.8, II, b) | vale, pelo texto, para quem **não** está exposto a risco classificado no PGR; o alerta do ASO sai com o dobro do intervalo da opção anterior |
| anual para IOE CLT, como escrito no PPR | [PPR-CLINICA p. 15] | a fonte é o PPR da clínica, que a CNEN pede que traga a periodicidade [GUIA-CNEN-RT p. 17]; IOE com outro vínculo fica sem periodicidade e, pela CAP-1, nasce "sem data"; o PPR é de uma clínica e de 2024, e cada clínica teria de informar o seu |
| sem periodicidade calculada: o físico lança a validade que o PCMSO ou o SESMT informar, e o ISOCENTRO só a compara com a data | CAP-3 ("data do exame e a validade"); [PPR-CLINICA p. 282], tabela O.1 | o registro guarda a validade informada, sem conferir com intervalo nenhum; as validades da tabela O.1 que vêm antes do exame ou não existem no calendário teriam de ser corrigidas na fonte antes de entrar; o ASO não traz validade [NR-7 p. 5], então a fonte de cada data é a informação do SESMT, e a CAP-1 teria de aceitar esse tipo de fonte, como já aceita "validade do documento" para a autorização |

Em qualquer opção, o retorno ao trabalho, a mudança de risco e a dose acima
do limite anual pedem novo ASO fora do calendário [NR-7 p. 4, p. 37]. Se
algum desses eventos deve fazer o ASO vencer na hora, como a modificação da
instalação faz com o levantamento (CAP-2), a spec não diz.

**Destrava:** R-48 (gravar a periodicidade com a fonte no memlog); R-49 (o
vencimento do ASO e a lista de IOE sem ASO, CAP-3); R-50 (a migração dos
ASOs do `ppr-streamlit` e o relatório de importados, CAP-6). A R-15 extrai
as datas do PDF e não depende da resposta.

resposta do físico: (26/10/2026) **Aplicação, na sessão, da regra que o físico fixou** (referência; havendo duas ou mais, a mais restritiva; sem base, a mais conservadora, provisória e levada à discussão no serviço). **A conferir pelo físico.** **Um ano a partir da data do exame**, ou menos se o PCMSO fixar [NR-7 p. 4], 7.5.8, II, a); vale para todo IOE, de qualquer vínculo [NN-3.01 p. 20], art. 65. Retorno ao trabalho, mudança de risco e dose acima do limite anual fazem o ASO vencer na hora [NR-7 p. 4, p. 37]. Quando a validade importada divergir do cálculo, vale a mais cedo. Discussão: o PCMSO de cada clínica (fora do acervo).

---

## Autorização: qual documento e qual periodicidade (V3)

**Pergunta.** A "autorização de funcionamento" que o ISOCENTRO acompanha é
qual documento, e de onde vem a data em que ela vence?

**Estado hoje.** A CAP-1 diz "autorização de funcionamento e SEVRRA: validade
do documento"; a spec deixa em aberto "periodicidade e fonte (hoje só há as
datas do documento)". No `ppr-streamlit`, a chave `autorizacao_funcionamento`
se chama "Autorização de Funcionamento (CNEN)" (`app.py:1486`) e guarda
realização e vencimento (`app.py:439-443`), lidos do PDF por IA externa
(`extrair_vencimentos_dos_pdfs`, `app.py:787-829`).

**O que a base diz.**

| fato | fonte |
|---|---|
| O titular requer as autorizações à CNEN conforme a Resolução 112/2011 | [NN-6.10 p. 2], art. 5º |
| A Autorização para Construção vale cinco anos, renovável por igual período | [NN-6.10 p. 3], art. 8º |
| A Autorização para Operação é pedida ao fim da construção, com o PPR | [NN-6.10 p. 3–4], arts. 12 e 13 |
| A norma de licenciamento não usa "autorização de funcionamento": os atos são aprovação do local, construção, modificação, aquisição de fontes, comissionamento, operação e retirada de operação | [NN-6.02 p. 5], art. 8º |
| Os prazos de validade da Autorização para Operação estão no Anexo II | [NN-6.02 p. 5], art. 8º, parágrafo único |
| Acelerador de 0,6 a 50 MeV é do subgrupo 7C; fonte selada em teleterapia ou HDR é do subgrupo 2B | [NN-6.02 p. 3–4], arts. 3º e 5º |
| Anexo II: a linha "3C, 6, 7C" tem validade de 1 a 3 anos. A tabela vem com células mescladas, e a linha 2B ficou sem valor na extração | [NN-6.02 p. 12], Anexo II |
| Alterar a autorização não muda o prazo de validade original | [NN-6.02 p. 8], art. 21, parágrafo único |
| A renovação é pedida com no mínimo 30 dias de antecedência do fim da validade | [NN-6.02 p. 8], art. 23; [GUIA-CNEN-RT p. 13], seção 9 |
| Só se renova autorização ainda vigente; o pedido leva o PPR atualizado, o contrato de monitoração individual e os certificados de calibração | [GUIA-CNEN-RT p. 13], 9.1 a 9.8 |
| Uma das sanções é antecipar o prazo de vigência da autorização | [NN-6.02 p. 9], art. 27, II |
| A habilitação no SUS pede "autorização para funcionamento emitida pela CNEN e alvará sanitário" vigentes | [SAES-1399-2019 p. 9], art. 16, d) |
| A RDC 20 chama o documento sanitário de "Licença de funcionamento/Licença sanitária/Alvará sanitário", expedido pelo órgão estadual ou municipal; a liberação e a renovação dependem dos requisitos da RDC 20, que não dá prazo | [RDC-20-2006 p. 3], 4.39; [p. 4], 5.1.3 |
| O glossário da NR-32 define o alvará como "licença ou autorização de funcionamento ou operação do serviço fornecida pela autoridade sanitária local" | [NR-32 p. 43], Glossário |
| A NR-32 manda manter o alvará vigente no local, na seção de radiodiagnóstico | [NR-32 p. 16], 32.4.15.1 |
| O PPR tem de estar "dentro do prazo de vigência" | [NR-32 p. 12], 32.4.2.1, a) |

"Autorização de funcionamento", na base, aparece com dois donos: a CNEN, na
SAES 1399, e a autoridade sanitária, no glossário da NR-32. Qual dos dois
documentos é o PDF que o `ppr-streamlit` guarda nessa chave, **a base não
responde**. A validade exata de cada clínica é a que está escrita na
autorização dela, que não está na base. O prazo do alvará sanitário,
**a base não responde**.

| opção | fonte | o que muda adiante |
|---|---|---|
| é a Autorização para Operação da CNEN, e vence na data escrita nela | NN-6.02, art. 8º e Anexo II [p. 5, p. 12]; CAP-1 ("validade do documento") | a periodicidade não é calculada: o físico lança a data de cada clínica, e o Anexo II só serve para conferir que fica entre 1 e 3 anos; o aviso prévio padrão de 60 dias (FR-34) já cobre os 30 dias mínimos do pedido de renovação [NN-6.02 p. 8]; alterar a autorização não muda a data (art. 21) |
| é o alvará sanitário (licença de funcionamento), e vence na data escrita nele | [RDC-20-2006 p. 3–4]; [NR-32 p. 43] | um documento de outro órgão, com outra data; a Autorização para Operação da CNEN fica fora do painel, a menos que entre como tipo próprio |
| os dois, como tipos separados, cada um pela data do próprio documento | [SAES-1399-2019 p. 9], art. 16, d); CAP-1 | dois itens por clínica no painel; a migração (CAP-6) tem uma só chave no `ppr-streamlit` para os dois, e o relatório teria de dizer a qual tipo ela foi |

Em qualquer opção, a data vem do documento e não de uma periodicidade
calculada, como a CAP-1 já prevê; a pergunta é qual documento e quantos
tipos.

**Destrava:** R-48 (gravar o tipo, ou os tipos, e a fonte); R-49 (cadastro
do tipo, CAP-1, e o alerta no painel, CAP-5); R-50 (a que tipo vai a chave
`autorizacao_funcionamento` na migração, CAP-6).

resposta do físico: (26/10/2026) **Aplicação, na sessão, da regra que o físico fixou** (referência; havendo duas ou mais, a mais restritiva; sem base, a mais conservadora, provisória e levada à discussão no serviço). **A conferir pelo físico.** **Os dois, como tipos separados**: Autorização para Operação da CNEN e alvará sanitário, cada um pela data escrita no próprio documento [SAES-1399-2019 p. 9], art. 16, d). Aviso prévio de 60 dias (cobre os 30 do pedido de renovação [NN-6.02 p. 8]). Discussão: a qual dos dois a chave `autorizacao_funcionamento` do ppr-streamlit pertence.

---

## SEVRRA: periodicidade (V3)

**Pergunta.** Quando uma avaliação SEVRRA vence, e com que fonte?

**Estado hoje.** A CAP-1 trata o SEVRRA como a autorização: "validade do
documento". No `ppr-streamlit`, a chave `sevrra` guarda realização e
vencimento (`app.py:439-443`), lidos do PDF pela mesma extração por IA
externa, e é uma das três seções obrigatórias de PDF
(`app.py:1440`).

**O que a base diz.**

| fato | fonte |
|---|---|
| SEVRRA é o "Sistema de Avaliação de Risco em Radioterapia"; o relatório tem código de verificação, data de finalização, assinatura do SPR e lista de ações para os riscos alto e muito alto | [PPR-CLINICA p. 85], seção 22.1; [p. 101–102], Anexos I e II do relatório |
| O PPR da CEL traz um relatório por equipamento (dois aceleradores e o HDR), todos finalizados em janeiro de 2023; nenhum dos três traz data de validade | [PPR-CLINICA p. 84–138], seção 22; datas de finalização em [p. 101], [p. 120] e [p. 138] |
| O PPR diz que a análise de riscos da prática é feita "através da ferramenta SEVRRA", com os últimos resultados no anexo | [PPR-CLINICA p. 13] |
| A CNEN pede no PPR o planejamento de análise de segurança (análise de risco), "aplicado antes do início da operação do Serviço de Radioterapia e realizado periodicamente", sem dizer o período e sem nomear o SEVRRA | [GUIA-CNEN-RT p. 17], Anexo I, item 14.3 |

A palavra "SEVRRA" não aparece na NN-6.10, na NN-6.02 nem no guia da CNEN.
O relatório SEVRRA que está no PPR não traz data de validade, só a data de
finalização. Que periodicidade vale para refazer a análise, **a base não
responde**; se uma mudança de equipamento ou de técnica obriga a refazer,
também não.

| opção | fonte | o que muda adiante |
|---|---|---|
| a validade escrita no documento, como diz a CAP-1 | CAP-1; spec, Open Questions | o relatório da base não traz validade: o item nasce "sem data" (CAP-1) até o físico ter uma data com fonte, e aparece como `informativo` no painel (CAP-5), nunca em dia |

A base não traz outra opção com fonte. Um intervalo fixo, ou a ligação com a
renovação da autorização (que pede o PPR atualizado [GUIA-CNEN-RT p. 13]),
precisaria de uma fonte que a base não tem.

**Destrava:** R-48 (gravar a fonte, ou registrar que não há); R-49 (o tipo
SEVRRA no cadastro, CAP-1); R-50 (a migração da chave `sevrra`, CAP-6).

resposta do físico: (26/10/2026) **Aplicação, na sessão, da regra que o físico fixou** (referência; havendo duas ou mais, a mais restritiva; sem base, a mais conservadora, provisória e levada à discussão no serviço). **A conferir pelo físico.** **Sem data** (CAP-1): o item aparece como `informativo` e nunca em dia, até haver data com fonte. Discussão: a periodicidade de refazer o SEVRRA (a base não tem) e se mudança de equipamento ou técnica obriga a refazer.

---

## Datas de partida dos itens (V2)

**Pergunta.** De onde vêm as datas de partida (última realização, ou
validade) de cada item da Documentação no dia em que o módulo entra, e quem
as confere?

**Estado hoje.** A spec pede "datas reais de partida dos itens"; no PRD, a
V2 falava dos instrumentos e certificados, que passaram para a GQ, e "a base
só tem modelo e número de série". A CAP-1 faz nascer "sem data" o item sem
data de partida. A CAP-6 importa os JSON do `ppr-streamlit`, e a CAP-8 confere
a migração item a item. Os itens deste módulo são: treinamento de PR,
treinamento de física médica, auditoria externa, levantamento radiométrico,
autorização, SEVRRA, ASO e monitoração individual (CAP-1, CAP-3, CAP-4).

**O que a base diz.**

| fato | fonte |
|---|---|
| O `ppr-streamlit` guarda realização e vencimento de autorização, levantamento radiométrico, auditoria e SEVRRA (e dos certificados, que são da GQ); não tem chave para os dois treinamentos nem para a monitoração mensal | `app.py:439-443` |
| Essas datas vêm do PDF por IA externa e ficam em JSON que o usuário carrega e baixa | `app.py:787-829`; spec, Why |
| A CNEN pede no PPR: o registro de frequência do último treinamento de PR e do de física médica; a periodicidade e o resultado do último levantamento radiométrico; a data do último ASO de cada IOE | [GUIA-CNEN-RT p. 17], Anexo I, itens 20, 22, 23 e 24 |
| No PPR da CEL: o levantamento radiométrico está anexado (seção 30); o treinamento anual de PR é registrado em "Caderno Ata em posse do departamento de Enfermagem"; o ASO de cada IOE está na tabela O.1 | [PPR-CLINICA p. 258], [p. 283], [p. 281–282] |
| O resultado mensal da monitoração individual vem da empresa contratada, com cada remessa de dosímetros e no site dela | [PPR-CLINICA p. 262], Anexo N |
| Os periódicos da NN-6.10 que a CAP-1 usa: treinamento de PR anual (art. 20, VI), treinamento de física médica até 2 anos (art. 24, I, f) | [NN-6.10 p. 6], art. 20, VI; [p. 7], art. 24, I, f) |

As datas atuais de cada clínica não estão na base: o PPR do acervo é de uma
clínica e de março de 2024, e o JSON do `ppr-streamlit` não está nesta
máquina. Quais são as datas reais, **a base não responde**.

| opção | fonte | o que muda adiante |
|---|---|---|
| as datas do JSON do `ppr-streamlit`, importadas pela migração | CAP-6; FR-35; `app.py:439-443` | cobre autorização, levantamento, auditoria e SEVRRA; os treinamentos e a monitoração ficam "sem data" até o lançamento manual; as datas foram extraídas por IA e a CAP-8 já manda conferir cada uma contra o `ppr-streamlit` antes do primeiro uso |
| as datas lançadas pelo físico ou pelo SPR a partir dos documentos de cada clínica (PPR, atas de treinamento, relatório de levantamento, autorização, ASO) | CAP-1; [GUIA-CNEN-RT p. 17]; [PPR-CLINICA p. 258, 281–283] | cada data tem um documento de origem que se pode citar; o trabalho é manual e por clínica; o JSON do `ppr-streamlit` serve só de conferência, e o "nunca gravação dupla" da CAP-6 continua valendo depois do corte |
| entrar com tudo "sem data" e preencher conforme cada item for refeito | CAP-1 ("sem data", nunca em dia) | nada vem de fonte velha, e o painel abre cheio de `informativo` (CAP-5); um item que já está vencido de fato não aparece como `alta` até ganhar uma data |

As opções podem se combinar por tipo (por exemplo, a migração para o que o
`ppr-streamlit` tem e o lançamento para o resto); a escolha por tipo também é
parte da resposta.

**Destrava:** R-48 (gravar a origem das datas por tipo); R-50 (o escopo da
migração e o relatório de importados e não importados, CAP-6 e CAP-8); R-49
(o painel aberto com dados reais em homologação, CAP-5).

resposta do físico: (26/10/2026) **Aplicação, na sessão, da regra que o físico fixou** (referência; havendo duas ou mais, a mais restritiva; sem base, a mais conservadora, provisória e levada à discussão no serviço). **A conferir pelo físico.** **Datas lançadas a partir do documento de origem de cada clínica** (PPR, atas, relatório de levantamento, autorização, ASO), cada uma citando o documento [GUIA-CNEN-RT p. 17]; o JSON do ppr-streamlit serve só de conferência; item sem documento nasce sem data.

---

## Lista de IOEs: de onde vem e quem mantém (V3)

**Pergunta.** De onde o ISOCENTRO tira a lista de IOEs de cada clínica, a
que o ASO (CAP-3) e a monitoração mensal (CAP-4) se ligam, e quem a mantém
em dia?

**Estado hoje.** A spec deixa em aberto: "cadastro de equipe do núcleo ou
PPR". A CAP-3 lista o IOE sem ASO e a CAP-4 faz pendência do mês sem
monitoração: as duas precisam saber quem é IOE. Hoje, no `ppr-streamlit`, a
lista é a soma das tabelas de médicos, físicos, técnicos, dosimetristas,
enfermagem e "Demais IOEs", sem os titulares, e é com ela que ele confere
"IOEs × ASOs" pelo nome (`app.py:1225-1244`). No ISOCENTRO, a equipe de hoje
são duas listas, médicos e físicos, em dois JSON por estação
(`~/.isocentro_medicos.json` e `~/.isocentro_fisicos.json`,
`isocentro/dados/equipe.py`), que a CAP-20 da Fundação migra para o banco.
A espinha põe a equipe com o dono das entidades de referência (AD-26) e diz,
no AD-38, que dado do serviço com duas fontes é o que se quer evitar.

**O que a base diz.**

| fato | fonte |
|---|---|
| IOE é o "indivíduo sujeito à exposição ocupacional" | [NN-3.01 p. 6], art. 6º, LVIII |
| É IOE quem trabalha em área supervisionada ou controlada; quem trabalha em área livre, ou entra nelas só de vez em quando para outra atividade, é público | [NN-3.01 p. 19], arts. 57 e 60 |
| O titular garante o acompanhamento da saúde ocupacional e o treinamento dos IOE, e mantém os registros ocupacionais | [NN-3.01 p. 19], art. 61, IX, XI e XII |
| O PPR traz a "descrição nominal de todos IOEs e suas funções, com informação da carga horária" | [GUIA-CNEN-RT p. 16], Anexo I, item 6 |
| O PPR é elaborado e revisado pelo SPR, e qualquer modificação de dados cadastrais vai à CNEN antes, com novo PPR ou complementação | [NN-6.10 p. 6], art. 20, II; [p. 5], art. 15, XIV |
| Cada trabalhador da instalação radiativa tem registro individual com identificação, funções e áreas, dosímetros, doses mensais e capacitações, guardado por 30 anos após o fim da ocupação | [NR-32 p. 13–14], 32.4.7 |
| No PPR da CEL, a lista de IOE do controle médico é a tabela O.1, nome a nome | [PPR-CLINICA p. 281–282], Anexo O |

Quem é IOE depende de onde a pessoa trabalha (área controlada ou
supervisionada), não do cargo [NN-3.01 p. 19]. Se cada um dos 7 perfis do
ISOCENTRO (o recepcionista, por exemplo) corresponde a IOE, **a base não
responde**. Se a lista do PPR de cada clínica está em dia hoje, também não.

| opção | fonte | o que muda adiante |
|---|---|---|
| o cadastro de equipe do núcleo, com uma marca "IOE" por pessoa e clínica | spec, Open Questions; AD-26; AD-38; Fundação, CAP-20 | uma só fonte da equipe para todos os módulos, como pede o AD-38; o cadastro de hoje só tem médicos e físicos, e teria de ganhar técnicos, dosimetristas, enfermagem e os demais IOE; quem tem o atributo admin mantém o cadastro (Configurações › Equipe, CAP-19), e a marca IOE precisa de alguém que a mantenha; na base, quem elabora o PPR, onde está a lista nominal, é o SPR [NN-6.10 p. 6] |
| a lista nominal do PPR de cada clínica, importada | spec, Open Questions; [GUIA-CNEN-RT p. 16], item 6; [PPR-CLINICA p. 281–282]; `app.py:1225-1244` | a lista é a que a CNEN já recebe; ela muda quando o PPR muda (e o PPR vai à CNEN antes [NN-6.10 p. 5]), então a lista do ISOCENTRO só se atualiza quando alguém importa de novo; é uma segunda fonte de equipe ao lado do cadastro do núcleo, o que o AD-38 quer evitar; no `ppr-streamlit` o casamento é por nome, e a espinha não liga por nome (AD-26) |
| o cadastro de usuários do ISOCENTRO (quem tem login) | Fundação, CAP-2 e CAP-3 | nada novo a manter; IOE sem login (terceirizado, quem não usa o sistema) fica de fora da lista, e usuário que trabalha só em área livre entra nela; a lista de IOE sem ASO (CAP-3) sairia errada nos dois sentidos |

Em qualquer opção, quem mantém a lista é parte da resposta: a spec pergunta
"e quem a mantém", e a base só diz que o PPR é do SPR [NN-6.10 p. 6].

**Destrava:** R-48 (gravar a origem e o responsável); R-49 (ASO por pessoa e
monitoração mensal por IOE, CAP-3 e CAP-4); R-19, se a resposta for o
cadastro do núcleo (a entidade equipe migrada pela CAP-20 ganharia a marca
IOE e os outros cargos); R-50 (a importação dos ASOs e a conferência IOE ×
ASO na migração, CAP-6).

resposta do físico: (26/10/2026) **Aplicação, na sessão, da regra que o físico fixou** (referência; havendo duas ou mais, a mais restritiva; sem base, a mais conservadora, provisória e levada à discussão no serviço). **A conferir pelo físico.** **Cadastro de equipe do núcleo, com marca IOE por pessoa e clínica** (uma só fonte, AD-38), mantida pelo SPR, que elabora o PPR [NN-6.10 p. 6], e conferida contra a lista nominal do PPR a cada revisão dele [GUIA-CNEN-RT p. 16]. IOE é quem trabalha em área controlada ou supervisionada, não o cargo [NN-3.01 p. 19]. Discussão: quem, em cada perfil, é IOE.
