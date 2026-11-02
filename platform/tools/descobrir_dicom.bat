@echo off
REM Descobre a configuracao DICOM de um servidor ARIA e grava num .txt.
REM SOMENTE LEITURA - ver o cabecalho do descobrir_dicom.ps1.
REM
REM PARA RODAR NO SERVIDOR (srvariadb):
REM   1. copie ESTES DOIS arquivos para uma pasta qualquer do servidor:
REM        descobrir_dicom.bat
REM        descobrir_dicom.ps1
REM      (o .bat sozinho nao faz nada - o trabalho esta no .ps1 ao lado)
REM   2. clique com o botao direito no .bat e "Executar como administrador";
REM   3. traga de volta o dicom_servidor_<MAQUINA>_<data>.txt que aparecer na
REM      mesma pasta.
REM
REM Sem Python, sem instalar nada: so o PowerShell que ja vem no Windows.
REM Escrito para a versao 5.1, que e a do Windows Server.
REM
REM O QUE ELE NAO FAZ, e e proposital: nao escreve em lugar nenhum alem do
REM proprio relatorio, nao toca no banco do ARIA nem em dado de paciente, e nao
REM altera servico, firewall, registro nem configuracao. Um bloco que falhe por
REM falta de permissao nao derruba os outros.
REM
REM SEM ADMINISTRADOR ele roda assim mesmo, e os blocos que precisarem de
REM privilegio saem com o motivo escrito - meio relatorio vale mais que
REM nenhum, e diz o que refazer.
REM
REM Instalacao fora do padrao (Varian noutro disco):
REM   descobrir_dicom.bat -Pastas D:\Varian
REM
REM O -ExecutionPolicy Bypass vale so para ESTA execucao: nao muda a politica
REM da maquina. Sem ele, servidor com script bloqueado recusaria o .ps1 e a
REM ida ao servidor se perderia por causa de uma linha.

chcp 65001 > nul
echo.
echo  Descoberta da configuracao DICOM - SOMENTE LEITURA
echo  Nada e alterado nesta maquina.
echo.

REM O .ps1 e procurado pelo nome DO PROPRIO .BAT (%~dpn0), nao por um nome
REM fixo. Motivo medido em 04/09/2026: baixados pelo navegador com o par ja
REM existente na pasta, os dois viraram "descobrir_dicom 1.bat" e
REM "descobrir_dicom 1.ps1" - e o .bat procurava "descobrir_dicom.ps1", que
REM nao existia mais. A ida ao servidor se perdeu num acento de nome.
set PS1=%~dpn0.ps1
if not exist "%PS1%" set PS1=%~dp0descobrir_dicom.ps1
if not exist "%PS1%" goto :faltou

powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%" %*
goto :fim

:faltou
echo.
echo  NAO ACHEI o .ps1, que e onde mora o trabalho.
echo.
echo  Procurei por:
echo    %~dpn0.ps1
echo    %~dp0descobrir_dicom.ps1
echo.
echo  Os DOIS arquivos precisam estar na mesma pasta e com o MESMO nome antes
echo  da extensao. Se o navegador renomeou um deles (o classico " (1)" no
echo  fim), renomeie os dois igual - ou apague e baixe de novo.

:fim

echo.
pause
