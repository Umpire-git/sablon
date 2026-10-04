@echo off
chcp 65001 >nul
echo Ornek kartlik uretiliyor (kalip PDF, 3B dosya ve Blender fotograflari)...
sablon yeni kapakli_citcitli_kartlik -o deneme.json
if exist doku (
  sablon cikti deneme.json -d deneme_cikti --foto hizli --doku doku
) else (
  sablon cikti deneme.json -d deneme_cikti --foto hizli
)
echo.
echo Bitti. Klasor aciliyor...
start "" deneme_cikti
pause
