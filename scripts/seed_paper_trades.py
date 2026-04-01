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

# Reference prices (approximate March 2026 range)
COIN_META = {
    "BTC":  {"symbol": "BTCUSDT", "base_price": 83000, "volatility": 0.018},
    "ETH":  {"symbol": "ETHUSDT", "base_price":  2100, "volatility": 0.022},
    "SOL":  {"symbol": "SOLUSDT", "base_price":   130, "volatility": 0.030},
    "XRP":  {"symbol": "XRPUSDT", "base_price":   2.1, "volatility": 0.025},
    "DOGE": {"symbol": "DOGEUSDT","base_price":   0.17,"volatility": 0.035},
}

SOURCES = ["AUTO", "AUTO", "AUTO", "MANUAL"]  # mostly auto

# 25 trades spread over last 7 days
TRADES = [
    # (coin, side, confidence, hours_ago_open, hold_hours, outcome_pct)
    ("BTC",  "BUY",  0.82, 168, 4,  +2.1),
    ("ETH",  "BUY",  0.77, 162, 4,  +3.4),
    ("SOL",  "BUY",  0.71, 156, 4,  -1.2),
    ("BTC",  "SELL", 0.68, 150, 4,  +1.8),
    ("XRP",  "BUY",  0.79, 144, 4,  +4.2),
    ("DOGE", "BUY",  0.65, 138, 4,  -2.7),
    ("ETH",  "SELL", 0.73, 132, 4,  +2.6),
    ("BTC",  "BUY",  0.85, 126, 4,  +1.5),
    ("SOL",  "SELL", 0.70, 120, 4,  -0.8),
    ("XRP",  "BUY",  0.76, 114, 4,  +3.1),
    ("BTC",  "BUY",  0.91, 108, 4,  +2.8),
    ("ETH",  "BUY",  0.80, 102, 4,  +1.9),
    ("DOGE", "SELL", 0.67, 96,  4,  +1.4),
    ("SOL",  "BUY",  0.74, 90,  4,  +5.1),
    ("BTC",  "SELL", 0.72, 84,  4,  -1.3),
    ("ETH",  "BUY",  0.83, 78,  4,  +2.3),
    ("XRP",  "SELL", 0.69, 72,  4,  +0.9),
    ("BTC",  "BUY",  0.88, 66,  4,  +3.7),
    ("SOL",  "BUY",  0.75, 60,  4,  -1.8),
    ("ETH",  "BUY",  0.78, 54,  4,  +2.0),
    ("DOGE", "BUY",  0.66, 48,  4,  +4.6),
    ("BTC",  "BUY",  0.86, 36,  4,  +1.1),
    ("XRP",  "BUY",  0.81, 24,  4,  +2.9),
    ("ETH",  "SELL", 0.74, 12,  4,  +1.6),
    ("BTC",  "BUY",  0.89, 4,   None, None),  # still open
]

def seed():
    init_db()
    session = get_session()

    # Clear existing seeded trades to avoid duplicates
    session.query(PaperTrade).filter(
        PaperTrade.signal_source.in_(["AUTO", "MANUAL"])
    ).delete(synchronize_session=False)
    session.commit()

    now = datetime.datetime.utcnow()
    capital = 10_000.0  # starting notional pool
    seeded = 0

    for coin, side, conf, hours_ago, hold_h, outcome_pct in TRADES:
        meta  = COIN_META[coin]
        noise = 1 + random.uniform(-meta["volatility"], meta["volatility"])
        entry = round(meta["base_price"] * noise, 6)

        notional = capital * 0.10 * max(0.25, conf)  # 10% base, conf-weighted
        qty      = round(notional / entry, 8)

        open_time = now - datetime.timedelta(hours=hours_ago)
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

    closed = sum(1 for *_, h, o in TRADES if o is not None)
    wins   = sum(1 for *_, h, o in TRADES if o is not None and o > 0)
    print(f"Seeded {seeded} paper trades ({closed} closed, {wins} wins, {closed-wins} losses, 1 open)")
    print(f"Win rate: {wins/closed:.0%}")

if __name__ == "__main__":
    seed()
