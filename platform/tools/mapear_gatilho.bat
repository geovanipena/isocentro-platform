@echo off
REM Pergunta ao variandw o que ele sabe de CURSO ATIVO e PLANO APROVADO - os
REM dois filtros que faltam para a exportacao automatica. So leitura; ver o
REM cabecalho do tools\mapear_gatilho.py.
REM
REM Uso, de uma maquina FORA do dominio:
REM   runas /netonly /user:CLINICA\geovani.pena "C:\...\isocentro\tools\mapear_gatilho.bat"
REM
REM Com um caso real (o registro de quem tem Documentacao aberta):
REM   ... "C:\...\tools\mapear_gatilho.bat" --paciente 9000019ANA
REM
REM Se a janela do runas piscar e fechar, abra um console com a identidade de
REM rede e rode este .bat DENTRO dele - e o caminho que nao depende de aspas:
REM   runas /netonly /user:CLINICA\geovani.pena cmd
REM
REM SENHA ERRADA NAO DA ERRO AQUI. O /netonly nao valida a senha: ele aceita o
REM que for digitado e a recusa so aparece la na frente, quando o programa toca
REM no servidor - e sai como "SRVINSIGHT respondeu e RECUSOU a identidade"
REM (SQLSTATE 28), que se parece com falta de permissao e nao e. Aconteceu em
REM 02/09/2026, as 18:18, depois de uma rodada boa as 17:11 com a mesma conta.
REM Se aparecer essa frase, redigite a senha antes de procurar qualquer outra
REM causa - e com cuidado, porque repetir errado bloqueia a conta no dominio.
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
REM e o arquivo nao tem DimPlan nenhuma, porque o gravador so guarda as
REM consultas que o app ja faz.
set ISOCENTRO_BANCO_LOCAL=

set PY=python
if exist "%CD%\.venv\Scripts\python.exe" set PY=%CD%\.venv\Scripts\python.exe

echo Python  : %PY%
echo Servidor: %ISOCENTRO_DB_SERVIDOR%
echo.
REM Grava tambem em arquivo: o relatorio e longo e o console do runas fecha.
"%PY%" tools\mapear_gatilho.py -o gatilho_achados.txt %*
echo.
pause
