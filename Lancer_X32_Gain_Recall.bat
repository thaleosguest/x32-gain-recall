@echo off
chcp 65001 >NUL
cd /d "%~dp0"
where py >NUL 2>&1
if not errorlevel 1 (
  py -3 x32_gain_recall.py %*
  goto :fin
)
python x32_gain_recall.py %*
:fin
if errorlevel 1 (
  echo.
  echo Si Python est introuvable : installez-le depuis https://www.python.org/downloads/
  echo en cochant "Add python.exe to PATH", puis relancez ce fichier.
  pause
)
