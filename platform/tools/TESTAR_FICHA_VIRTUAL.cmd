@echo off
REM ============================================================================
REM  CLIQUE DUAS VEZES NESTE ARQUIVO para abrir o ISOCENTRO com acesso ao
REM  banco, ja filtrado no medico escolhido abaixo.
REM
REM  So pede a senha de rede. Nada e guardado.
REM ============================================================================

REM ---- As duas unicas coisas que se edita aqui -------------------------------
set USUARIO_DE_REDE=CLINICA\geovani.pena
set ISOCENTRO_MEDICO=Rubens
REM ---------------------------------------------------------------------------

chcp 65001 > nul
title ISOCENTRO - teste da aba Ficha Virtual

echo.
echo   Abrindo o ISOCENTRO com o banco.
echo.
echo   Usuario de rede : %USUARIO_DE_REDE%
echo   Medico do painel: %ISOCENTRO_MEDICO%
echo.
echo   Vai pedir a SENHA DE REDE. Nao aparece nada enquanto voce digita - e
echo   normal. Depois abre uma janela nova com o programa.
echo.

REM O runas monta um ambiente LIMPO: as variaveis definidas aqui NAO passam para
REM o processo filho. Por isso o medico viaja no proprio comando, como argumento
REM do rodar_com_banco.bat - foi assim que a primeira versao deste atalho abria
REM sempre com "Todos os medicos", ignorando a linha la de cima.
runas /netonly /user:%USUARIO_DE_REDE% "%~dp0rodar_com_banco.bat %ISOCENTRO_MEDICO%"

if errorlevel 1 (
    echo.
    echo   ----------------------------------------------------------------
    echo   O runas recusou. Quase sempre e o nome do usuario de rede.
    echo   Edite a linha USUARIO_DE_REDE no topo deste arquivo.
    echo.
    echo   Se a janela do programa PISCAR e fechar, o caminho abaixo nao
    echo   depende de aspas nenhuma:
    echo.
    echo     1^) runas /netonly /user:%USUARIO_DE_REDE% cmd
    echo     2^) dentro do console preto que abrir:
    echo        "%~dp0rodar_com_banco.bat" %ISOCENTRO_MEDICO%
    echo   ----------------------------------------------------------------
)
echo.
pause
