@echo off
setlocal
cd /d "%~dp0"
echo Atualizacao do buscador CATMAS no GitHub Pages
echo O CSV sera validado antes do envio ao GitHub.
py -3 publicar.py
if errorlevel 3 (
  echo O envio ocorreu, mas a publicacao ainda precisa ser verificada.
) else if errorlevel 1 (
  echo Houve uma falha. Confira as mensagens e os relatorios.
) else (
  echo Atualizacao publicada e verificada.
)
pause
