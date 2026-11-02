@echo off
REM ============================================================================
REM  CLIQUE DUAS VEZES: investiga UM paciente no banco e grava um relatorio.
REM  Use quando a tela mostrar numero que nao bate com o ARIA.
REM ============================================================================

REM ---- As duas unicas coisas que se edita aqui -------------------------------
set USUARIO_DE_REDE=CLINICA\geovani.pena
set PACIENTE=9000011CEL
REM ---------------------------------------------------------------------------

title ISOCENTRO - investigar paciente %PACIENTE%
echo.
echo   Investigando o paciente %PACIENTE% no banco.
echo   Vai pedir a SENHA DE REDE (nao aparece nada enquanto digita).
echo.
echo   O relatorio sai na tela e fica gravado num arquivo; o caminho
echo   aparece no final. A janela so fecha quando voce mandar.
echo.

runas /netonly /user:%USUARIO_DE_REDE% "%~dp0mapear_tratamento.bat --paciente %PACIENTE%"

if errorlevel 1 (
    echo.
    echo   O runas recusou. Confira a linha USUARIO_DE_REDE no topo do arquivo.
)
echo.
pause
