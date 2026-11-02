# O que falta, por área

Estado em 16/10/2026, ao fim da primeira passada. **A coluna está estruturada:** 100 de 100 atividades têm ficha, ligadas a fontes, manuais e código (`indices/por-atividade.md`, `indices/cobertura.md`, `matriz/vinculos.csv`). Esta página lista o que **aprofundar** em cada área. Pendências do serviço (equipamento, PPR, compras) estão em `PENDENCIAS.md`.

| Área | Profundidade hoje | O que falta para "a devida atenção" |
| --- | --- | --- |
| **A. Equipamentos e dosimetria** | **Alta**: tolerâncias de TG-142, MPPG-8b, TECDOC e NN conferidas na imagem; programa de CQ por clínica gerado e importável no `ppr-streamlit` (commit `82b5c1e`) | Ficha de fonte do **TG-198** (procedimento de cada teste); MPPG-IGRT e TG-179 em ficha própria; procedimentos passo a passo com os dispositivos reais (DailyQA 3, MapCHECK 2) e os fantomas; converter os testes de CQ em formulários do ISOCENTRO |
| **B. TPS, sistemas e software** | **Alta** no regulatório (RDC-657, P&R ANVISA, YOO-2025, IMDRF) e no Eclipse (release note 15.6 MR5) | Fichas de manual do **Beam Configuration**, do guia de **algoritmos** e do **DICOM Import/Export**; **declaração de definição e classe** de cada módulo (decisão do físico) em `docs/qms`; IEC 62304 completa e RDC 751/2022 fora do acervo |
| **C. Simulação, planejamento e QA** | **Alta**: RDC 20 item a item, TG-275 ("++" e automação), TG-219/TG-114 conferidos, TG-263 | Lista de checagem consolidada (TG-275 + MPPG-11a + RDC + NN art. 17) **no formato do checklist do ISOCENTRO**; ficha do **MPPG-CT-2021**; TG-36, TG-203, TG-63, TG-201, TG-119 e TG-66 fora do acervo |
| **D. Tratamento e acompanhamento** | **Média**: obrigações (NN, RDC) e MPPG-11a | Diretriz de compensação de interrupção (fora do acervo); política escrita para hipofracionamento; desenho do painel de revisão semanal sobre o `variandw` |
| **E. Braquiterapia HDR** | **Média-alta**: MPPG-HDR conferido, TECDOC, NN art. 54/63/64 | Fichas de fonte do **TG-43U1**, **TG-56**, **TG-59**, **TG-186** e **ICRU-89**; ficha de manual do **IFU GammaMedplus iX** (emergência, troca de fonte, CQ diário) e do guia de **anel e tandem**; confirmar o TPS de braquiterapia |
| **F. Proteção radiológica** | **Média**: NN-6.10 completa nos artigos de processo; NN-3.01 (limites) | Fichas de fonte da **NN-3.01**, **NN-3.02** (SPR, 2026) e do **GUIA-CNEN-RT**; **PQRT-BLINDAGEM** (método de cálculo); conferir o cálculo de blindagem do TrueBeam para 10 MV/10FFF |
| **G. Gestão da qualidade** | **Média**: obrigações mapeadas; TG-100, MPPG-PEER, MPPG-CHECKLIST e RDC 36 citados | Fichas dos **casos de incidente** (pasta 11, com o padrão de falha e o controle); fichas de **TG-100**, **FORD-ILS** e das taxonomias; atualização dos **POPs** (rev. 2021) com esta base; Lei 13.787 e CFM 1.821 fora do acervo |
| **H. Ferramentas** | **Média**: inventário do que existe e do que falta | Validação de cada ferramenta (B06/B10), a começar pelo **cálculo paralelo** com as tabelas reais das quatro máquinas Varian e do Synergy (15 MV e W60) |
| **I. Avaliação clínica do plano** | **Baixa nos números**: fontes localizadas e páginas indicadas, valores **não transcritos** | **Transcrever e conferir** as tabelas de constraints (QUANTEC p. 15–18, TG-101 Tab. III p. 9, ASTRO 2025, HyTEC, ESTRO-REIRR, ABFM-SRS) para `matriz/constraints.csv` |

## Acervo

- **16 fichas de fonte** de 114 documentos; os demais são citados direto nas fichas de atividade, com página. Lista completa em `indices/cobertura.md`.
- **16 documentos do acervo** ainda **não vinculados** a nenhuma atividade (artigos de plan check como FURHANG, DEWHURST, YANG-2012-ECHART e QCQ-FORD; NJEH e SNYDER, de modelagem; ROTEIRO-VISA-HDR; AURA e DLT-GUIA; IMDRF-N41; FDA-HF-CONTENT-FR; IEC-82304 prévia; AULA-NN-3.01; RADFORMATION-TG275).
- **Manuais:** 74 convertidos em `texto/manuais/`; **2 com ficha** (ESAPI 15.5, release note do Eclipse 15.6 MR5).
- **Código externo:** 61 repositórios citados nas fichas; **1 com ficha** (pylinac).

## Ordem sugerida para a segunda passada

1. **I** (constraints): maior valor clínico e base direta do plan check e dos scripts.
2. **C** (checklist consolidado no ISOCENTRO) e **H01** (cálculo paralelo com as tabelas reais).
3. **E** (fichas de TG-43U1, TG-56, IFU GammaMed).
4. Fichas de repositório da pasta 02 e 03 do `codigo-externo` (PlanCheck, ESAPI) e de manuais.
