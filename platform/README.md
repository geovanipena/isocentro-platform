# ISOCENTRO

Aplicação **local** para gerar a **ficha técnica de tratamento em radioterapia**
a partir dos objetos DICOM-RT. Aponte para a pasta do paciente: o ISOCENTRO lê a
TC e o plano (RP/RS/RD), preenche a ficha, mostra os cortes e o corpo 3D, e
exporta o PDF — ficha, mapa de frações, alta e página de imagens.

Os dados do paciente **não saem da máquina**: tudo roda em processo local, e o
que é gravado vai para a pasta do próprio paciente.

## Como rodar

Requer **Python 3.12** (validado) no Windows.

```bash
python -m venv .venv
.venv\Scripts\activate             # Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
python run_gui.py                  # interface desktop — é o app principal
```

## Três telas

A faixa superior traz três botões, lado a lado no canto esquerdo. São o mesmo
seletor e trocam a mesma coisa — a tela do caso.

- **Ficha Total** — a bancada completa descrita abaixo. É onde o caso difícil se
  resolve: formulário, cortes, 3D, agendamento multi-plano.
- **Fichinha** — um campo, um botão. Cole o caminho da pasta (ou arraste-a),
  clique em **ISOCENTRO** e a ficha é montada do DICOM. A trilha abaixo
  acende em ordem: **Edição** e **Visualização** com a ficha montada,
  **Impressão** só depois de a prévia ter aberto de fato — editar de novo apaga
  a visualização, porque o que foi conferido deixou de ser o que sairia
  impresso. **Histórico** fica sempre disponível.

A regra da trilha é **botão aceso significa pronto**, e ela vale nos dois
sentidos:

- **Visualização exige o PDF já elaborado**, não só a ficha montada. Um caso
  multi-plano fica montado sem que o documento feche, porque falta o
  agendamento; até lá o botão fica apagado e o status diz o que resolver
  (*"o caso tem 2 planos e o agendamento não cobre todas as frações"*). Assim o
  clique nunca vira a elaboração — que é o que a trilha existe para tirar do
  caminho. Montado o agendamento na bancada, voltar à Fichinha refaz a prévia e
  acende o botão.
- **Limpar o campo do caminho (o `×`) desliga a trilha inteira.** A ficha segue
  na memória para a bancada, mas sem uma pasta apontada aqui a Visualização
  abriria a ficha do paciente anterior. Pelo mesmo motivo, o ícone de pasta
  confirma antes de trocar quando já há ficha montada.

- **Capa** — a *Ficha de Tratamento* institucional (2 páginas), **do
  posicionamento à impressão**. É uma tela só porque é um documento só: o que o
  dosimetrista registra ao sair da tomografia *é* a folha 2 da capa, e tê-lo
  numa tela à parte obrigava a preencher a mesma coisa duas vezes.

  Ela tem duas portas de entrada. **Sem caso carregado** — quem vem da
  tomografia — a busca de paciente aparece, e o que se preenche é o
  posicionamento: fotos, nota, preparo, imobilizador. **Com o caso na bancada**,
  a busca some (o paciente já está decidido) e a identificação, o curso e as
  prescrições chegam dos relatórios. Ver "Capa de Tratamento", abaixo.

  A caixa da **enfermagem** (alertas, dias alternados, planos de cuidado) não
  tem campo na tela: é preenchida à mão, no papel, depois de impressa — e
  continua saindo no PDF, em branco, como sempre saiu.
O paciente carregado é o mesmo nas três: trocar de tela não descarta nada, e um
caso aberto na bancada aparece pronto na Fichinha e na Capa.

Junto da ficha automática vem a conferência: as **pendências** (o que a ficha
está devendo) e os **alertas de padrão** (o que destoa das fichas já geradas —
ver `aprendizado.py`). Os alertas não preenchem campo nenhum: numa ficha
clínica, o palpite errado se assina, o campo vazio se vê.

## Fluxo de uso

1. **Importar pasta** — o app varre a pasta (e subpastas) atrás de `.dcm`,
   `.zip` e `.rar`, monta o volume da TC e agrupa até 5 planos com seus RS/RD
   por referência DICOM. Múltiplas tomografias são associadas ao plano certo
   pelo `FrameOfReferenceUID`.
2. **Conferir** — paciente, prescrição, feixes, SSD, estruturas e equipe vêm
   preenchidos do plano; o que for editado à mão prevalece.
3. **Navegar** — cortes axial/sagital/coronal, janelas (mama, pulmão, osso…),
   contornos do RT Struct, isodoses e corpo 3D.
4. **Impressão** — o PDF sai com a **capa na frente da ficha**, num arquivo só
   (é assim que os dois andam na prancheta). Salva também a alta, grava o
   **registro versionado** do paciente (JSON + PNGs) na pasta e, opcionalmente,
   apaga os DICOM já registrados. Se a capa não fechar — relatórios fora do ar,
   foto ilegível — a ficha sai sozinha e o motivo vai para o log: segurar a
   ficha por causa da capa seria trocar o importante pelo acessório.

## Cadastro de simulação

O dosimetrista acaba de posicionar o paciente na TC, fotografou o setup e sabe de
cor como montou. Ele registra isso **na própria Capa**, em um minuto — e é o
começo da corrente que termina na capa impressa no acelerador.

1. **Paciente** — busca por parte do nome ou do registro, na lista que sai dos
   relatórios (13 mil pacientes; a data de nascimento aparece para quem está no
   cadastro). Duas letras já filtram.
2. **Fotos** — arrasta, várias de uma vez, de qualquer lugar. Soltar uma pasta
   vale pelas imagens dela. Cada **posicionamento** é uma aba, e o que se arrasta
   cai na aba aberta: o paciente de fêmur e tórax tem as fotos separadas por
   setup, sem depender do nome do arquivo.
3. **Nota de posicionamento** — escolhida da biblioteca, que já vem semeada do
   acervo `.docx` do serviço (39 modelos: PELVE, MAMA - RAMPA, SNC
   RADIOCIRURGIA…). Aplicar a nota preenche acessórios e preparo; **Nova** cria
   uma a partir do que está na tela — quem clica ali acabou de montar um setup
   fora do padrão, e o conteúdo já está preenchido.
4. **Imobilizador** — máscara ou VacLok do inventário, só os disponíveis. Ver
   abaixo.

O primeiro e o segundo passo podem vir em qualquer ordem: quem chega com o
celular na mão às vezes solta as fotos antes de procurar o nome. **Cadastrar
Simulação** grava a pasta; os campos de cima (identificação, curso, prescrições)
ficam vazios até o caso ter plano, e completam sozinhos depois.

### A pasta que o cadastro grava

```
<raiz>/NOME_DO_PACIENTE_1234567ABC/08-2026/
    SIMULACAO.json          o cadastro inteiro, legível por programa
    POSICIONAMENTO.txt      a mesma coisa em texto, legível por pessoa
    01_TORAX_1.jpg          fotos, já no tamanho em que serão impressas
    01_TORAX_2.jpg
    02_FEMUR_1.jpg
```

**Pasta aberta, não pacote**: quem abre isso no explorador precisa ver as fotos —
o técnico confere o setup nelas antes de deitar o paciente, e um `.zip`
esconderia exatamente o que mais se olha. **JSON + txt**: o JSON é o que a Capa
lê sem interpretar nada (fim da adivinhação de vocabulário); o txt é o que sobra
de útil se um dia não houver programa para abrir o JSON. As fotos são gravadas
reamostradas para a resolução de impressão — o original de 5 MB do celular não
serve para nada depois e encheria o compartilhamento.

Cadastrar de novo no mesmo mês **substitui as fotos daquele cadastro** e mantém o
resto: uma segunda leva não obriga a refazer tudo, e nada que alguém pôs à mão na
pasta se perde. A raiz é `ISOCENTRO_SIMULACOES`, ou a escolhida pelo admin (botão
**📂 Pasta…**, visível só para ele), ou `Documentos/Simulacoes`.

**E é aqui que a corrente fecha**: a Capa procura a simulação pelo paciente, não
pela pasta. O dosimetrista cadastra ao sair da TC, dias antes de existir plano; a
Capa pergunta pelo nome e recebe os setups prontos, sem ninguém copiar arquivo de
um lugar para o outro. Havendo mais de uma simulação, vale a mais recente — o
replanejamento é o posicionamento que passou a valer.

### Inventário de imobilizadores

Acessório **padrão** (rampa, base, apoio, travesseiro) fica na sala, serve para
qualquer paciente e não precisa de inventário: basta dizer na nota que foi usado.
Acessório **individual** (máscara, VacLok) tem etiqueta, dono e histórico.

Só a **máscara** conta utilizações — é o material que se reaproveita, e é dele
que se quer saber quantas vezes já passou pelo forno; ao alcançar o limite, o
cadastro avisa. O VacLok é vinculado ao paciente e devolvido, sem contador.

A tela oferece só o que está disponível: mostrar um item que está com outro
paciente convida ao erro que o inventário existe para evitar. Mas vincular nunca
é bloqueado — a prateleira é a verdade, e o app não pode travar um cadastro
porque o inventário está atrasado; ele avisa. O arquivo atual é **fictício**,
semeado na primeira execução; o real entra no lugar dele sem mudança de código.

## Capa de Tratamento

A ficha técnica sai do DICOM; a capa não. Convênio, curso, intenção, CID e as
prescrições aprovadas vivem no sistema de registro, e o que chega ao app são
três relatórios exportados dele, lidos (nunca escritos) de uma pasta única:

| Arquivo | O que traz |
|---|---|
| `Capa_de_Tratamento_Periodo.csv` | cadastro: nome, DDN, sexo, contato, convênio, curso, intenção, CID, máquina, médico |
| `Prescrições por Período.csv` | uma linha por prescrição aprovada: volumes, doses, frações, técnica, quem aprovou |
| `Lista_Pacientes_Periodo_Foto.xlsx` | a foto 3×4, ancorada na linha do paciente |

A pasta vem, nesta ordem: do botão **📂 Relatórios…** na própria tela (a escolha
fica gravada para as próximas sessões), da variável **`ISOCENTRO_CAPA_DIR`**, da
subpasta `capa/` ao lado do programa, ou — se nenhuma delas tiver os relatórios
— de uma **procura automática** rasa sob a pasta do programa, atrás de um
diretório que contenha o CSV de cadastro. A procura existe porque `capa/` é uma
convenção que quem recebe a exportação não é obrigado a conhecer, e uma capa
vazia não explicaria que o problema era o nome da pasta. Sem os relatórios a tela ainda funciona: a
capa nasce em branco para preenchimento, com o aviso de onde eles não foram
achados — e o botão de escolher a pasta continua aceso, porque é justamente o
que se faz quando a busca não achou ninguém.

Um paciente que não está na exportação sai sem convênio, curso, CID e **sem a
foto 3×4** — o relatório de fotos cobre os mesmos pacientes do de cadastro. Não é
falha da busca: é a exportação que está velha.

O que sai impresso segue a capa institucional, não a grafia crua do relatório: o
**sítio anatômico** é traduzido (`Hard Palate` → `Palato duro`, cobrindo ~99% das
prescrições; o que não estiver no dicionário sai como veio, que é melhor do que
traduzir por adivinhação e imprimir a região errada); o **médico** é expandido
para o nome canônico da equipe (`Barbara Peixoto` → `Barbara Fontes Moura
Peixoto`); e as colunas de **preparo** usam o vocabulário do relatório — `Pé`,
`Lateral Dir`, `Ao lado corpo`, `4h`/`6h` para o jejum.

O casamento é por **ID e nome**, nessa ordem de confiança — o ID acha, o nome
confirma. Divergência não bloqueia nem corrige sozinha: vira aviso no topo da
tela, porque decidir se é homônimo, erro de digitação ou outra grafia do mesmo
nome é da pessoa, não do programa. Paciente ausente do relatório sai com os
campos vazios, nunca com dado inventado.

### Escolha das prescrições

O relatório traz o **histórico inteiro** do paciente — um dos casos de teste tem
nove prescrições de quatro cursos, a mais antiga de 2024 — e só **três** cabem
na folha. Quando há mais de uma, a tela mostra a lista para marcar quais entram,
com a **data primeiro**, que é o que distingue o curso que está correndo do que
já terminou:

```
[x] 8/6/2026 · C4_MAIO_2026 · Pulmão, esquerdo: PULMAO E 27Gy@3fr
[ ] 21/1/2026 · C3_JANEIRO_2026 · Pelve: ILIACO D+E 27Gy@3fr      (apagado)
```

Vêm marcadas as do **curso atual** (o que o cadastro aponta como em tratamento;
sem cadastro, o curso da prescrição mais recente), até o limite da folha. As de
cursos encerrados ficam na lista, apagadas — reimprimir capa antiga é pedido
real, e sumir com elas seria pior. A data do cabeçalho acompanha a escolha: uma
prescrição que não entrou não pode datar a capa.

### Folha 2: fotos e nota de posicionamento

A folha 2 não vem de relatório nenhum: vem da **pasta do paciente**, junto do
DICOM. Qualquer imagem solta vira foto de posicionamento (as quatro primeiras,
em ordem de nome), e qualquer `.docx`/`.txt` é lido como a nota que o técnico
escreveu ao montar o setup.

A nota é **interpretada**, não só copiada: o que nela é instrução de preparo vai
para as colunas da capa — bexiga, reto, gantry, decúbito, braços, jejum — e o
resto (rampa, base, máscara, apoio, medidas) fica na caixa de acessórios. Assim
`CABECA PARA O GANTRY / DECUBITO DORSAL / ProStep / TRAVESSEIRO / MÃOS NO TÓRAX
/ BEXIGA CHEIA / RETO VAZIO` vira quatro colunas preenchidas (com Bexiga, Reto e
Braços em âmbar, que é o preparo que alguém tem de executar) e dois acessórios.

**Mais de um setup.** Um paciente tratado de fêmur *e* de tórax tem dois jeitos
de ser deitado, com acessórios e preparo diferentes — no fêmur os braços vão
sobre o tórax, no tórax não. Cada nota da pasta é um setup, e a folha 2 se
divide ao meio: cada metade com suas fotos, seus acessórios e sua linha de
preparo. Fundir os dois numa linha só mandaria montar errado metade das sessões.
Com um setup só — a maioria — a folha sai idêntica ao modelo.

As fotos são distribuídas entre os setups **pelo nome**: `<paciente> FEMUR
FOTO.jpg` vai para `FEMUR.docx`. Quando o nome não diz nada (`<paciente>
1/2/4/5`), todas ficam no primeiro setup e quem monta a ficha redistribui nas
abas — adivinhar qual foto é da máscara de radiocirurgia e qual é da rampa de
tórax não é trabalho de programa. Cabem dois setups na folha; um terceiro é
anunciado na tela, não impresso em silêncio.

Linha que o app não reconhece **continua nos acessórios**: a nota é digitada à
mão, um setup novo aparece antes de o programa aprender a lê-lo, e perder a
linha seria perder a única instrução de como deitar o paciente. Duas notas na
mesma pasta (dois setups) entram uma só, com aviso de que existe outra.

As fotos de celular são reamostradas para a resolução em que serão impressas
(200 dpi) antes de entrar no PDF — embutir o bitmap cru fazia a capa passar de
100 MB, que na prática é uma capa que não imprime.

## Registro versionado

Ao gerar a ficha, tudo que a compõe (formulário, plano parseado, parâmetros de
render) é gravado num `FICHA_{NOME}_{REGISTRO}.json` na pasta do paciente, junto
dos PNGs de cortes e DVH. Cada geração acrescenta uma **versão** ao histórico —
uma mudança de dose ou um novo tratamento versiona o mesmo arquivo. Gerações sem
nenhuma alteração não criam versão nova.

Esse JSON é o que **sobrevive quando os DICOM são apagados**: dá para reabrir o
tratamento e regerar a ficha sem a TC. Por isso a exclusão de DICOM só é
oferecida depois que o registro grava com sucesso, e remove apenas os arquivos
**do paciente da ficha** (conferido pelo `PatientID`) — arquivos de outros
pacientes na mesma árvore são mantidos.

## Estrutura

Até 09/09/2026 os 61 módulos moravam soltos na raiz, misturados com os arquivos
que o app **grava** ao rodar. Hoje o código é o pacote `isocentro/`, e a
divisão é por **papel no fluxo**, não por tecnologia — a pergunta que a pasta
responde é "de onde vem isto?", não "com que biblioteca foi feito?".

```
isocentro/
├── run_gui.py                  # a porta de entrada; é o que o Isocentro.spec aponta
├── isocentro/
│   ├── raiz.py                 # onde o app mora em disco (pasta do app × assets)
│   ├── banco/                  # de onde vem o dado clínico, nos TRÊS DEGRAUS
│   │   ├── capa_db.py          #   1. o data warehouse variandw (leitura apenas)
│   │   ├── capa_espelho.py     #   2. o que o banco já respondeu daquele paciente
│   │   ├── capa_dados.py       #   3. os relatórios exportados, último recurso
│   │   ├── tratamento_db.py    # o tratamento ENTREGUE (aba Ficha Virtual)
│   │   ├── atividades_db.py    # o que está pendente no ARIA, e de quem
│   │   ├── gatilho_db.py       # que planos estão prontos para sair
│   │   └── banco_local.py      # o que o warehouse respondeu, para reproduzir
│   ├── dominio/                # a regra e o cálculo — sem interface nenhuma
│   │   ├── paralelo.py         # verificação independente de UM (AAPM TG-219)
│   │   ├── qualidade*.py       # índices do alvo e complexidade dos campos
│   │   ├── constantes.py       # máquinas, protocolos, gating
│   │   ├── agendamento.py      # etapas → sequência de frações
│   │   ├── aprendizado.py      # o que as fichas já geradas dizem sobre a nova
│   │   └── gatilho*.py         # a automação da exportação (varre, grava, anota)
│   ├── dicom/                  # ler o que veio do TPS, e virar imagem
│   │   ├── dicom_rt.py         # os objetos RT (TC, RP, RS, RD) e o SSD
│   │   ├── ct_series.py        # a série completa: volume 3D e cortes (MPR)
│   │   ├── cortes.py corpo3d.py dose3d.py dvh.py
│   ├── adaptadores/dicom/      # a borda: DICOM do disco e da rede, devolve Dataset
│   │   ├── leitura.py          # arquivo, .zip/.rar, cabeçalho de triagem
│   │   ├── rede.py             # falar com o DB Daemon do ARIA
│   ├── papel/                  # o que sai IMPRESSO e vai grampeado para a sala
│   │   ├── ficha_pdf.py        # a ficha técnica
│   │   ├── capa_pdf.py         # a Ficha de Tratamento (modelo Clinica)
│   │   ├── drr.py              # as páginas de setup do 600CD
│   │   └── rodape.py           # o "Impresso em …" de toda página de todo PDF
│   ├── interface/              # o que o usuário vê e opera
│   │   ├── gui.py              # a janela
│   │   ├── ui.py estilo.py     # as peças e a paleta — a tela nova começa aqui
│   │   ├── capa.py fichinha.py simulacao.py tratamento.py qualidade_tela.py
│   │   ├── tratamento_pecas.py tratamento_janelas.py   # peças da Ficha Virtual
│   │   ├── administracao.py posicionamento.py formulario.py visualizador.py
│   │   └── busca_ficha.py edicao_ficha.py checklist.py agendamento_tela.py
│   │                           # … e carregadores.py, que tira as cargas
│   │                           #   pesadas de cima da interface
│   └── dados/                  # o que o app grava e relê DELE MESMO
│       ├── registro_json.py    # o registro versionado do paciente
│       ├── indice.py           # o índice central, para a busca de Histórico
│       ├── ambiente.py         # as variáveis, pelos DOIS nomes
│       ├── auth.py equipe.py config_servico.py cadastro_sus.py
│       └── inventario.py notas_setup.py correcoes.py historico.py backup.py
├── assets/                     # logos e imagens do formulário, usados no PDF
├── tests/                      # a suíte
├── tools/                      # as ferramentas de bancada (ver docs/AMBIENTE.md)
├── Isocentro.spec                # a receita do PyInstaller — é FONTE, não descarte
└── requirements.txt            # versões fixadas — ver nota no arquivo
```

Os arquivos `.json` que aparecem na raiz de uma instalação (`usuarios.json`,
`registro_fichas.json` e os outros) **não** são código: são o que o app grava ao
lado de si, e é o que o `migrar.ps1` migra. Continuam na raiz de propósito —
mover qualquer um deles mudaria o disco de uma instalação que já existe.

## Testes

```bash
python -m unittest discover -s tests -v
```

Cobrem a geometria do SSD com fantomas sintéticos de resposta analítica (um
cilindro de raio R tem SSD = SAD − R): a tabela IEC de `_gantry_dir_xy`, os
sinais de `_tp0_coords` por decúbito e o raycast. São `unittest` da stdlib, sem
dependência extra.

Sintético de propósito: a ficha do TPS **não** é referência confiável — a do TC8
está errada. Validar contra ela mediria o TPS, não o código. Estes testes não
julgam se o contorno EXTERNAL é a superfície certa (isso é decisão clínica, já
validada em 8 pacientes), só se a matemática sobre ele fecha.

Há um `expectedFailure` documentando um defeito conhecido: a interpolação em z
mistura superfícies de estruturas diferentes quando um braço termina entre duas
fatias, colocando a "pele" no vão de ar (erro de 6,5 cm no fantoma). Ao corrigir,
remova o decorador — o teste vira regressão.

## Notas

- **SSD**: calculado pelo contorno EXTERNAL do RT Struct — a mesma superfície
  que o TPS usa. O raycast por HU na TC existe como *fallback* para quando não
  há RS, e é menos preciso. Ver `dicom_rt._ssd_via_rs`.
- **Dependências fixadas**: as versões em `requirements.txt` são exatas de
  propósito. Para atualizar, suba a versão e revalide a ficha contra o TPS.
- **`.rar`** exige `unrar`/`7z` instalado no sistema; `.zip` funciona sem nada.
- **Log**: erros tratados que não interrompem o uso (SSD que não calculou, corpo
  3D que não renderizou, imagem que não entrou no PDF) vão para
  `~/.isocentro.log`. O app é empacotado sem console — sem o log, essas falhas
  não deixam rastro. É o primeiro lugar para olhar quando algo sai vazio.
- **Executável**: `Isocentro.spec` empacota (gera `ISOCENTRO.exe`) com PyInstaller. Binários são
  distribuídos por **GitHub Releases**, não versionados no repositório.
- **Dados de paciente nunca são versionados** — ver `.gitignore` (`*.dcm`,
  `FICHA_*.json`, `CORTES_*.png`, `DVH_*.png`, `registro_fichas.json`).
