import logging
from typing import List, Dict, Tuple
from ..polygon_api.custom_bars_ohlc import get_minutes_data
from ..config import Config

logger = logging.getLogger(__name__)

def analyze_minute_by_minute_movements(ticker: str, minutes_data: Dict[str, any] = None) -> Dict[str, any]:
    """
    Analyze minute-by-minute price movements from today's minutes data
    
    Args:
        ticker: Stock ticker symbol
        minutes_data: Pre-fetched minutes data (optional, will fetch if not provided)
        
    Returns:
        Dict with analysis results including consecutive movements
    """
    try:
        # Use provided data or fetch if not provided
        if minutes_data is None:
            minutes_data = get_minutes_data(ticker)
            
        if not minutes_data or not minutes_data.get('results'):
            logger.warning(f"No minutes data available for {ticker}")
            return {'error': 'No minutes data available'}
        
        results = minutes_data['results']
        if len(results) < 2:
            logger.warning(f"Insufficient minutes data for {ticker} - only {len(results)} points")
            return {'error': 'Insufficient data points'}
        
        # Results are sorted desc (most recent first), so reverse for chronological order
        results = list(reversed(results))
        
        # Calculate minute-by-minute price changes
        minute_changes = []
        for i in range(1, len(results)):
            prev_close = float(results[i-1].get('c', 0))
            current_close = float(results[i].get('c', 0))
            timestamp = results[i].get('t')
            
            if prev_close > 0 and current_close > 0:
                percent_change = ((current_close - prev_close) / prev_close) * 100
                minute_changes.append({
                    'timestamp': timestamp,
                    'prev_close': prev_close,
                    'current_close': current_close,
                    'percent_change': percent_change
                })
        
        logger.info(f"{ticker} - Analyzed {len(minute_changes)} minute-by-minute movements")
        
        # Find consecutive movements
        consecutive_sequences = find_consecutive_minute_movements(minute_changes)
        
        return {
            'ticker': ticker,
            'total_minutes': len(minute_changes),
            'consecutive_sequences': consecutive_sequences,
            'raw_changes': minute_changes[-10:] if minute_changes else []  # Last 10 for debugging
        }
        
    except Exception as e:
        logger.error(f"Error analyzing minute movements for {ticker}: {e}")
        return {'error': str(e)}

def find_consecutive_minute_movements(minute_changes: List[Dict]) -> List[Dict]:
    """
    Find sequences of consecutive minutes with configurable threshold total movement
    
    Args:
        minute_changes: List of minute-by-minute changes
        
    Returns:
        List of consecutive movement sequences that meet criteria
    """
    sequences = []
    threshold = Config.CONSECUTIVE_MINUTES_THRESHOLD_PERCENT
    
    # Check all possible consecutive minute sequences (2+ minutes)
    for window_size in range(2, min(len(minute_changes) + 1, 11)):  # Check 2-10 minute windows
        for i in range(len(minute_changes) - window_size + 1):
            window = minute_changes[i:i+window_size]
            
            # Calculate total change across the window
            total_change = sum(change['percent_change'] for change in window)
            
            # Determine overall direction
            direction = 'up' if total_change > 0 else 'down'
            
            # Check if total change meets criteria
            if abs(total_change) >= threshold:
                sequence_summary = {
                    'direction': direction,
                    'consecutive_minutes': window_size,
                    'total_change_percent': round(total_change, 2),
                    'threshold_used': threshold,
                    'timeframe_name': f'{window_size}-minute',
                    'start_timestamp': window[0]['timestamp'],
                    'end_timestamp': window[-1]['timestamp'],
                    'duration_ms': window[-1]['timestamp'] - window[0]['timestamp'],
                    'start_price': window[0]['prev_close'],
                    'end_price': window[-1]['current_close'],
                    'window_start_index': i
                }
                sequences.append(sequence_summary)
    
    return sequences

def should_trigger_consecutive_minutes_alert(ticker: str, alert_directions: List[str], minutes_data: Dict[str, any] = None) -> Tuple[bool, str]:
    """
    Consecutive minutes alert filter - triggers on consecutive minutes with ±3% total move
    
    Args:
        ticker: Stock ticker symbol
        alert_directions: List of directions to watch ('up', 'down')
        minutes_data: Pre-fetched minutes data (optional)
        
    Returns:
        Tuple of (should_alert, reason)
    """
    analysis = analyze_minute_by_minute_movements(ticker, minutes_data)
    
    if 'error' in analysis:
        return False, f"minutes analysis failed: {analysis['error']}"
    
    sequences = analysis.get('consecutive_sequences', [])
    if not sequences:
        threshold = Config.CONSECUTIVE_MINUTES_THRESHOLD_PERCENT
        return False, f"no consecutive minute sequences found with ±{threshold}% total movement"
    
    # Check each sequence for alert criteria
    matching_sequences = []
    for seq in sequences:
        direction = seq['direction']
        total_change = seq['total_change_percent']
        threshold = seq['threshold_used']
        
        # Check if this sequence matches our position directions and meets threshold
        if direction == 'up' and 'up' in alert_directions and total_change >= threshold:
            matching_sequences.append(seq)
        elif direction == 'down' and 'down' in alert_directions and total_change <= -threshold:
            matching_sequences.append(seq)
    
    if matching_sequences:
        # Return the most significant sequence (prioritize by absolute change, then by window size)
        best_seq = max(matching_sequences, key=lambda s: (abs(s['total_change_percent']), s['consecutive_minutes']))
        direction_desc = "CALL" if best_seq['direction'] == 'up' else "PUT"
        timeframe_name = best_seq['timeframe_name']
        reason = f"{timeframe_name} window with {best_seq['total_change_percent']:+.2f}% total ({direction_desc} direction)"
        return True, reason
    
    # No matching sequences
    total_sequences = len(sequences)
    return False, f"found {total_sequences} minute sequences but none match position directions"