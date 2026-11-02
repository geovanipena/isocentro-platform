# LLM e IA em radioterapia — referências a incorporar ao ISOCENTRO

Levantamento de 2026-10-21. Filtro aplicado: escopo do ISOCENTRO (artigos revisados por pares, normativos e diretrizes). Preprints e resumos de congresso ficam na seção B até serem publicados. Nenhum item abaixo estava nas pastas 02, 07 e 08 na data do levantamento.

Cada linha traz o nome de arquivo proposto (padrão da base: CÓDIGO - Título (ano).pdf), a pasta de destino, o DOI e o requisito do sistema acessório que a referência sustentaria. A coluna de requisito é proposta, não está na matriz de rastreabilidade.

Itens marcados "via referência" entraram pela lista de referências de um artigo lido, sem leitura do próprio texto. Conferir o conteúdo ao baixar.

---

## A. Incorporar

### 02 Plan check e revisão de prontuário

| Arquivo proposto | DOI / fonte | O que a referência estabelece | Requisito proposto |
|---|---|---|---|
| COURT-2026-HAZARD - Can physics review catch prescription and PTV margin errors in fully automated plans (2026).pdf | 10.1002/acm2.70759 (JACMP, publ. 2026-09-28) | Estudo de hazard (MD Anderson, RPA, 20 próstatas, 5 casos com erro, 5 físicos). Prescrição errada detectada em 80% dos casos, sem falso positivo. Margem de PTV errada: 2 de 5 físicos não avaliaram margem; os outros 3 acharam todos os erros, mas com especificidade de 13–63%. Nome de estrutura com margem e estrutura de referência não melhoraram a detecção. Recomenda margens padrão por instituição, alerta embutido, checklist e verificação automática. | Verificação automática de margem CTV→PTV (independente da revisão humana); alerta quando a margem difere do padrão do protocolo. |
| NEALON-2022-CHECKLIST - Checklist for use with automatically generated radiotherapy plans (2022).pdf | 10.1002/acm2.13694 (JACMP 2022;23(9):e13694) | Checklist de 90 itens derivada do TG-275, TG-315 e de FMEA do RPA. Detecção de erros subiu de 3,4 ± 1,1 para 4,4 ± 0,74 por físico (p = 0,02), +20%. | Checklist específica para planos gerados por automação/IA, distinta da checklist de planos manuais. |
| STUHR-2022 - Automated plan checking software 3-year longitudinal analysis (2022).pdf | 10.1016/j.prro.2021.09.014 (PRO 2022;12(2):163-169). Via referência (Court 2026). | Melhoria sustentada de segurança e qualidade em 3 anos após plan check automatizado (MSKCC). | Evidência de efetividade do plan check automatizado ao longo do tempo; base para indicadores de desempenho do módulo. |
| BERRY-2020 - Efficiency and safety increases after a multi-institutional automated plan check tool (2020).pdf | 10.1002/acm2.12845 (JACMP 2020;21:51-58). Via referência (Fan 2026). | Ganho de eficiência e segurança após implantação de ferramenta de plan check automatizado multi-institucional. | Idem; complementa Covington 2016 e Gopan 2016, que já estão na pasta. |
| FAN-2026-AE - Interpretable deep-learning model for automated plan review of IMRT (2026).pdf | 10.3389/fonc.2026.1823869 (Front Oncol, publ. 2026-07-15) | Autoencoder para detectar planos anômalos, com explicação por perturbação de atributos. Distingue plano com erro (viola diretriz, pego por regra) de plano anômalo (dentro da diretriz, mas fora do padrão). AUC 0,98 com limiar fixado em 100% de sensibilidade. Limites: um centro, 576 planos, 18 anômalos, só mama com 2 tangentes + 2 campos IMRT. | Camada de detecção de outliers complementar às regras determinísticas, sempre com explicação de qual parâmetro gerou o alerta. |
| HUANG-2023-AE - Anomaly detection in radiotherapy plans using deep autoencoder networks (2023).pdf | 10.3389/fonc.2023.1142947 (Front Oncol 2023) | Trabalho anterior do mesmo grupo; base do FAN-2026. | Idem. |

### 03 Nomenclatura, prescrição e coordenadas

| Arquivo proposto | DOI / fonte | O que a referência estabelece | Requisito proposto |
|---|---|---|---|
| HOLMES-2024-TG263-LLM - Benchmarking a foundation LLM to relabel structure names per TG-263 (2024).pdf | PRO 2024;14(6):e515-e521. Preprint: arXiv 2310.03874 | GPT-4 com trechos do TG-263 no prompt, implementado como servidor DICOM. Em 50 pacientes por sítio, acurácia em OARs de 96,0% (próstata), 98,5% (cabeça e pescoço) e 96,9% (tórax). Em alvos: 100%, 93,1% e 91,1%. | Se houver LLM para renomear estruturas, ele só sugere. A aceitação passa por validação determinística contra a lista TG-263, e alvos exigem confirmação humana (acurácia menor). |

### 07 Risco, incidentes e segurança do paciente

| Arquivo proposto | DOI / fonte | O que a referência estabelece | Requisito proposto |
|---|---|---|---|
| WANG-2026-RCA-LLM - LLM-based root cause analysis of radiation oncology incidents (2026).pdf | 10.1371/journal.pdig.0001740 (PLOS Digit Health 2026;5(9)) | 19 casos públicos do RO-ILS, 4 LLMs (Gemini 2.5 Pro, GPT-4o, o3, Grok 3), prompt baseado nas diretrizes de RCA da AAPM. Todos alucinaram, de 11% a 61% (o preprint dizia 11–51%; vale a versão publicada). | LLM em análise de incidentes só como rascunho; causa raiz e ações sempre validadas por humano, com fonte citada para cada afirmação. |
| NEALON-2022-FMEA - FMEA of clinical adoption of automated contouring and planning tools (2022).pdf | 10.1016/j.prro.2022.01.003 (PRO 2022;12(4):e344-e353). Via referência (Court 2026). | FMEA da adoção clínica de contorno e planejamento automatizados; erro de usuário segue como modo de falha principal mesmo com automação. | Modelo de FMEA (TG-100) aplicado a módulos automatizados ou com IA do sistema acessório. |
| DEKERF-2025 - Multicentre prospective risk analysis of a fully automated radiotherapy workflow (2025).pdf | 10.1016/j.phro.2025.100765 (phiRO 2025;34:100765). Via referência (Court 2026). | Análise prospectiva multicêntrica de risco de fluxo totalmente automatizado; revisão manual inadequada de planos automáticos aparece como modo de falha de alta pontuação. | Idem; evidência para tratar viés de automação como risco explícito. |

### 08 Software, dispositivo médico e dados

| Arquivo proposto | DOI / fonte | O que a referência estabelece | Requisito proposto |
|---|---|---|---|
| HOLMES-2023-LLM-PHYSICS - Evaluating LLMs on radiation oncology physics (2023).pdf | 10.3389/fonc.2023.1219326 (Front Oncol 2023) | 100 questões de física (Mayo). GPT-4 superou a média dos físicos, mas o GPT-4 repete a mesma resposta entre tentativas, certa ou errada. Por isso, votação entre tentativas não melhora o resultado, enquanto a votação de um grupo de físicos superou o GPT-4 com folga. | Redundância de verificação precisa vir de fontes independentes (cálculo determinístico, outro método), nunca de repetir o mesmo LLM. |
| RTPHY-CHATBOT-2025 - RAG-based assistant for radiotherapy physics using LLaMA3 and AAPM reports (2025).pdf | 10.1002/acm2.70263 (JACMP, publ. 2025-10-09) | RAG sobre relatórios AAPM TG001–TG377 com Meta-LLaMA3-8B-Instruct; respostas com referência ao relatório de origem. Avaliado em apenas 20 perguntas-modelo. | Arquitetura de consulta ao próprio ISOCENTRO (RAG local, resposta sempre com documento e trecho de origem); conjunto de avaliação maior que o do artigo. |
| WANG-2025-GPTPLAN - Feasibility of automating radiotherapy planning with LLM agents (2025).pdf | 10.1088/1361-6560/adbff1 (PMB 2025;70(7)) | Sistema multiagente GPT-4 (dosimetrista + físico) em 12 pulmões IMRT e 5 colos VMAT, contra ECHO e planos manuais. LLM com visão foi impreciso ao ler imagens de dose. | Agente que interage com o TPS (via ESAPI) recebe dados numéricos (DVH, métricas), não imagens de dose. |
| OH-2024-LLMSEG - LLM-driven multimodal target volume contouring (2024).pdf | 10.1038/s41467-024-53387-y (Nat Commun 2024;15:9186) | Integra texto clínico (estadiamento, cirurgia, lateralidade) à delineação 3D de CTV em mama, com validação externa. | Referência de contexto; sem requisito direto no escopo atual. |
| PUTZ - Capabilities and limitations of LLMs for radiation oncology decision support (IJROBP).pdf | IJROBP; preprint arXiv 2501.02346. Ano, volume e DOI a confirmar. | Revisão crítica: desempenho inferior do GPT-4 em medidas de radiação, ginecologia e braquiterapia; limitação forte com informação visual. | Restrição de escopo: nada de LLM em decisão de braquiterapia ou dosimetria sem verificação independente. |
| NORRIS-2025 - Australasian survey on ChatGPT and LLMs in medical physics (2025).pdf | 10.1007/s13246-025-01571-9 (PESM 2025) | Físicos relatam ganho de eficiência, menos ganho de qualidade, preocupação com dados e falta de diretriz e treinamento. | Política institucional de uso de LLM (dados de paciente, revisão humana, treinamento). |
| IMDRF-N88-2025 - Good machine learning practice for medical device development guiding principles (2025).pdf | IMDRF/AIML WG/N88 FINAL:2025 (jan/2025), imdrf.org | 10 princípios de GMLP, harmonizados com FDA, Health Canada e MHRA. Complementa o N81-2025, que já está na pasta. | Princípios de ciclo de vida para qualquer componente de ML/LLM do sistema acessório. |

---

## B. Monitorar (fora do escopo até publicação revisada ou versão final)

| Item | Fonte | Por que acompanhar |
|---|---|---|
| DOLA — agente LLM local (LLaMA 3.1 8B/70B) para otimização no TPS, 18 próstatas 60 Gy/20 fx | arXiv 2503.17553 | Modelo local, sem envio de dados (LGPD). |
| SAGE — agente LLM com humano no circuito para planejamento de SRS (mesmo grupo do DOLA) | arXiv 2512.20586 | Traços de otimização como log auditável. |
| Agente LLM zero-shot para IMRT de cabeça e pescoço, 20 casos | arXiv 2510.11754; NeurIPS 2025 | Interação direta com TPS comercial sem fine-tuning. |
| Revisão "Applications of LLMs in Radiation Oncology" | arXiv 2604.03509 | Revisão mais recente encontrada. |
| RadOnc-GPT — agente com funções em lista branca sobre ARIA e Epic | arXiv 2509.25540 | Padrão de acesso controlado a banco clínico. |
| ARCoT — RAG + chain-of-thought sobre TGs, MPPGs e IAEA | arXiv 2405.11040 | Alternativa ao RTPhy. |
| Avaliação quantitativa de risco por RCA com LLM (Miami) | arXiv 2511.02223 | Continuação do WANG-2026. |
| ASTRO 2025: VLM para QA de dose em próstata; LLMs no RAPHEX 2024; AI-ILS com Llama 3.1 e HFACS | Resumos de congresso | Aguardar artigo completo. |
| FDA — AI-enabled device software functions: lifecycle management (minuta, jan/2025, docket FDA-2024-D-4488) | fda.gov | Ainda minuta no último acesso. |
| FDA — PCCP para AI-enabled device software functions (final dez/2024; atualização em 2025 citada por fonte secundária) | fda.gov | Confirmar versão vigente antes de incorporar. |
| IMDRF/AIML WG/N93 — Technical framework for AI life cycle management (minuta, 2026) | imdrf.org | Sucessor natural do N88. |

---

## C. Lacuna identificada

Não foi encontrado relatório de task group da AAPM nem documento da IAEA específico sobre LLMs em radioterapia. Até existir, o enquadramento normativo de um LLM no sistema acessório sai do que já está na pasta 08: tratar o modelo como software de terceiros (FDA-OTS-2023, IEC 62304), gerir risco pela ISO 14971 e TG-100, e aplicar os princípios do IMDRF N88.

---

## Update 22/10/2026 — achados novos (seção B, monitorar)

Busca de 22/10. Nenhum é artigo revisado com resultado completo; ficam em
monitoramento. Uso proposto no `analise-ia-2026-10-22.md`.

| Item | Fonte | Por que acompanhar |
|---|---|---|
| LLM sobre 10 anos de registros de manutenção de 4 LINACs (Stolen, Sohn — UChicago; Best in Physics, AAPM 2026) | medphys.uchicago.edu, notícia pré-congresso; sem resultado numérico | Texto de equipamento, sem dado de paciente: base da R-65 (Pareto de máquina parada) |
| The Daily Dose — resumo matinal por paciente e triagem de ensaios clínicos (Holmes, Waddle et al. — Mayo) | arXiv 2605.26346 | 3 campi; 83,6% usam diariamente ou várias vezes por semana; 27% relatam ≥10 min/dia. Avaliação só por questionário. Para o ISOCENTRO, o resumo determinístico já basta |
| LLM para agendamento de RT em ambiente simulado (Zhang et al. — Johns Hopkins) | arXiv 2605.12896 | 3 LINACs, 1.400 pacientes sintéticos, regras de viabilidade atendidas. Sem uso clínico. Referência para a aba Agenda, só como apoio com humano no circuito |
| AI-ILS — Llama 3.1 classificando incidentes pela HFACS | IJROBP, resumo (S0360-3016(25)01731-6) | 1.241 incidentes simulados; acurácia 53% → 80%; aplicado a 350 reais com revisão de dois especialistas. Contrapor ao WANG-2026. Base da R-68 |
| Agentes LLM sem referência, guiados pelo médico, no TPS (Yang et al.) | Med Phys 2026, doi 10.1002/mp.70592 | Agente que opera o TPS clínico; não lido (403) |

Continua sem relatório de task group da AAPM sobre LLM. A guia de ciclo de
vida de IA do FDA segue como minuta nas fontes encontradas (comentários de
2025 e 2026; a página do FDA não foi conferida).
