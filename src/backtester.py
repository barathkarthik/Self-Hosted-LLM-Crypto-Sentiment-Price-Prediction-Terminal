"""
Backtesting Engine — replays signals against historical prices.
Calculates: win rate, P&L, Sharpe ratio, max drawdown.
"""

import logging, datetime
import pandas as pd
import numpy as np

logger = logging.getLogger("Backtester")

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.database import get_session, Signal, PriceData


class Backtester:
    def __init__(self, initial_capital: float = 10000.0, position_pct: float = 0.1):
        self.initial_capital = initial_capital
        self.position_pct = position_pct

    def load_signals(self, coin: str = None, days: int = 30) -> pd.DataFrame:
        session = get_session()
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=days)
        q = session.query(Signal).filter(Signal.timestamp >= cutoff,
                                          Signal.signal_type.in_(["BUY", "SELL"]))
        if coin:
            q = q.filter(Signal.coin == coin)
        sigs = q.order_by(Signal.timestamp).all()
        session.close()
        if not sigs:
            return pd.DataFrame()
        return pd.DataFrame([{
            "coin": s.coin, "timestamp": s.timestamp, "signal_type": s.signal_type,
            "confidence": s.confidence, "reasoning": s.reasoning,
        } for s in sigs])

    def load_prices(self, coin: str, days: int = 30) -> pd.DataFrame:
        session = get_session()
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=days)
        prices = session.query(PriceData).filter(
            PriceData.coin == coin, PriceData.timestamp >= cutoff,
            PriceData.interval == "15m"
        ).order_by(PriceData.timestamp).all()
        session.close()
        if not prices:
            return pd.DataFrame()
        return pd.DataFrame([{"timestamp": p.timestamp, "close": p.close,
                               "high": p.high, "low": p.low, "volume": p.volume} for p in prices])

    def evaluate(self, coin: str, horizon_h: int = 4, days: int = 30) -> dict:
        sdf = self.load_signals(coin, days)
        pdf = self.load_prices(coin, days)
        if sdf.empty or pdf.empty:
            return {"error": "not enough data"}
        pdf = pdf.sort_values("timestamp").set_index("timestamp")
        results = []
        for _, sig in sdf.iterrows():
            t0, t1 = sig["timestamp"], sig["timestamp"] + datetime.timedelta(hours=horizon_h)
            e = pdf.loc[pdf.index >= t0].head(1)
            x = pdf.loc[pdf.index >= t1].head(1)
            if e.empty or x.empty:
                continue
            ep, xp = e["close"].iloc[0], x["close"].iloc[0]
            if sig["signal_type"] == "BUY":
                pnl = ((xp - ep) / ep) * 100
                ok = xp > ep
            else:
                pnl = ((ep - xp) / ep) * 100
                ok = xp < ep
            results.append({"coin": coin, "signal_type": sig["signal_type"],
                            "entry": ep, "exit": xp, "pnl_pct": pnl, "correct": ok,
                            "confidence": sig["confidence"]})
        if not results:
            return {"error": "no evaluatable signals"}
        return self._metrics(pd.DataFrame(results))

    def _metrics(self, df: pd.DataFrame) -> dict:
        n = len(df)
        wins = df["correct"].sum()
        wr = wins / n if n else 0
        pnl = df["pnl_pct"]
        sharpe = (pnl.mean() / pnl.std() * np.sqrt(252)) if pnl.std() > 0 else 0
        cum = (1 + pnl / 100).cumprod()
        dd = ((cum - cum.cummax()) / cum.cummax()).min() * 100
        cap = self.initial_capital
        cap_hist = [cap]
        for p in pnl:
            cap += cap * self.position_pct * (p / 100)
            cap_hist.append(cap)
        return {
            "total_trades": n, "wins": int(wins), "losses": n - int(wins),
            "win_rate": float(wr), "total_return_pct": float(pnl.sum()),
            "avg_return_pct": float(pnl.mean()), "sharpe_ratio": float(sharpe),
            "max_drawdown_pct": float(dd), "final_capital": float(cap),
            "capital_growth_pct": float((cap - self.initial_capital) / self.initial_capital * 100),
            "trades": df.to_dict("records"), "capital_history": cap_hist,
        }

    def run_full_backtest(self, days: int = 30) -> dict:
        session = get_session()
        coins = [r[0] for r in session.query(Signal.coin).distinct().all()]
        session.close()
        return {c: self.evaluate(c, days=days) for c in coins}


# Backward compatibility
def backtest(df: pd.DataFrame) -> float:
    """Quick accuracy check for your existing app.py."""
    if "target" not in df.columns:
        if "price" in df.columns:
            df["target"] = (df["price"].shift(-1) > df["price"]).astype(int)
        elif "close" in df.columns:
            df["target"] = (df["close"].shift(-1) > df["close"]).astype(int)
        else:
            return 0.0
    feat = [c for c in ["momentum", "rolling_mean"] if c in df.columns]
    if not feat:
        return 0.0
    clean = df.dropna()
    if len(clean) < 20:
        return 0.0
    split = int(len(clean) * 0.8)
    from sklearn.ensemble import GradientBoostingClassifier
    m = GradientBoostingClassifier(n_estimators=100, max_depth=4)
    m.fit(clean[feat].values[:split], clean["target"].values[:split])
    acc = m.score(clean[feat].values[split:], clean["target"].values[split:])
    return round(acc * 100, 2)
