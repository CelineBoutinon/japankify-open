import streamlit as st
import pandas as pd
import os
from theme_utils import apply_japanese_theme, japanese_header
from fpdf import FPDF
import datetime
from s3_utils import load_csv_from_s3

HOME_PAGE = "japankify-demo.py"

# --- 1. Config & Theme Setup ---
st.set_page_config(page_title="テレビタイム", page_icon="🍿", layout="wide")
apply_japanese_theme()
japanese_header("Living Japanese Notebook - Demo Version", "Record and review Japanese sentences & expressions from the wild")

# --- 2. Data Loading ---
@st.cache_data
def load_notebook():
    df = load_csv_from_s3("japankify-demo_living-japanese-sample.csv")
    if df.empty:
        return pd.DataFrame(columns=['sentence', 'kana', 'meaning', 'notes'])
    return df

df_notebook = load_notebook()

# --- 3. UI rendering ---
st.info("💡 **Demo Mode Active:** New sentence entry is disabled for the public demo. Displaying read-only sample notebook.")
st.divider()

# 3.2 - Notebook view & export
timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
st.markdown(f"### 📒 Sample Notebook - {len(df_notebook)} entries")
st.dataframe(df_notebook, use_container_width=True, height=400)

st.markdown("### 📥 Export Notebook")
export_col1, export_col2, _ = st.columns([1, 1, 4])
with export_col1:
    csv_data = df_notebook.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
    st.download_button(
        label="📄 Download CSV",
        data=csv_data,
        file_name=f"living_japanese_{timestamp}.csv",
        mime="text/csv",
    )
with export_col2:
    font_path = "assets/NotoSansJP-Regular.ttf"   
    if os.path.exists(font_path):
        pdf = FPDF()
        pdf.add_page()
        pdf.add_font('NotoSansJP', '', font_path)        
        pdf.set_font('NotoSansJP', '', 16)
        pdf.cell(0, 10, 'My Japanese Sentences (Living Notebook)', ln=True, align='C')
        pdf.ln(10)        
        pdf.set_font('NotoSansJP', '', 11)
        records = df_notebook.to_dict('records')        
        for row in records:
            sent = str(row.get('sentence', ''))
            kana = str(row.get('kana', ''))
            mean = str(row.get('meaning', ''))
            note = str(row.get('notes', ''))            
            text_block = f"【日本語】 {sent}\n【かな】 {kana}\n【意味】 {mean}\n【メモ】 {note}"
            pdf.multi_cell(0, 7, str(text_block), border=1)
            pdf.ln(5)             
        pdf_bytes = bytes(pdf.output())
        st.download_button(
            label="📕 Download PDF",
            data=pdf_bytes,
            file_name=f"living_japanese_{timestamp}.pdf",
            mime="application/pdf"
        )
    else:
        st.warning("⚠️ To enable PDF export, please place NotoSansJP-Regular.ttf in your 'assets' folder.")

st.divider()

if st.button("🏯 Home page"):
    st.switch_page(HOME_PAGE)