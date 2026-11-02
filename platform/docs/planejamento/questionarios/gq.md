# Questionário do físico — módulo Garantia da Qualidade

> **Rascunho da IA: nada aqui é decisão.** As opções abaixo são as que a spec
> do GQ e a base de conhecimento já levantam, cada uma com a fonte; nenhuma
> é recomendada. Quem decide é o físico responsável, na frente R-37, e a
> resposta vai para o memlog da spec (e as linhas de risco para o
> `docs/qms/riscos.md`) pelas mãos dele, não por este arquivo.

Frente R-72 (robô, 23/10/2026), que prepara a R-37. Spec:
`docs/planejamento/sistema-global/spec-isocentro-qualidade/SPEC.md` (Open
Questions). A numeração C2, C5, C6, C7 é a do PRD, §15.

**Como ler as fontes.** `[CÓDIGO p. N]` é o documento do acervo
(`conhecimento/matriz/fontes.csv`) e a página do texto integral em
`conhecimento/texto/`, conferida nesta sessão. `CAP-n` é da spec do GQ,
`FR-n` do PRD (`prd-isocentro-2026-10-16/prd.md`) e `AD-n` da espinha
(`architecture-isocentro-2026-10-19/ARCHITECTURE-SPINE.md`). O que vem de uma
ficha da base (`conhecimento/fichas/…`) ou do `PENDENCIAS.md` está citado
pelo arquivo, porque a ficha resume e não é o texto do documento. Onde a base
não tem o que dizer, está escrito "a base não responde" e não há opção
inventada.

Ordem: as duas que pesam no cálculo da calibração primeiro (classe e k_Q,
que travam a R-40), depois as da carga do programa (C2, sombra, Dermopan, na
R-39) e a retenção (R-43).

Fora deste questionário, embora a R-37 os peça: as linhas do GQ no
`riscos.md` (S, O, D são do físico) e a correção B1 na base (`fff` no
TrueBeam, HDR no `programa-cq.csv`), que é tarefa e não pergunta.

---

## Classe do cálculo TRS-398 (G1 no GQ)

**Pergunta.** O cálculo da calibração TRS-398 (CAP-7) fica na classe B
provisória do módulo GQ ou sobe ao rigor da classe C?

**Estado hoje.** O AD-35 põe núcleo, `rt`, Plano e Radioteraficha no rigor da
classe C e os "demais módulos" em classe B `[ASSUMPTION]` até o `riscos.md`.
A spec do GQ repete a classe B e deixa ao físico subir o cálculo (Constraints,
"Classe"; Assumptions), porque a calibração calculada define a dose de todos
os pacientes daquela máquina (Open Questions; FR-45). O AD-39 diz outra
coisa: cada **módulo** é um item de software IEC 62304, a classe
vem do `classificacao-62304.md` assinado pelo físico, e "módulo sem classe
atribuída vale rigor C". O `classificacao-62304.md` não classifica o GQ
(PRD §12.1). Qual dos dois ADs vale para o GQ enquanto a classe não é
atribuída também é parte da pergunta.

**O que a norma diz** [IEC-62304 p. 10]:

- classe B: o software contribui para risco inaceitável, depois das medidas
  de controle externas a ele, cujo dano possível é lesão **não grave**;
- classe C: idem, com dano possível **morte ou lesão grave**;
- o fabricante pode rebaixar a classe acrescentando medidas de controle de
  risco **externas** ao software (hardware, software independente,
  procedimento); a nota 1 dá esses exemplos;
- a classificação vale por item de software (a emenda troca "SOFTWARE SYSTEM"
  por "SOFTWARE ITEM" no item d), e, num grupo de itens, vale o processo do
  item de classe mais alta, salvo justificativa escrita no arquivo de
  gerenciamento de risco (item f).

| opção | fonte | o que muda adiante |
|---|---|---|
| o módulo inteiro, cálculo incluído, em classe B | AD-35; spec GQ, Constraints e Assumptions | a R-40 é construída no rigor B; o cálculo convive com o resto do GQ sem segregação a justificar; a classe B precisa ser escrita no `classificacao-62304.md`, senão o AD-39 põe o módulo em C |
| só o cálculo TRS-398 (CAP-7) em classe C, o resto do GQ em B | spec GQ, Constraints ("o físico decide se o cálculo TRS-398 (CAP-7) sobe ao rigor C"); [IEC-62304 p. 10], classe por item | o cálculo vira item de software próprio, no rigor C. Pelo AD-39 a unidade de classe é o módulo: ou o cálculo sai para um módulo próprio, ou o AD-39 é editado. Dentro de um mesmo grupo, a norma pede duas coisas separadas: identificar a segregação e dizer como se garante que ela é efetiva [IEC-62304 p. 13], 5.3.5 (exigência de classe C), e, para usar classe menor que a do item mais alto do grupo, uma justificativa escrita no arquivo de gerenciamento de risco [IEC-62304 p. 10], item f |
| o módulo GQ inteiro em classe C | [IEC-62304 p. 10], item f; AD-39 (módulo sem classe atribuída vale C) | a R-39 a R-43 seguem o rigor C; o `classificacao-62304.md` registra C para o GQ, e a spec do GQ (Constraints, Assumptions) deixa de dizer B |

Se o cálculo conta com medida externa que o rebaixe é parte da pergunta. A
spec já registra duas que dependem do físico: o cálculo reproduz a planilha
atual do serviço antes de dar veredito (CAP-7) e `nao_conforme` não bloqueia
nada, a decisão de parar a máquina é dele (Constraints, "Advisory"). A norma
brasileira exige auditoria externa e independente dos parâmetros físicos a
cada dois anos no máximo [NN-6.10 p. 9], art. 36. Se alguma delas conta como
medida de controle externa no sentido da IEC 62304, a base não responde.

**Destrava:** R-40 (rigor da construção e do comissionamento do cálculo) e o
rigor do relatório de validação da R-43 (CAP-13). A G1 do Plano (questionário
`plano.md`) é a mesma pergunta para outro módulo; a resposta de uma não
decide a outra.

resposta do físico: (26/10/2026, Geova, em sessão) **Só o cálculo TRS-398
em classe C; o resto do GQ em classe A** (como o Plano). Razão discutida na
sessão: o erro de calibração atinge todos os pacientes da máquina e passa
pelas conferências de plano, e as medidas externas do GQ (planilha atual,
advisory, auditoria bienal) não o pegam a tempo. O cálculo sai como item
próprio, sem tela e puro (ex.: `rt/calibracao`), para a classe valer por
módulo (AD-39) sem justificar segregação dentro do GQ.

---

## C5 — k_Q e N_D,w × ICRU 90

**Pergunta.** Com que conjunto de k_Q (TRS-398 de 2000 ou Rev. 1) e com que
certificado de N_D,w (anterior ou posterior à adoção do ICRU 90 pelo
laboratório) o ISOCENTRO calcula a dose de referência?

**O que a base diz.**

| fato | fonte |
|---|---|
| Os dados-chave do ICRU 90 foram endossados pelo CCRI e **implementados nos laboratórios** de calibração; o impacto nas calibrações varia com a modalidade | [TRS-398-R1 p. 20], 1.2.1 (c) |
| A mudança chega a ~1% nos padrões de kerma no ar (kV e Co-60); no padrão ionométrico de dose na água do BIPM em Co-60 é praticamente nula; pequena na calorimetria de grafite; nenhuma na de água | [TRS-398-R1 p. 19] |
| Os k_Q da Rev. 1 "não diferem substancialmente" dos da 1ª edição, em geral dentro das incertezas declaradas lá; a revisão existe para manter a consistência com os dados dos padrões | [TRS-398-R1 p. 19] |
| Tabela 16 da Rev. 1: k_Q de câmaras cilíndricas em fótons (inclui IBA FC65-G, IBA FC65-P e PTW 30013, as câmaras de referência do PPR) | [TRS-398-R1 p. 102–104] |
| O certificado da METROBRAS anexado ao PPR da BET (jul/2026) diz que a câmara foi posicionada "segundo recomendações do protocolo IAEA TRS-398 (2000)"; misturar N_D,w antigo com k_Q novo gera inconsistência | ficha `fichas/referencias/TRS-398-R1.md`, ponto de atenção 1 |
| O `pylinac` (`calibration/trs398.py`) usa a Tabela 6.III de 2000; para a PTW 30013 os k_Q dele ficam 0,24% (TPR 0,68) e 0,48% (TPR 0,74) acima da Rev. 1, e ele não tem k_Q de fótons para FC65-G nem FC65-P | ficha `fichas/referencias/TRS-398-R1.md`, ponto de atenção 2 |
| Pendência aberta: perguntar à METROBRAS se o N_D,w já incorpora o ICRU 90, antes de adotar os k_Q da Rev. 1 (todas as clínicas) | `conhecimento/PENDENCIAS.md`, pendência 6 |

Se o certificado em uso já incorpora o ICRU 90 é pergunta da pendência 6, ao
laboratório: a base não responde.

| opção | fonte | o que muda adiante |
|---|---|---|
| k_Q da Rev. 1 (Tab. 16) com N_D,w de certificado posterior ao ICRU 90 | CAP-7 ("k_Q vem da tabela do TRS-398 Rev. 1"); FR-45; [TRS-398-R1 p. 101] (Tab. 16) | depende da resposta do laboratório (pendência 6) e, se o certificado atual for anterior, de recalibrar; a tabela da R-40 é a Tab. 16, com teste de regressão contra os valores da ficha; o `pylinac` não serve para esse cálculo nas três câmaras sem tabela própria |
| k_Q da edição de 2000 com o N_D,w do certificado atual | ficha TRS-398-R1, pontos 1 e 2 | a CAP-7 e o FR-45 do PRD precisam ser reescritos (os dois fixam a Rev. 1; o FR-45 como decisão do usuário de 19/10/2026); o cálculo fica coerente com o certificado de hoje e com a planilha atual, se ela usa 2000 (a base não diz qual edição a planilha usa); o PPR também não diz qual edição adota (ficha, ponto 3) |
| cálculo sem veredito até a pendência 6 fechar | CAP-7 ("fator sem fonte nasce vazio, e o resultado fica `indeterminado`"); Constraints ("Campo sem fonte nasce vazio") | a R-40 pode ser construída, mas o resultado sai `indeterminado` com o motivo até o físico registrar a origem do k_Q e do N_D,w |

Em qualquer opção, o certificado e o conjunto de k_Q usados ficam
registrados com a execução, porque a mesma câmara pode trocar de certificado
no meio da vida (CAP-6, CAP-7: "cada fator mostra valor e origem").

**Destrava:** R-40 (depende expressamente da R-37 "k_Q/ICRU 90") e o caso
"TRS-398 com resposta conhecida" da bateria semeada da R-43 (CAP-13).

resposta do físico: (26/10/2026, Geova, em sessão) **k_Q da edição de 2000
com o N_D,w do certificado atual.** A CAP-7 e o FR-45 (que fixam a Rev. 1)
são reescritos.

---

## C2 — Ações por teste: quem cadastra e quando

**Pergunta.** Quem cadastra a ação prevista de cada teste do programa (o que
fazer quando ele sai da tolerância), e em que momento: antes da carga, antes
do uso real, ou à medida que os testes falham?

**Estado hoje.** O `programa-cq.csv` não tem coluna de ação (PRD §15, C2;
FR-23). A spec diz que a ação de cada teste "nasce vazia e é cadastrada pelo
físico" (CAP-2) e que o cartão do `nao_conforme` mostra "a ação prevista"
(CAP-3); o FR-23 diz "se houver". Não diz quando.

**O que a base diz sobre o "quem".** No MPPG 8.b, quando um teste falha, o
físico qualificado (QMP) avalia as causas e toma a ação corretiva; decide se
a máquina sai de serviço ou se os tratamentos ficam limitados a certos tipos
[MPPG-8b p. 12]. Na faixa entre tolerância e limite de ação, é o QMP quem
fixa por quanto tempo a máquina pode seguir em uso, em colaboração com o
médico, os técnicos e a equipe [MPPG-8b p. 23]. A RDC 20 manda guardar as
ações corretivas adotadas junto com os resultados de CQ [RDC-20-2006 p. 9],
8.1 (b).

**O que a spec já fixa**, e é a única leitura que ela e a base levantam:

| ponto | fonte | o que muda adiante |
|---|---|---|
| quem: o físico | CAP-2 ("cadastrada pelo físico"); FR-23; [MPPG-8b p. 12, p. 23] (o QMP) | o cadastro de ação é capacidade do perfil físico na R-39 |
| estado inicial: a ação nasce vazia | CAP-2 ("nasce vazia"); FR-23 ("mostra a ação prevista, se houver") | o cartão do `nao_conforme` (CAP-3) pode sair sem ação prevista; a tela precisa dizer que ela falta, nunca presumir (Constraints, "Campo sem fonte nasce vazio") |

Sobre o "quando" (antes da carga, antes do uso real, depois do 1º
`nao_conforme`), nem a spec nem a base dão prazo ou momento: **a base não
responde**, e por isso não há opção listada. Também não está escrito onde a
ação mora (coluna nova no `programa-cq.csv`, que a Constraint "Programa vem
da base" alcançaria, ou cadastro no banco do ISOCENTRO): é parte da mesma
resposta.

Ligada a esta: o limite de ação (diferente da tolerância) também nasce vazio
e só aparece na carta quando cadastrado (CAP-5; FR-25). Quem o cadastra não
está perguntado na spec.

**Destrava:** R-39 (carga do programa, cartão do `nao_conforme`) e o roteiro
de validação da R-43.

resposta do físico: (26/10/2026, Geova, em sessão) Quem: o físico. Quando:
**antes da carga**, com alguns exemplos de ação; a lista cresce com o uso
(teste sem ação continua possível, e o cartão diz que ela falta). Onde
mora: **cadastro no banco do ISOCENTRO**, editado pela tela (não coluna no
`programa-cq.csv`). Limite de ação: **também cadastrado pelo físico**, e
nasce vazio.

---

## C6 — Itens nível 2 com conferência visual pendente: ficam em sombra?

**Pergunta.** Os itens nível 2 que viram teste (os ~97 com tolerância, nível
de ação ou constância) ficam em sombra até a conferência linha a linha contra
os PDFs, ou seguem a regra de sombra de qualquer verificação nova?

**Estado hoje.**

- Dos 358 itens de `research-tabelas-protocolos-2026-10-13/digests/itens-nivel2.csv`,
  352 saíram da extração automática das tabelas (scripts `jats_tables.py` e
  `itens_nivel2.py`, lotes 1 a 5) e 6 foram acrescentados depois, do PDF do
  TECDOC-1274 (lote 6, câmara poço e fonte de HDR). O research está com
  status parcial e a "conferência visual linha a linha contra os PDFs" ficou
  pendente (memlog do research).
- A conferência automática (`scripts/confere.py`) achou 154 de 162 limites
  numéricos literalmente na fonte; as 8 diferenças são de forma (grau
  sobrescrito, colunas do TG-51, anotação PT) (memlog do research).
- Toda verificação nova já nasce em sombra: executa e loga, sem alerta, fila,
  contador nem sinal de máquina; a promoção grava quem, quando e o resumo do
  período (spec Fundação, CAP-10; FR-4). O mínimo em sombra é 30 dias
  `[SUPOSIÇÃO]`, encurtável pelo físico com justificativa (FR-4).
- Todo teste do GQ cita a referência com tabela e página, e teste sem origem
  não é carregado (Constraints, "Tolerância com origem").

| opção | fonte | o que muda adiante |
|---|---|---|
| ficam em sombra **até** a conferência linha a linha, além do período normal | spec GQ, Open Questions; PRD §15, C6 | a promoção desses testes passa a exigir um registro de conferência por item; a R-39 precisa de um estado ou marca "conferência pendente" que impeça promover; a conferência entra como tarefa antes do uso real |
| seguem a sombra normal (FR-4), sem condição extra | spec Fundação, CAP-10; FR-4 | o físico promove pelo resumo do período, como qualquer verificação; a conferência visual deixa de ser pré-requisito do módulo |

**Destrava:** R-39 (carga dos itens nível 2 e promoção) e o conteúdo do
relatório de validação da R-43.

resposta do físico: (26/10/2026, Geova, em sessão) **Ficam em sombra até a
conferência linha a linha**, além do período normal; a promoção exige o
registro de conferência por item.

---

## Dermopan — clínica, máquina e entrada na carga

**Pergunta.** O Dermopan entra na carga do programa de CQ, com os 12 testes
de ortovoltagem, em que clínica e com que cadastro de máquina?

**O que a base diz.**

| fato | fonte |
|---|---|
| Siemens Dermopan, s/n 491/2097, 50 kV, aceite em 1999, 7,55 cGy/min a 10,7 cm com aplicador 7×7 cm², na **CEL** | `conhecimento/servico/ppr-tecnico.md` (PPR CEL, mai/2026); `conhecimento/README.md`; ficha `fichas/atividades/A20.md` |
| O gerador do programa já liga o Dermopan à CEL com a etiqueta `orto` | `conhecimento/scripts/gerar_programa_cq.py`, `MAQUINAS` |
| 12 testes `orto` no `programa-cq.csv`: 3 diários, 3 mensais (dose de referência 3%, CSR 3%, planura e simetria 3%), 6 anuais (fuga ≤ 1 mGy/h, protetor de sobrecarga, dose/cones/PDD/braço 3%, CSR/mA/estabilidade 2%, temporizador 1% e 2 s) | `conhecimento/matriz/programa-cq.csv`, linhas `*_orto` |
| Obrigatório: segurança diária para todas as fontes e dose mensal em condição de referência | [NN-6.10 p. 9], art. 35, III e IV |
| Radioterapia superficial: dispositivo que indique tensão e corrente no tubo "quando estas puderem ser variadas"; para tubo com energia máxima de até 50 keV, fuga de no máximo 1 mGy/h em média numa área de 10 cm², a 5 cm da blindagem (inciso II); de 50 a 150 keV, 10 mGy/h (inciso III) | [NN-6.10 p. 14], art. 57 |
| O PPR da CEL usa 5% na dose mensal, e não tem o diário, a fuga nem o anual; o `programa-cq.csv` adotou os 3% do TECDOC-1151 | ficha A20, "PPR × TECDOC × norma" e "Lacuna no PPR" |
| A câmara usada na dosimetria do Dermopan, e se ela tem calibração em 50 kV, não está no PPR | `PENDENCIAS.md`, pendência 5; ficha A20, "Como fazer" |
| A Rev. 1 do TRS-398 passou a ter dados próprios para raios X de quilovoltagem, coerentes com o ICRU 90 | [TRS-398-R1 p. 20], 1.2.1 (e) |

A clínica e o equipamento a base responde (CEL, s/n 491/2097). Se o Dermopan
continua em uso clínico hoje, a base não responde: o dado mais novo é o PPR
de mai/2026.

| opção | fonte | o que muda adiante |
|---|---|---|
| entra na carga na CEL, com os 12 testes `orto` | CAP-1 (etiqueta `orto`); FR-24 (frequências diária, mensal e anual do Dermopan); Constraints, "Escopo de equipamentos" (ortovoltagem incluída) | a R-39 cadastra a máquina Dermopan na CEL pela chave canônica (AD-26) e instancia os 12 testes; os dosimétricos ficam `indeterminado` até haver instrumento cadastrado com calibração na qualidade (CAP-6; pendência 5) |
| fica fora da carga | spec GQ, Open Questions (Dermopan sem clínica e máquina definidas) | a ortovoltagem sai do escopo de equipamentos da spec (Constraints) e do FR-24; o programa de CQ do Dermopan continua fora do ISOCENTRO, e a obrigação do art. 35 [NN-6.10 p. 9] fica com o registro que existir fora dele |

Ligada a esta, mas fora da R-37: a dose de referência do Dermopan pelo
capítulo de kV da Rev. 1 (cálculo TRS-398 da CAP-7) depende da câmara da
pendência 5 e da resposta da C5.

**Destrava:** R-39 (carga e instância por máquina) e, para a dose de
referência do Dermopan, R-40.

resposta do físico: (26/10/2026, Geova, em sessão) **Entra na carga na
CEL, com os 12 testes `orto`.** Os dosimétricos ficam `indeterminado` até
haver câmara cadastrada com calibração em 50 kV (pendência 5).

---

## C7 — Retenção dos registros de CQ

**Pergunta.** Por quanto tempo o ISOCENTRO guarda os registros de CQ (execuções,
anexos, imagens, log): pela vida útil do equipamento ou por 10 anos após o
descarte do software, e qual prevalece quando os dois diferem?

**O que a base diz.**

| fato | fonte |
|---|---|
| Intervenções nos equipamentos, resultados das calibrações e dos testes de CQ e as ações corretivas são mantidos em arquivo **por toda a vida útil do equipamento** | [RDC-20-2006 p. 9], 8.1 (b) |
| Os resultados do programa de garantia da qualidade são registros arquivados, com cópia de segurança independente; a norma não fixa prazo | [NN-6.10 p. 16], art. 71, IX e parágrafo único |
| Os **registros de validação** do SaMD *in house* são mantidos por pelo menos 10 anos após o descarte do SaMD | [RDC-657 p. 3], art. 5º, §§ 2º e 3º |
| O backup conta a retenção como 10 anos após o descarte do software | AD-24 |
| A revisão da espinha anota que a vida útil do equipamento pode passar de 10 anos | `reviews/reconcile-prd-ux.md`, linha do FR-28 |
| Nada se apaga: sem DELETE em dado registrado | AD-5 |
| A retenção por tipo de registro ficou adiada para o épico do GQ | espinha, Deferred |

A RDC 657 fala dos registros de **validação** do software; se o prazo dela
alcança os registros de CQ que o software guarda, o texto não diz. A RDC 20
não diz por quanto tempo depois do fim da vida útil do equipamento o
registro fica: nos dois pontos, **a base não responde**.

| opção | fonte | o que muda adiante |
|---|---|---|
| vida útil do equipamento | [RDC-20-2006 p. 9]; FR-28; CAP-11 | o prazo é por máquina; o cadastro de máquina precisa da data de descarte. Descartar o registro ao fim do prazo esbarra no AD-5 (sem DELETE) e no log encadeado (AD-24, Prevents: "retenção menor que a do log"): a espinha não tem hoje caminho para isso |
| 10 anos após o descarte do software | [RDC-657 p. 3]; AD-24 | um prazo único para todo o banco, como o AD-24 já conta; um equipamento que dure mais que o software fica coberto até 10 anos depois do descarte do software, não do equipamento |

Em qualquer opção, o relatório de validação do GQ continua guardado 10 anos
após o descarte (CAP-13); a pergunta é sobre os registros de CQ.

**Destrava:** R-43 (CAP-11, restauração e guarda) e a decisão adiada de
retenção por tipo de registro na espinha (Deferred), que liga ao AD-24.

resposta do físico: (26/10/2026, Geova, em sessão) **O mais longo dos
dois**: nada se apaga enquanto o equipamento existir, nem antes de 10 anos
após o descarte do software. Coerente com o AD-5 (sem DELETE) e com o log
encadeado; a espinha não precisa de caminho de descarte para o MVP.
