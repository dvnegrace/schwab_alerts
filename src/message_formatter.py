from datetime import datetime, timezone, timedelta

def format_alert_message(ticker: str, percent_change: float, prev_close: float = None, 
                        current_price: float = None, volume: int = None, avg_volume: float = None,
                        is_incremental: bool = False, last_percent: float = None, 
                        position_details: str = None) -> str:
    """Format alert message for initial or incremental alerts"""
    
    # Get current time in EST
    est = timezone(timedelta(hours=-5))
    current_time = datetime.now(est).strftime("%Y-%m-%d %I:%M %p")
    
    # Format percentage and spike text
    if is_incremental and last_percent is not None:
        percent_text = f"{last_percent:.2f}% -> {percent_change:.2f}%"
        spike_text = "Another Spike!"
    else:
        percent_text = f"{percent_change:+.2f}%"
        if percent_change > 0:
            spike_text = "Spike UP!"
        else:
            spike_text = "Spike DOWN!"
    
    if prev_close is not None and current_price is not None:
        message_body = f"[{ticker}] [{current_time}] 🚨 {percent_text} 🚨 {spike_text} ${prev_close:.2f} → ${current_price:.2f}."
        
        if volume is not None:
            volume_text = f" || Volume: {volume:,}"
            if avg_volume is not None and avg_volume > 0:
                ratio = volume / avg_volume
                volume_text += f" ({avg_volume:,.0f} / {ratio:.2f}x avg)"
            else:
                volume_text += " (avg volume unavailable)"
            message_body += volume_text
        
        # Add position details if provided
        if position_details:
            message_body += f"\n\nWe have {position_details}"
    else:
        # Fallback format if price data not available
        if is_incremental:
            message_body = f"[{ticker}] [{current_time}] 🚨 {percent_text} 🚨 {spike_text}"
        else:
            direction = 'up' if percent_change > 0 else 'down'
            message_body = f"[{ticker}] [{current_time}] 🚨 {percent_text} 🚨 {spike_text} {direction}"
    
    # Telegram has 4096 character limit
    max_length = 4096
    if len(message_body) > max_length:
        if prev_close is not None and current_price is not None:
            message_body = f"[{ticker}] [{current_time}] {spike_text} ${prev_close:.2f} → ${current_price:.2f}"
        
        # If still too long, truncate the time format
        if len(message_body) > max_length:
            short_time = datetime.now(est).strftime("%m-%d %I:%M %p")
            message_body = f"[{ticker}] [{short_time}] {spike_text} ${prev_close:.2f} → ${current_price:.2f}"
    
    return message_body

