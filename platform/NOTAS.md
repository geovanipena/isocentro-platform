# Notas de trabalho

Checkpoint do que está em andamento, para uma queda de conexão custar
minutos e não a sessão. Atualizar **antes** de cada etapa longa e ao fim
dela.

Este arquivo é **curto de propósito**: tem as seções vivas e um **índice** do
resto. A história completa está em `notas/AAAA-MM.md` (byte a byte, nada
resumido) e as armadilhas saíram para o `ARMADILHAS.md`, que é permanente.
Em 08/09/2026 este arquivo tinha **7.873 linhas e 409 KB** — ninguém o lia
inteiro, nem eu, e nota que não se lê é nota que envelhece sem ser
questionada. Foi assim que nasceram os quatro registros vencidos daquele dia.

**Ao fechar uma etapa**: a seção nova entra aqui, no topo. Quando ela deixa
de ser o que está em andamento, **desce** para o `notas/AAAA-MM.md` do mês em
que foi escrita — mover, não resumir — e ganha uma linha no índice. Meta:
este arquivo caber numa leitura, umas 400 linhas.

---

> **RESPOSTA SEMPRE EM PORTUGUÊS DO BRASIL — inclusive o resumo final.** O
> usuário corrigiu isso cinco vezes; a última, em 29/09/2026, foi justamente o
> recado de fim de trabalho que saiu em inglês depois de uma sessão longa.
> Antes de mandar QUALQUER mensagem, conferir o idioma.

> **Desde 15/10/2026 o app se chama ISOCENTRO.** Radioteraficha, ficha-py e
> SGQ-RT são o mesmo sistema com os nomes antigos: o que está escrito antes
> desta data (aqui embaixo, em `notas/` e nas pesquisas datadas de
> `docs/planejamento/`) fica com o nome da época, de propósito.

## Revisão do fluxo de trabalho (29/10/2026)

Pedido do usuário depois da cascata e da suíte travada: "interação mais
inteligente e otimizada, só para decisões importantes — faça o necessário".

Feito:
- **Quando perguntar**: regra única no `CLAUDE.md` (6 casos; o resto se
  decide pela recomendada e se relata) e na memória `quando-perguntar`.
- **Bastidores versionados**: `.claude/hooks`, `commands`, `skills` no git
  (`settings.json` e `estado/` seguem fora: caminhos desta máquina);
  `tests/test_ganchos.py` roda cada gancho com o payload real em
  `ISOCENTRO_GANCHO_SEM_EFEITO` e confere espera interna < limite do
  gancho no `settings.json`.
- **Abertura**: manutenção em segundo plano (placar na seguinte); avisa
  variável `ISOCENTRO_*` mudada depois que o VS Code abriu; sobe o
  PostgreSQL local se estiver fora.
- **`tools/suite.py` com vigia** (contrato do robô mantido): teste >180 s
  vira "TRAVOU em <teste> (linha)". `/pronto` usa ela; `/fechar` ganhou
  "spec em dia" e "caminho do usuário".
- Spec Documentação CAP-10: edição pela aba PPR registrada (grava pelo
  dono; físico e admin provisórios até R-19/R-78).

**PRÓXIMA FRENTE — combinada para 30/10/2026, a PRIMEIRA da sessão:**
enxugar `ARMADILHAS.md` e `CLAUDE.md` (item 7 da revisão). Critério: o que
já tem trava em código vira uma linha apontando para ela; o que só existe
em texto ganha trava ou sai.

## PPR vivo: esqueleto da montagem no módulo Documentação (28/10/2026)

Decisão do usuário: o PPR é construído DENTRO do ISOCENTRO e é vivo, e cada
módulo guarda as suas seções (dado + texto); a Documentação só monta. Specs,
AD-41 e frentes R-84/R-85 em fa68f31; mapa em
`docs/planejamento/sistema-global/ppr-vivo-mapa-2026-10-28.md`.

Feito (layout aceito pelo usuário antes de editar):
- `dominio/ppr.py`: os 23 capítulos + Anexos com o módulo dono; `situacoes`
  pergunta a cada fachada (nenhuma existe ainda → tudo "sem dado");
  `motivo_para_nao_emitir` (por clínica; capítulo faltando).
- `interface/documentacao_tela.py`: abas PPR e Vencimentos (em construção);
  tabela # | Capítulo | Módulo dono | Situação; "Emitir PPR" sólido e
  apagado com o motivo no tooltip. Torre: Documentação `pronto=True`.
- Testes: `test_ppr.py` (9) + 2 em `test_torre.py`. Suíte 2.649 em ordem
  aleatória OK (semente 959107366). No shell do Claude Code, sem
  `PYTHONIOENCODING=utf-8`, 7 testes de tools (mapear_indicadores, robo,
  sondar_dicom) dão UnicodeEncodeError cp1252 — falham igual sem a mudança.

Falta: as fachadas dos módulos (R-84 GQ, R-85 demais + montagem).

**Plano para emitir (aceito 28/10):** 1 conteúdo (extrair dos 3 PPRs vigentes
para `Documents\isocentro\servico\<CLINICA>\ppr\semente.json`, FORA do git —
tem nome e CPF da equipe); 2 banco (migração 0004 + fachadas + importador);
3 papel (gerador em `papel/`, conferido contra o PPR CEL mai/26); 4 emissão
assinada (R-19). Até a R-19: PDF de RASCUNHO com marca d'água.
- Planta real em `dominio/ppr.py` (5588d5b): CEL 23 caps e anexos A–R, DUO e
  BET 22 e A–Q (rejeitos só com fonte radioativa); anexos em ordem própria.
- Fontes copiadas para `servico/<C>/ppr/fonte/`: CEL = JSON do ppr-streamlit
  e caps LaTeX; BET e DUO = PDF (LaTeX, mesmo molde). Páginas de pessoas
  (anexos A, B, C, ASO) só por script com saída mascarada.
- **Etapa 1 FEITA (6c3efde, e7348ac):** `tools/semente_ppr.py <CEL|BET|DUO>`
  grava `servico/<C>/ppr/semente.json` (45 partes da planta, cada uma com
  dono, texto vigente, documentos de origem e fonte; tabelas viram `dados`
  do módulo dono). CEL do JSON (anexos copiados de `Downloads\PPR\anexos\PDFs`
  sem ASOS; certificados pela pasta), BET/DUO do PDF (documento embutido =
  faixa de páginas do PDF vigente). Menção a anexo no texto = `{anexo:chave}`.
  Conferido contra o PPR: equipamentos, TPS, fontes, câmaras, instrumentos,
  fantomas, detectores, monitores, testes (DUO 16/26/17, BET 16/25/17).
  A conferir pelo usuário: CEL sem texto nos caps 12/12.1–12.3 (JSON vazio);
  enfermagem da DUO parece ter caído em "demais"; ASO da BET sem data do
  exame (a tabela só tem validade — não deduzir).
- **Etapa 2 FEITA (28/10, pedido "os textos ainda não aparecem"):** o
  usuário escolheu a etapa 2 completa, com o texto num painel EMBAIXO da
  tabela. `migracoes/0004_ppr.sql`: `ppr_parte` e `ppr_dado` em `nucleo`
  (Fundação), `qualidade`, `plano`, `seguranca`, `documentacao`, só-INSERT
  pelo `nucleo.gravar`; `ppr_dado` é PROVISÓRIO até cada módulo ter a tabela
  de verdade (GQ: R-84), com corte pela AD-37. `adaptadores/postgres/ppr.py`
  (porta, fachadas, `ler_do_ambiente`); `tools/importar_ppr.py <C> --conexao
  --quem` (roda de novo sem duplicar: igual pula, diferente entra com
  `substitui`). Decisões: vigente = registro que ninguém substitui (AD-5),
  não "o último"; chave gravada = a da semente (`anexo/<chave>`, SEVRRA
  `anexo/gq_sevrra`), via `ppr.chave_gravada`; condições da clínica = o
  `ppr_dado` "condicoes" da GQ; a tela lê por `ISOCENTRO_PG_APP`
  (PROVISÓRIA até a R-19); "Emitir" segue apagado (não há gerador).
  Banco de dev `isocentro` (5433) criado, na versão 4, com as 3 clínicas
  importadas (CEL 67, BET 59, DUO 59 registros). **Para ver no app:**
  definir `ISOCENTRO_PG_APP=host=localhost port=5433 user=postgres
  dbname=isocentro` como variável de usuário (FEITO nesta estação, 28/10) e
  REABRIR o VS Code: o app aberto por ele herda o ambiente antigo — foi por
  isso que o usuário viu a aba sem texto na primeira volta.
  Seletor de clínica PRÓPRIO da aba (pedido 28/10; layout aceito): combo na
  faixa de cima, abre na clínica do Início ou, com "Todas", na CEL; trocar
  ali não muda o Início. A tela não lê o banco ao nascer.
  Texto EDITÁVEL na aba (pedido 28/10; layout e "físico e admin" aceitos):
  editor POR PARTE (botões "Capítulo N / N.k / Anexo X / SEVRRA" no
  `torre.SeletorDeClinica`), Desfazer + Salvar (contorno). Salvar =
  `pg_ppr.gravar_texto`: grava pelo módulo DONO, `substitui` a vigente,
  mantém os documentos, fonte "edição no ISOCENTRO sobre <origem>"; versão
  já substituída por outra estação é recusada pelo banco. Na edição a
  menção fica `{anexo:x}`; troca de linha/parte/clínica com edição
  pendente pergunta. Esbarra na spec ("só o dono altera" na tela do dono):
  a tela é da Documentação, mas a gravação continua sendo do dono.
  Próximo: etapa 3, gerador em
  `papel/ppr_pdf.py` no leiaute do ppr-streamlit, RASCUNHO com marca d'água.
R-15 (ASO sem IA) segue no ramo local `r15-aso-local` do ppr-streamlit,
sem push; o Streamlit fica como está.

## O que está aberto

As seções que se declaram abertas. **A marca é do dia em que foi escrita** —
conferir antes de agir: das quatro notas vencidas de 08/09/2026, duas diziam
aberto o que já tinha fechado.

- 28/10 — [EM ANDAMENTO: R-23, porte PySide6 e shell Torre (28/10/2026)](notas/2026-10.md) — desceu sozinha em 28/10/2026; conferir se ainda está aberta
- 26/10 — [EM ANDAMENTO: decisões do físico → update das specs (26/10/2026)](notas/2026-10.md) — desceu sozinha em 26/10/2026; conferir se ainda está aberta
- 23/10 — [ESTACIONADA: R-52 — PDFs de referência página a página (robô, 23/10/2026)](notas/2026-10.md) — desceu sozinha em 23/10/2026; conferir se ainda está aberta
- 22/10 — [EM ANDAMENTO: R-58 — dividir `dicom/` (22/10/2026)](notas/2026-10.md) — desceu sozinha em 23/10/2026; conferir se ainda está aberta
- 22/10 — [EM ANDAMENTO: IA no ISOCENTRO — análise e frentes (22/10/2026)](notas/2026-10.md) — desceu sozinha em 22/10/2026; conferir se ainda está aberta
- 22/10 — [EM ANDAMENTO: espinha — módulos genéricos e específicos (Update 22/10/2026)](notas/2026-10.md) — desceu sozinha em 22/10/2026; conferir se ainda está aberta
- 20/10 — [EM ANDAMENTO: planejamento do sistema global fechado](notas/2026-10.md) — desceu sozinha em 22/10/2026; conferir se ainda está aberta
- 14/09 — [A varredura sem o app aberto](notas/2026-09.md) — **fechada no código, sem uso real**: nenhuma rodada agendada existiu, o exe só respondeu ao `--conferir` nesta máquina. Depende de fora do código: as 4 chaves DICOM, a `concentradora` (desde 18/09) e a `RAIZ_SIMULACOES` no `config_servico` do `clinica-python01`, e a conta de domínio da Tarefa Agendada
- 11/09 — [A ficha temporária na Fichinha: as quatro frentes](notas/2026-09.md) — **escritas e verdes, nenhuma exercitada com caso real**: nenhum caso foi preparado, liberado ou limpo fora de bancada
- 11/09 — [A rodada de 11/09, 11:14: a recontagem compara grandezas diferentes (ESTACIONADA)](notas/2026-09.md) — **não gravar `LISTA_VERIFICADA_EM`** enquanto ela estiver aberta
- 02/09 — [Exportação automática de imagem e plano (EM ABERTO)](notas/2026-09.md)
- 19/08 — [Estado (5) — a aba vira PAINEL, não busca (EM ANDAMENTO)](notas/2026-08.md) — **o bloqueio caiu em 10/09**: a permissão existe
- 19/08 — [Estado (4) — aba Radioterapeuta (TELA PRONTA, SQL BLOQUEADO)](notas/2026-08.md) — **o bloqueio caiu em 10/09**: a permissão existe

- 28/07 — **Soma de dose por grupos e corte no modo Soma** — estava só na memória do Claude; entrou aqui em 22/10/2026 sem reconferir:

  Trabalho iniciado em 28/07/2026 na branch `v6`, pausado pelo usuário ("depois continuamos esse raciocínio"). Já entregue e testado: pág. 2 dividida em blocos quando os campos somados passam de 21, e grupos de soma de dose na pág. 3 (chips "Somar:" no Agendamento).

  Duas pendências:

  1. **Corte errado no modo Soma.** O usuário relata que o botão 👁 Visualizar mostra o corte do isocentro enquanto o Gerar sai com o corte escolhido. Não achei divergência no código: os dois passam por `_gerar_pdf` → `_construir_pdf` e produzem os mesmos bytes. Corrigi um defeito real de perto (`_recalcular_soma` recentrava os cortes a cada Aplicar do agendamento). **Teste combinado e ainda não respondido: clicar Visualizar duas vezes seguidas sem tocar em nada** — se a 2ª sair certa, era o recentramento (já corrigido); se as duas saírem no isocentro com o Gerar certo, o problema está no leitor de PDF abrindo arquivo antigo, não na geração.

  2. **Grupos valendo também para cortes+DVH.** O usuário escolheu "grupos explícitos no Agendamento" valendo para a página combinada E para a dose. Só a dose foi feita. Estender exige generalizar `modo_ficha` (individual/soma/personalizado = 1 grupo + avulsos) para N grupos, com uma página de cortes+DVH por grupo — e decidir o que o viewer mostra, já que ele só combina uma visão por vez.

As duas de 19/08 paravam em "consulta que só roda com identidade de rede". **Em
10/09/2026 isso deixou de ser verdade, em dois degraus:**

1. **a permissão existe** — a estação da clínica lê `FactTreatmentHistory`,
   `DimMachine` e `DimActivity`, medido com `SELECT TOP 1` em cada;
2. **a estrutura foi medida** — o `INFORMATION_SCHEMA` das três tabelas veio
   por comando colado no prompt da estação (metadado puro, nenhuma linha de
   paciente), e confirma que o SQL já escrito se apoia em colunas que existem.

`tratamento_db.LISTA_VERIFICADA_EM` continua `""`, e agora por um motivo só,
que não é mais o tempo: **falta conferir o RESULTADO**. O TEMPO foi medido em
10/09/2026 na estação `198.51.100.58` — 0,19 s, 0,10 s e 0,18 s contra o limite
de 6 s (ver o item 3 de "EM ABERTO — a ida aos dois ambientes", no `notas/2026-09.md`) —, e
com essa margem a lista não precisa
sair da thread da interface. **A rodada do `--consulta` aconteceu em
10/09/2026, 18:41** ("A conferência da LISTA: `--consulta` no
`mapear_tratamento`", 10/09): o tempo da FUNÇÃO inteira, com as seis
consultas, deu **0,40 s**, e a janela trouxe **165** cursos. O que sobra
é uma coisa só, e é do usuário: **olhar os 165 contra o ARIA** —
os itens (a)/(b)/(c)/(d) daquela seção.

O ⚡ falso, que era o segundo item, **fechou em 11/09 por decisão do
usuário**: a marca de interrupção saiu da lista ("se o tratamento foi
realizado é o que interessa"). Ver "O ⚡ saiu da lista", no
`notas/2026-09.md`.

**Antes de agir, reconferir no código**: a consulta POR PACIENTE está
verificada desde 20/08 (`VERIFICADO_EM`), e as seções de 19/08 foram escritas
quando nada disso valia. A marca é do dia em que foram escritas.

A frente da **exportação automática** deixou de estar parada na clínica em
10/09: a TI cadastrou o AE chamador, o C-GET foi medido e **não existe** neste
daemon, e o C-MOVE entregou. O que falta é **nosso** — os itens 1, 2 e 4 da
seção "a ida aos dois ambientes", no `notas/2026-09.md`, e o detalhe em "O receptor existe" e
"O cadastro pegou" de 10/09, no `notas/2026-09.md`. (Até 11/09 esta linha
dizia "ver a seção do topo", que já era outra frente.) **Em 11/09 a CT
entrou no `trazer` e as doses passaram a vir por série** — medido no ARIA:
205 arquivos, 0 falha ("A CT entra no conjunto do `trazer`", no
`notas/2026-09.md`). ~~O que sobra de código é o `sondar_exportacao.bat`~~ —
**FECHADO em 11/09** ("O texto da sondagem deixa de perguntar o que já foi
respondido", 11/09): da exportação, não sobra código; sobra
rodada (itens 1 e 2) e decisão (item 4).

---

## Índice do que já foi (194 seções)

Uma linha por seção arquivada, para o `grep` achar assunto **e** arquivo de
uma vez: `grep -i ssd NOTAS.md`. É o mapa que substitui a leitura do
histórico inteiro.


### `notas/2026-10.md` — outubro (34 seções)

- 28/10 — [EM ANDAMENTO: R-23, porte PySide6 e shell Torre (28/10/2026)](notas/2026-10.md)
- 28/10 — [FEITO: R-21, alerta, assinatura, concentradora e âncora (28/10/2026)](notas/2026-10.md)
- 27/10 — [FEITO: R-20, motor de verificação gravando no PostgreSQL (27/10/2026)](notas/2026-10.md)
- 27/10 — [FEITO: R-18, núcleo: esquema, `nucleo.gravar` e log encadeado (27/10/2026)](notas/2026-10.md)
- 26/10 — [FEITO: R-82, origem `provisoria` da tolerância (26/10/2026, robô)](notas/2026-10.md)
- 26/10 — [FEITO: mapa de épicos sobre a fila (26/10/2026)](notas/2026-10.md)
- 26/10 — [EM ANDAMENTO: decisões do físico → update das specs (26/10/2026)](notas/2026-10.md)
- 23/10 — [FEITO: robô — frente só de documento, conhecimento e varredura (23/10/2026)](notas/2026-10.md)
- 23/10 — [FEITO: R-76 — esquema v1 do JSON ESAPI e validação (robô, 23/10/2026)](notas/2026-10.md)
- 23/10 — [FEITO: R-75 — questionário do físico para o módulo Radioteraficha (robô, 23/10/2026)](notas/2026-10.md)
- 23/10 — [FEITO: R-74 — questionário do físico para o módulo Documentação (robô, 23/10/2026)](notas/2026-10.md)
- 23/10 — [FEITO: R-73 — questionário do físico para o módulo Segurança (robô, 23/10/2026)](notas/2026-10.md)
- 23/10 — [FEITO: R-72 — questionário do físico para o módulo GQ (robô, 23/10/2026)](notas/2026-10.md)
- 23/10 — [FEITO: R-71 — questionário do físico para o módulo Plano (robô, 23/10/2026)](notas/2026-10.md)
- 23/10 — [FEITO: R-77 — contrato puro do motor de verificação (robô, 23/10/2026)](notas/2026-10.md)
- 23/10 — [FEITO: R-59 — raio de revisão a partir do diff (robô, 23/10/2026)](notas/2026-10.md)
- 23/10 — [ESTACIONADA: R-52 — PDFs de referência página a página (robô, 23/10/2026)](notas/2026-10.md)
- 23/10 — [FEITO: R-24 — teste de arquitetura (robô, 23/10/2026)](notas/2026-10.md)
- 22/10 — [EM ANDAMENTO: R-58 — dividir `dicom/` (22/10/2026)](notas/2026-10.md)
- 22/10 — [FEITO: memória da carga e o DVH intermitente (22/10/2026)](notas/2026-10.md)
- 22/10 — [FEITO: R-69 — pillow e pypdf (22/10/2026)](notas/2026-10.md)
- 22/10 — [FEITO: R-70 — Notas da capa em várias linhas (22/10/2026)](notas/2026-10.md)
- 22/10 — [FEITO: R-62 margem CTV→PTV (robô, 22/10/2026)](notas/2026-10.md)
- 22/10 — [EM ANDAMENTO: IA no ISOCENTRO — análise e frentes (22/10/2026)](notas/2026-10.md)
- 22/10 — [FEITO: cinco frentes de bancada](notas/2026-10.md)
- 22/10 — [FEITO: extensões e skills entram na manutenção semanal](notas/2026-10.md)
- 22/10 — [EM ANDAMENTO: espinha — módulos genéricos e específicos (Update 22/10/2026)](notas/2026-10.md)
- 20/10 — [EM ANDAMENTO: planejamento do sistema global fechado](notas/2026-10.md)
- 15/10 — [EM ANDAMENTO: o app passa a se chamar ISOCENTRO](notas/2026-10.md)
- 15/10 — [EM ANDAMENTO: reorganização da pasta central](notas/2026-10.md)
- 13/10 — [EM ANDAMENTO: BMad como camada de planejamento](notas/2026-10.md)
- 13/10 — [EM ANDAMENTO: protótipo da aba Radioteradados](notas/2026-10.md)
- 13/10 — [EM ANDAMENTO: quatro ajustes da análise BMad (Mary)](notas/2026-10.md)
- 07/10 — [EM ANDAMENTO: fluidez da demonstração — revisão completa](notas/2026-10.md)

### `notas/2026-09.md` — setembro (94 seções)

- 29/09 — [Correção de rumo: a atividade de parada ainda vai ser CRIADA](notas/2026-09.md)
- 28/09 — [Conferência das 3 hipóteses do Índice de Disponibilidade — estação real](notas/2026-09.md)
- 28/09 — [Taxa de Ocupação e Índice de Disponibilidade](notas/2026-09.md)
- 28/09 — ["Uma máquina só", além dos pares fixos](notas/2026-09.md)
- 28/09 — [Quatro indicadores novos na Agenda](notas/2026-09.md)
- 28/09 — [Nome do período escolhido aparece na Agenda](notas/2026-09.md)
- 24/09 — [Painel "em tratamento" vazio no banco local](notas/2026-09.md)
- 23/09 — [Ficha Virtual: quadro cortado e pop-up de posicionamento](notas/2026-09.md)
- 23/09 — [Aba Agenda, e a faixa reordenada](notas/2026-09.md)
- 23/09 — [Grupo Médico que segue a pessoa, e acesso único (EM ANDAMENTO)](notas/2026-09.md)
- 23/09 — [Prescrição manda na ficha — quatro frentes (EM ANDAMENTO)](notas/2026-09.md)
- 22/09 — [v8 — a Fichinha vira painel de listas (EM ANDAMENTO)](notas/2026-09.md)
- 22/09 — [Grupo Médico: a agenda em conjunto na Ficha Virtual](notas/2026-09.md)
- 18/09 — [Só a concentradora varre: a chave `concentradora`](notas/2026-09.md)
- 18/09 — [Alta sem imagens na ficha recarregada do JSON](notas/2026-09.md)
- 10/09 — [EM ABERTO — a ida aos dois ambientes](notas/2026-09.md)
- 29/09 — [Demonstração com o TRABALHO JÁ FEITO (29/09 a 07/10)](notas/2026-09.md)
- 29/09 — [Servidor LOCAL completo para demonstração fora da rede](notas/2026-09.md)
- 17/09 — [Proposta de divisão do `tratamento.py` (R-12)](notas/2026-09.md)
- 17/09 — [`test_padrao_visual` religado, e a triagem dos buracos](notas/2026-09.md)
- 16/09 — [R-06: cortes 1 e 6](notas/2026-09.md)
- 16/09 — [R-06: corte 5, capa e simulação](notas/2026-09.md)
- 16/09 — [R-06: corte 4, portão da geração](notas/2026-09.md)
- 16/09 — [R-06: divisão do `gui.py`, cortes 2 e 3](notas/2026-09.md)
- 16/09 — [R-05: proposta de divisão do `gui.py` (robô)](notas/2026-09.md)
- 15/09 — [R-04: fim de linha uniforme fora das pastas travadas (robô)](notas/2026-09.md)
- 15/09 — [R-03: roteiro de instalação da concentradora (robô)](notas/2026-09.md)
- 15/09 — [R-01: o "PARA A TI" do checkup pede o AE que já existe (robô)](notas/2026-09.md)
- 15/09 — [R-00: o teste da Capa que só passava nesta estação (robô)](notas/2026-09.md)
- 15/09 — [O robô medido pelas 7 sessões de 15/09: limite, interrupção e recusas](notas/2026-09.md)
- 15/09 — [A otimização do jeito de trabalhar: cache, suíte e custo por etapa](notas/2026-09.md)
- 15/09 — [O robô e o destino](notas/2026-09.md)
- 15/09 — [A recusa pelo tipo, não pelo relógio](notas/2026-09.md)
- 15/09 — [A porta fechada que não recusa na hora](notas/2026-09.md)
- 14/09 — [Os cinco que esperavam a rede](notas/2026-09.md)
- 14/09 — [Os 4,6 minutos eram dois testes esperando](notas/2026-09.md)
- 14/09 — [A poda do `NOTAS.md`: o ponteiro que não sobrevive à mudança de arquivo](notas/2026-09.md)
- 14/09 — [O layout da varredura: as três instruções que se contradiziam](notas/2026-09.md)
- 14/09 — [A ida à concentradora: dois achados antes de qualquer comando](notas/2026-09.md)
- 14/09 — [A varredura sem o app aberto: exe de console, trava entre processos e o degrau de serviço do DICOM](notas/2026-09.md)
- 11/09 — [FASE NOVA: a ficha temporária pronta na Fichinha — as quatro frentes](notas/2026-09.md)
- 11/09 — [A rodada de 11/09, 11:14: a recontagem compara grandezas diferentes](notas/2026-09.md)
- 11/09 — [O texto da sondagem deixa de perguntar o que já foi respondido](notas/2026-09.md)
- 11/09 — [A CT entra no conjunto do `trazer`, e as doses vêm por série](notas/2026-09.md)
- 11/09 — [O ⚡ saiu da lista em tratamento](notas/2026-09.md)
- 10/09 — [Uma ida só: o checkup completo dos DOIS ambientes](notas/2026-09.md)
- 10/09 — [A conferência da LISTA: `--consulta` no `mapear_tratamento`](notas/2026-09.md)
- 10/09 — [O receptor existe: o produto deixou de chamar o C-GET morto](notas/2026-09.md)
- 10/09 — [O cadastro pegou, o C-GET morreu medido, e o que falta é nosso](notas/2026-09.md)
- 10/09 — [O AE Title saiu pela METADE, e o app não sabia dizer isso](notas/2026-09.md)
- 10/09 — [A varredura de identidade, e os 13 que ela achou](notas/2026-09.md)
- 09/09 — [A raiz vira pacote: 60 módulos soltos entram em `radioteraficha/`](notas/2026-09.md)
- 09/09 — [O empacotamento estava quebrado, e ninguém sabia](notas/2026-09.md)
- 09/09 — [A raiz deixa de ser a pasta de saída de todo mundo](notas/2026-09.md)
- 09/09 — [O `capa_db` passa a enxergar o nome novo da variável](notas/2026-09.md)
- 09/09 — [A primeira manutenção virou trabalho: 4 achados, e um deles mentia](notas/2026-09.md)
- 09/09 — [A bancada também envelhece: manutenção do ambiente](notas/2026-09.md)
- 08/09 — [O editor deixa de ser configuração desta máquina](notas/2026-09.md)
- 08/09 — [Os três que faltavam: medir o PDF, avisar a mim, registrar o uso](notas/2026-09.md)
- 08/09 — [A rotina de sessão virou automática: quatro ganchos e uma barra](notas/2026-09.md)
- 08/09 — [O ambiente custava 6,3 mil tokens por turno, e um terço não era usado](notas/2026-09.md)
- 08/09 — [O NOTAS virou três arquivos, e o teste virou recorte](notas/2026-09.md)
- 08/09 — [Onde a exportação parou, e quatro notas vencidas](notas/2026-09.md)
- 08/09 — [Índice em memória da varredura de simulações](notas/2026-09.md)
- 08/09 — [A aba Total saiu da faixa: quem entra na bancada é a Edição](notas/2026-09.md)
- 04/09 — [Segunda revisão: a sincronia pendia da NAVEGAÇÃO](notas/2026-09.md)
- 04/09 — [A revisão da sincronia achou 8, e a pior era minha](notas/2026-09.md)
- 04/09 — [Um paciente por vez: a busca no servidor puxa a bancada](notas/2026-09.md)
- 04/09 — [Contracapa: 3 linhas de acessório no lugar de 17 pt de foto (MUDA O PAPEL)](notas/2026-09.md)
- 04/09 — [O convênio sai direto do servidor; SUS sem número vira ALERTA](notas/2026-09.md)
- 04/09 — ["Abrir pasta do paciente" deixa de perguntar o que já se sabe](notas/2026-09.md)
- 04/09 — [DIBH saía como "Amplitude" na ficha (MUDA O PAPEL)](notas/2026-09.md)
- 04/09 — [A revisão pegou três, e a primeira era minha regressão](notas/2026-09.md)
- 04/09 — [A pasta da exportação vira decisão de admin](notas/2026-09.md)
- 04/09 — [A descoberta ACABOU: 51404, AE `ARIA`](notas/2026-09.md)
- 04/09 — [As regras de FIREWALL nomearam cada porta](notas/2026-09.md)
- 04/09 — [A ida ao servidor se perdeu num nome de arquivo](notas/2026-09.md)
- 04/09 — [O AE errado é o DO ARIA, e isso se resolve daqui](notas/2026-09.md)
- 04/09 — [A varredura rodou: o caminho de rede está inteiro](notas/2026-09.md)
- 04/09 — [Clicar no .bat tinha de levar a algum lugar](notas/2026-09.md)
- 04/09 — [O SRVARIADB respondeu, e derrubou o palpite da porta](notas/2026-09.md)
- 04/09 — [Descobrir a configuração DICOM no servidor](notas/2026-09.md)
- 04/09 — [A sonda do DICOM, pronta para quando o AE Title sair](notas/2026-09.md)
- 04/09 — [A conferência rodou, e reprovou: o curso de QA](notas/2026-09.md)
- 04/09 — [A foto que sumia sem recado (FECHADO)](notas/2026-09.md)
- 04/09 — [O relógio da varredura](notas/2026-09.md)
- 04/09 — [O curso errado, e o relatório que deixa ver a ausência](notas/2026-09.md)
- 02/09 — [Exportação automática de imagem e plano (EM ABERTO)](notas/2026-09.md)
- 01/09 — [Atividades do ARIA: descobrir antes de consultar](notas/2026-09.md)
- 01/09 — [Banco LOCAL: simular o data warehouse sem servidor](notas/2026-09.md)
- 01/09 — [A tela de fracionamento travava o programa (FECHADO)](notas/2026-09.md)
- 02/09 — [Aba Qualidade: a unidade errada e a tela poluída](notas/2026-09.md)
- 02/09 — [O padrão de tela virou trava](notas/2026-09.md)
- 04/09 — [Pendências antigas — as três, fechadas](notas/2026-09.md)

### `notas/2026-08.md` — agosto (66 seções)

- 31/08 — [Identificador de paciente virou pseudônimo](notas/2026-08.md)
- 31/08 — [Cálculo paralelo (TG-219) — feito, e as duas travas](notas/2026-08.md)
- 31/08 — [A aba Qualidade — feita, e o que ela ensinou](notas/2026-08.md)
- 31/08 — [A régua estava quebrada, e ninguém sabia](notas/2026-08.md)
- 31/08 — [Fechar é fechar em todas, e o que a revisão pegou](notas/2026-08.md)
- 31/08 — [A máquina, e a ordem dos campos](notas/2026-08.md)
- 31/08 — [O convênio responde pelo SUS, e o portal recupera o nome](notas/2026-08.md)
- 31/08 — [O ciclo de 31/08/2026 — os cinco itens, e onde cada um está escrito](notas/2026-08.md)
- 27/08 — [A régua do papel virou ferramenta](notas/2026-08.md)
- 31/08 — [O diálogo de escolha de paciente, conferido na tela real](notas/2026-08.md)
- 31/08 — [A divisão do `gui.py` chegou ao fim](notas/2026-08.md)
- 31/08 — [Pylance: medido, reprovado, e duas anotações corrigidas](notas/2026-08.md)
- 31/08 — [Pasta com vários pacientes virava UMA ficha](notas/2026-08.md)
- 28/08 — [RETOMAR AQUI — CUMPRIDO em 31/08/2026](notas/2026-08.md)
- 27/08 — [O `connect` sai da thread da interface](notas/2026-08.md)
- 27/08 — [Poda do NOTAS.md e o CLAUDE.md em dia](notas/2026-08.md)
- 27/08 — [A suíte caiu de 9,5 para 1,9 minutos](notas/2026-08.md)
- 27/08 — [Ferramental do agente + divisão do `gui.py`](notas/2026-08.md)
- 26/08 — [PORTÃO — CUMPRIDO em 26/08/2026](notas/2026-08.md)
- 27/08 — [a pergunta do fechamento, sem a lista de telas](notas/2026-08.md)
- 26/08 — [o seletor de PLANO, e o pop-up que não dava para ler](notas/2026-08.md)
- 26/08 — [SSD e deslocamento legíveis no pop-up de Campos](notas/2026-08.md)
- 26/08 — [as abas: nomes curtos e recorte por FUNÇÃO](notas/2026-08.md)
- 26/08 — [RESOLVIDO: o paciente novo da busca herdava o anterior](notas/2026-08.md)
- 26/08 — [sete funções de usuário, e a coluna Mesa pelo que ela é](notas/2026-08.md)
- 26/08 — [RESOLVIDO: a conexão que não voltava sem o admin](notas/2026-08.md)
- 26/08 — [a barra da Capa e o peso dos pop-ups](notas/2026-08.md)
- 26/08 — [a pasta do paciente foi para a GAVETA da inicial](notas/2026-08.md)
- 26/08 — ["Confeccionar a capa" saiu do fim do cadastro de simulação](notas/2026-08.md)
- 26/08 — [DVH: PTV do laranja para a família teal (MUDA O PAPEL)](notas/2026-08.md)
- 26/08 — [a ficha conferida num caso real](notas/2026-08.md)
- 26/08 — [ferramentas do editor: extensões, ruff e corretor (FEITO)](notas/2026-08.md)
- 25/08 — [os seis achados da revisão do código](notas/2026-08.md)
- 25/08 — [uma grafia só para o nome do paciente (FEITO)](notas/2026-08.md)
- 25/08 — [o botão "Abrir pasta do paciente" relia a pasta do paciente ANTERIOR](notas/2026-08.md)
- 24/08 — [FEITO: Checklist e Ficha Completa na Ficha Virtual](notas/2026-08.md)
- 25/08 — [a folha de portais do 600CD entrou no padrão da ficha](notas/2026-08.md)
- 25/08 — [FEITO: um padrão para os pop-ups, e atalhos](notas/2026-08.md)
- 25/08 — [fotos centradas na contracapa](notas/2026-08.md)
- 25/08 — [armadilhas pagas nesta sessão (Qt)](notas/2026-08.md)
- 22/08 — [o botão que saiu da tela, e a aba que mostrava outro paciente](notas/2026-08.md)
- 21/08 — [o vínculo nota↔plano vem do cadastro, não de adivinhação](notas/2026-08.md)
- 21/08 — [a ficha do VMAT: gantry parado, página 1 estourando, dose fora do paciente](notas/2026-08.md)
- 21/08 — [o painel: faixas, interrupção que passou, e a prescrição](notas/2026-08.md)
- 21/08 — [a lista dizia "faltam 2" para quem tinha terminado](notas/2026-08.md)
- 21/08 — [os cinco buracos que a revisão do commit 6834e3f achou](notas/2026-08.md)
- 20/08 — [mama e FSC tratam JUNTAS: a fração dobrada](notas/2026-08.md)
- 20/08 — [a aba Radioterapeuta virou **Ficha Virtual**](notas/2026-08.md)
- 20/08 — [o que o banco assina virou o NOME de quem tratou](notas/2026-08.md)
- 20/08 — [por que a clínica não conecta: DOIS DOMÍNIOS](notas/2026-08.md)
- 20/08 — [Estado — o app fechava ao clicar num paciente](notas/2026-08.md)
- 19/08 — [Estado (5) — a aba vira PAINEL, não busca (EM ANDAMENTO)](notas/2026-08.md)
- 19/08 — [Estado (4) — aba Radioterapeuta (TELA PRONTA, SQL BLOQUEADO)](notas/2026-08.md)
- 19/08 — [Estado (3) — biblioteca de notas vazia na instalação nova](notas/2026-08.md)
- 19/08 — [Estado (2) — trilha, PREPARO e DDN](notas/2026-08.md)
- 19/08 — [Estado — abertura do agendamento no fim da carga](notas/2026-08.md)
- 17/08 — [Estado — tudo implementado, suíte 834 verde](notas/2026-08.md)
- 17/08 — ["não puxa curso, CID, convênio, contato"](notas/2026-08.md)
- 17/08 — [foto do paciente anterior na capa do seguinte](notas/2026-08.md)
- 17/08 — [usabilidade da aba Capa](notas/2026-08.md)
- 17/08 — [a pasta do admin passa a valer para todo mundo](notas/2026-08.md)
- 18/08 — [leitura direta do data warehouse da Varian](notas/2026-08.md)
- 18/08 — [o banco vira a fonte; a reserva é o ESPELHO](notas/2026-08.md)
- 18/08 — [comparação banco × relatórios, 200 pacientes](notas/2026-08.md)
- 18/08 — [configuração num lugar só (Configurações → Serviço)](notas/2026-08.md)
- 19/08 — [as práticas que faltavam (itens 1,2,3,5,6)](notas/2026-08.md)
