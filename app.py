import re
import base64
import pandas as pd
from io import BytesIO
import streamlit as st
from rapidfuzz import fuzz
import matplotlib.pyplot as plt

# --- Config ---
st.set_page_config(page_title="Adres Kontrol Uygulaması", 
                   layout="wide",
                   page_icon="🚚")

def load_local_css(file_name):
    with open(file_name) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_local_css("assets/styles.css")

# --- Title ---
st.markdown("""
    <div class='app-title'>
        <h1>Adres Kontrol Uygulaması</h1>
    </div>
""", unsafe_allow_html=True)

st.markdown("Bu araç, kullanıcıdan gelen adresleri kontrol ederek resmi adreslerle karşılaştırır.")

# --- Ayarlar ---
st.markdown("### Ayarlar")
left, _ = st.columns([0.7, 1.5])
with left:    
    threshold = st.number_input(
        label="Benzerlik Eşiği (%)", 
        min_value=0, 
        max_value=100, 
        value=50, 
        step=5, 
        format="%d"
    )

# --- Load Constant Postal Data ---
@st.cache_data
def load_postal_reference():
    return pd.read_excel("data/input/turkiye_posta_kodlari.xlsx", engine="openpyxl", dtype=str)

df_postal = load_postal_reference()

# --- Normalization ---
def normalize(text):
    text = str(text).strip()
    mapping = str.maketrans("iı", "İI")
    return re.sub(r"[^\w\sİÇÖŞÜĞçöşüğ]", "", text.translate(mapping).upper())

# --- Find Match ---
def find_best_match(user_address, canon_list, threshold=50):
    user_norm = normalize(user_address)
    scored = [(canon, fuzz.ratio(user_norm, normalize(canon))) for canon in canon_list]
    best_match, best_score = max(scored, key=lambda x: x[1], default=(None, 0))
    return (best_match, best_score) if best_score >= threshold else (None, best_score)
    
# --- Matching Logic ---
def perform_address_matching(df_user, df_postal, threshold):
    user_col = df_user.columns[0]
    postal_mahalle_col = "Mahalle"
    postal_il_col = "İl"
    postal_ilce_col = "İlçe"

    results = []

    for _, row in df_user.iterrows():
        user_addr = row[user_col]
        filtered_df = df_postal.copy()

        if postal_il_col in df_user.columns and postal_ilce_col in df_user.columns:
            user_il = row.get(postal_il_col)
            user_ilce = row.get(postal_ilce_col)
            filtered_df = filtered_df[
                (filtered_df[postal_il_col] == user_il) &
                (filtered_df[postal_ilce_col] == user_ilce)
            ]

        best_match, score = find_best_match(user_addr, filtered_df[postal_mahalle_col], threshold)

        results.append({
            "Kullanıcı Adresi": user_addr,
            "En Yakın Eşleşme": best_match if best_match else "Eşleşme yok",
            "Benzerlik Skoru": round(score, 2),
            "Düşük Güven Skoru": "⚠️" if score < threshold else "✅"
        })

    return pd.DataFrame(results)

# --- Render HTML Table ---
def render_table(df):
    table_html = '<table class="dhl-table"><thead><tr>'
    for col in df.columns:
        table_html += f'<th>{col}</th>'
    table_html += '</tr></thead><tbody>'

    for _, row in df.iterrows():
        highlight = row["En Yakın Eşleşme"] == "Eşleşme yok"
        row_style = ' style="background-color:#D40511; color:white;"' if highlight else ""
        table_html += f'<tr{row_style}>' + ''.join(f'<td>{val}</td>' for val in row) + '</tr>'

    table_html += '</tbody></table>'
    return table_html

# --- File Upload & Run Matching ---
left, _ = st.columns([0.7, 1.5])  
with left:
    user_file = st.file_uploader("Kullanıcı adres dosyasını yükleyin", type=[".xlsx"], label_visibility="collapsed")
    
if user_file:
    df_user = pd.read_excel(user_file, engine="openpyxl", dtype=str)

    with st.spinner("🔍 Eşleştirme işlemi devam ediyor..."):
        df_results = perform_address_matching(df_user, df_postal, threshold)

    col_table, col_chart = st.columns([2, 1])

    with col_table:
        # BUNA Bİ BAKKKK st.data_editor(df_results)
        st.markdown('<div class="dhl-table-wrapper"><h3>Eşleştirme Sonuçları</h3></div>', unsafe_allow_html=True)
        st.markdown(render_table(df_results), unsafe_allow_html=True)

    with col_chart:
        matched = (df_results["En Yakın Eşleşme"] != "Eşleşme yok").sum()
        unmatched = (df_results["En Yakın Eşleşme"] == "Eşleşme yok").sum()
        total = matched + unmatched

        labels = ["Eşleşen", "Eşleşmeyen"]
        values = [matched, unmatched]
        colors = ["#FFCC00", "#D40511"]

        fig, ax = plt.subplots()
        fig.set_size_inches(4, 3)

        explode = [0.03, 0.03]  # slight separation for both segments

        wedges, texts, autotexts = ax.pie(
            values,
            labels=labels,
            colors=colors,
            autopct=lambda pct: f"{int(pct/100.*total)}\n({pct:.0f}%)",
            startangle=90,
            counterclock=False,
            wedgeprops=dict(width=0.4),
            explode=explode,
            labeldistance=1.15
        )

        for text in texts:
            text.set_fontsize(9)
            text.set_horizontalalignment('center')

        for autotext in autotexts:
            autotext.set_fontsize(8)
            autotext.set_color("black")
            autotext.set_weight("bold")

        ax.set_title("Adres Eşleşme Durumu", fontsize=10)
        ax.axis("equal") 

        st.pyplot(fig)

        # --- Excel Download ---
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            df_results.to_excel(writer, index=False, sheet_name="Results")

        st.markdown(
        """
        <div style='text-align: center; margin-top: 20px;'>
            <a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{data}" 
               download="adres_eslesme_sonuclari.xlsx" 
               style="
                   display: inline-block;
                   padding: 10px 20px;
                   font-weight: bold;
                   background-color: #D40511;
                   color: white;
                   text-decoration: none;
                   border-radius: 6px;
                   font-family: Courier New, monospace;
                   font-size: 14px;">
                   Sonuçları İndir
            </a>
        </div>
        """.format(data=base64.b64encode(buffer.getvalue()).decode()),
        unsafe_allow_html=True
    )