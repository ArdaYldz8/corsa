"""
Health Check Server
Provides HTTP endpoint to keep the service awake on Render/Railway
"""
from flask import Flask, jsonify
from threading import Thread
import logging

logger = logging.getLogger('TradingBot')

app = Flask(__name__)

# Bot reference - will be set by main bot
bot_instance = None


def set_bot_instance(bot):
    """Set the bot instance for status reporting"""
    global bot_instance
    bot_instance = bot


@app.route('/')
def home():
    """Home page"""
    return "🤖 Trading Bot is running!"


@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "trading-bot"
    })


@app.route('/status')
def status():
    """Bot status endpoint"""
    if bot_instance:
        try:
            status = bot_instance.get_status()
            return jsonify({
                "running": status.get('running', False),
                "paper_mode": status.get('paper_mode', True),
                "symbol": status.get('symbol', 'N/A'),
                "summary": status.get('summary', {})
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    return jsonify({"status": "bot not initialized"})


def run_health_server(port: int = 8080):
    """Run the health check server in a background thread"""
    def run():
        # Disable Flask's default logging
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)
        
        logger.info(f"Health server starting on port {port}")
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
    
    thread = Thread(target=run, daemon=True)
    thread.start()
    logger.info("Health server started in background")
    return thread
