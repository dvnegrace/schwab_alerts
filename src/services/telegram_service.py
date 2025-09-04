import logging
import requests
from ..config import Config
from ..exceptions import NotificationError
from ..message_formatter import format_alert_message

logger = logging.getLogger(__name__)

def send_telegram_alert(ticker: str, percent_change: float, position_desc: str = None, 
                       prev_close: float = None, current_price: float = None, 
                       volume: int = None, avg_volume: float = None, 
                       detailed_position_desc: str = None, total_calls: int = 0, total_puts: int = 0) -> bool:
    """Send Telegram alert for stock movement"""
    try:
        # Initialize Telegram bot
        if not all([Config.TELEGRAM_BOT_TOKEN, Config.TELEGRAM_CHAT_ID]):
            raise NotificationError("Telegram credentials not fully configured")
        
        telegram_bot_token = Config.TELEGRAM_BOT_TOKEN
        telegram_chat_id = Config.TELEGRAM_CHAT_ID
        telegram_api_url = f"https://api.telegram.org/bot{telegram_bot_token}"
        
        message_body = format_alert_message(ticker, percent_change, prev_close, current_price, volume, avg_volume, position_details=detailed_position_desc, total_calls=total_calls, total_puts=total_puts)
        
        logger.info(f"📱 Sending Telegram alert for {ticker}: {message_body}")
        logger.info(f"📱 Telegram Details - Chat ID: {telegram_chat_id}")
        
        # Send Telegram message
        url = f"{telegram_api_url}/sendMessage"
        payload = {
            'chat_id': telegram_chat_id,
            'text': message_body,
            'parse_mode': 'HTML'  # Support HTML formatting if needed
        }
        
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        
        result = response.json()
        if result.get('ok'):
            logger.debug(f"Telegram message sent successfully: {result.get('result', {}).get('message_id')}")
            logger.info(f"✅ Telegram message sent successfully for {ticker}")
            logger.info(f"📊 Telegram Alert Summary - Ticker: {ticker}, Change: {percent_change:+.2f}%")
            
            # Add small delay to be respectful to Telegram API
            import time
            time.sleep(0.5)
            logger.debug(f"Rate limit delay applied after Telegram message for {ticker}")
            
            return True
        else:
            logger.error(f"Telegram API error: {result}")
            raise NotificationError(f"Failed to send Telegram message")
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error sending Telegram message: {e}")
        raise NotificationError(f"Unexpected Telegram error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error sending Telegram message for {ticker}: {e}")
        raise NotificationError(f"Unexpected Telegram error: {e}")

def send_telegram_incremental_alert(ticker: str, last_percent: float, current_percent: float, 
                                   position_desc: str = None, prev_close: float = None, 
                                   current_price: float = None, volume: int = None, 
                                   avg_volume: float = None, detailed_position_desc: str = None, total_calls: int = 0, total_puts: int = 0) -> bool:
    """Send incremental alert for additional 5% moves"""
    try:
        # Initialize Telegram bot
        if not all([Config.TELEGRAM_BOT_TOKEN, Config.TELEGRAM_CHAT_ID]):
            raise NotificationError("Telegram credentials not fully configured")
        
        telegram_bot_token = Config.TELEGRAM_BOT_TOKEN
        telegram_chat_id = Config.TELEGRAM_CHAT_ID
        telegram_api_url = f"https://api.telegram.org/bot{telegram_bot_token}"
        
        message_body = format_alert_message(ticker, current_percent, prev_close, current_price, volume, avg_volume, is_incremental=True, last_percent=last_percent, position_details=detailed_position_desc, total_calls=total_calls, total_puts=total_puts)
        
        logger.info(f"📱 Sending Telegram incremental alert for {ticker}: {message_body}")
        
        # Send Telegram message
        url = f"{telegram_api_url}/sendMessage"
        payload = {
            'chat_id': telegram_chat_id,
            'text': message_body,
            'parse_mode': 'HTML'  # Support HTML formatting if needed
        }
        
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        
        result = response.json()
        if result.get('ok'):
            logger.debug(f"Telegram message sent successfully: {result.get('result', {}).get('message_id')}")
            return True
        else:
            logger.error(f"Telegram API error: {result}")
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error sending Telegram message: {e}")
        return False
    except Exception as e:
        logger.error(f"Error sending Telegram incremental alert: {e}")
        return False