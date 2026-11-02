---
id: SPEC-isocentro-plano
companions:
  - ../spec-isocentro-fundacao/SPEC.md
  - ../architecture-isocentro-2026-10-19/ARCHITECTURE-SPINE.md
  - ../prd-isocentro-2026-10-16/prd.md
  - ../ux-isocentro-2026-10-16/EXPERIENCE.md
  - ../ux-isocentro-2026-10-16/DESIGN.md
  - ../decisoes-sem-base.md
  - rastreabilidade.md
sources:
  - ../../questionarios/plano.md
---

> **Contrato canônico.** Esta SPEC e os arquivos em `companions:` são o contrato completo do módulo Plano. Ela é construída **sobre a Fundação** (motor, log, alerta, assinatura, sombra, erro semeado, degraus): nada aqui reinventa o núcleo. A espinha (`AD-n`) é obrigatória, exceto o AD-35, que não vale mais para o Plano (classe A). Do PRD valem §5, §6, §12.2 e §13 (SM-1, SM-2, SM-9). Da UX valem UJ-1, UJ-2 e ML 30. Onde esta spec diverge do PRD (P3, P4, U1, NFR-5, P7, P8), vale esta spec. Atualizada em 26/10/2026 com as respostas do físico ao questionário (R-27).

# ISOCENTRO — Módulo Plano

## Why

A NN-6.10 exige um segundo sistema de cálculo (art. 15, XI, e) e a segunda assinatura por conferência (art. 17, IV). A RDC 20/2006 (9.7 c) manda verificar até a 3ª fração ou 10% da dose. Hoje o `paralelo.py` só tem tabelas de exemplo (`ELEKTA_SAT`): todo resultado sai como "demonstração" e não há cálculo para IMRT/VMAT. As listas votadas pelo serviço (Planejamento, Aprovação Física, Duplo Check) vivem em papel, e ninguém mede se o Duplo Check foi feito por outro físico dentro do prazo. O módulo Plano mede e alerta a partir do dado real das quatro máquinas Varian (TrueBeam e 6EX na CEL, 600CD na BET, VitalBeam na DUO), sem impor ordem e sem bloquear.

## Capabilities

Cada capacidade diz de onde vem o dado (**fonte**) e se muda o que sai impresso (**papel**). Nenhuma capacidade desta spec muda o papel. Toda verificação tem id `plano.<nome>`, nasce em sombra e entra na bateria de erro semeado da Fundação.

### Segunda checagem de cálculo (MVP 1)

- **CAP-1 — Tabelas de feixe por máquina e energia** (FR-10)
  - **intent:** O físico cadastra a tabela de feixe de cada máquina e energia a partir do comissionamento, com o registro da conversão.
  - **success:** Cada tabela tem máquina, energia, origem (relatório e data: TrueBeam e 6EX DOSEMED 2020; VitalBeam 2020; 600CD 2010), quem converteu e quando, e o resultado da validação contra pontos do relatório original. Também tem quem atesta que ela ainda representa a máquina. Os nomes DICOM são cadastrados um a um. 6FFF e 10FFF da TrueBeam e 6FFF da VitalBeam têm tabela própria. Filtros físicos ficam "sem tabela": estão comissionados, mas não são usados na rotina. Para modulado, a tabela traz transmissão do MLC e DLG com origem.
  - **fonte · papel:** `Documents/isocentro/comissionamento/` · não muda.

- **CAP-2 — Disparo da segunda checagem** (FR-11, AD-28, AD-30)
  - **intent:** A segunda checagem roda sozinha quando o plano entra em `Planning Approved` e fica pronta antes da fila de Aprovação Física.
  - **success:** A concentradora lê `Planning Approved` no `variandw`, busca o RT Plan por C-MOVE e confere se o `SOPInstanceUID` do arquivo é o do registro. Sem RT Plan ou com UID divergente, o resultado é `indeterminado` com alerta (nunca deixa de rodar em silêncio). Plano novo ou modificado gera nova execução, com prazo contado do plano novo; a anterior fica no log e deixa de valer. O critério de tempo é este: pronto antes de o plano aparecer na fila de Aprovação Física, sem número fixo de segundos (NFR-5 reescrito).
  - **fonte · papel:** `variandw` (status e UID) e RT Plan DICOM · não muda.

- **CAP-3 — Segunda checagem 3D por ponto** (FR-12)
  - **intent:** O físico vê a diferença calculado × TPS por campo e no composto, com o limite aplicado e a origem dele.
  - **success:** O cálculo é o TMR × Scp do `paralelo.py`. Os limites são os do TG-114 (Tab. II p. 8, 2% / 3,5% / 5% conforme geometria e heterogeneidade), exibidos com "origem: literatura, não derivado do serviço". `nao_conforme` contra limite de literatura é alerta, não reprovação. Trocar o ponto de cálculo gera nova execução, e as duas ficam no log. Os limites antigos do código (3%/5%, 10%/20%) não existem mais.
  - **fonte · papel:** RT Plan + tabela da máquina (CAP-1) · não muda (P10: nenhum PDF mostra o paralelo).

- **CAP-4 — Segunda checagem de modulado por Clarkson por ponto de controle** (P3, FR-12)
  - **intent:** Plano IMRT/VMAT recebe segunda checagem de dose no ponto, somando a contribuição de cada ponto de controle pela abertura do MLC.
  - **success:** A aceitação é pelo composto TG-219 (p. 17): 3% homogêneo / 5% heterogêneo. Campo único: 5% / 7%. Baixa dose ou alto gradiente: 5–10% (Tab. 9 p. 12). Todos com origem citada. O método usa transmissão do MLC e DLG da tabela (CAP-1). Enquanto a máquina não tiver comissionamento de modulado aprovado (CAP-6), o resultado é `indeterminado` com motivo. A SM-9 mede a fração de execuções `indeterminado` por motivo.
  - **fonte · papel:** RT Plan (pontos de controle, `CumulativeMetersetWeight`, lâminas) + tabela da máquina · não muda.

- **CAP-5 — Fora do alcance do cálculo** (FR-13)
  - **intent:** Plano que o cálculo não sabe tratar sai `indeterminado` com o motivo, nunca `conforme`.
  - **success:** Máquina sem tabela → "máquina sem tabela de feixe". Campo com filtro físico → "o cálculo não trata filtro". Técnica não tratada → motivo nomeado. O resultado `demonstracao` deixa de existir.
  - **fonte · papel:** RT Plan + cadastro de tabelas · não muda.

- **CAP-6 — Comissionamento do cálculo por máquina** (FR-14)
  - **intent:** O físico registra e aprova o comissionamento da segunda checagem em cada máquina antes de ela dar veredito.
  - **success:** No 3D, pontos da Tab. 8 do TG-219; no modulado, casos TG-119 (no acervo); ambos medido × calculado. Sem conversão validada (CAP-1) e comissionamento aprovado, o valor calculado aparece sem veredito, como `indeterminado` com o motivo "cálculo não comissionado para esta máquina". O relatório de comissionamento entra na validação do módulo (CAP-17).
  - **fonte · papel:** medidas de comissionamento registradas pelo físico · não muda.

- **CAP-7 — Prazo da segunda checagem** (FR-15, P5)
  - **intent:** O ISOCENTRO acompanha, por plano, se a segunda checagem foi feita e conferida dentro do prazo de verificação.
  - **success:**
    - Plano sem segunda checagem conferida gera alerta `alta` ao atingir a 3ª fração ou 10% da dose, o que vier primeiro; no alto risco (CAP-10), antes da 1ª fração.
    - A dose acumulada é a registrada no ARIA. Os 10% são calculados sobre o curso e sobre a fase; o alerta dispara pelo que vencer primeiro e diz qual venceu (provisório).
    - Curso sem `LISTA_VERIFICADA_EM` mostra o aviso "contagem de frações não conferida contra o ARIA" (a R-07 fecha antes do MVP 2; o aviso fica como rede de segurança).
    - Teste: prazo vencido com o app fechado aparece na abertura seguinte.
  - **fonte · papel:** tratamento entregue no `variandw` · não muda.

- **CAP-8 — Índices de qualidade do plano** (U1)
  - **intent:** Os índices de qualidade e de complexidade da aba Qualidade passam do Radioteraficha para o Plano como verificações do módulo.
  - **success:** São verificações `plano.*` para conformidade, gradiente, HI (ICRU 83), MCSv, SAS e UM/cGy. Cada tolerância tem origem de literatura e é marcada provisória até a derivação TG-218. "Fora da faixa" é alerta, nunca reprovação. A aba sai do Radioteraficha, e a tela Virtual não vem junto.
  - **fonte · papel:** RT Plan, RT Dose e RT Struct (DICOM) · não muda.

### Revisão com segunda assinatura e sequência real (MVP 2)

A R-07 (165 cursos conferidos contra o ARIA) é condição de entrada do MVP 2.

- **CAP-9 — Sequência real do plano** (FR-16)
  - **intent:** O ISOCENTRO lê do `variandw`, por plano, as datas de aprovação médica, PSQA, Treatment Approved, Duplo Check e 1ª fração.
  - **success:** Cada data mostra tabela, campo e degrau. Data não encontrada nasce vazia e a tela diz que falta; nunca é inferida de outra. O Duplo Check tem duas fontes, a assinatura no ISOCENTRO (CAP-15) e a atividade do Carepath. Se só uma existe, ou se as datas diferem, o resultado é alerta `atencao`, e a mudança de data no `variandw` é mostrada.
  - **fonte · papel:** `variandw` (códigos das atividades: P6) · não muda.

- **CAP-10 — Marcação de alto risco** (FR-18, P8)
  - **intent:** O caso de alto risco é marcado a partir do dado, e o físico completa à mão o que o ARIA não tem.
  - **success:**
    - É alto risco, o que disparar primeiro: dose por fração ≥ 6 Gy, nº de frações ≤ 5 ou curso em menos de 6 dias (TG-101 p. 3; TG-275 p. 4 e p. 14). O critério é provisório (faixa de 3 a 6 Gy sem base).
    - A duração vem do agendamento. Sem agendamento, o critério de duração fica "não informado".
    - Reirradiação (ou campo adjacente) e dispositivo implantado nascem "não informado".
    - Enquanto qualquer critério estiver "não informado", o prazo é antes da 1ª fração, com o alerta "alto risco não avaliado". A marcação manual grava quem e quando.
  - **fonte · papel:** prescrição e agendamento no `variandw` + marcação do físico · não muda.

- **CAP-11 — Filas de Aprovação Física e Duplo Check** (FR-17, ML 30)
  - **intent:** O físico vê as filas de planos sem Aprovação Física e sem Duplo Check, ordenadas pelo prazo.
  - **success:** Plano sem Duplo Check gera alerta `alta` no prazo. Caso de alto risco tratado sem Duplo Check gera alerta `alta` na 1ª fração. Plano já tratado sem Duplo Check aparece com a contagem de frações (e o aviso da CAP-7 quando o curso não tem `LISTA_VERIFICADA_EM`). Os contadores da Zona 1 ("3 ▲1") abrem o Plano filtrado pela clínica e pela fila.
  - **fonte · papel:** sequência real (CAP-9) e assinaturas · não muda.

- **CAP-12 — Lista de Planejamento** (FR-42)
  - **intent:** O dosimetrista confere o plano pelos 13 itens votados da etapa Planejamento, antes da aprovação médica.
  - **success:** Os 13 itens são os do `lista-verificacao-carepath.csv`. Os automáticos seguem a regra da CAP-13. A conferência grava quem e quando e não conta como segunda assinatura.
  - **fonte · papel:** `conhecimento/servico/lista-verificacao-carepath.csv`, RT Plan e `variandw` · não muda.

- **CAP-13 — Listas da Aprovação Física e do Duplo Check** (FR-19, P7)
  - **intent:** O físico confere o plano pela lista votada da etapa (8 itens na Aprovação Física, 8 no Duplo Check), com os itens automáticos já preenchidos.
  - **success:** Cada item automático mostra o valor lido, a fonte, a referência e a fonte da referência; o físico confirma ou contesta. Item sem referência nasce vazio, nunca `conforme`. Os automáticos são:
    - dose diária e total × prescrição, nas duas etapas;
    - máquina correta, nas duas etapas: a máquina da prescrição e a do agendamento são iguais entre si e à do RT Plan (provisório);
    - UM compatíveis, pela segunda checagem;
    - cursos anteriores abertos (status diferente de concluído; provisório), na Aprovação Física;
    - isocentro, no Duplo Check, em quatro conferências: (1) todos os campos, de tratamento e de setup, com o mesmo `IsocenterPosition`; (2) isocentro − marcador TP0 do RT Struct = deslocamentos de setup do RT Plan; (3) isocentro de cada fase = o da fase anterior no mesmo `FrameOfReferenceUID`, com divergência sinalizada para o físico confirmar (boost em outro ponto existe); (4) isocentro dentro do BODY. Sem tolerância em mm definida, (1)–(3) medem e mostram, sem veredito;
    - os itens "++" com "F" da Tab. S1.A.ii do TG-275 (p. 21), como verificações `plano.*` em sombra, cada um com referência e erro semeado.

    Os quatro itens removidos por maioria na Aprovação Física não entram. O resultado da segunda checagem é item das duas listas, e `nao_conforme` ou `indeterminado` pede justificativa sem bloquear.
  - **fonte · papel:** `lista-verificacao-carepath.csv`, RT Plan, RT Struct, `variandw` (prescrição, agendamento, cursos), segunda checagem · não muda.

- **CAP-14 — Conferência prescrição × RT Plan** (FR-21)
  - **intent:** Na etapa de Planejamento, o ISOCENTRO confronta a prescrição do ARIA com o RT Plan.
  - **success:** Dose total, dose por fração, nº de frações, energia e técnica divergentes → `nao_conforme` com os dois valores e as duas fontes. Energia e técnica casam pela tabela de equivalência cadastrada (ex.: "6X" ↔ "06 MV"); valor sem equivalência → `indeterminado`. Gravidez, tratamento anterior, dispositivo implantado e consentimento (RDC 20, 9.1) entram como registro manual, nascendo vazios.
  - **fonte · papel:** prescrição no `variandw` (`DWH.DimPrescription`) e RT Plan · não muda.

- **CAP-15 — Segunda assinatura do Duplo Check** (FR-20, AD-13, AD-30, P9)
  - **intent:** O físico do Duplo Check assina no ISOCENTRO ao concluir a lista, e o sistema confere que ele não é quem deu a Aprovação Física.
  - **success:**
    - Se quem assina é o autor do Treatment Approved (lido do ARIA) ou da Aprovação Física no ISOCENTRO, a assinatura não é registrada como Duplo Check, e o botão nunca esteve desabilitado.
    - Sem mapeamento ARIA ↔ ISOCENTRO, ou no degrau de reserva sem o autor, a assinatura é gravada com a marca "separação entre os físicos não conferida" e gera alerta `alta`.
    - A assinatura do Duplo Check e a da Aprovação Física voltam a pendente em quatro casos: UID novo com conteúdo igual, mudança de status no ARIA, conteúdo do RT Plan mudado sem UID novo, mudança menor (campo de setup, nome de campo). O terceiro caso exige detectar mudança de conteúdo além do UID (provisório).
    - Nada é gravado no ARIA.
  - **fonte · papel:** sessão do ISOCENTRO, autor do Treatment Approved no `variandw`, tabela de vínculo, RT Plan · não muda (P11).

- **CAP-16 — Módulo Plano no shell** (FR-9, AD-18, UJ-1, UJ-2)
  - **intent:** Físico e dosimetrista trabalham o plano numa tela do módulo: filas, caso com segunda checagem, índices, listas e assinatura.
  - **success:** O módulo abre do cartão da doca, do contador da Zona 1 ou da linha da Zona 2, já no caso ou na fila filtrada. Toda leitura demorada (`variandw`, DICOM, cálculo) roda em segundo plano, com "carregando", degrau e data. O acesso e as ações seguem a tabela perfil → capacidades da Fundação, configurável pelo admin; o valor inicial é físico (Aprovação Física, Duplo Check, cadastros), dosimetrista (segunda checagem, Lista de Planejamento) e médico (vê se o plano passou pelas conferências). Nenhuma configuração deixa outro perfil assinar a Aprovação Física ou o Duplo Check. UJ-1 e UJ-2 rodam de ponta a ponta em homologação.
  - **fonte · papel:** fachada de consulta do Plano; tabela de capacidades no banco · não muda.

- **CAP-17 — Validação do módulo Plano** (FR-6, FR-14, FR-40)
  - **intent:** O módulo tem relatório de validação antes do primeiro uso real.
  - **success:** O relatório traz, por verificação `plano.*`, a sensibilidade semeada. Os casos incluem RT Plan com UID trocado, conteúdo alterado sem UID novo, máquina trocada, dose × prescrição divergente e Duplo Check pelo mesmo físico. Traz também o comissionamento por máquina (CAP-6) e casos conferidos à mão. Fica guardado 10 anos após o descarte, e é refeito após upgrade do ARIA ou do Eclipse.
  - **fonte · papel:** execuções, comissionamento e testes · não muda.

- **CAP-18 — Catálogo MPPG 11.a** (P7)
  - **intent:** Os 160 itens nível 2 do MPPG 11.a (revisão de plano e prontuário) ficam disponíveis no Plano como catálogo de referência, sem mudar as listas votadas.
  - **success:**
    - O catálogo tem cada item com tabela, item e etapa: revisão inicial EBRT (Tab. 8–9), semanal (Tab. 10), fim de tratamento (Tab. 11) e HDR (Tab. 13–14).
    - O item automatizável vira verificação `plano.*` em sombra até a conferência linha a linha pelo físico.
    - O item manual aparece como opcional na lista da etapa, nascendo vazio.
    - As listas votadas (CAP-12, CAP-13) não ganham nem perdem item.
  - **fonte · papel:** `itens-nivel2.csv` (pesquisa de tabelas de protocolo, lote 5) e [MPPG-11a] · não muda.

- **CAP-19 — Seções do PPR do Plano** (PPR vivo, Documentação CAP-10)
  - **intent:** Os capítulos do PPR sobre o que este módulo conhece moram aqui, com dado e texto.
  - **success:** Sistemas de planejamento (TPS, versão e algoritmo, com o inventário de `modulos/software`); técnicas de tratamento oferecidas por máquina. Seção do PPR = dado vivo lido do próprio módulo + texto versionado do módulo, exposto pela fachada (Documentação CAP-10); texto com versão, autor e data; dado sem fonte sai vazio. A primeira versão do texto vem do PPR vigente de cada clínica, citado.
  - **fonte · papel:** inventário de software e tabelas por máquina (CAP-1) · entra no PPR.

## Constraints

- **Construído sobre a Fundação:** gravação por `nucleo.gravar`, alerta, assinatura, sombra, erro semeado e degraus vêm do núcleo; o Plano não tem log, alerta nem assinatura próprios (AD-3, AD-27, AD-29, AD-30).
- **Advisory:** nenhum resultado bloqueia Aprovação Física, Duplo Check ou tratamento; a trava é a do ARIA.
- **Somente leitura** no ARIA, `variandw` e Eclipse; nenhum script ESAPI gravável nesta spec (AD-16, NFR-1).
- **Máquina certa:** a tabela é escolhida pelo nome DICOM cadastrado exato, nunca por parecença (`TrueBeamSN1001` = VitalBeam; `TBuniverSN1002` = TrueBeam). Sem tabela, não há veredito.
- **Tolerância com origem:** todo limite cita TG-114, TG-219 ou a referência da literatura e diz "não derivado do serviço" até a derivação TG-218; `nao_conforme` contra literatura é alerta. Sem tolerância, mede e mostra sem veredito.
- **Campo sem fonte nasce vazio:** nenhuma data, referência ou valor inferido de outro (NFR-4).
- **Decisões provisórias:** as escolhas dos itens #2 a #8 do `decisoes-sem-base.md` valem até a discussão no serviço, e a tela diz "provisório" onde elas decidem.
- **Escopo de máquinas:** TrueBeam, 6EX, 600CD e VitalBeam; Synergy01 (SAT) fora.
- **Classe A** da IEC 62304 (`classificacao-62304.md`, 26/10/2026): a trava do ARIA e a assinatura em papel contam como medida externa. ANVISA classe I ou II até todos os testes. O AD-35 não vale para o Plano.
- **Papel não muda:** a segunda assinatura em papel (art. 17, IV) continua como hoje.
- **Identidade pela chave canônica** (`Ser` + clínica); usuário ARIA ↔ ISOCENTRO só pela tabela de vínculo (AD-13, AD-26).

## Non-goals

- Recálculo de dose 2D/3D próprio; a segunda checagem é por ponto.
- Resultado do PSQA dentro do ISOCENTRO: o MVP lê só a data do PSQA (SM-8).
- Tela Virtual (fica fora do Plano; U1) e redesenho das demais telas do Radioteraficha.
- Gravar no ARIA, inclusive a data do Duplo Check; substituir a assinatura do papel.
- Segunda checagem com filtro físico (fora da rotina).
- Synergy01/SAT, IORT; cálculo e CQ da braquiterapia HDR (MVP 3). Os itens de revisão de plano HDR do MPPG 11.a entram só como catálogo (CAP-18).
- Avaliador ESAPI em C# para o Plano: os índices e o cálculo rodam em Python sobre DICOM.
- Derivação local das tolerâncias (TG-218): é frente própria (R-10).

## Success signal

- Em homologação, um plano 3D e um VMAT reais de cada uma das quatro máquinas, com comissionamento aprovado: ao dar `Planning Approved`, a segunda checagem sai pronta antes da fila de Aprovação Física, com limite e origem. A Aprovação Física e o Duplo Check são feitos por físicos diferentes, e a fila e o contador da Zona 1 caem. Um Duplo Check tentado pelo mesmo físico não é registrado, e um plano alterado depois da assinatura, com ou sem UID novo, volta à fila.
- A bateria semeada da CAP-17 detecta cada erro plantado e o relatório de validação do Plano está assinado pelo físico antes do primeiro uso real.
- SM-1 e SM-2 medidos desde o primeiro mês de uso; SM-9 publicada por motivo.

## Assumptions

- **FR-11:** "junto do PSQA" significa disparo na aprovação médica, sem depender do PSQA.
- **FR-16:** PSQA e Duplo Check são lidos como atividades do Carepath; a assinatura no ISOCENTRO é o registro do Duplo Check.
- **P11:** a assinatura registrada convive com a do papel; substituir seria mudança no papel, com aviso.
- **MPPG 11.a manual:** os itens HDR, semanais e de fim de tratamento entram como manuais até haver leitura que os automatize; o Plano lê só RT Plan de teleterapia e não tem etapa semanal nem de fim de tratamento.

## Open Questions

- **P6 [bloqueia MVP 2]:** códigos reais das atividades PSQA, Aprovação Física e Duplo Check no `variandw` (frente `clinica`).
- **Clarkson por ponto de controle:** fonte das medidas de transmissão do MLC e DLG por máquina (o comissionamento atual traz?), e tratamento de arco (amostragem angular).
- **Etapas semanal e fim de tratamento** (CAP-18): onde aparecem — fila própria do Plano, caso do plano ou módulo Tratamento?
- **G2:** se a contagem usar o `dominio/ritmo`, a classe A dele continua valendo?
- **riscos.md:** linhas para os modos de falha do §12.2 do Plano (S, O, D pelo físico) antes do 1º épico.
