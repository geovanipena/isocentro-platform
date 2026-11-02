# Copia CIFRADA do _restrito/ para fora deste disco. O USUARIO roda; o agente
# so escreveu. (So ASCII de proposito: o PowerShell 5.1 le .ps1 sem BOM como
# ANSI, e acento vira lixo no meio de uma mensagem.)
#
# Por que existe (22/10/2026): nada do _restrito/ vai para o Drive nem para o
# GitHub, e esta certo. Mas os backups que existiam (backup_registros,
# backups-git) moram NO MESMO DISCO: um SSD que falha leva junto o espelho da
# capa, o indice de fichas, as simulacoes e os TCs_Teste com gabarito, que sao a
# base de validacao do calculo.
#
# Por que 7-Zip e nao BitLocker To Go: esta estacao e Windows 11 Home, que nao
# CRIA BitLocker em disco externo. O 7-Zip cifra com AES-256 e, com -mhe=on,
# cifra tambem os NOMES dos arquivos -- sem isso, a lista de pastas ja entrega
# nome de paciente. A senha e pedida pelo proprio 7-Zip e nao passa por este
# script nem fica em historico de terminal.
#
# Uso:
#   powershell -ExecutionPolicy Bypass -File tools\copiar_restrito.ps1 -Destino E:\copias
#
# Grava _restrito\ultima_copia.txt (data, destino, tamanho). O
# tools/manutencao.py le essa marca e acusa copia com mais de 30 dias.

param(
    [Parameter(Mandatory = $true)][string]$Destino
)

$ErrorActionPreference = 'Stop'

$restrito = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..\_restrito')).Path
$sete = @('C:\Program Files\7-Zip\7z.exe', 'C:\Program Files (x86)\7-Zip\7z.exe') |
    Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $sete) {
    Write-Host 'O 7-Zip nao esta instalado. Instale de https://www.7-zip.org e rode de novo.' -ForegroundColor Red
    Write-Host 'Sem cifra a copia nao sai: disco externo se perde, e o _restrito tem nome de paciente.'
    exit 1
}
if (-not (Test-Path $Destino)) {
    Write-Host "Destino nao existe: $Destino" -ForegroundColor Red
    exit 1
}

# Mesmo disco nao e copia: e o caso que este script existe para evitar.
$discoOrigem = [IO.Path]::GetPathRoot($restrito).ToUpper()
$discoDestino = [IO.Path]::GetPathRoot((Resolve-Path $Destino).Path).ToUpper()
if ($discoOrigem -eq $discoDestino) {
    Write-Host "O destino esta no mesmo disco ($discoDestino) do _restrito. Use um disco externo." -ForegroundColor Red
    exit 1
}
# G: e o Google Drive nesta estacao. Arquivo cifrado ainda e dado de paciente
# indo para fora, e a regra do README e "nada do _restrito vai para o Drive".
if ((Resolve-Path $Destino).Path -match 'Google Drive|My Drive|Meu Drive|OneDrive') {
    Write-Host 'Destino parece ser nuvem (Drive/OneDrive). O _restrito nao vai para la, nem cifrado.' -ForegroundColor Red
    exit 1
}

$data = Get-Date -Format 'yyyy-MM-dd'
$arquivo = Join-Path $Destino "restrito_$data.7z"
if (Test-Path $arquivo) {
    Write-Host "Ja existe $arquivo. Renomeie ou apague antes (nenhuma copia e sobrescrita)." -ForegroundColor Red
    exit 1
}

Write-Host "Copiando $restrito"
Write-Host "      para $arquivo"
Write-Host 'O 7-Zip vai pedir a senha DUAS vezes. Guarde-a fora deste computador.'
# -p sem valor: o 7-Zip pede a senha. -mhe=on: cifra os nomes. -mx=3: o DICOM
# comprime pouco, e nivel alto so gasta tempo.
& $sete a -t7z -mhe=on -mx=3 -p $arquivo "$restrito\*" '-xr!ultima_copia.txt'
if ($LASTEXITCODE -ne 0) {
    Write-Host "O 7-Zip saiu com $LASTEXITCODE. A copia NAO vale." -ForegroundColor Red
    exit 1
}

Write-Host 'Conferindo o arquivo (pede a senha de novo)...'
& $sete t -p $arquivo
if ($LASTEXITCODE -ne 0) {
    Write-Host 'A conferencia falhou. A copia NAO vale.' -ForegroundColor Red
    exit 1
}

$mb = [math]::Round((Get-Item $arquivo).Length / 1MB, 1)
# A marca diz QUANDO e PARA ONDE, nunca o conteudo: e lida pela manutencao, que
# roda no contexto do agente.
"$data`t$Destino`t$mb MB" | Out-File -FilePath (Join-Path $restrito 'ultima_copia.txt') -Encoding ascii
Write-Host "Pronto: $mb MB em $arquivo" -ForegroundColor Cyan
