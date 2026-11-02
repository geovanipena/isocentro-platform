@echo off
REM Abre o ISOCENTRO PURO, como a estacao abre: com login, e com o banco
REM que a configuracao do servico aponta (SRVINSIGHT).
REM
REM Fora da rede da clinica o banco nao responde: a Capa cai no espelho e nos
REM relatorios, e a Ficha Virtual fica vazia. Para ver com dado, use:
REM   tools\rodar_com_banco.bat        banco real (identidade de rede)
REM   tools\rodar_com_banco_local.bat  banco gravado, sem rede
REM   tools\servidor_local.bat         demonstracao completa, sem rede

chcp 65001 > nul
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8

set PY=python
if exist "%CD%\.venv\Scripts\python.exe" set PY=%CD%\.venv\Scripts\python.exe

"%PY%" run_gui.py
