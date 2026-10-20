@echo off
chcp 65001 >NUL
cd /d "%~dp0"
echo Installation de PyInstaller et PySide6...
py -3 -m pip install --upgrade pyinstaller PySide6-Essentials
if errorlevel 1 python -m pip install --upgrade pyinstaller PySide6-Essentials
echo.
echo Compilation...
set OPTS=--onefile --noconsole --uac-admin --hidden-import tkinter --hidden-import x32_qt_float --hidden-import x32_qt_panels --hidden-import x32_qt_stage --hidden-import lv1.remote --hidden-import lv1.colorclick --hidden-import PySide6.QtWidgets --hidden-import PySide6.QtSvg --icon assets\icon.ico --name XM32_Gain_Recall_LV1
py -3 -m PyInstaller %OPTS% x32_gain_recall.py
if errorlevel 1 python -m PyInstaller %OPTS% x32_gain_recall.py
echo.
if exist dist\XM32_Gain_Recall_LV1.exe (
  echo OK : copiez dist\XM32_Gain_Recall_LV1.exe sur l'autre ordinateur.
) else (
  echo ECHEC : voir les messages ci-dessus.
)
pause
