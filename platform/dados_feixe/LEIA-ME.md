# Dado de feixe do cálculo paralelo

Esta pasta guarda o que a aba Qualidade usa para a **verificação independente de
UM** (ver `paralelo.py`): as tabelas de TMR e Scp e os fatores por energia.

**O conteúdo NÃO vai para o git** (ver `.gitignore`). Dado de comissionamento é
medida de um acelerador específico, e parte do que existe aqui hoje veio de
outro serviço — repositório público não é lugar para isso. Só este arquivo é
versionado, porque é ele que diz como repor a pasta numa estação nova.

A pasta pode morar em outro lugar: `ISOCENTRO_DADOS_FEIXE` (ou
`ISOCENTRO_DADOS_FEIXE`) tem precedência sobre este caminho.

---

## O que precisa existir

```
dados_feixe/
  _maquinas.json                     cadastro das máquinas
  <MAQUINA>__<ENERGIA>MV__TMR.csv    tabela de TMR
  <MAQUINA>__<ENERGIA>MV__SCP.csv    tabela de Scp
```

`<MAQUINA>` é a chave usada no `_maquinas.json`, e `<ENERGIA>` é a energia
nominal em MV sem zeros à toa — `6`, `10`, `15`.

## `_maquinas.json`

```json
{
  "TRUEBEAM_4199": {
    "rotulo": "TrueBeam SN1001",
    "fabricante": "VARIAN",
    "exemplo": false,
    "fonte": "comissionamento de 00/00/0000",
    "nomes_dicom": ["TrueBeamSN1001"],
    "energias": {
      "6":  {"fd": 1.000, "fw": 0.000},
      "10": {"fd": 1.000, "fw": 0.000}
    }
  }
}
```

**`nomes_dicom` é a trava.** É a lista de nomes que o RT Plan escreve em
`TreatmentMachineName`, e o casamento é por nome EXATO — sem prefixo, sem
parecença. Duas TrueBeam da mesma clínica têm dado de feixe diferente, e é para
isso que existe o número de série no nome. Lista vazia = a máquina não casa com
plano nenhum, e o resultado sai marcado como **demonstração**.

`fd` é o fator distância (a razão que leva a dose de referência ao ponto de
cálculo) e `fw` o fator do filtro, os dois por energia. `exemplo: true` marca
dado que não é desta clínica — a tela anuncia.

## As tabelas

**TMR** — linha 1 são os tamanhos de campo em cm, coluna A as profundidades em
cm:

```
profundidade_cm,3,4,5,10,20,40
1.5,1.000,1.000,1.000,1.000,1.000,1.000
2.0,0.998,0.997,0.999,0.999,0.996,0.996
```

**Scp** — o fator de espalhamento total (Sc·Sp), em função do campo equivalente:

```
campo_cm,scp
3,0.917
10,1.000
40,1.083
```

A primeira profundidade da tabela de TMR é tratada como o **dmax**: campo cujo
isocentro fique acima dela é recusado, porque na região de build-up o formalismo
TMR não se aplica (ver a trava em `paralelo.calcular_feixe`).

Interpolação bilinear no TMR, linear no Scp, e **clamp** nas bordas — não
extrapola. Fora da faixa tabelada o valor fica preso na borda, e o desvio grande
que isso gera é o que chama atenção.

## Como as planilhas do serviço viram estes CSV

O formato das planilhas de origem é o mesmo, com os rótulos no estilo `10x10`
em vez de `10`. A conversão é trivial e vale fazê-la **com validação**: dado de
feixe transcrito à mão precisa falhar alto se algo saiu errado. O que se
confere:

- profundidade e campo **crescentes**, sem repetição;
- TMR dentro de `(0, 1]` — valor acima de 1 só nas linhas logo abaixo do dmax;
- Scp entre 0,8 e 1,2, e **exatamente 1,000 no campo 10×10**, que é a
  normalização;
- o número de linhas e colunas batendo com o que o serviço registrou.
