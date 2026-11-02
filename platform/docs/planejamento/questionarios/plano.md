# Questionário do físico — módulo Plano

> **Rascunho da IA: nada aqui é decisão.** As opções abaixo são as que a spec
> do Plano e a base de conhecimento já levantam, cada uma com a fonte; nenhuma
> é recomendada. Quem decide é o físico responsável, na frente R-27, e a
> resposta vai para o memlog da spec (e as linhas de risco para o
> `docs/qms/riscos.md`) pelas mãos dele, não por este arquivo.

Frente R-71 (robô, 23/10/2026), que prepara a R-27. Spec:
`docs/planejamento/sistema-global/spec-isocentro-plano/SPEC.md` (Open
Questions). A numeração (G1, P5…) é a do PRD, §15.

**Como ler as fontes.** `[CÓDIGO p. N]` é o documento do acervo
(`conhecimento/matriz/fontes.csv`) e a página do texto integral em
`conhecimento/texto/`, conferida nesta sessão. `CAP-n` é da spec do Plano,
`FR-n`/`NFR-n` do PRD (`prd-isocentro-2026-10-16/prd.md`) e `AD-n` da espinha
(`architecture-isocentro-2026-10-19/ARCHITECTURE-SPINE.md`). Onde a base não
tem o que dizer, está escrito "a base não responde" e não há opção inventada.

Ordem: as que bloqueiam o primeiro épico primeiro (G1), depois as do MVP 1
(NFR-5, FFF/filtros, P5) e as do MVP 2 (P7, P8, P9, P12).

---

## G1 — Classe IEC 62304 e classe ANVISA do módulo Plano

**Pergunta.** Em que classe de segurança da IEC 62304 (A, B ou C) e em que
classe de risco da ANVISA fica o módulo Plano?

**Estado hoje.** O AD-35 manda construir o núcleo e o Plano no rigor da
classe C até a classificação formal; a spec diz que a G1 fecha antes do 1º
épico do Plano (Constraints). O `docs/qms/classificacao-62304.md` só
classifica o Radioteradados e o `dominio/ritmo` (PRD §12.1).

**Opções — IEC 62304** (definições em [IEC-62304 p. 10]):

| opção | o que a norma diz | o que muda adiante |
|---|---|---|
| A | o sistema não contribui para situação perigosa, ou contribui sem risco inaceitável depois das medidas de controle externas a ele | rigor menor de documentação e teste; o AD-35 deixa de valer para o Plano |
| B | contribui para risco inaceitável cujo dano possível é lesão não grave | idem, rigor intermediário; o AD-35 cai para o Plano |
| C | contribui para risco inaceitável cujo dano possível é morte ou lesão grave | confirma o AD-35: o Plano segue no rigor atual da espinha |

A mesma página diz que o fabricante pode rebaixar a classe acrescentando
medidas de controle de risco **externas** ao software (hardware, outro
software independente, procedimento) [IEC-62304 p. 10]. A spec registra
duas que já existem: a trava é a do ARIA, e a assinatura em papel continua
(Constraints: "Advisory" e "Papel não muda"). Se elas contam como medida
externa é parte da pergunta.

**Opções — ANVISA:**

| opção | fonte | o que muda adiante |
|---|---|---|
| classe I ou II | [RDC-657 p. 2], art. 5º: SaMD *in house*, de uso exclusivo do serviço, nas classes I e II, não precisa de regularização | o caminho *in house* do PRD (§12.1, §14.2) continua valendo |
| acima de II | PRD §12.1 e §14.2: "se a classe passar de II, o art. 5º da RDC 657 deixa de valer" | o Plano passa a exigir regularização na ANVISA antes do uso |

A regra que classifica o dispositivo (RDC 751/2022) está **fora do acervo**
(`conhecimento/PENDENCIAS.md`, lacunas): para dizer em qual classe o Plano
cai, a base não responde.

**Destrava:** o 1º épico do Plano (spec, Constraints; espinha, Deferred) —
R-30, R-31, R-32, R-33, R-34, R-35; e o rigor do relatório de validação da
R-36. A justificativa de segregação entre classes no mesmo processo Python
(IEC 62304 §5.3.5) volta junto com a G1 (espinha, Deferred).

resposta do físico: (26/10/2026, Geova, em sessão) IEC 62304 **classe A**.
A trava do ARIA e a assinatura em papel **contam** como medida de controle
externa. ANVISA: **classe I ou II até todos os testes**. A mesma classe vale
para o núcleo e para o módulo Radioteraficha.

---

## NFR-5 — Tempo da segunda checagem

**Pergunta.** A segunda checagem de um plano precisa ficar pronta em menos
de 30 s, agora que o VMAT entra pelo Clarkson por ponto de controle?

**Estado hoje.** O número é `[SUPOSIÇÃO]` (NFR-5) e vem do aceite da Fase 3
do brief (`brief-sgq-rt-2026-10-13/addendum.md`: "< 30 s/plano"). A espinha
adiou o desempenho para o épico do Plano (Deferred). A base de conhecimento
não fixa tempo de segunda checagem: **a base não responde**; as opções
abaixo vêm só da spec, do PRD e da arquitetura.

| opção | fonte | o que muda adiante |
|---|---|---|
| confirmar 30 s por plano, contando C-MOVE + cálculo | NFR-5; brief, Fase 3; reconciliação PRD × UX, L6 (`reviews/reconcile-prd-ux.md`) | o orçamento cobre buscar o RT Plan e calcular; o Clarkson em VMAT tem de caber nele, e a medição entra na suíte ou no roteiro de validação |
| outro número para o modulado | a spec pede "confirmar o número" com o Clarkson (Open Questions); nenhum valor alternativo está escrito | 3D e modulado ganham orçamentos separados; a spec não propõe qual |
| sem número fixo: vale o critério do FR-11 | FR-11 / CAP-2: "resultado pronto antes de o plano aparecer na fila de Aprovação Física" | o aceite passa a ser de prazo no fluxo, não de segundos; NFR-5 é reescrito |

**Destrava:** R-30 (motor 3D), R-31 (Clarkson) e a medição de desempenho no
épico do Plano (espinha, Deferred).

resposta do físico: (26/10/2026, Geova, em sessão) **Sem número fixo**: vale
o critério do FR-11, resultado pronto antes de o plano aparecer na fila de
Aprovação Física. O NFR-5 é reescrito.

---

## FFF e filtros físicos — tabela própria ou "sem tabela"

**Pergunta.** Para cada energia FFF e cada conjunto de filtros físicos, a
segunda checagem ganha tabela de feixe própria ou fica explicitamente "sem
tabela"?

**O que está em jogo** (`conhecimento/PENDENCIAS.md`, pendências 9, 13 e 14;
FR-10):

- TrueBeam (CEL): comissionado com **6FFF e 10FFF**, que não constam do PPR
  (pendência 13).
- VitalBeam (DUO): 6FFF (FR-10) e **filtros físicos de 15° a 60°**
  comissionados no Eclipse; usar ou retirar (pendência 9).
- 600CD (BET): dados de **filtros físicos de 15° a 60°** de 2010, com o PPR
  marcando filtro como "Não aplicável" (pendência 14).

| opção | fonte | o que muda adiante |
|---|---|---|
| tabela própria por energia / filtro | CAP-1; FR-10 ("têm tabela própria") | entra na R-09 (conversão validada contra pontos do relatório) e no comissionamento da R-29; o filtro exige que o `paralelo.py` passe a tratar filtro, porque hoje o campo com filtro sai `indeterminado` (CAP-5, FR-13) |
| "sem tabela", declarado | CAP-1; FR-10 ("ou ficam explicitamente sem tabela") | todo campo FFF ou com filtro sai `indeterminado` com o motivo (CAP-5); a obrigação do segundo sistema de cálculo [NN-6.10 p. 5], art. 15, XI, e, fica sem cobertura do ISOCENTRO para esses campos |

Nas duas opções, se FFF ou filtro estiverem em uso, o PPR precisa recebê-los:
[NN-6.10 p. 5], art. 15, XIV, manda submeter PPR novo ou complementação
**antes** de modificar procedimento que altere a proteção radiológica (PRD
§14.2). Se estão em uso hoje é pergunta das pendências 9, 13 e 14, não desta.

**Destrava:** R-09 (tabelas), R-29 (comissionamento) e R-30 (casos de teste
"filtro → `indeterminado`").

resposta do físico: (26/10/2026, Geova, em sessão) **FFF com tabela
própria.** **Filtro físico: ignorar** — apesar de comissionado, não é mais
usado na rotina.

---

## P5 — De onde vem a dose acumulada dos 10%

**Pergunta.** Os "10% da dose total" do prazo de verificação contam a dose
registrada no ARIA ou a dose planejada × frações, e do curso ou da fase?

**O que a base diz.** A obrigação é da [RDC-20-2006 p. 10], 9.7 (c): "todo
cálculo deve ser verificado até a terceira aplicação ou até a dose acumulada
de 10% da dose total, o que ocorrer primeiro". O [TG-114 p. 6] recomenda a
verificação antes da 1ª fração e, quando não der, antes da 3ª fração ou de
10% da **dose prescrita**, "o que corresponder à menor dose entregue". Nenhum
dos dois diz se "dose total" é do curso ou da fase, nem se a acumulada é a
registrada ou a planejada: **a base não responde** a essas duas partes.

| opção | fonte | o que muda adiante |
|---|---|---|
| dose **registrada** no ARIA | FR-15; CAP-7 ("a contagem vem do tratamento entregue") | o prazo depende do tratamento entregue (`banco/tratamento_db.py`) e herda o aviso da R-07 (ver P12) |
| dose **planejada × frações** entregues | FR-15 | o prazo depende do RT Plan e da contagem de frações; frações com dose diferente da planejada não aparecem |
| 10% do **curso** | FR-15 | um plano novo de fase seguinte pode já nascer acima dos 10% do curso |
| 10% da **fase** | FR-15; FR-11 (plano novo ou modificado conta prazo do zero) | cada fase tem prazo próprio, coerente com "plano novo → nova execução" da CAP-2 |
| manter a regra provisória | spec, Assumptions ("vale o que vier primeiro entre as duas leituras disponíveis") | o alerta dispara pela leitura mais cedo; o físico vê qual das duas venceu |

**Destrava:** R-30 (prazo da CAP-7, testado com o app fechado) e R-33 (filas
ordenadas pelo prazo).

resposta do físico: (26/10/2026, Geova, em sessão) Dose acumulada = **dose
registrada no ARIA**. Base dos 10%: **a mais restritiva possível** — curso e
fase são calculados, e o alerta dispara pela que vencer primeiro (a regra
provisória da spec, Assumptions), mostrando qual venceu.

---

## P7 — Referência de cada item automático e lista dos itens "F" do TG-275

**Pergunta.** Contra o quê cada item automático das listas é conferido, e
quais itens marcados "F" no TG-275 entram no MVP?

**Parte 1 — referência de cada automático** (CAP-13; FR-19):

| item automático | fonte do valor lido | referência que a spec/PRD já cita | o que a spec deixa aberto |
|---|---|---|---|
| dose diária e total × prescrição (AF e Duplo Check) | RT Plan | prescrição do ARIA, `DWH.DimPrescription` (CAP-14) | — |
| máquina correta (AF e Duplo Check) | RT Plan | FR-19 dá dois candidatos: máquina da **prescrição** ou do **agendamento** | qual dos dois |
| UM compatíveis (Duplo Check) | RT Plan | a segunda checagem (CAP-13) | — |
| coordenadas do isocentro e fases no mesmo isocentro (Duplo Check) | RT Plan | a spec não diz contra o quê | a referência inteira |
| cursos anteriores abertos (AF) | `variandw` | a spec não diz o critério de "aberto" | o critério |

Regra que vale em qualquer resposta: item sem referência nasce vazio, nunca
`conforme` (CAP-13; NFR-4).

**Parte 2 — itens "F"**. No TG-275, "F" é a coluna "Auto. target" da
Tab. S1.A.ii: checagem que "pode potencialmente ser totalmente
automatizada"; "P" é automação parcial; "++" é checagem prioritária (RPN >
100 e uso > 60%) [TG-275 p. 21]. O PRD §6 diz que os itens "++"
automatizáveis (marcados F) são conferidos do RT Plan e do ARIA, e deixa a
lista exata ao físico (FR-19).

| opção | fonte | o que muda adiante |
|---|---|---|
| só os automáticos da CAP-13 | CAP-13 ("Os automáticos do MVP são: …") | a lista do MVP fica nos itens votados; nenhum item novo entra |
| CAP-13 + os "++" com "F" da Tab. S1.A.ii | PRD §6; [TG-275 p. 21] | entram verificações `plano.*` que não estão nas listas votadas de 30/03/2026; cada uma precisa de referência (parte 1) e de erro semeado (CAP-17) |
| incluir também itens do MPPG 11.a | memlog da spec (questão vinda da spec GQ: 160 itens nível 2 destinados ao Plano, forma de entrada em aberto) | pede um update da spec antes; não é decisão só da P7 |

**Destrava:** R-34 (listas e conferência da prescrição) e a bateria
semeada da R-36.

resposta do físico: (26/10/2026, Geova, em sessão) Parte 1 — **máquina**:
a da prescrição e a do agendamento têm de ser a mesma (o item confere as
duas contra o RT Plan e entre si). **Curso anterior aberto**: status
diferente de concluído. **Isocentro**: os quatro candidatos propostos na
sessão entram todos — (1) todos os campos, de tratamento e de setup, com o
mesmo `IsocenterPosition`; (2) isocentro − marcador TP0 do RT Struct =
deslocamentos de setup do RT Plan; (3) isocentro de cada fase = o da fase
anterior no mesmo `FrameOfReferenceUID`, divergência sinalizada para o
físico confirmar (boost em outro ponto existe); (4) isocentro dentro do
BODY. Tolerância em mm de (1)–(3): **não definida** — vazia, sem veredito
até o físico fixar. Parte 2 — **todos**: CAP-13 + os "++" com "F" da
Tab. S1.A.ii do TG-275 + os itens do MPPG 11.a (este último pede update da
spec antes).

---

## P8 — Limiar que marca hipofracionamento

**Pergunta.** A partir de que dose por fração (e/ou número de frações) o
caso é marcado como hipofracionado / SBRT, e portanto de alto risco?

**O que a base diz.**

| referência | o que diz | fonte |
|---|---|---|
| TG-101, Tab. I | "típico" de 3D/IMRT: 1,8–3 Gy por fração, 10–30 frações; de SBRT: 6–30 Gy por fração, 1–5 frações | [TG-101 p. 3] |
| TG-275 | casos de alto risco que pedem revisão antes da 1ª fração incluem "alta dose por fração ou poucas frações", sem número | [TG-275 p. 11] |
| TG-275 | política própria para hipofracionado entregue em **menos de seis dias**, porque a revisão semanal não o alcança | [TG-275 p. 14] |
| ACR-AAPM, citado no TG-275 | verificação das UM antes do 1º tratamento quando há **menos de cinco frações** | [TG-275 p. 4] |

A faixa entre 3 e 6 Gy por fração (fora das duas colunas da Tab. I do
TG-101) não tem limiar na base: para ela, **a base não responde**.

| opção | fonte | o que muda adiante |
|---|---|---|
| pela dose por fração da coluna SBRT (≥ 6 Gy) | [TG-101 p. 3] | só o SBRT típico vira alto risco pela prescrição; hipofracionamento moderado segue o prazo comum |
| pelo número de frações (≤ 5, ou < 5) | [TG-101 p. 3]; [TG-275 p. 4] | o critério independe da dose por fração |
| pela duração do curso (< 6 dias) | [TG-275 p. 14] | o critério depende do agendamento, não só da prescrição; a CAP-10 hoje lê só a prescrição |
| combinação de dose por fração **e** número de frações | CAP-10 ("dose por fração e nº de frações") | o limiar tem dois números, ambos do físico |

Em qualquer opção: enquanto reirradiação ou dispositivo estiverem "não
informado", o caso já é tratado como alto risco (CAP-10); a P8 só decide a
parte que vem da prescrição.

**Destrava:** R-33 (marcação de alto risco e prazo antes da 1ª fração).

resposta do físico: (26/10/2026, Geova, em sessão) **Todos**, o que
disparar primeiro: alto risco se dose por fração ≥ 6 Gy **ou** nº de
frações ≤ 5 **ou** curso em menos de 6 dias. O critério de duração lê o
agendamento (a CAP-10 hoje lê só a prescrição: pede update da spec).

---

## P9 — O que invalida uma assinatura

**Pergunta.** Quais mudanças no plano fazem a assinatura do Duplo Check (e
da Aprovação Física no ISOCENTRO) voltar a pendente?

**Estado hoje.** O AD-30 define a versão do plano como `Ser` +
`SOPInstanceUID` + `HstryDateTime`/status de aprovação: se ela muda, a
assinatura não se transfere. O FR-8 deixa ao físico o que conta como "outra
versão". O [TG-275 p. 11] diz que recálculo ou reotimização devem disparar
revisão completa, que outras ações (acrescentar um campo de setup, renomear
um campo) podem pedir revisão abreviada, e que **cada serviço deve definir
essa categorização** pelo próprio fluxo.

| caso | fonte | se invalida | se não invalida |
|---|---|---|---|
| UID novo com conteúdo igual | FR-8; spec P9 | reexportar ou reaprovar sem mudar nada devolve o plano à fila | o ISOCENTRO precisa comparar conteúdo para saber que é "igual"; a spec não define a comparação |
| mudança de status no ARIA (ex.: desaprovar e reaprovar) | FR-8; AD-30 (status faz parte da versão) | segue o AD-30 como está | o AD-30 precisa ser editado (sai o status da versão) |
| conteúdo mudado sem UID novo | spec P9 | exige detectar mudança de conteúdo além do UID | a assinatura continua valendo sobre conteúdo diferente do assinado |
| mudança "menor" (campo de setup, nome de campo) | [TG-275 p. 11] | qualquer mudança volta à fila | o serviço define a lista do que é menor, e o ISOCENTRO precisa reconhecê-la |

**Destrava:** R-34 ("plano alterado → pendente") e o caso semeado "plano
alterado depois da assinatura" da R-36 (Success signal da spec).

resposta do físico: (26/10/2026, Geova, em sessão) **Invalida em todos os
quatro casos**: UID novo com conteúdo igual, mudança de status no ARIA,
conteúdo mudado sem UID novo e mudança "menor". O AD-30 fica como está; o
caso 3 exige comparar conteúdo além do UID.

---

## P12 — A R-07 fecha antes do MVP 2?

**Pergunta.** A conferência dos 165 cursos contra o ARIA (frente R-07)
termina antes de o MVP 2 entrar em uso?

**Estado hoje.** A R-07 é frente `voce` e está pendente (`DESTINO.md`); ela
destrava o `LISTA_VERIFICADA_EM`. É cronograma do serviço: **a base não
responde**. As duas saídas abaixo são as que a spec já prevê.

| opção | fonte | o que muda adiante |
|---|---|---|
| fecha antes | CAP-7; FR-15 | o alerta de prazo e a fila mostram a contagem de frações sem ressalva |
| não fecha antes | CAP-7, CAP-11; FR-15, FR-17 | o MVP 2 entra com o aviso "contagem de frações não conferida contra o ARIA" em todo prazo e em todo plano tratado sem Duplo Check |

Ligada a esta, mas fora da R-27: a G2 (se a contagem usar o `dominio/ritmo`,
a classe A dele continua valendo).

**Destrava:** R-33 (filas com contagem de frações) e o texto de alerta da
R-30 (CAP-7).

resposta do físico: (26/10/2026, Geova, em sessão) **Fecha antes**: a R-07
é condição de entrada do MVP 2 (com a P5 em dose registrada, o alerta dos
10% depende da contagem conferida). O aviso automático por
`LISTA_VERIFICADA_EM` vazio continua como rede de segurança.
