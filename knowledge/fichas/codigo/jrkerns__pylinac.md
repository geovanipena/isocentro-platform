---
repo: jrkerns/pylinac
pasta: "codigo-externo/06 QA de equipamentos/jrkerns__pylinac"
linguagem: Python (>= 3.10)
licenca: MIT
versao: 3.49.0
ultimo_commit: 2026-10-14 (8096895)
atividades: [A03, A07, A08, A09, A13, A15, A17, A18, A19, H05]
refs: [TG-142, TRS-398-R1, MPPG-8b, MPPG-IGRT-2021, TG-179, TG-218, MPPG-9a-SRS, MPPG-CT-2021]
manuais: ["VitalBeam - Instructions for Use (v3.0, 2022-05)", "TrueBeam - RapidArc QA Test Procedures"]
isocentro: poderia-usar   # proposto em docs/BIBLIOTECAS_EXTERNAS.md §2.1 (fase 3 e 4); não embarcado hoje
conferida: 2026-10-16
---

# pylinac: análise automática de imagens e dados de CQ de acelerador

**Em uma frase.** Biblioteca que transforma as imagens e os arquivos dos testes de CQ do acelerador (Winston-Lutz, picket fence, CBCT, starshot, VMAT, perfis, logs) em número, tolerância e PDF, quase sempre em menos de dez linhas de código.

## O que implementa, e onde

| Teste da prática | Classe / função | Arquivo:linha | Atividade |
| --- | --- | --- | --- |
| Winston-Lutz (isocentro de radiação × mecânico, gantry/colimador/mesa) | `WinstonLutz`, `WinstonLutz2D` | `pylinac/winston_lutz.py:1339`, `:1241` | A17 |
| Winston-Lutz multialvo (SRS de múltiplas metástases) | `WinstonLutzMultiTargetMultiField` | `pylinac/winston_lutz.py:2967` | A17 |
| Picket fence (posição de lâmina do MLC) | `PicketFence` | `pylinac/picketfence.py:265` | A07 |
| Starshot (isocentro de rotação do gantry, colimador e mesa) | `Starshot` | `pylinac/starshot.py:98` | A07, A10 |
| VMAT: taxa de dose × gantry (DRGS) e velocidade de lâmina (DRMLC) | `DRGS`, `DRMLC`, `DRCS` | `pylinac/vmat.py:843`, `:872`, `:898` | A07 |
| Planura, simetria e penumbra | `FieldAnalysis`, `FieldProfileAnalysis` | `pylinac/field_analysis.py:442`, `pylinac/field_profile_analysis.py:93` | A07 |
| DLG (dosimetric leaf gap) | `DLG` | `pylinac/dlg.py:16` | A07, B02 |
| CBCT/TC: CatPhan 503/504/600/604/700, Quart, ACR CT e RM, Cheese | `CatPhan504`… `QuartDVT`, `ACRCT` | `pylinac/ct.py:3139`, `pylinac/quart.py:441`, `pylinac/acr.py:409` | A08, A09, A19 |
| Imagem planar kV/MV (Leeds, Las Vegas, QC-3, SNC, PTW EPID QC…) | `LeedsTOR`, `StandardImagingQC3`, `LasVegas`… | `pylinac/planar_imaging.py` | A08 |
| Log de entrega Varian (Dynalog e Trajectory log), gama de fluência planejada × entregue | `Dynalog`, `TrajectoryLog`, `GammaFluence` | `pylinac/log_analyzer.py:1896`, `:2339`, `:640` | A18 |
| Dose de referência TRS-398 (fótons e elétrons) | `TRS398Photon`, `TRS398Electron`, `kq_photon`, `k_tp`, `k_s` | `pylinac/calibration/trs398.py:817`, `:1044`, `:669`, `:575`, `:614` | A03, A13, A15 |
| Dose de referência TG-51 | `pylinac/calibration/tg51.py` | — | A03 (checagem cruzada) |
| Índice gama 1D/2D genérico | `gamma_1d`, `gamma_2d`, `gamma_geometric` | `pylinac/core/gamma.py:333`, `:229`, `:105` | C06 |
| Gerador de planos de teste DICOM (campos de picket fence, WL etc.) | `plan_generator/` | `pylinac/plan_generator/dicom.py` | A07 |

Entradas: DICOM de imagem (EPID, CBCT, TC), TIFF de filme, `.dlg` / `.bin` de log. Saídas: objeto de resultado (Pydantic, via `ResultsDataMixin`), `publish_pdf()`, figuras matplotlib e exportação QuAAC.

## Pontos de atenção

- **TRS-398: o pylinac usa a Tabela 6.III da edição de 2000** (`trs398.py:62`). Comparado com a **Tabela 16 da Rev. 1** [TRS-398-R1 p. 102–104], conferido na imagem:
  - **PTW 30013** (CEL e BET): o kQ antigo fica **+0,24% em TPR 0,68 (6 MV)** e **+0,48% em TPR 0,74 (10 MV)**, o que **superestima a dose de referência** na mesma proporção.
  - **IBA FC65-G (CEL) e FC65-P (DUO): não existem** no dicionário de fótons (`KQ_PHOTON_CHAMBERS`, `trs398.py:63`). Elas só aparecem na tabela de elétrons. `kq_photon(chamber="FC65-G")` falha.
  - Para usar `TRS398Photon`, passar o **kQ explícito da Rev. 1**. Antes, confirmar se o N_D,w do laboratório já incorpora o ICRU 90 (o certificado METROBRAS cita "TRS-398 (2000)").
- As tolerâncias padrão das classes são do autor, não do serviço. O valor de aceitação vem do TG-142 e do MPPG-8b (ver as fichas) e deve ser passado explicitamente (ex.: `tolerance=` em `PicketFence.analyze`).
- O Log Analyzer depende de acesso aos trajectory logs do VitalBeam pela rede: a decisão é de infraestrutura, não de código (`docs/BIBLIOTECAS_EXTERNAS.md` §6, fase 4).
- Biblioteca com validação própria (`tests_basic/`, um arquivo de teste por módulo), mas o uso clínico exige a validação local da atividade **B10** (software de terceiros): rodar com imagens do serviço e comparar com a análise de referência.

## Como se aplica no ISOCENTRO

- Hoje **não é dependência** do programa.
- Proposta registrada (`programa/isocentro/docs/BIBLIOTECAS_EXTERNAS.md` §2.1 e plano de fases): o pylinac seria o **motor de cálculo** de uma aba "QA de Equipamento" (Winston-Lutz, CBCT, picket fence, starshot, planura/simetria, TRS-398). A interface e a tabela de tolerância seguem o padrão do ISOCENTRO (pílula OK/Atenção/Fora da faixa, como em `interface/qualidade_tela.py`). O modelo de dados é Test List / Instance / tolerância / ação / frequência, no espírito do QATrack+.
- Fase 4: painel "Log da entrega" por fração na aba Ficha Virtual (`interface/tratamento.py`).

## Relações

- Complementa: `pymedphys/pymedphys` (gama 3D, MU density), `qatrackplus/qatrackplus` (gestão do programa de CQ), `pakoliver/winston_lutz_multi`.
- Normas e recomendações que dão as tolerâncias: TG-142, MPPG-8b (CQ do acelerador), MPPG-IGRT-2021 e TG-179 (CBCT), MPPG-9a-SRS (Winston-Lutz em SRS), TRS-398-R1 (dosimetria de referência, protocolo do PPR).
