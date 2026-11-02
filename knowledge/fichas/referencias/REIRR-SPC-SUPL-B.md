---
codigo: REIRR-SPC-SUPL-B
titulo: "University of Michigan: Special Medical Physics Consultation – Previous Treatment Evaluation (suplemento B, formulário-modelo)"
ano: ""
emissor: University of Michigan (material suplementar; uso só como exemplo)
tipo: POP (modelo de outra instituição)
vigencia: "exemplo; a própria Michigan não endossa uso fora da instituição"
atividades: [I03, C09, H03, H06]
refs: [HARDCASTLE-2024, ESTRO-EANO-GBM-2025, HYTEC-HN-CAROTID, QUANTEC-MARKS-2010]
manuais: []
repos: []
isocentro: ["dominio/ritmo"]
texto: "../../texto/04 Constraints, SBRT e reirradiação/REIRR-SPC-SUPL-B.md"
origem: "referencias/04 Constraints, SBRT e reirradiação/REIRR-SPC-SUPL-B - Michigan guia de avaliação de tratamento prévio e decaimento de dose (suplemento B).pdf"
conferida: 2026-10-20
---

# Michigan: consulta especial de física para tratamento prévio (reirradiação)

**Em uma frase.** É o **formulário** que Michigan usa quando o paciente já recebeu radioterapia na região: o médico informa os cursos anteriores e os objetivos; o físico monta a **soma de planos**, aplica um **desconto de recuperação da dose prévia por tempo decorrido** e devolve as doses permitidas em **EQD2 (α/β = 2,5 Gy), máximo em 0,1 cm³**, com assinatura do físico e aprovação do médico.

O PDF tem 4 páginas; a tabela foi conferida na imagem da página (o "α/β" saiu como "�" no texto). **O documento avisa que as diretrizes não são endossadas para uso fora de Michigan** [REIRR-SPC-SUPL-B p. 1].

## Fluxo do formulário

1. Cursos prévios: data de término, área, dose, frações, se foi em outra instituição; **registros externos digitalizados no ARIA** antes de abrir a tarefa [p. 1].
2. Pedido do médico: avaliar sobreposição, orientar limites, criar soma de planos [p. 1–2].
3. Objetivos do médico em EQD2 com a dose prévia descontada (tabela abaixo) [p. 2–3].
4. Recomendações do físico antes do planejamento; doses novas permitidas por OAR [p. 3–4].
5. Análise do físico no plano final (DVH do plano composto) [p. 4].
6. Assinatura do físico e aprovação do médico; revisão em *chart rounds* [p. 4].

## Limites compostos e desconto da dose prévia [REIRR-SPC-SUPL-B p. 2–3]

α/β = 2,5 Gy para todos; limite = **EQD2 máximo em 0,1 cm³**. Desconto (% da dose prévia que se "perdoa") por tempo desde o curso anterior: **< 3 meses 0%; 3–6 meses 10%; 6 meses–1 ano 25%; 1–3 anos 50%; > 3 anos 50% sugerido**.

| OAR | Limite EQD2 (Gy) | Exceção no desconto |
| --- | --- | --- |
| Bexiga | 85 | — |
| Plexo braquial | 70 | — |
| Tronco encefálico | 64 | — |
| Cauda equina | 60 | — |
| Parede torácica | 100 | — |
| Cólon | 70 | — |
| **Duodeno** | 54 | 0 / 0 / 10 / 25% |
| Esôfago | 70 | — |
| Grandes vasos | 100 | — |
| Coração | 70 | — |
| Rins | ALARA | **sem desconto** |
| Quiasma óptico, nervo óptico | 54 | — |
| Reto | 80 | — |
| Retina | 50 | — |
| Plexo sacral | 70 | — |
| **Intestino delgado**, **estômago** | 54 | 0 / 0 / 25 / 25% |
| **Medula** | **50** (55 se a < 2 mm do alvo) | — |
| Traqueia/brônquio | 70 | — |
| Fígado | limitado por NTCP | 0 / 0 / 50 / 100% (faixas: < 3 m, 3–6 m, 6 m–2 a, > 2 a) |
| Pulmões | caso a caso | 0 / 0 / 25 / 50% (mesmas faixas do fígado) |

## Como se aplica no CLINICA

- I03: modelo direto para um POP de **consulta física de reirradiação** nas três clínicas e para o cálculo no ISOCENTRO (EQD2 com desconto por tempo). Os valores são de **uma instituição**; usar como ponto de partida e comparar com as recomendações de consenso (ESTRO-EANO para glioblastoma, HyTEC para carótida) antes de adotar.
- C09: o passo 1 (registros externos no ARIA antes da consulta) responde ao modo de falha "dose prévia desconhecida" do TG-275 (ver RIEGEL-2022).
