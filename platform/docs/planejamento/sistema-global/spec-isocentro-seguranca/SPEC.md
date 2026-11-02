---
id: SPEC-isocentro-seguranca
companions:
  - ../spec-isocentro-fundacao/SPEC.md
  - ../architecture-isocentro-2026-10-19/ARCHITECTURE-SPINE.md
  - ../prd-isocentro-2026-10-16/prd.md
  - ../ux-isocentro-2026-10-16/EXPERIENCE.md
  - ../ux-isocentro-2026-10-16/DESIGN.md
  - ../decisoes-sem-base.md
  - rastreabilidade.md
sources:
  - ../incidentes/SPEC - Módulo incidentes v0.1.md
  - ../../questionarios/seguranca.md
---

> **Contrato canônico.** Esta SPEC e os arquivos em `companions:` são o contrato completo do módulo Segurança do paciente (`modulos/seguranca`). Ela é construída **sobre a Fundação** (gravação, log, alerta, concentradora, exportador): nada aqui reinventa o núcleo. A espinha (`AD-n`) é obrigatória. Do PRD valem §8, §12.2 e §13 (SM-4), com FR-29 a FR-31 na versão de 26/10/2026 (Ford 2012; Notivisa no lugar do Epimed). Da UX valem UJ-5 e a matriz de perfis. Toda decisão segue a regra do `docs/qms/escopo.md`: referência; com duas ou mais, a mais restritiva; sem base, `decisoes-sem-base.md`.

# ISOCENTRO — Módulo Segurança do paciente

## Why

A NN-6.10 (Res. 277/2021, art. 26) exige, em exposição médica não intencional, investigação imediata, relatório à ANSN em 30 dias e aviso escrito ao paciente e ao médico. A RDC 36/2013 exige notificação mensal pelo NSP no Notivisa até o 15º dia útil do mês seguinte, e em 72 h no óbito. O serviço não tem canal próprio: o formulário do Epimed não conhece etapa, fração, plano nem máquina, não devolve dado ao serviço e não acompanha prazo. O ISOCENTRO passa a ser o sistema próprio do serviço: registra o evento com a taxonomia da radioterapia (Ford 2012, WHO-ICPS), prepara o que o Notivisa e a ANSN pedem, acompanha os prazos, conduz a análise até o fechamento e mostra onde faltam barreiras.

A análise de risco do processo hoje é o SEVRRA: uma matriz de risco por prática (no 6EX, 146 eventos iniciadores em 11 etapas), declarada pelo serviço e assinada em jan/2023, sem validade. O ISOCENTRO já sabe se cada barreira funcionou (CQ da GQ, checagens do Plano, incidentes desta spec). Com isso ele mantém uma matriz de risco em tempo real: o nível de cada evento iniciador acompanha o estado medido das barreiras e os incidentes, e o físico confirma cada mudança.

## Capabilities

Cada capacidade diz de onde vem o dado (**fonte**) e se muda o que sai impresso (**papel**). Nenhuma capacidade desta spec muda o papel do paciente.

- **CAP-1 — Registro de incidente e quase-incidente** (FR-29)
  - **intent:** Qualquer perfil registra um incidente ou quase-incidente com a taxonomia da radioterapia.
  - **success:**
    - Etapa onde foi detectado e etapa onde ocorreu vêm da mesma lista: o mapa de processo do Ford 2012 (8 macroetapas; 91 passos de teleterapia e 88 de braquiterapia, com a marca de barreira de segurança), uma lista para as três clínicas. Quem relata escolhe a macroetapa e, se souber, o passo; a análise refina "onde ocorreu".
    - Desvio de dose pela escala do Ford 2012 (< 5%, 5–10%, 10–25%, 25–100%, > 100%, não se aplica); erro de local e volume pelo TG-100 (3–5 mm; > 5 mm). Dano clínico pela WHO-ICPS, em campo separado.
    - O registro tem também se atingiu o paciente, fatores causais (Ford 2012), descrição e data de identificação.
    - Liga a paciente, curso e plano pela chave canônica (AD-26), sem copiar dado clínico.
    - Um quase-incidente se registra em até 90 s.
    - Registro não se apaga; corrigir é registro novo. Guarda permanente.
  - **fonte · papel:** lançamento do usuário + chave do `variandw` · não muda.

- **CAP-2 — Leitura restrita, notificador oculto e trilha de leitura** (I2, AD-33)
  - **intent:** O texto livre e a dose estimada só chegam a quem precisa, toda leitura deles fica registrada, e quem notificou não é exposto.
  - **success:**
    - Texto livre e dose estimada são lidos só por físico, SPR/gestão e pelo próprio notificador; os demais perfis veem tipo, etapas e status.
    - Toda leitura desses campos gera evento com quem, quando e qual registro, sem o conteúdo (LGPD arts. 11, 37, 46).
    - O log guarda quem notificou, mas tela, triagem, revisão, matriz e relatório não mostram essa pessoa. O log de leitura guarda hash e mudança, sem o texto.
    - O teste prova a recusa no banco, não só na tela.
  - **fonte · papel:** sessão e capacidades do núcleo · não muda.

- **CAP-3 — Art. 26 e relatório à ANSN** (FR-30)
  - **intent:** Um incidente marcado como exposição médica não intencional abre a investigação imediata, o prazo de 30 dias e o relatório no formato do guia da CNEN.
  - **success:**
    - O prazo conta da data de identificação, que é obrigatória.
    - Alerta `alta` desde a identificação até "investigação iniciada" ser registrada (art. 26, "imediatamente").
    - A lista tem: investigação iniciada, dose estimada e distribuição, medidas corretivas, prevenção de reincidência, aviso escrito ao paciente, aviso escrito ao médico solicitante (não o radioterapeuta), registro no livro de ocorrências radiológicas, ciência de todos os IOEs e relatório à ANSN. Cada item registra quem e quando.
    - O relatório sai com os itens a–k do guia CNEN 2020 e as assinaturas de titular, SPR, responsável técnico e físico. O ISOCENTRO guarda o protocolo do requerimento.
    - Sem relatório registrado, o alerta é `atencao` aos 20 dias e `alta` aos 30, gerado pela concentradora.
  - **fonte · papel:** registro do incidente · não muda (o relatório é documento à ANSN, não papel do paciente).

- **CAP-4 — Notificação ao NSP e prazos do Notivisa** (FR-30, FR-31)
  - **intent:** O ISOCENTRO é o canal interno de notificação ao NSP e prepara o evento nas 10 etapas do Notivisa, acompanhando os prazos da RDC 36.
  - **success:**
    - O evento é organizado nas 10 etapas do formulário Notivisa. As etapas 1–4 valem para todo evento; as 5–10, para óbito e never event.
    - Never event é marcado pela lista da Anvisa, guardada como dado.
    - Prazos acompanhados: 15º dia útil do mês seguinte; 72 h do ocorrido no óbito; 60 dias corridos da notificação para concluir as etapas 5–10 em óbito e never event.
    - Dia útil: só sábado, domingo e feriado nacional deixam de contar.
    - O usuário registra a data e o número da notificação no Notivisa. Evento sem número no prazo gera alerta.
  - **fonte · papel:** registro do incidente + calendário de feriados nacionais · não muda.

- **CAP-5 — Ciclo de análise**
  - **intent:** Cada evento é conduzido até o fechamento, com ação definida e dono.
  - **success:** O estado vai de aberto a em análise, ação definida e fechado, e cada transição é um evento com quem e quando. A ação corretiva e a medida de prevenção têm responsável e prazo, e a ação vencida gera alerta. Só físico ou SPR/gestão fecham.
  - **fonte · papel:** registros do módulo · não muda.

- **CAP-6 — Vínculo do incidente com a matriz de risco**
  - **intent:** O físico liga cada incidente ao evento iniciador da matriz e à barreira que falhou ou segurou.
  - **success:** O vínculo é pelo ID do evento iniciador do catálogo (CAP-11) e da barreira. A contagem por evento e por período alimenta a CAP-14. Incidente causado pelo próprio ISOCENTRO também se liga à linha do `riscos.md` (ex.: `RD-2`), que o módulo lê e não escreve.
  - **fonte · papel:** catálogo da matriz + `docs/qms/riscos.md` (somente leitura) + vínculo gravado · não muda.

- **CAP-7 — Triagem semanal e revisão trimestral** (FR-32)
  - **intent:** O físico tria os eventos novos toda semana e revisa o trimestre com ata.
  - **success:** A fila de triagem mostra os eventos não triados, e evento sem triagem há mais de 7 dias gera alerta. A revisão trimestral agrupa por etapa de ocorrência e de detecção e registra a ata com quem e quando.
  - **fonte · papel:** registros do módulo · não muda.

- **CAP-8 — Matriz ocorrência × detecção e indicadores**
  - **intent:** O físico vê onde o erro nasce e onde é pego, e indicadores normalizados do período.
  - **success:**
    - A matriz de calor (etapa de ocorrência × etapa de detecção, no mapa do Ford 2012) sai por período e clínica, nas macroetapas ou nos passos.
    - Indicadores: taxa por 1.000 frações (denominador do `variandw`, com degrau e data), razão quase-incidente/evento e tempo até fechar.
    - No relatório exportado, células com menos de 5 casos são suprimidas.
    - Sem denominador, a taxa nasce vazia.
  - **fonte · papel:** registros do módulo + frações entregues no `variandw` · não muda.

- **CAP-9 — Módulo Segurança do paciente no shell** (FR-9, UJ-5)
  - **intent:** Qualquer perfil registra um evento; o físico e o SPR/gestão conduzem prazos, análise e revisão numa tela do módulo.
  - **success:** O cartão aparece para os 7 perfis. O registro é curto. O físico tem filas de triagem, prazos, análise, revisão e confirmação de mudanças da matriz, e o SPR/gestão acompanha. Alertas do art. 26 e da RDC 36 entram na Zona 2 do físico responsável da clínica, do responsável técnico e do SPR/gestão. A UJ-5 roda de ponta a ponta em homologação.
  - **fonte · papel:** fachada de consulta do módulo · não muda.

- **CAP-10 — Validação do módulo** (FR-40)
  - **intent:** O módulo tem relatório de validação antes do primeiro uso real.
  - **success:** Dois físicos classificam 30 incidentes históricos no mapa e nas escalas da CAP-1, com kappa ≥ 0,7, antes de a matriz ser usada. Os prazos do art. 26 e da RDC 36 são testados em casos de borda: virada de mês, feriado nacional, óbito (72 h), never event (60 dias). A ocultação do notificador, a restrição de leitura e a trilha de leitura são testadas. O RIPD do módulo existe. Com as barreiras declaradas no SEVRRA de jan/2023 do 6EX, a matriz reproduz o perfil daquele relatório (61 RM, 68 RB). Barreira sem dado e nível que desceria sem confirmação são testados. O relatório é assinado pelo físico.
  - **fonte · papel:** testes, casos históricos e SEVRRA do PPR · não muda.

- **CAP-11 — Catálogo da matriz de risco**
  - **intent:** O físico mantém, por prática, os eventos iniciadores do processo com as barreiras e os redutores de cada um, pelos dois métodos ligados.
  - **success:**
    - Por prática (acelerador, HDR): etapas, eventos iniciadores, barreiras, redutores de frequência e de consequência, com o nível pela matriz de risco (RB, RM, RA, RMA) e O, S, D do TG-100 em cada evento.
    - Cada barreira diz de onde vem o seu estado (verificação da GQ, do Plano ou da Segurança) ou que é manual.
    - Cada linha cita a fonte; linha sem fonte não é aceita.
  - **fonte · papel:** método da matriz de risco + TG-100 + carga do físico · não muda.

- **CAP-12 — Estado das barreiras em tempo real**
  - **intent:** O estado de cada barreira vem do que aconteceu, não do que foi declarado.
  - **success:**
    - Cada barreira tem estado medido (funcionando, falhou, sem dado) lido das fachadas da GQ, do Plano e da Segurança.
    - A mudança de estado gera uma proposta de mudança de nível. Ela só vale depois que o físico confirma, e a confirmação é evento com quem e quando.
    - A tela mostra lado a lado o declarado e o medido.
    - Barreira sem dado nunca conta como funcionando.
  - **fonte · papel:** fachadas da GQ, do Plano e da Segurança · não muda.

- **CAP-13 — Perfil de risco**
  - **intent:** O físico vê o risco do serviço agora, por prática e por etapa, e como ele mudou.
  - **success:** A contagem RB/RM/RA/RMA sai por prática e por etapa, atual e de referência, como no SEVRRA, com histórico. A lista dos eventos em RA e RMA mostra as barreiras que faltam. Uma proposta de subida a RA ou RMA gera alerta ao físico responsável da clínica já na proposta.
  - **fonte · papel:** catálogo + estado das barreiras · não muda.

- **CAP-14 — Ocorrência pelos incidentes**
  - **intent:** O O do TG-100 de cada evento iniciador sai dos incidentes reais do serviço.
  - **success:** A contagem de incidentes e quase-incidentes por evento iniciador e período (CAP-6) propõe o O. S e D são do físico. O RPN e o nível da matriz se recalculam depois da confirmação.
  - **fonte · papel:** registros do módulo · não muda.

- **CAP-15 — Seções do PPR da Segurança** (PPR vivo, Documentação CAP-10)
  - **intent:** Os capítulos do PPR sobre o que este módulo conhece moram aqui, com dado e texto.
  - **success:** Planejamento de análise de riscos (12.3 do capítulo da GQ) e o SEVRRA do anexo da GQ (perfil de risco, CAP-13); mecanismos e sistema de controle de acesso (barreiras, CAP-12); procedimentos de emergência. Seção do PPR = dado vivo lido do próprio módulo + texto versionado do módulo, exposto pela fachada (Documentação CAP-10); texto com versão, autor e data; dado sem fonte sai vazio. A primeira versão do texto vem do PPR vigente de cada clínica, citado.
  - **fonte · papel:** matriz de risco e PPR vigente · entra no PPR.

## Constraints

- **Notivisa e ANSN são os canais legais:** o ISOCENTRO prepara, acompanha prazo e guarda número e protocolo; não envia nem automatiza o envio (o Notivisa exige login do usuário cadastrado do NSP; o requerimento à ANSN, carta assinada pelo titular).
- **Relatório exportado sem identificação** do paciente e sem o notificador (AD-33, NFR-2).
- **Log íntegro com notificador oculto:** a pessoa fica no log, nunca em tela ou relatório.
- **Nada se apaga** em registro de incidente (AD-5); guarda permanente (CFM 1821, art. 7º); backup do AD-24 e chave de cifra sem prazo.
- **`riscos.md` é do físico e é o risco do software:** o módulo lê e liga, não escreve; a matriz de risco do processo clínico é dado do módulo, separada dele.
- **Risco medido nunca melhora sozinho:** barreira sem dado conta como não funcionando, e nenhum nível muda sem a confirmação do físico.
- **SEVRRA em paralelo:** até a CNEN aceitar a matriz própria como a análise de risco do PPR, o SEVRRA continua sendo feito e segue no painel da Documentação.
- **Campo sem fonte nasce vazio:** dose estimada, denominador e data nunca presumidos (NFR-4).
- **Visibilidade por clínica** pela RLS da sessão; o físico responsável vê as três (AD-12).
- **Decisão sem base é provisória e anunciada:** os itens em `decisoes-sem-base.md` seguem a opção mais conservadora até a discussão no serviço.
- **Classe A** (`classificacao-62304.md`, físico, 26/10/2026).

## Non-goals

- Epimed: nenhum registro, texto pronto, mapeamento de campos ou integração.
- Envio automático ao Notivisa ou à ANSN.
- Botão "Notificar incidente" em qualquer tela de paciente dos outros módulos (v0.1 §3).
- Sugestão automática de notificação vinda de outros módulos (Virtual, Qualidade, plan check) (v0.1 §6.3).
- Atualização automática de O e D no `riscos.md`.
- Substituir o relatório SEVRRA entregue à CNEN, enquanto ela não aceitar a matriz própria.
- Mudança de nível da matriz sem a confirmação do físico.
- Canal de alerta externo (e-mail, mensageiro).

## Success signal

- Em homologação, um dosimetrista registra um quase-incidente em menos de 90 s. Ele aparece na triagem do físico sem o nome de quem notificou, e um técnico da mesma clínica não lê o texto livre; a leitura do físico fica na trilha.
- Um evento marcado como exposição não intencional gera `alta` até a investigação ser iniciada, `atencao` aos 20 dias e `alta` aos 30 com o app fechado, e sai da Zona 2 quando o protocolo à ANSN é registrado.
- Um evento com óbito gera alerta às 72 h sem número do Notivisa, e outro aos 60 dias sem as etapas 5–10.
- Com o CQ diário de um acelerador vencido, a barreira correspondente passa a "falhou", a matriz propõe subir os eventos que dependem dela e o físico recebe o alerta; o nível só muda quando ele confirma.
- Com as barreiras declaradas em jan/2023, o perfil do 6EX sai igual ao do SEVRRA (61 RM, 68 RB).
- A matriz do trimestre e a taxa por 1.000 frações saem da revisão com ata. O kappa ≥ 0,7 está registrado no relatório de validação, e a SM-4 é medida desde o 1º mês.

## Assumptions

Aplicadas pela regra de decisão; a conferir pelo físico.

- **Art. 26:** `alta` imediata até a investigação iniciada; `atencao` aos 20 dias sem relatório (o 20 é sem base: `decisoes-sem-base.md`).
- **Quem recebe:** físico responsável da clínica, responsável técnico e SPR/gestão (NN-6.10 art. 26; guia CNEN).
- **Dia útil:** feriado estadual e municipal conta como útil, o que adianta o prazo (sem base: `decisoes-sem-base.md`).
- **Triagem:** evento sem triagem há mais de 7 dias gera alerta (sem base: `decisoes-sem-base.md`).
- **Kappa ≥ 0,7:** sem base no acervo (`decisoes-sem-base.md`).
- **Classe:** A (`classificacao-62304.md`, 26/10/2026).
- **Vínculo do incidente:** ao evento iniciador da matriz; ao `riscos.md` só quando a falha é do próprio ISOCENTRO.
- **SEVRRA em paralelo** até a CNEN aceitar a matriz (`decisoes-sem-base.md`).

## Open Questions

- **Método da matriz:** o documento do método (Foro Iberoamericano / IAEA TECDOC-1685) e o catálogo de eventos iniciadores e barreiras do SEVRRA por prática não estão no acervo; o uso do catálogo pode ter licença.
- **Etapas:** as 11 etapas do SEVRRA não são as 8 macroetapas do Ford 2012 da CAP-1; casar as duas listas ou manter uma tabela de correspondência.
- **Barreiras mensuráveis:** quais barreiras do catálogo têm dado no ISOCENTRO e quais ficam manuais.
- **Práticas:** acelerador e HDR entram; e a ortovoltagem (Dermopan) da CEL?
- **CNEN:** a matriz própria pode substituir o SEVRRA como análise de risco do PPR (guia CNEN, item 14.3)?

- **NSP (G04):** quem é o usuário Notivisa do serviço (gestor ou técnico) e como entra no ISOCENTRO (perfil novo ou atributo); o NSP do grupo inclui a radioterapia?
- **Campos do Notivisa:** o manual de 2025 das alterações do formulário (NSP) não está no acervo; sem ele, as listas de cada uma das 10 etapas ficam abertas.
- **Kappa:** os 30 incidentes históricos existem, e onde estão? A ficha G15 registra que o serviço não tem registro de quase-incidentes.
- **riscos.md:** linhas do módulo (S, O, D pelo físico): prazo de 30 dias contado de data errada, notificador exposto, dado sensível lido por perfil sem acesso, prazo do Notivisa perdido, barreira contada como funcionando sem dado.
- **Em discussão no serviço:** Ford 2012 × taxonomia britânica (#15), onde entra o "1º dia" (#16), registro de incidente como prontuário (#17).
