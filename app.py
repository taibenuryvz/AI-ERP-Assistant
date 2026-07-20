"""
app.py — Streamlit Web Arayüzü
Dosya yükle → Parse et → Sonuçları gör → Excel indir
"""

import streamlit as st
import pandas as pd
import tempfile
import os
from pathlib import Path

# ─────────────────────────────────────────
# Sayfa Ayarları
# ─────────────────────────────────────────
st.set_page_config(
    page_title="AI Banka Ekstresi Parser",
    page_icon="🏦",
    layout="wide",
)

# ─────────────────────────────────────────
# CSS
# ─────────────────────────────────────────
st.markdown("""
<style>
    .stApp { background-color: #0f1117; color: #e0e0e0; }
    .metric-card {
        background: #1e2130;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        border: 1px solid #2d3250;
    }
    .metric-num { font-size: 2.2rem; font-weight: 700; }
    .oto  { color: #4caf50; }
    .onay { color: #ffc107; }
    .manuel { color: #f44336; }
    .tag {
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.78rem;
        font-weight: 600;
    }
    .tag-oto    { background: #1b5e20; color: #a5d6a7; }
    .tag-onay   { background: #f57f17; color: #fff9c4; }
    .tag-manuel { background: #b71c1c; color: #ffcdd2; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────
# Header
# ─────────────────────────────────────────
st.title("🏦 AI Banka Ekstresi Parser")
st.caption("Karmaşık banka açıklamalarını 25 yapılandırılmış sütuna dönüştür")
st.divider()

# ─────────────────────────────────────────
# Sidebar — Konfigürasyon
# ─────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Ayarlar")

    api_key = st.text_input(
        "OpenAI API Key",
        type="password",
        placeholder="sk-...",
        help="Ortam değişkeni OPENAI_API_KEY ile de verilebilir",
    )
    if api_key:
        os.environ["OPENAI_API_KEY"] = api_key

    st.divider()

    erp_choice = st.selectbox(
        "Çıktı Formatı (ERP)",
        ["excel", "json", "1c", "netsis"],
        index=0,
    )

    st.divider()

    st.subheader("Güven Eşikleri")
    auto_thresh   = st.slider("Otomatik Aktar (%)",  50, 100, 90)
    review_thresh = st.slider("Onay Bekle (%)",       30,  90, 70)

    st.divider()
    dry_run = st.checkbox("🧪 Dry Run (API çağrısı yapma)", value=False)

# ─────────────────────────────────────────
# Dosya Yükleme
# ─────────────────────────────────────────
col1, col2 = st.columns([2, 1])

with col1:
    uploaded = st.file_uploader(
        "Banka Ekstresi Yükle",
        type=["xlsx", "xls", "csv"],
        help="Excel veya CSV formatında banka ekstresi",
    )

with col2:
    st.info(
        "**Desteklenen formatlar:**\n"
        "- Excel (.xlsx, .xls)\n"
        "- CSV (.csv)\n\n"
        "PDF desteği yakında eklenecek.",
        icon="📋"
    )

# ─────────────────────────────────────────
# Dosya Yüklendiyse: Sütun Seçimi
# ─────────────────────────────────────────
if uploaded:
    with tempfile.NamedTemporaryFile(
        suffix=Path(uploaded.name).suffix, delete=False
    ) as tmp:
        tmp.write(uploaded.read())
        tmp_path = tmp.name

    # Dosyayı oku ve sütunları göster
    from file_reader import FileReader
    reader = FileReader(tmp_path)
    df_raw = reader.read()

    st.success(f"✅ Dosya yüklendi: **{uploaded.name}** — {len(df_raw)} satır")

    st.divider()
    st.subheader("📋 Sütun Haritalaması")
    st.caption("Banka ekstrenizden hangi sütunun ne anlama geldiğini seçin")

    cols = list(df_raw.columns)
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        aciklama_col = st.selectbox("🔑 Ham Açıklama Sütunu *", cols,
                                     help="AI bu sütunu işleyecek")
    with c2:
        tarih_options = ["— Seçme —"] + cols
        tarih_col = st.selectbox("📅 Tarih Sütunu", tarih_options)
        tarih_col = None if tarih_col == "— Seçme —" else tarih_col
    with c3:
        tutar_options = ["— Seçme —"] + cols
        tutar_col = st.selectbox("💰 Tutar Sütunu", tutar_options)
        tutar_col = None if tutar_col == "— Seçme —" else tutar_col
    with c4:
        yon_options = ["— Seçme —"] + cols
        yon_col = st.selectbox("↕️ Giriş/Çıkış Sütunu", yon_options)
        yon_col = None if yon_col == "— Seçme —" else yon_col

    # Önizleme
    with st.expander("👁️ Ham Veri Önizleme (ilk 5 satır)"):
        st.dataframe(df_raw.head(), use_container_width=True)

    st.divider()

    # ── Parse Butonu ───────────────────────────────────────────
    run_btn = st.button(
        "🚀 Parse Et",
        type="primary",
        use_container_width=True,
        disabled=(not api_key and not dry_run),
    )

    if not api_key and not dry_run:
        st.warning("API key girin veya Dry Run modunu aktifleştirin.")

    if run_btn:
        with st.spinner("AI parse ediliyor... Lütfen bekleyin."):
            from main import run_pipeline

            # Config'i güncellenmiş eşiklerle yaz
            import config
            config.CONFIDENCE_AUTO   = auto_thresh   / 100
            config.CONFIDENCE_REVIEW = review_thresh / 100

            try:
                results, output_path = run_pipeline(
                    file_path    = tmp_path,
                    aciklama_col = aciklama_col,
                    tarih_col    = tarih_col,
                    tutar_col    = tutar_col,
                    yon_col      = yon_col,
                    erp          = erp_choice,
                    dry_run      = dry_run,
                )
                st.session_state["results"]     = results
                st.session_state["output_path"] = output_path
            except Exception as e:
                st.error(f"Hata: {e}")

# ─────────────────────────────────────────
# Sonuçlar
# ─────────────────────────────────────────
if "results" in st.session_state:
    results     = st.session_state["results"]
    output_path = st.session_state["output_path"]

    from confidence import summary_stats
    stats = summary_stats(results)

    st.divider()
    st.subheader("📊 Özet")

    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        st.markdown(f"""
        <div class="metric-card">
          <div style="color:#90caf9">Toplam</div>
          <div class="metric-num">{stats['toplam']}</div>
          <div>satır</div>
        </div>""", unsafe_allow_html=True)
    with m2:
        st.markdown(f"""
        <div class="metric-card">
          <div class="oto">Otomatik</div>
          <div class="metric-num oto">{stats['oto_aktar']}</div>
          <div>{stats['oto_oran']}</div>
        </div>""", unsafe_allow_html=True)
    with m3:
        st.markdown(f"""
        <div class="metric-card">
          <div class="onay">Onay Bekle</div>
          <div class="metric-num onay">{stats['onay_bekle']}</div>
        </div>""", unsafe_allow_html=True)
    with m4:
        st.markdown(f"""
        <div class="metric-card">
          <div class="manuel">Manuel</div>
          <div class="metric-num manuel">{stats['manuel']}</div>
        </div>""", unsafe_allow_html=True)
    with m5:
        st.markdown(f"""
        <div class="metric-card">
          <div style="color:#ce93d8">Ort. Güven</div>
          <div class="metric-num" style="color:#ce93d8">{stats['avg_guven']}</div>
        </div>""", unsafe_allow_html=True)

    st.divider()

    # ── Tablo ─────────────────────────────────────────────────
    st.subheader("📋 Parse Sonuçları")

    df_results = pd.DataFrame(results)

    # Filtreler
    filter_col = st.selectbox(
        "Filtrele",
        ["Tümü", "OTO_AKTAR", "ONAY_BEKLE", "MANUEL"],
        horizontal=True if hasattr(st, "radio") else False,
    )
    if filter_col != "Tümü" and "aksiyon" in df_results.columns:
        df_show = df_results[df_results["aksiyon"] == filter_col]
    else:
        df_show = df_results

    # Önemli sütunları öne çıkar
    priority_cols = [
        "islem_tarihi", "islem_tipi", "islem_yonu",
        "tutar_tl", "karsitaraf_ad", "karsitaraf_iban",
        "fatura_no", "muhasebe_hesabi",
        "cari_durumu", "guven_skoru", "aksiyon",
    ]
    show_cols = [c for c in priority_cols if c in df_show.columns]
    st.dataframe(df_show[show_cols], use_container_width=True, height=400)

    # ── İndirme ───────────────────────────────────────────────
    st.divider()
    with open(output_path, "rb") as f:
        st.download_button(
            label="⬇️ Çıktıyı İndir",
            data=f.read(),
            file_name=Path(output_path).name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            type="primary",
        )
