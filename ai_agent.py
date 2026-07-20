"""
ai_agent.py — AI Agent Modülü (Google Gemini + Simülasyon)
Regex ile çözülemeyen 'BELİRSİZ' satırları Gemini (1.5 Flash) servisine gönderir.
Eğer API key geçersizse veya sınır aşılmışsa Simülasyon (Mock) modu devreye girer.
"""

import json
import logging
from typing import Dict, Optional
import google.generativeai as genai
import os

logger = logging.getLogger(__name__)

# GÜVENLİK GÜNCELLEMESİ: GitHub Push Protection
# API anahtarını asla kod içine açık (hardcoded) yazmıyoruz. Çevre değişkeninden (.env) okuyoruz.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

SYSTEM_PROMPT = """
Sen Ziraat Katılım Bankası ve genel Türk bankacılık ekstre formatlarını çok iyi bilen bir veri ayrıştırma (parsing) asistanısın.
Sana verilen banka ekstresi açıklamasını incele ve aşağıdaki alanları çıkararak SADECE JSON formatında yanıt dön.

{
  "islem_tipi": "",
  "karsitaraf_ad": "",
  "karsitaraf_iban": "",
  "karsitaraf_banka": "",
  "aciklama_temiz": "",
  "cari_durumu": "",
  "muhasebe_hesabi": ""
}
Kurallar:
- Güven skoru vb. ekleme. Sadece JSON objesi döndür.
- Karsitaraf adını bulamıyorsan boş bırak.
"""

def mock_ai_response(aciklama: str) -> Dict:
    """API çalışmazsa sistemin çökmemesi için sahte (simülasyon) cevap üretir."""
    # Basit bir kelime tahmini
    up_acik = aciklama.upper()
    tip = "DIGER"
    cari = "BELİRSİZ"
    hesap = "999"
    
    if "KİRA" in up_acik or "KIRA" in up_acik:
        tip = "KIRA_ODEMESI"
        cari = "CARİ_BELLİ"
        hesap = "770"
    elif "SİGORTA" in up_acik or "SIGORTA" in up_acik:
        tip = "SIGORTA"
        cari = "CARİ_BELLİ"
        hesap = "770"
    elif "A.Ş" in up_acik or "LTD" in up_acik:
        tip = "HAVALE_GIDEN"
        cari = "CARİ_BELLİ"
        hesap = "320"
        
    return {
        "islem_tipi": tip,
        "karsitaraf_ad": "AI_TEST_FİRMA_ADI",
        "karsitaraf_iban": "",
        "karsitaraf_banka": "",
        "aciklama_temiz": f"[AI_SIM] {aciklama[:40]}...",
        "cari_durumu": cari,
        "muhasebe_hesabi": hesap
    }

def parse_with_ai(aciklama: str, islem_yonu: str) -> Optional[Dict]:
    """Gemini API'ye istek atar, hata olursa Mock Mode çalışır."""
    if not GEMINI_API_KEY:
        return mock_ai_response(aciklama)
        
    try:
        model = genai.GenerativeModel(
            'gemini-1.5-flash',
            system_instruction=SYSTEM_PROMPT,
            generation_config={"response_mime_type": "application/json", "temperature": 0.1}
        )
        
        prompt = f"Yön: {islem_yonu} | Açıklama: {aciklama}"
        response = model.generate_content(prompt)
        
        if response.text:
            result_json = response.text.replace("```json", "").replace("```", "").strip()
            return json.loads(result_json)
        else:
            return mock_ai_response(aciklama)
            
    except Exception as e:
        logger.error(f"Gemini API hatası: {e}")
        # Hata anında Simülasyon'a düş
        return mock_ai_response(aciklama)
