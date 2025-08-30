import logging
from typing import List, Tuple
from ..config import Config

logger = logging.getLogger(__name__)

def should_trigger_basic_alert(percent_change: float, alert_directions: List[str], last_alerted_percent: float = 0) -> Tuple[bool, str]:
    """
    Basic alert filter - triggers when price movement exceeds threshold in matching direction
    
    Args:
        percent_change: Today's percentage change
        alert_directions: List of directions to watch ('up', 'down')
        last_alerted_percent: The percentage at which we last alerted (default 0)
        
    Returns:
        Tuple of (should_alert, reason)
    """
    # Check upward movements for calls
    if 'up' in alert_directions and percent_change > 0:
        if percent_change >= Config.ALERT_THRESHOLD_14_PERCENT and last_alerted_percent < Config.ALERT_THRESHOLD_14_PERCENT:
            reason = f"+{percent_change:.2f}% upward move matches CALL positions (14% threshold)"
            return True, reason
        elif percent_change >= Config.ALERT_THRESHOLD_12_PERCENT and last_alerted_percent < Config.ALERT_THRESHOLD_12_PERCENT:
            reason = f"+{percent_change:.2f}% upward move matches CALL positions (12% threshold)"
            return True, reason
        elif percent_change >= Config.ALERT_THRESHOLD_10_PERCENT and last_alerted_percent < Config.ALERT_THRESHOLD_10_PERCENT:
            reason = f"+{percent_change:.2f}% upward move matches CALL positions (10% threshold)"
            return True, reason
        elif percent_change >= Config.ALERT_THRESHOLD_PERCENT and last_alerted_percent < Config.ALERT_THRESHOLD_PERCENT:
            reason = f"+{percent_change:.2f}% upward move matches CALL positions (basic threshold)"
            return True, reason
    
    # Check downward movements for puts
    if 'down' in alert_directions and percent_change < 0:
        if percent_change <= -Config.ALERT_THRESHOLD_14_PERCENT and last_alerted_percent > -Config.ALERT_THRESHOLD_14_PERCENT:
            reason = f"{percent_change:.2f}% downward move matches PUT positions (14% threshold)"
            return True, reason
        elif percent_change <= -Config.ALERT_THRESHOLD_12_PERCENT and last_alerted_percent > -Config.ALERT_THRESHOLD_12_PERCENT:
            reason = f"{percent_change:.2f}% downward move matches PUT positions (12% threshold)"
            return True, reason
        elif percent_change <= -Config.ALERT_THRESHOLD_10_PERCENT and last_alerted_percent > -Config.ALERT_THRESHOLD_10_PERCENT:
            reason = f"{percent_change:.2f}% downward move matches PUT positions (10% threshold)"
            return True, reason
        elif percent_change <= -Config.ALERT_THRESHOLD_PERCENT and last_alerted_percent > -Config.ALERT_THRESHOLD_PERCENT:
            reason = f"{percent_change:.2f}% downward move matches PUT positions (basic threshold)"
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
    percent_increase_since_last = current_percent - last_alerted_percent
    
    if percent_increase_since_last >= Config.ALERT_THRESHOLD_PERCENT:
        reason = f"was {last_alerted_percent:.2f}%, now {current_percent:.2f}% (+{percent_increase_since_last:.2f}%)"
        return True, reason
    else:
        reason = f"was {last_alerted_percent:.2f}%, now {current_percent:.2f}% (+{percent_increase_since_last:.2f}%)"
        return False, reason