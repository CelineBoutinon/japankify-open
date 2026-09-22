import streamlit as st

# --- Define theme colors ---
# Sango Red - for progress bars and primary buttons
primaryColor = "#E63946"
# Gofun White - off-white background with "paper" feel
backgroundColor = "#F7F2F0"
# Sakura-nezumi - for sidebar and secondary elements
secondaryBackgroundColor = "#E8E1DF"
# Kachi Navy - for all text
textColor = "#242164"


# --- Theme application function ---
def apply_japanese_theme():
    """
    Injects custom CSS into the Streamlit app to apply a minimalist Japanese-inspired 
    aesthetic, including custom fonts, colors, and button styling.

    Returns:
        None
    """
    st.markdown(f"""
        <style>
        /* Main background */
        .stApp {{
            background-color: {backgroundColor};
        }}
        
        /* Headers - Japanese Typography Style */
        h1, h2, h3 {{
            color: {textColor} !important;
            font-family: 'Hiragino Mincho ProN', 'MS Mincho', serif;
            letter-spacing: 0.05em;
        }}
        
        /* Buttons - Modern Minimalist */
        .stButton>button {{
            border-radius: 2px;
            border: 1px solid {textColor};
            background-color: transparent;
            color: {textColor};
            transition: all 0.3s ease;
        }}
        
        .stButton>button:hover {{
            background-color: {textColor};
            color: white;
            border: 1px solid {textColor};
        }}
        
        /* Progress Bar */
        .stProgress > div > div > div > div {{
            background-color: {primaryColor};
        }}
        </style>
    """, unsafe_allow_html=True)

# --- Japanese-themed UI components ---
def japanese_header(title, subtitle=""):
    """
    Renders a centered header with a Japanese-themed icon.

    Args:
        text (str): The header title text.
        icon (str, optional): The emoji or character icon to prepend. Defaults to "🏮".

    Returns:
        None
    """
    st.markdown(f"""
        <div style="border-left: 5px solid {primaryColor}; padding-left: 15px; margin-bottom: 25px;">
            <h1 style="margin: 0;">{title}</h1>
            <p style="color: #BFA4A4; font-style: italic; margin: 0;">{subtitle}</p>
        </div>
    """, unsafe_allow_html=True)

def render_flashcard(content=None, sub_content=None, meaning=None, onyomi=None, kunyomi=None, smart_composites=None):
    """
    Renders a flashcard-style UI component displaying Kanji character details.

    Args:
        kanji (str): The Kanji character.
        meaning (str): The English translation/definition.
        onyomi (str): On-yomi reading.
        kunyomi (str): Kun-yomi reading.
        smart_composites (str): HTML-formatted string containing composite examples.

    Returns:
        None
    """
    details_html = ""
    # Card back
    if meaning:
        reading_text_style = (
            "color:{primaryColor}; "
            "font-family: 'Hiragino Mincho ProN', 'MS Mincho', serif;"
            
            "font-weight: 600; "
            "margin-left: 10px;"
        )
        composites_text_style = (
            "color:{primaryColor}; "
            "color: {textColor}; " 
            "font-family: Georgia, serif;"
            "font-weight: 600; "
            "margin-left: 10px;"
        )

        details_html = f"""
        <div style="color: {textColor}; font-family: Georgia, serif; margin-top: 25px; border-top: 1px solid #f0f0f0; padding-top: 15px; width: 85%;">
            <h2 style="margin-bottom: 10px; color: {primaryColor};">{meaning}</h2>
            <div style="margin: 5px 0; font-size: 1.2em;">
                <strong>音読み (Onyomi):</strong> 
                <span style="{reading_text_style}">{onyomi}</span>
            </div>
            <div style="margin: 5px 0; font-size: 1.2em;">
                <strong>訓読み (Kunyomi):</strong> 
                <span style="{reading_text_style}">{kunyomi}</span>
            </div>
            <div style="margin: 5px 0; font-size: 1.2em;">
                <strong><br>Composite words:<br></strong> 
                <span style="{composites_text_style}">{smart_composites}</span>
            </div>
        </div>
        """
    # Card Front
    st.markdown(f"""
        <div style="
            background-color: white;
            padding: 40px 20px;
            border-radius: 4px;
            border: 1px solid #E8E1DF;
            box-shadow: 2px 2px 15px rgba(0,0,0,0.05);
            text-align: center;
            margin-bottom: 30px;
            min-height: 350px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
        ">
            <h1 style="font-size: 6em; color: {textColor}; margin: 0; line-height: 1.2;font-family: 'Hiragino Mincho ProN', 'MS Mincho', serif;">{content}</h1>
            {f'<p style="color: {textColor}; font-size: 1.5em; margin-top: 10px; font-style: italic;">{sub_content}</p>' if sub_content else ''}
            {details_html}
        </div>
    """, unsafe_allow_html=True)


