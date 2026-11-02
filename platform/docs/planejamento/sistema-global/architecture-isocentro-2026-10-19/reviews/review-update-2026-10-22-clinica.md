---
alvo: ../ARCHITECTURE-SPINE.md (Update de 22/10/2026: AD-38 a AD-41; emendas a AD-2, AD-22, AD-35; tabela "Destino dos pacotes atuais")
lente: docs/qms/revisao-clinica.md (regras 1 a 9)
base: docs/qms/escopo.md, docs/qms/classificacao-62304.md, docs/qms/riscos.md; código atual em isocentro/dicom/ e isocentro/dominio/constantes.py
data: '2026-10-22'
revisor: agente (revisão adversária independente, somente leitura; a espinha não foi editada)
---

# Revisão clínica: Update de 22/10/2026 da espinha

## Veredito

**A revisão por módulo, com o raio tirado dos imports, ainda não é segura para o paciente.**
A ideia (módulo como item de software, `rt` sem veredito, raiz de composição explícita) é boa e
deve ficar. O problema é que o raio só enxerga o acoplamento por `import`, e no ISOCENTRO o dano
chega ao paciente por quatro caminhos que não passam por import: o valor que muda de sentido atrás
de uma fachada que não mudou, o gatilho do motor, o papel e a configuração por máquina. Além disso,
quem declara a classe é o próprio código (o `MANIFESTO`), não o físico. E a escrita no Eclipse
continua sem um critério de validação que se possa conferir. Antes do Update, a tabela de destino
coloca na `rt` um código que já hoje contradiz a AD-38: ele lê arquivo, importa `dominio`/`dados`,
casa máquina por substring e decide o sinal do número impresso na ficha.

Gravidades: **bloqueante**: resolver antes de qualquer épico que use o raio do AD-39 para reduzir
revisão, ou antes de mover código para `rt/`. **Importante**: resolver no épico do núcleo ou na
migração. **Observação**: anotar.

---

## A pergunta central, caso a caso

### 1. Módulo de classe B cujo resultado aparece num documento usado na sala

O AD-35 continua dizendo "demais módulos: classe B [ASSUMPTION]". Pela tabela de destino nova,
`papel/` (ficha, capa, DRR, rodapé) vai para `modulos/radioteraficha/`. Juntando as duas coisas, a
ficha técnica, que o posicionador confere na mesa, nasce num módulo que a espinha presume classe B.
Pela IEC 62304 (4.3), a classe sai do dano possível **sem** contar as medidas externas ao software.
A conferência humana na sala é medida externa, então não pode baixar a classe. Um deslocamento de
mesa com o sinal trocado ou uma SSD errada na ficha pode levar a tratar o lugar errado. A decisão é
do físico e não cabe a mim propor classe. Cabe apontar que a presunção B, aplicada a quem imprime
para a sala, é exatamente o que a regra 9 manda não presumir.

Além disso, o raio do AD-39 para um "arquivo interno de um módulo" é "aquele módulo". Mudança em
`modulos/radioteraficha/papel/...` é interna, então o raio não exige gerar e comparar o PDF
(`tools/caso.py` + `tools/comparar_pdf.py`) nem avisar que o papel mudou (regra 4). O critério
"o papel mudou" é ortogonal ao grafo de imports e precisa ser uma dimensão própria do raio.

### 2. Dado compartilhado que muda de sentido sem mudar o import

O raio só cresce para fora do módulo quando o diff toca `consulta.py` ou o `MANIFESTO`. Três
cenários escapam:

- **Semântica atrás da fachada.** Um arquivo interno de `modulos/tratamento` passa a contar frações
  entregues em vez de agendadas, ou a devolver dose em cGy em vez de Gy, ou a gravar a hora do
  lançamento em vez da hora do fato (AD-23). `consulta.py` não muda (a função continua a mesma), mas
  o valor que `plano`, `seguranca` ou `radioteraficha` recebem muda de sentido. Raio calculado:
  só `tratamento`. A revisão não chega a quem imprime.
- **Gatilho pelo motor.** Pelo AD-3(3), a reação a outro módulo passa pelo motor
  (`evento`/`estado`/`prazo`), não por import. Se um módulo muda quando emite um estado, muda quem
  reage a ele. O grafo de imports não mostra essa aresta, mas ela existe no catálogo (AD-31) e no
  registro de gatilhos.
- **O que não é Python.** Migração `.sql` (AD-19), o esquema JSON do ESAPI
  (`adaptadores/esapi_json/`, que sai como adaptador, ok), tabelas de feixe/TMR/Scp, tolerâncias,
  `correcoes.py`/correções por paciente, assets do papel (logo, modelos), arquivos `.json` ao lado do
  app, versões de `pydicom`/`numpy`/`PyInstaller` (dependência externa da `rt`) e a spec do
  empacotamento. Nada disso aparece num grafo de imports. Hoje o AD-39 não diz qual raio se aplica
  a cada um.

Um teste de contrato da fachada, com valores e unidades fixados, é o que faz uma mudança de sentido
virar mudança visível. Sem ele, o raio por import dá falsa segurança.

### 3. Classe da `rt` derivada do consumidor

O AD-39(1) diz que "`nucleo` e `rt` têm a classe do consumidor mais crítico", e o consumidor
declara a sua classe no próprio `MANIFESTO` (AD-40). São três problemas:

- **A classe passa a ser um campo do código.** `classificacao-62304.md` diz que a classe é decisão
  do físico. Se o `MANIFESTO` a declara, há duas fontes, e a do código pode ser editada por
  quem mexe no código, inclusive a IA. Se o valor do manifesto cair, a classe da `rt` e do núcleo
  cai junto, sem ninguém decidir.
- **Classe herdada não basta como segregação.** Para dar a um item classe menor que a do sistema,
  a IEC 62304 (4.3 e 5.3.5) exige segregação identificada e justificada. Os módulos rodam no mesmo
  processo Python: compartilham memória, estado global de módulo, monkeypatch, `estilo.pintar` e o
  `QApplication`. Uma divisão por import é uma fronteira de código, e o documento ainda não
  justifica por que ela seria uma segregação.
- **"Sem veredito" não quer dizer "sem risco".** A `rt` não aprova nem reprova, mas calcula
  números que vão para a ficha: SSD pelo contorno BODY (`corpo3d`), deslocamentos de mesa, ângulo
  de mesa no console da série C, DVH. Um número errado sem veredito também chega ao paciente. O
  AD-35 emendado põe a `rt` no rigor C até a classificação formal, e isso está certo e deve ficar. O
  que não pode é o AD-39 abrir caminho para que a classe da `rt` baixe automaticamente.

### 4. Scripts ESAPI que escrevem no Eclipse, fora do processo do ISOCENTRO

O AD-41 é coerente com o escopo, porque o ISOCENTRO não escreve no Eclipse. Mas tirar a escrita do
processo não tira o risco do sistema, só o tira da vista. Sobre isso:

- O escopo (`escopo.md`, Fronteiras) só aceita escrita no Eclipse "depois de validado em ambiente não
  clínico", com a validação registrada antes do primeiro uso real. O AD-41(3) cria o campo
  "registro de validação", mas não diz **como** se valida (o que se testa, por quem, onde fica a
  evidência). E esse critério está em "Em aberto" no próprio `escopo.md`. Pela regra 2, isso é
  bloqueante. O critério é do físico, mas a espinha precisa ter o lugar dele e o efeito de ele
  faltar.
- O inventário é um **registro**, não uma **trava**. Nada impede que uma versão não validada rode no
  Eclipse, e o ISOCENTRO nem saberia. A trava possível, do lado do ISOCENTRO, é na leitura: o JSON
  do AD-15 traz só a versão do esquema (AD-41(2)), não o id, a versão e o hash da DLL do script. A
  concentradora deveria cruzar esses dados com o inventário e tratar um resultado vindo de script
  não inventariado ou não validado como `indeterminado`, nunca como `ok`.
- **A classe dos scripts graváveis.** Estruturas de otimização e pesos de campo (field-in-field)
  mudam a dose. Num repositório separado, com versão própria, eles ficam fora da tabela
  `classificacao-62304.md` e fora do raio do AD-39. A espinha deve dizer que eles são itens de
  software do sistema global (o escopo diz que o ISOCENTRO "é o núcleo do sistema global"), com
  classe a decidir, e não deixar que "outro repositório" vire "fora do QMS".
- **Plano mexido depois da checagem.** Um script gravável roda depois de o ISOCENTRO verificar o
  plano. O AD-15 já cobre isso ("versão do plano diferente da atual → `indeterminado`"). Vale citar o
  AD-15 no AD-41 para essa ligação não se perder.

---

## Achados

| # | Trecho citado | Regra | Gravidade | Pergunta ao físico |
| --- | --- | --- | --- | --- |
| 1 | AD-35: "Demais módulos: classe B [ASSUMPTION]" + destino: "`papel/` (ficha, capa, DRR, rodapé) → `modulos/radioteraficha/`" | 9, 4 | **bloqueante** | Qual a classe de `modulos/radioteraficha`, que imprime ficha e capa para a sala? Até a decisão, ele deve ter o rigor C, como o Plano, em vez da presunção B? |
| 2 | AD-39(2): "arquivo interno de um módulo → aquele módulo; sua fachada `consulta.py` ou seu manifesto → o módulo e os consumidores da fachada" | 8, 4 | **bloqueante** | O raio pode ignorar (a) mudança de sentido atrás de uma fachada inalterada, (b) a aresta do gatilho pelo motor, (c) arquivos não-Python (SQL, tabelas de feixe, tolerâncias, assets, dependências)? Proposta: teste de contrato da fachada (valor, unidade, sentido) ligado a um risco; o raio também segue gatilhos do catálogo; toda mudança que chega ao papel exige `comparar_pdf` contra caso conferido e aviso ao usuário, qualquer que seja o import. |
| 3 | AD-39(1)/AD-40: classe "declarada no seu `MANIFESTO`"; "`nucleo` e `rt` têm a classe do consumidor mais crítico" | 9 | **bloqueante** | A fonte da classe continua sendo `classificacao-62304.md`, preenchido pelo físico? Proposta: o manifesto não declara classe, ou declara e um teste reprova divergência com o `.md`. Módulo ausente do `.md` vale "não classificado", tratado com rigor C, nunca B por padrão. `rt`/`nucleo` nunca abaixo de C sem decisão escrita. |
| 4 | AD-39(1): "cada módulo é um item de software IEC 62304 com classe própria" | 9 | importante | Com tudo num processo Python só, qual a justificativa de segregação (IEC 62304, 5.3.5) para um módulo ter classe menor que o sistema? Sem ela, vale a classe do sistema para todos. |
| 5 | AD-38: "Sem Qt, banco, arquivo, rede ou estado; importa só bibliotecas externas (pydicom, numpy) e a si mesmo. Não decide nada" + destino: "`dicom/dicom_rt` … → `rt/`" | 5, 1 | **bloqueante** | `dicom_rt.py` hoje importa `isocentro.dominio.constantes` e `isocentro.dados.nomes`, lê arquivo/zip (`tempfile`, `zipfile`), tem `equipe_da_maquina` (equipe, não RT) e decide o **valor impresso**: `desl_vert *= _mesa_vert_sign(maquina)` ("Valor de exibição na ficha: 6EX/600CD mostram o vertical com sinal invertido") e `_mesa_angulo_console`. Ambos usam `constantes.identificar_maquina`, que casa por **substring** do nome. Isso é convenção de máquina por parecença de nome, dentro da camada que "não decide nada". Onde mora a convenção do console por máquina (série C), e como a máquina é identificada sem casar por substring? Proposta: a `rt` devolve só a geometria física (IEC 61217); a conversão para o console fica no módulo que imprime, com a máquina vinda da chave canônica do AD-26; máquina não reconhecida → campo vazio e aviso, nunca a convenção padrão. |
| 6 | AD-38: "sem I/O" × `dvh`, `cortes`, `ct_series` desenham com PIL; `corpo3d` usa `threading` | 1 | observação | Desenho de imagem e cache com lock entram na `rt` ou ficam numa borda (interface/papel)? A regra precisa dizer, para o teste do AD-22 não nascer com uma lista de exceções. |
| 7 | AD-41(3): "registro de validação em ambiente não clínico" | 2 | **bloqueante** | Qual o critério da validação dos scripts graváveis (o que se testa, por quem, onde fica a evidência)? Hoje está em "Em aberto" no `escopo.md`. A espinha deve citar onde esse critério vai morar e dizer que, sem registro, o script consta no inventário como "não validado". |
| 8 | AD-41(2): "o script grava a versão do esquema que usa" | 2, 8 | importante | O JSON deve trazer também id, versão e hash da DLL? Proposta: a concentradora cruza com o inventário de `modulos/software`; script fora do inventário ou não validado → `indeterminado`. Assim o inventário vira trava, e não só registro. |
| 9 | AD-41(1): "`scriptsvarian` … segue em repositório próprio, com versão própria" | 9, 8 | importante | Os scripts graváveis (estruturas de otimização, field-in-field) são itens de software do sistema global, com linha própria em `classificacao-62304.md` e em `riscos.md`? Repositório separado não pode querer dizer fora do QMS. |
| 10 | AD-39(2): raio não menciona `interface/modulos/<m>/` | 4, 8 | importante | Uma mudança na tela de um módulo (por exemplo, a tela de SSD ou deslocamento, que mostra o que vai para a ficha) entra no raio de quem? Proposta: a tela herda o raio do módulo pelo nome do manifesto. |
| 11 | AD-39(2): "Uma ferramenta em `tools/` calcula o raio a partir do diff" | 8 | importante | A ferramenta é ela mesma software que reduz verificação (IEC 62304, 8.1.2: ferramenta que afeta a verificação precisa de validação). Ela pega import dentro de função, `from x import *` e import condicional? Proposta: o raio calculado só pode **somar** à suíte mínima (a suíte inteira continua no fechamento, como no `CLAUDE.md`). Ele serve para escolher a revisão humana e a comparação de PDF, não para cortar teste. |
| 12 | AD-39(3): "a nota de cada versão lista os módulos tocados e o raio de cada mudança" | 8 | observação | A nota também deve dizer "papel mudou: sim/não" e qual caso conferido foi comparado, para que a regra 4 vire evidência por versão. |
| 13 | AD-35 emendado: "núcleo, `rt` e módulo Plano … no rigor da classe C" | 9 | observação (positivo) | Manter. Só é preciso deixar explícito que o AD-39(1) não rebaixa esse piso enquanto não houver decisão formal. |

**Achados bloqueantes: 5** (1, 2, 3, 5, 7).

## O que o Update acerta e deve ficar

- A `rt` sem veredito, com tolerância e 2º cálculo de UM no `modulos/plano` (AD-38). Isso mantém a
  regra da máquina certa e a do `CALIBRADO` num dono só.
- Raiz de composição explícita, sem descoberta por pasta (AD-40). App e concentradora com o mesmo
  conjunto de módulos fecha uma classe inteira de "verificação que roda num lado e não no outro".
- Versão única do executável (AD-39(3) + AD-20). Uma versão por módulo seria rastreabilidade de
  fachada num processo só.
- O ISOCENTRO não executa script ESAPI (AD-41(1)), coerente com "Não escreve no Eclipse" do escopo.
- `rt`, `nucleo` e adaptador valendo a suíte inteira (AD-39(2)).
