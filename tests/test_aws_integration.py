import pytest
from unittest.mock import patch, MagicMock
from srs_logging_utils import (
    upload_app_file_to_s3,
    upload_stats_file_to_s3,
    upload_matplotlib_fig_to_s3
)
from botocore.exceptions import ClientError

def test_upload_app_file_to_s3_success():
    """Verify that uploading an application backup file to S3 succeeds."""
    with patch("srs_logging_utils.boto3.client") as mock_s3_client:
        mock_instance = mock_s3_client.return_value
        mock_instance.upload_file.return_value = None 
        
        with patch("os.path.exists", return_value=True), \
             patch("os.getenv", return_value="my-test-bucket"):
             
            success, message = upload_app_file_to_s3("fake_path.parquet", "test_file", "parquet")
            
            assert success is True
            assert "Successfully uploaded" in message
            mock_instance.upload_file.assert_called_once()

def test_upload_app_file_to_s3_failure():
    """Verify that an S3 ClientError during app file upload returns False."""
    with patch("srs_logging_utils.boto3.client") as mock_s3_client:
        mock_instance = mock_s3_client.return_value
        mock_instance.upload_file.side_effect = ClientError(
            {"Error": {"Code": "403", "Message": "Forbidden"}}, "PutObject"
        )
        
        with patch("os.path.exists", return_value=True), \
             patch("os.getenv", return_value="my-test-bucket"):
             
            success, message = upload_app_file_to_s3("fake_path.parquet", "test_file", "parquet")
            
            assert success is False
            assert "AWS S3 Client Error" in message

def test_upload_stats_file_to_s3_success():
    """Verify that uploading weekly stats files to S3 succeeds."""
    with patch("srs_logging_utils.boto3.client") as mock_s3_client:
        mock_instance = mock_s3_client.return_value
        mock_instance.upload_file.return_value = None
        
        with patch("os.path.exists", return_value=True), \
             patch("os.getenv", return_value="my-test-bucket"):
             
            success, message = upload_stats_file_to_s3("fake_stats.parquet", "weekly_report", "parquet")
            
            assert success is True
            assert "Successfully uploaded" in message
            mock_instance.upload_file.assert_called_once()

def test_upload_stats_file_to_s3_failure():
    """Verify that an S3 ClientError during stats file upload returns False."""
    with patch("srs_logging_utils.boto3.client") as mock_s3_client:
        mock_instance = mock_s3_client.return_value
        mock_instance.upload_file.side_effect = ClientError(
            {"Error": {"Code": "500", "Message": "InternalError"}}, "PutObject"
        )
        
        with patch("os.path.exists", return_value=True), \
             patch("os.getenv", return_value="my-test-bucket"):
             
            success, message = upload_stats_file_to_s3("fake_stats.parquet", "weekly_report", "parquet")
            
            assert success is False
            assert "AWS S3 Client Error" in message

def test_upload_matplotlib_fig_to_s3_success():
    """Verify that uploading a Matplotlib figure buffer to S3 succeeds."""
    with patch("srs_logging_utils.boto3.client") as mock_s3_client:
        mock_instance = mock_s3_client.return_value
        mock_instance.put_object.return_value = {}
        
        mock_fig = MagicMock()
        mock_fig.get_facecolor.return_value = "#ffffff"
        
        with patch("os.getenv", return_value="my-test-bucket"):
            success, message = upload_matplotlib_fig_to_s3(mock_fig, "vocab_chart")
            
            assert success is True
            assert "Successfully uploaded figure" in message
            mock_instance.put_object.assert_called_once()

def test_upload_matplotlib_fig_to_s3_failure():
    """Verify that an S3 ClientError during figure upload returns False."""
    with patch("srs_logging_utils.boto3.client") as mock_s3_client:
        mock_instance = mock_s3_client.return_value
        mock_instance.put_object.side_effect = ClientError(
            {"Error": {"Code": "403", "Message": "Forbidden"}}, "PutObject"
        )
        
        mock_fig = MagicMock()
        mock_fig.get_facecolor.return_value = "#ffffff"
        
        with patch("os.getenv", return_value="my-test-bucket"):
            success, message = upload_matplotlib_fig_to_s3(mock_fig, "vocab_chart")
            
            assert success is False
            assert "AWS S3 Upload Error" in message