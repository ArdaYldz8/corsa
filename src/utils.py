"""
Utility functions for the trading bot
"""
import os
import yaml
import logging
from datetime import datetime
from pathlib import Path


def load_config(config_path: str = None) -> dict:
    """Load configuration from YAML file and environment variables"""
    if config_path is None:
        # Try config.yaml first, then config.example.yaml
        base_path = Path(__file__).parent.parent / "config"
        if (base_path / "config.yaml").exists():
            config_path = base_path / "config.yaml"
        else:
            config_path = base_path / "config.example.yaml"
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # Override with environment variables (for cloud deployment)
    # Telegram settings
    if os.environ.get('TELEGRAM_BOT_TOKEN'):
        config.setdefault('telegram', {})
        config['telegram']['bot_token'] = os.environ['TELEGRAM_BOT_TOKEN']
        config['telegram']['enabled'] = True
    
    if os.environ.get('TELEGRAM_CHAT_ID'):
        config.setdefault('telegram', {})
        config['telegram']['chat_id'] = os.environ['TELEGRAM_CHAT_ID']
    
    # Exchange settings
    if os.environ.get('BINANCE_API_KEY'):
        config.setdefault('exchange', {})
        config['exchange']['api_key'] = os.environ['BINANCE_API_KEY']
    
    if os.environ.get('BINANCE_API_SECRET'):
        config.setdefault('exchange', {})
        config['exchange']['api_secret'] = os.environ['BINANCE_API_SECRET']
    
    # Trading settings
    if os.environ.get('TRADING_SYMBOL'):
        config.setdefault('trading', {})
        config['trading']['symbol'] = os.environ['TRADING_SYMBOL']
    
    if os.environ.get('PAPER_MODE'):
        config.setdefault('trading', {})
        config['trading']['paper_mode'] = os.environ['PAPER_MODE'].lower() == 'true'
    
    return config


def setup_logging(config: dict) -> logging.Logger:
    """Setup logging configuration"""
    log_config = config.get('logging', {})
    log_level = getattr(logging, log_config.get('level', 'INFO'))
    log_file = log_config.get('file', 'logs/trading.log')
    
    # Create logs directory if needed
    log_dir = Path(log_file).parent
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Configure logging
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger('TradingBot')


def format_currency(amount: float, currency: str = "TRY") -> str:
    """Format amount as currency string"""
    if currency == "TRY":
        return f"₺{amount:,.2f}"
    elif currency == "USD":
        return f"${amount:,.2f}"
    else:
        return f"{amount:,.8f} {currency}"


def format_percentage(value: float) -> str:
    """Format value as percentage"""
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.2f}%"


def timestamp_to_str(timestamp: int) -> str:
    """Convert timestamp to readable string"""
    return datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')


def calculate_pnl(entry_price: float, current_price: float, quantity: float) -> tuple:
    """Calculate profit/loss"""
    pnl = (current_price - entry_price) * quantity
    pnl_pct = ((current_price - entry_price) / entry_price) * 100
    return pnl, pnl_pct


class TradingState:
    """Simple state management for paper trading"""
    
    def __init__(self, initial_balance: float = 1000.0):
        self.balance = initial_balance
        self.initial_balance = initial_balance
        self.positions = {}  # symbol -> {quantity, entry_price, entry_time}
        self.trades = []  # List of completed trades
        self.paper_mode = True
    
    def buy(self, symbol: str, price: float, amount: float) -> dict:
        """Execute a buy order"""
        quantity = amount / price
        
        if amount > self.balance:
            return {"success": False, "error": "Insufficient balance"}
        
        self.balance -= amount
        
        if symbol in self.positions:
            # Average into existing position
            existing = self.positions[symbol]
            total_qty = existing['quantity'] + quantity
            avg_price = ((existing['entry_price'] * existing['quantity']) + 
                        (price * quantity)) / total_qty
            self.positions[symbol] = {
                'quantity': total_qty,
                'entry_price': avg_price,
                'entry_time': existing['entry_time']
            }
        else:
            self.positions[symbol] = {
                'quantity': quantity,
                'entry_price': price,
                'entry_time': datetime.now()
            }
        
        trade = {
            'type': 'BUY',
            'symbol': symbol,
            'price': price,
            'quantity': quantity,
            'amount': amount,
            'time': datetime.now()
        }
        self.trades.append(trade)
        
        return {"success": True, "trade": trade}
    
    def sell(self, symbol: str, price: float, quantity: float = None) -> dict:
        """Execute a sell order"""
        if symbol not in self.positions:
            return {"success": False, "error": "No position to sell"}
        
        position = self.positions[symbol]
        sell_qty = quantity if quantity else position['quantity']
        
        if sell_qty > position['quantity']:
            return {"success": False, "error": "Insufficient quantity"}
        
        amount = sell_qty * price
        self.balance += amount
        
        # Calculate PnL
        pnl, pnl_pct = calculate_pnl(position['entry_price'], price, sell_qty)
        
        # Update or remove position
        if sell_qty >= position['quantity']:
            del self.positions[symbol]
        else:
            position['quantity'] -= sell_qty
        
        trade = {
            'type': 'SELL',
            'symbol': symbol,
            'price': price,
            'quantity': sell_qty,
            'amount': amount,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'time': datetime.now()
        }
        self.trades.append(trade)
        
        return {"success": True, "trade": trade}
    
    def get_total_value(self, current_prices: dict) -> float:
        """Calculate total portfolio value"""
        total = self.balance
        for symbol, position in self.positions.items():
            if symbol in current_prices:
                total += position['quantity'] * current_prices[symbol]
        return total
    
    def get_summary(self, current_prices: dict = None) -> dict:
        """Get portfolio summary"""
        if current_prices is None:
            current_prices = {}
        
        total_value = self.get_total_value(current_prices)
        total_pnl = total_value - self.initial_balance
        total_pnl_pct = (total_pnl / self.initial_balance) * 100
        
        return {
            'initial_balance': self.initial_balance,
            'current_balance': self.balance,
            'total_value': total_value,
            'total_pnl': total_pnl,
            'total_pnl_pct': total_pnl_pct,
            'positions': self.positions,
            'trade_count': len(self.trades),
            'winning_trades': len([t for t in self.trades if t.get('pnl', 0) > 0]),
            'losing_trades': len([t for t in self.trades if t.get('pnl', 0) < 0])
        }
