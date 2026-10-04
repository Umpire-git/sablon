@echo off
chcp 65001 >nul
echo ============================================
echo   Sablon kurulumu
echo ============================================
python --version >nul 2>&1
if errorlevel 1 (
  echo Python bulunamadi.
  echo https://www.python.org/downloads/ adresinden Python 3.11 veya 3.12 kurun
  echo ve kurulumda "Add python.exe to PATH" kutusunu ISARETLEYIN.
  pause
  exit /b 1
)
python -m pip install --upgrade pip
python -m pip install -e .
if errorlevel 1 (
  echo Kurulumda hata oldu. Yukaridaki mesaji kopyalayip gonderin.
  pause
  exit /b 1
)
echo.
echo Kurulum tamam.
echo Fotogercekci gorseller icin Blender'i da kurun: https://www.blender.org/download/
pause
