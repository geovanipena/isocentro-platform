# Decisões sem base bibliográfica — para discussão no serviço

Pedida pelo físico responsável em 26/10/2026, junto com a regra de decisão do
ISOCENTRO (`docs/qms/escopo.md`, "Regra de decisão"): **toda decisão se apoia
numa referência; havendo duas ou mais, vale a mais restritiva.** O que está
abaixo é o que ficou **sem** referência no acervo (`conhecimento/`). Cada linha
diz o que o software faz **até** a discussão (a opção mais conservadora, dita
como provisória na tela) e quem pode responder.

Origem de cada linha: os questionários em `docs/planejamento/questionarios/`,
respondidos em 26/10/2026. Quando a discussão fechar um item, a resposta volta
ao questionário e à spec do módulo, e a linha aqui ganha a data de fechamento.

| # | Módulo | O que falta decidir | Por que não tem base | Até a discussão, o software… | Quem pode responder |
| --- | --- | --- | --- | --- | --- |
| 1 | Todos | Classe ANVISA do ISOCENTRO | A regra que classifica (RDC 751/2022) não está no acervo | Segue o caminho *in house* da RDC 657 (classe I ou II), "até todos os testes" | Físico; trazer a RDC 751 ao acervo |
| 2 | Plano | Tempo máximo da segunda checagem (NFR-5) | A base não fixa tempo | Usa o critério do FR-11: pronta antes da fila de Aprovação Física | Físico |
| 3 | Plano | Dose acumulada dos 10%: registrada ou planejada; curso ou fase | RDC 20 e TG-114 não dizem | Dose registrada no ARIA; curso e fase, dispara a que vencer primeiro | Físico e radioterapeutas |
| 4 | Plano | Máquina da prescrição = máquina do agendamento | Regra do serviço, sem referência | Confere as duas contra o RT Plan e entre si | Físico |
| 5 | Plano | Critério de "curso anterior aberto" | Regra do serviço | Status diferente de concluído | Físico |
| 6 | Plano | Conferências do isocentro (4) e **tolerância em mm** | A base não tem | Mede e mostra, **sem veredito** até a tolerância existir | Físico |
| 7 | Plano | Alto risco na faixa de 3 a 6 Gy por fração | TG-101 e TG-275 não cobrem a faixa | Alto risco por ≥ 6 Gy/fr, ≤ 5 frações ou < 6 dias (o que disparar) | Físico e radioterapeutas |
| 8 | Plano | O que invalida uma assinatura | O TG-275 manda cada serviço definir | Invalida em todos os casos (UID novo, status, conteúdo, mudança menor) | Físicos |
| 9 | Fundação | Valor inicial da tabela perfil → módulos/ações | Suposições da UX, sem referência | Matriz da UX; o admin ajusta em Configurações | Físico, gestão |
| 10 | GQ | k_Q 2000 × Rev. 1: o N_D,w atual já incorpora o ICRU 90? | Pergunta ao laboratório (pendência 6) | k_Q de 2000 com o N_D,w atual | METROBRAS |
| 11 | GQ | Quando cadastrar a ação de cada teste | A base não dá momento | Antes da carga, com alguns exemplos; o cartão diz quando falta | Físico |
| 12 | GQ | Itens nível 2 com conferência visual pendente | Processo interno | Ficam em sombra até a conferência linha a linha | Físico |
| 13 | GQ | Dermopan em uso clínico hoje? | O dado mais novo é o PPR de mai/2026 | Entra na carga da CEL; dosimétricos `indeterminado` sem câmara em 50 kV | Físico da CEL |
| 14 | GQ | O que acontece com o registro de CQ depois do prazo | RDC 20 e RDC 657 não dizem | Nada se apaga (o mais longo dos dois prazos) | Físico, jurídico |
| 15 | Segurança | Ford 2012 × taxonomia britânica 2024 | Duas listas que não se ordenam por "mais restritiva" | Ford 2012, mesma lista nos dois campos, 8 macroetapas e 91 passos | Físico, NSP |
| 16 | Segurança | Onde entra o "1º dia" do FR-29 no mapa do Ford | A base não casa os dois | Fica como opção de detecção até ser casado com um passo | Físico, NSP |
| 17 | Segurança | Registro de incidente é prontuário? O art. 7º do CFM 1821 segue valendo ao lado da Lei 13.787? | A base não responde | Guarda permanente | Jurídico, NSP |
| 18 | Documentação | Periodicidade do ASO no PCMSO de cada clínica | O PCMSO não está no acervo | 1 ano do exame, para todo IOE; vence na hora em retorno, mudança de risco ou dose acima | SESMT, médico do PCMSO |
| 19 | Documentação | A chave `autorizacao_funcionamento` do ppr-streamlit é a da CNEN ou o alvará? | A base não diz | Os dois como tipos separados | SPR |
| 20 | Documentação | Periodicidade do SEVRRA, e se mudança de equipamento obriga a refazer | Nenhuma norma do acervo cita o SEVRRA | Sem data, `informativo`, nunca em dia | SPR, físico |
| 21 | Documentação | Quem, em cada perfil, é IOE | Depende da área de trabalho, não do cargo | Marca IOE por pessoa e clínica, mantida pelo SPR | SPR |
| 22 | Radioteraficha | Limite de usos da máscara (hoje 20 no código) | Sem fonte | Mantém o aviso aos 20; usos desconhecidos nascem vazios | Físico, dosimetria |
| 23 | Radioteraficha | Qual é o "outro sistema" do inventário de imobilizadores | O código cita e não diz qual | Levantamento na prateleira, por clínica | Dosimetria |
| 24 | Radioteraficha | Quem edita os modelos de notas de posicionamento; as três clínicas usam o mesmo vocabulário? | A base não diz | Modelos globais, notas do paciente por clínica | Físico, radioterapeutas |
| 25 | Radioteraficha | Prazo e providência para o vínculo pendente que nunca liga | A base não tem | Sem prazo, na lista do físico, sem ligação à mão | Físico |
| 26 | Radioteraficha | Raízes reais do share para a varredura das fichas antigas | Dado de cada clínica | União de todas as fontes, inclusive os `.zip` | TI de cada clínica |
| 27 | Todos | Política de uso de LLM no serviço | Rascunho (`politica-llm-rascunho-2026-10-26.md`) | Vale o AD-42 dentro do ISOCENTRO | Físico, direção, encarregado LGPD |
| 28 | Segurança | Alerta `atencao` antes dos 30 dias do art. 26 | NN-6.10 e guia CNEN dão só os 30 dias | `atencao` aos 20 dias, `alta` aos 30; `alta` desde a identificação até a investigação iniciada ("imediatamente", art. 26) | Físico |
| 29 | Segurança | Feriado estadual e municipal no 15º dia útil da RDC 36 | A RDC 36 não define o calendário | Só sábado, domingo e feriado nacional deixam de contar (prazo mais cedo) | Físico, NSP |
| 30 | Segurança | Prazo para triar evento novo | Ford 2012 pede retorno e acompanhamento, sem prazo | Alerta aos 7 dias sem triagem | Físico |
| 31 | Segurança | Kappa mínimo entre físicos na classificação (CAP-10) | O acervo não traz limiar de concordância para taxonomia de incidente | Kappa ≥ 0,7 em 30 casos antes de usar a matriz | Físico |
| 32 | Segurança | A matriz de risco do ISOCENTRO pode substituir o SEVRRA no PPR? | O guia CNEN pede análise de risco periódica sem nomear o método | SEVRRA continua em paralelo; a matriz não substitui o documento entregue | SPR, CNEN |
| 33 | Todos | Tempo máximo para abrir um painel (NFR-5) | A base não fixa tempo de resposta de tela | 3 s, provisório | Físico |
| 34 | Todos | Segregação (IEC 62304 4.3 e 5.3.5) entre o cálculo TRS-398 (C) e o núcleo (A) no mesmo processo | O texto da norma não está no acervo (só link de blog); o físico pediu esperar o texto (IEC-62304-TEXTO na aquisição) | O mais restritivo: com o TRS-398 no executável, todo item do processo tem rigor C | Físico |
| 35 | Fundação | Como o alerta passa a "visto" (UX U8) | A base não trata | Por ação explícita da pessoa, nunca ao abrir (abrir não prova leitura) | Físico |
| 36 | Fundação | Destino do botão "Abrir fila" do Início | A UX não definiu | Lista completa dos alertas do perfil na clínica, na ordem da Zona 2 | Físico |
| 37 | Fundação | Destino do clique na máquina "normal" da Zona 1 | A UX não definiu | Sem destino: a linha só é clicável quando tem motivo | Físico |
| 38 | Fundação | Relógio de referência e borda dos prazos (spec Fundação, Open Questions) | A base não trata | Hora do banco central para todas as clínicas; no instante do vencimento o prazo já está vencido (`alta`), e no do aviso já está em aviso (R-21) | Físico |

## Também a levar, embora tenham base

- **FFF no PPR** (pendência 13): o FFF está em uso no TrueBeam e não consta do
  PPR; a NN-6.10, art. 15, XIV, pede a complementação **antes** de mudar
  procedimento.
- **R-07 antes do MVP 2**: decidido; é cronograma, não falta de base.
