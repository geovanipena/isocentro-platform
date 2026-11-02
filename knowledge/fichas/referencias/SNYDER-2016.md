---
codigo: SNYDER-2016
titulo: "Snyder M et al. Modeling the Agility MLC in the Monaco treatment planning system. J Appl Clin Med Phys 17(3)"
ano: 2016
emissor: Karmanos Cancer Institute (artigo, JACMP)
tipo: artigo
vigencia: histórico (Elekta Monaco 5.0; lição vale para o modelo de MLC de qualquer TPS)
atividades: [B01, B02, C06]
refs: [MPPG-5b-TPS, TG-119, TG-332, TG-218]
manuais: []
repos: []
isocentro: []
texto: "../../texto/05 QA de equipamentos, IGRT e dosimetria/SNYDER-2016.md"
origem: "referencias/05 QA de equipamentos, IGRT e dosimetria/SNYDER-2016 - Modeling the Agility MLC in the Monaco treatment planning system (2016).pdf"
conferida: 2026-10-20
---

# Snyder 2016: ajustar o modelo de MLC (Agility) no Monaco

**Em uma frase.** Mostra que o modelo de MLC proposto pelo fornecedor (pacote ExpressQA) **passou na auditoria IROC**, mas ficou **inferior** ao ajustado localmente com medidas pontuais em vários planos clínicos (TG-119), e propõe uma **receita** que ajusta só três parâmetros: **offset da lâmina, fuga na ponta e transmissão** [SNYDER-2016 p. 10–11].

PDF de 12 páginas (impressão da página web do JACMP); texto limpo.

## Lições

- Um único campo de teste do fornecedor não dá estatística: o pior modelo podia ter a maior aprovação 2%/2 mm num campo isolado [p. 10].
- Campos de teste do MLC são "patológicos" (isolam um efeito); ajustar perfeitamente esses perfis **não garante** o melhor modelo para planos clínicos [p. 10].
- Com muitos parâmetros ajustáveis há risco de **sobremodelagem**; parar em offset, fuga na ponta e transmissão [p. 11].
- Arranjos de baixa resolução e densidade diferente da água (ArcCHECK) complicam o ajuste; preferir sistemas mais simples e medidas pontuais [p. 10].

## Receita proposta [SNYDER-2016 p. 11]

1. Partir do modelo padrão e criar vários planos IMRT/VMAT (TG-119 ou casos típicos da clínica).
2. Medir dose pontual **no alvo e na região de dose baixa**.
3. Dose média no alvo alta ou baixa → ajustar offset/fuga na ponta.
4. Conferir campo de junção (3ABUT) no detector de maior resolução.
5. Dose fora do alvo baixa ou alta → ajustar transmissão e compensar no offset.
6. Recalcular os planos clínicos num fantoma de água e conferir as taxas de aprovação γ.

## Como se aplica no CLINICA

- B01/B02: o Eclipse (AAA/Acuros) tem parâmetros equivalentes (**DLG** e **transmissão do MLC**); a mesma lógica vale: ajustar com **vários planos clínicos medidos**, não só com campos de teste do fornecedor, e não confiar apenas em passar na auditoria externa (ver TG-332).
