import os
from typing import Optional

class Config:
    # Local testing mode - set to True to print alerts instead of sending them
    LOCAL_TESTING_MODE: bool = os.getenv('LOCAL_TESTING_MODE', 'false').lower() == 'true'
    
    S3_BUCKET_NAME: str = os.getenv('S3_BUCKET_NAME', 'stock-positions-bucket')
    POSITIONS_JSON_KEY: str = os.getenv('POSITIONS_JSON_KEY', 'positions.json')
    POSITIONS_FILE_KEY: str = os.getenv('POSITIONS_FILE_KEY') or os.getenv('POSITIONS_JSON_KEY', 'positions.json')
    
    DYNAMODB_TABLE_NAME: str = os.getenv('DYNAMODB_TABLE_NAME', 'AlertState')
    
    POLYGON_API_KEY: str = os.getenv('POLYGON_API_KEY', '')
    
    # Telegram configuration
    TELEGRAM_BOT_TOKEN: str = os.getenv('TELEGRAM_BOT_TOKEN', '')
    TELEGRAM_CHAT_ID: str = os.getenv('TELEGRAM_CHAT_ID', '')
    
    # Twilio configuration (for voice calls only)
    TWILIO_ACCOUNT_SID: str = os.getenv('TWILIO_ACCOUNT_SID', '')
    TWILIO_AUTH_TOKEN: str = os.getenv('TWILIO_AUTH_TOKEN', '')
    TWILIO_VOICE_FROM_NUMBER: str = os.getenv('TWILIO_VOICE_FROM_NUMBER', '')  # Voice call number
    ALERT_PHONE_NUMBER: str = os.getenv('ALERT_PHONE_NUMBER', '')
    
    # Slack configuration
    SLACK_WEBHOOK_URL: str = os.getenv('SLACK_WEBHOOK_URL', '')
    
    # Discord configuration
    DISCORD_WEBHOOK_URL: str = os.getenv('DISCORD_WEBHOOK_URL', '')
    
    # IFTTT configuration
    IFTTT_WEBHOOK_URL: str = os.getenv('IFTTT_WEBHOOK_URL', '')
    
    AWS_REGION: str = os.getenv('AWS_REGION', 'us-east-1')
    
    ALERT_THRESHOLD_PERCENT: float = float(os.getenv('ALERT_THRESHOLD_PERCENT', '7.0'))
    
    # Additional basic alert thresholds
    ALERT_THRESHOLD_10_PERCENT: float = float(os.getenv('ALERT_THRESHOLD_10_PERCENT', '10.0'))
    ALERT_THRESHOLD_12_PERCENT: float = float(os.getenv('ALERT_THRESHOLD_12_PERCENT', '12.0'))
    ALERT_THRESHOLD_14_PERCENT: float = float(os.getenv('ALERT_THRESHOLD_14_PERCENT', '14.0'))
    
    # Consecutive seconds alert thresholds
    FIVE_CONSECUTIVE_SECONDS_THRESHOLD_PERCENT: float = float(os.getenv('FIVE_CONSECUTIVE_SECONDS_THRESHOLD_PERCENT', '1.5'))
    TEN_CONSECUTIVE_SECONDS_THRESHOLD_PERCENT: float = float(os.getenv('TEN_CONSECUTIVE_SECONDS_THRESHOLD_PERCENT', '2.0'))
    FIFTEEN_CONSECUTIVE_SECONDS_THRESHOLD_PERCENT: float = float(os.getenv('FIFTEEN_CONSECUTIVE_SECONDS_THRESHOLD_PERCENT', '2.5'))
    
    # Consecutive minutes alert threshold
    CONSECUTIVE_MINUTES_THRESHOLD_PERCENT: float = float(os.getenv('CONSECUTIVE_MINUTES_THRESHOLD_PERCENT', '3.0'))
    
    # Performance configuration
    CONCURRENT_WORKERS: int = int(os.getenv('CONCURRENT_WORKERS', '10'))
    VOLUME_FETCH_WORKERS: int = int(os.getenv('VOLUME_FETCH_WORKERS', '8'))
    
    @classmethod
    def validate(cls) -> None:
        # Always require Polygon API key
        required_vars = ['POLYGON_API_KEY']
        
        # Only require notification credentials if not in local testing mode
        if not cls.LOCAL_TESTING_MODE:
            required_vars.extend([
                'TELEGRAM_BOT_TOKEN',
                'TELEGRAM_CHAT_ID',
                'TWILIO_ACCOUNT_SID', 
                'TWILIO_AUTH_TOKEN',
                'TWILIO_VOICE_FROM_NUMBER',
                'ALERT_PHONE_NUMBER'
            ])
        
        missing = [var for var in required_vars if not getattr(cls, var)]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
