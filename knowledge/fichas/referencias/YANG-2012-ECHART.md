---
codigo: YANG-2012-ECHART
titulo: "Yang D et al. Technical Note: Electronic chart checks in a paperless radiation therapy clinic. Med Phys 39(8):4726–4732"
ano: 2012
emissor: Washington University, St. Louis (artigo, Medical Physics)
tipo: artigo
vigencia: histórico (arquitetura ainda útil)
atividades: [C04, D03, D05, H05, B04, C11]
refs: [FURHANG-2009, TG-275, TG-201, DEWHURST-2015]
manuais: []
repos: []
isocentro: ["interface/checklist.py"]
texto: "../../texto/02 Plan check e revisão de prontuário/YANG-2012-ECHART.md"
origem: "referencias/02 Plan check e revisão de prontuário/YANG-2012-ECHART - Electronic chart checks in a paperless radiation therapy clinic (2012).pdf"
conferida: 2026-10-20
---

# Yang 2012 (EcCk): checagem eletrônica de prontuário

**Em uma frase.** Descreve o **EcCk**, sistema que junta dados do R&V (MOSAIQ por SQL), dos TPS (Pinnacle, Eclipse), do PACS DICOM-RT e até de PDF e Word, e compara tudo por **regras configuráveis** (dicionário de dados + arquivo de regras com tolerância e gravidade), gerando um relatório colorido. É **apoio à decisão**, não substitui o físico [YANG-2012-ECHART p. 1].

PDF de 7 páginas, texto limpo.

## Tarefas cobertas (Tabela I) [YANG-2012-ECHART p. 2]

1. Checagem física inicial sob demanda (plano × R&V, documentos e aprovações, resultado do QA de IMRT).
2. Checagem do dosimetrista após importar o plano no R&V.
3. Checagem final ao término do curso (registros completos, documentos exigidos).
4. Checagens automáticas diárias/semanais: consistência entre frações, **peso**, mudanças de documentação, setup, **imagens portais rejeitadas**, tendência da posição da mesa (em desenvolvimento).

## O que a checagem inicial confere (Tabela III) [YANG-2012-ECHART p. 4]

Prescrição no R&V × plano e DICOM; campos e **pontos de controle**; calendário de frações × dose/fração; documentos exigidos e aprovados; folha de deslocamentos; **orientação do paciente na TC × setup**; DRR em todos os campos e campos de setup; setup do sítio; atribuição de campos às frações; **QA de IMRT aprovado**; isocentro do CBCT, TC e estruturas enviados ao R&V.

## Arquitetura que vale copiar

- **Dicionário de dados** por fonte (nome padrão → caminho no dado) e **arquivo de regras** (o quê comparar, como, em que condição, tolerância, gravidade: erro maior, menor, aviso, e a explicação) [YANG-2012-ECHART p. 3].
- Resolver a **correspondência** entre plano do TPS, plano DICOM e sítio do R&V é o problema mais difícil; usar o UID do plano DICOM quando o R&V o guarda [YANG-2012-ECHART p. 3–4].
- Os autores dizem que portar para o ARIA exigiria entender a estrutura de dados do ARIA, talvez só mudando consultas SQL e dicionários [YANG-2012-ECHART p. 6].

## Achados no teste beta

Documentos faltando ou inacabados, rótulos de plano e campo trocados, **calendário de tratamento errado**, campos de setup errados, energias incompatíveis [YANG-2012-ECHART p. 6].

## Como se aplica no CLINICA

- H05: a separação "dicionário + regras + relatório" é um bom desenho para o checklist do ISOCENTRO; no Eclipse/ARIA, a ESAPI dá o plano aprovado e os UIDs, e o relatório do ARIA (AURA) ou consultas de leitura dão calendário e registros.
- D03/D05: as checagens semanais (peso, imagens rejeitadas, mesa) e a final são o mesmo conteúdo do ChartCheck (ver RADFORMATION-TG275).
