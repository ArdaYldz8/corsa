"""
Exchange connection module using ccxt
Supports Binance and Binance TR
"""
import ccxt
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import logging

logger = logging.getLogger('TradingBot')


class Exchange:
    """Wrapper for exchange operations"""
    
    def __init__(self, config: dict):
        self.config = config
        exchange_config = config.get('exchange', {})
        
        self.api_key = exchange_config.get('api_key', '')
        self.api_secret = exchange_config.get('api_secret', '')
        self.use_binance_tr = exchange_config.get('use_binance_tr', True)
        
        self.exchange = self._create_exchange()
        self._markets_loaded = False
    
    def _create_exchange(self) -> ccxt.Exchange:
        """Create exchange instance"""
        # Binance TR uses the same API as Binance but different base URL
        exchange_class = ccxt.binance
        
        options = {
            'apiKey': self.api_key if self.api_key != "YOUR_BINANCE_API_KEY" else None,
            'secret': self.api_secret if self.api_secret != "YOUR_BINANCE_API_SECRET" else None,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',
            }
        }
        
        # Remove None values
        options = {k: v for k, v in options.items() if v is not None}
        
        exchange = exchange_class(options)
        
        # Use Binance TR endpoint if configured
        if self.use_binance_tr:
            # Binance TR uses same API, just different trading pairs
            # TRY pairs are available on regular Binance for Turkish users
            pass
        
        return exchange
    
    def load_markets(self) -> None:
        """Load available markets"""
        if not self._markets_loaded:
            try:
                self.exchange.load_markets()
                self._markets_loaded = True
                logger.info("Markets loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load markets: {e}")
                raise
    
    def get_ticker(self, symbol: str) -> dict:
        """Get current ticker for symbol"""
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return {
                'symbol': symbol,
                'last': ticker['last'],
                'bid': ticker['bid'],
                'ask': ticker['ask'],
                'volume': ticker['baseVolume'],
                'change_24h': ticker.get('percentage', 0),
                'timestamp': ticker['timestamp']
            }
        except Exception as e:
            logger.error(f"Failed to fetch ticker for {symbol}: {e}")
            raise
    
    def get_ohlcv(self, symbol: str, timeframe: str = '1h', 
                  limit: int = 100) -> pd.DataFrame:
        """Get OHLCV candlestick data"""
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            return df
        except Exception as e:
            logger.error(f"Failed to fetch OHLCV for {symbol}: {e}")
            raise
    
    def get_balance(self, currency: str = 'TRY') -> float:
        """Get balance for a currency"""
        try:
            if not self.api_key or self.api_key == "YOUR_BINANCE_API_KEY":
                logger.warning("No API key configured, returning 0 balance")
                return 0.0
            
            balance = self.exchange.fetch_balance()
            return balance.get(currency, {}).get('free', 0.0)
        except Exception as e:
            logger.error(f"Failed to fetch balance: {e}")
            return 0.0
    
    def create_market_order(self, symbol: str, side: str, amount: float) -> dict:
        """Create a market order"""
        try:
            if side.lower() == 'buy':
                order = self.exchange.create_market_buy_order(symbol, amount)
            else:
                order = self.exchange.create_market_sell_order(symbol, amount)
            
            logger.info(f"Order created: {side} {amount} {symbol}")
            return order
        except Exception as e:
            logger.error(f"Failed to create order: {e}")
            raise
    
    def create_limit_order(self, symbol: str, side: str, 
                          amount: float, price: float) -> dict:
        """Create a limit order"""
        try:
            if side.lower() == 'buy':
                order = self.exchange.create_limit_buy_order(symbol, amount, price)
            else:
                order = self.exchange.create_limit_sell_order(symbol, amount, price)
            
            logger.info(f"Limit order created: {side} {amount} {symbol} @ {price}")
            return order
        except Exception as e:
            logger.error(f"Failed to create limit order: {e}")
            raise
    
    def get_available_symbols(self, quote: str = 'TRY') -> List[str]:
        """Get symbols available for trading with given quote currency"""
        self.load_markets()
        symbols = []
        for symbol in self.exchange.symbols:
            if symbol.endswith(f'/{quote}'):
                symbols.append(symbol)
        return sorted(symbols)
    
    def test_connection(self) -> bool:
        """Test exchange connection"""
        try:
            self.exchange.fetch_time()
            logger.info("Exchange connection successful")
            return True
        except Exception as e:
            logger.error(f"Exchange connection failed: {e}")
            return False
