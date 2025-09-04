import logging
from datetime import datetime, timezone, timedelta
from typing import List, Tuple, Optional
from ..config import Config

logger = logging.getLogger(__name__)

def should_trigger_basic_alert(percent_change: float, alert_directions: List[str], last_alerted_percent: float = 0, last_alert_timestamp: Optional[str] = None) -> Tuple[bool, str]:
    """
    Basic alert filter - triggers when price movement exceeds threshold in matching direction
    
    Args:
        percent_change: Today's percentage change
        alert_directions: List of directions to watch ('up', 'down')
        last_alerted_percent: The percentage at which we last alerted (default 0)
        last_alert_timestamp: ISO timestamp of last alert for time-based retriggering
        
    Returns:
        Tuple of (should_alert, reason)
    """
    # If retriggering is enabled and cooldown has passed, reset last_alerted_percent to allow retriggering
    is_retrigger = False
    if Config.ENABLE_ALERT_RETRIGGERING and last_alert_timestamp and last_alerted_percent != 0:
        try:
            last_alert_time = datetime.fromisoformat(last_alert_timestamp.replace('Z', '+00:00'))
            time_since_alert = datetime.now(timezone.utc) - last_alert_time
            if time_since_alert >= timedelta(seconds=Config.ALERT_RETRIGGER_COOLDOWN_SECONDS):
                logger.debug(f"Retrigger eligible: {time_since_alert.total_seconds():.0f}s since last alert")
                is_retrigger = True
                last_alerted_percent = 0  # Reset to allow retriggering at same threshold
        except Exception as e:
            logger.warning(f"Error parsing timestamp {last_alert_timestamp}: {e}")
    
    # Check upward movements for calls
    if 'up' in alert_directions and percent_change > 0:
        if percent_change >= Config.ALERT_THRESHOLD_PERCENT and last_alerted_percent < Config.ALERT_THRESHOLD_PERCENT:
            reason = f"+{percent_change:.2f}% upward move matches CALL positions"
            if is_retrigger:
                reason += " [RETRIGGER]"
            return True, reason
    
    # Check downward movements for puts
    if 'down' in alert_directions and percent_change < 0:
        if percent_change <= -Config.ALERT_THRESHOLD_PERCENT and last_alerted_percent > -Config.ALERT_THRESHOLD_PERCENT:
            reason = f"{percent_change:.2f}% downward move matches PUT positions"
            if is_retrigger:
                reason += " [RETRIGGER]"
            return True, reason
    
    # No alert triggered
    directions_str = ' and '.join(alert_directions) if alert_directions else 'none'
    reason = f"change {percent_change:+.2f}% - no new threshold crossed (last alert: {last_alerted_percent:.2f}%)"
    return False, reason

def should_trigger_incremental_alert(current_percent: float, last_alerted_percent: float) -> Tuple[bool, str]:
    """
    Incremental alert filter - triggers when movement increases by threshold amount from last alert
    
    Args:
        current_percent: Current percentage change
        last_alerted_percent: Percentage change when last alerted
        
    Returns:
        Tuple of (should_alert, reason)
    """
    percent_increase_since_last = abs(current_percent) - abs(last_alerted_percent)
    
    if percent_increase_since_last >= Config.ALERT_INCREMENTAL_THRESHOLD:
        reason = f"was {last_alerted_percent:.2f}%, now {current_percent:.2f}% (+{percent_increase_since_last:.2f}%)"
        return True, reason
    else:
        reason = f"was {last_alerted_percent:.2f}%, now {current_percent:.2f}% (+{percent_increase_since_last:.2f}%)"
        return False, reason