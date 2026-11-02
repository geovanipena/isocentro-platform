# Compila os DOIS hospedeiros do mesmo codigo:
#
#   PrePlan.esapi.dll  -> plug-in, importado no Eclipse
#   PrePlan.exe        -> standalone, rodado pelo tools\preplan.bat
#
# O Eclipse guarda o script pela identidade do assembly e recusa reimportar por
# cima de um nome que ja existe -- entao, para o PLUG-IN, cada rodada de
# desenvolvimento precisa de um nome novo:
#
#   .\tools\compilar.ps1            -> PrePlan.esapi.dll  e  PrePlan.exe
#   .\tools\compilar.ps1 -Sufixo v5 -> PrePlan_v5.esapi.dll  e  PrePlan_v5.exe
#
# O .exe nao tem esse problema: e so rodar de novo. O sufixo so o acompanha
# para os dois nao se perderem um do outro.

param(
    [string]$Sufixo = "",
    [string]$EsapiDir = "",
    [switch]$SoExe
)

$ErrorActionPreference = "Stop"
$raiz = Split-Path $PSScriptRoot -Parent
$proj = Join-Path $raiz "PrePlan"
$out  = Join-Path $proj "bin\x64\Release"

if ($EsapiDir -eq "") { $EsapiDir = Join-Path $raiz "..\..\lib" }

$csc = "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if (-not (Test-Path $csc)) { throw "csc do .NET Framework nao encontrado em $csc" }

$ra = Get-ChildItem "C:\Program Files (x86)\Reference Assemblies\Microsoft\Framework\.NETFramework" -Directory |
      Sort-Object Name | Select-Object -Last 1
if (-not $ra) { throw "Reference assemblies do .NET Framework nao encontradas" }

foreach ($d in @("VMS.TPS.Common.Model.API.dll","VMS.TPS.Common.Model.Types.dll")) {
    if (-not (Test-Path (Join-Path $EsapiDir $d))) {
        throw "ESAPI nao encontrada: $EsapiDir\$d  -- ver o README"
    }
}

New-Item -ItemType Directory -Force $out | Out-Null

# Todos os fontes vao nos dois: o plug-in leva junto um Programa.Main que nunca
# e chamado, e o .exe uma classe Script que o Eclipse nunca ve. Duas listas de
# arquivo seriam duas listas para esquecer de atualizar.
$fontes = @(
    "Script.cs", "Programa.cs", "Fluxo.cs", "Bancada.cs",
    "Pedido.cs", "Montagem.cs", "Maquinas.cs", "Sonda.cs",
    "JanelaPrePlan.cs", "JanelaAbrir.cs", "Properties\AssemblyInfo.cs"
) | ForEach-Object { Join-Path $proj $_ }

$referencias = @(
    "$EsapiDir\VMS.TPS.Common.Model.API.dll",
    "$EsapiDir\VMS.TPS.Common.Model.Types.dll",
    "$($ra.FullName)\PresentationCore.dll",
    "$($ra.FullName)\PresentationFramework.dll",
    "$($ra.FullName)\WindowsBase.dll",
    "$($ra.FullName)\System.Xaml.dll"
)

function Compilar($alvo, $tipo, $extras) {
    # /codepage:65001 e obrigatorio: os fontes sao UTF-8 SEM BOM e tem acento
    # dentro de string de tela. Sem ele o csc le pela codepage ANSI da estacao e
    # o acento chega torto na MessageBox -- compila limpo, e so aparece na
    # frente de quem esta usando.
    $args = @("/nologo","/warn:4","/warnaserror","/optimize+","/codepage:65001",
              "/target:$tipo","/platform:x64","/out:$alvo")
    $args += ($referencias | ForEach-Object { "/r:$_" })
    $args += $extras
    $args += $fontes

    & $csc $args
    if ($LASTEXITCODE -ne 0) { throw "compilacao de $alvo falhou" }
}

$desktop = [Environment]::GetFolderPath("Desktop")
$feitos = @()

if (-not $SoExe) {
    $nomeDll = if ($Sufixo -eq "") { "PrePlan.esapi.dll" } else { "PrePlan_$Sufixo.esapi.dll" }
    $alvoDll = Join-Path $out $nomeDll
    Compilar $alvoDll "library" @()
    Copy-Item $alvoDll $desktop -Force
    $feitos += $alvoDll
}

$nomeExe = if ($Sufixo -eq "") { "PrePlan.exe" } else { "PrePlan_$Sufixo.exe" }
$alvoExe = Join-Path $out $nomeExe
Compilar $alvoExe "exe" @("/main:VMS.TPS.Programa")
Copy-Item $alvoExe $desktop -Force
$feitos += $alvoExe

# O .bat vai JUNTO, sempre. Ele procura o PrePlan.exe ao lado dele primeiro, e
# separar os dois e o que faz alguem achar o executavel e nao achar o .bat --
# e ai roda o exe direto, sem o pause que segura o codigo de saida na tela.
$bat = Join-Path $PSScriptRoot "preplan.bat"
Copy-Item $bat $out -Force
Copy-Item $bat $desktop -Force

foreach ($f in $feitos) {
    "OK  {0}" -f (Split-Path $f -Leaf)
    "    {0:N0} bytes" -f (Get-Item $f).Length
    "    $f"
}
"    copiados para $desktop"
