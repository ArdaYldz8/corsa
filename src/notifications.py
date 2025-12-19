"""
Telegram Notifications Module
Sends trade alerts and daily reports
"""
import asyncio
from datetime import datetime
from typing import Optional
import logging
import requests

logger = logging.getLogger('TradingBot')


class TelegramNotifier:
    """Send notifications via Telegram"""
    
    def __init__(self, config: dict):
        tg_config = config.get('telegram', {})
        
        self.enabled = tg_config.get('enabled', False)
        self.bot_token = tg_config.get('bot_token', '')
        self.chat_id = tg_config.get('chat_id', '')
        
        if self.enabled and (not self.bot_token or self.bot_token == "YOUR_TELEGRAM_BOT_TOKEN"):
            logger.warning("Telegram enabled but token not configured, disabling")
            self.enabled = False
        
        if self.enabled:
            logger.info("Telegram notifications enabled")
    
    def _send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send a message via Telegram API"""
        if not self.enabled:
            logger.debug(f"Telegram disabled, would send: {text[:50]}...")
            return False
        
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": parse_mode
            }
            
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                logger.debug("Telegram message sent successfully")
                return True
            else:
                logger.error(f"Telegram API error: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False
    
    def send_trade_alert(self, trade: dict) -> bool:
        """Send trade alert"""
        trade_type = trade.get('type', 'UNKNOWN')
        symbol = trade.get('symbol', 'N/A')
        price = trade.get('price', 0)
        quantity = trade.get('quantity', 0)
        amount = trade.get('amount', 0)
        
        emoji = "🟢" if trade_type == "BUY" else "🔴"
        
        message = (
            f"{emoji} <b>{trade_type} Signal</b>\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"📊 Pair: {symbol}\n"
            f"💰 Price: ₺{price:,.2f}\n"
            f"📦 Quantity: {quantity:.8f}\n"
            f"💵 Amount: ₺{amount:,.2f}\n"
            f"⏰ Time: {datetime.now().strftime('%H:%M:%S')}"
        )
        
        if trade_type == "SELL" and 'pnl' in trade:
            pnl = trade['pnl']
            pnl_pct = trade.get('pnl_pct', 0)
            pnl_emoji = "📈" if pnl >= 0 else "📉"
            message += f"\n{pnl_emoji} PnL: ₺{pnl:+,.2f} ({pnl_pct:+.2f}%)"
        
        return self._send_message(message)
    
    def send_daily_report(self, summary: dict) -> bool:
        """Send daily performance report"""
        total_pnl = summary.get('total_pnl', 0)
        total_pnl_pct = summary.get('total_pnl_pct', 0)
        pnl_emoji = "📈" if total_pnl >= 0 else "📉"
        
        message = (
            f"📊 <b>Daily Report</b>\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"💰 Initial: ₺{summary.get('initial_balance', 0):,.2f}\n"
            f"💵 Current: ₺{summary.get('total_value', 0):,.2f}\n"
            f"{pnl_emoji} PnL: ₺{total_pnl:+,.2f} ({total_pnl_pct:+.2f}%)\n"
            f"📝 Trades: {summary.get('trade_count', 0)}\n"
            f"✅ Wins: {summary.get('winning_trades', 0)}\n"
            f"❌ Losses: {summary.get('losing_trades', 0)}\n"
            f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        
        # Add positions if any
        positions = summary.get('positions', {})
        if positions:
            message += "\n\n📦 <b>Open Positions:</b>"
            for symbol, pos in positions.items():
                message += f"\n• {symbol}: {pos['quantity']:.8f}"
        
        return self._send_message(message)
    
    def send_analysis(self, analysis_text: str) -> bool:
        """Send market analysis"""
        return self._send_message(f"<pre>{analysis_text}</pre>")
    
    def send_error(self, error: str) -> bool:
        """Send error notification"""
        message = f"⚠️ <b>Bot Error</b>\n━━━━━━━━━━━━━━━━━\n{error}"
        return self._send_message(message)
    
    def send_startup(self, config: dict) -> bool:
        """Send startup notification"""
        trading_config = config.get('trading', {})
        paper_mode = trading_config.get('paper_mode', True)
        symbol = trading_config.get('symbol', 'N/A')
        
        mode = "📝 PAPER" if paper_mode else "💰 LIVE"
        
        message = (
            f"🤖 <b>Trading Bot Started</b>\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"📊 Symbol: {symbol}\n"
            f"🎮 Mode: {mode}\n"
            f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        return self._send_message(message)
    
    def test_connection(self) -> bool:
        """Test Telegram connection"""
        if not self.enabled:
            return False
        
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getMe"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('ok'):
                    bot_name = data.get('result', {}).get('username', 'Unknown')
                    logger.info(f"Telegram connected: @{bot_name}")
                    return True
            
            logger.error(f"Telegram test failed: {response.text}")
            return False
            
        except Exception as e:
            logger.error(f"Telegram test error: {e}")
            return False
