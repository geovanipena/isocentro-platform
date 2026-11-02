---
status: final
created: 2026-10-26
stepsCompleted: ['step-01-validate-prerequisites', 'step-02-design-epics', 'step-03-create-stories', 'step-04-final-validation']
inputDocuments:
  - prd-isocentro-2026-10-16/prd.md
  - prd-isocentro-2026-10-16/addendum.md
  - architecture-isocentro-2026-10-19/ARCHITECTURE-SPINE.md
  - ux-isocentro-2026-10-16/DESIGN.md
  - ux-isocentro-2026-10-16/EXPERIENCE.md
  - spec-isocentro-fundacao/SPEC.md
  - spec-isocentro-plano/SPEC.md
  - spec-isocentro-qualidade/SPEC.md
  - spec-isocentro-seguranca/SPEC.md
  - spec-isocentro-documentacao/SPEC.md
  - spec-isocentro-radioteraficha/SPEC.md
---

# ISOCENTRO - Epic Breakdown

## Overview

Este documento quebra em épicos e histórias os requisitos do PRD, do contrato de UX (DESIGN.md + EXPERIENCE.md), da espinha de arquitetura e das seis specs de bloco do ISOCENTRO.

**Relação com o `DESTINO.md`:** neste repositório o BMad é só planejamento (`docs/planejamento/LEIA-ME.md`), e a execução é a fila do `DESTINO.md`, onde as specs já viraram as frentes R-16..R-82. Este documento é um **mapa** (decisão de 26/10/2026, pela regra de decisão: opção recomendada, sem segunda lista de trabalho). Cada "história" é uma frente do DESTINO, e o critério de aceite é o **"pronto quando" daquela frente**, que não é copiado aqui para não divergir. Requisito sem frente vira **proposta** (seção "Propostas para o DESTINO"), e só entra na fila depois do aceite do usuário.

Convenções: `FR-n`/`NFR-n` = PRD; `AD-n` = espinha; `<spec> CAP-n` = capacidade da spec; `[SUPOSIÇÃO]` = valor padrão do PRD que só vale depois de confirmado pelo físico (NFR-4).

## Requirements Inventory

### Functional Requirements

#### Núcleo e plataforma (PRD §4)

- FR-1: O físico cadastra uma verificação com regra, proveniência, gatilho, responsável (perfil), avaliador, severidade e estado. É recusado o cadastro sem fonte, com fonte que não resolve para ficha da base ou com tolerância sem origem (`literatura` + referência; `servico` + data e método TG-218; `provisoria` + item de `decisoes-sem-base.md`).
- FR-2: O avaliador recebe o contexto e devolve resultado, evidência e motivo, sem gravar nada. O avaliador Python e o ESAPI (JSON) devolvem o mesmo formato. Exceção vira `erro` com a mensagem, e dado insuficiente vira `indeterminado` com motivo, nunca `conforme`.
- FR-3: Toda execução, assinatura, promoção e mudança de regra entra num log append-only encadeado por hash, sem edição nem exclusão. A verificação de integridade aponta o registro e a posição alterados. Retenção de 10 anos após o descarte (RDC 657 art. 5º).
- FR-4: Toda verificação nasce em `sombra`: executa e grava, sem alerta e sem fila. O físico promove para `ativa` ou poda, e a promoção grava quem, quando e o resumo da sombra. Sombra mínima de 30 dias, encurtável com justificativa [SUPOSIÇÃO]. Na verificação de obrigação legal, o processo manual continua até a promoção.
- FR-5: Resultado gera alerta na severidade cadastrada e nunca bloqueia ação. Nenhum botão fica desabilitado por resultado. `nao_conforme` em `alta` pede justificativa de quem segue [SUPOSIÇÃO].
- FR-6: O físico roda a verificação contra casos semeados e obtém a sensibilidade (semeados, detectados, não detectados). Execução `semeado` nunca entra em indicador. A bateria roda após cada upgrade do ARIA ou do Eclipse. Caso feito de plano real é anonimizado.
- FR-7: Sete perfis (médico, físico, dosimetrista, técnico, enfermeiro, recepcionista, SPR/gestão). Admin e físico responsável são atributos da pessoa. A tabela perfil → capacidades fica no banco, configurável pelo admin com log, e a capacidade é conferida no ato. Quatro travas ficam fora da tabela: só o físico assina AF/DC; o físico do DC ≠ o da AF; ninguém assina por outro; cada clínica vê só os seus dados.
- FR-8: A assinatura grava usuário logado, perfil, data e hora, objeto e versão (SOPInstanceUID + status no ARIA) e entra no log. A assinatura volta a pendente quando o plano tem nova versão: UID novo com conteúdo igual, status mudado, conteúdo mudado sem UID novo ou mudança menor.
- FR-9: Cada módulo do MVP é tela do shell, com o mesmo tema; nada abre fora dele (sem Streamlit). Toda tela com dado do `variandw` anuncia o degrau e a data.
- FR-41: Gera alerta para o perfil responsável, na clínica do objeto: todo `nao_conforme`, `indeterminado` ou `erro` de verificação ativa, e todo prazo em aviso ou vencido. O alerta aparece no painel "O que precisa de ação" (ordenado por severidade e prazo) e no módulo de origem. Estados aberto → visto → resolvido (justificativa em `alta`), no log. Os prazos são calculados com o app fechado, e o vencido aparece como `alta` na abertura. Só no app no MVP.

#### Plano — segunda checagem (MVP 1, PRD §5)

- FR-10: Tabela de feixe por máquina e energia (TrueBeam, 6EX, 600CD, VitalBeam) com origem, quem converteu, validação contra pontos do relatório original e atestado de que ainda representa a máquina. Nomes DICOM cadastrados um a um, sem parecença. FFF com tabela própria, filtros físicos explicitamente sem tabela, e MLC/DLG com origem para o modulado.
- FR-11: A segunda checagem dispara em `Planning Approved` com o RT Plan disponível e fica pronta antes da fila de Aprovação Física. Plano novo ou modificado dispara nova checagem. Sem RT Plan ou com UID divergente do `variandw`, sai `indeterminado` com alerta.
- FR-12: Diferença calculado × TPS por campo e no composto, com limite e origem. 3D: TG-114 (2% / 3,5% / 5%). Modulado: Clarkson por ponto de controle, TG-219 (3% / 5% no composto; 5% / 7% campo único; 5–10% em baixa dose). O ponto nunca é trocado para passar. Saem os limites antigos e o rótulo "demonstração". O papel não muda.
- FR-13: Máquina sem tabela, filtro físico ou técnica não tratada → `indeterminado` com motivo. Modulado sem comissionamento → `indeterminado`. O resultado `demonstracao` deixa de existir.
- FR-14: O físico registra e aprova o comissionamento por máquina (Tab. 8 do TG-219 no 3D, TG-119 no modulado). Sem ele, o valor aparece sem veredito ("cálculo não comissionado para esta máquina").
- FR-15: Plano sem segunda checagem conferida → alerta `alta` na 3ª fração ou aos 10% da dose (curso e fase, o que vencer primeiro, dizendo qual); no alto risco, antes da 1ª fração. Frações contadas do tratamento entregue, com o aviso "contagem não conferida" quando o curso não tem `LISTA_VERIFICADA_EM`.
- FR-43: Índices de qualidade e de complexidade (conformidade, gradiente, HI ICRU 83, MCSv, SAS, UM/cGy) viram verificações `plano.*`, com tolerância de literatura marcada provisória até o TG-218. "Fora da faixa" é alerta. A tela Virtual não vem junto, e o papel não muda.

#### Plano — revisão com segunda assinatura (MVP 2, PRD §6)

- FR-16: O ISOCENTRO lê do `variandw`, por plano, as datas de aprovação médica, PSQA, Treatment Approved, Duplo Check e 1ª fração, com tabela, campo e degrau. Data não encontrada nasce vazia. O Duplo Check tem duas fontes (assinatura no ISOCENTRO e Carepath), e a divergência entre elas gera `atencao`. Depende do mapeamento dos códigos (P6).
- FR-17: Fila de Duplo Check ordenada por prazo. Gera `alta` no prazo, e `alta` quando a 1ª fração de caso de alto risco acontece sem Duplo Check. Plano já tratado sem Duplo Check aparece com a contagem de frações.
- FR-18: O alto risco é marcado pelo dado (≥ 6 Gy por fração, ≤ 5 frações ou curso em menos de 6 dias, provisório) e à mão (reirradiação, dispositivo implantado). Enquanto houver critério "não informado", o caso é tratado como alto risco, com o alerta "alto risco não avaliado". A marcação grava quem e quando.
- FR-19: Listas votadas da Aprovação Física (8 itens) e do Duplo Check (8 itens), com os automáticos preenchidos: valor, fonte, referência e resultado. Item sem referência nasce vazio. O isocentro tem quatro conferências, sem veredito até haver tolerância em mm. Os itens TG-275 "++F" e MPPG 11.a entram como catálogo em sombra ou opcional, e as listas votadas não mudam. A segunda checagem é item das duas listas; `nao_conforme` ou `indeterminado` pede justificativa.
- FR-20: O físico do Duplo Check assina ao concluir a lista. Assinatura do mesmo usuário da Aprovação Física não é registrada como Duplo Check. O vínculo ARIA ↔ ISOCENTRO é feito por tabela; sem vínculo, a assinatura leva a marca "separação entre os físicos não conferida" e gera alerta `alta`. Nada é gravado no ARIA, e o papel não muda.
- FR-21: Na etapa de Planejamento, a prescrição do ARIA é confrontada com o RT Plan: dose total, dose por fração, nº de frações, energia e técnica. Energia e técnica casam pela tabela de equivalência; sem equivalência, sai `indeterminado`. Os itens da RDC 20 9.1 entram como registro manual e nascem vazios.
- FR-42: O dosimetrista confere a Lista de Planejamento (13 itens votados) antes da aprovação médica, com os automáticos preenchidos. A conferência grava quem e quando e não é segunda assinatura.

#### Garantia da Qualidade (MVP 3, PRD §7)

- FR-22: Programa de CQ por clínica e máquina, carregado sem digitação: os 103 testes do `qualidade.json` mais cerca de 97 itens nível 2 com limite. A versão do programa é registrada. A instância por máquina sai das etiquetas `aplica`. A fusão de itens repetidos é confirmada pelo físico. MPPG 11.a vai ao Plano e MPPG 5.b ao Software.
- FR-23: Registro de execução: valor, instrumento, quem e quando. O resultado é calculado pela tolerância e nunca digitado; o teste funcional é passa/falha. Fora da tolerância → `nao_conforme` com alerta `alta` no mesmo dia, mostrando a ação prevista, que o físico cadastra e que nasce vazia. Nada é bloqueado.
- FR-24: Teste que passa da frequência sem execução gera alerta; o diário, até o 1º tratamento do dia [SUPOSIÇÃO]. As demais frequências vão ao painel de vencimentos.
- FR-25: Carta de controle do output diário por máquina e energia, com a tolerância e a origem; o limite de ação só aparece quando cadastrado. A detecção de tendência fica fora do MVP.
- FR-26: Importação das exportações do DailyQA 3 e do MapCHECK como evidência guardada com a execução. Formato não lido entra como anexo com valor digitado. Exportação com identificação de paciente não é importada no MVP.
- FR-27: Os testes de HDR (ficha E03, TECDOC-1274) entram no programa, e a troca de fonte gera os testes da troca. A fonte fica "não liberada", com alerta `alta`, até a medida de S_K (3% meta / 5% limite, MPPG-HDR).
- FR-28: Os registros de CQ têm cópia de segurança independente na rede do serviço. A restauração prova registros e log íntegros. Retenção pelo maior prazo (vida do equipamento, ou 10 anos após o descarte), sem caminho de descarte no MVP.
- FR-36: Aferição com fonte-teste (Sr-90) ou Ir-192, com correção do decaimento pelo cadastro da fonte e comparação com ±1%. Campo vazio deixa a aferição `indeterminado`.
- FR-44: Cadastro de instrumentos com o certificado (modelo, série, laboratório, data, N_D,w ou S_K/N_K) e a periodicidade por tipo (arts. 49, 52, 54, 55). Conserto, dano ou transporte vencem o instrumento na hora. Instrumento ausente ou vencido deixa o teste `indeterminado`. Os prazos vão ao painel.
- FR-45: Cálculo da calibração pelo TRS-398 (D_w,Q = M × k_TP × k_pol × k_s × k_elec × N_D,w × k_Q, k_Q de 2000), comparado à saída nominal com 1%. Fator sem fonte deixa o resultado `indeterminado`. O cálculo reproduz a planilha do serviço antes de dar veredito. É item próprio de classe C, puro e sem tela.
- FR-46: Os testes de imagem (picket fence, Winston-Lutz, kV/CBCT) recebem o valor do pylinac, nunca digitado. A versão e os parâmetros ficam registrados, e a imagem é guardada com hash. A análise é comissionada contra imagens de resultado conhecido antes de dar veredito.

#### Segurança do paciente (MVP 4, PRD §8)

- FR-29: Qualquer perfil registra incidente ou quase-incidente com: etapas pelo mapa do Ford 2012 (onde ocorreu e onde foi detectado), desvio de dose pela escala do Ford, local e volume pelo TG-100, dano pela WHO-ICPS e fatores causais. O registro liga pelo identificador do ARIA. Texto livre e dose estimada só são lidos por físico, SPR/gestão e notificador. O notificador fica no log e não aparece na leitura.
- FR-30: A exposição médica não intencional abre o prazo de 30 dias e a lista do art. 26, cada item com quem e quando. Alerta `alta` até a investigação ser iniciada. O relatório segue os itens a–k do guia CNEN 2020, com as quatro assinaturas e o protocolo guardado. Sem relatório: `atencao` aos 20 dias e `alta` aos 30 [SUPOSIÇÃO].
- FR-31: O ISOCENTRO é o canal interno ao NSP, com o evento organizado nas 10 etapas do Notivisa. Prazos: 15º dia útil do mês seguinte; 72 h no óbito; 60 dias para as etapas 5–10. O número da notificação é registrado e o evento sem número no prazo gera alerta. Não há envio automático.
- FR-32: Triagem semanal dos eventos novos e revisão trimestral com ata, agrupando por etapa de ocorrência e de detecção.
- FR-47: Ciclo de análise: aberto → em análise → ação definida → fechado, com quem e quando. Ação corretiva e de prevenção têm responsável e prazo, e a vencida gera alerta. O vínculo é ao evento iniciador e à barreira. O `riscos.md` só recebe vínculo de incidente do próprio ISOCENTRO, e o módulo não escreve nele.
- FR-48: Matriz etapa de ocorrência × etapa de detecção, por período e clínica. Indicadores: taxa por 1.000 frações, razão quase-incidente/evento e tempo até fechar. Sem denominador, a taxa nasce vazia. Células com menos de 5 casos são suprimidas no relatório. A taxonomia é validada com kappa ≥ 0,7.
- FR-49: Matriz de risco em tempo real por prática: SEVRRA como espinha mais O, S, D do TG-100. O estado da barreira vem das verificações; o ISOCENTRO propõe e o físico confirma. Barreira sem dado conta como não funcionando. Perfil RB/RM/RA/RMA atual e de referência com histórico, e proposta de subida gera alerta. O SEVRRA segue em paralelo.

#### Documentação e conformidade (MVP 5, PRD §9)

- FR-33: Itens com vencimento (treinamento de PR e de física médica, auditoria, levantamento radiométrico, ASO, Autorização CNEN, alvará, SEVRRA, monitoração individual), cada tipo com periodicidade e fonte. A data de partida sai do documento de origem; sem documento, "sem data". Há vencimento por evento (modificação da instalação, retorno após 30 dias, mudança de risco, dose acima do limite). A lista de IOEs é marca no cadastro de equipe. Do ASO, só pessoa, data e validade; da monitoração, só "recebido".
- FR-34: Painel de vencimentos por clínica, com janela configurável (padrão de 60 dias [SUPOSIÇÃO]). Vencido em `alta`, dentro do aviso em `atencao`. Inclui os testes de CQ não diários, os instrumentos e as aferições da GQ.
- FR-35: O `ppr-streamlit` entra como conferência, não como fonte, com relatório item a item. A divergência usa a data que vence mais cedo. O ASO é lançado à mão até a R-15. Os certificados de instrumento vão à GQ. Depois do corte, o `ppr-streamlit` deixa de ser fonte.

#### Software e sistemas no MVP (PRD §10.1)

- FR-37: Cobertura publicada: fração das atividades com verificação ativa, calculada do cadastro (sombra não conta), sobre 74 e sobre 60 atividades [SUPOSIÇÃO].
- FR-38: Inventário SOUP com versão e licença, gerado das dependências, com as ressalvas de risco conhecido; entra no relatório de validação.
- FR-39: A execução registra o identificador e o checksum do RT Plan e a data da carga do `variandw` de que partiu.
- FR-40: Relatório de validação por módulo antes do 1º uso real: requisitos, testes, casos à mão, sensibilidade semeada, comissionamento, SOUP e versão. Guardado 10 anos após o descarte e refeito após upgrade do ARIA ou do Eclipse.

### NonFunctional Requirements

- NFR-1: Somente leitura no ARIA, no `variandw`, nos relatórios exportados e no Eclipse; todo avaliador ESAPI é somente leitura, separado das DLLs graváveis.
- NFR-2: Nenhum dado de paciente ou de funcionário sai da rede do serviço (log, repositório, terceiros, IA). Teste com `varrer_identidade` e teste de log. CEL, BET e DUO estão na mesma rede.
- NFR-3: Toda tela com dado do `variandw` mostra o degrau e a data.
- NFR-4: Campo sem fonte nasce vazio. Os padrões `[SUPOSIÇÃO]` só valem depois de confirmados pelo físico.
- NFR-5: A segunda checagem fica pronta antes da fila de Aprovação Física, sem número fixo. Painéis abrem em menos de 3 s [SUPOSIÇÃO, `decisoes-sem-base.md` #33].
- NFR-6: CEL, BET e DUO veem cada uma os próprios dados; o físico responsável vê as três.
- NFR-7: Com o `variandw` fora, a tela mostra o último dado com degrau e data, e nenhum prazo vira `conforme` por falta de dado.
- NFR-8: Todo FR clínico liga a um item do `docs/qms/riscos.md` e a uma forma de verificação; as linhas de risco são do físico.
- NFR-9: A suíte de testes continua verde e rápida a cada entrega.
- NFR-10: Banco central em servidor da clínica, fora da infraestrutura do ARIA; o `escopo.md` é atualizado antes do 1º épico que grava no banco.

### Additional Requirements

**Ponto de partida:** não há starter template. O projeto é brownfield: o pacote `isocentro/` existe e está em uso clínico (Radioteraficha). A árvore-alvo (`nucleo/`, `rt/`, `modulos/`, `adaptadores/`, `interface/modulos/`, `migracoes/`) cresce ao lado dos pacotes atuais (espinha, Semente estrutural).

#### Da espinha de arquitetura (AR)

- AR-1: Monólito modular, um executável, sem plug-in em tempo de execução. Dependências `interface → modulos → nucleo ← adaptadores`, `modulos → rt` e `interface → rt`. Módulo não importa outro módulo (só a fachada `consulta.py`), adaptador nem Qt (AD-1, AD-2, AD-3).
- AR-2: Teste de arquitetura por `ast` reprova as violações de dependência, gravação em tabela alheia, manifesto sem tela, prefixo de verificação alheio e classe divergente do `classificacao-62304.md`. As violações atuais entram numa lista de exceções com data de saída (AD-22; Fundação CAP-21).
- AR-3: `tools/raio.py` calcula o raio de revisão do diff, que só soma: SQL, dependência, tabela de máquina ou arquivo sem dono → suíte inteira; alcance de `papel/` → `comparar_pdf` e aviso ao usuário (AD-39).
- AR-4: PostgreSQL 18 em `clinica-python01`, driver `psycopg[binary]` 3.3, um schema por módulo. Esquema por `.sql` numerado com tabela de versão, aplicado por `isocentro_dono`, sem Alembic. App com versão divergente abre somente leitura com "atualize" (AD-10, AD-19, AD-27; Fundação CAP-1).
- AR-5: Toda gravação passa por `nucleo.gravar`: dado e linha de log na mesma transação, registro tabela → dono conferido, log único sem texto livre (AD-4, AD-27, AD-33).
- AR-6: Nada se apaga nem se edita: correção é registro novo que aponta o anterior, e o vigente é calculado. Única exceção: o espelho, que é cache (AD-5, AD-17).
- AR-7: Corrente de hash global por gatilho `SECURITY DEFINER`. Papéis `isocentro_app` e `isocentro_concentradora` só com INSERT/SELECT no log; `isocentro_dono` só para DDL (AD-6).
- AR-8: Âncora diária do hash da ponta numa pasta da TI só-acrescentar, e um verificador que aponta registro e posição alterados (AD-32; Fundação CAP-5).
- AR-9: Login da pessoa conferido no PostgreSQL por função `SECURITY DEFINER`. O PBKDF2 migra para o banco. TLS obrigatório. A senha do `isocentro_app` (scram) fica no `keyring` do Windows, e sozinha não lê nem grava dado (AD-25; Fundação CAP-2).
- AR-10: Capacidade conferida no núcleo e no banco. RLS por clínica pela sessão; toda tabela é de clínica (`CEL`/`BET`/`DUO`) ou global. A concentradora não tem `BYPASSRLS` (AD-11, AD-12; Fundação CAP-3).
- AR-11: Unidades `CEL`/`BET`/`DUO`; o código migra `ANA` → `DUO`; SAT fica fora (AD-8).
- AR-12: Entidades de referência no núcleo: chave canônica `Ser` + clínica, e REG, nome, `PatientId` e SOPInstanceUID como apelidos. O vínculo ARIA ↔ ISOCENTRO fica em tabela, só cadastrada por admin (AD-13, AD-26; Fundação CAP-6).
- AR-13: Contrato da verificação: resultado em 5 valores, severidade em 3, estados `sombra`/`ativa`/`podada`, `origem` `producao`/`semeado`, id `<modulo>.<nome>` (AD-14, AD-31).
- AR-14: O avaliador é puro. O ESAPI grava JSON com esquema versionado, hash e versão do plano, numa pasta restrita, e a concentradora importa e valida. Esquema desconhecido → `erro`; versão do plano diferente → `indeterminado`; script fora do inventário → `indeterminado` (AD-15, AD-41; Fundação CAP-9).
- AR-15: O `variandw` é lido só por pyodbc ReadOnly pelo `_consultar`/`FalhaDeLeitura`. Degraus: `variandw` → espelho (no PostgreSQL, RLS, 60 dias, limpeza no log) → CSV. DICOM por C-MOVE (AD-16, AD-17; Fundação CAP-15).
- AR-16: A concentradora (`run_varredura.py`, Tarefa Agendada sem Qt) é a única a rodar gatilhos de tempo; sai o `QTimer` de `gatilho_relogio`. A execução é idempotente (uma só vigente por objeto e versão) (AD-9, AD-20, AD-28; Fundação CAP-14).
- AR-17: Alerta como eventos acrescentados no núcleo (aberto, visto, resolvido) (AD-29; Fundação CAP-12).
- AR-18: Assinatura no núcleo, ligada a objeto + versão (`Ser` + SOPInstanceUID + `HstryDateTime`/status) (AD-30; Fundação CAP-13).
- AR-19: Banco central fora: estações em somente leitura com o aviso "banco central fora — nada será gravado"; sem fila local; degraus `variandw` → CSV (AD-23; Fundação CAP-16).
- AR-20: Backup `pg_dump` diário cifrado em AES-256 em `\\fileserver`, guardado 30 dias, mais um dump mensal em mídia separada. A chave fica com Geova, com cópia lacrada com SPR/gestão. Restauração mensal registrada no log e roteiro de manutenção escrito (AD-21, AD-24; Fundação CAP-17).
- AR-21: Exportador único do núcleo, sem identificação; nenhum módulo gera arquivo por conta própria (AD-33; Fundação CAP-18).
- AR-22: Três ambientes (desenvolvimento, homologação, produção); gatilhos, papéis e RLS testados contra PostgreSQL (AD-34).
- AR-23: Classe IEC 62304 por item: núcleo, `rt`, Plano, Radioteraficha, GQ, Segurança e Documentação são A; o cálculo TRS-398 é C (`modulos/qualidade/calibracao`); item sem linha vale rigor C. Provisório: com o TRS-398 no executável, todo item do processo tem rigor C (AD-35, AD-39; `decisoes-sem-base.md` #34).
- AR-24: A interface migra de PyQt5 para PySide6, junto com a Torre. A Fundação porta o app inteiro sem redesenho, e telas novas já nascem em PySide6 (AD-36; Fundação CAP-19).
- AR-25: Corte de migração por entidade (usuários → sessões → equipe → configuração → …): migra, confere e corta, sem gravação dupla; o JSON vira somente leitura e depois é arquivado (AD-37; Fundação CAP-20). A equipe ganha cargo e marca IOE por pessoa e clínica.
- AR-26: Camada `rt/` pura (modelos imutáveis, geometria IEC 61217, cortes, DVH), sem veredito nem dado do serviço; divisão de `dicom/` em `rt/`, `adaptadores/dicom/` e desenho (AD-38; R-58).
- AR-27: `MANIFESTO` por módulo (nome, classe, capacidades, verificações, tabelas, fachada) e raízes de composição explícitas (`isocentro/composicao.py`, `interface/composicao.py`). O Radioteraficha é o primeiro módulo com manifesto (AD-40; Fundação CAP-24).
- AR-28: Repositórios vizinhos: `scriptsvarian` fica à parte e o ISOCENTRO não executa ESAPI; `modulos/software` guarda o inventário dos scripts; `ppr-streamlit` e `parallel-mu-check` entram por importador único e ficam congelados (AD-41).
- AR-29: IA só sugere: nunca preenche campo nem dá veredito; toda sugestão traz a origem e o rótulo "sugestão de IA"; o modelo é SOUP com versão e hash; dado de paciente só em modelo dentro da rede (AD-42).
- AR-30: Mesma versão para app e concentradora. PyInstaller 6.21.0 onedir, CI em `windows-2025`, dependências fixadas exatas. PySide6 e keyring têm versão a confirmar antes do 1º épico (AD-20, Stack).
- AR-31: Tabela perfil → capacidades configurável em Configurações, com valor inicial da matriz do `escopo.md`, cada mudança no log, e teste de que nenhuma configuração desliga as quatro travas (Fundação CAP-23).
- AR-32: Relatório de validação do núcleo assinado antes do 1º módulo em produção (Fundação CAP-22).
- AR-33: Pré-requisitos de gestão que a espinha e o PRD põem antes de épicos: `escopo.md` com o banco central antes do 1º épico que grava (G6/Q8, R-16); linhas S/O/D no `riscos.md` antes da 1ª gravação clínica (físico); R-07 (165 cursos) antes do MVP 2; P6 (códigos do Carepath) antes do FR-16; TG-119 no acervo antes do comissionamento modulado; texto da IEC 62304 antes do épico do TRS-398.

#### Das specs, sem FR no PRD (SR) — módulo Radioteraficha

- SR-1: O Radioteraficha abre pela doca com as abas Capa, Fichinha, Total e Agenda no topo de módulo. Saem as abas Qualidade, Radioteradados e Virtual. O recorte por perfil é herdado de `MODOS_POR_PAPEL` e conferido como capacidade. Liberar para impressão é capacidade de físico e admin. Ctrl+O/E/H/G valem só no módulo (Radioteraficha CAP-1).
- SR-2: As quatro telas passam aos componentes Torre com a árvore de widgets mantida (print antes/depois): pesos de botão novos, pendências como linhas com chip de severidade, reserva usada em primeiro lugar, `test_padrao_visual` sem exceção nova (CAP-2).
- SR-3: O papel fica inalterado. Os PDFs dos casos de referência (`TCs_Teste`, `dicom-teste`) são comparados página a página após cada corte; diferença reprova (CAP-3).
- SR-4: O registro é versionado no banco: geração com mudança cria versão; os PDFs e PNGs ficam na pasta com hash e caminho; a ficha é reaberta e regerada sem a TC; a exclusão de DICOM só aparece depois do registro gravado (CAP-4).
- SR-5: Identidade pela chave canônica com vínculo pendente: REG sem `Ser` grava como pendente e se liga sozinho pelo `PatientId`, sem prazo e sem ligação à mão. Com o banco fora, o PDF sai com "versão não registrada" (CAP-5).
- SR-6: A correção da capa vira registro novo; quando a fonte passa a concordar, fica no histórico sem efeito (CAP-6).
- SR-7: O cadastro SUS vai ao banco, com a mesma validação do cartão e o convênio do `variandw` como primeira fonte (CAP-7).
- SR-8: Simulação, notas de posicionamento (39 modelos globais; nota do paciente por clínica) e inventário de imobilizadores (por clínica, RLS) vão ao banco. Usos desconhecidos nascem vazios, nunca 0; o aviso aos 20 usos é provisório; vincular nunca é bloqueado (CAP-8).
- SR-9: O índice de fichas é derivado das versões. As preferências seguem sessão → estação → serviço → padrão. O `historico_uso.jsonl` vira legado somente leitura (CAP-9).
- SR-10: Migração por entidade do módulo, mais varredura única das `FICHA_*.json` pela união das raízes (inclusive dentro de `ARQUIVOS_*.zip`), com relatório e sem alterar as pastas (CAP-10).
- SR-11: Retirada do checklist (histórico em leitura, depois da lista do Plano ativa) e da Virtual, que abre portada pelo cartão Tratamento da doca (CAP-11).
- SR-12: Relatório de validação do Radioteraficha assinado: comparação de PDFs, relatórios de migração, vínculo pendente, banco fora, correção e recorte por perfil (CAP-12).

#### Das specs, detalhes além do FR correspondente

- SR-13: Segurança CAP-2: toda leitura de texto livre ou dose estimada gera evento (quem, quando, registro, sem conteúdo; LGPD). A recusa é conferida no banco. O RIPD do módulo existe.
- SR-14: Segurança CAP-1: o quase-incidente se registra em até 90 s; never event é marcado pela lista da Anvisa, guardada como dado; dia útil exclui só sábado, domingo e feriado nacional.
- SR-15: Segurança CAP-11..14: catálogo da matriz por prática (acelerador, HDR), cada linha com fonte; estado da barreira declarado × medido lado a lado; O proposto pela contagem de incidentes. A validação reproduz o SEVRRA do 6EX de jan/2023 (61 RM, 68 RB).
- SR-16: Documentação CAP-3/4/9: leitura do ASO só por SPR/gestão e físico responsável, com recusa no banco; IOE sem ASO listado; monitoração mensal por IOE "recebido"/pendente; lista de IOEs mantida só pelo SPR e conferida contra o PPR.
- SR-17: GQ CAP-1: o item nível 2 fica em sombra até a conferência linha a linha contra o PDF (provisório, #12). O Dermopan entra na CEL com 12 testes `orto`.
- SR-18: GQ CAP-15: teste de arquitetura reprova o GQ calculando dose por conta própria fora do item TRS-398.

### UX Design Requirements

#### Tokens e base visual

- UX-DR1: O `estilo.py` troca as paletas `DIA`/`NOITE` pelas 23 chaves do DESIGN.md (noite simples, dia com `-dia`). Saem o acento verde-azulado e os apelidos `AZUL*`/`VERDE*`, e o modo padrão é noite.
- UX-DR2: O `test_padrao_visual.py` confere contra a paleta nova e reprova verde fora da dose (o token `dose` só nos arquivos de isodose), inclusive em `QColor(r,g,b)`.
- UX-DR3: Tipografia Segoe UI com base de 13 px e entrelinha 1,35; os 18 papéis da escala do DESIGN.md; números tabulares em toda a janela; glifos ▲◆○ forçados a texto (VS15). Hierarquia por peso e tamanho, nunca por cor; maiúsculas só em rótulo de zona, sigla de clínica e severidade; nada abaixo de 10 px.
- UX-DR4: Visual chapado, sem sombra, brilho nem gradiente; profundidade tonal fundo → superfície → superfície elevada (hover); linhas com severidade clareiam 8–10% no hover; os cantos seguem a tabela `rounded`.
- UX-DR5: Ícones SVG de traço único de 1,6 px, sem preenchimento, cor herdada, um desenho por módulo, mais a marca do ISOCENTRO (dois círculos e retículo). Emoji não é ícone.

#### Componentes (`ui.py`)

- UX-DR6: Botões primário (sólido, um por tela, verbo no rótulo), secundário (contorno), discreto e perigo (contorno vermelho, nunca sólido). Mapeamento de `btn_solido`/`btn_contorno`/`btn_fantasma`/`btn_perigo`; sai o `ui.botao(brilho=True)` verde.
- UX-DR7: Chip de severidade "▲ ALTA" / "◆ ATENÇÃO" / "○ INFO": forma, cor e palavra juntas, não clicável.
- UX-DR8: Linha com borda lateral de 3 px, fundo da severidade e cantos só à direita, para máquina e ação. Estado "visto": sem fundo, borda tracejada, texto secundário e "visto · nome · hh:mm".
- UX-DR9: Selo de degrau "fonte ● ao vivo · dd/mm hh:mm", "◌ espelho hh:mm · data" e "relatório · data", sempre com a data.
- UX-DR10: Tabela de leitura com linhas de 23 px: "dentro" neutro, "a lançar" em itálico sem cor, só a linha fora com fundo, borda e forma.
- UX-DR11: Cartão de alerta: severidade e título, rótulo/valor (valor medido em 15/700), bloco "Ação prevista" e um primário.
- UX-DR12: Gráfico de controle: série neutra, tolerância tracejada, zero em borda e ponto fora como ▲ em `alta` com o valor.

#### Shell e Início

- UX-DR13: Topo do Início: marca, seletor de clínica, relógio "dd/mm/aaaa · hh:mm", noite/dia (lua/sol, lembrado por estação) e usuário.
- UX-DR14: Seletor de clínica segmentado com só as clínicas permitidas (CEL · BET · DUO) e "Todas" para o físico responsável. A opção marcada usa `acao-fundo`, não preenchido. A escolha é lembrada por usuário, e trocar refaz a Zona 1 e refiltra a Zona 2 na hora.
- UX-DR15: Zona 1, "Situação do serviço": uma coluna por clínica. A máquina normal aparece neutra com "normal"; a máquina com problema, com a pior severidade e o motivo em peso 600. A agenda mostra pacientes de hoje e o próximo horário, com selo de degrau. Três contadores (Duplo Check, Aprovação Física, Vencimentos 60d) com "▲n". O clique abre o módulo filtrado pela clínica, máquina ou fila.
- UX-DR16: Zona 2, "O que precisa de ação": filtrada por perfil e clínica, ordenada por severidade e depois prazo. Grade de 6 colunas (104/232/resto/150/56/150), 5 linhas, "ver mais N" e "Abrir fila" como primário. O clique abre o módulo de origem no item; resolver `alta` pede justificativa. O total aparece no rótulo da zona.
- UX-DR17: Zona 3, doca: 9 blocos na ordem do EXPERIENCE.md, sem contagem. Bloco de módulo inexistente leva o selo "em construção" e abre um painel sem dado; bloco sem acesso some, e os restantes mantêm 1/9 de largura alinhados à esquerda.
- UX-DR18: Topo do módulo: "◂ Início", ícone e nome, faixa de abas recortada por perfil (ativa com sublinhado de 2 px), contexto "clínica · máquina" à direita e sem seletor de clínica. Aberto com "Todas", o módulo mostra a coluna ou etiqueta "Clínica" em cada item.
- UX-DR19: Barra de status: "usuário · perfil · clínica" à esquerda e selo de degrau à direita; "Configurações" só com admin; mensagens transitórias.

#### Estados, teclado, acessibilidade e texto

- UX-DR20: Estados:
  - Banco central fora: sem máquina "normal", sem fila zero e sem "Nada precisa de ação"; a tela diz desde quando falta o dado.
  - `variandw` fora: último dado com degrau e data, e prazo `indeterminado`.
  - Tudo normal: sem verde e sem selo de OK.
  - "Nada precisa de ação nesta clínica."
  - Trabalho em segundo plano com "carregando".
  - Sessão aberta em outra estação fecha esta; senha a trocar abre o `DialogTrocarSenha` obrigatório; exceção cai no `ui.falhar`.
- UX-DR21: Teclado:
  - Anel de foco de 2 px afastado 2 px em todo clicável.
  - Ordem de Tab definida no Início e no módulo; foco inicial na 1ª linha da Zona 2.
  - Alt+Home volta ao Início; Ctrl+Tab circula as abas; Ctrl+P/Ctrl+Enter disparam o primário, nunca ação destrutiva.
  - Enter confirma e Esc cancela; sem diálogo sobre diálogo.
- UX-DR22: Acessibilidade: texto ≥ 4,5:1 e sinal ≥ 3:1 nos dois modos; severidade nunca só por cor (no modo dia, a forma decide); todo destino alcançável por teclado; botão sempre com texto.
- UX-DR23: Microcopy pelo glossário do PRD:
  - "normal", "sem data", "`indeterminado`: motivo", "origem: literatura, não derivado do serviço", "visto · nome · hh:mm".
  - Verbo no botão; termos do ARIA em inglês.
  - Sem exclamação, emoji nem elogio; "conforme" nunca digitado.

#### Divergências e lacunas da UX (a resolver, não inventar)

- U3 respondida pelo FR-41 (a Zona 2 mostra os alertas cujo responsável é o perfil, na clínica). U8, destino do "Abrir fila" e clique na máquina normal: provisórios em `decisoes-sem-base.md` #35–#37.
- O EXPERIENCE.md ainda diz "envio ao Epimed" na Segurança (o Epimed saiu em 26/10) e "Tratamento em construção" (a spec do Radioteraficha manda o cartão Tratamento abrir a Virtual). Também cita PyQt5, quando o alvo é PySide6.

### FR Coverage Map

| FR | Épico | Frente(s) |
| --- | --- | --- |
| FR-1 | 2 — Verificação confiável | R-77 ✓, R-82 |
| FR-2 | 2 | R-77 ✓, R-76 ✓, R-20 |
| FR-3 | 1 (log, verificador) e 2 (âncora diária) | R-18; R-21 (âncora, P-3) |
| FR-4 | 2 | R-77 ✓ (regra); R-83 (tela de promoção) |
| FR-5 | 2 | R-21; nenhum botão desabilitado: R-23 e telas de módulo |
| FR-6 | 2 | R-77 ✓ (origem `semeado`), R-26; R-83 (relatório em tela) |
| FR-7 | 1 — Torre e identidade | R-16, R-19, R-78 |
| FR-8 | 2 | R-21 |
| FR-9 | 1 | R-23 (shell); cada módulo: R-35, R-43, R-47, R-50, R-54 |
| FR-10 | 3 — Plano | R-09, R-29, R-30 |
| FR-11 | 3 | R-30 |
| FR-12 | 3 | R-30 (3D), R-31 (modulado) |
| FR-13 | 3 | R-30, R-31 |
| FR-14 | 3 | R-29 |
| FR-15 | 3 | R-30, R-07 |
| FR-16 | 3 | R-28, R-33 |
| FR-17 | 3 | R-33 |
| FR-18 | 3 | R-33 |
| FR-19 | 3 | R-34, R-79 |
| FR-20 | 3 | R-34 |
| FR-21 | 3 | R-34 |
| FR-22 | 5 — Garantia da Qualidade | R-37, R-39 |
| FR-23 | 5 | R-39 |
| FR-24 | 5 | R-39 |
| FR-25 | 5 | R-39 |
| FR-26 | 5 | R-38, R-42 |
| FR-27 | 5 | R-42 |
| FR-28 | 5 | R-25, R-43 |
| FR-29 | 6 — Segurança do paciente | R-46 |
| FR-30 | 6 | R-46 |
| FR-31 | 6 | R-45, R-46 |
| FR-32 | 6 | R-46 |
| FR-33 | 7 — Documentação | R-48, R-49 |
| FR-34 | 7 | R-49 |
| FR-35 | 7 | R-15, R-50 |
| FR-36 | 5 | R-40 |
| FR-37 | 2 | R-83 |
| FR-38 | 2 | R-83 |
| FR-39 | 2 | R-20 (ampliada pela P-2) |
| FR-40 | todos | R-26 (núcleo), R-36, R-43, R-47, R-50, R-55 |
| FR-41 | 2 | R-21 |
| FR-42 | 3 | R-34 |
| FR-43 | 3 | R-32 |
| FR-44 | 5 | R-40 |
| FR-45 | 5 | R-40 |
| FR-46 | 5 | R-38, R-41 |
| FR-47 | 6 e 8 | R-46 (ciclo), R-81 (vínculo à matriz) |
| FR-48 | 6 | R-44 (kappa), R-47 |
| FR-49 | 8 — Matriz de risco | R-80, R-81 |

**SR (Radioteraficha):** SR-1, SR-2, SR-11 → R-54; SR-3 → R-52; SR-4..SR-10 → R-53; SR-10 (varredura) e SR-12 → R-55. **SR-13, SR-14** → R-46. **SR-15** → R-81. **SR-16** → R-49. **SR-17** → R-39. **SR-18** → R-40.

**UX-DR:** UX-DR1..5, UX-DR13..20 → R-23. Teclado, acessibilidade e estados do Início entraram na R-23 pela P-4. UX-DR6..9 → R-23 (Início) e R-54 (Radioteraficha). UX-DR10..12 (tabela de leitura, cartão de alerta, gráfico de controle) → R-43. UX-DR21, UX-DR22 → R-23 (P-4). UX-DR23 → todas as telas.

**AR:**

- AR-1, AR-2 → R-24 ✓.
- AR-3 → R-59 ✓.
- AR-4, AR-5, AR-6, AR-7 → R-17, R-18.
- AR-8 → R-17 (pasta), R-18 (verificador), R-21 (gravação diária, P-3).
- AR-9, AR-10, AR-11, AR-12, AR-25 → R-19.
- AR-13 → R-77 ✓.
- AR-14 → R-76 ✓, R-20, R-61.
- AR-15, AR-19, AR-21 → R-22.
- AR-16, AR-17, AR-18 → R-08, R-21.
- AR-20 → R-25.
- AR-22 → R-17, R-18.
- AR-23 → R-16; o texto da IEC 62304 está na lista de aquisição.
- AR-24 → R-23.
- AR-26 → R-58.
- AR-27 → R-60.
- AR-28 → R-61, R-50.
- AR-29 → R-63.
- AR-30 → R-56 ✓; versões de PySide6 e keyring → R-23, R-19.
- AR-31 → R-78.
- AR-32 → R-26.
- AR-33 → R-16, R-07, R-28, R-37 (B1), lista de aquisição.

**Fora destes épicos:**

- R-10 (base histórica TG-218: derivação das tolerâncias, pós-MVP no PRD §10).
- R-64..R-68 (IA: sem FR no PRD; só a regra AD-42 entra, pela R-63).
- R-62, R-69, R-70 (feitas, fora do sistema global).

## Epic List

### Épico 1 — Entrar no ISOCENTRO pela Torre, com identidade que vale no banco

Cada pessoa entra com o próprio login, conferido no PostgreSQL. Vê só as clínicas a que tem acesso e encontra o Início da Torre (situação do serviço, o que precisa de ação, doca de 9) num app inteiro em PySide6. Com o banco fora, o app diz que nada será gravado, e o backup é restaurável.
**FRs covered:** FR-3 (log e verificador), FR-7, FR-9 · NFR-2, 3, 6, 7, 9, 10 · AR-4..12, 15, 19..22, 24..26, 31 · UX-DR1..23

### Épico 2 — Verificação confiável de ponta a ponta

O físico cadastra uma verificação com proveniência, deixa-a em sombra, mede a sensibilidade com erro semeado e promove. O alerta chega a quem é responsável mesmo com o app fechado. A assinatura fica presa à versão do plano. O log se prova íntegro contra a âncora diária. Cobertura e SOUP são publicados, e o núcleo tem relatório de validação.
**FRs covered:** FR-1, 2, 3 (âncora), 4, 5, 6, 8, 37, 38, 39, 40 (núcleo), 41 · AR-13, 14, 16..18, 27, 28, 32

### Épico 3 — Plano — segunda checagem, Aprovação Física e Duplo Check

O dosimetrista e o físico recebem a segunda checagem pronta antes da Aprovação Física (3D e modulado, com limite citado e prazo de 3ª fração/10%). Conferem pelas listas votadas com os automáticos preenchidos, e o segundo físico assina o Duplo Check, preso à versão do plano. Inclui os índices de qualidade e o catálogo MPPG 11.a.
**FRs covered:** FR-10..21, 40 (Plano), 42, 43

### Épico 4 — Radioteraficha na Torre e no banco, com o papel intacto

A equipe usa Capa, Fichinha, Total e Agenda dentro da Torre. O estado do módulo passa a morar no PostgreSQL, com versão, vínculo pendente e correção que não se apaga. Ficha, capa, alta, imagens e DRR saem idênticos aos de antes, e a Virtual abre pelo cartão Tratamento.
**FRs covered:** FR-9 (módulo), FR-40 (Radioteraficha) · SR-1..12

### Épico 5 — Garantia da Qualidade — programa de CQ por máquina

O técnico registra o CQ do dia sem digitar "conforme". O físico recebe no mesmo dia o que está fora da tolerância, vê a carta de controle e mantém instrumentos, aferição com decaimento e a calibração TRS-398 calculada. Os testes de imagem saem do pylinac, e o HDR e a troca de fonte entram no programa.
**FRs covered:** FR-22..28, 36, 40 (GQ), 44, 45, 46 · SR-17, 18

### Épico 6 — Segurança do paciente — notificar e conduzir incidentes

Qualquer perfil registra um quase-incidente em até 90 s. O físico e o SPR/gestão conduzem o art. 26 e os prazos do Notivisa, tiram a análise até o fechamento e veem onde o erro nasce e onde é pego, com leitura restrita e notificador oculto.
**FRs covered:** FR-29..32, 40 (Segurança), 47 (ciclo), 48 · SR-13, 14

### Épico 7 — Documentação e conformidade — vencimentos do serviço

O físico e o SPR/gestão acompanham num só painel os vencimentos do serviço com fonte (treinamentos, auditoria, levantamento, ASO por IOE, autorização, alvará, monitoração) e os prazos da GQ, com o `ppr-streamlit` aposentado depois da conferência.
**FRs covered:** FR-33, 34, 35, 40 (Documentação) · SR-16

### Épico 8 — Matriz de risco em tempo real

O físico vê o risco do processo clínico por prática e etapa acompanhando o estado medido das barreiras (vindo das verificações do Plano, da GQ e da Segurança). O ISOCENTRO propõe a mudança de nível e o físico confirma. O SEVRRA segue em paralelo até a CNEN aceitar.
**FRs covered:** FR-47 (vínculo), FR-49 · SR-15

## Epic 1: Entrar no ISOCENTRO pela Torre, com identidade que vale no banco

Cada pessoa entra com o próprio login, conferido no banco, e encontra a Torre de controle com as clínicas que lhe cabem.

### Story 1.1: R-16 — Escopo, perfis e riscos da Fundação

Frente R-16 (voce · pendente). Cobre FR-7, NFR-10, AR-23, AR-33. É pré-requisito de gestão: nada grava no banco antes dela.

**Acceptance Criteria:** o "pronto quando" da R-16 no `DESTINO.md`.

### Story 1.2: R-17 — PostgreSQL 18 em `clinica-python01`

Frente R-17 (clinica · pendente). Cobre AR-4, AR-7, AR-8 (pasta da âncora), AR-22.

**Acceptance Criteria:** o "pronto quando" da R-17.

### Story 1.3: R-18 — Núcleo: esquema, `nucleo.gravar` e log encadeado

Frente R-18 (voce · pendente). Cobre FR-3, AR-4..7.

**Acceptance Criteria:** o "pronto quando" da R-18.

### Story 1.4: R-19 — Identidade: login no banco, capacidades, RLS e migração do núcleo

Frente R-19 (voce · pendente). Cobre FR-7, NFR-6, AR-9..12, AR-25, AR-30 (keyring).

**Acceptance Criteria:** o "pronto quando" da R-19.

### Story 1.5: R-78 — Tabela perfil → capacidades configurável

Frente R-78 (voce · pendente). Cobre FR-7, AR-31.

**Acceptance Criteria:** o "pronto quando" da R-78.

### Story 1.6: R-22 — Degraus no PostgreSQL, banco fora e exportador

Frente R-22 (voce · pendente). Cobre NFR-2, NFR-3, NFR-7, AR-15, AR-19, AR-21.

**Acceptance Criteria:** o "pronto quando" da R-22.

### Story 1.7: R-58 — Camada `rt/`: dividir `dicom/` em modelo, leitura e desenho

Frente R-58 (voce · pendente). Cobre AR-26.

**Acceptance Criteria:** o "pronto quando" da R-58.

### Story 1.8: R-23 — Porte PySide6 e shell Torre de controle

Frente R-23 (voce · pendente). Cobre FR-9, AR-24, UX-DR1..20. Inclui teclado, acessibilidade, estados e versão do PySide6 (P-4).

**Acceptance Criteria:** o "pronto quando" da R-23.

### Story 1.9: R-25 — Backup cifrado e restauração

Frente R-25 (clinica · pendente). Cobre AR-20, FR-28 (base).

**Acceptance Criteria:** o "pronto quando" da R-25.

Já feitas e que servem a este épico: R-24 (teste de arquitetura, AR-1, AR-2), R-59 (raio de revisão, AR-3), R-56 (versões fixas).

## Epic 2: Verificação confiável de ponta a ponta

O físico confia no que a verificação diz, e qualquer um prova que o registro não foi alterado.

### Story 2.1: R-82 — Origem `provisoria` da tolerância no catálogo

Frente R-82 (robo · pendente). Cobre FR-1. Base já feita: R-77 (contrato puro do motor).

**Acceptance Criteria:** o "pronto quando" da R-82.

### Story 2.2: R-20 — Motor de verificação

Frente R-20 (voce · pendente). Cobre FR-2, AR-13, AR-14. Inclui o FR-39 (P-2). Base já feita: R-76 (esquema ESAPI v1).

**Acceptance Criteria:** o "pronto quando" da R-20.

### Story 2.3: R-61 — Contrato ESAPI: esquema versionado e inventário dos scripts

Frente R-61 (voce · pendente). Cobre AR-14, AR-28.

**Acceptance Criteria:** o "pronto quando" da R-61.

### Story 2.4: R-08 — Instalar a concentradora no `clinica-python01`

Frente R-08 (clinica · pendente). Cobre AR-16.

**Acceptance Criteria:** o "pronto quando" da R-08.

### Story 2.5: R-21 — Alerta, assinatura e concentradora

Frente R-21 (voce · pendente). Cobre FR-5, FR-8, FR-41, AR-16..18. Inclui a âncora diária (FR-3, P-3).

**Acceptance Criteria:** o "pronto quando" da R-21.

### Story 2.6: R-83 — Módulo Software e sistemas: catálogo, promoção, sensibilidade, cobertura e SOUP

Frente R-83 (voce · pendente; nasceu da P-1). Cobre FR-4 (tela), FR-6 (relatório em tela), FR-37, FR-38.

**Acceptance Criteria:** o "pronto quando" da R-83.

### Story 2.7: R-60 — `MANIFESTO` e raiz de composição única

Frente R-60 (voce · pendente). Cobre AR-27. Depende de R-18, R-20 e R-23.

**Acceptance Criteria:** o "pronto quando" da R-60.

### Story 2.8: R-26 — Relatório de validação do núcleo

Frente R-26 (voce · pendente). Cobre FR-40 (núcleo), AR-32.

**Acceptance Criteria:** o "pronto quando" da R-26.

## Epic 3: Plano — segunda checagem, Aprovação Física e Duplo Check

Ordem da fila: insumos → MVP 1 → entrada do MVP 2 (R-07) → MVP 2 → tela e validação.

### Story 3.1: R-27 — Decisões do físico para o módulo Plano

Frente R-27 (voce · pendente). Pré-requisito: linhas do Plano no `riscos.md`.

**Acceptance Criteria:** o "pronto quando" da R-27.

### Story 3.2: R-09 — Tabelas de feixe dos aceleradores do serviço

Frente R-09 (clinica · pendente). Cobre FR-10.

**Acceptance Criteria:** o "pronto quando" da R-09.

### Story 3.3: R-29 — Comissionamento da segunda checagem por máquina

Frente R-29 (clinica · pendente). Cobre FR-14.

**Acceptance Criteria:** o "pronto quando" da R-29.

### Story 3.4: R-30 — Segunda checagem 3D no motor

Frente R-30 (voce · pendente). Cobre FR-10..13, FR-15.

**Acceptance Criteria:** o "pronto quando" da R-30.

### Story 3.5: R-31 — Clarkson por ponto de controle para IMRT/VMAT

Frente R-31 (voce · pendente). Cobre FR-12, FR-13 (modulado).

**Acceptance Criteria:** o "pronto quando" da R-31.

### Story 3.6: R-32 — Índices de qualidade como verificações `plano.*`

Frente R-32 (voce · pendente). Cobre FR-43.

**Acceptance Criteria:** o "pronto quando" da R-32.

### Story 3.7: R-07 — Conferir os 165 cursos contra o ARIA

Frente R-07 (voce · pendente). Condição de entrada do MVP 2 (FR-15).

**Acceptance Criteria:** o "pronto quando" da R-07.

### Story 3.8: R-28 — Códigos das atividades PSQA, Aprovação Física e Duplo Check no `variandw`

Frente R-28 (clinica · pendente). Cobre FR-16 (P6).

**Acceptance Criteria:** o "pronto quando" da R-28.

### Story 3.9: R-33 — Sequência real, alto risco e filas

Frente R-33 (voce · pendente). Cobre FR-16, FR-17, FR-18.

**Acceptance Criteria:** o "pronto quando" da R-33.

### Story 3.10: R-34 — Listas, conferência da prescrição e segunda assinatura

Frente R-34 (voce · pendente). Cobre FR-19, FR-20, FR-21, FR-42.

**Acceptance Criteria:** o "pronto quando" da R-34.

### Story 3.11: R-79 — Catálogo MPPG 11.a como verificações `plano.*`

Frente R-79 (voce · pendente). Cobre FR-19 (catálogo).

**Acceptance Criteria:** o "pronto quando" da R-79.

### Story 3.12: R-35 — Tela do módulo Plano

Frente R-35 (voce · pendente). Cobre FR-9 (Plano).

**Acceptance Criteria:** o "pronto quando" da R-35.

### Story 3.13: R-36 — Relatório de validação do Plano

Frente R-36 (voce · pendente). Cobre FR-6, FR-40 (Plano).

**Acceptance Criteria:** o "pronto quando" da R-36.

## Epic 4: Radioteraficha na Torre e no banco, com o papel intacto

### Story 4.1: R-51 — Insumos do módulo Radioteraficha

Frente R-51 (voce · pendente). Inclui tirar Epimed e PyQt5 do EXPERIENCE.md (P-6).

**Acceptance Criteria:** o "pronto quando" da R-51.

### Story 4.2: R-52 — PDFs de referência e comparação página a página

Frente R-52 (robo · **estacionada**: `TCs_Teste` é paciente real em `_restrito/`; a fonte congelada da capa e o formato da referência esperam decisão sua). Cobre SR-3.

**Acceptance Criteria:** o "pronto quando" da R-52.

### Story 4.3: R-53 — Estado do módulo no PostgreSQL

Frente R-53 (voce · pendente). Cobre SR-4..SR-10.

**Acceptance Criteria:** o "pronto quando" da R-53.

### Story 4.4: R-54 — Encaixe Torre, recorte por perfil e retirada

Frente R-54 (voce · pendente). Cobre SR-1, SR-2, SR-11. Depende de R-23, R-32 e R-34 (Épico 3).

**Acceptance Criteria:** o "pronto quando" da R-54.

### Story 4.5: R-55 — Corte em produção e validação do módulo

Frente R-55 (clinica · pendente). Cobre SR-10 (varredura), SR-12, FR-40.

**Acceptance Criteria:** o "pronto quando" da R-55.

## Epic 5: Garantia da Qualidade — programa de CQ por máquina

### Story 5.1: R-37 — Decisões do físico para o módulo GQ

Frente R-37 (voce · pendente). Inclui B1 (`fff` e HDR no `programa-cq.csv`).

**Acceptance Criteria:** o "pronto quando" da R-37.

### Story 5.2: R-38 — Origem das imagens de CQ e das exportações de medida

Frente R-38 (clinica · pendente). Cobre FR-26, FR-46 (insumo).

**Acceptance Criteria:** o "pronto quando" da R-38.

### Story 5.3: R-39 — Programa de CQ, registro, fora de tolerância e vencidos

Frente R-39 (voce · pendente). Cobre FR-22..25, SR-17.

**Acceptance Criteria:** o "pronto quando" da R-39.

### Story 5.4: R-40 — Instrumentos, aferição e calibração TRS-398 calculada

Frente R-40 (voce · pendente). Cobre FR-36, FR-44, FR-45, SR-18. A parte TRS-398 espera o texto da IEC 62304 para a segregação (`decisoes-sem-base.md` #34).

**Acceptance Criteria:** o "pronto quando" da R-40.

### Story 5.5: R-41 — Análise de imagem pelo pylinac

Frente R-41 (voce · pendente). Cobre FR-46.

**Acceptance Criteria:** o "pronto quando" da R-41.

### Story 5.6: R-42 — HDR e importação de exportações

Frente R-42 (voce · pendente). Cobre FR-26, FR-27.

**Acceptance Criteria:** o "pronto quando" da R-42.

### Story 5.7: R-43 — Tela do GQ e relatório de validação

Frente R-43 (voce · pendente). Cobre FR-28, FR-40 (GQ), UX-DR10..12.

**Acceptance Criteria:** o "pronto quando" da R-43.

## Epic 6: Segurança do paciente — notificar e conduzir incidentes

### Story 6.1: R-44 — Decisões e insumos para o módulo Segurança do paciente

Frente R-44 (voce · pendente). Cobre FR-48 (kappa).

**Acceptance Criteria:** o "pronto quando" da R-44.

### Story 6.2: R-45 — NSP e Notivisa

Frente R-45 (clinica · pendente). Cobre FR-31 (insumo).

**Acceptance Criteria:** o "pronto quando" da R-45.

### Story 6.3: R-46 — Registro, leitura restrita, prazos e análise

Frente R-46 (voce · pendente). Cobre FR-29..32, FR-47 (ciclo), SR-13, SR-14.

**Acceptance Criteria:** o "pronto quando" da R-46.

### Story 6.4: R-47 — Matriz, indicadores, tela e validação

Frente R-47 (voce · pendente). Cobre FR-48, FR-40 (Segurança).

**Acceptance Criteria:** o "pronto quando" da R-47.

## Epic 7: Documentação e conformidade — vencimentos do serviço

### Story 7.1: R-48 — Insumos do módulo Documentação

Frente R-48 (voce · pendente).

**Acceptance Criteria:** o "pronto quando" da R-48.

### Story 7.2: R-15 — PPR: extração de ASOs sem enviar texto a terceiros

Frente R-15 (voce · pendente). Cobre FR-35 (ASO).

**Acceptance Criteria:** o "pronto quando" da R-15.

### Story 7.3: R-49 — Vencimentos, ASO, monitoração e painel

Frente R-49 (voce · pendente). Cobre FR-33, FR-34, SR-16. Depende da R-39 (Épico 5).

**Acceptance Criteria:** o "pronto quando" da R-49.

### Story 7.4: R-50 — Migração do ppr-streamlit, tela e validação

Frente R-50 (voce · pendente). Cobre FR-35, FR-40 (Documentação).

**Acceptance Criteria:** o "pronto quando" da R-50.

## Epic 8: Matriz de risco em tempo real

### Story 8.1: R-80 — Insumos da matriz de risco

Frente R-80 (voce · pendente). Cobre FR-49 (catálogo).

**Acceptance Criteria:** o "pronto quando" da R-80.

### Story 8.2: R-81 — Matriz de risco em tempo real

Frente R-81 (voce · pendente). Cobre FR-47 (vínculo), FR-49, SR-15. Depende de R-33, R-39, R-46.

**Acceptance Criteria:** o "pronto quando" da R-81.

## Propostas para o DESTINO

Requisitos sem frente ou com frente incompleta. **Aceitas pelo usuário e gravadas em 26/10/2026**: P-1 virou a frente R-83; P-2..P-6 e P-8 ampliaram R-20, R-21, R-23, R-19, R-51, R-07 e R-08 no `DESTINO.md`; P-7 virou os itens #35–#37 do `decisoes-sem-base.md`.

### P-1 — Nova frente: módulo Software e sistemas (catálogo, promoção, sensibilidade, cobertura e SOUP)

- classe: voce · pilar: sistema global (PRD FR-4, FR-6, FR-37, FR-38; EXPERIENCE.md, Software e sistemas: "cadastra, promove, poda verificação")
- pronto quando: a tela do módulo lista o catálogo com estado (sombra, ativa, podada) e, para o físico, promove ou poda com o resumo da sombra gravado por `nucleo.gravar`; mostra o relatório de sensibilidade por verificação (semeados, detectados, não detectados); publica a cobertura (atividades com verificação ativa, sombra fora) sobre 74 e sobre 60, calculada do cadastro; gera o inventário SOUP com versão e licença a partir do `requirements.txt` + `constraints.txt`, com as ressalvas de risco conhecido; aceite da tela antes. Depende de R-20, R-21, R-23.
- Por quê: nenhuma frente cobre FR-37 e FR-38, e o relatório de validação de todo módulo (FR-40) exige o SOUP.

### P-2 — Ampliar R-20: integridade da transferência (FR-39)

- Acrescentar ao "pronto quando": toda execução registra o identificador e o checksum do arquivo lido (RT Plan) e a data da carga do `variandw`; teste prova que execução sem esses campos é recusada.

### P-3 — Ampliar R-21: âncora diária (AD-32, FR-3)

- Acrescentar: a concentradora grava todo dia o hash da ponta da corrente na pasta da TI só-acrescentar (R-17), e o verificador da R-18 compara a corrente com as âncoras, apontando registro e posição; teste com linha alterada depois da âncora.

### P-4 — Ampliar R-23: teclado, acessibilidade, estados e versão (UX-DR20..22, AR-30)

- Acrescentar:
  - anel de foco em todo clicável, ordem de Tab do EXPERIENCE.md, Alt+Home, Ctrl+Tab e Ctrl+P/Ctrl+Enter;
  - contraste conferido nos dois modos (texto ≥ 4,5:1, sinal ≥ 3:1);
  - estados "banco central fora", "`variandw` fora" e "nada precisa de ação" sem máquina "normal" nem zero por falta de dado;
  - versão do PySide6 fixada no `requirements.txt`/`constraints.txt` depois de conferida no PyPI.

### P-5 — Ampliar R-19: versão do keyring (AR-30)

- Acrescentar: `keyring` (WinVaultKeyring) e `pywin32` fixados depois de conferidos no PyPI.

### P-6 — Ampliar R-51: EXPERIENCE.md em dia

- Acrescentar à atualização do EXPERIENCE.md: tirar "envio ao Epimed" (o ISOCENTRO é o canal interno ao NSP desde 26/10/2026) e "PyQt5" (alvo PySide6, AD-36), além do cartão Tratamento que já está na R-51.

### P-7 — Itens novos em `decisoes-sem-base.md` (questões da UX sem referência)

A U3 já tem resposta no PRD: a Zona 2 mostra os alertas cujo responsável é o perfil da pessoa, na clínica (FR-41). As três abaixo não têm base, e vale a opção mais conservadora, anunciada como provisória:

- **U8, como se marca "visto":** por ação explícita da pessoa, nunca ao abrir. É a opção mais conservadora, porque abrir não prova leitura.
- **Destino do "Abrir fila":** a lista completa dos alertas do perfil na clínica, ordenada como a Zona 2.
- **Clique na máquina normal:** sem destino; a linha não é clicável enquanto não houver motivo.

### P-8 — Dar "pronto quando" à R-07 e à R-08

As duas são de antes do formato atual e não têm critério medível; o mapa usa as duas como histórias.

- R-07: os 165 cursos conferidos contra o ARIA nos itens (a)–(d) da conferência da LISTA (`notas/2026-09.md`, 10/09), divergências anotadas, e `LISTA_VERIFICADA_EM` gravado em cada curso conferido.
- R-08: o destino `RADIOTERAFICHA` aponta para `192.0.2.20:104` com a porta liberada, o share e a conta da Tarefa Agendada existem, e a concentradora roda pelo roteiro da R-03, com uma execução registrada.

## Validação final (26/10/2026, refeita depois das propostas gravadas)

| Verificação | Resultado |
| --- | --- |
| Starter template | não se aplica: brownfield, sem template na espinha |
| Tabelas criadas só quando necessárias | ok: o esquema do núcleo nasce na R-18 e cada módulo cria o seu schema na própria frente (AD-27) |
| Dependência para frente dentro do épico | ok: a ordem das histórias segue o "depende de" de cada frente |
| Dependência entre épicos | ok: 1 → 2 → 3 → 4; 5 e 6 depois do 2; 7 depois do 5; 8 depois de 3, 5 e 6 |
| Churn de arquivos | ok: MVP 1 e 2 do Plano juntos num épico, porque a tela (R-35) e a validação (R-36) já servem aos dois |
| Cobertura dos FR | ok: os 49 FR têm frente (R-83 nova; R-20 e R-21 ampliadas) |
| Cobertura dos UX-DR | ok: UX-DR20..22 entraram na R-23 |
| Critério de aceite em toda história | ok: R-07 e R-08 ganharam "pronto quando" |
| Questões da UX sem base | ok: U8, "Abrir fila" e máquina normal em `decisoes-sem-base.md` #35–#37, provisórias |
| Frente bloqueada | **R-52 estacionada**: falta decisão do usuário sobre a fonte congelada da capa e o formato da referência (`TCs_Teste` é paciente real). A frente existe e tem critério; a R-54 espera por ela |
