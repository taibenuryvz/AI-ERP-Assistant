"""
confidence.py — Güven Skoru ve Aksiyon Yönlendirme
"""

from config import (
    CONFIDENCE_AUTO,
    CONFIDENCE_REVIEW,
    AKSIYON_OTO,
    AKSIYON_ONAY,
    AKSIYON_MANUEL,
)


def determine_action(row: dict) -> str:
    """
    Güven skoruna göre aksiyonu belirler.
    
    >= CONFIDENCE_AUTO  (0.90) → OTO_AKTAR
    >= CONFIDENCE_REVIEW (0.70) → ONAY_BEKLE
    <  CONFIDENCE_REVIEW       → MANUEL
    """
    try:
        score = float(row.get("guven_skoru", 0))
    except (TypeError, ValueError):
        score = 0.0

    if score >= CONFIDENCE_AUTO:
        return AKSIYON_OTO
    elif score >= CONFIDENCE_REVIEW:
        return AKSIYON_ONAY
    else:
        return AKSIYON_MANUEL


def enrich_with_action(result: dict) -> dict:
    """
    AI çıktısına aksiyon alanını ekler.
    Banka giderleri doğrudan OTO_AKTAR alır.
    """
    cari = result.get("cari_durumu", "")
    if cari in ("BANKA_GİDERİ", "DEVLET_ÖDEMESİ"):
        result["aksiyon"] = AKSIYON_OTO
    else:
        result["aksiyon"] = determine_action(result)
    return result


def summary_stats(results: list[dict]) -> dict:
    """
    Toplu parse sonrası özet istatistik üretir.
    Dashboard'a ve log'a yazılacak.
    """
    total   = len(results)
    oto     = sum(1 for r in results if r.get("aksiyon") == AKSIYON_OTO)
    onay    = sum(1 for r in results if r.get("aksiyon") == AKSIYON_ONAY)
    manuel  = sum(1 for r in results if r.get("aksiyon") == AKSIYON_MANUEL)
    avg_score = (
        sum(float(r.get("guven_skoru", 0)) for r in results) / total
        if total else 0
    )

    return {
        "toplam"        : total,
        "oto_aktar"     : oto,
        "onay_bekle"    : onay,
        "manuel"        : manuel,
        "oto_oran"      : f"%{100 * oto / total:.1f}" if total else "—",
        "avg_guven"     : f"%{avg_score * 100:.1f}",
    }
