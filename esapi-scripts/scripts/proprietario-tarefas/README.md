# Proprietário de tarefas (ARIA)

- `Proprietario_Tarefas.cs` (+ `Proprietario_Tarefas_Core.cs` e `.csproj`) — DLL que **não
  grava no paciente**: o ESAPI serve só para ler `context.CurrentUser` e o paciente aberto; a atribuição é
  feita por **UI Automation** sobre a janela do ARIA (processo `VMS.SF.Host`, mesma sessão do Eclipse — o
  título nunca contém "ARIA"). Torna o usuário logado **proprietário** das atividades de Care Path
  *Documentação* e *Aprovação Física* (obrigatórias) + *Preparação/Execução/Análise PD* (**opcionais** —
  nem todo fluxo tem PD; ausência não é erro). O Eclipse é devolvido na hora (trabalho em thread de fundo —
  leitura longa na thread da UI já fechou o Eclipse uma vez); aviso discreto no canto e **mensagem só em
  problema**. Trava: confere atividade, data (a lista mostra `dd/MM`, o diálogo `MM/dd`), paciente e status
  da linha antes de gravar e cancela sem salvar se algo não bater; a equipe (ex. "Físicos - Radioterapia")
  é mantida. **Status:** assume pendentes em qualquer estágio (inclusive *Em andamento* e status ilegível na
  lista — sob Citrix a coluna às vezes só desenha o ícone, e aí o status real vem do diálogo);
  Concluídas/Canceladas são **puladas sem parar** o resto; mais de uma pendente da mesma atividade = todas
  as recentes (até 3). **Citrix/uma tela:** DPI da thread casado com o da janela, janela fora do monitor é
  movida para dentro (e devolvida no fim), janela coberta é trazida à frente, e abrir a linha errada faz
  cancelar e repetir (até 3× por linha) antes de desistir. **Fim:** terminando sem problema, a janela do
  PACIENTE no ARIA é fechada (WM_CLOSE; as outras janelas e o aplicativo ficam); parando no meio, fica
  aberta para conferência, e se o ARIA pedir confirmação o script não responde por ele. Versão PowerShell equivalente em
  `Proprietario_Tarefas.ps1` (nesta pasta) (UTF-8 **com** BOM, exigência do PS 5.1). Compilar com **csc** do .NET
  Framework (linha de comando no README); saída `AriaTarefasV2_8.esapi.dll`.
  **Validado no ARIA real** (V2.1, 4/4 atividades do paciente de teste); V2.6 testada só em mock — aguarda
  teste real.

**Compilar:** DLL: `MSBuild.exe Proprietario_Tarefas.csproj /p:Configuration=Release` nesta pasta (ou o `csc` abaixo).

Histórico das rodadas e o que está pendente: [NOTAS.md](NOTAS.md).

## Detalhe: automação de interface do ARIA (fora do ESAPI)

`Proprietario_Tarefas.ps1` — PowerShell 5.1 + UI Automation. Atribui o usuário logado como
proprietário das atividades de Care Path **Documentação · Aprovação Física · Preparação PD · Execução PD ·
Análise PD**. Não usa ESAPI (que não expõe tarefas) nem toca no banco Varian.

```powershell
.\Proprietario_Tarefas.ps1 -Modo Inspecionar   # 1x: descobre os AutomationId da tela
.\Proprietario_Tarefas.ps1                     # simulação (padrão) — não altera nada
.\Proprietario_Tarefas.ps1 -Modo Aplicar       # grava
```

Precisa rodar **dentro da sessão onde o ARIA executa** — a partir do cliente Citrix a janela é um bitmap
remoto e o UI Automation não enxerga os controles (o script detecta e aborta). Arquivo em **UTF-8 com BOM**
(PowerShell 5.1 exige BOM para ler os acentos).

### Versão DLL (plug-in ESAPI)

`Proprietario_Tarefas.cs` + `Proprietario_Tarefas_Core.cs` +
`Proprietario_Tarefas.csproj` → binary plug-in `AriaTarefasV2_8.esapi.dll`, rodado pelo Eclipse em
**Tools ▸ Scripts**. Vantagem sobre o `.ps1`: executa no servidor onde o Eclipse está publicado (se o ARIA
estiver na mesma sessão, o problema do Citrix desaparece) e pega o usuário logado direto de
`context.CurrentUser` — sem heurística de barra de status.

Fluxo: o Eclipse é devolvido na hora e o trabalho corre em segundo plano — lê a aba **Sequência de
Tratamento** do Care Path, abre cada atividade pendente, adiciona o usuário como proprietário (mantendo a
equipe) e salva. Aviso discreto no canto: "assumindo…" → "✓ N tarefas assumidas"; **mensagem só em
problema** (parou, tarefa ambígua, obrigatória ausente, leitura parcial), com o log na área de
transferência. Antes de gravar confere atividade, data, paciente e status **no próprio diálogo** e cancela
sem salvar se algo não bater. Não grava no paciente (dispensa `ESAPIScript(IsWriteable=true)`).

**Status das atividades.** São assumidas as pendentes em qualquer estágio — *Pendente*, *Disponível*, *Em
andamento*, *Parcialmente concluído* — e também aquelas cuja coluna de status não é legível na lista (sob
Citrix ela às vezes só desenha o ícone): nesse caso o status verdadeiro é lido no diálogo. *Concluída* e
*Cancelada* nunca são tocadas — são **puladas**, e a execução continua nas outras. Havendo mais de uma
ocorrência pendente da mesma atividade, todas as recentes são assumidas (até 3; acima disso quem escolhe é
o usuário).

**Citrix, resolução e uma tela só.** A medição e o clique são feitos no mesmo modo de DPI da janela do ARIA
(escala da sessão ≠ escala do console fazia o clique cair em outra linha). Mexer na posição da janela é
**último recurso**: só quando a própria linha a clicar está fora da área visível do monitor, e **nunca** com
a janela maximizada (o retângulo de uma janela maximizada passa da área de trabalho pelas bordas invisíveis
— "corrigir" isso desalinhava o ARIA e o clique deixava de abrir a atividade); movida, ela volta ao lugar no
fim. Se estiver coberta
(Eclipse maximizado, barra do Citrix, pop-up), é trazida à frente e a tentativa se repete — o clique só sai
depois que o Windows confirma que o ponto é mesmo a linha certa. Abrindo a linha errada, o diálogo é
cancelado sem salvar e a linha é aberta de novo (até 3 vezes) antes de o script desistir.

**Fim da execução.** Terminando sem problema, a **janela do paciente no ARIA é fechada** (as demais janelas
do ARIA e o próprio aplicativo continuam abertos) e o foco volta ao Eclipse. Se o script parar no meio, a
janela **fica aberta** para conferência. Se o ARIA pedir confirmação ao fechar, o script não responde por
você: a janela permanece e o aviso diz o porquê.

Build sem Visual Studio (csc do .NET Framework, `/codepage:65001` porque os fontes são UTF-8 sem BOM):

```
csc /noconfig /nostdlib+ /target:library /platform:x64 /langversion:5 /codepage:65001 ^
    /out:bin\Release\AriaTarefasV2_8.esapi.dll ^
    /r:<ref>\mscorlib.dll /r:<ref>\System.dll /r:<ref>\System.Core.dll /r:<ref>\System.Xml.dll ^
    /r:<ref>\System.Xaml.dll /r:<ref>\UIAutomationClient.dll /r:<ref>\UIAutomationTypes.dll ^
    /r:<ref>\WindowsBase.dll /r:<ref>\PresentationFramework.dll /r:<ref>\PresentationCore.dll ^
    /r:..\..\lib\VMS.TPS.Common.Model.API.dll /r:..\..\lib\VMS.TPS.Common.Model.Types.dll ^
    Proprietario_Tarefas_Core.cs Proprietario_Tarefas.cs
```
`<ref>` = `C:\Program Files (x86)\Reference Assemblies\Microsoft\Framework\.NETFramework\v4.5.2`.

**Como o ARIA é localizado:** pelo **processo `VMS.SF.Host`**, não pelo título — as janelas do ARIA se
chamam `PACIENTE, NOME (ID) - <workspace>` e nunca contêm "ARIA" no nome. O script examina todas as janelas
desse processo e usa a primeira que (1) exibe o paciente aberto no Eclipse e (2) contém as tarefas. Se o
paciente da tela não for o do Eclipse, aborta sem escrever.
