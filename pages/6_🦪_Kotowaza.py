import streamlit as st
import pandas as pd
import os
from theme_utils import apply_japanese_theme, japanese_header
from srs_logging_utils import save_and_refresh
from fpdf import FPDF
import datetime

HOME_PAGE = "japankify.py"

# --- 1. Config & Theme Setup ---
st.set_page_config(page_title="ことわざ", page_icon="🎐", layout="wide")
apply_japanese_theme()
japanese_header("諺 - ことわざ", "Your personal collection of Japanese proverbs")

# --- Load data ---
MASTER_CSV_PATH = "assets/yojijukugo_master_list.csv"
KOTOWAZA_BANK_PATH = "assets/my_kotowaza_bank.parquet"

KOTOWAZA_SCHEMA = {'category': 'str',
                   'cat_kana': 'str', 
                   'saying': 'str', 
                   'kana': 'str', 
                   'translation': 'str', 
                   'meaning': 'str', 
                   'english equivalent': 'str'}

# --- 2. Data Loading & Session Initialization ---
@st.cache_data
def load_all_kotowaza():
    """
    Loads and combines the master and user-specific Kotowaza (proverb) datasets.

    Utilizes Streamlit's caching mechanism to optimize read operations. It reads a 
    static master CSV file and appends any user-added proverbs stored in a local 
    Parquet file. If the user's custom bank does not exist yet, it initializes an 
    empty DataFrame using the predefined schema before concatenation.

    Returns:
        pd.DataFrame: A unified DataFrame containing all available proverbs from 
            both the master list and the user's personal collection.
    """
    df_master = pd.read_csv(MASTER_CSV_PATH)
    if os.path.exists(KOTOWAZA_BANK_PATH):
        df_bank = pd.read_parquet(KOTOWAZA_BANK_PATH)
    else:
        df_bank = pd.DataFrame(columns=KOTOWAZA_SCHEMA.keys())
    return pd.concat([df_master, df_bank], ignore_index=True)

df_all = load_all_kotowaza()

# --- 3. UI rendering ---
# 3.1 - Add new kotowaza
st.subheader("🦪 Add Proverb")
with st.container(border=True):
    with st.form("new_kotowaza_form"):
        col1, col2 = st.columns(2)
        with col1:
            cat_options = df_all['category'].unique().tolist()
            new_category = st.selectbox("Category", cat_options)
            new_saying = st.text_input("Saying *", placeholder="e.g. 一石二鳥")
            new_kana = st.text_input("Kana", placeholder="e.g. いっせきにちょう")
        with col2:
            new_translation = st.text_input("Translation *", placeholder="e.g. one stone, two birds")
            new_meaning = st.text_area("Meaning", placeholder="e.g. to accomplish two things with one action")
            new_eng_eq = st.text_input("English Equivalent", placeholder="e.g. to kill two birds with one stone")        
        submitted = st.form_submit_button("💾 Save", type="primary")        
        st.markdown(" \* indicates required field")

        if submitted:
            if not new_saying or not new_translation:
                st.error("🚨 'Saying' and 'Translation' are required fields!")
            else:
                if new_saying in df_all['saying'].values:
                    st.warning("⚠️ This exact proverb is already in your collection!")
                else:
                    new_entry = {'category': new_category,
                                 'cat_kana': 'よじじゅくご' if '熟語' in new_category else 'いいならわし',
                                 'saying': new_saying, 'kana': new_kana, 
                                 'translation': new_translation, 'meaning': new_meaning, 
                                 'english equivalent': new_eng_eq}
                    if os.path.exists(KOTOWAZA_BANK_PATH):
                        df_bank = pd.read_parquet(KOTOWAZA_BANK_PATH)
                    else:
                        df_bank = pd.DataFrame(columns=KOTOWAZA_SCHEMA.keys())     

                    df_bank = pd.concat([df_bank, pd.DataFrame([new_entry])], ignore_index=True)
                    save_and_refresh(df_bank, KOTOWAZA_BANK_PATH, KOTOWAZA_SCHEMA, index_col='saying')            
                    st.success(f"Added {new_saying} to your personal bank!")
                    st.rerun()
                        
st.divider()

# 3.2 - Proverbs list view & export
st.subheader(f"🎐 Combined Collection - {len(df_all)} proverbs")
all_cats = ["All"] + df_all['category'].unique().tolist()
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
    # csv export
    csv_data = display_df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
    st.download_button(
        label="📄 Download CSV",
        data=csv_data,
        file_name=f"kotowaza_export_{filter_cat}_{timestamp}.csv",
        mime="text/csv",
    )
with export_col2:
    # pdf export
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