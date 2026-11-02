# Estruturas auxiliares — anéis de otimização

Plug-in do Eclipse (ESAPI) que cria dois anéis de controle a partir da soma dos
PTVs escolhidos por quem está planejando.

Isto grava no **banco clínico**. Um anel errado não é um bug de software — é uma
estrutura que o otimizador vai obedecer.

---

## O que ele cria

| estrutura | interno | externo | espessura |
|---|---|---|---|
| `Anel1` | soma dos PTVs + 2 mm | soma dos PTVs + 20 mm | 18 mm |
| `Anel2` | soma dos PTVs + 20 mm | soma dos PTVs + 40 mm | 20 mm |

Os dois **encostam sem lacuna e sem sobreposição**: o interno do `Anel2` é
exatamente o externo do `Anel1`. Ambos são cortados pelo contorno externo
(`And` com o `EXTERNAL`) — sem isso, um anel de 4 cm sai da pele e fica no ar,
e o otimizador tenta poupar um volume que não existe. Em cabeça-pescoço e mama
isso acontece sempre.

Tipo DICOM das duas: `CONTROL`.

As margens estão em constantes no topo do [`Script.cs`](AneisOtimizacao/Script.cs),
**em milímetros** — a API inteira trabalha em mm enquanto a conversa clínica é
em cm, e é uma casa decimal entre um anel de 2 cm e um de 20 cm, sem erro
nenhum na tela.

---

## Como ele decide

**Os PTVs são escolhidos na tela, não adivinhados.** A janela lista as
estruturas preenchidas e já vem com as de tipo DICOM `PTV` marcadas, mas quem
confirma é o usuário. Filtro automático por prefixo pegaria junto `PTV_eval`,
`PTV-2mm` e auxiliares de casos anteriores — e um PTV a mais ou a menos muda os
dois anéis inteiros, em silêncio.

**O contorno externo é achado pelo tipo `EXTERNAL`, não pelo nome.** `BODY`,
`External` e `Corpo` são o mesmo tipo em serviços diferentes.

**A soma dos PTVs não vira estrutura.** Ela existe só como `SegmentVolume`
intermediário. O structure set recebe duas estruturas, não três.

---

## O que ele recusa fazer

Cada uma destas é uma falha que, sem a checagem, apareceria como exceção no meio
da execução — com o `Anel1` já gravado e o `Anel2` não:

- **Resolução misturada.** A API não opera entre estrutura de alta resolução e
  de resolução padrão. O script mostra quais são quais e para.
- **Anel já existente e travado.** Pergunta ao `CanEditSegmentVolume`, que
  devolve junto o **motivo** — e o motivo é o que o usuário precisa para
  resolver sozinho. Se existir e for editável, pergunta antes de substituir.
- **Teto de 99 estruturas.** Pergunta ao `CanAddStructure` antes de escrever
  qualquer coisa.
- **Sem contorno externo preenchido.**

E, no fim, confere o que criou: operação booleana que não sobrepõe nada devolve
estrutura **vazia**, não erro. Se algum anel sair vazio, a mensagem final avisa
em vez de dizer que deu certo.

---

## Compilar

**1. As DLLs da Varian não estão neste repositório** — são licenciadas. Elas
ficam na estação com Eclipse, em:

```
C:\Program Files\Varian\RTM\<versão>\esapi\API
```

Copiar as duas para uma pasta `lib/` na raiz deste repositório, que é onde o
`.csproj` as procura por padrão. O `.gitignore` já barra `lib/`.

**2. Versão.** Este projeto está compilado contra a **ESAPI 15.6**
(`AssemblyVersion 1.0.300.11`, `FileVersion 15.6.8.73`). Para compilar contra
outra instalação:

```
msbuild AneisOtimizacao.sln /p:Configuration=Release /p:Platform=x64 /p:EsapiDir="C:\Program Files\Varian\RTM\17.0\esapi\API"
```

Se o caminho estiver errado a compilação para com a mensagem dizendo isso, em
vez de despejar uma cascata de "tipo não encontrado".

**3. `TargetFrameworkVersion` é `v4.5`**, que é o TargetFramework das próprias
DLLs da ESAPI 15.6. Mirar mais alto que o host é o erro que não aparece na
compilação: o Eclipse simplesmente não carrega o plug-in, sem dizer por quê.

**4. x64 e o sufixo `.esapi`** já estão no `.csproj` e não devem ser mexidos. O
padrão do Visual Studio é AnyCPU, que não carrega; e o Eclipse só reconhece
como plug-in o assembly cujo nome termina em `.esapi`.

Saída: `AneisOtimizacao.esapi.dll`.

**Atalho:** `.	ools\compilar.ps1` faz tudo isso e copia o resultado para a
Área de Trabalho. Com `-Sufixo v3` ele versiona o nome do assembly, que é o que
destrava a reimportação no Eclipse durante o desenvolvimento.

---

## Instalar e rodar

Copiar o `.esapi.dll` para a pasta de scripts do Eclipse e aprová-lo pelo
caminho normal do serviço. Depois: abrir o paciente com imagem e structure set,
e chamar o script pelo menu de ferramentas.

**Licença necessária:** Eclipse Automation 15.1.1 ou posterior. Só o ESAPI
básico não basta — ele é read-only, e este plug-in escreve.

---

## Armadilhas já pagas

**`CanAddStructure` responde "não" antes de `BeginModifications()`.** Ele fala do
estado ATUAL do paciente: enquanto o paciente não foi aberto para modificação,
tudo é read-only e a resposta é sempre negativa. A recusa não fala do structure
set — fala do modo. Chamar `BeginModifications()` cedo não grava nada, só
habilita, então ele vem antes de qualquer pergunta sobre escrita.

Custou uma rodada em 03/09/2026, e a mensagem de erro piorou o rastro: ela
**afirmava** o teto de 99 estruturas e imprimia "ele tem 13" na linha seguinte.
Mensagem que se contradiz manda procurar no lugar errado. Hoje ela testa os
tipos DICOM e relata o que encontrou, em vez de chutar causa.

**O Eclipse não deixa reimportar um script por cima.** Ele guarda o script pela
identidade do assembly. Durante o desenvolvimento, cada rodada precisa de um
nome novo — é para isso que `tools\compilar.ps1` aceita `-Sufixo`. O sufixo é
andaime: quando a versão fecha, remover as tentativas da lista do Eclipse e
importar o nome limpo uma vez só. Lista com quatro versões da mesma coisa é
onde alguém roda a errada.

**`Structure.CanModify` não existe**, apesar da documentação. O correto é
`CanEditSegmentVolume(out string motivo)` — que ainda devolve a razão da recusa.

---

## Estado

Escrito e compilado em 03/09/2026, **contra as DLLs reais da ESAPI 15.6**, com
`/warn:4 /warnaserror /optimize+` — zero erros e zero avisos.

O binário foi conferido por reflexão:

| conferido | resultado |
|---|---|
| arquitetura | `Amd64` |
| referência gravada | `VMS.TPS.Common.Model.API, 1.0.300.11, Token 305B81E210EC4B89` |
| atributo | `ESAPIScript(IsWriteable = True)` |
| ponto de entrada | `VMS.TPS.Script.Execute(ScriptContext)`, classe pública |

Todos os membros usados foram verificados na API real por reflexão, não na
documentação — que erra. `Structure.CanModify`, por exemplo, **não existe**; o
correto é `CanEditSegmentVolume(out string)`.

**Rodou no Eclipse em 03/09/2026**, criando os dois anéis. Confirmado nessa
rodada: `CONTROL` é aceito como tipo DICOM, e a correção da ordem do
`BeginModifications()` resolveu a recusa do `CanAddStructure`.

O que uma rodada boa ainda não cobre: caso com PTV único, caso com alvos
distantes entre si (onde a soma vira dois volumes separados e cada anel também),
e alvo raso, encostado na pele, onde o corte pelo `EXTERNAL` faz mais trabalho.
Volume plausível na mensagem final não prova contorno certo — a régua continua
sendo olhar o anel no Eclipse.

Se algum dia entrar margem assimétrica aqui, a assinatura verificada é
`AsymmetricMargin(AxisAlignedMargins)` — um objeto, não uma lista de
parâmetros. A ordem dos seis eixos e o sinal de
`StructureMarginGeometry.Inner` continuam por conferir.
