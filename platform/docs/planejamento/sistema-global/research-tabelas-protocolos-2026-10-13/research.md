---
topic: Tabelas dos protocolos de CQ e dosimetria para o nível 2 do catálogo SGQ-RT
type: domain
decision: Gerar o nível 2 do catálogo (obrigação → item de verificação), cada item marcado com o protocolo de origem
source: "import: extracao_protocolos_QA_radioterapia_2026.md (ferramenta externa, 0 itens) + extração local dos textos de acesso aberto (IAEA, AAPM, Europe PMC)"
status: parcial — lotes 1–5 com fontes abertas; lote 6 só com TECDOC-1274; documentos fechados pendentes
created: '2026-10-13'
updated: '2026-10-13'
---

# Nível 2 do catálogo SGQ-RT: itens extraídos dos protocolos

## Resumo

Há **358 itens de verificação** em [digests/itens-nivel2.csv](digests/itens-nivel2.csv). Cada um traz o protocolo, a tabela, o limite literal e o id da obrigação do `catalogo-v1.csv`. Os valores vieram de forma determinística do texto integral publicado pela fonte: XML do Europe PMC para os MPPGs e PDF oficial para o TRS-398 e o adendo do TG-51. Nenhum valor veio de resumo ou de memória.

O relatório externo não trouxe nenhum item. A ferramenta não leu os documentos e recusou transcrever as tabelas. Dele só se aproveitou a lista de versões vigentes.

| Lote | Protocolo | Itens | Obrigações |
|---|---|---:|---|
| 1 Acelerador | MPPG 8.b (2023), Tab. 3–8 | 57 | A07, A10, A13, A14, A15 |
| 2 Imagem/IGRT | MPPG 2.b (2021), Tab. 1 | 20 | A08 |
| 3 Dosimetria | TRS-398 Rev. 1 (2024), Tab. 3, 14, 15, 18, 19, §4.2–4.4 | 31 | A03, A04, A05, A06 |
| 3 Checagem cruzada | Adendo TG-51 (2014), Tab. III | 6 | A04 |
| 4 TPS | MPPG 5.b (2022), tabela-resumo e Tab. 4–10 | 56 | B01, B02 |
| 5 SRS/SBRT | MPPG 9.b (2025), Tab. 1 (linac braço C) | 22 | C07, A07 |
| 5 Plano e prontuário | MPPG 11.a (2021), Tab. 7–11, 13, 14 | 160 | C04, D05, E03, LACUNA |
| 6 HDR | TECDOC-1274 (2002), §5.5, §7.1.3, §7.1.6, §9.1, §9.2 | 6 | E02, E03, E06 |

## Achados

1. **Conflito de periodicidade da calibração.** O TRS-398 Rev. 1 (§4.3, p. 61 do PDF) admite calibrar a câmara de referência em intervalos de até 3 anos. A NN 6.10 (art. 49) exige 2 anos. No sistema prevalece a norma brasileira; o item mantém a observação do conflito [1].
2. **Câmara de classe de referência: os dois protocolos divergem num critério.** Para a dependência de Ppol com a energia, o TRS-398 Rev. 1 (Tab. 3) admite menos de 0,3% entre Co-60 e 10 MV. O adendo do TG-51 (Tab. III) admite menos de 0,5% na faixa total. Fuga, recombinação e estabilidade coincidem [1][2].
3. **A constância mensal do MPPG 8.b não cumpre o art. 35, IV da NN 6.10.** O MPPG 8.b (Tab. 4, D1) compara a saída com a linha de base do dispositivo (diário 3%, mensal 2%) e só no anual a compara com o TG-51 (1%). A norma pede dose absorvida na água em condições de referência todo mês. O item mensal fica ligado à A15 com essa ressalva [3].
4. **O MPPG 8.b usa o TG-51 como referência anual de saída.** Por decisão do usuário, o IT0004 passa a valer como "1% da saída nominal pelo protocolo do PPR (TRS-398 Rev. 1)"; o limite literal fica preservado.
5. **A checagem física semanal confirma a lacuna do catálogo v1.** O MPPG 11.a (Tab. 10 e 14) traz itens semanais para teleterapia e braquiterapia, e o catálogo não tem obrigação correspondente. Esses itens estão marcados `LACUNA` [5].
6. **TC de simulação:** existe o AAPM TG-66U1 (relatório 83.B, Med Phys 2026), que atualiza o TG-66. Ele deve substituir o TG-66 no lote 2, mas o texto não estava aberto na API.

## Pendências (fontes fechadas ou bloqueadas)

| Documento | Situação | Rota |
|---|---|---|
| TG-142 (2009) | aapm.org bloqueia download automático (403) | você baixa o PDF no navegador |
| TG-51 original (1999) | idem | idem; necessário para condições de referência e %dd(10)x |
| TG-198, TG-218, TG-201, TG-114, TG-203, TG-179, TG-132 | Med Phys sem acesso aberto | PDF pela assinatura AAPM/ABFM |
| TG-263, TG-275, TG-66U1 | estão no PMC, mas sem texto integral na API | baixar o PDF pelo PMC no navegador |
| Lote 6 HDR: TG-56, TG-59, TG-43U1, ESTRO, GammaMedplus | só o TECDOC-1274 foi extraído; falta a tolerância entre a medida da fonte e o certificado | PDFs; manual do GammaMedplus como fonte do fabricante |
| MPPG 1 (TC) | não pesquisado | Europe PMC |

## Limitações

- Os itens do MPPG 5.b receberam a frequência "comissionamento e após mudança relevante do TPS" pelo escopo do documento. O texto não foi lido em busca de uma frequência de rotina.
- A transcrição do TG-51 vem de PDF em duas colunas; confira a Tab. III na página 15. Na Tab. 19 do TRS-398 o símbolo "≥" se perdeu e foi marcado `[≥]`.
- O status `TRANSCRITO` quer dizer que o texto foi tirado da fonte por script. A conferência automática (`scripts/confere.py`) achou literalmente na fonte 154 dos 162 limites numéricos. Os 8 restantes são de forma, não de valor: grau sobrescrito no XML, quebra de coluna no TG-51 e anotação em português no TECDOC. Os outros 196 itens não têm limite numérico: são condições, itens de checklist ou remetem a outra tabela.

## Fontes

1. IAEA. *TRS-398 Rev. 1: Absorbed Dose Determination in External Beam Radiotherapy*. 2024. https://www-pub.iaea.org/MTCD/publications/PDF/p15048-DOC-010-398-Rev1_web.pdf (acesso 13/10/2026)
2. McEwen M et al. *Addendum to the AAPM's TG-51 protocol for clinical reference dosimetry of high-energy photon beams*. Med Phys 41(4), 2014. https://www.aapm.org/pubs/reports/RPT_67_Addendum.pdf (acesso 13/10/2026)
3. *AAPM MPPG 8.b: Linear accelerator performance tests*. JACMP, 2023. PMC10647991 (acesso 13/10/2026)
4. *AAPM MPPG 2.b: Commissioning and QA of X-ray-based IGRT systems*. JACMP, 2021. PMC8425868; *MPPG 5.b*. JACMP, 2022. PMC9512346; *AAPM-RSS MPPG 9.b: SRS-SBRT*. JACMP, 2025. PMC11969102 (acesso 13/10/2026)
5. Xia P et al. *MPPG 11.a: Plan and chart review in external beam radiotherapy and brachytherapy*. JACMP, 2021. PMC8425907 (acesso 13/10/2026)
6. IAEA. *TECDOC-1274: Calibration of photon and beta ray sources used in brachytherapy*. 2002. https://www-pub.iaea.org/MTCD/Publications/PDF/te_1274_prn.pdf (acesso 13/10/2026)

## Validade (quando reconferir)

As versões dos MPPGs e do TRS-398 devem ser reconferidas a cada 12 meses no catálogo da AAPM e da IAEA.
