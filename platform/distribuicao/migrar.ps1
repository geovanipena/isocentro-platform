<#
    Traz os dados da instalação antiga (ISOCENTRO, ou Radioteraficha antes de
    15/10/2026) para esta pasta. Os arquivos de dados não mudaram de nome.

    Uso:  .\migrar.ps1 "C:\caminho\da\instalacao\antiga"

    NUNCA sobrescreve: se o arquivo já existe aqui, pula e avisa. Perder o
    usuarios.json de uma instalação em uso é perder o acesso de todo mundo, e
    um script de migração não é lugar para decidir isso sozinho.

    (É por isso que o pacote de distribuição não pode levar nenhum arquivo de
    dados: um deles aqui faria a migração PULAR o arquivo real do serviço, e a
    biblioteca de notas sumiria sem aviso. O tools/gerar_executavel.py confere.)

    Rode com o programa FECHADO em todas as estações que usam esta pasta.
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$Antiga
)

$ErrorActionPreference = "Stop"
$Nova = $PSScriptRoot

if (-not (Test-Path -LiteralPath $Antiga)) {
    Write-Host "Pasta antiga nao encontrada: $Antiga" -ForegroundColor Red
    exit 1
}
if ((Resolve-Path -LiteralPath $Antiga).Path -eq (Resolve-Path -LiteralPath $Nova).Path) {
    Write-Host "A pasta antiga e esta mesma pasta. Nada a fazer." -ForegroundColor Yellow
    exit 1
}

# Os .lock e os .tmp ficam de fora de proposito: sao lixo de trabalho, e o
# .lock e justamente o arquivo que o Windows mantem travado.
# O sessoes.json NAO entra: ele diz quem esta logado AGORA, e uma sessao morta
# trazida da instalacao antiga derrubaria quem entrasse depois.
$itens = @(
    "usuarios.json",
    "preferencias.json",
    "registro_fichas.json",
    "historico_uso.jsonl",
    "cadastro_sus.json",
    "inventario_imobilizadores.json",
    "notas_posicionamento.json",
    "correcoes_capa.json",
    "config_servico.json",
    "backup_registros",
    "espelho_capa"
)

$copiados = 0; $pulados = 0; $ausentes = 0
foreach ($item in $itens) {
    $origem  = Join-Path $Antiga $item
    $destino = Join-Path $Nova   $item

    if (-not (Test-Path -LiteralPath $origem)) {
        Write-Host ("  [nao existe la] {0}" -f $item) -ForegroundColor DarkGray
        $ausentes++
        continue
    }
    if (Test-Path -LiteralPath $destino) {
        Write-Host ("  [JA EXISTE AQUI - pulado] {0}" -f $item) -ForegroundColor Yellow
        $pulados++
        continue
    }
    Copy-Item -LiteralPath $origem -Destination $destino -Recurse
    Write-Host ("  [copiado] {0}" -f $item) -ForegroundColor Green
    $copiados++
}

Write-Host ""
Write-Host ("{0} copiados, {1} pulados (ja existiam), {2} ausentes na antiga." -f `
            $copiados, $pulados, $ausentes)
Write-Host ""
if (-not (Test-Path -LiteralPath (Join-Path $Nova "config_servico.json"))) {
    Write-Host "PROXIMO PASSO: abrir o programa como admin e ir em" -ForegroundColor Yellow
    Write-Host "Configuracoes -> Servico para apontar o banco (SRVINSIGHT)," -ForegroundColor Yellow
    Write-Host "os relatorios e as simulacoes. Ver o item 0 do MIGRAR.txt." -ForegroundColor Yellow
    Write-Host ""
}
Write-Host "Medicos e fisicos ficam em %USERPROFILE% e sao migrados sozinhos."
