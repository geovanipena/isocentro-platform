# Bibliotecas externas — onde agregam ao ISOCENTRO

Análise das seis bibliotecas/ferramentas da lista de revisão (pylinac, PyMedPhys,
pydicom/pynetdicom, QATrack+, DICOMautomaton, dicompyler-core) e dos quatro itens
de infraestrutura (pyqtgraph/Streamlit, Pydantic, SQLModel, busca vetorial local),
mapeados contra o código que já existe em `isocentro/` — não contra uma
descrição genérica do projeto.

Cada item segue três passos: **o que é** (referência primária), **onde já
colide ou não com o que o app faz hoje** (crítica), **o que dá para construir a
partir daí** (extensão). Nenhuma proposta aqui assume que uma biblioteca "faz
mais" do que a documentação dela diz — onde a documentação não deu certeza
suficiente, isso está marcado.

> **Atualização de 21/10/2026.** As seções 1 a 7 são anteriores à arquitetura
> de 19/10. Duas propostas foram superadas: o banco é PostgreSQL 18 (AD-10),
> não SQLModel/SQLite (§3.3); e a interface migra de PyQt5 para PySide6
> (AD-36), o que vale também para o pyqtgraph (§3.1). A avaliação dos 61
> repositórios de `Documents/isocentro/codigo-externo` contra o PRD e a
> arquitetura está na §8.

---

## 1. O que já existe, e que a proposta tem de respeitar

Antes de mapear bibliotecas, o estado atual do código — porque toda proposta
abaixo é um incremento sobre isto, não uma reescrita:

| Onde | O que já faz | Arquivo |
|---|---|---|
| Aba Qualidade — índices do alvo | D98/D95/D50/D2/HI (ICRU 83), CI RTOG, CI/GI de Paddick — tudo calculado do RT Dose + RT Struct em NumPy puro | `dominio/qualidade.py` |
| Aba Qualidade — complexidade | MCSv e SAS (McNiven 2010 / Masi 2013), UM/cGy, a partir das posições de lâmina e `CumulativeMetersetWeight` do RT Plan | `dominio/qualidade.py` |
| Aba Qualidade — 2º cálculo | Verificação independente de UM por TMR/Scp analítico (AAPM TG-219), porte do `parallel-mu-check` | `dominio/paralelo.py` |
| DVH | Rasterização de contorno RT Struct sobre a grade do RT Dose, DVH cumulativo | `dicom/dvh.py` |
| Rede DICOM | C-ECHO/C-FIND/C-GET/C-MOVE contra o DB Daemon do ARIA, **só leitura** | `adaptadores/dicom/rede.py` (usa `pynetdicom` já) |
| Aprendizado | Compara ficha nova com o histórico do próprio serviço (faixa min–max, amostra mínima 6); **não** é SPC (TG-218) ainda | `dominio/aprendizado.py` |
| Persistência | JSON versionado por paciente (`FICHA_*.json`) + JSON administrativo com `.lock` manual (`registro_fichas.json.lock`, `checklist_pre_tratamento.json.lock`, `config_servico.json.lock`) | `dados/registro_json.py` e raiz |
| Render | Qt nativo (`interface/`) + Matplotlib para cortes/3D/DVH que viram PNG na ficha impressa | `desenho/corte.py`, `corpo.py`, `grafico_dvh.py` |
| Dependências | Fixadas em `requirements.txt`, atualização exige revalidar a ficha contra o TPS | `requirements.txt` |

Três regras do `CLAUDE.md` valem para toda proposta abaixo, sem exceção:
**nunca inventar dado** (campo sem fonte fica vazio, nunca um LLM ou uma
biblioteca "resolve" um valor clínico); **dados do paciente não saem da
máquina**; e **documento impresso muda com aviso**. Uma biblioteca que exige
servidor, nuvem, ou que produz número sem explicar o método, não passa nisso
— e está marcado onde é o caso.

---

## 2. As seis bibliotecas de QA/física médica

### 2.1 pylinac — QA de equipamento e imagem

**Referência.** MIT, versão atual 3.48 [[pylinac docs]](https://pylinac.readthedocs.io/).
Cobre Winston-Lutz, CBCT (CatPhan/Quart/ACR/Cheese), picket fence, starshot,
VMAT (DRGS/DRMLC), flatness/symmetry, TG-51/TRS-398, imagem planar e o
**Log Analyzer** (dynalog e trajectory log Varian, versões 2.1/3.0/4.0)
[[Log Analyzer]](https://pylinac.readthedocs.io/en/latest/log_analyzer.html).
Gera PDF nativamente (`publish_pdf()`) e a própria documentação define a meta
de "a maioria dos scripts em menos de 10 linhas".

**Crítica.** É QA de **máquina/imagem**, não QA de **plano** — não há
sobreposição real com o que `qualidade.py` já calcula (que é 100%
plano-a-partir-do-DICOM, sem imagem de EPID/CBCT nenhuma). Não substitui nada
existente; ocupa um espaço que o ISOCENTRO hoje não tem: não existe aba
de controle de máquina. O ponto de contato genuíno com o que já existe é o
**Log Analyzer**: ele lê trajectory logs Varian — o mesmo fabricante do
serviço — e devolve fluência planejada × entregue, erro de lâmina por eixo,
holdoff. É exatamente o dado que falta na aba **Ficha Virtual**, que hoje "só
mostra o que foi tratado (data e parâmetros da ficha técnica)" sem nada sobre
COMO foi entregue.

**Extensão.**
1. Nova aba **"QA de Equipamento"** (ver §4) usando os módulos de imagem do
   pylinac como motor de cálculo — a interface e a tabela de tolerância/status
   continuam sendo as do ISOCENTRO (mesmo padrão visual de
   `qualidade_tela.py`: pílula OK/Atenção/Fora da faixa, nunca verde).
2. Na aba **Ficha Virtual**, um painel "Log da entrega" por fração: para cada
   fração já tratada, se o trajectory log daquele campo estiver acessível
   (mesma dependência de identidade de rede que `gravar_banco.py`/`.bat` já
   tem — ver §5), rodar o Log Analyzer e mostrar erro RMS de lâmina e gamma
   fluência planejada×entregue. Isso fecha exatamente a lacuna que a nota do
   dia 20/08 registrou ao criar a aba ("a aba Radioterapeuta virou Ficha
   Virtual"): hoje ela mostra o que foi PROGRAMADO, não o que a máquina de
   fato fez.

### 2.2 PyMedPhys — segunda verificação por fluência

**Referência.** Apache 2.0, Python 3.10–3.12. Documentação own: "nenhuma API
é garantida estável entre versões" — projeto pré-1.0
[[docs.pymedphys.com]](https://docs.pymedphys.com/). O módulo relevante aqui é
**MU Density** (`pymedphys.mudensity`): confirmado na documentação que o
cálculo usa **as posições de lâmina do MLC e das mordentes**, não só as
mordentes [[MU Density]](https://master--pymedphys.netlify.app/ref/lib/mudensity.html).
Tem também **gamma** (2D/3D, dose ou fluência)
[[Gamma]](https://docs.pymedphys.com/users/ref/lib/gamma.html) e um módulo de
leitura de log (`Delivery`, Elekta e Varian).

**Crítica — este é o ponto mais importante do documento.** O próprio
`paralelo.py` documenta três limitações no cabeçalho, e a terceira é textual:
*"Não usa a abertura do MLC (...) Separar Sc (mordente) de Sp (abertura)
seria o certo, e exigiria duas tabelas em vez de uma Sc,p combinada. Enquanto
não houver, o resultado de IMRT/VMAT é rastreio grosseiro."* O `mudensity` do
PyMedPhys calcula exatamente essa abertura, a partir do próprio RT Plan — sem
precisar de tabela de máquina nenhuma, porque não é um cálculo de dose
absoluta, é um mapa de fluência relativa. Isso não substitui `paralelo.py`
(que é TMR/Scp com dose absoluta em UM), **complementa**: um é cálculo
analítico independente (TG-219, ponto único), o outro é comparação de
fluência 2D (mais perto do espírito do gamma de TG-218/TG-219 para campos
modulados). Dois métodos genuinamente independentes vale mais do que um só
mais sofisticado — é a mesma lógica que já rege `paralelo.py` vs. `qualidade.py`
(dois módulos, dois formalismos, nenhum lê resultado do outro).
O custo real é a instabilidade de API que a própria documentação admite: teria
que ser pinado com o mesmo rigor do resto do `requirements.txt`, e qualquer
bump exige revalidar contra casos já conferidos — a MESMA disciplina que já
existe para `pydicom`/`numpy`, não uma nova.

**Extensão.**
1. Na aba Qualidade, uma sub-tabela nova **"Verificação por fluência (MLC)"**,
   ao lado da tabela `_COLUNAS_PARALELO` já existente: por campo, MU density
   planejado × "recalculado" a partir do próprio RT Plan (sem log ainda — é
   uma checagem de autoconsistência do plano) e, quando houver log de entrega
   (ver 2.1), gamma fluência planejada×entregue. Duas travas na linha de
   `paralelo.maquina_do_plano`: sem log, mostra só a autoconsistência
   plano-vs-plano (baixo valor); com log, mostra a comparação real.
2. Estender `paralelo.py` para trocar o campo aberto pelo mordente por um
   fator derivado do `mudensity` quando o campo é modulado — isso é o item que
   tira o "rastreio grosseiro" documentado e transforma IMRT/VMAT em
   verificação de verdade. É trabalho de meses, não de uma tarde; entra no
   faseamento do §6 como o item de maior retorno clínico da lista inteira.

### 2.3 pydicom / pynetdicom — já em uso, extensão pontual

**Referência.** Já são dependência fixada (`pydicom==3.0.2`,
`pynetdicom==3.0.4`) e já sustentam `dicom_rt.py` (parse de CT/RP/RS/RD) e
`dicom_rede.py` (C-ECHO/C-FIND/C-GET/C-MOVE contra o DB Daemon do ARIA).

**Crítica.** Não há nada para "adicionar" no sentido de nova dependência —
seria enganoso listar como se fosse novidade. O ganho está em usar mais do
que já está pago.

**Extensão.**
1. **DICOM SR (Structured Report)** via `pydicom` para gravar o resultado do
   segundo cálculo (TG-219) e, se a extensão 2.2 avançar, o gamma de fluência,
   como objeto DICOM formal — não só no `FICHA_*.json`. Isso dá ao resultado
   da conferência um formato que o próprio ARIA sabe arquivar/associar ao
   plano, sem inventar um formato de arquivo novo. É opcional e não muda o
   fluxo atual — o JSON continua sendo a fonte que "sobrevive ao apagamento
   dos DICOM".
2. `dicom_rede.py` já evita abrir porta de entrada por preferir C-GET a
   C-MOVE — é a decisão certa e não deveria mudar. Se o Log Analyzer (2.1)
   precisar trazer trajectory logs por rede, a busca deveria seguir a MESMA
   regra: nunca abrir um SCP de armazenamento neste app. Trajectory logs não
   trafegam por C-MOVE/C-GET (não são objetos DICOM) — teriam que vir pelo
   mesmo padrão `.bat` com identidade de rede que já existe para
   `gravar_banco.py`/`atividades.py`, lendo direto do compartilhamento onde o
   TrueBeam/Aria grava os logs. Isso é decisão de infraestrutura da clínica,
   não de biblioteca — mas é o tipo de detalhe que, se ignorado, faz a
   proposta do §2.1 parecer mais simples do que é.

### 2.4 QATrack+ — não é biblioteca, é referência de modelo de dados

**Referência.** Django (Python) + PostgreSQL/MySQL/MSSQL, MIT, "transicionando
para um modelo de manutenção comunitária" em 2025–2026, com hospedagem
comercial disponível via RadMachine (Radformation)
[[qatrackplus.com]](https://qatrackplus.com/). Modelo de dados: **Test List**
(coleção de testes), **Test Instance** (uma medição), tolerância/nível de
ação, frequência e unidade — tudo "não amarrado a fabricante".

**Crítica, sem meio-termo.** QATrack+ é uma aplicação web completa —
servidor, banco relacional, navegador. Isso colide **diretamente** com a
arquitetura declarada no `README.md`: app local, processo único, empacotado
como um `.exe` via PyInstaller, sem servidor. Importar QATrack+ "como
biblioteca" não é uma opção que existe — não tem essa forma. A única maneira
honesta de usar QATrack+ seria a clínica rodar uma instância separada (outro
servidor, outro processo de adoção, outra equipe de TI) e o ISOCENTRO, no
máximo, exportar dados para lá por API/CSV. Isso é um projeto à parte, não um
incremento do ISOCENTRO.

**Extensão — o que sobra de aproveitável.** O **modelo de dados**. "Test
List → Test Instance → tolerância/ação → frequência", com trending por
unidade, é uma boa carta arquitetural para desenhar a nova aba **QA de
Equipamento** (§2.1) SEM adotar o QATrack+ em si: um schema local (SQLModel/
SQLite, ver §3.3) com as mesmas quatro entidades, alimentado pelos módulos do
pylinac, mostrado no mesmo padrão de tabela/pílula da aba Qualidade. Se algum
dia a clínica adotar QATrack+ como sistema central, o schema já nasce
parecido o bastante para exportar sem remodelar tudo.

### 2.5 DICOMautomaton — ferramenta de pesquisa, nunca no caminho clínico

**Referência.** C++, GPLv3+, desenvolvimento ativo (histórico extenso de
commits, CI, imagens Docker). Registro deformável (TPS-RPM), operações de
contorno (erosão/dilatação/booleanas), reconstrução de superfície, DVH,
modelagem radiobiológica (BED/EQD2). **Não calcula dose** — e os próprios
autores escrevem que a ferramenta **não deve ser usada clinicamente**, só em
pesquisa, com saída sempre validada pelo usuário
[[GitHub hdclark/DICOMautomaton]](https://github.com/hdclark/DICOMautomaton).

**Crítica.** O aviso do próprio autor já é a crítica — e ele é exatamente o
mesmo padrão de cautela que `paralelo.py` já aplica sozinho ("resultado sai
marcado como DEMONSTRAÇÃO e sem veredito" quando falta tabela de máquina).
GPLv3+ para uma chamada externa via linha de comando (subprocess, sem linkar
biblioteca C++ dentro do processo Python) não contamina a licença do
ISOCENTRO da mesma forma que linkar estaticamente contaminaria — mas isso
não é aconselhamento jurídico e merece uma checagem própria antes de
distribuir o `.exe` com o binário do DICOMautomaton junto. Mais simples:
**não empacotar** — tratar como ferramenta de bancada do físico, fora do
`ISOCENTRO.exe`, no mesmo espírito de `tools/`.

**Extensão.** Uso pontual, offline, nunca no caminho do documento impresso:
1. **Registro deformável** para casos de replanejamento — somar dose do curso
   1 (deformado para a anatomia do curso 2) com o curso 2, quando a
   pergunta clínica é "quanto essa região já recebeu no total". Hoje isso não
   existe no ISOCENTRO e não é trivial de fazer sem registro deformável.
2. **Métricas de concordância de contorno** (Dice, Hausdorff) como ferramenta
   de bancada para QA de segmentação — útil se algum dia entrar
   auto-contorno no fluxo, não antes.

Os dois usos ficam em `tools/`, chamados por linha de comando, com saída
sempre revisada por uma pessoa — nunca escrevendo na ficha sozinhos.

### 2.6 dicompyler-core — oráculo de validação, não dependência de runtime

**Referência.** BSD, `dicomparser`/`dvh`/`dvhcalc`/`dose`. Última versão
publicada é a 0.5.6, de maio de 2023 [[PyPI]](https://pypi.org/project/dicompyler-core/)
— sem aviso formal de arquivamento, mas dois anos sem release confirmam a
leitura de "descontinuado" já registrada. O `dvhcalc` faz exatamente o que
`dicom/dvh.py` já faz: rasteriza contorno do RT Struct sobre a grade do RT
Dose e monta o DVH cumulativo — é uma implementação **independente** do
mesmo problema.

**Crítica.** Não faz sentido adicionar como dependência de runtime: seria
puxar um pacote parado há dois anos para dentro de um `requirements.txt` cuja
filosofia inteira é "versão fixa, revalidada a cada bump" — o risco não
compensa quando o ISOCENTRO já tem a própria implementação rodando em
produção. A leitura de "descontinuado, mas útil como referência" já estava
certa antes desta pesquisa; a pesquisa só confirma a data.

**Extensão — é aqui que ele vale, e só aqui.** Como **oráculo de teste**, só
em tempo de desenvolvimento, nunca embarcado no `.exe`: rodar `dvhcalc` do
dicompyler-core contra os MESMOS RT Dose/RT Struct sintéticos de
`TCs_Teste/` que já validam `dvh.py`, e comparar os dois DVHs. Duas
implementações independentes concordando é uma evidência de correção mais
forte do que uma suíte de testes sozinha contra um fantoma sintético — e é
exatamente o padrão que o `README.md` já descreve para os testes de SSD
("fantomas sintéticos de resposta analítica"). Entra como um teste a mais em
`tests/`, com `dicompyler-core` como dependência **de desenvolvimento**
(`requirements-dev.txt` ou extra), nunca do pacote distribuído.

---

## 3. Infraestrutura: interface, dados e a "camada de IA"

### 3.1 pyqtgraph — sim, dentro do Qt existente; Streamlit — não, quebra o modelo

**pyqtgraph.** BSD, renderização acelerada por OpenGL, widget Qt nativo
[[pyqtgraph.org]](https://www.pyqtgraph.org/). Comparação publicada pelo
próprio projeto (números promocionais, mas a direção é consensual na
comunidade científica Python): ~50–60 fps e <10 ms de latência contra ~5–15
fps e ~200 ms do Matplotlib em atualização interativa
[[pyqtgraph.com]](https://pyqtgraph.com/is-pyqtgraph-better-than-matplotlib-for-live-plots/).
**Crítica**: o ISOCENTRO já usa Matplotlib para cortes/3D/DVH, mas
**para o PNG que entra no PDF** — ali a velocidade não importa, é renderizado
uma vez. Onde importa é na navegação interativa da aba **Visualizador**
(scroll de corte axial/sagital/coronal, troca de janela mama/pulmão/osso) —
se essa navegação hoje usa o mesmo widget Matplotlib embutido em Qt
(`FigureCanvasQTAgg`), é ali que a lentidão se sentiria com volumes grandes.
**Extensão**: pyqtgraph para o widget interativo de navegação (ganho real de
responsividade, mora inteiramente dentro do PyQt5 já usado, sem novo processo
nem servidor), Matplotlib continua como está para o que vai para o papel — a
mesma divisão que `papel/` × `interface/` já impõe no resto do projeto. Ponto
de atenção prático, não teórico: `ARMADILHAS.md` já documenta que
`QT_QPA_PLATFORM=offscreen` não desenha texto e que a `JanelaPrincipal` cai
sem `setStyleSheet` antes — um widget pyqtgraph novo entra na MESMA rotina de
conferência do `tools/tela.py`, não numa nova.

**Streamlit.** Não recomendado dentro do ISOCENTRO, e a razão está
escrita no próprio `README.md`: *"os dados do paciente não saem da máquina:
tudo roda em processo local"*, empacotado como um `.exe` único. Streamlit
precisa de um servidor web local e de um navegador — dois processos, uma
porta aberta, uma superfície nova — exatamente o tipo de coisa que
`dicom_rede.py` evita ao preferir C-GET a C-MOVE só para não abrir porta
nenhuma. Não é questão de gosto de interface, é meta-conflito arquitetural.
**Onde poderia caber**: só como ferramenta **separada**, fora do
`ISOCENTRO.exe`, se o "painel de indicadores agregados do serviço" (ideia
já cogitada, ainda em avaliação) virar realidade — porque ali o dado é
agregado por serviço, não a ficha individual de um paciente, e rodar num
servidor de gestão (não na estação de tratamento) já é uma decisão
categoricamente diferente. Mesmo nesse caso, vale considerar antes uma tela
PyQt5/pyqtgraph a mais dentro do app existente — mais um processo é mais uma
coisa para manter.

### 3.2 Pydantic — validação declarativa dos JSON que já existem

**Crítica.** O projeto já valida "na mão": dataclasses (`IndicesAlvo` e
afins) para o que é calculado em memória, parsing manual para o que é lido de
disco (`registro_json.py`, `diff_versoes.py`). O ganho de Pydantic não é
"passar a validar" — já se valida, cada arquivo tem regra própria escrita à
mão. O ganho é **centralizar** a regra e ganhar mensagem de erro clara quando
um JSON de instalação antiga não bate mais com o formato esperado — hoje
isso provavelmente falha silenciosamente ou com uma exceção genérica em
algum ponto do parsing manual. Pydantic v2 (core em Rust) é rápido o
suficiente para não pesar na abertura de ficha; a ressalva é a mesma de
sempre — pinar a versão exata e revalidar ao atualizar, porque a mudança de
v1 para v2 já quebrou API de muita gente, e não há razão para achar que v2
para v3 será diferente.

**Extensão.** Modelos Pydantic como camada de FRONTEIRA em `dados/*` —
`SimulacaoModel`, `FichaRegistroModel`, `ConfigServicoModel` — validando na
leitura e na escrita, mas gravando o MESMO JSON de sempre
(`model.model_dump()` continua sendo dict → `json.dumps`), sem mudar o
formato em disco nem quebrar `migrar.ps1`. Baixo risco, porque não migra
dado nenhum: só formaliza o que já é lido e escrito hoje.

### 3.3 SQLModel — onde o `.lock` manual já denuncia o problema certo

**Crítica.** O padrão `registro_fichas.json.lock`, `checklist_pre_tratamento.json.lock`,
`config_servico.json.lock` na raiz do projeto é o sintoma mais direto de
"isto já devia ser um banco": lock de arquivo é a forma mais frágil de
resolver escrita concorrente, e a pasta de rede
`\\fileserver.clinica.example\Gerenciamento de Pacientes\` prevista para o
ISOCENTRO torna concorrência real (várias estações, mesma pasta) e não
hipotética. SQLModel (Pydantic + SQLAlchemy) sobre SQLite em modo WAL
resolve exatamente essa classe de problema — transação real, sem inventar
protocolo de lock.

**Onde NÃO aplicar**: o registro versionado por paciente (`FICHA_*.json`)
deve continuar como está. A propriedade que o `README.md` descreve —
"sobrevive ao apagamento dos DICOM", um arquivo autocontido por paciente,
copiável, legível sem programa nenhum se necessário — é justamente o que um
banco central destruiria. Banco é para dado **agregado/administrativo**, não
para o documento clínico por paciente.

**Extensão — os candidatos reais, já nomeados na conversa que precedeu este
documento:**
- **Vencimentos** (já planejada): tabela `vencimento(categoria, item,
  data_realizacao, data_vencimento)`, com a regra "ASOs mostra só os 10 mais
  próximos" virando um `ORDER BY data_vencimento LIMIT 10` de verdade, em vez
  de carregar tudo em memória e cortar em Python.
- **QA de Equipamento** (§2.1/§2.4): schema Test List/Test Instance,
  alimentado pelos módulos do pylinac.
- **Índice central** (`dados/indice.py`), hoje o que `aprendizado.py` lê —
  migrar para SQLite daria consulta por máquina/técnica sem varrer tudo a
  cada ficha nova, e abriria caminho para o SPC de verdade do §4.
- **Care Path** (registro de quem fez cada etapa — ideia já registrada):
  é literalmente uma tabela de eventos (`etapa, quem, quando, paciente`),
  o caso de uso mais óbvio de todos para SQLModel na lista.

### 3.4 Busca vetorial local (ChromaDB/LanceDB) — só para recuperar, nunca para gerar

**Crítica que vem antes de qualquer proposta.** Este é o item onde a regra
"nunca inventar dado" pesa mais, porque é o único dos dez que lida com texto
livre e teria uma tentação óbvia de "deixar o modelo preencher". Isso não
entra em nenhuma hipótese aqui: o papel de uma busca vetorial neste projeto é
**recuperação** (achar o item mais parecido e mostrar QUAL é, com nome/data),
nunca geração de valor clínico. É a mesma fronteira que `aprendizado.py` já
traça entre "comparar e apontar" e "preencher campo" — a extensão abaixo
herda essa fronteira, não a move.

**ChromaDB vs. LanceDB**, ambos embarcáveis sem servidor: ChromaDB nas
versões recentes roda com um client persistente local (SQLite + HNSW),
mais leve do que a geração antiga baseada em DuckDB; LanceDB é um formato de
arquivo colunar (Rust) pensado para embutido desde o início, sem processo
próprio. Para um app local single-exe, os dois cumprem "sem servidor" — a
escolha entre eles é menos crítica do que garantir que o índice vetorial vive
DENTRO da pasta de dados do app (nunca em serviço externo) e é reconstruível
a qualquer momento a partir dos `.docx`/JSON de origem, nunca a única cópia
de nada.

**Extensão concreta, ancorada no que já existe:**
1. **Biblioteca de notas de posicionamento** (39 modelos `.docx`, já semeada):
   indexar por embedding e, ao cadastrar uma simulação fora do padrão
   (`Nova`), sugerir a nota mais parecida já existente antes de criar do
   zero — reduzindo duplicação de notas quase-idênticas na biblioteca. Isso
   pede também extração de PDF/DOCX com reconhecimento de layout (para notas
   que não são texto puro), mas o ganho é pequeno perto do próximo item.
2. **`aprendizado.py`**: hoje o "balde" de comparação é exato
   (máquina+técnica). Um índice vetorial sobre o histórico permitiria achar
   "os 5 casos mais parecidos com este" por similaridade de prescrição/técnica
   mesmo quando o balde exato tem menos que `MIN_AMOSTRA`, ENTREGUE como
   citação — "ver casos X, Y, Z" — nunca como um número novo de faixa
   inferida. Isso não substitui a checagem aritmética nem o SPC do §4: soma-se
   como uma terceira fonte de contexto, sempre citável.

---

## 4. Onde cada coisa agrega — tabela consolidada por aba

| Aba / módulo hoje | Contribuição | Origem |
|---|---|---|
| **Qualidade** — índices do alvo | (sem mudança — já cobre ICRU 83/RTOG/Paddick) | — |
| **Qualidade** — 2º cálculo (TMR/Scp) | Segundo método independente por fluência de MLC, tira a lacuna documentada de "rastreio grosseiro" em IMRT/VMAT | PyMedPhys `mudensity`/`gamma` (§2.2) |
| **Qualidade** — geral | Validação cruzada do DVH em tempo de desenvolvimento (nunca em runtime) | dicompyler-core (§2.6) |
| **Ficha Virtual** (tratamento entregue) | Painel "Log da entrega": erro de lâmina, gamma fluência planejado×entregue, por fração | pylinac Log Analyzer (§2.1) |
| **Visualizador** (cortes/3D/DVH) | Navegação interativa mais responsiva (scroll, janela) | pyqtgraph (§3.1) |
| **Administração** — inventário/config | Validação declarativa dos JSON de configuração | Pydantic (§3.2) |
| **Administração** — dado agregado | Fim do `.lock` manual; base para Vencimentos, Care Path, índice central | SQLModel/SQLite (§3.3) |
| **Capa** — biblioteca de notas | Sugestão de nota parecida ao cadastrar setup fora do padrão | Busca vetorial local (§3.4) |
| **Aprendizado** | Terceira fonte de contexto por similaridade, sempre citável | Busca vetorial local (§3.4) |
| **Rede DICOM** | Objeto SR formal para o resultado da conferência | pydicom (§2.3) — sem dependência nova |

---

## 5. Abas novas

### 5.1 "QA de Equipamento" (nova)

A única lacuna real de escopo — hoje não existe controle de máquina no
ISOCENTRO, só controle de plano. Motor de cálculo: módulos de imagem do
**pylinac** (Winston-Lutz, CBCT, picket fence, starshot, flatness/symmetry,
TG-51). Modelo de dados: **Test List / Test Instance / tolerância / ação /
frequência**, no espírito do QATrack+ mas local (§2.4), persistido em
**SQLModel/SQLite** (§3.3). Interface: o mesmo padrão visual de
`qualidade_tela.py` — pílula OK/Atenção/Fora da faixa, nunca verde, aviso de
calibração em primeiro lugar quando a tolerância ainda é da literatura e não
do processo local (mesma regra de `qualidade.CALIBRADO`).

Isto por si só responde a duas das ideias já registradas para "avaliar
amanhã": controle de qualidade de equipamento com periodicidade/status, e
parte do painel de indicadores (pelo menos o lado "máquina", não o lado
"serviço inteiro").

### 5.2 Sub-painel "Verificação por fluência (MLC)" dentro de Qualidade

Não é uma aba nova, é uma tabela nova ao lado de `_COLUNAS_PARALELO`,
alimentada pelo `mudensity` do PyMedPhys (§2.2). Listada aqui separadamente
porque é, das dez bibliotecas avaliadas, a que fecha uma lacuna já
**documentada em código** — não uma lacuna inferida por esta análise.

---

## 6. Ir além: o que fecha o que o próprio código já está pedindo

Três extensões que não vêm de nenhuma das dez bibliotecas isoladamente, mas
nascem de somar duas ou três delas ao que o `qualidade.py`/`aprendizado.py`
já admitem estar faltando:

1. **SPC de verdade (TG-218), fechando `CALIBRADO=False`.** O índice central
   migrado para SQLite (§3.3) dá consulta rápida por máquina+técnica; com
   isso, calcular mediana e desvio por processo (Pawlicki, controle
   estatístico) deixa de exigir "esperar dado suficiente sem estrutura para
   agregá-lo" e vira uma consulta. Quando `n` por contexto passar de um
   limiar (o mesmo `MIN_AMOSTRA=6` que `aprendizado.py` já usa, ou maior — é
   decisão clínica), a tolerância de `qualidade.py` deixa de vir só da
   literatura e passa a citar as duas: "literatura: X; processo local (n=42):
   Y". Isto não precisa de biblioteca nova — NumPy já basta para
   mediana/desvio — o que faltava era o dado organizado para consultar, que é
   exatamente o que o SQLModel resolve.
2. **Verificação contínua, não só no fechamento do plano.** Hoje o 2º cálculo
   roda uma vez, na aba Qualidade, antes do tratamento começar. Com o Log
   Analyzer (§2.1) lendo trajectory log por fração na aba Virtual, a mesma
   lógica de "desvio dentro/fora de faixa" pode rodar a CADA fração entregue,
   não só no plano — detectando deriva (uma lâmina que começa a errar mais a
   cada sessão) antes que vire um erro isolado grande. É uma extensão de
   meses, não de uma tarde, mas é o tipo de coisa que aproxima o ISOCENTRO
   de "melhor sistema acessório" de verdade: a maioria dos softwares
   acessórios de radioterapia verifica o plano; poucos verificam a entrega
   sessão a sessão.
3. **Toda recuperação por similaridade (busca vetorial, §3.4) cita a fonte.**
   Não é uma proposta nova, é uma trava que vale registrar aqui explicitamente
   porque vale para as três extensões acima juntas: nenhuma delas pode virar
   "o sistema decidiu que está OK" sem citar EXATAMENTE em que dado, caso ou
   cálculo se baseou — imagem espelho da regra que já rege `aprendizado.py`
   ("o palpite errado se assina, o campo vazio se vê").

---

## 7. Faseamento sugerido, por risco/esforço

| Fase | Item | Por quê primeiro/depois |
|---|---|---|
| 1 | Pydantic nos modelos de `dados/*` | Baixo risco, não muda formato em disco, prepara terreno para o resto |
| 1 | SQLModel para Vencimentos e Care Path | Tabelas novas, sem dado legado para migrar — o caso mais seguro para aprender a ferramenta |
| 2 | pyqtgraph no Visualizador | Contido dentro do PyQt5 já existente; risco é só de empacotamento (testar com `tools/gerar_executavel.py`) |
| 2 | dicompyler-core como oráculo de teste | Só em dev, zero risco de runtime |
| 3 | pylinac — aba QA de Equipamento | Escopo novo, mas isolado (não toca ficha nem capa) |
| 3 | SQLModel para o índice central + SPC (TG-218) | Depende da Fase 1 madura; é o item de maior valor clínico de médio prazo |
| 4 | PyMedPhys `mudensity`/gamma na aba Qualidade | Maior valor clínico da lista inteira, mas também o de maior custo de validação (API beta, precisa revalidar contra casos conferidos) |
| 4 | pylinac Log Analyzer na Ficha Virtual | Depende de acesso a trajectory log por rede — é decisão de infraestrutura da clínica, não só de código |
| Bancada (fora do `.exe`) | DICOMautomaton para registro deformável/soma de dose | Nunca embarcado; ferramenta de físico, sempre revisada à mão |
| Avaliar depois | Busca vetorial (notas + aprendizado) | Maior ambiguidade de escopo da lista; vale prototipar pequeno antes de comprometer arquitetura |
| Fora do ISOCENTRO | Streamlit / QATrack+ completo | Só fazem sentido como ferramenta ou sistema separado, nunca dentro do `.exe` local |

---

## 8. Os 61 repositórios de `codigo-externo` (21/10/2026)

Critérios: se atende um FR do MVP; se a linguagem serve (Python entra no app,
C# só no avaliador ESAPI da AD-15); se a licença permite reuso (sem licença =
só leitura, GPL só como ferramenta externa); e se respeita a arquitetura (só
leitura no ARIA, AD-16; dado não sai da rede, AD-7; nenhum servidor dentro
do executável). O veredito de cada repositório também está na coluna `nota`
de `conhecimento/matriz/codigo.csv`.

### 8.1 Usar no código do ISOCENTRO (Python)

| Repositório | Onde entra | Ressalva |
|---|---|---|
| pydicom, pynetdicom, pyodbc | Já são dependências fixadas | Nada a mudar |
| jrkerns/pylinac (MIT) | FR-46: picket fence, Winston-Lutz, CBCT, starshot | Não usar `calibration/trs398.py` no FR-45: o kQ é o do TRS-398 de 2000; o ISOCENTRO calcula pela tabela da Rev. 1 |
| blairconrad/dicognito (MIT) ou pydicom/deid (MIT) | FR-6 (casos semeados) e FR-26 (exportação com paciente) | O `dicom-teste/pseudonimizar.py` já faz o básico com pydicom; um dos dois pode substituí-lo ou conferi-lo |
| kildealab/TG263ComplianceTool (MIT) ou o3-core/TG263NameChecker (Apache) | Vocabulário TG-263 do núcleo (fase 0 do brief) | Nenhum traz a tabela TG-263; o vocabulário vem da `TG-263-PLANILHA` da base de conhecimento |

### 8.2 Só em teste, nunca no executável

| Repositório | Para quê |
|---|---|
| dicompyler-core, glucee/DVH (MIT) | Oráculos independentes do `dicom/dvh.py` |
| MAAS-PlanComplexity (C#) | Conferir MCS/SAS do `qualidade.py` (FR-43); licença própria, ler o LICENSE antes |
| pydicom-data | Arquivos RT de teste |
| DCMTK, Orthanc (GPL) | Ferramentas externas: diagnóstico de rede e servidor DICOM de testes; `tools/servidor_dicom_local.py` já cobre parte |
| KitwareMedical/dicom-anonymizer (BSD) | Perfil PS3.15 para conferir se a pseudonimização cobre todas as tags |

### 8.3 Avaliador ESAPI em C# (AD-15, repositório `scriptsvarian`)

Compilam contra a ESAPI 15.6, a versão instalada:

- **LDClark/PlanCheck** (MIT): regras para FR-19, FR-21 e FR-42; o mais aproveitável do grupo.
- **brjdenis/VarianESAPi-Dosimetry** (MIT): objetivos de dose.
- **MAAS-PlanScoreCard**: licença própria, só consulta até ler o LICENSE.
- **VarianESAPI-EQD2Converter** (MIT): BED/EQD2 (H03, I03), fora do MVP.
- ESAPIX e Varian-Code-Samples (MIT): apoio de infraestrutura.
- PlanCheck_article (MIT): escrito para a ESAPI 16.1, exige porte.

### 8.4 Referência de modelo ou formato (ler, não importar)

- **qatrackplus**: modelo de lista de testes, tolerância e ação; o
  `scripts/create_dqa3_testlist.py` lista os campos da exportação do
  **DailyQA 3**, o formato ainda não levantado no FR-26.
- **IMRT-QA-Data-Miner** (MIT, `parsers/sncpatient.py`) e o leitor
  `_experimental/.../mapcheck` do pymedphys (Apache): leitura de **MapCHECK**,
  para o FR-26 quando o PSQA entrar (no MVP só CQ de máquina).
- **pymedphys**: gama e mudensity; API beta, depois do MVP. Não tem Clarkson,
  que é o que o FR-13 prevê para o modulado.
- DVH-Analytics, EclipseDataMiner, TPS_QAHelper: indicadores e integração com
  QATrack+, fora do MVP.

### 8.5 Descartar

| Motivo | Repositórios |
|---|---|
| Escrevem no ARIA (viola AD-16) | PDFtoAria, PDFtoAriaPlugin, pushAriaDoc |
| Sem licença | brachy-hdr-tg43-check, Point-Dose TG-43, BED_Calc, DVH-Check, MetricExtractor, RapidPlanQ, UAB-RO TG-263 (×2), Evil-DICOM, DICOM_Communication_101, VarianDeveloper, dicompyler, ESAPI_DICOMrt-Mining |
| Fora do escopo do MVP | rt-utils, DicomRTTool (GPL), pydicer, platipy, SlicerRT, SlicerRadReirradiation, RadComp, MAAS-UncertaintyClinicalGoals, BatchExportGUI, BatchExport_AURAReport, winston_lutz_multi (GPL; pylinac cobre), RSNA/anonymizer (aplicação completa) |
| Superados ou incompatíveis | pynetdicom_wrapper (`dicom_rede.py` já faz), MAAS-DICOMtools (ESAPI 18.1), uhg-plancheck (parado desde 2016), gacou54/tg263 (2019), PyESAPI (a AD-15 põe a ESAPI em C# gravando JSON, não dentro do processo Python) |
| Servidor web | QATrack+ como sistema (só o modelo de dados serve) |

### 8.6 Lacunas: o que nenhum repositório cobre

- Clarkson por ponto de controle para o modulado (FR-13).
- Leitura da exportação do DailyQA 3 (só a lista de campos no QATrack+).
- Cálculo TG-43 com licença de reuso.

---

## Referências

- AAPM TG-218 (2018) — tolerância/ação e calibração local por SPC; McNiven,
  Sharpe & Purdie (2010); Masi et al. (2013); Paddick (2000, 2006); ICRU 83
  (2010) — já citadas no cabeçalho de `dominio/qualidade.py`.
- AAPM TG-219 (2021) — verificação independente de UM; AAPM TG-114 (2011) —
  já citadas no cabeçalho de `dominio/paralelo.py`.
- pylinac — [documentação](https://pylinac.readthedocs.io/) · [Log Analyzer](https://pylinac.readthedocs.io/en/latest/log_analyzer.html) · [GitHub](https://github.com/jrkerns/pylinac)
- PyMedPhys — [documentação](https://docs.pymedphys.com/) · [MU Density](https://master--pymedphys.netlify.app/ref/lib/mudensity.html) · [Gamma](https://docs.pymedphys.com/users/ref/lib/gamma.html)
- QATrack+ — [site](https://qatrackplus.com/) · [GitHub](https://github.com/qatrackplus)
- DICOMautomaton — [GitHub](https://github.com/hdclark/DICOMautomaton)
- dicompyler-core — [GitHub](https://github.com/dicompyler/dicompyler-core) · [PyPI](https://pypi.org/project/dicompyler-core/)
- pyqtgraph — [site](https://www.pyqtgraph.org/) · [comparação com Matplotlib](https://pyqtgraph.com/is-pyqtgraph-better-than-matplotlib-for-live-plots/)
