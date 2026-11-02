#requires -Version 5
<#
  Roda TODOS os checks do projeto de uma vez (use antes de commitar):
    1. paridade da #region PADRÃO CLINICA   (tools/check_region_parity.py)
    2. armadilhas do single-file C# 5       (tools/check_csharp_traps.py)
    3. typecheck / compilação C#5 net452    (tools/typecheck.ps1)
    4. encoding: BOM / EOL / chaves         (tools/check_encoding.sh, se houver bash)

  Uso:  powershell -ExecutionPolicy Bypass -File tools\check_all.ps1
  Saída: 0 = tudo PASS · 1 = alguma falha. Typecheck sem DLLs (exit 3) é apenas avisado.
#>
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
$py = (Get-Command python -ErrorAction SilentlyContinue)
if (-not $py) { $py = (Get-Command python3 -ErrorAction SilentlyContinue) }
if (-not $py) { Write-Error 'python não encontrado no PATH.'; exit 4 }
$py = $py.Source
$fail = 0

Write-Host '== 1/4  paridade #region PADRAO CLINICA ==' -ForegroundColor Cyan
& $py (Join-Path $root 'tools\check_region_parity.py'); if ($LASTEXITCODE -ne 0) { $fail++ }

Write-Host '== 2/4  armadilhas C# 5 ==' -ForegroundColor Cyan
& $py (Join-Path $root 'tools\check_csharp_traps.py'); if ($LASTEXITCODE -ne 0) { $fail++ }

Write-Host '== 3/4  typecheck (compilacao C#5/net452) ==' -ForegroundColor Cyan
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'tools\typecheck.ps1')
if ($LASTEXITCODE -eq 3) { Write-Host 'AVISO: DLLs Varian ausentes em lib/ - typecheck pulado.' -ForegroundColor Yellow }
elseif ($LASTEXITCODE -ne 0) { $fail++ }

$bash = (Get-Command bash -ErrorAction SilentlyContinue)
if ($bash) {
    Write-Host '== 4/4  encoding (BOM / EOL / chaves) ==' -ForegroundColor Cyan
    & $bash.Source (Join-Path $root 'tools/check_encoding.sh'); if ($LASTEXITCODE -ne 0) { $fail++ }
} else {
    Write-Host '== 4/4  encoding - pulado (bash nao encontrado) ==' -ForegroundColor Yellow
}

Write-Host ('=' * 50)
if ($fail -gt 0) { Write-Host "CHECK_ALL: FALHA - $fail check(s) com erro." -ForegroundColor Red; exit 1 }
Write-Host 'CHECK_ALL: PASS' -ForegroundColor Green
exit 0
