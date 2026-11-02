---
codigo: FONTENOT-2014
titulo: "Fontenot JD. Evaluation of a novel secondary check tool for intensity-modulated radiotherapy treatment planning. J Appl Clin Med Phys 15(5):207–215"
ano: 2014
emissor: Mary Bird Perkins Cancer Center (artigo, JACMP)
tipo: artigo
vigencia: histórico (produto hoje Varian Mobius3D)
atividades: [C05, H01, C06, B10, I01]
refs: [TG-219, TG-218, TG-119, MPPG-5b-TPS]
manuais: []
repos: []
isocentro: ["dominio/paralelo.py"]
texto: "../../texto/02 Plan check e revisão de prontuário/FONTENOT-2014.md"
origem: "referencias/02 Plan check e revisão de prontuário/FONTENOT-2014 - Evaluation of a novel secondary check tool for IMRT planning Mobius3D (2014).pdf"
conferida: 2026-10-20
---

# Fontenot 2014: avaliação do Mobius3D como segundo cálculo 3D de IMRT/VMAT

**Em uma frase.** Testa o **Mobius3D** (cálculo independente 3D por convolução/superposição em GPU, com **modelo de feixe "de fábrica"** por modelo de acelerador, que também compara DVH com limites RTOG) contra medidas em fantoma e contra o TPS em 30 pacientes de VMAT: a exatidão foi **comparável à do TPS** [FONTENOT-2014 p. 1].

PDF de 9 páginas, texto limpo.

## Resultados

| Teste | Resultado | Página |
| --- | --- | --- |
| Pontos com câmara, planos TG-119 (IMRT) | Diferença média −0,8% (TPS) e −0,6% (M3D) | Tab. 1 [FONTENOT-2014 p. 4] |
| Pontos com câmara (VMAT) | −1,9% (TPS) e −1,6% (M3D); maiores desvios em região de gradiente (C-shape, cabeça e pescoço até cerca de 4–5%) | Tab. 1 [FONTENOT-2014 p. 4] |
| Filme, γ 3%/3 mm | M3D e TPS sem diferença estatística | [FONTENOT-2014 p. 4–5] |
| Pacientes, M3D × TPS, **γ 5%/3 mm** | Próstata 100%; pulmão 99,7%; cabeça e pescoço 98,7% (mínimo 93,2%); média 99,5% | [FONTENOT-2014 p. 1, 5] |
| Onde falha | **Ar na traqueia e no esôfago**: M3D calcula 5–7% a menos no ar que o TPS | [FONTENOT-2014 p. 5] |
| DVH | Sinalizou limites RTOG excedidos (cabeça de fêmur, bexiga, bulbo, medula/PRV, esôfago, parótidas, mandíbula) em planos já aprovados pelo médico | [FONTENOT-2014 p. 5] |

## Pontos de atenção

- Modelo **não comissionado localmente** (dados de referência do fabricante): é vantagem para adoção, mas o próprio autor alerta que o algoritmo é parecido com o do TPS, e o erro que ele pega é sobretudo de **implementação ou de software**, não do algoritmo [FONTENOT-2014 p. 7].
- Só um TPS (Pinnacle) e um acelerador (Elekta) foram testados; o critério γ 5%/3 mm entre cálculos é frouxo.

## Como se aplica no CLINICA

- C05/H01: ajuda a escolher um sistema comercial de segundo cálculo 3D para VMAT (Mobius3D, hoje da Varian) e a definir a aceitação (γ entre cálculos, regiões de ar). O `dominio/paralelo.py` do ISOCENTRO faz cálculo de UM pontual; para VMAT a NN-6.10 pede segundo sistema de cálculo, e um 3D independente seria o caminho.
- B10: se adotar um sistema "pré-comissionado", validar localmente antes do uso clínico (ver TG-219 e MPPG-5b).
