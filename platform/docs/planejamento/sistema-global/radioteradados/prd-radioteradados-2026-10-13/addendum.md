---
title: 'Adendo do PRD — Radioteradados'
created: '2026-10-13'
---

# Adendo do PRD — Radioteradados

Detalhes técnicos para a arquitetura. O PRD diz *o quê*; aqui fica *de onde vem o dado* e as regras de cálculo que dependem do banco.

## Origem provável no data warehouse do ARIA

O catálogo completo, com o estado do dado de cada indicador, está no adendo do brief (`../brief-radioteradados-2026-10-13/addendum.md`). As tabelas abaixo são as que `isocentro/banco/` já consulta, atualizadas com o mapeamento de 13/10/2026 (`mapeamento-banco-2026-10-13.txt`, ao lado).

| FR | Origem | Estado |
|---|---|---|
| FR-4, FR-9, FR-11 | `FactTreatmentHistory` (frações entregues, `FractionNumber > 0`, `TreatmentStartTime`), `DimCourse` | confirmado |
| FR-5, FR-22 | `DimCourse.NoTxSessionPlanned/Delivered/Remaining`; óbito em `DimPatient.PatientDeathStatus/PatientDeathDate` | contagens do curso a conferir (pergunta 6 do PRD, §11); `ClinicalStatus` NÃO serve (só ACTIVE/COMPLETED, cursos não são fechados) |
| FR-6, FR-11 | `DimPrescriptionProperty`, `PropertyType = 7` (frequência da prescrição aprovada), já lido por `tratamento_db._marcar_frequencia` e convertido em ritmo por `_RITMO`; sem valor conhecido = frequência não identificada (sem inferência pelas pausas) | confirmado (fonte da Capa e da Ficha Virtual); falta o valor do regime semanal (pergunta 5) |
| FR-7, FR-13 | `DimActivityTransaction` + `DimActivity`: "TOMO-DUO / TOMO-ANA" (simulação), "1a Consulta" | confirmado pelo usuário; nomes vão para a configuração do serviço |
| FR-10 | `FactTreatmentHistory` + `DimActualMachineID`/`DimMachine` (6EX, VitalBeam, 600CD, TB Universitario) | capacidade por máquina vira configuração do serviço |
| FR-12 | `DimActivityTransaction` (agenda; `DimLookupID_CancelReasonType` existe) | status que distinguem falta de cancelamento (pergunta 7); até lá, indicador vazio |
| FR-14 | `FactPatientPayor`, `FactPatientDiagnosis`/`DimDiagnosisCode`, `DimLookupID_TreatmentIntentType`, `DimPrescriptionAnatomy` | confirmado (já usado pela Capa) |
| FR-15 | teleterapia: `FactTreatmentHistory`; braquiterapia: agenda da braquiterapia (`DimActivityTransaction`) | recurso/atividade da braquiterapia a mapear (pergunta 4) |

Já registrado no projeto: a linha-resumo do curso tem `FractionNumber = 0` em `FactTreatmentHistory`, e as consultas de sessão filtram `FractionNumber > 0`.

## Regra de interrupção (FR-6), em detalhe

1. Ordenar as frações entregues do curso por data.
2. Para cada par consecutivo, contar os dias úteis entre as datas, sem fins de semana nem feriados do calendário configurado.
3. Limiar: frequências não semanais, mais de 3 dias úteis; frequência semanal, mais de 7 dias corridos + 3 dias úteis.
4. O curso conta como interrompido se tiver pelo menos uma interrupção (pausa acima do limiar). A lista de origem guarda todas as interrupções.

A Ficha Virtual já usa `_INTERVALO_ATENCAO = 3` dias úteis para pintar de âmbar a faixa de intervalos. Convém compartilhar a mesma função de contagem de dias úteis, **preservando o comportamento atual da Ficha Virtual**: o desconto de feriados entra como opção que só o Radioteradados liga (revisão clínica, achado 3). Mudar a faixa da Ficha Virtual seria outra frente, com aviso e aceite.

## Padrões do projeto que a arquitetura precisa respeitar

- Banco somente leitura; três degraus (banco → espelho → relatório) e "reserva usada é reserva anunciada" (FR-21).
- Consultas novas entram em `banco/servidor_local.traduzir` e em `tests/test_servidor_local.py`.
- Portão no estilo do `LISTA_VERIFICADA_EM` para a faixa EXPERIMENTAL (FR-20).
- Tela nova começa pelo `ui.py`; layout descrito em texto e aceito antes de editar (regra do CLAUDE.md do repositório).
