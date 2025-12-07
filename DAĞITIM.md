# PDF Temizleyici - Dağıtım Kılavuzu

Taranmış Arapça PDF'lerdeki lekeleri ve çizgileri temizleyen uygulama.

---

## 📦 Hazır Dosyalar

### macOS

- `dist/PDFTemizleyiciMAC.app` - macOS uygulaması (çift tıkla çalışır)

### Windows

Windows'ta aşağıdaki komutla build alınmalı:

```bash
pip install flet pyinstaller
flet pack app.py --name "PDFTemizleyiciWINDOWS"
```

Sonuç: `dist/PDFTemizleyiciWINDOWS.exe`

---

## 🚀 Son Kullanıcıya Gönderme

### macOS

1. `dist/PDFTemizleyiciMAC.app` dosyasını ZIP'le
2. Kullanıcıya gönder
3. Kullanıcı ZIP'i açıp uygulamaya çift tıklasın
4. İlk açılışta sağ tık → "Aç" (Gatekeeper uyarısı için)

### Windows

1. `dist/PDFTemizleyiciWINDOWS.exe` dosyasını gönder
2. Kullanıcı çift tıklayıp çalıştırsın

---

## ⚙️ Kullanım

1. Uygulamayı aç
2. PDF dosya yolunu yapıştır veya "Seç" butonuna tıkla
3. Ayarları düzenle (DPI, ortalama vb.)
4. Çıktı dosya yolunu belirle
5. "TEMİZLE" butonuna tıkla
6. İşlem bitince temizlenmiş PDF çıktı klasöründe olacak

---

## 📋 Gereksinimler

- **macOS**: 10.13+ (High Sierra veya üstü)
- **Windows**: Windows 10/11

Python veya başka yazılım kurulumu gerekmez.
