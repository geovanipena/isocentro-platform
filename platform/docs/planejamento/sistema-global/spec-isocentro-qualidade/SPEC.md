---
id: SPEC-isocentro-qualidade
companions:
  - ../spec-isocentro-fundacao/SPEC.md
  - ../architecture-isocentro-2026-10-19/ARCHITECTURE-SPINE.md
  - ../prd-isocentro-2026-10-16/prd.md
  - ../ux-isocentro-2026-10-16/EXPERIENCE.md
  - ../ux-isocentro-2026-10-16/DESIGN.md
  - ../decisoes-sem-base.md
  - rastreabilidade.md
sources:
  - ../../questionarios/gq.md
---

> **Contrato canônico.** Esta SPEC e os arquivos em `companions:` são o contrato completo do módulo Garantia da Qualidade (`modulos/qualidade`). Ela é construída **sobre a Fundação** (motor, log, alerta, sombra, erro semeado, exportador, backup): nada aqui reinventa o núcleo. A espinha (`AD-n`) é obrigatória. Do PRD valem §7, §12.2 e §13 (SM-3). Da UX valem UJ-3 e o sinal de máquina. Onde esta spec diverge do PRD (C1, itens nível 2, TRS-398 calculado, pylinac no MVP, k_Q de 2000), vale esta spec. Atualizada em 26/10/2026 com as respostas do físico ao questionário (R-37).

# ISOCENTRO — Módulo Garantia da Qualidade

## Why

A NN-6.10 exige um programa de CQ executado e registrado (art. 35) e cópia de segurança independente dos registros (art. 71, IX). A RDC 20/2006 (8.1 b) manda guardar os registros pela vida útil do equipamento. Hoje o programa existe só na base (`programa-cq.csv`, 103 testes, e `qualidade.json` por clínica), sem execução registrada, sem alerta de teste vencido nem de valor fora da tolerância. A calibração TRS-398 vive em planilha avulsa. O módulo transforma o programa em testes por máquina, registra cada execução com instrumento e autor, calcula o resultado e alerta no mesmo dia.

## Capabilities

Cada capacidade diz de onde vem o dado (**fonte**) e se muda o que sai impresso (**papel**). Nenhuma capacidade desta spec muda o papel do paciente. Todo teste do programa é uma verificação `qualidade.<nome>`, nasce em sombra e entra na bateria de erro semeado da Fundação.

- **CAP-1 — Programa de CQ versionado por clínica e máquina** (FR-22)
  - **intent:** O ISOCENTRO carrega, sem digitação, o programa de CQ de cada clínica e máquina, a partir da base e dos protocolos de equipamento.
  - **success:**
    - A carga junta os 103 testes do `qualidade.json` e os itens nível 2 com limite: tolerância, nível de ação ou constância, cerca de 97 de MPPG 8.b, 2.b, 9.b e TECDOC-1274.
    - Item nível 2 que vira teste fica em sombra até a conferência linha a linha contra o PDF, além do período normal; a promoção exige o registro da conferência daquele item (provisório).
    - Itens "recomendado" ou "opcional" ficam no catálogo como referência e só viram teste se o físico ativar.
    - O Dermopan (s/n 491/2097) entra na CEL com os 12 testes `orto`; os dosimétricos ficam `indeterminado` até haver câmara cadastrada com calibração em 50 kV.
    - A instância por máquina real sai do cadastro de máquina × etiquetas `aplica` (`todas`, `kv`, `epid`, `eletrons`, `fff`, `edw`, `srs`, `orto`).
    - Item repetido entre as duas fontes vira um teste com as duas referências, e só depois de o físico confirmar a fusão.
    - A versão do programa em uso é registrada, e mudar um teste é mudar a base e recarregar.
  - **fonte · papel:** `conhecimento/matriz/programa-cq.csv`, `servico/<CLÍNICA>/qualidade.json`, `itens-nivel2.csv` · não muda.

- **CAP-2 — Registro de execução** (FR-23)
  - **intent:** O técnico ou o físico registra a execução de um teste: valor, instrumento de medida, quem e quando.
  - **success:** O resultado é calculado pela tolerância, e o usuário nunca digita "conforme". O teste funcional é registrado como passa/falha, mostrando o texto da tolerância. A execução dosimétrica cita um instrumento cadastrado (CAP-6). A ação prevista e o limite de ação de cada teste moram num cadastro do banco, editado pelo físico na tela, e nascem vazios. O físico cadastra alguns exemplos antes da carga e a lista cresce com o uso. Teste sem ação continua valendo, e o cartão diz que ela falta (C2).
  - **fonte · papel:** lançamento do usuário + programa (CAP-1) + cadastro de ações · não muda.

- **CAP-3 — Fora de tolerância** (FR-23, C1, FR-41)
  - **intent:** Resultado fora da tolerância vira `nao_conforme` e chega ao físico no mesmo dia.
  - **success:** `nao_conforme` gera alerta `alta`. A máquina passa a ▲ na Zona 1, com o motivo ("CQ diário fora da tolerância"). O cartão mostra a ação prevista e o horário do 1º paciente. A repetição é uma nova execução, e as duas ficam no log. Nada bloqueia o tratamento.
  - **fonte · papel:** execuções (CAP-2) e agenda no `variandw` · não muda.

- **CAP-4 — Teste vencido sem registro** (FR-24)
  - **intent:** Teste que passa da frequência sem execução gera alerta.
  - **success:** O diário sem registro até o 1º tratamento do dia gera alerta; o teste vem da concentradora, com o app fechado. Semanais, mensais, semestrais, anuais e os de ortovoltagem viram prazos que o painel de Vencimentos lê pela fachada de consulta.
  - **fonte · papel:** programa, execuções e agenda do `variandw` · não muda.

- **CAP-5 — Carta de controle** (FR-25)
  - **intent:** O físico vê a carta de controle do output diário de cada máquina e energia.
  - **success:** A carta mostra os pontos, a tolerância com a origem e o limite de ação, este só quando cadastrado. `nao_conforme` aparece como ▲. A detecção de tendência fica fora do MVP.
  - **fonte · papel:** execuções do output diário · não muda.

- **CAP-6 — Cadastro de instrumentos de medida**
  - **intent:** O físico cadastra câmaras, eletrômetros e câmara poço com o certificado de calibração, e cada execução cita o instrumento usado.
  - **success:**
    - Cada instrumento tem modelo, número de série, laboratório, data e N_D,w (ou S_K/N_K na câmara poço) do certificado.
    - Cada tipo tem a periodicidade e a fonte:
      - sistema de referência: calibração a cada 2 anos e aferição trimestral (art. 49, III; prevalece sobre os 3 anos do TRS-398);
      - barômetro e termômetro: 2 anos; régua e nível: 5 anos (art. 52);
      - câmara poço: 2 anos e aferição trimestral (art. 54);
      - monitor de área: 2 anos (art. 55).
    - Conserto, suspeita de dano ou transporte registrados fazem a calibração ou a aferição vencer na hora (art. 49 p.ú. I, II, IV; arts. 54, 55).
    - Instrumento ausente ou vencido deixa `indeterminado` o teste que depende dele, com o motivo.
    - Os prazos ficam expostos na fachada, e o painel de Vencimentos (módulo Documentação) os lê de lá.
  - **fonte · papel:** certificados de calibração; inventário em `servico/ppr-tecnico.md` · não muda.

- **CAP-7 — Calibração TRS-398 calculada**
  - **intent:** O ISOCENTRO calcula a dose absorvida em condição de referência pelo TRS-398 a partir das leituras e dos fatores, em vez de só registrar o resultado.
  - **success:**
    - D_w,Q = M × k_TP × k_pol × k_s × k_elec × N_D,w × k_Q.
    - O cálculo é o item próprio de classe C (CAP-15); o GQ entrega leituras e fatores e mostra o resultado.
    - k_Q vem do TRS-398 de 2000 para a câmara cadastrada (Tab. 6.III da V.12 de 2006, que traz a PTW 30013; FC65-G e FC65-P pela atualização IAEA de 2002, `TRS-398-KQ-SW`), e N_D,w do certificado atual (CAP-6), que é posicionado pela edição de 2000. O conjunto de k_Q e o certificado usados ficam registrados com cada execução. As condições de referência citam o item nível 2.
    - O resultado é comparado à saída nominal com 1% (IT0004).
    - Cada fator mostra valor e origem; fator sem fonte nasce vazio, e o resultado fica `indeterminado`.
    - Antes de dar veredito, o cálculo reproduz a planilha atual do serviço em casos conferidos à mão.
  - **fonte · papel:** leituras do físico, certificado, [TRS-398] e [TRS-398-KQ-SW] · não muda.

- **CAP-8 — Análise de imagem pelo pylinac**
  - **intent:** Os testes de imagem do programa (picket fence, Winston-Lutz, fantomas de kV/CBCT e demais) recebem o valor da análise automática do pylinac.
  - **success:** O valor do teste sai da análise, nunca é digitado. A versão do pylinac e os parâmetros ficam registrados com a execução. A imagem fica guardada com hash como evidência. Cada análise é comissionada contra imagens de resultado conhecido antes de dar veredito; sem comissionamento, o resultado é `indeterminado`.
  - **fonte · papel:** imagens de CQ da máquina (origem a definir) · não muda.

- **CAP-9 — Importação DailyQA 3 e MapCHECK** (FR-26)
  - **intent:** O ISOCENTRO importa as exportações de medida de CQ de máquina como evidência da execução.
  - **success:** O arquivo fica guardado com hash junto da execução. Formato não lido entra como anexo, e o valor é digitado. Exportação com identificação de paciente (PSQA) não é importada no MVP.
  - **fonte · papel:** exportações do DailyQA 3 e do MapCHECK · não muda.

- **CAP-10 — Braquiterapia HDR no programa** (FR-27)
  - **intent:** O programa inclui os testes de HDR do GammaMedplus (Ir-192) da CEL, e a troca de fonte gera os testes da troca.
  - **success:**
    - Os testes são os da ficha E03: segurança diária (art. 35, III); recolhimento, temporizador, cofre, pinça e cortador (art. 63); posição da fonte 1 mm; atividade no console × tabela 1%; bateria, data e hora; kit de emergência.
    - Entram também os itens do TECDOC-1274 com limite, como a constância da câmara poço ±1%.
    - Na troca de fonte, a fonte nova fica "não liberada", com alerta `alta`, até a medida de S_K. O critério é medido × certificado, 3% como meta e 5% como limite (MPPG-HDR Tab. 4).
  - **fonte · papel:** ficha E03, TECDOC-1274, certificado da fonte · não muda.

- **CAP-11 — Guarda e restauração dos registros de CQ** (FR-28, AD-24)
  - **intent:** Os registros de CQ têm cópia independente e voltam íntegros na restauração.
  - **success:** O teste de restauração prova que os registros, os anexos e o log encadeado voltam válidos. A cópia é independente do original e fica na rede do serviço. A retenção é a mais longa de duas: nada se apaga enquanto o equipamento existir, nem antes de 10 anos após o descarte do software. Não há caminho de descarte no MVP (AD-5).
  - **fonte · papel:** banco central e anexos · não muda.

- **CAP-12 — Módulo GQ no shell** (FR-9, AD-18, UJ-3)
  - **intent:** O técnico registra o CQ do dia e o físico gerencia programa, carta, instrumentos e calibração numa tela do módulo.
  - **success:** O módulo tem lista do dia por clínica e máquina, programa, carta, instrumentos e calibração. O acesso e as ações seguem a tabela perfil → capacidades da Fundação, configurável pelo admin; o valor inicial é físico (cadastra testes, ações e carta), técnico (registra a execução) e SPR/gestão (só leitura). A UJ-3 roda de ponta a ponta em homologação. A análise do pylinac e o cálculo rodam em segundo plano.
  - **fonte · papel:** fachada de consulta do módulo · não muda.

- **CAP-13 — Validação do módulo GQ** (FR-6, FR-40)
  - **intent:** O módulo tem relatório de validação antes do primeiro uso real.
  - **success:** O relatório traz a sensibilidade semeada: valor fora da tolerância, teste vencido, instrumento vencido, imagem com erro conhecido e caso TRS-398 com resposta conhecida. Traz também o comissionamento do pylinac e do cálculo TRS-398 e os casos conferidos à mão. Fica guardado 10 anos após o descarte, e é refeito após upgrade do pylinac ou mudança do programa.
  - **fonte · papel:** execuções e testes · não muda.

- **CAP-14 — Aferição com decaimento** (FR-36)
  - **intent:** O físico registra a aferição com fonte-teste ou com a fonte de Ir-192, e o ISOCENTRO corrige o decaimento e compara com ±1%.
  - **success:** A aferição usa fonte-teste (Sr-90, no sistema de referência) ou a fonte de Ir-192 (câmara poço). O valor esperado é corrigido pelo decaimento a partir do nuclídeo, da meia-vida com referência e do valor e da data de referência do cadastro da fonte. O resultado mostra esperado, medido, diferença e tolerância ±1% com a fonte (art. 49 p.ú. III; art. 54 p.ú.). Campo vazio deixa a aferição `indeterminado`.
  - **fonte · papel:** cadastro da fonte e do instrumento (CAP-6) + leitura do físico · não muda.

- **CAP-15 — Cálculo TRS-398 como item próprio** (G1)
  - **intent:** O cálculo da calibração TRS-398 é um item de software separado do módulo GQ, para carregar sozinho a classe C.
  - **success:** O item é puro, sem tela, banco, rede nem arquivo (ex.: `modulos/qualidade/calibracao`; nunca no `rt`, AD-38). Recebe leituras, fatores, k_Q e N_D,w com origem e devolve D_w,Q com a origem de cada fator, ou `indeterminado` com o motivo. Tem classe C no `classificacao-62304.md` e no manifesto, e o teste de arquitetura reprova o GQ calculando a dose por conta própria. Os casos de comissionamento da CAP-7 rodam contra ele.
  - **fonte · papel:** entradas da CAP-7 · não muda.

- **CAP-16 — Inventário dos equipamentos e seções do PPR da GQ** (PPR vivo, Documentação CAP-10)
  - **intent:** Os capítulos do PPR sobre o que este módulo conhece moram aqui, com dado e texto.
  - **success:** Inventário técnico de cada máquina emissora (fabricante, modelo, série, energias de fóton e elétron com FFF, MLC, imagem EPID/kV/CBCT, técnicas habilitadas IMRT/VMAT/SRS/SBRT, filtros, fonte HDR, ortovoltagem kV e filtros), cada campo com o documento de origem (comissionamento, manual, certificado); recurso da máquina sem teste no programa (CAP-1) vira alerta, e teste de recurso que a máquina não tem é recusado. Capítulos: equipamentos e fontes emissoras; fontes de referência; instrumentos de dosimetria e fantomas (CAP-6); monitores de área; programa de GQ com o Anexo H gerado do programa versionado (CAP-1); gerência de rejeitos (fonte HDR decaída, CAP-10). Seção do PPR = dado vivo lido do próprio módulo + texto versionado do módulo, exposto pela fachada (Documentação CAP-10); texto com versão, autor e data; dado sem fonte sai vazio. A primeira versão do texto vem do PPR vigente de cada clínica, citado.
  - **fonte · papel:** comissionamento e manuais (`isocentro/comissionamento`), `servico/ppr-tecnico.md`, programa de CQ · entra no PPR.

## Constraints

- **Construído sobre a Fundação:** gravação, log, alerta, sombra, erro semeado, exportador e backup vêm do núcleo (AD-3, AD-27, AD-29).
- **Advisory:** `nao_conforme` não bloqueia tratamento; a decisão de parar a máquina é do físico.
- **Tolerância com origem:** todo teste cita a referência (programa ou item nível 2, com tabela e página); teste sem origem não é carregado.
- **Instrumento certo:** execução dosimétrica cita o instrumento cadastrado, nunca um presumido; certificado vencido → `indeterminado`.
- **Campo sem fonte nasce vazio:** nenhum fator, valor ou ação presumido (NFR-4).
- **Programa vem da base:** o ISOCENTRO não edita teste; muda a base e recarrega, registrando a versão.
- **Máquina certa:** a instância de teste é ligada à máquina pela chave canônica (AD-26), nunca por nome parecido.
- **Classe** (`classificacao-62304.md`, 26/10/2026): módulo GQ classe A; o cálculo TRS-398 (CAP-15) classe C, como item próprio. ANVISA classe I ou II até todos os testes.
- **Decisões provisórias:** a sombra até a conferência linha a linha (`decisoes-sem-base.md`, #12) vale até a discussão no serviço, e a tela diz "provisório".
- **Papel:** nada aqui muda o que sai impresso para o paciente; relatório de CQ para inspeção só pelo exportador do núcleo.
- **Escopo de equipamentos:** TrueBeam, 6EX, 600CD, VitalBeam, GammaMedplus (CEL) e ortovoltagem; Synergy01 (SAT) fora.

## Non-goals

- Detecção de tendência na carta de controle (Fase 4 do brief).
- Derivação local das tolerâncias (TG-218).
- Itens nível 2 do MPPG 11.a (vão para o Plano) e do MPPG 5.b (vão para Software e sistemas).
- QA de paciente (PSQA): resultado e importação de exportações com identificação.
- Controle da máquina ou bloqueio de tratamento.
- Painel de vencimentos: é do módulo Documentação (MVP 5), que lê os prazos daqui.
- IORT; unidade SAT.

## Success signal

- Em homologação, numa manhã da DUO, a técnica registra os 22 diários do VitalBeam. O output 6 MV a +3,4% (tol. ±3%) vira `nao_conforme` ▲ na máquina, aparece na Zona 2 do físico e na carta, e a repetição dentro fica no log ao lado. Num dia sem registro, o alerta de diário vencido sai antes do 1º paciente, com o app fechado.
- A calibração TRS-398 de uma energia reproduz a planilha atual do serviço. Uma imagem de picket fence com erro plantado é detectada pelo pylinac. Uma troca de fonte HDR fica "não liberada" até a medida de S_K.
- O relatório de validação do GQ está assinado antes do uso real, e a SM-3 é medida desde o 1º mês.

## Assumptions

- **Diário:** alertado até o 1º tratamento do dia (FR-24, `[SUPOSIÇÃO]` do PRD).
- **Instrumentos:** o GQ é dono do cadastro técnico; o módulo Documentação lê os vencimentos pela fachada.

## Open Questions

- **Imagens para o pylinac:** de onde vêm (exportação do EPID/kV pelo ARIA, Portal Dosimetry, Offline Review ou arquivo da estação), em que formato e em que pasta.
- **C3:** formato das exportações do DailyQA 3 e do MapCHECK.
- **TG-142 e TG-51 original** sem texto conferido (aapm.org 403): podem ser citados só pelas referências do `programa-cq.csv`?
- **B1:** etiqueta `fff` no TrueBeam e testes de HDR no `programa-cq.csv` antes da carga.
- **Instrumentos pendentes:** câmara ≤ 0,03 cm³ para SRS na CEL, < 0,1 cm³ para IMRT na BET, dispositivo de QA da DUO.
- **riscos.md:** linhas do GQ (S, O, D pelo físico): tolerância errada, teste vencido marcado em dia, fonte HDR sem S_K, k_Q errado, pylinac mal configurado.
