@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Dagli Studio kuruluyor...
python -m pip install --upgrade pip
python -m pip install -e .
if errorlevel 1 (
  echo.
  echo Kurulum basarisiz. Python 3.10+ kurulu ve "Add python.exe to PATH" isaretli olmali.
  pause
  exit /b 1
)
echo.
echo Kurulum tamam. Simdi dagli.bat dosyasina cift tiklayin.
pause
