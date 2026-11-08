"""
S3 Configuration Module

This module provides S3 client initialization supporting both IAM role and
explicit credentials authentication.
"""

import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError
from functools import lru_cache
from typing import Optional
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class S3Config:
    """S3 Configuration class that handles client initialization and credential management."""
    
    def __init__(self):
        self.access_key = settings.AWS_S3_ACCESS_KEY
        self.secret_key = settings.AWS_S3_SECRET_KEY
        self.region = settings.AWS_S3_REGION
        self.bucket_name = settings.AWS_S3_BUCKET_NAME
        self.presigned_url_duration_minutes = settings.AWS_S3_PRESIGNED_URL_DURATION_MINUTES
        self.use_iam_role = settings.AWS_S3_USE_IAM_ROLE

    def get_credentials_config(self) -> dict:
        """
        Get AWS credentials configuration based on settings.
        If use_iam_role is True or access keys are not provided, 
        use default credentials provider which automatically uses IAM role 
        credentials from EC2 instance metadata.
        
        Returns:
            dict: Configuration for boto3 client
        """
        config = {"region_name": self.region}
        
        if self.use_iam_role or not self.access_key or not self.secret_key:
            logger.info("Using IAM role credentials (EC2 instance profile, ECS task role, etc.)")
            # Don't specify credentials - boto3 will use default credential chain
            # (IAM role, environment variables, credentials file, etc.)
        else:
            logger.info("Using explicit access key credentials")
            config.update({
                "aws_access_key_id": self.access_key,
                "aws_secret_access_key": self.secret_key
            })
        
        return config

    @lru_cache()
    def get_s3_client(self):
        """
        Create and return S3 client with appropriate credentials.
        
        Returns:
            boto3.client: Configured S3 client
            
        Raises:
            NoCredentialsError: When credentials are not available
            PartialCredentialsError: When credentials are incomplete
        """
        try:
            credentials_config = self.get_credentials_config()
            client = boto3.client('s3', **credentials_config)
            
            # Test the connection by listing buckets (if permissions allow)
            # This validates the credentials
            try:
                client.head_bucket(Bucket=self.bucket_name)
                logger.info(f"Successfully connected to S3 bucket: {self.bucket_name}")
            except Exception as e:
                logger.warning(f"Could not verify bucket access: {e}")
            
            return client
            
        except (NoCredentialsError, PartialCredentialsError) as e:
            logger.error(f"AWS credentials error: {e}")
            raise
        except Exception as e:
            logger.error(f"Error creating S3 client: {e}")
            raise

    def get_s3_resource(self):
        """
        Create and return S3 resource with appropriate credentials.
        
        Returns:
            boto3.resource: Configured S3 resource
        """
        try:
            credentials_config = self.get_credentials_config()
            return boto3.resource('s3', **credentials_config)
        except Exception as e:
            logger.error(f"Error creating S3 resource: {e}")
            raise

    def generate_presigned_url(
        self, 
        key: str, 
        expiration: Optional[int] = None, 
        method: str = 'get_object'
    ) -> str:
        """
        Generate a presigned URL for S3 object operations.
        
        Args:
            key (str): S3 object key
            expiration (int, optional): URL expiration time in seconds. 
                                      Defaults to configured duration.
            method (str): S3 operation method (get_object, put_object, etc.)
            
        Returns:
            str: Presigned URL
        """
        if expiration is None:
            expiration = self.presigned_url_duration_minutes * 60
            
        try:
            s3_client = self.get_s3_client()
            url = s3_client.generate_presigned_url(
                method,
                Params={'Bucket': self.bucket_name, 'Key': key},
                ExpiresIn=expiration
            )
            logger.info(f"Generated presigned URL for key: {key}")
            return url
        except Exception as e:
            logger.error(f"Error generating presigned URL for key {key}: {e}")
            raise

    def upload_file(self, file_path: str, key: str) -> bool:
        """
        Upload a file to S3.
        
        Args:
            file_path (str): Local file path
            key (str): S3 object key
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            s3_client = self.get_s3_client()
            s3_client.upload_file(file_path, self.bucket_name, key)
            logger.info(f"Successfully uploaded {file_path} to {key}")
            return True
        except Exception as e:
            logger.error(f"Error uploading file {file_path} to {key}: {e}")
            return False

    def download_file(self, key: str, file_path: str) -> bool:
        """
        Download a file from S3.
        
        Args:
            key (str): S3 object key
            file_path (str): Local file path to save
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            s3_client = self.get_s3_client()
            s3_client.download_file(self.bucket_name, key, file_path)
            logger.info(f"Successfully downloaded {key} to {file_path}")
            return True
        except Exception as e:
            logger.error(f"Error downloading file {key} to {file_path}: {e}")
            return False

    def delete_file(self, key: str) -> bool:
        """
        Delete a file from S3.
        
        Args:
            key (str): S3 object key
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            s3_client = self.get_s3_client()
            s3_client.delete_object(Bucket=self.bucket_name, Key=key)
            logger.info(f"Successfully deleted {key}")
            return True
        except Exception as e:
            logger.error(f"Error deleting file {key}: {e}")
            return False

    def get_object(self, key: str) -> bytes:
        """
        Get object content from S3 as bytes.

        Args:
            key (str): S3 object key

        Returns:
            bytes: Object content as bytes

        Raises:
            Exception: If object retrieval fails
        """
        try:
            s3_client = self.get_s3_client()
            response = s3_client.get_object(Bucket=self.bucket_name, Key=key)
            content = response['Body'].read()
            logger.info(f"Successfully retrieved object {key} from S3")
            return content
        except Exception as e:
            logger.error(f"Error retrieving object {key}: {e}")
            raise

    def get_object_stream(self, key: str):
        """
        Get object as a streaming body from S3.
        Useful for large files to avoid loading entire content into memory.

        Args:
            key (str): S3 object key

        Returns:
            StreamingBody: Streaming response body

        Raises:
            Exception: If object retrieval fails
        """
        try:
            s3_client = self.get_s3_client()
            response = s3_client.get_object(Bucket=self.bucket_name, Key=key)
            logger.info(f"Successfully opened stream for object {key} from S3")
            return response['Body']
        except Exception as e:
            logger.error(f"Error retrieving object stream {key}: {e}")
            raise

    def check_object_exists(self, key: str) -> bool:
        """
        Check if an object exists in S3.

        Args:
            key (str): S3 object key

        Returns:
            bool: True if object exists, False otherwise
        """
        try:
            s3_client = self.get_s3_client()
            s3_client.head_object(Bucket=self.bucket_name, Key=key)
            logger.info(f"Object {key} exists in S3")
            return True
        except Exception as e:
            logger.debug(f"Object {key} does not exist or is inaccessible: {e}")
            return False

    @property
    def bucket(self) -> str:
        """Get the configured bucket name."""
        return self.bucket_name