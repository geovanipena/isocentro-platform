@echo off
REM Confere as hipoteses 2 e 3 do Indice de Disponibilidade: se "Servico" e
REM "Calibracao" aparecem SEM paciente vinculado, e quanto tempo cada uma dura.
REM Mesmas armadilhas dos outros .bat -- o runas comeca em outra pasta, monta
REM ambiente limpo sem o .venv, e o console abre em code page 850 -- e a mesma
REM solucao.
REM
REM Uso, de uma maquina FORA do dominio:
REM   runas /netonly /user:CLINICA\geovani.pena "C:\...\isocentro\tools\checar_parada.bat"
REM
REM Se 90 dias nao trouxer nada (manutencao e rara):
REM   ... "C:\...\tools\checar_parada.bat --dias 365"

chcp 65001 > nul
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8
REM Data e hora no nome: rodar de novo NAO apaga a saida anterior.
for /f "tokens=1-5 delims=/:. " %%a in ("%date% %time%") do set CARIMBO=%%c%%b%%a-%%d%%e
set SAIDA=%TEMP%\checar_parada_%CARIMBO%.txt

set PY=python
if exist "%CD%\.venv\Scripts\python.exe" set PY=%CD%\.venv\Scripts\python.exe

echo Python: %PY%
echo.
"%PY%" tools\checar_parada.py %* > "%SAIDA%" 2>&1
type "%SAIDA%"

echo.
echo ----------------------------------------------------------------------
echo A saida (longa) esta gravada em:
echo   %SAIDA%
echo ----------------------------------------------------------------------
echo.
pause
