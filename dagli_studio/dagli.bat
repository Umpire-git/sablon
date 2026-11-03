@echo off
chcp 65001 >nul
cd /d "%~dp0"
:menu
cls
echo ==============================================
echo   DAGLI LEATHER STUDIO - kalip uretim hatti
echo ==============================================
echo  1  Rakip taramasi (Etsy)
echo  2  Fikir uret (1. kapi)
echo  3  Tasarla - Claude urun kodunu yazar (2. kapi)
echo  4  Kontrol + en kotu durum testi
echo  5  Kagit deneme paketi (2. kapi teslimi)
echo  6  Tam satis paketi (3. kapi)
echo  7  Gercekci gorseller (Gemini)
echo  8  Ornek urunler
echo  0  Cikis
echo.
set /p sec="Secim: "
if "%sec%"=="1" goto pazar
if "%sec%"=="2" goto fikir
if "%sec%"=="3" goto tasarla
if "%sec%"=="4" goto kontrol
if "%sec%"=="5" goto deneme
if "%sec%"=="6" goto uret
if "%sec%"=="7" goto gorsel
if "%sec%"=="8" goto ornek
if "%sec%"=="0" exit /b
goto menu
:pazar
set /p q="Etsy'de aranacak ifade (Ingilizce, or. leather pen holder pattern): "
python -m dagli pazar "%q%" --web
pause & goto menu
:fikir
set /p q="Ne istiyorsun? (or. masa duzenleyici, yilbasi hediyesi): "
set /p p="Pazar klasoru (bos birakilabilir, or. pazar\leather_pen_holder_pattern): "
if "%p%"=="" (python -m dagli fikir "%q%") else (python -m dagli fikir "%q%" --pazar "%p%")
pause & goto menu
:tasarla
set /p s="Secilen fikrin adi: "
set /p o="Urun dosyasi adi (or. urunler\kartlik.py): "
python -m dagli tasarla fikirler.md --sec "%s%" -o "%o%"
pause & goto menu
:kontrol
set /p u="Urun dosyasi (or. urunler\round_pen_cup.py): "
python -m dagli kontrol "%u%"
pause & goto menu
:deneme
set /p u="Urun dosyasi: "
python -m dagli deneme "%u%"
pause & goto menu
:uret
set /p u="Urun dosyasi: "
set /p p="Pazar klasoru (bos birakilabilir): "
if "%p%"=="" (python -m dagli uret "%u%") else (python -m dagli uret "%u%" --pazar "%p%")
start "" teslim
pause & goto menu
:gorsel
set /p u="Urun dosyasi: "
set /p a="Onayli foto (bos birakilabilir): "
if "%a%"=="" (python -m dagli gorsel "%u%") else (python -m dagli gorsel "%u%" --onayli "%a%")
pause & goto menu
:ornek
python -m dagli ornekler
pause & goto menu
