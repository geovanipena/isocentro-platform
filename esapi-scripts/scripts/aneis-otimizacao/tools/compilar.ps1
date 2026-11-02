# Compila o plug-in. O Eclipse guarda o script pela identidade do assembly e
# recusa reimportar por cima de um nome que ja existe -- entao durante o
# desenvolvimento cada rodada precisa de um nome novo.
#
#   .\tools\compilar.ps1            -> AneisOtimizacao.esapi.dll
#   .\tools\compilar.ps1 -Sufixo v3 -> AneisOtimizacao_v3.esapi.dll
#
# O sufixo e so para iterar. A versao que vai para o servico volta a ser o
# nome limpo, depois de remover as tentativas antigas da lista do Eclipse.

param(
    [string]$Sufixo = "",
    [string]$EsapiDir = ""
)

$ErrorActionPreference = "Stop"
$raiz = Split-Path $PSScriptRoot -Parent
$proj = Join-Path $raiz "AneisOtimizacao"
$out  = Join-Path $proj "bin\x64\Release"

if ($EsapiDir -eq "") { $EsapiDir = Join-Path $raiz "..\..\lib" }

$nome = if ($Sufixo -eq "") { "AneisOtimizacao.esapi.dll" } else { "AneisOtimizacao_$Sufixo.esapi.dll" }
$alvo = Join-Path $out $nome

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

& $csc /nologo /warn:4 /warnaserror /optimize+ /target:library /platform:x64 `
    /out:"$alvo" `
    /r:"$EsapiDir\VMS.TPS.Common.Model.API.dll" `
    /r:"$EsapiDir\VMS.TPS.Common.Model.Types.dll" `
    /r:"$($ra.FullName)\PresentationCore.dll" `
    /r:"$($ra.FullName)\PresentationFramework.dll" `
    /r:"$($ra.FullName)\WindowsBase.dll" `
    /r:"$($ra.FullName)\System.Xaml.dll" `
    (Join-Path $proj "Script.cs") `
    (Join-Path $proj "JanelaEscolha.cs") `
    (Join-Path $proj "Properties\AssemblyInfo.cs")

if ($LASTEXITCODE -ne 0) { throw "compilacao falhou" }

# Copia para a Area de Trabalho: e de la que o arquivo e arrastado para o Eclipse.
$desktop = [Environment]::GetFolderPath("Desktop")
Copy-Item $alvo $desktop -Force

"OK  $nome"
"    {0:N0} bytes" -f (Get-Item $alvo).Length
"    $alvo"
"    copiado para $desktop"
