import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional
from .base_client import RATE_LIMIT_DELAY
from .custom_bars_ohlc import get_seconds_data, get_previous_days
from .indices_snapshot import get_index_snapshot
from ..calculations import calculate_percent_change, calculate_volume_ratio

logger = logging.getLogger(__name__)

def get_ticker_concurrent(tickers: List[str]) -> Dict[str, Dict]:
    """Get snapshots for specific tickers using concurrent requests with rate limiting"""
    logger.info(f"🚀 Starting concurrent processing of {len(tickers)} tickers with 50 workers (20 req/sec limit)")
    
    snapshots = {}
    tickers_upper = [t.upper() for t in tickers]
    
    # Separate index and stock tickers
    index_tickers = [t for t in tickers_upper if t.startswith('$')]
    stock_tickers = [t for t in tickers_upper if not t.startswith('$')]
    
    # Process index tickers
    if index_tickers:
        for ticker in index_tickers:
            snapshot = get_index_snapshot(ticker)
            if snapshot:
                snapshots[ticker] = snapshot
                logger.info(f"✅ Got index snapshot for {ticker}: {snapshot['todays_change_perc']:+.2f}%")
            else:
                logger.warning(f"❌ Failed to get index snapshot for {ticker}")
    
    # Process stock tickers concurrently
    if stock_tickers:
        stock_snapshots = _process_stock_tickers_concurrent(stock_tickers)
        snapshots.update(stock_snapshots)
    
    # Report results
    found_tickers = set(snapshots.keys())
    requested_tickers = set(stock_tickers + index_tickers)
    missing_tickers = requested_tickers - found_tickers
    
    if missing_tickers:
        logger.warning(f"❌ Missing snapshots for {len(missing_tickers)} tickers: {', '.join(sorted(missing_tickers))}")
    
    logger.info(f"✅ Concurrent processing completed: {len(snapshots)}/{len(requested_tickers)} successful")
    return snapshots

def _process_stock_tickers_concurrent(stock_tickers: List[str]) -> Dict[str, Dict]:
    """Process stock tickers with ThreadPoolExecutor and rate limiting"""
    snapshots = {}
    
    def fetch_single_ticker(ticker: str) -> tuple:
        """Fetch data for a single ticker using OHLC bars with rate limiting"""
        time.sleep(RATE_LIMIT_DELAY)  # Rate limiting
        
        try:
            # Get current price from seconds data
            seconds_data = get_seconds_data(ticker)
            if not seconds_data or not seconds_data.get('results'):
                return ticker, None, 'No seconds data'
            
            # Get previous close from daily data
            daily_data = get_previous_days(ticker)
            if not daily_data or not daily_data.get('results'):
                return ticker, None, 'No daily data'
            
            # Combine data into ticker_data format
            ticker_data = {
                'ticker': ticker,
                'seconds_results': seconds_data['results'],
                'daily_results': daily_data['results']
            }
            
            return ticker, ticker_data, None
                
        except Exception as e:
            return ticker, None, str(e)
    
    # Use ThreadPoolExecutor for concurrent requests
    with ThreadPoolExecutor(max_workers=50) as executor:
        futures = [executor.submit(fetch_single_ticker, ticker) for ticker in stock_tickers]
        
        for future in futures:
            try:
                ticker, ticker_data, error = future.result()
                
                if error:
                    logger.warning(f"Failed to get data for {ticker}: {error}")
                    continue
                
                # Process the ticker data
                snapshot = parse_ticker_data(ticker_data)
                if snapshot:
                    snapshots[ticker] = snapshot
                    
            except Exception as e:
                logger.error(f"Error processing concurrent result: {e}")
    
    return snapshots

def parse_ticker_data(ticker_data: dict) -> Optional[Dict]:
    """Parse ticker data from OHLC bars"""
    try:
        ticker = ticker_data.get('ticker', '').upper()
        if not ticker:
            return None
        
        # Extract price data from OHLC bars
        current_price = None
        prev_close = None
        todays_change_perc = None
        volume = None
        
        # Get current price from most recent seconds data
        seconds_results = ticker_data.get('seconds_results', [])
        if seconds_results:
            # Results are sorted desc, so first is most recent
            latest_second = seconds_results[0]
            current_price = float(latest_second.get('c', 0))
            seconds_timestamp = latest_second.get('t')
            logger.debug(f"{ticker} - Latest seconds data: c={current_price}, t={seconds_timestamp}")
        
        # Get previous close from most recent daily data
        daily_results = ticker_data.get('daily_results', [])
        if daily_results:
            # Results are sorted desc, so first is most recent
            latest_day = daily_results[0]
            prev_close = float(latest_day.get('c', 0))
            daily_timestamp = latest_day.get('t')
            logger.debug(f"{ticker} - Latest daily data: c={prev_close}, t={daily_timestamp}")
        
        # Calculate percentage change
        if current_price and prev_close and prev_close > 0:
            todays_change_perc = ((current_price - prev_close) / prev_close) * 100
            logger.debug(f"{ticker} - Computed price change: {todays_change_perc:.2f}% (${prev_close} → ${current_price})")
        
        # Get volume from most recent seconds data
        if seconds_results:
            latest_second = seconds_results[0]
            volume_val = latest_second.get('v')
            if volume_val is not None and volume_val > 0:
                volume = int(volume_val)
        
        # STRICT CHECK: Skip if any critical data is missing or zero
        if (current_price is None or current_price == 0 or 
            prev_close is None or prev_close == 0 or
            volume is None or volume == 0):
            logger.debug(f"Skipping {ticker} - missing or zero critical data "
                       f"(current: {current_price}, prev_close: {prev_close}, volume: {volume})")
            return None
        
        if todays_change_perc is None:
            logger.error(f"Unexpected: Failed to calculate percentage change for {ticker}")
            return None
        
        snapshot = {
            'ticker': ticker,
            'current_price': current_price,
            'prev_close': prev_close,
            'todays_change_perc': round(todays_change_perc, 2),
            'volume': volume or 0,
            'volume_ratio': calculate_volume_ratio(volume, None)
        }
        
        # Log all ticker snapshots at debug level only
        logger.debug(f"{ticker} - Final snapshot: {snapshot['todays_change_perc']:+.2f}% change, volume: {volume:,}")
        return snapshot
        
    except (ValueError, KeyError, TypeError) as e:
        logger.warning(f"Error parsing ticker data for {ticker_data.get('ticker', 'unknown')}: {e}")
        return None
