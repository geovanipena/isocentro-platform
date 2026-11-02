---
codigo: DEWHURST-2015
titulo: "Dewhurst JM et al. AutoLock: a semiautomated system for radiotherapy treatment plan quality control. J Appl Clin Med Phys 16(3):339–350"
ano: 2015
emissor: The Christie NHS Foundation Trust, Manchester (artigo, JACMP)
tipo: artigo
vigencia: vigente como modelo
atividades: [C04, H05, B06, G17, I06]
refs: [FURHANG-2009, YANG-2012-ECHART, TG-275]
manuais: ["Eclipse 15.5 ESAPI Reference Guide"]
repos: []
isocentro: ["interface/checklist.py"]
texto: "../../texto/02 Plan check e revisão de prontuário/DEWHURST-2015.md"
origem: "referencias/02 Plan check e revisão de prontuário/DEWHURST-2015 - AutoLock semiautomated radiotherapy plan quality control (2015).pdf"
conferida: 2026-10-20
---

# Dewhurst 2015 (AutoLock): checagem automática que trava a finalização do plano

**Em uma frase.** O **AutoLock** (script do Pinnacle + Java) roda **31 checagens automáticas** e um checklist eletrônico na mão do **planejador**, e **só deixa finalizar o plano** se tudo passar e todos os itens forem reconhecidos. Com ele, a **taxa de rejeição na checagem física caiu 32%** [DEWHURST-2015 p. 1, 8].

PDF de 12 páginas, texto limpo; os gráficos de taxa por checagem (Fig. 7–8) são imagem.

## Desenho

| Elemento | Como funciona | Página |
| --- | --- | --- |
| Posição no fluxo | O mais cedo possível: **antes** da checagem independente e da revisão do médico | [DEWHURST-2015 p. 2–3] |
| Revisar e travar | Módulo Review gera o arquivo do plano e checa; LockPlan **recalcula um checksum** e só trava se o plano não mudou desde a revisão; grava uma "Plan Lock Sheet" permanente | [DEWHURST-2015 p. 3] |
| Resultado | Pass, **Fail**, **For review** (precisa ser reconhecido), Not checked, Error | Tab. 1 [DEWHURST-2015 p. 4] |
| Configuração | Arquivo de configuração externo; novas checagens fáceis de acrescentar | [DEWHURST-2015 p. 3, 5] |
| Comissionamento do próprio software | **Dados de teste com erros propositais**, verificação independente do código, beta e usabilidade | [DEWHURST-2015 p. 8] |

## Checagens que valem para o Eclipse (Tabelas 2–5) [DEWHURST-2015 p. 5–7]

- Gerais: só um plano final; **mesa removida/inserida**; **grade de dose ≤ 0,3 cm**; limiar ar/paciente; origem × localizador; **lista de overrides de densidade para revisão**; nome curto para exportar DICOM; **ROIs dentro da grade**; cálculo de UM independente rodado; versão clínica do TPS.
- Prescrição: dose e frações; prescrito em ponto ou média de ROI (não em UM); isodoses; **ponto máximo ≤ 110%**.
- Campos: **mesmo modelo de máquina** (e data do modelo = a do sistema da qualidade); mesmo tipo de campo; algoritmo; heterogeneidade e tabela de densidade; mesmo isocentro; mesma prescrição; **ID de campo preenchido**; rótulos; pontos de in vivo.
- Pontos de controle: nenhum com **menos de 3 UM**; mandíbulas acompanhando o MLC; sem linhas de junção no eixo central (step-and-shoot Varian).

## Resultados (2.384 planos, 2014)

- Adesão chegou a **100%** porque o AutoLock **é** a finalização (depois virou obrigatório no sistema da qualidade) [DEWHURST-2015 p. 9–10].
- Taxa de ação (alguma correção) de **28%** dos planos; maior em IMRT/VMAT (30%) [DEWHURST-2015 p. 8].
- Rejeições por override de densidade e por origem caíram cerca de **70%** [DEWHURST-2015 p. 11].
- Checagens com taxa de ação perto de zero valem a pena: pegam o erro raro, e depois de comissionadas custam nada [DEWHURST-2015 p. 11].

## Como se aplica no CLINICA

- H05 e B06: modelo direto para o checklist ESAPI do ISOCENTRO: rodar no planejador, **bloquear a aprovação** (ou registrar o reconhecimento) e guardar um hash do plano para saber se mudou depois da checagem.
- B06: o comissionamento com casos de teste com erros propositais é o roteiro de validação de script próprio.
