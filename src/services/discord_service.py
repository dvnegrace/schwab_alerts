import logging
import requests
from ..config import Config
from ..exceptions import NotificationError
from ..message_formatter import format_alert_message

logger = logging.getLogger(__name__)

def send_discord_alert(ticker: str, percent_change: float, position_desc: str = None, 
                      prev_close: float = None, current_price: float = None, 
                      volume: int = None, avg_volume: float = None, 
                      detailed_position_desc: str = None) -> bool:
    """Send Discord alert for stock movement"""
    try:
        # Initialize Discord webhook
        if not Config.DISCORD_WEBHOOK_URL:
            raise NotificationError("Discord webhook URL not configured")
        
        message_body = format_alert_message(ticker, percent_change, prev_close, current_price, volume, avg_volume, position_details=detailed_position_desc)
        
        logger.info(f"📱 Sending Discord alert for {ticker}: {message_body}")
        
        # Send Discord message
        payload = {
            'content': message_body
        }
        
        response = requests.post(Config.DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        response.raise_for_status()
        
        if response.status_code == 204:
            logger.info(f"✅ Discord message sent successfully for {ticker}")
            logger.info(f"📊 Discord Alert Summary - Ticker: {ticker}, Change: {percent_change:+.2f}%")
            
            # Add small delay to be respectful to Discord API
            import time
            time.sleep(0.5)
            logger.debug(f"Rate limit delay applied after Discord message for {ticker}")
            
            return True
        else:
            logger.error(f"Discord API error: {response.text}")
            raise NotificationError(f"Failed to send Discord message")
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error sending Discord message: {e}")
        raise NotificationError(f"Unexpected Discord error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error sending Discord message for {ticker}: {e}")
        raise NotificationError(f"Unexpected Discord error: {e}")

def send_discord_incremental_alert(ticker: str, last_percent: float, current_percent: float, 
                                  position_desc: str = None, prev_close: float = None, 
                                  current_price: float = None, volume: int = None, 
                                  avg_volume: float = None, detailed_position_desc: str = None) -> bool:
    """Send incremental alert for additional 5% moves"""
    try:
        # Initialize Discord webhook
        if not Config.DISCORD_WEBHOOK_URL:
            raise NotificationError("Discord webhook URL not configured")
        
        message_body = format_alert_message(ticker, current_percent, prev_close, current_price, volume, avg_volume, is_incremental=True, last_percent=last_percent, position_details=detailed_position_desc)
        
        logger.info(f"📱 Sending Discord incremental alert for {ticker}: {message_body}")
        
        # Send Discord message
        payload = {
            'content': message_body
        }
        
        response = requests.post(Config.DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        response.raise_for_status()
        
        if response.status_code == 204:
            logger.debug(f"Discord message sent successfully")
            return True
        else:
            logger.error(f"Discord API error: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error sending Discord message: {e}")
        return False
    except Exception as e:
        logger.error(f"Error sending Discord incremental alert: {e}")
        return False