import streamlit as st
import pandas as pd
import io
import time
from parse_ekstre import veri_oku, satir_parse_et

st.set_page_config(page_title="AI Bank Reconciliation", page_icon="🏦", layout="wide")

st.title("🏦 AI Bank Statement Parser (Etap 1 Test Arayüzü)")
st.markdown("Bu arayüz, banka ekstrelerini AI destekli ayrıştırma (parsing) motorundan geçirerek standart yapılandırılmış verilere (Canonical Data Model) dönüştürür. **Regex** ve **Gemini AI** birlikte çalışır.")

uploaded_file = st.file_uploader("Banka Ekstresi Excel Dosyasını Yükleyin", type=["xlsx", "xls"])

if uploaded_file is not None:
    # Dosyayı oku
    try:
        df, mapping_report = veri_oku(uploaded_file)
        st.success(f"✅ Dosya başarıyla yüklendi! Toplam **{len(df)}** satır tespit edildi.")
        
        with st.expander("📊 Column Mapping Report (Bank Agnostic)", expanded=True):
            st.code(mapping_report, language="text")
            
        st.subheader("1. Ham Veri Önizlemesi")
        st.dataframe(df.head(5))
        
        if st.button("🚀 AI ile Parse Et (Analizi Başlat)", type="primary"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            sonuclar = []
            total_rows = len(df)
            
            start_time = time.time()
            for i, row in df.iterrows():
                # Streamlit UI'ı bloke etmemesi için her 10 adımda bir UI güncelle
                if i % max(1, total_rows // 100) == 0:
                    progress_bar.progress((i + 1) / total_rows)
                    status_text.text(f"İşleniyor: {i + 1} / {total_rows} satır...")
                
                parsed = satir_parse_et(str(row.get("aciklama_ham", "")), str(row.get("islem_yonu", "")))
                sonuclar.append(parsed)
                time.sleep(1.5)  # Free tier RPM limitini aşmamak için
            
            # İşlem bitti
            progress_bar.progress(1.0)
            elapsed_time = time.time() - start_time
            status_text.text(f"🎉 İşlem {elapsed_time:.1f} saniyede tamamlandı!")
            
            # Birleştir
            df_parsed = pd.DataFrame(sonuclar)
            df_final = pd.concat([
                df.reset_index(drop=True),
                df_parsed.reset_index(drop=True)
            ], axis=1)
            
            st.subheader("2. AI Çıktısı (Parsed Excel)")
            
            # İstatistikleri Göster (Transaction Coverage)
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**İşlem Tipi (Transaction) Dağılımı**")
                st.dataframe(df_final["islem_tipi"].value_counts().reset_index())
            with col2:
                st.markdown("**Güven Skoru (Confidence Score) Dağılımı**")
                # Confidence score sayısal ortalamasını göster
                df_final["confidence_score"] = pd.to_numeric(df_final["confidence_score"], errors='coerce')
                st.metric(label="Ortalama Güven Skoru", value=f"% {df_final['confidence_score'].mean():.1f}")
                st.markdown("**XAI (Explainable AI) Örneği**")
                st.dataframe(df_final[["islem_tipi", "confidence_score", "explanation"]].head(10))

            # Tam Tablo
            st.dataframe(df_final)
            
            # İndirme Butonu (Memory üzerinden Excel yarat)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_final.to_excel(writer, index=False, sheet_name='Parsed_Data')
            processed_data = output.getvalue()
            
            st.download_button(
                label="📥 Parsed Excel Dosyasını İndir",
                data=processed_data,
                file_name="Hesap_Hareketleri_PARSED.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )

    except Exception as e:
        st.error(f"Dosya okunurken hata oluştu: {e}")
