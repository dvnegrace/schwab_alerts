import logging
from twilio.rest import Client
from twilio.base.exceptions import TwilioException
from ..config import Config
from ..exceptions import NotificationError

logger = logging.getLogger(__name__)

def send_voice_alert(ticker: str, percent_change: float) -> bool:
    """Send voice call alert for stock movement"""
    try:
        # Initialize Twilio client for voice calls only
        if not all([Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN, 
                   Config.TWILIO_VOICE_FROM_NUMBER, Config.ALERT_PHONE_NUMBER]):
            raise NotificationError("Twilio voice credentials not fully configured")
        
        client = Client(Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN)
        voice_from_number = Config.TWILIO_VOICE_FROM_NUMBER  # Voice call number
        to_number = Config.ALERT_PHONE_NUMBER
        
        # Create TwiML for voice message
        direction = "up" if percent_change > 0 else "down"
        abs_percent = abs(percent_change)
        
        twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">Alert: {ticker} is {direction} {abs_percent:.1f} percent.</Say>
    <Pause length="1"/>
    <Say voice="alice">I repeat: {ticker} is {direction} {abs_percent:.1f} percent.</Say>
</Response>'''
        
        logger.info(f"📞 Sending voice alert for {ticker}: {direction} {abs_percent:.2f}%")
        logger.info(f"📞 Voice Details - From: {voice_from_number}, To: {to_number}")
        
        call = client.calls.create(
            twiml=twiml,
            from_=voice_from_number,
            to=to_number
        )
        
        logger.info(f"✅ Voice call initiated successfully! Call SID: {call.sid}, Status: {call.status}")
        logger.info(f"📊 Voice Alert Summary - Ticker: {ticker}, Change: {percent_change:+.2f}%, Time: {call.date_created}")
        return True
        
    except TwilioException as e:
        logger.error(f"Twilio error sending voice call for {ticker}: {e}")
        raise NotificationError(f"Failed to send voice alert: {e}")
    except Exception as e:
        logger.error(f"Unexpected error sending voice call for {ticker}: {e}")
        raise NotificationError(f"Unexpected voice call error: {e}")

def send_voice_incremental_alert(ticker: str, last_percent: float, current_percent: float) -> bool:
    """Send voice alert for incremental spike"""
    try:
        # Initialize Twilio client for voice calls only
        if not all([Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN, 
                   Config.TWILIO_VOICE_FROM_NUMBER, Config.ALERT_PHONE_NUMBER]):
            raise NotificationError("Twilio voice credentials not fully configured")
        
        client = Client(Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN)
        voice_from_number = Config.TWILIO_VOICE_FROM_NUMBER
        to_number = Config.ALERT_PHONE_NUMBER
        
        voice_message = f"Alert: {ticker} has increased another {current_percent - last_percent:.1f} percent, now at {current_percent:.1f} percent total."
        
        call = client.calls.create(
            twiml=f'<Response><Say voice="woman">{voice_message}</Say></Response>',
            to=to_number,
            from_=voice_from_number
        )
        
        logger.info(f"📞 Voice incremental alert sent successfully. Call SID: {call.sid}")
        return True
        
    except TwilioException as e:
        logger.error(f"Twilio error sending voice incremental call for {ticker}: {e}")
        raise NotificationError(f"Failed to send voice incremental alert: {e}")
    except Exception as e:
        logger.error(f"Error sending voice incremental alert: {e}")
        raise NotificationError(f"Unexpected voice incremental alert error: {e}")