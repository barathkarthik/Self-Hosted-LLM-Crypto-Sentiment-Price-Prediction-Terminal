"""
Demo Data Seeder — run this ONCE before streamlit run app.py
Fills the database with realistic crypto data for the demo.
Usage: python seed_demo.py
"""
import random
import math
import hashlib
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from src.database import (
    Base, PriceData, Signal, SentimentSnapshot,
    WhaleTransaction, RedditPost, NewsArticle
)

DB_URL = "sqlite:///crypto_terminal.db"
engine = create_engine(DB_URL, echo=False)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

random.seed(42)
NOW = datetime.utcnow()

# ── Realistic starting prices ──
COINS = {
    "BTC":  {"price": 67500, "vol_base": 850_000_000},
    "ETH":  {"price": 3480,  "vol_base": 420_000_000},
    "SOL":  {"price": 178,   "vol_base": 95_000_000},
    "XRP":  {"price": 0.62,  "vol_base": 55_000_000},
    "DOGE": {"price": 0.18,  "vol_base": 30_000_000},
}

def gbm_prices(start, steps, drift=0.0002, vol=0.003):
    prices = [start]
    for _ in range(steps):
        r = drift + vol * random.gauss(0, 1)
        prices.append(prices[-1] * math.exp(r))
    return prices

print("Seeding price data (48h × 15m candles)...")
session.query(PriceData).delete()
for coin, cfg in COINS.items():
    closes = gbm_prices(cfg["price"], 192)  # 48h × 4 per hour
    for i, close in enumerate(closes):
        ts = NOW - timedelta(hours=48) + timedelta(minutes=i*15)
        spread = close * random.uniform(0.001, 0.004)
        o = close * random.uniform(0.998, 1.002)
        h = max(o, close) + spread
        l = min(o, close) - spread
        vol = cfg["vol_base"] * random.uniform(0.7, 1.4) / (24 * 4)
        session.add(PriceData(coin=coin, timestamp=ts, open=o, high=h, low=l,
                               close=close, volume=vol, interval="15m"))
session.commit()
print(f"  ✓ {192 * len(COINS)} price candles inserted")

print("Seeding sentiment snapshots...")
session.query(SentimentSnapshot).delete()
sentiments = {
    "BTC":  (0.72, "BULLISH"),
    "ETH":  (0.65, "BULLISH"),
    "SOL":  (0.58, "NEUTRAL"),
    "XRP":  (0.41, "NEUTRAL"),
    "DOGE": (0.78, "BULLISH"),
}
for coin, (base_score, base_label) in sentiments.items():
    for i in range(48):
        ts = NOW - timedelta(hours=48-i)
        score = max(0.1, min(0.95, base_score + random.gauss(0, 0.05)))
        if score > 0.7: label = "BULLISH"
        elif score < 0.3: label = "BEARISH"
        else: label = "NEUTRAL"
        session.add(SentimentSnapshot(coin=coin, timestamp=ts, avg_score=score,
                                       label=label, sample_count=random.randint(12, 80),
                                       source="reddit+news", model_used="mistral:7b"))
session.commit()
print(f"  ✓ {48 * len(COINS)} sentiment snapshots inserted")

print("Seeding trading signals...")
session.query(Signal).delete()
signal_data = [
    ("BTC",  "BUY",  0.83, "Strong bullish momentum: RSI 58, MACD crossover, whale accumulation $42M. LLM: 'Market structure bullish, resistance at $68.5K likely to break.'", "UP",   "ACCUMULATION"),
    ("ETH",  "BUY",  0.76, "Positive funding rate, ETH/BTC ratio improving. LLM: 'DeFi TVL increasing 12%, staking yield attractive. Bullish short-term.'",                  "UP",   "NEUTRAL"),
    ("SOL",  "HOLD", 0.61, "Consolidating near support. LLM: 'Mixed signals — on-chain activity strong but broader market uncertainty. Wait for confirmation.'",              "FLAT", "NEUTRAL"),
    ("XRP",  "HOLD", 0.55, "Range-bound $0.58-$0.66. LLM: 'Regulatory clarity improving but volume weak. Hold until breakout confirmed.'",                                   "FLAT", "NEUTRAL"),
    ("DOGE", "BUY",  0.69, "Social volume spike +340%, whale buys detected. LLM: 'Meme cycle indicators active, momentum trade setup. Tight stop recommended.'",             "UP",   "ACCUMULATION"),
]
for coin, stype, conf, reason, pred, whale in signal_data:
    session.add(Signal(coin=coin, timestamp=NOW - timedelta(minutes=random.randint(5, 45)),
                        signal_type=stype, confidence=conf, sentiment_score=random.uniform(0.55, 0.82),
                        prediction_direction=pred, prediction_confidence=conf * 0.9,
                        whale_activity=whale, reasoning=reason))
session.commit()
print(f"  ✓ {len(signal_data)} signals inserted")

print("Seeding whale transactions...")
session.query(WhaleTransaction).delete()
whale_events = [
    ("BTC",  42_300_000, 623.4,  "ACCUMULATION"),
    ("BTC",  18_700_000, 276.8,  "TRANSFER"),
    ("ETH",  31_500_000, 9053.4, "ACCUMULATION"),
    ("ETH",  12_200_000, 3506.9, "DISTRIBUTION"),
    ("SOL",  8_400_000,  47191,  "ACCUMULATION"),
    ("DOGE", 5_600_000,  31111111,"ACCUMULATION"),
    ("BTC",  25_000_000, 370.4,  "DISTRIBUTION"),
    ("ETH",  19_800_000, 5690.8, "TRANSFER"),
    ("XRP",  7_300_000,  11774193,"ACCUMULATION"),
    ("SOL",  4_100_000,  23033,  "TRANSFER"),
]
for i, (coin, usd, tokens, txtype) in enumerate(whale_events):
    ts = NOW - timedelta(hours=random.randint(1, 40))
    tx_hash = hashlib.md5(f"{coin}{i}{ts}".encode()).hexdigest()
    from_addr = hashlib.md5(f"from{i}".encode()).hexdigest()[:40]
    to_addr   = hashlib.md5(f"to{i}".encode()).hexdigest()[:40]
    session.add(WhaleTransaction(tx_hash=tx_hash, coin=coin, from_address=from_addr,
                                  to_address=to_addr, value_usd=usd, value_token=tokens,
                                  block_number=random.randint(19_000_000, 20_000_000),
                                  timestamp=ts, tx_type=txtype))
session.commit()
print(f"  ✓ {len(whale_events)} whale transactions inserted")

print("Seeding Reddit posts...")
session.query(RedditPost).delete()
posts = [
    ("BTC", "r/Bitcoin", "Bitcoin breaking ATH resistance — technical analysis", 0.81, "BULLISH"),
    ("BTC", "r/Bitcoin", "Institutional BTC buying accelerates in Q1 2026",       0.75, "BULLISH"),
    ("ETH", "r/ethereum", "Ethereum staking rewards hit 4.8% APY",                0.68, "BULLISH"),
    ("ETH", "r/ethereum", "Layer 2 TVL surpasses $40B milestone",                 0.72, "BULLISH"),
    ("SOL", "r/solana",  "Solana DeFi volume hits $8B weekly record",             0.65, "BULLISH"),
    ("XRP", "r/XRP",     "XRP legal clarity could unlock institutional demand",   0.60, "NEUTRAL"),
    ("DOGE", "r/dogecoin","Dogecoin social volume spike — whale alert triggered", 0.79, "BULLISH"),
    ("BTC", "r/Bitcoin", "BTC on-chain fundamentals remain strong — HODL signal", 0.77, "BULLISH"),
]
for i, (coin, sub, title, score, label) in enumerate(posts):
    pid = hashlib.md5(f"post{i}".encode()).hexdigest()[:10]
    session.add(RedditPost(post_id=pid, coin=coin, subreddit=sub, title=title,
                            body=f"Detailed analysis of {coin} market conditions...",
                            score=random.randint(150, 2400), num_comments=random.randint(20, 380),
                            created_utc=NOW - timedelta(hours=random.randint(1, 20)),
                            sentiment_score=score, sentiment_label=label))
session.commit()
print(f"  ✓ {len(posts)} Reddit posts inserted")

print("Seeding news articles...")
session.query(NewsArticle).delete()
articles = [
    ("BTC", "CoinDesk",    "Bitcoin ETF inflows hit $650M in single day",              0.82, "BULLISH"),
    ("BTC", "Bloomberg",   "MicroStrategy adds 2,100 BTC to treasury holdings",        0.78, "BULLISH"),
    ("ETH", "The Block",   "Ethereum network activity surges ahead of upgrade",         0.71, "BULLISH"),
    ("ETH", "CoinTelegraph","ETH derivatives show record open interest",               0.66, "BULLISH"),
    ("SOL", "Decrypt",     "Solana meme coin activity drives record fee revenue",       0.60, "NEUTRAL"),
    ("XRP", "Reuters",     "Ripple secures new banking partnerships in Southeast Asia", 0.63, "BULLISH"),
    ("BTC", "CNBC",        "Crypto market cap returns to $2.8T amid bull run",          0.74, "BULLISH"),
    ("DOGE", "CoinDesk",   "DOGE social metrics at highest level since 2021",           0.77, "BULLISH"),
]
for i, (coin, source, title, score, label) in enumerate(articles):
    aid = hashlib.md5(f"news{i}".encode()).hexdigest()
    session.add(NewsArticle(article_id=aid, coin=coin, source=source, title=title,
                             description=f"{title}. Full analysis and market impact assessment.",
                             url=f"https://example.com/news/{aid[:8]}",
                             published_at=NOW - timedelta(hours=random.randint(1, 18)),
                             sentiment_score=score, sentiment_label=label))
session.commit()
print(f"  ✓ {len(articles)} news articles inserted")

session.close()
print("\n✅ Demo database ready!")
print("   Run: streamlit run app.py")
