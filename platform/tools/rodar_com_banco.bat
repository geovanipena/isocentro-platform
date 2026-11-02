@echo off
REM Abre o ISOCENTRO COM acesso ao data warehouse, de uma maquina que nao
REM esta no dominio. E o que permite ver a aba Ficha Virtual com dado real sem
REM ir ate a clinica.
REM
REM Uso:
REM   runas /netonly /user:CLINICA\geovani.pena "C:\...\isocentro\tools\rodar_com_banco.bat"
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

REM O servidor por variavel de ambiente: esta maquina nao tem config_servico.json,
REM e a variavel tem precedencia sobre ele de qualquer forma. Assim testar aqui
REM nao mexe na configuracao de nenhuma estacao.
if "%ISOCENTRO_DB_SERVIDOR%%RADIOTERAFICHA_DB_SERVIDOR%%FICHAPY_DB_SERVIDOR%"=="" set ISOCENTRO_DB_SERVIDOR=SRVINSIGHT

REM Pula o login. E aceitavel AQUI porque isto e ferramenta de teste na maquina
REM de desenvolvimento, nunca o que se distribui: o pacote da clinica nao leva a
REM pasta tools\.
set ISOCENTRO_DEV=1

REM -- Simulacao, so nesta maquina -----------------------------------------
REM Liga o painel "em tratamento" ANTES de ele estar conferido contra o banco.
REM A tela ANUNCIA isso numa faixa ambar - e e para conferir os numeros contra o
REM ARIA que ele e ligado aqui. Nao vai no pacote: tools\ nao e distribuida.
set ISOCENTRO_LISTA_EXPERIMENTAL=1

REM Qual medico ja vem escolhido. O app nao sabe quem esta logado (o login tem
REM papel admin/fisico, nao identidade de medico), entao isto SIMULA a tela de
REM um medico sem fingir que ele entrou. Casa por pedaco do nome.
REM
REM O ARGUMENTO manda, e existe por causa do runas: ele monta ambiente limpo,
REM entao a variavel definida por quem chama NAO chega aqui.
REM
REM %* e nao %~1: nome de medico tem ESPACO ("Ramos Junior"), e %~1 pegaria so
REM o primeiro pedaco. Filtrar por "Ramos" acha outro medico e o echo confirmaria
REM o nome truncado, entao o erro passaria despercebido.
if not "%~1"=="" set ISOCENTRO_MEDICO=%*
if "%ISOCENTRO_MEDICO%%RADIOTERAFICHA_MEDICO%%FICHAPY_MEDICO%"=="" set ISOCENTRO_MEDICO=Rubens

set PY=python
if exist "%CD%\.venv\Scripts\python.exe" set PY=%CD%\.venv\Scripts\python.exe

echo Python : %PY%
echo Servidor: %ISOCENTRO_DB_SERVIDOR%
echo Medico  : %ISOCENTRO_MEDICO%
echo.
echo Se a aba Ficha Virtual disser "Tratamento indisponivel", a identidade de
echo rede nao chegou: rode de novo pelo runas /netonly.
echo.
"%PY%" run_gui.py
pause
