"""
Configuration — Crypto Trading Intelligence Terminal
All API keys loaded from .env.local (never commit keys to GitHub).
"""

import os
from pathlib import Path

# Try loading .env.local if python-dotenv is available
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / ".env.local"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

# ──────────────────────────────────────────────
# API Keys (FREE tiers only — total cost ₹0)
# ──────────────────────────────────────────────
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "CryptoTerminal/1.0")

NEWS_API_KEY        = os.getenv("NEWS_API_KEY", "")
_tg_id = os.getenv("TELEGRAM_API_ID", "0")
TELEGRAM_API_ID     = int(_tg_id) if _tg_id.isdigit() else 0
TELEGRAM_API_HASH   = os.getenv("TELEGRAM_API_HASH", "")

ETHERSCAN_API_KEY   = os.getenv("ETHERSCAN_API_KEY", "")
WHALE_ALERT_API_KEY = os.getenv("WHALE_ALERT_API_KEY", "")  # whale-alert.io — free tier: 10 req/min

# Binance Testnet — paper trading (keys from testnet.binance.vision)
BINANCE_TESTNET_API_KEY    = os.getenv("BINANCE_TESTNET_API_KEY", "")
BINANCE_TESTNET_API_SECRET = os.getenv("BINANCE_TESTNET_API_SECRET", "")
BINANCE_TESTNET_BASE_URL   = "https://testnet.binance.vision/api/v3"

# ──────────────────────────────────────────────
# Binance (public endpoints — no API key needed)
# ──────────────────────────────────────────────
BINANCE_BASE_URL = "https://api.binance.com/api/v3"

# ──────────────────────────────────────────────
# Supported Coins (at least 5 as required)
# ──────────────────────────────────────────────
COINS = {
    "BTC":  {"binance": "BTCUSDT", "subreddit": "Bitcoin",    "name": "Bitcoin"},
    "ETH":  {"binance": "ETHUSDT", "subreddit": "ethereum",   "name": "Ethereum"},
    "SOL":  {"binance": "SOLUSDT", "subreddit": "solana",     "name": "Solana"},
    "XRP":  {"binance": "XRPUSDT", "subreddit": "XRP",        "name": "Ripple"},
    "DOGE": {"binance": "DOGEUSDT","subreddit": "dogecoin",   "name": "Dogecoin"},
}

# ──────────────────────────────────────────────
# Database (SQLite default — swap to PostgreSQL via env)
# ──────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DATABASE_PATH = BASE_DIR / "data" / "crypto_terminal.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATABASE_PATH}")

# ──────────────────────────────────────────────
# LLM Settings (Ollama — runs locally)
# ──────────────────────────────────────────────
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral:7b-instruct-q4_0")
SENTIMENT_TIMEOUT = 30  # seconds per LLM request

# ──────────────────────────────────────────────
# Prediction Model
# ──────────────────────────────────────────────
MODEL_SAVE_PATH = str(BASE_DIR / "models")

# ──────────────────────────────────────────────
# Signal Thresholds
# ──────────────────────────────────────────────
BULLISH_THRESHOLD = 0.7
BEARISH_THRESHOLD = 0.3
WHALE_ALERT_MIN_USD = 1_000_000

# ──────────────────────────────────────────────
# Scheduler Intervals (seconds)
# ──────────────────────────────────────────────
PRICE_FETCH_INTERVAL = 60
REDDIT_FETCH_INTERVAL = 120
NEWS_FETCH_INTERVAL = 300
ONCHAIN_FETCH_INTERVAL = 180
SENTIMENT_RUN_INTERVAL = 120
SIGNAL_RUN_INTERVAL = 60

# ──────────────────────────────────────────────
# Backtesting & Risk Controls  (ported from SRL)
# ──────────────────────────────────────────────
SLIPPAGE_PCT       = float(os.getenv("SLIPPAGE_PCT",       "0.001"))  # 0.1% per side
COMMISSION_PCT     = float(os.getenv("COMMISSION_PCT",     "0.001"))  # 0.1% round-trip fee
POSITION_SIZE_PCT  = float(os.getenv("POSITION_SIZE_PCT",  "0.10"))   # 10% capital per trade
MIN_CONFIDENCE     = float(os.getenv("MIN_CONFIDENCE",     "0.55"))   # skip signals below this
WHALE_NET_FLOW_MIN = float(os.getenv("WHALE_NET_FLOW_MIN", "500000")) # $500k net-flow threshold

# ──────────────────────────────────────────────
# API Resilience — exponential backoff (from SRL)
# ──────────────────────────────────────────────
API_MAX_RETRIES        = int(os.getenv("API_MAX_RETRIES",    "3"))
API_BACKOFF_BASE       = float(os.getenv("API_BACKOFF_BASE", "1.0"))
API_BACKOFF_MULTIPLIER = float(os.getenv("API_BACKOFF_MULT", "2.0"))

# ──────────────────────────────────────────────
# Feature Manifest — model/feature alignment (from SRL)
# ──────────────────────────────────────────────
FEATURE_MANIFEST_PATH = BASE_DIR / "models" / "feature_manifest.json"
