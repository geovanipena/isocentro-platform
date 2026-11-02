@echo off
REM Roda o diagnostico do banco a partir de QUALQUER pasta e com o Python certo.
REM
REM Tres armadilhas ja pagas, e cada uma custou uma tentativa:
REM
REM 1. O runas inicia a janela nova em C:\Users\<voce>, nao na pasta do
REM    projeto: o python morria em "arquivo nao encontrado" antes de imprimir
REM    qualquer coisa, e a janela abria e fechava sem deixar rastro.
REM 2. O runas monta um ambiente LIMPO, sem o PATH da sessao — e caia no Python
REM    do sistema, sem pyodbc, dizendo "pyodbc nao instalado" mesmo com ele
REM    instalado no .venv do projeto. Por isso o .venv e escolhido explicitamente.
REM 3. O console do Windows abre em code page 850: a saida em UTF-8 aparecia
REM    como "ÔÇö" e "n├úo". O chcp 65001 resolve a EXIBICAO (o arquivo gravado
REM    sempre esteve correto).
REM
REM Uso, de uma maquina FORA do dominio:
REM   runas /netonly /user:CLINICA\geovani.pena "C:\...\isocentro\tools\diagnostico_db.bat"
REM
REM De uma estacao do dominio, basta dar um duplo clique.

chcp 65001 > nul
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8
REM Data e hora no nome: rodar de novo NAO apaga a saida anterior.
REM (aconteceu: um teste meu sobrescreveu o resultado bom.)
for /f "tokens=1-5 delims=/:. " %%a in ("%date% %time%") do set CARIMBO=%%c%%b%%a-%%d%%e
set SAIDA=%TEMP%\diagnostico_db_%CARIMBO%.txt

set PY=python
if exist "%CD%\.venv\Scripts\python.exe" set PY=%CD%\.venv\Scripts\python.exe

echo Python: %PY%
echo.
"%PY%" tools\diagnostico_db.py %* > "%SAIDA%" 2>&1
type "%SAIDA%"

echo.
echo ----------------------------------------------------------------------
echo A saida acima tambem esta gravada em:
echo   %SAIDA%
echo ----------------------------------------------------------------------
echo.
pause
