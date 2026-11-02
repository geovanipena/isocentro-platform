---
title: 'Pesquisa acadêmica: conferência das referências do brief SGQ-RT v0.5'
type: academic-lit
topic: 'Conferência das referências e números do brief técnico SGQ-RT v0.5'
decision: 'Quais números e fontes do brief SGQ-RT entram como fato no brief e no PRD do sistema global'
source: 'import: imports/sgq-rt-brief-v5.html (brief do autor, v0.5), verificado contra fonte primária em 3 frentes'
status: complete
preset: standard
validation: 'reforçada: todos os números listados pelo usuário tratados como load-bearing'
created: '2026-10-13'
updated: '2026-10-13'
claims: '20 entradas no ledger: 15 verified, 1 disputed, 3 overturned, 1 unverified (o recon_kit tally junta refs com sufixo, ex. [7]/[7b], e conta 14)'
---

# Conferência das referências do brief SGQ-RT v0.5

**Decisão que esta pesquisa atende:** quais números e fontes do brief SGQ-RT
podem entrar como fato no brief do produto e no PRD do sistema global.

Decisões já tomadas pelo usuário, fora do escopo desta pesquisa: o motor é
só advisory, nunca bloqueante; o núcleo é em Python, com ESAPI na fronteira.

## Resumo executivo

O brief se sustenta. Todas as 29 referências que foram checadas existem e
quase todos os números estão na fonte. Mas **quatro afirmações precisam ser
corrigidas antes do PRD**, e uma condição regulatória que o brief não
menciona muda a decisão de "ambição regulatória".

1. **Corrigir quatro números.**
   - Os 31,8% de Riegel valem para alguns modos de falha, não para a
     revisão física em geral [1].
   - "151 itens" do TG-275 é contagem do survey [3].
   - "69 de 71 mais viáveis" foi só reavaliado [4].
   - "Quatro para cinco sigma" vale apenas para o shift de isocentro [5].
2. **Separar a ref [6] em dois artigos.** O estudo longitudinal de 1169
   planos (Stuhr et al. 2022 [6]) não mede tempo. Os −20% e o ≈½ FTE são de
   Berry et al. 2020 [7], e o ½ FTE é uma estimativa.
3. **A dispensa de registro da RDC 657/2022 tem condições.** Ela vale só para
   SaMD in house das **classes de risco I e II**, sem interferir em
   dispositivo regularizado e sem comercializar nem doar. Exige registro
   completo da validação, guardado por 10 anos após o descarte [11].
   - A "biblioteca de regras citável" (inovação V) pode ser adotada por
     outro serviço. Mas o **software** não pode ser doado sem
     regularização.
   - O plan check precisa de classe de risco ANVISA decidida, além da classe
     IEC 62304.

**Maior ressalva:** o argumento do brief contra o comercial e a tabela
"A lacuna" não têm fonte. São afirmações do autor e foram marcadas assim; não
foram verificadas.

## Número a número

### Fatos da seção 01

| Brief v0.5 | Situação | Redação corrigida para o PRD | Fonte |
| --- | --- | --- | --- |
| 31,8% de detecção pela revisão física | **disputada (escopo)** | Em incidentes ROILS mapeados contra os modos de falha do TG-275, a checagem inicial do físico detectou de 31,3% a 87,5% conforme o modo de falha; 31,8% em "plano subótimo" | Riegel 2022 [1] |
| "outro estudo, 38%" | verificada | A revisão física detectou 38% dos eventos que poderia detectar | Gopan 2016 [2] |
| 102–163 min / 29–56 min, 8 físicos | verificada | Igual. Uma instituição só; a variação foi entre físicos, não entre sítios | Xu 2021 [4] |
| 151 itens / 112 modos de falha / +55 / 48 HDR | **151 derrubado**, demais verificados | O TG-275 traz 112 modos de falha de alto risco na revisão inicial de EBRT fóton/elétron, 55 na semanal/fim de tratamento, 24 em prótons e 48 em HDR | Ford 2020 [3] |
| 44–98% de tempo; 15–85% de erro residual | verificada | Igual | Xu 2021 [4] |
| 69 de 71 "mais viáveis" | **derrubado** | Os 69 itens que o TG-275 julgou não totalmente automatizáveis foram reavaliados; dos 60 que a Tab. 3 mostra, 35 ficaram totalmente automatizáveis e 2 não | Xu 2021 [4] |
| 16,1%→4,1%; RPN 129,2→83,7; −82,7%; −84,4% | verificada | Igual. Autores: Liu et al., Stanford | Liu 2019 [5] |
| "de quatro para cinco sigma" | **derrubado** | Só os erros de shift de isocentro foram de 4σ para 5σ; a divergência prescrição/plano ficou em 4σ | Liu 2019 [5] |
| ≈½ FTE, ~20%, 3 anos, 1169 planos, 11 checagens | **disputada (fusão)** | Berry et al. mediram −20% no tempo de chart check e estimaram ≈½ FTE [7]. Stuhr et al. acompanharam 11 checagens em 1169 planos por ~3 anos, sem medir tempo [6] | [6], [7] |
| Advertência do TG-275 sobre ferramenta mal testada | verificada (redação) | Ferramenta mal implementada ou testada pode fazer erros **passarem sistematicamente sem ser identificados**. O MPPG 11.a pede validação rigorosa contra erro sistemático | [3], [8] |
| Falsos negativos por nomenclatura | verificada | Stuhr et al. separam falso negativo por convenção de nomenclatura | [6] |

### Referências sem autor no brief (completadas)

- **[7] do brief** → Liu S, Bush KK, Bertini J, …, Kovalchuk N. JACMP
  2019;20(8):56–64 [5].
- **[11] do brief** → Huang P, Shang J, Xu Y, Hu Z, Zhang K, Dai J, Yan H.
  Front Oncol 2023;13:1142947 [9]. 576 planos de mama, AUC 0,9985, recall
  100%, precisão 0,51: verificado. São 19 planos anômalos, de um único grupo:
  é pista, não fato replicado.
- **[8]–[10] do brief** (Kalet 2015, Luk 2019, Chang 2019) existem como
  citados [10]. Chang fala em "erro de ordem médica", não em erro de
  prescrição.

### Task groups e normas

- **MPPG 11.a e TG-315** são o mesmo trabalho: o TG-315 escreveu o MPPG
  11.a. É um mínimo, não inclui todo o TG-275 e distribui checagens a
  dosimetrista e técnico [8].
- **TG-201 (Siochi 2021).** O relatório completo foi confirmado [12]. As
  recomendações de teste ponta-a-ponta e checksum só foram lidas na
  comunicação rápida de 2010 [13]. Para citar essa redação ao relatório de
  2021, é preciso ler o texto completo.
- **CNEN NN 6.10** vigente, na redação da Res. 277/2021 [14].
  - Art. 35: teste diário do fator de calibração **para aceleradores
    lineares**; dose absorvida mensal **para fontes de teleterapia**.
  - Art. 36: auditoria externa e independente com frequência máxima de 2
    anos.
- **RDC ANVISA 20/2006** vigente [15]. O item 6.9 pede avaliação externa a
  cada **4 anos**: duas periodicidades vigentes para obrigações parecidas.
- **PQRT/INCA** ativo, desde julho de 1999, com avaliações locais e postais
  [16]. O TLD aparece em RBFM 2009 [17]; a página atual fala em "sistemas
  postais".
- **GT 2302 da ABFM:** Giglioli et al., RBFM 2023;17:746 [18]. Foi feito a
  pedido da CNEN para detalhar o Art. 36 e tem a seção 3.3.6, "Teste
  end-to-end". É documento técnico, não normativo. A CNEN tem ainda um guia
  de relatório de auditoria externa, de nov/2023 [19].
- **RDC 657/2022** [11], [20]: ver o item 3 do resumo. Está vigente pelo
  Anvisa Legis. Uma revisão estaria na agenda regulatória 2026–27, mas só por
  fonte secundária [21] (*unverified*).

## O que só a combinação mostra

- **A inovação III é a resposta ao achado mais repetido.** O TG-275 adverte
  sobre erro que passa sem ser visto [3]. O MPPG 11.a pede validação contra
  erro sistemático [8]. Stuhr et al. observaram falso negativo por
  nomenclatura em produção [6]. A RDC 657 exige evidência de "capacidade de
  discernir registros inválidos ou alterados" [11]. A sensibilidade medida
  por erro semeado atende os quatro com o mesmo dado: é o registro de
  validação que a RDC 657 pede.
- **A auditoria espelhada (inovação I) tem dois relógios.** A NN 6.10 pede
  auditoria externa a cada 2 anos [14] e a RDC 20/2006, avaliação externa a
  cada 4 [15]. O roteiro técnico de referência é o GT 2302 [18]. O gatilho de
  calendário precisa das duas periodicidades, cada uma com a sua fonte.
- **A ambição regulatória e a classe de risco são a mesma decisão.** A
  dispensa da RDC 657 depende da classe ANVISA (I ou II) [11]. Se o plan
  check for classe III, o regime in house deixa de valer, mesmo para uso
  interno. Esta pesquisa não classificou: isso é decisão do físico.

## Recomendações

| # | Recomendação | Alimenta | Base |
| --- | --- | --- | --- |
| R1 | Usar a coluna "Redação corrigida" acima no lugar dos números do v0.5 | Brief do sistema global, seção de problema | alta: fontes primárias lidas |
| R2 | Citar [6] e [7] como dois artigos; apresentar ½ FTE como estimativa | Brief e PRD | alta |
| R3 | Registrar em `docs/qms/` as condições do art. 5º da RDC 657 e a retenção de 10 anos após o descarte; pedir ao físico a classe de risco ANVISA de cada módulo, ao lado da classe 62304 | `docs/qms/classificacao-62304.md`, PRD (requisito de retenção do log) | alta |
| R4 | Na inovação V, deixar escrito que se publica a biblioteca de regras, não o software (§1º do art. 5º) | Brief, seção de diferencial | alta |
| R5 | Gatilho de calendário com NN 6.10 (2 anos) e RDC 20/2006 (4 anos) como fontes distintas; roteiro de testes do GT 2302 | PRD, Fase 4 | alta |
| R6 | Não usar o autoencoder (Huang 2023) como meta de desempenho; só como evidência de viabilidade | PRD, Fase 6 | média: grupo único, 19 positivos |
| R7 | Antes de citar o TG-201 de 2021 para ponta-a-ponta e checksum, ler o texto completo ou citar a comunicação de 2010 | Arquitetura (log, integridade) | alta (2010) / pendente (2021) |

## Perguntas em aberto

- **Classe de risco ANVISA de cada módulo (I a IV).** É decisão do físico; a
  regra de classificação vem da RDC 751/2022, que esta pesquisa não leu.
- **RDC 751/2022 e 830/2023 alteram a 657?** Não verificado. O caminho é
  consultar o Anvisa Legis por alterações.
- **Follow-up de Liu et al. (16,1%→2,3% em 5946 planos).** Visto só num
  trecho do ResearchGate. Uma busca dirigida no PubMed resolve.
- **Tabela "A lacuna" (comercial × in-house × SGQ-RT).** Sem fonte no brief.
  Uma pesquisa `competitive` resolveria, se ela for entrar no PRD.

## Fontes

| # | Afirmação que sustenta | Publicador | Pub. | Acesso | Confiança |
| --- | --- | --- | --- | --- | --- |
| 1 | 31,3–87,5% por modo de falha; 31,8% em plano subótimo | [Riegel AC et al., JACMP 23(6):e13640](https://pmc.ncbi.nlm.nih.gov/articles/PMC9194987/) | 2022-05 | 2026-10-13 | alta |
| 2 | 38% de detecção pela revisão física | Gopan O et al., Med Phys 43(9):5181–7 (via [1]) | 2016-09 | 2026-10-13 | média |
| 3 | Modos de falha 112/55/24/48; 151 é survey; advertência sobre automação | [Ford E et al., AAPM TG-275, Med Phys 47(6):e236–72](https://pmc.ncbi.nlm.nih.gov/articles/PMC9012523/) | 2020-06 | 2026-10-13 | alta |
| 4 | 102–163 e 29–56 min; −44–98%; −15–85%; reavaliação dos 69 itens | [Xu H et al., JACMP 22(3):234–45](https://pmc.ncbi.nlm.nih.gov/articles/PMC7984492/) | 2021-03 | 2026-10-13 | alta |
| 5 | APC Six Sigma: 16,1%→4,1%, RPN, −82,7%, −84,4%, sigma só no shift | [Liu S et al., JACMP 20(8):56–64](https://pmc.ncbi.nlm.nih.gov/articles/PMC6698761/) | 2019-08 | 2026-10-13 | alta |
| 6 | 11 checagens, 1169 planos, ~3 anos, falso negativo por nomenclatura | [Stuhr D … Berry SL, Pract Radiat Oncol 12(2):163–9](https://pubmed.ncbi.nlm.nih.gov/34670137/) | 2021-10 | 2026-10-13 | alta |
| 7 | −20% no tempo de chart check; ≈½ FTE estimado | [Berry SL et al., JACMP 21(4):51–8](https://pmc.ncbi.nlm.nih.gov/articles/PMC7170286/) | 2020-03 | 2026-10-13 | alta |
| 8 | MPPG 11.a = TG-315; mínimo e papéis; validar ferramenta | [Xia P et al., JACMP 22(9):4–19](https://pmc.ncbi.nlm.nih.gov/articles/PMC8425907/) | 2021-09 | 2026-10-13 | alta |
| 9 | Autoencoder: 576 planos de mama, AUC 0,9985 | [Huang P et al., Front Oncol 13:1142947](https://pmc.ncbi.nlm.nih.gov/articles/PMC10043249/) | 2023-03 | 2026-10-13 | alta (grupo único) |
| 10 | Kalet 2015, Luk 2019 e Chang 2019 existem | [PubMed 25768885](https://pubmed.ncbi.nlm.nih.gov/25768885/), [30927253](https://pubmed.ncbi.nlm.nih.gov/30927253/), [31158426](https://pubmed.ncbi.nlm.nih.gov/31158426/) | 2015–2019 | 2026-10-13 | alta |
| 11 | RDC 657 art. 5º: classes I/II, sem doar, registro de validação, 10 anos após o descarte | [DOU, RDC ANVISA 657/2022](https://www.in.gov.br/en/web/dou/-/resolucao-de-diretoria-colegiada-rdc-n-657-de-24-de-marco-de-2022-389603457) | 2022-03 | 2026-10-13 | alta |
| 12 | Siochi 2021 = relatório do TG-201 | [Siochi RA et al., Med Phys 48(6):e86–e114](https://doi.org/10.1002/mp.14868) | 2021-04 | 2026-10-13 | alta (só resumo) |
| 13 | TG-201: teste ponta-a-ponta e checksum | [Siochi RA et al., JACMP 12(1):170–81](https://pmc.ncbi.nlm.nih.gov/articles/PMC5718574/) | 2010-12 | 2026-10-13 | alta |
| 14 | NN 6.10 arts. 35–36, vigente | [CNEN NN 6.10 consolidada](https://www.gov.br/cnen/pt-br/acesso-rapido/normas/grupo-6/ansn-6-10-requisitos-de-seguranca-e-protecao-radiologica-para-servicos-de-radioterapia.pdf) | 2021-08 | 2026-10-13 | alta |
| 15 | RDC 20/2006 vigente; 6.9 avaliação a cada 4 anos | [normasbrasil, RDC 20/2006](https://www.normasbrasil.com.br/norma/resolucao-20-2006_104087.html) + Anvisa Legis | 2006-02 | 2026-10-13 | alta |
| 16 | PQRT desde 1999, local e postal, ativo | [INCA, PQRT](https://www.gov.br/inca/pt-br/assuntos/gestor-e-profissional-de-saude/programa-de-qualidade-em-radioterapia) | 2025-08 | 2026-10-13 | alta |
| 17 | PQRT com TLD | [Souza, Araujo, Viegas, RBFM 2(1):28–9](https://rbfm.emnuvens.com.br/rbfm/article/download/24/v2n1p28/82) | 2009 | 2026-10-13 | média |
| 18 | GT 2302: auditoria externa, §3.3.6 end-to-end | [Giglioli M et al., RBFM 17:746](https://rbfm.emnuvens.com.br/rbfm/article/download/746/651/3887) | 2023 | 2026-10-13 | alta |
| 19 | Guia CNEN de relatório de auditoria externa | [CNEN, Guia v1.0](https://appasp2019.cnen.gov.br/seguranca/orientacoes/images/cnen/documentos/drs/orientacoes/Guia-para-elaboracao-de-Relatorio-de-Auditoria-Externa-e-independente-em-Instalacoes-de-Radioterapia.pdf) | 2023-11 | 2026-10-13 | média |
| 20 | Q&A da RDC 657: in house, rede assistencial, pacientes do serviço | [Anvisa, Perguntas e respostas RDC 657 v1](https://www.gov.br/anvisa/pt-br/assuntos/noticias-anvisa/2022/software-como-dispositivo-medico-perguntas-e-respostas/perguntas-respostas-rdc-657-de-2022-v1-01-09-2022.pdf/@@download/file) | 2022-09 | 2026-10-13 | alta |
| 21 | Revisão da RDC 657 na agenda 2026–27 | [Emergo by UL (secundária)](https://www.emergobyul.com/news/brazil-anvisa-announces-priorities-2026-2027-year) | 2026 | 2026-10-13 | baixa |

## Validade

Calculado com `recon_kit.py staleness`, janelas em meses: vigência de norma
12, revisão normativa em curso 6, estado da arte 12, achado empírico
fundante e task group 120.

| Afirmação | Reconferir em | Vencida |
| --- | --- | --- |
| Liu 2019 como resultado de referência (há follow-up 16,1%→2,3%) | 2020-08-19 | sim |
| Autoencoder (Huang 2023) como estado da arte | 2024-03-14 | sim |
| PQRT/INCA ativo | 2026-08-14 | sim (página de 08/2025) |
| CNEN NN 6.10 vigente | 2027-01-26 | não |
| RDC 657 em revisão (agenda 2026–27) | 2027-04-13 | não |
| RDC 657 e RDC 20/2006 vigentes | 2027-10-13 | não |
| TG-275 | 2030-06-01 | não |
| Xu 2021 | 2031-03-11 | não |

O primeiro a reconferir já venceu: os resultados de detecção automática
(Liu 2019, Huang 2023) são de 2019–2023, e a área anda rápido. Antes do PRD
da Fase 3 (plan check), vale um Deepen nessas duas linhas. O Refresh e o
Deepen deste skill cuidam disso.
