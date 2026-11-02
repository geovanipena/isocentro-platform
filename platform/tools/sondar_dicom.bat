@echo off
REM Pergunta ao DB Daemon do ARIA O QUE ELE IMPLEMENTA: C-ECHO, C-FIND, C-GET e
REM C-MOVE. So leitura. Ver o cabecalho do tools\sondar_dicom.py.
REM
REM A PERGUNTA QUE ESTE .BAT EXISTE PARA RESPONDER: o servidor faz C-GET?
REM Se fizer, os arquivos voltam pela MESMA conexao e a exportacao nao precisa
REM de porta ouvindo, de regra de firewall para dentro, nem de AE de destino
REM cadastrado - o pedido a TI encolhe para "cadastrem este AE Title".
REM
REM RESPONDIDA EM 10/09/2026: NAO faz. O C-GET nao existe neste daemon, e a
REM exportacao e por C-MOVE, com o destino RADIOTERAFICHA ja cadastrado. O .bat
REM continua servindo para descobrir portas (--varrer) e sondar outro servidor;
REM para o servico da exportacao, o atalho com os valores da TI e o
REM tools\sondar_exportacao.bat.
REM
REM ANTES DE RODAR, e preciso ter da TI/Varian:
REM   ISOCENTRO_DICOM_SERVIDOR    host:porta do DB Daemon (costuma ser 51402)
REM   ISOCENTRO_DICOM_AE_REMOTO   o AE Title do ARIA
REM   ISOCENTRO_DICOM_AE_LOCAL    o AE Title DESTA estacao, cadastrado no ARIA
REM
REM Da para testar o que eles disserem sem gravar nada em estacao nenhuma:
REM   sondar_dicom.bat --servidor SRVARIA:51402 --ae-remoto VMSDBD --ae-local RTF
REM
REM DUAS IDENTIDADES DIFERENTES, e vale saber antes de rodar. O DICOM se
REM autentica por AE Title, nao pela conta do Windows: a sondagem em si NAO
REM precisa de runas. Quem precisa e o passo que descobre o UID do plano, que
REM fala com o variandw. Rodando assim, os dois funcionam de uma vez:
REM   runas /netonly /user:CLINICA\geovani.pena "C:\...\tools\sondar_dicom.bat"
REM
REM Sem identidade de rede, passe o UID na mao e o banco fica de fora:
REM   sondar_dicom.bat --uid 1.2.246.352.71.5.642399144380.534594.20260903123254
REM
REM O ARQUIVO QUE O C-GET TROUXER E DADO DE PACIENTE. Ele cai numa pasta
REM temporaria do sistema (nunca no repositorio) e o relatorio diz onde - para
REM poder ser apagado depois de conferido.
REM
REM Mesmas armadilhas dos outros .bat: o runas comeca em outra pasta, monta
REM ambiente limpo sem o .venv, e o console abre em code page 850.

chcp 65001 > nul
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8

REM O servidor do BANCO, so para o passo do UID. O DICOM tem o proprio endereco.
if "%ISOCENTRO_DB_SERVIDOR%%RADIOTERAFICHA_DB_SERVIDOR%%FICHAPY_DB_SERVIDOR%"=="" set ISOCENTRO_DB_SERVIDOR=SRVINSIGHT

REM Com ele definido, o UID viria do ARQUIVO gravado em vez do servidor - e o
REM banco local nao tem DimPlan, porque o gravador so guarda o que o app pede.
set ISOCENTRO_BANCO_LOCAL=

set PY=python
if exist "%CD%\.venv\Scripts\python.exe" set PY=%CD%\.venv\Scripts\python.exe

echo Python  : %PY%
echo.

REM CLICAR NO .BAT E O GESTO NATURAL, e sem argumento a ferramenta nao tinha o
REM que sondar - saia dizendo "falta o ISOCENTRO_DICOM_SERVIDOR" e pronto.
REM Aconteceu em 04/09/2026: a ida se perdeu num clique. Entao, sem argumento,
REM ele PERGUNTA o servidor e roda a varredura, que e a coisa util a fazer
REM quando ainda nao se sabe a porta.
if not "%~1"=="" goto :rodar

echo  Nenhum argumento. Vou perguntar o servidor e VARRER as portas dele -
echo  e a varredura que descobre qual delas e o daemon de consulta.
echo  (Enter em branco: nao roda nada e explica o que fazer.)
echo.
set SRV=
set /p SRV=  Servidor do ARIA (ex.: SRVARIADB):
if "%SRV%"=="" goto :rodar
echo.
"%PY%" tools\sondar_dicom.py --varrer --servidor "%SRV%" -o sonda_dicom.txt
goto :fim

:rodar
REM Grava tambem em arquivo: o console do runas fecha, e o relatorio que mais
REM importa e justamente o da rodada que deu errado.
"%PY%" tools\sondar_dicom.py -o sonda_dicom.txt %*

:fim
echo.
pause
