---
id: SPEC-isocentro-radioteraficha
companions:
  - ../spec-isocentro-fundacao/SPEC.md
  - ../spec-isocentro-plano/SPEC.md
  - ../architecture-isocentro-2026-10-19/ARCHITECTURE-SPINE.md
  - ../prd-isocentro-2026-10-16/prd.md
  - ../ux-isocentro-2026-10-16/EXPERIENCE.md
  - ../ux-isocentro-2026-10-16/DESIGN.md
  - rastreabilidade.md
sources: []
---

> **Contrato canônico.** Esta SPEC e os arquivos em `companions:` são o contrato completo do módulo Radioteraficha (`modulos/radioteraficha`, telas em `interface/modulos/radioteraficha/`). Ela é construída **sobre a Fundação**: o porte mecânico para PySide6, a paleta nova, o shell, o banco central, a gravação única e as entidades de referência são de lá. Aqui ficam o encaixe Torre das telas Capa, Fichinha, Total e Agenda e a migração para o PostgreSQL de todo o estado em JSON do módulo. A aba Qualidade é do Plano (CAP de índices) e o checklist pré-tratamento é absorvido pela lista do Plano (FR-19/FR-21). Da UX valem Foundation (Migração), IA, Perfis e State Patterns; da espinha, AD-5, AD-9, AD-18, AD-23, AD-26, AD-36 e AD-37.

# ISOCENTRO — Módulo Radioteraficha

## Why

Visão e dívida. O Radioteraficha monta os documentos que vão à sala de tratamento (ficha técnica, capa, alta, página de imagens) e é a parte do ISOCENTRO em uso diário. Hoje ele tem visual próprio, que a UX substituiu pela Torre de controle para o app inteiro, e guarda o estado em JSON no share e na pasta do paciente, com lock de arquivo, correção que se apaga quando a divergência some e paciente identificado por nome e REG. A arquitetura proíbe dois padrões visuais e estado fora do banco. Esta spec leva o módulo para dentro da Torre e do PostgreSQL **sem mudar uma linha do papel**.

## Capabilities

Cada capacidade diz de onde vem o dado (**fonte**) e se muda o que sai impresso (**papel**). Nenhuma capacidade desta spec muda o papel.

- **CAP-1 — Módulo Radioteraficha no shell** (FR-9, AD-18)
  - **intent:** O usuário abre o Radioteraficha pela doca e encontra as abas Capa, Fichinha, Total e Agenda dentro do cabeçalho de módulo da Torre.
  - **success:**
    - Cabeçalho "◂ Início · Radioteraficha · abas · contexto", sem seletor de clínica, e barra de status com degrau e data.
    - Saem do módulo as abas Qualidade (vai ao Plano), Radioteradados (vai a Indicadores) e Ficha Virtual (CAP-11).
    - Recorte por perfil herdado de `MODOS_POR_PAPEL`, sem a Virtual: físico e admin veem as quatro; médico vê Agenda; os demais perfis veem Capa e Agenda; papel desconhecido cai no padrão, nunca em "todas".
    - O recorte é capacidade do núcleo, conferida também no banco, e não só aba escondida.
    - Liberar para impressão o caso que a automação preparou é capacidade de físico e admin.
    - Ctrl+O, Ctrl+E, Ctrl+H e Ctrl+G valem só dentro do módulo.
  - **fonte · papel:** tabela perfil → capacidades do núcleo · não muda.

- **CAP-2 — Componentes Torre nas quatro telas** (AD-18, AD-36, DESIGN.md)
  - **intent:** Capa, Fichinha, Total e Agenda passam a usar só os componentes Torre, com o layout interno de cada tela mantido.
  - **success:**
    - Botões pelos pesos novos (mapeamento de `btn_solido`, `btn_contorno`, `btn_fantasma`, `btn_perigo` no DESIGN.md → Ações); um sólido por tela, que anda com o trabalho.
    - Pendências e alertas de padrão da ficha viram linhas com chip de severidade de forma + cor (IEC 60601-1-8).
    - Reserva usada (espelho ou relatório) aparece em primeiro lugar, com degrau e data.
    - A árvore de widgets de cada tela é a mesma de antes, conferida por print antes/depois (`tools/tela.py`).
    - `test_padrao_visual` passa sem exceção nova no módulo; verde só na isodose.
  - **fonte · papel:** `ui.py` e `estilo.py` · não muda (nenhum PDF passa pelo Qt).

- **CAP-3 — Papel inalterado**
  - **intent:** Ficha técnica, capa, alta, página de imagens e DRR saem iguais aos de antes do redesenho e da migração.
  - **success:** Para um conjunto de casos de referência (`TCs_Teste` e `dicom-teste`), os PDFs gerados depois de cada corte são comparados com os PDFs de referência gerados antes, página a página; qualquer diferença reprova e, se for desejada, só entra com aviso ao usuário do que muda e por quê.
  - **fonte · papel:** DICOM-RT; `variandw` → espelho → relatório exportado · não muda.

- **CAP-4 — Registro versionado no banco** (AD-5, AD-9, `registro_json`)
  - **intent:** Cada geração da ficha grava no PostgreSQL uma versão do registro do paciente, e a ficha pode ser reaberta e regerada sem a TC.
  - **success:**
    - Geração com mudança cria versão nova que aponta a anterior; geração idêntica não cria versão.
    - Nenhuma versão é editada nem apagada.
    - PDFs e PNGs (cortes, DVH) continuam na pasta do paciente, com hash e caminho gravados no banco; hash divergente ao reabrir é avisado.
    - Reabrir e regerar a ficha sem DICOM sai do banco.
    - A exclusão de DICOM só é oferecida depois do registro gravado no banco e só remove arquivos do `PatientID` da ficha.
  - **fonte · papel:** DICOM-RT e formulário · não muda.

- **CAP-5 — Identidade pela chave canônica, com vínculo pendente** (AD-26, AD-23)
  - **intent:** O registro se liga ao paciente pela chave `Ser` + clínica; quando o REG ainda não resolve, ele é gravado mesmo assim e ligado depois.
  - **success:**
    - REG, nome e `PatientId` só existem como apelidos; nenhuma junção por nome.
    - REG sem `Ser` correspondente grava o registro com o apelido REG e vínculo `pendente`; a ligação à chave canônica acontece quando o `Ser` aparecer pelo mesmo `PatientId`, e entra no log.
    - Vínculos pendentes aparecem numa lista para o físico; o PDF sai normalmente.
    - O pendente não tem prazo: fica na lista até ligar pelo `PatientId`. Não há ligação à mão, pelo risco de ligar ao paciente errado, e sair da lista nunca é apagar o registro (AD-5).
    - Com o banco central fora, o PDF sai, a tela avisa "versão não registrada" e nada é gravado nem enfileirado.
  - **fonte · papel:** `variandw` (somente leitura) e DICOM · não muda.

- **CAP-6 — Correções da capa sem apagar** (AD-5, `correcoes`)
  - **intent:** A correção feita à mão num campo da capa que diverge do sistema de registro vira registro novo que aponta o anterior.
  - **success:**
    - Só o campo que diverge é gravado, com quem e quando.
    - A correção vigente é calculada; nada é marcado por UPDATE nem apagado.
    - Quando a fonte passa a concordar, a correção fica no histórico e deixa de ter efeito na capa.
    - Os relatórios exportados continuam lidos, nunca escritos.
  - **fonte · papel:** `variandw` e lançamento do usuário · não muda (a capa sai com a correção, como hoje).

- **CAP-7 — Cadastro SUS no banco** (`cadastro_sus`)
  - **intent:** A marcação de paciente SUS e o número do cartão ficam no banco, ligados à chave canônica.
  - **success:** A validação do número do cartão SUS continua a mesma; alterar a marcação é registro novo; o convênio do `variandw` continua sendo a primeira fonte (`sus_do_convenio`).
  - **fonte · papel:** `variandw` e lançamento do usuário · não muda.

- **CAP-8 — Simulação, notas de posicionamento e imobilizadores no banco**
  - **intent:** O cadastro de simulação, a biblioteca de notas de posicionamento e o inventário de imobilizadores ficam no banco; as fotos continuam na pasta.
  - **success:**
    - O conteúdo do `SIMULACAO.json` vai para o banco, ligado à chave canônica.
    - Fotos reamostradas e `POSICIONAMENTO.txt` continuam na pasta da simulação, com hash e caminho no banco, porque o técnico abre a pasta no explorador.
    - A Capa acha a simulação pelo paciente; vale a mais recente.
    - Cadastrar de novo no mesmo mês cria registro novo e substitui as fotos daquele cadastro.
    - Notas de posicionamento: os modelos (39) ficam numa tabela global; a nota criada para um paciente fica na clínica dele, sob RLS (AD-12).
    - O inventário de imobilizadores (máscara com contador de usos, VacLok vinculado ao paciente) é **por clínica**, sob RLS, porque o item carrega o paciente. O real vem de levantamento na prateleira, lançado pelo dosimetrista ou técnico.
    - Número de usos desconhecido nasce **vazio, nunca 0**, e a máscara sem número de usos aparece com aviso. O aviso aos 20 usos fica, provisório e sem fonte.
    - Vincular imobilizador nunca é bloqueado; só avisa.
  - **fonte · papel:** lançamento do dosimetrista ou técnico · não muda.

- **CAP-9 — Índice de fichas, preferências e histórico de uso no banco**
  - **intent:** O índice das fichas geradas, as preferências por usuário e o histórico de uso saem dos JSON.
  - **success:**
    - O índice (`registro_fichas.json`) é derivado das versões do registro no banco.
    - As preferências (ex.: médicos do painel) seguem a ordem sessão → estação → serviço → padrão, e a tela diz qual venceu.
    - O `historico_uso.jsonl` entra como histórico legado somente leitura.
  - **fonte · papel:** banco central · não muda.

- **CAP-10 — Migração por entidade** (AD-37, FR-40)
  - **intent:** Cada entidade do módulo sai do JSON para o PostgreSQL uma por vez, sem gravação dupla.
  - **success:**
    - Para cada entidade (correções, cadastro SUS, simulação, notas, inventário, preferências, registro versionado, índice, histórico do checklist, histórico de uso): migra, confere contra o JSON, e a partir do corte só o banco grava. O JSON fica somente leitura e depois é arquivado.
    - As `FICHA_*.json` das pastas dos pacientes entram por **varredura única** no corte do registro, com relatório do que entrou, do que não entrou e por quê; as pastas não são alteradas.
    - A varredura percorre a união das raízes: a raiz das simulações de cada clínica, as pastas do índice central (`registro_fichas.json`), as raízes de reindexação gravadas no `historico_uso` e as que a TI de cada clínica apontar. Ela inclui o JSON que só existe dentro de `ARQUIVOS_*.zip`.
    - O histórico do checklist pré-tratamento entra somente leitura.
  - **fonte · papel:** JSON do share e das pastas dos pacientes · não muda.

- **CAP-11 — Retirada do checklist e da Virtual do módulo**
  - **intent:** O checklist pré-tratamento dá lugar à lista do Plano, e a Ficha Virtual passa a abrir pelo cartão Tratamento.
  - **success:**
    - Depois do corte do checklist, não há gravação nova no `checklist_pre_tratamento.json` nem no banco por esta via; o histórico fica legível.
    - A Virtual, portada sem redesenho, abre pelo cartão Tratamento da doca, que deixa de ser "em construção", com o checklist em leitura e apontando para o Plano.
  - **fonte · papel:** `variandw`, índice e histórico do checklist · não muda.

- **CAP-12 — Validação do módulo** (FR-40)
  - **intent:** O módulo tem relatório de validação antes do primeiro uso real depois do redesenho e da migração.
  - **success:** O relatório cobre:
    - a comparação de PDFs da CAP-3;
    - os relatórios de migração conferidos item a item (CAP-10);
    - os casos de vínculo pendente, de banco fora e de correção que deixa de divergir;
    - o recorte por perfil.

    O relatório é assinado pelo físico.
  - **fonte · papel:** testes, migração e PDFs de referência · não muda.

## Constraints

- **Papel muda com aviso:** nenhuma capacidade altera campo, ordem, texto de célula ou geometria do PDF; diferença na comparação reprova (CLAUDE.md, regras do domínio).
- **Layout interno mantido:** o encaixe troca componentes e moldura, não a árvore de widgets das telas; layout novo exigiria descrição aceita antes de editar.
- **Nunca inventar dado:** campo sem fonte nasce vazio e a tela diz que falta; alerta de padrão não preenche campo (NFR-4).
- **Três degraus anunciados** para a capa: `variandw` → espelho → relatório, com degrau e data na tela (AD-16, AD-17).
- **Somente leitura** no `variandw` e nos relatórios exportados (NFR-1).
- **Nada se apaga nem se edita** em registro, correção, cadastro SUS ou simulação (AD-5).
- **Chave canônica** `Ser` + clínica; nome e REG só como apelidos (AD-26).
- **Banco fora:** nada gravado nem enfileirado; o papel sai (AD-23).
- **Corte sem gravação dupla** por entidade (AD-37).
- **Dado de paciente não sai da rede**, nem para log ou repositório (NFR-2).
- **Classe A** do módulo (IEC 62304; `classificacao-62304.md`, 26/10/2026): contam como medidas de controle externas a trava de aprovação do ARIA e a assinatura em papel da ficha e da capa. ANVISA classe I ou II até todos os testes.

## Non-goals

- Redesenho de layout das telas Capa, Fichinha, Total e Agenda.
- Redesenho da Ficha Virtual (spec do Tratamento).
- A lista de conferência que substitui o checklist (spec do Plano, FR-19/FR-21) e os índices de qualidade (spec do Plano).
- Radioteradados (módulo Indicadores).
- Qualquer mudança no que sai impresso.
- Porte PySide6, paleta, shell, Início e agenda da Zona 1 (Fundação).
- Escrita no ARIA, no `variandw` ou nos relatórios exportados.

## Success signal

- Em homologação, depois de todos os cortes: a Fichinha monta um caso de `dicom-teste`, o PDF sai idêntico ao de referência, a versão aparece no banco com hash dos PNGs, a TC é apagada e a ficha é regerada só do banco — e uma capa com correção à mão continua saindo com a correção, que fica no histórico quando a fonte passa a concordar.
- Um caso com REG ainda fora do `variandw` imprime, grava com vínculo pendente e se liga sozinho quando o `Ser` aparece.
- O relatório de validação do módulo (CAP-12) está assinado pelo físico.

## Assumptions

- **Banco fora:** o PDF sai e a exclusão de DICOM não é oferecida, porque o registro não foi gravado (Fundação CAP-16).
- **Histórico de uso:** é trilha do app inteiro (login, usuário criado); entra como legado somente leitura, fora da cadeia de hash do log do núcleo.
- **Ordem do corte do checklist:** só depois que a lista do Plano (FR-19/FR-21) estiver ativa; até lá segue em JSON.
- **Respostas pela regra do físico** (26/10/2026, a conferir por ele): inventário por clínica e levantado na prateleira, notas com modelos globais, vínculo pendente sem prazo e varredura pela união das raízes saíram da regra de decisão do `escopo.md`, não de resposta direta. O que ficou sem base está no `decisoes-sem-base.md`, itens 22 a 26.

## Open Questions

- **UX:** cartão Tratamento abrindo a Virtual portada diverge da doca (Tratamento "em construção"); atualizar EXPERIENCE.md.
- **riscos.md:** linhas do módulo (S, O, D pelo físico): papel que muda sem aviso na migração; versão do registro perdida; vínculo ligado ao paciente errado; correção que some.
- **Para a discussão no serviço** (`decisoes-sem-base.md`): limite de usos da máscara (#22); o "outro sistema" do inventário (#23); quem edita os modelos de notas e se as três clínicas usam o mesmo vocabulário (#24); prazo e providência para o pendente que nunca liga (#25); raízes reais do share, pela TI de cada clínica (#26).
