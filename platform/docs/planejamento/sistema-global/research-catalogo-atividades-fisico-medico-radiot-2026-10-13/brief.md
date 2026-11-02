---
topic: Catálogo de atividades do físico médico em radioterapia no Brasil
type: domain
decision: Construir o catálogo que é a espinha e o denominador de cobertura do SGQ-RT
status: aguardando relatório externo
created: '2026-10-13'
---

# Prompt de pesquisa (colar na ferramenta de deep research)

```text
PAPEL E OBJETIVO
Você é um pesquisador de regulação e de prática profissional em física médica.
Quero um CATÁLOGO COMPLETO DAS ATIVIDADES DO FÍSICO MÉDICO EM UM SERVIÇO DE
RADIOTERAPIA NO BRASIL. Cada atividade deve vir ligada à sua base normativa
ou de recomendação, à periodicidade, ao responsável, à evidência que gera e
ao tempo de guarda dessa evidência.

O catálogo será a espinha de um sistema interno de gestão da qualidade. Uma
linha que falta é uma obrigação que o sistema não vai cobrar. Por isso
COMPLETUDE e FONTE valem mais que prosa.

Contexto do serviço: teleterapia com aceleradores lineares Varian (ARIA e
Eclipse), TC de simulação, IGRT, técnicas 3D, IMRT e VMAT, possivelmente
SBRT. Braquiterapia HDR: pesquise como área condicional. IORT está FORA do
escopo.

REGRAS DE EVIDÊNCIA (inegociáveis)
1. Toda afirmação traz a URL da fonte, a data de publicação e o item exato
   (artigo, inciso, seção ou tabela). Sem fonte, não entra; se entrar, vai
   marcada como "NÃO VERIFICADO".
2. Prefira fonte primária:
   - in.gov.br (DOU), gov.br/cnen, gov.br/anvisa, Anvisa Legis, Saúde Legis;
   - aapm.org e as revistas Medical Physics e JACMP;
   - iaea.org, estro.org, icru.org;
   - pubmed.ncbi.nlm.nih.gov e docs.developer.varian.com.
   Blog, curso ou apresentação de terceiros não valem como fonte de obrigação.
3. Para CADA norma brasileira citada, confirme se está VIGENTE em 2026:
   revogação, alteração ou substituição. Diga onde conferiu e quando.
   Aponte também as revisões em andamento: consulta pública, agenda
   regulatória, minuta.
4. Obrigação regulatória e prazo legal precisam de DUAS fontes
   independentes (por exemplo, o texto no DOU e a página do órgão). Se só
   houver uma, diga.
5. Diferencie sempre três níveis:
   - OBRIGATÓRIO-BR: lei, norma CNEN, RDC ANVISA, NR, resolução de conselho;
   - RECOMENDAÇÃO: AAPM TG/MPPG, IAEA TRS/TECDOC/SSG, ESTRO/ACROP, ICRU,
     NCRP, ABFM;
   - BOA PRÁTICA: literatura sem caráter normativo.
6. Quando duas fontes conflitarem em periodicidade, tolerância ou
   responsável, registre o CONFLITO com as duas citações. Não escolha uma.
7. Não copie valores de tolerância: aponte a tabela onde estão (por exemplo,
   "TG-142 Tab. II").
8. Admita lacunas. "Não encontrei fonte para X" é um resultado válido.

ÁREAS (pesquise todas; as listas são PONTOS DE PARTIDA a verificar, não
fatos — confirme existência, número, ano e vigência de cada documento)

A. EQUIPAMENTO
   Aceitação, comissionamento e dados de feixe; calibração absoluta e
   protocolo adotado; CQ diário, mensal e anual de acelerador, MLC, mesa,
   imagem e IGRT; TC de simulação; lasers; dosímetros, eletrômetros e
   fantomas, com calibração rastreável (IRD/LNMRI) e periodicidade.
   Candidatos: CNEN NN 6.10; AAPM TG-142, TG-198, TG-106, TG-51 e
   adendo, TG-179, TG-66, MPPG 8; IAEA TRS-398 (verificar revisão recente)
   e TRS-483.

B. SISTEMAS E SOFTWARE
   Comissionamento e CQ do TPS; atualização de versão do TPS e do R&V;
   transferência de dados e integridade; backup; validação de software
   desenvolvido no próprio serviço; segurança da informação e LGPD.
   Candidatos: IAEA TRS-430 e TECDOC-1540/1583; AAPM MPPG 5, TG-53,
   TG-201, TG-262; RDC ANVISA 657/2022 e normas correlatas de software
   como dispositivo médico; Lei 13.709/2018.

C. PACIENTE: PLANEJAMENTO
   Simulação e imobilização; nomenclatura de estruturas; restrições de dose
   adotadas; checagem inicial de plano e prontuário; cálculo independente
   de UM ou dose; QA específico de IMRT e VMAT; SBRT e SRS; registro de
   imagens; pacientes especiais (gestante, marca-passo/CDI, prótese,
   reirradiação).
   Candidatos: AAPM TG-263, TG-275, MPPG 11.a (TG-315), TG-114, TG-219,
   TG-218, TG-119, TG-101, MPPG 9, TG-132, TG-36, TG-203; ICRU 50, 62, 83
   e 91.

D. PACIENTE: TRATAMENTO E ACOMPANHAMENTO
   Primeira sessão; revisão semanal de prontuário; verificação de imagem;
   dosimetria in vivo; alteração de plano em curso; interrupções;
   revisão de fim de tratamento; registro da dose entregue.
   Candidatos: AAPM TG-275, MPPG 11.a; RDC ANVISA 20/2006.

E. BRAQUITERAPIA HDR (condicional)
   Aceitação; troca e calibração de fonte; teste de fuga; CQ diário e
   periódico; cálculo e verificação de plano; segurança e emergência;
   inventário e devolução de fonte.
   Candidatos: CNEN NN 6.10; AAPM TG-43, TG-56, TG-59, TG-40; ICRU 89;
   ESTRO/GEC recommendations.

F. PROTEÇÃO RADIOLÓGICA E LICENCIAMENTO
   Plano de proteção radiológica e sua revisão; supervisor de proteção
   radiológica (certificação e atribuições); licenciamento junto à CNEN
   (construção, operação, modificação, renovação); projeto e cálculo de
   blindagem; levantamento radiométrico; monitoração individual
   (laboratório credenciado, periodicidade, guarda); monitoração de área;
   exames médicos ocupacionais; treinamento periódico; inventário de
   fontes; rejeitos e transporte; plano de emergência e comunicação de
   eventos à CNEN, com prazos; relatórios periódicos exigidos pela CNEN.
   Candidatos: CNEN NN 3.01, NN 3.02, NN 6.10, NN 7.01, NN 8.01, NN 5.01;
   NR-32 e NR-7; NCRP 151; IAEA SSG-46 e GSR Part 3.

G. GESTÃO DA QUALIDADE, SEGURANÇA DO PACIENTE E DOCUMENTAÇÃO
   Programa de garantia da qualidade e POPs controlados; responsável
   técnico; avaliação externa e auditorias (PQRT/INCA, IAEA/IROC, CNEN
   art. 36); notificação de eventos adversos (Notivisa, prazos); análise
   de incidentes e FMEA; indicadores; competência, treinamento e
   educação continuada; dimensionamento de físicos por carga de trabalho;
   alvará e licença sanitária; contratos de manutenção; guarda de
   prontuário e de registros de CQ (tempo mínimo e fundamento legal).
   Candidatos: RDC ANVISA 20/2006, 63/2011, 36/2013; Lei 13.787/2018 e
   resoluções CFM sobre prontuário; AAPM TG-100; IAEA QUATRO e documentos
   de dimensionamento de pessoal; ASTRO "Safety is No Accident"; ESTRO
   e EFOMP sobre dimensionamento; ABFM.

H. FERRAMENTAS DE ROTINA (não normativas)
   Que tarefas recorrentes do físico consomem mais tempo segundo estudos
   de carga de trabalho? Que cálculos e checagens rápidas são rotina:
   UM, decaimento, BED/EQD2, gap entre campos, compensação de
   interrupção? Que ferramentas abertas são usadas para CQ e checagem?
   Exemplos a verificar: pylinac, QATrack+, scripts ESAPI.

PERGUNTAS TRANSVERSAIS
1. Quem é legalmente responsável por cada atividade? Distinga titular da
   instalação, supervisor de proteção radiológica, físico médico
   responsável, responsável técnico médico, dosimetrista e técnico.
   O que só o físico pode assinar?
2. O que a CNEN e a vigilância sanitária efetivamente cobram em
   inspeção? Busque roteiros de inspeção, relatórios, autos de infração e
   não conformidades publicados.
3. Que mudanças regulatórias estão em andamento ou previstas para
   2026–2027 (CNEN, ANVISA)?
4. Glossário: os termos que o físico usa nas normas brasileiras e o
   equivalente nas recomendações internacionais.

FORMATO DA RESPOSTA (siga exatamente)
1. Resumo de uma página: quantas atividades por área, as dez obrigações
   com maior risco de esquecimento, conflitos entre normas e lacunas.
2. TABELA-CATÁLOGO, uma linha por atividade, com as colunas:
   id | área (A–H) | atividade | gatilho ou periodicidade | nível
   (OBRIGATÓRIO-BR / RECOMENDAÇÃO / BOA PRÁTICA) | documento e item exato |
   quem executa | quem assina/aprova | evidência ou registro gerado |
   guarda mínima e fundamento | órgão que fiscaliza | URL | data da fonte |
   vigência conferida (sim/não + data da conferência) | conflito/observação
3. Tabela de CONFLITOS entre fontes.
4. Tabela de DOCUMENTOS: título, número, ano, órgão, URL, vigência,
   revisão em andamento.
5. Glossário.
6. Lacunas: o que não foi encontrado e onde seria preciso procurar.
7. Lista numerada de fontes com URL e data de publicação.
```

Ao terminar, salve o relatório (PDF, Markdown ou texto) e diga "processa o
relatório": ele vai para `imports/` desta pasta.
