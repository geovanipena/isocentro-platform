# Como se trabalha neste projeto

ISOCENTRO monta **documentos que vão para a sala de tratamento**: a ficha
técnica e a capa que andam grampeadas, conferidas por quem posiciona o paciente
na mesa. Um número errado no papel não é um bug de software — é um erro que
chega ao paciente. Tudo abaixo sai daí.

---

## Idioma

**Português do Brasil em tudo**: conversa, comentários, docstrings, mensagens de
tela, mensagens de commit, nomes de variável e de função. Código em inglês nesta
base é exceção herdada, não padrão a seguir.

---

## Checkpoint em `NOTAS.md` — sempre

**Antes de começar uma etapa longa e ao terminá-la**, gravar o estado em
`NOTAS.md`: o que está feito, o que falta, as decisões já tomadas e por quê.

A conexão deste projeto cai (`API Error: Connection refused` é rotina). Sem
checkpoint, a queda custa a sessão inteira; com ele, custa minutos.

**São três arquivos**, porque nota que ninguém lê inteira envelhece sem ser
questionada:

| arquivo | o quê |
|---|---|
| `NOTAS.md` | o que está **vivo** + o índice do resto. Cabe numa leitura (~400 linhas) |
| `notas/AAAA-MM.md` | a história congelada, byte a byte, nada resumido |
| `ARMADILHAS.md` | o que já custou tempo aqui. **Permanente**, não se arquiva por data |

A seção nova entra no topo do `NOTAS.md`. Quando deixa de ser o que está em
andamento, **desce** para o `notas/AAAA-MM.md` do mês em que foi escrita — mover,
não resumir — e ganha uma linha no índice. Procurar assunto é `grep -i ssd
NOTAS.md`: o índice devolve o título **e** o arquivo.

**Ao FECHAR uma pendência, voltar na seção que a abriu.** Um "EM ABERTO" que
já foi resolvido é pior que nota nenhuma: ninguém questiona o que está escrito,
e o sintoma de um registro vencido é que ele parece certo.

Não é burocracia: é o registro que sobrevive à queda.

---

**Higiene é automática, não pedido.** A abertura desce o `NOTAS.md` sozinha (`tools/notas.py`) e roda a
manutenção semanal; este arquivo tem orçamento de 360 linhas, e a abertura avisa quando passa — aí
o que é situacional muda de casa (`docs/AMBIENTE.md`, `tools/LEIAME_CLINICA.md`) na mesma sessão.

---

## Onde mora o código

Os módulos são o pacote **`isocentro/`** desde 09/09/2026; antes disso os
61 estavam soltos na raiz. A divisão é por **papel no fluxo**:

| pasta | o quê |
|---|---|
| `banco/` | de onde vem o dado clínico — os três degraus, e `capa_dados` (CSV) fica com eles |
| `dominio/` | a regra e o cálculo, sem interface nenhuma |
| `dicom/` | ler o que veio do TPS, e virar imagem |
| `papel/` | o que é IMPRESSO. Diff aqui = o papel mudou = avisar o usuário |
| `interface/` | telas e peças visuais |
| `dados/` | o que o app grava e relê dele mesmo |

Duas regras que não se descobrem lendo a pasta:

- **Caminho de arquivo vem do `isocentro/raiz.py`, nunca de `__file__`.**
  São coisas DIFERENTES: `pasta_do_app()` é onde se GRAVA (a pasta do `.exe`) e
  `pasta_assets()` é de onde se LÊ o que veio no pacote (`_internal/assets`, um
  nível abaixo). Trocar uma pela outra é a ficha sair sem logo, ou o
  `usuarios.json` nascer na pasta errada — sem erro nenhum na tela.
- **Os `.json` da raiz não são código.** São o que o app grava ao lado de si e o
  que o `migrar.ps1` migra. Não movê-los: mudariam o disco de instalações que já
  existem.

`tools/mapa.py` e os testes aceitam o **nome solto** (`mapa.py gui.py` continua
valendo): quem resolve é `tools/mapa._achar` e `tests/fontes.caminho`. Nome
ambíguo não é adivinhado — os dois listam os candidatos e param.

---

## Economia de contexto

Cada turno reenvia o contexto inteiro, **com cache**: o que não mudou se relê a
~0,1× do preço da entrada, e o que é novo se GRAVA a 2× (cache de 1 h). As
contas que valem saem daí (medidas em 15/09/2026; a conta antiga, que ignorava
o cache, está no `docs/AMBIENTE.md`):

- **O que entra é caro uma vez e pesa para sempre.** O `gui.py` inteiro (~60 mil
  tokens) grava a 2× e depois cobra o equivalente a ~6 mil de entrada em CADA
  turno seguinte — além de ocupar a janela e diluir a atenção.
- **Um commit por frente, sempre; o `/clear` tem gatilho próprio.** Sessão nova
  não é de graça: grava o contexto de partida inteiro (51 mil tokens, US$ 0,51
  no preço de lista). O `/clear` se paga quando **(a)** vou **parar** mais de
  uma hora — o cache expira e a volta regrava tudo; **(b)** o **assunto muda** —
  o contexto velho não serve à frente nova; **(c)** o contexto passou de **~150
  mil** (o aviso do `limite_de_contexto.py`). Duas frentes pequenas e vizinhas
  saem mais baratas na mesma sessão.
- **`tools/mapa.py` antes de qualquer arquivo com mais de mil linhas**, sem
  exceção: `mapa.py gui.py --buscar trocar_modo` (nome solto basta, ele acha no
  pacote) e depois ler só o intervalo. São 70 linhas em vez de 5.654.
- **Revisar o diff, não o arquivo** — `git diff -U8 -- arquivo.py`. Quando parecer
  que falta contexto, o que falta quase sempre são três linhas de `-U`.
- **`tools/testar.py` durante o trabalho**; a suíte inteira no fechamento.
- **Conferir medindo, não lendo.** Um `grab()` de tela custa ~1,5 mil tokens;
  abrir o `gui.py` para "ver se o layout está certo" custa 40× isso e ainda não
  responde. No papel: gerar os dois PDF e passar o `tools/comparar_pdf.py`.

---

## Quando perguntar ao usuário

Ele pediu (29/10/2026) interação **só para decisões importantes**. Perguntar
— com a opção recomendada primeiro — apenas quando: (1) muda o que sai no
papel, chega ao paciente ou vai à CNEN; (2) contradiz spec, decisão anterior
dele ou regra do domínio; (3) é irreversível além de commit e push; (4) é
layout de tela nova ou mudança grande de tela; (5) depende de fato do
serviço que só ele sabe; (6) cresce muito além do pedido. **O resto se
decide** pela opção recomendada, a mais restritiva e com base, e se relata
numa linha: escolha técnica, ordem, conserto de ambiente, ferramenta.
Decisão que contradiz spec atualiza a spec **no mesmo commit**.

---

## Antes de dizer que está pronto

1. **Suíte completa e ordem aleatória pelo `tools/suite.py`** (e
   `--aleatoria`): com VIGIA — teste que passa de 3 min vira "TRAVOU em
   <teste>" com a linha, em vez de silêncio (em 28–29/10/2026 a suíte ficou
   1h40 parada sem ninguém saber). Uns **7,5 min** cada com os testes de
   banco (2.703 testes, 460 s, 29/10/2026); número que não bate é achado.
   Relatar o número de testes, o resultado e a semente.
2. **Funcionar no caminho DELE, não no meu.** Tela ou integração: conferir
   como ele abre o app (pelo VS Code, com as variáveis que o VS Code dele
   enxerga — a abertura avisa variável defasada). O que depender dele fazer
   (reabrir o VS Code, empacotar, rodar na clínica) se diz ANTES de "pronto".
3. Mudança visual: renderizar e olhar (`tools/tela.py`); PDF: gerar e medir.
4. **O que ficou de fora**, dizer o que e por quê.

---

## Ferramentas do projeto

O detalhe de cada uma — o porquê, o número medido, o que ela NÃO faz — está em
`docs/AMBIENTE.md`, junto com os ganchos, os comandos de sessão, o `.vscode/`
(extensões, tarefas e atalhos) e a tabela de variáveis de ambiente. Ler aquele
arquivo ao usar a ferramenta; aqui fica só o gatilho, que é o que precisa estar
na cabeça antes de decidir.

| ferramenta | quando |
|---|---|
| `tools/mapa.py <arq.py> [--buscar X]` | **antes** de abrir qualquer arquivo com mais de mil linhas |
| `tools/testar.py` | durante o trabalho — recorte por import da frente aberta. **Não substitui a suíte** |
| `tools/caso.py <TC8\|Elekta\|…>` | mudança no PDF: gera a ficha de um caso real pelo caminho do programa |
| `tools/comparar_pdf.py <antes> <depois>` | e então **medir** — a ficha do TC8 tem 214 células, e a olho não se vê um 92,3 que virou 91,8 |
| `tools/tela.py <alvo>` | mudança visual: grava o PNG do widget com o texto desenhado, pela sequência que não derruba o processo |
| `tools/gerar_executavel.py` | empacotar, **nunca** à mão |
| `tools/varrer_identidade.py` | **antes de todo commit** — dado real de paciente que está entrando |
| `tools/manutencao.py` | o ambiente em volta do código (armazenamento, `.claude/`, notas, extensões). Semanal, relata e **não apaga** |
| `tools/servidor_local.bat [funcao\|varredura]` | demonstração FORA DA REDE (DW simulado, DICOM local, trabalho do dia pronto) — detalhe no `docs/AMBIENTE.md` |
| `tools/robo.py [--uma\|--simular]` | frentes `classe: robo` do `DESTINO.md`, sozinho, na branch `robo` (detalhe no `docs/AMBIENTE.md`) |

**Para onde o app vai** está no `DESTINO.md`: os quatro pilares e a fila de
frentes, cada uma com quem anda nela (`robo`, `voce`, `clinica`). Frente nova
entra lá, no formato fixo — o robô lê.

**O BMad é só planejamento** (13/10/2026): pesquisa, brief, PRD, arquitetura e spec, com saída em
`docs/planejamento/`; a execução é a fila do `DESTINO.md`. `docs/qms/*.md` quem preenche é o físico,
nunca a IA. O porquê está em `docs/planejamento/LEIA-ME.md`.

**Banco, ARIA e DICOM** (`gravar_banco.py`, `atividades.py`, `sondar_dicom.py`,
`descobrir_dicom.bat`) estão em `tools/LEIAME_CLINICA.md`, e a skill `/clinica`
os carrega. Quando o assunto for banco ou DICOM, ler aquele arquivo ANTES de
escrever o comando — nenhum deles roda desta máquina.

Doc oficial da Varian antes de escrever a chamada; o que exige identidade de rede vai pelo `.bat`, e a
saída se lê do ARQUIVO — regras completas no `tools/LEIAME_CLINICA.md` (skill `/clinica`; ESAPI, skill `esapi`).

**Comandos de sessão** (`/abrir` … `/fechar`, `/manutencao`) e os ganchos moram em `.claude/`, VERSIONADOS e testados (`tests/test_ganchos.py`);
o que cada um faz está no `docs/AMBIENTE.md`. O `/fechar` é suíte → checkpoint → commit.

---

## Comentários explicam o PORQUÊ

Este código é comentado num estilo específico e ele deve ser mantido: o
comentário diz **por que é assim**, e de preferência **o que quebrou quando era
de outro jeito**.

```python
# Largura ZERO no palpite de tamanho: o que interessa é a altura. Com a largura
# NATURAL da linha (que inclui o nome inteiro, antes de elidir), o item ficava
# mais largo que a área visível — e, com a barra horizontal desligada, o
# excedente era simplesmente cortado: a data do lado direito saía pela metade.
```

Não escrever comentário que repete o código (`# soma 1 ao contador`). Escrever o
que o próximo leitor não pode adivinhar: a restrição, o caso real que motivou, a
alternativa que foi tentada e falhou.

O mesmo vale para as **docstrings de teste**: elas dizem o que quebrou no uso,
não o que a função faz.

---

## Regras do domínio (não negociáveis)

- **Nunca inventar dado.** Campo sem fonte nasce **vazio**, e a tela diz que
  está faltando. Uma capa que afirma um sexo por sorteio é pior que uma capa
  incompleta.
- **A fonte da capa é o BANCO** (`capa_db.py`, data warehouse `variandw`),
  desde 18/08/2026. Leitura apenas — este banco é o sistema clínico.
- **Três degraus, e cada um se identifica na tela**: banco → **espelho**
  (`capa_espelho.py`, o que o banco já respondeu sobre AQUELE paciente) →
  relatórios exportados, só como último recurso. Os CSV **não** servem de
  reserva: ninguém os reexporta depois da migração e envelhecem em bloco, e
  reserva que mente é pior que reserva nenhuma. O espelho envelhece por
  paciente, e a tela diz a data dele.
- **Reserva usada é reserva anunciada.** Capa que não veio do banco carrega
  aviso em primeiro lugar na lista, com a data do dado. Emergência silenciosa
  vira o normal em duas semanas.
- **Relatório é retrato do dia da exportação.** Os arquivos que alimentam a
  capa são **lidos, nunca escritos**. Correção feita à mão vai para
  `correcoes.py`, e só o campo que DIVERGE.
- **Ficha do TPS não é fonte de verdade confiável** — já se achou ficha errada
  no acervo. Conferir no sistema antes de mudar cálculo.
- **Documento impresso muda com aviso.** Alterar o que sai no papel (ordem de
  campos, texto de célula, geometria) exige dizer ao usuário o que muda e por
  quê, mesmo quando a mudança foi pedida.
- **Verde é dose.** A tela mostra isodose ao lado dos botões; nenhum elemento de
  interface usa verde como cor de ação (ver `estilo.py`).
- **Cálculo paralelo só com a tabela DAQUELA máquina.** TMR e Scp são de cada
  acelerador; casar por parecença de nome ("TrueBeam" pegando
  "TrueBeamSN1001") faria o programa verificar planos com a curva de outra
  máquina, em silêncio. Sem tabela da máquina do plano, o resultado é
  DEMONSTRAÇÃO e não tem veredito — ver `paralelo.maquina_do_plano`.
- **Índice fora da faixa não é plano reprovado** enquanto `qualidade.CALIBRADO`
  for falso. As tolerâncias da aba Qualidade vêm da literatura, não da base
  histórica do serviço; o AAPM TG-218 manda derivá-las do próprio processo. A
  tela anuncia isso em primeiro lugar — mesma regra da capa que veio de
  reserva.

---

## Interface

- **Tela nova começa pelo `ui.py`, não pelo Qt.** Janela é `ui.Dialogo` +
  `rodape(...)`; abas são `ui.abas(...)`; pop-up é
  `ui.avisar/alertar/falhar/confirmar/escolher`; cor é `estilo.pintar`. A
  tabela completa está no topo do `ui.py`, e `tests/test_padrao_visual.py`
  **reprova** o Qt cru — inclusive o hexadecimal de tela. Fugir do padrão é
  possível, mas com nome e motivo na lista de exceções do teste: a divergência
  nunca veio de discordância, veio de esquecimento, e era descoberta por print
  de tela depois da tela pronta.
- **Layout novo se descreve ANTES de editar.** Árvore de widgets e divisão de
  linhas/colunas em texto, e esperar o aceite. As 13 sessões de tela são o ponto
  quente de retrabalho do projeto — a aba Capa, as telas de SSD/deslocamento, os
  layouts de PDF e o painel do radioterapeuta levaram duas ou mais rodadas
  rejeitadas cada. O print (`tools/tela.py`) vem DEPOIS do aceite, para conferir
  o que foi combinado; usá-lo para descobrir o que se queria é pagar a
  implementação inteira por uma pergunta de duas linhas.
- **Peso de botão, não matiz**: um **sólido** por tela (o passo que não se
  desfaz), **contorno** no resto do fluxo, **fantasma** na navegação, **contorno
  vermelho** no destrutivo — preenchido, ele atrai o clique de que avisa.
- **O sólido anda com o trabalho**: com a bancada vazia é "Abrir pasta"; com o
  caso carregado é "Impressão".
- **Botão aceso significa pronto.** Se clicar vai só avisar que não deu, o botão
  devia estar apagado, com o motivo no tooltip.
- **Não reservar espaço vazio** "por via das dúvidas" — exceto quando a reserva
  impede o layout de saltar sob o cursor (ver a faixa de ações da Fichinha).
- **Cor só de `estilo.py`.** Folha de estilo montada com `estilo.pintar(w, fn)`
  para acompanhar dia↔noite; hexadecimal cru no código é bug, salvo os casos
  intencionais já comentados (preto do corte, ícone do app, cores de plano).

---

## Armadilhas já pagas neste repositório

A lista completa é o `ARMADILHAS.md`, e o gancho `abertura.py` injeta os
**títulos** dela no começo de cada sessão — para saber que a entrada existe sem
pagar o corpo dela em todo turno. Quando um título soar como o problema da vez,
abrir o arquivo e ler aquela entrada.

Quatro delas o `checar_py.py` já recusa na edição (`del modulo.funcao` em teste,
`setSpecialValueText("")`, `setCurrentText("")`, `ISOCENTRO_DB_SERVIDOR` zerado).

Ficam as que mordem enquanto se **escreve**, antes de qualquer gancho rodar:

- **`| tail` numa suíte perde o veredito.** O `unittest` relata em stderr (sai na
  hora) e os `print` dos testes vão em stdout (bufferizado até o fim do
  processo): o resumo cai no meio, o `tail` corta, e o código de saída que sobra
  é o do `tail`. Gravar em arquivo e filtrar depois — é o que o `/pronto` manda.
- **Usar `assert` em toda substituição por script**, e **script com barra
  invertida vai por arquivo, nunca por heredoc** (`python - <<'PY'` come uma
  camada de escape; `cat > x.py <<'PY'` já morreu no meio de um arquivo de 230
  linhas). Duas edições falharam em silêncio por falta do `assert`, e o teste só
  pegou uma. **`posicionamento.py` ainda tem BOM e CRLF**: normalizar antes.
- **`estilo.pintar` registra um ouvinte por chamada.** Em método que roda a cada
  mudança de estado, registrar uma vez e reaplicar a folha à mão. **Em teste o
  efeito é cumulativo e caro:** arquivo de teste que monta tela precisa da linha
  `from tests.limpeza_de_tela import load_tests`; sem ela a suíte volta a levar
  9 minutos em vez de 2.
- **A ordem dos testes importa**: `test_capa_tela` antes de `test_capa` quebra 16
  casos (estado global da pasta de relatórios). O `discover` alfabético esconde.
- **Reordenar lista de exibição quebra quem indexa por posição.** A tabela de
  edição de feixes rotulava `Campo {i+1}`; com a ordem do gantry, a 4ª linha
  deixou de ser o "Campo 4" impresso.
- **Conferir tela é `tools/tela.py`, não `grab()` à mão.** As duas armadilhas
  aqui se disfarçam de bug de layout: o `offscreen` **não desenha texto** (saem
  as caixas certas e os rótulos vazios) e a `JanelaPrincipal` derruba o processo
  com exit 127 e nenhum traceback se o `setStyleSheet` não vier antes. A
  ferramenta faz as duas coisas na ordem certa.

---

## Git

- **Commit e push SEMPRE, sem perguntar** (combinado em 04/09/2026). O
  objetivo é o repositório estar sempre em dia — esta conexão cai, e trabalho
  conferido parado na árvore é trabalho que pode se perder. Vale a mesma regra
  de antes para o resto: rodar a suíte primeiro, e dividir em commits por
  frente, para uma poder voltar atrás sem levar as outras.
- **A linha de trabalho é a `main`; versão é TAG, não branch** (desde 13/10/2026 — as branches
  `v2`…`v7` deixaram a `main` 385 commits atrás). Ao empacotar: `git tag -a vN.M -m ...` e push da tag.
- **Mensagem em português**, no mesmo espírito dos comentários: o título diz o
  que mudou, o corpo diz **por quê** e o que quebrava antes.
- **Antes do commit, `python tools/varrer_identidade.py`.** Ele varre as linhas
  que ENTRAM atrás de registro e nome reais de paciente, e devolve saída 1.
  Tirar dado já versionado custou reescrever o histórico, e o que esteve
  público não se desfaz. Achado não se contorna: troca-se pelo pseudônimo
  (`900NNNN`).
- **Binários (`.exe`, `.rar`) não entram no repositório** — publicar como asset
  de Release.
- Do `.claude/`, só `hooks/`, `commands/` e `skills/` entram no git; o resto
  (`settings.json`, `estado/`) é da estação.

---

## Configuração

Pastas por variável de ambiente, com padrão ao lado do programa. **A tabela das
20 variáveis está em `docs/AMBIENTE.md`** — é consulta, e consulta não precisa
ser paga em toda requisição. O que vale sempre:

- **Ler por `ambiente.ler(...)`, nunca por `os.environ.get` direto.** Valem três
  nomes — `ISOCENTRO_*` (o atual, tem precedência), `RADIOTERAFICHA_*` e
  `FICHAPY_*` (os antigos, continuam funcionando) — e renomear e pronto quebraria em silêncio as estações
  que a TI já configurou.
- **Precedência: escolha da sessão → variável da estação → configuração do
  serviço → padrão**, e a tela mostra qual venceu (`origem_da_pasta`). Sem isso,
  quem aponta a pasta e não vê efeito não tem como descobrir que uma variável
  local está mandando nela.
- **Pasta do serviço é decisão de admin, não de estação**: vai para o
  `config_servico.json`, ao lado do índice central. **Não usar `QSettings`** —
  no Windows ele é `HKEY_CURRENT_USER`, e a escolha valeria para um usuário do
  Windows numa máquina só.
- Login inicial `admin`/`admin`, troca obrigatória no primeiro acesso.
