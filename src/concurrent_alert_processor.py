import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple, Optional
from .config import Config
from .alert_logic.basic_alerts import should_trigger_basic_alert, should_trigger_incremental_alert
from .alert_logic.seconds_alerts import should_trigger_consecutive_seconds_alert
from .alert_logic.minutes_alerts import should_trigger_consecutive_minutes_alert
from .polygon_api.historical_volume import get_historical_volume

logger = logging.getLogger(__name__)

class ConcurrentAlertProcessor:
    """Handles concurrent processing of alert logic and API calls"""
    
    def __init__(self, max_workers: int = 10):
        self.max_workers = max_workers
        
    def process_ticker_alerts_concurrent(self, tickers_data: List[Dict]) -> Dict[str, Dict]:
        """
        Process alert logic for multiple tickers concurrently
        
        Args:
            tickers_data: List of dicts containing ticker, snapshot, and position data
            
        Returns:
            Dict mapping ticker to alert results
        """
        logger.info(f"🚀 Processing alert logic for {len(tickers_data)} tickers with {self.max_workers} workers")
        
        results = {}
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all alert processing tasks
            future_to_ticker = {
                executor.submit(self._process_single_ticker_alerts, ticker_data): ticker_data['ticker']
                for ticker_data in tickers_data
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_ticker):
                ticker = future_to_ticker[future]
                try:
                    alert_result = future.result()
                    if alert_result:
                        results[ticker] = alert_result
                        
                except Exception as e:
                    logger.error(f"Error processing alerts for {ticker}: {e}")
                    results[ticker] = {'error': str(e)}
        
        logger.info(f"✅ Concurrent alert processing completed: {len(results)} results")
        return results
    
    def _process_single_ticker_alerts(self, ticker_data: Dict) -> Optional[Dict]:
        """Process all alert logic for a single ticker"""
        try:
            ticker = ticker_data['ticker']
            snapshot = ticker_data['snapshot']
            position = ticker_data['position']
            
            percent_change = snapshot['todays_change_perc']
            alert_directions = position.get_alert_directions()
            
            logger.debug(f"{ticker}: Starting alert processing ({percent_change:+.2f}%)")
            
            # Check basic alert first (concurrent processor doesn't track last_alerted_percent or timestamp)
            should_alert_basic, basic_reason = should_trigger_basic_alert(percent_change, alert_directions, 0, None)
            
            alert_triggered = should_alert_basic
            alert_reason = basic_reason
            alert_type = "basic" if should_alert_basic else None
            
            # If basic didn't trigger, check seconds and minutes concurrently
            if not should_alert_basic:
                alert_triggered, alert_reason, alert_type = self._check_time_based_alerts_concurrent(
                    ticker, alert_directions
                )
            
            if alert_triggered:
                logger.info(f"{ticker}: Alert triggered - {alert_type}: {alert_reason}")
                
                # Get historical volume concurrently with other processing
                avg_volume = self._get_volume_with_timeout(ticker)
                
                return {
                    'ticker': ticker,
                    'should_alert': True,
                    'alert_type': alert_type,
                    'alert_reason': alert_reason,
                    'percent_change': percent_change,
                    'snapshot': snapshot,
                    'position': position,
                    'avg_volume': avg_volume
                }
            else:
                logger.debug(f"{ticker}: No alert - {alert_reason}")
                return None
                
        except Exception as e:
            logger.error(f"Error in single ticker alert processing: {e}")
            return None
    
    def _check_time_based_alerts_concurrent(self, ticker: str, alert_directions: List[str]) -> Tuple[bool, str, str]:
        """Check seconds and minutes alerts concurrently"""
        
        with ThreadPoolExecutor(max_workers=2) as executor:
            # Submit both checks concurrently
            seconds_future = executor.submit(should_trigger_consecutive_seconds_alert, ticker, alert_directions)
            minutes_future = executor.submit(should_trigger_consecutive_minutes_alert, ticker, alert_directions)
            
            # Get results
            should_alert_seconds, seconds_reason = seconds_future.result()
            should_alert_minutes, minutes_reason = minutes_future.result()
        
        # Prioritize seconds alerts over minutes alerts
        if should_alert_seconds:
            return True, seconds_reason, "consecutive_seconds"
        elif should_alert_minutes:
            return True, minutes_reason, "consecutive_minutes"
        else:
            # Combine reasons for debugging
            combined_reason = f"Seconds: {seconds_reason} | Minutes: {minutes_reason}"
            return False, combined_reason, "none"
    
    def _get_volume_with_timeout(self, ticker: str, timeout: int = 10) -> Optional[float]:
        """Get historical volume with timeout to prevent hanging"""
        
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(get_historical_volume, ticker)
            try:
                return future.result(timeout=timeout)
            except Exception as e:
                logger.warning(f"Volume fetch timeout/error for {ticker}: {e}")
                return None

    def get_historical_volumes_concurrent(self, tickers: List[str]) -> Dict[str, Optional[float]]:
        """Fetch historical volumes for multiple tickers concurrently"""
        logger.info(f"🚀 Fetching historical volumes for {len(tickers)} tickers concurrently")
        
        volumes = {}
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_ticker = {
                executor.submit(get_historical_volume, ticker): ticker
                for ticker in tickers
            }
            
            for future in as_completed(future_to_ticker):
                ticker = future_to_ticker[future]
                try:
                    volume = future.result(timeout=15)  # 15 second timeout per ticker
                    volumes[ticker] = volume
                    
                except Exception as e:
                    logger.warning(f"Volume fetch failed for {ticker}: {e}")
                    volumes[ticker] = None
        
        successful = sum(1 for v in volumes.values() if v is not None)
        logger.info(f"✅ Volume fetch completed: {successful}/{len(tickers)} successful")
        return volumes
