import boto3
import logging
from typing import Optional
from botocore.exceptions import ClientError, NoCredentialsError
from .config import Config
from .exceptions import StockAlertError

logger = logging.getLogger(__name__)

class S3Client:
    def __init__(self):
        try:
            self.s3_client = boto3.client('s3', region_name=Config.AWS_REGION)
        except NoCredentialsError:
            logger.error("AWS credentials not found")
            raise StockAlertError("AWS credentials not configured")
    
    def download_positions_file(self) -> str:
        """Download positions file (CSV or JSON) from S3 and return content as string"""
        try:
            logger.info(f"Downloading {Config.POSITIONS_FILE_KEY} from bucket {Config.S3_BUCKET_NAME}")
            
            response = self.s3_client.get_object(
                Bucket=Config.S3_BUCKET_NAME,
                Key=Config.POSITIONS_FILE_KEY
            )
            
            content = response['Body'].read().decode('utf-8')
            file_type = 'JSON' if Config.POSITIONS_FILE_KEY.lower().endswith('.json') else 'CSV'
            logger.info(f"Successfully downloaded {file_type} file with {len(content)} characters")
            return content
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                logger.error(f"Positions file {Config.POSITIONS_FILE_KEY} not found in bucket")
                raise StockAlertError(f"Positions file not found in S3 bucket")
            elif error_code == 'NoSuchBucket':
                logger.error(f"S3 bucket {Config.S3_BUCKET_NAME} not found")
                raise StockAlertError(f"S3 bucket {Config.S3_BUCKET_NAME} does not exist")
            else:
                logger.error(f"Failed to download positions file: {e}")
                raise StockAlertError(f"Failed to download positions file: {e}")
        except Exception as e:
            logger.error(f"Unexpected error downloading positions file: {e}")
            raise StockAlertError(f"Unexpected error downloading positions file: {e}")
    
    # Keep legacy method for backward compatibility
    def download_positions_csv(self) -> str:
        """Legacy method - download positions file"""
        return self.download_positions_file()