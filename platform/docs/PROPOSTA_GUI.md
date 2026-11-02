# Proposta de divisão do `gui.py`

Frente **R-05** (robô, 16/09/2026). **É proposta:** nenhuma linha do `gui.py`
mudou para escrevê-la. Executar é a **R-06**, do usuário — `interface/` é tela,
e tela muda com aceite.

Tudo aqui foi **medido**, não lido: `tools/mapa.py gui.py --metodos` para os
intervalos, e um script de AST descartável (em
`relatorios_ferramentas/tmp_robo/`, fora do git) para chamadas e atributos: para
cada método da `JanelaPrincipal`, quais `self.<método>` ele cita, quais
`self.<atributo>` grava e lê, e quais nomes do topo do módulo usa. O resto é
`grep` em `tests/`, `tools/` e no pacote. As linhas citadas são as do commit
`fcbac1a`, e **envelhecem**: na R-06, medir de novo antes de cortar.

---

## 1. O tamanho, e o que já foi decidido

| | 31/08/2026 | 16/09/2026 |
|---|---|---|
| `gui.py` | 5.073 | **5.728** |
| `JanelaPrincipal` | 4.484 (88%) | **5.143 (90%)** |
| métodos da `JanelaPrincipal` | — | 175 |
| atributos de instância distintos | — | 77 |
| `.connect(` no arquivo | — | 61 |

Os **655 linhas** que entraram desde a divisão anterior foram **todas** para a
classe (4.484 → 5.143). O que está fora dela quase não mudou.

**A divisão por arquivo acabou em 31/08** (`notas/2026-08.md`, "A divisão do
`gui.py` chegou ao fim"): sete módulos saíram, e o que sobrou é a
`JanelaPrincipal`. A mesma seção deixou duas decisões que esta proposta
**mantém**:

- **Mixin, não.** Medido em 27/08: em cinco dos sete temas, 100% dos atributos
  do tema eram tocados por outro tema. Mixin divide o arquivo sem dividir o
  estado; para entender um método seria preciso saber em qual dos arquivos mora
  o atributo. A medida de hoje é **pior** (seção 3): em **8 dos 10** blocos,
  nenhum atributo é só dele.
- **Se for encarar, é composição** — um objeto por tema, com estado próprio —
  e isso muda comportamento, portanto pede o portão de conferência (seção 6).

---

## 2. Os blocos

A classe está escrita em ordem de tema; os intervalos abaixo são contíguos (só
`capa` e `pdf` aparecem em dois pedaços).

| bloco | intervalo | métodos | linhas | o que é |
|---|---|---|---|---|
| `montagem` | 349–732 | 1 | 384 | o `__init__`: constrói widgets, liga os 61 sinais |
| `navegacao` | 734–955 | 10 | 193 | `closeEvent`, arrastar-soltar, atalhos, `_trocar_modo` |
| `bancada` | 957–1494 | 24 | 512 | a Fichinha: gerar, conferir, prévia, imprimir, liberar, recentes, atividades |
| `capa` | 1501–1565, 2228–2768 | 20 | 587 | aba Capa e o cadastro de simulação |
| `qualidade` | 1575–1595 | 1 | 21 | `_qualidade_ao_abrir` |
| `tratamento` | 1597–2220 | 22 | 596 | Ficha Virtual (painel do radioterapeuta) + 5 leitores do índice |
| `pasta` | 2770–3185 | 14 | 401 | abrir/carregar pasta, reabrir registro, **limpeza do caso** |
| `viewer` | 3189–3958 | 37 | 728 | TC, planos, soma de dose, 3D, cortes |
| `pdf` | 3962–4064, 4667–5217 | 13 | 642 | montar recursos, construir a ficha, arquivar, `_gerar_pdf` |
| `conferencia` | 4066–4664 | 25 | 569 | pendências, SUS, gating, 600CD, prévia, progresso |
| `pos_carga` | 5219–5490 | 8 | 264 | perguntas depois da carga, agendamento, edição, `carregar_registro` |

Fora da classe: `DialogEscolherPaciente` (168–284, **fica**: decidido em 31/08,
vive colado ao `_carregar_pasta`), três auxiliares numéricas (`_para_numero`,
`_trio`, `_dose_prescrita`, 299–345), dois leitores (`_texto_da_nota`,
`_pasta_tem_dicom`) e o arranque (`_avisar_erro`, `_instalar_rede_de_seguranca`,
`_usuario_de_dev`, `main`: 5577–5723, 141 linhas).

---

## 3. Quem chama quem

Conta de pares método→método por `self.<método>` (a linha chama a coluna). A
diagonal é chamada **dentro** do bloco.

| de \ para | mont | nav | banc | capa | qual | trat | pasta | view | pdf | conf | pós |
|---|---|---|---|---|---|---|---|---|---|---|---|
| montagem | 0 | 4 | 9 | 11 | 0 | 9 | 5 | 7 | 0 | 3 | 3 |
| navegacao | 0 | **5** | 5 | 1 | 1 | 1 | 3 | 0 | 0 | 1 | 3 |
| bancada | 0 | 3 | **17** | 1 | 1 | 1 | 4 | 0 | 2 | 5 | 1 |
| capa | 0 | 1 | 0 | **13** | 0 | 2 | 1 | 0 | 0 | 1 | 0 |
| qualidade | 0 | 0 | 0 | 0 | **0** | 0 | 0 | 1 | 0 | 0 | 0 |
| tratamento | 0 | 0 | 0 | 1 | 0 | **18** | 0 | 0 | 0 | 0 | 0 |
| pasta | 0 | 0 | 1 | 1 | 0 | 1 | **14** | 3 | 0 | 1 | 1 |
| viewer | 0 | 0 | 0 | 0 | 0 | 0 | 2 | **42** | 0 | 2 | 1 |
| pdf | 0 | 0 | 2 | 1 | 0 | 1 | 2 | 4 | **14** | 9 | 2 |
| conferencia | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | **14** | 0 |
| pos_carga | 0 | 1 | 1 | 0 | 0 | 0 | 2 | 5 | 0 | 4 | **3** |

O que a matriz diz:

- **`tratamento` e `conferencia` são folhas.** Cada um chama UM método de fora
  (`_capa_do_caso → _capa_buscar`; `_escolher_ficha → _gerar_pdf`). São os
  candidatos baratos.
- **`viewer` é coeso** (42 dentro, 5 fora), mas o problema dele não é chamada:
  é estado (seção 4).
- **`bancada`, `navegacao` e `pos_carga` são cola.** Chamam mais para fora do
  que para dentro (bancada 18 × 17; navegação 15 × 5; pós-carga 13 × 3). Não
  são tema: são o fluxo que amarra os temas, e o lugar deles é a janela.
- **`pdf` tem UMA entrada** (`_gerar_pdf`, chamado pela bancada e por
  `_escolher_ficha`), mas chama 21 de fora — 10 deles no `_gerar_pdf` sozinho
  (165 linhas), quase todos portões da `conferencia`.
- **`montagem` só sai** (51 referências, sem entrada): é o `__init__` ligando
  sinal a método. Cada método que sair da classe muda uma linha aqui.

As entradas de cada bloco — o que teria de continuar acessível depois do corte
— estão na seção 6, corte a corte.

---

## 4. O estado

| bloco | atributos tocados | só dele | grava |
|---|---|---|---|
| montagem | 70 | 11 | 62 |
| navegacao | 17 | 0 | 1 |
| bancada | 21 | 4 | 3 |
| capa | 15 | 0 | 7 |
| qualidade | 4 | 1 | 1 |
| tratamento | 9 | 0 | 4 |
| pasta | 36 | 0 | **24** |
| viewer | 22 | 0 | **17** |
| pdf | 21 | 0 | 2 |
| conferencia | 15 | 0 | 3 |
| pos_carga | 14 | 0 | 9 |

"Só dele" conta a montagem como outro bloco: quase todo atributo nasce no
`__init__`. Descontada ela, os que só um tema grava são os **candidatos a sair
junto**: `_medicos_tratamento`, `_paciente_em_foco`, `_refs_tratamento`
(tratamento); `_capa_buscando`, `_capa_caminho`, `_capa_completa_pedida`,
`_pacientes_carregados`, `_refs_pacientes` (capa); `_worker_3d` (viewer).

**Os compartilhados por quase todos** são peças da janela, não de tema: `form`
(11 blocos), `status` (9), `_dados` (9), `capa` (6), `fichinha` (5),
`_usuario` (5).

### O estado do CASO

O achado que mais pesa na proposta. **25 atributos descrevem o paciente
carregado**, e são zerados um a um, à mão, em `_executar_limpeza`
(2995–3014): `_dados`, `_ct`, `_rs`, `_rd`, `_png_3d`, `_rs_3d`,
`_rs_estruturas`, `_png_3d_rs`, `_cache_3d`, `_modo_soma`, `_dose_soma`,
`_rs_soma`, `_indices_soma`, `_planos`, `_plano_ativo`, `_agendamento`,
`_agendamento_pendente`, `_perguntas_pendentes`, `_pasta_carregada`,
`_origem_temporaria`, `_registro_carregado`, `_drrs_png_caso`,
`_drrs_titulos_caso`, `_tmp_extraido`, `_sus`.

Quem os **grava**: a montagem (valor inicial), a `pasta` (carga e limpeza), o
`viewer` e o `pos_carga` (`carregar_registro`). `_planos`, `_agendamento`,
`_agendamento_pendente`, `_plano_ativo` e `_perguntas_pendentes` são gravados
por **quatro** blocos cada.

A lista existe em dois lugares (`__init__` e limpeza), e atributo novo do caso
que entre só no primeiro **sobrevive à troca de paciente**. A própria limpeza já
carrega três comentários desse tipo ("renders do caso anterior: outro paciente,
outro corpo"; a prévia; a capa). Não é defeito achado hoje — é a forma do
defeito que esta estrutura permite, e é o tipo que chega ao papel.

---

## 5. O que prende o código ao `gui.py` de fora

Custo de corte que não aparece no próprio arquivo.

**a) O endereço.** `gui.JanelaPrincipal` é citado **78 vezes em 10 arquivos**.
Métodos da classe citados por nome, por arquivo:

| arquivo | refs | blocos |
|---|---|---|
| `tests/test_gui_smoke.py` | 129 | viewer 36, tratamento 29, bancada 19, capa 19, pasta 10, conferência 7, navegação 6, pós-carga 3 |
| `tests/test_sus_convenio.py` | 27 | conferência 27 |
| `tests/test_capa_tela.py` | 18 | capa 9, navegação 7, pasta 2 |
| `tests/test_liberacao.py` | 13 | bancada 13 |
| `tests/test_tratamento.py` | 7 | viewer 4, tratamento 3 |
| `tests/test_padrao_ui.py` | 4 | navegação 2, conferência 1, pasta 1 |
| `tools/caso.py` | 4 | viewer 2, bancada 1, pdf 1 |
| `tests/test_modo_cor.py`, `tests/test_pasta_multipaciente.py` | 1 cada | navegação; pasta |

No **pacote**, nenhum módulo chama método da `JanelaPrincipal`: os acertos do
grep (`administracao._erro`, `agendamento_tela._indices_ficha`, os
`resizeEvent`) são homônimos de outras classes. Conferido.

**b) "Janela reduzida".** Três testes montam uma janela falsa emprestando
métodos da classe — e são os que **quebram na composição**, porque o `self`
deixa de ser a janela:

- `tests/test_sus_convenio.py:100–140`: classe falsa com `_coletar_sus`,
  `_aplicar_sus`, `_recado_do_convenio`, `_recado_do_cadastro_guardado`,
  `_alertar_sus_sem_numero`.
- `tests/test_liberacao.py:31` em diante: `J = gui.JanelaPrincipal` sobre
  `SimpleNamespace`.
- `tests/test_tratamento.py:3175`: `gui.JanelaPrincipal._tratamento_checklist_marcar`.

Além deles, estáticos chamados direto na classe: `_png_do_indice` (5×),
`_pasta_da_ficha` (3×), `_resumo_do_plano` (2×), `_agendamento_da_ficha` (2×,
com `self` falso) — todos em `test_gui_smoke.py`.

**c) Troca no namespace do `gui` — o custo SILENCIOSO.** Estes testes trocam um
nome **no módulo `gui`**. Se o código que usa o nome for para outro módulo, a
troca continua "funcionando" e o teste passa a rodar a peça verdadeira — sem
erro nenhum:

| troca | onde | o código que a lê |
|---|---|---|
| `gui.DialogEscolherPaciente = ` | `test_pasta_multipaciente.py:267, 275` | `_carregar_pasta` |
| `gui._CarregarTudo = ` | `test_pasta_multipaciente.py:268, 275` | `_carregar_pasta` |
| `trocar(gui, "QFileDialog", …)` | `test_liberacao.py:71` | `_pasta_do_paciente_para_liberar` |
| `gui._avisar_erro`, `gui._avisando` | `test_tratamento.py:526, 543, 571` | o arranque |

(As trocas em `gui.ui.alertar`, `gui.ui.falhar` e `gui.AcoesDeFicha._abrir_arquivo`
mexem no objeto do OUTRO módulo e seguem valendo onde quer que o código vá.)

**d) Testes que leem o TEXTO do `gui.py`.**
`test_pasta_multipaciente.py:206–207` recorta o corpo de `def _carregar_pasta(self`
em `fontes.texto("gui.py")`; `test_aquecer_banco.py:150–151` recorta o `def main():`.
Mover um desses dois é trocar o arquivo lido no teste — senão ele falha com
`ValueError` no `index`, o que ao menos é barulhento.

**e) Troca na instância.** `j._carregar_pasta = lambda …`
(`test_gui_smoke.py:2232`), `j._fichinha_carga_assentou`
(`test_gui_smoke.py:2072`), `janela._fichinha_gerar` (`test_liberacao.py:152,
184`), `j._escolher_ficha` e `j._abrir_pasta` (`test_padrao_ui.py:406–407`).
Continuam valendo enquanto quem chama passar pela janela; se o objeto novo
chamar direto o seu próprio método, a troca some em silêncio — mesma família
do item (c).

**f) O empacotador.** `tools/gerar_executavel.py:64` (`DENTRO_DO_PACOTE`) lista
os módulos que saíram do `gui.py`, porque import no meio do arquivo é o que sai
do pacote sem ninguém ver. **Módulo novo da R-06 entra nessa lista.** Há 10
imports tardios dentro de métodos hoje (ex.: `simulacao` em 1083, `drr` em 4680,
`pypdf` em 4829); cada um viaja com o método que o contém.

---

## 6. A proposta: seis cortes, em ordem de custo

Cada corte é **um commit**, com a suíte e a ordem aleatória, e pode parar em
qualquer um. A ordem é do mais barato para o mais caro, e os dois primeiros
preparam os seguintes.

### Corte 1 — Estáticos viram funções de módulo (sem mudança de comportamento)

15 `@staticmethod` da classe, **~250 linhas**: `_dentro_de`,
`_resumo_do_plano`, `_pasta_da_ficha`, `_png_do_indice`, `_montar_plano_app`,
`_px_copia`, `_cache_3d_valido`, `_chave_3d`, `_sus_pelo_convenio`,
`_recado_do_convenio`, `_recado_do_cadastro_guardado`, `_e_600cd`,
`_render_drrs_png`, `_montar_render_meta`, `_ler_bytes_seguro`.

- **Para onde:** com o tema de cada um no módulo do corte que o leva (os de SUS
  com o corte 2, os do índice com o corte 3), ou, se o corte 1 for sozinho,
  para funções no topo do próprio `gui.py`.
- **Custo:** baixo. Manter na classe `_png_do_indice = staticmethod(f)` deixa os
  testes do item (5b) intactos; sem o apelido, são ~12 referências a trocar.
  Nenhuma troca de namespace (5c) envolvida.
- **Ganho:** pequeno em linhas; tira da classe o que nunca foi dela.

### Corte 2 — Arranque para `interface/arranque.py`

`_avisar_erro`, `_instalar_rede_de_seguranca`, `_usuario_de_dev`, `main`
e a variável `_avisando` (5574–5723, **~150 linhas**), fora da classe.

- **Custo:** baixo, mas com as duas armadilhas de fora: `test_aquecer_banco.py:150–151`
  lê o `main` no texto do `gui.py` (5d) e `test_tratamento.py:526–571` troca
  `gui._avisar_erro`/`gui._avisando` (5c) — as duas trocas precisam passar a
  apontar o módulo novo, e a segunda **não falha se esquecida**. Mais:
  `run_gui.py` importa o `main`, e o módulo entra em `DENTRO_DO_PACOTE` (5f).
  Reimportar `main` no `gui.py` mantém o endereço antigo.

### Corte 3 — Ficha Virtual (tratamento) por composição

`_tratamento_ao_abrir` … `_tratamento_abrir_pdf` (1597–2114, **~470 linhas**
fora o `_resumo_do_plano`, que é do corte 1; 17 métodos) para um objeto próprio (nome sugerido: `ControleTratamento`, em
`interface/`), dono de `_medicos_tratamento`, `_paciente_em_foco` e
`_refs_tratamento`.

- **Por que primeiro entre os de composição:** é folha (18 chamadas dentro, 1
  fora) e toca só 9 atributos.
- **O que precisa receber da janela:** `ficha_virtual`, `form`, `capa`,
  `_usuario`, a leitura de `_pasta_carregada`, e `_sync_recusado` (que a capa
  também grava — decidir quem é dono).
- **Entradas que continuam na janela:** `_tratamento_ao_abrir` (da navegação e
  da bancada) e `_fechar_na_ficha_virtual` (da limpeza); as outras 8 são sinais
  ligados na montagem.
- **Os 5 leitores do índice** (2116–2220: `_respiratorio_da_ficha`,
  `_pasta_da_ficha`, `_png_do_indice`, `_capa_do_caso`, `_capa_ja_montada`)
  **não** vão junto: capa e pdf também os chamam.
- **Custo:** médio. `test_gui_smoke.py` cita 29 vezes o bloco e
  `test_tratamento.py:3175` empresta um método (5b).

### Corte 4 — Portão da geração (conferência e SUS) por composição

Os 18 métodos que decidem se a ficha pode sair: `_planos_gating_pendente`,
`_agendamento_completo`, `_pendencias_da_ficha`, `_confirmar_pendencias`,
`_maquina_sus_elegivel`, `_perguntar_sus`, `_validar_campos_obrigatorios`,
`_confirmar_gating_pendente`, `_planos_incompletos`,
`_confirmar_planos_incompletos`, `_coletar_sus`, `_aplicar_sus`,
`_sus_pelo_convenio`, `_recado_do_convenio`, `_alertar_sus_sem_numero`,
`_recado_do_cadastro_guardado`, `_e_600cd`, `_confirmar_600cd_sem_portal`
(**~440 linhas**).

- **Ficam na janela** os 7 restantes do bloco, que são peça de tela e não
  portão: `_escolher_ficha`, `_abrir_pdf_previa`, `_descartar_previa`,
  `_aviso_progresso`, `_abrir_configuracoes`, `_autor`, `_atualizar_btn_pdf`.
- **Lê:** `_agendamento`, `_ct`, `_dados`, `_planos`, `_registro_carregado`,
  `_usuario`, `form`, `status`; **grava** `_sus`. Depois do corte 6, recebe o
  caso em vez de ler a janela.
- **Custo:** médio. `test_sus_convenio.py` (27 refs) é a "janela reduzida" deste
  bloco e **reescreve** — para melhor: a classe falsa das linhas 100–140 vira a
  construção do objeto. `test_liberacao.py` não é afetado.
- **Atenção:** o que este bloco decide **vai para o papel** (o número SUS, e se
  a ficha sai com planos incompletos). Mesmo sem mudar regra, é mudança que se
  confere com `tools/caso.py` + `tools/comparar_pdf.py` antes e depois.

### Corte 5 — Capa e simulação por composição

Os 20 métodos do bloco `capa` (**587 linhas**), com `_capa_buscando`,
`_capa_caminho`, `_capa_completa_pedida`, `_pacientes_carregados` e
`_refs_pacientes`.

- **Custo:** médio-alto. 14 entradas, 11 delas sinais da montagem. Chama 5
  métodos de fora, e dois são de fluxo: `_sincronizar_bancada` (75 linhas) manda
  **carregar pasta** e `_capa_mudou` descarta a prévia — ficam como chamada de
  volta para a janela. Divide `_previa_ok` com bancada e conferência, e
  `_sync_recusado` com o tratamento.
- Testes: `test_capa_tela.py` 18 refs, `test_gui_smoke.py` 19.
- Tela com duas ou mais rodadas rejeitadas na história do projeto (a aba Capa):
  conferir por `tools/tela.py` a cada passo.

### Corte 6 — O estado do caso num objeto (o de maior ganho e maior risco)

Os 25 atributos da seção 4 num objeto `Caso` (dataclass). A limpeza passa a ser
**`self.caso = Caso()`** — atributo novo do caso deixa de poder ser esquecido
na troca de paciente — e o `_executar_limpeza` fica só com o que é tela (painéis,
botões, capa, ficha virtual).

- **Com ele, o `viewer` pode sair** (728 linhas: TC, soma, 3D) como operações
  sobre `caso` + `self.viewer`, e o `pdf` vira montagem da ficha a partir do
  caso. Sem ele, os dois não saem: gravam e leem o estado de quatro blocos.
- **Custo:** alto. Toca `pasta`, `viewer`, `pdf`, `conferencia`, `pos_carga` e
  `bancada` ao mesmo tempo. Até **53 referências** a esses atributos em
  `tests/` e `tools/` (`test_gui_smoke.py` 34; `tools/caso.py` 5;
  `test_isodose_recorte.py` 6 e `test_cortes_axial.py` 3 a conferir, podem ser
  homônimos). `tools/caso.py` gera a ficha pelo caminho do programa e precisa
  andar junto, ou a régua da conferência quebra no dia em que mais importa.
- **Portão:** `tools/caso.py` + `tools/comparar_pdf.py` em TC8, Elekta e um
  caso de soma de dose, antes e depois, com diferença **zero**; e trocar de
  paciente duas vezes seguidas na janela (o defeito que o corte previne é
  justamente o que a suíte não vê).

### O que NÃO se corta

- **`bancada`, `navegacao`, `pos_carga`, `montagem`**: são a cola (seção 3). A
  janela é o lugar deles; depois dos cortes 3–6 eles encolhem sozinhos, porque
  passam a chamar objetos em vez de 60 métodos.
- **`DialogEscolherPaciente`**: decidido em 31/08.
- **Mixin temático**: decidido em 27/08, e a medida de hoje reforça.

---

## 7. Onde isso deixa o `gui.py`

Estimativa por soma de linhas movidas (sem contar o que a composição acrescenta
de construção e ligação, algumas dezenas por corte):

| depois do corte | sai | `gui.py` |
|---|---|---|
| hoje | — | 5.728 |
| 1 — estáticos | ~250 | ~5.480 |
| 2 — arranque | ~150 | ~5.330 |
| 3 — Ficha Virtual | ~470 | ~4.860 |
| 4 — portão da geração | ~390 (fora os 4 estáticos do corte 1) | ~4.470 |
| 5 — capa | ~590 | ~3.880 |
| 6 — caso + viewer + pdf | ~1.270 (fora os 6 estáticos do corte 1) | ~2.610 |

Os cortes 1–3 são independentes entre si e do resto. O 4 e o 5 ficam mais
simples **depois** do 6, mas não dependem dele. O 6 é o único que muda a forma
do estado, e é o único cujo ganho não é de tamanho: é tirar da memória de quem
edita a obrigação de lembrar de zerar cada atributo novo.

## Perguntas para a R-06

Decisões que esta medida não toma:

1. Nome e pasta dos objetos novos (`interface/` é o óbvio; o `Caso` sem Qt
   poderia morar em `dominio/`).
2. Quem é dono de `_sync_recusado` (tratamento e capa gravam) e de `_previa_ok`
   (bancada, capa e conferência gravam).
3. Manter os endereços antigos (`gui.JanelaPrincipal._png_do_indice`,
   `gui.main`) por reimportação, como nas sete extrações de agosto, ou migrar os
   testes de uma vez.
