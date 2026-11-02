@echo off
REM Pergunta ao variandw que tabelas de ATIVIDADE existem, e quais delas sao de
REM "Documentacao". So leitura, e sem dado de paciente - ver o cabecalho do
REM tools\atividades.py.
REM
REM Uso, de uma maquina FORA do dominio:
REM   runas /netonly /user:CLINICA\geovani.pena "C:\...\isocentro\tools\atividades.bat"
REM
REM Se a janela do runas piscar e fechar, abra um console com a identidade de
REM rede e rode este .bat DENTRO dele - e o caminho que nao depende de aspas:
REM   runas /netonly /user:CLINICA\geovani.pena cmd
REM
REM Mesmas tres armadilhas dos outros .bat (o runas comeca em outra pasta, monta
REM ambiente limpo sem o .venv, e o console abre em code page 850) e a mesma
REM solucao.

chcp 65001 > nul
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8

REM O servidor por variavel de ambiente: esta maquina pode nao ter
REM config_servico.json, e a variavel tem precedencia sobre ele de qualquer
REM forma. Assim perguntar aqui nao mexe na configuracao de nenhuma estacao.
if "%ISOCENTRO_DB_SERVIDOR%%RADIOTERAFICHA_DB_SERVIDOR%%FICHAPY_DB_SERVIDOR%"=="" set ISOCENTRO_DB_SERVIDOR=SRVINSIGHT

REM Se ela estiver definida, o app leria o ARQUIVO gravado em vez do servidor -
REM e o arquivo nao tem tabela de atividade nenhuma, porque o gravador so guarda
REM as consultas que o app ja faz.
set ISOCENTRO_BANCO_LOCAL=

set PY=python
if exist "%CD%\.venv\Scripts\python.exe" set PY=%CD%\.venv\Scripts\python.exe

echo Python  : %PY%
echo Servidor: %ISOCENTRO_DB_SERVIDOR%
echo.
REM Grava tambem em arquivo: o relatorio e longo e o console do runas fecha.
"%PY%" tools\atividades.py -o atividades_achadas.txt %*
echo.
pause
