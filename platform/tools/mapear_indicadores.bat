@echo off
REM Mapeia no data warehouse o que o Radioteradados (aba de indicadores) precisa:
REM motivo de encerramento do curso, frequencia prescrita, simulacao/consulta
REM como atividades e braquiterapia no ARIA. So catalogos e contagens -- nenhuma
REM linha de paciente.
REM Mesmas armadilhas do mapear_dw.bat -- o runas comeca em outra pasta, monta
REM ambiente limpo sem o .venv, e o console abre em code page 850 -- e a mesma
REM solucao.
REM
REM Uso, de uma maquina FORA do dominio:
REM   runas /netonly /user:CLINICA\geovani.pena "C:\Users\geova\Documents\isocentro\programa\isocentro\tools\mapear_indicadores.bat"

chcp 65001 > nul
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8
REM Data e hora no nome: rodar de novo NAO apaga a saida anterior.
for /f "tokens=1-5 delims=/:. " %%a in ("%date% %time%") do set CARIMBO=%%c%%b%%a-%%d%%e
set SAIDA=%TEMP%\mapear_indicadores_%CARIMBO%.txt

set PY=python
if exist "%CD%\.venv\Scripts\python.exe" set PY=%CD%\.venv\Scripts\python.exe

echo Python: %PY%
echo.
"%PY%" tools\mapear_indicadores.py %* > "%SAIDA%" 2>&1
type "%SAIDA%"

echo.
echo ----------------------------------------------------------------------
echo A saida (longa) esta gravada em:
echo   %SAIDA%
echo ----------------------------------------------------------------------
echo.
pause
