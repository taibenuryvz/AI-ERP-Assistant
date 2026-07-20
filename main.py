"""
main.py — Pipeline Orkestrasyonu
Tüm modülleri bir araya getirir ve uçtan uca çalıştırır.

Kullanım:
    python main.py --file ekstre.xlsx --aciklama_col "Açıklama" --erp excel
"""

import argparse
import logging
import sys
from pathlib import Path

from file_reader   import FileReader
from preprocessor  import Preprocessor
from ai_parser     import AIParser
from confidence    import enrich_with_action, summary_stats
from erp_adapter   import get_adapter

# ─────────────────────────────────────────
# Loglama
# ─────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("parser.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("main")


# ─────────────────────────────────────────
# Ana pipeline
# ─────────────────────────────────────────
def run_pipeline(
    file_path    : str,
    aciklama_col : str,
    tarih_col    : str  = None,
    tutar_col    : str  = None,
    yon_col      : str  = None,
    erp          : str  = "excel",
    output_dir   : str  = "output",
    dry_run      : bool = False,   # True → AI çağrısı yapma, test için
):
    logger.info("=" * 60)
    logger.info(f"Pipeline başladı: {Path(file_path).name}")
    logger.info("=" * 60)

    # ── 1. Dosya Okuma ────────────────────────────────────────
    logger.info("[1/5] Dosya okunuyor...")
    reader = FileReader(file_path)
    df = reader.read()
    reader.show_columns()

    # ── 2. Ön İşleme ─────────────────────────────────────────
    logger.info("[2/5] Ön işleme...")
    prep = Preprocessor(
        aciklama_sutunu=aciklama_col,
        tutar_sutunu=tutar_col,
        tarih_sutunu=tarih_col,
    )
    df_clean, stats = prep.process(df)
    logger.info(f"Ön işleme tamamlandı: {stats}")

    # Ön sınıflananları ayır
    df_preclassified = prep.get_preclassified_rows(df_clean)
    df_for_ai        = prep.get_ai_rows(df_clean)

    logger.info(
        f"  Ön sınıflanan (AI'ya gönderilmeyecek): {len(df_preclassified)} satır"
        f"\n  AI'ya gönderilecek: {len(df_for_ai)} satır"
    )

    # ── 3. AI Parsing ────────────────────────────────────────
    logger.info("[3/5] AI parsing başlıyor...")
    ai_results = []

    if not dry_run and len(df_for_ai) > 0:
        parser = AIParser(use_few_shot=True)
        df_parsed = parser.parse_dataframe(
            df_for_ai,
            aciklama_col=aciklama_col,
            tarih_col=tarih_col,
            tutar_col=tutar_col,
            yon_col=yon_col,
        )
        ai_results = df_parsed.to_dict(orient="records")
    elif dry_run:
        logger.info("DRY RUN modu — AI çağrısı atlandı.")
        # Boş sonuçlar oluştur (test için)
        ai_results = [
            {"aciklama_ham": row[aciklama_col], "guven_skoru": 0.99,
             "cari_durumu": "TEST", "aksiyon": "OTO_AKTAR"}
            for _, row in df_for_ai.iterrows()
        ]

    # Ön sınıflamalı satırları ekle
    for _, row in df_preclassified.iterrows():
        pre_result = row.to_dict()
        pre_result["cari_durumu"] = row.get("on_sinif", "BELİRSİZ")
        pre_result["guven_skoru"] = 0.99
        pre_result["aksiyon"]     = "OTO_AKTAR"
        ai_results.append(pre_result)

    # ── 4. Aksiyon Zenginleştirme ─────────────────────────────
    logger.info("[4/5] Aksiyon atanıyor...")
    final_results = [enrich_with_action(r) for r in ai_results]

    # ── 5. ERP Çıktısı ───────────────────────────────────────
    logger.info(f"[5/5] ERP çıktısı: {erp}...")
    adapter     = get_adapter(erp, output_dir)
    output_path = adapter.export(final_results)

    # ── Özet ─────────────────────────────────────────────────
    stats_out = summary_stats(final_results)
    logger.info("=" * 60)
    logger.info("PIPELINE TAMAMLANDI")
    logger.info(f"  Toplam satır  : {stats_out['toplam']}")
    logger.info(f"  Oto aktar     : {stats_out['oto_aktar']} ({stats_out['oto_oran']})")
    logger.info(f"  Onay bekle    : {stats_out['onay_bekle']}")
    logger.info(f"  Manuel        : {stats_out['manuel']}")
    logger.info(f"  Ort. güven    : {stats_out['avg_guven']}")
    logger.info(f"  Çıktı dosyası : {output_path}")
    logger.info("=" * 60)

    return final_results, output_path


# ─────────────────────────────────────────
# CLI
# ─────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Banka Ekstresi AI Parser")
    parser.add_argument("--file",         required=True,  help="Excel/CSV dosya yolu")
    parser.add_argument("--aciklama_col", required=True,  help="Ham açıklamanın bulunduğu sütun adı")
    parser.add_argument("--tarih_col",    default=None,   help="Tarih sütunu adı")
    parser.add_argument("--tutar_col",    default=None,   help="Tutar sütunu adı")
    parser.add_argument("--yon_col",      default=None,   help="Giriş/Çıkış sütunu adı")
    parser.add_argument("--erp",          default="excel",help="Çıktı formatı: excel | 1c | netsis | json")
    parser.add_argument("--output_dir",   default="output")
    parser.add_argument("--dry_run",      action="store_true", help="AI çağrısı yapmadan test et")
    args = parser.parse_args()

    run_pipeline(
        file_path    = args.file,
        aciklama_col = args.aciklama_col,
        tarih_col    = args.tarih_col,
        tutar_col    = args.tutar_col,
        yon_col      = args.yon_col,
        erp          = args.erp,
        output_dir   = args.output_dir,
        dry_run      = args.dry_run,
    )
