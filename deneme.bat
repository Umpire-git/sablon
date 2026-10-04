@echo off
chcp 65001 >nul
echo Ornek kartlik uretiliyor (kalip PDF, 3B dosya ve gorseller)...
sablon yeni kapakli_citcitli_kartlik -o deneme.json
set EK=
if exist doku set EK=--doku doku
if defined GEMINI_API_KEY (
  sablon cikti deneme.json -d deneme_cikti --foto hizli %EK% --gemini studyo,ahsap
) else (
  echo [Bilgi] GEMINI_API_KEY yok: gercekci Gemini gorselleri atlandi.
  sablon cikti deneme.json -d deneme_cikti --foto hizli %EK%
)
echo.
echo Bitti. Klasor aciliyor...
start "" deneme_cikti
pause
