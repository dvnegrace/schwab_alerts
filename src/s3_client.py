import boto3
import logging
import os
from typing import Optional
from botocore.exceptions import ClientError, NoCredentialsError
from .config import Config
from .exceptions import StockAlertError

logger = logging.getLogger(__name__)

class S3Client:
    def __init__(self):
        # Only initialize S3 client if not in local testing mode
        if not Config.LOCAL_TESTING_MODE:
            try:
                self.s3_client = boto3.client('s3', region_name=Config.AWS_REGION)
            except NoCredentialsError:
                logger.error("AWS credentials not found")
                raise StockAlertError("AWS credentials not configured")
        else:
            self.s3_client = None
            logger.info("🧪 LOCAL TESTING MODE - Will look for local positions.json file")
    
    def download_positions_file(self) -> str:
        """Download positions file (CSV or JSON) from S3 and return content as string"""
        # In local testing mode, try to read local file first
        if Config.LOCAL_TESTING_MODE:
            local_file = 'positions.json'
            if os.path.exists(local_file):
                logger.info(f"📂 Reading local file: {local_file}")
                try:
                    with open(local_file, 'r') as f:
                        content = f.read()
                    logger.info(f"✅ Successfully read local file with {len(content)} characters")
                    return content
                except Exception as e:
                    logger.error(f"Failed to read local file {local_file}: {e}")
                    raise StockAlertError(f"Failed to read local positions file: {e}")
            else:
                logger.error(f"Local file {local_file} not found in current directory")
                raise StockAlertError(f"Local positions file not found. Please ensure {local_file} exists in the current directory")
        
        # Production mode - download from S3
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