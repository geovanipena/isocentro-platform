---
topic: Tabelas dos protocolos de CQ e dosimetria para o nível 2 do catálogo SGQ-RT
type: domain
decision: Gerar o nível 2 do catálogo (obrigação → item de verificação), cada item marcado com o protocolo de origem
status: aguardando relatório externo
created: '2026-10-13'
---

# Prompt de pesquisa (colar na ferramenta de deep research)

Se a ferramenta aceitar anexos, anexe os PDFs dos protocolos que você tiver
(TG-142, TRS-398 etc.): a transcrição de tabelas a partir do PDF anexado é
muito mais confiável que a feita a partir de busca.

Se a resposta for cortada por limite de tamanho, peça "continue a partir do
lote N" na mesma conversa.

```text
PAPEL E OBJETIVO
Você é um físico médico pesquisador, especialista em controle de qualidade e
dosimetria em radioterapia. Quero EXTRAIR, PROTOCOLO POR PROTOCOLO, AS
TABELAS DE TESTES (teste, frequência, tolerância ou nível de ação, método)
dos documentos listados abaixo, transcritas de forma literal e rastreável.

Cada linha extraída vai virar um ITEM DE VERIFICAÇÃO de um sistema interno de
gestão da qualidade. O sistema tem dois níveis: OBRIGAÇÃO (da norma
brasileira, já catalogada) → ITEM (gerado da tabela do protocolo). Todos os
protocolos candidatos geram itens, cada item marcado com o protocolo de
origem. Um valor errado vira um alerta errado; por isso FIDELIDADE AO
DOCUMENTO e RASTREABILIDADE valem mais que prosa ou resumo.

Contexto do serviço (Brasil): aceleradores lineares Varian com MLC, ARIA e
Eclipse, IGRT (kV, MV e CBCT), TC de simulação, técnicas 3D, IMRT, VMAT,
SRS/SBRT; braquiterapia HDR. IORT está FORA do escopo.
Protocolo de dosimetria de referência adotado no plano de proteção
radiológica: IAEA TRS-398. O AAPM TG-51 (com adendo) entra como checagem
cruzada, também extraído.

REGRAS DE EXTRAÇÃO (inegociáveis)
1. Transcreva os valores EXATAMENTE como estão no documento: número,
   unidade, sinal (±), "ou" e "o que for maior", notas de rodapé da tabela.
   Não arredonde, não converta unidade, não "harmonize" valores entre
   protocolos.
2. Toda linha traz: documento, versão/ano, número da tabela ou seção, página
   e URL. Linha sem localização exata vai marcada "NÃO VERIFICADO".
3. Se você não teve acesso ao texto integral do documento (só resumo, citação
   secundária ou memória), diga isso no cabeçalho do lote e marque todas as
   linhas dele "NÃO VERIFICADO". Não reconstrua tabela de memória.
4. Fonte primária apenas: aapm.org (relatórios e MPPGs), Medical Physics,
   JACMP, iaea.org (publicações), estro.org, PubMed/PMC para localizar o
   artigo. Slides, cursos, blogs, planilhas de terceiros e manuais de
   fabricante não valem como fonte do valor.
5. Para cada documento, confirme a VERSÃO VIGENTE em 2026: se foi
   substituído, atualizado, recebeu adendo ou errata (exemplos a verificar:
   TRS-398 Rev. 1; TG-51 e adendo; MPPG 5 → 5.b; MPPG 8 → 8.b; MPPG 9 → 9.b;
   TG-142 e o relatório que o atualiza; TG-43 e atualizações U1/U2; TG-36 e
   TG-158). Extraia da versão vigente e cite a anterior só se o valor mudou.
6. Quando o mesmo teste aparecer em dois protocolos com frequência ou
   tolerância diferentes, extraia AMBOS como linhas separadas e registre o
   CONFLITO. Não escolha um.
7. Diferencie tolerância, nível de ação e nível de investigação quando o
   documento fizer essa distinção; não junte.
8. Preserve as condições de aplicabilidade da linha: tipo de máquina, energia
   (fótons/elétrons), técnica (não-IMRT, IMRT, SRS/SBRT), modalidade de
   imagem. Teste condicional sem a condição é teste errado.
9. Admita lacunas. "Este documento não traz tabela de frequência/tolerância
   para X" é resultado válido.

LOTES (faça na ordem; as listas são PONTOS DE PARTIDA: confirme número, ano,
versão e vigência de cada documento antes de extrair)

LOTE 1. ACELERADOR, MLC, MESA, LASERS, SEGURANÇA
   AAPM TG-142 (Tabelas de testes diários, mensais e anuais; tabelas de MLC
   e de imagem); relatório que atualiza o TG-142, se houver; AAPM MPPG 8
   (versão vigente) — testes mínimos de acelerador; AAPM TG-198
   (implementação do TG-142: métodos de medida); TG-135/TG-148 só se o
   serviço os aplicar (registre a existência, não extraia).
   Liga às obrigações: A07, A10, A13, A14.

LOTE 2. IMAGEM, IGRT E TC DE SIMULAÇÃO
   AAPM MPPG 2 (versão vigente, 2.a ou 2.b) — CQ de imagem/IGRT; TG-179
   (CBCT); TG-142 (parte de imagem, se não extraída no lote 1); TG-104 se
   houver tabela; AAPM TG-66 (TC de simulação) e MPPG 1 (versão vigente,
   protocolos de TC); TG-132 (registro de imagens: testes de comissionamento
   e periódicos).
   Liga às obrigações: A08, A09, C08.

LOTE 3. DOSIMETRIA DE REFERÊNCIA E INSTRUMENTOS
   IAEA TRS-398 (versão vigente; protocolo de referência do serviço):
   condições de referência por feixe (fótons, elétrons), especificação da
   qualidade do feixe, requisitos de câmara e eletrômetro, correções (kT,P,
   kpol, ks, kelec), incerteza estimada; quaisquer verificações periódicas ou
   de constância recomendadas. AAPM TG-51 e adendo para fótons: as mesmas
   grandezas, para checagem cruzada. Ponto de conflito esperado: definição
   de qualidade de feixe (TPR20,10 × %dd(10)x) e condições de referência —
   tabele lado a lado. IAEA TRS-483 só se aplicável a campos pequenos
   (SRS/SBRT): requisitos de detector e fatores de saída.
   Inclua as constâncias mensais/diárias de dose e fator de calibração que
   os protocolos recomendam, para casar com a norma brasileira (CNEN NN 6.10,
   art. 35: diário fator de calibração do acelerador; mensal dose absorvida
   na água em condições de referência; art. 49: calibração bienal do
   sistema de referência e aferição trimestral com fonte-teste, ±1%).
   Liga às obrigações: A03, A04, A05, A06, A11, A13, A15, A16.

LOTE 4. TPS, TRANSFERÊNCIA DE DADOS E CÁLCULO INDEPENDENTE
   AAPM MPPG 5 (versão vigente): testes de comissionamento e validação de
   dose, com critérios; TG-53 se ainda referenciado; TG-201 (transferência e
   integridade de dados); TG-114 (cálculo independente de UM: níveis de
   ação); TG-219 (cálculo independente para IMRT/VMAT, se publicado);
   TG-106 (comissionamento de feixe: requisitos de medida, não valores de
   feixe).
   Liga às obrigações: A02, B01, B02, B03, B04, C05, H01.

LOTE 5. PACIENTE: PLANO, QA ESPECÍFICO E TÉCNICAS ESPECIAIS
   AAPM TG-218 (QA específico de IMRT/VMAT: critérios de gamma, limites de
   tolerância e de ação, método); TG-119 se citado como teste de
   comissionamento; MPPG 9 (versão vigente, SRS/SBRT); TG-101 (SBRT: itens
   de QA e de verificação); TG-275 e MPPG 11.a (itens da checagem física
   inicial, semanal e de fim de tratamento — liste os itens de checagem
   recomendados como tabela); TG-263 (nomenclatura: regras verificáveis);
   TG-36/TG-158 (dose periférica e gestante: limiares de ação); TG-203
   (marca-passo/CDI: categorias de risco e limiares de dose).
   Liga às obrigações: C03, C04, C06, C07, C09, D03, D05.

LOTE 6. BRAQUITERAPIA HDR
   AAPM TG-56 (testes de aceitação e periódicos de afterloader, com
   frequências e tolerâncias); TG-59 (segurança do HDR: testes diários e
   de troca de fonte); TG-40 (parte de braquiterapia, se ainda vigente);
   TG-43 e atualizações (somente: dados de entrada a verificar no TPS e
   critérios de aceitação de cálculo, não tabelas de dose de fonte); IAEA
   TECDOC-1274 (calibração de fontes de braquiterapia: tolerância entre
   certificado e medida); ESTRO booklet de QA de braquiterapia (n.º a
   confirmar) e recomendações GEC-ESTRO aplicáveis a HDR.
   Liga às obrigações: E01, E02, E03, E04, E06, H02.

PARA CADA LOTE, ANTES DA TABELA
- Cabeçalho do lote: documentos usados (título, número, ano, versão
  vigente, URL, acesso ao texto integral: sim/não).
- O que o documento NÃO traz (sem tabela, só recomendação qualitativa).

FORMATO DA RESPOSTA (siga exatamente)
1. Resumo de uma página: quantos itens por lote e por protocolo, os
   conflitos mais relevantes entre protocolos, documentos sem acesso
   integral, documentos substituídos ou com versão nova.
2. TABELA DE ITENS, uma linha por teste, em Markdown, com as colunas na
   ordem abaixo (célula vazia = "—", nunca omita a coluna):
   lote | obrigação (id do catálogo, ex. A07) | protocolo | versão/ano |
   tabela/seção | página | categoria (ex. dosimetria, mecânico, segurança,
   imagem, MLC, TPS, paciente) | teste (texto literal) | aplicabilidade
   (máquina/energia/técnica/modalidade) | frequência (literal) | tolerância
   (literal) | nível de ação (literal) | método ou instrumento indicado |
   nota de rodapé da tabela | URL | acesso integral (sim/não) | status
   (VERIFICADO / NÃO VERIFICADO) | conflito/observação
3. Tabela de CONFLITOS: teste | protocolo A (valor, tabela) | protocolo B
   (valor, tabela) | natureza da diferença.
4. Tabela TRS-398 × TG-51 lado a lado (lote 3).
5. Tabela de DOCUMENTOS: título, número, ano, versão vigente, substitui ou
   é substituído por, URL, acesso integral.
6. Lacunas: o que não foi encontrado e onde seria preciso procurar.
7. Lista numerada de fontes com URL e data de publicação.
```

Ao terminar, salve o relatório (PDF, Markdown ou texto) e diga "processa o
relatório": ele vai para `imports/` desta pasta. No Process, cada linha
marcada VERIFICADO ainda é conferida contra o PDF do protocolo antes de virar
item do catálogo.
