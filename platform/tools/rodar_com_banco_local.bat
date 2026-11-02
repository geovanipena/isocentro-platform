@echo off
REM Abre o ISOCENTRO lendo o banco LOCAL gravado - SEM REDE e sem runas.
REM
REM E o irmao do rodar_com_banco.bat: aquele precisa da identidade de rede e fala
REM com o servidor de verdade; este le o arquivo que o gravar_banco.bat deixou
REM pronto, e por isso funciona em casa, no aviao e com o servidor fora do ar.
REM
REM Uso:
REM   tools\rodar_com_banco_local.bat
REM   tools\rodar_com_banco_local.bat "Rubens"     (medico ja escolhido)
REM
REM O dado e CONGELADO no dia da gravacao, e o app anuncia isso: a Capa sai com
REM aviso de SIMULACAO em primeiro lugar e Configuracoes -> Servico mostra
REM "BANCO LOCAL". Se algo disser "consulta nao gravada" no historico, e porque
REM o SQL daquela consulta mudou depois da gravacao - regrave.

chcp 65001 > nul
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8

set ISOCENTRO_BANCO_LOCAL=%CD%\TCs_Teste\banco de dados\banco_local.sqlite
if not exist "%ISOCENTRO_BANCO_LOCAL%" (
  echo Nao existe: %ISOCENTRO_BANCO_LOCAL%
  echo.
  echo Grave primeiro, de uma maquina com identidade de rede:
  echo   runas /netonly /user:CLINICA\geovani.pena "%CD%\tools\gravar_banco.bat"
  echo.
  pause
  exit /b 1
)

REM O servidor fica DE FORA de proposito: com o banco local ligado ele nao seria
REM consultado, e apontar um servidor aqui so faria a tela de diagnostico falar
REM de uma conexao que ninguem esta usando.
set ISOCENTRO_DB_SERVIDOR=

REM Pula o login. Aceitavel AQUI porque isto e ferramenta de teste na maquina de
REM desenvolvimento, nunca o que se distribui: o pacote da clinica nao leva a
REM pasta tools\.
set ISOCENTRO_DEV=1

REM Liga o painel "em tratamento" antes de ele estar conferido contra o banco.
REM A tela ANUNCIA isso numa faixa ambar.
set ISOCENTRO_LISTA_EXPERIMENTAL=1

REM Qual medico ja vem escolhido. %* e nao %~1: nome de medico tem ESPACO.
if not "%~1"=="" set ISOCENTRO_MEDICO=%*
if "%ISOCENTRO_MEDICO%%RADIOTERAFICHA_MEDICO%%FICHAPY_MEDICO%"=="" set ISOCENTRO_MEDICO=Rubens

set PY=python
if exist "%CD%\.venv\Scripts\python.exe" set PY=%CD%\.venv\Scripts\python.exe

echo Python : %PY%
echo Banco  : %ISOCENTRO_BANCO_LOCAL%
echo Medico : %ISOCENTRO_MEDICO%
echo.
"%PY%" run_gui.py
pause
