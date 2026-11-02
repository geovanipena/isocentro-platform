@echo off
REM Sonda O SERVICO QUE A TI SUBIU PARA O ISOCENTRO - o alvo da frente da
REM exportacao automatica. E um atalho, nada mais: quem faz o trabalho e o
REM tools\sondar_dicom.bat, e os valores abaixo sao os que a TI mandou.
REM
REM QUANDO A TI MUDAR OS VALORES, MUDE AQUI. Eles ja mudaram uma vez: em
REM 04/09/2026 o alvo era a 51404 (AE 'ARIA'), medida na varredura; em
REM 10/09/2026 a TI subiu um servico NOVO na 51405, com AE 'isocentro'.
REM Por isso este arquivo NAO se chama pelo numero da porta - nome com o valor
REM dentro envelhece calado, que foi exatamente o defeito da lista de portas do
REM sondar_dicom.py, cega para a 51405 ate 10/09/2026.
REM
REM E O TEXTO TAMBEM ENVELHECE. Ate 11/09/2026 este cabecalho mandava ler "a
REM linha do C-GET" e dizia que faltava a TI cadastrar o nosso AE - as duas
REM perguntas ja tinham resposta desde 10/09, e quem seguisse o arquivo iria
REM atras de uma decisao ja tomada. O que ja se sabe, medido em 10/09/2026:
REM   * o AE chamador RADIOTERAFICHA esta CADASTRADO, sem amarrar IP;
REM   * o C-GET NAO EXISTE neste daemon. A exportacao e por C-MOVE;
REM   * o AE de DESTINO RADIOTERAFICHA esta cadastrado apontando para a
REM     198.51.100.57, porta 104. E em 11/09 o C-MOVE trouxe o conjunto inteiro
REM     para la: CT x199, RTDOSE x4, RTPLAN, RTSTRUCT, 0 falha.
REM Por isso este atalho agora passa o --ae-destino: sem ele o C-MOVE nem e
REM tentado, e a sondagem pararia no C-GET que ja se sabe morto.
REM
REM O QUE "FUNCIONA" QUER DIZER DEPENDE DE ONDE RODA. O ARIA entrega no IP
REM cadastrado para o destino, nao em quem pediu (ARMADILHAS.md, "No C-MOVE,
REM os arquivos NAO voltam pela conexao que pediu"):
REM   * na 198.51.100.57: FUNCIONA e o esperado. NADA CHEGOU aqui e porta 104
REM     fechada ou regra de firewall de ENTRADA para o python.exe;
REM   * em QUALQUER OUTRA maquina: NADA CHEGOU e o esperado, e nao e defeito -
REM     os arquivos foram para a 198.51.100.57. E o "teste cruzado" do
REM     docs\ROTEIRO_DA_IDA.md: com o receptor de pe la, chegar la prova o
REM     concentrador sem pedir nada a TI.
REM
REM DAR DOIS CLIQUES chega ao C-ECHO sem senha nenhuma: o DICOM se autentica
REM por AE Title, nao pela conta do Windows, e desde 10/09 o C-ECHO roda ANTES
REM do banco. Quem precisa de identidade de rede e so o passo que pergunta ao
REM variandw qual plano esta pronto - sem ela, o C-FIND e o C-MOVE ficam sem
REM plano, e o relatorio diz isso em vez de fingir que rodou.
REM
REM PARA IR ATE O C-MOVE, com o UID vindo do banco:
REM   runas /netonly /user:CLINICA\geovani.pena "C:\Users\geova\Documents\isocentro\programa\isocentro\tools\sondar_exportacao.bat"
REM
REM Ou, com um UID na mao, sem banco e sem runas:
REM   sondar_exportacao.bat --uid 1.2.246.352.71.5.642399144380.534594.20260903123254
REM
REM O QUE O C-MOVE TROUXER E DADO DE PACIENTE: cai numa pasta temporaria do
REM sistema, nunca no repositorio, e o relatorio diz onde - para apagar depois
REM de conferido.
REM
REM QUEM CHAMA, EM PRODUCAO, E CADA ESTACAO. Todo mundo executa o MESMO
REM .exe, que fica numa pasta do FILESERVER - mas .exe em share roda na maquina de
REM QUEM ABRE, e o FILESERVER so serve o arquivo. Por isso o AE chamador foi
REM cadastrado SEM amarrar a um IP: amarrado, seria um chamado por estacao,
REM para sempre. Isto ja saiu ao contrario duas vezes - ate 10/09/2026 este
REM comentario dizia que quem chamava era o FILESERVER (192.0.2.33).
REM
REM O DESTINO, ao contrario, AMARRA IP - e tem de amarrar: e para la que o ARIA
REM abre a conexao. E por isso que a concentradora (qual maquina recebe) e
REM decisao ainda em aberto, no NOTAS.md.

setlocal

REM Os valores da TI, 10/09/2026. O --servidor da linha de comando vence a
REM variavel da estacao (ele grava o nome ISOCENTRO_*, que tem
REM precedencia), entao o ISOCENTRO_DICOM_SERVIDOR apontado para o srvariadb nao
REM desvia esta sondagem em silencio. O %* vai POR ULTIMO: um --ae-destino
REM digitado na linha de comando vence o daqui.
set ALVO=192.0.2.9:51405
set AE_REMOTO=isocentro
set AE_LOCAL=RADIOTERAFICHA
set AE_DESTINO=RADIOTERAFICHA

echo.
echo  Alvo     : %ALVO%  (AE do servico: %AE_REMOTO%)
echo  Chamando : %AE_LOCAL%
echo  Destino  : %AE_DESTINO%  (cadastrado para a 198.51.100.57, porta 104)
echo.
echo  O QUE LER NA SAIDA, nesta ordem:
echo    1. C-ECHO. Recusado com "Calling AE title not recognised" = o cadastro
echo       do nosso AE caiu - ele existe desde 10/09/2026;
echo    2. C-GET vai sair FALHOU, e isso e o esperado: nao existe neste daemon;
echo    3. a linha do C-MOVE e a que decide:
echo         FUNCIONA    = o circuito esta fechado NESTA maquina;
echo         NADA CHEGOU = na 198.51.100.57, porta ou firewall de entrada;
echo                       em outra maquina, e o esperado (foi para la).
echo.

call "%~dp0sondar_dicom.bat" --servidor %ALVO% --ae-remoto %AE_REMOTO% --ae-local %AE_LOCAL% --ae-destino %AE_DESTINO% %*
