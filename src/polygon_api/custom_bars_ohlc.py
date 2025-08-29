import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from .base_client import make_polygon_request, BASE_URL

logger = logging.getLogger(__name__)

def get_bars_ohlc(ticker: str, 
                  multiplier: int, 
                  timespan: str,
                  from_date: str, 
                  to_date: str,
                  adjusted: bool = True,
                  sort: str = "desc",
                  limit: int = 5000) -> Optional[Dict[str, Any]]:
    """Get OHLC bars data from Polygon API"""
    
    url = f"{BASE_URL}/v2/aggs/ticker/{ticker.upper()}/range/{multiplier}/{timespan}/{from_date}/{to_date}"
    
    params = {
        'adjusted': str(adjusted).lower(),
        'sort': sort,
        'limit': limit
    }
    
    logger.debug(f"Fetching {timespan} bars for {ticker.upper()} from {from_date} to {to_date}")
    
    data = make_polygon_request(url, params, timeout=30)
    
    if data:
        results_count = data.get('resultsCount', 0)
        logger.debug(f"Retrieved {results_count} {timespan} bars for {ticker.upper()}")
    
    return data

def get_previous_days(ticker: str) -> Optional[Dict[str, Any]]:
    """Get previous 3 days of daily data"""
    
    # Calculate date range (go back 10 days to account for weekends)
    end_date = datetime.now() - timedelta(days=1)  # Yesterday
    start_date = end_date - timedelta(days=10)     # 10 days back
    
    from_date = start_date.strftime('%Y-%m-%d')
    to_date = end_date.strftime('%Y-%m-%d')
    
    return get_bars_ohlc(
        ticker=ticker,
        multiplier=1,
        timespan="day",
        from_date=from_date,
        to_date=to_date,
        adjusted=True,
        sort="desc",
        limit=10
    )

def get_seconds_data(ticker: str) -> Optional[Dict[str, Any]]:
    """Get seconds data for today, with fallback to previous trading day if empty"""
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    # First try today's data
    data = get_bars_ohlc(
        ticker=ticker,
        multiplier=1,
        timespan="second",
        from_date=today,
        to_date=today,
        adjusted=True,
        sort="desc",
        limit=3600
    )
    
    # If no results, try previous trading day (yesterday)
    if not data or not data.get('results'):
        logger.info(f"No seconds data for {ticker} on {today}, trying previous trading day")
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        data = get_bars_ohlc(
            ticker=ticker,
            multiplier=1,
            timespan="second",
            from_date=yesterday,
            to_date=yesterday,
            adjusted=True,
            sort="desc",
            limit=3600
        )
        
        if data and data.get('results'):
            logger.info(f"Found seconds data for {ticker} on {yesterday} (previous trading day)")
    
    return data

def get_minutes_data(ticker: str) -> Optional[Dict[str, Any]]:
    """Get minutes data for today (last 60 minutes)"""
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    return get_bars_ohlc(
        ticker=ticker,
        multiplier=1,
        timespan="minute",
        from_date=today,
        to_date=today,
        adjusted=True,
        sort="desc",
        limit=60
    )

def get_concurrent_data(tickers: List[str], data_type: str = "minutes") -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Get data concurrently for multiple tickers
    
    Args:
        tickers: List of ticker symbols
        data_type: Type of data to fetch ("minutes", "seconds", "days")
        
    Returns:
        Dictionary mapping ticker to data results
    """
    results = {}
    
    def fetch_single_data(ticker: str) -> tuple:
        """Fetch data for a single ticker"""
        try:
            if data_type == "minutes":
                data = get_minutes_data(ticker)
            elif data_type == "seconds":
                data = get_seconds_data(ticker)
            elif data_type == "days":
                data = get_previous_days(ticker)
            else:
                raise ValueError(f"Invalid data_type: {data_type}")
                
            return ticker, data, None
        except Exception as e:
            logger.error(f"Error fetching {data_type} data for {ticker}: {e}")
            return ticker, None, str(e)
    
    # Use concurrent processing with 30 workers
    with ThreadPoolExecutor(max_workers=30) as executor:
        futures = [executor.submit(fetch_single_data, ticker) for ticker in tickers]
        
        for future in futures:
            try:
                ticker, data, error = future.result()
                results[ticker] = data
                
                if error:
                    logger.warning(f"Failed to get {data_type} data for {ticker}: {error}")
                    
            except Exception as e:
                logger.error(f"Error processing concurrent {data_type} result: {e}")
    
    logger.info(f"Concurrent {data_type} fetch completed: {len([r for r in results.values() if r is not None])}/{len(tickers)} successful")
    return results

def get_concurrent_minutes_data(tickers: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
    """Get minutes data concurrently for multiple tickers"""
    return get_concurrent_data(tickers, "minutes")

def get_concurrent_seconds_data(tickers: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
    """Get seconds data concurrently for multiple tickers"""
    return get_concurrent_data(tickers, "seconds")

def get_concurrent_days_data(tickers: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
    """Get previous days data concurrently for multiple tickers"""
    return get_concurrent_data(tickers, "days")
