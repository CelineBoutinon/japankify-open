import streamlit as st
import pandas as pd
from theme_utils import apply_japanese_theme, japanese_header
import random
from datetime import datetime, timedelta
from s3_utils import load_csv_from_s3

# --- 1. Config & Theme Setup ---
st.set_page_config(page_title="Japankify - Home", page_icon="🏯", layout="wide")
apply_japanese_theme()

# --- 2. S3 Demo Data Loader (using s3_utils) ---
if 'vocab_df' not in st.session_state:
    st.session_state.vocab_df = load_csv_from_s3("japankify-demo_N5-N3-voc-sample.csv")
if 'df_kanji' not in st.session_state:
    st.session_state.df_kanji = load_csv_from_s3("japankify-demo_N5-N3-kan-sample.csv")

# --- 4. Sidebar ---
with st.sidebar:
    reward_list = ['🍙', '🍣', '🥟', '🍤', '🍮🥄', '🪭', '🌸', '🏮', '🎏', '🍜', '🍥', '🍡', '🍛', '🪷']
    if "reward" not in st.session_state:
        st.session_state.reward = random.choice(reward_list)
    
    st.info("💡 **Demo Mode Active**\n\nSync features and database writing are disabled. Displaying sample N5-N3 datasets.")

# --- 5. Header Section ---
st.markdown("<br>", unsafe_allow_html=True)
japanese_header("Japankify - Demo Version", "Your Path to JLPT N3 Mastery")

# --- 6. Kotowaza logic---
@st.cache_data(ttl=3600)
def get_random_koto():
    try:
        df_koto = load_csv_from_s3("japankify-demo_kotowaza-sample.csv")
        df_yoji = df_koto[df_koto['category'] == '四字熟語']
        if df_yoji.empty: return None
        random_idx = random.randint(0, len(df_yoji) - 1)
        return df_yoji.iloc[random_idx]
    except Exception:
        return None

koto_data = get_random_koto()

if koto_data is not None:
    with st.container(border=True):
        st.markdown(f"""
    <div style="text-align: left; display: flex; justify-content: left; align-items: baseline; gap: 5px; margin-bottom: 20px;">
        <h2 style="margin: 0; display: inline;">
            🪪 Japanese pearls of wisdom - today's 
            <span style="margin-right: 2px;">
                <ruby>四<rt style="color: gray; font-size: 0.4em;">よ</rt></ruby><ruby>字<rt style="color: gray; font-size: 0.4em;">じ</rt></ruby><ruby>熟<rt style="color: gray; font-size: 0.4em;">じゅく</rt></ruby><ruby>語<rt style="color: gray; font-size: 0.4em;">ご</rt></ruby>
            </span>
        </h2>
        <h2 style="margin: 0; display: inline;">is:</h2>
    </div>""", unsafe_allow_html=True)
        st.write("")        
        col1, col2 = st.columns([2, 3])
        with col1:
            koto_str = koto_data['idiom']
            def is_kanji(ch):
                return '\u4e00' <= ch <= '\u9faf'
            
            links_html = " ".join([
                f'<a href="/Dictionary-demo?query={char}" target="_self" style="text-decoration:none; font-size:2.5em; color:#E63946;">{char}</a>'
                if is_kanji(char) else f'<span style="font-size:2.5em; color:#242164;">{char}</span>'
                for char in koto_str
            ])

            st.markdown(f'<div style="text-align:center; line-height:1.2;">{links_html}</div>', unsafe_allow_html=True)
            st.markdown(f'<div style="text-align:center; line-height:1.2;">click a Kanji to lookup</div>', unsafe_allow_html=True)
            
        with col2:
            st.markdown(f"#### {koto_data['id_kana']}   --   {koto_data['translation']}")
            st.write(f"*{koto_data['meaning']}*")
            st.write(f"*{koto_data['english equivalent']}*")

# --- 7. Main Focus Section ---
st.markdown("### 🎯 Study Focus")
CONTAINER_HEIGHT = 480
batch_size = [1, 5, 10, 25, 50, 75, 100]
c1, c2 = st.columns(2)

with c1:
    with st.container(border=True, height=CONTAINER_HEIGHT):
        st.markdown("#### 🈂️ Vocabulary")
        st.write("Review words and phrases based on JLPT levels.")
        st.write("")
        st.write("") 
        st.write("") 
        st.write("") 
        st.write("") 
        v_level = st.selectbox("Select JLPT Level", ["N5", "N4", "N3","All JLPT"], key="v_level")
        v_batch = st.pills(label="Session Size", options=batch_size, key="v_batch", selection_mode="single", default=1)
        v_due = st.checkbox("Only review due items", value=True, key="v_due")
        
        if st.button("Start Vocab Review", use_container_width=True, type="primary"):
            st.session_state.level = v_level
            st.session_state.batch_size = v_batch
            st.session_state.only_due = v_due
            if 'vocab_session_indices' in st.session_state:
                del st.session_state.vocab_session_indices
            st.session_state.vocab_pos = 0
            st.switch_page("pages/1_🈂️_Vocabulary-demo.py")

with c2:
    with st.container(border=True, height=CONTAINER_HEIGHT):
        st.markdown("#### 🈳 Kanji")
        st.write("Practice characters by JLPT level or Primary School Grade.")
        
        k_mode = st.radio("Group by:", ["JLPT Level", "School Grade"], horizontal=True)
        
        if k_mode == "JLPT Level":
            k_filter = st.selectbox("Select JLPT Level", ["N5", "N4", "N3","All JLPT"], key="k_level")
            st.session_state.kanji_filter_type = "JLPT"
        else:
            k_filter = st.selectbox("Select School Grade", 
                          ["Grade 1", "Grade 2", "Grade 3", "Grade 4", "Grade 5", "Grade 6", "High School", "Tertiary Education", "All Grades"], 
                          key="k_grade")
            st.session_state.kanji_filter_type = "Grade"
            
        k_batch = st.pills(label="Session Size", options=batch_size, key="k_batch", selection_mode="single", default=1)
        k_due = st.checkbox("Only review due items", value=True, key="k_due")
        
        if st.button("Start Kanji Review", use_container_width=True, type="primary"):
            st.session_state.level = k_filter
            st.session_state.kanji_filter_type = "JLPT" if k_mode == "JLPT Level" else "Grade"
            st.session_state.batch_size = k_batch
            st.session_state.only_due = k_due
            if 'kanji_session_indices' in st.session_state:
                del st.session_state.kanji_session_indices
            st.session_state.kanji_pos = 0
            st.switch_page("pages/2_🈳_Kanji-demo.py")