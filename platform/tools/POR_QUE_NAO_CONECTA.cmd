@echo off
REM ============================================================================
REM  CLIQUE DUAS VEZES quando o app disser "Nao consegui conectar a SRVINSIGHT".
REM
REM  Ele roda os 8 passos do diagnostico e diz QUAL das quatro coisas falhou:
REM    driver ODBC  |  rede  |  identidade  |  permissao
REM
REM  Elas dao mensagens parecidas e exigem providencias completamente
REM  diferentes - por isso o diagnostico existe.
REM ============================================================================

title ISOCENTRO - por que nao conecta?

echo.
echo   Rodando o diagnostico EXATAMENTE como o app faz: com a sua identidade
echo   do Windows, sem emprestar credencial nenhuma.
echo.
echo   E assim de proposito. Se falhar aqui e funcionar com runas, a resposta
echo   ja e essa: a maquina nao esta no dominio.
echo.

call "%~dp0diagnostico_db.bat"
