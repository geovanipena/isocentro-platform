@echo off
REM Grava o banco LOCAL: pergunta ao variandw tudo o que o app pergunta sobre os
REM pacientes que ja estao em TCs_Teste, e guarda as respostas num arquivo.
REM Depois disso da para trabalhar sem rede - ver rodar_com_banco_local.bat.
REM
REM Uso, de uma maquina FORA do dominio:
REM   runas /netonly /user:CLINICA\geovani.pena "C:\...\isocentro\tools\gravar_banco.bat"
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
REM forma. Assim gravar aqui nao mexe na configuracao de nenhuma estacao.
if "%ISOCENTRO_DB_SERVIDOR%%RADIOTERAFICHA_DB_SERVIDOR%%FICHAPY_DB_SERVIDOR%"=="" set ISOCENTRO_DB_SERVIDOR=SRVINSIGHT

REM Se ela estiver definida, o app leria o ARQUIVO em vez do servidor - e a
REM gravacao gravaria o proprio arquivo em cima de si mesmo.
set ISOCENTRO_BANCO_LOCAL=

REM O painel "em tratamento" ainda esta atras do portao experimental. Sem isto
REM o em_tratamento devolve None sem consultar nada, e a gravacao sairia sem a
REM lista - para so se descobrir isso na hora de usar, offline. (O proprio .py
REM tambem liga, com setdefault; aqui e para quem le o .bat saber.)
set ISOCENTRO_LISTA_EXPERIMENTAL=1

set PY=python
if exist "%CD%\.venv\Scripts\python.exe" set PY=%CD%\.venv\Scripts\python.exe

echo Python  : %PY%
echo Servidor: %ISOCENTRO_DB_SERVIDOR%
echo.
"%PY%" tools\gravar_banco.py %*
echo.
pause
