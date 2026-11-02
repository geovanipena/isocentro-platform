---
codigo: MPPG-5b-TPS
titulo: "AAPM MPPG 5.b: Commissioning and QA of treatment planning dose calculations — megavoltage photon and electron beams"
ano: 2022
emissor: AAPM (Geurts et al., J. Appl. Clin. Med. Phys.)
tipo: recomendação
vigencia: vigente (substitui o MPPG 5.a)
atividades: [A02, B01, B02, B03, C06, A09]
refs: [TG-218, TG-119, TG-142, MPPG-8b, TRS-398-R1, ICRU-91]
manuais: ["Beam Configuration 15.5 Reference Guide", "ECLIPSE-ALG-15.5 - Photon and electron algorithms reference guide (v15.5)", "Eclipse Treatment Planning - Customer Release Note (v15.6 MR5, 2025-12)"]
repos: [jrkerns/pylinac, pymedphys/pymedphys]
isocentro: ["dominio/paralelo.py (cálculo independente de UM)"]
texto: "../../texto/05 QA de equipamentos, IGRT e dosimetria/MPPG-5b-TPS.md"
origem: "referencias/05 QA de equipamentos, IGRT e dosimetria/MPPG-5b-TPS - Commissioning and QA of TPS dose calculations MV photons and electrons (2022).pdf"
conferida: 2026-10-16
---

# MPPG-5b: comissionamento e CQ do cálculo de dose do TPS

**Em uma frase.** É o roteiro mínimo para pôr em uso clínico, e manter, o cálculo de dose de fótons e elétrons de um TPS. Cobre aquisição de dados, modelagem, validação em campos básicos, heterogeneidade, IMRT/VMAT e elétrons, e o **CQ de rotina anual e após upgrade** com tolerância de **1%/1 mm** contra planos de referência.

O PDF tem 20 páginas e o texto saiu limpo. O checklist do Apêndice A (p. 20) reúne todas as tolerâncias.

## Etapas e tolerâncias (Apêndice A [p. 20]; Tabelas 4 a 10 [p. 9–15])

| # | Validação | Tolerância |
| --- | --- | --- |
| 1–4 | Físico treinado no algoritmo; cronograma; guia do fabricante; equipamento calibrado; calibração de TC; revisão dos dados brutos contra dados publicados; modelagem conforme o fabricante | — |
| 5.1 | Dose absoluta nas condições de calibração (fótons) | **0,5%** |
| 5.2 | Dose no módulo clínico × módulo de física (Beam Configuration) | Incerteza estatística, de grade e de material |
| 5.3 | Pontos de PDD, fator de campo e OAF contra os dados de comissionamento | **2%** |
| 5.4–5.8 | Campos pequenos por MLC (não SRS); transmissão e overtravel do MLC; fora do eixo e colimador primário; divergência e DFS; incidência oblíqua | **2%** alta dose (um parâmetro); **5%** (vários); **2 mm** na penumbra; **3% da dose máxima** na cauda até 5 cm |
| 5.9 | Filtro não físico (EDW): campo grande para cada ângulo | Tabela 6 |
| 6.1 | Densidades eletrônicas (ou de massa) informadas pelo TPS contra valores conhecidos (curva HU) | — |
| 6.2 | Correção de heterogeneidade após pulmão (5×5 cm²) | **3%** |
| 7.1–7.2 | PDD e output de campos pequenos por MLC (< 2×2 cm²) | Tab. 9 |
| 7.3 | Testes do TG-119 (cabeça e pescoço; C-shape) | Tab. 9 |
| 7.4 | Pelo menos **dois casos clínicos** planejados e medidos | Tab. 9 |
| 7.5 | **Revisão externa**: fantoma antropomórfico simulado, planejado e tratado | 5% |
| 8.1 | Dose absoluta nas condições de calibração (elétrons) | **0,5%** |
| 8.2 | Recortes personalizados em DFS padrão e estendida | **3%/3 mm** |
| 8.3 | Superfície irregular ou incidência oblíqua | **5%** |
| 8.4 | Heterogeneidade | **7%** |
| 9 | CQ de rotina estabelecido, com plano(s) de referência para cada feixe configurado | — |

### Critérios para IMRT/VMAT (Tabela 9 [p. 14])

| Método | Região | Critério |
| --- | --- | --- |
| Câmara de ionização | Alvo, baixo gradiente | 2% da dose prescrita |
| Câmara de ionização | OAR, alto gradiente | 3% da dose prescrita |
| Matriz planar ou volumétrica | Todas | **Sem taxa mínima de aprovação**; investigar o que falha em 2%/2 mm |
| Fim a fim | Alvo, baixo gradiente | 5% da dose prescrita |

## CQ de rotina do TPS (§9) [p. 15–16]

- **Objetivo:** provar que (1) o TPS **não foi modificado sem intenção** e (2) o cálculo continua **consistente após upgrades**.
- **Integridade:** **checksums** dos executáveis, bibliotecas e arquivos de configuração e de banco usados no cálculo. Os fornecedores deveriam oferecer o método.
- **Consistência:** recalcular um subconjunto dos testes das §§5–8 **anualmente e após cada upgrade**. **Não precisa medir**: comparar o recálculo com o plano de referência do comissionamento.
- **Tolerância: 1%/1 mm** contra a referência. Desvio maior pode exigir recomissionamento parcial ou total.
- Planos de referência: um por feixe configurado (estático e com filtro pela Tab. 5; IMRT/VMAT pela Tab. 8); em elétrons, por energia, em conjunto heterogêneo com curvatura, distância estendida e bolus. O conjunto de dados de exemplo da AAPM está em aapm.org/pubs/MPPG/TPS.
- Verificações extras com os mesmos dados: cálculo de DVH, profundidade efetiva e consistência do número de TC.

## Outras exigências do texto

- Relatório final de comissionamento pelo físico, **acrescido a cada modificação ou recomissionamento** [p. 16].
- **Revisão por pares** dos parâmetros do modelo, da concordância com a medida e da validação, de preferência com cálculo e medida independentes feitos por outro físico [p. 16].
- Campo pequeno: tamanho mínimo medido com confiança sem dosimetria especial = 2 × rLCPE + d. Exemplo: 6 MV com detector de 7 mm, **FWHM ≥ 2,7 cm**; 6FFF, 2,3 cm (Tabela 3 [p. 7]).

## Como se aplica no serviço

- **Eclipse 15.6** nas três clínicas, com AAA e Acuros (fótons) e eMC (elétrons). No VitalBeam da DUO, o comissionamento de abril de 2020 deixou **os modelos eMC para o físico calcular e aprovar** (ver A02).
- **Upgrade 15.6 MR5:** o §9 pede recálculo dos planos de referência com 1%/1 mm (ver B03).
- **Checksum:** o ISOCENTRO pode registrar o hash dos arquivos de configuração de feixe exportáveis e do Beam Configuration, para detectar mudança não intencional (candidato).
- Revisão externa (7.5): auditoria postal ou presencial com fantoma (IROC, LCR/IRD), que também atende à NN-6.10 art. 36 (G02).
