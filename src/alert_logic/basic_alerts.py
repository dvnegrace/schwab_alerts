import logging
from typing import List, Tuple
from ..config import Config

logger = logging.getLogger(__name__)

def should_trigger_basic_alert(percent_change: float, alert_directions: List[str]) -> Tuple[bool, str]:
    """
    Basic alert filter - triggers when price movement exceeds threshold in matching direction
    
    Args:
        percent_change: Today's percentage change
        alert_directions: List of directions to watch ('up', 'down')
        
    Returns:
        Tuple of (should_alert, reason)
    """
    # Check if movement matches position types and exceeds threshold
    if percent_change >= Config.ALERT_THRESHOLD_PERCENT and 'up' in alert_directions:
        # Stock moved up and we have calls
        reason = f"+{percent_change:.2f}% upward move matches CALL positions (basic threshold)"
        return True, reason
        
    elif percent_change <= -Config.ALERT_THRESHOLD_PERCENT and 'down' in alert_directions:
        # Stock moved down and we have puts  
        reason = f"{percent_change:.2f}% downward move matches PUT positions (basic threshold)"
        return True, reason
    
    # No alert triggered
    directions_str = ' and '.join(alert_directions) if alert_directions else 'none'
    reason = f"change {percent_change:+.2f}% - no alert (watching {directions_str} moves, threshold: ±{Config.ALERT_THRESHOLD_PERCENT}%)"
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