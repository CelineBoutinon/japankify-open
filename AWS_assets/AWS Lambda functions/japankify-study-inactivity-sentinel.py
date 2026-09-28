import boto3
from datetime import datetime, timezone
import os

# # Environment variables for S3 prefixes and SES
bucket_name = os.environ.get('AWS_BUCKET_NAME')
folder_prefix = "app-data/"
recipient_email = os.environ.get('RECIPIENT_EMAIL')
sender_email = os.environ.get('SENDER_EMAIL', recipient_email)

def lambda_handler(event, context):
    s3_client = boto3.client('s3')
    ses_client = boto3.client('ses')
    
    try:
        # 1. List objects in the folder to find the most recent one
        response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=folder_prefix)
        
        if 'Contents' not in response:
            print("No files found in bucket folder.")
            return {"status": "NO_FILES_FOUND"}
            
        # 2. Sort files by LastModified and take the latest one
        files = response['Contents']
        latest_file = max(files, key=lambda x: x['LastModified'])
        
        last_modified = latest_file['LastModified']
        file_name = latest_file['Key']
        
        # 3. Calculate time elapsed
        now = datetime.now(timezone.utc)
        days_inactive = (now - last_modified).days
        
        print(f"Latest file: {file_name}. Modified: {last_modified}. Days: {days_inactive}")
        
        # 4. Logic for Alert
        if days_inactive >= 3:
            print(f"Alert triggered! Sending inactivity reminder via SES...")
            
            email_body = f"""
            <html>
            <body style="font-family: sans-serif; color: #242164; line-height: 1.6;">
                <p>Dear Learner,</p>
                <p>Your last study session was recorded on <strong><code>{last_modified.strftime('%Y-%m-%d')}</code></strong>.</p>
                <p>Don't let your JLPT N3 study goals slip away! Regular practice is the key to long-term memory.</p>
                <p>🥷🏿 <em>頑張ってください !</em></p>
            </body>
            </html>
            """
            
            ses_client.send_email(
                Source=sender_email,
                Destination={'ToAddresses': [recipient_email]},
                Message={
                    'Subject': {'Data': f"🏮 Japankify Study Reminder: you have not reviewed any flashcards over the past {days_inactive} days."},
                    'Body': {'Html': {'Data': email_body}}
                }
            )
            return {"status": "ALERT_SENT", "latest_file": file_name, "days_inactive": days_inactive}
            
        return {"status": "SYSTEM_HEALTHY", "latest_file": file_name, "days_inactive": days_inactive}
        
    except Exception as e:
        print(f"Error evaluating S3 dynamic state: {e}")
        raise e