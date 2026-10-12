@echo off
chcp 65001 >NUL
cd /d "%~dp0"
echo Installation de PyInstaller...
py -3 -m pip install --upgrade pyinstaller
if errorlevel 1 python -m pip install --upgrade pyinstaller
echo.
echo Compilation...
py -3 -m PyInstaller --onefile --icon assets\icon.ico --name XM32_Gain_Recall_LV1 x32_gain_recall.py
if errorlevel 1 python -m PyInstaller --onefile --icon assets\icon.ico --name XM32_Gain_Recall_LV1 x32_gain_recall.py
echo.
if exist dist\XM32_Gain_Recall_LV1.exe (
  echo OK : copiez dist\XM32_Gain_Recall_LV1.exe sur l'autre ordinateur.
) else (
  echo ECHEC : voir les messages ci-dessus.
)
pause
