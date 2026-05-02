# Elbise Fiyat ve Stok Takibi

Bu küçük uygulama Trendyol Milla ürününü belirli aralıklarla kontrol eder ve şartlar sağlanırsa telefona bildirim gönderir.

İzlenen koşullar:

- Ürün: `https://tyml.gl/uq4mog25i63ut`
- Hedef fiyat: `800-1250 TL`
- Beden: `M` veya `L`
- Renk: `mavi` / `lacivert`
- Bildirim: telefon push bildirimi için `ntfy`

## Telefon Bildirimi Kurulumu

1. Telefona **ntfy** uygulamasını kur.
   - Android: Google Play'de `ntfy`
   - iPhone: App Store'da `ntfy`
2. Kendine tahmin edilmesi zor bir konu adı seç. Örnek:
   - `abdul-elbise-660272836-9x4p`
3. ntfy uygulamasında bu konuya abone ol.
4. `config.example.json` dosyasını `config.json` olarak kopyala.
5. `ntfy_topic` değerini kendi konu adınla değiştir.

## Çalıştırma

```powershell
python .\src\dress_watch.py --config .\config.json
```

Tek sefer kontrol etmek için:

```powershell
python .\src\dress_watch.py --config .\config.json --once
```

Bildirim test etmek için:

```powershell
python .\src\dress_watch.py --config .\config.json --test-notify
```

## Windows Görev Zamanlayıcı

Bu bilgisayarda `Elbise Fiyat Stok Takibi` adında bir görev oluşturuldu. Her 10 dakikada bir şu komutu arka planda çalıştırır:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\Users\Abdul\Documents\Codex\2026-05-02\bir-elbise-alaca-m-ancak-elbise\run-watch.ps1" --once
```

Görevi elle çalıştırmak için:

```powershell
schtasks /Run /TN "Elbise Fiyat Stok Takibi"
```

Görevi kapatmak için:

```powershell
schtasks /Change /TN "Elbise Fiyat Stok Takibi" /DISABLE
```

Tekrar açmak için:

```powershell
schtasks /Change /TN "Elbise Fiyat Stok Takibi" /ENABLE
```

## Bilgisayar Kapalıyken Takip

Bilgisayar kapalıyken yerel Windows görevi çalışamaz. Bunun için `.github/workflows/dress-watch.yml` dosyası eklendi. Bu workflow GitHub Actions üzerinde her 10 dakikada bir çalışır.

Kurulum:

1. Bu klasörü GitHub'da yeni bir depoya yükle.
2. GitHub deposunda `Settings > Secrets and variables > Actions` bölümüne gir.
3. `New repository secret` ile şu secret'ı ekle:

```text
Name: NTFY_TOPIC
Value: abdul-elbise-660272836-20260502
```

4. Depoda `Actions` sekmesine gir.
5. `Elbise Fiyat Stok Takibi` workflow'unu aç.
6. `Run workflow` ile bir kez elle çalıştır.

Notlar:

- GitHub zamanlayıcısı dakikası dakikasına garanti vermez; bazen birkaç dakika gecikebilir.
- Şart sağlandığında sürekli aynı bildirimi atmamak için `data/state.json` dosyası workflow tarafından depoya geri kaydedilir.
- Secret kullanıldığı için bildirim konu adı workflow loglarında açıkça görünmez.

## Notlar

Trendyol sayfaları bazen Cloudflare veya bot koruması ile doğrudan HTML erişimini engelleyebilir. Bu yüzden uygulama önce ürün ID'si ile JSON uç noktalarını dener, sonra kısa linkin yönlendiği sayfadan veri çıkarmaya çalışır.

Uygulama aynı fiyat/beden durumu için sürekli bildirim yağdırmaz; son bildirimi `data/state.json` içinde saklar.

## Birden Fazla Ürün Takibi

`config.json` içinde `products` listesine yeni ürünler ekleyebilirsin:

```json
{
  "name": "Siyah elbise",
  "product_url": "https://urun-linki",
  "product_id": "linkteki-p-sonrasi-id",
  "target_price_min": 500,
  "target_price_max": 900,
  "target_sizes": ["M", "L"],
  "color_keywords": ["siyah"]
}
```

Her ürün kendi fiyat aralığı, beden ve renk filtresiyle takip edilir. Bildirim konusu ortak kalır; şartı sağlayan ürünün adı ve linki bildirim içinde gelir.
