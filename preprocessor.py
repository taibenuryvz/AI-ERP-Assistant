"""
preprocessor.py — Ön İşleme Katmanı
Ham Excel verisini AI'ya göndermeden önce temizler ve hazırlar.
"""

import re
import pandas as pd
import logging
from typing import Tuple

from config import BANKA_GIDER_KEYWORDS, DEVLET_ODEME_KEYWORDS, BANKA_GIDERI, DEVLET_ODEME

logger = logging.getLogger(__name__)


class Preprocessor:
    """
    Ham DataFrame'i alır, satırları temizler ve
    AI'ya gönderilmeye hazır hale getirir.
    
    Görevler:
      1. Boş / anlamsız satırları sil
      2. String değerleri normalize et
      3. Kural tabanlı hızlı ön sınıflama (banka gideri mi?)
      4. AI'ya gönderilecek ham_aciklama sütununu belirle
    """

    def __init__(
        self,
        aciklama_sutunu: str,    # Ham açıklamanın bulunduğu sütun adı
                                 # → Sen verini atınca bu parametre netleşir
        tutar_sutunu: str = None,
        tarih_sutunu: str = None,
    ):
        self.aciklama_sutunu = aciklama_sutunu
        self.tutar_sutunu    = tutar_sutunu
        self.tarih_sutunu    = tarih_sutunu

    # ─────────────────────────────────────────
    # Ana giriş noktası
    # ─────────────────────────────────────────
    def process(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, dict]:
        """
        DataFrame'i temizler ve ön sınıflama yapar.
        
        Returns:
            df_clean  : Temizlenmiş DataFrame
            stats     : İstatistikler (kaç satır silindi, kaç öne sınıflandı...)
        """
        stats = {"toplam": len(df), "silinen": 0, "on_sinif": 0}

        df = df.copy()
        df = self._drop_empty_rows(df, stats)
        df = self._clean_strings(df)
        df = self._quick_classify(df, stats)

        logger.info(
            f"Preprocessing: {stats['toplam']} → {len(df)} satır "
            f"({stats['silinen']} silindi, {stats['on_sinif']} öne sınıflandı)"
        )
        return df, stats

    # ─────────────────────────────────────────
    # 1. Boş satır temizliği
    # ─────────────────────────────────────────
    def _drop_empty_rows(self, df: pd.DataFrame, stats: dict) -> pd.DataFrame:
        """
        Açıklama sütunu boş olan veya sadece başlık/özet
        satırı gibi görünen satırları kaldırır.
        """
        before = len(df)

        # Açıklama sütunu yoksa veya tamamen boşsa
        if self.aciklama_sutunu in df.columns:
            df = df[df[self.aciklama_sutunu].str.strip() != ""]
            df = df[df[self.aciklama_sutunu].notna()]

        # Tüm sütunlar boş olan satırlar
        df = df.dropna(how="all")

        stats["silinen"] = before - len(df)
        return df.reset_index(drop=True)

    # ─────────────────────────────────────────
    # 2. String normalizasyonu
    # ─────────────────────────────────────────
    @staticmethod
    def _clean_strings(df: pd.DataFrame) -> pd.DataFrame:
        """
        Tüm string sütunlarında:
          - Baş/son boşlukları temizle
          - Çoklu boşlukları tekile indir
          - \r \n gibi kontrol karakterlerini temizle
        """
        for col in df.select_dtypes(include="object").columns:
            df[col] = (
                df[col]
                .astype(str)
                .str.strip()
                .str.replace(r"\s+", " ", regex=True)
                .str.replace(r"[\r\n\t]", " ", regex=True)
            )
        return df

    # ─────────────────────────────────────────
    # 3. Kural tabanlı hızlı ön sınıflama
    # ─────────────────────────────────────────
    def _quick_classify(self, df: pd.DataFrame, stats: dict) -> pd.DataFrame:
        """
        Banka komisyonları ve devlet ödemeleri gibi
        kesin kalıpları AI'ya göndermeden önce işaretle.
        Bu satırlar için AI çağrısı yapılmayabilir (maliyet tasarrufu).
        """
        if self.aciklama_sutunu not in df.columns:
            return df

        df["on_sinif"] = ""

        for idx, row in df.iterrows():
            aciklama = str(row[self.aciklama_sutunu]).upper()

            # Banka gideri mi?
            if any(kw in aciklama for kw in BANKA_GIDER_KEYWORDS):
                df.at[idx, "on_sinif"] = BANKA_GIDERI
                stats["on_sinif"] += 1
                continue

            # Devlet ödemesi mi?
            if any(kw in aciklama for kw in DEVLET_ODEME_KEYWORDS):
                df.at[idx, "on_sinif"] = DEVLET_ODEME
                stats["on_sinif"] += 1

        return df

    # ─────────────────────────────────────────
    # 4. AI'ya gönderilecek satırları filtrele
    # ─────────────────────────────────────────
    def get_ai_rows(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Ön sınıflamada kesin sonuç alınamayan satırları döner.
        Bunlar AI pipeline'ına gönderilecek.
        
        Not: İstersen ön sınıflı satırları da AI'ya göndererek
        doğrulama yaptırabilirsin. Bu bir konfigürasyon kararı.
        """
        return df[df["on_sinif"] == ""].copy()

    def get_preclassified_rows(self, df: pd.DataFrame) -> pd.DataFrame:
        """Kural tabanlı ön sınıflama yapılmış satırlar."""
        return df[df["on_sinif"] != ""].copy()
