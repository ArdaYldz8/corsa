#!/usr/bin/env python3
"""
Trading Bot Entry Point
Run the trading bot in paper or live mode
"""
import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.bot import create_bot


def main():
    parser = argparse.ArgumentParser(description='Crypto Trading Bot')
    parser.add_argument(
        '--config', '-c',
        type=str,
        default=None,
        help='Path to config file (default: config/config.yaml)'
    )
    parser.add_argument(
        '--live',
        action='store_true',
        help='Run in live trading mode (USE WITH CAUTION!)'
    )
    
    args = parser.parse_args()
    
    if args.live:
        print("\n" + "="*50)
        print("⚠️  WARNING: LIVE TRADING MODE ⚠️")
        print("="*50)
        print("You are about to trade with REAL MONEY!")
        print("Make sure you understand the risks.")
        print("="*50)
        
        confirm = input("\nType 'YES' to confirm: ")
        if confirm != "YES":
            print("Cancelled.")
            sys.exit(0)
    
    try:
        bot = create_bot(config_path=args.config, live=args.live)
        bot.start()
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
