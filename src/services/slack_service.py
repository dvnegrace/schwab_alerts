import logging
import requests
from ..config import Config
from ..exceptions import NotificationError
from ..message_formatter import format_alert_message

logger = logging.getLogger(__name__)

def send_slack_alert(ticker: str, percent_change: float, position_desc: str = None, 
                    prev_close: float = None, current_price: float = None, 
                    volume: int = None, avg_volume: float = None) -> bool:
    """Send Slack alert for stock movement"""
    try:
        # Initialize Slack webhook
        if not Config.SLACK_WEBHOOK_URL:
            raise NotificationError("Slack webhook URL not configured")
        
        message_body = format_alert_message(ticker, percent_change, prev_close, current_price, volume, avg_volume)
        
        logger.info(f"📱 Sending Slack alert for {ticker}: {message_body}")
        
        # Send Slack message
        payload = {
            'text': message_body
        }
        
        response = requests.post(Config.SLACK_WEBHOOK_URL, json=payload, timeout=10)
        response.raise_for_status()
        
        if response.text == 'ok':
            logger.info(f"✅ Slack message sent successfully for {ticker}")
            logger.info(f"📊 Slack Alert Summary - Ticker: {ticker}, Change: {percent_change:+.2f}%")
            
            # Add small delay to be respectful to Slack API
            import time
            time.sleep(0.5)
            logger.debug(f"Rate limit delay applied after Slack message for {ticker}")
            
            return True
        else:
            logger.error(f"Slack API error: {response.text}")
            raise NotificationError(f"Failed to send Slack message")
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error sending Slack message: {e}")
        raise NotificationError(f"Unexpected Slack error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error sending Slack message for {ticker}: {e}")
        raise NotificationError(f"Unexpected Slack error: {e}")

def send_slack_incremental_alert(ticker: str, last_percent: float, current_percent: float, 
                                position_desc: str = None, prev_close: float = None, 
                                current_price: float = None, volume: int = None, 
                                avg_volume: float = None) -> bool:
    """Send incremental alert for additional 5% moves"""
    try:
        # Initialize Slack webhook
        if not Config.SLACK_WEBHOOK_URL:
            raise NotificationError("Slack webhook URL not configured")
        
        message_body = format_alert_message(ticker, current_percent, prev_close, current_price, volume, avg_volume, is_incremental=True, last_percent=last_percent)
        
        logger.info(f"📱 Sending Slack incremental alert for {ticker}: {message_body}")
        
        # Send Slack message
        payload = {
            'text': message_body
        }
        
        response = requests.post(Config.SLACK_WEBHOOK_URL, json=payload, timeout=10)
        response.raise_for_status()
        
        if response.text == 'ok':
            logger.debug(f"Slack message sent successfully")
            return True
        else:
            logger.error(f"Slack API error: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error sending Slack message: {e}")
        return False
    except Exception as e:
        logger.error(f"Error sending Slack incremental alert: {e}")
        return False