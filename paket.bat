@echo off
chcp 65001 >nul
echo ============================================
echo   Hazir modellerin satis paketleri
echo ============================================
echo Her model icin: A4/Letter/tam boy PDF kalip, SVG, DXF, 3B, gorseller, Etsy metni.
echo Yapay zeka KULLANILMAZ, ucretsizdir.
set KLASOR=%~1
if "%KLASOR%"=="" set KLASOR=hazir_modeller
set FOTO=
set /p F=Blender ile fotogercekci gorsel de uretilsin mi? (E/H, Blender kurulu olmali) :
if /i "%F%"=="E" set FOTO=--foto hizli
for %%f in ("%KLASOR%\*.json") do (
  echo.
  echo === %%~nf ===
  sablon cikti "%%f" -d "%KLASOR%\%%~nf" %FOTO%
)
echo.
echo Bitti. Her modelin klasoru '%KLASOR%' icinde.
start "" "%KLASOR%"
pause
