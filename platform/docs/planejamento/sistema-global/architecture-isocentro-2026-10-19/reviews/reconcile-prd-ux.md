---
type: reconcile
target: ../ARCHITECTURE-SPINE.md
inputs:
  - ../../prd-isocentro-2026-10-16/prd.md
  - ../../ux-isocentro-2026-10-16/EXPERIENCE.md
date: '2026-10-19'
---

# Reconciliação PRD + UX × espinha de arquitetura

Espinha lida em modo somente leitura. Só entram requisitos com implicação **arquitetural** (dado, fronteira, processo, topologia, integridade, retenção, desempenho); regra de tela fica de fora.

Legenda: **Cobre** = um AD resolve; **Parcial** = um AD toca, mas a regra que o FR exige não está escrita; **Defere** = consta em Deferred; **Não cobre** = nenhum AD nem Deferred; **Módulo** = cabe no detalhe do módulo, sem decisão transversal pendente.

## Veredito

A espinha cobre bem a fundação (direção de dependência, dono do dado, transação dado + log, RLS, só leitura no ARIA, topologia, backup), mas a estrutura de ADs deixou cair várias regras "silenciosas" do motor e da conformidade: verificação de integridade do log e ancoragem da corrente, origem `semeado`, promoção da sombra, invalidação da assinatura por versão do RT Plan, desempenho (NFR-5), restrição de campo sensível (FR-29) e retenção do relatório de validação (FR-40). Não está pronta para épicos do núcleo sem um passe de Update.

## Lacunas mais graves

| # | Requisito | Situação | Por que é grave | Sugestão |
| --- | --- | --- | --- | --- |
| L1 | FR-3 verificação de integridade do log | Não cobre | O AD-6 calcula o hash, mas não há verificador que percorra a corrente e aponte registro e posição (consequência testável do FR-3, RDC 657 art. 5º § 4º). A corrente vive no mesmo servidor e o `isocentro_dono` pode desligar o gatilho e reescrever tudo de forma consistente: nada ancora o hash fora do banco. | AD novo: verificador da corrente (no núcleo, rodado pela concentradora e após restauração, FR-28) + âncora periódica do hash-cabeça fora do servidor (ex.: junto do dump mensal do AD-24, ou registro em papel/arquivo assinado). |
| L2 | FR-3/AD-5 dado das tabelas dos módulos | Não cobre | O AD-6 nega UPDATE/DELETE só no log; as tabelas dos donos continuam com UPDATE (necessário para "marcado substituído", AD-5). Se a linha de log não leva o hash do conteúdo gravado, alterar o dado no módulo não é detectável. | Escrever que a linha de log carrega o hash do registro gravado (não só "o quê"), e que UPDATE em tabela de dono só pode tocar a marca de substituído (gatilho ou permissão por coluna). |
| L3 | FR-6 erro semeado | Não cobre | O AD-14 não tem o campo `origem` (`producao`/`semeado`); sem ele, execuções semeadas contaminam indicadores, cobertura e alertas. Também não diz onde vivem os casos semeados nem a anonimização antes de sair da pasta do paciente (NFR-2). | Acrescentar `origem` ao contrato do AD-14, regra de que fachadas e alertas filtram `semeado`, e local dos casos (fora do repositório, dentro da rede). |
| L4 | FR-8/FR-20 assinatura presa à versão do RT Plan | Parcial (AD-4, AD-11, AD-13) | "Versão da origem" está na linha de log, mas falta a regra de **invalidação**: quem detecta RT Plan novo (`SOPInstanceUID` ou status), qual gatilho põe o Duplo Check de volta em pendente e quem é o dono do estado "pendente". P9 está aberta no PRD e não aparece em Deferred. | AD (ou cláusula do AD-14) para entidade Assinatura: objeto + versão imutáveis; gatilho `estado` compara versão vigente; P9 em Deferred. |
| L5 | FR-11/FR-41 quem executa gatilho de evento e prazo com o app fechado | Parcial (AD-9) | O AD-9 dá à concentradora o agendado e os prazos, mas não diz quem detecta o `Planning Approved` e roda a segunda checagem "antes da fila". Na topologia, só as estações fazem C-MOVE; a concentradora não busca RT Plan. Com N estações abertas, nada impede execução duplicada. A vigilância da concentradora (Q5) está adiada, mas é ela que sustenta FR-41 e o risco "checagem não roda e ninguém percebe" (§12.2). | Fixar: todo gatilho `evento`/`prazo`/`calendario` roda só na concentradora (estação só dispara por ação do usuário); acrescentar CON → DB Daemon (C-MOVE); execução idempotente por (verificação, objeto, versão); sinal de "concentradora parada desde hh:mm" no shell como regra, não Deferred. |
| L6 | NFR-5 desempenho | Não cobre | 30 s por plano (inclui C-MOVE + cálculo) e painéis em 3 s. A Zona 1/Zona 2 agrega todos os módulos por fachadas; sem decisão (tabela de alertas abertos indexada no núcleo, sem varrer módulos) o orçamento não tem dono. Não consta nos `binds`. | AD de desempenho: painel lê só a tabela de alertas do núcleo; medição dos dois números na suíte ou no roteiro de validação. |
| L7 | FR-29 texto livre e dose estimada restritos; log com hash; exportação sem identificação | Não cobre | O AD-12 recorta por clínica e o AD-11 por ação; nada recorta **campo** por perfil. O FR-29 diz que o log guarda o hash e a mudança, mas o AD-4 põe "o quê" na linha de log: texto sensível pode ir em claro para o log (lido por todos que leem o log). A exportação sem identificação (FR-29, FR-26 MapCHECK, EXPERIENCE "exportação sem identificação") não tem caminho único. | Regra de campo sensível (coluna restrita, ou tabela à parte com RLS por capacidade); log de campo sensível só com hash; um só exportador no núcleo que remove identificação. |
| L8 | FR-40 relatório de validação; FR-3 retenção 10 anos após o descarte | Parcial (AD-24) | O AD-24 guarda um dump por mês por 10 anos, contados do dump, não "10 anos após o descarte do software". O relatório de validação (e o de comissionamento, sensibilidade, SOUP) não tem lugar de guarda nem retenção. A execução não grava a versão do software que a produziu (necessário para o FR-40 e para revalidar após upgrade do ARIA/Eclipse). | Retenção como "10 anos após o descarte"; guarda dos relatórios de validação (banco ou área do share com backup); `versao_software` em toda execução e linha de log. |

## Tabela completa

### Núcleo e plataforma

| Req. | Implicação arquitetural | Situação | AD / observação |
| --- | --- | --- | --- |
| FR-1 | Proveniência obrigatória que **resolve** para ficha da base (`fichas/atividades/<ID>.md`); tolerância com origem | Parcial | AD-14 exige proveniência; não diz como o banco referencia a base de conhecimento (arquivos fora do banco, que mudam), nem como o esquema "recusa" fonte que não resolve, nem versão da base. Ver L9 abaixo. |
| FR-2 | Avaliador puro; Python e ESAPI no mesmo formato; exceção → `erro` | Cobre | AD-14, AD-15 (JSON com esquema versionado). |
| FR-3 | Log append-only encadeado; mudança de regra e promoção no log | Parcial | AD-4, AD-5, AD-6. Faltam verificador e âncora (L1), hash do dado (L2), retenção pós-descarte (L8). |
| FR-4 | Sombra invisível; promoção com quem, quando e resumo do período; mínimo de 30 dias encurtável com justificativa | Parcial | AD-14 define estados e "sombra sem alerta". Não diz que fachadas, filas, contadores, sinal de máquina e cobertura (FR-37) excluem sombra; promoção como comando do núcleo com resumo calculado e capacidade (AD-11 lista `cadastrar_verificacao`, não `promover`/`podar`). G4 não está em Deferred. |
| FR-5 | Nenhum bloqueio; justificativa em `alta` | Cobre | AD-14 ("nenhuma bloqueia"). Justificativa é dado do alerta (ver FR-41). |
| FR-6 | Origem `semeado` fora dos indicadores; relatório de sensibilidade; anonimização | Não cobre | L3. |
| FR-41 | Alerta com estados aberto/visto/resolvido no log; destinatário por perfil e clínica; prazos com app fechado | Parcial | AD-3 (motor → alerta → log), AD-9 (concentradora), AD-12 (clínica). Falta entidade Alerta no núcleo (dono, estados, deduplicação), relógio de referência e quem executa gatilhos (L5). Q5 adiada. |
| FR-7 | Perfis definem visão e assinatura | Defere | Q1 e tabela perfil → capacidades em Deferred; AD-11 dá o mecanismo. |
| FR-8 | Assinatura com usuário, perfil, hora, objeto e versão; não vale para outra versão | Parcial | L4. "Usuário logado na sessão atual" depende da sessão, hoje por estação (Q7); sessão única (UX) com banco central não tem decisão. |
| FR-9 | Telas no shell; degrau anunciado | Cobre | AD-18. |

### Plano (MVP 1 e 2)

| Req. | Implicação arquitetural | Situação | AD / observação |
| --- | --- | --- | --- |
| FR-10 | Tabelas de feixe versionadas, com validação guardada; mapa explícito de nomes DICOM | Módulo | AD-3 (dono). Sem decisão transversal. |
| FR-11 | Disparo por `Planning Approved` antes da fila; RT Plan conferido por UID | Parcial | AD-3 gatilho `evento`, AD-16 C-MOVE. Executor e C-MOVE da concentradora em L5. |
| FR-12 | Troca de ponto = nova execução, ambas no log | Cobre | AD-5. |
| FR-13 | `indeterminado` com motivo | Cobre | AD-14. |
| FR-14 | Comissionamento entra no relatório de validação | Parcial | L8 (guarda do relatório). |
| FR-15 | Prazo por frações (dado do Tratamento) | Cobre | AD-3 (fachada do Tratamento + gatilho `prazo`). Estado `LISTA_VERIFICADA_EM` é do módulo. |
| FR-16 | Datas com fonte (tabela e campo) e degrau; divergência ISOCENTRO × `variandw` alerta | Parcial | AD-14 (proveniência, degrau); P6 em Deferred. Fonte por campo (tabela/coluna do `variandw`) não está no contrato de entrada. |
| FR-17 | Fila por prazo | Cobre | AD-3, AD-14. |
| FR-18 | Marcação à mão com quem e quando | Cobre | AD-4, AD-5. |
| FR-19 | Item automático com valor, fonte e referência; vazio quando falta | Cobre | AD-14 + convenção "campo sem fonte". |
| FR-20 | Separação entre físicos; mapa ARIA ↔ ISOCENTRO | Parcial | AD-13 cobre o mapa; invalidação por versão em L4. |
| FR-21 | Tabela de equivalência energia/técnica cadastrada | Módulo | AD-3. |
| FR-42 | Lista conferida com quem e quando | Cobre | AD-4. |

### Garantia da Qualidade (MVP 3)

| Req. | Implicação arquitetural | Situação | AD / observação |
| --- | --- | --- | --- |
| FR-22 | Programa carregado de `qualidade.json` gerado da base; versão do programa em uso | Parcial | Ver L9: ingestão de dado de referência vindo da base, com versão. |
| FR-23 | Resultado calculado pela tolerância; alerta no mesmo dia | Cobre | AD-14, AD-3. |
| FR-24 | Diário até o 1º tratamento do dia (agenda do `variandw`) | Cobre | Gatilho `calendario` (AD-3) na concentradora (AD-9). |
| FR-25 | Carta de controle | Módulo | — |
| FR-26 | Arquivo importado guardado com a execução; pseudonimização | Não cobre | Onde ficam anexos binários (banco ou share), backup e RLS deles não está decidido; pseudonimização entra em L7. |
| FR-27 | Troca de fonte como evento | Cobre | AD-3 gatilho `evento`. |
| FR-28 | Cópia independente; restauração prova log íntegro; guarda por toda a vida do equipamento | Parcial | AD-21, AD-24. "Log válido depois da restauração" depende do verificador (L1); vida útil do equipamento pode passar de 10 anos. |

### Segurança do paciente (MVP 4)

| Req. | Implicação arquitetural | Situação | AD / observação |
| --- | --- | --- | --- |
| FR-29 | Campo sensível por perfil; log com hash; exportação sem identificação | Não cobre | L7. I2 aberta no PRD, ausente de Deferred. |
| FR-30 | Prazo de 30 dias; RDC 36 em dias úteis e 72 h | Parcial | Gatilho `prazo` (AD-3). Calendário de dias úteis/feriados e relógio de referência (servidor) não decididos. |
| FR-31 | Nada vai ao Epimed | Cobre | AD-7 + fronteira de só leitura. |
| FR-32 | Revisão periódica com ata | Módulo | — |

### Documentação e conformidade (MVP 5)

| Req. | Implicação arquitetural | Situação | AD / observação |
| --- | --- | --- | --- |
| FR-33 | Vencimento por calendário e por evento | Cobre | AD-3 gatilhos. |
| FR-34 | Painel por clínica | Cobre | AD-12, AD-18; desempenho em L6. |
| FR-35 | Migração do `ppr-streamlit`; extração de ASO local | Parcial | AD-7 cobre "não vai a terceiros"; a migração (importador único com relatório) é do módulo. |
| FR-36 | Aferição com decaimento | Módulo | — |

### Software e sistemas

| Req. | Implicação arquitetural | Situação | AD / observação |
| --- | --- | --- | --- |
| FR-37 | Cobertura calculada do cadastro, sem sombra | Parcial | Depende da exclusão de sombra (FR-4) e do vínculo verificação ↔ atividade da base (L9). |
| FR-38 | Inventário SOUP gerado das dependências | Parcial | AD-10 diz que PostgreSQL e psycopg entram; convenção "dependências fixadas exatas". Falta: gerado de onde (lock do build, AD-20), e inclusão do lado C# (ESAPI) e do servidor (PostgreSQL, Windows). |
| FR-39 | Execução registra identificador e checksum do RT Plan, data da carga do `variandw` | Parcial | AD-4/AD-14 registram "versão" e "data". Checksum do arquivo DICOM, hash do JSON ESAPI e data da **carga** do `variandw` (ETL), não a data da consulta, não estão escritos. |
| FR-40 | Relatório de validação por módulo, guardado 10 anos após o descarte; reexecução da bateria semeada após upgrade | Não cobre | L8. |

### Não funcionais

| Req. | Implicação arquitetural | Situação | AD / observação |
| --- | --- | --- | --- |
| NFR-1 | Só leitura no ARIA/Eclipse; entrega confere que script ESAPI não declara escrita | Parcial | AD-15, AD-16 cobrem a leitura; a conferência na entrega (script ESAPI sem escrita, separado das DLLs graváveis) não está em AD-20 nem AD-22. |
| NFR-2 | Nada sai da rede; teste `varrer_identidade` e de log | Cobre | AD-7 + convenção de logging. Lacunas pontuais em FR-6, FR-26, FR-29 (L3, L7). |
| NFR-3 | Degrau anunciado | Cobre | AD-16, AD-18, AD-14 (degrau na entrada). |
| NFR-4 | Campo sem fonte vazio; suposições só valem confirmadas | Parcial | Convenção cobre o vazio. Parâmetros `[SUPOSIÇÃO]` (30 dias de sombra, 60 de aviso, 20 de incidente) precisam de estado "não confirmado" na configuração; nada diz isso. |
| NFR-5 | 30 s por plano, 3 s por painel | Não cobre | L6. |
| NFR-6 | Clínica vê o que é seu; físico responsável vê três | Cobre | AD-12. |
| NFR-7 | `variandw` fora: último dado com degrau; prazo nunca `conforme` | Cobre | AD-16, AD-17, AD-14. |
| NFR-8 | FR clínico ligado a risco e verificação | Fora | Processo do QMS, sem implicação de estrutura. |
| NFR-9 | Suíte verde e rápida | Cobre | AD-22. |
| NFR-10 | Banco em servidor da clínica, fora do ARIA; escopo atualizado **antes** da arquitetura | Cobre / atrito | AD-9, AD-10. O PRD pede o `escopo.md` atualizado antes da arquitetura; a espinha adia (Q8). Registrar que a ordem foi invertida de propósito. |

### Regras da UX com implicação arquitetural

| Regra (EXPERIENCE.md) | Situação | Observação |
| --- | --- | --- |
| Banco central inacessível: arranque aquece; nada "normal" nem zero | Cobre | AD-23. |
| Prazo vencido com app fechado entra como `alta` | Parcial | AD-9; depende de L5 (concentradora viva). |
| Sessão única: abrir em outra estação fecha esta | Não cobre | Hoje por estação; com banco central, onde vive a sessão não está decidido (perto de Q7). |
| Última clínica lembrada **por usuário**; noite/dia por estação | Parcial | A precedência de configuração (sessão → estação → serviço → padrão) não tem nível "usuário". |
| Zona 1 com pior severidade da máquina, de qualquer módulo | Parcial | Agregação pelo núcleo (tabela de alertas) não escrita; ver L6. |
| Sombra invisível em fila, contador e sinal | Parcial | FR-4 acima. |
| Visto grava quem e quando | Parcial | Entidade Alerta não definida (FR-41). |
| Consulta ao log, relatório de sensibilidade, relatório para auditor sem tela | Não cobre | Leitura/exportação do log para inspeção (RDC 657) não tem caminho; liga a L1 e L8. |
| Registros em papel lançados depois (AD-23) | Atrito | Lançamento tardio exige separar hora do fato e hora do registro em todo dado; não está na convenção da linha de log. |

## Outras lacunas (fora das 8)

- **L9 — Dado de referência vindo da base de conhecimento.** FR-1 (proveniência resolve para ficha), FR-22 (`qualidade.json` com versão), FR-19/FR-42 (`lista-verificacao-carepath.csv`), FR-37 (`atividades.csv`): o sistema depende de arquivos versionados fora do banco. Falta decidir como entram (importador único, versão registrada, quem é dono) e o que acontece quando a ficha citada muda ou some.
- **Relógio de referência.** "Quando" de assinatura, prazo e log deve vir do servidor (`now()` do PostgreSQL), não da estação; não está escrito.
- **Versão da verificação na execução.** "Mudança de regra entra no log" (FR-3) e AD-5 implicam que a execução aponta a versão da verificação vigente; o "versão" do AD-14 é ambíguo (dado? regra? software?).
- **Capacidades de promover/podar** (FR-7, FR-4) não estão na lista de exemplo do AD-11.
- **Questões do PRD ausentes do Deferred:** G4 (sombra), P9 (invalidação da assinatura), I2 (leitura do texto livre), G7 (ambição regulatória, que muda retenção e validação). P3, P6 e G1 já estão.
- **`binds` da espinha** não lista FR-6, FR-29, FR-38, FR-39, FR-40 nem NFR-5, embora tenham regra transversal; FR-8 e FR-41 estão listados, mas a regra escrita não cobre as consequências testáveis deles.
