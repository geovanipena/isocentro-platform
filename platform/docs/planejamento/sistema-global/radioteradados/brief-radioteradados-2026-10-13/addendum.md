---
title: 'Adendo — Radioteradados'
created: '2026-10-13'
---

# Adendo — Radioteradados

Detalhes que servem ao PRD e à arquitetura, mas não cabem no brief.

## Catálogo inicial de indicadores e disponibilidade do dado

As tabelas citadas são as que o código do ISOCENTRO já consulta no data warehouse do ARIA (`isocentro/banco/`). As definições abaixo são **propostas** e precisam da aprovação do físico responsável antes de valer.

| Indicador | Origem | Definição proposta | Dado |
|---|---|---|---|
| Tempo médio do tratamento | RDC 20/2006, 6.11a | média de dias corridos da 1ª à última fração, por curso concluído no período | sai do banco (`FactTreatmentHistory`, `DimCourse`) |
| Taxa de abandono | RDC 20/2006, 6.11b | cursos iniciados que não chegaram às frações prescritas, sem encerramento planejado ÷ cursos iniciados | sai do banco; "encerramento planejado" precisa de regra |
| Taxa de simulação | RDC 20/2006, 6.11c | pacientes simulados ÷ pacientes tratados no período | **a mapear**: depende da TC de simulação estar registrada como atividade (`DimActivity`) |
| Taxa de interrupção | RDC 20/2006, 6.11d | cursos com intervalo não planejado acima de N dias úteis entre frações ÷ cursos | sai do banco; N a definir |
| Adesão a protocolos | RDC 20/2006, 6.11e | — | **fora da v1** |
| Desvio da dose absoluta | RDC 20/2006, 6.11f | — | **fora da v1** (controle de qualidade) |
| Tempo total e prolongamento | literatura (Harden 2022; Yao 2019) | dias reais da 1ª à última fração; prolongamento = real − planejado | sai do banco |
| Pacientes novos / cursos iniciados | literatura (Bovet 2026) | 1º curso do paciente no período / início de curso | sai do banco; **definir o evento** (divergência de 7–10% em Zurique) |
| Sessões por máquina e ocupação | literatura (Harden 2022) | frações entregues por máquina; ocupação = sessões ÷ capacidade configurada | sai do banco (`DimActualMachineID`); capacidade é configuração |
| Faltas | literatura (Chen D 2026) | sessões agendadas sem tratamento ÷ agendadas | sai da agenda (`DimActivityTransaction`) |
| Percurso | literatura (Chen D 2026) | consulta → simulação → 1ª fração, em dias (mediana) | **a mapear**: depende das atividades registradas |
| Mix | gestão | por convênio, sítio, diagnóstico, intenção, fracionamento | sai do banco (`FactPatientPayor`, `FactPatientDiagnosis`, `DimPrescription`) |
| Tempo total no colo do útero ≤ 50 dias | ESGO/ESTRO 2023 | cursos de colo do útero com tempo total ≤ 50 dias ÷ cursos de colo do útero (meta ≥ 90%) | sai do banco, se teleterapia e braquiterapia estiverem no ARIA |
| Cálculo verificado até a 3ª fração | RDC 20/2006, 9.7c | — | **a mapear**: não se sabe se a verificação fica registrada no ARIA |
| Revisão médica / física semanal | RDC 20/2006, 9.3; TG-275 | — | **a mapear**; pertence também ao módulo Revisão Semanal |
| Tempo de acelerador perdido | literatura (Harden 2022) | — | **a mapear**: a atividade de parada ainda vai ser criada no ARIA |
| Início em até 60 dias do diagnóstico | Lei 12.732/2012 | — | **fora da v1**: a data do laudo não está no ARIA |

## Restrições técnicas já conhecidas

- O banco é **somente leitura** (regra do projeto).
- Consultas novas precisam caber no servidor local de demonstração (`banco/servidor_local.traduzir`), ou os testes quebram.
- Cada número mostra fonte e data, seguindo a regra do projeto de que "reserva usada é reserva anunciada".
- A aba segue o padrão de tela do projeto (`ui.py`, `estilo.py`, verde reservado à dose).
