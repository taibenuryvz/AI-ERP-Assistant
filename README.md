# AI Banka Ekstresi Parser

Banka ekstresindeki tek sütuna sıkışmış ham açıklamaları
yapay zeka ile 25 yapılandırılmış sütuna dönüştüren sistem.

---

## Kurulum

```bash
cd bank_parser
pip install -r requirements.txt
```

## Ortam Değişkeni

```bash
# .env dosyası oluştur veya doğrudan ayarla
OPENAI_API_KEY=sk-...buraya_keyi_yaz...
```

## Çalıştırma

### Web Arayüzü (Önerilen)
```bash
streamlit run app.py
```
Tarayıcıda `http://localhost:8501` açılır.
Dosyayı yükle → Sütunu seç → Parse Et → İndir.

### Komut Satırı
```bash
# Basit kullanım
python main.py --file ekstre.xlsx --aciklama_col "Açıklama"

# Tüm parametrelerle
python main.py \
  --file ekstre.xlsx \
  --aciklama_col "Açıklama" \
  --tarih_col "Tarih" \
  --tutar_col "Tutar" \
  --yon_col "İşlem Yönü" \
  --erp excel \
  --output_dir output

# API çağrısı yapmadan test et
python main.py --file ekstre.xlsx --aciklama_col "Açıklama" --dry_run
```

---

## Dosya Yapısı

```
bank_parser/
├── config.py          ← Merkezi konfigürasyon (eşikler, sütunlar)
├── file_reader.py     ← Excel/CSV okuma (PDF ileride)
├── preprocessor.py    ← Temizlik + kural tabanlı ön sınıflama
├── ai_parser.py       ← GPT entegrasyonu + sistem prompt
├── confidence.py      ← Güven skoru → Aksiyon yönlendirme
├── erp_adapter.py     ← ERP çıktı adaptörleri (Excel/1C/Netsis/JSON)
├── main.py            ← Pipeline orkestrasyonu + CLI
├── app.py             ← Streamlit web arayüzü
└── requirements.txt
```

## Sütun Eşikleri (config.py'den değiştirilebilir)

| Güven Skoru | Aksiyon |
|-------------|---------|
| >= %90 | Otomatik aktar |
| %70 – %89 | Dashboard'a düşür, onay bekle |
| < %70 | Manuel inceleme |

## ERP Agnostic Çıktı

```python
# İstediğin ERP için adaptör seç
from erp_adapter import get_adapter

adapter = get_adapter("excel")   # veya "1c", "netsis", "json"
adapter.export(results)
```

---

## Sonraki Adım

Sen gerçek banka ekstresi verilerini (20-30 satır ham açıklama) paylaşınca:
1. `ai_parser.py` içindeki `FEW_SHOT_EXAMPLES` bölümü gerçek örneklerle doldurulacak
2. Sütun isimleri senin ekstrenin gerçek sütun adlarına kalibre edilecek
3. Prompt Türkiye'nin o bankasına özgü formatlar için ince ayar yapılacak
