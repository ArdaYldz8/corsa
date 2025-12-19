# Crypto Trading Bot

Binance TR için basit RSI/EMA trading botu.

## Özellikler
- ✅ RSI/EMA tabanlı strateji
- ✅ Paper trading modu (güvenli test)
- ✅ Telegram bildirimleri
- ✅ Günlük rapor
- ✅ Binance TR desteği

## Kurulum

```bash
# Bağımlılıkları yükle
pip install -r requirements.txt

# Config dosyasını oluştur
cp config/config.example.yaml config/config.yaml

# config.yaml dosyasını API anahtarlarınla düzenle
```

## Kullanım

```bash
# Paper trading modunda başlat (varsayılan)
python run.py

# Gerçek trading modunda başlat (DİKKAT!)
python run.py --live
```

## Strateji

**Al Sinyali:**
- RSI < 30 (aşırı satım)
- Fiyat > EMA(50) (trend yukarı)

**Sat Sinyali:**
- RSI > 70 (aşırı alım)
- VEYA Fiyat < EMA(50) (trend aşağı)

## Yapılandırma

`config/config.yaml` dosyasını düzenle:

```yaml
exchange:
  api_key: "BINANCE_API_KEY"
  api_secret: "BINANCE_API_SECRET"

trading:
  symbol: "BTC/TRY"
  trade_amount: 100  # TL
  paper_mode: true   # Gerçek işlem için false yap

strategy:
  rsi_period: 14
  rsi_oversold: 30
  rsi_overbought: 70
  ema_period: 50

telegram:
  enabled: true
  bot_token: "TELEGRAM_BOT_TOKEN"
  chat_id: "YOUR_CHAT_ID"
```

## ⚠️ Uyarı

Bu bot eğitim amaçlıdır. Gerçek para ile kullanmadan önce:
1. Paper trading ile en az 1 hafta test et
2. Küçük miktarlarla başla
3. Kaybetmeyi göze alabileceğin parayı kullan
