@echo off
REM SERVIDOR LOCAL de demonstracao - o app INTEIRO fora da rede da clinica,
REM com o trabalho do dia JA FEITO: fichas impressas, altas na pasta, casos do
REM gatilho preparados (PRONTA), checklists conferidos e Datas Relevantes.
REM
REM Uso:
REM   tools\servidor_local.bat                 abre o app (admin, sem login)
REM   tools\servidor_local.bat medico          abre com os olhos de uma funcao
REM                                            (medico, fisico, tecnico...)
REM   tools\servidor_local.bat varredura       so roda UMA passada do gatilho
REM
REM O que ele faz, nesta ordem:
REM   1. monta o banco simulado a partir de TCs_Teste (montar_servidor_local.py),
REM      com as datas deslocadas para HOJE - por isso monta de novo a cada abertura;
REM   2. sobe o servidor DICOM local (servidor_dicom_local.py) numa janela
REM      minimizada - e o "ARIA" que entrega os planos ao gatilho;
REM   3. prepara o que uma estacao ja teria feito (preparar_demo.py): fichas e
REM      altas pela Impressao do programa, checklists e Datas Relevantes. A
REM      PRIMEIRA vez leva ~1 min por caso; depois so refaz o que falta;
REM   4. roda uma passada do gatilho, que deixa a Documentacao como PRONTA;
REM   5. liga as variaveis e abre o app; ao fechar, derruba o servidor DICOM.
REM
REM O que a demonstracao grava fica em TCs_Teste\servidor_local\ (fora do git),
REM menos as fichas e altas: essas vao para a pasta de cada TC, que e onde o
REM programa as grava (so acrescenta; o DICOM nunca e apagado).
REM O app ANUNCIA a simulacao: Configuracoes -> Servico mostra "SERVIDOR LOCAL
REM (demonstracao)" e a Capa sai com o aviso de sempre.

chcp 65001 > nul
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8

set PY=python
if exist "%CD%\.venv\Scripts\python.exe" set PY=%CD%\.venv\Scripts\python.exe
set SL=%CD%\TCs_Teste\servidor_local

echo Montando o servidor local (banco simulado + simulacoes)...
"%PY%" tools\montar_servidor_local.py
if errorlevel 1 (
  echo.
  echo A conferencia acusou tela sem dado - veja as linhas com "!!" acima.
  echo O app abre mesmo assim; o que estiver marcado pode aparecer vazio.
  echo.
)

REM --- Banco: o arquivo decide o modo (servidor local, nao gravacao). ---------
set ISOCENTRO_BANCO_LOCAL=%SL%\dw_simulado.sqlite
set ISOCENTRO_DB_SERVIDOR=

REM --- Os paineis ainda nao conferidos contra o banco real: ligados, e a tela
REM     anuncia isso numa faixa ambar. ---------------------------------------
set ISOCENTRO_LISTA_EXPERIMENTAL=1
set ISOCENTRO_ATIVIDADES_EXPERIMENTAL=1
set ISOCENTRO_GATILHO_EXPERIMENTAL=1
REM Jean: o medico com mais pacientes das pastas (os casos completos).
if "%ISOCENTRO_MEDICO%%RADIOTERAFICHA_MEDICO%%FICHAPY_MEDICO%"=="" set ISOCENTRO_MEDICO=Jean

REM --- DICOM: o servidor local faz as vezes do DB Daemon do ARIA. ------------
set ISOCENTRO_DICOM_SERVIDOR=127.0.0.1:11112
set ISOCENTRO_DICOM_AE_REMOTO=ARIA_LOCAL
set ISOCENTRO_DICOM_AE_LOCAL=ISOCENTRO
set ISOCENTRO_DICOM_AE_DESTINO=ISOCENTRO_DEST
set ISOCENTRO_DICOM_PORTA_ESCUTA=11113

REM --- Pastas: o que a demonstracao grava fica ao lado do banco. -------------
set ISOCENTRO_EXPORTACAO=%SL%\exportacao
set ISOCENTRO_SIMULACOES=%SL%\simulacoes
set ISOCENTRO_ESPELHO=%SL%\espelho
set ISOCENTRO_GATILHO_REGISTRO=%SL%\gatilho_registro.json
set ISOCENTRO_DATAS_RELEVANTES=%SL%\datas_relevantes.json
set ISOCENTRO_CHECKLIST=%SL%
set ISOCENTRO_CAPA_DIR=%CD%\TCs_Teste\banco de dados
if not exist "%ISOCENTRO_EXPORTACAO%" mkdir "%ISOCENTRO_EXPORTACAO%"

echo.
echo Subindo o servidor DICOM local (janela minimizada)...
start "Servidor DICOM local" /min "%PY%" tools\servidor_dicom_local.py

if /i "%~1"=="varredura" (
  echo Uma passada do gatilho - os planos vao para %ISOCENTRO_EXPORTACAO%
  "%PY%" run_varredura.py --uma-vez
  goto :fim
)

echo.
echo Preparando o trabalho ja feito (fichas, altas, checklists, datas)...
"%PY%" tools\preparar_demo.py

echo.
echo Gatilho: preparando os casos com Documentacao aberta (PRONTA)...
"%PY%" run_varredura.py --uma-vez

REM Pula o login - ferramenta de demonstracao na maquina de trabalho, nunca o
REM pacote da clinica. Com argumento, abre na funcao pedida (ver
REM arranque._usuario_de_dev).
set ISOCENTRO_DEV=1
if not "%~1"=="" set ISOCENTRO_DEV=%~1

echo.
echo Banco   : %ISOCENTRO_BANCO_LOCAL%
echo DICOM   : %ISOCENTRO_DICOM_AE_REMOTO% em %ISOCENTRO_DICOM_SERVIDOR%
echo Funcao  : %ISOCENTRO_DEV%
echo.
"%PY%" run_gui.py

:fim
taskkill /FI "WINDOWTITLE eq Servidor DICOM local*" /T /F > nul 2>&1
pause
