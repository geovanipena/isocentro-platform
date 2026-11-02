---
codigo: DLT-GUIA
titulo: "Varian. Data Lineage Tool Reference Guide, versão 1.1.0.0 (P1037746-001-A), compatível com AURA 2.0 (15.6)"
ano: 2019
emissor: Varian Medical Systems
tipo: manual de fabricante
vigencia: "compatível com AURA 2.0 (ARIA 15.6); conferir a versão instalada"
atividades: [C04, G18, B04]
refs: [AURA-IFU-15.1]
manuais: []
repos: []
isocentro: []
texto: "../../texto/09 Sistemas Varian (cópias)/DLT-GUIA.md"
origem: "referencias/09 Sistemas Varian (cópias)/DLT-GUIA - Data Lineage Tool Reference Guide (v15.6).pdf"
conferida: 2026-10-21
---

# Data Lineage Tool (Varian, 2019): dicionário do data warehouse e dos modelos AURA

**Em uma frase.** Utilitário autônomo (`DataLineage.exe`) que documenta **todas as tabelas do data warehouse** do ARIA e os **modelos de relatório AURA** (de data warehouse e de tempo real), com busca por nome de coluna ou por sinônimo e a lista de tabelas usadas por cada modelo.

O PDF tem 12 páginas (1 só com imagem); texto limpo.

## Conteúdo

| Item | Conteúdo | Página |
| --- | --- | --- |
| Público | Serviços profissionais, suporte e **quem desenha ou personaliza relatórios AURA** | [DLT-GUIA p. 5] |
| Instalação | Zip do MyVarian; extrair e abrir `DataLineage.exe` | [p. 6] |
| Aba Search | Busca em colunas e *tags* de tabelas e modelos (ex.: "Gender" acha PatientSex); **Show** abre o esquema com a coluna destacada | [p. 7–8] |
| Aba Data Models | Escolher modelo de data warehouse ou de tempo real; descrição, uso pretendido, parâmetros, **tabelas usadas** e esquema | [p. 8–9] |
| Aba Table Search | Busca por nome de tabela (ex.: DimActivityAttribute) | [p. 9] |
| Personalizar | Descrições em **CSV separado por vírgula**: não usar vírgula, usar `@#@`; não alterar arquivos `.pak` (o utilitário trava) | [p. 10] |
| Pastas | `resources/app/files`: **TableSchema** em `Common`, **ModelSchema** em `AURA` | [p. 10–11] |

## Como se aplica no CLINICA

- C04 e B04: antes de escrever consulta ou relatório que leia o data warehouse (inclusive no ISOCENTRO), usar a ferramenta para achar a tabela e a coluna certas e registrar de qual modelo o dado vem.
- G18: a busca mostra onde estão os campos identificáveis (nome, sexo, foto), útil para pseudonimizar extrações.
