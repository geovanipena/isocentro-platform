@echo off
REM Mapeia as colunas do data warehouse. Mesmas armadilhas do diagnostico_db.bat
REM (runas comeca em outra pasta, monta ambiente limpo sem o .venv, e o console
REM abre em code page 850) — a solucao aqui e a mesma.
REM
REM Uso, de uma maquina FORA do dominio:
REM   runas /netonly /user:CLINICA\geovani.pena "C:\...\isocentro\tools\mapear_dw.bat"
REM
REM Com um paciente real, para conferir o mapeamento:
REM   ... "C:\...\tools\mapear_dw.bat --paciente 9000001CEL"

chcp 65001 > nul
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8
REM Data e hora no nome: rodar de novo NAO apaga a saida anterior.
REM (aconteceu: um teste meu sobrescreveu o resultado bom.)
for /f "tokens=1-5 delims=/:. " %%a in ("%date% %time%") do set CARIMBO=%%c%%b%%a-%%d%%e
set SAIDA=%TEMP%\mapear_dw_%CARIMBO%.txt

set PY=python
if exist "%CD%\.venv\Scripts\python.exe" set PY=%CD%\.venv\Scripts\python.exe

echo Python: %PY%
echo.
"%PY%" tools\mapear_dw.py %* > "%SAIDA%" 2>&1
type "%SAIDA%"

echo.
echo ----------------------------------------------------------------------
echo A saida (longa) esta gravada em:
echo   %SAIDA%
echo ----------------------------------------------------------------------
echo.
pause
