import os
import re
import io
import boto3
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import pandas as pd # Add AWSSDKPandas-Python312 as a Lambda layer

# Initialize core AWS infrastructure clients
s3_client = boto3.client('s3')
ses_client = boto3.client('ses')

def get_s3_image_bytes(bucket_name, key):
    """
    Downloads a pre-rendered visualization graphic from S3 
    straight into memory as a raw binary stream buffer.
    """
    try:
        s3_object = s3_client.get_object(Bucket=bucket_name, Key=key)
        return s3_object['Body'].read()
    except Exception as e:
        print(f"Warning: Failed to fetch image asset {key}. Error: {str(e)}")
        return None

def lambda_handler(event, context):
    """
    Stateful Lambda Worker invoked natively by AWS Step Functions.
    Processes S3 data lake snapshots and dispatches summaries via Amazon SES.
    """
    # 1. Log incoming event coordinates for debugging visibility
    print(f"DEBUG - Full Incoming Event Payload Context: {event}")
    
    # 2. Extract execution settings from the Lambda container environment
    bucket_name = os.environ.get('AWS_BUCKET_NAME')
    recipient_email = os.environ.get('RECIPIENT_EMAIL')
    sender_email = os.environ.get('SENDER_EMAIL', recipient_email)
    
    latest_parquet_key = event.get('parquet_key')
    event_timestamp = event.get('timestamp')
    
    if not latest_parquet_key or not event_timestamp:
        return {
            'statusCode': 400,
            'body': "Execution Error: Missing target parquet keys or event timestamp from Step Function."
        }
        
    try:
        # 3. Parse out the operational execution date string using Python regex
        # Target match: "weekly-stats/review_history_2026-05-20.parquet" -> "2026-05-20"
        date_match = re.search(r'_(\d{4}-\d{2}-\d{2})\.parquet$', latest_parquet_key)
        if date_match:
            date_str = date_match.group(1)
        else:
            date_str = event_timestamp.split('T')[0]
            
        # Reconstruct the expected chart keys using clean Python formatting expressions
        vocab_chart_key = f"weekly-stats/vocab_chart_{date_str}.png"
        kanji_chart_key = f"weekly-stats/kanji_chart_{date_str}.png"
        
        # 4. DEFENSIVE CHECK: Run a lightweight metadata check on S3 to ensure images are present
        try:
            s3_client.head_object(Bucket=bucket_name, Key=vocab_chart_key)
            s3_client.head_object(Bucket=bucket_name, Key=kanji_chart_key)
            print(f"Asset Validation Passed: Verified charts exist for execution date {date_str}")
        except Exception:
            raise RuntimeError(f"Target visualization charts are missing from S3 for date token: {date_str}")

        # 5. Read the Parquet binary stream from memory using standard pyarrow
        s3_object = s3_client.get_object(Bucket=bucket_name, Key=latest_parquet_key)
        df = pd.read_parquet(io.BytesIO(s3_object['Body'].read()), engine='pyarrow')
        
        # 6. Execute tracking analytics logic over the trailing 7 days
        df['date'] = pd.to_datetime(df['date'])
        max_date = df['date'].max()
        seven_days_ago = max_date - pd.Timedelta(days=7)
        last_7_days = df[df['date'] > seven_days_ago]
        
        # Calculate raw total volume subsets cleanly
        vocab_subset = last_7_days[last_7_days['type'] == 'Vocab']
        kanji_subset = last_7_days[last_7_days['type'] == 'Kanji']
        
        v_count = len(vocab_subset)
        k_count = len(kanji_subset)
        
        # Build JLPT Level Breakdowns dynamically using categorical distribution tallies
        jlpt_order = ['N5', 'N4', 'N3', 'N2', 'N1']
        
        v_counts = vocab_subset['level'].dropna().value_counts()
        v_details = ", ".join([f"{lvl}: {v_counts.get(lvl, 0)}" for lvl in jlpt_order if lvl in v_counts or v_counts.get(lvl, 0) > 0])
        vocab_display_str = f"{v_count} words ({v_details})" if v_count > 0 else "0 words"
        
        k_counts = kanji_subset['level'].dropna().value_counts()
        k_details = ", ".join([f"{lvl}: {k_counts.get(lvl, 0)}" for lvl in jlpt_order if lvl in k_counts or k_counts.get(lvl, 0) > 0])
        kanji_display_str = f"{k_count} characters ({k_details})" if k_count > 0 else "0 characters"
        
        # Hardened Grade Parsing (Handles string formats like "Grade 1", "Grade 3", etc.)
        valid_grades = kanji_subset['grade'].dropna().astype(str)
        valid_grades = valid_grades[(valid_grades != 'NA') & (valid_grades.str.strip() != '')]
        
        if not valid_grades.empty:
            def clean_grade_string(val):
                digits = re.findall(r'\d+', val)
                return int(digits[0]) if digits else None

            cleaned_series = valid_grades.map(clean_grade_string).dropna().astype(int)
            g_counts = cleaned_series.value_counts().sort_index()
            grade_display_str = ", ".join([f"Grade {g}: {c}" for g, c in g_counts.items()])
        else:
            grade_display_str = "None"
        
        # 7. Initialize Multi-part MIME Email Container
        msg = MIMEMultipart('related')
        msg['Subject'] = f"📊 Your Weekly Japankify Progress Report - {v_count + k_count} Items Reviewed"
        msg['From'] = sender_email
        msg['To'] = recipient_email
        
        # 8. Build HTML Layout Structure Template (With escaped CSS curly braces)
        html_content = f"""
        <html>
            <body style="font-family: sans-serif; color: #242164; background-color: #fcfcfc; padding: 20px;">
                <h2 style="color: #242164; border-bottom: 2px solid #242164; padding-bottom: 8px;">🪸 Cloud Knowledge Growth Summary</h2>
                <p>Here is your automated production metrics lookback tracking your study health over the past 7 days:</p>
                
                <div style="background-color: #f0f4f8; border-left: 4px solid #242164; padding: 15px; border-radius: 4px; margin-bottom: 25px;">
                    <ul style="list-style-type: none; padding-left: 0; margin: 0; line-height: 1.6;">
                        <li><strong>🈂️ Vocabulary:</strong> {vocab_display_str}</li>
                        <li><strong>🉐 Kanji:</strong> {kanji_display_str}</li>
                        <li><strong>🎓 School Grades Breakdown:</strong> {grade_display_str}</li>
                    </ul>
                </div>
                
                <h3 style="color: #242164; margin-top: 20px;">🈂️ Vocabulary Review Progress Metrics</h3>
                <div style="margin-bottom: 30px;">
                    <img src="cid:vocab_chart" style="width: 100%; max-width: 700px; height: auto; border-radius: 4px;"/>
                </div>
                
                <h3 style="color: #242164; margin-top: 20px;">🉐 Kanji Review Progress Metrics</h3>
                <div>
                    <img src="cid:kanji_chart" style="width: 100%; max-width: 700px; height: auto; border-radius: 4px;"/>
                </div>
                
                <p style="font-size: 11px; color: #777; margin-top: 40px; border-top: 1px solid #eee; padding-top: 10px;">
                    Sent automatically via AWS serverless pipeline orchestration (EventBridge + Step Functions + S3 + Lambda + SES).
                </p>
            </body>
        </html>
        """
        msg.attach(MIMEText(html_content, 'html'))
        
        # 9. Fetch Graphic Binaries from S3 and Attach as CIDs
        v_img_bytes = get_s3_image_bytes(bucket_name, vocab_chart_key)
        if v_img_bytes:
            v_mime = MIMEImage(v_img_bytes)
            v_mime.add_header('Content-ID', '<vocab_chart>')
            v_mime.add_header('Content-Disposition', 'inline', filename='vocab_chart.png')
            msg.attach(v_mime)
            
        k_img_bytes = get_s3_image_bytes(bucket_name, kanji_chart_key)
        if k_img_bytes:
            k_mime = MIMEImage(k_img_bytes)
            k_mime.add_header('Content-ID', '<kanji_chart>')
            k_mime.add_header('Content-Disposition', 'inline', filename='kanji_chart.png')
            msg.attach(k_mime)
            
        # 10. Ship Payload via AWS SES Raw Email Protocol interface
        response = ses_client.send_raw_email(
            Source=sender_email,
            Destinations=[recipient_email],
            RawMessage={'Data': msg.as_string()}
        )
        
        print(f"Email dispatched flawlessly via SES! MessageID: {response['MessageId']}")
        
        return {
            'statusCode': 200,
            'body': 'Notification dispatched successfully!'
        }
        
    except Exception as e:
        print(f"Pipeline Transmission Failure: {str(e)}")
        raise RuntimeError(f"Lambda Pipeline Execution Crash: {str(e)}")