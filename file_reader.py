"""
file_reader.py — Dosya Okuma Katmanı
Desteklenen: Excel (.xlsx, .xls), CSV
Genişletilebilir: PDF desteği ileride buraya eklenir
"""

import pandas as pd
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class FileReader:
    """
    Farklı dosya formatlarını okuyup standart bir
    DataFrame'e dönüştürür.
    
    Kullanım:
        reader = FileReader("ekstre.xlsx")
        df = reader.read()
    """

    def __init__(self, file_path: str, sheet_name: Optional[str] = None):
        self.path      = Path(file_path)
        self.sheet     = sheet_name   # None → ilk sayfa
        self.extension = self.path.suffix.lower()
        self._raw_df: Optional[pd.DataFrame] = None

    # ─────────────────────────────────────────
    # Ana giriş noktası
    # ─────────────────────────────────────────
    def read(self) -> pd.DataFrame:
        """
        Dosyayı okur ve ham DataFrame döner.
        Sütun isimlerini normalize eder.
        """
        if self.extension in (".xlsx", ".xls"):
            df = self._read_excel()
        elif self.extension == ".csv":
            df = self._read_csv()
        else:
            raise ValueError(
                f"Desteklenmeyen format: {self.extension}. "
                f"Desteklenenler: .xlsx, .xls, .csv"
            )

        df = self._normalize_columns(df)
        self._raw_df = df
        logger.info(f"Dosya okundu: {self.path.name} — {len(df)} satır")
        return df

    # ─────────────────────────────────────────
    # Format okuyucular
    # ─────────────────────────────────────────
    def _read_excel(self) -> pd.DataFrame:
        try:
            # Önce başlıkla dene
            df = pd.read_excel(
                self.path,
                sheet_name=self.sheet or 0,
                dtype=str,
                keep_default_na=False,
            )
            # İlk sütun tarih formatına benziyorsa (GG.AA.YYYY) başlık yok demektir
            first_col = str(df.columns[0]).strip()
            import re
            if re.match(r"\d{2}\.\d{2}\.\d{4}", first_col):
                # Başlık satırı yok — header=None ile tekrar oku
                df = pd.read_excel(
                    self.path,
                    sheet_name=self.sheet or 0,
                    dtype=str,
                    keep_default_na=False,
                    header=None,
                )
                # Bu dosyaya özel standart kolon adları
                col_count = len(df.columns)
                default_names = ["islem_tarihi", "fis_no", "aciklama", "yon"]
                df.columns = default_names[:col_count] + [f"sutun_{i}" for i in range(col_count - len(default_names))]
                logger.info("Başlıksız Excel tespit edildi — standart kolon adları atandı.")
            return df
        except Exception as e:
            logger.error(f"Excel okuma hatası: {e}")
            raise

    def _read_csv(self) -> pd.DataFrame:
        # Encoding'i otomatik dene
        for enc in ["utf-8", "utf-8-sig", "cp1254", "latin-1"]:
            try:
                df = pd.read_csv(
                    self.path,
                    dtype=str,
                    encoding=enc,
                    sep=None,       # Ayraç otomatik tespit
                    engine="python",
                    keep_default_na=False,
                )
                logger.info(f"CSV encoding: {enc}")
                return df
            except UnicodeDecodeError:
                continue
        raise ValueError("CSV encoding tespit edilemedi.")

    # ─────────────────────────────────────────
    # Sütun adı normalizasyonu
    # ─────────────────────────────────────────
    @staticmethod
    def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
        """
        Sütun adlarını küçük harfe çevirir, boşlukları alt çizgiye dönüştürür.
        Banka ekstrelerinde sütun isimleri bankadan bankaya farklı olabileceği
        için bu normalizasyon kritik.
        
        Örnek:
          "İşlem Tarihi"  → "islem_tarihi"
          "Alacak Tutarı" → "alacak_tutari"
        """
        tr_map = str.maketrans("ğĞıİöÖüÜşŞçÇ", "gGiIoOuUsScC")

        def clean(col: str) -> str:
            col = str(col).strip()
            col = col.translate(tr_map)
            col = col.lower()
            col = col.replace(" ", "_").replace("-", "_")
            return col

        df.columns = [clean(c) for c in df.columns]
        return df

    # ─────────────────────────────────────────
    # Yardımcı: Sütun haritası görüntüle
    # ─────────────────────────────────────────
    def show_columns(self) -> None:
        """
        Dosyadaki mevcut sütunları listeler.
        Hangi sütunun ham açıklamayı içerdiğini bulmak için kullanılır.
        """
        if self._raw_df is None:
            self.read()
        print("\n=== DOSYA SÜTUNLARI ===")
        for i, col in enumerate(self._raw_df.columns):
            sample = self._raw_df[col].iloc[0] if len(self._raw_df) > 0 else "—"
            print(f"  [{i:02d}] {col:<30} | Örnek: {str(sample)[:60]}")
        print(f"\nToplam: {len(self._raw_df)} satır\n")


# ─────────────────────────────────────────
# TODO: PDF Desteği (ileride eklenecek)
# ─────────────────────────────────────────
# class PDFReader:
#     def read(self) -> pd.DataFrame:
#         # pdfplumber veya camelot ile tablo çıkarımı
#         pass
