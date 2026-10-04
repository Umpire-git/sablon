@echo off
chcp 65001 >nul
echo ============================================
echo   Yeni urun fikirleri (Gemini veya Claude)
echo ============================================
if not defined GEMINI_API_KEY if not defined ANTHROPIC_API_KEY (
  echo Anahtar yok. Gemini icin: https://aistudio.google.com/apikey
  echo Sonra komut penceresinde:  setx GEMINI_API_KEY "anahtariniz"   yazin, pencereyi kapatip acin.
  pause
  exit /b 1
)
set /p TARIF=Ne istiyorsunuz? (ornek: kapakli citcitli dikissiz kartlik, crazy horse) :
set /p ADET=Kac fikir? (ornek: 4) :
if "%ADET%"=="" set ADET=4
set /p EKO=Ekonomi modu? Ucuz ve hizli, biraz daha az isabetli (E/H, varsayilan H) :
set EKOARG=
if /i "%EKO%"=="E" set EKOARG=--ekonomi
sablon fikir "%TARIF%" -n %ADET% -d fikirler --tam %EKOARG%
if errorlevel 1 (
  echo.
  echo Uygulanabilir fikir cikmadi veya bir hata oldu. Yukaridaki yaziyi okuyun.
  if exist fikirler\elenenler start "" fikirler\elenenler
  pause
  exit /b 1
)
echo.
echo Her fikir kendi klasorunde: PDF kaliplar, SVG, DXF, 3B, gorseller ve Etsy metni hazir.
if exist fikirler\koleksiyon.pdf start "" fikirler\koleksiyon.pdf
start "" fikirler
pause
