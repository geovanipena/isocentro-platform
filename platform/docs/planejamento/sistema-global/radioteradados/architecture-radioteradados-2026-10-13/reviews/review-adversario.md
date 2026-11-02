---
tipo: revisão adversária do spine
alvo: ../ARCHITECTURE-SPINE.md (com ../.memlog.md e ../../prd-radioteradados-2026-10-13/prd.md)
data: 2026-10-13
método: para cada buraco, duas unidades um nível abaixo (módulo/frente) que obedecem a todos os ADs ao pé da letra e mesmo assim saem incompatíveis
código conferido: dados/config_servico.py, dados/datas_relevantes.py, dados/auth.py, banco/tratamento_db.py, banco/capa_dados.py, interface/fichinha.py
---

# Revisão adversária — Radioteradados

**Total: 22 buracos** — 6 críticos, 9 altos, 7 médios.

Gravidade: **CRÍTICO** = número oficial errado, dado de paciente vazando ou relatório imutável incoerente; **ALTO** = duas frentes que não se encaixam e exigem retrabalho; **MÉDIO** = ambiguidade que vira bug pontual.

---

## Críticos

### B-01 — Retrato do mês guarda a lista de origem (nomes de pacientes) na pasta do serviço

- **Unidade A:** `dados/indicadores_registro.gravar_retrato(mes, resultados)` — o AD-6 manda gravar "o `Resultado` de cada indicador"; o AD-3 diz que o `Resultado` contém a lista de origem. A frente grava o `Resultado` inteiro, como manda.
- **Unidade B:** a tela do perfil `gestao` lê o retrato do mês definitivo (AD-6: "passa a ser lido") e só deixa de *montar o widget* da lista (AD-8).
- **Como obedecem:** AD-6 e AD-3 literais; AD-5 só proíbe nome no **log** e no git; AD-8 só restringe a **montagem** da lista.
- **Colisão:** o JSON do serviço, legível por qualquer estação e qualquer login, passa a conter nome e registro de todos os pacientes de cada mês. A estação da gestão tem o arquivo inteiro na mão; um mês de médico A lido por médico B também. Viola FR-18 / §7 (RD-5) sem violar AD nenhum.
- **AD que fecha (apertar AD-6 + AD-5):** "O retrato do mês guarda **só o agregado** do `Resultado` (valor, numerador, denominador, contagem de excluídos, versões, data, degrau, recorte) e as **chaves de curso** (B-03) da lista de origem, nunca nome nem registro. A lista de origem de mês definitivo é remontada na hora a partir das chaves, pelo `banco/`, e passa pelo filtro do AD-8. Nenhum arquivo do estado do serviço contém nome de paciente."

### B-02 — Duas bases de curso: o portão R-07 confere uma consulta, os indicadores usam outra

- **Unidade A:** `banco/indicadores_db` escreve o seu próprio SQL de cursos, frações entregues e frações prescritas (AD-1: "SQL só em `indicadores_db`"), com portão `VERIFICADO_EM` próprio.
- **Unidade B:** `tratamento_db` (Ficha Virtual) continua com a sua lista de cursos, que é o que `LISTA_VERIFICADA_EM` (R-07) atesta.
- **Como obedecem:** AD-1 manda o SQL novo para `indicadores_db`; AD-9 só exige que as duas datas estejam preenchidas.
- **Colisão:** a faixa EXPERIMENTAL sai porque a lista *da Ficha Virtual* foi conferida, mas o número vem de outra consulta, com outra regra de "curso", "frações prescritas" (§3: revisão vigente, reforço soma) e "concluído". O próprio `tratamento_db` documenta erros históricos exatamente nisso (frações de cursos diferentes somadas, `FractionsDelivered` 0). Ficha Virtual e Radioteradados discordam sobre o mesmo curso — o que o AD-2 queria impedir, só que na base, não na pausa.
- **AD que fecha (novo AD-12 "um dono para o curso"):** "A identificação do curso, das frações entregues (datas) e das frações prescritas do curso tem **um** dono. Ou `indicadores_db` reaproveita a consulta de cursos do `tratamento_db` (estendida), ou a nova consulta é a única e a Ficha Virtual passa a usá-la. O AD-9 só considera a chave R-07 válida se ela atesta a mesma consulta que alimenta os indicadores."

### B-03 — Chave do curso indefinida: classificação gravada não casa com o curso calculado

- **Unidade A:** `dados/indicadores_registro.classificar(...)` grava a classificação com a chave que a tela tinha à mão, p.ex. `CourseSer` ou `CourseId` ("C1").
- **Unidade B:** `dominio/indicadores` casa classificações com cursos pela chave que o `tratamento_db` já usa: `(registro, DimCourseID)`.
- **Como obedecem:** nenhum AD define a identidade de curso; AD-5 só fala de formato de arquivo.
- **Colisão:** classificação feita e nunca aplicada — o curso volta como "a classificar", o mês nunca fica definitivo pelo critério (só pelo teto de 3 meses), o abandono sai zerado. Pior: `DimCourseID` é chave substituta do data warehouse e pode mudar numa recarga, órfãando o histórico. Afeta também aprovações (amostra conferida), retratos (B-01) e reaproveitamento da lista.
- **AD que fecha (novo AD-13 "identidade estável"):** "Curso = `(PatientId do ARIA, CourseSer)` (ou outra chave **de origem**, nunca chave substituta do DW), definida num único tipo `ChaveCurso` em `dominio/`, usada por `banco/`, `dados/` e retrato. Máquina = um identificador só (B-06). Pessoa = login do `auth` (B-09)."

### B-04 — Reclassificação depois do retrato: dois caminhos de mutação para o mesmo número

- **Unidade A:** `indicadores_registro` aceita reclassificar a qualquer tempo e guarda a anterior (FR-22, AD-5 "só acrescenta").
- **Unidade B:** `retrato` do mês definitivo é lido, nunca recalculado (AD-6).
- **Como obedecem:** cada uma cumpre o seu AD.
- **Colisão:** o físico reclassifica um abandono de junho (definitivo) como alta antecipada. A lista de origem remontada (se for remontada) mostra N−1, o retrato mostra N: quebra o AD-3 ("lista soma o numerador"). E o teto de 3 meses congela o mês **com encerramentos ainda a classificar** — classificados depois, nunca entram.
- **AD que fecha (apertar AD-6):** "Classificar ou reclassificar curso de mês definitivo **não** altera o retrato: grava a classificação e marca o mês como 'retrato desatualizado — há classificações posteriores'; corrigir o mês é gravar um **novo retrato versionado** (acrescentado, nunca sobrescrito) por ação explícita do físico responsável, como no relatório (AD-7). A lista de origem de mês definitivo é a do retrato (chaves + classificação vigente na data do retrato)."

### B-05 — "Primeira estação grava o retrato": executáveis de versões diferentes, fichas diferentes

- **Unidade A:** estação 1, com o `.exe` antigo (fórmula `interrupcao` v1), abre a aba em 01/01 e grava o retrato de setembro sob lock (AD-6).
- **Unidade B:** estação 2, já atualizada (fórmula v2, aprovada), abre uma hora depois, encontra retrato e o lê.
- **Como obedecem:** AD-6 ("primeira que abrir grava sob lock"); AD-4 ("versão da fórmula no código").
- **Colisão:** o mês fica congelado para sempre com a fórmula velha, ou com definição **não aprovada** — nada impede retrato de `Resultado` "não oficial". Também: a estação 1 pode ter lido `config_servico` (feriados, capacidade) antes da edição do admin.
- **AD que fecha (apertar AD-6):** "Só se grava retrato de indicador cuja ficha vigente está **aprovada** e cuja versão de fórmula da estação é a que a aprovação cita; senão o mês continua provisório para aquele indicador. O retrato grava as versões de ficha, de fórmula, do executável e a impressão digital da configuração usada (B-11). Estação que encontra retrato com versão diferente da aprovada atual mostra o aviso, não o substitui."

### B-06 — Supressão "< 5" num lugar só, mas para quem?

- **Unidade A:** `dominio/indicadores` aplica a supressão dentro do `Resultado` (AD-7: "aplicada em `dominio/indicadores`, num lugar só").
- **Unidade B:** a tela do físico mostra o `Resultado` (AD-3: "só lê `Resultado`, nenhum recalcula") e precisa do valor real para conferir (UJ-1, SM-2).
- **Como obedecem:** AD-7 e AD-3 literais.
- **Colisão:** ou o físico vê "< 5" na própria tela (inútil para conferir), ou a tela recebe o valor cru e a gestão, no recorte por médico/máquina/convênio, vê células de 1–4 casos sem supressão na tela — reidentificação fora do PDF (RD-3), e recorte por médico vira ranking (fora de propósito, §5). Também não há regra de **supressão secundária**: total − demais células revela a célula suprimida.
- **AD que fecha (apertar AD-7):** "`dominio/indicadores.suprimir(resultado, publico)` é a única função de supressão; o `Resultado` sai cru. O PDF chama sempre com `publico='agregado'`; a tela chama com o público do papel (gestão = agregado). A supressão inclui a complementar (nenhuma célula deduzível por subtração). Recorte por médico não é oferecido ao papel `gestao`."

---

## Altos

### B-07 — Máquina identificada por dois identificadores diferentes

- **A:** a tela de administração grava a capacidade por `MachineId` ("TB1") — AD-10 permite.
- **B:** `indicadores_db` devolve as frações por `ctrResourceSer` (inteiro) — AD-10 também permite ("`MachineId`/`ctrResourceSer`").
- **Colisão:** nenhuma máquina casa; todas aparecem "capacidade não configurada", ou alguém escreve um mapeamento por nome — exatamente o que o AD-10 proíbe.
- **Fecha (apertar AD-10):** escolher **um** (`ctrResourceSer`, recomendado por ser estável) e registrar o `MachineId` só como rótulo.

### B-08 — `config_servico.json` só guarda strings de uma lista fechada

- **A:** frente "configuração" acrescenta `capacidade_maquinas`, `feriados`, `fisico_responsavel`, `atividade_consulta`, `atividade_simulacao` às `CHAVES` e usa `definir()`/`valor()` — que só aceitam e devolvem **string** (`str(...).strip()`), com `{valor, por, em}`.
- **B:** `dominio/indicadores` espera `dict[máquina → int]` e `list[date]`.
- **Como obedecem:** AD-10 "chaves novas do `config_servico.json`"; nada diz o formato.
- **Colisão:** a frente A serializa `"TB1=40;TB2=35"` ou JSON dentro de string; a B espera estrutura. Além disso `ler()` devolve `{}` em arquivo ilegível — capacidade e feriados somem em silêncio, e o número muda sem aviso (contra "nunca zero no lugar de sem dado").
- **Fecha (apertar AD-10):** "As chaves do Radioteradados têm schema próprio (tipos, validação) num leitor tipado em `dados/config_servico`, que devolve estrutura e distingue *ausente* de *ilegível*; ilegível vira `None` + motivo no `Resultado`, nunca lista vazia."

### B-09 — Identidade de pessoa: login do app × médico do ARIA × "nome" do físico responsável

- **A:** `config_servico.fisico_responsavel` guarda o nome de exibição ("Geovani Pena"); a aprovação grava "nome" (UJ-3).
- **B:** a tela compara com `auth` usuário (`geovani.pena`) para liberar aprovar/classificar (AD-8). E o filtro "só os meus" do médico precisa casar o login com o médico do curso no ARIA — que pode ser o oncologista primário, quem aprovou a prescrição ou o médico da agenda.
- **Como obedecem:** AD-8 diz "o físico responsável da configuração" e "filtrada pelo próprio médico", sem dizer por qual identificador.
- **Colisão:** ninguém consegue aprovar, ou qualquer homônimo consegue; médico vê lista vazia ou de outro médico.
- **Fecha (novo, junto do AD-13):** "Pessoa no estado do serviço = login do `auth`. O vínculo login → médico do ARIA (`ResourceSer`) é chave do `config_servico` mantida pelo admin; o 'médico do curso' é definido na ficha técnica (campo único do ARIA). Registros gravam login + nome de exibição na data."

### B-10 — A permissão é conferida só na tela; o registro confia

- **A:** a tela esconde o botão "Aprovar" de quem não é o físico responsável (AD-8).
- **B:** `indicadores_registro.aprovar(indicador, versao, por)` grava o que receber (AD-5 só fala de lock e histórico). Uma ferramenta em `tools/` ou um teste grava aprovação por qualquer um.
- **Agravante no código:** `fichinha.modos_do_papel` trata **papel vazio** (janela sem login) como "vê tudo"; aplicada ao AD-8, a lista de origem com nomes é montada sem login.
- **Fecha (apertar AD-8):** "A checagem de papel e de físico responsável mora em `dados/indicadores_registro` (gravações) e em `dominio`/montagem da lista (leitura), recebendo o usuário; papel vazio **não** monta lista de origem nem grava nada no Radioteradados."

### B-11 — Configuração muda o número sem mudar a versão da ficha

- **A:** o admin acrescenta um feriado ou corrige a capacidade de uma máquina (AD-10).
- **B:** o AD-4 garante que "mudar parâmetro cria versão nova e invalida a aprovação".
- **Colisão:** feriados, códigos de atividade e capacidade mudam interrupção, simulação, percurso e ocupação **sem** nova versão nem aprovação; um mês provisório muda de valor entre duas aberturas sem nada no rastro. SM-C1 contornável: tirar uma atividade do código de simulação "melhora" a taxa.
- **Fecha (apertar AD-4/AD-10):** "Todo `Resultado` carrega a impressão digital (hash) das chaves de configuração que usou; o retrato a grava. Mudança em chave que entra numa fórmula fica registrada com autor/data (já existe `por`/`em`) e aparece na ficha técnica como 'configuração alterada depois da aprovação'."

### B-12 — Ficha técnica com dois donos: código ou JSON do serviço

- **A:** o Structural Seed põe "fichas técnicas" em `dominio/indicadores.py` → fichas como constantes no código; mudar parâmetro = novo executável.
- **B:** o AD-4 diz que a ficha é "um registro" e o FR-17 diz que mudar parâmetro cria versão nova → frente de `indicadores_registro` grava fichas editáveis no JSON do serviço (AD-5 lista "aprovações", não fichas).
- **Colisão:** duas fontes de parâmetro; estação com ficha no código e estação lendo ficha do JSON calculam diferente; ninguém sabe quem pode editar parâmetro (admin? físico?).
- **Fecha (apertar AD-4):** decidir explicitamente: *ou* fichas no código (versão sobe com o executável, JSON só guarda aprovações por `(indicador, versão_ficha, versão_fórmula)`), *ou* fichas no estado do serviço com escritor único (físico responsável) e `dominio` recebendo a ficha como argumento.

### B-13 — "Invalidar a aprovação": gravar ou derivar?

- **A:** `indicadores_registro` ao criar versão nova "invalida" a aprovação vigente gravando `revogada=True` na linha antiga.
- **B:** AD-5 "históricos só acrescentam, nunca sobrescrevem" → outra frente deriva a validade comparando versões.
- **Colisão:** A sobrescreve histórico (viola AD-5 por outro caminho) ou B considera aprovada uma versão que A revogou; o selo "oficial" diverge entre tela e PDF.
- **Fecha (apertar AD-4):** "Aprovação nunca é editada. 'Vigente e aprovada' é **derivada**: existe aprovação para exatamente `(indicador, versão_ficha, versão_fórmula)` em uso. Uma função só em `dominio` decide; tela e PDF a usam."

### B-14 — Frequência: o reaproveitamento do `tratamento_db` contradiz o próprio AD-2

- **A:** `dominio/indicadores` usa `_RITMO` e a frequência preenchida por `_marcar_frequencia`, como manda o AD-2.
- **B:** o mesmo AD-2 diz "valor fora do `_RITMO` = não identificada".
- **Colisão no código:** `_marcar_frequencia` **falha em silêncio** e deixa toda linha como diária; `_RITMO.get(freq, (1, 1))` trata desconhecida como diária; e curso com várias prescrições recebe uma frequência só ("a diária ganha"). Além disso `_marcar_frequencia` não é pura — consulta `capa_db` —, e importar `tratamento_db` de `dominio/` importa `capa_db` (AD-1 proíbe). Resultado: cursos de frequência desconhecida entram na taxa de interrupção como diários — o RD-2 que o FR-6 quis evitar.
- **Fecha (apertar AD-2):** "`indicadores_db` lê o valor cru da frequência (todas as prescrições do curso) e o devolve como dado bruto; a tradução e a regra multi-prescrição moram numa função pura extraída (p.ex. `dominio/frequencia.py`) usada por `tratamento_db` e por `indicadores`; falha de leitura vira 'não identificada' no Radioteradados (nunca diária), mantendo o comportamento atual da Ficha Virtual por parâmetro."

### B-15 — Duas funções de dias úteis; só uma ganha feriados

- **A:** pausa (FR-6) via `dias_uteis_entre(..., feriados=...)` (AD-2).
- **B:** prolongamento (FR-11, dias esperados) e ocupação (FR-10, dias úteis do período) usam `_somar_dias_uteis` ou contagem própria, sem feriados — o AD-2 só nomeia `dias_uteis_entre`.
- **Colisão:** num mês com feriado, a pausa não acusa interrupção, mas o prolongamento acusa um dia a mais e a ocupação usa denominador diferente.
- **Fecha (apertar AD-2):** "Todo cálculo de dia útil do Radioteradados (entre datas, somar dias, dias do período) sai de um único módulo puro com o mesmo calendário de feriados."

---

## Médios

### B-16 — Qual limiar vale para "Duas Vezes por Semana" e "Dias Alternados"?

- **A:** a fórmula trata "semanal" como `_RITMO` com dias ≥ 3 → "Duas Vezes por Semana" usa 7 corridos + 3 úteis.
- **B:** a ficha técnica fala em "frequência semanal" (que o vocabulário do ARIA nem tem, PRD §11.5) → só um valor futuro "Semanal" usa o limiar longo; "Duas Vezes por Semana" fica no limiar de 3 úteis e todo curso desses vira interrupção.
- **Fecha (apertar AD-2/AD-4):** "O mapa valor de frequência → classe de limiar é parâmetro da ficha técnica (versionado e aprovado), não do código."

### B-17 — Curso que volta a ter fração depois de classificado

- **A:** `dominio` deixa de listar o curso como encerramento (voltou a tratar).
- **B:** `indicadores_registro` mantém a classificação "abandono" (histórico só acrescenta).
- **Colisão:** curso concluído conta como abandono ou como nenhum dos dois, dependendo de quem aplica a classificação primeiro.
- **Fecha (apertar AD-5/AD-3):** "Classificação só se aplica se a última fração entregue do curso é a mesma registrada na classificação; caso contrário fica 'classificação superada' e sai da conta."

### B-18 — Numeração da versão do relatório disputada entre estações

- **A e B:** duas estações emitem o relatório de setembro ao mesmo tempo; cada uma lê o índice, calcula "v3" e grava `setembro_v3.pdf` (AD-7: "arquivo novo versionado").
- **Colisão:** um sobrescreve o outro (o AD-7 proíbe, mas só o índice está sob lock no AD-5, não o nome do arquivo), ou o índice aponta para o PDF errado.
- **Fecha (apertar AD-7):** "Versão alocada e linha do índice gravada dentro do mesmo lock; o arquivo é criado em modo exclusivo (`x`), com hash do conteúdo no índice. A pasta dos relatórios é chave própria (não a `capa_pasta_relatorios`, que é a dos relatórios exportados do ARIA)."

### B-19 — "Última leitura" do FR-21 sem dono

- **A:** a tela guarda a última leitura em memória/arquivo da estação.
- **B:** outra frente usa o retrato/estado do serviço como reserva.
- **Colisão:** estações mostram reservas diferentes; se for no serviço, volta o problema de nomes (B-01).
- **Fecha (apertar AD-6):** "Reserva = último retrato ou último cálculo provisório **agregado** gravado no estado do serviço, com data e degrau 'reserva'; nunca contém lista de origem."

### B-20 — Retrato e recorte

- **A:** o retrato grava o `Resultado` do serviço inteiro (AD-6 fala "de cada indicador").
- **B:** a tela, com recorte por máquina/convênio num mês definitivo, precisa de valor — e o AD-6 diz "lido, não recalculado".
- **Colisão:** ou recalcula (viola AD-6 e muda número congelado), ou não mostra recorte de mês definitivo; o PDF de um recorte sai de onde?
- **Fecha (apertar AD-6):** "O retrato guarda o resultado por curso (chave + atributos do recorte + contribuição a numerador/denominador), de onde qualquer recorte é agregado sem consultar o banco."

### B-21 — Quem grava o retrato: thread do cálculo ou thread da tela

- **A:** o `QThread` de cálculo chama `indicadores_registro.gravar_retrato` ao terminar.
- **B:** a tela grava ao receber o sinal (AD-1: "a tela orquestra").
- **Colisão:** gravação dupla ou nenhuma; `travar_arquivo` com espera na thread da tela congela a aba (NFR-2) quando outra estação segura o lock.
- **Fecha (apertar AD-6):** "Toda gravação do estado do serviço roda fora da thread da tela, num ponto só (o carregador), com `travar_ou_desistir` e mês continuando provisório se não conseguir."

### B-22 — Formato do `Resultado` e da linha da lista de origem "no mínimo"

- **A:** `dominio` devolve a linha da lista de origem com `registro`, `curso`, `motivo`.
- **B:** a tela precisa do médico do curso para filtrar (AD-8) e o PDF precisa dos atributos de recorte; o "motivo" é texto livre numa e código noutra; `None` com motivo (convenção) não tem tipo.
- **Fecha (apertar AD-3):** "`Resultado`, `LinhaOrigem` e `Ausente(motivo)` são dataclasses congeladas em `dominio/indicadores`, com campos fixos (chave do curso, médico do ARIA, atributos de recorte, motivo como código + texto); serialização para retrato é função única do mesmo módulo."

---

## Resumo dos ADs a criar ou apertar

| AD | Ação | Buracos |
| --- | --- | --- |
| AD-12 (novo) — um dono para o curso | criar | B-02 |
| AD-13 (novo) — identidade estável de curso, máquina e pessoa | criar | B-03, B-07, B-09 |
| AD-2 | apertar: frequência pura e sem padrão diário; calendário único; classe de limiar na ficha | B-14, B-15, B-16 |
| AD-3 | apertar: tipos fixos de `Resultado`/`LinhaOrigem` | B-17, B-22 |
| AD-4 | apertar: dono único da ficha; aprovação derivada; config na impressão digital | B-11, B-12, B-13 |
| AD-5 | apertar: nenhum nome no estado do serviço | B-01, B-17 |
| AD-6 | apertar: retrato agregado por curso, só de definição aprovada, versionado, reserva, gravação fora da tela | B-01, B-04, B-05, B-19, B-20, B-21 |
| AD-7 | apertar: supressão por público e complementar; versão alocada sob lock | B-06, B-18 |
| AD-8 | apertar: checagem no registro; papel vazio não vê nada | B-10 |
| AD-10 | apertar: um identificador de máquina; schema tipado | B-07, B-08 |
