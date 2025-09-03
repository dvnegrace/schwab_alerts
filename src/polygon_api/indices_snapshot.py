import logging
from typing import Optional, Dict
from .base_client import make_polygon_request, BASE_URL
from ..calculations import calculate_volume_ratio

logger = logging.getLogger(__name__)

def get_index_snapshot(ticker: str) -> Optional[Dict]:
    """Get snapshot for an index ticker (like $SPX)"""
    try:
        # Convert $SPX to I:SPX format for Polygon
        if ticker.startswith('$'):
            polygon_ticker = f"I:{ticker[1:]}"
        else:
            polygon_ticker = ticker
        
        url = f"{BASE_URL}/v3/snapshot/indices"
        params = {
            'ticker': polygon_ticker,
        }
        
        logger.info(f"Fetching index snapshot for {ticker} (Polygon: {polygon_ticker})")
        data = make_polygon_request(url, params, timeout=30)
        
        if not data or not data.get('results'):
            logger.error(f"No index data for {ticker}: {data}")
            return None
        
        result = data['results'][0]
        session = result.get('session', {})
        
        current_value = result.get('value')
        prev_close = session.get('previous_close')
        change_percent = session.get('change_percent', 0.0)
        
        if current_value is None or prev_close is None:
            logger.error(f"Missing required index data for {ticker}")
            return None
        
        # Create snapshot dict with index data (indices don't have volume)
        snapshot = {
            'ticker': ticker,
            'current_price': current_value,
            'prev_close': prev_close,
            'volume': None,
            'todays_change_perc': change_percent,
            'volume_ratio': None
        }
        
        logger.debug(f"Index {ticker}: {change_percent:+.2f}% (prev: ${prev_close} → current: ${current_value})")
        return snapshot
        
    except Exception as e:
        logger.error(f"Error fetching index snapshot for {ticker}: {e}")
        return None
