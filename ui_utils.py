import streamlit as st
import streamlit.components.v1 as components
import json
import pandas as pd
import os
import requests

def raining_success(emoji="🥷🏻", font_size=54, falling_speed=5, animation_length="1"):
    """
    Injects CSS and HTML to trigger an animated emoji rain effect.

    Args:
        emoji (str): The emoji character to display during the animation.
        font_size (int): Size of the emoji in pixels.
        falling_speed (int): Duration of the fall animation in seconds.
        animation_length (str): Number of iterations for the animation.
    """
    st.markdown(f"""
    <style>
    .emoji {{
        font-size: {font_size}px;
        position: fixed;
        top: -10%;
        z-index: 99999;
        animation-name: emojis-fall, emojis-shake;
        animation-duration: {falling_speed}s, 3s;
        animation-timing-function: linear, ease-in-out;
        animation-iteration-count: {animation_length}, {animation_length};
    }}
    @keyframes emojis-fall {{ 0% {{ top: -10%; }} 100% {{ top: 100%; }} }}
    @keyframes emojis-shake {{ 0% {{ transform: translateX(0px); }} 50% {{ transform: translateX(20px); }} 100% {{ transform: translateX(0px); }} }}
    /* Randomize horizontal positions for the rain */
    .emoji:nth-of-type(1) {{ left: 10%; animation-delay: 0s; }}
    .emoji:nth-of-type(2) {{ left: 25%; animation-delay: 1s; }}
    .emoji:nth-of-type(3) {{ left: 40%; animation-delay: 0.5s; }}
    .emoji:nth-of-type(4) {{ left: 55%; animation-delay: 2s; }}
    .emoji:nth-of-type(5) {{ left: 70%; animation-delay: 1.5s; }}
    .emoji:nth-of-type(6) {{ left: 85%; animation-delay: 3s; }}
    </style>
    """, unsafe_allow_html=True)
    emojis_html = "".join([f'<div class="emoji">{emoji}</div>' for _ in range(12)])
    st.markdown(f'<div class="emojis">{emojis_html}</div>', unsafe_allow_html=True)

def generate_genkouyoushi_print_html(kanji_char, numbered_svg_code, meaning="", onyomi="", kunyomi="", smart_composites=""):
    """
    Generates a printable HTML string designed for Genkouyoushi (Japanese practice sheets).

    Args:
        kanji_char (str): The Kanji character to be printed.
        numbered_svg_code (str): The raw SVG string for the stroke order guide.
        meaning (str, optional): English definition. Defaults to "".
        onyomi (str, optional): On-yomi reading. Defaults to "".
        kunyomi (str, optional): Kun-yomi reading. Defaults to "".
        smart_composites (str, optional): HTML-formatted string of examples. Defaults to "".

    Returns:
        str: A full HTML document string formatted for printing.
    """
    grid_html = ""
    for i in range(20):
        square_id = 'id="target-square"' if i == 0 else ""
        grid_html += f'<div class="square" {square_id}></div>'
    composites_block = ""
    if smart_composites:
        composites_block = f"""
        <div style="margin-top: 15px; padding-top: 10px; border-top: 1px dashed #e8e1df;">
            <strong style="color: #242164;">Composite words:</strong>
            <div style="color: #E63946; font-family: Georgia, serif; font-size: 1em; margin-top: 5px; line-height: 1.5;">
                {smart_composites}
            </div>
        </div>
        """
    return f"""
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <style>
            @media print {{
                @page {{ 
                    size: A4 landscape; 
                    margin: 0; 
                }}
                .no-print {{ display: none; }}
                body {{ 
                    margin: 0; 
                    padding: 12mm 15mm; 
                    background-color: white !important; 
                    -webkit-print-color-adjust: exact; 
                }}
                .grid {{
                    background-color: white !important;
                    border: 2px solid #333;
                }}
            }}
            body {{ 
                font-family: sans-serif; 
                display: flex; 
                flex-direction: column; 
                align-items: center; 
                background: white;
                padding-top: 20px;
            }}
            .grid {{
                display: grid;
                grid-template-columns: repeat(10, 25mm);
                grid-template-rows: repeat(2, 25mm);
                gap: 0;
                border: 2px solid #333;
                background: white;
            }}
            .square {{
                width: 25mm;
                height: 25mm;
                border: 0.5px solid #333;
                position: relative;
                display: flex;
                justify-content: center;
                align-items: center;
                box-sizing: border-box;
            }}
            .square::before, .square::after {{
                content: "";
                position: absolute;
                border: 0.5px dashed #bbb;
                z-index: 0;
            }}
            .square::before {{ width: 100%; height: 0; top: 50%; left: 0; }}
            .square::after {{ width: 0; height: 100%; top: 0; left: 50%; }}
            
            #target-square svg {{ 
                width: 85%; 
                height: 85%; 
                z-index: 1;
            }}
            svg text {{ font-size: 10px !important; fill: #E63946 !important; font-weight: bold; }}
            
            .controls {{ margin-bottom: 25px; text-align: center; }}
            button {{ padding: 10px 25px; font-size: 18px; cursor: pointer; background: #242164; color: white; border: none; border-radius: 5px; }}
        </style>
    </head>
    <body>
        <div class="controls no-print">
            <h1 id="page-title">Genkouyoushi Practice:</h1>
            <button onclick="window.print()">🖨️</button>
        </div>
        
        <div class="grid">
            {grid_html}
        </div>

        <div style="
            width: 250mm; 
            margin-top: 20px; 
            padding: 15px 20px;
            background: #ffffff;
            border-left: 5px solid #E63946;
            box-sizing: border-box;
            text-align: left;
        ">
            <h2 style="margin: 0 0 10px 0; color: #242164; font-size: 1.8em;">{meaning}</h2>
            <div style="font-size: 1.1em; margin: 4px 0; color: #242164;">
                <strong>音読み (On):</strong> 
                <span style="color: #E63946; font-family: Georgia, serif; font-weight: 600; margin-left: 10px;">{onyomi}</span>
            </div>
            <div style="font-size: 1.1em; margin: 4px 0; color: #242164;">
                <strong>訓読み (Kun):</strong> 
                <span style="color: #E63946; font-family: Georgia, serif; font-weight: 600; margin-left: 10px;">{kunyomi}</span>
            </div>
            {composites_block}
        </div>
    </body>
    </html>
    """

def get_numbered_svg(NUMBERED_SVG_DIR, url):
    """
    Downloads or retrieves a cached numbered stroke order SVG from a URL.

    Args:
        directory (str): Local path where SVGs are cached.
        url (str): The URL source of the SVG file.

    Returns:
        str: The content of the SVG file as a string, or None if download fails.
    """
    filename = url.split('/')[-1]
    local_path = os.path.join(NUMBERED_SVG_DIR, filename)
    
    if os.path.exists(local_path):
        with open(local_path, "r", encoding="utf-8") as f:
            svg_text = f.read()
    else:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                svg_text = response.text
                with open(local_path, "w", encoding="utf-8") as f:
                    f.write(svg_text)
            else:
                return None
        except Exception as e:
            st.error(f"Error downloading numbered SVG: {e}")
            return None

    if svg_text:
        svg_text = svg_text.replace("]>", "").replace("]> ", "")
    return svg_text

def show_print_button(NUMBERED_SVG_DIR, card_row, smart_composites=""):
    """
    Renders a Streamlit component button that triggers a browser print action 
    for the Kanji practice sheet.

    Args:
        number_svg_dir (str): Local directory for cached SVGs.
        card_row (dict): A dictionary containing 'kanji', 'stroke_order_url', 
            and metadata.
        smart_composites (str, optional): Pre-formatted string of composite examples.
    """
    svg_code = get_numbered_svg(NUMBERED_SVG_DIR, card_row['stroke_order_url'])
    if not svg_code:
        return
    print_template = generate_genkouyoushi_print_html(
        kanji_char=card_row['kanji'],
        numbered_svg_code="",
        meaning=card_row.get('meaning', ''),
        onyomi=card_row.get('onyomi', ''),
        kunyomi=card_row.get('kunyomi', ''),
        smart_composites=smart_composites
    )
    html_code = f"""
    <button id="print-btn" style="background-color: #f0f2f6; border: 1px solid #d1d5db; border-radius: 5px; padding: 8px 16px; cursor: pointer; color: #242164;">
        🖨️ Print Practice Sheet
    </button>
    <script>
        const btn = document.getElementById("print-btn");
        btn.onclick = function() {{
            const win = window.open("", "_blank");
            win.document.write(`{print_template}`);
            win.onload = function() {{
                const target = win.document.getElementById("target-square");
                if (target) target.innerHTML = `{svg_code}`;
            }};
            win.document.close();
        }};
    </script>
    """
    components.html(html_code, height=60)