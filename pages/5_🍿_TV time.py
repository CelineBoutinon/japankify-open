import streamlit as st
import pandas as pd
import os
from theme_utils import apply_japanese_theme, japanese_header
from srs_logging_utils import save_and_refresh
from fpdf import FPDF
import datetime

HOME_PAGE = "japankify.py"

# --- 1. Config & Theme Setup ---
st.set_page_config(page_title="テレビタイム", page_icon="🍿", layout="wide")
apply_japanese_theme()
japanese_header("Living Japanese Notebook", "Record and review Japanese sentences & expressions from the wild")

# Local storage paths
NOTEBOOK_PARQUET_PATH = "assets/living_japanese.parquet"
NOTEBOOK_CSV_PATH = "assets/living_japanese.csv"
INITIAL_SEED_CSV = "assets/top_25_questions+bonus.csv"
# These datasets are available from https://github.com/CelineBoutinon/japankify-open/assets

NOTEBOOK_SCHEMA = {'sentence': 'str', 
                  'kana': 'str', 
                  'meaning': 'str', 
                  'notes': 'str'}

# --- 2. Data Loading & Session Initialization ---
@st.cache_data
def load_notebook():
    """
    Loads the 'Living Japanese' notebook dataset into a pandas DataFrame.

    Utilizes Streamlit's caching to optimize performance by preventing redundant 
    disk reads. The function prioritizes loading from the active Parquet file. 
    If the Parquet file is missing, it attempts to initialize the database from 
    a predefined seed CSV, saving the result as a new Parquet file. If neither 
    exists, it safely falls back to an empty DataFrame.

    Returns:
        pd.DataFrame: The populated notebook dataset, or an empty DataFrame 
            configured with the standard notebook schema columns if no source 
            files are found.
    """
    if os.path.exists(NOTEBOOK_PARQUET_PATH):
        return pd.read_parquet(NOTEBOOK_PARQUET_PATH)
    elif os.path.exists(INITIAL_SEED_CSV):
        st.toast("🔄 Initializing Parquet database from seed CSV...")
        df = pd.read_csv(INITIAL_SEED_CSV)
        save_and_refresh(df, NOTEBOOK_PARQUET_PATH, NOTEBOOK_SCHEMA)
        return pd.read_parquet(NOTEBOOK_PARQUET_PATH)
    else:
        return pd.DataFrame(columns=NOTEBOOK_SCHEMA.keys())

df_notebook = load_notebook()

# --- 3. UI rendering ---
# 3.1 - Add new sentence
st.markdown("### ✏️ Take notes")
with st.form("add_sentence_form", clear_on_submit=True):
    col1, col2 = st.columns(2)    
    with col1:
        new_sentence = st.text_input("Sentence (kanji & kana) *", placeholder="e.g. 映画を見に行きませんか")
        new_kana = st.text_input("Reading (kana only)", placeholder="e.g. えいがをみにいきませんか")    
    with col2:
        new_meaning = st.text_input("Translation *", placeholder="e.g. Would you like to go see a movie?")
        new_notes = st.text_input("Source / Notes / Context", placeholder="e.g. Heard in Terrace House S1E4")
               
    submitted = st.form_submit_button("📒 Save", type="primary")
    st.markdown(" \* indicates required field") 

    if submitted:
        if not new_sentence or not new_meaning:
            st.error("🚨 'Sentence' and 'Translation' are required fields!")
        else:
            if new_sentence in df_notebook['sentence'].values:
                st.warning("⚠️ This exact sentence is already in your notebook!")
            else:
                new_row = pd.DataFrame([{
                    'sentence': new_sentence,
                    'kana': new_kana,
                    'meaning': new_meaning,
                    'notes': new_notes
                }])
                updated_df = pd.concat([df_notebook, new_row], ignore_index=True)
                save_and_refresh(updated_df, NOTEBOOK_PARQUET_PATH, NOTEBOOK_SCHEMA)
                st.success(f"✅ Added: {new_sentence}")
                st.rerun()

st.divider()

# 3.2 - Notebook view & export
# Notebook view
timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
st.markdown(f"### 📒 Current Notebook - {len(df_notebook)} entries")
st.dataframe(df_notebook, use_container_width=True, height=400)
st.markdown("### 📥 Export Notebook")
export_col1, export_col2, _ = st.columns([1, 1, 4])
with export_col1:
    # notebook csv export
    csv_data = df_notebook.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
    st.download_button(
        label="📄 Download CSV",
        data=csv_data,
        file_name=f"living_japanese_{timestamp}.csv",
        mime="text/csv",
    )
with export_col2:
    font_path = "assets/NotoSansJP-Regular.ttf"   
    # Notebook pdf export 
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
        st.warning(
            "⚠️ To enable PDF export, please download the "
            "[NotoSansJP-Regular.ttf](https://fonts.google.com/noto/specimen/Noto+Sans+JP) "
            "file and place it in your 'assets' folder."
        )

st.divider()

if st.button("🏯 Home page"):
    st.switch_page(HOME_PAGE)