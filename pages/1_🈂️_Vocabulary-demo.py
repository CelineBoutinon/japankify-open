import json
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import datetime
import random
from theme_utils import apply_japanese_theme, japanese_header, render_flashcard
from ui_utils import raining_success
from s3_utils import load_csv_from_s3

HOME_PAGE = "japankify-demo.py"

# --- 1. Config & Theme Setup ---
st.set_page_config(page_title="Vocab Flashcards", page_icon="🈂️", layout="wide")
apply_japanese_theme()

# --- 2. Session Validation & Data Loader ---
if "level" not in st.session_state:
    st.warning("Please choose your JLPT level on the Home page first.")
    if st.button("Home page"): st.switch_page(HOME_PAGE)
    st.stop()

if 'vocab_df' not in st.session_state:
    st.session_state.vocab_df = load_csv_from_s3("japankify-demo_N5-N3-voc-sample.csv")

# --- 3. Session Initialization Logic ---
if 'vocab_session_indices' not in st.session_state:
    vocab = st.session_state.vocab_df.copy()
    level = st.session_state.level
    batch_size = st.session_state.batch_size
    only_due = st.session_state.get('only_due', False)
    
    if level == 'All JLPT':
        potential_vocab = vocab[vocab['JLPT_level'].isin(['N5', 'N4', 'N3'])].copy()
    else:
        potential_vocab = vocab[vocab['JLPT_level'] == level].copy()
        
    for col in ['repetition', 'interval', 'easiness']:
        if col in potential_vocab.columns:
            potential_vocab[col] = pd.to_numeric(potential_vocab[col], errors='coerce').fillna(0)

    if 'next_review' in potential_vocab.columns:
        potential_vocab['next_review'] = pd.to_datetime(potential_vocab['next_review'], errors='coerce')
        potential_vocab = potential_vocab.sort_values(by='next_review', ascending=True, na_position='last')
    
    session_df = potential_vocab.sample(min(batch_size, len(potential_vocab)))
    
    if not session_df.empty:
        st.session_state.vocab_session_indices = session_df.sample(frac=1).index.tolist()
        st.session_state.vocab_pos = 0
        st.session_state.vocab_show_answer = False
    else:
        st.error(f"No data found for level {level}.")
        st.stop()

# --- 4. UI Rendering ---
japanese_header(f"{st.session_state.level} Vocabulary Review - Demo Version", "Working towards fluency, one word at a time")
v_indices = st.session_state.get('vocab_session_indices', [])

if len(v_indices) > 0 and st.session_state.vocab_pos >= len(v_indices):
    current_reward = st.session_state.get("reward", "🎉")
    raining_success(emoji=current_reward)
    st.success("Vocab Session Complete!")
    st.info("💡 **Demo Mode:** Your progress was not written to the user's personal database.")
    if st.button("🏯 Home page", key="vocab_home"):
        del st.session_state.vocab_session_indices
        st.switch_page(HOME_PAGE)

elif len(v_indices) > 0:
    curr_idx = v_indices[st.session_state.vocab_pos]
    card = st.session_state.vocab_df.loc[curr_idx]
    st.progress(st.session_state.vocab_pos / len(v_indices))
    
    if not st.session_state.vocab_show_answer:
        render_flashcard(card['word'])
        if pd.notna(card.get('audio')) and card['audio'] != "": 
            st.audio(card['audio'], format="audio/mp3", autoplay=True)
        if st.button("Show Answer", use_container_width=True, type="primary"):
            st.session_state.vocab_show_answer = True
            st.rerun()
    else:
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
            pass
            
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
                pass
                
        jlpt = f"{card['JLPT_level']}{parsed_tags_str}"

        sentence_html = ""
        if selected_jp_sentence:
            sentence_html = f"""
                <div style="margin: 12px 0 4px 0; font-size: 1.15em; border-top: 1px dashed #e0e0e0; padding-top: 10px; text-align: center; width: 100%;">
                    <strong>例文 (Example):</strong> 
                    <span style="color:#242164; font-weight: 600; margin-left: 8px; font-family: 'Hiragino Mincho ProN', 'MS Mincho', serif;">{selected_jp_sentence}</span>
                </div>
                <div style="margin: 2px 0 4px 0; font-size: 1.05em; text-align: center; width: 100%;">
                    <span style="font-family: Georgia, serif; font-style: italic; color: #555;">{selected_en_sentence}</span>
                </div>
            """
            
        html_audio_card = f"""
        <div style="
            background-color: white; padding: 30px 20px; border-radius: 4px;
            border: 1px solid #E8E1DF; box-shadow: 2px 2px 15px rgba(0,0,0,0.05);
            text-align: center; margin-bottom: 20px;
            display: flex; flex-direction: column; justify-content: center; align-items: center;
        ">
            <h1 style="font-size: 5em; color: #242164; margin: 0; line-height: 1.2; font-family: 'Hiragino Mincho ProN', 'MS Mincho', serif;">{word}</h1>
            <p style="color: #BFA4A4; font-size: 1.4em; margin-top: 8px; font-style: italic;">{jlpt}</p>
            
            <div style="color: #242164; margin-top: 20px; border-top: 1px solid #f0f0f0; padding-top: 15px; width: 90%; display: flex; flex-direction: column; align-items: center;">
                <div style="margin: 4px 0; font-size: 1.2em; width: 100%;">
                    <strong>読み (Reading):</strong> 
                    <span style="color:#E63946; font-family: Georgia, serif; font-weight: 600; margin-left: 10px;">{kana}</span>
                </div>
                <div style="margin: 4px 0; font-size: 1.2em; width: 100%;">
                    <strong>意味 (Meaning):</strong> 
                    <span style="color:#242164; font-family: Georgia, serif; font-weight: 600; margin-left: 10px;">{definition}</span>
                </div>
                
                <div style="margin-top: 15px; width: 100%; display: flex; justify-content: center;">
                    <button onclick="speakWord()" style="
                        padding: 6px 18px; border: 1px solid #242164;
                        border-radius: 2px; background-color: transparent; color: #242164;
                        cursor: pointer; font-size: 0.9em; font-family: sans-serif; transition: all 0.3s ease;
                    " onmouseover="this.style.backgroundColor='#242164'; this.style.color='white';" 
                       onmouseout="this.style.backgroundColor='transparent'; this.style.color='#242164';">
                        🔊 Replay Word
                    </button>
                </div>

                {sentence_html}

                <div style="margin-top: 8px; width: 100%; display: flex; justify-content: center;">
                    <button onclick="speakSentence()" style="
                        padding: 6px 18px; border: 1px solid #242164;
                        border-radius: 2px; background-color: transparent; color: #242164;
                        cursor: pointer; font-size: 0.9em; font-family: sans-serif; transition: all 0.3s ease;
                    " onmouseover="this.style.backgroundColor='#242164'; this.style.color='white';" 
                       onmouseout="this.style.backgroundColor='transparent'; this.style.color='#242164';">
                        🔊 Replay Sentence
                    </button>
                </div>
            </div>
        </div>

        <script>
            function speakWord() {{
                window.speechSynthesis.cancel(); 
                const utterance = new SpeechSynthesisUtterance("{word}");
                utterance.lang = "ja-JP"; 
                utterance.rate = 0.85; 
                const voices = window.speechSynthesis.getVoices();
                const jaVoice = voices.find(v => v.lang === 'ja-JP' || v.lang.includes('JP'));
                if (jaVoice) utterance.voice = jaVoice;
                window.speechSynthesis.speak(utterance);
            }}
            function speakSentence() {{
                window.speechSynthesis.cancel(); 
                const utterance = new SpeechSynthesisUtterance("{selected_jp_sentence}");
                utterance.lang = "ja-JP"; 
                utterance.rate = 0.85; 
                const voices = window.speechSynthesis.getVoices();
                const jaVoice = voices.find(v => v.lang === 'ja-JP' || v.lang.includes('JP'));
                if (jaVoice) utterance.voice = jaVoice;
                window.speechSynthesis.speak(utterance);
            }}
        </script>
        """
        components.html(html_audio_card, height=540)    

        st.divider()
        st.write("### How well did you know this?")
        cols = st.columns(5)
        labels = ["Again", "Hard", "Good", "Easy", "Mastered"]
        for i, lbl in enumerate(labels):
            if cols[i].button(lbl, use_container_width=True, key=f"v_{lbl}"):
                st.session_state.vocab_pos += 1
                st.session_state.vocab_show_answer = False
                st.rerun()