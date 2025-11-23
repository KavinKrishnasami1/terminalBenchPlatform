"""Cloud storage module for S3/R2 integration"""
import os
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Storage configuration
USE_CLOUD_STORAGE = os.getenv('USE_CLOUD_STORAGE', 'false').lower() == 'true'
S3_ENDPOINT_URL = os.getenv('S3_ENDPOINT_URL')  # e.g., https://<account-id>.r2.cloudflarestorage.com
S3_ACCESS_KEY_ID = os.getenv('S3_ACCESS_KEY_ID')
S3_SECRET_ACCESS_KEY = os.getenv('S3_SECRET_ACCESS_KEY')
S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME', 'tbench-storage')
S3_REGION = os.getenv('S3_REGION', 'auto')  # 'auto' for R2, us-east-1 for AWS

def get_s3_client():
    """Get configured S3 client (works with R2 and AWS S3)"""
    if not USE_CLOUD_STORAGE:
        return None

    if not all([S3_ENDPOINT_URL, S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY]):
        logger.warning("Cloud storage enabled but credentials not configured")
        return None

    return boto3.client(
        's3',
        endpoint_url=S3_ENDPOINT_URL,
        aws_access_key_id=S3_ACCESS_KEY_ID,
        aws_secret_access_key=S3_SECRET_ACCESS_KEY,
        region_name=S3_REGION,
        config=Config(signature_version='s3v4')
    )

def upload_file_to_s3(local_path: str, s3_key: str) -> bool:
    """Upload a file to S3/R2"""
    if not USE_CLOUD_STORAGE:
        return False

    s3_client = get_s3_client()
    if not s3_client:
        return False

    try:
        s3_client.upload_file(local_path, S3_BUCKET_NAME, s3_key)
        logger.info(f"Uploaded {local_path} to s3://{S3_BUCKET_NAME}/{s3_key}")
        return True
    except ClientError as e:
        logger.error(f"Failed to upload {local_path} to S3: {e}")
        return False

def download_file_from_s3(s3_key: str, local_path: str) -> bool:
    """Download a file from S3/R2"""
    if not USE_CLOUD_STORAGE:
        return False

    s3_client = get_s3_client()
    if not s3_client:
        return False

    try:
        # Create parent directory if it doesn't exist
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)

        s3_client.download_file(S3_BUCKET_NAME, s3_key, local_path)
        logger.info(f"Downloaded s3://{S3_BUCKET_NAME}/{s3_key} to {local_path}")
        return True
    except ClientError as e:
        logger.error(f"Failed to download {s3_key} from S3: {e}")
        return False

def upload_directory_to_s3(local_dir: str, s3_prefix: str) -> bool:
    """Upload an entire directory to S3/R2"""
    if not USE_CLOUD_STORAGE:
        return False

    s3_client = get_s3_client()
    if not s3_client:
        return False

    try:
        local_dir_path = Path(local_dir)
        for file_path in local_dir_path.rglob('*'):
            if file_path.is_file():
                # Get relative path from local_dir
                relative_path = file_path.relative_to(local_dir_path)
                s3_key = f"{s3_prefix}/{relative_path}".replace('\\', '/')

                s3_client.upload_file(str(file_path), S3_BUCKET_NAME, s3_key)
                logger.debug(f"Uploaded {file_path} to s3://{S3_BUCKET_NAME}/{s3_key}")

        logger.info(f"Uploaded directory {local_dir} to s3://{S3_BUCKET_NAME}/{s3_prefix}")
        return True
    except ClientError as e:
        logger.error(f"Failed to upload directory {local_dir} to S3: {e}")
        return False

def download_directory_from_s3(s3_prefix: str, local_dir: str) -> bool:
    """Download an entire directory from S3/R2"""
    if not USE_CLOUD_STORAGE:
        return False

    s3_client = get_s3_client()
    if not s3_client:
        return False

    try:
        # List all objects with the prefix
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=S3_BUCKET_NAME, Prefix=s3_prefix)

        for page in pages:
            if 'Contents' not in page:
                continue

            for obj in page['Contents']:
                s3_key = obj['Key']
                # Remove prefix to get relative path
                relative_path = s3_key[len(s3_prefix):].lstrip('/')
                local_file_path = Path(local_dir) / relative_path

                # Create parent directory
                local_file_path.parent.mkdir(parents=True, exist_ok=True)

                # Download file
                s3_client.download_file(S3_BUCKET_NAME, s3_key, str(local_file_path))
                logger.debug(f"Downloaded s3://{S3_BUCKET_NAME}/{s3_key} to {local_file_path}")

        logger.info(f"Downloaded directory s3://{S3_BUCKET_NAME}/{s3_prefix} to {local_dir}")
        return True
    except ClientError as e:
        logger.error(f"Failed to download directory {s3_prefix} from S3: {e}")
        return False

def list_s3_objects(prefix: str) -> list:
    """List objects in S3/R2 with given prefix"""
    if not USE_CLOUD_STORAGE:
        return []

    s3_client = get_s3_client()
    if not s3_client:
        return []

    try:
        response = s3_client.list_objects_v2(Bucket=S3_BUCKET_NAME, Prefix=prefix)
        return [obj['Key'] for obj in response.get('Contents', [])]
    except ClientError as e:
        logger.error(f"Failed to list objects with prefix {prefix}: {e}")
        return []

def delete_s3_object(s3_key: str) -> bool:
    """Delete an object from S3/R2"""
    if not USE_CLOUD_STORAGE:
        return False

    s3_client = get_s3_client()
    if not s3_client:
        return False

    try:
        s3_client.delete_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
        logger.info(f"Deleted s3://{S3_BUCKET_NAME}/{s3_key}")
        return True
    except ClientError as e:
        logger.error(f"Failed to delete {s3_key} from S3: {e}")
        return False
