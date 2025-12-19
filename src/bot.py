"""
Main Trading Bot
Orchestrates strategy, exchange, and notifications
"""
import time
import schedule
from datetime import datetime
from typing import Optional
import logging
import argparse

from .utils import load_config, setup_logging, TradingState
from .exchange import Exchange
from .strategy import RSIEMAStrategy, Signal
from .notifications import TelegramNotifier
from .telegram_controller import TelegramController
from .database import TradeDatabase


class TradingBot:
    """Main trading bot class"""
    
    def __init__(self, config: dict):
        self.config = config
        self.logger = setup_logging(config)
        
        # Trading configuration
        trading_config = config.get('trading', {})
        self.symbol = trading_config.get('symbol', 'BTC/TRY')
        self.trade_amount = trading_config.get('trade_amount', 100)
        self.timeframe = trading_config.get('timeframe', '1h')
        self.paper_mode = trading_config.get('paper_mode', True)
        self.max_position = trading_config.get('max_position', 500)
        self.stop_loss_pct = trading_config.get('stop_loss_pct', 5.0)
        self.take_profit_pct = trading_config.get('take_profit_pct', 10.0)
        
        # Scheduler config
        scheduler_config = config.get('scheduler', {})
        self.check_interval = scheduler_config.get('check_interval', 15)
        self.daily_report_time = scheduler_config.get('daily_report_time', '20:00')
        
        # Initialize components
        self.exchange = Exchange(config)
        self.strategy = RSIEMAStrategy(config)
        self.notifier = TelegramNotifier(config)
        self.telegram_controller = TelegramController(config, self)
        self.database = TradeDatabase()
        
        # Trading state (paper trading)
        initial_balance = trading_config.get('trade_amount', 1000)
        self.state = TradingState(initial_balance=initial_balance)
        self.state.paper_mode = self.paper_mode
        
        self.running = False
        self.last_check = None
        
        self.logger.info(f"Bot initialized - Symbol: {self.symbol}, Paper Mode: {self.paper_mode}")
    
    def start(self):
        """Start the trading bot"""
        self.running = True
        
        # Test connections
        if not self._test_connections():
            self.logger.error("Connection test failed, exiting")
            return
        
        # Send startup notification
        self.notifier.send_startup(self.config)
        
        # Start Telegram controller in background
        self.telegram_controller.run_in_thread()
        
        # Schedule regular checks
        schedule.every(self.check_interval).minutes.do(self.check_market)
        
        # Schedule daily report
        schedule.every().day.at(self.daily_report_time).do(self.send_daily_report)
        
        self.logger.info(f"Bot started - Checking every {self.check_interval} minutes")
        print(f"\n{'='*50}")
        print(f"🤖 Trading Bot Started")
        print(f"{'='*50}")
        print(f"📊 Symbol: {self.symbol}")
        print(f"📝 Mode: {'PAPER' if self.paper_mode else 'LIVE'}")
        print(f"⏰ Check Interval: {self.check_interval} minutes")
        print(f"💰 Trade Amount: ₺{self.trade_amount:,.0f}")
        print(f"📊 Timeframe: {self.timeframe}")
        print(f"{'='*50}\n")
        
        # Run initial check
        self.check_market()
        
        # Main loop
        try:
            while self.running:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Shutdown requested")
            self.stop()
    
    def stop(self):
        """Stop the trading bot"""
        self.running = False
        self.logger.info("Bot stopped")
        print("\n🛑 Bot stopped")
    
    def _test_connections(self) -> bool:
        """Test all connections"""
        self.logger.info("Testing connections...")
        
        # Test exchange
        if not self.exchange.test_connection():
            self.logger.error("Exchange connection failed")
            return False
        
        # Test telegram (optional)
        if self.notifier.enabled:
            self.notifier.test_connection()
        
        return True
    
    def check_market(self):
        """Check market and execute strategy"""
        try:
            self.last_check = datetime.now()
            self.logger.info(f"Checking market at {self.last_check.strftime('%H:%M:%S')}")
            
            # Get market data
            df = self.exchange.get_ohlcv(self.symbol, self.timeframe, limit=150)
            ticker = self.exchange.get_ticker(self.symbol)
            current_price = ticker['last']
            
            # Check if we have a position and get entry price
            symbol_base = self.symbol.split('/')[0]
            has_position = symbol_base in self.state.positions
            entry_price = None
            if has_position:
                entry_price = self.state.positions[symbol_base].get('entry_price')
            
            # Analyze market with entry price for trailing stop
            signal, analysis = self.strategy.analyze(df, has_position, entry_price)
            
            # Print status
            macd_text = "📈" if analysis.get('macd_bullish', False) else "📉"
            status_msg = (
                f"⏰ {self.last_check.strftime('%H:%M:%S')} - {self.symbol}\n"
                f"💰 Price: ₺{current_price:,.0f}\n"
                f"📊 RSI: {analysis.get('rsi', 0):.1f}\n"
                f"📈 EMA: ₺{analysis.get('ema', 0):,.0f}\n"
                f"{macd_text} MACD: {'Bullish' if analysis.get('macd_bullish') else 'Bearish'}\n"
                f"🎯 Signal: {signal.value}\n"
                f"💡 {analysis.get('reason', 'N/A')}"
            )
            print(f"\n{status_msg}")
            
            # Send to Telegram
            self.notifier.send_analysis(status_msg)
            
            # Execute trades
            if signal == Signal.BUY:
                self._execute_buy(current_price, analysis)
            elif signal == Signal.SELL:
                self._execute_sell(current_price, analysis)
            
            # Check stop loss / take profit
            self._check_stop_loss_take_profit(current_price)
            
        except Exception as e:
            self.logger.error(f"Market check error: {e}")
            self.notifier.send_error(f"Market check failed: {str(e)}")
    
    def _execute_buy(self, price: float, analysis: dict):
        """Execute a buy order"""
        symbol_base = self.symbol.split('/')[0]
        
        # Check max position
        current_position_value = 0
        if symbol_base in self.state.positions:
            pos = self.state.positions[symbol_base]
            current_position_value = pos['quantity'] * price
        
        if current_position_value + self.trade_amount > self.max_position:
            self.logger.info(f"Max position reached, skipping buy")
            return
        
        if self.paper_mode:
            # Paper trading
            result = self.state.buy(symbol_base, price, self.trade_amount)
            if result['success']:
                trade = result['trade']
                trade['symbol'] = self.symbol
                trade['paper_mode'] = True
                trade['reason'] = analysis.get('reason', '')
                
                # Record to database
                self.database.record_trade(trade)
                
                self.logger.info(f"PAPER BUY: {trade['quantity']:.8f} @ ₺{price:,.2f}")
                print(f"\n🟢 PAPER BUY: {trade['quantity']:.8f} {symbol_base} @ ₺{price:,.2f}")
                self.notifier.send_trade_alert(trade)
            else:
                self.logger.warning(f"Buy failed: {result.get('error')}")
        else:
            # Real trading
            try:
                quantity = self.trade_amount / price
                order = self.exchange.create_market_order(self.symbol, 'buy', quantity)
                self.logger.info(f"REAL BUY: {order}")
                
                trade = {
                    'type': 'BUY',
                    'symbol': self.symbol,
                    'price': price,
                    'quantity': quantity,
                    'amount': self.trade_amount
                }
                self.notifier.send_trade_alert(trade)
                
            except Exception as e:
                self.logger.error(f"Buy order failed: {e}")
                self.notifier.send_error(f"Buy failed: {str(e)}")
    
    def _execute_sell(self, price: float, analysis: dict):
        """Execute a sell order"""
        symbol_base = self.symbol.split('/')[0]
        
        if symbol_base not in self.state.positions:
            self.logger.debug("No position to sell")
            return
        
        if self.paper_mode:
            # Paper trading
            result = self.state.sell(symbol_base, price)
            if result['success']:
                trade = result['trade']
                trade['symbol'] = self.symbol
                trade['paper_mode'] = True
                trade['reason'] = analysis.get('reason', '')
                
                # Record to database
                self.database.record_trade(trade)
                
                pnl_emoji = "📈" if trade['pnl'] >= 0 else "📉"
                self.logger.info(f"PAPER SELL: {trade['quantity']:.8f} @ ₺{price:,.2f} | PnL: ₺{trade['pnl']:+,.2f}")
                print(f"\n🔴 PAPER SELL: {trade['quantity']:.8f} {symbol_base} @ ₺{price:,.2f}")
                print(f"{pnl_emoji} PnL: ₺{trade['pnl']:+,.2f} ({trade['pnl_pct']:+.2f}%)")
                self.notifier.send_trade_alert(trade)
            else:
                self.logger.warning(f"Sell failed: {result.get('error')}")
        else:
            # Real trading
            try:
                position = self.state.positions.get(symbol_base, {})
                quantity = position.get('quantity', 0)
                
                if quantity > 0:
                    order = self.exchange.create_market_order(self.symbol, 'sell', quantity)
                    self.logger.info(f"REAL SELL: {order}")
                    
                    trade = {
                        'type': 'SELL',
                        'symbol': self.symbol,
                        'price': price,
                        'quantity': quantity,
                        'amount': quantity * price
                    }
                    self.notifier.send_trade_alert(trade)
                    
            except Exception as e:
                self.logger.error(f"Sell order failed: {e}")
                self.notifier.send_error(f"Sell failed: {str(e)}")
    
    def _check_stop_loss_take_profit(self, current_price: float):
        """Check and execute stop loss / take profit"""
        symbol_base = self.symbol.split('/')[0]
        
        if symbol_base not in self.state.positions:
            return
        
        position = self.state.positions[symbol_base]
        entry_price = position['entry_price']
        pnl_pct = ((current_price - entry_price) / entry_price) * 100
        
        # Stop loss
        if pnl_pct <= -self.stop_loss_pct:
            self.logger.warning(f"Stop loss triggered at {pnl_pct:.2f}%")
            print(f"\n⛔ STOP LOSS triggered at {pnl_pct:.2f}%")
            self._execute_sell(current_price, {'reason': 'Stop loss'})
        
        # Take profit
        elif pnl_pct >= self.take_profit_pct:
            self.logger.info(f"Take profit triggered at {pnl_pct:.2f}%")
            print(f"\n🎯 TAKE PROFIT triggered at {pnl_pct:.2f}%")
            self._execute_sell(current_price, {'reason': 'Take profit'})
    
    def send_daily_report(self):
        """Send daily performance report"""
        try:
            # Get current prices
            ticker = self.exchange.get_ticker(self.symbol)
            current_prices = {self.symbol.split('/')[0]: ticker['last']}
            
            # Get summary
            summary = self.state.get_summary(current_prices)
            
            # Log
            self.logger.info(f"Daily Report: PnL ₺{summary['total_pnl']:+,.2f} ({summary['total_pnl_pct']:+.2f}%)")
            
            # Print
            print(f"\n{'='*50}")
            print(f"📊 Daily Report - {datetime.now().strftime('%Y-%m-%d')}")
            print(f"{'='*50}")
            print(f"💰 Initial: ₺{summary['initial_balance']:,.2f}")
            print(f"💵 Current: ₺{summary['total_value']:,.2f}")
            print(f"📈 PnL: ₺{summary['total_pnl']:+,.2f} ({summary['total_pnl_pct']:+.2f}%)")
            print(f"📝 Trades: {summary['trade_count']}")
            print(f"{'='*50}\n")
            
            # Send telegram
            self.notifier.send_daily_report(summary)
            
        except Exception as e:
            self.logger.error(f"Daily report error: {e}")
    
    def get_status(self) -> dict:
        """Get current bot status"""
        try:
            ticker = self.exchange.get_ticker(self.symbol)
            current_prices = {self.symbol.split('/')[0]: ticker['last']}
        except:
            current_prices = {}
        
        return {
            'running': self.running,
            'paper_mode': self.paper_mode,
            'symbol': self.symbol,
            'last_check': self.last_check,
            'summary': self.state.get_summary(current_prices)
        }


def create_bot(config_path: str = None, live: bool = False) -> TradingBot:
    """Factory function to create bot instance"""
    config = load_config(config_path)
    
    if live:
        config['trading']['paper_mode'] = False
    
    return TradingBot(config)
