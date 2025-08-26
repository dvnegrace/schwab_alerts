import logging
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from .base_client import make_polygon_request, BASE_URL, RATE_LIMIT_DELAY
import time

logger = logging.getLogger(__name__)

def get_historical_volume(ticker: str, days: int = 30) -> Optional[float]:
    """Get average volume over the last N days for comparison"""
    try:
        # Calculate date range (ending yesterday to avoid incomplete current day)
        end_date = datetime.now() - timedelta(days=1)
        start_date = end_date - timedelta(days=days)
        
        # Format dates for API
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')
        
        url = f"{BASE_URL}/v2/aggs/ticker/{ticker}/range/1/day/{start_str}/{end_str}"
        params = {
            'adjusted': 'true',
            'sort': 'asc',
            'limit': days + 10,  # Buffer for weekends/holidays
        }
        
        logger.info(f"Fetching {days}-day historical volume for {ticker}")
        data = make_polygon_request(url, params, timeout=30)
        
        if not data:
            return None
        
        results = data.get('results', [])
        if not results:
            logger.warning(f"No historical volume data found for {ticker}")
            return None
        
        # Extract volumes and calculate average
        volumes = [result['v'] for result in results if 'v' in result and result['v'] > 0]
        
        if not volumes:
            logger.warning(f"No valid volume data in historical results for {ticker}")
            return None
        
        avg_volume = sum(volumes) / len(volumes)
        logger.debug(f"{ticker}: {len(volumes)} days of volume data, average: {avg_volume:,.0f}")
        
        return avg_volume
        
    except Exception as e:
        logger.error(f"Error fetching historical volume for {ticker}: {e}")
        return None

def get_historical_volumes_concurrent(tickers: List[str], days: int = 30, max_workers: int = 10) -> Dict[str, Optional[float]]:
    """Get historical volumes for multiple tickers concurrently with rate limiting"""
    logger.info(f"🚀 Fetching historical volumes for {len(tickers)} tickers concurrently")
    
    volumes = {}
    
    def fetch_volume_with_rate_limit(ticker: str) -> tuple:
        """Fetch volume for single ticker with rate limiting"""
        time.sleep(RATE_LIMIT_DELAY)  # Rate limiting
        try:
            volume = get_historical_volume(ticker, days)
            return ticker, volume
        except Exception as e:
            logger.warning(f"Volume fetch failed for {ticker}: {e}")
            return ticker, None
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_ticker = {
            executor.submit(fetch_volume_with_rate_limit, ticker): ticker
            for ticker in tickers
        }
        
        for future in as_completed(future_to_ticker):
            ticker = future_to_ticker[future]
            try:
                fetched_ticker, volume = future.result(timeout=20)  # 20 second timeout
                volumes[fetched_ticker] = volume
                
            except Exception as e:
                logger.warning(f"Concurrent volume fetch failed for {ticker}: {e}")
                volumes[ticker] = None
    
    successful = sum(1 for v in volumes.values() if v is not None)
    logger.info(f"✅ Concurrent volume fetch completed: {successful}/{len(tickers)} successful")
    return volumes