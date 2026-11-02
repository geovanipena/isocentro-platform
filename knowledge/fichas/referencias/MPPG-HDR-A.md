---
codigo: MPPG-HDR-A
titulo: "AAPM MPPG 13.a: HDR brachytherapy, part A"
ano: 2023
emissor: AAPM (Richardson et al., J. Appl. Clin. Med. Phys.)
tipo: recomendação
vigencia: vigente
atividades: [E01, E02, E03, E04, E06, E07, E08]
refs: [TG-56, TG-59, TG-43U1, TG-186, TECDOC-1151, NN-6.10, ICRU-89]
manuais: ["GammaMedplus iX - Instructions for Use (v1.2.5, 2026-06)", "GammaMed - IFU Guidelines for Commissioning Ring and Tandem Applicators (2021-09)", "GammaMed VariSource - Generic Decay Table for Iridium-192 Sources (2018-01)"]
repos: [vcc-LG/brachy-hdr-tg43-check, jaimeh94/Point-Dose-Calculation_TG-43]
isocentro: []
texto: "../../texto/06 Braquiterapia/MPPG-HDR-A.md"
origem: "referencias/06 Braquiterapia/MPPG-HDR-A - HDR brachytherapy part A (2023).pdf"
conferida: 2026-10-16
---

# MPPG HDR (parte A): programa de braquiterapia HDR

**Em uma frase.** É o roteiro mínimo e atual (2023) do CQ do afterloader, dos aplicadores e do TPS de braquiterapia. Cada teste tem frequência e tolerância **recomendada** e, entre parênteses, a **exigida**.

O PDF tem 18 páginas e o texto saiu limpo. Frequências: **SE** = troca de fonte; **D** = diário (dia de tratamento); **AS** = após serviço; **C** = comissionamento; **A** = anual [p. 10].

## Afterloader (Tabela 4) [p. 10]

| Teste | Freq. | Tolerância |
| --- | --- | --- |
| Intensidade da fonte (medida) | SE | **3% (5%)** |
| Exatidão da posição da fonte | SE, D | **1 (2) mm** |
| Recolhimento com bateria na falta de energia | SE | Funcional |
| Exatidão do temporizador | SE, D | 1 s ou 1%, o maior |
| Linearidade do temporizador | AS | 1% (3%) |
| Intertravamento de porta; botão de recolhimento de emergência; botão de "último a sair"; interrupção; indicadores de fonte exposta | SE, D | Funcional |
| Áudio e vídeo; **kit de emergência completo**; monitor de sala independente com display remoto; **monitor de área calibrado presente** | D | Funcional |
| Data e hora do console | SE, D, horário de verão | 1 h |
| **Intensidade decaída no console × tabela de decaimento** | SE, D | **1%** |
| Conexão errada de cateter, canal e turret | D | Funcional |
| Comunicação TPS → console | SE | Funcional |

A posição da fonte exigida pela NRC é 1 mm, mas o próprio guia admite 2 mm como valor prático, pelo TG-56 [p. 10]. Linearidade do temporizador: a leitura com 60 s deve ser o dobro da de 30 s, dentro de 3% [p. 10]. **CQ diário obrigatório após qualquer reparo** [p. 10]. Se o console estiver integrado ao R&V, validar a comunicação no comissionamento e **ter um método alternativo de transferência** se a rede cair [p. 9–10].

## Aplicadores e tubos de transferência (Tabela 5) [p. 11]

| Teste | Freq. | Tolerância |
| --- | --- | --- |
| Inspeção visual da integridade (aplicadores, tubos, conexões usados no dia) | D | Passa/falha |
| Autorradiografia (se possível) | C | Referência |
| Comprimento do conjunto aplicador + tubo | A, D (ver texto), C | 1 mm (2 mm) |
| Conexões, integridade geométrica, trajeto da fonte e offsets | C | Passa/falha; referência |
| Biblioteca de aplicadores sólidos × aplicador físico | C | 1 mm (2 mm) |

## TPS de braquiterapia (Tabelas 6 a 8) [p. 13–15]

| Teste | Tolerância |
| --- | --- |
| Imagem: transferência, orientação, rótulos (obrigatórios) | Passa/falha |
| Delineamento de fonte, ponto e linha | 1 mm (2 mm) |
| **Dados do modelo da fonte** (C, A) | **Exato** |
| **Decaimento da fonte** (C, SE) | **1%** |
| Dose em ponto, fonte única (C, A) | **2% (3%)** |
| Dose em ponto, várias fontes (C) | 3% (5%) |
| DVH (C) | Funcional |
| Geometria do aplicador sólido | 1 mm (2 mm) |
| Posição da fonte no aplicador | 2 mm (3 mm), conforme o aplicador |
| Integridade da transferência de dados; **dry run fim a fim** | Funcional (obrigatórios) |

## Como se aplica

Base das fichas E01–E08. O GammaMedplus iX (fonte de Ir-192, troca a cada cerca de 4 meses, POP-023) tem no IFU os capítulos de emergência, troca de fonte e CQ diário (ver a ficha E04).
