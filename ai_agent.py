"""
ai_agent.py — AI Agent Modülü (Google Gemini + Simülasyon)
Regex ile çözülemeyen 'BELİRSİZ' satırları Gemini (1.5 Flash) servisine gönderir.
Eğer API key geçersizse veya sınır aşılmışsa Simülasyon (Mock) modu devreye girer.
"""

import json
import logging
import os
import time
import random
from typing import Dict, Optional
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
is_first_call = True  # İlk çağrıyı takip etmek için global değişken

# GÜVENLİK GÜNCELLEMESİ: GitHub Push Protection
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

# 1. PROMPT REPOSITORY (Prompt dosyasından dinamik okuma)
PROMPT_FILE_PATH = os.path.join(os.path.dirname(__file__), "prompts", "transaction_parser_v1.md")

def get_system_prompt() -> str:
    """Sistem promptunu v1.md dosyasından yükler."""
    if os.path.exists(PROMPT_FILE_PATH):
        with open(PROMPT_FILE_PATH, "r", encoding="utf-8") as f:
            return f.read()
    return "Lütfen çıktıyı sadece JSON olarak verin."

def mock_ai_response(aciklama: str, fallback_reason: str = "Bilinmeyen Neden") -> Dict:
    """API çalışmazsa sistemin çökmemesi için sahte (simülasyon) cevap üretir. Sessiz fallback olmaması için sebebi (reason) kaydeder."""
    up_acik = aciklama.upper()
    tip = "DIGER"
    cari = "BELİRSİZ"
    hesap = "999"
    explanation = f"Fallback Reason: {fallback_reason}"
    confidence = 50
    
    if "KİRA" in up_acik or "KIRA" in up_acik:
        tip = "MASRAF"
        cari = "CARİ_BELLİ"
        hesap = "770"
        explanation = "Kira kelimesi bulunduğu için Masraf olarak sınıflandırıldı."
        confidence = 94
    elif "SİGORTA" in up_acik or "SIGORTA" in up_acik:
        tip = "MASRAF"
        cari = "CARİ_BELLİ"
        hesap = "770"
        explanation = "Sigorta poliçesi ödemesi tespit edildi."
        confidence = 92
    elif "A.Ş" in up_acik or "LTD" in up_acik:
        tip = "HAVALE"
        cari = "CARİ_BELLİ"
        hesap = "320"
        explanation = "Anonim/Limited şirket ibaresi (Tüzel kişi) tespit edildi."
        confidence = 88
        
    return {
        "islem_tipi": tip,
        "karsitaraf_ad": "MOCK_FIRMA",
        "karsitaraf_iban": "",
        "karsitaraf_banka": "",
        "aciklama_temiz": f"[AI_SIM] {aciklama[:40]}...",
        "cari_durumu": cari,
        "muhasebe_hesabi": hesap,
        "confidence_score": confidence,
        "explanation": explanation
    }

def parse_with_ai(aciklama: str, islem_yonu: str, max_retries: int = 3) -> Optional[Dict]:
    """Gemini API'ye istek atar, limit aşımında bekleyip tekrar dener."""
    global is_first_call
    
    if not GEMINI_API_KEY or client is None:
        print("Gemini API Error: Missing API Key in environment.")
        return mock_ai_response(aciklama, fallback_reason="Invalid/Missing API Key")
        
    prompt = f"Yön: {islem_yonu} | Açıklama: {aciklama}"
    
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=get_system_prompt(),
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )
            
            if is_first_call:
                print("\n=== İLK İŞLEM İÇİN GEMINI RAW RESPONSE ===")
                print(f"Prompt: {prompt}")
                print(f"Response: {response.text if hasattr(response, 'text') else 'NO TEXT'}")
                print("==========================================\n")
                is_first_call = False
                
            if response.text:
                result_json = response.text.replace("```json", "").replace("```", "").strip()
                return json.loads(result_json)
            else:
                print("Gemini API Error: Empty text in response.")
                return mock_ai_response(aciklama, fallback_reason="Empty AI Response")
                
        except json.JSONDecodeError as e:
            print(f"Gemini API Error: JSON Parse Error -> {e}")
            return mock_ai_response(aciklama, fallback_reason=f"JSON Parse Error: {str(e)}")
        except Exception as e:
            err_str = str(e)
            print(f"Gemini API Error (attempt {attempt+1}): {err_str}")
            logger.error(f"Gemini API hatası: {e}")
            
            if "RESOURCE_EXHAUSTED" in err_str or "429" in err_str:
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                time.sleep(wait_time)
                continue
            else:
                return mock_ai_response(aciklama, fallback_reason=err_str)
                
    return mock_ai_response(aciklama, fallback_reason="Rate limit: max retries exceeded")
