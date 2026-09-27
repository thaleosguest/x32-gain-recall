@echo off
chcp 65001 >NUL
cd /d "%~dp0"
echo Installation de PyInstaller...
py -3 -m pip install --upgrade pyinstaller
if errorlevel 1 python -m pip install --upgrade pyinstaller
echo.
echo Compilation...
py -3 -m PyInstaller --onefile --name X32_Gain_Recall x32_gain_recall.py
if errorlevel 1 python -m PyInstaller --onefile --name X32_Gain_Recall x32_gain_recall.py
echo.
if exist dist\X32_Gain_Recall.exe (
  echo OK : copiez dist\X32_Gain_Recall.exe sur l'autre ordinateur.
) else (
  echo ECHEC : voir les messages ci-dessus.
)
pause
