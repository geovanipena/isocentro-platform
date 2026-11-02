@echo off
REM ============================================================================
REM  A conexao volta sozinha depois de cair?
REM
REM  Nao e o diagnostico ("por que nao conecta", em camadas) - e o teste da
REM  RECUPERACAO: derruba a conexao de proposito e confere que o app volta sem
REM  ninguem entrar como admin.
REM
REM  Numa maquina FORA DO DOMINIO, abra o console com a identidade de rede e
REM  rode este .bat DENTRO dele:
REM     runas /netonly /user:CLINICA\geovani.pena cmd
REM     cd /d C:\Users\geova\Documents\isocentro\programa\isocentro
REM     tools\testar_reconexao.bat
REM
REM  As mesmas tres armadilhas dos outros .bat, e a mesma solucao: o runas
REM  comeca em outra pasta, monta ambiente limpo sem o .venv, e o console abre
REM  em code page 850.
REM ============================================================================

chcp 65001 > nul
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8

REM Por variavel de ambiente, que tem precedencia sobre o config_servico.json:
REM testar aqui nao mexe na configuracao de estacao nenhuma.
if "%ISOCENTRO_DB_SERVIDOR%%RADIOTERAFICHA_DB_SERVIDOR%%FICHAPY_DB_SERVIDOR%"=="" set ISOCENTRO_DB_SERVIDOR=SRVINSIGHT

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" tools\testar_reconexao.py
) else (
    python tools\testar_reconexao.py
)

echo.
pause
