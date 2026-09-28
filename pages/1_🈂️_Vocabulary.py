import json
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import datetime
from srs_logging_utils import upload_app_file_to_s3, handle_card_review
from theme_utils import apply_japanese_theme, japanese_header, render_flashcard
from ui_utils import raining_success
import random

HOME_PAGE = "japankify.py"

# --- Load data ---
voc_file_path = "assets/my_wordbank_all_voc.parquet"
# This dataset is available from https://github.com/CelineBoutinon/japankify-open/assets

# --- 1. Config & Theme Setup ---
st.set_page_config(page_title="Vocab Flashcards", page_icon="🈂️", layout="wide")
apply_japanese_theme()

# --- 2. Data Loading & Session Initialization ---
if "level" not in st.session_state:
    st.warning("Please choose your JLPT level on the Home page first.")
    if st.button("Home page"): st.switch_page(HOME_PAGE)
    st.stop()

@st.cache_data
def load_vocab():
    """
    Loads the vocabulary dataset from disk and sanitizes Spaced Repetition System (SRS) metrics.

    Reads the Parquet file specified by the global `voc_file_path` variable. It ensures 
    that the 'repetition', 'interval', and 'easiness' columns are strictly numeric. 
    Missing or invalid data is coerced to safe default values (0 for repetition and 
    interval; 2.5 for easiness) to prevent runtime crashes during review calculations.

    Returns:
        pd.DataFrame: The loaded and cleaned vocabulary DataFrame ready for the session.
    """
    df = pd.read_parquet(voc_file_path)
    # Ensure SRS columns exist and are numeric to prevent crashes
    for col in ['repetition', 'interval', 'easiness']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0 if col != 'easiness' else 2.5)
    return df

if 'vocab_df' not in st.session_state:
    st.session_state.vocab_df = load_vocab()

# --- 3. Session Initialization Logic ---
if 'vocab_session_indices' not in st.session_state:
    vocab = st.session_state.vocab_df.copy()
    level = st.session_state.level
    batch_size = st.session_state.batch_size
    only_due = st.session_state.get('only_due', False)
    # Level Filtering
    if level == 'All JLPT':
        potential_vocab = vocab[vocab['JLPT_level'].isin(['N5', 'N4', 'N3'])].copy()
    else:
        potential_vocab = vocab[vocab['JLPT_level'] == level].copy()
    # Data Cleaning & Sorting
    potential_vocab['next_review'] = pd.to_datetime(potential_vocab['next_review'], errors='coerce')
    potential_vocab = potential_vocab.sort_values(by='next_review', ascending=True, na_position='last')
    # SRS Filtering
    today = datetime.date.today()
    due_vocab = potential_vocab[potential_vocab['next_review'].dt.date <= today]
    if only_due:
        session_df = due_vocab.sample(batch_size)
    else:
        new_vocab = potential_vocab[potential_vocab['repetition'] == 0]
        session_df = pd.concat([due_vocab, new_vocab]).sample(batch_size) if not due_vocab.empty else new_vocab.sample(batch_size)
    if session_df.empty:
        session_df = potential_vocab.sample(batch_size)
    # Final Storage
    if not session_df.empty:
        st.session_state.vocab_session_indices = session_df.sample(frac=1).index.tolist()
        st.session_state.vocab_pos = 0
        st.session_state.vocab_show_answer = False
    else:
        st.error(f"No data found for level {level}.")
        st.stop()


# --- 4. UI Rendering ---
japanese_header(f"{st.session_state.level} Vocabulary Review", "Working towards fluency, one word at a time")
v_indices = st.session_state.get('vocab_session_indices', [])
# 4.1 - End of session emoji rain & return home button
if len(v_indices) > 0 and st.session_state.vocab_pos >= len(v_indices):
    current_reward = st.session_state.get("reward")
    raining_success(emoji=current_reward)
    st.success("Vocab Session Complete!")
    st.warning("⚠️ **Reminder:** Don't forget to sync your session stats!")
    st.session_state.vocab_df.to_parquet(voc_file_path)
    upload_app_file_to_s3(voc_file_path, base_filename="my_wordbank_all_voc", extension="parquet")
    if st.button("🏯 Home page", key="vocab_home"):
        del st.session_state.vocab_session_indices
        st.switch_page(HOME_PAGE)

# 4.2 - Active session with flashcard rendering
elif len(v_indices) > 0:
    curr_idx = v_indices[st.session_state.vocab_pos]
    card = st.session_state.vocab_df.loc[curr_idx]
    st.progress(st.session_state.vocab_pos / len(v_indices))
    if not st.session_state.vocab_show_answer:
        # Front of card
        render_flashcard(card['word'])
        if pd.notna(card.get('audio')) and card['audio'] != "": 
            st.audio(card['audio'], format="audio/mp3", autoplay=True)
        if st.button("Show Answer", use_container_width=True, type="primary"):
            st.session_state.vocab_show_answer = True
            st.rerun()
    else:
        # Back of card       
        sentences_raw = card.get("all_sentences_json", "[]")
        selected_jp_sentence = ""
        selected_en_sentence = ""
        grammar_tags = card.get('grammar_tags_json', '[]')
        try:
            sentences_list = json.loads(sentences_raw)
            if isinstance(sentences_list, list) and len(sentences_list) > 0:
                chosen_sentence = random.choice(sentences_list)
                selected_jp_sentence = chosen_sentence.get("jp", "")
                selected_en_sentence = chosen_sentence.get("en", "")
        except Exception:
            selected_jp_sentence = ""
            selected_en_sentence = ""
        word = card['word']
        kana = card['kana']
        definition = card['definition']
        parsed_tags_str = ""
        if pd.notna(grammar_tags) and grammar_tags != '[]' and grammar_tags != "":
            try:
                tags_list = json.loads(grammar_tags)
                if isinstance(tags_list, list) and len(tags_list) > 0:
                    parsed_tags_str = f" -- {', '.join(tags_list)}"
            except Exception:
                parsed_tags_str = ""
        jlpt = f"{card['JLPT_level']}{parsed_tags_str}"

        sentence_jp=selected_jp_sentence
        sentence_en=selected_en_sentence

        sentence_html = ""
        if sentence_jp:
            sentence_html = f"""
                <div style="margin: 15px 0 5px 0; font-size: 1.3em; border-top: 1px dashed #e0e0e0; padding-top: 15px; text-align: center; width: 100%;">
                    <strong>例文 (Example):</strong> 
                    <span style="color:#242164; font-weight: 600; margin-left: 12px; font-style: bold; font-family: 'Hiragino Mincho ProN', 'MS Mincho', serif;">{sentence_jp}</span>
                </div>
                <div style="margin: 5px 0 5px 0; font-size: 1.2em; text-align: center; width: 100%; padding-left: 170px; box-sizing: border-box;">
                    <span style="#242164; font-family: Georgia, serif; font-style: italic; font-weight: 400;">{sentence_en}</span>
                </div>
            """
        # Back of card audio elements
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
            <h1 style="font-size: 6em; color: #242164; margin: 0; line-height: 1.2; font-family: 'Hiragino Mincho ProN', 'MS Mincho', serif;">{word}</h1>
            <p style="color: #BFA4A4; font-size: 1.5em; margin-top: 10px; font-style: italic;">{jlpt}</p>
            
            <div style="color: #242164; margin-top: 25px; border-top: 1px solid #f0f0f0; padding-top: 15px; width: 85%; display: flex; flex-direction: column; align-items: flex-start;">
                <div style="margin: 5px 0; font-size: 1.3em; text-align: center; width: 100%;">
                    <strong>読み (Reading):</strong> 
                    <span style="color:#E63946; font-family: Georgia, serif; font-weight: 600; margin-left: 10px;">{kana}</span>
                </div>
                <div style="margin: 5px 0; font-size: 1.3em; text-align: center; width: 100%;">
                    <strong>意味 (Meaning):</strong> 
                    <span style="color:#242164; font-family: Georgia, serif; font-weight: 600; margin-left: 10px;">{definition}</span>
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

                    {sentence_html}

                    <div style="width: 100%; text-align: center;">
                    <button onclick="speakSentence()" style="
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
                        🔊 Replay Sentence
                    </button>



                </div>
            </div>
        </div>

        <script>
            function speakWord() {{
                window.speechSynthesis.cancel(); // Terminate any lingering speech strings
                
                const utterance = new SpeechSynthesisUtterance("{word}");
                utterance.lang = "ja-JP"; 
                utterance.rate = 0.85; // Natural learning speed cadence
                
                const voices = window.speechSynthesis.getVoices();
                const jaVoice = voices.find(v => v.lang === 'ja-JP' || v.lang.includes('JP'));
                if (jaVoice) utterance.voice = jaVoice;
                
                window.speechSynthesis.speak(utterance);
            }}

            // Fires automatically when component lands in DOM frame
           /*speakWord();*/
        
            function speakSentence() {{
                window.speechSynthesis.cancel(); // Terminate any lingering speech strings
                
                const utterance = new SpeechSynthesisUtterance("{sentence_jp}");
                utterance.lang = "ja-JP"; 
                utterance.rate = 0.85; // Natural learning speed cadence
                
                const voices = window.speechSynthesis.getVoices();
                const jaVoice = voices.find(v => v.lang === 'ja-JP' || v.lang.includes('JP'));
                if (jaVoice) utterance.voice = jaVoice;
                
                window.speechSynthesis.speak(utterance);
            }}

            // Fires automatically when component lands in DOM frame
            /*speakSentence();*/
        </script>

        """
        components.html(html_audio_card, height=560)    

        st.divider()
        # User self-assessment buttons
        st.write("### How well did you know this?")
        cols = st.columns(5)
        labels = ["Again", "Hard", "Good", "Easy", "Mastered"]
        for i, lbl in enumerate(labels):
            if cols[i].button(lbl, use_container_width=True, key=f"v_{lbl}"):
                handle_card_review(lbl, 'vocab')