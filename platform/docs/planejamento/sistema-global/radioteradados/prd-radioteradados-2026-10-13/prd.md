---
title: 'PRD: Radioteradados — painel de indicadores do ISOCENTRO'
status: final
created: '2026-10-13'
updated: '2026-10-13'
inputs:
  - '../brief-radioteradados-2026-10-13/brief.md'
  - '../brief-radioteradados-2026-10-13/addendum.md'
  - '../research-bi-radioterapia-indicadores-2026-10-13/research.md'
  - 'mapeamento-banco-2026-10-13.txt'
---

# PRD: Radioteradados

## 0. Propósito do documento

Este PRD orienta a construção do Radioteradados, a aba de indicadores do ISOCENTRO. Destina-se ao autor (físico médico responsável e desenvolvedor) e aos fluxos seguintes do BMad no repositório: `bmad-architecture` e `bmad-spec`, que propõem as frentes da fila do `DESTINO.md`. Ele parte do brief, do seu adendo, da pesquisa de domínio e do mapeamento do banco de 13/10/2026, e não repete o que eles dizem. O vocabulário segue o Glossário (§3). Os requisitos são numerados FR-1 a FR-23 e agrupados por tema; a numeração é estável, não segue a ordem do texto. Suposições aparecem como `[SUPOSIÇÃO]` e estão reunidas no §12. O "como" técnico fica no `addendum.md`.

## 1. Visão

O Radioteradados calcula, a partir do banco do Varian ARIA que o ISOCENTRO já lê, os indicadores que um serviço de radioterapia precisa acompanhar e apresentar. Primeiro vêm os que a RDC ANVISA 20/2006 manda a avaliação externa considerar; depois, os operacionais que a literatura usa. Cada número mostra como foi calculado, de quando é o dado e quais pacientes estão por trás dele.

Hoje esses números saem de consulta ao banco ou de planilha, montadas pelo físico responsável fora do horário, e mudam conforme quem faz a conta. O único BI publicado sobre o ARIA (um centro, em Zurique) precisou adaptar a maioria dos painéis do fornecedor; as contagens divergiram de 7 a 10% por definição de evento, e o trabalho levou cerca de 50 pessoa-dias. A fonte é única e sem medida de resultado, mas aponta onde está o risco: na definição. Por isso, aqui, nenhum número vale sem a definição aprovada pelo físico responsável.

A v1 serve ao serviço do autor e é o primeiro corte de um catálogo que pretende cobrir todos os indicadores recomendados que o banco permitir. Se der certo, a direção de 2 a 3 anos é um painel que um serviço brasileiro com ARIA instala localmente para responder à vigilância, à gestão e à operadora, em português e com definições que um avaliador aceita. É essa direção que manda tirar do código os nomes do serviço e das atividades (FR-23).

## 2. Usuários

### 2.1 Trabalhos a fazer

- **Físico responsável:** fechar o mês, ter prontos os indicadores da avaliação externa, confiar no número e conseguir defendê-lo.
- **Gestão / responsável técnico:** acompanhar volume, ocupação, convênios e tendência sem pedir relatório ao físico responsável.
- **Médico (radioterapeuta):** saber como estão os próprios pacientes (interrupção, tempo total, percurso) sem montar consulta.

### 2.2 Fora do público da v1

Outros serviços (comercialização), operadoras, pacientes e a vigilância sanitária como usuária direta. A vigilância recebe o relatório mensal; não opera a tela.

### 2.3 Jornadas

- **UJ-1. Geova fecha setembro na primeira segunda-feira de outubro.** Abre a aba Radioteradados, que já mostra setembro. Antes de tudo, vê "4 encerramentos a classificar" e classifica os quatro (dois abandonos, uma alta antecipada, uma mudança de conduta). Os indicadores de coorte de setembro aparecem como PROVISÓRIOS, porque muitos cursos de setembro ainda estão em andamento; os de agosto e julho já mostram os seus valores; junho está maduro, e ele o congela, o que o torna DEFINITIVO. A taxa de interrupção de agosto subiu para 9%. Ele clica no número e vê, na lista de origem, os 5 cursos por trás dele, cada um com as pausas e as datas. Logo abaixo, à parte, aparecem 2 cursos semanais cujas pausas ficaram dentro do limiar da frequência prescrita e 1 curso de frequência não identificada. Ele gera o relatório mensal de setembro, marcado como provisório, e o arquiva. **Caso de borda:** o banco não responde. A aba diz isso em primeiro lugar e mostra a última leitura com a data e o degrau da fonte, nunca zero no lugar de "sem dado".
- **UJ-2. Dra. Ana confere os pacientes dela.** Com o perfil de médico, a aba abre filtrada em "só os meus". Ela vê o tempo médio do tratamento e o percurso dos próprios pacientes, abre a lista de origem de um número e reconhece a paciente que faltou por internação. Pode ver o total do serviço, mas a lista de origem continua só com os pacientes dela.
- **UJ-3. Geova aprova a definição de abandono antes de o número valer.** O indicador aparece como "definição não aprovada", com o valor provisório e a lista de origem marcados como não oficiais. Ele abre a ficha técnica, lê a fórmula, o prazo de 30 dias e as exclusões (óbito, alta antecipada, mudança de conduta), confere três cursos da lista e aprova. A aprovação fica registrada com o nome dele, a data e a versão 1 da definição.
- **UJ-4. A responsável técnica prepara a reunião da diretoria.** Com o perfil de gestão, ela vê os indicadores do último trimestre por máquina e por convênio e baixa o relatório mensal. Não vê nome de paciente em lugar nenhum.

## 3. Glossário

- **Curso** — o curso de tratamento do ARIA. Um paciente pode ter vários; cada curso tem uma ou mais prescrições e planos.
- **Frações prescritas do curso** — a soma das frações das prescrições do curso na revisão vigente. `[SUPOSIÇÃO: prescrição revisada conta na última revisão aprovada; reforço sequencial soma]`
- **Fração entregue** — sessão registrada como tratada no histórico de tratamento do ARIA.
- **Curso iniciado no período** — curso cuja 1ª fração entregue cai dentro do período. Denominador de abandono e de interrupção.
- **Curso concluído** — curso que entregou todas as frações prescritas do curso.
- **Coorte do mês** — os cursos iniciados num mês. Os indicadores de coorte (abandono, interrupção) e o tempo médio do tratamento dependem de cursos que ainda podem estar em andamento.
- **Mês provisório / maduro / definitivo** — um mês fica provisório enquanto houver curso da coorte em andamento ou encerramento a classificar, e no máximo até 3 meses depois do fim do mês; depois fica **maduro, aguardando congelamento**. Só vira definitivo quando o físico responsável o congela (decisão de 13/10/2026, na arquitetura), e só com a data da carga do data warehouse conhecida e cobrindo o mês.
- **Paciente tratado no período** — paciente com pelo menos uma fração entregue no período.
- **Encerramento planejado** — fim de curso antes das frações prescritas por alta antecipada por decisão médica, óbito ou mudança de conduta. Não conta como abandono.
- **Encerramento a classificar** — curso que parou antes das frações prescritas, sem óbito que o explique, ainda sem classificação. O ARIA não guarda o motivo de forma estruturada (mapeamento de 13/10/2026).
- **Classificação de encerramento** — a decisão registrada sobre um encerramento a classificar: abandono, alta antecipada ou mudança de conduta, com nome e data.
- **Frequência prescrita** — o ritmo de frações do curso, lido da frequência da prescrição aprovada no ARIA (a mesma fonte que a Capa e a Ficha Virtual já usam, conferida contra o banco). Valores vistos no serviço: uma vez por dia, duas vezes por dia, dias alternados, duas vezes por semana, aplicação única.
- **Frequência não identificada** — curso sem frequência na prescrição, ou com um valor que o ISOCENTRO não sabe converter em ritmo. Fica fora da taxa de interrupção.
- **Pausa** — dias úteis entre duas frações entregues consecutivas do mesmo curso, sem contar os dois dias: sexta → segunda = 0; segunda → sexta = 3.
- **Interrupção** — pausa maior que o limiar da frequência prescrita (FR-6).
- **Indicador** — número calculado por uma fórmula sobre o banco, para um período e um recorte.
- **Ficha técnica** — a definição escrita de um indicador: fórmula, numerador, denominador, exclusões, parâmetros (prazos, limiares), origem no banco, versão e estado de aprovação.
- **Definição aprovada** — versão da ficha técnica aceita pelo físico responsável, com nome e data.
- **Recorte** — combinação de filtros: período, máquina, médico, sítio, convênio.
- **Lista de origem** — os pacientes e cursos que compõem o numerador de um número, com o motivo de cada um ter entrado.
- **Núcleo RDC** — os indicadores do item 6.11 da RDC 20/2006 que saem do banco.
- **Camada operacional** — indicadores da literatura e da gestão que não são exigência normativa.
- **Data do dado** — a data da última carga do data warehouse que o número usou, mais a data do cálculo.
- **Degrau da fonte** — de onde veio o dado. Nesta aba: banco, banco local (demonstração), cache provisório ou mês congelado. Os degraus da Capa (espelho, relatório exportado) não se aplicam aqui.
- **Faixa EXPERIMENTAL** — aviso no topo da aba enquanto os números não forem conferidos contra o ARIA.
- **Relatório mensal** — o PDF dos indicadores de um mês. Imutável depois de emitido.
- **Configuração do serviço** — parâmetros do serviço que não ficam no código: nomes das atividades, capacidade por máquina, calendário de feriados, físico responsável (FR-23).
- **Físico responsável** — a pessoa designada na configuração do serviço. Só ela aprova definições, classifica encerramentos e registra a conferência.
- **Perfis** — físico, médico, gestão e administrador. Gestão vê só agregados; médico vê a lista de origem só dos próprios pacientes; administrador mantém a configuração.

## 4. Funcionalidades

### 4.1 A aba e os recortes

**Descrição:** o Radioteradados é uma aba do ISOCENTRO, ao lado da Agenda e da Ficha Virtual. Abre no mês anterior. Mostra o núcleo RDC primeiro e a camada operacional abaixo. Realiza UJ-1, UJ-2 e UJ-4.

#### FR-1: Abrir a aba no mês anterior

O usuário logado abre o Radioteradados e vê os indicadores do mês anterior.

**Consequências (testáveis):**
- Aberta em qualquer dia de outubro, a aba mostra setembro.
- Cada indicador mostra a data do dado, o degrau da fonte e se o mês é provisório ou definitivo.

#### FR-2: Escolher o período e comparar

O usuário escolhe qualquer mês, o mês atual ou os últimos 12 meses, e vê cada indicador ao lado do mesmo indicador no mês anterior.

**Consequências:**
- Nos 12 meses, cada indicador mostra a série mês a mês, com os meses provisórios marcados.
- O mês atual aparece como "em andamento".

#### FR-3: Recortar por máquina, médico, sítio e convênio

O usuário combina filtros, e todos os indicadores respeitam o recorte.

**Consequências:**
- O recorte vigente aparece escrito acima dos números.
- O perfil de médico abre em "só os meus"; pode ver os totais do serviço, mas a lista de origem nunca mostra pacientes de outro médico.
- A máquina é identificada pelo identificador do ARIA, não pelo nome.

**Fora do escopo:** ranking de médicos (§5).

### 4.2 Núcleo RDC

**Descrição:** os indicadores do item 6.11 da RDC 20/2006 que o banco permite calcular. Adesão a protocolos e desvio da dose absoluta ficam fora da v1, e a tela diz isso. Realiza UJ-1 e UJ-3.

#### FR-4: Tempo médio do tratamento

O sistema calcula a média de dias corridos entre a 1ª e a última fração entregue dos cursos concluídos no período.

**Consequências:**
- Cursos com encerramento planejado ficam fora.
- A ficha técnica diz que o curso é atribuído ao mês em que foi concluído.

#### FR-5: Taxa de abandono

O sistema calcula os cursos iniciados no período classificados como abandono, divididos pelos cursos iniciados no período.

**Consequências:**
- Um curso vira encerramento a classificar quando fica 30 dias corridos sem fração entregue e ainda tem frações a entregar. O prazo é parâmetro da ficha técnica, aprovado pelo físico responsável (decisão do serviço, sem referência na literatura). `[SUPOSIÇÃO: 30 dias]`
- Óbito registrado no cadastro do paciente até 30 dias depois da última fração entregue exclui o curso automaticamente. Óbito posterior não exclui: o curso vai para classificação. `[SUPOSIÇÃO: janela de 30 dias, parâmetro da ficha técnica]`
- Só conta como abandono o curso classificado assim (FR-22). Ao lado da taxa aparece quantos encerramentos ainda estão a classificar.

#### FR-22: Classificar encerramentos

O físico responsável vê a lista de encerramentos a classificar e classifica cada um como abandono, alta antecipada ou mudança de conduta. Realiza UJ-1.

**Consequências:**
- A classificação registra nome, data e motivo, e é gravada pelo ISOCENTRO, nunca no ARIA.
- Reclassificar guarda a anterior (histórico, nunca sobrescrita).
- Os registros ficam na pasta do serviço definida pelo administrador, fora do repositório (`.gitignore`), e não aparecem em log com nome ou registro de paciente.
- Lançamento pela enfermagem fica para depois `[FORA DA v1]`: o papel de quem classifica deve poder ser estendido.

#### FR-6: Taxa de interrupção, conforme a frequência prescrita

O sistema calcula os cursos iniciados no período com pelo menos uma interrupção, divididos pelos cursos iniciados no período com frequência prescrita identificada.

**Consequências:**
- Frequências não semanais: interrupção é pausa maior que 3 dias úteis — a mesma regra da faixa âmbar da Ficha Virtual. O mapeamento de 13/10/2026 confirma: 2.475 pausas de 3 dias corridos em 6 meses, o fim de semana.
- Frequência semanal: interrupção é pausa maior que 7 dias corridos mais 3 dias úteis. É parâmetro da ficha técnica, decisão do serviço sem referência na literatura. `[SUPOSIÇÃO]`
- Curso de frequência não identificada fica fora da taxa e aparece contado ao lado dela; a frequência **não** é inferida pelas pausas, porque um curso diário com interrupções longas seria lido como semanal e a interrupção sumiria.
- Feriados do calendário da configuração do serviço não contam como dia útil. O Radioteradados não altera a Ficha Virtual: se a contagem de dias úteis for compartilhada, o comportamento atual dela é preservado.
- A lista de origem mostra cada pausa com as datas e o tamanho; os cursos com pausa justificada pela frequência prescrita aparecem à parte, fora da lista que soma o numerador.

#### FR-7: Taxa de simulação

O sistema calcula os pacientes com o 1º curso iniciado no período que tiveram TC de simulação, divididos pelos pacientes com o 1º curso iniciado no período.

**Consequências:**
- A TC de simulação é a atividade "TOMO-DUO / TOMO-ANA" do ARIA (confirmado pelo usuário em 13/10/2026), casada pelo código exato configurado (FR-23). Atividade parecida, mas não configurada, não conta.
- A simulação conta se ocorreu até 60 dias antes da 1ª fração entregue. `[SUPOSIÇÃO: janela de 60 dias]` A taxa nunca passa de 100%.

#### FR-8: Indicadores da RDC fora da v1 aparecem como tal

Adesão a protocolos e desvio da dose absoluta aparecem no núcleo RDC com a marca "fora do banco — v2", e não somem.

**Consequências:**
- O relatório mensal lista os dois com a mesma marca.

### 4.3 Camada operacional

**Descrição:** indicadores de gestão e da literatura, sem metas na v1, exceto a de tempo total no colo do útero. Realiza UJ-1, UJ-2 e UJ-4.

#### FR-9: Pacientes novos e cursos iniciados

O sistema conta os pacientes com o 1º curso iniciado no período e os cursos iniciados no período.

**Consequências:**
- A ficha técnica nomeia o evento de início: a 1ª fração entregue. (É exatamente a escolha de evento que fez as contagens divergirem em Zurique.)

#### FR-10: Sessões por máquina e ocupação

O sistema conta as frações entregues por máquina e calcula a ocupação: frações entregues ÷ (capacidade diária da máquina, em sessões × dias úteis do período).

**Consequências:**
- Máquina sem capacidade configurada mostra só as frações entregues, com "capacidade não configurada". Máquina nova ou renomeada nunca herda a capacidade de outra.

#### FR-11: Tempo total e prolongamento

O sistema mostra, por curso concluído, os dias da 1ª à última fração entregue e o prolongamento: dias reais menos dias esperados, sendo os esperados os dias úteis necessários para entregar as frações prescritas no ritmo da frequência prescrita.

**Consequências:**
- A distribuição (mediana e percentil 90) aparece além da média.
- Curso de frequência não identificada não tem prolongamento calculado.

#### FR-12: Faltas

O sistema calcula as sessões agendadas sem fração entregue no mesmo dia, divididas pelas sessões agendadas.

**Consequências:**
- Enquanto não estiver confirmado que o status do agendamento separa falta de cancelamento pelo serviço, o indicador fica vazio e diz que falta a fonte. Cancelamento pelo serviço nunca conta como falta do paciente.

#### FR-13: Percurso

O sistema calcula as medianas, em dias, de 1ª consulta → TC de simulação → 1ª fração entregue.

**Consequências:**
- Consulta e simulação são as atividades "1a Consulta" e "TOMO-DUO / TOMO-ANA", casadas pelo código exato configurado (FR-23).
- Paciente sem uma das etapas aparece na lista de origem com a etapa faltando e fica fora da mediana daquele trecho.

#### FR-14: Distribuição

O sistema mostra os cursos iniciados por convênio, sítio, diagnóstico, intenção e fracionamento.

**Consequências:**
- Curso sem o dado aparece como "sem convênio", "sem diagnóstico" etc., e não some da soma.

#### FR-15: Colo do útero ≤ 50 dias

O sistema calcula a proporção de cursos de colo do útero (CID C53) com tempo total de até 50 dias, da 1ª fração de teleterapia à última sessão de braquiterapia, e a mostra ao lado da meta ESGO/ESTRO de pelo menos 90%.

**Consequências:**
- A braquiterapia não está no histórico de tratamento do ARIA, mas está na agenda da braquiterapia (usuário, 13/10/2026). Enquanto essa agenda não estiver mapeada, o indicador mede só a teleterapia, diz isso e **não mostra a comparação com a meta**.
- A meta é referência publicada, não reprova o serviço; não foi adotada pelo serviço como meta própria.
- O curso é atribuído ao mês da última sessão.
- A outra meta ESGO/ESTRO (início em até 6 semanas do encaminhamento) fica fora: a data de encaminhamento não está no ARIA.

### 4.4 Ficha técnica e aprovação

**Descrição:** nenhum indicador vale sem definição aprovada. Realiza UJ-3.

#### FR-16: Ver a ficha técnica de qualquer indicador

Qualquer usuário abre a ficha técnica de um indicador: fórmula, numerador, denominador, exclusões, parâmetros, origem no banco, versão, estado de aprovação, quem aprovou e quando, e a data do dado.

#### FR-17: Aprovar uma definição

O físico responsável aprova uma versão da ficha técnica de um indicador.

**Consequências:**
- Antes da aprovação, o valor e a lista de origem aparecem marcados "definição não aprovada — não oficial", para que o físico responsável confira cursos de exemplo antes de aprovar.
- Mudar fórmula ou parâmetro cria uma versão nova, que volta a precisar de aprovação.
- A tela recalcula com a versão vigente e diz qual é; relatórios já emitidos não mudam (FR-19).

### 4.5 Lista de origem

**Descrição:** todo número abre a lista de origem: os pacientes e cursos por trás dele. Realiza UJ-1 e UJ-2.

#### FR-18: Abrir a lista de origem

O físico e o médico (este, só dos próprios pacientes) clicam num indicador e veem a lista de origem: paciente (nome e registro), curso, datas relevantes e o motivo de ter entrado no número.

**Consequências:**
- A lista soma exatamente o numerador mostrado.
- Casos excluídos pela regra (pausa justificada pela frequência prescrita, frequência não identificada, óbito) aparecem numa seção à parte, que não soma o numerador.
- O perfil de gestão não vê a lista de origem.

### 4.6 Relatório mensal

#### FR-19: Gerar o relatório mensal em PDF

O usuário gera o relatório de um mês: indicadores, recorte, ficha técnica resumida e versão de cada um, estado de aprovação, data do dado, degrau da fonte, se o mês é provisório ou definitivo, e a faixa EXPERIMENTAL, se ainda valer.

**Consequências:**
- O relatório sai **só com agregados**: sem nome, registro ou qualquer dado que identifique paciente.
- Célula de recorte com menos de 5 casos sai suprimida ("< 5"). `[SUPOSIÇÃO: mínimo de 5]`
- O relatório emitido é imutável. Corrigir um mês é emitir um relatório novo, com versão e data; o anterior é guardado.
- O rodapé segue o padrão de impressão do ISOCENTRO ("Impresso em …").

### 4.7 Confiabilidade

#### FR-20: Faixa EXPERIMENTAL até a conferência

A aba mostra a faixa EXPERIMENTAL até o físico responsável registrar a conferência dos números contra o ARIA.

**Consequências:**
- A conferência depende do portão R-07 do ISOCENTRO (conferência dos cursos contra o ARIA, frente `voce` pendente no `DESTINO.md`): é a mesma base de cursos que o painel "em tratamento" usa. Enquanto o R-07 não fechar, a faixa não sai.
- A saída exige a conferência de SM-2, registrada com data; nunca é automática (mesma regra do `LISTA_VERIFICADA_EM`).

#### FR-21: Dado de reserva anunciado

Quando o banco não responde, a aba mostra a última leitura com a data e o degrau da fonte, e o aviso aparece em primeiro lugar. Nunca mostra zero no lugar de "sem dado".

### 4.8 Configuração do serviço

#### FR-23: Manter a configuração do serviço

O administrador mantém a configuração do serviço: códigos das atividades de consulta e simulação, capacidade diária por máquina (pelo identificador do ARIA), calendário de feriados e físico responsável.

**Consequências:**
- A configuração mora no `config_servico.json` do serviço, ao lado do índice central, seguindo a regra do projeto de que pasta e parâmetro do serviço são decisão de administrador, nunca da estação.
- Parâmetro de cálculo (prazos e limiares) não fica aqui: fica na ficha técnica, com versão e aprovação (FR-17).

## 5. Fora de propósito (explícito)

- O Radioteradados **não escreve** no ARIA nem em nenhum sistema clínico. O que ele grava (aprovação de definição, classificação de encerramento, conferência, relatórios) fica no próprio ISOCENTRO.
- **Não promete** aumento de ocupação nem de eficiência. Mede a ocupação; nenhum estudo mediu ganho de ocupação depois de implantar um painel, e o único ganho medido na literatura foi de um painel somado a mudança de processo.
- **Não classifica** médicos, físicos ou planejadores: nenhuma visão ordena pessoas por indicador.
- **Não define metas** do serviço na v1; mostra tendências e a meta ESGO/ESTRO de tempo total no colo do útero, como referência.
- **Não substitui** o sistema de notificação de incidentes nem o controle de qualidade.
- **Não é** produto comercial na v1: sem multi-instituição e sem configuração de marca.

## 6. Escopo da v1

### 6.1 Dentro, em duas fatias

- **Fatia 1 (o núcleo, entra primeiro):** FR-1 a FR-8, FR-16 a FR-23.
- **Fatia 2 (camada operacional):** FR-9 a FR-15. FR-12 e FR-15 entram parcialmente até os mapeamentos pendentes (§11).

Só dados do banco do ARIA, mais a classificação de encerramento feita pelo físico responsável.

### 6.2 Fora da v1

- **Adesão a protocolos e desvio da dose absoluta** — fora do banco; v2 com lançamento manual.
- **Exigências contínuas da RDC 20/2006 e da norma CNEN/ANSN 6.10** — cálculo verificado até a 3ª fração (RDC 9.7c), segunda assinatura no plano e consulta médica semanal (norma 6.10). O mapeamento achou as atividades "Duplo Check", "Aprovação Física", "Duplo Check Médico" e "Alta de Tratamento", com milhares de registros por ano: ponto de partida para a v2.
- **Revisão física semanal e pendências de física** — recomendação AAPM TG-275, **não exigência brasileira**; v2, junto com o módulo Revisão Semanal.
- **Tempo de acelerador perdido** — a atividade de parada ainda precisa ser **criada no ARIA** pelo serviço, fora do software.
- **Incidentes** — outro sistema.
- **Prazo de 60 dias da Lei 12.732** — a data do laudo não está no ARIA.
- **Classificação de encerramento pela enfermagem** — evolução prevista do FR-22.
- **Metas do serviço, previsão de demanda, comparação entre serviços.**

## 7. Conformidade e governança de dados

- **RDC 20/2006, item 6.11:** os indicadores do núcleo RDC preparam a avaliação externa (6.9), que considera esses seis indicadores "no mínimo". O texto não fixa fórmula; a ficha técnica aprovada (FR-17) é a definição do serviço. A vigência da RDC em 2026 não foi confirmada no DOU (§11).
- **Norma CNEN/ANSN 6.10:** origem das exigências contínuas adiadas para a v2 (§6.2).
- **AAPM TG-275:** recomendação internacional, não exigência; o PRD separa as duas coisas.
- **Dado de paciente:** a lista de origem identifica pacientes e só existe na rede do serviço, para físico e médico (este, só dos próprios). O relatório mensal sai agregado, com supressão de células pequenas (FR-19). Os registros de classificação ficam fora do repositório e de logs (FR-22).
- **Somente leitura:** nenhuma escrita no banco do ARIA (regra do projeto; `docs/qms/escopo.md`, Fronteiras).
- **Rastreabilidade:** aprovações, classificações, conferência e relatórios emitidos ficam registrados com nome, data e versão.
- **Classe e riscos (`docs/qms`, decididos pelo físico responsável em 13/10/2026):** classe IEC 62304 **A**. Ligação requisito → risco: FR-4 a FR-7, FR-17, FR-18 e FR-20 → RD-1 (fórmula ou definição errada); FR-6 → RD-2 (interrupção não detectada); FR-19 → RD-3 (reidentificação no relatório); NFR-1 → RD-4 (mês congelado incompleto); FR-22 → RD-5 (registro de classificação vaza). S, O e D ainda a preencher em `riscos.md`.

## 8. Requisitos não funcionais transversais

- **NFR-1 Carga no banco clínico e mês maduro:** as consultas não podem degradar o ARIA em horário de tratamento. Um mês só é congelado depois que a carga do data warehouse cobre o mês inteiro; antes disso, o número aparece como "carga incompleta" ou com a data da carga ausente. O mês provisório é recalculado em segundo plano; o congelado é guardado e não recalculado (§3). Cálculo automático só fora de uma janela configurável de horário de tratamento; dentro dela, só a pedido (decisão de 13/10/2026, na arquitetura).
- **NFR-2 Tempo de tela:** a aba abre em até 3 segundos com os meses já calculados. `[SUPOSIÇÃO]`
- **NFR-3 Fora da rede:** tudo funciona contra o servidor local de demonstração; consulta nova entra na tradução do servidor local e no seu teste, senão a suíte quebra.
- **NFR-4 Padrão de tela:** a aba segue `ui.py` e `estilo.py`, sem verde como cor de ação (verde é dose), com o modo dia/noite. O layout é descrito em texto e aceito antes de ser codificado (regra do repositório).
- **NFR-5 Idioma:** português do Brasil em tela, ficha técnica e relatório.
- **NFR-6 Local, sem nuvem:** roda na rede do serviço, sobre o banco que o ISOCENTRO já lê; nenhum dado sai para serviço de terceiros (`docs/qms/escopo.md`).
- **NFR-7 Sem versão mínima de ARIA própria:** funciona com a versão de ARIA do serviço; não exige atualização do ARIA para existir.

## 9. Métricas de sucesso

**Primárias**
- **SM-1:** por três meses seguidos, os indicadores do núcleo RDC que saem do banco são produzidos sem planilha nem consulta manual; o único trabalho manual é a classificação de encerramentos. Valida FR-4 a FR-7, FR-19 e FR-22.
- **SM-2:** a conferência contra o ARIA bate. (a) Numa amostra de pelo menos 20 cursos, a lista de origem de cada indicador bate com o ARIA, divergência zero. (b) Num conjunto de cursos conferidos à mão, cobrindo interrupção, frequência semanal, abandono, óbito e frequência não identificada, cada fórmula classifica igual à conferência manual. Valida FR-4 a FR-7, FR-18 e FR-20. `[SUPOSIÇÃO: 20 cursos; o conjunto manual tem pelo menos 2 casos de cada tipo]`

**Secundárias**
- **SM-3:** todo indicador mostrado como oficial tem definição aprovada. Valida FR-17.
- **SM-4:** o físico responsável deixa de montar planilha de indicadores para a chefia.
- **SM-5 (condicional):** o relatório mensal é aceito como material na próxima avaliação externa. Valida FR-19.

**Contramétrica (não otimizar)**
- **SM-C1: taxa de interrupção baixa.** Não deve ser "melhorada" ampliando exclusões ou afrouxando limiares numa versão nova da ficha técnica. Contrabalança SM-3: definição aprovada não é definição conveniente.

## 10. Riscos e dependências

- **Definição.** A primeira versão de cada fórmula é proposta e precisa da aprovação do físico responsável; é onde o BI de Zurique teve mais retrabalho.
- **Portão R-07.** A conferência dos cursos contra o ARIA, pendente no `DESTINO.md`, libera também este painel (FR-20).
- **Mapeamentos pendentes.** Agenda da braquiterapia, status de falta × cancelamento, e o valor de frequência do regime semanal (§11).
- **Qualidade do ARIA.** O estado clínico do curso não é mantido (17.940 ACTIVE contra 13.181 COMPLETED); o painel não pode depender dele.
- **Atividade de parada.** Precisa ser criada no ARIA pelo serviço antes do indicador de tempo de acelerador perdido (v2).
- **Para vender (fora da v1):** o enquadramento do software pela ANVISA (RDC 657/2022) não foi verificado; nomes do serviço e de atividades ainda estão fixos no código em outras partes do app.
- **QMS do repositório:** resolvido em 13/10/2026 — classe A, linha no `escopo.md`, riscos RD-1 a RD-5 (§7). Falta preencher S, O e D.

## 11. Perguntas em aberto

Respondidas em 13/10/2026 pelo `tools/mapear_indicadores` (`mapeamento-banco-2026-10-13.txt`) e pelo usuário: motivo de encerramento (não estruturado, só óbito → FR-22), frequência prescrita (frequência da prescrição — corrigido na arquitetura: a primeira leitura apontava o padrão de frações do plano), simulação e consulta ("TOMO-DUO / TOMO-ANA" e "1a Consulta"), braquiterapia (na agenda da braquiterapia).

**Do físico responsável:**
1. ~~Classe IEC 62304~~ — **A** (13/10/2026).
2. ~~Inclusão no `docs/qms/escopo.md`~~ — feita (13/10/2026).
3. ~~Modos de falha em `docs/qms/riscos.md`~~ — RD-1 a RD-5 (13/10/2026). **Pendente:** preencher S, O e D (não bloqueia a arquitetura; revisitar antes da 1ª frente de código do núcleo RDC).

**Do banco, na próxima rodada do mapeador:**
4. **Qual recurso ou atividade é a agenda da braquiterapia?** FR-15.
5. **Como o regime semanal aparece na frequência da prescrição?** O vocabulário já traduzido pela Capa não tem "semanal"; conferir os 7 valores distintos na próxima rodada do mapeador. FR-6 e FR-11.
6. **As contagens do curso (sessões planejadas, entregues e restantes) servem?** A consulta pela linha-resumo do histórico voltou vazia. FR-5 e FR-22.
7. **O status do agendamento separa falta de cancelamento pelo serviço?** FR-12.

**Externas:**
8. **A RDC 20/2006 está vigente em 2026?** Conferir no DOU antes de usar o relatório na avaliação externa.
9. **O relatório mensal será aceito pela vigilância?** (SM-5)

## 12. Índice de suposições

- §3: prescrição revisada conta na última revisão aprovada; reforço sequencial soma.
- FR-5: prazo de 30 dias para encerramento a classificar.
- FR-5: óbito até 30 dias depois da última fração entregue exclui o curso.
- FR-6: limiar da frequência semanal = 7 dias corridos + 3 dias úteis.
- FR-7: TC de simulação até 60 dias antes da 1ª fração entregue.
- FR-19: mínimo de 5 casos por célula no relatório.
- NFR-1: cálculo em segundo plano, fora do horário de tratamento.
- NFR-2: aba abre em até 3 s.
- SM-2: 20 cursos; conjunto manual com pelo menos 2 casos de cada tipo.
- Herdada do brief: o relatório mensal é aceito pela vigilância (SM-5).
