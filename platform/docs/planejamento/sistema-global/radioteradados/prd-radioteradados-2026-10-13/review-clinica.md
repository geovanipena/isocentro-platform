---
title: 'Revisão de segurança clínica — PRD Radioteradados'
created: '2026-10-13'
revisado: 'prd.md (draft, 2026-10-13), com addendum.md como apoio'
instrucao: 'docs/qms/revisao-clinica.md'
fatos: 'docs/qms/escopo.md, docs/qms/riscos.md, docs/qms/classificacao-62304.md'
---

# Revisão de segurança clínica — PRD Radioteradados

O documento não foi reescrito. Cada linha traz o trecho citado, a regra de `docs/qms/revisao-clinica.md` que ele viola, a gravidade e a pergunta que o físico precisa responder.

Contexto da revisão: o Radioteradados só lê o data warehouse e não imprime nada que vá para a sala de tratamento. O que ele grava (aprovação, classificação, conferência) fica no ISOCENTRO, nunca no ARIA (PRD §5 e §7). Por isso nenhum achado é bloqueante pela regra 2. Os riscos que sobram são número oficial errado (avaliação externa, gestão) e dado de paciente.

Também foi conferido `mapeamento-banco-2026-10-13.txt`, que está versionado no repositório. Ele declara "nenhuma linha de paciente foi lida: só catálogos e contagens", e a busca não achou nome nem registro de paciente.

## Achados

| # | Trecho citado | Regra | Gravidade | Pergunta ao físico |
|---|---|---|---|---|
| 1 | §4 / §6.1: o Radioteradados como "aba do ISOCENTRO" que calcula indicadores sobre o `variandw` | 9 | importante | `classificacao-62304.md` está vazio, e o Radioteradados não tem classe. Além disso, a tabela "O que o sistema faz" do `escopo.md` só prevê o `variandw` para a Capa de tratamento. Qual é a classe do módulo, e o escopo será atualizado para incluir o painel de indicadores antes da arquitetura? |
| 2 | FR-4 a FR-22 (todos os requisitos clínicos), §7 "Rastreabilidade" | 8 | importante | `riscos.md` está vazio, então nenhum FR se liga a um modo de falha. A única verificação contra o ARIA (SM-2) confere se a lista de origem bate. Ela não confere se a regra de interrupção, abandono ou prolongamento classifica certo. Quais modos de falha entram em `riscos.md`, e haverá um conjunto de cursos conferidos à mão (com interrupção, semanal, abandono, óbito) como teste de cada fórmula? |
| 3 | addendum, regra de interrupção: "Convém compartilhar a mesma função de contagem de dias úteis" com a Ficha Virtual (`_INTERVALO_ATENCAO = 3`), mais FR-6 "calendário de feriados configurável" | 4 | importante | Se a função for compartilhada e passar a descontar feriados, a faixa âmbar de intervalos da Ficha Virtual muda de comportamento, e o PRD não diz isso. A mudança na Ficha Virtual (e em qualquer impresso que use essa contagem) é aceita? Se for, onde fica escrita? |
| 4 | FR-5: "`[SUPOSIÇÃO: 30 dias corridos sem fração com sessões restantes]`" | 6 | importante | O prazo de 30 dias decide quem vira candidato a abandono e não cita referência nem processo do serviço. De onde vem esse limiar? Ele fica na ficha técnica como parâmetro que o físico aprova (FR-17)? |
| 5 | FR-6: "Regime semanal: interrupção é pausa maior que 7 dias corridos mais 3 dias úteis. `[SUPOSIÇÃO]`" | 6 | importante | O limiar do regime semanal não tem origem (literatura ou derivação do serviço). Qual é a referência? Enquanto não houver uma, a taxa de interrupção dos cursos semanais aparece como oficial ou com aviso? |
| 6 | FR-6: "Sem ele, vem da pausa mediana observada no curso, e a lista de origem diz que a frequência foi inferida" | 1 | importante | Isso é valor presumido por parecença. Um curso diário com interrupções longas pode ter mediana alta, ser inferido como semanal e esconder a interrupção que deveria contar. O curso sem `FractionPattern` deve ficar fora do indicador, como "frequência desconhecida"? Ou a inferência é aceita, e com que salvaguarda? |
| 7 | FR-12: "Sessões canceladas pelo serviço … não contam como falta. `[SUPOSIÇÃO: o status do agendamento permite distinguir; a mapear]`" | 1 | importante | Se o status não distinguir, o cancelamento pelo serviço entra como falta do paciente. Enquanto o mapeamento não confirmar o status, o indicador de faltas fica vazio, com aviso de que falta a fonte? |
| 8 | FR-15: "compara à meta ESGO/ESTRO de pelo menos 90%" e "Enquanto o recurso … da braquiterapia não estiver mapeado, o indicador mede só a teleterapia e diz isso" | 6 / 1 | importante | Medir só a teleterapia e comparar com a meta de ≤ 50 dias (que inclui a braquiterapia) produz um "atinge a meta" falso. Enquanto a braquiterapia não estiver mapeada, a comparação com a meta (e qualquer veredito) é suprimida? A meta ESGO/ESTRO foi adotada pelo serviço, ou fica como referência sem reprovar? |
| 9 | FR-19: "O PDF sai sem nomes de pacientes, só com os agregados. `[SUPOSIÇÃO: a lista de origem não vai para o PDF]`" | 7 | importante | A ausência de dado identificável no PDF, que vai para fora do serviço (vigilância), está como suposição, e não como requisito. Também não há regra para recortes com poucos casos: num recorte por médico, sítio ou convênio, "1 curso interrompido" pode identificar a paciente. Isso vira requisito? Há um mínimo de casos por célula no PDF? |
| 10 | §5: "O que ele grava (aprovação de definição, classificação de encerramento, conferência) fica no próprio ISOCENTRO, ao lado do app"; FR-22 | 7 | importante | A classificação de encerramento associa curso e paciente a "abandono" e a nome de quem classificou. O `escopo.md` só prevê "ao lado do app" para configuração e índices. Onde exatamente ficam esses registros? É garantido que ficam fora do repositório e de logs, e quem acessa? |
| 11 | NFR-1: "O mês fechado é calculado uma vez e reaproveitado"; FR-1: "Aberta em qualquer dia de outubro, a aba mostra setembro" | 1 / 3 | importante | Se o cálculo rodar antes de a carga do data warehouse trazer as frações dos últimos dias do mês, um número incompleto fica guardado como oficial. Qual é a condição para considerar o mês fechado (data da última carga do `variandw`)? A tela e o PDF mostram a data da carga usada, além da data do cálculo? |
| 12 | FR-21: "a aba mostra a última leitura com a data dela"; addendum: "três degraus (banco → espelho → relatório)" | 3 | observação | O FR-21 anuncia a data, mas não diz o degrau (espelho ou relatório exportado), e o FR-19 não diz se o PDF registra o degrau. A tela e o PDF devem nomear o degrau usado? |
| 13 | FR-17: "O físico responsável aprova…" e "Só usuários com o papel de administrador ou físico podem aprovar"; FR-20: conferência registrada "pelo administrador" | 8 | observação | Um administrador que não é físico poderia aprovar uma definição clínica ou tirar a faixa EXPERIMENTAL. A aprovação (FR-17) e a classificação (FR-22) ficam restritas ao físico responsável? |
| 14 | FR-7 / FR-13: atividades "TOMO-DUO / TOMO-ANA" e "1a Consulta" na configuração do serviço | 1 | observação | O mapeamento mostra variantes de nome por unidade (ex.: "Agendar Paciente CEL", "Agendar Paciente BET"). O casamento da atividade é por código exato ou por nome? Uma atividade parecida, mas não configurada, fica de fora e é anunciada? |
| 15 | FR-10: "calcula a ocupação contra a capacidade configurada de cada máquina" | 5 | observação | A capacidade é ligada à máquina pelo identificador do ARIA (`DimMachine`) ou pelo nome (6EX, VitalBeam, 600CD, TB Universitario)? Uma máquina renomeada ou nova fica como "capacidade não configurada", sem herdar a capacidade de outra por parecença? |
| 16 | FR-5: "Óbito registrado no cadastro do paciente exclui o curso automaticamente" | 1 | observação | O PRD não liga a data do óbito à parada do curso. Um óbito registrado meses depois de um abandono real tira o curso do abandono. A exclusão exige que `PatientDeathDate` caia dentro de uma janela após a última fração? Qual janela? |

## Total

**Achados bloqueantes: 0.** Importantes: 11. Observações: 5.
