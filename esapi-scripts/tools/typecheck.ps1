#requires -Version 5
<#
  Typecheck dos scripts single-file ESAPI — espelha o compilador single-file do
  Eclipse (C# 5, warnings-as-error, net452) e pega ANTES do deploy os erros que
  hoje só aparecem no Eclipse (CS0414 static readonly não usado, CS0162/CS0429,
  sintaxe, recursos > C# 5).

  Compila CADA script ISOLADAMENTE — todos declaram VMS.TPS.Script, então não
  podem ser compilados juntos (tipo duplicado). Ignora os .cs que têm um .csproj
  de mesmo nome (esses são as DLLs graváveis, compiladas via MSBuild próprio).

  PRÉ-REQUISITO (uma vez): copiar do GAC do servidor Eclipse para lib/:
    C:\Windows\Microsoft.NET\assembly\GAC_64\  ->  lib\
      VMS.TPS.Common.Model.API.dll
      VMS.TPS.Common.Model.Types.dll

  Uso:  powershell -ExecutionPolicy Bypass -File tools\typecheck.ps1
        powershell -ExecutionPolicy Bypass -File tools\typecheck.ps1 -Path scripts\constraints\Foo.cs
        (com -Path compila SÓ aquele script; sem -Path compila todos)

  Saídas: 0 = PASS · 1 = erro de compilação · 3 = DLLs Varian ausentes · 4 = sem csc.
#>
param([string]$Path = '')
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot            # tools/ -> raiz do repo
$lib  = Join-Path $root 'lib'
$dllApi   = Join-Path $lib 'VMS.TPS.Common.Model.API.dll'
$dllTypes = Join-Path $lib 'VMS.TPS.Common.Model.Types.dll'

if (-not (Test-Path $dllApi) -or -not (Test-Path $dllTypes)) {
    Write-Host "FALTAM as DLLs Varian em lib\. Copie do servidor:" -ForegroundColor Yellow
    Write-Host "  C:\Windows\Microsoft.NET\assembly\GAC_64\  ->  $lib"
    Write-Host "  (VMS.TPS.Common.Model.API.dll e VMS.TPS.Common.Model.Types.dll)"
    exit 3
}

# --- localizar csc.exe: 1) Roslyn via vswhere (se houver VS); 2) csc clássico do
#     .NET Framework (C:\Windows\Microsoft.NET\Framework64\v4.0.30319), que já
#     suporta /langversion:5 e net452 — presente em qualquer máquina com .NET 4.x. ---
$cscPath = $null
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
if (Test-Path $vswhere) {
    $vsPath = & $vswhere -latest -products * -property installationPath
    if ($vsPath) {
        $roslyn = Get-ChildItem -Path (Join-Path $vsPath 'MSBuild') -Filter csc.exe -Recurse -ErrorAction SilentlyContinue |
                  Where-Object { $_.FullName -match 'Roslyn' } | Select-Object -First 1
        if ($roslyn) { $cscPath = $roslyn.FullName }
    }
}
if (-not $cscPath) {
    $classic = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
    if (Test-Path $classic) { $cscPath = $classic }
}
if (-not $cscPath) { Write-Error 'Nenhum csc.exe encontrado (nem Roslyn/VS, nem .NET Framework 4.x).'; exit 4 }
Write-Host "csc: $cscPath" -ForegroundColor DarkGray

# --- referências: Varian + BCL/WPF do net452 (reference assemblies se existirem) ---
$refDir = Join-Path ${env:ProgramFiles(x86)} 'Reference Assemblies\Microsoft\Framework\.NETFramework\v4.5.2'
$refs = @($dllApi, $dllTypes)
foreach ($a in @('System.dll','System.Core.dll','System.Data.dll','System.Xml.dll',
                 'PresentationCore.dll','PresentationFramework.dll','WindowsBase.dll','System.Xaml.dll')) {
    $p = Join-Path $refDir $a
    if (Test-Path $p) { $refs += $p } else { $refs += $a }  # fallback: nome simples
}
$refArgs = $refs | ForEach-Object { "/reference:$_" }

# --- alvos: um único arquivo (-File) ou todos os scripts/<pasta>/*.cs ---
$scriptsDir = Join-Path $root 'scripts'
if ($Path) {
    if (-not (Test-Path -LiteralPath $Path)) { Write-Error "Arquivo não encontrado: $Path"; exit 4 }
    $targets = @(Get-Item -LiteralPath $Path)
} else {
    $targets = @(Get-ChildItem -Path $scriptsDir -Filter *.cs -Recurse -Depth 1)
}
$fail = 0
$targets | ForEach-Object {
    # pasta com .csproj = plug-in DLL, compilado pelo próprio projeto -> pula
    if (Get-ChildItem -Path $_.DirectoryName -Filter *.csproj) { return }
    $out = Join-Path $env:TEMP ($_.BaseName + '.typecheck.dll')
    Write-Host "==> $($_.Name)" -ForegroundColor Cyan
    # /noconfig: ignora o csc.rsp padrão (que auto-referencia System.*, causando
    # CS1703 duplicado com nossas refs net452 explícitas). mscorlib segue implícito.
    & $cscPath /noconfig /nologo /target:library /langversion:5 /warnaserror+ /out:"$out" @refArgs "$($_.FullName)"
    if ($LASTEXITCODE -ne 0) { $script:fail++ }
}

if ($fail -gt 0) { Write-Host "TYPECHECK: $fail arquivo(s) com erro." -ForegroundColor Red; exit 1 }
Write-Host 'TYPECHECK: PASS' -ForegroundColor Green
exit 0
