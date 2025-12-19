"""
Trade Database Module
SQLite database for storing trade history
"""
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import logging

logger = logging.getLogger('TradingBot')


class TradeDatabase:
    """SQLite database for trade history"""
    
    def __init__(self, db_path: str = "data/trades.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize database tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Trades table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                price REAL NOT NULL,
                quantity REAL NOT NULL,
                amount REAL NOT NULL,
                pnl REAL DEFAULT 0,
                pnl_pct REAL DEFAULT 0,
                reason TEXT,
                paper_mode INTEGER DEFAULT 1
            )
        ''')
        
        # Daily summaries table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE UNIQUE NOT NULL,
                starting_balance REAL,
                ending_balance REAL,
                total_pnl REAL,
                trade_count INTEGER,
                win_count INTEGER,
                loss_count INTEGER
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info(f"Database initialized at {self.db_path}")
    
    def record_trade(self, trade: dict) -> int:
        """Record a trade to the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO trades (symbol, side, price, quantity, amount, pnl, pnl_pct, reason, paper_mode)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            trade.get('symbol', ''),
            trade.get('type', ''),
            trade.get('price', 0),
            trade.get('quantity', 0),
            trade.get('amount', 0),
            trade.get('pnl', 0),
            trade.get('pnl_pct', 0),
            trade.get('reason', ''),
            1 if trade.get('paper_mode', True) else 0
        ))
        
        trade_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"Trade recorded: ID {trade_id}")
        return trade_id
    
    def get_recent_trades(self, limit: int = 10) -> List[Dict]:
        """Get recent trades"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?
        ''', (limit,))
        
        trades = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return trades
    
    def get_trades_today(self) -> List[Dict]:
        """Get today's trades"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM trades 
            WHERE date(timestamp) = date('now', 'localtime')
            ORDER BY timestamp DESC
        ''')
        
        trades = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return trades
    
    def get_statistics(self) -> Dict:
        """Get trading statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Total trades
        cursor.execute('SELECT COUNT(*) FROM trades')
        total_trades = cursor.fetchone()[0]
        
        # Winning trades
        cursor.execute('SELECT COUNT(*) FROM trades WHERE pnl > 0')
        winning_trades = cursor.fetchone()[0]
        
        # Losing trades
        cursor.execute('SELECT COUNT(*) FROM trades WHERE pnl < 0')
        losing_trades = cursor.fetchone()[0]
        
        # Total PnL
        cursor.execute('SELECT COALESCE(SUM(pnl), 0) FROM trades WHERE side = "SELL"')
        total_pnl = cursor.fetchone()[0]
        
        # Best trade
        cursor.execute('SELECT MAX(pnl) FROM trades')
        best_trade = cursor.fetchone()[0] or 0
        
        # Worst trade
        cursor.execute('SELECT MIN(pnl) FROM trades WHERE pnl < 0')
        worst_trade = cursor.fetchone()[0] or 0
        
        conn.close()
        
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'best_trade': best_trade,
            'worst_trade': worst_trade
        }
    
    def save_daily_summary(self, summary: dict):
        """Save daily summary"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        cursor.execute('''
            INSERT OR REPLACE INTO daily_summary 
            (date, starting_balance, ending_balance, total_pnl, trade_count, win_count, loss_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            today,
            summary.get('initial_balance', 0),
            summary.get('total_value', 0),
            summary.get('total_pnl', 0),
            summary.get('trade_count', 0),
            summary.get('winning_trades', 0),
            summary.get('losing_trades', 0)
        ))
        
        conn.commit()
        conn.close()
