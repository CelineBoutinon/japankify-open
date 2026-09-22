import streamlit as st
import pandas as pd
import io
import boto3

@st.cache_resource
def get_s3_client():
    """Initializes and returns a boto3 S3 client using Streamlit secrets."""
    return boto3.client(
        's3',
        aws_access_key_id=st.secrets["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=st.secrets["AWS_SECRET_ACCESS_KEY"],
        region_name=st.secrets["AWS_DEFAULT_REGION"]
    )

@st.cache_data
def load_parquet_from_s3(s3_key, default_columns=None):
    """Fetches a Parquet file directly from S3 into a pandas DataFrame using boto3."""
    try:
        s3 = get_s3_client()
        bucket = st.secrets["AWS_BUCKET_NAME"]
        response = s3.get_object(Bucket=bucket, Key=s3_key)
        return pd.read_parquet(io.BytesIO(response['Body'].read()))
    except Exception as e:
        st.error(f"Failed to load Parquet {s3_key} from S3: {e}")
        return pd.DataFrame(columns=default_columns) if default_columns else pd.DataFrame()

@st.cache_data
def load_csv_from_s3(s3_key):
    """Fetches a CSV file directly from S3 into a pandas DataFrame using boto3."""
    try:
        s3 = get_s3_client()
        bucket = st.secrets["AWS_BUCKET_NAME"]
        response = s3.get_object(Bucket=bucket, Key=s3_key)
        return pd.read_csv(io.BytesIO(response['Body'].read()))
    except Exception as e:
        st.error(f"Failed to load CSV {s3_key} from S3: {e}")
        return pd.DataFrame()

@st.cache_data
def get_s3_file_content(s3_key):
    """Fetches a text/SVG file directly from S3 using boto3."""
    try:
        s3 = get_s3_client()
        bucket = st.secrets["AWS_BUCKET_NAME"]
        response = s3.get_object(Bucket=bucket, Key=s3_key)
        return response['Body'].read().decode('utf-8')
    except Exception:
        return None