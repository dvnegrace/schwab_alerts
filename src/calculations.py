def calculate_percent_change(current_price: float, prev_close: float) -> float:
    """Calculate percentage change from previous close"""
    if prev_close <= 0:
        raise ValueError(f"Invalid prior close price: {prev_close}")
    
    change = ((current_price - prev_close) / prev_close) * 100
    return round(change, 2)

def calculate_volume_ratio(current_volume: int, avg_volume: float) -> float:
    """Calculate volume ratio vs average volume"""
    if avg_volume is None or avg_volume <= 0:
        return None
    
    if current_volume is None:
        return None
        
    return current_volume / avg_volume