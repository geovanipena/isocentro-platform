# Extrato de entradas para o PRD do ISOCENTRO (16/10/2026)

Somente fatos extraídos, cada um com a fonte (arquivo:linha ou ID). Nada aqui é decisão nova.
Abreviações de caminho: `APP` = `Documents\isocentro\programa\isocentro`; `CON` = `Documents\isocentro\conhecimento`.

---

## A. O que o app faz hoje (`APP/README.md`, com conferência no código)

### A.1 Propósito e restrições declaradas

| Fato | Fonte |
| --- | --- |
| App **local** que gera a ficha técnica de tratamento a partir do DICOM-RT (TC, RP, RS, RD); mostra cortes e corpo 3D; exporta PDF (ficha, mapa de frações, alta, imagens) | README.md:3-6 |
| Dados do paciente não saem da máquina; o que é gravado vai para a pasta do paciente | README.md:8-9 |
| Python 3.12, Windows, PyQt5; entrada `run_gui.py`; empacotado com PyInstaller (`Isocentro.spec` → `ISOCENTRO.exe`), binários por GitHub Releases | README.md:13-20, 370-371 |
| Dependências com versão exata; atualizar exige revalidar a ficha contra o TPS | README.md:363-364 |
| Log de falhas tratadas em `~/.isocentro.log` (app sem console) | README.md:366-369 |
| Dados de paciente nunca versionados (`.gitignore`) | README.md:372-373 |
| Testes `unittest` (stdlib); fantomas sintéticos do SSD; 1 `expectedFailure` documentando defeito conhecido de interpolação em z (erro de 6,5 cm no fantoma) | README.md:337-356 |

### A.2 Telas/abas descritas no README

| Tela | O que faz | Fonte |
| --- | --- | --- |
| Ficha Total (bancada) | Formulário, cortes, 3D, agendamento multi-plano | README.md:27-28 |
| Fichinha | Campo único + botão; trilha Edição → Visualização → Impressão, "botão aceso = pronto"; Histórico | README.md:29-49 |
| Capa | Ficha de Tratamento institucional (2 páginas), do posicionamento à impressão; cadastro de simulação | README.md:51-64, 90-114 |
| Conferência | **Pendências** (o que a ficha deve) e **alertas de padrão** (`aprendizado.py`), que não preenchem campo | README.md:68-71 |

Observação: o README só descreve três telas. O código e o NOTAS citam também **Agenda**, **Ficha Virtual**, **Qualidade** e **Radioteradados** (ver A.4 e B). O README está defasado quanto às abas.

### A.3 Fontes de dados

| Fonte | Uso | Fonte do fato |
| --- | --- | --- |
| Pasta do paciente com `.dcm`/`.zip`/`.rar`; até 5 planos com RS/RD por referência DICOM; múltiplas TCs por `FrameOfReferenceUID` | Ficha técnica | README.md:75-78 |
| Data warehouse `variandw` (leitura apenas) → espelho local → relatórios exportados (3 degraus) | Capa, tratamento entregue, atividades, gatilho | README.md:285-292; `banco/capa_db.py:1,51` |
| Relatórios: `Capa_de_Tratamento_Periodo.csv`, `Prescrições por Período.csv`, `Lista_Pacientes_Periodo_Foto.xlsx` (lidos, nunca escritos) | Capa (último recurso) | README.md:164-172 |
| DB Daemon do ARIA (DICOM): `srvariadb.clinica.example:51404`, AE `ARIA` (Varian DB Service) | Exportação/C-MOVE de imagem e plano | `dicom/dicom_rede.py:80-91`; README.md:302 |
| Fotos e notas `.docx/.txt` da pasta do paciente; `SIMULACAO.json` + `POSICIONAMENTO.txt` | Folha 2 da capa, simulação | README.md:116-133, 222-257 |
| Registro versionado `FICHA_{NOME}_{REGISTRO}.json` + PNGs (sobrevive à exclusão do DICOM) | Reabrir e regerar ficha | README.md:259-271 |

**Atenção para o PRD:** `srvariadb` no código é o **servidor DICOM** (DB Daemon). Os status de plano e as atividades do care path são lidos do **`variandw`** (SQL), em `banco/gatilho_db.py` e `banco/atividades_db.py`, não do srvariadb.

### A.4 O que já existe (módulo → caminho)

| Capacidade | Caminho | Estado/observação | Fonte |
| --- | --- | --- | --- |
| Cálculo paralelo de UM (TG-219) | `isocentro/dominio/paralelo.py` (724 linhas) | TMR × Scp, fator distância e filtro; limites 3% atenção / 5% falha por campo; modulado 10% / 20% (rastreio, nunca veredito); `demonstracao=True` quando a tabela não é da máquina | README.md:294; paralelo.py:70-84, 594, 619-664 |
| Tabelas de feixe do paralelo | `APP/dados_feixe/` (`_maquinas.json` + CSV `<MAQ>__<E>MV__<TMR|SCP>.csv`) | Só `ELEKTA_SAT` 6 e 10 MV, marcado "dado de EXEMPLO", `nomes_dicom: []` (não casa com plano nenhum) | dados_feixe/_maquinas.json:2-27 |
| Índices de qualidade do alvo e complexidade dos campos | `dominio/qualidade.py`, `qualidade_metodo.py`; tela `interface/qualidade_tela.py` | Aba Qualidade (`qualidade.CALIBRADO` rege aviso de não calibrado) | README.md:295, 313; paralelo.py:75 |
| Máquinas, protocolos de imagem, gating | `dominio/constantes.py` | 5 máquinas: `TrueBeamSN1001` (rótulo **VitalBeam**), `TBuniverSN1002` (rótulo **TrueBeam**), `600CD`, `6EX`, `Synergy01` (Elekta/Monaco, unidade **SAT**) | constantes.py:40-68 |
| Regra imagem diária ≥ 501 cGy/fr; fracionamento vindo da prescrição | `constantes.DOSE_IMAGEM_DIARIA_CGY`, `tratamento_db.fracionamento_prescrito` | Feito em 23/09 | NOTAS.md:991-1015 |
| Agendamento multi-plano | `dominio/agendamento.py`, `interface/agendamento_tela.py` | — | README.md:297, 316 |
| Alertas de padrão | `dominio/aprendizado.py` | Advisory, não preenche campo | README.md:68-71, 298 |
| Gatilho de exportação (plano pronto) | `dominio/gatilho*.py`, `banco/gatilho_db.py` | "Aprovado" = `Planning Approved` (decisão 02/09/2026); escada medida: Unapproved, Planning Approved, Treatment Approved, Reviewed, 3rd Party Approval, Rejected, Retired, Completed, Completed Early, Unplanned Treatment | gatilho_db.py:89-104 |
| Tratamento entregue (Ficha Virtual) | `banco/tratamento_db.py`; telas `tratamento.py`, `tratamento_pecas.py`, `tratamento_janelas.py` | `LISTA_VERIFICADA_EM = ""` — falta conferir os 165 cursos contra o ARIA | README.md:289; NOTAS.md:1704-1719 |
| Pendências do ARIA por dono | `banco/atividades_db.py` | `CODIGOS = ("Documentação",)`; `CODIGOS_ALTA = ("Verificar Programação", …)`; `variandw` é case-sensitive | atividades_db.py:83, 123, 141 |
| Checklist pré-tratamento | `interface/checklist.py` + `checklist_pre_tratamento.json` | 6 itens: Nome/D.N/RGH/Foto; Prescrição (capa × ficha); Contra-Capa; Exames; Acessórios; Lateralidade e Anatomia — com marca, autor e data | CON/fichas/atividades/C01.md:43 |
| Objetos DICOM-RT e SSD | `dicom/dicom_rt.py` (SSD pelo EXTERNAL do RS; raycast por HU como fallback) | — | README.md:301, 360-362 |
| Soma de dose 3D, DVH, cortes, corpo 3D | `dicom/dose3d.py`, `dvh.py`, `cortes.py`, `corpo3d.py` | Cache do corpo 3D (07/10) | README.md:304; NOTAS.md:239-246 |
| Registro versionado e diff de versões | `dados/registro_json.py`, `dados/diff_versoes.py` | — | README.md:321; D03.md:41 |
| Índice central / histórico | `dados/indice.py`, `dados/historico.py` | — | README.md:322, 324 |
| Login, equipe, sessão única, preferências por usuário | `dados/auth.py`, `equipe.py`, `sessao.py`, `preferencias.py` | Último login vence; admin isento | README.md:323; NOTAS.md:920-956 |
| Inventário de imobilizadores | `dados/inventario.py` | Arquivo atual **fictício** | README.md:146-160 |
| Datas relevantes (quadro do serviço) | `dados/datas_relevantes.py` | JSON com lock | NOTAS.md:1219-1221 |
| PDFs | `papel/ficha_pdf.py`, `capa_pdf.py` (inclui campos "FÍSICO MÉDICO" / "DUPLO CHECK" na capa), `drr.py`, `rodape.py` | — | README.md:305-309; capa_pdf.py:907 |
| Agenda e indicadores de máquina | `banco/agenda_db.py`, `interface/agenda_tela.py`, `controle_agenda.py` | Taxa de ocupação, índice de disponibilidade | NOTAS.md:390-469; ls de `interface/` |
| Radioteradados (protótipo) | `interface/radioteradados_tela.py`, `controle_radioteradados.py` | Experimental, só físico/admin | NOTAS.md:167-193 |

---

## B. NOTAS.md — seções "EM ANDAMENTO"

| Linha | Título · data | Estado | O que fica aberto e toca o PRD |
| --- | --- | --- | --- |
| 31 | App passa a se chamar ISOCENTRO · 15/10/2026 | Código feito (260 arquivos, suíte 2327 OK) | Falta o usuário rodar o script de renomear pastas e o ramo `robo` (pacote com nome antigo). AE Titles `RADIOTERAFICHA`/`radioteraficha` cadastrados no ARIA **não mudam**. Compatibilidade de 3 nomes em variáveis/arquivos (NOTAS.md:46-67) |
| 70 | Reorganização da pasta central · 15/10/2026 | Commitado em parte | Movimentações pendentes com o usuário (dados identificados → `_restrito`, `scriptsvarian` → `programa\`). SPEC de incidentes copiado para `docs/planejamento/sistema-global/incidentes/` (NOTAS.md:87-88) |
| 110 | BMad como camada de planejamento · 13/10/2026 | Feito (overrides, `docs/qms`) | Decisões: ISOCENTRO é o núcleo; PPR e ESAPI entram como módulos; escrita no Eclipse só por script ESAPI validado em ambiente não clínico; extração de ASO passa a ser local (R-15). `docs/qms/escopo.md` "Em aberto": perfis de usuário, pasta do serviço, critério de validação dos scripts graváveis (escopo.md:52-57). `classificacao-62304.md` e `riscos.md` vazios para o físico preencher |
| 167 | Protótipo da aba Radioteradados · 13/10/2026 | Feito (9 testes) | Não inclui `dominio/ritmo`, fórmulas do núcleo RDC, aprovação, congelamento, PDF. Próximo: `bmad-spec` → frentes. Toca o módulo Indicadores |
| 195 | Quatro ajustes da análise BMad · 13/10/2026 | 3 feitos, 1 sem mudança | Sem tag de versão para o exe de 23/09; condição "fora da rede" sai como ERROR com traceback no log. Nada bloqueante para o PRD |
| 234 | Fluidez da demonstração · 07/10/2026 | Achados 1–5 resolvidos | Nenhum item marcado aberto. Fato útil: PRONTA de Elekta/Monaco não traz o aprovador ("Plano não aprovado — sem médico") (NOTAS.md:304-308) |
| 890 | Grupo Médico que segue a pessoa, e acesso único · 23/09/2026 | Pronto (25 testes) | Base para identidade do usuário (2ª assinatura): sessão única por usuário em `sessoes.json`; preferências em `preferencias.json` |
| 958 | Prescrição manda na ficha — quatro frentes · 23/09/2026 | Feito; nota da prescrição = `DWH.DimPrescription.Notes` | Decisão do usuário pendente: campo Notas da tela é uma linha só (a coluna aceita 1024 caracteres) (NOTAS.md:1052-1055) |
| 1058 | v8 — a Fichinha vira painel de listas · 22/09/2026 | Suíte fechada (2.113 OK) | Altas Prontas: consulta voltou vazia; código da atividade "ainda não está decidido" e falta a rodada `atividades.bat --consulta --palavra erificar`; `VERIFICADO_EM` cobre a Documentação, não a alta (NOTAS.md:1251-1260, 1404-1412) |

Outros abertos globais (NOTAS.md:1680-1735): varredura agendada nunca rodou em uso real; ficha temporária nunca exercitada com caso real; `LISTA_VERIFICADA_EM` não gravar enquanto a recontagem de 11/09 estiver aberta; exportação automática: falta rodada (itens 1 e 2) e decisão (item 4).

---

## C. Base de conhecimento (`CON`)

### C.1 Estrutura e regras (`CON/README.md`)

| Fato | Fonte |
| --- | --- |
| 4 camadas: texto integral (`texto/`), fichas (referências, manuais, código), matriz (`matriz/`), índices (`indices/`); mais fichas de atividade e dados do serviço (`servico/`) | README.md:5-12 |
| `matriz/atividades.csv` = 74 obrigações do catálogo v1 + itens PRÁTICA (origem `extensão-2026-10-16`); área nova I | README.md:16 |
| Fonte de verdade das ligações = cabeçalho da ficha; matriz é gerada | README.md:20 |
| Todo número traz `[CÓDIGO p. N]`; `obrigatório` só para norma brasileira (NN, RDC, Lei, NR); TG/MPPG/IAEA/ICRU = recomendação | README.md:21-22 |
| Nada identificado de paciente na base | README.md:23 |
| `programa-cq.csv` (sep. `|`) é fonte única dos testes de acelerador e ortovoltagem; `gerar_programa_cq.py` grava `servico/<CLÍNICA>/qualidade.json`, importável no `ppr-streamlit` (ramo `programa-cq-tg142`), substituindo só as listas de testes | README.md:65-67 |
| Clínicas: **CEL** (TrueBeam 4045, Clinac 6EX 1254, GammaMed IX, Dermopan), **BET** (Clinac 600CD 1196), **DUO** = Anápolis (VitalBeam 4199) | README.md:69 |

### C.2 `matriz/atividades.csv`

Colunas (sep. `;`): `id; area; atividade; gatilho; nivel; base; origem`. 100 linhas. Origem: `catalogo-v1` 73, `extensão-2026-10-16` 26, `v1 corrigido 2026-10-16` 1.

| Área | Atividades | Nível começa com "OBRIGATÓRIO" |
| --- | --- | --- |
| A. Equipamentos e dosimetria | 20 | 15 |
| B. TPS, sistemas e software | 10 | 4 |
| C. Paciente: simulação, planejamento e QA | 11 | 5 |
| D. Paciente: tratamento e acompanhamento | 6 | 5 |
| E. Braquiterapia HDR | 9 | 6 |
| F. Proteção radiológica e licenciamento | 13 | 12 |
| G. Gestão da qualidade, segurança e documentação | 19 | 13 |
| H. Ferramentas de rotina | 6 | 0 |
| I. Avaliação clínica do plano | 6 | 0 |
| **Total** | **100** | **60** |

Níveis (contagem): OBRIGATÓRIO-BR 45; PRÁTICA 26; OBRIGATÓRIO-BR + RECOMENDAÇÃO 7; RECOMENDAÇÃO 7; BOA PRÁTICA 5; demais variantes 10.

Linhas do MVP no CSV (gatilho; nível; base):

| ID | Atividade | Gatilho | Nível no CSV | Base |
| --- | --- | --- | --- | --- |
| C01 | Conferência da identificação, prescrição e dados de planejamento | Antes do planejamento e antes da 1ª sessão | OBRIGATÓRIO-BR | RDC 20 9.1, 9.2; NN 6.10 art. 24, I, d–e |
| C04 | Verificação do plano e do prontuário | Antes do 1º tratamento e revisões previstas | OBRIG. + RECOM. | RDC 20 9.1–9.2; MPPG 11.a |
| C05 | Cálculo independente de dose ou UM | Conforme procedimento e risco | OBRIG. + RECOM. | NN-6.10 art. 15, XI, e; RDC 20 9.7(c); TG-114; TG-219 |
| C09 | Gestação, marca-passo/CDI, próteses, reirradiação | Quando o caso indicar | RECOMENDAÇÃO | TG-36, TG-203, TG-275; RDC 20 9.1(a)(VI) |
| D03 | Revisão após mudança | Alteração clínica/técnica relevante | OBRIG. (documentação); fluxo a definir | RDC 20 9.1, 9.4; MPPG 11.a |
| H01 | Cálculo independente de UM | Conforme protocolo | **RECOMENDAÇÃO** | TG-114 |
| B10 | Validação OTS/SOUP | Na adoção e a cada atualização | PRÁTICA | FDA-OTS-2023; IEC-62304 |
| A04 | Calibração do sistema de referência | 2 anos; após reparo/suspeita | OBRIGATÓRIO-BR | NN 6.10 art. 49, p.ú., I–II |
| A05 | Aferição com fonte-teste | No mínimo trimestral | OBRIGATÓRIO-BR | NN 6.10 art. 49, p.ú., III |
| A11 | Instrumentos de grandezas de influência | Barômetro/termômetro 2 anos; régua/nível 5 anos | OBRIGATÓRIO-BR | NN 6.10 art. 52 |
| A12 | Monitores de área | Bienal e após reparo | OBRIGATÓRIO-BR | NN 6.10 art. 55 |
| E02 | Calibração do sistema de referência HDR | 2 anos e após reparo | OBRIGATÓRIO-BR | NN 6.10 art. 54 |
| E03 | Verificação da fonte e do cálculo de dose | Cada troca de fonte e protocolo de CQ | OBRIG. + RECOM. | NN 6.10 art. 24, I, b–e; TG-43, TG-56 |
| E06 | Taxa de kerma no ar antes de nova fonte | A cada nova fonte | OBRIGATÓRIO-BR | NN 6.10 art. 35, V |
| F04 | Monitoração ocupacional | Resultados mensais | OBRIGATÓRIO-BR | NN 6.10 art. 20, IV–V |
| F05 | Treinamento em proteção radiológica | Anual | OBRIGATÓRIO-BR | NN 6.10 art. 20, VI |
| F06 | Treinamento em física médica | Máximo 2 anos | OBRIGATÓRIO-BR | NN 6.10 art. 24, I, f |
| F07 | Instrumentos de proteção calibrados | Bienal | OBRIGATÓRIO-BR | NN 6.10 arts. 20, IX e 55 |
| F08 | Investigar e comunicar incidentes | Imediato; relatório à ANSN em 30 dias | OBRIGATÓRIO-BR | NN 6.10 art. 26; ANSN 3.01 art. 98, II |
| F13 | Blindagem e levantamento radiométrico | Projeto, mudança, licenciamento | **PRÁTICA** (CSV) | PQRT-BLINDAGEM; GUIA-CNEN-RT; NN-6.10 |
| G02 | Auditoria externa | Máximo 2 anos | OBRIGATÓRIO-BR | NN 6.10 art. 36 |
| G04 | NSP | Contínuo | OBRIGATÓRIO-BR | RDC 36/2013 arts. 4–8 |
| G05 | Notificar eventos adversos | Mensal até 15º dia útil; óbito 72 h | OBRIGATÓRIO-BR | RDC 36/2013 art. 10 |
| G15 | Aprendizado com incidentes | Contínuo | PRÁTICA | FORD-2012-ILS; WHO-ICPS-2009; UK-RT-TAXONOMIA; SNA-2019 |

### C.3 `matriz/programa-cq.csv`

Colunas (sep. `|`): `chave | tipo | teste | tolerancia | referencia | aplica | atividade`. 103 testes.

| Frequência (`chave`) | Testes |
| --- | --- |
| testes_diarios | 22 |
| testes_semanais | 1 |
| testes_mensais | 31 |
| testes_semestrais | 1 |
| testes_anuais | 36 |
| testes_diarios_orto / mensais_orto / anuais_orto | 3 / 3 / 6 |

Etiqueta `aplica`: todas 60; orto 12; srs 12; kv,epid 7; eletrons 6; edw 2; epid 2; fff 1; kv 1. Atividade: A07 49; A20 12; A17 12; A14 10; A08 9; A10 5; A13 3; A03 2; A15 1.

Mapa máquina → etiquetas (`CON/scripts/gerar_programa_cq.py:15-24`, "confirmado pelo usuário em 16/10/2026: 6EX tem EPID; 600CD não tem (usa CR); nenhuma clínica usa filtro dinâmico; SRS/SBRT só no TrueBeam e no VitalBeam"):

| Clínica | Máquina | Etiquetas |
| --- | --- | --- |
| CEL | TrueBeam | todas, eletrons, kv, epid, srs (**sem fff**) |
| CEL | 6EX | todas, epid |
| CEL | Dermopan | orto |
| BET | 600CD | todas |
| DUO | VitalBeam | todas, eletrons, kv, epid, fff, srs |

Testes gerados por clínica (`servico/<CLÍNICA>/qualidade.json`):

| Clínica | Diários | Semanais | Mensais | Semestrais | Anuais | Orto (d/m/a) |
| --- | --- | --- | --- | --- | --- | --- |
| CEL | 22 | 1 | 29 | 1 | 35 | 3/3/6 |
| BET | 13 | 1 | 22 | — | 24 | — |
| DUO | 22 | 1 | 30 | 1 | 35 | — |

Cada teste no JSON: `tipo, teste, tolerancia, referencia, equipamento` (ex.: "Intertravamento de porta", Funcional, NN-6.10 art. 42; TG-142 T.I; MPPG-8b S1). **Synergy (SAT) não está no mapa** e não há programa de CQ para ela. HDR não está no `programa-cq.csv` (só acelerador e ortovoltagem; README.md:67).

### C.4 `servico/lista-verificacao-carepath.csv`

Colunas: `etapa; item; voto_sim_nao; situacao; fonte`. Fonte de todas as linhas: "LISTA-VERIF-CAREPATH (Forms 30/03/2026, 5 respondentes; placar lido das barras)". 33 itens; 28 mantidos, 5 removidos.

| Etapa | Itens mantidos (placar) | Removidos (maioria NÃO) |
| --- | --- | --- |
| 1. Planejamento (13, todos mantidos) | Nome do plano correto (5-0); Luz de campo em mama (3-2); Tolerância de mesa (5-0); Margem dos PTVs (4-1); Distribuição de dose e DVH (5-0); Dose diária/total × prescrição (5-0); Matriz de cálculo (5-0); Fases diferentes no mesmo isocentro (3-2); Contraste/Artefatos (4-1); Zerar origem da imagem (5-0); UM compatíveis com a dose (4-1); Coordenadas de ISO e localização (4-1); Máquina correta (5-0) | — |
| 2. Aprovação Física (8 mantidos de 12) | Distribuição de dose e DVH (3-2); Dose diária/total × prescrição (4-1); Máquina correta (3-2); Dias alternados (5-0); Curva de 4D (5-0); Concluir cursos anteriores (5-0); Orientações de agendamento (4-1); Se dose única, imprimir alta (4-1) | Normalização e ponto de referência (2-3); Contraste/Artefatos (1-4); Zerar origem (2-3); UM compatíveis (2-3) |
| 3. Duplo Check (8, todos mantidos) | Luz de campo em mama (3-2); Dose diária/total × prescrição (5-0); Fases no mesmo isocentro (3-2); UM compatíveis (4-1); Análise do planejamento (DVH) (5-0); Coordenadas de ISO (4-1); Máquina correta (5-0); Mudar data do duplo check se necessário (5-0) | — |

(linhas 2-34 do CSV)

### C.5 Fichas de atividade do MVP

#### MVP 1 — segunda checagem de cálculo

| Ficha | Norma | Exigência exata (fonte) | Lacuna PPR | Pendências / próximos passos |
| --- | --- | --- | --- | --- |
| **C05** | NN-6.10 art. 15, XI, e; RDC 20 9.7(c); TG-114; TG-219 | "Segundo sistema de cálculo de dose" [NN p. 4–5]. "Todo cálculo deve ser verificado até a terceira aplicação ou até a dose acumulada de 10% da dose total, o que ocorrer primeiro" [RDC-20 p. 10]. Limites: 3D 2% / 3,5% / 5% [TG-114 Tab. II p. 8]; IMRT/VMAT composto 3% homogêneo / 5% heterogêneo; campo único 5% / 7%; baixa dose/alto gradiente 5–10% [TG-219 Tab. 9 p. 12]; aceitação pelo plano composto [TG-219 p. 17]; nunca mudar o ponto para passar [p. 16] | não se aplica | Hoje só tabelas SAT (exemplo), não calcula campo com filtro. Cadastrar tabelas reais (TrueBeam, 6EX, 600CD DOSEMED/2010, VitalBeam, Synergy 15 MV e W60 a converter); comissionar o próprio cálculo (TG-219 Tab. 8 + casos TG-119); ajustar limites após validação; escrever no POP-019 a etapa com prazo (C05.md:19-53) |
| **H01** | NN-6.10 art. 15, XI, e; RDC 20 9.7(c) (ficha); TG-114 (CSV) | Ficha diz **obrigatório**; limites remetem a C05 | — | Tabelas reais "das quatro máquinas Varian"; app RT Plan Viewer existe para Synergy/SAT (H01-H06.md:20). Regra: planilha também é software (versão, dono, teste, registro) [YOO-2025 p. 8] (H01-H06.md:29) |
| **B10** | FDA-OTS-2023; IEC-62304 (prévia); YOO-2025-ISQM | Por software de prateleira: descrição, avaliação de risco, testes, manutenção [FDA-OTS p. 7–10] | não se aplica | Exemplo: pylinac usa kQ do TRS-398 de 2000 (+0,24% 6 MV, +0,48% 10 MV p/ PTW 30013) e não tem kQ para FC65-G/FC65-P. Candidato: inventário de SOUP do `requirements.txt` + licenças no relatório de liberação (B10.md:29, 45) |

Comissionamento disponível (`Documents\isocentro\comissionamento\CATALOGO.md`): VitalBeam 4199 (abr/2020; 6 MV, 6 MV-FFF, elétrons 6–15 MeV, filtros físicos 15–60°; `Pasta de Cálculo - Anápolis.xlsx` com PDP/TMR/OAR/fatores); TrueBeam 4045 (DOSEMED out/2020; 6, 10 MV, **6FFF e 10FFF**, elétrons; TMR por energia); 6EX 1254 (DOSEMED out/2020; 6 MV); 600CD 1196 (2010; 6 MV, filtros 15–60°); Synergy01 SAT (só conjunto do cálculo paralelo: TMR aberto, TMR W60, Scp de 6/10/15 MV; FW 0,269/0,286/0,283 e FD 1,03/1,044/1,053; convertidos só 6 e 10 MV aberto; sem relatório de comissionamento) (CATALOGO.md:5-60).

#### MVP 2 — revisão do plano, 2ª assinatura, sequência real

| Ficha | Norma | Exigência exata (fonte) | Lacuna | Pendências / candidato |
| --- | --- | --- | --- | --- |
| **C01** | RDC 20 9.1, 9.2; NN-6.10 art. 24, I, d–e; TG-275; MPPG-11a | Antes do tratamento: identificação, histórico com tratamentos anteriores, exames, diagnóstico e estadiamento, gravidez confirmada ou suspeita, tratamento combinado, médico solicitante (nome, especialidade, CRM), prescrição escrita [RDC 9.1 p. 9]; consentimento anexado [9.2 p. 9] | não se aplica | Checklist atual não tem tratamento anterior, gravidez, dispositivo implantado e consentimento; candidato: confronto automático prescrição ARIA × RT Plan (dose total, por fração, nº frações, energia, técnica) (C01.md:48-49) |
| **C04** | RDC 20 9.7(c,d), 9.8(a); NN-6.10 art. 17, IV e art. 24, I, e; TG-275; MPPG-11a | Verificação até a 3ª aplicação ou 10% [RDC 9.7c p. 10]; ficha com parâmetros de todos os campos [9.7d, 9.8a]; **planejamentos impressos em papel com segunda assinatura por conferência** [NN art. 17, IV p. 5]; TG-275: antes da 1ª fração com bloqueio [§5.A.1, §7 p. 11–17]; alto risco obrigatoriamente antes: dispositivo implantado, reirradiação/campo adjacente, hipofracionamento/SBRT, complexos [TG-275 p. 11]; fim de tratamento até 1 semana depois | não se aplica | **POP-019 não tem etapa de revisão independente nem de segunda checagem** (C04.md:50). Candidatos: POP com prazo; "Treatment Approved só após a física" como forcing function; plan check automático dos itens "F" do TG-275 com registro de quase-incidentes (C04.md:56-58) |
| **D03** | RDC 20 9.1, 9.4, 9.7(c,d); TG-275; MPPG-11a; POP-036 | 9.7(c) vale também para o cálculo novo de replanejamento [p. 9–10]; plano novo/modificado = revisão inicial completa [TG-275 p. 12]; Eclipse 15.6 MR5: protocolo de movimento pode se desvincular sem aviso ao copiar/desaprovar/trocar máquina [CRN p. 38]. Gatilhos POP-036: folga de máscara > 0,5 cm (1,0 cm laringe) ou variação > 1,0 cm pelve/tórax | não se aplica | Fluxo mínimo de 6 passos (D03.md:30-37); nível no CSV: "fluxo específico precisa ser definido" |
| **C09** | RDC 20 9.1(a) II e VI; TG-275; ESTRO-REIRR; Eclipse CRN | Gravidez e tratamentos anteriores registrados antes do tratamento [RDC p. 9]; dispositivos e RT prévia = "++" RPN 214 [TG-275 p. 21]; > 32.767 HU: sobrescrever HU [CRN p. 38] | não se aplica | TG-36, TG-203, TG-63 fora do acervo; candidato: campos obrigatórios na simulação (gravidez, dispositivo, prótese, RT prévia) que mandam o caso para revisão antes da 1ª fração (C09.md:32-36) |

Fatos de código ligados à sequência: o gatilho considera "aprovado" `Planning Approved`; `Treatment Approved` "só vem depois do controle de qualidade" (gatilho_db.py:91-93); caso 9000019ANA tinha Documentação aberta com plano em Planning Approved e nenhum em Treatment Approved (gatilho_db.py:96-98). Atividade lida hoje: só `Documentação` (atividades_db.py:83). Nenhum código lê a atividade "Duplo Check" (busca por "duplo check" só acha o rótulo da capa, capa_pdf.py:907).

#### MVP 3 — registro do programa de CQ (ver C.3) e MVP 5 — vencimentos

| Ficha | Exigência (fonte) | Situação PPR | Candidato / pendência |
| --- | --- | --- | --- |
| **A04** | Dois sistemas de referência (câmara 0,6 cm³, eletrômetro 4 dígitos, cabo) [NN art. 49 p. 12]; calibração **a cada 2 anos** na RBC e após conserto/suspeita [art. 49 p.ú. I–II]; placas paralelas calibradas ou intercomparadas [art. 50]; variação de N_D,w > 0,5–1% merece investigação | CEL FC65-G + TN30013; BET 2× TN30013; DUO 2× FC65-P; "bianualmente, nunca ambos ao mesmo tempo" (conforme) | Vencimento = calibração + 2 anos, **alerta 60 dias antes**, aproveitando o painel de vencimentos de ASO do `ppr-streamlit`; histórico de N_D,w com gráfico (A04.md:63). Pendência nº 6 (ICRU 90 no N_D,w) |
| **A05** | Aferição **no mínimo trimestral**, fonte-teste própria, **±1%** [NN art. 49 p.ú. III p. 12]; antes e depois de transporte [IV]; TECDOC: em cada uso 2%, fuga 0,1% [Tab. XIII p. 48] | PPR não escreve ±1% nem correção de decaimento do Sr-90 (meia-vida 28,8 anos, ~0,2%/mês) | Calculadora de aferição com decaimento, ±1%, alerta trimestral por sistema; planilha atual em `G:\Meu Drive\...\LINEARIDADE, REPRODUTIBILIDADE E FUGA.xlsx` (A05.md:49, 61) |
| **A11** | Barômetro (0,5 mmHg aneroide / 0,1 hPa digital) e termômetro (0,25 °C): **2 anos** RBC; régua (0,5 mm) e nível: **5 anos** [NN art. 52 p. 13]; TECDOC: barômetro trimestral 1 mmHg | Calibração anual (conforme); resolução não informada | Mesmo cadastro de vencimentos da A04; conferência trimestral do barômetro (INMET) |
| **A12** | Monitor de área: calibração **2 anos** RBC e após conserto [NN art. 55 p. 13]; HDR: detector na sala e indicador no comando [art. 56] | As 3 clínicas só têm Geiger-Müller | Confirmar instrumento do levantamento radiométrico; cadastro de vencimentos |
| **E02** | Câmara poço: calibração **2 anos** RBC; aferição **trimestral ±1%**; antes/depois de transporte [NN art. 54 p.ú. p. 13]; TECDOC: checagens redundantes a cada uso 2% [Tab. XIV p. 49] | HDR 1000 Plus s/n A001242 (CEL); PPR não descreve a aferição trimestral nem ±1% | Conferir se a calibração está dentro dos 2 anos |
| **E03** | Testes diários de segurança [NN art. 35, III]; recolhimento, temporizador verificado, cofre, pinça ≥ 15 cm, cortador [art. 63]; na troca: segurança e indicadores de posição [art. 64]; posição da fonte diária 1 mm [TECDOC Tab. X p. 45] / diária e troca 1 (2) mm [MPPG-HDR Tab. 4 p. 10]; atividade console × tabela 1% | PPR faz posição só trimestral; faltam temporizador, bateria, data/hora e atividade decaída, kit de emergência; `ppr-streamlit` só tem diária e trimestral para braqui (falta "na troca de fonte" e anual) | Checklist diário HDR + decaimento (H02). Fonte Ir-192 10 Ci, troca a cada 4 meses (POP-023) |
| **E06** | S_K **antes do uso** de cada fonte nova [NN art. 35, V p. 9]; medido × certificado 3% recomendado, **5% exigido** [MPPG-HDR Tab. 4 p. 10]; decaimento no TPS 1% [Tab. 7 p. 14] | PPR: "trimestral, 2%" — deve ser por evento (fonte nova) | Registro de troca de fonte com bloqueio do "liberado" até a medida |
| **F04–F07** | F04 doses mensais a cada IOE [NN art. 20, IV–V]; limites IOE 20 mSv/ano, público 1 mSv [NN-3.01 p. 17–18]; F05 treinamento PR **anual** [art. 20, VI]; F06 física médica **≤ 2 anos** [art. 24, I, f]; F07 instrumentos de proteção **bienal** [arts. 20, IX; 55] | Vencimentos de ASO e certificados hoje no `ppr-streamlit` | Unificar no ISOCENTRO o que está no `ppr-streamlit` (F01-F07.md:34). F03: um SPR só responde por um serviço (art. 19) |
| **F13** | Monitoração de área antes da operação, **no máximo a cada 2 anos** e após modificação [NN art. 29 p. 9]; modificação de blindagem: aprovação prévia [art. 33] | Ficha diz OBRIGATÓRIO-BR; CSV diz PRÁTICA | 10 MV e 10FFF do TrueBeam: conferir se cálculo e último levantamento cobrem (Pendência 13) |
| **G02** | Auditoria externa **no máximo a cada 2 anos** [NN art. 36 p. 9]; avaliação externa (G03) a cada 4 anos [RDC 20 6.9] | Comprovante anexo ao PPR | ISOCENTRO como sistema do programa de GQ: POPs com versão/revisão; CQ com execução registrada; auditoria com plano de ação (G01-G03-G13.md:25) |

Agregado A01–A20 (cabeçalhos das fichas): 20 fichas; nível OBRIGATÓRIO-BR em 13, OBRIG. + RECOM. em 4 (A07, A08, A09, A20), RECOMENDAÇÃO em 1 (A10), PRÁTICA em 3 (A17, A18, A19). `lacuna_ppr`: true em 6 (A07, A08, A17, A18, A19, A20), parcial em 8 (A03, A05, A06, A10, A12, A14, A15, A16), false em 5 (A01, A02, A04, A11, A13), a-confirmar em 1 (A09). `isocentro: candidato` em 16; `nao-se-aplica` em 4 (A01, A02, A16, A19). A17/A18/A19 só CEL e DUO (600CD sem EPID); A20 só CEL (Dermopan 50 kV); A09 clínicas a confirmar.

#### MVP 4 — incidentes e quase-incidentes

| Ficha | Exigência (fonte) | Lacuna | Candidato |
| --- | --- | --- | --- |
| **F08** | Investigar **imediatamente**; determinar dose recebida e distribuição; medidas corretivas; prevenir reincidência; relatório à CNEN/ANSN **em até 30 dias** da identificação; **informar por escrito paciente e médico solicitante** [NN-6.10 art. 26 p. 8]; RDC 20 lista como evento tratamento por equívoco, falha de equipamento, erro de dose [p. 8] | lacuna_ppr: a-confirmar | Registro com o fluxo do art. 26: data de identificação, prazo de 30 dias contando, dose estimada, comunicação ao paciente e relatório (F08.md:48). Padrões de falha dos casos (Panamá, Glasgow, Toulouse, Costa Rica, Białystok, Épinal) ligados a controles (F08.md:35-42) |
| **G04** | NSP e plano de segurança [RDC 36 arts. 4–8 p. 2] | Confirmar se o NSP do grupo inclui a radioterapia | — |
| **G05** | Notificação **mensal pelo NSP até o 15º dia útil do mês seguinte; óbito em 72 h** [RDC 36 art. 10 p. 3] | — | Paralelo à comunicação nuclear de 30 dias (F08) |
| **G15** | ILS; WHO-ICPS-2009, UK-RT-TAXONOMIA; TG-275: registrar quase-incidentes achados na revisão (só 51% faziam) [p. 12] | **Não há registro de quase-incidentes no serviço** | Pacote mínimo: registro com taxonomia WHO-ICPS e campo "detectado em" (revisão de plano, 1º dia, semanal, tratamento); FMEA pequena (TG-275 pronto); revisão trimestral (G04-…md:24-28). `docs/qms/riscos.md` tem RD-1 a RD-5 com S, O e D em branco (G14) |

SPEC do módulo de incidentes v0.1 (14/10/2026) em `APP/docs/planejamento/sistema-global/incidentes/SPEC - Módulo incidentes v0.1.md`: ARIA somente leitura; **nenhuma escrita no Epimed** por automação; Epimed Patient Safety continua canal oficial do NSP; o módulo registra o envio e cobra pendências; flag "exposição médica não intencional" dispara checklist de investigação/comunicação à CNEN; modelo de dados Ford 2012 (etapa onde ocorreu e onde foi detectado, gravidade, fatores causais). **Pendente: mapear os campos reais do formulário Epimed** (seção 5 provisória) (SPEC:3-4, 8-29).

### C.6 Profundidade por área (`indices/o-que-falta.md`, `indices/cobertura.md`)

| Fato | Fonte |
| --- | --- |
| 100 de 100 atividades com ficha; candidatas a item do ISOCENTRO: A 16, B 10, C 11, D 6, E 6, F 13, G 19, H 6, I 6 | cobertura.md:136-146 |
| 114 documentos no acervo; 16 com ficha de fonte; 98 sem ficha; 16 nunca vinculados; TG-119 citado e fora do acervo | cobertura.md:148-160; o-que-falta.md:119 |
| Manuais: 74 convertidos, 2 com ficha; código externo: 61 repositórios, 1 com ficha (pylinac) | o-que-falta.md:121-122 |
| Área A: falta ficha do TG-198, procedimentos com DailyQA 3 e MapCHECK 2, **converter os testes de CQ em formulários do ISOCENTRO** | o-que-falta.md:107 |
| Área B: falta **declaração de definição e classe de cada módulo** (decisão do físico) em `docs/qms`; IEC 62304 completa e RDC 751/2022 fora do acervo | o-que-falta.md:108 |
| Área C: falta **lista de checagem consolidada (TG-275 + MPPG-11a + RDC + NN art. 17) no formato do checklist do ISOCENTRO** | o-que-falta.md:109 |
| Área D: falta desenho do painel de revisão semanal sobre o `variandw`; política de hipofracionamento | o-que-falta.md:110 |
| Área G: fichas de casos de incidente, TG-100, FORD-ILS, taxonomias; POPs (rev. 2021) a atualizar | o-que-falta.md:113 |
| Área H: validar cada ferramenta (B06/B10), "a começar pelo cálculo paralelo com as tabelas reais das quatro máquinas Varian e do Synergy (15 MV e W60)" | o-que-falta.md:114 |
| Área I: constraints **não transcritos** (QUANTEC, TG-101, ASTRO 2025, HyTEC, ESTRO-REIRR, ABFM-SRS) para `matriz/constraints.csv` | o-que-falta.md:115 |
| Ordem da 2ª passada: I → C (checklist) e H01 → E → repositórios/manuais | o-que-falta.md:124-129 |

---

## D. Itens em aberto que bloqueiam requisitos do MVP

| # | Item | Bloqueia | Fonte |
| --- | --- | --- | --- |
| D1 | Tabelas reais de TMR/Scp não cadastradas para TrueBeam, 6EX, 600CD, VitalBeam; Synergy 15 MV e W60 não convertidos; ELEKTA_SAT com `nomes_dicom: []` → todo resultado sai como demonstração | MVP 1 | C05.md:46-50; _maquinas.json:16-27; CATALOGO.md:52-60 |
| D2 | Paralelo não calcula campo com filtro; campos modulados só como rastreio (10%/20%) | MVP 1 (IMRT/VMAT, filtros 600CD/VitalBeam) | C05.md:46; paralelo.py:80-84 |
| D3 | Comissionamento do próprio cálculo paralelo (TG-219 Tab. 8, casos TG-119; TG-119 fora do acervo) e limites locais | MVP 1 (sair de "referência") | C05.md:51-52; cobertura.md:160 |
| D4 | Decisão do usuário sobre limites (código 3%/5% por campo × TG-219 composto 3%/5%, campo 5%/7%) | MVP 1 | paralelo.py:70-78; C05.md:28, 52 |
| D5 | Validação SOUP/ferramenta (B10/B06) e declaração de definição e classe de cada módulo em `docs/qms` (classificacao-62304.md vazio) | MVP 1 e todos | o-que-falta.md:108, 114; NOTAS.md:139-141 |
| D6 | Código/nome real das atividades "Duplo Check" e "Aprovação Física" no `variandw` não mapeados (hoje só `Documentação` e `Verificar Programação`); o próprio código de alta segue sem decisão | MVP 2 | atividades_db.py:83, 123; NOTAS.md:1404-1412 |
| D7 | Fluxo de aprovação: código usa `Planning Approved` como "aprovado"; MVP pede Aprovação Física/Treatment Approved; C04 propõe Treatment Approved só após a física (forcing function) — decisão de serviço | MVP 2 | gatilho_db.py:89-104; C04.md:57 |
| D8 | POP-019 sem etapa de revisão independente nem segunda checagem; prazo RDC não escrito | MVP 1 e 2 | C04.md:50; C05.md:53 |
| D9 | Lista de verificação consolidada (TG-275 + MPPG-11a + RDC + NN art. 17) no formato do checklist; checklist atual sem gravidez, tratamento anterior, dispositivo implantado, consentimento | MVP 2 | o-que-falta.md:109; C01.md:48 |
| D10 | Lista de tratamento entregue não conferida (`LISTA_VERIFICADA_EM = ""`, 165 cursos a olhar contra o ARIA) — base da contagem de frações/10% da dose | MVP 2 (alerta 3ª fração/10%) | NOTAS.md:1704-1719 |
| D11 | Monaco/Elekta não traz o aprovador do plano | MVP 2 para SAT/Synergy | NOTAS.md:304-308 |
| D12 | Instrumentos: câmara ≤ 0,03 cm³ SRS no TrueBeam (TN31010 é 0,125 cm³); câmara < 0,1 cm³ IMRT na BET; dispositivo planar IMRT na DUO; câmara do Dermopan; MapCHECK 2 da CEL como diário?; modelo do CR da BET | MVP 3 | PENDENCIAS.md:83-90 |
| D13 | Máquinas/feixes fora do PPR: TrueBeam 6FFF/10FFF (etiqueta `fff` ausente no TrueBeam); filtros físicos no VitalBeam e no 600CD (PPR "Não aplicável"); SRS/SBRT fora de "Técnicas" (CEL, DUO) | MVP 1 e 3 | PENDENCIAS.md:91-96; gerar_programa_cq.py:18 |
| D14 | Correções do PPR (linearidade das UM 1%, monitor secundário sem unidade, PDD de elétrons DUO, anticolisão, ortovoltagem 5%→3% e fuga ≤ 1 mGy/h, edição do TRS-398) | MVP 3 | PENDENCIAS.md:92 |
| D15 | Programa de CQ não cobre Synergy (SAT) nem HDR; `ppr-streamlit` sem frequência "na troca de fonte" e anual para braqui | MVP 3 | gerar_programa_cq.py:17-24; E03.md:53; README(CON).md:67 |
| D16 | Formato do registro de execução de CQ no ISOCENTRO não existe ("converter os testes de CQ em formulários do ISOCENTRO") | MVP 3 | o-que-falta.md:107 |
| D17 | Datas reais de calibração/certificados não estão na base (só modelos e s/n): conferir HDR 1000 Plus nos 2 anos; resolução dos instrumentos A11; relatórios de aceitação (onde estão) | MVP 5 | E02.md:37; A11.md:40; PENDENCIAS.md:93 |
| D18 | Vencimentos de ASO/certificados hoje vivem no `ppr-streamlit`; unificação no ISOCENTRO e extração local de ASO (LGPD, R-15) | MVP 5 | F01-F07.md:16, 34; NOTAS.md:136-139 |
| D19 | Campos reais do formulário Epimed não mapeados; NSP do grupo inclui RT? | MVP 4 | SPEC incidentes:29; G04 |
| D20 | FMEA: `docs/qms/riscos.md` com S, O e D em branco | MVP 4 e risco do produto | G04-G05-G14-G15-G17.md:20 |
| D21 | `docs/qms/escopo.md` em aberto: perfis de usuário, pasta do serviço na rede, critério de validação dos scripts graváveis | Todos (2ª assinatura depende de perfil) | escopo.md:52-57 |
| D22 | TG-36, TG-203, TG-63, TG-201, TG-66, MPPG 1.b, TRS-483, TG-106, RDC 751/2022, Lei 13.787/2018 fora do acervo | C09 (MVP 2), B (MVP 1) | PENDENCIAS.md:100 |
