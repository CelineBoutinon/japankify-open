import boto3
from datetime import datetime, timezone
import os

# Environment variables for S3 prefixes and SES
bucket_name = os.environ.get('AWS_BUCKET_NAME')
raw_study_prefix = os.environ.get('RAW_STUDY_PREFIX', 'app-data/')   # S3 raw flashcard logs from study sessions
weekly_stats_prefix = os.environ.get('WEEKLY_STATS_PREFIX', 'weekly-stats/') # S3 synced chart artifacts
recipient_email = os.environ.get('RECIPIENT_EMAIL')
sender_email = os.environ.get('SENDER_EMAIL', recipient_email)

def get_latest_modified_time(s3_client, bucket, prefix):
    """Helper function to fetch the LastModified timestamp of the latest object in an S3 prefix."""
    response = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
    if 'Contents' not in response:
        return None
    latest_file = max(response['Contents'], key=lambda x: x['LastModified'])
    return latest_file['LastModified']

def lambda_handler(event, context):
    s3_client = boto3.client('s3')
    ses_client = boto3.client('ses')
    
    try:
        now = datetime.now(timezone.utc)
        
        # 1. Check when the user last studied (raw flashcard data timestamp)
        latest_study_time = get_latest_modified_time(s3_client, bucket_name, raw_study_prefix)
        
        if not latest_study_time:
            print(f"No study records found in prefix '{raw_study_prefix}'.")
            return {"status": "NO_STUDY_DATA_FOUND"}
            
        days_since_study = (now - latest_study_time).days
        print(f"Latest raw study session recorded: {latest_study_time} ({days_since_study} days ago)")
        
        # 2. If no study activity in the last 3 days, step back (Lambda 1 handles total inactivity alerts)
        if days_since_study > 3:
            print("No study activity detected in the last 3 days. Sync alert not required.")
            return {"status": "NO_RECENT_STUDY_IN_3_DAYS"}
            
        # 3. User HAS studied in the last 3 days! Now check when they last clicked "Sync Progress"
        latest_sync_time = get_latest_modified_time(s3_client, bucket_name, weekly_stats_prefix)
        
        needs_sync_alert = False
        
        if not latest_sync_time:
            # User studied recently, but has NEVER synced weekly stats
            needs_sync_alert = True
            sync_date_str = "Never"
        else:
            sync_date_str = latest_sync_time.strftime('%Y-%m-%d')
            # Trigger alert if the report was generated BEFORE the last study session, OR if sync is older than 3 days
            if latest_sync_time < latest_study_time or (now - latest_sync_time).days >= 3:
                needs_sync_alert = True

        # 4. Send SES email if progress is unsynced
        if needs_sync_alert:
            print("Recent study activity found, but weekly sync report is outdated. Sending alert via SES...")
            
            email_body = f"""
            <html>
            <body style="font-family: sans-serif; color: #242164; line-height: 1.6;">
                <p>Dear Learner,</p>
                <p>We noticed you've been studying on <strong>Japankify</strong> recently (last flashcard activity: <strong><code>{latest_study_time.strftime('%Y-%m-%d')}</code></strong>)!</p>
                <p>However, your progress report and charts were last synced on <strong><code>{sync_date_str}</code></strong>.</p>
                <p>Don't forget generate your custom stats by clicking <strong>"🚀 Sync progress"</strong> after each session to keep monitoring your weekly progress!</p>
                <p>🥷🏿 <em>頑張ってください !</em></p>
            </body>
            </html>
            """
            
            ses_client.send_email(
                Source=sender_email,
                Destination={'ToAddresses': [recipient_email]},
                Message={
                    'Subject': {'Data': "🚨 Japankify Alert: Unsynced Study Sessions Detected!"},
                    'Body': {'Html': {'Data': email_body}}
                }
            )
            return {
                "status": "ALERT_SENT",
                "latest_study_time": str(latest_study_time),
                "latest_sync_time": str(latest_sync_time) if latest_sync_time else "Never"
            }

        return {
            "status": "SYSTEM_HEALTHY",
            "message": "User studied recently and progress reports are fully synced."
        }
        
    except Exception as e:
        print(f"Error evaluating S3 sync state: {e}")
        raise e