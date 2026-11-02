---
title: 'Addendum: PRD ISOCENTRO — detalhe para UX e arquitetura'
created: '2026-10-16'
updated: '2026-10-19'
---

# Addendum do PRD ISOCENTRO

Detalhes que sustentam o PRD, mas são de arquitetura ou de UX. Fatos de código e
da base com arquivo e linha estão em `extrato-entradas.md`. O esboço do
objeto Verificação, os quatro gatilhos, o reaproveitamento de código externo e
os números de literatura continuam no addendum do brief
(`../brief-sgq-rt-2026-10-13/addendum.md`) e não são repetidos aqui.

## Máquinas e nomes DICOM (FR-10)

| Clínica | Máquina | Nome DICOM no código | Comissionamento disponível |
| --- | --- | --- | --- |
| CEL | TrueBeam 4045 | `TBuniverSN1002` | DOSEMED out/2020; 6, 10, 6FFF, 10FFF MV; elétrons |
| CEL | Clinac 6EX 1254 | `6EX` | DOSEMED out/2020; 6 MV |
| BET | Clinac 600CD 1196 | `600CD` | 2010; 6 MV; filtros físicos 15–60° |
| DUO | VitalBeam 4199 | `TrueBeamSN1001` | abr/2020; 6, 6FFF MV; elétrons 6–15 MeV; filtros 15–60° |
| SAT (fora do MVP) | Synergy01 | `Synergy01` | só conjunto do paralelo (TMR aberto e W60; Scp 6/10/15 MV) |

Fonte: `dominio/constantes.py:40-68`; `Documents/isocentro/comissionamento/CATALOGO.md`.
O `dados_feixe/_maquinas.json` de hoje só tem `ELEKTA_SAT` com
`nomes_dicom: []`.

## Segunda checagem: o que o código faz hoje (FR-12, FR-13)

- `dominio/paralelo.py`: TMR × Scp por ponto, fator distância e filtro.
- Limites no código: 3% atenção / 5% falha por campo; modulado 10% / 20%,
  como rastreio. Os limites do TG-219 (Tab. 9) são outros: composto 3%
  homogêneo / 5% heterogêneo; campo único 5% / 7%.
- `demonstracao=True` quando a tabela não é da máquina. O PRD troca isso por
  `indeterminado`.
- Não trata campo com filtro (C05).

## Sequência real: o que o código lê hoje (FR-16)

- Status do plano no `variandw` (`banco/gatilho_db.py:89-104`). A escala medida
  tem 10 valores: Unapproved, Planning Approved, Treatment Approved, Reviewed,
  3rd Party Approval, Rejected, Retired, Completed, Completed Early,
  Unplanned Treatment.
- Atividades do Carepath (`banco/atividades_db.py`): só `Documentação` e
  `Verificar Programação`. O `variandw` diferencia maiúsculas e minúsculas.
- O `srvariadb.clinica.example:51404` é o DB Daemon (DICOM), não a fonte das
  datas.
- Tratamento entregue: `banco/tratamento_db.py`, com `LISTA_VERIFICADA_EM = ""`
  até a R-07.
- Planos do Monaco não trazem o aprovador (NOTAS, 07/10/2026). Só pesa se a SAT
  entrar.

## Decisões de arquitetura (fechadas em 19/10/2026)

A espinha (`../architecture-isocentro-2026-10-19/ARCHITECTURE-SPINE.md`,
AD-1..AD-37) fechou o que este addendum deixava aberto:

- Banco: PostgreSQL 18 em `clinica-python01`, servidor da clínica, com a
  concentradora no mesmo host (AD-9, AD-10).
- Compartilhamento entre as três clínicas: banco central único, RLS por
  clínica pela sessão (AD-12).
- Avaliador ESAPI: JSON versionado com hash numa pasta restrita, importado
  pela concentradora (AD-15).
- Retenção de log, backup e relatório de validação: 10 anos após o descarte
  (AD-24).
- Shell: PySide6, com a identidade Torre de controle (AD-36); por isso o §4.2
  do PRD não cita mais PyQt5.

## Métodos escolhidos nas specs de módulo (19/10/2026)

- Segunda checagem de modulado (FR-12, P3): Clarkson modificado por ponto de
  controle, somando a abertura do MLC em cada ponto de controle; exige
  transmissão do MLC e DLG na tabela da máquina. O MU density do pymedphys
  foi descartado porque compara fluências e não calcula dose. Nenhum dos 61
  repositórios de `codigo-externo/` traz cálculo independente para modulado.
- Programa de CQ (FR-22): os itens nível 2 com limite somam cerca de 97 (MPPG
  8.b 57, 2.b 15, 9.b 22, TECDOC-1274 3). As condições de referência e as
  especificações do TRS-398 e do adendo TG-51 alimentam o FR-45 e o FR-44,
  não viram teste.
- pylinac e QATrack+ estão em `codigo-externo/06 QA de equipamentos/`.
