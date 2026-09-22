import streamlit as st
import pandas as pd
import os
from theme_utils import apply_japanese_theme, japanese_header
from fpdf import FPDF
import datetime
from s3_utils import load_csv_from_s3

HOME_PAGE = "japankify-demo.py"

# --- 1. Config & Theme Setup ---
st.set_page_config(page_title="ことわざ", page_icon="🎐", layout="wide")
apply_japanese_theme()
japanese_header("諺 - ことわざ - Demo Version", "Your personal collection of Japanese proverbs")

# --- 2. Data Loading ---
@st.cache_data
def load_all_kotowaza():
    df = load_csv_from_s3("japankify-demo_kotowaza-sample.csv")
    if df.empty:
        return pd.DataFrame(columns=['category', 'cat_kana', 'saying', 'kana', 'translation', 'meaning', 'english equivalent'])
    return df
    
df_all = load_all_kotowaza()

# --- 3. UI rendering ---
st.info("💡 **Demo Mode Active:** Adding new proverbs is disabled. Displaying the base reference list.")
st.divider()

# Proverbs list view & export
st.subheader(f"🎐 Base Collection - {len(df_all)} proverbs")
all_cats = ["All"] + df_all['category'].unique().tolist() if not df_all.empty else ["All"]
filter_cat = st.radio("Filter by Category", all_cats, horizontal=True)

if filter_cat != "All":
    display_df = df_all[df_all['category'] == filter_cat]
else:
    display_df = df_all
st.dataframe(display_df, use_container_width=True, hide_index=True)

# --- 4. EXPORT SECTION ---
st.divider()
timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
st.markdown("### 📥 Export Collection")
export_col1, export_col2, _ = st.columns([1, 1, 4])
with export_col1:
    csv_data = display_df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
    st.download_button(
        label="📄 Download CSV",
        data=csv_data,
        file_name=f"kotowaza_export_{filter_cat}_{timestamp}.csv",
        mime="text/csv",
    )
with export_col2:
    font_path = "assets/NotoSansJP-Regular.ttf"    
    if os.path.exists(font_path):
        pdf = FPDF()
        pdf.add_page()
        pdf.add_font('NotoSansJP', '', font_path)
        pdf.set_font('NotoSansJP', '', 16)
        pdf.cell(0, 10, f'Kotowaza Library: {filter_cat}', ln=True, align='C')
        pdf.ln(10)        
        pdf.set_font('NotoSansJP', '', 11)
        for _, row in display_df.iterrows():
            saying = str(row.get('saying', ''))
            kana = str(row.get('kana', ''))
            trans = str(row.get('translation', ''))
            mean = str(row.get('meaning', ''))            
            text_block = f"【諺】 {saying}\n【かな】 {kana}\n【意味】 {trans}\n【解説】 {mean}"            
            pdf.multi_cell(0, 7, text_block, border=1)
            pdf.ln(5) 
        pdf_bytes = bytes(pdf.output())
        st.download_button(
            label="📕 Download PDF",
            data=pdf_bytes,
            file_name=f"kotowaza_export_{filter_cat}_{timestamp}.pdf",
            mime="application/pdf"
        )
    else:
        st.warning("⚠️ PDF export requires 'assets/NotoSansJP-Regular.ttf'")

st.divider()

if st.button("🏯 Home page"):
    st.switch_page(HOME_PAGE)