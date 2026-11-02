@echo off
REM Mapeia as tabelas de TRATAMENTO ENTREGUE (aba Ficha Virtual).
REM Mesmas armadilhas do mapear_dw.bat — o runas comeca em outra pasta, monta
REM ambiente limpo sem o .venv, e o console abre em code page 850 — e a mesma
REM solucao.
REM
REM Uso, de uma maquina FORA do dominio:
REM   runas /netonly /user:CLINICA\geovani.pena "C:\...\isocentro\tools\mapear_tratamento.bat"
REM
REM Com um paciente EM TRATAMENTO (e a amostra que prova qual tabela e a certa):
REM   ... "C:\...\tools\mapear_tratamento.bat --paciente 9000001CEL"
REM
REM Para CONFERIR A LISTA do painel contra o ARIA (roda o tratamento_db de
REM verdade, mede o tempo da funcao inteira e imprime curso a curso) -- e a
REM rodada que destrava o LISTA_VERIFICADA_EM:
REM   ... "C:\...\tools\mapear_tratamento.bat --consulta"

chcp 65001 > nul
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8
REM Data e hora no nome: rodar de novo NAO apaga a saida anterior.
for /f "tokens=1-5 delims=/:. " %%a in ("%date% %time%") do set CARIMBO=%%c%%b%%a-%%d%%e
set SAIDA=%TEMP%\mapear_tratamento_%CARIMBO%.txt

set PY=python
if exist "%CD%\.venv\Scripts\python.exe" set PY=%CD%\.venv\Scripts\python.exe

echo Python: %PY%
echo.
"%PY%" tools\mapear_tratamento.py %* > "%SAIDA%" 2>&1
type "%SAIDA%"

echo.
echo ----------------------------------------------------------------------
echo A saida (longa) esta gravada em:
echo   %SAIDA%
echo ----------------------------------------------------------------------
echo.
pause
