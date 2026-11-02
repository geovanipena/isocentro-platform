@echo off
rem Roda o PrePlan por fora do Eclipse.
rem
rem   tools\preplan.bat              -> abre a janela de busca de paciente
rem   tools\preplan.bat 123456       -> ja procura por esse Id
rem   tools\preplan.bat --onde       -> so mostra onde a ESAPI sera procurada
rem
rem As DLLs da Varian NAO acompanham o executavel: elas sao licenciadas, e o
rem exe as procura na instalacao da estacao (ver --onde). Para apontar outra:
rem   set PREPLAN_ESAPI=C:\Program Files\Varian\RTM\15.6\esapi\API
rem
rem Numa maquina fora do dominio, a identidade de rede vai por fora:
rem   runas /netonly /user:DOMINIO\usuario "...\tools\preplan.bat"
rem O console do runas fecha sozinho no fim -- por isso o pause la embaixo.

setlocal

set "EXE=%~dp0PrePlan.exe"
if not exist "%EXE%" set "EXE=%~dp0..\PrePlan\bin\x64\Release\PrePlan.exe"

if not exist "%EXE%" (
    echo PrePlan.exe nao encontrado.
    echo Compile antes:  powershell -ExecutionPolicy Bypass -File "%~dp0compilar.ps1"
    echo Ou copie o PrePlan.exe para junto deste .bat.
    pause
    exit /b 1
)

"%EXE%" %*
set CODIGO=%ERRORLEVEL%

echo.
echo PrePlan terminou com codigo %CODIGO%.
echo    0 = montou    1 = cancelado    2 = sessao nao abriu    3 = erro
pause
exit /b %CODIGO%
