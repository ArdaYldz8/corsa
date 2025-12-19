"""
Trading Strategy Module
RSI + EMA + MACD based trading strategy with Trailing Stop-Loss
"""
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator, MACD
from ta.volatility import AverageTrueRange
from typing import Optional, Dict, Tuple
from enum import Enum
import logging

logger = logging.getLogger('TradingBot')


class Signal(Enum):
    """Trading signals"""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class RSIEMAStrategy:
    """
    RSI + EMA + MACD Trading Strategy with Trailing Stop-Loss
    
    Buy Signal:
    - RSI < oversold threshold (default 30)
    - Price > EMA (uptrend confirmation)
    - MACD line > Signal line (momentum confirmation)
    
    Sell Signal:
    - RSI > overbought threshold (default 70)
    - OR Price < EMA (downtrend)
    - OR Trailing Stop-Loss triggered
    """
    
    def __init__(self, config: dict):
        strategy_config = config.get('strategy', {})
        
        self.rsi_period = strategy_config.get('rsi_period', 14)
        self.rsi_oversold = strategy_config.get('rsi_oversold', 30)
        self.rsi_overbought = strategy_config.get('rsi_overbought', 70)
        self.ema_period = strategy_config.get('ema_period', 50)
        self.min_bars = strategy_config.get('min_bars', 100)
        
        # MACD settings
        self.macd_fast = strategy_config.get('macd_fast', 12)
        self.macd_slow = strategy_config.get('macd_slow', 26)
        self.macd_signal = strategy_config.get('macd_signal', 9)
        self.use_macd_confirmation = strategy_config.get('use_macd_confirmation', True)
        
        # Trailing Stop-Loss settings
        self.trailing_stop_pct = strategy_config.get('trailing_stop_pct', 3.0)
        self.highest_price_since_buy = None
        
        self.last_signal = Signal.HOLD
        self.last_analysis = None
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate RSI, EMA, and MACD indicators"""
        df = df.copy()
        
        # Calculate RSI using ta library
        rsi_indicator = RSIIndicator(close=df['close'], window=self.rsi_period)
        df['rsi'] = rsi_indicator.rsi()
        
        # Calculate EMA using ta library
        ema_indicator = EMAIndicator(close=df['close'], window=self.ema_period)
        df['ema'] = ema_indicator.ema_indicator()
        
        # Calculate MACD
        macd = MACD(close=df['close'], window_slow=self.macd_slow, 
                    window_fast=self.macd_fast, window_sign=self.macd_signal)
        df['macd'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()
        df['macd_histogram'] = macd.macd_diff()
        
        # Calculate ATR for volatility-based stop loss (future use)
        atr = AverageTrueRange(high=df['high'], low=df['low'], close=df['close'])
        df['atr'] = atr.average_true_range()
        
        # Calculate additional helpful indicators
        df['ema_distance'] = ((df['close'] - df['ema']) / df['ema']) * 100
        
        return df
    
    def analyze(self, df: pd.DataFrame, has_position: bool = False, 
                entry_price: float = None) -> Tuple[Signal, dict]:
        """
        Analyze market data and return trading signal
        
        Args:
            df: OHLCV DataFrame
            has_position: Whether we currently hold a position
            entry_price: Entry price if has_position is True
            
        Returns:
            Tuple of (Signal, analysis_dict)
        """
        if len(df) < self.min_bars:
            logger.warning(f"Not enough data: {len(df)} bars, need {self.min_bars}")
            return Signal.HOLD, {"error": "Insufficient data"}
        
        # Calculate indicators
        df = self.calculate_indicators(df)
        
        # Get latest values
        current = df.iloc[-1]
        previous = df.iloc[-2]
        
        rsi = current['rsi']
        ema = current['ema']
        close = current['close']
        ema_distance = current['ema_distance']
        macd_line = current['macd']
        macd_signal_line = current['macd_signal']
        macd_histogram = current['macd_histogram']
        atr = current['atr']
        
        # MACD conditions
        macd_bullish = macd_line > macd_signal_line
        macd_bearish = macd_line < macd_signal_line
        
        analysis = {
            'price': close,
            'rsi': rsi,
            'ema': ema,
            'ema_distance': ema_distance,
            'macd': macd_line,
            'macd_signal': macd_signal_line,
            'macd_histogram': macd_histogram,
            'macd_bullish': macd_bullish,
            'atr': atr,
            'rsi_oversold': self.rsi_oversold,
            'rsi_overbought': self.rsi_overbought,
            'has_position': has_position
        }
        
        self.last_analysis = analysis
        
        # Check for NaN values
        if pd.isna(rsi) or pd.isna(ema) or pd.isna(macd_line):
            logger.warning("Indicators contain NaN values")
            return Signal.HOLD, analysis
        
        signal = Signal.HOLD
        
        # ===== BUY CONDITIONS =====
        if not has_position:
            rsi_condition = rsi < self.rsi_oversold
            ema_condition = close > ema
            macd_condition = macd_bullish if self.use_macd_confirmation else True
            
            if rsi_condition and ema_condition and macd_condition:
                signal = Signal.BUY
                # Reset trailing stop tracker
                self.highest_price_since_buy = close
                
                macd_text = " + MACD bullish" if self.use_macd_confirmation else ""
                analysis['reason'] = f"RSI oversold ({rsi:.1f}) + Price>EMA{macd_text}"
                logger.info(f"BUY signal: {analysis['reason']}")
        
        # ===== SELL CONDITIONS =====
        if has_position:
            # Update trailing stop tracker
            if self.highest_price_since_buy is None:
                self.highest_price_since_buy = entry_price if entry_price else close
            else:
                self.highest_price_since_buy = max(self.highest_price_since_buy, close)
            
            # Calculate trailing stop level
            trailing_stop_price = self.highest_price_since_buy * (1 - self.trailing_stop_pct / 100)
            analysis['trailing_stop'] = trailing_stop_price
            analysis['highest_since_buy'] = self.highest_price_since_buy
            
            # Check sell conditions
            if rsi > self.rsi_overbought:
                signal = Signal.SELL
                analysis['reason'] = f"RSI overbought ({rsi:.1f} > {self.rsi_overbought})"
                logger.info(f"SELL signal: {analysis['reason']}")
                self.highest_price_since_buy = None
                
            elif close < trailing_stop_price:
                signal = Signal.SELL
                pnl_pct = ((close - (entry_price or self.highest_price_since_buy)) / 
                          (entry_price or self.highest_price_since_buy)) * 100
                analysis['reason'] = f"Trailing Stop hit (₺{trailing_stop_price:,.0f}) | PnL: {pnl_pct:+.1f}%"
                logger.info(f"SELL signal: {analysis['reason']}")
                self.highest_price_since_buy = None
                
            elif close < ema and macd_bearish:
                signal = Signal.SELL
                analysis['reason'] = f"Price below EMA + MACD bearish"
                logger.info(f"SELL signal: {analysis['reason']}")
                self.highest_price_since_buy = None
        
        if signal == Signal.HOLD:
            analysis['reason'] = "No clear signal"
        
        self.last_signal = signal
        return signal, analysis
        
        if signal == Signal.HOLD:
            analysis['reason'] = "No clear signal"
        
        self.last_signal = signal
        return signal, analysis
    
    def get_status_text(self) -> str:
        """Get human-readable status"""
        if self.last_analysis is None:
            return "No analysis yet"
        
        a = self.last_analysis
        return (
            f"📊 Market Analysis\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"💰 Price: ₺{a['price']:,.2f}\n"
            f"📈 RSI: {a['rsi']:.1f} (OS:{a['rsi_oversold']} / OB:{a['rsi_overbought']})\n"
            f"📉 EMA: ₺{a['ema']:,.2f}\n"
            f"📏 EMA Distance: {a['ema_distance']:+.2f}%\n"
            f"🎯 Signal: {self.last_signal.value}\n"
            f"💡 Reason: {a.get('reason', 'N/A')}"
        )


class GridStrategy:
    """
    Simple Grid Trading Strategy (for future use)
    Places buy/sell orders at fixed intervals
    """
    
    def __init__(self, config: dict):
        grid_config = config.get('grid', {})
        self.grid_count = grid_config.get('count', 10)
        self.grid_spacing = grid_config.get('spacing_pct', 1.0)  # 1% between grids
    
    def calculate_grid_levels(self, center_price: float) -> Dict[str, list]:
        """Calculate buy and sell grid levels"""
        buy_levels = []
        sell_levels = []
        
        for i in range(1, self.grid_count // 2 + 1):
            # Buy levels below center
            buy_price = center_price * (1 - (i * self.grid_spacing / 100))
            buy_levels.append(buy_price)
            
            # Sell levels above center
            sell_price = center_price * (1 + (i * self.grid_spacing / 100))
            sell_levels.append(sell_price)
        
        return {
            'center': center_price,
            'buy_levels': sorted(buy_levels, reverse=True),
            'sell_levels': sorted(sell_levels)
        }
