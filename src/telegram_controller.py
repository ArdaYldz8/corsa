"""
Telegram Bot Controller
Allows controlling the trading bot via Telegram commands
"""
import asyncio
import logging
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from typing import Optional, Callable
import threading

logger = logging.getLogger('TradingBot')


class TelegramController:
    """
    Telegram bot for controlling the trading bot
    
    Commands:
    /start - Start message
    /status - Get current status
    /price - Get current price
    /balance - Get balance
    /buy - Manual buy
    /sell - Manual sell
    /stop - Stop the bot
    /help - Show commands
    """
    
    def __init__(self, config: dict, trading_bot=None):
        tg_config = config.get('telegram', {})
        
        self.enabled = tg_config.get('enabled', False)
        self.bot_token = tg_config.get('bot_token', '')
        self.chat_id = tg_config.get('chat_id', '')
        self.authorized_users = set()  # Will store authorized chat IDs
        
        self.trading_bot = trading_bot
        self.application: Optional[Application] = None
        self._running = False
        
        if self.chat_id:
            self.authorized_users.add(str(self.chat_id))
    
    def set_trading_bot(self, bot):
        """Set the trading bot instance"""
        self.trading_bot = bot
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user_id = str(update.effective_chat.id)
        self.authorized_users.add(user_id)
        
        await update.message.reply_text(
            "🤖 *Trading Bot Controller*\n"
            "━━━━━━━━━━━━━━━━━\n\n"
            f"✅ Bağlantı başarılı!\n"
            f"📱 Chat ID: `{user_id}`\n\n"
            "*Komutlar:*\n"
            "/status - Bot durumu\n"
            "/price - Güncel fiyat\n"
            "/balance - Bakiye\n"
            "/trades - Son işlemler\n"
            "/report - Günlük rapor\n"
            "/help - Yardım\n\n"
            "💡 Bot her 15 dakikada piyasayı kontrol eder.",
            parse_mode='Markdown'
        )
        
        logger.info(f"User {user_id} connected to Telegram controller")
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        await update.message.reply_text(
            "📚 *Komut Listesi*\n"
            "━━━━━━━━━━━━━━━━━\n\n"
            "/status - Bot durumu ve pozisyonlar\n"
            "/price - Güncel fiyat ve RSI\n"
            "/balance - Mevcut bakiye\n"
            "/trades - Son 5 işlem\n"
            "/report - Günlük performans\n"
            "/buy - Manuel al emri\n"
            "/sell - Manuel sat emri\n"
            "/stop - Botu durdur\n"
            "/help - Bu mesaj",
            parse_mode='Markdown'
        )
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        if not self.trading_bot:
            await update.message.reply_text("❌ Bot bağlı değil")
            return
        
        status = self.trading_bot.get_status()
        summary = status.get('summary', {})
        
        mode = "📝 PAPER" if status.get('paper_mode', True) else "💰 LIVE"
        running = "✅ Çalışıyor" if status.get('running', False) else "⏸️ Durdu"
        
        msg = (
            f"🤖 *Bot Durumu*\n"
            f"━━━━━━━━━━━━━━━━━\n\n"
            f"📊 Coin: {status.get('symbol', 'N/A')}\n"
            f"🎮 Mod: {mode}\n"
            f"⚡ Durum: {running}\n\n"
            f"💰 *Portföy:*\n"
            f"├ Başlangıç: ₺{summary.get('initial_balance', 0):,.0f}\n"
            f"├ Şu an: ₺{summary.get('total_value', 0):,.0f}\n"
            f"└ PnL: ₺{summary.get('total_pnl', 0):+,.0f} ({summary.get('total_pnl_pct', 0):+.1f}%)\n\n"
            f"📝 İşlem: {summary.get('trade_count', 0)}"
        )
        
        # Add positions
        positions = summary.get('positions', {})
        if positions:
            msg += "\n\n📦 *Açık Pozisyonlar:*"
            for symbol, pos in positions.items():
                msg += f"\n• {symbol}: {pos['quantity']:.6f}"
        
        await update.message.reply_text(msg, parse_mode='Markdown')
    
    async def price_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /price command"""
        if not self.trading_bot:
            await update.message.reply_text("❌ Bot bağlı değil")
            return
        
        try:
            ticker = self.trading_bot.exchange.get_ticker(self.trading_bot.symbol)
            
            # Get latest analysis if available
            analysis = self.trading_bot.strategy.last_analysis or {}
            
            msg = (
                f"📊 *{self.trading_bot.symbol}*\n"
                f"━━━━━━━━━━━━━━━━━\n\n"
                f"💰 Fiyat: ₺{ticker['last']:,.0f}\n"
                f"📈 24h: {ticker.get('change_24h', 0):+.2f}%\n\n"
            )
            
            if analysis:
                msg += (
                    f"📉 RSI: {analysis.get('rsi', 0):.1f}\n"
                    f"📊 EMA: ₺{analysis.get('ema', 0):,.0f}\n"
                    f"🎯 Sinyal: {self.trading_bot.strategy.last_signal.value}"
                )
            
            await update.message.reply_text(msg, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Hata: {str(e)}")
    
    async def balance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /balance command"""
        if not self.trading_bot:
            await update.message.reply_text("❌ Bot bağlı değil")
            return
        
        summary = self.trading_bot.state.get_summary()
        
        msg = (
            f"💰 *Bakiye*\n"
            f"━━━━━━━━━━━━━━━━━\n\n"
            f"🏦 TRY: ₺{summary.get('current_balance', 0):,.0f}\n"
            f"📊 Toplam: ₺{summary.get('total_value', 0):,.0f}\n"
            f"📈 PnL: ₺{summary.get('total_pnl', 0):+,.0f}"
        )
        
        await update.message.reply_text(msg, parse_mode='Markdown')
    
    async def trades_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /trades command"""
        if not self.trading_bot:
            await update.message.reply_text("❌ Bot bağlı değil")
            return
        
        trades = self.trading_bot.state.trades[-5:]  # Last 5 trades
        
        if not trades:
            await update.message.reply_text("📝 Henüz işlem yok")
            return
        
        msg = "📝 *Son İşlemler*\n━━━━━━━━━━━━━━━━━\n"
        
        for trade in reversed(trades):
            emoji = "🟢" if trade['type'] == 'BUY' else "🔴"
            time_str = trade['time'].strftime('%d/%m %H:%M')
            msg += f"\n{emoji} {trade['type']} ₺{trade['amount']:,.0f} @ {time_str}"
            if 'pnl' in trade:
                msg += f" (PnL: ₺{trade['pnl']:+,.0f})"
        
        await update.message.reply_text(msg, parse_mode='Markdown')
    
    async def report_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /report command"""
        if not self.trading_bot:
            await update.message.reply_text("❌ Bot bağlı değil")
            return
        
        try:
            ticker = self.trading_bot.exchange.get_ticker(self.trading_bot.symbol)
            current_prices = {self.trading_bot.symbol.split('/')[0]: ticker['last']}
        except:
            current_prices = {}
        
        summary = self.trading_bot.state.get_summary(current_prices)
        
        win_rate = 0
        if summary['trade_count'] > 0:
            win_rate = (summary['winning_trades'] / summary['trade_count']) * 100
        
        msg = (
            f"📊 *Günlük Rapor*\n"
            f"━━━━━━━━━━━━━━━━━\n\n"
            f"💰 Başlangıç: ₺{summary['initial_balance']:,.0f}\n"
            f"💵 Şu an: ₺{summary['total_value']:,.0f}\n"
            f"📈 PnL: ₺{summary['total_pnl']:+,.0f} ({summary['total_pnl_pct']:+.1f}%)\n\n"
            f"📝 Toplam: {summary['trade_count']} işlem\n"
            f"✅ Kazanan: {summary['winning_trades']}\n"
            f"❌ Kaybeden: {summary['losing_trades']}\n"
            f"🎯 Win Rate: %{win_rate:.0f}"
        )
        
        await update.message.reply_text(msg, parse_mode='Markdown')
    
    async def buy_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /buy command"""
        if not self.trading_bot:
            await update.message.reply_text("❌ Bot bağlı değil")
            return
        
        try:
            ticker = self.trading_bot.exchange.get_ticker(self.trading_bot.symbol)
            price = ticker['last']
            
            # Execute buy
            self.trading_bot._execute_buy(price, {'reason': 'Manual Telegram command'})
            
            await update.message.reply_text(
                f"🟢 *Manuel AL Emri*\n\n"
                f"💰 Fiyat: ₺{price:,.0f}\n"
                f"📦 Miktar: ₺{self.trading_bot.trade_amount}",
                parse_mode='Markdown'
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Hata: {str(e)}")
    
    async def sell_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /sell command"""
        if not self.trading_bot:
            await update.message.reply_text("❌ Bot bağlı değil")
            return
        
        try:
            ticker = self.trading_bot.exchange.get_ticker(self.trading_bot.symbol)
            price = ticker['last']
            
            # Execute sell
            self.trading_bot._execute_sell(price, {'reason': 'Manual Telegram command'})
            
            await update.message.reply_text(
                f"🔴 *Manuel SAT Emri*\n\n"
                f"💰 Fiyat: ₺{price:,.0f}",
                parse_mode='Markdown'
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Hata: {str(e)}")
    
    async def stop_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stop command"""
        if not self.trading_bot:
            await update.message.reply_text("❌ Bot bağlı değil")
            return
        
        self.trading_bot.stop()
        await update.message.reply_text("🛑 Bot durduruldu")
    
    async def unknown_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle unknown commands"""
        await update.message.reply_text(
            "❓ Bilinmeyen komut. /help yazarak komutları görebilirsin."
        )
    
    def run_in_thread(self):
        """Run the telegram bot in a separate thread"""
        if not self.enabled or not self.bot_token or self.bot_token == "YOUR_TELEGRAM_BOT_TOKEN":
            logger.warning("Telegram controller disabled or not configured")
            return
        
        def run():
            asyncio.run(self._run_bot())
        
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        logger.info("Telegram controller started in background thread")
    
    async def _run_bot(self):
        """Run the telegram bot"""
        self.application = Application.builder().token(self.bot_token).build()
        
        # Add handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("price", self.price_command))
        self.application.add_handler(CommandHandler("balance", self.balance_command))
        self.application.add_handler(CommandHandler("trades", self.trades_command))
        self.application.add_handler(CommandHandler("report", self.report_command))
        self.application.add_handler(CommandHandler("buy", self.buy_command))
        self.application.add_handler(CommandHandler("sell", self.sell_command))
        self.application.add_handler(CommandHandler("stop", self.stop_command))
        
        # Handle unknown commands
        self.application.add_handler(MessageHandler(filters.COMMAND, self.unknown_command))
        
        self._running = True
        logger.info("Telegram controller initialized")
        
        # Start polling
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling(drop_pending_updates=True)
        
        # Keep running
        while self._running:
            await asyncio.sleep(1)
        
        await self.application.stop()
