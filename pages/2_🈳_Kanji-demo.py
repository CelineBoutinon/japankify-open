import random
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import datetime
import json
import base64
import requests
from theme_utils import apply_japanese_theme, japanese_header, render_flashcard
from ui_utils import raining_success, generate_genkouyoushi_print_html
from s3_utils import load_csv_from_s3, get_s3_file_content

HOME_PAGE = "japankify-demo.py"

# --- 1. Config & Theme Setup ---
st.set_page_config(page_title="Kanji Flashcards", page_icon="🈳", layout="wide")
apply_japanese_theme()

# --- 2. Session Validation & S3 Data Loader ---
if "level" not in st.session_state:
    st.warning("Please configure your session on the Home page first.")
    if st.button("Go to Home"):
        st.switch_page(HOME_PAGE)
    st.stop()

if 'df_kanji' not in st.session_state:
    st.session_state.df_kanji = load_csv_from_s3("japankify-demo_N5-N3-kan-sample.csv")

if 'kanji_session_indices' not in st.session_state:
    kanji = st.session_state.df_kanji.copy()
    level = st.session_state.level
    batch_size = st.session_state.batch_size
    kanji_filter = st.session_state.get('kanji_filter_type', 'JLPT')
    
    potential_kanji = pd.DataFrame()

    if kanji_filter == "JLPT":
        if level == 'All JLPT':
            potential_kanji = kanji[kanji['JLPT_level'].isin(['N5', 'N4', 'N3'])].copy()
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

    for col in ['repetition', 'interval', 'easiness']:
        if col in potential_kanji.columns:
            potential_kanji[col] = pd.to_numeric(potential_kanji[col], errors='coerce').fillna(0)

    if 'next_review' in potential_kanji.columns:
        potential_kanji['next_review'] = pd.to_datetime(potential_kanji['next_review'], errors='coerce')
        potential_kanji = potential_kanji.sort_values(by='next_review', ascending=True, na_position='last')

    session_df = potential_kanji.sample(min(batch_size, len(potential_kanji)))

    if not session_df.empty:
        st.session_state.kanji_session_indices = session_df.sample(frac=1).index.tolist()
        st.session_state.kanji_pos = 0
        st.session_state.kanji_show_answer = False
    else:
        st.error(f"No data found for level {level}.")
        st.stop()

# --- 3. Helper Functions (S3 Direct Fetching) ---
@st.cache_data
def get_animated_svg(kanji_char):
    """Fetches animated Kanji SVG prioritizing S3, with a CDN fallback."""
    if not kanji_char or pd.isna(kanji_char):
        return None
    char = str(kanji_char)[0]
    decimal_code = ord(char)
    hex_code = hex(decimal_code)[2:].lower().zfill(5)
    
    # 1. Try fetching from S3
    s3_keys = [
        f"kanji_animations/{decimal_code}.svg",
        f"kanji_animations/{hex_code}.svg",
        f"kanji_animations/{char}.svg"
    ]
    for key in s3_keys:
        svg_text = get_s3_file_content(key)
        if svg_text:
            return svg_text
            
    # 2. Fallback to CDN if missing from S3
    paths = ["svgsJa", "svgs"]
    for path in paths:
        url = f"https://cdn.jsdelivr.net/gh/parsimonhi/anim-cjk@master/{path}/{decimal_code}.svg"
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                return response.text
        except Exception:
            continue
            
    return None

@st.cache_data
def get_numbered_svg_from_s3(stroke_order_url, kanji_char):
    """Fetches numbered stroke order SVG from S3 bucket."""
    filename = ""
    if stroke_order_url and not pd.isna(stroke_order_url):
        url_str = str(stroke_order_url).strip()
        filename = url_str.split('/')[-1] if "/" in url_str else url_str
            
    if not filename and kanji_char:
        filename = f"{hex(ord(str(kanji_char)[0]))[2:].lower().zfill(5)}.svg"
        
    if not filename:
        return None
        
    svg_text = get_s3_file_content(f"numbered_stroke_order/{filename}")
    if svg_text:
        return svg_text
        
    return None

def animated_kanji_with_replay(kanji_char):
    svg_code = get_animated_svg(kanji_char)
    if not svg_code:
        st.warning("Animation not available in S3.")
        return

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

def numbered_stroke_order(card, formatted_composites_for_print=""):
    url = card.get('stroke_order_url')
    kanji_char = card['kanji']
    svg_code = get_numbered_svg_from_s3(url, kanji_char)
    
    if not svg_code:
        st.warning("Numbered stroke order diagram not available in S3.")
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
japanese_header(f"{st.session_state.level} Kanji Review - Demo Version", "Mastering the characters and radicals")
indices = st.session_state.get('kanji_session_indices', [])

if len(indices) > 0 and st.session_state.kanji_pos >= len(indices):
    current_reward = st.session_state.get("reward")
    raining_success(emoji=current_reward)
    st.success("Kanji Session Complete!")
    st.info("💡 **Demo Mode:** Your progress was not written to the user's personal database.")
    if st.button("🏯 Home page", key="kanji_home"): 
        del st.session_state.kanji_session_indices
        st.switch_page(HOME_PAGE)

elif len(indices) > 0:
    idx = indices[st.session_state.kanji_pos]
    card = st.session_state.df_kanji.loc[idx]    
    st.progress(st.session_state.kanji_pos / len(indices))
    
    if not st.session_state.kanji_show_answer:
        render_flashcard(card['kanji'])
        if st.button("Show Answer", use_container_width=True, type="primary"):
            st.session_state.kanji_show_answer = True
            st.rerun()
    else:
        raw_composites = card.get('smart_composites', '')
        formatted_composites = ""
        composites_list = []
        kanji = card['kanji']
        strokes = card['strokes']
        onyomi = card['onyomi']
        kunyomi = card['kunyomi']
        meaning = card['meaning']

        composite_word = composite_kana = composite_defn = composite_level = ""
        if pd.notna(raw_composites) and raw_composites != "":
            try:
                composites_list = json.loads(raw_composites)
                lines = [f"{item.get('word', '')} ({item.get('kana', '')}) — {item.get('definition', '')}" for item in composites_list]
                formatted_composites = "<br>".join(lines)      
                if isinstance(composites_list, list) and len(composites_list) > 0:
                    chosen_composite = random.choice(composites_list)
                    composite_word = chosen_composite.get("word", "")
                    composite_kana = chosen_composite.get("kana", "")
                    composite_defn = chosen_composite.get("definition", "")
                    composite_level = chosen_composite.get("level", "")
            except Exception:
                pass

        jlpt = f"{card['JLPT_level']} -- {card['kyouiku_grade']}"
        random_composite = f"{composite_word} ({composite_kana}) — {composite_defn} [{composite_level}]"

        html_audio_card = f"""
        <div style="background-color: white; padding: 40px 20px; border-radius: 4px; border: 1px solid #E8E1DF; box-shadow: 2px 2px 15px rgba(0,0,0,0.05); text-align: center; margin-bottom: 30px; padding-bottom: 40px; display: flex; flex-direction: column; justify-content: center; align-items: center;">
        <h1 style="font-size: 6em; color: #242164; margin: 0; line-height: 1.2; font-family: 'Hiragino Mincho ProN', 'MS Mincho', serif;">{kanji}</h1>
        <p style="color: #BFA4A4; font-size: 1.5em; margin-top: 10px; font-style: italic;">{jlpt}</p>
        
        <div style="color: #242164; margin-top: 25px; border-top: 1px solid #f0f0f0; padding-top: 15px; width: 85%; display: flex; flex-direction: column; align-items: flex-start;">
            <div style="margin: 5px 0; font-size: 1.3em; text-align: center; width: 100%;">
                <strong>音読み (Onyomi):</strong> <span style="color:#E63946; font-family: Georgia, serif; font-weight: 600; margin-left: 10px;">{onyomi}</span>
            </div>
            <div style="margin: 5px 0; font-size: 1.3em; text-align: center; width: 100%;">
                <strong>訓読み (Kunyomi):</strong> <span style="color:#E63946; font-family: Georgia, serif; font-weight: 600; margin-left: 10px;">{kunyomi}</span>
            </div>
            <div style="margin: 5px 0; font-size: 1.3em; text-align: center; width: 100%;">
                <strong>意味 (Meaning):</strong> <span style="color:#242164; font-family: Georgia, serif; font-weight: 600; margin-left: 10px;">{meaning}</span>
            </div>
            <div style="margin: 5px 0; font-size: 1.3em; text-align: center; width: 100%;">
                <strong><br>Composite word example:<br> </strong> <span style="color:#242164; font-family: Georgia, serif; font-weight: 600; margin-left: 10px;">{random_composite}</span>
            </div>
                        
            <div style="width: 100%; text-align: center;">
                <button onclick="speakWord()" style="margin-top: 25px; padding: 6px 20px; border: 1px solid #242164; border-radius: 2px; background-color: transparent; color: #242164; cursor: pointer; font-size: 0.95em; font-family: sans-serif; transition: all 0.3s ease;" onmouseover="this.style.backgroundColor='#242164'; this.style.color='white';" onmouseout="this.style.backgroundColor='transparent'; this.style.color='#242164';">
                    🔊 Replay Word
                </button>
            </div>
        </div>

        <script>
            function speakWord() {{
                window.speechSynthesis.cancel();
                const utterance = new SpeechSynthesisUtterance("{composite_word}");
                utterance.lang = "ja-JP"; 
                utterance.rate = 0.85;
                const voices = window.speechSynthesis.getVoices();
                const jaVoice = voices.find(v => v.lang === 'ja-JP' || v.lang.includes('JP'));
                if (jaVoice) utterance.voice = jaVoice;                
                window.speechSynthesis.speak(utterance);
            }}
        </script>
        </div>
        """
        components.html(html_audio_card, height=560)    

        with st.container(border=True):
            st.write(f"### Stroke Order - {strokes} stroke{'s' if strokes > 1 else ''}")        
            col1, col2 = st.columns([1, 1.2])                                            
            with col1:
                numbered_stroke_order(card, formatted_composites)    
            with col2:                
                animated_kanji_with_replay(card['kanji'])
                
        cols = st.columns(5)
        for i, lbl in enumerate(["Again", "Hard", "Good", "Easy", "Mastered"]):
            if cols[i].button(lbl, use_container_width=True, key=f"k_{lbl}"):                 
                st.session_state.kanji_pos += 1
                st.session_state.kanji_show_answer = False
                st.rerun()