"""
ai_parser.py — AI Parsing Katmanı
Her banka ekstresi satırını GPT'ye gönderir ve 25 sütunu doldurur.

KALİBRASYON: Hesap_Hareketleri_22062026.xlsx verisiyle kalibre edildi.
Banka: Ziraat Katılım Bankası (0145 şubesi)
Tespit edilen format grupları:
  GKDA → Döviz Alım işlemleri
  HOHH → Havale Komisyonu / BSMV
  IHMM → İhracat IBKB + TCMB dönüşüm desteği
  KRTM → Komisyon Gecikme Faizi + BSMV
  Vad.Hes → Vadeli Hesap virman/para çekme/kapama
  QNB/EFT → Ziraat Mobil EFT ve FAST işlemleri (tedarikçi/personel)
  Ziraat Katılım → Gelen EFT ödemeleri
"""

import json
import logging
import time
from typing import Optional

import openai

from config import (
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENAI_TIMEOUT,
    OUTPUT_COLUMNS,
)

logger = logging.getLogger(__name__)
openai.api_key = OPENAI_API_KEY


# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM PROMPT
# Bu prompt gerçek veri geldikten sonra ham satır örnekleriyle kalibre edilir.
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """
Sen Ziraat Katılım Bankası ekstre formatını çok iyi bilen bir Türk muhasebe uzmanısın.
Görevin banka ekstresi satırlarını analiz edip yapılandırılmış JSON çıktısı üretmek.

## VERİ FORMATI HAKKINDA ÖNEMLİ BİLGİ
Bu banka ekstresinde 4 sütun var:
  Kolon 1: İşlem tarihi (GG.AA.YYYY formatı)
  Kolon 2: Fiş numarası (F01234 formatı — banka referans no)
  Kolon 3: Ham açıklama (parse edeceğin sütun)
  Kolon 4: 100 veya -100 (GİRİŞ=100, ÇIKIŞ=-100 — gerçek tutar ERP'de eşlenecek)

## TESPİT EDİLEN AÇIKLAMA FORMATLARI

**FORMAT 1 — GKDA (Döviz Alım):**
  `0145GKDA25002033 Ref, Borçlu Müşteri: USD 140.000,00 Kur: 39,64 Döviz Alış İşlemi`
  Yapı: [Ref] Ref, Borçlu Müşteri: [DÖVİZ] [TUTAR] Kur: [KUR] Döviz Alış İşlemi

**FORMAT 2 — HOHH (Havale Komisyonu):**
  `0145HOHH25238389 Referanslı Havale - BSMV Tahsilatı`
  `0145HOHH25238389 Referanslı Havale Komisyonu Tahsilatı`
  Yapı: [Ref] Referanslı Havale [Komisyon/BSMV]

**FORMAT 3 — IHMM (İhracat IBKB):**
  `0145IHMM25000359 Ref. USD 183512 İhracat İBKB Alı - TCMB İhracat Karşılığı TCMB Kuru 40,005`
  `0145IHMM26000099 Ref. USD 250224 İhracat TCMB Döviz Dönüm Destekli Pirim Ödemesi`
  Yapı: [Ref] Ref. [DÖVİZ] [TUTAR] İhracat [İBKB Alı/TCMB Prim]

**FORMAT 4 — KRTM (Komisyon Gecikme Faizi):**
  `0145KRTM25000106 237275,43 Komisyon Gecikme faizi 2,44`  (tutar, oran)
  `0145KRTM25000106 0,12 Komisyon Gecikme faizi BSMV TRY`  (BSMV)
  Yapı: [Ref] [TUTAR] Komisyon Gecikme faizi [ORAN veya BSMV]

**FORMAT 5 — Vadeli Hesap Virman:**
  `145-97826392-5012 No.lu Vds. Hes. Aktararak 97826392-5066 No.lu Vadeli Hesap Kapama`
  `145-97826392-5012 No.lu Vds. Hes.tan 97826392-5041 -Hes.Açılı,Hes. Aç. Tr: 10/07/2025 VB: 10/07/2025 VS: 11/08/2025`
  Yapı: [KAYNAK_HES] No.lu Vds. Hes. [Aktararak/tan] [HEDEF_HES] No.lu Vadeli Hesap [Kapama/Para Çekme]

**FORMAT 6 — EFT/FAST (QNB Bank üzerinden tedarikçi/personel):**
  `QNB BANK A.Ş.//TR550011100000000151243567--LEVARE VSD POMPA SİSTEMLERİ ANONİM ŞİRKETİ/Ziraat Mobil EFT LEVARE VSD POMPA`
  `QNB Bank A.Ş./TR250011100000000152316830-EMRE ÇEK/Levare ÖdemeFAST işlemi`
  Yapı: [BANKA ADI]//[IBAN]--[ALICI ADI]/[AÇIKLAMA] veya [BANKA]/[IBAN]-[AD]/[AÇIKLAMA]FAST işlemi

**FORMAT 7 — Ziraat Katılım Gelen EFT:**
  `Ziraat Katılım Bankası A.Ş./TR310020900001824035000001-ABT ELEKTRİK AYDINLATMA MÜHENDSLİK TAAHHÜT İTHALAT İHRACAT SANA`
  Yapı: [BANKA ADI]/[IBAN]-[GÖNDEREN ADI]

## GÖREV
Sana verilen ham banka ekstresi satırından aşağıdaki alanları çıkar.
Emin olmadığın alanları boş bırak (""), asla uydurma.

## ÇIKTI FORMATI
Sadece geçerli bir JSON objesi döndür. Başka hiçbir şey yazma.

{
  "islem_tipi": "",         // EFT | HAVALE | VİRMAN | SWIFT_GELEN | SWIFT_GİDEN | DÖVİZ_ALIM | DÖVİZ_SATIM | CEK_TAHSILAT | CEK_ODEME | SENET | EFT_KOM | HAVALE_KOM | SWIFT_KOM | HSP_ISLETIM | POS_TAHSILAT | POS_KOM | KART_ODEME | VERGI | SGK | ICRA | FAİZ | VİRMAN | BELİRSİZ
  "islem_yonu": "",         // GİRİŞ | ÇIKIŞ
  "doviz_cinsi": "",        // TRY | USD | EUR | GBP | ... (yoksa boş)
  "doviz_tutari": "",       // Sayısal, nokta ondalık ayracı (yoksa boş)
  "kur": "",                // Uygulanan kur (yoksa boş)
  "aciklama_temiz": "",     // Açıklamanın sade, normalize edilmiş hali
  "karsitaraf_ad": "",      // Gönderen veya alıcının tam adı
  "karsitaraf_iban": "",    // Tam IBAN (TRXX XXXX... formatında)
  "karsitaraf_banka": "",   // IBAN'dan veya metinden tespit edilen banka
  "karsitaraf_ulke": "",    // ISO 2 harfli ülke kodu (SWIFT için)
  "karsitaraf_vkn_tckn": "",// 10 haneli VKN veya 11 haneli TC (yoksa boş)
  "karsitaraf_adres": "",   // Varsa adres/şehir bilgisi
  "fatura_no": "",          // Fatura numarası (F-1042, FAT:1042 gibi)
  "cek_no": "",             // Çek seri numarası
  "banka_ref_no": "",       // Bankanın referans numarası
  "muhasebe_hesabi": "",    // Önerilen hesap kodu (102, 120, 320, 780...)
  "cari_durumu": "",        // CARİ_BELLİ | MUHTEMEL_CARİ | YENİ_CARİ | BELİRSİZ | BANKA_GİDERİ | DEVLET_ÖDEMESİ
  "guven_skoru": 0.0,       // 0.00 ile 1.00 arası, ondalık sayı
  "guven_aciklama": ""      // Neden bu skoru verdin? 1 cümle.
}

## İŞLEM TİPİ TANIMLAMA KURALLARI (Bu Veriye Özgü)
- "DOVIZ_ALIM" → GKDA formatlı satırlar (Döviz Alış İşlemi)
- "IHRACAT_IBKB" → IHMM formatlı İBKB Alı satırları
- "TCMB_PRIM" → IHMM formatlı TCMB Döviz Dönüm Destekli Prim Ödemesi
- "KOM_GEC_FAIZ" → KRTM formatlı Komisyon Gecikme faizi (tutar satırı)
- "KOM_GEC_BSMV" → KRTM formatlı BSMV satırları
- "HAVALE_KOM" → HOHH formatlı Referanslı Havale Komisyonu
- "HAVALE_BSMV" → HOHH formatlı BSMV Tahsilatı
- "VADELI_AKTARIM" → Vadeli hesaplar arası virman (Aktararak)
- "VADELI_PARA_CEKME" → Vadeli hesaptan para çekme (Hes.tan)
- "VADELI_KAPAMA" → Vadeli Hesap Kapama
- "EFT_GIDEN" → QNB Bank üzerinden Ziraat Mobil EFT (ÇIKIŞ)
- "FAST_GIDEN" → FAST işlemi ile giden ödeme (ÇIKIŞ)
- "EFT_GELEN" → Ziraat Katılım üzerinden gelen EFT (GİRİŞ)
- "BELİRSİZ" → Hiçbir kategori uymuyorsa

## MUHASEBE HESAP KODU ÖNERİSİ
- Banka hesabı: 102
- Müşteri alacakları: 120.XXX
- Satıcı borçları: 320.XXX
- Banka komisyon gideri: 780
- Faiz geliri: 642
- Kur farkı gideri/geliri: 656 / 646
- Vergi: 360 (KDV), 361 (stopaj)
- SGK: 361

## CARİ DURUMU KURALLARI (Bu Veriye Özgü)
- GKDA → BANKA_GİDERİ (banka bünyesinde döviz işlemi)
- HOHH (komisyon/BSMV) → BANKA_GİDERİ
- KRTM (gecikme faizi/BSMV) → BANKA_GİDERİ
- IHMM (İBKB/TCMB) → BANKA_GİDERİ (devlet/TCMB işlemi)
- Vadeli Hesap → BANKA_GİDERİ (kendi iç hareketi)
- QNB/EFT ile IBAN ve alıcı adı varsa → CARİ_BELLİ
- FAST işleminde kişi adı + IBAN varsa → CARİ_BELLİ
- Ziraat Katılım gelen EFT + IBAN varsa → CARİ_BELLİ
- IBAN var alıcı adı yok → YENİ_CARİ
- Hiçbir ipucu yoksa → BELİRSİZ

## GÜVEN SKORU
- 0.95 – 1.00: Tüm alanlar kesin, çelişki yok
- 0.80 – 0.94: Çoğu alan dolu, küçük belirsizlik var
- 0.60 – 0.79: Bazı alanlar çıkarılamadı, tahmin var
- 0.00 – 0.59: Açıklama yetersiz, çoğu alan boş

## ÖNEMLI KURALLAR
1. Sadece JSON döndür — başında ``` veya açıklama yazma
2. Emin olmadığında o alanı boş bırak, asla uydurma
3. IBAN'ı standart formata çevir: TR12 3456 7890 1234 5678 9012 34
4. Tutarları noktayı ondalık ayraç olarak kullan (virgül değil)
5. Tarihleri YYYY-MM-DD formatına çevir (mümkünse)
"""

# Gerçek veriden alınan few-shot örnekler:
FEW_SHOT_EXAMPLES = """

## GERÇEK VERİ ÖRNEKLERİ (Hesap_Hareketleri_22062026.xlsx'ten alınmıştır)

### Örnek 1 — Döviz Alım (GKDA)
Girdi: "0145GKDA25002033 Ref, Borçlu Müşteri: USD 140.000,00 Kur: 39,64 Döviz Alış İşlemi"
Yön: 100 (GİRİŞ)
Çıktı:
{
  "islem_tipi": "DOVIZ_ALIM",
  "islem_yonu": "GİRİŞ",
  "doviz_cinsi": "USD",
  "doviz_tutari": "140000.00",
  "kur": "39.64",
  "aciklama_temiz": "Döviz Alış İşlemi",
  "karsitaraf_ad": "",
  "karsitaraf_iban": "",
  "karsitaraf_banka": "Ziraat Katılım Bankası",
  "banka_ref_no": "0145GKDA25002033",
  "muhasebe_hesabi": "102",
  "cari_durumu": "BANKA_GİDERİ",
  "guven_skoru": 0.98,
  "guven_aciklama": "GKDA formatı kesin, döviz tutarı ve kur açık."
}

### Örnek 2 — Havale BSMV (HOHH)
Girdi: "0145HOHH25238389 Referanslı Havale - BSMV Tahsilatı"
Yön: -100 (ÇIKIŞ)
Çıktı:
{
  "islem_tipi": "HAVALE_BSMV",
  "islem_yonu": "ÇIKIŞ",
  "doviz_cinsi": "",
  "doviz_tutari": "",
  "kur": "",
  "aciklama_temiz": "Referanslı Havale BSMV Tahsilatı",
  "karsitaraf_ad": "",
  "karsitaraf_iban": "",
  "banka_ref_no": "0145HOHH25238389",
  "muhasebe_hesabi": "780",
  "cari_durumu": "BANKA_GİDERİ",
  "guven_skoru": 0.99,
  "guven_aciklama": "HOHH+BSMV formatı kesin banka gideridir."
}

### Örnek 3 — İhracat IBKB (IHMM)
Girdi: "0145IHMM25000359 Ref. USD 183512 İhracat İBKB Alı - TCMB İhracat Karşılığı TCMB Kuru 40,005"
Yön: 100 (GİRİŞ)
Çıktı:
{
  "islem_tipi": "IHRACAT_IBKB",
  "islem_yonu": "GİRİŞ",
  "doviz_cinsi": "USD",
  "doviz_tutari": "183512.00",
  "kur": "40.005",
  "aciklama_temiz": "İhracat İBKB Alı TCMB Kuru 40,005",
  "karsitaraf_ad": "TCMB",
  "banka_ref_no": "0145IHMM25000359",
  "muhasebe_hesabi": "102",
  "cari_durumu": "BANKA_GİDERİ",
  "guven_skoru": 0.97,
  "guven_aciklama": "IHMM İBKB formatı, TCMB işlemi."
}

### Örnek 4 — Komisyon Gecikme Faizi (KRTM - tutar)
Girdi: "0145KRTM25000106 237275,43 Komisyon Gecikme faizi 2,44"
Yön: -100 (ÇIKIŞ)
Çıktı:
{
  "islem_tipi": "KOM_GEC_FAIZ",
  "islem_yonu": "ÇIKIŞ",
  "doviz_cinsi": "",
  "aciklama_temiz": "Komisyon Gecikme Faizi - Oran: %2,44 - Anapara: 237.275,43 TL",
  "karsitaraf_ad": "",
  "banka_ref_no": "0145KRTM25000106",
  "muhasebe_hesabi": "780",
  "cari_durumu": "BANKA_GİDERİ",
  "guven_skoru": 0.97,
  "guven_aciklama": "KRTM komisyon gecikme faizi formatı kesin."
}

### Örnek 5 — Komisyon Gecikme BSMV (KRTM - BSMV)
Girdi: "0145KRTM25000106 0,12 Komisyon Gecikme faizi BSMV TRY"
Yön: -100 (ÇIKIŞ)
Çıktı:
{
  "islem_tipi": "KOM_GEC_BSMV",
  "islem_yonu": "ÇIKIŞ",
  "doviz_cinsi": "TRY",
  "aciklama_temiz": "Komisyon Gecikme Faizi BSMV - 0,12 TL",
  "banka_ref_no": "0145KRTM25000106",
  "muhasebe_hesabi": "780",
  "cari_durumu": "BANKA_GİDERİ",
  "guven_skoru": 0.99,
  "guven_aciklama": "KRTM BSMV satırı kesin banka gideri."
}

### Örnek 6 — Vadeli Hesap Kapama (İç Virman)
Girdi: "145-97826392-5012 No.lu Vds. Hes. Aktararak 97826392-5066 No.lu Vadeli Hesap Kapama"
Yön: 100 (GİRİŞ)
Çıktı:
{
  "islem_tipi": "VADELI_KAPAMA",
  "islem_yonu": "GİRİŞ",
  "aciklama_temiz": "Vadeli Hesap Kapama - Kaynak: 145-97826392-5012 → Hedef: 97826392-5066",
  "karsitaraf_ad": "",
  "muhasebe_hesabi": "102",
  "cari_durumu": "BANKA_GİDERİ",
  "guven_skoru": 0.97,
  "guven_aciklama": "Kendi vadeli hesabı kapatma, iç virman."
}

### Örnek 7 — EFT Giden Tedarikçi (QNB/Ziraat Mobil EFT)
Girdi: "QNB BANK A.Ş.//TR550011100000000151243567--LEVARE VSD POMPA SİSTEMLERİ ANONİM ŞİRKETİ/Ziraat Mobil EFT LEVARE VSD POMPA"
Yön: -100 (ÇIKIŞ)
Çıktı:
{
  "islem_tipi": "EFT_GIDEN",
  "islem_yonu": "ÇIKIŞ",
  "aciklama_temiz": "EFT - Levare VSD Pompa Sistemleri A.Ş. ödemesi",
  "karsitaraf_ad": "LEVARE VSD POMPA SİSTEMLERİ ANONİM ŞİRKETİ",
  "karsitaraf_iban": "TR55 0011 1000 0000 0151 2435 67",
  "karsitaraf_banka": "QNB Bank A.Ş.",
  "muhasebe_hesabi": "320",
  "cari_durumu": "CARİ_BELLİ",
  "guven_skoru": 0.95,
  "guven_aciklama": "IBAN ve alıcı firma adı açık, EFT çıkış."
}

### Örnek 8 — FAST Giden Personel (Kişi adı)
Girdi: "QNB Bank A.Ş./TR250011100000000152316830-EMRE ÇEK/Levare ÖdemeFAST işlemi"
Yön: -100 (ÇIKIŞ)
Çıktı:
{
  "islem_tipi": "FAST_GIDEN",
  "islem_yonu": "ÇIKIŞ",
  "aciklama_temiz": "FAST - Emre Çek personel ödemesi",
  "karsitaraf_ad": "EMRE ÇEK",
  "karsitaraf_iban": "TR25 0011 1000 0000 0152 3168 30",
  "karsitaraf_banka": "QNB Bank A.Ş.",
  "muhasebe_hesabi": "335",
  "cari_durumu": "CARİ_BELLİ",
  "guven_skoru": 0.93,
  "guven_aciklama": "FAST kişi adı ve IBAN mevcut, personel ödemesi."
}

### Örnek 9 — EFT Gelen Tedarikçi (Ziraat Katılım)
Girdi: "Ziraat Katılım Bankası A.Ş./TR310020900001824035000001-ABT ELEKTRİK AYDINLATMA MÜHENDSLİK TAAHHÜT İTHALAT İHRACAT SANAY"
Yön: -100 (ÇIKIŞ)
Çıktı:
{
  "islem_tipi": "EFT_GIDEN",
  "islem_yonu": "ÇIKIŞ",
  "aciklama_temiz": "EFT - ABT Elektrik Aydınlatma Mühendislik ödemesi",
  "karsitaraf_ad": "ABT ELEKTRİK AYDINLATMA MÜHENDSLİK TAAHHÜT İTHALAT İHRACAT SANAYİ",
  "karsitaraf_iban": "TR31 0020 9000 0182 4035 0000 01",
  "karsitaraf_banka": "Ziraat Katılım Bankası A.Ş.",
  "muhasebe_hesabi": "320",
  "cari_durumu": "CARİ_BELLİ",
  "guven_skoru": 0.93,
  "guven_aciklama": "IBAN ve alıcı firma adı mevcut, ancak açıklama kısa."
}
"""


class AIParser:
    """
    Tek bir ham banka satırını GPT'ye gönderir,
    standart JSON çıktı alır.
    """

    def __init__(self, use_few_shot: bool = True):
        self.system = SYSTEM_PROMPT
        if use_few_shot:
            self.system += FEW_SHOT_EXAMPLES

    # ─────────────────────────────────────────
    # Tek satır parse
    # ─────────────────────────────────────────
    def parse_row(
        self,
        aciklama: str,
        ek_bilgi: str = "",    # Tarih, tutar gibi ek bağlam
        retry: int = 2,
    ) -> dict:
        """
        Tek bir ham açıklamayı parse eder.
        
        Args:
            aciklama : Ham banka açıklaması
            ek_bilgi : "Tarih: 2026-07-14, Tutar: 47500 TL, Yön: GİRİŞ" gibi
            retry    : Hata durumunda kaç kez tekrar dene
            
        Returns:
            25 alanlı dict
        """
        user_msg = f"Ham açıklama: {aciklama}"
        if ek_bilgi:
            user_msg += f"\nEk bilgi: {ek_bilgi}"

        for attempt in range(retry + 1):
            try:
                response = openai.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": self.system},
                        {"role": "user",   "content": user_msg},
                    ],
                    temperature=0.0,      # Deterministik çıktı
                    timeout=OPENAI_TIMEOUT,
                    response_format={"type": "json_object"},  # GPT-4o destekli
                )
                raw = response.choices[0].message.content
                return self._safe_parse_json(raw, aciklama)

            except openai.RateLimitError:
                wait = 2 ** attempt
                logger.warning(f"Rate limit — {wait}s bekleniyor...")
                time.sleep(wait)
            except openai.APIError as e:
                logger.error(f"API hatası: {e}")
                if attempt == retry:
                    return self._empty_result(aciklama, error=str(e))

        return self._empty_result(aciklama, error="max_retry")

    # ─────────────────────────────────────────
    # Toplu parse (DataFrame'den)
    # ─────────────────────────────────────────
    def parse_dataframe(
        self,
        df,
        aciklama_col: str,
        tarih_col: str   = None,
        tutar_col: str   = None,
        yon_col: str     = None,
        batch_delay: float = 0.3,   # Rate limit için satırlar arası bekleme
    ):
        """
        DataFrame'deki her satırı parse eder.
        Sonuçları orijinal DataFrame ile birleştirip döner.
        """
        import pandas as pd

        results = []
        total   = len(df)

        for i, row in df.iterrows():
            aciklama = str(row.get(aciklama_col, ""))

            # Ek bağlam oluştur
            ek_parcalar = []
            if tarih_col and tarih_col in row:
                ek_parcalar.append(f"Tarih: {row[tarih_col]}")
            if tutar_col and tutar_col in row:
                ek_parcalar.append(f"Tutar: {row[tutar_col]}")
            if yon_col and yon_col in row:
                ek_parcalar.append(f"Yön: {row[yon_col]}")
            ek_bilgi = ", ".join(ek_parcalar)

            logger.info(f"[{i+1}/{total}] Parse ediliyor: {aciklama[:60]}...")
            result = self.parse_row(aciklama, ek_bilgi)
            result["aciklama_ham"] = aciklama   # Ham açıklamayı koru
            results.append(result)

            time.sleep(batch_delay)

        result_df = pd.DataFrame(results)
        return pd.concat(
            [df.reset_index(drop=True), result_df],
            axis=1
        )

    # ─────────────────────────────────────────
    # Yardımcı fonksiyonlar
    # ─────────────────────────────────────────
    @staticmethod
    def _safe_parse_json(raw: str, aciklama: str) -> dict:
        """JSON parse hatalarını yumuşak yakalar."""
        try:
            data = json.loads(raw)
            return data
        except json.JSONDecodeError:
            logger.warning(f"JSON parse hatası. Ham yanıt: {raw[:200]}")
            return AIParser._empty_result(aciklama, error="json_parse")

    @staticmethod
    def _empty_result(aciklama: str, error: str = "") -> dict:
        """Parse başarısız olunca dönen boş şablon."""
        return {col: "" for col in OUTPUT_COLUMNS} | {
            "aciklama_ham": aciklama,
            "guven_skoru": 0.0,
            "cari_durumu": "BELİRSİZ",
            "aksiyon": "MANUEL",
            "guven_aciklama": f"Parse hatası: {error}",
        }
