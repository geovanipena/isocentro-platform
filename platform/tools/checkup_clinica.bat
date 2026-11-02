@echo off
REM MEDE DE UMA VEZ TUDO O QUE O ISOCENTRO PRECISA DA REDE, e escreve o
REM pedido a TI ja pronto. SO LEITURA - ver o cabecalho do checkup_clinica.py.
REM
REM POR QUE ELE EXISTE: cada pergunta a infraestrutura virou um chamado
REM proprio, e a resposta de um chegava depois de o outro estar fechado. Este
REM aqui pergunta tudo numa rodada: rede, banco, pastas, DICOM, impressora - e
REM o bloco 12 junta o que faltou num texto para copiar no chamado.
REM
REM SAO DOIS AMBIENTES, e o relatorio comeca dizendo qual e qual:
REM   * DESENVOLVIMENTO - a maquina do fonte, fora do dominio. O banco vai
REM     falhar em SSPI aqui, e isso e o ESPERADO, nao um achado;
REM   * CLINICA - o .exe do share, em cada estacao, com conta de dominio.
REM
REM RODAR NAS DUAS PONTAS, e guardar os dois arquivos. E a comparacao entre
REM eles que responde a pergunta que decide o custo de producao: o cadastro do
REM nosso AE Title amarra IP? Se amarrar, e um chamado por estacao, para
REM sempre - ou a topologia de concentrador.
REM
REM COMO RODAR
REM   1. DOIS CLIQUES: faz tudo o que nao precisa de conta de dominio. O DICOM
REM      se autentica por AE Title, entao C-ECHO, C-FIND, receptor e o circuito
REM      inteiro respondem assim mesmo - desde que se passe um --uid;
REM   2. COM IDENTIDADE DE REDE, para o banco e para achar o UID sozinho:
REM        runas /netonly /user:CLINICA\geovani.pena "C:\Users\geova\Documents\isocentro\programa\isocentro\tools\checkup_clinica.bat"
REM   3. COM UID NA MAO, sem banco e sem runas:
REM        checkup_clinica.bat --uid 1.2.246.352.71.5.642399144380.534594.20260903123254
REM
REM OS EXTRAS, que nao rodam por padrao porque custam tempo e disco:
REM   --ct        traz UMA serie de CT e mede objetos, MB e segundos. E o que
REM               orca a proxima frente: sem esse numero, "a CT e cara" e
REM               palpite;
REM   --carga 4   quatro associacoes ao mesmo tempo, para saber se o daemon
REM               aceita varias estacoes pedindo junto;
REM   --pular banco,dicom   recorta a rodada quando so se quer uma parte.
REM
REM O QUE LER NA SAIDA, nesta ordem:
REM   1. o bloco 12 - e o chamado, ja escrito e separado por fase;
REM   2. dentro dele, a secao NOSSO: essas nao sao da TI, sao configuracao
REM      desta maquina, e abrir chamado para elas gasta uma ida a toa;
REM   3. o bloco 1, campo "IP de saida": e o numero que a TI cadastra, e o que
REM      se compara entre as duas estacoes.
REM
REM O QUE ELE ESCREVE, e sao so duas coisas: um arquivo de teste em cada pasta
REM que precisa aceitar escrita (criado e apagado na hora) e o DICOM que
REM chegar, numa pasta temporaria do sistema que o relatorio NOMEIA - e dado de
REM paciente, e alguem precisa apaga-lo depois de conferir.
REM
REM Mesmas armadilhas dos outros .bat: o runas comeca noutra pasta, monta
REM ambiente limpo sem o .venv, e o console abre em code page 850.

chcp 65001 > nul
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8

REM Os tres valores da TI, medidos em 10/09/2026. Ficam aqui e nao no .py
REM porque sao configuracao DESTA clinica: no codigo, o dia em que mudarem o
REM valor estaria mentindo calado. Passar --servidor na linha de comando vence
REM estes.
if "%ISOCENTRO_DICOM_SERVIDOR%%RADIOTERAFICHA_DICOM_SERVIDOR%%FICHAPY_DICOM_SERVIDOR%"=="" set ISOCENTRO_DICOM_SERVIDOR=192.0.2.9:51405
if "%ISOCENTRO_DICOM_AE_REMOTO%%RADIOTERAFICHA_DICOM_AE_REMOTO%%FICHAPY_DICOM_AE_REMOTO%"=="" set ISOCENTRO_DICOM_AE_REMOTO=radioteraficha
if "%ISOCENTRO_DICOM_AE_LOCAL%%RADIOTERAFICHA_DICOM_AE_LOCAL%%FICHAPY_DICOM_AE_LOCAL%"=="" set ISOCENTRO_DICOM_AE_LOCAL=RADIOTERAFICHA

REM O servidor do BANCO, so para os blocos 4 e 6. O DICOM tem o proprio.
if "%ISOCENTRO_DB_SERVIDOR%%RADIOTERAFICHA_DB_SERVIDOR%%FICHAPY_DB_SERVIDOR%"=="" set ISOCENTRO_DB_SERVIDOR=SRVINSIGHT

REM Com ele definido, o UID viria do ARQUIVO gravado em vez do servidor - e o
REM banco local nao tem DimPlan, porque o gravador so guarda o que o app pede.
set ISOCENTRO_BANCO_LOCAL=

set PY=python
if exist "%CD%\.venv\Scripts\python.exe" set PY=%CD%\.venv\Scripts\python.exe

echo.
echo  Python  : %PY%
echo  DICOM   : %ISOCENTRO_DICOM_SERVIDOR%  (AE %ISOCENTRO_DICOM_AE_REMOTO%)
echo  Chamando: %ISOCENTRO_DICOM_AE_LOCAL%
echo  Banco   : %ISOCENTRO_DB_SERVIDOR%
echo.
echo  SO LEITURA. Nada e alterado em estacao nenhuma.
echo.

REM Grava tambem em arquivo, e por isso o .bat existe: o console do runas
REM fecha ao terminar, e o relatorio que mais importa e o da rodada que deu
REM errado. O nome ganha data e hora quando ja existe um - nenhuma rodada
REM sobrescreve o que a anterior trouxe.
"%PY%" tools\checkup_clinica.py -o checkup_clinica.txt %*

echo.
echo  O arquivo caiu em relatorios_ferramentas\ - e ELE que vai para o chamado.
echo.
pause
