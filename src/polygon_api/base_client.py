import requests
import logging
from typing import Optional
from ..config import Config
from ..exceptions import PriceDataError

logger = logging.getLogger(__name__)

# Constants
API_KEY = Config.POLYGON_API_KEY
BASE_URL = "https://api.polygon.io"
RATE_LIMIT_DELAY = 1.0 / 20  # 20 requests per second = 0.05 seconds between requests

if not API_KEY:
    raise PriceDataError("Polygon API key not configured")

def make_polygon_request(url: str, params: dict, timeout: int = 30) -> Optional[dict]:
    """Make HTTP request to Polygon API with error handling"""
    try:
        # Add API key to params
        params['apikey'] = API_KEY
        
        response = requests.get(url, params=params, timeout=timeout)
        
        if response.status_code == 429:
            logger.error(f"Rate limit exceeded for Polygon API")
            raise PriceDataError("Polygon API rate limit exceeded")
        
        if response.status_code == 403:
            logger.error(f"Polygon API authentication failed")
            raise PriceDataError("Polygon API authentication failed - check API key")
        
        if response.status_code != 200:
            logger.error(f"Polygon API returned status {response.status_code}: {response.text}")
            raise PriceDataError(f"Failed to fetch data: HTTP {response.status_code}")
        
        data = response.json()
        
        if data.get('status') != 'OK':
            logger.error(f"Polygon API error: {data}")
            raise PriceDataError(f"Polygon API error: {data.get('error', 'Unknown error')}")
        
        return data
        
    except requests.exceptions.Timeout:
        logger.error(f"Timeout fetching data from Polygon API")
        raise PriceDataError(f"Timeout fetching data from Polygon API")
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error fetching data: {e}")
        raise PriceDataError(f"Network error fetching data: {e}")
    except PriceDataError:
        raise
    except Exception as e:
        logger.error(f"Unexpected error fetching data: {e}")
        raise PriceDataError(f"Unexpected error fetching data: {e}")