# Mede uma ESTACAO da clinica sem instalar nada. SOMENTE LEITURA.
#
# Existe porque a estacao clinica nao aceita .exe nem .bat, e e justamente ela
# que precisa ser medida: o CheckupClinica.exe roda no clinica-python01, que
# esta na MESMA VLAN do ARIA (192.0.2.x) - o pacote dele nao atravessa
# roteamento nenhum entre VLANs, e a travessia e o que o app vai enfrentar.
#
# O QUE ELE RESPONDE, e cada resposta manda ligar para uma pessoa diferente:
#   1. esta estacao ALCANCA o ARIA e o banco? (rota, firewall entre VLANs)
#   2. o AE Title desta estacao e ACEITO? (cadastro no ARIA)
#   3. a conta REDE consegue LER o variandw do CLINICA? (relacao de
#      confianca entre dominios - a pergunta nova, e a maior)
#   4. o que falta NA MAQUINA: driver ODBC, porta livre, firewall, impressora
#
# O C-ECHO E MONTADO A MAO, byte a byte. Nao ha pynetdicom aqui, e nao havera:
# instalar Python numa estacao clinica e mudanca em producao. O que se monta e
# o A-ASSOCIATE-RQ do DICOM (PS3.8), e a resposta ja separa as tres coisas que
# o telefone confunde - "nao chega", "chega e recusa o nosso AE", "chega e
# recusa o AE do ARIA".
#
# O QUE ELE NAO FAZ, e e proposital: nao escreve nada alem do proprio
# relatorio e de um arquivo de teste que ele mesmo apaga, nao altera firewall,
# registro, servico nem configuracao, e nao traz dado de paciente nenhum - o
# C-ECHO nao pede imagem, so pergunta se o servidor esta la.
#
# Escrito para PowerShell 5.1: sem operador ternario, sem ?? e sem
# -AsHashtable. Cada bloco tem o seu try - um que falhe por falta de permissao
# nao pode levar o relatorio inteiro junto.
#
# SE .PS1 FOR BLOQUEADO NESTA ESTACAO, os tres degraus que mais importam saem
# colados no prompt, um de cada vez - ver docs\ROTEIRO_DA_IDA.md.

param(
    [string]$Servidor = "192.0.2.9",
    [int]$Porta = 51405,
    [string]$AeRemoto = "isocentro",
    [string]$AeLocal = "RADIOTERAFICHA",
    [string]$Banco = "SRVINSIGHT",
    [int]$PortaBanco = 1433,
    [int]$PortaEscuta = 104,
    # Pasta compartilhada do app, para o teste de escrita. Vazio: nao testa.
    [string]$Share = "",
    [string]$Saida = ""
)

$ErrorActionPreference = "Continue"
$linhas = New-Object System.Collections.ArrayList
$pedidos = New-Object System.Collections.ArrayList

function Escrever($texto) {
    if ($null -eq $texto) { $texto = "" }
    Write-Host $texto
    [void]$linhas.Add($texto)
}

function Titulo($n, $texto) {
    Escrever ""
    Escrever ("===== " + $n + ". " + $texto + " " + ("=" * 20))
}

function Medir($rotulo, $estado, $detalhe) {
    $marca = $estado.PadLeft(3).PadRight(5)
    Escrever ("  [" + $marca + "] " + $rotulo.PadRight(32) + " " + $detalhe)
}

function Pedir($texto) {
    [void]$pedidos.Add($texto)
}

# ---------------------------------------------------------------- 1. quem sou
Titulo 1 "Quem sou eu, e de onde estou falando"
Escrever ("  Data: " + (Get-Date -Format "dd/MM/yyyy HH:mm:ss"))
Medir "maquina" "ok" $env:COMPUTERNAME
Medir "conta do Windows" "ok" ($env:USERDOMAIN + "\" + $env:USERNAME)
Medir "dominio DNS" "ok" $env:USERDNSDOMAIN

# O IP DE SAIDA, e nao "o IP da maquina": estacao com VPN ou segunda placa tem
# varios, e para o ARIA sai um so. E este o numero que a TI cadastra.
$ipSaida = ""
try {
    $rota = Find-NetRoute -RemoteIPAddress $Servidor -ErrorAction Stop
    $ipSaida = $rota[0].IPAddress
} catch {
    try {
        $s = New-Object System.Net.Sockets.Socket("InterNetwork", "Dgram", "Udp")
        $s.Connect($Servidor, 80)
        $ipSaida = $s.LocalEndPoint.Address.ToString()
        $s.Close()
    } catch { $ipSaida = "" }
}
if ($ipSaida -ne "") {
    Medir "IP de saida para o ARIA" "ok" ($ipSaida + " -> falando com " + $Servidor)
} else {
    Medir "IP de saida para o ARIA" "AVISO" "nao deu para determinar"
}

try {
    $perfis = (Get-NetConnectionProfile -ErrorAction Stop |
               Select-Object -ExpandProperty NetworkCategory) -join ", "
    if ($perfis -match "Public") {
        Medir "perfil da rede" "AVISO" ($perfis + " - regra de entrada de outro perfil nao vale")
    } else {
        Medir "perfil da rede" "ok" $perfis
    }
} catch { Medir "perfil da rede" "AVISO" "nao respondeu" }

# ------------------------------------------------------------- 2. alcance
Titulo 2 "A estacao ALCANCA o ARIA e o banco?"

function Testar-Porta($alvo, $porta, $rotulo) {
    $cliente = New-Object System.Net.Sockets.TcpClient
    $inicio = Get-Date
    try {
        $tarefa = $cliente.BeginConnect($alvo, $porta, $null, $null)
        $ok = $tarefa.AsyncWaitHandle.WaitOne(4000, $false)
        if ($ok -and $cliente.Connected) {
            $gasto = ((Get-Date) - $inicio).TotalSeconds
            $cliente.EndConnect($tarefa)
            Medir $rotulo "ok" ("aberta em " + $gasto.ToString("0.00") + " s")
            return $true
        }
        # Espera ate o prazo e recusa imediata sao causas DIFERENTES: a
        # primeira e pacote sumindo (firewall entre VLANs), a segunda e o
        # sistema do outro lado dizendo que nao ha nada nessa porta.
        $gasto = ((Get-Date) - $inicio).TotalSeconds
        if ($gasto -ge 3.5) {
            Medir $rotulo "FALHA" ("sem resposta em " + $gasto.ToString("0.0") + " s - assinatura de FIREWALL")
        } else {
            Medir $rotulo "FALHA" "recusada na hora - nao ha servico nessa porta"
        }
        return $false
    } catch {
        Medir $rotulo "FALHA" $_.Exception.Message
        return $false
    } finally { $cliente.Close() }
}

$alcancaAria = Testar-Porta $Servidor $Porta ("ARIA " + $Servidor + ":" + $Porta)
if (-not $alcancaAria) {
    Pedir ("esta estacao (" + $ipSaida + ") nao alcanca " + $Servidor + ":" + $Porta +
           " - liberar a saida TCP dessa porta da VLAN da estacao para a do ARIA")
}
$alcancaBanco = Testar-Porta $Banco $PortaBanco ("banco " + $Banco + ":" + $PortaBanco)
if (-not $alcancaBanco) {
    Pedir ("esta estacao nao alcanca " + $Banco + ":" + $PortaBanco +
           " - liberar a saida TCP 1433 para o data warehouse")
}

# --------------------------------------------------------------- 3. C-ECHO
Titulo 3 "O AE Title desta estacao e ACEITO? (C-ECHO)"

function Bytes-AE($nome) {
    # AE Title tem 16 bytes, preenchidos com ESPACO (nao com zero) - PS3.8.
    $texto = $nome.PadRight(16).Substring(0, 16)
    return [System.Text.Encoding]::ASCII.GetBytes($texto)
}

function Bytes-UID($uid) {
    return [System.Text.Encoding]::ASCII.GetBytes($uid)
}

function Item-Curto($tipo, $conteudo) {
    # Item de PDU: tipo(1) + reservado(1) + tamanho(2, BIG endian) + conteudo.
    # BIG endian e o ponto: o resto do DICOM e little, e os PDUs da camada de
    # associacao sao big. Trocar os dois e o erro classico aqui, e ele produz
    # um "tamanho absurdo" que o servidor derruba sem explicar.
    $tam = [System.BitConverter]::GetBytes([uint16]$conteudo.Length)
    [array]::Reverse($tam)
    return @($tipo, 0x00) + $tam + $conteudo
}

function Montar-Associacao($chamado, $chamador) {
    $appCtx = Item-Curto 0x10 (Bytes-UID "1.2.840.10008.3.1.1.1")

    # Um contexto de apresentacao so: Verification, em Implicit VR LE.
    $abstrato = Item-Curto 0x30 (Bytes-UID "1.2.840.10008.1.1")
    $transfer = Item-Curto 0x40 (Bytes-UID "1.2.840.10008.1.2")
    $corpoPC = @(0x01, 0x00, 0x00, 0x00) + $abstrato + $transfer
    $presCtx = Item-Curto 0x20 $corpoPC

    $maxLen = @(0x51, 0x00, 0x00, 0x04, 0x00, 0x00, 0x40, 0x00)
    $implUID = Item-Curto 0x52 (Bytes-UID "1.2.826.0.1.3680043.9.7460.1")
    $implNome = Item-Curto 0x55 ([System.Text.Encoding]::ASCII.GetBytes("RTFICHA_PS1"))
    $userInfo = Item-Curto 0x50 ($maxLen + $implUID + $implNome)

    $variavel = $appCtx + $presCtx + $userInfo
    $fixo = @(0x00, 0x01, 0x00, 0x00) + (Bytes-AE $chamado) + (Bytes-AE $chamador) +
            (New-Object byte[] 32)
    $corpo = $fixo + $variavel

    $tam = [System.BitConverter]::GetBytes([uint32]$corpo.Length)
    [array]::Reverse($tam)
    return [byte[]](@(0x01, 0x00) + $tam + $corpo)
}

function Ler-PDU($fluxo) {
    $cabeca = New-Object byte[] 6
    $lidos = 0
    while ($lidos -lt 6) {
        $n = $fluxo.Read($cabeca, $lidos, 6 - $lidos)
        if ($n -le 0) { return $null }
        $lidos += $n
    }
    $tamBytes = $cabeca[2..5]
    [array]::Reverse($tamBytes)
    $tam = [System.BitConverter]::ToUInt32($tamBytes, 0)
    $corpo = New-Object byte[] $tam
    $lidos = 0
    while ($lidos -lt $tam) {
        $n = $fluxo.Read($corpo, $lidos, $tam - $lidos)
        if ($n -le 0) { break }
        $lidos += $n
    }
    return @{ Tipo = $cabeca[0]; Corpo = $corpo }
}

function Motivo-Da-Recusa($corpo) {
    # PS3.8: reservado(1), resultado(1), origem(1), motivo(1). A ORIGEM e o que
    # decide de quem e o problema, e por isso ela sai por extenso: "calling"
    # e o NOSSO AE (so a Varian/TI cadastra) e "called" e o do ARIA (erro de
    # parametro nosso, resolve-se aqui). Confundir os dois abre chamado para
    # consertar o que estava na propria mao.
    if ($corpo.Length -lt 4) { return "recusa sem corpo legivel" }
    $origem = $corpo[2]
    $motivo = $corpo[3]
    if ($origem -eq 1) {
        switch ($motivo) {
            1 { return "recusada pelo servico - nenhum motivo declarado" }
            2 { return "contexto de aplicacao nao suportado" }
            3 { return "CALLING AE nao reconhecido - o NOSSO AE ('" + $AeLocal + "') nao esta cadastrado no ARIA" }
            7 { return "CALLED AE nao reconhecido - o nome do ARIA ('" + $AeRemoto + "') esta errado do nosso lado" }
            default { return ("recusada pelo servico, motivo " + $motivo) }
        }
    }
    if ($origem -eq 2) { return "recusada pela camada ACSE, motivo " + $motivo }
    if ($origem -eq 3) {
        if ($motivo -eq 1) { return "congestionamento temporario - tentar de novo" }
        if ($motivo -eq 2) { return "limite local de associacoes excedido" }
    }
    return ("recusada (origem " + $origem + ", motivo " + $motivo + ")")
}

function Montar-CEcho() {
    # Command set do C-ECHO-RQ em Implicit VR Little Endian. Aqui o endian
    # inverte: os PDUs sao big, o conteudo DICOM e little.
    function Elem($grupo, $elemento, $valor) {
        $g = [System.BitConverter]::GetBytes([uint16]$grupo)
        $e = [System.BitConverter]::GetBytes([uint16]$elemento)
        $t = [System.BitConverter]::GetBytes([uint32]$valor.Length)
        return $g + $e + $t + $valor
    }
    $sop = [System.Text.Encoding]::ASCII.GetBytes("1.2.840.10008.1.1")
    $sop = $sop + @([byte]0)          # UID de tamanho impar leva pad de NULL
    $corpo = (Elem 0x0000 0x0002 $sop) +
             (Elem 0x0000 0x0100 ([System.BitConverter]::GetBytes([uint16]0x0030))) +
             (Elem 0x0000 0x0110 ([System.BitConverter]::GetBytes([uint16]0x0001))) +
             (Elem 0x0000 0x0800 ([System.BitConverter]::GetBytes([uint16]0x0101)))
    $tamanho = Elem 0x0000 0x0000 ([System.BitConverter]::GetBytes([uint32]$corpo.Length))
    $comando = $tamanho + $corpo

    # PDV: tamanho(4, big) + id do contexto(1) + cabecalho de controle(1) + dados
    $pdv = @([byte]0x01, [byte]0x03) + $comando
    $tamPdv = [System.BitConverter]::GetBytes([uint32]$pdv.Length)
    [array]::Reverse($tamPdv)
    $corpoPData = $tamPdv + $pdv
    $tamPdu = [System.BitConverter]::GetBytes([uint32]$corpoPData.Length)
    [array]::Reverse($tamPdu)
    return [byte[]](@(0x04, 0x00) + $tamPdu + $corpoPData)
}

$associou = $false
if ($alcancaAria) {
    $cliente = New-Object System.Net.Sockets.TcpClient
    try {
        $cliente.Connect($Servidor, $Porta)
        $fluxo = $cliente.GetStream()
        $fluxo.ReadTimeout = 15000
        $pedido = Montar-Associacao $AeRemoto $AeLocal
        $fluxo.Write($pedido, 0, $pedido.Length)
        $resposta = Ler-PDU $fluxo

        if ($null -eq $resposta) {
            Medir "associacao" "FALHA" "a porta abriu e nao respondeu DICOM - endereco ou porta errados"
        } elseif ($resposta.Tipo -eq 0x02) {
            $associou = $true
            Medir "associacao" "ok" ("ACEITA como '" + $AeLocal + "' de " + $ipSaida)
            # O C-ECHO propriamente: a associacao aceita ja prova o cadastro,
            # e isto prova que o SERVICO responde, nao so a camada de baixo.
            try {
                $echo = Montar-CEcho
                $fluxo.Write($echo, 0, $echo.Length)
                $rsp = Ler-PDU $fluxo
                $texto = ""
                if ($null -ne $rsp -and $rsp.Tipo -eq 0x04) {
                    # Procura a tag (0000,0900) - Status - com valor 0x0000.
                    for ($i = 0; $i -lt $rsp.Corpo.Length - 9; $i++) {
                        if ($rsp.Corpo[$i] -eq 0 -and $rsp.Corpo[$i+1] -eq 0 -and
                            $rsp.Corpo[$i+2] -eq 0 -and $rsp.Corpo[$i+3] -eq 9) {
                            if ($rsp.Corpo[$i+8] -eq 0 -and $rsp.Corpo[$i+9] -eq 0) {
                                $texto = "status 0x0000 - o servico respondeu"
                            } else {
                                $texto = "status diferente de zero"
                            }
                            break
                        }
                    }
                }
                if ($texto -eq "") { $texto = "associacao aceita; resposta do C-ECHO nao confirmada" }
                Medir "C-ECHO" "ok" $texto
            } catch {
                Medir "C-ECHO" "AVISO" ("associacao aceita, C-ECHO falhou: " + $_.Exception.Message)
            }
            # A-RELEASE-RQ: fechar direito, para nao deixar associacao pendurada.
            try {
                $rel = [byte[]](@(0x05, 0x00, 0x00, 0x00, 0x00, 0x04, 0x00, 0x00, 0x00, 0x00))
                $fluxo.Write($rel, 0, $rel.Length)
            } catch { }
        } elseif ($resposta.Tipo -eq 0x03) {
            $motivo = Motivo-Da-Recusa $resposta.Corpo
            Medir "associacao" "FALHA" ("RECUSADA - " + $motivo)
            if ($motivo -match "CALLING") {
                Pedir ("cadastrar o AE Title chamador '" + $AeLocal + "' para esta estacao (" +
                       $ipSaida + ") - ele JA funciona de outras maquinas, entao o cadastro amarrou endereco")
            }
        } else {
            Medir "associacao" "FALHA" ("resposta inesperada, PDU tipo " + $resposta.Tipo)
        }
    } catch {
        Medir "associacao" "FALHA" $_.Exception.Message
    } finally { $cliente.Close() }
} else {
    Medir "associacao" "--" "nao tentada: a porta nao abriu (bloco 2)"
}

# ------------------------------------------------------- 4. banco e dominio
Titulo 4 "A conta deste dominio LE o data warehouse?"
if ($alcancaBanco) {
    # System.Data.SqlClient com Integrated Security: e a MESMA autenticacao que
    # o app usa (Trusted_Connection), e nao precisa de sqlcmd nem de driver
    # ODBC. E o unico jeito de responder, sem instalar nada, a pergunta que
    # nenhuma medida respondeu ate hoje: a conta REDE consegue provar
    # quem e para um SQL do CLINICA?
    try {
        $cx = New-Object System.Data.SqlClient.SqlConnection
        $cx.ConnectionString = ("Server=" + $Banco + "," + $PortaBanco +
                                ";Database=variandw;Integrated Security=SSPI;" +
                                "Connect Timeout=10;Application Name=ISOCENTRO (sonda)")
        $cx.Open()
        $cmd = $cx.CreateCommand()
        $cmd.CommandText = "SELECT SUSER_SNAME(), DB_NAME()"
        $ler = $cmd.ExecuteReader()
        if ($ler.Read()) {
            Medir "autenticacao integrada" "ok" ("o servidor me ve como " + $ler.GetString(0) +
                                                 ", em " + $ler.GetString(1))
        }
        $ler.Close()
        # O inventario COMPLETO, e nao duas tabelas de amostra. Medido em
        # 10/09/2026: a autenticacao entre dominios funciona, entao o que ainda
        # nao se sabe e QUAIS tabelas a conta enxerga - e permissao de banco
        # costuma vir pela metade. As tres ultimas sao as que bloqueiam as duas
        # frentes paradas desde 19/08/2026: sem elas, nenhuma linha do SQL da
        # aba Ficha Virtual deve ser escrita, porque consulta que nao roda e
        # consulta que ninguem conferiu.
        $tabelas = @("DWH.DimPatient", "DWH.DimCourse", "DWH.DimPlan",
                     "DWH.DimPrescription", "DWH.FactPatientPrescription",
                     "DWH.FactPatientDiagnosis", "DWH.DimPatientPhoto",
                     "DWH.FactTreatmentHistory", "DWH.DimMachine",
                     "DWH.DimActivity")
        foreach ($tabela in $tabelas) {
            try {
                $c2 = $cx.CreateCommand()
                $c2.CommandText = "SELECT TOP 1 1 FROM " + $tabela
                [void]$c2.ExecuteScalar()
                Medir $tabela "ok" "le"
            } catch {
                Medir $tabela "FALHA" $_.Exception.Message
                Pedir ("dar SELECT em " + $tabela + " para a conta/grupo desta estacao")
            }
        }
        $cx.Close()
    } catch {
        $msg = $_.Exception.Message
        Medir "autenticacao integrada" "FALHA" $msg
        if ($msg -match "18452|untrusted|nao confiavel|not associated") {
            Escrever "          ISTO E A PERGUNTA DOS DOIS DOMINIOS, e a resposta e nao."
            Escrever "          A estacao autentica num dominio e o SQL esta noutro; sem"
            Escrever "          relacao de confianca o servidor recusa ANTES de olhar"
            Escrever "          permissao. Nao e senha errada, e identidade."
            Pedir ("estabelecer relacao de confianca entre o dominio da estacao (" +
                   $env:USERDOMAIN + ") e o do SQL, ou dar outro caminho de autenticacao " +
                   "para o variandw - hoje a estacao nao consegue provar quem e")
        } elseif ($msg -match "Login failed|Falha de logon") {
            Pedir ("liberar LEITURA no variandw para a conta/grupo do dominio " + $env:USERDOMAIN)
        }
    }
} else {
    Medir "autenticacao integrada" "--" "nao tentada: a porta 1433 nao abriu"
}

# ----------------------------------------------------------- 5. a maquina
Titulo 5 "O que falta NESTA maquina"

# O DRIVER ODBC e o degrau que o teste do banco NAO cobre, e e preciso dizer
# isso: System.Data.SqlClient e .NET e nao passa por ODBC nenhum. Medido em
# 10/09/2026 nesta estacao - a autenticacao integrada funcionou pelo SqlClient,
# e o app conecta por pyodbc. Sem driver, ele nao conecta apesar de a
# identidade e a rota estarem provadas: o pior tipo de "esta tudo certo".
try {
    $odbc = Get-ItemProperty "HKLM:\SOFTWARE\ODBC\ODBCINST.INI\ODBC Drivers" -ErrorAction Stop
    $nomes = ($odbc.PSObject.Properties | Where-Object { $_.Name -notmatch "^PS" } |
              Select-Object -ExpandProperty Name) -join ", "
    if ($nomes -match "ODBC Driver 1[78] for SQL Server") {
        Medir "driver ODBC" "ok" $nomes
    } elseif ($nomes -match "SQL Server") {
        Medir "driver ODBC" "AVISO" ("so o antigo: " + $nomes)
        Pedir "instalar o ODBC Driver 18 for SQL Server - o app funciona com o antigo, que e depreciado"
    } else {
        Medir "driver ODBC" "FALHA" ("nenhum de SQL Server: " + $nomes)
        Pedir "instalar o ODBC Driver 18 for SQL Server nesta estacao"
    }
} catch { Medir "driver ODBC" "AVISO" "nao deu para ler o registro" }

try {
    $ouvinte = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Any, $PortaEscuta)
    $ouvinte.Start()
    $ouvinte.Stop()
    Medir ("porta " + $PortaEscuta + " livre para ouvir") "ok" "o bind passou"
} catch {
    Medir ("porta " + $PortaEscuta + " livre para ouvir") "FALHA" $_.Exception.Message
    Pedir ("a porta " + $PortaEscuta + " esta ocupada nesta maquina - escolher outra para o receptor DICOM")
}

try {
    $bloqueios = Get-NetFirewallRule -Direction Inbound -Enabled True -Action Block -ErrorAction Stop |
                 Where-Object { $_.DisplayName -match "python|radiotera|ficha" } |
                 Select-Object -First 5 -ExpandProperty DisplayName
    if ($bloqueios) {
        Medir "regras que BLOQUEIAM entrada" "AVISO" ($bloqueios -join ", ")
        Escrever "          Regra de BLOQUEIO vence regra de permissao no Windows."
    } else {
        Medir "regras que BLOQUEIAM entrada" "ok" "nenhuma para nos"
    }
} catch { Medir "regras que BLOQUEIAM entrada" "AVISO" "nao deu para ler o firewall" }

try {
    $impressoras = (Get-Printer -ErrorAction Stop | Select-Object -ExpandProperty Name) -join ", "
    if ($impressoras) { Medir "impressoras" "ok" $impressoras }
    else { Medir "impressoras" "AVISO" "nenhuma - a ficha nao sai desta estacao" }
} catch { Medir "impressoras" "AVISO" "nao respondeu" }

if ($Share -ne "") {
    # Criar arquivo e SUBSTITUIR arquivo sao permissoes diferentes em SMB, e o
    # app sempre substitui: grava num temporario ao lado e troca, para que uma
    # estacao desligada no meio nao deixe o indice pela metade.
    $alvo = Join-Path $Share ".sonda_isocentro.json"
    $tmp = $alvo + ".tmp"
    try {
        Set-Content -Path $alvo -Value "{}" -Encoding utf8 -ErrorAction Stop
        Set-Content -Path $tmp -Value "{}" -Encoding utf8 -ErrorAction Stop
        [System.IO.File]::Replace($tmp, $alvo, $null)
        Remove-Item $alvo -Force -ErrorAction SilentlyContinue
        Medir "share: escreve e substitui" "ok" $Share
    } catch {
        Medir "share: escreve e substitui" "FALHA" $_.Exception.Message
        Pedir ("em " + $Share + ", a conta precisa poder CRIAR e APAGAR arquivo, nao so criar")
        Remove-Item $tmp -Force -ErrorAction SilentlyContinue
        Remove-Item $alvo -Force -ErrorAction SilentlyContinue
    }
} else {
    Medir "share do app" "--" "nao testado: passe -Share \\servidor\pasta"
}

# ------------------------------------------------------------- 6. o pedido
Titulo 6 "O que falta - copiar daqui para o chamado"
if ($pedidos.Count -eq 0) {
    Escrever ""
    Escrever "  Nada a pedir: o que foi medido nesta estacao passou."
    if ($associou) {
        Escrever "  E o principal esta provado: esta estacao ALCANCA o ARIA e o AE"
        Escrever "  Title dela e aceito. E o caminho que o app vai percorrer."
    }
} else {
    Escrever ""
    for ($i = 0; $i -lt $pedidos.Count; $i++) {
        Escrever ("   " + ($i + 1) + ". " + $pedidos[$i])
    }
}

Escrever ""
Escrever ("=" * 60)
Escrever ("  Estacao " + $env:COMPUTERNAME + " (" + $ipSaida + "), dominio " + $env:USERDOMAIN)
Escrever ("=" * 60)

if ($Saida -eq "") {
    $Saida = Join-Path ([Environment]::GetFolderPath("Desktop")) `
             ("sonda_estacao_" + $env:COMPUTERNAME + "_" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".txt")
}
try {
    $linhas | Out-File -FilePath $Saida -Encoding utf8
    Write-Host ""
    Write-Host ("Gravado em " + $Saida)
} catch {
    Write-Host ""
    Write-Host ("NAO DEU PARA GRAVAR em " + $Saida + ": " + $_.Exception.Message)
    Write-Host "O relatorio esta acima, na tela."
}
