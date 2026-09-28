import streamlit as st
import pandas as pd
import datetime
from theme_utils import apply_japanese_theme, japanese_header
from srs_logging_utils import save_and_refresh
import os
import requests
import time
import datetime
import json
import random
from fpdf import FPDF
import re
from ui_utils import show_print_button

# Setup
HOME_PAGE = "japankify.py"

# --- Load data ---
# User-specific datasets
user_voc_file_path = "assets/my_wordbank_all_voc.parquet"
user_kanji_file_path = "assets/my_wordbank_all_kan.parquet"
# These datasets are available from https://github.com/CelineBoutinon/japankify-open/assets

# JLPT syllabus master datasets
master_voc_file_path = "assets/JLPT_vocab_master_list.parquet"
# This dataset is available from https://www.kaggle.com/datasets/celineboutinon/jlpt-master-vocabulary-library-n5-n1
# See assets/csv-to-parquet_converter.ipynb for conversion from CSV to Parquet
master_kanji_file_path = "assets/JLPT_kanji_master_list.parquet"
# This dataset is available from https://www.kaggle.com/datasets/celineboutinon/jlpt-master-kanji-library-n5-n1
# See assets/csv-to-parquet_converter.ipynb for conversion from CSV to Parquet

# Other assets
NUMBERED_SVG_DIR = "assets/numbered_stroke_order"
# This dataset is available from https://www.kaggle.com/datasets/celineboutinon/jlpt-n5n1-kanji-static-stroke-order-diagrams
if not os.path.exists(NUMBERED_SVG_DIR):
    os.makedirs(NUMBERED_SVG_DIR)
custom_jisho_file_path = "assets/my_custom_jisho.parquet"
# This dataset is available from https://github.com/CelineBoutinon/japankify-open/assets

# --- 1. Config & Theme Setup ---
st.set_page_config(page_title="Dictionary", page_icon="📓", layout="wide")
apply_japanese_theme()
japanese_header("Dictionary Search", "Search and add new items to your library")

# --- 2. Data Loading & Session Initialization ---
@st.cache_data
def load_data():
    """
    Loads user and master JLPT vocabulary and Kanji datasets from disk.

    Utilizes Streamlit's caching mechanism to read four Parquet files only once 
    per session to optimize app performance.

    Returns:
        tuple: A 4-element tuple containing:
            - v_user (pd.DataFrame): User's custom vocabulary library.
            - k_user (pd.DataFrame): User's custom Kanji library.
            - v_mast (pd.DataFrame): Master JLPT vocabulary reference.
            - k_mast (pd.DataFrame): Master JLPT Kanji reference.
    """
    v_user = pd.read_parquet(user_voc_file_path)
    k_user = pd.read_parquet(user_kanji_file_path)
    v_mast = pd.read_parquet(master_voc_file_path)
    k_mast = pd.read_parquet(master_kanji_file_path)
    return v_user, k_user, v_mast, k_mast

v_user, k_user, v_mast, k_mast = load_data()

# Initialize states
match_v_user, match_k_user = pd.DataFrame(), pd.DataFrame()
match_v_mast, match_k_mast = pd.DataFrame(), pd.DataFrame()
in_v_user, in_k_user, in_v_master, in_k_master = False, False, False, False

# Define schemas for sanitization
VOC_SCHEMA = {'id': 'str',
             'JLPT_level': 'str',
             'word': 'str', 
             'kana': 'str', 
             'definition': 'str', 
             'romaji': 'str', 
             'all_sentences_json': 'str',     
             'grammar_tags_json': 'str', 
             'sentence_match_count': 'float',
             'easiness': 'float',
             'interval': 'int', 
             'repetition': 'int',
             'next_review': 'str'}

KANJI_SCHEMA = {'id': 'str', 
               'kanji': 'str', 
               'JLPT_level': 'str', 
               'jouyou_index': 'int',
               'kyouiku_grade': 'str',
               'in_prefectures': 'int', 
               'strokes': 'int',
               'stroke_order_url': 'str',
               'rad_num': 'int', 
               'rad_glyph': 'str',
               'onyomi': 'str',
               'kunyomi': 'str',
               'romaji_on': 'str', 
               'romaji_kun': 'str',
               'meaning': 'str', 
               'rank': 'int', 
               'easiness': 'float',
               'interval': 'int',
               'repetition': 'int', 
               'next_review': 'str', 
               'smart_composites': 'str'}

JISHO_SCHEMA = {'word': 'str', 
               'reading': 'str',
               'other_forms': 'str', 
               'definition': 'str',
               'parts_of_speech': 'str',
               'tags': 'str', 
               'jlpt': 'str',
               'easiness': 'float', 
               'interval': 'int', 
               'repetition': 'int',
               'next_review': 'str'}

def parse_jisho_match(match, default_query=""):
    """
    Extracts and flattens deeply nested JSON data from a Jisho.org API response.

    Parses the raw dictionary to construct a rich, formatted representation of 
    a Japanese word, including its readings, definitions, parts of speech, and 
    associated tags (like JLPT level and commonality).

    Args:
        match (dict): A single dictionary entry from the Jisho API 'data' list.
        default_query (str, optional): The fallback string to use if the 'slug' 
            key is missing. Defaults to "".

    Returns:
        dict: A flattened dictionary containing cleaned and formatted fields 
            ready for UI rendering and DataFrame ingestion.
    """
    jisho_slug = match.get('slug', default_query)
    is_common = match.get('is_common', False)

    # Extract Japanese Forms
    japanese_list = match.get('japanese', [{}])
    primary_jp = japanese_list[0] if japanese_list else {}
    word = primary_jp.get('word', primary_jp.get('reading', jisho_slug))
    reading = primary_jp.get('reading', '')
    other_forms_list = []
    for jp in japanese_list[1:]:
        w, r = jp.get('word'), jp.get('reading')
        if w and r:
            other_forms_list.append(f"{w}【{r}】")
        elif w:
            other_forms_list.append(w)
        elif r:
            other_forms_list.append(r)
    other_forms = "、".join(other_forms_list)

    # Extract Senses (Definitions, Parts of Speech, Notes, AND LINKS)
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

    # Extract Root Tags
    root_tags = ", ".join(match.get('tags', [])) 
    jlpt = ", ".join(match.get('jlpt', []))
    db_tags = ", ".join(filter(None, ["Common Word" if is_common else "", root_tags, jlpt] + list(all_sense_tags)))
    return {
        'word': word, 'reading': reading, 'other_forms': other_forms,
        'definition': full_definition, 'parts_of_speech': parts_of_speech,
        'tags': db_tags, 'jlpt': jlpt,
        '_raw_senses': formatted_senses, '_is_common': is_common, '_root_tags': root_tags
    }


def clean_markdown(text):
    """
    Strips specific Markdown formatting characters from a string.

    Designed to sanitize UI-styled text strings (containing bolding, italics, 
    and Markdown links) back into plain text before saving them to the persistent 
    custom library dataset.

    Args:
        text (str): The raw string containing Markdown characters.

    Returns:
        str: The cleaned plain text string. If the input is not a string, 
            it returns the input unmodified.
    """
    if not isinstance(text, str):
        return text
    
    # Remove bold, italics, links, and specific Jisho-related markdown
    clean = re.sub(r'\*\*', '', text)  
    clean = re.sub(r'\*', '', clean)  
    clean = re.sub(r'\_', '', clean)   
    clean = re.sub(r'🔗', '', clean)    
    clean = re.sub(r'\[.*?\]\(.*?\)', '', clean) 
    return clean.strip()


def clear_search_fields():
    """
    Clears the active search query and input box values.

    Acts as a callback function for the 'Clear Search' button, resetting the 
    relevant Streamlit session state variables before the page reruns.

    Returns:
        None
    """
    st.session_state.search_query = ""
    st.session_state.input_box = ""


# --- 3. Search logic ---
# 3.1 - Search bar code
# Initialize the persistent state
if 'search_query' not in st.session_state:
    st.session_state.search_query = st.query_params.get("query", "")

# Input box bound to the session state
query_jp = st.text_input("Enter kanji, kana or romaji", 
                        value=st.session_state.search_query,
                        key="input_box",
                        placeholder="e.g. 食べる, たべる or taberu"
                        ).strip()

# Keep the session state in sync if the user types something new
if query_jp != st.session_state.search_query:
    st.session_state.search_query = query_jp
st.write('or')
query_eng = st.text_input("Enter English word", placeholder="e.g. to eat").strip()

# Clean the URL once
if st.query_params.get("query"):
    st.query_params.clear()

# 3.2 - Clear search button
col1, col2 = st.columns([0.85, 0.15])
with col1:
    if st.button("🚮 Clear Search", on_click=clear_search_fields):
        st.rerun()

st.divider()


# --- 4. Helper functions ---
def display_vocab(row, title="Vocab"):
    """
    Renders Streamlit UI elements to display vocabulary item details.

    Outputs the word, reading, JLPT level, definition, and randomly selects 
    one example sentence (with English translation) from the available JSON pool.

    Args:
        row (pd.Series or dict): A data row containing vocabulary attributes.
        title (str, optional): The header label to display above the word. 
            Defaults to "Vocab".

    Returns:
        None
    """
    st.markdown(f"### 🈂️ {title}: {row['word']}")
    st.write(f"**Reading:** {row['kana']} | **Level:** {row['JLPT_level']}")
    st.write(f"**Grammar Tags:** {row['grammar_tags_json'][2:-2]}")
    st.write(f"**Definition:** {row['definition']}")
    sentences_raw = row.get("all_sentences_json", "[]")
    selected_jp_sentence = ""
    selected_en_sentence = ""
    try:
        if pd.isna(sentences_raw) or sentences_raw.strip() == "":
            sentences_list = []
        else:
            sentences_list = json.loads(sentences_raw)
    except (json.JSONDecodeError, TypeError):
        sentences_list = []
    if isinstance(sentences_list, list) and len(sentences_list) > 0:
        chosen_sentence = random.choice(sentences_list)
        selected_jp_sentence = chosen_sentence.get("jp", "")
        selected_en_sentence = chosen_sentence.get("en", "")
        st.write(f"**Example:** {selected_jp_sentence} | **Meaning:** {selected_en_sentence}")

    
def display_kanji(row, title="Kanji"):
    """
    Renders Streamlit UI elements to display Kanji item details.

    Outputs the character, educational metadata (JLPT, grade, strokes), 
    readings, meanings, and randomly selects one example composite word 
    from the available JSON pool.

    Args:
        row (pd.Series or dict): A data row containing Kanji attributes.
        title (str, optional): The header label to display above the Kanji. 
            Defaults to "Kanji".

    Returns:
        None
    """
    st.markdown(f"### 🈳 {title}: {row['kanji']}")
    st.write(f"**JLPT Level:** {row['JLPT_level']} | **Taught in:** {row['kyouiku_grade']} | **Strokes:** {row['strokes']}")
    st.write(f"**Radical:** {row['rad_glyph']}")
    st.write(f"**On:** {row['onyomi']} | **Kun:** {row['kunyomi']}")
    st.write(f"**Meanings:** {row['meaning']}")
    raw_composites = row.get('smart_composites', '')
    if pd.notna(raw_composites) and raw_composites != "":
        composites_list = json.loads(raw_composites)
        for item in composites_list:
            word = item.get('word', '')
    if isinstance(composites_list, list) and len(composites_list) > 0 and len(word) >1:
        chosen_composite = random.choice(composites_list)
        composite_word = chosen_composite.get("word", "")
        composite_kana = chosen_composite.get("kana", "")
        composite_defn = chosen_composite.get("definition", "")
        composite_level = chosen_composite.get("level", "")
        st.write(f"**Example Composite:** {composite_word} ({composite_kana}) — {composite_defn} | **Level:** {composite_level}")


# --- 5. Extraction layer (search logic) ---
if query_jp:
    # Search User Library First    
    v_user_mask = (v_user['word'] == query_jp) | \
                  (v_user['kana'] == query_jp) | \
                  (v_user['romaji'] == query_jp) 
    match_v_user = v_user[v_user_mask]
    in_v_user = not match_v_user.empty    

    k_user_mask = (k_user['kanji'] == query_jp) | \
                  (k_user['onyomi'].str.contains(query_jp, case=False, na=False)) | \
                  (k_user['romaji_on'].str.contains(rf"\b{query_jp}\b", case=False, na=False)) | \
                  (k_user['kunyomi'].str.contains(query_jp, case=False, na=False)) | \
                  (k_user['romaji_kun'].str.contains(rf"\b{query_jp}\b", case=False, na=False))
    match_k_user = k_user[k_user_mask]
    in_k_user = not match_k_user.empty

    st.session_state.match_v_user = match_v_user
    st.session_state.in_v_user = not match_v_user.empty
    st.session_state.match_k_user = match_k_user
    st.session_state.in_k_user = not match_k_user.empty

    # Search JLPT Master file (Only if not in user bank)
    if not in_v_user:
        v_master_mask = (v_mast['word'] == query_jp) | \
                        (v_mast['kana'] == query_jp) | \
                        (v_mast['romaji'] == query_jp)
        match_v_mast = v_mast[v_master_mask]
        in_v_master = not match_v_mast.empty
    if not in_k_user:
        k_master_mask = (k_mast['kanji'] == query_jp) | \
                        (k_mast['onyomi'].str.contains(query_jp, case=False, na=False)) | \
                        (k_mast['romaji_on'].str.contains(rf"\b{query_jp}\b", case=False, na=False)) | \
                        (k_mast['kunyomi'].str.contains(query_jp, case=False, na=False)) | \
                        (k_mast['romaji_kun'].str.contains(rf"\b{query_jp}\b", case=False, na=False)) 
        match_k_mast = k_mast[k_master_mask]
        in_k_master = not match_k_mast.empty
    st.session_state.match_k_mast = match_k_mast
    st.session_state.in_k_mast = not match_k_mast.empty
    st.session_state.match_v_mast = match_v_mast
    st.session_state.in_v_mast = not match_v_mast.empty   

elif query_eng:
    # Search User Library First    
    v_user_mask = (v_user['definition'].str.contains(rf"\b{query_eng}\b", case=False, na=False))
    match_v_user = v_user[v_user_mask]
    in_v_user = not match_v_user.empty
    k_user_mask = (k_user['meaning'].str.contains(rf"\b{query_eng}\b", case=False, na=False))
    match_k_user = k_user[k_user_mask]
    in_k_user = not match_k_user.empty
    st.session_state.match_v_user = match_v_user
    st.session_state.in_v_user = not match_v_user.empty
    st.session_state.match_k_user = match_k_user
    st.session_state.in_k_user = not match_k_user.empty

    # Search Master (Only if not in user bank)
    if not in_v_user:
        v_master_mask = (v_mast['definition'].str.contains(rf"\b{query_eng}\b", case=False, na=False))
        match_v_mast = v_mast[v_master_mask]
        in_v_master = not match_v_mast.empty
    if not in_k_user:
        k_master_mask = (k_mast['meaning'].str.contains(rf"\b{query_eng}\b", case=False, na=False))
        match_k_mast = k_mast[k_master_mask]
        in_k_master = not match_k_mast.empty    
    st.session_state.match_k_mast = match_k_mast
    st.session_state.in_k_mast = not match_k_mast.empty
    st.session_state.match_v_mast = match_v_mast
    st.session_state.in_v_mast = not match_v_mast.empty

# --- 6. Display & Save Layer ---
if query_jp or query_eng:
    # 6.1 - If found in user library
    if in_v_user or in_k_user:
        st.info("📍 From your library :")
        if in_v_user:
            for _, row in match_v_user.iterrows():
                display_vocab(row, title="My Vocab")
                st.divider()
        if in_k_user:
            for _, row in match_k_user.iterrows():
                display_kanji(row, title="My Kanji")
                raw_comps = row.get('smart_composites', '[]')
                try:
                    composites_list = json.loads(raw_comps)
                    lines = [f"{c.get('word', '')} ({c.get('kana', '')}) — {c.get('definition', '')}" for c in composites_list]
                    formatted_comps = "<br>".join(lines)
                except:
                    formatted_comps = ""
                if 'stroke_order_url' in row and pd.notna(row['stroke_order_url']):
                    show_print_button(NUMBERED_SVG_DIR, row, smart_composites=formatted_comps)
                st.divider()

    # 6.2 - If found in master list
    elif in_v_master or in_k_master:
        st.success("✨ Not in your library - from the Master JLPT Reference :")
        selected_v_indices = []
        selected_k_indices = []

        # Display all Master Vocab Matches
        if in_v_master:
            st.write("#### Vocabulary Matches")
            for idx, row in match_v_mast.iterrows():
                display_vocab(row, title="Master Vocab")
                if st.checkbox(f"Add {row['word']} to wordbank", key=f"v_mast_{idx}"):
                    selected_v_indices.append(idx)
                st.divider()

        # Display all Master Kanji Matches
        if in_k_master:
            st.write("#### Kanji Matches")
            for idx, row in match_k_mast.iterrows():
                display_kanji(row, title="Master Kanji")
                if st.checkbox(f"Add {row['kanji']} to kanji bank", key=f"k_mast_{idx}"):
                    selected_k_indices.append(idx)
                st.divider()        
        
        # Disable button if nothing is checked
        if st.button("➕ Add Selected to My Study Library", type="primary", disabled=not (selected_v_indices or selected_k_indices)):
            today = str(datetime.date.today())

            # Process selected vocab item(s)
            if selected_v_indices:
                selected_v_df = match_v_mast.loc[selected_v_indices].copy()
                selected_v_df['easiness'] = 2.5
                selected_v_df['interval'] = 0
                selected_v_df['repetition'] = 0
                selected_v_df['next_review'] = today

                # Save to Vocab Bank
                v_user = pd.concat([v_user, selected_v_df], ignore_index=True)
                save_and_refresh(v_user, user_voc_file_path, VOC_SCHEMA, index_col='word')

                # Smart Kanji Auto-Save: Check if any of the checked vocab are kanji
                for _, row in selected_v_df.iterrows():
                    found_word = row['word']
                    is_kanji = (len(found_word) == 1) and ('\u4e00' <= found_word <= '\u9faf')                    
                    if is_kanji:
                        kanji_match = k_mast[k_mast['kanji'] == found_word]
                        if not kanji_match.empty and found_word not in k_user['kanji'].values:
                            new_k = kanji_match.iloc[0].to_dict()
                            new_k.update({'easiness': 2.5, 'interval': 0, 'repetition': 0, 'next_review': today})
                            k_user = pd.concat([k_user, pd.DataFrame([new_k])], ignore_index=True)
                            save_and_refresh(k_user, user_kanji_file_path, KANJI_SCHEMA, index_col='kanji')
                st.toast("✅ Selected items saved to Library!")
                time.sleep(0.5)
                st.session_state.search_query = "" 
                st.rerun()

            # Process selected kanji item(s)
            if selected_k_indices:
                selected_k_df = match_k_mast.loc[selected_k_indices].copy()
                selected_k_df['easiness'] = 2.5
                selected_k_df['interval'] = 0
                selected_k_df['repetition'] = 0
                selected_k_df['next_review'] = today                
                k_user = pd.concat([k_user, selected_k_df], ignore_index=True)         

                # Drop duplicates just in case the Auto-Kanji step already added it
                k_user = k_user.drop_duplicates(subset=['kanji']) 
                save_and_refresh(k_user, user_kanji_file_path, KANJI_SCHEMA, index_col='kanji')
                st.toast("✅ Selected items saved to Library!")
                time.sleep(0.5)
                st.session_state.search_query = "" 
                st.rerun()
                

    # 6.3 - Fallback to Jisho if not found in user list nor master list
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
                    selected_jisho = []
                    parsed_matches = [parse_jisho_match(m, active_query) for m in matches_to_show]                   
                    for i, p_match in enumerate(parsed_matches):
                        st.markdown(f"### 🪺 Jisho: {p_match['word']}")
                        kanji_chars = [char for char in p_match['word'] if '\u4e00' <= char <= '\u9faf']
                        if kanji_chars:
                            kanji_md = " ".join([f"[{c}](https://jisho.org/search/{c}%20%23kanji)" for c in kanji_chars])
                            st.markdown(f"**Kanji in this word:** {kanji_md}")

                        # Tags
                        ui_tags = []
                        if p_match['_is_common']: ui_tags.append("🟩 **Common Word**")
                        if p_match['jlpt']: ui_tags.append(f"📘 **{p_match['jlpt']}**")
                        if p_match['_root_tags']: ui_tags.append(f"🏷️ **{p_match['_root_tags']}**")                        
                        if ui_tags:
                            st.caption(" | ".join(ui_tags))                            

                        # Main Readings & Forms
                        if p_match['reading'] and p_match['reading'] != p_match['word']:
                            st.write(f"**Reading:** {p_match['reading']}")                            
                        if p_match['other_forms']:
                            st.write(f"**Other forms:** {p_match['other_forms']}")                       

                        # Definitions List
                        st.write("**Definitions:**")
                        for sense in p_match['_raw_senses']:
                            st.markdown(sense)

                        # Render Checkbox
                        st.write("") 
                        if st.checkbox(f"Add {p_match['word']} to custom list", key=f"jisho_{i}"):
                            selected_jisho.append(p_match)                            
                        st.divider()

                    # Save logic for selected Jisho item(s)
                    if st.button("➕ Add Selected Jisho Words", type="primary", disabled=not selected_jisho):
                        today = str(datetime.date.today())
                        clean_jisho_list = []
                        for item in selected_jisho:
                            clean_item = {k: v for k, v in item.items() if not k.startswith('_')}
                            if 'definition' in clean_item:
                                clean_item['definition'] = clean_markdown(clean_item['definition'])
                            clean_item.update({'easiness': 2.5, 'interval': 0, 'repetition': 0, 'next_review': today})
                            clean_jisho_list.append(clean_item)
                        new_jisho_df = pd.DataFrame(clean_jisho_list)
                        if os.path.exists(custom_jisho_file_path):
                            existing_jisho = pd.read_parquet(custom_jisho_file_path)
                            combined_jisho = pd.concat([existing_jisho, new_jisho_df], ignore_index=True)                        
                        else:
                            combined_jisho = new_jisho_df
                            existing_jisho = pd.DataFrame()
                        num_duplicates = combined_jisho.duplicated(subset=['word', 'reading']).sum()
                        if num_duplicates == 0:
                            save_and_refresh(combined_jisho, custom_jisho_file_path, JISHO_SCHEMA, index_col='word')
                            st.toast("✅ Saved Jisho words to custom library!")
                            time.sleep(0.5)
                            st.session_state.search_query = ""
                            st.rerun()
                        else:
                            clean_jisho = combined_jisho.drop_duplicates(subset=['word', 'reading'], keep='first')
                            if len(clean_jisho) == len(existing_jisho):
                                st.toast("❌️ Word(s) already in custom library!")
                                time.sleep(0.5)
                                st.session_state.search_query = ""
                                st.rerun()
                            else:
                                save_and_refresh(clean_jisho, custom_jisho_file_path, JISHO_SCHEMA, index_col='word')
                                st.toast(f"✅ Saved new words! (Skipped {num_duplicates} duplicate/s)")
                                time.sleep(0.5)
                                st.session_state.search_query = ""
                                st.rerun()                
                else:
                    st.error(f"No *common* words found. [View all results on Jisho.org](https://jisho.org/search/{active_query})")

            else:
                st.error("No results found on Jisho.org.")

        except Exception as e:
            st.error(f"Failed to connect to Jisho: {e}")

# --- 7. View and export custom Jisho list ---
if os.path.exists(custom_jisho_file_path):
    combined_jisho = pd.read_parquet(custom_jisho_file_path)
else:
    combined_jisho = pd.DataFrame(columns=JISHO_SCHEMA.keys())
timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
japanese_header("My Custom Jisho List", "Add JLPT extra-curricular words from Jisho.org to your own custom list.")
st.dataframe(combined_jisho, use_container_width=True, height=400)
st.markdown("### 📥 Export Custom Jisho List")
export_col1, export_col2, _ = st.columns([1, 1, 4])
with export_col1:
    csv_data = combined_jisho.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
    st.download_button(
        label="📄 Download CSV",
        data=csv_data,
        file_name=f"my_custom_jisho_list_{timestamp}.csv",
        mime="text/csv",
    )
with export_col2:
    font_path = "assets/NotoSansJP-Regular.ttf"    
    if os.path.exists(font_path):
        pdf = FPDF()
        pdf.add_page()
        pdf.add_font('NotoSansJP', '', font_path)        
        pdf.set_font('NotoSansJP', '', 16)
        pdf.cell(0, 10, 'My Custom Jisho List', ln=True, align='C')
        pdf.ln(10)        
        pdf.set_font('NotoSansJP', '', 11)
        records = combined_jisho.to_dict('records')        
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
            file_name=f"my_custom_jisho_list_{timestamp}.pdf",
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