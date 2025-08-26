class StockAlertError(Exception):
    """Base exception for stock alert application"""
    pass

class CSVParsingError(StockAlertError):
    """Raised when CSV parsing fails"""
    pass

class PriceDataError(StockAlertError):
    """Raised when price data retrieval fails"""
    pass

class AlertStateError(StockAlertError):
    """Raised when alert state operations fail"""
    pass

class NotificationError(StockAlertError):
    """Raised when notification sending fails"""
    pass