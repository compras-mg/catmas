@echo off
setlocal
cd /d "%~dp0"
set /p "CATMAS_CSV=Caminho completo do CSV do KNIME: "
set "CATMAS_CSV=%CATMAS_CSV:"=%"
set /p "CATMAS_SAIDA=Nome de uma nova pasta de resultados: "
py -3 atualizar.py "%CATMAS_CSV%" --saida "%CATMAS_SAIDA%"
if errorlevel 1 echo A preparacao falhou. Confira a mensagem e o relatorio, se gerado.
pause
