import json
import logging
from typing import List, Dict, Set
from .exceptions import CSVParsingError

logger = logging.getLogger(__name__)

class PositionSummary:
    def __init__(self, underlying: str):
        self.underlying = underlying.upper().strip()
        self.calls = 0
        self.puts = 0
        self.total_positions = 0
        self.positions = []  # Store detailed position objects
    
    def add_position(self, put_call: str, qty: float, side: str, position_details: 'OptionsPosition' = None):
        """Add a position to the summary"""
        self.total_positions += 1
        
        # Store detailed position if provided
        if position_details:
            self.positions.append(position_details)
        
        # Simply count calls and puts
        if put_call.upper().strip() == 'CALL':
            self.calls += 1
        elif put_call.upper().strip() == 'PUT':
            self.puts += 1
    
    def get_position_description(self) -> str:
        """Generate a concise description of positions"""
        parts = []
        
        if self.calls > 0:
            parts.append(f"{self.calls} call{'s' if self.calls != 1 else ''}")
        if self.puts > 0:
            parts.append(f"{self.puts} put{'s' if self.puts != 1 else ''}")
        
        if len(parts) == 0:
            return "No positions"
        elif len(parts) == 1:
            return parts[0]
        else:
            return f"{parts[0]} and {parts[1]}"
    
    def has_calls(self) -> bool:
        """Check if this underlying has any call positions"""
        return self.calls > 0
    
    def has_puts(self) -> bool:
        """Check if this underlying has any put positions"""
        return self.puts > 0
    
    def get_alert_directions(self) -> List[str]:
        """Get list of alert directions needed for this position: 'up', 'down', or both"""
        directions = []
        
        if self.has_calls():
            directions.append('up')  # Calls benefit from upward moves
        
        if self.has_puts():
            directions.append('down')  # Puts benefit from downward moves
        
        return directions
    
    def get_detailed_position_description(self, current_price: float = None, prev_close: float = None) -> str:
        """Generate a detailed description of positions with strikes, expirations, and quantities"""
        if not self.positions:
            return "No position details available"
        
        # Group positions by similar characteristics for cleaner display
        position_lines = []
        
        for position in self.positions:
            # Format expiration date (from "2025-11-21" to "21 Nov 25")
            try:
                from datetime import datetime
                exp_date = datetime.strptime(position.exp, "%Y-%m-%d")
                formatted_exp = exp_date.strftime("%d %b %y")
            except:
                formatted_exp = position.exp
            
            # Format quantity with sign
            qty_str = f"{position.qty:+.0f}" if position.qty != int(position.qty) else f"{int(position.qty):+d}"
            
            # Format strike price
            strike_str = f"{position.strike:.0f}" if position.strike == int(position.strike) else f"{position.strike:.2f}"
            
            # Calculate OTM percentages if prices are available
            otm_info = ""
            if current_price and prev_close:
                # Calculate OTM % (positive = OTM, negative = ITM)
                if position.put_call.upper() == "CALL":
                    prev_otm = ((position.strike - prev_close) / prev_close) * 100
                    curr_otm = ((position.strike - current_price) / current_price) * 100
                else:  # PUT
                    prev_otm = ((prev_close - position.strike) / prev_close) * 100
                    curr_otm = ((current_price - position.strike) / current_price) * 100
                
                otm_info = f" || OTM: Previously {prev_otm:+.2f}%, Now {curr_otm:+.2f}%"
            
            # Format trade price
            trade_price_str = f" || Trade: ${position.avg_price:.2f}"
            
            # Create position description
            option_type = position.put_call[0]  # "P" or "C"
            position_line = f"• {formatted_exp} {strike_str}{option_type} || Qty: {qty_str}{otm_info}{trade_price_str}"
            position_lines.append(position_line)
        
        if len(position_lines) == 1:
            return f"ONE position at risk:\n{position_lines[0]}"
        else:
            positions_text = "\n".join(position_lines)
            return f"{len(position_lines)} positions at risk:\n{positions_text}"
    
    def __repr__(self):
        return f"PositionSummary(underlying='{self.underlying}', {self.get_position_description()})"

class OptionsPosition:
    def __init__(self, underlying: str, option_symbol: str, put_call: str, strike: float, 
                 exp: str, dte: int, qty: float, side: str, avg_price: float, 
                 market_value: float, short_open_pl: float):
        self.underlying = underlying.upper().strip()
        self.option_symbol = option_symbol.strip()
        self.put_call = put_call.upper().strip()
        self.strike = strike
        self.exp = exp
        self.dte = dte
        self.qty = qty
        self.side = side.strip()
        self.avg_price = avg_price
        self.market_value = market_value
        self.short_open_pl = short_open_pl
    
    def __repr__(self):
        return f"OptionsPosition(underlying='{self.underlying}', option_symbol='{self.option_symbol}', side='{self.side}')"

class JSONProcessor:
    def __init__(self):
        pass
    
    def parse_positions_json(self, json_content: str) -> List[PositionSummary]:
        """Parse JSON content and return list of PositionSummary objects"""
        try:
            data = json.loads(json_content)
            
            if not isinstance(data, list):
                raise CSVParsingError("JSON must contain a list of positions")
            
            if not data:
                raise CSVParsingError("JSON file contains no positions")
            
            # Group positions by underlying
            position_summaries = {}
            row_count = 0
            
            for item in data:
                row_count += 1
                
                try:
                    if not isinstance(item, dict):
                        logger.warning(f"Item {row_count} is not a dictionary, skipping")
                        continue
                    
                    # Extract required fields
                    underlying = item.get('Underlying')
                    if not underlying or not underlying.strip():
                        logger.warning(f"Missing or empty 'Underlying' field in item {row_count}, skipping")
                        continue
                    
                    underlying = underlying.upper().strip()
                    
                    # Create position summary if not exists
                    if underlying not in position_summaries:
                        position_summaries[underlying] = PositionSummary(underlying)
                    
                    # Extract position details
                    put_call = item.get('Put/Call', '').upper().strip()
                    side = item.get('Side', '').strip()
                    
                    try:
                        qty = float(item.get('Qty', 0))
                    except (ValueError, TypeError):
                        qty = 0
                    
                    # Add position to summary
                    if put_call in ['PUT', 'CALL']:
                        # Extract additional fields for detailed position
                        try:
                            option_symbol = item.get('Option Symbol', '')
                            strike = float(item.get('Strike', 0))
                            exp = item.get('Exp', '')
                            dte = int(item.get('DTE', 0))
                            avg_price = float(item.get('Avg Price', 0))
                            market_value = float(item.get('Market Value', 0))
                            short_open_pl = float(item.get('Short Open PL', 0))
                            
                            # Create detailed position object
                            position_details = OptionsPosition(
                                underlying=underlying,
                                option_symbol=option_symbol,
                                put_call=put_call,
                                strike=strike,
                                exp=exp,
                                dte=dte,
                                qty=qty,
                                side=side,
                                avg_price=avg_price,
                                market_value=market_value,
                                short_open_pl=short_open_pl
                            )
                            
                            position_summaries[underlying].add_position(put_call, qty, side, position_details)
                        except (ValueError, TypeError) as e:
                            logger.warning(f"Error parsing position details for {underlying} item {row_count}: {e}")
                            # Fall back to basic position tracking
                            position_summaries[underlying].add_position(put_call, qty, side)
                    else:
                        logger.debug(f"Unknown Put/Call type '{put_call}' for {underlying}, skipping")
                    
                except KeyError as e:
                    logger.warning(f"Missing field {e} in item {row_count}, skipping")
                    continue
                except Exception as e:
                    logger.warning(f"Error processing item {row_count}: {e}, skipping")
                    continue
            
            if not position_summaries:
                raise CSVParsingError("No valid positions found in JSON")
            
            summaries_list = list(position_summaries.values())
            logger.info(f"Successfully parsed {len(summaries_list)} unique underlying positions from JSON ({row_count} total items)")
            
            # Log position details for debugging
            for summary in summaries_list:
                logger.debug(f"{summary.underlying}: {summary.get_position_description()}")
            
            return summaries_list
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON format: {e}")
            raise CSVParsingError(f"Invalid JSON format: {e}")
        except CSVParsingError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error parsing JSON: {e}")
            raise CSVParsingError(f"Failed to parse JSON: {e}")
    
    def get_position_summary(self, json_content: str) -> Dict:
        """Get summary statistics about the positions JSON"""
        try:
            data = json.loads(json_content)
            
            if not isinstance(data, list):
                return {"error": "JSON must contain a list"}
            
            total_items = len(data)
            unique_underlyings = set()
            sides = {}
            put_call_count = {}
            
            for item in data:
                if isinstance(item, dict):
                    underlying = item.get('Underlying')
                    if underlying:
                        unique_underlyings.add(underlying.upper().strip())
                    
                    side = item.get('Side', '')
                    if side:
                        sides[side] = sides.get(side, 0) + 1
                    
                    put_call = item.get('Put/Call', '')
                    if put_call:
                        put_call_count[put_call] = put_call_count.get(put_call, 0) + 1
            
            return {
                "total_items": total_items,
                "unique_underlyings": len(unique_underlyings),
                "underlyings": sorted(list(unique_underlyings)),
                "sides": sides,
                "put_call_distribution": put_call_count
            }
            
        except json.JSONDecodeError as e:
            return {"error": f"Invalid JSON: {e}"}
        except Exception as e:
            return {"error": f"Processing error: {e}"}