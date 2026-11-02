---
codigo: BALLESTER-2004-ERRATUM
titulo: "Ballester F et al. Erratum: 'Technical note: Monte-Carlo dosimetry of the HDR 12i and Plus 192Ir sources' [Med Phys 28, 2586–2591 (2001)]. Med Phys 31(8):2372"
ano: 2004
emissor: Universidade de Valência / Hospital La Fe (errata, Medical Physics)
tipo: artigo (errata)
vigencia: "vigente; o artigo original de 2001 não está no acervo (pendência de aquisição)"
atividades: [E01, E03, E07, H02]
refs: [MPPG-HDR-A, CLRP-GM12i, TG-43U1]
manuais: ["GammaMedplus iX - Instructions for Use (v1.2.5, 2026-06)"]
repos: [vcc-LG/brachy-hdr-tg43-check, jaimeh94/Point-Dose-Calculation_TG-43]
isocentro: []
texto: "../../texto/06 Braquiterapia/BALLESTER-2004-ERRATUM.md"
origem: "referencias/06 Braquiterapia/BALLESTER-2004-ERRATUM - Erratum Monte-Carlo dosimetry of HDR 12i and Plus sources (2004).pdf"
conferida: 2026-10-21
---

# Errata de Ballester 2004: sinal do coeficiente a₃ da função de dose radial (fontes GammaMed 12i e Plus)

**Em uma frase.** Corrige o **sinal do coeficiente a₃** do ajuste polinomial da **função de dose radial g(r)** publicado em 2001 para as fontes de Ir-192 **GammaMed HDR 12i e Plus**: o valor correto é **a₃ = 2,8781 × 10⁻⁵** (positivo); o valor errado gera desvios de **> 0,5% a 3 cm, > 1,5% a 5 cm, > 3% a 6 cm e > 6% a 8 cm** [BALLESTER-2004-ERRATUM p. 1].

PDF de 1 página; valor conferido na imagem da página (o texto extraído perdeu os sinais).

## Como se aplica no CLINICA

- E03/E07 (CEL, GammaMed IX): qualquer **cálculo independente TG-43** (planilha, script, pacote do GitHub) que use os parâmetros de Ballester 2001 para a fonte Plus deve usar **a₃ positivo**; o erro só aparece longe da fonte (> 3 cm), justamente onde ficam pontos de OAR.
- Preferir as tabelas de g(r) e F(r,θ) do consenso/registro de dados (ex.: CLRP, na pasta `06/CLRP-GM12i`) em vez do ajuste polinomial; conferir qual fonte o BrachyVision/TPS usa (Plus × 12i).
