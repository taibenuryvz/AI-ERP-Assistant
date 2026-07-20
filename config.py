"""
config.py — Merkezi Konfigürasyon
Banka Ekstresi AI Parser Sistemi
"""

import os

# ─────────────────────────────────────────
# OpenAI API
# ─────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "sk-...buraya_api_keyi_yaz...")
OPENAI_MODEL   = "gpt-4o"          # gpt-4o-mini ile maliyet düşürülebilir
OPENAI_TIMEOUT = 30                # saniye

# ─────────────────────────────────────────
# Güven Skoru Eşikleri
# ─────────────────────────────────────────
CONFIDENCE_AUTO   = 0.90   # >= bu → otomatik aktar
CONFIDENCE_REVIEW = 0.70   # >= bu → onay bekle
                           # <  bu → manuel inceleme

# ─────────────────────────────────────────
# Cari Durumu Etiketleri
# ─────────────────────────────────────────
CARI_BELLI      = "CARİ_BELLİ"
CARI_MUHTEMEL   = "MUHTEMEL_CARİ"
CARI_YENİ       = "YENİ_CARİ"
CARI_BELIRSIZ   = "BELİRSİZ"
BANKA_GIDERI    = "BANKA_GİDERİ"
DEVLET_ODEME    = "DEVLET_ÖDEMESİ"

# ─────────────────────────────────────────
# Aksiyon Etiketleri
# ─────────────────────────────────────────
AKSIYON_OTO     = "OTO_AKTAR"
AKSIYON_ONAY    = "ONAY_BEKLE"
AKSIYON_MANUEL  = "MANUEL"

# ─────────────────────────────────────────
# 25 Çıktı Sütunu (standart şema)
# ─────────────────────────────────────────
OUTPUT_COLUMNS = [
    # Zaman
    "islem_tarihi",
    "valor_tarihi",
    # İşlem kimliği
    "islem_tipi",          # EFT, SWIFT, CEK, KOMISYON, POS ...
    "islem_yonu",          # GİRİŞ / ÇIKIŞ
    # Tutarlar
    "tutar_tl",
    "bakiye",
    "doviz_cinsi",         # USD, EUR, — (yoksa boş)
    "doviz_tutari",
    "kur",
    # Ham veri
    "aciklama_ham",        # Orijinal satır — hiç değiştirilmez
    "aciklama_temiz",      # AI'nın normalize ettiği
    # Karşı taraf
    "karsitaraf_ad",
    "karsitaraf_iban",
    "karsitaraf_banka",    # IBAN'dan çıkarılır (TR prefix'e göre)
    "karsitaraf_ulke",     # SWIFT için
    "karsitaraf_vkn_tckn",
    "karsitaraf_adres",
    # Referanslar
    "fatura_no",
    "cek_no",
    "banka_ref_no",
    "erp_ref_no",          # Boş başlar — ERP eşleştirme sonrası dolar
    # Sınıflama
    "muhasebe_hesabi",     # Önerilen hesap kodu
    "cari_durumu",         # CARİ_BELLİ / BELİRSİZ / BANKA_GİDERİ ...
    "guven_skoru",         # 0.00 – 1.00
    "aksiyon",             # OTO_AKTAR / ONAY_BEKLE / MANUEL
]

# ─────────────────────────────────────────
# Dosya Kaynağı
# ─────────────────────────────────────────
SUPPORTED_FORMATS = [".xlsx", ".xls", ".csv"]  # PDF ileride eklenecek
WATCH_FOLDER      = r"Z:\Mutabakat\Gelenler"   # Watchdog için ağ klasörü

# ─────────────────────────────────────────
# Banka Komisyon Anahtar Kelimeleri
# (Cari Tespiti — kural tabanlı hızlı filtre)
# ─────────────────────────────────────────
BANKA_GIDER_KEYWORDS = [
    # Gerçek Ziraat Katılım Bankası kalıpları
    "GKDA",             # Döviz Alım
    "HOHH",             # Havale Komisyonu / BSMV
    "IHMM",             # İhracat IBKB / TCMB
    "KRTM",             # Komisyon Gecikme Faizi
    "VDS. HES",         # Vadeli Hesap
    "VADELİ HESAP",     # Vadeli Hesap Kapama
    "VADELI HESAP",
    "PARA ÇEKME",
    "BSMV",
    # Genel kalıplar
    "KOM", "KOMİSYON", "KOMISYON", "FAİZ", "FAIZ",
    "ÜCRT", "ÜCRET", "HSP İŞLT", "HESAP İŞLT",
    "DEKONT", "SWIFT KOM", "STOPAJ", "MUNZAM",
]

DEVLET_ODEME_KEYWORDS = [
    "VERGİ", "VERGI", "KDV", "SGK", "PRİM", "PRIM",
    "İCRA", "ICRA", "BÜTÇE", "HAZİNE", "GİB",
    "GELİR İD", "KURUMLAR", "DAMGA",
    "TCMB", "TCMB KURU",  # TCMB işlemleri
]
