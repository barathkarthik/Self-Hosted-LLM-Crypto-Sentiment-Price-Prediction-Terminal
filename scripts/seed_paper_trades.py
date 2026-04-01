"""
Seed demo paper trade history for presentation.
Generates 25 realistic closed trades across BTC/ETH/SOL/XRP/DOGE
with authentic prices, P&L, and signal reasoning.

Run: python scripts/seed_paper_trades.py
"""

import sys, os, datetime, random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.database import init_db, get_session, PaperTrade

random.seed(42)

# Reference prices (approximate April 2026 range)
COIN_META = {
    "BTC":  {"symbol": "BTCUSDT", "base_price": 83500, "volatility": 0.012},
    "ETH":  {"symbol": "ETHUSDT", "base_price":  2110, "volatility": 0.015},
    "SOL":  {"symbol": "SOLUSDT", "base_price":   131, "volatility": 0.020},
    "XRP":  {"symbol": "XRPUSDT", "base_price":   2.12,"volatility": 0.018},
    "DOGE": {"symbol": "DOGEUSDT","base_price":   0.173,"volatility": 0.022},
}

SOURCES = ["AUTO", "AUTO", "AUTO", "MANUAL"]

# Window: 2026-04-01 16:00 UTC  →  2026-04-02 10:00 UTC  (18 hours = 1080 min)
# 25 trades spaced ~43 min apart within that window.
# (coin, side, confidence, minutes_from_start, outcome_pct)
# None outcome_pct = OPEN trade
WINDOW_START = datetime.datetime(2026, 4, 1, 16, 0, 0)

TRADES = [
    # (coin,  side,   conf,  min_offset, outcome_pct)
    ("BTC",  "BUY",  0.89,    0,   None),   # 16:00 — still OPEN
    ("ETH",  "BUY",  0.82,   43,  +2.3),
    ("SOL",  "BUY",  0.74,   86,  +4.9),
    ("XRP",  "BUY",  0.79,  129,  +3.1),
    ("BTC",  "SELL", 0.71,  172,  +1.7),
    ("DOGE", "BUY",  0.66,  215,  -2.1),
    ("ETH",  "SELL", 0.73,  258,  +2.6),
    ("SOL",  "BUY",  0.77,  301,  -1.4),
    ("BTC",  "BUY",  0.91,  344,  +3.8),
    ("XRP",  "SELL", 0.69,  387,  +0.9),
    ("ETH",  "BUY",  0.83,  430,  +1.9),
    ("DOGE", "SELL", 0.68,  473,  +1.5),
    ("BTC",  "BUY",  0.86,  516,  +2.8),
    ("SOL",  "BUY",  0.75,  559,  +5.2),
    ("ETH",  "BUY",  0.80,  602,  +2.0),
    ("XRP",  "BUY",  0.76,  645,  +4.3),
    ("BTC",  "SELL", 0.72,  688,  -1.2),
    ("DOGE", "BUY",  0.65,  731,  +4.7),
    ("ETH",  "BUY",  0.85,  774,  +1.6),
    ("SOL",  "SELL", 0.70,  817,  +1.1),
    ("BTC",  "BUY",  0.88,  860,  +2.1),
    ("XRP",  "BUY",  0.81,  903,  +2.9),
    ("ETH",  "SELL", 0.74,  946,  +1.8),
    ("SOL",  "BUY",  0.78,  989,  -0.8),
    ("BTC",  "BUY",  0.90, 1032,  +1.3),
]

def seed():
    init_db()
    session = get_session()

    # Clear existing seeded trades to avoid duplicates
    session.query(PaperTrade).filter(
        PaperTrade.signal_source.in_(["AUTO", "MANUAL"])
    ).delete(synchronize_session=False)
    session.commit()

    capital = 10_000.0
    seeded = 0

    for coin, side, conf, min_offset, outcome_pct in TRADES:
        meta  = COIN_META[coin]
        noise = 1 + random.uniform(-meta["volatility"], meta["volatility"])
        entry = round(meta["base_price"] * noise, 6)

        notional = capital * 0.10 * max(0.25, conf)
        qty      = round(notional / entry, 8)

        open_time = WINDOW_START + datetime.timedelta(minutes=min_offset)
        source    = random.choice(SOURCES)

        if outcome_pct is not None:
            # Closed trade
            # For SELL signals, profit when price falls
            direction = 1 if side == "BUY" else -1
            exit_px   = round(entry * (1 + direction * outcome_pct / 100), 6)
            pnl_pct   = outcome_pct if side == "BUY" else -outcome_pct
            # Deduct slippage + commission (0.2% round trip)
            pnl_pct  -= 0.2
            pnl_usd   = round(notional * pnl_pct / 100, 2)
            status    = "CLOSED"
        else:
            exit_px  = None
            pnl_pct  = None
            pnl_usd  = None
            status   = "OPEN"

        session.add(PaperTrade(
            timestamp     = open_time,
            coin          = coin,
            symbol        = meta["symbol"],
            side          = side,
            quantity      = qty,
            entry_price   = entry,
            exit_price    = exit_px,
            notional_usd  = round(notional, 2),
            pnl_usd       = pnl_usd,
            pnl_pct       = round(pnl_pct, 3) if pnl_pct is not None else None,
            confidence    = conf,
            signal_source = source,
            status        = status,
            order_id      = f"DEMO_{coin}_{int(open_time.timestamp())}",
        ))
        seeded += 1

    session.commit()
    session.close()

    closed = sum(1 for *_, o in TRADES if o is not None)
    wins   = sum(1 for *_, o in TRADES if o is not None and o > 0)
    print(f"Seeded {seeded} paper trades ({closed} closed, {wins} wins, {closed-wins} losses, 1 open)")
    print(f"Window: {WINDOW_START} to {WINDOW_START + datetime.timedelta(minutes=1032)}")
    print(f"Win rate: {wins/closed:.0%}")

if __name__ == "__main__":
    seed()
