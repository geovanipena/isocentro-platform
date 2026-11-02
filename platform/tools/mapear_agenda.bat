@echo off
REM Mapeia a AGENDA do ARIA no data warehouse (aba Agenda).
REM Mesmas armadilhas do mapear_dw.bat -- o runas comeca em outra pasta, monta
REM ambiente limpo sem o .venv, e o console abre em code page 850 -- e a mesma
REM solucao.
REM
REM Uso, de uma maquina FORA do dominio:
REM   runas /netonly /user:CLINICA\geovani.pena "C:\...\isocentro\tools\mapear_agenda.bat"
REM
REM Com um DIA util de agenda cheia -- e a amostra que PROVA o mapeamento, e a
REM que se confere contra a agenda do ARIA aberta na mesma data:
REM   ... "C:\...\tools\mapear_agenda.bat --dia 2026-09-23"

chcp 65001 > nul
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8
REM Data e hora no nome: rodar de novo NAO apaga a saida anterior.
for /f "tokens=1-5 delims=/:. " %%a in ("%date% %time%") do set CARIMBO=%%c%%b%%a-%%d%%e
set SAIDA=%TEMP%\mapear_agenda_%CARIMBO%.txt

set PY=python
if exist "%CD%\.venv\Scripts\python.exe" set PY=%CD%\.venv\Scripts\python.exe

echo Python: %PY%
echo.
"%PY%" tools\mapear_agenda.py %* > "%SAIDA%" 2>&1
type "%SAIDA%"

echo.
echo ----------------------------------------------------------------------
echo A saida (longa) esta gravada em:
echo   %SAIDA%
echo ----------------------------------------------------------------------
echo.
pause
