import random
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import datetime
import json
import os
import requests
from srs_logging_utils import upload_app_file_to_s3, handle_card_review
from theme_utils import apply_japanese_theme, japanese_header, render_flashcard
from ui_utils import raining_success, generate_genkouyoushi_print_html, get_numbered_svg
import base64

HOME_PAGE = "japankify.py"

# Define local storage paths for kanji graphics
LOCAL_SVG_DIR = "assets/kanji_animations"
# This dataset is available from https://www.kaggle.com/datasets/celineboutinon/jlpt-n5n1-kanji-animated-stroke-order-diagrams
if not os.path.exists(LOCAL_SVG_DIR):
    os.makedirs(LOCAL_SVG_DIR)
NUMBERED_SVG_DIR = "assets/numbered_stroke_order"
# This dataset is available from https://www.kaggle.com/datasets/celineboutinon/jlpt-n5n1-kanji-static-stroke-order-diagrams
if not os.path.exists(NUMBERED_SVG_DIR):
    os.makedirs(NUMBERED_SVG_DIR)

# --- Load data ---
kanji_file_path = "assets/my_wordbank_all_kan.parquet"
# This dataset is available from https://github.com/CelineBoutinon/japankify-open/assets

# --- 1. Config & Theme Setup ---
st.set_page_config(page_title="Kanji Flashcards", page_icon="🈳", layout="wide")
apply_japanese_theme()

# --- 2. Data Loading & Session Initialization ---
if "level" not in st.session_state:
    st.warning("Please configure your session on the Home page first.")
    if st.button("Go to Home"):
        st.switch_page(HOME_PAGE)
    st.stop()

@st.cache_data
def load_kanji():
    """
    Loads the master Kanji dataset from disk into a pandas DataFrame.

    Utilizes Streamlit's caching mechanism to prevent redundant file I/O operations
    across session reruns. Relies on the globally defined `kanji_file_path`.

    Returns:
        pd.DataFrame: The complete Kanji dataset.
    """
    return pd.read_parquet(kanji_file_path)

if 'df_kanji' not in st.session_state:
    st.session_state.df_kanji = load_kanji()

if 'kanji_session_indices' not in st.session_state:
    kanji = st.session_state.df_kanji.copy()
    level = st.session_state.level
    batch_size = st.session_state.batch_size
    only_due = st.session_state.get('only_due', False)
    kanji_filter = st.session_state.get('kanji_filter_type', 'JLPT')
    
    potential_kanji = pd.DataFrame()

    if kanji_filter == "JLPT":
        if level == 'All JLPT':
            potential_kanji = kanji[kanji['JLPT_level'].isin(['N5', 'N4', 'N3', 'N2', 'N1'])].copy()
        else:
            potential_kanji = kanji[kanji['JLPT_level'] == level].copy()
 
    elif kanji_filter == "Grade":
        if level == 'All Grades':
            grades = ['Grade 1', 'Grade 2', 'Grade 3', 'Grade 4', 'Grade 5', 'Grade 6', 'High School', 'Tertiary Education']
            potential_kanji = kanji[kanji['kyouiku_grade'].isin(grades)].copy()    
        else:
            potential_kanji = kanji[kanji['kyouiku_grade'] == level].copy()
    
    if potential_kanji.empty:
        st.error(f"No Kanji found for {kanji_filter}: {level}. Check your data columns.")
        st.stop()

    potential_kanji['repetition'] = pd.to_numeric(potential_kanji['repetition'], errors='coerce').fillna(0)
    potential_kanji['next_review'] = pd.to_datetime(potential_kanji['next_review'], errors='coerce')
    potential_kanji = potential_kanji.sort_values(by='next_review', ascending=True, na_position='last')

    today = datetime.date.today()
    due_kanji = potential_kanji[potential_kanji['next_review'].dt.date <= today]

    if only_due:
        session_df = due_kanji.sample(batch_size)
    else:
        new_kanji = potential_kanji[potential_kanji['repetition'] == 0]
        session_df = pd.concat([due_kanji, new_kanji]).sample(batch_size) if not due_kanji.empty else new_kanji.sample(batch_size)
    
    if session_df.empty:
        session_df = potential_kanji.sample(batch_size)

    st.session_state.kanji_session_indices = session_df.sample(frac=1).index.tolist()
    st.session_state.kanji_pos = 0
    st.session_state.kanji_show_answer = False

# --- 3. Helper Functions ---
# 3.1 - Animated SVG Retrieval with Local Caching
@st.cache_data
def get_animated_svg(kanji_char):
    """
    Retrieves an animated SVG of a Kanji character from a local cache or remote CDN.

    Converts the character to its decimal Unicode point to locate the corresponding 
    SVG file. If the file is not found in `LOCAL_SVG_DIR`, it attempts to download 
    it from the 'anim-cjk' repository and caches it locally for future access.

    Args:
        kanji_char (str): The single Kanji character to fetch the SVG for.

    Returns:
        str or None: The raw SVG XML content as a string, or None if the download fails.
    """
    decimal_code = ord(kanji_char)
    local_path = os.path.join(LOCAL_SVG_DIR, f"{decimal_code}.svg")
    
    if os.path.exists(local_path):
        with open(local_path, "r", encoding="utf-8") as f:
            return f.read()
    
    paths = ["svgsJa", "svgs"]
    for path in paths:
        url = f"https://cdn.jsdelivr.net/gh/parsimonhi/anim-cjk@master/{path}/{decimal_code}.svg"
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                svg_text = response.text
                with open(local_path, "w", encoding="utf-8") as f:
                    f.write(svg_text)
                return svg_text
        except Exception:
            continue
    return None

# 3.2 - Animated SVG Card with Replay Button
def animated_kanji_with_replay(kanji_char):
    """
    Renders an interactive animated Kanji SVG component with a replay button.

    Injects a custom HTML/JS component into the Streamlit interface that displays 
    the stroke order animation. It includes a JavaScript-powered button that 
    briefly clears and restores the DOM container to re-trigger the SVG animation.

    Args:
        kanji_char (str): The Kanji character to animate.

    Returns:
        None
    """
    svg_code = get_animated_svg(kanji_char)
    if not svg_code: return

    html_code = f"""
    <div style="
        background: white; 
        padding: 20px; 
        border-radius: 15px; 
        border: 1px solid #ddd;
        height: 320px; 
        display: flex;
        flex-direction: column;
        align-items: center;
        box-sizing: border-box;
    ">
        <div style="flex-grow: 1; display: flex; align-items: center; justify-content: center; width: 100%;">
            <div id="kanji-container" style="width: 180px;">{svg_code}</div>
        </div>

        <div style="margin-top: 10px;">
            <button onclick="replay()" style="
                background-color: #f0f2f6; 
                border: 1px solid #d1d5db; 
                border-radius: 5px; 
                padding: 4px 12px; 
                cursor: pointer; 
                font-family: sans-serif; 
                color: #242164; 
                font-size: 0.85em;
            ">
                🖌️Re-write kanji
            </button>
        </div>
    </div>
    <script>
        function replay() {{
            var container = document.getElementById('kanji-container');
            var content = container.innerHTML;
            container.innerHTML = ''; 
            setTimeout(function() {{ container.innerHTML = content; }}, 50);
        }}
    </script>
    <style>svg {{ width: 100%; height: auto; }}</style>
    """
    components.html(html_code, height=360)

# 3.3 - Kanji practice sheet generator with numbered stroke order
def numbered_stroke_order(card, formatted_composites_for_print=""):
    """
    Displays a static numbered stroke order guide and a practice sheet print button.

    Fetches the numbered SVG graphic and generates a Base64-encoded HTML template 
    for a Genkouyoushi practice sheet. Renders a Streamlit component containing 
    the SVG and a JavaScript-driven button that opens the print-ready HTML in a new tab.

    Args:
        card (dict or pd.Series): The data row for the current Kanji. Must contain 
            keys: 'kanji', 'stroke_order_url', 'meaning', 'onyomi', and 'kunyomi'.
        formatted_composites_for_print (str, optional): An HTML-formatted string 
            listing composite words to be included on the print sheet. Defaults to "".

    Returns:
        None
    """
    url = card['stroke_order_url']
    kanji_char = card['kanji']
    svg_code = get_numbered_svg(NUMBERED_SVG_DIR, url)
    
    if not svg_code:
        st.warning("Numbered stroke order diagram not available.")
        return

    print_template = generate_genkouyoushi_print_html(
        kanji_char=kanji_char,
        numbered_svg_code="",
        meaning=card['meaning'],
        onyomi=card['onyomi'],
        kunyomi=card['kunyomi'],
        smart_composites=formatted_composites_for_print
    )

    b64_template = base64.b64encode(print_template.encode('utf-8')).decode()
    b64_svg = base64.b64encode(svg_code.encode('utf-8')).decode()

    html_code = f"""
    <div style="background: white; padding: 20px; border-radius: 15px; border: 1px solid #ddd; height: 320px; display: flex; flex-direction: column; align-items: center; box-sizing: border-box;">
        <div style="flex-grow: 1; display: flex; align-items: center; justify-content: center; width: 100%;">
            <div style="width: 180px;">{svg_code}</div>
        </div>
        <div style="margin-top: 10px;">
            <button onclick="printSheet()" style="background-color: #f0f2f6; border: 1px solid #d1d5db; border-radius: 5px; padding: 4px 12px; cursor: pointer; font-family: sans-serif; color: #242164; font-size: 0.85em;">
                🖨️ Print Practice Sheet
            </button>
        </div>
    </div>

    <script>
        function b64DecodeUnicode(str) {{
            return decodeURIComponent(atob(str).split('').map(function(c) {{
                return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
            }}).join(''));
        }}

        function printSheet() {{
            const template = b64DecodeUnicode("{b64_template}");
            const svgContent = b64DecodeUnicode("{b64_svg}");
            
            const win = window.open("", "_blank");
            win.document.write(template);

            const target = win.document.getElementById("target-square");
            if (target) target.innerHTML = svgContent;
            
            win.document.close();
        }}
    </script>
    <style>
        svg {{ width: 100% !important; height: auto !important; display: block; }}
        svg text {{ font-size: 9px !important; fill: #E63946 !important; font-weight: bold; }}
    </style>
    """
    components.html(html_code, height=360)

# --- 4. Main UI Flow ---
japanese_header(f"{st.session_state.level} Kanji Review", "Mastering the characters and radicals")
indices = st.session_state.get('kanji_session_indices', [])

# 4.1 - End of session logic
if len(indices) > 0 and st.session_state.kanji_pos >= len(indices):
    current_reward = st.session_state.get("reward")
    raining_success(emoji=current_reward)
    st.success("Kanji Session Complete!")
    st.warning("⚠️ **Reminder:** Don't forget to sync your session stats!")
    st.session_state.df_kanji.to_parquet(kanji_file_path)
    upload_app_file_to_s3(kanji_file_path, base_filename="my_wordbank_all_kanji", extension="parquet")
    if st.button("🏯 Home page", key="kanji_home"): 
        del st.session_state.kanji_session_indices
        st.switch_page(HOME_PAGE)

# 4.2 - Active session logic
elif len(indices) > 0:
    idx = indices[st.session_state.kanji_pos]
    card = st.session_state.df_kanji.loc[idx]    
    st.progress(st.session_state.kanji_pos / len(indices))
    if not st.session_state.kanji_show_answer:
        # Front of card
        render_flashcard(card['kanji'])
        if st.button("Show Answer", use_container_width=True, type="primary"):
            st.session_state.kanji_show_answer = True
            st.rerun()
    else:
        # Back of card
        raw_composites = card.get('smart_composites', '')
        formatted_composites = ""
        composites_list = []
        kanji = card['kanji']
        JLPT_level = card['JLPT_level']
        kyouiku_grade = card['kyouiku_grade']
        strokes = card['strokes']
        stroke_order_url = card['stroke_order_url']
        onyomi = card['onyomi']
        kunyomi = card['kunyomi']
        meaning = card['meaning']

        composite_word = composite_kana = composite_defn = composite_level = ""
        if pd.notna(raw_composites) and raw_composites != "":
            try:
                composites_list = json.loads(raw_composites)
                lines = []
                for item in composites_list:
                    word = item.get('word', '')
                    kana = item.get('kana', '')
                    defn = item.get('definition', '')
                    lines.append(f"{word} ({kana}) — {defn}")
                    
                formatted_composites = "<br>".join(lines)      
                if isinstance(composites_list, list) and len(composites_list) > 0 and len(word) >1:
                    chosen_composite = random.choice(composites_list)
                    composite_word = chosen_composite.get("word", "")
                    composite_kana = chosen_composite.get("kana", "")
                    composite_defn = chosen_composite.get("definition", "")
                    composite_level = chosen_composite.get("level", "")

            except Exception:
                pass

            jlpt = f"{card['JLPT_level']} -- {card['kyouiku_grade']}"
            random_composite = f"{composite_word} ({composite_kana}) — {composite_defn} [{composite_level}]"

            # Back of card with audio replay and composite example
            html_audio_card = f"""
            <div style="
            background-color: white;
            padding: 40px 20px;
            border-radius: 4px;
            border: 1px solid #E8E1DF;
            box-shadow: 2px 2px 15px rgba(0,0,0,0.05);
            text-align: center;
            margin-bottom: 30px;
            /*min-height: 420px;*/
            padding-bottom: 40px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            ">
            <h1 style="font-size: 6em; color: #242164; margin: 0; line-height: 1.2; font-family: 'Hiragino Mincho ProN', 'MS Mincho', serif;">{kanji}</h1>
            <p style="color: #BFA4A4; font-size: 1.5em; margin-top: 10px; font-style: italic;">{jlpt}</p>
            
            <div style="color: #242164; margin-top: 25px; border-top: 1px solid #f0f0f0; padding-top: 15px; width: 85%; display: flex; flex-direction: column; align-items: flex-start;">
                <div style="margin: 5px 0; font-size: 1.3em; text-align: center; width: 100%;">
                    <strong>音読み (Onyomi):</strong> 
                    <span style="color:#E63946; font-family: Georgia, serif; font-weight: 600; margin-left: 10px;">{onyomi}</span>
                </div>

                <div style="margin: 5px 0; font-size: 1.3em; text-align: center; width: 100%;">
                    <strong>訓読み (Kunyomi):</strong> 
                    <span style="color:#E63946; font-family: Georgia, serif; font-weight: 600; margin-left: 10px;">{kunyomi}</span>
                </div>


                <div style="margin: 5px 0; font-size: 1.3em; text-align: center; width: 100%;">
                    <strong>意味 (Meaning):</strong> 
                    <span style="color:#242164; font-family: Georgia, serif; font-weight: 600; margin-left: 10px;">{meaning}</span>
                </div>

                <div style="margin: 5px 0; font-size: 1.3em; text-align: center; width: 100%;">
                    <strong><br>Composite word example:<br> </strong> 
                    <span style="color:#242164; font-family: Georgia, serif; font-weight: 600; margin-left: 10px;">{random_composite}</span>
                </div>
                            
                
                <div style="width: 100%; text-align: center;">
                    <button onclick="speakWord()" style="
                        margin-top: 25px;
                        padding: 6px 20px;
                        border: 1px solid #242164;
                        border-radius: 2px;
                        background-color: transparent;
                        color: #242164;
                        cursor: pointer;
                        font-size: 0.95em;
                        font-family: sans-serif;
                        transition: all 0.3s ease;
                    " onmouseover="this.style.backgroundColor='#242164'; this.style.color='white';" 
                       onmouseout="this.style.backgroundColor='transparent'; this.style.color='#242164';">
                        🔊 Replay Word
                    </button>
                </div>



            </div>

            <script>
                function speakWord() {{
                    window.speechSynthesis.cancel(); // Terminate any lingering speech strings
                
                    const utterance = new SpeechSynthesisUtterance("{composite_word}");
                    utterance.lang = "ja-JP"; 
                    utterance.rate = 0.85; // Natural learning speed cadence
                
                    const voices = window.speechSynthesis.getVoices();
                    const jaVoice = voices.find(v => v.lang === 'ja-JP' || v.lang.includes('JP'));
                    if (jaVoice) utterance.voice = jaVoice;                
                    window.speechSynthesis.speak(utterance);}}

                // Fires automatically when component lands in DOM frame
                /*speakWord();*/
        
                
            </script>
            """
        components.html(html_audio_card, height=560)    

       # Kanji graphics containers below back of card
        with st.container(border=True):
            if strokes > 1:
                    st.write(f"### Stroke Order - {strokes} strokes")
            else:
                    st.write(f"### Stroke Order - {strokes} stroke")        
            col1, col2 = st.columns([1, 1.2])                                            
            with col1:
                numbered_stroke_order(card, formatted_composites)    
                svg_data = get_numbered_svg(NUMBERED_SVG_DIR, card['stroke_order_url'])
                if svg_data:
                    safe_svg = svg_data.replace('"', '\\"').replace('\n', '')
                    print_html = generate_genkouyoushi_print_html(card['kanji'], safe_svg)
            with col2:                
                animated_kanji_with_replay(card['kanji'])
        cols = st.columns(5)
        for i, lbl in enumerate(["Again", "Hard", "Good", "Easy", "Mastered"]):
            if cols[i].button(lbl, use_container_width=True, key=f"k_{lbl}"):                 
                handle_card_review(lbl, 'kanji')
