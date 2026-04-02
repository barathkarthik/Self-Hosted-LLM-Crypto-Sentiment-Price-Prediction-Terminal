"""
Main Orchestrator — runs all pipelines on schedule.
Start this BEFORE launching the Streamlit dashboard.

Usage:
    python main.py                  # Full run (fetch history + train + live)
    python main.py --skip-history   # Skip 90-day fetch (already loaded)
    python main.py --train-only     # Just train models and exit
"""

import time, logging, threading, argparse

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
                    handlers=[logging.StreamHandler(), logging.FileHandler("terminal.log")])
logger = logging.getLogger("Main")

from config import (PRICE_FETCH_INTERVAL, NEWS_FETCH_INTERVAL,
                     ONCHAIN_FETCH_INTERVAL, SENTIMENT_RUN_INTERVAL,
                     SIGNAL_RUN_INTERVAL, COINS)
from src.database import init_db
from src.data_loader import CryptoPanicCollector, FearGreedCollector, NewsCollector, PriceCollector, WhaleCollector
from src.sentiment_engine import SentimentEngine
from src.model import PredictionEngine
from src.signal_engine import SignalGenerator
from src.paper_trader import PaperTrader


class CryptoTerminal:
    def __init__(self):
        logger.info("=" * 55)
        logger.info("  CRYPTO TRADING INTELLIGENCE TERMINAL")
        logger.info("=" * 55)
        init_db()
        self.price      = PriceCollector()
        self.news       = NewsCollector()
        self.whale      = WhaleCollector()
        self.cryptopanic= CryptoPanicCollector()
        self.feargreed  = FearGreedCollector()
        self.sentiment  = SentimentEngine()
        self.prediction = PredictionEngine()
        self.signals    = SignalGenerator(self.prediction, self.sentiment)
        self.paper      = PaperTrader()
        self._running = False

    def load_history(self):
        logger.info("[Init] Loading 90 days of historical prices...")
        for coin in COINS:
            try:
                n = self.price.fetch_historical(coin, days=90)
                logger.info(f"  {coin}: {n} candles")
            except Exception as e:
                logger.error(f"  {coin}: {e}")

    def train(self):
        logger.info("[Train] Training models...")
        for coin in COINS:
            try:
                r = self.prediction.train_all(coin)
                logger.info(f"  {coin}: {r}")
            except Exception as e:
                logger.error(f"  {coin}: {e}")

    def _loop(self, fn, interval, name):
        while self._running:
            try:
                fn()
            except Exception as e:
                logger.error(f"[{name}] {e}")
            time.sleep(interval)

    def start(self, skip_history=False):
        self._running = True
        if not skip_history:
            self.load_history()
        self.train()

        tasks = [
            (lambda: self.price.collect(),       PRICE_FETCH_INTERVAL,    "Prices"),
            (lambda: self.news.collect(),        NEWS_FETCH_INTERVAL,     "News"),
            (lambda: self.cryptopanic.collect(), NEWS_FETCH_INTERVAL,     "Telegram"),
            (lambda: self.feargreed.collect(),   NEWS_FETCH_INTERVAL,     "FearGreed"),
            (lambda: self.whale.collect(),       ONCHAIN_FETCH_INTERVAL,  "OnChain"),
            (lambda: self.sentiment.run_full_cycle(), SENTIMENT_RUN_INTERVAL, "Sentiment"),
            (lambda: self.signals.generate_all_signals(), SIGNAL_RUN_INTERVAL, "Signals"),
            (lambda: self.paper.auto_close_open_trades(hold_hours=4), 3600, "PaperClose"),
        ]
        for fn, interval, name in tasks:
            t = threading.Thread(target=self._loop, args=(fn, interval, name), daemon=True, name=name)
            t.start()
            logger.info(f"  ✅ {name} every {interval}s")

        logger.info("\n" + "=" * 55)
        logger.info("  TERMINAL RUNNING — Ctrl+C to stop")
        logger.info("  Dashboard: streamlit run app.py")
        logger.info("=" * 55)
        try:
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            self._running = False
            logger.info("Shutting down.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--skip-history", action="store_true")
    p.add_argument("--train-only", action="store_true")
    a = p.parse_args()
    term = CryptoTerminal()
    if a.train_only:
        term.load_history()
        term.train()
    else:
        term.start(skip_history=a.skip_history)
