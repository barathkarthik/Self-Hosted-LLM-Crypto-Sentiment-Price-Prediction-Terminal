"""
Data Ingestion Pipeline — 5 collectors running on schedule.
Telegram | Fear&Greed | NewsAPI | Binance OHLCV | Etherscan Whales
All free-tier APIs with built-in rate limiting.
"""

import time, hashlib, datetime, logging, requests, asyncio

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("DataLoader")

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import (
    NEWS_API_KEY, ETHERSCAN_API_KEY, BINANCE_BASE_URL, COINS,
    TELEGRAM_API_ID, TELEGRAM_API_HASH,
)
from src.database import (
    get_session, RedditPost, NewsArticle, PriceData, WhaleTransaction,
    SentimentSnapshot,
)

# ═══════════════════════════════════════════════
#  TELEGRAM CONFIG
# ═══════════════════════════════════════════════
TELEGRAM_CHANNELS = [
    "bitcoinnews",
    "cointelegraph",
    "Bitcoin",
    "CryptoNewsEnglish",
    "whale_alert_io",
]

COIN_KEYWORDS = {
    "BTC":  ["bitcoin", "btc", "#btc"],
    "ETH":  ["ethereum", "eth", "ether", "#eth"],
    "SOL":  ["solana", "sol", "#sol"],
    "XRP":  ["ripple", "xrp", "#xrp"],
    "DOGE": ["dogecoin", "doge", "#doge"],
}


# ═══════════════════════════════════════════════
#  1. TELEGRAM COLLECTOR (replaces Reddit)
# ═══════════════════════════════════════════════
class CryptoPanicCollector:
    """Reads public Telegram crypto channels using Telethon. No key needed beyond API credentials."""

    def __init__(self):
        self.available = bool(TELEGRAM_API_ID and TELEGRAM_API_HASH)
        if not self.available:
            logger.warning("[Telegram] API credentials not set — add TELEGRAM_API_ID and TELEGRAM_API_HASH to .env.local")

    def _get_client(self):
        from telethon import TelegramClient
        session_path = os.path.join(os.path.dirname(__file__), "..", "telegram.session")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        client = TelegramClient(session_path, TELEGRAM_API_ID, TELEGRAM_API_HASH, loop=loop)
        return client, loop

    def fetch_posts(self, coin: str, limit: int = 30) -> list[dict]:
        if not self.available:
            return []
        keywords = COIN_KEYWORDS.get(coin, [coin.lower()])
        posts = []

        async def _fetch():
            client, loop = self._get_client()
            await client.connect()
            if not await client.is_user_authorized():
                logger.error("[Telegram] Session expired — run setup_telegram.py again")
                await client.disconnect()
                return []
            results = []
            for channel in TELEGRAM_CHANNELS:
                try:
                    async for msg in client.iter_messages(channel, limit=limit):
                        if not msg.text:
                            continue
                        if not any(kw in msg.text.lower() for kw in keywords):
                            continue
                        pid = hashlib.md5(f"{channel}{msg.id}".encode()).hexdigest()
                        results.append({
                            "post_id": pid, "coin": coin,
                            "subreddit": channel,
                            "title": msg.text[:500],
                            "body": msg.text[:500],
                            "score": getattr(msg, "views", 0) or 0,
                            "num_comments": getattr(msg, "forwards", 0) or 0,
                            "created_utc": msg.date.replace(tzinfo=None),
                        })
                except Exception as e:
                    logger.error(f"[Telegram] {channel}: {e}")
            await client.disconnect()
            return results

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            posts = loop.run_until_complete(_fetch())
            loop.close()
        except Exception as e:
            logger.error(f"[Telegram] fetch_posts {coin}: {e}")
        return posts

    def save_posts(self, posts: list[dict]) -> int:
        session = get_session()
        saved = 0
        for p in posts:
            if not session.query(RedditPost).filter_by(post_id=p["post_id"]).first():
                session.add(RedditPost(**p))
                saved += 1
        session.commit()
        session.close()
        return saved

    def collect(self, coins: list[str] = None) -> int:
        if not self.available:
            return 0
        total = 0
        for coin in (coins or list(COINS.keys())):
            total += self.save_posts(self.fetch_posts(coin))
            time.sleep(1)
        logger.info(f"[Telegram] Saved {total} new posts")
        return total


# ═══════════════════════════════════════════════
#  FEAR & GREED INDEX COLLECTOR
# ═══════════════════════════════════════════════
class FearGreedCollector:
    URL = "https://api.alternative.me/fng/?limit=1"

    def collect(self) -> dict:
        try:
            resp = requests.get(self.URL, timeout=10)
            resp.raise_for_status()
            data = resp.json()["data"][0]
            value = int(data["value"])
            label_map = {
                range(0, 25):  ("BEARISH", "Extreme Fear"),
                range(25, 45): ("BEARISH", "Fear"),
                range(45, 55): ("NEUTRAL", "Neutral"),
                range(55, 75): ("BULLISH", "Greed"),
                range(75, 101):("BULLISH", "Extreme Greed"),
            }
            sentiment_label, mood = next(
                (v for k, v in label_map.items() if value in k),
                ("NEUTRAL", "Neutral")
            )
            score = round(value / 100, 2)
            session = get_session()
            for coin in COINS:
                session.add(SentimentSnapshot(
                    coin=coin, avg_score=score,
                    label=sentiment_label, sample_count=1,
                    source="fear_greed", model_used="alternative.me",
                ))
            session.commit()
            session.close()
            logger.info(f"[FearGreed] {mood} ({value}/100) → score={score}")
            return {"value": value, "label": sentiment_label, "mood": mood, "score": score}
        except Exception as e:
            logger.error(f"[FearGreed] {e}")
            return {}


# ═══════════════════════════════════════════════
#  2. NEWS COLLECTOR
# ═══════════════════════════════════════════════
class NewsCollector:
    BASE_URL = "https://newsapi.org/v2/everything"

    def fetch_news(self, coin: str, page_size: int = 20) -> list[dict]:
        if not NEWS_API_KEY:
            return []
        name = COINS[coin]["name"]
        try:
            resp = requests.get(self.BASE_URL, params={
                "q": f"{name} OR {coin} cryptocurrency",
                "language": "en", "sortBy": "publishedAt",
                "pageSize": page_size, "apiKey": NEWS_API_KEY,
            }, timeout=10)
            resp.raise_for_status()
            articles = []
            for a in resp.json().get("articles", []):
                aid = hashlib.md5((a.get("url", "") + a.get("title", "")).encode()).hexdigest()
                pub = None
                if a.get("publishedAt"):
                    pub = datetime.datetime.fromisoformat(a["publishedAt"].replace("Z", "+00:00"))
                articles.append({
                    "article_id": aid, "coin": coin,
                    "source": a.get("source", {}).get("name", ""),
                    "title": a.get("title", ""), "description": a.get("description", ""),
                    "url": a.get("url", ""), "published_at": pub,
                })
            return articles
        except Exception as e:
            logger.error(f"[News] {coin}: {e}")
            return []

    def save_articles(self, articles: list[dict]) -> int:
        session = get_session()
        saved = 0
        for a in articles:
            if not session.query(NewsArticle).filter_by(article_id=a["article_id"]).first():
                session.add(NewsArticle(**a))
                saved += 1
        session.commit()
        session.close()
        return saved

    def collect(self, coins: list[str] = None) -> int:
        total = 0
        for coin in (coins or list(COINS.keys())):
            total += self.save_articles(self.fetch_news(coin))
            time.sleep(1)
        logger.info(f"[News] Saved {total} new articles")
        return total


# ═══════════════════════════════════════════════
#  3. BINANCE PRICE COLLECTOR
# ═══════════════════════════════════════════════
class PriceCollector:

    def fetch_klines(self, coin: str, interval: str = "15m", limit: int = 100) -> list[dict]:
        symbol = COINS[coin]["binance"]
        try:
            resp = requests.get(f"{BINANCE_BASE_URL}/klines",
                                params={"symbol": symbol, "interval": interval, "limit": limit},
                                timeout=10)
            resp.raise_for_status()
            return [{
                "coin": coin,
                "timestamp": datetime.datetime.utcfromtimestamp(k[0] / 1000),
                "open": float(k[1]), "high": float(k[2]),
                "low": float(k[3]), "close": float(k[4]),
                "volume": float(k[5]), "interval": interval,
            } for k in resp.json()]
        except Exception as e:
            logger.error(f"[Price] {coin}: {e}")
            return []

    def fetch_current_price(self, coin: str) -> float | None:
        symbol = COINS[coin]["binance"]
        try:
            resp = requests.get(f"{BINANCE_BASE_URL}/ticker/price",
                                params={"symbol": symbol}, timeout=5)
            return float(resp.json()["price"])
        except Exception:
            return None

    def save_klines(self, candles: list[dict]) -> int:
        session = get_session()
        saved = 0
        for c in candles:
            if not session.query(PriceData).filter_by(
                    coin=c["coin"], timestamp=c["timestamp"], interval=c["interval"]).first():
                session.add(PriceData(**c))
                saved += 1
        session.commit()
        session.close()
        return saved

    def collect(self, coins: list[str] = None, interval: str = "15m") -> int:
        total = 0
        for coin in (coins or list(COINS.keys())):
            total += self.save_klines(self.fetch_klines(coin, interval))
            time.sleep(0.5)
        logger.info(f"[Price] Saved {total} new candles")
        return total

    def fetch_historical(self, coin: str, days: int = 90, interval: str = "15m") -> int:
        """Bulk-fetch historical data for model training."""
        symbol = COINS[coin]["binance"]
        ms_per_candle = {"15m": 900_000, "1h": 3_600_000, "4h": 14_400_000}
        step = ms_per_candle.get(interval, 900_000)

        end_ms = int(datetime.datetime.utcnow().timestamp() * 1000)
        cur = end_ms - (days * 86_400_000)
        total = 0
        while cur < end_ms:
            try:
                resp = requests.get(f"{BINANCE_BASE_URL}/klines", params={
                    "symbol": symbol, "interval": interval,
                    "startTime": cur, "limit": 1000,
                }, timeout=15)
                data = resp.json()
                if not data:
                    break
                candles = [{
                    "coin": coin,
                    "timestamp": datetime.datetime.utcfromtimestamp(k[0] / 1000),
                    "open": float(k[1]), "high": float(k[2]),
                    "low": float(k[3]), "close": float(k[4]),
                    "volume": float(k[5]), "interval": interval,
                } for k in data]
                total += self.save_klines(candles)
                cur = int(data[-1][0]) + step
                time.sleep(0.3)
            except Exception as e:
                logger.error(f"[Price] history: {e}")
                break
        logger.info(f"[Price] {coin}: {total} historical candles")
        return total


# ═══════════════════════════════════════════════
#  4. WHALE / ON-CHAIN TRACKER
# ═══════════════════════════════════════════════
class WhaleCollector:
    BASE_URL = "https://api.etherscan.io/api"

    KNOWN_EXCHANGES = {
        "0x28c6c06298d514db089934071355e5743bf21d60",  # Binance Hot
        "0x21a31ee1afc51d94c2efccaa2092ad1028285549",  # Binance
        "0xdfd5293d8e347dfe59e90efd55b2956a1343963d",  # Binance
        "0x1ab4973a48dc892cd9971ece8e01dcc7688f8f23",  # Coinbase
    }

    def _get_eth_price(self) -> float:
        try:
            r = requests.get(f"{BINANCE_BASE_URL}/ticker/price",
                             params={"symbol": "ETHUSDT"}, timeout=5)
            return float(r.json()["price"])
        except Exception:
            return 3000.0

    def _classify(self, tx: dict) -> str:
        to_a = (tx.get("to") or "").lower()
        from_a = (tx.get("from") or "").lower()
        if to_a in self.KNOWN_EXCHANGES:
            return "DISTRIBUTION"
        if from_a in self.KNOWN_EXCHANGES:
            return "ACCUMULATION"
        return "TRANSFER"

    def fetch_whale_txns(self, min_eth: float = 100) -> list[dict]:
        if not ETHERSCAN_API_KEY:
            return []
        try:
            r = requests.get(self.BASE_URL, params={
                "module": "proxy", "action": "eth_blockNumber",
                "apikey": ETHERSCAN_API_KEY,
            }, timeout=10)
            latest = int(r.json()["result"], 16)
            eth_price = self._get_eth_price()
            txns = []
            for offset in range(5):
                blk = hex(latest - offset)
                r2 = requests.get(self.BASE_URL, params={
                    "module": "proxy", "action": "eth_getBlockByNumber",
                    "tag": blk, "boolean": "true", "apikey": ETHERSCAN_API_KEY,
                }, timeout=10)
                blk_data = r2.json().get("result", {})
                if not blk_data or not blk_data.get("transactions"):
                    continue
                blk_time = datetime.datetime.utcfromtimestamp(int(blk_data["timestamp"], 16))
                for tx in blk_data["transactions"]:
                    val_eth = int(tx.get("value", "0x0"), 16) / 1e18
                    if val_eth >= min_eth:
                        txns.append({
                            "tx_hash": tx["hash"], "coin": "ETH",
                            "from_address": tx.get("from", ""),
                            "to_address": tx.get("to", ""),
                            "value_token": val_eth, "value_usd": val_eth * eth_price,
                            "block_number": int(tx.get("blockNumber", "0x0"), 16),
                            "timestamp": blk_time, "tx_type": self._classify(tx),
                        })
                time.sleep(0.25)
            return txns
        except Exception as e:
            logger.error(f"[Whale] {e}")
            return []

    def save_txns(self, txns: list[dict]) -> int:
        session = get_session()
        saved = 0
        for t in txns:
            if not session.query(WhaleTransaction).filter_by(tx_hash=t["tx_hash"]).first():
                session.add(WhaleTransaction(**t))
                saved += 1
        session.commit()
        session.close()
        logger.info(f"[Whale] Saved {saved} transactions")
        return saved

    def collect(self) -> int:
        return self.save_txns(self.fetch_whale_txns())


# ═══════════════════════════════════════════════
#  RUN ALL COLLECTORS
# ═══════════════════════════════════════════════
def run_full_collection(coins=None):
    results = {}
    results["cryptopanic"] = CryptoPanicCollector().collect(coins)
    results["fear_greed"]  = FearGreedCollector().collect()
    results["news"]        = NewsCollector().collect(coins)
    results["prices"]      = PriceCollector().collect(coins)
    results["whales"]      = WhaleCollector().collect()
    logger.info(f"[Collection] {results}")
    return results
