# Proposta de divisão do `tratamento.py`

**É proposta:** nenhuma linha do `tratamento.py` mudou para escrevê-la.
Executar é frente do usuário — `interface/` é tela, e tela muda com aceite.

Tudo aqui foi **medido**, não lido: `tools/mapa.py tratamento.py --metodos`
para os intervalos, e dois scripts de AST descartáveis (no scratchpad da
sessão) para o grafo interno, o estado que cada seção toca e as chamadas
cruzadas. O resto é `grep` em `tests/`, `tools/` e no pacote. As linhas citadas
são as do commit `94f0feb`, e **envelhecem**: medir de novo antes de cortar.

O molde é a `PROPOSTA_GUI.md` (R-05), e a conclusão aqui é diferente da de lá:
no `gui.py` havia onze blocos que se separavam; aqui o arquivo tem **duas
naturezas** bem separadas e uma classe que não se divide barato.

---

## 1. O tamanho

| | linhas |
|---|---|
| `tratamento.py` | **3.077** |
| as 15 peças do topo (104–1419) | 1.316 (43%) |
| `PainelFichaVirtual` (1422–3076) | **1.655 (54%)** |
| métodos do painel | 63 |
| atributos de instância distintos | 69 |

## 2. Os blocos

**Topo do arquivo: 15 peças visuais, nenhuma delas é Ficha Virtual.** São
widgets e janelas genéricas que a aba usa. Medido pelo grafo interno, o que
cada uma cita do próprio módulo:

| peça | linhas | usa do módulo | quem a usa aqui |
|---|---|---|---|
| `_popup_legivel` | 41 | `_ALTURA_ITEM`, `_LARG_MAX_POPUP` | painel |
| `_abrir_na_frente` | 18 | — | painel, `_ImagemEscalada`, `_Nota` |
| `_Fileira` (QLayout) | 98 | — | painel, `_JanelaCampos` |
| `_NumeroGrande` | 39 | — | painel |
| `_ValorClicavel` | 51 | — | painel |
| `_JanelaChecklist` | **237** | — | painel |
| `_JanelaCampos` | **307** | `_Fileira` | painel |
| `_JanelaTexto` | 45 | — | `_Nota` |
| `_Nota` | 59 | `_JanelaTexto`, `_abrir_na_frente` | painel |
| `_JanelaImagem` | 60 | — | `_ImagemEscalada` |
| `_ImagemEscalada` | 74 | `_JanelaImagem`, `_abrir_na_frente` | painel |
| `_Barra` | 44 | — | painel |
| `_EscolhaMedicos` | 78 | — | painel |
| `_Elide` | 30 | — | `_LinhaPainel` |
| `_LinhaPainel` | 107 | `_Elide` | painel |

Nenhuma peça cita o painel, e nenhuma é usada por outro módulo do pacote (só
por testes — ver seção 4). **As dependências entre elas formam três pares
fechados**: `_JanelaTexto`←`_Nota`, `_JanelaImagem`←`_ImagemEscalada`,
`_Elide`←`_LinhaPainel`.

**As importações que cada bloco levaria** (contagem de citações):

| bloco | código | precisa de |
|---|---|---|
| as 13 peças menores | 744 | `st`(104), `ui`(6), `QApplication`(4) |
| `_JanelaChecklist` + `_JanelaCampos` | 544 | `st`(40), `ui`(18), `QApplication`(4), `ficha_pdf`(4) |
| `PainelFichaVirtual` | 1.655 | `st`(78), `ui`(44), `tratamento_db`(24), `checklist`(6), `constantes`(4), `dicom_rt`(2) |

Isto é o achado que orienta os cortes: **as peças não sabem nada do domínio**.
`tratamento_db`, `checklist`, `constantes` e `dicom_rt` são citados só pelo
painel.

**O painel, pelas faixas de comentário que ele já tem escritas:**

| seção | intervalo | métodos | linhas | estado tocado |
|---|---|---|---|---|
| montagem (`__init__`) | 1451–1555 | 1 | 105 | 26 |
| aviso | 1557–1586 | 1 | 28 | 2 |
| painel (em tratamento) | 1588–1736 | 8 | 142 | 8 |
| busca | 1741–1897 | 12 | 144 | 11 |
| quadro (fração, dose) | 1899–2327 | 14 | **414** | 31 |
| histórico (sessões, fotos) | 2329–2635 | 14 | 288 | 17 |
| estados da tela | 2637–3076 | 13 | **426** | **38** |

## 3. Quem chama quem, e o estado

Chamadas de método entre seções (contagem de citações `self.<método>`):

| de → para | |
|---|---|
| montagem → histórico 3, estados 2, aviso 1, quadro 1, painel 1, busca 1 | a construção liga tudo |
| estados → quadro 8, histórico 6, busca 1 | **a seção que manda nas outras** |
| quadro → estados 5 | e é chamada de volta |
| histórico → quadro 2, estados 1 | |
| painel → busca 2, busca → histórico 2, busca → estados 1 | |

**45 dos 69 atributos são compartilhados por mais de uma seção**, e a seção
"estados" aparece em 38 deles. `_registro` é tocado por cinco seções; `_curso_na_tela`,
`_foto`, `_tem_fotos` e `_tem_imagens`, por quatro cada.

É isto que decide a proposta: "estados" (`limpar`, `mostrar`,
`_pintar_quadro`, `_estado`, `sem_conexao`) **não é uma área da tela, é o
maquinário que apaga e reacende todas as áreas**. Tirá-la da classe não a
separaria de nada — levaria consigo a referência a quase todos os widgets, e
cada acesso viraria `self.janela.x`, como no corte 6b da R-06, mas sem o ganho
de fronteira, porque aqui as duas metades continuariam se chamando nas duas
direções.

## 4. O que prende o arquivo de fora

| quem | o que usa | efeito no corte |
|---|---|---|
| `gui.py:62` | `tratamento.PainelFichaVirtual` | um nome só: indiferente |
| `tests/test_tratamento.py` | `_JanelaCampos`, `_JanelaChecklist`, `_JanelaImagem`, `_JanelaTexto`, `_ValorClicavel`, `_ALTURA_ITEM`, `_LARG_IMAGENS`, `_RECUO_CAB`, `st`, `PainelFichaVirtual` | reimportar no `tratamento.py` mantém tudo |
| `tests/test_padrao_ui.py` | `_JanelaCampos`, `_JanelaChecklist`, `_JanelaTexto` | idem |
| `tests/test_gui_smoke.py` | `PainelFichaVirtual` | fica |
| `tests/test_padrao_visual.py` | **`EXCECOES["tratamento.py:_JanelaImagem"]`** | **a chave morre no corte**: o teste confere `class _JanelaImagem(` dentro de `tratamento.py`. Mover a peça exige trocar a chave para o arquivo novo, no MESMO commit |

Essa última é a armadilha do corte: reimportação satisfaz o `import`, mas o
`test_toda_excecao_ainda_existe` lê o **texto** do arquivo.

## 5. A proposta: dois cortes, e um que eu não faria

**Corte 1 — as 13 peças menores saem** para `interface/pecas_tratamento.py`
(~744 linhas). Levam `st`, `ui` e Qt, e nada do domínio. Os três pares fechados
vão juntos, o que evita import cruzado. `tratamento.py` reimporta os nomes que
os testes citam. Custo: o menor do arquivo — nenhuma dessas peças toca estado do
painel, e a única constante compartilhada é `_ALTURA_ITEM` (do `_popup_legivel`
e do painel), que fica no arquivo novo e volta por reimportação.

**Corte 2 — as duas janelas grandes saem** para `interface/janelas_tratamento.py`
(~544 linhas). São diálogos fechados: `_JanelaChecklist` não cita nada do
módulo, `_JanelaCampos` cita só `_Fileira` (que o corte 1 já moveu). Trazem o
único uso de `ficha_pdf` fora do painel. **Aqui entra a troca da chave de
`EXCECOES`** se o `_JanelaImagem` tiver ido no corte 1 — conferir a lista antes
de fechar o commit.

**O corte que eu não faria agora: dissolver o `PainelFichaVirtual`.** Depois
dos dois cortes o arquivo fica com ~1.760 linhas, das quais 1.655 são a classe.
Pelos números da seção 3, o único recorte com fronteira estreita é o
**histórico** (288 linhas, 17 atributos, 8 deles compartilhados: `tabela`,
`_faixa_cab`, `_cartao_fotos`, `_cartao_imagens`, `_tem_fotos`,
`_tem_imagens`, `_procedencia_fotos`, `_procedencia_imagens`), e ele é chamado
de fora 11 vezes. Os outros recortes (quadro, estados) compartilham 31 e 38
atributos: seriam duas classes amarradas, com chamada nas duas direções — a
forma que o corte 6b evitou, não a que ele fez.

Se a meta for "nenhum arquivo acima de 2.000 linhas", os dois cortes já a
cumprem. Se for "nenhuma classe acima de 1.000", aí sim é preciso mexer no
painel, e o caminho menos ruim é o histórico primeiro, medindo de novo depois.

## 6. Onde isso deixa o arquivo

| depois do corte | sai | `tratamento.py` |
|---|---|---|
| hoje | — | 3.077 |
| 1 — as 13 peças | ~770 (com as linhas em branco e as faixas) | ~2.300 |
| 2 — as duas janelas | ~550 | **~1.760** |

Os dois cortes são independentes entre si. Nenhum toca o `dominio/` nem o
`papel/`, e nenhum muda o que aparece na tela: as peças mudam de arquivo, não
de comportamento.

**Portão de cada commit**, pelo que a R-06 usou e o que é específico daqui:
`tools/tela.py` na aba Ficha Virtual (o painel é tela, e o teste passa sem
provar que ela desenha), a suíte inteira e a ordem aleatória. A ficha em PDF
não é caminho desta aba (não há impressão aqui, decisão de 19/08/2026), então
o `comparar_pdf` não é portão — o que substitui é o print da aba.

## Perguntas para quem executar

1. Nome dos arquivos novos: `pecas_tratamento.py` / `janelas_tratamento.py`,
   ou `tratamento_pecas.py` / `tratamento_janelas.py`? O segundo agrupa na
   listagem da pasta; o primeiro lê melhor no import.
2. As peças são realmente de uso geral (`_Fileira` é um QLayout, `_Elide` é um
   rótulo que elide) e poderiam ir para o `ui.py`, que é onde o projeto guarda
   peça compartilhada — o `ui.py:574` já MANDA o leitor ver o `_Fileira`, que
   mora noutro arquivo. Contra: o `ui.py` já tem 1.382 linhas e as peças daqui
   não são usadas por nenhuma outra tela hoje.
3. Manter os endereços antigos por reimportação (como nas extrações de agosto e
   na R-06) ou migrar os testes de uma vez?
4. Vale o corte do histórico depois, ou o painel fica como está até haver
   motivo de uso (e não de tamanho) para dividi-lo?
