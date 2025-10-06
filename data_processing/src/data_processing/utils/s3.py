"""S3/MinIO storage utilities for cloud and local object storage.

Supports both AWS S3 (production) and MinIO (local development) with automatic detection.
"""
import os
import logging
from pathlib import Path
from typing import Optional, Union
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Check if S3 libraries are available
try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    S3_AVAILABLE = True
except ImportError:
    S3_AVAILABLE = False
    logger.warning("boto3 not installed. S3/MinIO support disabled.")


class S3Storage:
    """S3/MinIO storage handler with automatic endpoint detection.

    Supports:
    - AWS S3 (production): s3://bucket/path/file.parquet
    - MinIO (local): s3://bucket/path/file.parquet with custom endpoint

    Environment Variables:
    - AWS_ACCESS_KEY_ID: Access key
    - AWS_SECRET_ACCESS_KEY: Secret key
    - AWS_ENDPOINT_URL: MinIO endpoint (optional, for local development)
    - AWS_REGION: AWS region (default: us-east-1)
    """

    def __init__(self):
        if not S3_AVAILABLE:
            raise ImportError("boto3 required for S3/MinIO support. Install: pip install boto3")

        # Get configuration from environment
        self.endpoint_url = os.environ.get('AWS_ENDPOINT_URL')
        self.region = os.environ.get('AWS_REGION', 'us-east-1')

        # Determine if we're using MinIO (local) or S3 (production)
        self.is_minio = self.endpoint_url is not None

        # Create S3 client
        self.client = boto3.client(
            's3',
            endpoint_url=self.endpoint_url,
            region_name=self.region,
            aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
        )

        # For MinIO, we need to configure path-style access
        if self.is_minio:
            self.client._client_config.s3 = {'addressing_style': 'path'}
            logger.info(f"Using MinIO endpoint: {self.endpoint_url}")
        else:
            logger.info("Using AWS S3")

    @staticmethod
    def parse_s3_path(s3_path: str) -> tuple[str, str]:
        """Parse S3 path into bucket and key.

        Args:
            s3_path: S3 URI like s3://bucket/path/to/file.parquet

        Returns:
            Tuple of (bucket, key)

        Example:
            >>> parse_s3_path('s3://my-bucket/data/file.parquet')
            ('my-bucket', 'data/file.parquet')
        """
        parsed = urlparse(s3_path)
        if parsed.scheme != 's3':
            raise ValueError(f"Invalid S3 path: {s3_path}. Must start with s3://")

        bucket = parsed.netloc
        key = parsed.path.lstrip('/')

        return bucket, key

    @staticmethod
    def is_s3_path(path: Union[str, Path]) -> bool:
        """Check if path is an S3 URI.

        Args:
            path: File path or S3 URI

        Returns:
            True if path starts with s3://
        """
        return str(path).startswith('s3://')

    def upload_file(self, local_path: Union[str, Path], s3_path: str) -> None:
        """Upload file to S3/MinIO.

        Args:
            local_path: Local file path
            s3_path: S3 destination (s3://bucket/path/file.parquet)
        """
        bucket, key = self.parse_s3_path(s3_path)

        try:
            self.client.upload_file(str(local_path), bucket, key)
            logger.info(f"Uploaded {local_path} to {s3_path}")
        except (ClientError, NoCredentialsError) as e:
            logger.error(f"Failed to upload to S3: {e}")
            raise

    def download_file(self, s3_path: str, local_path: Union[str, Path]) -> None:
        """Download file from S3/MinIO.

        Args:
            s3_path: S3 source (s3://bucket/path/file.parquet)
            local_path: Local destination path
        """
        bucket, key = self.parse_s3_path(s3_path)

        # Create parent directories
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)

        try:
            self.client.download_file(bucket, key, str(local_path))
            logger.info(f"Downloaded {s3_path} to {local_path}")
        except ClientError as e:
            logger.error(f"Failed to download from S3: {e}")
            raise

    def file_exists(self, s3_path: str) -> bool:
        """Check if file exists in S3/MinIO.

        Args:
            s3_path: S3 URI

        Returns:
            True if file exists
        """
        bucket, key = self.parse_s3_path(s3_path)

        try:
            self.client.head_object(Bucket=bucket, Key=key)
            return True
        except ClientError:
            return False

    def get_file_size(self, s3_path: str) -> int:
        """Get file size in bytes.

        Args:
            s3_path: S3 URI

        Returns:
            File size in bytes
        """
        bucket, key = self.parse_s3_path(s3_path)

        try:
            response = self.client.head_object(Bucket=bucket, Key=key)
            return response['ContentLength']
        except ClientError as e:
            logger.error(f"Failed to get file size: {e}")
            raise

    def list_files(self, s3_path: str, prefix: str = '') -> list[str]:
        """List files in S3/MinIO bucket.

        Args:
            s3_path: S3 bucket URI (s3://bucket/)
            prefix: Filter by prefix (e.g., 'data/')

        Returns:
            List of S3 URIs
        """
        bucket, _ = self.parse_s3_path(s3_path)

        try:
            response = self.client.list_objects_v2(Bucket=bucket, Prefix=prefix)

            if 'Contents' not in response:
                return []

            return [f"s3://{bucket}/{obj['Key']}" for obj in response['Contents']]
        except ClientError as e:
            logger.error(f"Failed to list files: {e}")
            raise

    def delete_file(self, s3_path: str) -> None:
        """Delete file from S3/MinIO.

        Args:
            s3_path: S3 URI
        """
        bucket, key = self.parse_s3_path(s3_path)

        try:
            self.client.delete_object(Bucket=bucket, Key=key)
            logger.info(f"Deleted {s3_path}")
        except ClientError as e:
            logger.error(f"Failed to delete file: {e}")
            raise

    def create_bucket(self, bucket_name: str) -> None:
        """Create S3/MinIO bucket.

        Args:
            bucket_name: Bucket name
        """
        try:
            if self.is_minio:
                # MinIO uses path-style
                self.client.create_bucket(Bucket=bucket_name)
            else:
                # AWS S3 requires location constraint for regions other than us-east-1
                if self.region == 'us-east-1':
                    self.client.create_bucket(Bucket=bucket_name)
                else:
                    self.client.create_bucket(
                        Bucket=bucket_name,
                        CreateBucketConfiguration={'LocationConstraint': self.region}
                    )
            logger.info(f"Created bucket: {bucket_name}")
        except ClientError as e:
            if e.response['Error']['Code'] == 'BucketAlreadyOwnedByYou':
                logger.info(f"Bucket {bucket_name} already exists")
            else:
                logger.error(f"Failed to create bucket: {e}")
                raise

    def get_s3fs_storage_options(self) -> dict:
        """Get storage options for s3fs/polars/pyarrow.

        Returns:
            Dict of storage options for S3 access
        """
        options = {
            'key': os.environ.get('AWS_ACCESS_KEY_ID'),
            'secret': os.environ.get('AWS_SECRET_ACCESS_KEY'),
        }

        if self.endpoint_url:
            options['endpoint_url'] = self.endpoint_url
            options['client_kwargs'] = {'region_name': self.region}

        return options


def get_s3_storage() -> Optional[S3Storage]:
    """Get S3Storage instance if configured.

    Returns:
        S3Storage instance or None if not configured
    """
    if not S3_AVAILABLE:
        return None

    # Check if credentials are configured
    if not os.environ.get('AWS_ACCESS_KEY_ID'):
        logger.debug("S3 not configured (no AWS_ACCESS_KEY_ID)")
        return None

    try:
        return S3Storage()
    except Exception as e:
        logger.warning(f"Failed to initialize S3 storage: {e}")
        return None


def resolve_path(path: Union[str, Path]) -> tuple[str, Optional[dict]]:
    """Resolve path and return storage options if S3.

    Args:
        path: Local path or S3 URI

    Returns:
        Tuple of (resolved_path, storage_options)
        - For local files: (path, None)
        - For S3 files: (s3_path, storage_options_dict)
    """
    path_str = str(path)

    if S3Storage.is_s3_path(path_str):
        s3_storage = get_s3_storage()
        if s3_storage:
            return path_str, s3_storage.get_s3fs_storage_options()
        else:
            raise RuntimeError("S3 path provided but S3 not configured")

    return path_str, None
