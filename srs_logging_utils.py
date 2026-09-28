import pandas as pd
import numpy as np
import datetime
from datetime import datetime, date, timedelta
import os
import io
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
import streamlit as st

LOG_FILE = "assets/review_history.parquet"
CSV_FILE = "assets/review_history.csv"
# These datasets are available from https://github.com/CelineBoutinon/japankify-open/assets

utils_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(utils_dir)
env_path = os.path.join(root_dir, '.env')

load_dotenv(dotenv_path=env_path)

def log_review(item_name, item_type, level, grade=None, jouyou_idx=None):
    """
    Records a single study review event to the local logs.

    Args:
        item_name (str): The name or character of the item studied (e.g., '生姜' or '生').
        item_type (str): The category of the item, must be either 'Vocab' or 'Kanji'.
        level (str): The JLPT level (e.g., 'N3').
        grade (str, optional): The educational grade for Kanji items. Defaults to None.
        jouyou_idx (str, optional): The Jouyou Kanji index. Defaults to None.

    Returns:
        None
    """
    new_entry = {
        'date': datetime.now(),
        'item': item_name,
        'type': item_type,
        'level': level,
        'grade': grade if grade != 'NA' else None,
        'jouyou_index': jouyou_idx if jouyou_idx != 'NA' else None
    }
    
    if os.path.exists(LOG_FILE):
        history_df = pd.read_parquet(LOG_FILE)
        history_df = pd.concat([history_df, pd.DataFrame([new_entry])], ignore_index=True)
    else:
        history_df = pd.DataFrame([new_entry])
    
    history_df.to_parquet(LOG_FILE)
    history_df.to_csv(CSV_FILE, header=True, index=False, encoding='utf-8-sig') # for ease of log inspection


def get_s3_client():
    """
    Initializes and returns a boto3 S3 client using environment credentials.

    Returns:
        boto3.client: An authenticated S3 client instance.

    Raises:
        ClientError: If AWS credentials are missing or invalid.
    """
    return boto3.client(
        's3',
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_REGION", "eu-west-1")
    )

# --- Helper functions for weekly stats email ---
def build_weekly_stats_key(base_filename, extension):
    """
    Constructs a unique S3 object key for a user's weekly statistics file.

    Args:
        user_id (str): The unique identifier for the user.

    Returns:
        str: The formatted S3 object key (e.g., 'weekly-stats/user_id_YYYY-MM-DD.parquet').
    """
    date_suffix = datetime.now().strftime("_%Y-%m-%d")
    return f"weekly-stats/{base_filename}{date_suffix}.{extension}"

def upload_stats_file_to_s3(local_file_path, base_filename, extension):
    """
    Uploads a local file to a specified AWS S3 bucket.

    Args:
        local_path (str): The local file system path to the file.
        s3_key (str): The destination key in the S3 bucket.
        bucket_name (str): The name of the target S3 bucket.

    Returns:
        bool: True if the upload was successful, False otherwise.
    """
    bucket_name = os.getenv("AWS_BUCKET_NAME")
    if not bucket_name:
        return False, "S3 Configuration Error: 'AWS_BUCKET_NAME' not detected. Check your root .env file keys."
    s3_client = get_s3_client()
    if not os.path.exists(local_file_path):
        return False, f"Local file not found at {local_file_path}"
    s3_object_key = build_weekly_stats_key(base_filename, extension)
    try:
        s3_client.upload_file(local_file_path, bucket_name, s3_object_key)
        return True, f"Successfully uploaded {local_file_path} to s3://{bucket_name}/{s3_object_key}"
    except ClientError as e:
        return False, f"AWS S3 Client Error: {e.response['Error']['Message']}"

def upload_matplotlib_fig_to_s3(fig, base_filename):
    """
    Uploads a Matplotlib figure directly to S3 as an image buffer.

    Args:
        fig (matplotlib.figure.Figure): The Matplotlib figure object.
        bucket_name (str): Name of the S3 bucket.
        object_name (str): Destination path/name in S3.

    Returns:
        bool: True if upload successful, else False.
    """
    bucket_name = os.getenv("AWS_BUCKET_NAME")
    if not bucket_name:
        return False, "S3 Configuration Error: 'AWS_BUCKET_NAME' not detected. Check your root .env file keys."
    s3_client = get_s3_client()
    s3_object_key = build_weekly_stats_key(base_filename, "png")
    try:
        img_buf = io.BytesIO()
        fig.savefig(img_buf, format='png', dpi=200, bbox_inches='tight', facecolor=fig.get_facecolor())
        img_buf.seek(0) 
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_object_key,
            Body=img_buf,
            ContentType='image/png'
        )
        return True, f"Successfully uploaded figure to s3://{bucket_name}/{s3_object_key}"
    except ClientError as e:
        return False, f"AWS S3 Upload Error: {e.response['Error']['Message']}"


# --- Helper functions for vocab and kanji files logging (inc. SRS data) ---
def build_app_data_key(base_filename, extension):
    """
    Generates a standardized S3 object key for application data backups.

    Args:
        app_name (str): The name of the application.
        file_type (str): The type of file (e.g., 'parquet', 'csv').

    Returns:
        str: A formatted S3 object key string.
    """
    date_suffix = datetime.now().strftime("_%Y-%m-%d")
    return f"app-data/{base_filename}{date_suffix}.{extension}"

def upload_app_file_to_s3(local_file_path, base_filename, extension):
    """
    Uploads a local file to an AWS S3 bucket.

    Args:
        file_name (str): Path to the local file.
        bucket_name (str): Name of the target S3 bucket.
        object_name (str, optional): S3 object name. Defaults to file_name.

    Returns:
        bool: True if file was uploaded, else False.
    """
    bucket_name = os.getenv("AWS_BUCKET_NAME")
    if not bucket_name:
        return False, "S3 Configuration Error: 'AWS_BUCKET_NAME' not detected. Check your root .env file keys."
    s3_client = get_s3_client()
    if not os.path.exists(local_file_path):
        return False, f"Local file not found at {local_file_path}"
    s3_object_key = build_app_data_key(base_filename, extension)
    try:
        s3_client.upload_file(local_file_path, bucket_name, s3_object_key)
        return True, f"Successfully uploaded {local_file_path} to s3://{bucket_name}/{s3_object_key}"
    except ClientError as e:
        return False, f"AWS S3 Client Error: {e.response['Error']['Message']}"


# --- Helper functions for dictionary, TV-time and kotowaza pages ---
def sanitize_df(df, column_types):
    """
    Cleans a DataFrame by enforcing data types and removing null artifacts.

    Args:
        df (pd.DataFrame): The raw DataFrame to sanitize.
        column_types (dict): A dictionary where keys are column names and values 
            are strings representing the target type ('str', 'float', 'int').

    Returns:
        pd.DataFrame: A cleaned version of the input DataFrame.
    """
    clean_df = df.copy()
    for col, dtype in column_types.items():
        if col in clean_df.columns:
            # 1. Fill NAs before converting types
            if dtype == 'str':
                clean_df[col] = clean_df[col].fillna('')
                clean_df[col] = clean_df[col].astype(str).replace({'nan': '', 'None': '', 'NaN': ''})
            elif dtype in ['int', 'float']:
                # 2. Force conversion to numeric, turning errors (like 'bad_data') into NaN, then fill with 0
                clean_df[col] = pd.to_numeric(clean_df[col], errors='coerce').fillna(0)
                clean_df[col] = clean_df[col].astype(dtype)
    return clean_df

def save_and_refresh(df, file_path, schema, index_col=None):
    """
    Saves a DataFrame to Parquet and CSV formats and clears Streamlit's data cache.

    Args:
        df (pd.DataFrame): The DataFrame containing the new data.
        file_path (str): The filesystem path where the Parquet file will be saved.
        schema (dict): A dictionary mapping column names to target types for sanitization.
        index_col (str, optional): The column name to use for duplicate removal. 
            Defaults to None.

    Returns:
        None
    """
    clean_df = sanitize_df(df, schema)
    if index_col and index_col in clean_df.columns:
        clean_df = clean_df.drop_duplicates(subset=[index_col], keep='first')
    clean_df.to_parquet(file_path)
    os.makedirs("csvs", exist_ok=True)
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    clean_df.to_csv(os.path.join("csvs", f"{base_name}.csv"), index=False, encoding='utf-8-sig')
    st.cache_data.clear()

def calculate_srs_metrics(quality, interval, easiness, repetition):
    """
    Calculates updated SuperMemo-2 (SM-2) algorithm metrics for a flashcard.

    Args:
        quality (int): User's performance rating (0-6).
        interval (float): Current repetition interval in days.
        easiness (float): Current ease factor of the card.
        repetition (int): Number of successful repetitions.

    Returns:
        tuple: (new_interval, new_repetitions, new_ease_factor)
    """
    # Math for Mastered
    if quality == 6:
        return 21, repetition + 1, 2.5
    # Math for Correct (Good/Easy/Hard)
    if quality >= 3:
        if repetition == 0: ivl = 1
        elif repetition == 1: ivl = 6
        else: ivl = max(1, round(interval * easiness))
        reps = repetition + 1
    # Math for Again
    else:
        reps, ivl = 0, 1
    # Easiness factor adjustment
    new_ef = max(1.3, easiness + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))
    return ivl, reps, new_ef

def handle_card_review(label, card_type):
    """
    Processes a user's SRS review action and updates performance metrics.

    Args:
        label (str): The button label clicked by the user (e.g., 'Again', 'Good').
        card_type (str): The type of card reviewed, 'vocab' or 'kanji'.

    Returns:
        None

    Raises:
        KeyError: If the provided label or card_type is not recognized.
    """
    mapping = {"Again": 0, "Hard": 3, "Good": 4, "Easy": 5, "Mastered": 6}
    q = mapping[label]
    # Define configuration for each type
    config = {
        'vocab': {'df': 'vocab_df', 'pos': 'vocab_pos', 'indices': 'vocab_session_indices', 'show': 'vocab_show_answer', 'log_func': lambda c: log_review(c['word'], 'Vocab', c['JLPT_level'], 'NA', 'NA')},
        'kanji': {'df': 'df_kanji', 'pos': 'kanji_pos', 'indices': 'kanji_session_indices', 'show': 'kanji_show_answer', 'log_func': lambda c: log_review(c['kanji'], 'Kanji', c['JLPT_level'], c['kyouiku_grade'], c['jouyou_index'])}
    }
    cfg = config[card_type]
    # Extract Card
    df = st.session_state[cfg['df']]
    idx = st.session_state[cfg['indices']][st.session_state[cfg['pos']]]
    card = df.loc[idx]
    # Log
    cfg['log_func'](card)
    # Math (This remains untouched!)
    new_ivl, new_reps, new_ef = calculate_srs_metrics(q, float(card['easiness']), int(card['interval']), int(card['repetition']))
    # Generic Update
    st.session_state[cfg['df']].at[idx, 'interval'] = new_ivl
    st.session_state[cfg['df']].at[idx, 'repetition'] = new_reps
    st.session_state[cfg['df']].at[idx, 'easiness'] = new_ef
    st.session_state[cfg['df']].at[idx, 'next_review'] = (date.today() + timedelta(days=new_ivl)).strftime('%Y-%m-%d')
    # Generic UI reset
    st.session_state[cfg['pos']] += 1
    st.session_state[cfg['show']] = False