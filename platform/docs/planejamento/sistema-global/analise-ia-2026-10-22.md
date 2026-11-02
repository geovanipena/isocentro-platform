---
data: 2026-10-22
origem: conversa com o usuário — balanço das frentes de organização e otimização (15/09 a 22/10) e literatura recente de LLM em radioterapia
destino: DESTINO.md (R-62 a R-69) e ARCHITECTURE-SPINE.md (AD-42, proposta)
---

# Balanço da organização e IA no ISOCENTRO

## 1. O que as frentes de organização renderam

| Frente | Antes → depois |
|---|---|
| Arquivos grandes (R-06, R-13) | `gui.py` 5.728 → 2.595 linhas; `tratamento.py` 3.321 → 1.771 |
| Suíte | 270 s → 160 s em 14/09; em 22/10, 195 s com 2.369 testes (eram ~1.945) |
| Contexto da sessão | `CLAUDE.md` 394 → 352 linhas; descida do `NOTAS.md` automática; manutenção semanal |
| Papel | regressão célula a célula em 4 casos (`tools/regressao_papel.py`) |
| Build e segurança | `constraints.txt`; `pip-audit` na CI; dado de dev em `_restrito\estacao` |
| Acervo | `fontes.csv` (234) única, `acervo.py verificar`; `sincronizar.py`; `REPOS.md` |
| Planejamento | brief, PRD (FR-1..48), espinha (AD-1..41), specs de 5 módulos, R-16..R-61 |

O ganho de fundo: o que dependia de alguém lembrar passou a ser cobrado por
ferramenta (descida das notas, contagem da suíte, sessão concorrente, idade
da cópia do `_restrito/`, regressão do papel).

## 2. Onde ainda há espaço

1. **Plano à frente do código.** 12 frentes feitas, 51 pendentes; a
   Fundação (R-16..R-55) não começou. O meta-trabalho dos últimos dez dias
   valeu, mas o retorno dele cai: o próximo ganho grande é de campo.
2. **Código verde que nunca rodou de verdade.** Ficha temporária e varredura
   sem o app aberto esperam a R-08 (concentradora).
3. **"EM ANDAMENTO" vencidos.** Dez seções desceram para `notas/` marcadas
   "sem reconferir".
4. **Dois riscos no papel.** DVH intermitente (ficha sem DVH, calada) e 79
   vulnerabilidades conhecidas em pillow e pypdf.
5. **Arquivos grandes voltando.** `gui.py` 2.595 → 2.913; seguem
   `ficha_pdf.py` (3.585), `tratamento_db.py` (2.534), `fichinha.py` (2.432).
6. **CQ Plano sem calibrar** (R-10, TG-218).
7. **Acervo:** 128 fontes sem emissor, 18 com DOI.
8. **IA ausente do produto.** O levantamento de 21/10 deu 17 referências e
   nenhum requisito. A espinha só diz o que a IA NÃO recebe (dado de paciente
   não sai da rede); falta dizer o que ela pode fazer — é o AD-42.

## 3. O que a literatura aponta

Convergência: **o LLM sugere, uma conferência determinística decide, e a
tela diz de onde veio** — a mesma regra da reserva anunciada. Evidência:

- WANG-2026 (RCA de incidentes): os 4 LLMs alucinaram, de 11% a 61%.
- HOLMES-2023: o GPT-4 repete a mesma resposta, certa ou errada; votar entre
  tentativas não é redundância.
- COURT-2026: com plano automatizado, 2 de 5 físicos não avaliaram a margem
  do PTV; quem avaliou teve especificidade de 13% a 63%.
- NEALON-2022 e DEKERF-2025: revisão inadequada de plano automatizado é modo
  de falha de alta pontuação (viés de automação).

Novos em relação ao levantamento de 21/10 (detalhe no Update dele): análise
de 10 anos de manutenção de LINAC com LLM (UChicago, AAPM 2026), The Daily
Dose (Mayo), agendamento com LLM em simulação (Johns Hopkins), AI-ILS com
HFACS (IJROBP).

## 4. Propostas, em ordem de valor/risco

| # | Proposta | IA? | Dado de paciente? | Frente |
|---|---|---|---|---|
| 0 | AD-42: política de IA no ISOCENTRO | — | — | R-63 |
| 1 | Margem CTV→PTV medida pelo código | não | sim, local | R-62 (robô) |
| 2 | "Pergunte à base": RAG com a citação conferida por máquina | sim | não | R-64 |
| 3 | Pareto de máquina parada a partir do texto livre das paradas | sim | não (equipamento) | R-65 |
| 4 | Lint do texto livre contra o campo estruturado (DIBH, bolus, lateralidade) | sim, local | sim | R-66 |
| 5 | Plano anômalo explicável, sobre a base histórica da R-10 | estatística | sim, local | R-67 |
| 6 | Rascunho estruturado de incidente (HFACS), cada campo com trecho de origem | sim, local | sim | R-68 |

Fora: o "bom dia" no estilo Daily Dose não precisa de LLM — a Fichinha já
tem Altas Prontas e Datas Relevantes, e o resumo determinístico entrega o
ganho.

O diferencial da proposta 2 é o que só o ISOCENTRO tem: a citação
`[CÓDIGO p. N]` já é conferida na página. A resposta só sai se o trecho
citado existir no texto extraído daquela página; o conjunto de avaliação sai
das próprias fichas (norma, tolerância, página), centenas de perguntas contra
as 20 do RTPhy-ChatBot.

## 5. Sequência

1. Reconferir os "EM ANDAMENTO" vencidos; caçar o DVH intermitente.
2. R-08 (concentradora): destrava o código que nunca rodou.
3. AD-42 aceito pelo físico; R-62 pelo robô; R-64 e R-65 em seguida.
