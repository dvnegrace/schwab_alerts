import logging
from typing import List, Dict, Tuple
from ..polygon_api.custom_bars_ohlc import get_seconds_data
from ..config import Config

logger = logging.getLogger(__name__)

def analyze_second_by_second_movements(ticker: str, seconds_data: Dict[str, any] = None) -> Dict[str, any]:
    """
    Analyze second-by-second price movements from today's seconds data
    
    Args:
        ticker: Stock ticker symbol
        seconds_data: Pre-fetched seconds data (optional, will fetch if not provided)
        
    Returns:
        Dict with analysis results including consecutive movements
    """
    try:
        # Use provided data or fetch if not provided
        if seconds_data is None:
            seconds_data = get_seconds_data(ticker)
            
        if not seconds_data or not seconds_data.get('results'):
            logger.warning(f"No seconds data available for {ticker}")
            return {'error': 'No seconds data available'}
        
        results = seconds_data['results']
        if len(results) < 2:
            logger.warning(f"Insufficient seconds data for {ticker} - only {len(results)} points")
            return {'error': 'Insufficient data points'}
        
        # Results are sorted desc (most recent first), so reverse for chronological order
        results = list(reversed(results))
        
        # Calculate second-by-second price changes
        second_changes = []
        for i in range(1, len(results)):
            prev_close = float(results[i-1].get('c', 0))
            current_close = float(results[i].get('c', 0))
            timestamp = results[i].get('t')
            
            if prev_close > 0 and current_close > 0:
                percent_change = ((current_close - prev_close) / prev_close) * 100
                second_changes.append({
                    'timestamp': timestamp,
                    'prev_close': prev_close,
                    'current_close': current_close,
                    'percent_change': percent_change
                })
        
        logger.info(f"{ticker} - Analyzed {len(second_changes)} second-by-second movements")
        
        # Find consecutive movements
        consecutive_sequences = find_consecutive_movements(second_changes)
        
        return {
            'ticker': ticker,
            'total_seconds': len(second_changes),
            'consecutive_sequences': consecutive_sequences,
            'raw_changes': second_changes[-10:] if second_changes else []  # Last 10 for debugging
        }
        
    except Exception as e:
        logger.error(f"Error analyzing second movements for {ticker}: {e}")
        return {'error': str(e)}

def find_consecutive_movements(second_changes: List[Dict]) -> List[Dict]:
    """
    Find sequences of 5, 10, and 15 consecutive seconds with configurable thresholds
    
    Args:
        second_changes: List of second-by-second changes
        
    Returns:
        List of consecutive movement sequences that meet criteria
    """
    sequences = []
    
    # Define timeframe configurations
    timeframes = [
        {
            'seconds': 5,
            'threshold': Config.FIVE_CONSECUTIVE_SECONDS_THRESHOLD_PERCENT,
            'name': '5-second'
        },
        {
            'seconds': 10,
            'threshold': Config.TEN_CONSECUTIVE_SECONDS_THRESHOLD_PERCENT,
            'name': '10-second'
        },
        {
            'seconds': 15,
            'threshold': Config.FIFTEEN_CONSECUTIVE_SECONDS_THRESHOLD_PERCENT,
            'name': '15-second'
        }
    ]
    
    # Check each timeframe
    for config in timeframes:
        seconds_count = config['seconds']
        threshold = config['threshold']
        name = config['name']
        
        # Use sliding window of specified seconds
        if len(second_changes) < seconds_count:
            continue  # Not enough data for this timeframe
            
        for i in range(len(second_changes) - seconds_count + 1):
            window = second_changes[i:i+seconds_count]
            
            # Calculate total change across the window
            total_change = sum(change['percent_change'] for change in window)
            
            # Determine overall direction
            direction = 'up' if total_change > 0 else 'down'
            
            # Check if total change meets criteria for this timeframe
            if abs(total_change) >= threshold:
                sequence_summary = {
                    'direction': direction,
                    'consecutive_seconds': seconds_count,
                    'total_change_percent': round(total_change, 2),
                    'threshold_used': threshold,
                    'timeframe_name': name,
                    'start_timestamp': window[0]['timestamp'],
                    'end_timestamp': window[-1]['timestamp'],
                    'duration_ms': window[-1]['timestamp'] - window[0]['timestamp'],
                    'start_price': window[0]['prev_close'],
                    'end_price': window[-1]['current_close'],
                    'window_start_index': i
                }
                sequences.append(sequence_summary)
    
    return sequences

def should_trigger_consecutive_seconds_alert(ticker: str, alert_directions: List[str], seconds_data: Dict[str, any] = None) -> Tuple[bool, str]:
    """
    Consecutive seconds alert filter - triggers on 5, 10, or 15 consecutive seconds with configurable thresholds
    
    Args:
        ticker: Stock ticker symbol
        alert_directions: List of directions to watch ('up', 'down')
        seconds_data: Pre-fetched seconds data (optional)
        
    Returns:
        Tuple of (should_alert, reason)
    """
    analysis = analyze_second_by_second_movements(ticker, seconds_data)
    
    if 'error' in analysis:
        return False, f"seconds analysis failed: {analysis['error']}"
    
    sequences = analysis.get('consecutive_sequences', [])
    if not sequences:
        return False, "no consecutive sequences found matching any timeframe thresholds"
    
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
        # Return the most significant sequence (prioritize by absolute change, then by timeframe)
        best_seq = max(matching_sequences, key=lambda s: (abs(s['total_change_percent']), s['consecutive_seconds']))
        direction_desc = "CALL" if best_seq['direction'] == 'up' else "PUT"
        timeframe_name = best_seq['timeframe_name']
        reason = f"{timeframe_name} window with {best_seq['total_change_percent']:+.2f}% total ({direction_desc} direction)"
        return True, reason
    
    # No matching sequences
    total_sequences = len(sequences)
    timeframes_checked = "5s/10s/15s"
    return False, f"found {total_sequences} sequences ({timeframes_checked}) but none match position directions"