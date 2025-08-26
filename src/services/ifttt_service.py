import logging
import requests
from ..config import Config
from ..exceptions import NotificationError

logger = logging.getLogger(__name__)

def send_ifttt_call() -> bool:
    """Trigger IFTTT webhook to make phone call"""
    try:
        if not Config.IFTTT_WEBHOOK_URL:
            raise NotificationError("IFTTT webhook URL not configured")
        
        logger.info(f"📞 Triggering IFTTT phone call")
        
        response = requests.post(Config.IFTTT_WEBHOOK_URL, timeout=10)
        response.raise_for_status()
        
        logger.info(f"✅ IFTTT webhook triggered successfully")
        return True
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error triggering IFTTT webhook: {e}")
        raise NotificationError(f"IFTTT webhook error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error triggering IFTTT webhook: {e}")
        raise NotificationError(f"Unexpected IFTTT error: {e}")