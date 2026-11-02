---
id: SPEC-isocentro-documentacao
companions:
  - ../spec-isocentro-fundacao/SPEC.md
  - ../spec-isocentro-qualidade/SPEC.md
  - ../architecture-isocentro-2026-10-19/ARCHITECTURE-SPINE.md
  - ../prd-isocentro-2026-10-16/prd.md
  - ../ux-isocentro-2026-10-16/EXPERIENCE.md
  - ../ux-isocentro-2026-10-16/DESIGN.md
  - ../decisoes-sem-base.md
  - rastreabilidade.md
sources:
  - ../../questionarios/documentacao.md
---

> **Contrato canônico.** Esta SPEC e os arquivos em `companions:` são o contrato completo do módulo Documentação e conformidade (`modulos/documentacao`) no MVP 5. Ela é construída **sobre a Fundação** (gravação, log, alerta, concentradora, cadastro de equipe). Instrumentos, certificados e aferição com decaimento (FR-36 e parte do FR-33) são da **spec da GQ**, e aqui só aparecem no painel. Do PRD valem §9 e §13. Da UX valem UJ-4, a matriz de perfis e a fila Vencimentos 60d. Toda decisão segue a regra do `docs/qms/escopo.md`: referência; com duas ou mais, a mais restritiva; sem base, `decisoes-sem-base.md`.

# ISOCENTRO — Módulo Documentação e conformidade

## Why

A NN-6.10 impõe prazos a treinamentos, auditoria externa, levantamento radiométrico, saúde ocupacional e monitoração individual. Hoje esses prazos ficam no `ppr-streamlit`, em JSON que o usuário carrega e baixa, sem alerta e sem histórico. O ASO ainda é extraído enviando o texto a uma IA externa (R-15). O módulo leva os vencimentos para o banco central, alerta antes de vencer e mesmo com o app fechado, e junta num só painel os prazos do serviço e os da GQ. O PPR de cada clínica deixa de ser documento montado à mão: o módulo o monta a partir das seções que cada módulo guarda, e ele muda quando o dado muda (decisão do usuário, 28/10/2026; mapa em `../ppr-vivo-mapa-2026-10-28.md`).

## Capabilities

Cada capacidade diz de onde vem o dado (**fonte**) e se muda o que sai impresso (**papel**). Nenhuma capacidade desta spec muda o papel do paciente.

- **CAP-1 — Cadastro de itens com vencimento** (FR-33)
  - **intent:** O físico ou o SPR/gestão cadastra itens com obrigação periódica, e cada tipo traz a periodicidade e a fonte dela.
  - **success:**
    - A periodicidade vem da norma ou da validade do próprio documento:
      - treinamento de PR: anual (NN-6.10 art. 20, VI);
      - treinamento de física médica: até 2 anos (art. 24, I, f);
      - auditoria externa: até 2 anos (art. 36);
      - levantamento radiométrico: até 2 anos (art. 29);
      - ASO: 1 ano do exame, ou menos se o PCMSO fixar (NR-7 7.5.8, II, a);
      - Autorização para Operação da CNEN e alvará sanitário: dois tipos, cada um pela data escrita no documento (SAES 1399 art. 16, d; NN-6.02 art. 8º);
      - SEVRRA: sem data, até haver data com fonte.
    - Cada data de partida é lançada a partir do documento de origem da clínica (PPR, ata, relatório de levantamento, autorização, alvará, ASO) e cita esse documento.
    - Item sem documento nasce "sem data" e aparece como informativo, nunca como em dia.
    - Tipo sem fonte de periodicidade não é aceito.
  - **fonte · papel:** NN-6.10, NR-7, NN-6.02 e documentos do serviço · não muda.

- **CAP-2 — Vencimento por evento** (FR-33)
  - **intent:** Um evento registrado faz o item vencer na hora, além do calendário.
  - **success:**
    - Modificação da instalação faz o levantamento radiométrico vencer (art. 29).
    - Retorno ao trabalho após ausência de 30 dias ou mais, mudança de risco e dose acima do limite anual fazem o ASO da pessoa vencer (NR-7 7.5.9; Anexo V, 5.1–5.2). O evento não guarda valor de dose.
    - O evento grava quem, quando e o que mudou. O alerta sai no mesmo dia.
  - **fonte · papel:** evento registrado pelo físico ou SPR · não muda.

- **CAP-3 — ASO por pessoa** (FR-33, V1)
  - **intent:** O ISOCENTRO acompanha a validade do ASO de cada IOE, de qualquer vínculo, sem guardar o documento.
  - **success:** O registro tem só a pessoa, a data do exame e a validade (exame + 12 meses, ou o intervalo menor do PCMSO); o PDF e o resultado (apto/inapto) não entram. Só SPR/gestão e o físico responsável leem, com recusa no banco. IOE sem ASO aparece listado. O lançamento é manual até a R-15.
  - **fonte · papel:** lançamento do SPR ou do físico; NR-7; PCMSO · não muda.

- **CAP-4 — Monitoração individual mensal** (art. 20, IV–V)
  - **intent:** O ISOCENTRO acompanha, por IOE, se o resultado mensal da monitoração individual foi recebido.
  - **success:** Cada IOE tem, por mês, "recebido" com data ou pendente, sem valor de dose. Mês sem recebimento vira pendência no painel.
  - **fonte · papel:** lançamento do SPR ou do físico · não muda.

- **CAP-5 — Painel de vencimentos** (FR-34, FR-41)
  - **intent:** O usuário vê o que vence, por clínica, numa janela configurável, com os prazos do serviço e os da GQ juntos.
  - **success:**
    - Aviso prévio por tipo, padrão de 60 dias (cobre os 30 dias mínimos do pedido de renovação da autorização, NN-6.02 art. 23).
    - Vencido em `alta`, dentro do aviso em `atencao` e sem data em `informativo`.
    - Inclui os testes de CQ não diários, os instrumentos e as aferições da GQ, lidos pela fachada de consulta dela.
    - Prazo que vence com o app fechado aparece como `alta` na abertura (concentradora).
    - O contador "Vencimentos 60d" da Zona 1 abre o painel filtrado pela clínica.
  - **fonte · papel:** itens deste módulo + fachada da GQ · não muda.

- **CAP-6 — Migração do ppr-streamlit** (FR-35, AD-37)
  - **intent:** O que hoje está no `ppr-streamlit` serve de conferência para as datas lançadas no ISOCENTRO, e depois do corte ele deixa de ser fonte.
  - **success:**
    - O físico importa os JSON do PPR como conferência: autorização, levantamento, auditoria, SEVRRA, ASOs e os certificados (os de instrumento vão para a GQ).
    - Um relatório lista, item a item, o que casou com o documento, o que diverge e o que não foi importado.
    - Divergência entre documento e JSON, até resolvida, usa a data que vence mais cedo.
    - Depois do corte, o `ppr-streamlit` deixa de ser fonte de vencimento e nunca há gravação dupla.
  - **fonte · papel:** documentos de cada clínica + JSON do `ppr-streamlit` · não muda.

- **CAP-7 — Módulo Documentação no shell** (FR-9, UJ-4)
  - **intent:** O físico e o SPR/gestão cadastram, registram eventos e acompanham o painel numa tela do módulo.
  - **success:** O cartão aparece só para físico e SPR/gestão. O painel abre por clínica ou "Todas" para o físico responsável. A UJ-4 roda de ponta a ponta em homologação.
  - **fonte · papel:** fachada de consulta do módulo · não muda.

- **CAP-8 — Validação do módulo** (FR-40)
  - **intent:** O módulo tem relatório de validação antes do primeiro uso real.
  - **success:** O relatório cobre:
    - casos de borda de prazo: dentro do aviso, vencido no fim de semana com o app fechado, sem data e por evento (levantamento e ASO);
    - o relatório de migração conferido item a item contra o `ppr-streamlit`;
    - o teste de leitura restrita do ASO.

    O relatório é assinado pelo físico.
  - **fonte · papel:** testes e migração · não muda.

- **CAP-9 — Lista de IOEs**
  - **intent:** O ASO e a monitoração mensal se ligam a uma só lista de IOEs por clínica, mantida pelo SPR.
  - **success:** A lista é a marca "IOE" por pessoa e clínica no cadastro de equipe do núcleo (AD-38), não uma segunda fonte. IOE é quem trabalha em área controlada ou supervisionada, não o cargo (NN-3.01 arts. 57 e 60). Só o SPR mantém a marca, e a lista é conferida contra a lista nominal do PPR a cada revisão dele.
  - **fonte · papel:** cadastro de equipe da Fundação (CAP-20) + PPR de cada clínica · não muda.

- **CAP-10 — PPR vivo: montagem do documento** (FR-35, AD-41)
  - **intent:** O PPR de cada clínica é montado pelo ISOCENTRO com as seções que cada módulo guarda, e muda quando o dado muda.
  - **success:**
    - Cada capítulo é lido da fachada do módulo dono (mapa em `../ppr-vivo-mapa-2026-10-28.md`): Fundação, GQ, Plano, Segurança e este módulo. A Documentação não guarda dado nem texto de outro módulo.
    - Uma seção é o dado vivo do módulo mais o texto versionado dele. Dado que falta sai marcado "sem dado — <módulo>", nunca preenchido.
    - **Edição pela aba PPR** (decisão do usuário, 28/10/2026): a aba da Documentação edita o texto de qualquer seção, uma parte por vez, mas grava na tabela do módulo DONO (`<modulo>.ppr_parte`, AD-3 mantido no banco), com autor no log e a versão anterior substituída, não apagada (AD-5). Quem edita, provisoriamente: físico e admin — até a R-19/R-78 darem a capacidade de SPR que a CAP-11 pede.
    - A emissão é um retrato com versão, assinado pelo SPR (assinatura presa à versão, Fundação CAP-13). Mudança, depois da última emissão, em dado ou texto que entra no PPR vira aviso "PPR desatualizado", com a lista do que mudou e de qual módulo.
    - Modificação da instalação exige PPR novo antes dela (NN-6.10 art. 15, XIV), e o aviso sai como `alta`.
    - O leiaute segue o modelo do serviço (`referencias/01 .../PPR-CLINICA`, mar/2024).
  - **fonte · papel:** fachadas dos módulos · **muda:** o PPR passa a sair do ISOCENTRO (documento novo; o papel do paciente não muda).

- **CAP-11 — Seções do PPR deste módulo**
  - **intent:** Os capítulos de radioproteção e conformidade do PPR moram aqui, com dado e texto.
  - **success:** Objetivo e descrição; classificação e descrição das áreas; cálculo de barreiras e estimativas de dose; monitoração individual (CAP-4) e de áreas (levantamento); controle médico dos IOEs (CAP-3); treinamento em PR e educação continuada (CAP-1); níveis operacionais e restrições; anexos (documentos de origem da CAP-1). O texto tem versão, autor e data, e só o SPR o altera. A primeira versão vem do PPR vigente de cada clínica (CEL mai/2026, BET jul/2026, DUO jan/2025), citado.
  - **fonte · papel:** PPR vigente de cada clínica e itens deste módulo · entra no PPR.

## Constraints

- **Instrumentos são da GQ:** a Documentação não cadastra instrumento nem aferição e não grava em tabela da GQ; lê pela fachada (AD-3).
- **Dado de funcionário não sai da rede:** nenhum texto ou PDF de ASO vai a terceiros ou a IA externa (R-15, NFR-2); o ISOCENTRO não guarda o PDF nem o resultado do ASO.
- **Periodicidade com fonte:** artigo da norma, NR-7, PCMSO ou validade do documento; sem fonte, o item fica "sem data".
- **Data com documento:** toda data de partida cita o documento de origem; o JSON do `ppr-streamlit` nunca é fonte.
- **Cada módulo guarda as suas seções do PPR:** a montagem só lê fachadas (AD-3); texto de outro módulo nunca é copiado para cá.
- **Uma só lista de equipe:** a lista de IOEs é marca no cadastro do núcleo (AD-38), nunca tabela própria do módulo.
- **Sem dose individual:** a monitoração individual entra só como recebimento.
- **Visibilidade por clínica** pela RLS; "Todas" só para o físico responsável (AD-12).
- **Decisão sem base é provisória e anunciada:** os itens de `decisoes-sem-base.md` (#18–21) seguem a opção mais conservadora até a discussão no serviço.
- **Classe A** (`classificacao-62304.md`, físico, 26/10/2026).

## Non-goals

- O `ppr-streamlit` fica como está até o corte (AD-41) e não recebe o PPR vivo; o ramo `programa-cq-tg142` dele não é trazido (o programa de GQ vem da GQ).
- Instrumentos, certificados de instrumento e aferição com decaimento (spec da GQ, CAP-6 e CAP-14).
- Valor de dose da monitoração individual e níveis de investigação.
- Guarda do PDF ou do resultado do ASO; extração automática de ASO antes da R-15.
- Canal de alerta externo.

## Success signal

- Em homologação, a migração do `ppr-streamlit` sai com relatório conferido item a item, e cada data no ISOCENTRO cita o documento de origem.
- O painel da BET mostra, juntos, a calibração bienal de um instrumento (vinda da GQ), a aferição trimestral, o treinamento anual de PR, a Autorização para Operação e o alvará como itens separados, e o SEVRRA como "○ sem data", que nunca aparece em dia.
- Um prazo vencido no sábado aparece como `alta` na segunda ao abrir.
- Registrar uma modificação da instalação faz o levantamento vencer na hora; registrar o retorno de um IOE após 30 dias de afastamento faz o ASO dele vencer na hora.
- Um técnico não lê ASO.

## Assumptions

Aplicadas pela regra de decisão; a conferir pelo físico.

- **ASO:** 1 ano do exame para todo IOE, até o PCMSO de cada clínica dizer outro intervalo (`decisoes-sem-base.md` #18).
- **Autorização:** a chave `autorizacao_funcionamento` do `ppr-streamlit` é conferida contra os dois tipos (#19).
- **SEVRRA:** sem data (#20).
- **IOE por perfil:** marca por pessoa, mantida pelo SPR (#21).
- **Divergência na migração:** vale a data que vence mais cedo.
- **Aviso prévio:** padrão de 60 dias (FR-34; ficha A04; NN-6.02 art. 23).
- **Classe:** A (`classificacao-62304.md`, 26/10/2026).

## Open Questions

- **Corte do PPR:** a partir de qual emissão o PPR do ISOCENTRO substitui o do `ppr-streamlit` em cada clínica.
- **riscos.md:** linhas do módulo (S, O, D pelo físico): item marcado em dia sem data; vencimento por evento não disparado; data lançada sem documento; IOE fora da lista.
- **Em discussão no serviço:** PCMSO de cada clínica (#18), chave da autorização (#19), periodicidade do SEVRRA (#20), quem é IOE em cada perfil (#21).
