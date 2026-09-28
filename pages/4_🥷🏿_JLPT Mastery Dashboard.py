import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from theme_utils import apply_japanese_theme, japanese_header

HOME_PAGE = "japankify.py"

# --- 1. Config & Theme Setup ---
st.set_page_config(page_title='', page_icon='', layout="wide")
apply_japanese_theme()
japanese_header("🥷🏿 JLPT Mastery Dashboard", 'Track your progress towards JLPT level goals')

# --- Load data ---
voc_file_path = "assets/my_wordbank_all_voc.parquet"
kanji_file_path = "assets/my_wordbank_all_kan.parquet"
metadata_path = "assets/kaggle_voc_kan_metadata.json"
log_file_path = "assets/review_history.parquet"
# These datasets are available from https://github.com/CelineBoutinon/japankify-open/assets

# --- 2. Data Loading & Session Initialization ---
@st.cache_data
def load_stats_data():
    """
    Loads the vocabulary, Kanji, and review history datasets from local Parquet files.

    Utilizes Streamlit's caching to minimize disk I/O. If a file is missing 
    or corrupted, it gracefully falls back to returning an empty DataFrame 
    (ensuring the log history DataFrame retains its required columns).

    Returns:
        tuple: A 3-element tuple containing:
            - df_voc (pd.DataFrame): Vocabulary dataset.
            - df_kan (pd.DataFrame): Kanji dataset.
            - df_log (pd.DataFrame): Review history logs.
    """
    try:
        df_voc = pd.read_parquet(voc_file_path)
    except:
        df_voc = pd.DataFrame()
    try:
        df_kan = pd.read_parquet(kanji_file_path)
    except:
        df_kan = pd.DataFrame()
    try:
        df_log = pd.read_parquet(log_file_path)
    except:
        df_log = pd.DataFrame(columns=['date', 'item', 'type', 'level', 'grade', 'jouyou_index'])        
    return df_voc, df_kan, df_log

vocab_df, kanji_df, history_df = load_stats_data()
metadata_df = pd.read_json(metadata_path)
metadata_dict = metadata_df.to_dict()
history_df['jouyou_index'] = pd.to_numeric(history_df['jouyou_index'], errors='coerce')
mastered_count = history_df[history_df['type'] == 'Kanji']['item'].nunique()

# --- 3. Targets & Mastery Logic ---
required_vocab = ['N5', 'N4', 'N3']
required_kanji_jlpt = ['N5', 'N4', 'N3']
required_kanji_grade = ['Grade 1', 'Grade 2', 'Grade 3', 'Grade 4', 'Grade 5', 'Grade 6']
vocab_source = metadata_dict.get('vocabulary', {})
kanji_source = metadata_dict.get('kanji', {})

# Verify all required levels present in the JSON source arrays
vocab_valid = all(lvl in vocab_source for lvl in required_vocab)
kanji_jlpt_valid = all(lvl in kanji_source for lvl in required_kanji_jlpt)
kanji_grade_valid = all(lvl in kanji_source for lvl in required_kanji_grade)
if not (vocab_valid and kanji_jlpt_valid and kanji_grade_valid):
    st.error("❌ **Metadata Error:** Missing target counts! Please check your JSON input configuration file.")
    st.info("Ensure `my_wordbank_voc_kan_metadata.json` contains all required JLPT levels (N5-N3) and school grades (Grade 1-6).")
    st.stop()

# Extract targets from confirmed JSON profile fields
voc_target_counts = {lvl: vocab_source[lvl] for lvl in required_vocab}
kanji_JLPT_target_counts = {lvl: kanji_source[lvl] for lvl in required_kanji_jlpt}
kanji_kyouiku_target_counts = {lvl: kanji_source[lvl] for lvl in required_kanji_grade}
kanji_jouyou_target_counts = kanji_source['jouyou_index'].nunique() if 'jouyou_index' in kanji_source else 0
MASTERY_THRESHOLD = 21 # Consistent with flashcard logic

# --- 4. Helper functions ---
def get_JLPT_stats(df, level):
    """
    Calculates the number of items mastered within a specific JLPT level.

    An item is considered mastered if its spaced repetition 'interval' 
    meets or exceeds the global MASTERY_THRESHOLD.

    Args:
        df (pd.DataFrame): The dataset to query (vocabulary or Kanji).
        level (str): The target JLPT level to filter by (e.g., 'N5', 'N4').

    Returns:
        int: The total count of mastered items for the specified level.
    """
    JLPT_level_df = df[df['JLPT_level'] == level]
    mastered = len(JLPT_level_df[JLPT_level_df['interval'] >= MASTERY_THRESHOLD])
    return mastered

def get_kyouiku_stats(df, level):
    """
    Calculates the number of Kanji mastered within a specific Japanese school grade.

    Filters the dataset based on the 'kyouiku_grade' column and counts items 
    that have an 'interval' meeting or exceeding the global MASTERY_THRESHOLD.

    Args:
        df (pd.DataFrame): The Kanji dataset to query.
        level (str): The target school grade to filter by (e.g., 'Grade 1').

    Returns:
        int: The total count of mastered Kanji for the specified school grade.
    """
    kyouiku_level_df = df[df['kyouiku_grade'] == level]
    mastered = len(kyouiku_level_df[kyouiku_level_df['interval'] >= MASTERY_THRESHOLD])
    return mastered

def render_gauge(current, target, label, color):
    """
    Generates a Plotly gauge chart to visualize progress towards a specific goal.

    Calculates the completion percentage (capped at 100%) and formats a 
    semi-circular gauge indicator with customized typography and margins.

    Args:
        current (int or float): The current progress value (e.g., mastered items).
        target (int or float): The target goal value (e.g., total items required).
        label (str): The title text displayed inside the gauge (e.g., 'JLPT N5').
        color (str): The hex color code for the progress bar arc.

    Returns:
        plotly.graph_objects.Figure: The configured Plotly gauge chart figure.
    """
    pct = min((current / target) * 100, 100)
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = pct,
        number = {'suffix': "%", 'font': {'size': 24}},
        title = {'text': label, 'font': {'size': 18}},
        gauge = {
            'axis': {'range': [0, target]},
            'bar': {'color': color},
            'steps': [
                {'range': [0, target], 'color': "#E8E1DF"},              
            ],
            
        }
    ))
    fig.update_layout(height=200, margin=dict(l=10, r=10, t=50, b=10))
    return fig


# --- 5. UI Rendering ---
JLPT_levels = ['N5', 'N4', 'N3']
kyouiku_levels = ['Grade 1', 'Grade 2', 'Grade 3', 'Grade 4', 'Grade 5', 'Grade 6']

# 5.1 - Vocab section
st.markdown(f"""
    <div style="text-align: left; display: flex; justify-content: left; align-items: baseline; gap: 5px; margin-bottom: 20px;">
        <h2 style="margin: 0; display: inline;">
            🈂️ 
            <span style="margin-right: 2px;">
                <ruby>単<rt style="color: gray; font-size: 0.4em;">たん</rt></ruby>
                <ruby>語<rt style="color: gray; font-size: 0.4em;">ご</rt></ruby>
            </span>
        </h2>
        <h2 style="margin: 0; display: inline;"> - Vocabulary :</h2>
    </div>""", unsafe_allow_html=True)
v_cols = st.columns(len(JLPT_levels))
for i, lvl in enumerate(JLPT_levels):
    mastered = get_JLPT_stats(vocab_df, lvl)
    with v_cols[i]:
        st.plotly_chart(render_gauge(mastered, voc_target_counts[lvl], f"JLPT {lvl}", "#242164"), use_container_width=True)
        st.markdown(
            f"""<div style="text-align: center; margin-top: -10px;">
                <small style="color: gray;">{int(mastered)} / {int(voc_target_counts[lvl])} words</small>
            </div>""", 
            unsafe_allow_html=True
        )

st.divider()

# 5.2 - Kanji section
st.markdown(f"""
    <div style="text-align: left; display: flex; justify-content: left; align-items: baseline; gap: 5px; margin-bottom: 20px;">
        <h2 style="margin: 0; display: inline;">
            🈳 
            <span style="margin-right: 2px;">
                <ruby>漢<rt style="color: gray; font-size: 0.4em;">かん</rt></ruby>
                <ruby>字<rt style="color: gray; font-size: 0.4em;">じ</rt></ruby>
            </span>
        </h2>
        <h2 style="margin: 0; display: inline;"> - Kanji :</h2>
    </div>""", unsafe_allow_html=True)

# 5.2.1 - JLPT kanji
st.markdown(f"""
    <div style="text-align: left; display: flex; justify-content: left; align-items: baseline; gap: 5px; margin-bottom: 20px;">
        <h3 style="margin: 0; display: inline;">
            🎌 
            <span style="margin-right: 2px;">
                <ruby>日<rt style="color: gray; font-size: 0.4em;">に</rt></ruby>
                <ruby>本<rt style="color: gray; font-size: 0.4em;">ほん</rt></ruby>
                <ruby>語<rt style="color: gray; font-size: 0.4em;">ご</rt></ruby>
                <ruby>能<rt style="color: gray; font-size: 0.4em;">のう</rt></ruby>
                <ruby>力<rt style="color: gray; font-size: 0.4em;">りょく</rt></ruby>
                <ruby>試<rt style="color: gray; font-size: 0.4em;">し</rt></ruby>
                <ruby>漢<rt style="color: gray; font-size: 0.4em;">けん</rt></ruby>
                <ruby>の<rt style="color: gray; font-size: 0.4em;"> </rt></ruby>
                <ruby>漢<rt style="color: gray; font-size: 0.4em;">かん</rt></ruby>
                <ruby>字<rt style="color: gray; font-size: 0.4em;">じ</rt></ruby>
            </span>
        </h3>
        <h3 style="margin: 0; display: inline;"> - JLPT Kanji :</h3>
    </div>""", unsafe_allow_html=True)
k_cols = st.columns(len(JLPT_levels))
for i, lvl in enumerate(JLPT_levels):
    mastered = get_JLPT_stats(kanji_df, lvl)
    with k_cols[i]:
        st.plotly_chart(render_gauge(mastered, kanji_JLPT_target_counts[lvl], f"JLPT {lvl}", "#e63946"), use_container_width=True)
        st.markdown(
            f"""<div style="text-align: center; margin-top: -10px;">
                <small style="color: gray;">{int(mastered)} / {int(kanji_JLPT_target_counts[lvl])} kanji</small>
            </div>""", 
            unsafe_allow_html=True
        )
st.divider()

# 5.2.2 - Kyouiku kanji
st.markdown(f"""
    <div style="text-align: left; display: flex; justify-content: left; align-items: baseline; gap: 5px; margin-bottom: 20px;">
        <h3 style="margin: 0; display: inline;">
            🎓
            <span style="margin-right: 2px;">
                <ruby>教<rt style="color: gray; font-size: 0.4em;">きょう</rt></ruby>
                <ruby>育<rt style="color: gray; font-size: 0.4em;">いく</rt></ruby>
                <ruby>漢<rt style="color: gray; font-size: 0.4em;">かん</rt></ruby>
                <ruby>字<rt style="color: gray; font-size: 0.4em;">じ</rt></ruby>
            </span>
        </h3>
        <h3 style="margin: 0; display: inline;"> - Kyōiku Kanji:</h3>
    </div>""", unsafe_allow_html=True)
k_cols = st.columns(len(kyouiku_levels))
for i, lvl in enumerate(kyouiku_levels):
    mastered = get_kyouiku_stats(kanji_df, lvl)
    with k_cols[i]:
        st.plotly_chart(render_gauge(mastered, kanji_kyouiku_target_counts[lvl], f"{lvl} Kanji", "#e63946"), use_container_width=True)
        st.markdown(
            f"""<div style="text-align: center; margin-top: -10px;">
                <small style="color: gray;">{int(mastered)} / {int(kanji_kyouiku_target_counts[lvl])} kanji</small>
            </div>""", 
            unsafe_allow_html=True
        )
st.divider()

# 5.2.3 - Jouyou kanji
st.markdown(f"""
    <div style="text-align: left; display: flex; justify-content: left; align-items: baseline; gap: 5px; margin-bottom: 20px;">
        <h3 style="margin: 0; display: inline;">
            🪸 
            <span style="margin-right: 2px;">
                <ruby>常<rt style="color: gray; font-size: 0.4em;">じょう</rt></ruby>
                <ruby>用<rt style="color: gray; font-size: 0.4em;">よう</rt></ruby>
                <ruby>漢<rt style="color: gray; font-size: 0.4em;">かん</rt></ruby>
                <ruby>字<rt style="color: gray; font-size: 0.4em;">じ</rt></ruby>
            </span>
        </h3>
        <h3 style="margin: 0; display: inline;"> - Jōyō Kanji:</h3>
    </div>""", unsafe_allow_html=True)
total = 2137 # current number of jouyou kanji on latest government list published
percentage = (mastered_count / total) * 100
fig = go.Figure(go.Indicator(
    mode = "gauge+number",
    value = mastered_count,
    number = {
        'suffix': f"<br><span style='font-size:0.6em;color:gray'>{percentage:.1f}%</span>",
        'font': {'size': 36}
    },
    title = {'text': "Practiced", 'font': {'size': 18}},
    gauge = {'axis': {'range': [0, total]}, 'bar': {'color':  "#e63946"},
             'steps':[ {'range': [0, total], 'color': "#E8E1DF"}]           
            }
    
))
st.plotly_chart(fig)


# --- 6. Study Health ---
st.divider()
st.subheader("🧠 Memory Building")
daily_counts = history_df.copy()
daily_counts['day'] = daily_counts['date'].dt.date
chart_data = daily_counts.groupby(['day', 'type']).size().reset_index(name='count')
chart_data['cumulative_sum'] = chart_data.groupby('type')['count'].cumsum()
fig = px.bar(
    chart_data, 
    x='day', 
    y='cumulative_sum', 
    color='type',
    barmode='group',
    title="Daily Progress",
    color_discrete_map={'Vocab': '#242164', 'Kanji': '#e63946'})
fig.update_layout(
   xaxis_title=None,
   yaxis_title=None,
   legend_title=None,
   hovermode="x unified",
   paper_bgcolor='rgba(0,0,0,0)',
   plot_bgcolor='rgba(0,0,0,0)',
   font_color='#242164')
st.plotly_chart(fig, use_container_width=True)

# Rolling weekly study statistics
date_range = history_df['date'].max() - history_df['date'].min()
if date_range >= pd.Timedelta(days=7):
    last_7_days = history_df[history_df['date'] >= (history_df['date'].max() - pd.Timedelta(days=7))]
    v_count = len(last_7_days[last_7_days['type'] == 'Vocab'])
    k_count = len(last_7_days[last_7_days['type'] == 'Kanji'])
    valid_grades = last_7_days[last_7_days['grade'].isin(kyouiku_levels)]['grade']
st.markdown(f"""
    <div style="background-color: #E8E1DF; padding: 15px; border-radius: 5px; border-left: 5px solid #242164; color: #242164;">
        <strong>Rolling weekly summary:</strong><br>
        <ul>
            <li><strong>Vocabulary:</strong> {v_count} words reviewed</li>
            <li><strong>Kanji:</strong> {k_count} characters practiced</li>
            <li><strong>Top JLPT Level Focused:</strong> {last_7_days['level'].mode()[0] if not last_7_days.empty else 'N/A'}</li>
            <li><strong>Top School Grade Focused:</strong> {valid_grades.mode()[0] if not valid_grades.empty else 'N/A'}</li>
        </ul>
    </div>
""", unsafe_allow_html=True)

st.divider()

if st.button("🏯 Home page"):
    st.switch_page(HOME_PAGE)

