# PPR vivo — de onde vem cada seção (28/10/2026)

Decisões do usuário (28/10/2026):

- O PPR é construído **dentro do ISOCENTRO** e é **vivo**. Não é programa à
  parte nem JSON carregado e baixado: cada seção é lida do módulo dono daquele
  dado, e o documento muda quando o dado muda.
- **Cada módulo guarda as suas seções**, dado e texto. A Documentação só monta o
  documento pelas fachadas (spec Documentação CAP-10; AD-41 item 4).
- A **GQ** é dona de todo o controle de qualidade e do **inventário técnico dos
  equipamentos**, e alimenta o programa de GQ do PPR (Anexo H).

Consequências:

- O ramo `programa-cq-tg142` do `ppr-streamlit` **não vem**. A fonte do Anexo H
  é o programa de CQ versionado da GQ (CAP-1), não o `qualidade.json`.
- O `ppr-streamlit` fica como está, com o Streamlit Cloud intocado, até o corte.
  A R-15 (ASO sem IA) vive no ramo `r15-aso-local` e vem com a Documentação.
- Frentes: R-84 (inventário e seções da GQ) e R-85 (seções dos módulos e
  montagem), no `DESTINO.md`.

Fontes do levantamento: `Downloads\PPR\PPR.tex` (23 capítulos, CEL mai/2026),
o JSON do `ppr-streamlit` (33 chaves) e as seis specs de bloco.

## Seção → módulo dono

Uma seção é o dado vivo do módulo mais o texto versionado dele. A primeira
versão do texto sai do PPR vigente de cada clínica (CEL mai/2026, BET jul/2026,
DUO jan/2025), citado.

| # | capítulo do PPR | chave no JSON atual | módulo dono |
|---|---|---|---|
| 1 | Identificação da Instalação | `instalacao` | Fundação CAP-25 |
| 2 | Objetivo e Descrição | `textos_caps` | Documentação CAP-11 |
| 3 | Estrutura Organizacional | `supervisor`, `responsavel_tecnico`, substitutos, `diretor_clinico` | Fundação CAP-25 (função no cadastro de equipe) |
| 4 | Descrição dos IOEs | `equipes_*` | Fundação CAP-25 (marca IOE da Documentação CAP-9) |
| 5 | Classificação da Instalação | `instalacao.grupo/subgrupo` | Fundação CAP-25 (grupo e subgrupo da NN-6.02; corrigido em 28/10 ao ler o corpo) |
| 6 | Classificação e Descrição das Áreas | `textos_caps`, `imagens` | Documentação CAP-11 |
| 7 | Mecanismos e Controle de Acesso | `textos_caps` | Segurança CAP-15 (barreiras) |
| 8 | Equipamentos e Fontes Emissoras | `equipamentos` | GQ CAP-16 (inventário técnico) |
| 9 | Fontes de Referência | `fontes_referencia` | GQ CAP-16 |
| 10 | Instrumentos de Dosimetria | `conjunto_dosimetrico`, `instrumentos_medicao`, `outros_detectores`, `fantomas` | GQ CAP-16 (CAP-6) |
| 11 | Monitores de Área | `monitores_area` | GQ CAP-16 (CAP-6) |
| 12 | Programa de Garantia da Qualidade + Anexo H | `testes_*` (7 listas) | **GQ CAP-16 (programa da CAP-1)**; 12.3 Análise de riscos e o SEVRRA do anexo H: Segurança CAP-15 |
| 13 | Sistemas de Planejamento | `sistemas_planejamento` | Plano CAP-19 |
| 14 | Técnicas de Tratamento | `tecnicas_tratamento` | Plano CAP-19 |
| 15 | Cálculo de Barreiras e Estimativas de Dose | `textos_caps`, `pdfs` | Documentação CAP-11 |
| 16 | Monitoração Individual | `textos_caps` | Documentação CAP-11 (CAP-4) |
| 17 | Monitoração de Áreas | `pdfs` (levantamento) | Documentação CAP-11 |
| 18 | Gerência de Rejeitos Radioativos | `textos_caps` | GQ CAP-16 (fonte HDR decaída) |
| 19 | Controle Médico dos IOEs | `asos` | Documentação CAP-11 (CAP-3; R-15) |
| 20 | Treinamento em Proteção Radiológica | `textos_caps`, `vencimentos` | Documentação CAP-11 (CAP-1) |
| 21 | Educação Continuada | `textos_caps` | Documentação CAP-11 |
| 22 | Níveis Operacionais e Restrições | `textos_caps` | Documentação CAP-11 |
| 23 | Procedimentos de Emergência | `textos_caps` | Segurança CAP-15 |
| — | Anexos (autorização, levantamento, auditoria, SEVRRA, certificados) | `pdfs`, `vencimentos` | Documentação CAP-11 (documento de origem) + GQ (certificados) |

Por módulo: Fundação 4 capítulos, GQ 6, Plano 2, Segurança 2 (+ 12.3 e SEVRRA), Documentação 9 e os anexos.

A planta exata (números, letras de anexo, partes) está em `isocentro/dominio/ppr.py`: rejeitos só existe com
fonte radioativa (CEL: 23 capítulos e anexos A–R; DUO e BET: 22 e A–Q), e os anexos têm ordem própria.
