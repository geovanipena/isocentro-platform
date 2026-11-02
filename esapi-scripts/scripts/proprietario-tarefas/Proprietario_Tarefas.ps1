#Requires -Version 5.1
<#
.SYNOPSIS
    Atribui o usuário logado como proprietário das atividades de Care Path do ARIA.

.DESCRIPTION
    Automação de interface (UI Automation) sobre a janela do ARIA. NÃO usa ESAPI —
    o ESAPI 15.6 não expõe tarefas/atividades — e NÃO escreve no banco Varian.

    Tarefas-alvo padrão:
        Documentação · Aprovação Física · Preparação PD · Execução PD · Análise PD

    Três modos:
        Inspecionar → despeja a árvore de controles da janela (use UMA vez para
                      descobrir os AutomationId reais e preencher $SELETORES).
        Simular     → localiza as tarefas e mostra o que faria. NÃO altera nada. (padrão)
        Aplicar     → define o proprietário de fato.

.PARAMETER Modo
    Inspecionar | Simular | Aplicar. Padrão: Simular.

.PARAMETER Usuario
    Nome do proprietário a atribuir. Se omitido, tenta ler o usuário logado no ARIA
    (barra de status/título) e, falhando, usa o usuário Windows da sessão.

.PARAMETER Tarefas
    Sobrescreve a lista de tarefas-alvo.

.EXAMPLE
    .\Proprietario_Tarefas.ps1 -Modo Inspecionar -Saida C:\temp\arvore.txt

.EXAMPLE
    .\Proprietario_Tarefas.ps1

.EXAMPLE
    .\Proprietario_Tarefas.ps1 -Modo Aplicar

.NOTES
    Física Médica — Clinica/Rede. Geovani Pena.
    VALIDAR EM PACIENTE DE TESTE ANTES DE USO CLÍNICO.
#>

[CmdletBinding()]
param(
    [ValidateSet('Inspecionar', 'Simular', 'Aplicar')]
    [string]   $Modo = 'Simular',
    [string]   $Usuario,
    [string[]] $Tarefas,
    [string]   $TituloJanela = 'ARIA',
    [int]      $TimeoutSeg = 20,
    [int]      $Profundidade = 14,
    [string]   $Saida,
    [string]   $LogPath = (Join-Path $env:TEMP 'aria-proprietario-tarefas.log')
)

$ErrorActionPreference = 'Stop'

# =====================================================================
#  CONFIGURAÇÃO
# =====================================================================

# Tarefas de Care Path que devem receber o usuário logado como proprietário.
$TAREFAS_PADRAO = @(
    'Documentação',
    'Aprovação Física',
    'Preparação PD',
    'Execução PD',
    'Análise PD'
)

# Rótulos possíveis da coluna/campo de proprietário (pt-BR e en-US).
$ALIAS_PROPRIETARIO = @('Proprietário', 'Proprietario', 'Owner', 'Responsável', 'Responsavel', 'Assigned To')

# ---------------------------------------------------------------------
#  PREENCHER APÓS RODAR O MODO Inspecionar
#  Deixe '' para o script cair na busca heurística (mais lenta e frágil).
# ---------------------------------------------------------------------
$SELETORES = @{
    # Grade/lista que contém as atividades do Care Path
    GradeAutomationId  = ''
    # Campo editável de proprietário dentro da linha selecionada
    CampoAutomationId  = ''
    # Botão de confirmação, se a edição exigir (ex.: 'Salvar', 'OK'). '' = não clicar.
    BotaoConfirmarNome = ''
}

# =====================================================================
#  INFRAESTRUTURA
# =====================================================================

function Write-Log {
    param(
        [string] $Mensagem,
        [ValidateSet('INFO', 'OK', 'ATN', 'FAIL')]
        [string] $Nivel = 'INFO'
    )

    $linha = ('{0} [{1}] {2}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Nivel, $Mensagem)
    $cor = 'Gray'
    if ($Nivel -eq 'OK')   { $cor = 'Green' }
    if ($Nivel -eq 'ATN')  { $cor = 'Yellow' }
    if ($Nivel -eq 'FAIL') { $cor = 'Red' }
    Write-Host $linha -ForegroundColor $cor
    try { Add-Content -Path $LogPath -Value $linha -Encoding UTF8 } catch { }
}

# Normalização acento- e caixa-insensível (mesma regra do Norm() dos scripts ESAPI).
function Norm {
    param([string] $Texto)

    if ([string]::IsNullOrWhiteSpace($Texto)) { return '' }
    $d = $Texto.Normalize([Text.NormalizationForm]::FormD)
    $sb = New-Object System.Text.StringBuilder
    foreach ($ch in $d.ToCharArray()) {
        $cat = [Globalization.CharUnicodeInfo]::GetUnicodeCategory($ch)
        if ($cat -ne [Globalization.UnicodeCategory]::NonSpacingMark) { [void]$sb.Append($ch) }
    }
    return ($sb.ToString() -replace '\s+', ' ').Trim().ToUpperInvariant()
}

function Initialize-UIA {
    Add-Type -AssemblyName UIAutomationClient
    Add-Type -AssemblyName UIAutomationTypes
    Add-Type -AssemblyName WindowsBase
}

function Get-ControlTypeNome {
    param($Elemento)
    try { return ($Elemento.Current.ControlType.ProgrammaticName -replace 'ControlType\.', '') } catch { return '' }
}

function Get-NomeSeguro {
    param($Elemento)
    try { return $Elemento.Current.Name } catch { return '' }
}

# =====================================================================
#  LOCALIZAÇÃO DA JANELA
# =====================================================================

function Get-JanelaAria {
    param([string] $Titulo, [int] $Timeout)

    $root = [System.Windows.Automation.AutomationElement]::RootElement
    $cond = New-Object System.Windows.Automation.PropertyCondition(
        [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
        [System.Windows.Automation.ControlType]::Window)

    $alvo = Norm $Titulo
    $limite = (Get-Date).AddSeconds($Timeout)

    while ((Get-Date) -lt $limite) {
        $janelas = $root.FindAll([System.Windows.Automation.TreeScope]::Children, $cond)
        foreach ($j in $janelas) {
            $nome = Get-NomeSeguro $j
            if ($nome -and (Norm $nome).Contains($alvo)) { return $j }
        }
        Start-Sleep -Milliseconds 500
    }
    return $null
}

# Citrix: a janela do receiver é um bitmap remoto — UI Automation não enxerga
# os controles internos do ARIA a partir do cliente.
function Test-Citrix {
    param($Janela)

    $procsCitrix = @('wfica32', 'CDViewer', 'SelfServicePlugin', 'concentr')
    try {
        $idProc = $Janela.Current.ProcessId
        $proc = Get-Process -Id $idProc -ErrorAction SilentlyContinue
        if ($proc -and ($procsCitrix -contains $proc.ProcessName)) {
            Write-Log ("A janela pertence ao processo Citrix '{0}'. UI Automation NAO alcanca os controles do ARIA a partir do cliente." -f $proc.ProcessName) 'FAIL'
            Write-Log 'Rode este script DENTRO da sessão publicada (no servidor onde o ARIA executa).' 'ATN'
            return $true
        }
        if ($proc) { Write-Log ("Janela do processo '{0}' (PID {1})." -f $proc.ProcessName, $idProc) 'INFO' }
    } catch { }
    return $false
}

# =====================================================================
#  USUÁRIO LOGADO
# =====================================================================

function Get-UsuarioAria {
    param($Janela)

    # 1) Barra de status do ARIA costuma exibir o usuário corrente.
    try {
        $cond = New-Object System.Windows.Automation.PropertyCondition(
            [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
            [System.Windows.Automation.ControlType]::StatusBar)
        $barras = $Janela.FindAll([System.Windows.Automation.TreeScope]::Descendants, $cond)
        foreach ($b in $barras) {
            $txt = Get-NomeSeguro $b
            $filhos = $b.FindAll([System.Windows.Automation.TreeScope]::Descendants,
                [System.Windows.Automation.Condition]::TrueCondition)
            foreach ($f in $filhos) {
                $n = Get-NomeSeguro $f
                if ($n) { $txt = $txt + ' ' + $n }
            }
            if ($txt -match '(?i)(usu[áa]rio|user)\s*:\s*([^\s|;]+)') { return $Matches[2] }
        }
    } catch { }

    # 2) Título da janela: "ARIA ... - [usuario]"
    $titulo = Get-NomeSeguro $Janela
    if ($titulo -match '\[([^\]]+)\]\s*$') { return $Matches[1] }

    # 3) Fallback: usuário Windows da sessão.
    return $env:USERNAME
}

# =====================================================================
#  MODO Inspecionar — despejo da árvore de controles
# =====================================================================

function Get-PadroesSuportados {
    param($Elemento)

    $nomes = @()
    try {
        foreach ($p in $Elemento.GetSupportedPatterns()) {
            $nomes += ($p.ProgrammaticName -replace 'PatternIdentifiers\.Pattern', '')
        }
    } catch { }
    return ($nomes -join ',')
}

function Export-ArvoreUI {
    param($Elemento, [int] $Nivel, [int] $Max, [System.Text.StringBuilder] $Buffer)

    if ($Nivel -gt $Max) { return }

    $indent = ' ' * ($Nivel * 2)
    $ct = Get-ControlTypeNome $Elemento
    $nome = Get-NomeSeguro $Elemento
    $aid = ''; $cls = ''
    try { $aid = $Elemento.Current.AutomationId } catch { }
    try { $cls = $Elemento.Current.ClassName } catch { }
    $pats = Get-PadroesSuportados $Elemento

    [void]$Buffer.AppendLine(('{0}<{1}> Name="{2}" AutomationId="{3}" Class="{4}" Patterns=[{5}]' -f $indent, $ct, $nome, $aid, $cls, $pats))

    $walker = [System.Windows.Automation.TreeWalker]::ControlViewWalker
    $filho = $null
    try { $filho = $walker.GetFirstChild($Elemento) } catch { return }
    while ($null -ne $filho) {
        Export-ArvoreUI -Elemento $filho -Nivel ($Nivel + 1) -Max $Max -Buffer $Buffer
        try { $filho = $walker.GetNextSibling($filho) } catch { break }
    }
}

# =====================================================================
#  LOCALIZAÇÃO DAS TAREFAS
# =====================================================================

function Get-GradeAtividades {
    param($Janela)

    # 1) Seletor explícito, se configurado.
    if ($SELETORES.GradeAutomationId) {
        $c = New-Object System.Windows.Automation.PropertyCondition(
            [System.Windows.Automation.AutomationElement]::AutomationIdProperty, $SELETORES.GradeAutomationId)
        $g = $Janela.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $c)
        if ($g) { return $g }
        Write-Log ("Grade com AutomationId '{0}' não encontrada; caindo na heurística." -f $SELETORES.GradeAutomationId) 'ATN'
    }

    # 2) Heurística: primeira DataGrid/Table/List/Tree que contenha itens.
    $tipos = @(
        [System.Windows.Automation.ControlType]::DataGrid,
        [System.Windows.Automation.ControlType]::Table,
        [System.Windows.Automation.ControlType]::List,
        [System.Windows.Automation.ControlType]::Tree
    )
    foreach ($t in $tipos) {
        $c = New-Object System.Windows.Automation.PropertyCondition(
            [System.Windows.Automation.AutomationElement]::ControlTypeProperty, $t)
        $achados = $Janela.FindAll([System.Windows.Automation.TreeScope]::Descendants, $c)
        foreach ($g in $achados) {
            $itens = $g.FindAll([System.Windows.Automation.TreeScope]::Descendants,
                [System.Windows.Automation.Condition]::TrueCondition)
            if ($itens.Count -gt 0) { return $g }
        }
    }
    return $null
}

# Comprimento máximo de Name aceito como rótulo de tarefa. Acima disso é bloco de
# texto (painel, log, editor) e casaria por acidente.
$MAX_NOME_TAREFA = 200

# Procura, no escopo dado, elementos cujo Name corresponda ao nome da tarefa.
function Find-LinhasTarefa {
    param($Escopo, [string] $NomeTarefa)

    $alvo = Norm $NomeTarefa
    $linhas = @()
    $todos = $Escopo.FindAll([System.Windows.Automation.TreeScope]::Descendants,
        [System.Windows.Automation.Condition]::TrueCondition)

    foreach ($e in $todos) {
        $nome = Get-NomeSeguro $e
        if (-not $nome) { continue }
        if ($nome.Length -gt $MAX_NOME_TAREFA) { continue }

        $n = Norm $nome
        $exato = ($n -eq $alvo)
        if (-not $exato -and -not $n.Contains($alvo)) { continue }

        $ct = Get-ControlTypeNome $e
        $ehLinha = (@('DataItem', 'TreeItem', 'ListItem', 'Custom') -contains $ct)

        # Prioridade: rótulo exato em contêiner de linha > exato > linha > resto.
        $prio = 3
        if ($exato -and $ehLinha) { $prio = 0 }
        elseif ($exato)           { $prio = 1 }
        elseif ($ehLinha)         { $prio = 2 }

        $linhas += [pscustomobject]@{
            Elemento    = $e
            Nome        = $nome
            ControlType = $ct
            Prioridade  = $prio
        }
    }
    # O chamador embrulha em @() — array de 1 item é desembrulhado no retorno.
    return ($linhas | Sort-Object Prioridade)
}

# Testa se o elemento contém algum campo editável (célula de proprietário candidata).
function Test-TemCampoEditavel {
    param($Elemento)

    $filhos = $Elemento.FindAll([System.Windows.Automation.TreeScope]::Descendants,
        [System.Windows.Automation.Condition]::TrueCondition)
    foreach ($f in $filhos) {
        $ct = Get-ControlTypeNome $f
        if (@('ComboBox', 'Edit') -contains $ct) { return $true }
    }
    return $false
}

# Sobe na árvore até achar o contêiner da linha.
#  1) DataItem/TreeItem/ListItem (grade clássica);
#  2) senão, primeiro ancestral que contenha um campo editável (WPF com Pane/Custom);
#  3) senão, o próprio elemento.
function Get-LinhaContainer {
    param($Elemento)

    $walker = [System.Windows.Automation.TreeWalker]::ControlViewWalker

    $ancestrais = @()
    $atual = $Elemento
    for ($i = 0; $i -lt 6 -and $null -ne $atual; $i++) {
        $ct = Get-ControlTypeNome $atual
        if (@('DataItem', 'TreeItem', 'ListItem') -contains $ct) { return $atual }
        $ancestrais += $atual
        try { $atual = $walker.GetParent($atual) } catch { break }
    }

    foreach ($a in $ancestrais) {
        $ctA = Get-ControlTypeNome $a
        if ($ctA -eq 'Window') { break }   # não subir até a janela inteira
        if (Test-TemCampoEditavel $a) { return $a }
    }
    return $Elemento
}

# Dentro da linha, acha a célula/campo de proprietário.
function Get-CampoProprietario {
    param($Linha)

    if ($SELETORES.CampoAutomationId) {
        $c = New-Object System.Windows.Automation.PropertyCondition(
            [System.Windows.Automation.AutomationElement]::AutomationIdProperty, $SELETORES.CampoAutomationId)
        $f = $Linha.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $c)
        if ($f) { return $f }
    }

    $filhos = $Linha.FindAll([System.Windows.Automation.TreeScope]::Descendants,
        [System.Windows.Automation.Condition]::TrueCondition)

    # 1) Casamento por rótulo da célula.
    foreach ($f in $filhos) {
        $nome = Get-NomeSeguro $f
        if (-not $nome) { continue }
        foreach ($alias in $ALIAS_PROPRIETARIO) {
            if ((Norm $nome).Contains((Norm $alias))) { return $f }
        }
    }
    # 2) Primeiro ComboBox/Edit da linha.
    foreach ($f in $filhos) {
        $ct = Get-ControlTypeNome $f
        if (@('ComboBox', 'Edit') -contains $ct) { return $f }
    }
    return $null
}

# =====================================================================
#  ESCRITA
# =====================================================================

function Set-Proprietario {
    param($Campo, [string] $Valor, [switch] $Executar)

    $ct = Get-ControlTypeNome $Campo

    # a) ValuePattern — campo de texto ou combo editável.
    $vp = $null
    try { $vp = $Campo.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern) } catch { }
    if ($vp -and -not $vp.Current.IsReadOnly) {
        if (-not $Executar) { return ("SIMULADO: ValuePattern.SetValue('{0}') em <{1}>" -f $Valor, $ct) }
        $Campo.SetFocus()
        $vp.SetValue($Valor)
        return ("ValuePattern.SetValue('{0}')" -f $Valor)
    }

    # b) ExpandCollapse + SelectionItem — combo de lista fechada.
    $ec = $null
    try { $ec = $Campo.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern) } catch { }
    if ($ec) {
        if (-not $Executar) { return ("SIMULADO: expandir <{0}> e selecionar '{1}'" -f $ct, $Valor) }
        $Campo.SetFocus()
        $ec.Expand()
        Start-Sleep -Milliseconds 300

        $alvo = Norm $Valor
        $itens = $Campo.FindAll([System.Windows.Automation.TreeScope]::Descendants,
            [System.Windows.Automation.Condition]::TrueCondition)
        foreach ($it in $itens) {
            $nome = Get-NomeSeguro $it
            if (-not $nome) { continue }
            if (-not (Norm $nome).Contains($alvo)) { continue }

            $si = $null
            try { $si = $it.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern) } catch { }
            if ($si) { $si.Select(); $ec.Collapse(); return ("SelectionItem.Select('{0}')" -f $nome) }

            $ip = $null
            try { $ip = $it.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern) } catch { }
            if ($ip) { $ip.Invoke(); return ("Invoke('{0}')" -f $nome) }
        }
        $ec.Collapse()
        throw ("Usuário '{0}' não encontrado na lista de proprietários." -f $Valor)
    }

    throw ("Campo <{0}> não expõe ValuePattern nem ExpandCollapsePattern — rode -Modo Inspecionar e preencha CampoAutomationId." -f $ct)
}

function Invoke-BotaoConfirmar {
    param($Janela, [switch] $Executar)

    if (-not $SELETORES.BotaoConfirmarNome) { return }

    $c = New-Object System.Windows.Automation.PropertyCondition(
        [System.Windows.Automation.AutomationElement]::NameProperty, $SELETORES.BotaoConfirmarNome)
    $b = $Janela.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $c)
    if (-not $b) {
        Write-Log ("Botão '{0}' não encontrado." -f $SELETORES.BotaoConfirmarNome) 'ATN'
        return
    }
    if (-not $Executar) {
        Write-Log ("SIMULADO: clicar em '{0}'." -f $SELETORES.BotaoConfirmarNome) 'INFO'
        return
    }
    $b.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
    Write-Log ("Clicado '{0}'." -f $SELETORES.BotaoConfirmarNome) 'OK'
}

# =====================================================================
#  EXECUÇÃO
# =====================================================================

Write-Log '===== ARIA — atribuição de proprietário de tarefas =====' 'INFO'
Write-Log ("Modo: {0} | Log: {1}" -f $Modo, $LogPath) 'INFO'

Initialize-UIA

$janela = Get-JanelaAria -Titulo $TituloJanela -Timeout $TimeoutSeg
if (-not $janela) {
    Write-Log ("Nenhuma janela com '{0}' no título após {1}s. Abra o ARIA no workspace de atividades." -f $TituloJanela, $TimeoutSeg) 'FAIL'
    exit 2
}
Write-Log ("Janela encontrada: '{0}'" -f (Get-NomeSeguro $janela)) 'OK'

if (Test-Citrix -Janela $janela) { exit 3 }

# ---- Modo Inspecionar ------------------------------------------------
if ($Modo -eq 'Inspecionar') {
    if (-not $Saida) { $Saida = Join-Path $env:TEMP 'aria-arvore-ui.txt' }
    $buf = New-Object System.Text.StringBuilder
    [void]$buf.AppendLine(('# Árvore de UI Automation — {0}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm')))
    [void]$buf.AppendLine(('# Janela: {0}' -f (Get-NomeSeguro $janela)))
    [void]$buf.AppendLine('')
    Export-ArvoreUI -Elemento $janela -Nivel 0 -Max $Profundidade -Buffer $buf
    Set-Content -Path $Saida -Value $buf.ToString() -Encoding UTF8
    Write-Log ("Árvore exportada para: {0}" -f $Saida) 'OK'
    Write-Log 'Localize a grade de atividades e o campo de proprietário; preencha $SELETORES no topo do script.' 'ATN'
    exit 0
}

# ---- Proprietário ----------------------------------------------------
if (-not $Usuario) { $Usuario = Get-UsuarioAria -Janela $janela }
Write-Log ("Proprietário a atribuir: '{0}'" -f $Usuario) 'INFO'

$listaTarefas = $TAREFAS_PADRAO
if ($Tarefas) { $listaTarefas = $Tarefas }
Write-Log ("Tarefas-alvo: {0}" -f ($listaTarefas -join ' · ')) 'INFO'

try { $janela.SetFocus() } catch { Write-Log 'Não foi possível focar a janela do ARIA.' 'ATN' }

$escopo = Get-GradeAtividades -Janela $janela
if ($escopo) {
    $aid = ''
    try { $aid = $escopo.Current.AutomationId } catch { }
    Write-Log ("Grade de atividades: <{0}> AutomationId='{1}'" -f (Get-ControlTypeNome $escopo), $aid) 'OK'
} else {
    Write-Log 'Grade de atividades não identificada — buscando as tarefas na janela inteira.' 'ATN'
    $escopo = $janela
}

$executar = ($Modo -eq 'Aplicar')
$ok = 0; $falhas = 0; $naoAchadas = 0

foreach ($tarefa in $listaTarefas) {
    Write-Log ("--- {0} ---" -f $tarefa) 'INFO'

    $achados = @(Find-LinhasTarefa -Escopo $escopo -NomeTarefa $tarefa)
    if ($achados.Count -eq 0) {
        Write-Log ("Tarefa '{0}' não encontrada na tela atual." -f $tarefa) 'ATN'
        $naoAchadas++
        continue
    }
    $rotulo = ($achados[0].Nome -replace '\s+', ' ').Trim()
    if ($rotulo.Length -gt 60) { $rotulo = $rotulo.Substring(0, 60) + '…' }
    Write-Log ("{0} ocorrência(s); usando <{1}> Name='{2}'." -f $achados.Count, $achados[0].ControlType, $rotulo) 'INFO'

    $linha = Get-LinhaContainer -Elemento $achados[0].Elemento
    $campo = Get-CampoProprietario -Linha $linha
    if (-not $campo) {
        Write-Log ("Campo de proprietário não localizado na linha de '{0}'. Rode -Modo Inspecionar e preencha CampoAutomationId." -f $tarefa) 'FAIL'
        $falhas++
        continue
    }

    try {
        $r = Set-Proprietario -Campo $campo -Valor $Usuario -Executar:$executar
        if ($executar) { Write-Log $r 'OK' } else { Write-Log $r 'INFO' }
        $ok++
    } catch {
        Write-Log ("Falha em '{0}': {1}" -f $tarefa, $_.Exception.Message) 'FAIL'
        $falhas++
    }
}

Invoke-BotaoConfirmar -Janela $janela -Executar:$executar

Write-Log '===== RESUMO =====' 'INFO'
$nivelResumo = 'OK'
if ($falhas -gt 0 -or $naoAchadas -gt 0) { $nivelResumo = 'ATN' }
Write-Log ("Atribuídas/simuladas: {0} | Não encontradas: {1} | Falhas: {2}" -f $ok, $naoAchadas, $falhas) $nivelResumo
if (-not $executar) { Write-Log 'Modo SIMULAR — nada foi alterado no ARIA. Use -Modo Aplicar para gravar.' 'ATN' }

if ($falhas -gt 0) { exit 1 }
exit 0
