# Descobre a configuracao DICOM de um servidor ARIA. SOMENTE LEITURA.
#
# Existe porque a alternativa era eu chutar um caminho de instalacao e mandar
# procurar la - a mesma armadilha do nome de tabela do data warehouse, que
# devolve resposta plausivel e errada. Aqui nada e suposto: pergunta-se ao
# proprio Windows quais servicos existem, que portas eles ouvem e o que os
# arquivos de configuracao dizem.
#
# O QUE ELE NAO FAZ, e e proposital:
#   * nao escreve nada, em lugar nenhum, alem do proprio relatorio;
#   * nao toca no banco do ARIA nem em dado de paciente;
#   * nao altera servico, firewall, registro nem configuracao.
#
# Escrito para PowerShell 5.1 (o que vem no Windows Server): sem operador
# ternario, sem ?? e sem -AsHashtable. Cada bloco tem o seu try: um que falhe
# por falta de permissao nao pode levar o relatorio inteiro junto - o que se
# quer e o mapa do que deu para ver.

param(
    # Pastas extras onde procurar arquivo de configuracao. As tres da Varian ja
    # entram sozinhas; isto e para instalacao fora do padrao.
    [string[]]$Pastas = @(),
    # Onde gravar. Padrao: ao lado deste arquivo.
    [string]$Saida = ""
)

$ErrorActionPreference = "Continue"
$linhas = New-Object System.Collections.ArrayList

function Escrever($texto) {
    if ($null -eq $texto) { $texto = "" }
    Write-Host $texto
    [void]$linhas.Add($texto)
}

function Titulo($texto) {
    Escrever ""
    Escrever "===== $texto ====="
}

# As portas que interessam. 104 e a registrada do DICOM; 51402 e a que o DB
# Daemon da Varian costuma usar; 11112 e a do padrao para outros nos.
# 104 e a registrada do DICOM e 11112 e a do padrao. As outras foram MEDIDAS
# no SRVARIADB em 04/09/2026 - e 51402, que a literatura da como a do DB Daemon
# da Varian, NAO estava ouvindo la. Serve de lembrete: esta lista e pista, e
# quem acha de verdade e a marcacao por processo.
$PORTAS_DICOM = @(104, 106, 11112, 50501, 50502, 50503, 50504, 51402, 51403,
                  51404, 51601, 57345)
$PISTAS = "vms|varian|dicom|dbd|daemon"

Escrever "Descoberta da configuracao DICOM - SOMENTE LEITURA"
Escrever ("Servidor : " + $env:COMPUTERNAME)
Escrever ("Usuario  : " + $env:USERDOMAIN + "\" + $env:USERNAME)
Escrever ("Quando   : " + (Get-Date -Format "dd/MM/yyyy HH:mm:ss"))
Escrever ("PowerShell " + $PSVersionTable.PSVersion.ToString())

# ---------------------------------------------------------------- 1. servicos
Titulo "1. Servicos com Varian/VMS/DICOM no nome"
Escrever "  Filtro largo de proposito: perder o servico certo custa outra ida"
Escrever "  ao servidor, e falso positivo aqui so ocupa linha (fora do servidor"
Escrever "  ele pega qualquer coisa com VMS no nome, e tudo bem)."
Escrever ""
try {
    $servicos = Get-Service -ErrorAction SilentlyContinue | Where-Object {
        ($_.DisplayName -match $PISTAS) -or ($_.Name -match $PISTAS)
    } | Sort-Object DisplayName
    if ($servicos) {
        foreach ($s in $servicos) {
            Escrever ("  [{0,-8}] {1}  ({2})" -f $s.Status, $s.DisplayName, $s.Name)
        }
    } else {
        Escrever "  nenhum servico com Varian/VMS/DICOM no nome."
        Escrever "  (se este e o servidor certo, o nome do servico foge do padrao"
        Escrever "   e vale olhar a lista inteira: Get-Service | Sort DisplayName)"
    }
} catch {
    Escrever ("  NAO deu para listar os servicos: " + $_.Exception.Message)
}

# ------------------------------------------------------------------ 2. portas
Titulo "2. Portas ouvindo, e quem ouve"
Escrever "  E daqui que sai o host:porta do DB Daemon."
Escrever ""
$achouPorta = $false
try {
    # Get-NetTCPConnection existe do Server 2012 em diante. Em maquina mais
    # antiga cai no netstat, que existe em todas - e um relatorio a menos por
    # causa da versao do Windows seria uma ida a mais ao servidor.
    $conns = Get-NetTCPConnection -State Listen -ErrorAction Stop
    $tabela = foreach ($c in $conns) {
        $proc = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
        $nome = "?"
        if ($proc) { $nome = $proc.ProcessName }
        $marca = ""
        if ($PORTAS_DICOM -contains $c.LocalPort) { $marca = "<== porta DICOM conhecida" }
        if ($nome -match $PISTAS) { $marca = "<== processo da Varian" }
        [pscustomobject]@{ Porta = $c.LocalPort; Processo = $nome; Nota = $marca }
    }
    foreach ($t in ($tabela | Sort-Object Porta -Unique)) {
        if ($t.Nota -ne "") { $achouPorta = $true }
        Escrever ("  {0,-7} {1,-28} {2}" -f $t.Porta, $t.Processo, $t.Nota)
    }
} catch {
    Escrever ("  Get-NetTCPConnection nao serviu (" + $_.Exception.Message + ")")
    Escrever "  Caindo no netstat:"
    try {
        $saidaNet = netstat -ano | Select-String "LISTENING"
        foreach ($l in $saidaNet) { Escrever ("  " + $l.ToString().Trim()) }
    } catch {
        Escrever ("  netstat tambem nao deu: " + $_.Exception.Message)
    }
}
if (-not $achouPorta) {
    Escrever ""
    Escrever "  ATENCAO: nenhuma porta bateu com processo da Varian nem com as"
    Escrever "  portas conhecidas (104, 11112, 51402). Ou o servico esta parado,"
    Escrever "  ou o DB Daemon nao mora nesta maquina."
}

# --------------------------------------------------- 2b. onde esses processos moram
Titulo "2b. O executavel de cada processo da Varian que ouve"
Escrever "  Medido no SRVARIADB em 04/09/2026: as portas DICOM sao TODAS do"
Escrever "  mesmo processo (VMS.DICOMServices.ServiceFW.GenericControlledServiceHost),"
Escrever "  e o nome do servico nao diz qual porta e o DB Daemon. Quem diz e a"
Escrever "  configuracao, e ela mora na pasta do executavel - por isso o caminho"
Escrever "  vem antes da procura por arquivo."
Escrever ""
$pastasDoProcesso = @()
try {
    $conns2 = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue
    $pids = $conns2 | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($umPid in $pids) {
        $proc = Get-Process -Id $umPid -ErrorAction SilentlyContinue
        if ($null -eq $proc) { continue }
        if (-not ($proc.ProcessName -match $PISTAS)) { continue }
        $caminho = "(sem permissao para ler o caminho)"
        try {
            if ($proc.Path) { $caminho = $proc.Path }
        } catch {
            $caminho = "(sem permissao para ler o caminho)"
        }
        Escrever ("  {0}" -f $proc.ProcessName)
        Escrever ("      {0}" -f $caminho)
        if ($caminho -like "?:\*") {
            $pasta = Split-Path $caminho -Parent
            if ($pastasDoProcesso -notcontains $pasta) {
                $pastasDoProcesso = $pastasDoProcesso + $pasta
            }
        }
    }
    if ($pastasDoProcesso.Count -eq 0) {
        Escrever "  nenhum caminho legivel - rode como ADMINISTRADOR para ver."
    }
} catch {
    Escrever ("  NAO deu: " + $_.Exception.Message)
}

# ---------------------------------------------------------------- 3. firewall
Titulo "3. Regras de firewall para essas portas"
try {
    $regras = Get-NetFirewallPortFilter -ErrorAction Stop | Where-Object {
        $PORTAS_DICOM -contains $_.LocalPort
    }
    if ($regras) {
        foreach ($r in $regras) {
            $rr = $r | Get-NetFirewallRule -ErrorAction SilentlyContinue
            if ($rr) {
                Escrever ("  porta {0,-7} {1,-8} {2,-8} {3}" -f $r.LocalPort, $rr.Direction, $rr.Action, $rr.DisplayName)
            }
        }
    } else {
        Escrever "  nenhuma regra para 104, 11112 ou 51402."
        Escrever "  (nao quer dizer bloqueado: pode estar liberado por perfil ou por programa)"
    }
} catch {
    Escrever ("  NAO deu para ler o firewall: " + $_.Exception.Message)
}

# ---------------------------------------------------------------- 4. registro
Titulo "4. Registro: chaves da Varian com AE Title ou porta"
$chaves = @("HKLM:\SOFTWARE\Varian", "HKLM:\SOFTWARE\WOW6432Node\Varian")
$achouReg = $false
foreach ($raiz in $chaves) {
    if (-not (Test-Path $raiz)) { continue }
    try {
        $subs = Get-ChildItem $raiz -Recurse -ErrorAction SilentlyContinue
        foreach ($k in $subs) {
            $props = Get-ItemProperty $k.PSPath -ErrorAction SilentlyContinue
            if ($null -eq $props) { continue }
            foreach ($p in $props.PSObject.Properties) {
                if ($p.Name -match "AE|Port|Dicom|Daemon") {
                    $achouReg = $true
                    Escrever ("  {0}" -f $k.Name)
                    Escrever ("      {0} = {1}" -f $p.Name, $p.Value)
                }
            }
        }
    } catch {
        Escrever ("  NAO deu para ler " + $raiz + ": " + $_.Exception.Message)
    }
}
if (-not $achouReg) { Escrever "  nada encontrado no registro." }

# ------------------------------------------------------- 5. arquivos de config
Titulo "5. Arquivos de configuracao com AE Title"
# A pasta do EXECUTAVEL vem primeiro: e onde a configuracao do servico mora, e
# foi a licao da primeira ida ao SRVARIADB - varrer "Program Files\Varian"
# inteiro devolveu quatro linhas de log de MIGRACAO DE BANCO de 2020 e nada
# mais. Achado plausivel e inutil e o que faz perder a viagem seguinte.
$pastas = $pastasDoProcesso + @("C:\ProgramData\Varian",
            "C:\Program Files (x86)\Varian", "C:\Program Files\Varian") + $Pastas
$vistas = 0
foreach ($pasta in $pastas) {
    if (-not (Test-Path $pasta)) {
        Escrever ("  (nao existe: " + $pasta + ")")
        continue
    }
    Escrever ("  procurando em " + $pasta + " ...")
    try {
        $arqs = Get-ChildItem $pasta -Recurse -ErrorAction SilentlyContinue `
                    -Include *.xml, *.ini, *.config, *.txt, *.cfg -File
        # Os .log.xml de migracao do banco falam de AETitle em ALTER TABLE, e
        # foram o unico achado da primeira ida - ruido que parece resposta.
        $arqs = $arqs | Where-Object { $_.Name -notlike "*log*" }
        $hits = $arqs | Select-String -Pattern "AETitle|AE_Title|AeTitle|CalledAE|CallingAE|DicomPort" -ErrorAction SilentlyContinue
        foreach ($h in ($hits | Select-Object -First 60)) {
            $vistas = $vistas + 1
            Escrever ("    " + $h.Path)
            Escrever ("        " + $h.Line.Trim())
        }
    } catch {
        Escrever ("    NAO deu para varrer: " + $_.Exception.Message)
    }
}
if ($vistas -eq 0) {
    Escrever "  nenhuma linha com AE Title nos lugares olhados."
    Escrever "  Se a instalacao esta fora do padrao, rode de novo apontando a"
    Escrever "  pasta:  descobrir_dicom.bat -Pastas D:\Varian"
}

# ------------------------------------------------------------------- fechamento
Titulo "O que fazer com isto"
Escrever "  Tres coisas saem daqui, e sao exatamente as que a sondagem precisa:"
Escrever ""
Escrever "   1. HOST:PORTA  - o nome desta maquina mais a porta do passo 2;"
Escrever "   2. AE do ARIA  - o AE Title do DB Daemon (passos 2b, 4 e 5). Se"
Escrever "      nao aparecer em arquivo nenhum, ele esta no BANCO do ARIA: a"
Escrever "      primeira ida ao SRVARIADB achou, num log de migracao, as"
Escrever "      tabelas [DicomLocation] e [Resource], as duas com coluna"
Escrever "      [AETitle]. E de la que a Varian le a lista de nos DICOM;"
Escrever "   3. AE local    - o da estacao que vai LER. Este NAO se descobre"
Escrever "      lendo: e uma entrada nova na lista de nos DICOM conhecidos do"
Escrever "      ARIA, e cadastra-la e mudanca de configuracao em producao."
Escrever ""
Escrever "  Com 1 e 2 ja da para rodar a sondagem, mesmo sem o 3: a recusa da"
Escrever "  associacao ('called/calling AE title not recognized') e uma BOA"
Escrever "  noticia - quer dizer que se achou o servidor certo e falta so o"
Escrever "  cadastro. Conexao recusada ou timeout, ao contrario, e porta errada."

# ------------------------------------------------------------------- gravacao
if ($Saida -eq "") {
    $quando = Get-Date -Format "yyyyMMdd-HHmmss"
    $Saida = Join-Path $PSScriptRoot ("dicom_servidor_" + $env:COMPUTERNAME + "_" + $quando + ".txt")
}
try {
    # UTF8 para o acento nao virar lixo se o arquivo for lido noutra maquina.
    $linhas | Out-File -FilePath $Saida -Encoding utf8
    Write-Host ""
    Write-Host ("Gravado em " + $Saida)
} catch {
    Write-Host ""
    Write-Host ("NAO DEU PARA GRAVAR em " + $Saida + ": " + $_.Exception.Message)
    Write-Host "O relatorio esta acima, na tela."
}
