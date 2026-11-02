<#
    build_esapi.ps1 — compila um script ESAPI gravável e entrega a DLL na
    pasta de scripts, em UM comando.

    Existe para eliminar o passo que mais custa tempo no ciclo de
    desenvolvimento: abrir o ESAPI Script Administration a cada build.
    Isso NÃO é necessário. A Eclipse identifica o script por nome + versão
    do assembly; enquanto os dois não mudarem, o registro publicado/aprovado
    continua valendo e basta SOBRESCREVER a DLL na pasta.

    Republicar só é necessário quando a versão do assembly muda — e mudar a
    versão é ato deliberado de release, não algo que acontece a cada build
    (por isso AssemblyVersion é fixa, nunca wildcard).

    Uso:
        powershell -ExecutionPolicy Bypass -File tools\build_esapi.ps1 `
            -Projeto "scripts\estruturas-bexiga-minima\EstruturasOpt_Bexiga_Minima.csproj" `
            -Destino "\\Client\G$\4 - FÍSICA\22. Scripts Clinica"

    Omitindo -Destino, a DLL fica só em bin\Release e o caminho é impresso.
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$Projeto,

    [string]$Destino,

    [string]$MSBuild = "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\MSBuild.exe"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $Projeto)) {
    Write-Host "ERRO: projeto nao encontrado: $Projeto" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $MSBuild)) {
    Write-Host "ERRO: MSBuild nao encontrado: $MSBuild" -ForegroundColor Red
    Write-Host "      Informe o caminho com -MSBuild."
    exit 1
}

$projetoDir = Split-Path -Parent (Resolve-Path $Projeto)

# As DLLs licenciadas da Varian ficam fora do git; sem elas o build falha com
# erros de referencia que nao explicam a causa real.
$lib = Join-Path (Split-Path -Parent $PSScriptRoot) "lib"
foreach ($dll in @("VMS.TPS.Common.Model.API.dll", "VMS.TPS.Common.Model.Types.dll")) {
    if (-not (Test-Path (Join-Path $lib $dll))) {
        Write-Host "ERRO: falta $dll em $lib" -ForegroundColor Red
        Write-Host "      Copie as duas DLLs da Varian do GAC_64 do servidor Eclipse."
        exit 1
    }
}

Write-Host "Compilando $(Split-Path -Leaf $Projeto)..." -ForegroundColor Cyan
& $MSBuild $Projeto /p:Configuration=Release /nologo /verbosity:minimal

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "FALHA na compilacao. Nada foi copiado." -ForegroundColor Red
    exit $LASTEXITCODE
}

$saida = Get-ChildItem -Path (Join-Path $projetoDir "bin\Release") -Filter "*.esapi.dll" |
         Sort-Object LastWriteTime -Descending |
         Select-Object -First 1

if (-not $saida) {
    Write-Host "ERRO: build terminou sem erro mas nao produziu .esapi.dll" -ForegroundColor Red
    exit 1
}

$versao = [System.Diagnostics.FileVersionInfo]::GetVersionInfo($saida.FullName).FileVersion

Write-Host ""
Write-Host "OK: $($saida.Name)  (versao de arquivo: $versao)" -ForegroundColor Green

if ($Destino) {
    if (-not (Test-Path $Destino)) {
        Write-Host "ERRO: destino nao encontrado: $Destino" -ForegroundColor Red
        exit 1
    }
    Copy-Item $saida.FullName -Destination $Destino -Force
    Write-Host "Copiado para: $Destino" -ForegroundColor Green
} else {
    Write-Host "DLL em: $($saida.FullName)"
    Write-Host "(sem -Destino: copie manualmente para a pasta de scripts)"
}

Write-Host ""
Write-Host "-----------------------------------------------------------------"
Write-Host " NAO abra o ESAPI Script Administration." -ForegroundColor Yellow
Write-Host " Nome e versao do assembly nao mudaram, entao o registro ja"
Write-Host " aprovado continua valendo. Publicar de novo so devolve"
Write-Host " 'o script ... ja existe'."
Write-Host ""
Write-Host " Va direto na Eclipse: Tools > Scripts > pasta > Executar."
Write-Host "-----------------------------------------------------------------"
