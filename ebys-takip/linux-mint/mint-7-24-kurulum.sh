#!/usr/bin/env bash
# EBYS Görev Takip — Linux Mint 7/24 bilgisayar ayarları
# Kullanım: Terminal'de bu klasöre gelip:  bash mint-7-24-kurulum.sh
# Yönetici şifresi istemez; yalnızca bu kullanıcının ayarlarını değiştirir. Tekrar çalıştırmak zararsızdır.
set -euo pipefail

PORTAL="https://ebys.usak.edu.tr/enVision/RheaModule/Portal_Rhea.aspx"

# Tarayıcı: Firefox (Mint'te kurulu gelir). Google Chrome kuruluysa onu tercih etmek için: TARAYICI=google-chrome bash ...
TARAYICI="${TARAYICI:-firefox}"
if ! command -v "$TARAYICI" >/dev/null 2>&1; then
  echo "HATA: '$TARAYICI' bulunamadı. Firefox'u Yazılım Yöneticisi'nden kurun." >&2
  exit 1
fi
TARAYICI_YOLU="$(command -v "$TARAYICI")"

echo "1/4 Uyku ve otomatik kapanma kapatılıyor (ekran kararabilir, bilgisayar uyumaz)..."
if command -v gsettings >/dev/null 2>&1; then
  for anahtar in sleep-inactive-ac-timeout sleep-inactive-battery-timeout; do
    gsettings set org.cinnamon.settings-daemon.plugins.power "$anahtar" 0 2>/dev/null || true
  done
  gsettings set org.cinnamon.settings-daemon.plugins.power lid-close-ac-action 'nothing' 2>/dev/null || true
  # Ekran koruyucu kilidi açık kalsın: tarayıcı kilitli ekranın arkasında çalışmaya devam eder
  gsettings set org.cinnamon.desktop.screensaver lock-enabled true 2>/dev/null || true
else
  echo "   (gsettings yok; Sistem Ayarları → Güç Yönetimi'nden 'Bilgisayarı uyut: Asla' seçin)"
fi

echo "2/4 Açılışta EBYS ana sayfası otomatik açılacak..."
mkdir -p "$HOME/.config/autostart"
cat > "$HOME/.config/autostart/ebys-takip.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=EBYS Görev Takip
Comment=EBYS ana sayfasını açar; Tampermonkey betiği görevleri takip tablosuna aktarır
Exec=$TARAYICI_YOLU --new-window $PORTAL
X-GNOME-Autostart-Delay=45
X-GNOME-Autostart-enabled=true
EOF

echo "3/4 Tarayıcı her gece 03:30'da yeniden başlatılacak (bellek şişmesine karşı)..."
mkdir -p "$HOME/.local/bin"
cat > "$HOME/.local/bin/ebys-tarayici-yenile.sh" <<EOF
#!/usr/bin/env bash
# Tarayıcıyı kapatıp EBYS ana sayfasıyla yeniden açar
pkill -f "$TARAYICI_YOLU" || true
sleep 15
export DISPLAY="\${DISPLAY:-:0}"
export XDG_RUNTIME_DIR="\${XDG_RUNTIME_DIR:-/run/user/\$(id -u)}"
nohup "$TARAYICI_YOLU" --new-window "$PORTAL" >/dev/null 2>&1 &
EOF
chmod +x "$HOME/.local/bin/ebys-tarayici-yenile.sh"
GOREV="30 3 * * * $HOME/.local/bin/ebys-tarayici-yenile.sh"
{ crontab -l 2>/dev/null | grep -v 'ebys-tarayici-yenile.sh' || true; echo "$GOREV"; } | crontab -

echo "4/4 Kontrol..."
echo "   Otomatik başlatma: $HOME/.config/autostart/ebys-takip.desktop"
echo "   Gece yenilemesi : $(crontab -l | grep ebys-tarayici-yenile.sh)"
echo
echo "Tamam. Kalan elle yapılacaklar (LINUX-MINT.md):"
echo "  - Tarayıcıya Tampermonkey + EBYS Görev Takip betiğini kurun, ayarlarını ve 'Otomatik giriş'i girin"
echo "  - Menü → Giriş Penceresi → Kullanıcılar: bu kullanıcı için otomatik oturum açmayı açın"
echo "  - BIOS: elektrik gelince bilgisayar kendiliğinden açılsın (Restore on AC power loss: Power On)"
