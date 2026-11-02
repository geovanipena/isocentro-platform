# PrePlan — o plano montado antes da otimização

Cria o plano, os campos, o isocentro e o ajuste de colimador de um caso novo, a
partir do que se escolhe numa janela só. Roda de duas formas, com o mesmo
código: **`PrePlan.exe`**, pelo `tools\preplan.bat`, e **`PrePlan.esapi.dll`**,
como plug-in do Eclipse.

Isto grava no **banco clínico**. Um campo com a máquina errada não é um bug de
software — é um plano que alguém vai otimizar achando que confere.

**A fonte é a documentação oficial**, sempre, antes de escrever a chamada:

    https://docs.developer.varian.com/api/15.6/index.html
    .../api/15.6/VMS.TPS.Common.Model.API.<Classe>.html
    .../api/15.6/VMS.TPS.Common.Model.Types.<Classe>.html

O índice é JavaScript e não se navega — as URLs acima se montam à mão. A
reflexão nas DLLs continua valendo, mas as duas respondem coisas diferentes:
**reflexão dá a forma** (a assinatura real, e pega o membro que a doc inventa),
**a doc dá o conteúdo** (o que cada parâmetro espera). Depurar sem a segunda
custou duas idas ao Eclipse em 03/09/2026.

---

## O que ele monta

| passo | o que faz |
|---|---|
| plano | `AddExternalPlanSetup` no curso escolhido, com o Id digitado |
| prescrição | dose por fração × frações, a 100% |
| campos | **VMAT**: 2 arcos 181→179 horário e 179→181 anti-horário. **Fixos**: N campos igualmente espaçados a partir de 180° |
| isocentro | centro do alvo escolhido, ou a origem do usuário (marcação da TC) |
| colimador | ângulo digitado + `FitCollimatorToStructure` com a margem escolhida, jaws assimétricas |
| otimização | o NTO automático, com a prioridade escolhida |

No fim, a mensagem relata o que foi criado — inclusive **a abertura de cada
campo em cm**. É o que denuncia um ajuste de colimador que não aconteceu: 10 × 10
num alvo de 12 cm salta aos olhos ali, e não saltaria no Eclipse até alguém
abrir o BEV.

O isocentro sai em duas linhas, **DICOM e coordenada do usuário**. A de DICOM é
a que a API usa; a do usuário é a única que o físico consegue comparar com o que
está na tela do Eclipse.

---

## O que ele NÃO faz, e por quê

**Não otimiza e não calcula dose.** `Optimize` e `CalculateDose` só são
liberados em **aplicativo standalone** — num plug-in rodado de dentro do Eclipse
os métodos existem na DLL e a recusa vem em tempo de execução. O `PrePlan.exe`
já é standalone, então a porta está aberta; ela continua fechada de propósito.
O passo que decide dose fica com quem responde por ele, e plano otimizado por
script que ninguém olhou é exatamente o que este repositório não quer produzir.

**Não cria curso.** Abrir curso é decisão clínica e administrativa do serviço. Um
plug-in que cria curso sozinho deixa "Curso 2" vazio atrás de si. Sem curso, o
script manda criar no Eclipse e para.

**Não escolhe modelo de cálculo nem de otimização.** Os nomes (`AAA_15606`,
`PO_15606`…) são da configuração de cada serviço, e um modelo escolhido por
chute é um plano calculado com o algoritmo errado.

**Não cria objetivos do alvo nem dos órgãos de risco.** Eles são do protocolo. Um
objetivo inventado por script é uma dose que o otimizador vai perseguir. O NTO
automático é a única exceção, porque ele não afirma nível de dose nenhum — só
prioridade — e está numa caixa que se desmarca.

A mensagem final lista tudo isso como **FALTA, antes de otimizar**. "O script
rodou" e "o plano está pronto" são coisas diferentes, e essa lista é a
diferença.

---

## Como ele decide

**O alvo é escolhido na tela, não adivinhado.** Ele decide o isocentro E a
abertura dos campos. A janela já vem com o **maior** de tipo DICOM `PTV`
marcado — quando há PTV de vários níveis, o de dose mais baixa costuma ser o que
engloba os outros — mas quem confirma é quem está olhando. Filtro por prefixo
pegaria junto `PTV_eval`, `PTV_old` e as auxiliares de casos anteriores.

**A máquina não é inventada.** A ESAPI 15.6 **não tem catálogo de máquinas**: não
há como perguntar à API quais existem. E os campos de
`ExternalBeamMachineParameters` são strings cruas que precisam bater exatamente
com a configuração (`TrueBeamSN1234` não é `TrueBeam`). Então a lista da janela
é **colhida**: das máquinas dos planos que o paciente já tem, mais as que já
deram certo nesta estação (`%LOCALAPPDATA%\PrePlan\maquinas.txt`). Vêm juntas a
**energia** (já separada do modo de fluência) e a **taxa de dose**.

**A técnica é a exceção: ela vem da doc, não da colheita.** `ARC` e `STATIC` são
o que o `ExternalBeamMachineParameters` documenta; o `Technique.Id` de um feixe
já existente é o nome da técnica **do plano** (`SRS ARC`), que é nome de
exibição — e a colheita dele entra só como **segunda tentativa**.

Na primeira vez alguém digita; da segunda em diante escolhe. E só entra no
histórico o que **funcionou**, na leitura que funcionou — guardar a tentativa
faria a lista oferecer, da próxima vez, justamente o que o Eclipse recusou.

**Os dois arcos têm colimadores opostos** (30 e 330, por padrão): o vazamento
entre lâminas de um cai onde o outro não tem junta. Dois arcos com colimador em
0 empilham o vazamento das duas passagens na mesma linha.

**Um arco de 360° cheio não existe**: início e fim iguais seriam um arco de zero
grau. 181→179 é a convenção do Eclipse, e deixa o ponto morto atrás do paciente
supino, não sobre ele.

**Os campos fixos saem estáticos e abertos**, com as jaws ajustadas ao alvo. É o
mesmo ponto de partida de quem cria os campos à mão: quem os transforma em
fluência é o otimizador, com o plano marcado como IMRT. A mensagem final lembra
disso.

**Origem do usuário só é oferecida se existe.** Sem `HasUserOrigin`, a "origem"
da imagem é o canto do volume da TC — e um isocentro ali fica fora do paciente,
sem erro nenhum, só errado.

---

## O que ele recusa fazer

- **Sem imagem no structure set**: o isocentro é uma coordenada da imagem.
- **Sem estrutura preenchida**: não há alvo de onde tirar isocentro nem abertura.
- **Sem curso**: ver acima.
- **Id de plano repetido no curso**, ou vazio — o botão fica apagado, com o
  motivo no tooltip.
- **Curso que não aceita plano novo**: pergunta ao `CanAddPlanSetup` **antes de
  qualquer escrita** e para com o motivo.
- **Isocentro NaN**: estrutura com contorno degenerado devolve coordenada
  inválida, e o `AddBeam` **aceita** — o campo nasceria com isocentro inválido e
  o Eclipse só reclamaria muito depois.

Depois da primeira escrita o script **não aborta mais**: cada passo que pode
falhar sozinho (nome do plano, prescrição, ajuste de colimador de cada campo,
NTO) tem seu próprio `try`, e a falha vira **aviso na lista**. Um plano criado
pela metade que desaparece dentro de uma mensagem de erro é pior que um plano
criado pela metade que se anuncia — e o script **não apaga** o que criou:
remover plano do banco clínico é decisão de quem está lá.

---

## Compilar

**1. As DLLs da Varian não estão neste repositório** — são licenciadas. Elas
ficam na estação com Eclipse, em:

```
C:\Program Files\Varian\RTM\<versão>\esapi\API
```

Copiar as duas para uma pasta `lib/` na raiz, que é onde o `.csproj` as procura.
O `.gitignore` já barra `lib/`.

**2. Versão.** Compilado contra a **ESAPI 15.6** (`AssemblyVersion 1.0.300.11`).
Para outra instalação:

```
msbuild PrePlan.sln /p:Configuration=Release /p:Platform=x64 /p:EsapiDir="C:\Program Files\Varian\RTM\17.0\esapi\API"
```

**3. `TargetFrameworkVersion` é `v4.5`**, que é o das próprias DLLs da ESAPI
15.6. Mirar mais alto que o host é o erro que não aparece na compilação: o
Eclipse simplesmente não carrega o plug-in.

**4. x64 e o sufixo `.esapi`** já estão no `.csproj` e não devem ser mexidos. O
padrão do Visual Studio é AnyCPU, que não carrega; e o Eclipse só reconhece como
plug-in o assembly cujo nome termina em `.esapi`.

**5. `/codepage:65001`.** Os fontes são UTF-8 **sem BOM** e têm acento dentro de
string de tela. Sem essa opção o `csc` lê pela codepage ANSI da estação e o
acento chega torto na `MessageBox` — compila limpo, e só aparece na frente de
quem está usando. Está no `.csproj` (`<CodePage>`) e no `compilar.ps1`.

**Atalho:** `.\tools\compilar.ps1` compila **os dois** e copia para a Área de
Trabalho. Com `-Sufixo v5` versiona os nomes, que é o que destrava a
reimportação no Eclipse durante o desenvolvimento; `-SoExe` pula o plug-in.

Saída: `PrePlan.esapi.dll` e `PrePlan.exe`. **Os mesmos fontes nos dois** — o
plug-in leva junto um `Programa.Main` que nunca é chamado, e o `.exe` uma classe
`Script` que o Eclipse nunca vê. Duas listas de arquivo seriam duas listas para
esquecer de atualizar.

---

## Rodar — dois caminhos, um código só

O mesmo código roda de duas formas. A diferença entre elas está inteira numa
classe de 60 linhas (`Bancada.cs`): de onde vêm o paciente e o structure set, e
quem grava no banco.

### 1. Pelo `.bat`, por fora do Eclipse — `PrePlan.exe`

```
tools\preplan.bat              abre a janela de busca de paciente
tools\preplan.bat 123456       já procura por esse Id
tools\preplan.bat --onde       só mostra onde a ESAPI será procurada
```

É o caminho de trabalho. O Eclipse guarda o script pela identidade do assembly e
**não deixa reimportar por cima**: cada rodada de desenvolvimento no plug-in
custa um nome novo e uma volta pela tela de aprovação. O `.exe` se roda de novo
apertando a seta para cima. E é por esta porta que `Optimize` e `CalculateDose`
entram no dia em que entrarem — eles só são liberados em aplicativo standalone.

**As DLLs da Varian não acompanham o executável.** São licenciadas; o `.exe` as
procura na instalação da estação, nesta ordem: `%PREPLAN_ESAPI%`, a pasta do
próprio executável, e as instalações em
`C:\Program Files\Varian\RTM\<versão>\esapi\API`, da versão mais nova para a
mais antiga. `--onde` mostra a lista e diz quais existem.

Numa máquina fora do domínio, a identidade de rede vai por fora, como no
gravador de banco do ISOCENTRO:

```
runas /netonly /user:DOMINIO\usuario "...\tools\preplan.bat"
```

O `.bat` termina com `pause` por causa disso: o console do `runas` fecha
sozinho, e sem a pausa o código de saída (0 montou, 1 cancelado, 2 sessão não
abriu, 3 erro) some junto.

### 2. Como plug-in do Eclipse — `PrePlan.esapi.dll`

Copiar o `.esapi.dll` para a pasta de scripts do Eclipse e aprová-lo pelo
caminho normal do serviço. Depois: abrir o paciente com imagem, structure set e
**um curso já existente**, e chamar pelo menu de ferramentas.

**Licença necessária, nos dois casos:** Eclipse Automation. Só o ESAPI básico
não basta — ele é read-only, e isto escreve.

---

## Armadilhas já pagas

**Nome de exibição não é identificador — duas vezes.** A doc oficial do
`ExternalBeamMachineParameters` diz, com todas as letras:

| parâmetro | o que a doc diz |
|---|---|
| `energyModeId` | *"For example, `6X`, or `18X`."* |
| `techniqueId` | *"Typically `STATIC` or `ARC`."* |
| `primaryFluenceModeId` | *"Acceptable values are: null, empty string, `SRS`, `FFF`."* |

E o que a API **devolve** sobre um feixe que já existe é outra coisa:
`EnergyModeDisplayName` dá `6X-FFF` (energia e fluência grudadas) e
`Technique.Id` dá `SRS ARC` (o nome da técnica do plano). Colher esses dois e
passá-los de volta ao `AddBeam` é a receita de
`ApplicationException: External beam configuration not found` — com a máquina, a
taxa e "a técnica" idênticas às de um plano que existe e funciona.

Custou duas rodadas no Eclipse em 03/09/2026, e a segunda foi pior que a
primeira: eu tinha *corrigido* a energia e, no mesmo passo, passado a preferir a
técnica colhida ao `ARC` documentado. O diagnóstico do script mostrava as duas
linhas iguais — a pedida e a gravada — o que mandava procurar em qualquer lugar
menos no certo.

**A energia que o Eclipse mostra é composta.** `EnergyModeDisplayName` devolve
`6X-FFF`, mas isso é **energia `6X` + modo de fluência `FFF`**, e o
`ExternalBeamMachineParameters` quer os dois em parâmetros separados. Passar
`6X-FFF` inteiro como energia, com a fluência vazia, dá:

```
ApplicationException: External beam configuration not found
```

— com a máquina, a taxa de dose e a técnica **idênticas** às de um plano que já
existe na mesma máquina. Foi assim que a primeira rodada real falhou
(03/09/2026, TrueBeamSN1001 / 6X-FFF / 1400 UM/min / SRS ARC): o script colheu a
energia do plano vizinho, mostrou a mesma string na mensagem de erro e na lista
de comparação, e as duas linhas idênticas mandavam procurar em qualquer lugar
menos no lugar certo.

Não há como perguntar à API qual leitura é a certa: o
`ExternalBeamTreatmentUnit` **não lista energias** (conferido por reflexão; ele
tem `Id`, `MachineModel`, `SourceAxisDistance` e mais nada disso). Então o
script separa na colheita, mostra separado na janela — e, se a primeira leitura
não criar campo nenhum, **tenta a leitura oposta**, uma vez. Só enquanto nada
foi gravado: com um arco já criado, repetir duplicaria.

**No standalone, sem `SaveModifications()` nada é gravado.** Dentro do Eclipse
quem grava é o Eclipse. Fora dele, o script roda inteiro, o relatório sai bonito,
a mensagem diz que criou o plano — e o banco não muda. É a pior forma de falhar
que existe aqui, porque ela parece sucesso. Por isso a gravação é **uma linha,
num lugar só** (`Bancada.Salvar`), e a falha dela é relatada como falha.

**O resolvedor de assembly tem de ser registrado antes de o JIT tocar na ESAPI.**
O JIT compila um método inteiro ao **entrar** nele: se o `Main` mencionasse
qualquer tipo da API, o processo morreria antes da primeira linha, com
`FileNotFoundException`, sem chance de o `AssemblyResolve` ajudar. Por isso o
`Main` só registra o resolvedor e chama outro método (`NoInlining`), que é onde a
API aparece.

**`Version` sozinho não compila dentro de `namespace VMS.TPS`**: a ESAPI tem um
namespace `VMS.TPS.Version`, e o compilador para dizendo que um namespace está
sendo usado como tipo. É `System.Version` por extenso.

**`BeginModifications()` vem cedo, antes de qualquer `Can…`.** Ele responde
sobre o estado ATUAL do paciente: enquanto o paciente não foi aberto para
modificação, tudo é read-only e a resposta é sempre negativa — e a recusa não
fala do curso, fala do modo. Custou uma rodada no plug-in dos anéis, com
`CanAddStructure`. Chamar cedo não grava nada, só habilita.

**O terceiro parâmetro do `SetPrescription` é fração, não porcentagem.** `1.0` é
100%. Passar `100` daria uma prescrição cem vezes maior, e isso não aparece em
lugar nenhum até a normalização sair errada.

**O Eclipse não deixa reimportar um script por cima.** Ele guarda o script pela
identidade do assembly; durante o desenvolvimento cada rodada precisa de nome
novo — é para isso que `tools\compilar.ps1` aceita `-Sufixo`. O sufixo é
andaime: quando a versão fecha, remover as tentativas da lista do Eclipse e
importar o nome limpo uma vez só.

**Nada de assinatura vinda do resumo da documentação da Varian.** Todo membro
usado aqui foi lido por reflexão nas DLLs reais em 03/09/2026. A doc já inventou
membro (`Structure.CanModify` não existe).

---

## A conferir na próxima rodada

**Já confirmado em 03/09/2026:** o plug-in carrega e roda; o plano é criado no
curso com o Id digitado; a prescrição entra; o isocentro sai no centro do PTV e
a conversão para coordenada do usuário funciona; a colheita de máquina, taxa e
técnica acerta (`SRS ARC` veio do plano vizinho, não do palpite `ARC`).

Aberto ainda, em ordem de risco:

1. **A criação dos campos.** A energia composta (acima) parou a primeira
   tentativa antes de qualquer `AddBeam` completar — então `AddVMATBeam` **ainda
   não foi exercido**: nem os 178 pontos de controle com pesos iguais, nem se o
   Eclipse aceita o arco como VMAT otimizável direto.
2. **`FitCollimatorToStructure` num feixe VMAT.** Em campo estático o
   comportamento é o do botão homônimo do Eclipse; num arco, ajustar jaws a uma
   estrutura ao longo de 360° pode não fazer o que se espera — ou recusar. A
   abertura em cm sai na mensagem final justamente para isso ser visto na hora.
3. **Limite de tamanho do Id do plano e do campo.** O código já segue e avisa em
   vez de abortar, mas ainda não se sabe qual é o limite aqui.

---

## Estado

Escrito e compilado em 03/09/2026 contra as DLLs reais da ESAPI 15.6, com
`/warn:4 /warnaserror /optimize+ /codepage:65001` — zero erros, zero avisos.

Binário conferido por reflexão:

| conferido | resultado |
|---|---|
| arquitetura | `Amd64` |
| referências | `VMS.TPS.Common.Model.API` e `.Types`, 1.0.300.11, Token 305B81E210EC4B89 |
| atributo | `ESAPIScript(IsWriteable = True)` |
| ponto de entrada | `VMS.TPS.Script.Execute(ScriptContext)`, classe pública, construtor sem argumentos |

**Rodou no Eclipse em 03/09/2026** (TrueBeamSN1001, caso de cabeça): plano
criado, prescrição e isocentro certos, **campos recusados** pela energia
composta. Corrigido em seguida — separação na colheita, na janela e a segunda
tentativa —, mas essa correção **ainda não foi rodada**.

Volume plausível na mensagem não prova campo certo: a régua é abrir o plano e
olhar o BEV.
