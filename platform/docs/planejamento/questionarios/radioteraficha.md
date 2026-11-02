# Questionário do físico — módulo Radioteraficha

> **Rascunho da IA: nada aqui é decisão.** As opções abaixo são as que a spec
> do módulo Radioteraficha, o código de hoje e a base de conhecimento já
> levantam, cada uma com a fonte; nenhuma é recomendada. Quem decide é o
> físico responsável, na frente R-51, e a resposta vai para o memlog da spec
> (e as linhas de risco para o `docs/qms/riscos.md`) pelas mãos dele, não por
> este arquivo.

Frente R-75 (robô, 23/10/2026), que prepara a R-51. Spec:
`docs/planejamento/sistema-global/spec-isocentro-radioteraficha/SPEC.md`
(Open Questions). A G1 é a do PRD (§15).

**Como ler as fontes.** `[CÓDIGO p. N]` é o documento do acervo
(`conhecimento/matriz/fontes.csv`) e a página do texto integral em
`conhecimento/texto/`, conferida nesta sessão. Exceção: os POPs do CLINICA
(`[POP-019]`, `[POP-021]`, `[POP-036]`) **não** estão no `fontes.csv`; o
texto deles está em `conhecimento/texto/10 POPs CLINICA/`, vindo de
`servico/pops/`, sem marca de página, e a página citada é a do cabeçalho do
próprio POP ("PÁGINA 01/02"). `CAP-n` é da spec do módulo Radioteraficha, `FR-n` do PRD
(`prd-isocentro-2026-10-16/prd.md`) e `AD-n` da espinha
(`architecture-isocentro-2026-10-19/ARCHITECTURE-SPINE.md`). O que vem do
código está citado pelo arquivo e pela linha (`isocentro/...`), porque é
código e não texto da base. `[PPR-CLINICA]` é o PPR da CEL de março de 2024,
guardado no acervo como modelo de formatação: diz o que **uma** clínica
escreveu em 2024. Onde a base não tem o que dizer, está escrito "a base não
responde" e não há opção inventada.

**Sobre o "Destrava".** No `DESTINO.md`, só a R-55 depende da R-51
expressamente. A R-53 constrói o que três destas respostas definem
(inventário, notas, vínculo pendente), mas a dependência dela está escrita
só para R-18, R-19, R-22 e R-52: onde a R-53 aparece abaixo, é por usar a
resposta, não por dependência registrada.

Ordem: a classe primeiro (decide o rigor de tudo o mais), depois o
inventário e as notas, que são a mesma pergunta de tabela (de clínica ou
global, AD-12), o vínculo pendente e, por fim, as raízes da varredura, que
só servem no corte (R-55).

Fora deste questionário, embora a R-51 os peça: as linhas do módulo no
`riscos.md` (S, O, D são do físico) e a atualização do `EXPERIENCE.md`
(cartão Tratamento abrindo a Virtual), que não é pergunta com opções.

---

## G1 — Classe IEC 62304 e classe ANVISA do módulo

**Pergunta.** Em que classe de segurança da IEC 62304 (A, B ou C) e em que
classe de risco da ANVISA fica o módulo Radioteraficha, que imprime a ficha
e a capa conferidas na sala de tratamento?

**Estado hoje.** A spec diz "Classe B provisória (AD-35)" nas Constraints e
nas Assumptions, e o memlog repete. O AD-35 da espinha diz outra coisa:
"núcleo, `rt`, módulo Plano e módulo Radioteraficha (imprime a ficha e a capa
da sala) são projetados e construídos no rigor da classe C até a
classificação formal". O AD-39 completa: "módulo sem classe atribuída vale
rigor C", e a fonte da classe é o `docs/qms/classificacao-62304.md` assinado
pelo físico. Esse arquivo hoje classifica só o Radioteradados e o
`dominio/ritmo` (classe A); a espinha registra que o `dominio/ritmo` não
existe no código (tabela de divergências do AD-35), e não há
`isocentro/dominio/ritmo*`. O cabeçalho do `classificacao-62304.md` diz que
"a classe considera o software sem as medidas de controle de risco externas
a ele".

**O que a base diz.**

| fato | fonte |
|---|---|
| Classe A: o sistema não contribui para situação perigosa, ou contribui sem risco inaceitável **depois** de consideradas as medidas de controle de risco externas a ele | [IEC-62304 p. 9–10], 4.3 a), na redação da Emenda 1 (2015) |
| Classe B: contribui para risco inaceitável depois das medidas externas, e o dano possível é lesão não grave; classe C: o dano possível é morte ou lesão grave | [IEC-62304 p. 10], 4.3 a) |
| O fabricante pode acrescentar medidas de controle externas (hardware, software independente, procedimento de saúde) e reclassificar depois | [IEC-62304 p. 10], 4.3 a) e Nota 1 |
| O fabricante identifica a segregação entre itens de software necessária ao controle de risco e diz como garante que ela é efetiva; a exigência vale para a classe C | [IEC-62304 p. 13], 5.3.5 ("[Class C]") |
| Software que presta informação usada em decisão terapêutica é classe II; classe III se a decisão puder causar deterioração grave da saúde; classe IV se puder causar morte ou deterioração irreversível | [RDC-751-2022 p. 14–15], Regra 11 |
| O software que comanda um dispositivo ou influencia o seu uso fica na classe desse dispositivo; SaMD independente é classificado sozinho | [RDC-751-2022 p. 4], art. 8º, §§ 3º e 4º |
| Dispositivo ativo que emite radiação ionizante para fins terapêuticos, e o que o controla, monitora ou influencia diretamente o seu desempenho, é classe III | [RDC-751-2022 p. 14], Regra 9, 3º parágrafo; a Regra 10 repete para "radiologia diagnóstica ou terapêutica" no último parágrafo |
| Qualquer outro SaMD, fora dos casos da Regra 11, é classe I | [RDC-751-2022 p. 15], Regra 11, último parágrafo |
| SaMD *in house*, de uso exclusivo do serviço (matriz ou filiais), nas classes I e II, não é regularizado na ANVISA, desde que não interfira no funcionamento de dispositivo regularizável | [RDC-657 p. 2], art. 5º |
| Software que só transporta ou armazena dado médico não é dispositivo médico | [ANVISA-RDC657-PR p. 29], pergunta 74 |

Do lado do código: a ficha leva valores que o programa **calcula** a partir
do DICOM, como a SSD (`isocentro/dicom/dicom_rt.py:1542`, `calcular_ssds`),
e não só os transporta. E o `CLAUDE.md` do projeto descreve a conferência:
a ficha e a capa são "conferidas por quem posiciona o paciente na mesa".
Se essa conferência conta como medida de controle externa, no sentido da
Nota 1 do 4.3, **a base não responde**: é parte da pergunta. Se a ficha
"influencia o uso" do acelerador no sentido do art. 8º, § 3º, ou é SaMD
independente (§ 4º), também não.

**Opções — IEC 62304** (definições em [IEC-62304 p. 9–10]):

| opção | o que a norma diz | o que muda adiante |
|---|---|---|
| A | não contribui para situação perigosa, ou contribui sem risco inaceitável depois das medidas externas | o AD-35 deixa de valer para o módulo; a conferência na sala teria de constar como medida externa no `riscos.md`; o cabeçalho do `classificacao-62304.md` (classe "sem as medidas externas") fica em conflito com a redação de 2015 da base |
| B | risco inaceitável depois das medidas externas, dano possível não grave | o que a spec já escreve; o AD-35 e o AD-39 (rigor C até a classificação) cedem para o módulo; com o núcleo e o `rt` em C, a espinha (Deferred) pede a justificativa da segregação do 5.3.5 entre itens de classes diferentes no mesmo processo Python |
| C | risco inaceitável depois das medidas externas, dano possível morte ou lesão grave | confirma o AD-35; a spec do módulo teria de trocar "Classe B provisória" nas Constraints e nas Assumptions |

**Opções — ANVISA:**

| opção | fonte | o que muda adiante |
|---|---|---|
| não é dispositivo médico | [ANVISA-RDC657-PR p. 29], pergunta 74 (software que só transporta ou armazena) | nenhuma regularização nem classe ANVISA; a pergunta 74 fala de software que "somente" transporta ou armazena, e a ficha leva a SSD calculada pelo programa (`dicom_rt.py:1542`) |
| classe I | [RDC-751-2022 p. 15], Regra 11, último parágrafo | o caminho *in house* do [RDC-657 p. 2], art. 5º, vale |
| classe II (Regra 11, caso geral) | [RDC-751-2022 p. 14], Regra 11, caput | o caminho *in house* do [RDC-657 p. 2], art. 5º, continua valendo |
| classe III ou IV (Regra 11, a) ou b)) | [RDC-751-2022 p. 14–15], Regra 11 | PRD §12.1 e §14.2: "se a classe passar de II, o art. 5º da RDC 657 deixa de valer"; o módulo passaria a exigir regularização na ANVISA antes do uso |
| classe do acelerador (III), por influenciar o uso dele | [RDC-751-2022 p. 4], art. 8º, § 3º; [p. 14], Regra 9 | idem: acima de II, sem o caminho *in house* |

O questionário do Plano (`plano.md`, G1) diz que a RDC 751 está fora do
acervo; hoje o texto dela está em `conhecimento/texto/08 Software,
dispositivo médico e dados/RDC-751-2022.md`, e é dele que vêm as linhas
acima. Qual regra se aplica ao módulo, **a base não responde**.

**Destrava:** R-55 (o rigor do relatório de validação assinado, CAP-12); a
correção da spec nas Constraints e nas Assumptions, qualquer que seja a
classe; R-53 e R-54, que constroem no rigor que a classe fixa (AD-39).

resposta do físico: (26/10/2026, Geova, em sessão, respondida no
questionário do Plano) IEC 62304 **classe A**, a mesma do Plano e do núcleo.
A trava do ARIA e a assinatura em papel **contam** como medida de controle
externa. ANVISA: **classe I ou II até todos os testes**.

---

## Inventário de imobilizadores: de onde vem o real, e se é por clínica

**Pergunta.** De onde vem o inventário real de máscaras e VacLok que
substitui o fictício, e ele é um só para o serviço ou um por clínica?

**Estado hoje.** A spec diz que "o arquivo atual é fictício" e põe o
inventário no banco (CAP-8: "máscara com contador de usos, VacLok vinculado
ao paciente"; "vincular imobilizador nunca é bloqueado; só avisa"). No
código, o `inventario_imobilizadores.json` é semeado com itens fictícios na
primeira execução, e "o inventário real entra no lugar dele sem mudança de
código, bastando substituir o arquivo" (`isocentro/dados/inventario.py:20-23`).
Os comentários dizem duas vezes que "o inventário real vem de outro sistema"
(`inventario.py:82`, `inventario.py:100`), sem dizer qual. Cada item guarda
etiqueta, tipo, estado, nome e registro do paciente, número de usos e data
de aquisição (`inventario.py:70-79`); só a máscara conta usos, e o aviso
acende aos 20 (`LIMITE_USOS`, `inventario.py:63-66`). O arquivo fica na
pasta do app ou em `ISOCENTRO_INVENTARIO_DIR` (`inventario.py:128-130`).

**O que a base diz.**

| fato | fonte |
|---|---|
| O serviço tem de dispor de "suportes e imobilizadores adequados ao tratamento realizado" | [RDC-20-2006 p. 6], 5.5.9, a4 |
| Na simulação, a imobilização é feita da mesma forma com que o paciente será tratado | [RDC-20-2006 p. 10], 9.5, d) |
| A oficina que confecciona moldes e máscaras de imobilização tem dispositivos de segurança próprios; o serviço pode contratar com terceiros o fornecimento desses dispositivos | [RDC-20-2006 p. 10], 9.6, a) e b) |
| Na CEL, confeccionar máscaras termoplásticas, VacLok, rampas e apoios é do dosimetrista | [PPR-CLINICA p. 22], seção 4 |
| No POP do CLINICA, a máscara é moldada pelo dosimetrista e o paciente segue para a simulação "já de posse de sua máscara"; o POP não fala em etiqueta, reuso nem contagem | [POP-021 p. 1], item 4 |
| Na sala, o contato da máscara com a pele é conferido todo dia; folga acima de 0,5 cm (ou 1,0 cm unilateral, na laringe) chama o físico para avaliar máscara, tomografia e planejamento novos | [POP-036 p. 1], item 4, 3 |

Que sistema ou planilha guarda hoje as etiquetas e os usos, **a base não
responde**. Se cada clínica tem prateleira e oficina próprias, também não.
O limite de 20 usos não tem fonte na base.

| opção | fonte | o que muda adiante |
|---|---|---|
| importar do "outro sistema" que o código menciona | `inventario.py:20-23`, `:82`, `:100` | precisa de alguém que diga qual sistema e entregue o arquivo; os campos dele têm de casar com os do `Item` (`inventario.py:70-79`); a migração (CAP-10) importa uma vez, e a partir do corte só o banco grava (AD-37) |
| levantamento na prateleira, lançado pelo dosimetrista ou pelo técnico | CAP-8 ("fonte: lançamento do dosimetrista ou técnico"); `inventario.py:16-18` | não depende de outro sistema; o número de usos de cada máscara já em uso não é conhecido; o código de hoje transforma uso vazio ou ilegível em 0 (`inventario.py:81-88`), o que cruza com a regra "nunca inventar dado" e cala o aviso dos 20 para essas máscaras |
| inventário **por clínica** | AD-12 (tabela "de clínica", coluna `clinica` e RLS) | cada clínica vê só o próprio; o nome e o registro do paciente no item (`inventario.py:75-76`) ficam sob RLS, como o resto do dado de paciente |
| inventário **global** | AD-12 (tabela "global", sem coluna de clínica e sem RLS) | uma prateleira só para as três; o item carrega nome e registro de paciente (`inventario.py:75-76`) numa tabela sem RLS, e o AD-26 pede que o vínculo vá pela chave canônica, que já tem a clínica |

As duas primeiras respondem "de onde vem"; as duas últimas, "por clínica".
A resposta é um par. Em qualquer origem, o código de hoje grava 0 onde o
número de usos vier vazio (`inventario.py:81-88`).

**Destrava:** R-53 (a tabela do inventário e a migração dele, CAP-8 e
CAP-10); R-55 (o relatório de migração conferido, CAP-12).

resposta do físico: (26/10/2026) **Aplicação, na sessão, da regra que o físico fixou** (referência; havendo duas ou mais, a mais restritiva; sem base, a mais conservadora, provisória e levada à discussão no serviço). **A conferir pelo físico.** **Inventário por clínica** (o item carrega paciente: tabela de clínica com RLS, AD-12), **levantado na prateleira** pelo dosimetrista ou técnico. Número de usos desconhecido nasce **vazio, nunca 0** (o código de hoje grava 0: muda na R-53), e a máscara com usos desconhecidos aparece com aviso. Discussão: o limite de 20 usos (sem fonte) e qual é o "outro sistema" que o código cita.

---

## Notas de posicionamento: biblioteca global ou por clínica

**Pergunta.** A biblioteca de notas de posicionamento é uma só para o
serviço ou uma por clínica?

**Estado hoje.** A spec diz que "a biblioteca de notas (39 modelos) e o
inventário ... vivem no banco" (CAP-8) e deixa em aberto se ela é global. No código, a biblioteca mistura
dois tipos de nota: o **modelo** do acervo, compartilhado, e a nota criada
**para um paciente**, que "aparece no fim da lista e pode ser apagada"
(`isocentro/dados/notas_setup.py:71-73`). Ela nasce do acervo `.docx` em
`TCs_Teste/Posicionamento/NOTAS DE POSICIONAMENTO` ou de uma pasta
`notas_posicionamento` (`notas_setup.py:57-62`) e, sem acervo, da semente
empacotada `assets/notas_modelo.json` (`notas_setup.py:24-26`, `:121-129`). O
arquivo de trabalho fica na pasta do app ou em `ISOCENTRO_NOTAS_DIR`
(`notas_setup.py:95-97`). A nota aplicada vira o setup que a Capa imprime
(acessórios e preparo, `notas_setup.py:82-86`).

**O que a base diz.**

| fato | fonte |
|---|---|
| Na simulação, a imobilização é feita da mesma forma com que o paciente será tratado | [RDC-20-2006 p. 10], 9.5, d) |
| No POP do CLINICA, a forma de posicionar é definida pelo radioterapeuta na consulta, e o físico orienta a equipe técnica ao fim do planejamento | [POP-019 p. 1], itens 1 e 9 |

De que clínica é o acervo `.docx` que semeou a biblioteca, e se as três
usam o mesmo vocabulário de notas, **a base não responde**.

| opção | fonte | o que muda adiante |
|---|---|---|
| global | AD-12 (tabela "global", sem RLS) | um acervo só para as três clínicas; a nota criada para um paciente (`notas_setup.py:71-73`) fica visível nas três |
| por clínica | AD-12 (tabela "de clínica") | cada clínica mantém o seu acervo; os 39 modelos de hoje entram numa clínica, e as outras duas começam do quê é parte da resposta |
| modelos globais, notas do paciente por clínica | AD-12; `notas_setup.py:71-73` (o campo `modelo` já separa os dois tipos) | duas tabelas no lugar de uma; o modelo é editado por quem, e vale para as três, é parte da resposta |

A `Nota` não tem campo que identifique o paciente: só nome, acessórios,
preparo e a marca `modelo` (`notas_setup.py:66-73`). Se o nome ou o texto
das notas criadas para um paciente trazem dado dele, a base não responde.

A spec diz "39 modelos"; o docstring do código diz "umas quarenta notas"
(`notas_setup.py:3`). Quantas estão na biblioteca real de cada clínica, a
base não responde.

**Destrava:** R-53 (a tabela das notas e a migração dela, CAP-8 e CAP-10);
R-55 (o relatório de migração conferido, CAP-12).

resposta do físico: (26/10/2026) **Aplicação, na sessão, da regra que o físico fixou** (referência; havendo duas ou mais, a mais restritiva; sem base, a mais conservadora, provisória e levada à discussão no serviço). **A conferir pelo físico.** **Modelos globais, notas do paciente por clínica** (nota de paciente fica sob RLS, AD-12). Discussão: quem edita os modelos e se as três clínicas usam o mesmo vocabulário.

---

## Vínculo pendente: prazo para um vínculo que nunca liga

**Pergunta.** Quanto tempo um registro com vínculo `pendente` (REG sem `Ser`
no `variandw`) pode ficar sem ligar antes de exigir alguma providência, e
qual é essa providência?

**Estado hoje.** A CAP-5 grava o registro com o apelido REG e vínculo
`pendente`, e liga sozinho "quando o `Ser` aparecer pelo mesmo
`PatientId`", com entrada no log; os pendentes "aparecem numa lista para o
físico", e o PDF sai normalmente. A spec não dá prazo, nem diz o que
acontece com um pendente que nunca liga ("paciente que não entra no ARIA",
Open Questions). O AD-26 manda guardar só a chave canônica (`Ser` +
clínica), com REG e `PatientId` como apelidos; o AD-5 proíbe apagar e
editar registro. Entre as linhas de risco que a spec manda o físico avaliar
está "vínculo ligado ao paciente errado" (Open Questions, `riscos.md`).

**O que a base diz.**

| fato | fonte |
|---|---|
| Os filmes de simulação levam nome do paciente, número do prontuário e data | [RDC-20-2006 p. 10], 9.5, c) |

É só isso: sobre identidade entre sistemas, a base não tem mais nada. O
papel continua identificando o paciente por nome e prontuário, independente
do vínculo (CAP-5: "o PDF sai normalmente"). Fora da base: o PRD deixa a
unidade SAT (Synergy01, Monaco) fora do MVP (§2.2 e §14.1), e o programa já
monta ficha de caso Elekta/Monaco (`tools/caso.py Elekta`, no `CLAUDE.md`);
se esses pacientes entram no `variandw`, e portanto se ligam algum dia,
**a base não responde**. Um prazo em dias, **a base não responde**: a única
validade em dias que a espinha fixa é a do espelho (60 dias, AD-17), que é
cache e não identidade.

| opção | fonte | o que muda adiante |
|---|---|---|
| sem prazo: o pendente fica na lista do físico até ligar | CAP-5, como está escrita | nada vence; a lista cresce com todo paciente que nunca entra no ARIA, e a spec não diz como ele sai dela; pelo AD-5, sair da lista não pode ser apagar o registro |

A base não traz outra opção com fonte. Um prazo fixo, um aviso que acende
depois de N dias, ou a ligação feita à mão pelo físico (que a CAP-5 não
prevê, e que cruza com o risco "vínculo ligado ao paciente errado")
precisariam de uma fonte ou de uma decisão que a base não tem.

**Destrava:** R-53 (o vínculo pendente que liga pelo `PatientId`, CAP-5);
R-55 (os casos de vínculo pendente no relatório de validação, CAP-12).

resposta do físico: (26/10/2026) **Aplicação, na sessão, da regra que o físico fixou** (referência; havendo duas ou mais, a mais restritiva; sem base, a mais conservadora, provisória e levada à discussão no serviço). **A conferir pelo físico.** **Sem prazo**: o pendente fica na lista do físico até ligar (CAP-5), sem ligação à mão e sem apagar (AD-5). Discussão: prazo e providência para o pendente que nunca liga.

---

## Raízes do share para a varredura das fichas antigas

**Pergunta.** Quais pastas, em cada uma das três clínicas, a varredura única
das fichas antigas tem de percorrer no corte do registro?

**Estado hoje.** A CAP-10 manda a varredura única das `FICHA_*.json` das
pastas dos pacientes, "com relatório do que entrou, do que não entrou e por
quê; as pastas não são alteradas". No código:

- a ficha é gravada na pasta de onde o caso foi aberto (`pasta_carregada`,
  `isocentro/interface/controle_ficha.py:746`, `:770-774`), que pode ser
  qualquer pasta da estação;
- a ficha liberada da pasta temporária vai para a pasta do cadastro de
  simulação, dentro da raiz das simulações, e, sem cadastro, para a pasta
  que a pessoa escolher (`isocentro/interface/gui.py:1036-1076`);
- a raiz das simulações vem da escolha da sessão, de `ISOCENTRO_SIMULACOES`,
  do `config_servico.json` (`RAIZ_SIMULACOES`) ou, sem nada disso, de
  `Documentos\Simulacoes` do usuário da estação
  (`isocentro/interface/simulacao.py:72-93`);
- depois de arquivada, a ficha pode existir só **dentro** de
  `ARQUIVOS_*.zip`, e a reindexação de hoje varre os dois
  (`isocentro/dados/indice.py:375-400`, `:428-453`);
- a reindexação manual pede a raiz numa caixa de diálogo e grava no
  `historico_uso` um evento `reindexacao` com a raiz usada
  (`isocentro/interface/busca_ficha.py:411-428`);
- o índice central `registro_fichas.json` é lido por todas as estações
  (`isocentro/dados/indice.py:32-38`) e guarda o caminho (`json_path`) de
  cada versão indexada (`indice.py:229-261`); para a ficha que só existe no
  zip, esse caminho é o do JSON solto que não está no disco
  (`indice.py:376-392`).

**O que a base diz.** Nada: quais compartilhamentos existem em cada clínica
e onde ficam as pastas dos pacientes não estão na base de conhecimento, e o
`config_servico.json` de cada clínica não está nesta máquina. Quais são as
raízes, **a base não responde**.

As opções abaixo são de onde a lista de raízes pode sair; podem se combinar.

| opção | fonte | o que muda adiante |
|---|---|---|
| a raiz das simulações de cada clínica | `simulacao.py:72-93`; `gui.py:1036-1060` | cobre as fichas liberadas para a pasta do cadastro; não cobre a ficha gravada onde o caso foi aberto, nem a estação que caiu no padrão `Documentos\Simulacoes` local, fora do share |
| as pastas que o índice central já conhece | `registro_fichas.json` (`indice.py:229-261`) | cobre o que foi indexado; não cobre ficha gerada antes do índice, nem estação que gravou num índice de outra pasta do app; a entrada de ficha zipada aponta para um JSON que não está no disco (`indice.py:376-392`) |
| as raízes já usadas na reindexação manual | `historico_uso` (`busca_ficha.py:428`) | mostra onde alguém já mandou reindexar; cobre tanto quanto o histórico de cada clínica |
| as pastas apontadas pelo físico ou pela TI de cada clínica | CAP-10; R-55 (`classe: clinica`) | depende de quem conhece os compartilhamentos; não sai do código nem do índice |

A CAP-10 fala só em `FICHA_*.json`. Se a varredura inclui o JSON que só
existe dentro do `ARQUIVOS_*.zip` (`indice.py:375-400`), a spec não diz; a
reindexação de hoje inclui.

**Destrava:** R-55 (a varredura nas três clínicas e o relatório do que
entrou e do que não entrou, CAP-10 e CAP-12). A R-53 migra as outras
entidades e não depende desta resposta.

resposta do físico: (26/10/2026) **Aplicação, na sessão, da regra que o físico fixou** (referência; havendo duas ou mais, a mais restritiva; sem base, a mais conservadora, provisória e levada à discussão no serviço). **A conferir pelo físico.** **A união de todas as fontes**: raiz das simulações de cada clínica, pastas do índice central, raízes do `historico_uso` e as que a TI apontar, **incluindo** o JSON que só existe dentro do `ARQUIVOS_*.zip`. As raízes reais vêm da TI de cada clínica (R-55).
