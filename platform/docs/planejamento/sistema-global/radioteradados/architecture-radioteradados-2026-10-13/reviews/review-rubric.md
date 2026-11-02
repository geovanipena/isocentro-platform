# Revisão por rubrica: ARCHITECTURE-SPINE.md (Radioteradados)

Data: 13/10/2026. Lente: o spine fixa todos os pontos em que unidades construídas separadamente podem divergir, ratifica o código existente e cobre o PRD e o envelope operacional?

**Veredito:** a forma está boa: camadas, `Resultado` único, ficha versionada, estado do serviço com lock e relatório imutável são os eixos certos. Mas três pontos de divergência real ficaram sem dono ou com o dono errado: a frequência prescrita, a conexão compartilhada com a thread de cálculo e o retrato do mês diante de recortes e da lista de origem. Há também vários "Prevents" que a Rule correspondente não impede de fato. Não está pronto para a fatia 1 sem corrigir os críticos e os altos.

**Observação de entrada:** o `.memlog.md` citado como registro das decisões **não existe** na pasta (`ls` mostra só `ARCHITECTURE-SPINE.md` e `reviews/`). As `[ASSUMPTION]` do spine ficam, portanto, sem rastro de quem as decidiu (ver B1).

Contagem: **3 críticos, 8 altos, 11 médios, 6 baixos.**

---

## Críticos

### C1. AD-2 aponta como dona da frequência uma função impura, com limite silencioso e regra de colapso não ratificada

> "a frequência prescrita vem de `tratamento_db._marcar_frequencia` e o ritmo de `_RITMO`" (AD-2)
> "`dominio/indicadores` não importa Qt, `banco/` de consulta nem `dados/`. A única exceção é ler as funções puras de frequência e de dias úteis do `tratamento_db`" (Design Paradigm)

Código (`banco/tratamento_db.py:1599`): `_marcar_frequencia(linhas)` **faz SQL** (`capa_db._consultar`), altera as linhas no lugar e, quando há mais de `_MAX_NA_CONTAGEM = 400` registros, **retorna sem marcar nada**, em silêncio. O mesmo acontece em `FalhaDeLeitura`: o próprio comentário diz que, nesse caso, "toda linha conta como diária". Um mês de serviço passa fácil de 400 registros, e 12 meses (FR-2) passam com certeza. Resultado: ou todos os cursos viram "frequência não identificada" e a taxa de interrupção some, ou o implementador copia o comportamento da Ficha Virtual ("conta como diária") e infere justamente o que o FR-6 proíbe. Além disso:
- a regra de colapso de várias prescrições ("a DIÁRIA ganha; sem diária, a menor em ordem alfabética") está só no código e o spine não a ratifica; um implementador do `indicadores_db` que escreva a própria consulta pode decidir de outro jeito;
- a chave do `_RITMO` é o texto **já traduzido** por `capa_dados.traduzir_frequencia`, e o spine não diz isso;
- importar `tratamento_db` a partir do `dominio/` traz junto `capa_db`, `capa_dados` e `dados.ambiente`, o que fere a própria regra do AD-1.

**Correção:** reescrever o AD-2 separando a consulta da regra. (a) A SQL da frequência por curso (a mesma de `_SQL_FREQUENCIA_DOS_CURSOS`, sem o teto de 400, ou paginada) mora em `indicadores_db`. (b) As funções puras (`traduzir_frequencia` → `frequencia_do_curso(valores)` com a regra "diária ganha, senão a menor em ordem alfabética" → `ritmo(frequencia) -> (dias, por) | None`, `dias_uteis_entre(…, feriados=())`) passam para um módulo de `dominio/` (por exemplo, `dominio/ritmo.py`), e o `tratamento_db` passa a importá-las de lá, preservando o fallback (1, 1) **só** no `prever_fim` da Ficha Virtual. (c) Regra explícita: falha de leitura da frequência vira `None` + motivo no `Resultado`, nunca `""` nem "diária".

### C2. AD-6 + AD-11: cálculo em `QThread` sobre a conexão única do `capa_db`, com 6 s de limite

> "Mês provisório é recalculado sob demanda, em `QThread`" (AD-6)
> "toda consulta usa a conexão do `capa_db`" (AD-11)

Código (`banco/capa_db.py`): há **uma** conexão global (`_conexao`). A `_trava` protege só a abertura da conexão, não o `execute`. O tempo-limite de consulta é `TEMPO_LIMITE_S = 6`, pensado para a thread da interface. O próprio `tratamento_db` avisa que a `FactTreatmentHistory` tem cerca de 2,7 milhões de linhas e que o tempo das agregações nunca foi medido. Com o worker do Radioteradados e a Ficha Virtual (que consulta na thread da tela) usando o mesmo objeto pyodbc ao mesmo tempo, aparecem dois problemas. Primeiro, conexões pyodbc não devem ser compartilhadas entre threads. Segundo, o `_consultar` do worker que estourar 6 s chama `_soltar_conexao()` e derruba a consulta em andamento da outra thread. A tela e o cálculo, construídos separadamente, vão se atrapalhar. Além disso, a NFR-1 (não degradar o ARIA no horário de tratamento) não tem nenhuma Rule.

**Correção:** nova Rule no AD-11. O `indicadores_db` obtém uma conexão **própria por thread de cálculo**, por uma fábrica do `capa_db` que respeite a mesma precedência (banco local → configurado), com tempo-limite de consulta próprio e declarado (por exemplo, 60 s), e nunca toca `capa_db._conexao` nem `_soltar_conexao`. Fixar também a regra da NFR-1: consulta agregada por mês (nada de laço por paciente), uma consulta por indicador e mês, e cálculo automático só fora do horário de tratamento, configurável. Fora dessa janela, só por pedido explícito.

### C3. Retrato do mês definitivo não diz o que guarda para recortes e para a lista de origem

> "Ao virar definitivo, o `Resultado` de cada indicador é gravado como retrato (valores, versões das fichas e data da carga) e passa a ser lido, não recalculado." (AD-6)
> "Tela e PDF só leem `Resultado`; nenhum dos dois recalcula." (AD-3)

O FR-3 pede qualquer combinação de máquina × médico × sítio × convênio, e o FR-18 pede a lista de origem de qualquer número, inclusive de mês definitivo. O retrato descrito guarda só valores, e o spine não diz se é por recorte. Quem implementar a tela vai recalcular a lista (ou um recorte) de um mês definitivo com o dado e a versão de hoje, e a lista deixa de somar o numerador congelado: é exatamente o que o AD-3 diz impedir (FR-18: "A lista soma exatamente o numerador mostrado"). A alternativa ingênua, gravar a lista com nomes no JSON da pasta compartilhada, choca com AD-5/FR-22 e com o RD-5.

**Correção:** decidir no AD-6 o conteúdo do retrato. Sugestão: por indicador e mês, gravar os **identificadores** dos cursos do numerador, do denominador e dos excluídos (`DimCourseID`, sem nome nem registro), com os atributos de recorte congelados (máquina, médico, sítio, convênio) e o motivo de cada um. Recorte de mês definitivo vira filtro sobre esse conjunto, e a lista resolve nome e registro na hora de exibir, para quem pode ver. Se for decidido não congelar recortes, escrever isso: "recorte ≠ serviço inteiro em mês definitivo é recalculado e marcado como tal".

---

## Altos

### A1. A precedência "variável → serviço → padrão" deixa cada estação gravar e ler o estado do serviço num lugar diferente

> "JSON ao lado do índice central, no padrão do `datas_relevantes` (precedência variável → serviço → padrão…)" (AD-5)
> "chaves novas do `config_servico.json`" (AD-10)

No código, `datas_relevantes.caminho()` aceita `ISOCENTRO_DATAS_RELEVANTES`, e `config_servico.caminho()` aceita `ISOCENTRO_CONFIG`. Uma estação com a variável definida grava aprovações, classificações e retratos em outro arquivo e lê outros feriados, outra capacidade e **outro físico responsável**. É justamente o "classificação ou aprovação parando na estação errada" do Prevents do AD-5, e abre uma brecha de autorização no AD-8.

**Correção:** os arquivos do Radioteradados seguem uma raiz só, a pasta de `indice.REGISTRO_PATH`/`config_servico.caminho()`, sem variável própria por arquivo. A variável de ambiente fica só para teste e demonstração, e a aba mostra o caminho em uso quando ele não for o padrão. Registrar no AD-10 que o físico responsável nunca vem de variável de ambiente.

### A2. "Fração entregue" e "frações prescritas do curso" sem dono

> "cada indicador é uma função de `dominio/indicadores`…" (AD-3), sem regra sobre como contar frações.

No código, `tratamento_db.fracoes_entregues` (planos diferentes no mesmo dia contam uma fração; o mesmo plano duas vezes no dia conta duas), `intervalos_das_sessoes` (pausas sobre o **conjunto de datas**), `planos_simultaneos` e `cobre` (o caso "9 / 4" do `FractionsPlanned`) são quatro correções já pagas, e o spine não as amarra. "Curso concluído" (FR-4, FR-11), "encerramento a classificar" (FR-5) e as pausas (FR-6) dependem disso, e a pergunta 6 do PRD continua aberta.

**Correção:** ampliar o AD-2 para "um dono para frequência, dias úteis **e contagem de frações**". O Radioteradados conta frações e pausas com a mesma semântica de `fracoes_entregues`/`intervalos_das_sessoes`, movidas para o `dominio/` junto com C1. "Frações prescritas do curso" é uma função só, com a regra do Glossário (última revisão aprovada, reforço sequencial soma), até a pergunta 6 ser respondida.

### A3. O Deferred "data da carga" tira de um campo obrigatório do contrato a sua fonte e impede o mês definitivo na v1

> "Data da carga do data warehouse — falta descobrir… Até lá, o AD-6 não grava retrato definitivo." (Deferred)
> "Todo `Resultado` carrega o degrau da fonte e a data do dado" (Convenções)

Cada implementador vai preencher "data do dado" de um jeito (data do cálculo, `MAX(TreatmentStartTime)`, vazio). Além disso, nenhum mês fica definitivo na v1, contra o Glossário, que manda congelar no máximo 3 meses após o fim do mês. Sem retrato, a série de 12 meses (FR-2) recalcula tudo e a NFR-2 (3 s com meses já calculados) fica inalcançável.

**Correção:** decidir o valor provisório e único de `data_do_dado` (por exemplo, `None` + motivo "carga do DW não mapeada", acompanhada sempre da data do cálculo) e escrever a consequência aceita: "na v1, até o mapeamento, nenhum mês é definitivo e a NFR-2 vale só para o mês corrente". Outra saída é promover o mapeamento a pré-requisito da fatia 1.

### A4. Papel vazio e identidade do médico não decididos (vazamento de lista de origem)

> "a lista de origem só é montada para `fisico`/`admin` e para `medico`, e neste caso já filtrada pelo próprio médico" (AD-8)

No código, `fichinha.modos_do_papel("")` devolve **todas** as abas e `pode_liberar("")` devolve `True` (janela sem login, em testes e ferramentas). O `auth` guarda só `usuario`, `nome` e `papel`, sem vínculo com o médico do ARIA. O `tratamento_db` casa médico por **pedaço de nome** (`ENV_MEDICO`). "O próprio médico" não tem implementação definida, e "médico do curso" (o `DimPatientDoctor` da lista de tratamento? o da prescrição? o da Capa, `_SQL_MEDICO`?) também não. O recorte "por médico" (FR-3) e o filtro da lista podem usar regras diferentes.

**Correção:** no AD-8, (a) papel vazio ou desconhecido **não** monta lista de origem (exceção explícita à convenção do `modos_do_papel`); (b) vínculo usuário → identificador do médico no ARIA, mantido pelo administrador em `usuarios.json`, sem casamento por nome; (c) "médico do curso" definido uma vez no `indicadores_db` e usado tanto no recorte quanto no filtro.

### A5. Recorte (FR-3) sem dono nem regra de atribuição

> "FR-1 a FR-3 (aba, período, recorte) | `interface/radioteradados_tela`" (Capability Map)

O spine não diz onde o recorte se aplica (no `WHERE` da SQL ou no `dominio/`), nem como um curso com duas máquinas, dois convênios ou mais de um sítio entra no recorte. Se o `indicadores_db` filtrar máquina na SQL e o `dominio` filtrar médico em Python, numerador e denominador saem de universos diferentes.

**Correção:** Rule nova. O `indicadores_db` devolve os cursos do período com os atributos de recorte, e o recorte é sempre um filtro aplicado no `dominio/` sobre esse conjunto, antes de calcular. As regras de atribuição (máquina da 1ª fração ou da maioria; convênio vigente na 1ª fração; "sem convênio" como valor) ficam na ficha técnica de cada indicador.

### A6. Onde mora a ficha técnica e quem cria versão nova de parâmetro

> "a ficha técnica é um registro (…)" (AD-4); a tabela põe "fichas técnicas" em `dominio/indicadores` e "aprovações" em `dados/indicadores_registro`.

Fica ambíguo se os parâmetros (30 dias, 60 dias, limiar semanal) são constantes no código (mudar é publicar um executável novo) ou dado no JSON do serviço (mudar é editar pela tela, e então quem edita?). Quem implementa o `dominio` e quem implementa o `dados` vão escolher diferente.

**Correção:** decidir e escrever. Sugestão coerente com o resto: a ficha técnica (parâmetros incluídos) vem versionada no código (`dominio/`), e a aprovação no `dados/` usa a chave `(id_indicador, versao_ficha, versao_formula)`. Mudar parâmetro passa a ser uma entrega de código com versão nova, sem edição na tela.

### A7. Versões diferentes do executável nas estações quebram o AD-6

> "`[ASSUMPTION: cálculo na estação; a primeira que abrir grava o retrato sob lock]`" (AD-6)
> "Entrega: o mesmo executável de sempre" (Structural Seed)

Com atualização estação por estação, uma estação antiga (fórmula v1) e uma nova (fórmula v2) calculam valores diferentes para o mesmo mês provisório, e **qual delas congela o retrato depende de quem abre primeiro**. É o "cada estação calculando um valor diferente" que o AD-6 diz impedir. O envelope operacional (como se atualiza, convivência de versões) não está decidido.

**Correção:** no AD-6, a estação só grava retrato se as versões de fórmula dela forem iguais às das fichas aprovadas vigentes, registradas no estado do serviço. Estação com versão diferente mostra "versão do programa diferente da aprovada" e não grava. No Structural Seed, uma linha sobre implantação: atualização de todas as estações antes de aprovar uma versão nova de fórmula.

### A8. A lista de origem viaja dentro do `Resultado` até o PDF e a gestão

> "devolve um `Resultado` com, no mínimo: valor, numerador, denominador, lista de origem…" (AD-3)
> "o PDF é gerado só a partir de `Resultado`, sem a lista de origem" (AD-7)
> "a lista de origem só é montada para `fisico`/`admin` e para `medico`" (AD-8)

As três frases se contradizem: o AD-3 sempre monta a lista (mesma passada), o AD-8 diz que ela só é montada para alguns papéis, e o AD-7 entrega ao PDF um objeto que contém nomes e confia que ele os ignore. É assim que o RD-3 acontece.

**Correção:** dividir o tipo. `dominio` devolve `Agregado` (valor, numerador, denominador, contagem de excluídos, versões, data, degrau, estado) e `ListaOrigem` (identificação) em objetos separados, produzidos na mesma passada. `papel/indicadores_pdf` só aceita `Agregado` (e um teste garante isso). A tela só pede `ListaOrigem` depois do filtro de papel do AD-8. Trocar "só é montada" por "só é entregue".

---

## Médios

### M1. O limiar de interrupção e a "família semanal" não têm dono
> "Valor de frequência fora do `_RITMO` = frequência não identificada" (AD-2)

`_DIAS_PARADO = 3` (`tratamento_db`) e `_INTERVALO_ATENCAO = 3` (`interface/tratamento.py`) são constantes de código. O AD-4 diz que o limiar é parâmetro da ficha. E o spine não decide se "Duas Vezes por Semana" (ritmo (3, 1)) entra no limiar semanal. **Correção:** a ficha da interrupção traz o mapa frequência → família de limiar, e o `dominio` nunca importa aquelas constantes. Registrar a pergunta 5 do PRD como bloqueante desse mapa.

### M2. Dias úteis "esperados" (FR-11) e do período (FR-10) ficam fora do AD-2
O AD-2 cobre só `dias_uteis_entre`. O prolongamento precisa de `_somar_dias_uteis`/`prever_fim` (sem feriado, com fallback (1, 1)), e a ocupação precisa dos dias úteis do mês. **Correção:** uma só função de calendário com feriados no `dominio/` para as três contagens, citada no AD-2.

### M3. O AD-10 supõe valores estruturados que o `config_servico` não guarda
O `config_servico` aceita só chaves de `CHAVES` com `{"valor": str, "por", "em"}`, e o `definir()` recebe uma string. Capacidade por `MachineId` e lista de feriados não cabem. **Correção:** decidir o formato (seção nova estruturada com `versao`, ou JSON serializado no `valor`) e quem edita (painel de `administracao`), com autoria por chave mantida.

### M4. Envelope operacional: esquema, cópia de segurança e restauração dos arquivos de estado
O AD-5 não pede campo de versão de esquema (o `datas_relevantes` tem `_VERSAO = 1`) nem diz se os arquivos novos entram no `dados/backup.py`. Perder `classificacoes.json` apaga o único dado manual do sistema (SM-1). **Correção:** todo arquivo de estado carrega `versao`. Decidir cópia de segurança e restauração, e o que acontece com arquivo ilegível (padrão `_preservar_ilegivel` do `registro_json`).

### M5. O portão `VERIFICADO_EM` do `indicadores_db` pode travar a própria conferência
> "`banco/indicadores_db.py`: SQL e portão `VERIFICADO_EM`"

No `tratamento_db`, o portão desliga a funcionalidade (`lista_disponivel`), e foi preciso criar `ENV_EXPERIMENTAL` para escapar do "impasse honesto". O FR-20 quer a aba visível **com** faixa até a conferência. **Correção:** dizer que `VERIFICADO_EM` vazio não bloqueia o cálculo, só mantém a faixa (AD-9). Ou então adotar o mesmo par portão + variável experimental, com a mesma faixa.

### M6. FR-21 (reserva): onde fica a "última leitura" e quais são os degraus
O spine não diz de onde vem a última leitura quando o banco cai (retrato? cache local? espelho?), nem lista os valores possíveis do degrau (banco, banco local de demonstração, espelho, retrato). **Correção:** enumerar o degrau no `Resultado`, decidir a fonte de reserva e garantir que ela não grava identificação de paciente fora da pasta do serviço.

### M7. Os estados de indicador não estão enumerados
FR-8 ("fora do banco — v2"), FR-12 ("falta a fonte"), FR-15 ("só teleterapia, sem meta"), FR-10 ("capacidade não configurada"), FR-17 ("não oficial") e o provisório/definitivo/em andamento são estados que a tela e o PDF precisam exibir igual. **Correção:** um campo `estado`/`motivo` enumerado no `Resultado`, definido no `dominio`, com o texto de exibição num lugar só.

### M8. Gravação do retrato sob lock: semântica não fixada
"A primeira que abrir grava o retrato sob lock" não diz se o cálculo acontece dentro do lock (a espera do `travar_arquivo` é de 30 s) nem o que faz quem chega depois. **Correção:** calcular fora do lock e, dentro dele, gravar só se ainda não houver retrato ("grava se ausente"). Quem chega depois descarta o próprio cálculo e lê o gravado.

### M9. O paradigma diz que o pacote "já segue" um `dominio/` puro, e o código não segue
> "**Camadas por papel no fluxo**, o padrão que o pacote `isocentro/` já segue, com **núcleo funcional**"

Hoje `dominio/qualidade_metodo.py` e `dominio/gatilho_relogio.py` importam PyQt5, `dominio/gatilho.py` importa `banco/` e `dados/`, e o registro gravado do gatilho (`gatilho_registro`) mora em `dominio/`, não em `dados/`. **Correção:** dizer que a pureza é regra nova, valendo só para `dominio/indicadores` (e o módulo extraído em C1), e torná-la verificável com um teste que falha se esses módulos importarem `PyQt5`, `isocentro.banco` ou `isocentro.dados`.

### M10. Stack sem registrar o fim de suporte do Qt 5
PyQt5 5.15.11 é a última versão (2024), e o suporte padrão do Qt 5.15 acabou em 05/2025. O reportlab já tem 5.x, e o Python 3.12 está só em correções de segurança. A fixação é deliberada (`requirements.txt`), mas o spine não registra o risco. **Correção:** uma linha no Deferred ("migração para PyQt6/Qt 6 LTS: fora da v1; a tela nova evita APIs removidas no Qt 6").

### M11. Sem regra de leitura atômica entre estado gravado e cálculo
A classificação (FR-22) muda o numerador do abandono. Se a tela lê `classificacoes.json` num momento e o worker em outro, o número e a lista podem sair de versões diferentes do arquivo. **Correção:** o worker recebe um instantâneo do estado do serviço (classificações, aprovações, configuração) lido uma vez no início do cálculo, e o `Resultado` registra o carimbo desse instantâneo.

---

## Baixos

### B1. `.memlog.md` ausente
As `[ASSUMPTION]` (AD-5, AD-6, AD-10) e as decisões ADOPTED não têm registro de origem. **Correção:** criar o memlog ou retirar a referência ao memlog das instruções da revisão.

### B2. Papel `gestao`: o código pede três lugares, não dois
> "o papel `gestao` entra em `auth.PAPEIS` e em `MODOS_POR_PAPEL`"

O comentário de `auth.py` exige também o rótulo em `administracao._FUNCAO_LABEL`. Falta dizer que o modo novo entra em `ROTULOS_MODO`, no `"medico"` do `MODOS_POR_PAPEL`, e fica **fora** do `MODOS_PADRAO`. **Correção:** listar os quatro pontos.

### B3. A supressão "< 5" não define "caso"
Não está dito se os 5 se aplicam ao numerador, ao denominador ou a ambos, nem se a supressão vale também na tela da gestão. **Correção:** fixar na função única do `dominio` (por exemplo, "suprime se numerador ou denominador < 5") e dizer onde ela se aplica.

### B4. A seta `pdf --> dom` no diagrama confunde
O diagrama sugere que o PDF chama o `dominio`, e o AD-3 diz que ele só lê `Resultado`. **Correção:** marcar a seta como "tipos e supressão" ou retirá-la.

### B5. "Mês anterior" e "Impresso em" usam o relógio da estação
Não importa na maioria dos dias, mas na virada do mês duas estações com relógios diferentes abrem em meses diferentes. **Correção:** uma linha nas Convenções ("data de referência = relógio da estação; aceito").

### B6. Tamanho previsto do `dominio/indicadores.py`
Cerca de 15 fórmulas, fichas, `Resultado` e supressão num arquivo só passam rápido de mil linhas (o repositório já precisa do `tools/mapa.py`). **Correção:** permitir `dominio/indicadores/` como pacote (um módulo por indicador mais `tipos.py`), mantendo a regra do AD-1.

---

## Cobertura do PRD e da altitude (resumo)

| Item | Situação |
| --- | --- |
| FR-1 a FR-23, NFR-1 a NFR-7 | Todos estão em `binds`. Faltam regra para NFR-1 (C2), regra que permita cumprir a NFR-2 (A3) e dono para o recorte do FR-3 (A5) e para a reserva do FR-21 (M6). |
| Implantação | Só "o mesmo executável". Falta convivência de versões (A7). |
| Ambientes | Rede da clínica e servidor local de demonstração estão cobertos (AD-11). |
| Operação | Faltam cópia de segurança, restauração e esquema dos arquivos de estado (M4), além da janela de carga no banco (C2). |
| Segurança e privacidade | AD-7 e AD-8 estão na direção certa. Falta fechar papel vazio, identidade do médico (A4) e separação de tipos (A8). |
