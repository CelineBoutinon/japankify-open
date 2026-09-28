# To launch the app run:
# python -m streamlit run japankify.py
# in the terminal from the root directory of the project
# This will start the Streamlit server, and the app will open in your default browser at 
# http://localhost:8501

import streamlit as st
import pandas as pd
from theme_utils import apply_japanese_theme, japanese_header
import random
from datetime import datetime, timedelta
from srs_logging_utils import upload_stats_file_to_s3, upload_matplotlib_fig_to_s3
import numpy as np
import matplotlib.pyplot as plt
from dotenv import load_dotenv


# --- 1. Config & Theme Setup ---
# Force load the .env file
load_dotenv(override=True)

# Force matplotlib to render at higher dpi
plt.rcParams['figure.dpi'] = 400

# --- Load data ---
voc_file_path = "assets/my_wordbank_all_voc.parquet" 
kanji_file_path = "assets/my_wordbank_all_kan.parquet" 
metadata_file_path = "assets/my_wordbank_voc_kan_metadata.json"
log_file_path = "assets/review_history.parquet"
kotowaza_file_path = "assets/kotowaza_sample.csv"
# These datasets are available from https://github.com/CelineBoutinon/japankify-open/assets

# Streamlit page config
st.set_page_config(page_title="Japankify - Home", page_icon="🏯", layout="wide")
apply_japanese_theme()

# --- 2. Load Data ---
# 2.1 - Parquet file reading with graceful fallback to empty DataFrame
def _safe_read_parquet(file_path, default_columns=None):
    """
    Safely reads a parquet file into a DataFrame, falling back gracefully on failure.

    Args:
        file_path (str): The filesystem path to the Parquet file.
        default_columns (list of str, optional): A list of column names to initialize 
            an empty DataFrame with if the file read fails. Defaults to None.

    Returns:
        pd.DataFrame: The loaded DataFrame, or an empty DataFrame (with default 
            columns if provided) if the file cannot be read.
    """
    try:
        return pd.read_parquet(file_path)
    except Exception:
        return pd.DataFrame(columns=default_columns) if default_columns else pd.DataFrame()

# 2.2 - Cached Streamlit Data Ingestion Layer
@st.cache_data
def load_all_stats_data(voc_path, kan_path, log_path, meta_path):
    """
    Unified ingestion engine. Caches core dataframes and the configuration 
    dictionary atomically to eliminate redundant file system reads.

    Args:
        voc_path (str): The filesystem path to the vocabulary Parquet file.
        kan_path (str): The filesystem path to the kanji Parquet file.
        log_path (str): The filesystem path to the review history Parquet file.
        meta_path (str): The filesystem path to the JSON metadata file.

    Returns:
        tuple: A 4-element tuple containing:
            - df_voc (pd.DataFrame): Vocabulary data.
            - df_kan (pd.DataFrame): Kanji data.
            - df_log (pd.DataFrame): Review history logs.
            - meta_dict (dict): Parsed metadata configuration dictionary.
    """
    df_voc = _safe_read_parquet(voc_path)
    df_kan = _safe_read_parquet(kan_path)
    df_log = _safe_read_parquet(log_path, default_columns=['date', 'item', 'type', 'level', 'grade'])
    try:
        meta_df = pd.read_json(meta_path)
        meta_dict = meta_df.to_dict()
    except Exception:
        meta_dict = {
            "vocabulary": {"total": 5464, "mastered": 0},
            "kanji": {"total": 694, "mastered": 0}
        }
    return df_voc, df_kan, df_log, meta_dict

# 2.3 - Global State Initialization
vocab_df, kanji_df, history_df, metadata_dict = load_all_stats_data(
    voc_path=voc_file_path,
    kan_path=kanji_file_path,
    log_path=log_file_path,
    meta_path=metadata_file_path
)
min_date = history_df['date'].min().date() if not history_df.empty else datetime.today().date() - timedelta(days=30)
max_date = history_df['date'].max().date() if not history_df.empty else datetime.today().date()

# 2.4 - Apply filter masks
mask = (history_df['date'].dt.date >= min_date) & (history_df['date'].dt.date <= max_date)
filtered_df = history_df[mask].copy()

vocab_history = filtered_df[filtered_df['type'] == 'Vocab']
kanji_history = filtered_df[filtered_df['type'] == 'Kanji']

# 2.5 - Helper Function to Create Dual-Axis Grouped Charts via Matplotlib for weekly summary statistics email
def create_srs_chart(data_df, item_type_label, color_palette):
    """
    Builds a pixel-perfect, static dual-axis chart with clustered bars for daily level 
    metrics and matching cumulative trendlines anchored precisely over their respective 
    level columns.

    Args:
        data_df (pd.DataFrame): The filtered review history dataset to plot.
        item_type_label (str): The title label for the chart (e.g., 'Vocabulary (All-Time)').
        color_palette (dict): A nested dictionary mapping JLPT levels to their 
            hex color codes for 'bar' and 'line' aesthetics.

    Returns:
        matplotlib.figure.Figure or None: The generated Matplotlib figure object, 
            or None if the provided data_df is empty.
    """
    if data_df.empty:
        return None
        
    plot_df = data_df.copy()
    
    # Standardize dates to clean localized string formats for categorical indexing
    plot_df['date_only'] = pd.to_datetime(plot_df['date']).dt.date
    daily_grouped = plot_df.groupby(['date_only', 'level']).size().reset_index(name='daily_count')
    
    # Extract uniquely sorted tracking dates as clean strings
    unique_dates = sorted(daily_grouped['date_only'].unique())
    date_strings = [d.strftime('%Y-%m-%d') for d in unique_dates]
    
    all_levels = ['N5', 'N4', 'N3', 'N2', 'N1']
    active_levels = [l for l in all_levels if l in daily_grouped['level'].unique()]
    
    if not unique_dates:
        return None

    # Generate a tight multi-index matrix mapping active dates to active levels
    multi_idx = pd.MultiIndex.from_product([unique_dates, active_levels], names=['date_only', 'level'])
    compact_grid = pd.DataFrame(index=multi_idx).reset_index()
    
    # Merge matrix grid back with aggregated review log counts
    chart_prep = pd.merge(compact_grid, daily_grouped, on=['date_only', 'level'], how='left').fillna(0)
    chart_prep = chart_prep.sort_values(by=['date_only', 'level']).reset_index(drop=True)
    
    # Compute running total matching sequential timeline flow
    chart_prep['cumulative_sum'] = chart_prep.groupby('level')['daily_count'].cumsum()
    
    # Initialize Matplotlib Canvas Layout & Geometry Math ---
    fig, ax1 = plt.subplots(figsize=(12, 5.5), dpi=200, layout='tight')
    ax2 = ax1.twinx() 
    
    # Set backgrounds to standard solid white for crisp visibility
    fig.patch.set_facecolor('white')
    ax1.set_facecolor('white')
    
    # Compute manual positional offsets for grouping bars side-by-side
    x_indexes = np.arange(len(unique_dates)) 
    total_active = len(active_levels)
    bar_width = 0.20
    
    # Calculate starting offset so group clusters remain perfectly centered on the date tick
    start_offset = -((total_active - 1) * bar_width) / 2.0
    
    # Render Clustered Bars and Center Trendlines Simultaneously
    for idx, lvl in enumerate(active_levels):
        lvl_data = chart_prep[chart_prep['level'] == lvl].reset_index(drop=True)
        
        # Calculate precise pixel shifts for this specific level column group
        exact_x = x_indexes + start_offset + (idx * bar_width)
        
        # Draw Native Bars (Y-Axis 1)
        ax1.bar(
            exact_x,
            lvl_data['daily_count'],
            width=bar_width,
            color=color_palette[lvl]['bar'],
            label=f"{lvl} Studied",
            edgecolor='none',
            zorder=2
        )
        
        # Draw Trendlines Pinned Exactly on the Calculated exact_x coordinates (Y-Axis 2)
        ax2.plot(
            exact_x,
            lvl_data['cumulative_sum'],
            color=color_palette[lvl]['line'],
            marker='o',
            linewidth=2.5,
            markersize=6,
            label=f"{lvl} Cumulative Total",
            zorder=3
        )
        
    # Polish Typography and Layout Aesthetics (Matching your #242164 Navy theme)
    ax1.set_title(f"Daily Review Distribution & Cumulative Progress: {item_type_label}", 
                 fontsize=14, pad=15, color='#242164', fontweight='bold', family='sans-serif')
    
    ax1.set_xlabel("Review Date", color='#242164', fontsize=11, fontweight='semibold', labelpad=10)
    ax1.set_ylabel("Daily Items Studied Count", color='#242164', fontsize=11, fontweight='semibold')
    ax2.set_ylabel("Total Cumulative Items Progress", color='#242164', fontsize=11, fontweight='semibold')
    
    # Apply matching coordinate grids to the categorical string lists
    ax1.set_xticks(x_indexes)
    ax1.set_xticklabels(date_strings, rotation=15)
    
    # Enforce color harmony on axis labels and borders
    ax1.tick_params(axis='x', colors='#242164')
    ax1.tick_params(axis='y', colors='#242164')
    ax2.tick_params(axis='y', colors='#242164')
    
    # Mute outer boundary lines
    for ax in [ax1, ax2]:
        for spine in ax.spines.values():
            spine.set_color('#242164')
            spine.set_alpha(0.3)
            
    # Add a soft horizontal grid baseline layer to the primary canvas axis
    ax1.grid(axis='y', linestyle='--', alpha=0.4, color='#242164', zorder=1)
    
    # Consolidate and format legends neatly below the chart area
    handles1, labels1 = ax1.get_legend_handles_labels()
    handles2, labels2 = ax2.get_legend_handles_labels()
    
    # Render a clean, non-overlapping unified layout legend
    fig.legend(handles1 + handles2, labels1 + labels2, 
               loc='upper center', bbox_to_anchor=(0.5, -0.05), ncol=2, frameon=False, fontsize=9)
    
    return fig


# --- 3. Style Palettes Specification ---
vocab_colors = {
    'N5': {'bar': '#A9D6E5', 'line': '#014F86'},
    'N4': {'bar': '#89C2D9', 'line': '#2A6F97'},
    'N3': {'bar': '#61A5C2', 'line': '#4682B4'},
    'N2': {'bar': '#4C95AF', 'line': '#1D3557'},
    'N1': {'bar': '#2C7A7B', 'line': '#004D40'}
}

kanji_colors = {
    'N5': {'bar': '#FAD2E1', 'line': '#E63946'},
    'N4': {'bar': '#FFB5A7', 'line': '#D90429'},
    'N3': {'bar': '#FCCBB5', 'line': '#F77F00'},
    'N2': {'bar': '#E8AEB7', 'line': '#9B2226'},
    'N1': {'bar': '#D8B4F8', 'line': '#6A0DAD'}
}

JLPT_colors = {
    'N5': {'bar': 'yellow', 'line': 'gold'},
    'N4': {'bar': 'plum', 'line': 'orchid'},
    'N3': {'bar': 'lime', 'line': 'limegreen'},
    'N2': {'bar': 'lighsalmon', 'line': 'darkorange'},
    'N1': {'bar': 'lavenderblush', 'line': 'deppink'}
}

# --- 4. Sidebar ---
with st.sidebar:
    # 4.1 - Reward selection for end of session emoji rain
    reward_list = ['🍙', '🍣', '🥟', '🍤', '🍮🥄', '🪭', '🌸', '🏮', '🎏', '🍜', '🍥', '🍡', '🍛', '🪷']
    # Randomly select reward
    if "reward" not in st.session_state:
        st.session_state.reward = random.choice(reward_list)
    # Optional: Display the selected reward to the user
    # st.write(f"Your mystery reward for this session: {st.session_state.reward}")
    # st.divider()
    
    # 4.2 - Quiet pipeline execution
    # Charts compile inside the socket handler and silently sync to S3
    if st.button("🚀 Sync progress", use_container_width=True):
        with st.spinner("Opening secure runtime socket connection to AWS data endpoints..."):
            # Isolate tracking channels straight from the scoped filtered dataframes
            vocab_history = filtered_df[filtered_df['type'] == 'Vocab']
            kanji_history = filtered_df[filtered_df['type'] == 'Kanji']
            # Quietly construct complete history figures in background memory frames
            v_fig = create_srs_chart(vocab_history, "Vocabulary (All-Time)", vocab_colors)
            k_fig = create_srs_chart(kanji_history, "Kanji (All-Time)", kanji_colors)
            errors = []
            successes = []
            # Extract memory streams to S3
            if v_fig:
                s2, m2 = upload_matplotlib_fig_to_s3(v_fig, base_filename="vocab_chart")
                (successes if s2 else errors).append(m2)
            if k_fig:
                s3, m3 = upload_matplotlib_fig_to_s3(k_fig, base_filename="kanji_chart")
                (successes if s3 else errors).append(m3)
            # Ship Parquet file to kick off AWS EventBridge pipeline
            s1, m1 = upload_stats_file_to_s3(log_file_path, base_filename="review_history", extension="parquet")
            (successes if s1 else errors).append(m1)
            # Display transaction summary feedbacks
            if not errors:
                st.success("🎯 **S3 Data Lake Sync Successful!** ")
                with st.expander("AWS transaction signatures"):
                    for s in successes:
                        st.write(f"✅ {s}")
            else:
                st.error("⚠️ **S3 Data Lake Sync Incomplete.** ")
                for e in errors:
                    st.write(f"❌ {e}")
                for s in successes:
                    st.write(f"✅ {s}")


# --- 5. Header Section ---
st.markdown("<br>", unsafe_allow_html=True) # Spacer
japanese_header("Japankify", "Your Path to JLPT N3 Mastery")

# --- 6. Kotowaza logic---
# 6.1 - Fetch a random Yojijukugo from the dataset with caching to avoid redundant reads
@st.cache_data(ttl=3600)
def get_random_koto():
    """
    Fetches a random Yojijukugo (four-character idiom) from the Kotowaza dataset.

    Returns:
        pd.Series or None: A single row representing the selected idiom, 
            or None if the file cannot be read or no Yojijukugo are found.
    """
    try:
        # Load the full CSV
        df_koto = pd.read_csv(kotowaza_file_path)
        # FILTER: Keep only rows where category is '四字熟語'
        df_yoji = df_koto[df_koto['category'] == '四字熟語']
        if df_yoji.empty:
            st.warning("No Yojijukugo found in the data.")
            return None
        # Select randomly from the filtered subset
        random_idx = random.randint(0, len(df_yoji) - 1)
        return df_yoji.iloc[random_idx]
    except Exception as e:
        st.error(f"Error loading Yojijukugo: {e}")
        return None

koto_data = get_random_koto()

# 6.2 - Display the selected Yojijukugo with interactive Kanji links to the dictionary page
if koto_data is not None:
    with st.container(border=True):
        st.markdown(f"""
    <div style="text-align: left; display: flex; justify-content: left; align-items: baseline; gap: 5px; margin-bottom: 20px;">
        <h2 style="margin: 0; display: inline;">
            🦪 Japanese pearls of wisdom - today's 
            <span style="margin-right: 2px;">
                <ruby>四<rt style="color: gray; font-size: 0.4em;">よ</rt></ruby><ruby>字<rt style="color: gray; font-size: 0.4em;">じ</rt></ruby><ruby>熟<rt style="color: gray; font-size: 0.4em;">じゅく</rt></ruby><ruby>語<rt style="color: gray; font-size: 0.4em;">ご</rt></ruby>
            </span>
        </h2>
        <h2 style="margin: 0; display: inline;">is:</h2>
    </div>""", unsafe_allow_html=True)
        st.write("")        
        col1, col2 = st.columns([2, 3])
        with col1:
            # Display the 4 Kanji as clickable links
            koto_str = koto_data['idiom']
            # Helper function to check if a character is Kanji
            def is_kanji(ch):
                """
                Checks whether a given character falls within the standard Unicode CJK Unified Ideographs block.

                Args:
                    ch (str): A single character string to evaluate.

                Returns:
                    bool: True if the character is a Kanji, False otherwise.
                """
                return '\u4e00' <= ch <= '\u9faf'
            
            links_html = " ".join([
                f'<a href="/Dictionary?query={char}" target="_self" style="text-decoration:none; font-size:2.5em; color:#E63946;">{char}</a>'
                if is_kanji(char) else f'<span style="font-size:2.5em; color:'#242164';">{char}</span>'
                for char in koto_str
            ])

            st.markdown(f'<div style="text-align:center; line-height:1.2;">{links_html}</div>', unsafe_allow_html=True)
            st.markdown(f'<div style="text-align:center; line-height:1.2;">click a Kanji to lookup</div>', unsafe_allow_html=True)
            
        with col2:
            st.markdown(f"#### {koto_data['id_kana']}{"   --   "}{koto_data['translation']}")
            st.write(f"*{koto_data['meaning']}*")
            st.write(f"*{koto_data['english equivalent']}*")

# --- 7. Main Focus Section ---
st.markdown("### 🎯 Study Focus")
CONTAINER_HEIGHT = 480
batch_size = [1, 5, 10, 25, 50, 75, 100]
c1, c2 = st.columns(2)
# 7.1 - Parameters selection for vocab review session
with c1:
    with st.container(border=True, height=CONTAINER_HEIGHT):
        st.markdown("#### 🈂️ Vocabulary")
        st.write("Review words and phrases based on JLPT levels.")
        st.write("")
        st.write("") 
        st.write("") 
        st.write("") 
        st.write("") 
        v_level = st.selectbox("Select JLPT Level", ["N5", "N4", "N3", "N2", "N1","All JLPT"], key="v_level")
        v_batch = st.pills(label="Session Size", options=batch_size, key="v_batch", selection_mode="single", default=1)
        v_due = st.checkbox("Only review due items", value=True, key="v_due")
        
        if st.button("Start Vocab Review", use_container_width=True, type="primary"):
            st.session_state.level = v_level
            st.session_state.batch_size = v_batch
            st.session_state.only_due = v_due
            if 'vocab_session_indices' in st.session_state:
                del st.session_state.vocab_session_indices
            st.session_state.vocab_pos = 0
            st.switch_page("pages/1_🈂️_Vocabulary.py")

# 7.2 - Parameters selection for kanji review session
with c2:
    with st.container(border=True, height=CONTAINER_HEIGHT):
        st.markdown("#### 🈳 Kanji")
        st.write("Practice characters by JLPT level or Primary School Grade.")
        
        k_mode = st.radio("Group by:", ["JLPT Level", "School Grade"], horizontal=True)
        
        if k_mode == "JLPT Level":
            k_filter = st.selectbox("Select JLPT Level", ["N5", "N4", "N3", "N2", "N1", "All JLPT"], key="k_level")
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
            st.switch_page("pages/2_🈳_Kanji.py")
            