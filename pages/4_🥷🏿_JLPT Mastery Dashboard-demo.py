import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from theme_utils import apply_japanese_theme, japanese_header
from datetime import datetime, timedelta

HOME_PAGE = "japankify.py"

# --- 1. Config & Theme Setup ---
st.set_page_config(page_title='Dashboard', page_icon='🥷🏿', layout="wide")
apply_japanese_theme()
japanese_header("🥷🏿 JLPT Mastery Dashboard - Demo Version", 'Track your progress towards JLPT level goals')

st.info("💡 **Demo Mode Active:** This dashboard uses realistic, hardcoded dummy statistics to demonstrate the UI layout of a user actively studying for the N3.")

# --- 2. Static Dummy Data Initialization ---
# Simulated Targets based on real JLPT/Jouyou counts
voc_target_counts = {'N5': 675, 'N4': 680, 'N3': 1800}
kanji_JLPT_target_counts = {'N5': 103, 'N4': 181, 'N3': 366}
kanji_kyouiku_target_counts = {
    'Grade 1': 80, 'Grade 2': 160, 'Grade 3': 200, 
    'Grade 4': 200, 'Grade 5': 185, 'Grade 6': 181
}
total_jouyou = 2137

# Simulated Progress for an N3 Student
voc_mastered = {'N5': 662, 'N4': 580, 'N3': 850}
kanji_JLPT_mastered = {'N5': 103, 'N4': 165, 'N3': 150}
kanji_kyouiku_mastered = {
    'Grade 1': 80, 'Grade 2': 155, 'Grade 3': 120, 
    'Grade 4': 40, 'Grade 5': 15, 'Grade 6': 0
}
jouyou_mastered_count = 893

# --- 3. Helper functions ---
def render_gauge(current, target, label, color):
    """Generates a Plotly gauge chart to visualize progress towards a specific goal."""
    pct = min((current / target) * 100, 100)
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = pct,
        number = {'suffix': "%", 'font': {'size': 24}},
        title = {'text': label, 'font': {'size': 18}},
        gauge = {
            'axis': {'range': [0, target]},
            'bar': {'color': color},
            'steps': [{'range': [0, target], 'color': "#E8E1DF"}],
        }
    ))
    fig.update_layout(height=200, margin=dict(l=10, r=10, t=50, b=10))
    return fig

# --- 4. UI Rendering ---
JLPT_levels = ['N5', 'N4', 'N3']
kyouiku_levels = ['Grade 1', 'Grade 2', 'Grade 3', 'Grade 4', 'Grade 5', 'Grade 6']

# 4.1 - Vocab section
st.markdown(f"""
    <div style="text-align: left; display: flex; justify-content: left; align-items: baseline; gap: 5px; margin-bottom: 20px;">
        <h2 style="margin: 0; display: inline;">🈂️ <ruby>単<rt>たん</rt></ruby><ruby>語<rt>ご</rt></ruby></h2>
        <h2 style="margin: 0; display: inline;"> - Vocabulary :</h2>
    </div>""", unsafe_allow_html=True)

v_cols = st.columns(len(JLPT_levels))
for i, lvl in enumerate(JLPT_levels):
    with v_cols[i]:
        st.plotly_chart(render_gauge(voc_mastered[lvl], voc_target_counts[lvl], f"JLPT {lvl}", "#242164"), use_container_width=True)
        st.markdown(f"""<div style="text-align: center; margin-top: -10px;">
            <small style="color: gray;">{voc_mastered[lvl]} / {voc_target_counts[lvl]} words</small>
        </div>""", unsafe_allow_html=True)

st.divider()

# 4.2 - Kanji section
st.markdown(f"""
    <div style="text-align: left; display: flex; justify-content: left; align-items: baseline; gap: 5px; margin-bottom: 20px;">
        <h2 style="margin: 0; display: inline;">🈳 <ruby>漢<rt>かん</rt></ruby><ruby>字<rt>じ</rt></ruby></h2>
        <h2 style="margin: 0; display: inline;"> - Kanji :</h2>
    </div>""", unsafe_allow_html=True)

# 4.2.1 - JLPT kanji
st.markdown("### 🎌 JLPT Kanji :")
k_cols = st.columns(len(JLPT_levels))
for i, lvl in enumerate(JLPT_levels):
    with k_cols[i]:
        st.plotly_chart(render_gauge(kanji_JLPT_mastered[lvl], kanji_JLPT_target_counts[lvl], f"JLPT {lvl}", "#e63946"), use_container_width=True)
        st.markdown(f"""<div style="text-align: center; margin-top: -10px;">
            <small style="color: gray;">{kanji_JLPT_mastered[lvl]} / {kanji_JLPT_target_counts[lvl]} kanji</small>
        </div>""", unsafe_allow_html=True)
st.divider()

# 4.2.2 - Kyouiku kanji
st.markdown("### 🎓 Kyōiku Kanji:")
k_cols = st.columns(len(kyouiku_levels))
for i, lvl in enumerate(kyouiku_levels):
    with k_cols[i]:
        st.plotly_chart(render_gauge(kanji_kyouiku_mastered[lvl], kanji_kyouiku_target_counts[lvl], f"{lvl}", "#e63946"), use_container_width=True)
        st.markdown(f"""<div style="text-align: center; margin-top: -10px;">
            <small style="color: gray;">{kanji_kyouiku_mastered[lvl]} / {kanji_kyouiku_target_counts[lvl]}</small>
        </div>""", unsafe_allow_html=True)
st.divider()

# 4.2.3 - Jouyou kanji
st.markdown("### 🪸 Jōyō Kanji:")
percentage = (jouyou_mastered_count / total_jouyou) * 100
fig = go.Figure(go.Indicator(
    mode = "gauge+number",
    value = jouyou_mastered_count,
    number = {
        'suffix': f"<br><span style='font-size:0.6em;color:gray'>{percentage:.1f}%</span>",
        'font': {'size': 36}
    },
    title = {'text': "Practiced", 'font': {'size': 18}},
    gauge = {'axis': {'range': [0, total_jouyou]}, 'bar': {'color':  "#e63946"},
             'steps':[ {'range': [0, total_jouyou], 'color': "#E8E1DF"}]           
            }
))
st.plotly_chart(fig)

# --- 5. Study Health (Static Simulated Chart) ---
st.divider()
st.subheader("🧠 Memory Building")

# Generate 14 days of realistic dummy daily progress data
today = datetime.today().date()
dates = [today - timedelta(days=x) for x in range(14)][::-1]
dummy_vocab_daily = [45, 60, 55, 30, 0, 80, 95, 40, 50, 65, 70, 20, 85, 40]
dummy_kanji_daily = [15, 20, 10, 5, 0, 25, 30, 15, 20, 25, 30, 5, 35, 15]

chart_data = pd.DataFrame({
    'day': dates * 2,
    'count': dummy_vocab_daily + dummy_kanji_daily,
    'type': ['Vocab'] * 14 + ['Kanji'] * 14
})
chart_data['cumulative_sum'] = chart_data.groupby('type')['count'].cumsum()

fig = px.bar(
    chart_data, 
    x='day', y='cumulative_sum', color='type',
    barmode='group', title="Daily Progress (Simulated)",
    color_discrete_map={'Vocab': '#242164', 'Kanji': '#e63946'}
)
fig.update_layout(
   xaxis_title=None, yaxis_title=None, legend_title=None,
   hovermode="x unified", paper_bgcolor='rgba(0,0,0,0)',
   plot_bgcolor='rgba(0,0,0,0)', font_color='#242164'
)
st.plotly_chart(fig, use_container_width=True)

st.markdown(f"""
    <div style="background-color: #E8E1DF; padding: 15px; border-radius: 5px; border-left: 5px solid #242164; color: #242164;">
        <strong>Rolling weekly summary (Simulated):</strong><br>
        <ul>
            <li><strong>Vocabulary:</strong> 405 words reviewed</li>
            <li><strong>Kanji:</strong> 145 characters practiced</li>
            <li><strong>Top JLPT Level Focused:</strong> N3</li>
            <li><strong>Top School Grade Focused:</strong> Grade 3</li>
        </ul>
    </div>
""", unsafe_allow_html=True)

st.divider()
if st.button("🏯 Home page"):
    st.switch_page(HOME_PAGE)