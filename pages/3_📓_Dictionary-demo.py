import streamlit as st
import pandas as pd
from theme_utils import apply_japanese_theme, japanese_header
import requests
import json
import random
from s3_utils import load_parquet_from_s3, load_csv_from_s3, get_s3_file_content

HOME_PAGE = "japankify-demo.py"

# --- 1. Config & Theme Setup ---
st.set_page_config(page_title="Dictionary", page_icon="📓", layout="wide")
apply_japanese_theme()
japanese_header("Dictionary Search- Demo Version", "Search the JLPT Reference and Jisho.org")
st.info("💡 **Demo Mode Active:** Adding new words to the user's personal database is disabled.")

# --- 2. S3 Data & SVG Loaders ---
@st.cache_data
def load_master_data():
    v_mast = load_parquet_from_s3("kaggle_all_voc_v2.parquet")
    k_mast = load_parquet_from_s3("kaggle_all_kan_v2.parquet")
    return v_mast, k_mast

v_mast, k_mast = load_master_data()

@st.cache_data
def get_svg_from_s3(stroke_order_url):
    """Fetches a numbered stroke order SVG directly from the S3 bucket using s3_utils."""
    if not stroke_order_url or pd.isna(stroke_order_url):
        return None
    return get_s3_file_content(f"assets/numbered_stroke_order/{stroke_order_url}")

# Ensure datasets exist in session state (auto-load from S3 if user navigated here directly)
if 'vocab_df' not in st.session_state:
    st.session_state.vocab_df = load_csv_from_s3("japankify-demo_N5-N3-voc-sample.csv")
if 'df_kanji' not in st.session_state:
    st.session_state.df_kanji = load_csv_from_s3("japankify-demo_N5-N3-kan-sample.csv")

v_user = st.session_state.vocab_df
k_user = st.session_state.df_kanji

def parse_jisho_match(match, default_query=""):
    jisho_slug = match.get('slug', default_query)
    is_common = match.get('is_common', False)
    japanese_list = match.get('japanese', [{}])
    primary_jp = japanese_list[0] if japanese_list else {}
    word = primary_jp.get('word', primary_jp.get('reading', jisho_slug))
    reading = primary_jp.get('reading', '')
    
    other_forms_list = []
    for jp in japanese_list[1:]:
        w, r = jp.get('word'), jp.get('reading')
        if w and r: other_forms_list.append(f"{w}【{r}】")
        elif w: other_forms_list.append(w)
        elif r: other_forms_list.append(r)
    other_forms = "、".join(other_forms_list)
    
    senses_list = match.get('senses', [])
    formatted_senses = []
    all_pos, all_sense_tags = set(), set()
    for i, sense in enumerate(senses_list, 1):
        pos = ", ".join(sense.get('parts_of_speech', []))
        if pos: all_pos.add(pos)
        defs = ", ".join(sense.get('english_definitions', []))
        links = sense.get('links', [])
        if links:
            link_mds = [f"[{l.get('text', 'Link')}]({l.get('url', '')})" for l in links if l.get('url')]
            defs += " 🔗 " + " / ".join(link_mds)
        sense_tags = ", ".join(sense.get('tags', []))
        info = ", ".join(sense.get('info', []))
        if sense_tags: all_sense_tags.add(sense_tags)        
        
        sense_str = f"**{i}.** "
        if pos: sense_str += f"*{pos}* — "
        sense_str += defs
        if sense_tags: sense_str += f" _({sense_tags})_"
        if info: sense_str += f" _[{info}]_"        
        formatted_senses.append(sense_str)
        
    full_definition = "\n".join(formatted_senses)
    parts_of_speech = ", ".join(filter(None, all_pos))    
    root_tags = ", ".join(match.get('tags', [])) 
    jlpt = ", ".join(match.get('jlpt', []))
    db_tags = ", ".join(filter(None, ["Common Word" if is_common else "", root_tags, jlpt] + list(all_sense_tags)))
    
    return {
        'word': word, 'reading': reading, 'other_forms': other_forms,
        'definition': full_definition, 'parts_of_speech': parts_of_speech,
        'tags': db_tags, 'jlpt': jlpt,
        '_raw_senses': formatted_senses, '_is_common': is_common, '_root_tags': root_tags
    }

def clear_search_fields():
    st.session_state.search_query = ""
    st.session_state.input_box = ""

# --- 3. Search logic ---
if 'search_query' not in st.session_state:
    st.session_state.search_query = st.query_params.get("query", "")

query_jp = st.text_input("Enter kanji, kana or romaji", value=st.session_state.search_query, key="input_box", placeholder="e.g. 食べる, たべる or taberu").strip()

if query_jp != st.session_state.search_query:
    st.session_state.search_query = query_jp
st.write('or')
query_eng = st.text_input("Enter English word", placeholder="e.g. to eat").strip()

if st.query_params.get("query"):
    st.query_params.clear()

col1, col2 = st.columns([0.85, 0.15])
with col1:
    if st.button("🚮 Clear Search", on_click=clear_search_fields):
        st.rerun()

st.divider()

# --- 4. Helper functions ---
def display_vocab(row, title="Vocab"):
    st.markdown(f"### 🈂️ {title}: {row['word']}")
    st.write(f"**Reading:** {row['kana']} | **Level:** {row['JLPT_level']}")
    if 'grammar_tags_json' in row and pd.notna(row['grammar_tags_json']):
        st.write(f"**Grammar Tags:** {row['grammar_tags_json'][2:-2]}")
    st.write(f"**Definition:** {row['definition']}")
    sentences_raw = row.get("all_sentences_json", "[]")
    try:
        sentences_list = json.loads(sentences_raw) if pd.notna(sentences_raw) and sentences_raw.strip() != "" else []
    except:
        sentences_list = []
    if isinstance(sentences_list, list) and len(sentences_list) > 0:
        chosen_sentence = random.choice(sentences_list)
        st.write(f"**Example:** {chosen_sentence.get('jp', '')} | **Meaning:** {chosen_sentence.get('en', '')}")
    
def display_kanji(row, title="Kanji"):
    st.markdown(f"### 🈳 {title}: {row['kanji']}")
    st.write(f"**JLPT Level:** {row.get('JLPT_level', 'N/A')} | **Taught in:** {row.get('kyouiku_grade', 'N/A')} | **Strokes:** {row.get('strokes', 'N/A')}")
    st.write(f"**Radical:** {row.get('rad_glyph', 'N/A')}")
    st.write(f"**On:** {row.get('onyomi', 'N/A')} | **Kun:** {row.get('kunyomi', 'N/A')}")
    st.write(f"**Meanings:** {row.get('meaning', 'N/A')}")
    
    svg_code = get_svg_from_s3(row.get('stroke_order_url'))
    if svg_code:
        st.markdown(f'<div style="width: 150px; margin: 10px 0;">{svg_code}</div>', unsafe_allow_html=True)
    
    raw_composites = row.get('smart_composites', '')
    if pd.notna(raw_composites) and raw_composites != "":
        try:
            composites_list = json.loads(raw_composites)
            if isinstance(composites_list, list) and len(composites_list) > 0:
                chosen_composite = random.choice(composites_list)
                st.write(f"**Example Composite:** {chosen_composite.get('word', '')} ({chosen_composite.get('kana', '')}) — {chosen_composite.get('definition', '')} | **Level:** {chosen_composite.get('level', '')}")
        except:
            pass

# --- 5. Extraction layer (search logic) ---
in_v_user = in_k_user = in_v_master = in_k_master = False
match_v_user = match_k_user = match_v_mast = match_k_mast = pd.DataFrame()

if query_jp:
    if not v_user.empty:
        match_v_user = v_user[(v_user['word'] == query_jp) | (v_user['kana'] == query_jp) | (v_user['romaji'] == query_jp)]
        in_v_user = not match_v_user.empty    
    if not k_user.empty:
        match_k_user = k_user[(k_user['kanji'] == query_jp) | (k_user['onyomi'].str.contains(query_jp, case=False, na=False)) | (k_user['kunyomi'].str.contains(query_jp, case=False, na=False))]
        in_k_user = not match_k_user.empty

    if not in_v_user and not v_mast.empty:
        match_v_mast = v_mast[(v_mast['word'] == query_jp) | (v_mast['kana'] == query_jp) | (v_mast['romaji'] == query_jp)]
        in_v_master = not match_v_mast.empty
    if not in_k_user and not k_mast.empty:
        match_k_mast = k_mast[(k_mast['kanji'] == query_jp) | (k_mast['onyomi'].str.contains(query_jp, case=False, na=False)) | (k_mast['kunyomi'].str.contains(query_jp, case=False, na=False))]
        in_k_master = not match_k_mast.empty

elif query_eng:
    if not v_user.empty:
        match_v_user = v_user[v_user['definition'].str.contains(rf"\b{query_eng}\b", case=False, na=False)]
        in_v_user = not match_v_user.empty
    if not k_user.empty:
        match_k_user = k_user[k_user['meaning'].str.contains(rf"\b{query_eng}\b", case=False, na=False)]
        in_k_user = not match_k_user.empty

    if not in_v_user and not v_mast.empty:
        match_v_mast = v_mast[v_mast['definition'].str.contains(rf"\b{query_eng}\b", case=False, na=False)]
        in_v_master = not match_v_mast.empty
    if not in_k_user and not k_mast.empty:
        match_k_mast = k_mast[k_mast['meaning'].str.contains(rf"\b{query_eng}\b", case=False, na=False)]
        in_k_master = not match_k_mast.empty    

# --- 6. Display Layer ---
if query_jp or query_eng:
    if in_v_user or in_k_user:
        st.info("📍 From the Sample Library :")
        if in_v_user:
            for _, row in match_v_user.iterrows():
                display_vocab(row, title="Sample Vocab")
                st.divider()
        if in_k_user:
            for _, row in match_k_user.iterrows():
                display_kanji(row, title="Sample Kanji")
                st.divider()

    elif in_v_master or in_k_master:
        st.success("✨ Found in the Master JLPT Reference :")
        if in_v_master:
            st.write("#### Vocabulary Matches")
            for idx, row in match_v_mast.iterrows():
                display_vocab(row, title="Master Vocab")
                st.divider()
        if in_k_master:
            st.write("#### Kanji Matches")
            for idx, row in match_k_mast.iterrows():
                display_kanji(row, title="Master Kanji")
                st.divider()        
                
    else:
        st.info("🚨 Not found in JLPT Master List. Querying Jisho.org...")
        active_query = query_jp if query_jp else query_eng
        jisho_url = f"https://jisho.org/api/v1/search/words?keyword={active_query}"        
        try:
            response = requests.get(jisho_url)
            data = response.json()
            all_matches = data.get('data', [])            
            if all_matches:
                common_matches = [m for m in all_matches if m.get('is_common')]
                matches_to_show = common_matches[:5]                 
                if matches_to_show:
                    st.warning(f"Found {len(matches_to_show)} common result(s) on Jisho.org:")                    
                    hidden_count = len(all_matches) - len(common_matches)
                    if hidden_count > 0:
                        st.info(f"💡 Found {hidden_count} additional uncommon/rare results. [View all results on Jisho.org](https://jisho.org/search/{active_query})")
                    parsed_matches = [parse_jisho_match(m, active_query) for m in matches_to_show]                   
                    for i, p_match in enumerate(parsed_matches):
                        st.markdown(f"### 🪺 Jisho: {p_match['word']}")
                        kanji_chars = [char for char in p_match['word'] if '\u4e00' <= char <= '\u9faf']
                        if kanji_chars:
                            kanji_md = " ".join([f"[{c}](https://jisho.org/search/{c}%20%23kanji)" for c in kanji_chars])
                            st.markdown(f"**Kanji in this word:** {kanji_md}")
                        ui_tags = []
                        if p_match['_is_common']: ui_tags.append("🟩 **Common Word**")
                        if p_match['jlpt']: ui_tags.append(f"📘 **{p_match['jlpt']}**")
                        if p_match['_root_tags']: ui_tags.append(f"🏷️ **{p_match['_root_tags']}**")                        
                        if ui_tags:
                            st.caption(" | ".join(ui_tags))                            
                        if p_match['reading'] and p_match['reading'] != p_match['word']:
                            st.write(f"**Reading:** {p_match['reading']}")                            
                        if p_match['other_forms']:
                            st.write(f"**Other forms:** {p_match['other_forms']}")                        
                        
                        st.write("**Definitions:**")
                        for sense in p_match['_raw_senses']:
                            st.markdown(sense)
                        st.divider()
                else:
                    st.error(f"No *common* words found. [View all results on Jisho.org](https://jisho.org/search/{active_query})")
            else:
                st.error("No results found on Jisho.org.")
        except Exception as e:
            st.error(f"Failed to connect to Jisho: {e}")

if st.button("🏯 Home page"):
    st.switch_page(HOME_PAGE)