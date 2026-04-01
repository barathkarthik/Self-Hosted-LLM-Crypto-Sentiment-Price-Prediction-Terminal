"""
Backtesting Engine — replays signals against historical prices.

Improvements ported from SRL (Strategy Research Lab):
  - Slippage modeling    (live_executor.py  — SLIPPAGE_BASE pattern)
  - Commission deduction (backtesting.py    — realistic cost model)
  - Sortino ratio        (backtesting.py    — downside-deviation risk)
  - CAGR                 (backtesting.py    — annualised compound return)
  - Rolling Sharpe       (comparison_dashboard.py — 126-period window)
  - Confidence-weighted position sizing (live_executor.py — scale by signal prob)
"""

import logging
import datetime
import pandas as pd
import numpy as np

logger = logging.getLogger("Backtester")

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.database import get_session, Signal, PriceData
from config import SLIPPAGE_PCT, COMMISSION_PCT, POSITION_SIZE_PCT


class Backtester:
    def __init__(self, initial_capital: float = 10_000.0,
                 position_pct: float = POSITION_SIZE_PCT):
        self.initial_capital = initial_capital
        self.position_pct = position_pct

    # ──────────────────────────────────────────────────────
    #  DATA LOADING
    # ──────────────────────────────────────────────────────
    def load_signals(self, coin: str = None, days: int = 30) -> pd.DataFrame:
        session = get_session()
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=days)
        q = session.query(Signal).filter(
            Signal.timestamp >= cutoff,
            Signal.signal_type.in_(["BUY", "SELL"]),
        )
        if coin:
            q = q.filter(Signal.coin == coin)
        sigs = q.order_by(Signal.timestamp).all()
        session.close()
        if not sigs:
            return pd.DataFrame()
        return pd.DataFrame([{
            "coin": s.coin, "timestamp": s.timestamp,
            "signal_type": s.signal_type, "confidence": s.confidence,
            "reasoning": s.reasoning,
        } for s in sigs])

    def load_prices(self, coin: str, days: int = 30) -> pd.DataFrame:
        session = get_session()
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=days)
        prices = session.query(PriceData).filter(
            PriceData.coin == coin,
            PriceData.timestamp >= cutoff,
            PriceData.interval == "15m",
        ).order_by(PriceData.timestamp).all()
        session.close()
        if not prices:
            return pd.DataFrame()
        return pd.DataFrame([{
            "timestamp": p.timestamp, "close": p.close,
            "high": p.high, "low": p.low, "volume": p.volume,
        } for p in prices])

    # ──────────────────────────────────────────────────────
    #  EVALUATION
    # ──────────────────────────────────────────────────────
    def evaluate(self, coin: str, horizon_h: int = 4, days: int = 30) -> dict:
        sdf = self.load_signals(coin, days)
        pdf = self.load_prices(coin, days)
        if sdf.empty or pdf.empty:
            return {"error": "not enough data"}

        pdf = pdf.sort_values("timestamp").set_index("timestamp")
        results = []

        for _, sig in sdf.iterrows():
            t0 = sig["timestamp"]
            t1 = t0 + datetime.timedelta(hours=horizon_h)
            e = pdf.loc[pdf.index >= t0].head(1)
            x = pdf.loc[pdf.index >= t1].head(1)
            if e.empty or x.empty:
                continue

            ep = e["close"].iloc[0]
            xp = x["close"].iloc[0]
            conf = float(sig.get("confidence") or 0.5)

            if sig["signal_type"] == "BUY":
                # Apply slippage: pay more on entry, receive less on exit
                ep_slip = ep * (1 + SLIPPAGE_PCT)
                xp_slip = xp * (1 - SLIPPAGE_PCT)
                pnl = ((xp_slip - ep_slip) / ep_slip) * 100 - COMMISSION_PCT * 100
                ok = xp > ep
            else:  # SELL / short
                ep_slip = ep * (1 - SLIPPAGE_PCT)
                xp_slip = xp * (1 + SLIPPAGE_PCT)
                pnl = ((ep_slip - xp_slip) / ep_slip) * 100 - COMMISSION_PCT * 100
                ok = xp < ep

            results.append({
                "coin": coin, "signal_type": sig["signal_type"],
                "entry": ep, "exit": xp,
                "entry_after_slip": ep_slip, "exit_after_slip": xp_slip,
                "pnl_pct": pnl, "correct": ok, "confidence": conf,
                "timestamp": t0,
            })

        if not results:
            return {"error": "no evaluatable signals"}
        return self._metrics(pd.DataFrame(results))

    # ──────────────────────────────────────────────────────
    #  METRICS  (SRL additions: Sortino, CAGR, rolling Sharpe,
    #            confidence-weighted equity curve)
    # ──────────────────────────────────────────────────────
    def _metrics(self, df: pd.DataFrame) -> dict:
        n = len(df)
        wins = int(df["correct"].sum())
        wr = wins / n if n else 0
        pnl = df["pnl_pct"]

        # ── Sharpe (annualised, 252 trading days) ──
        sharpe = float(pnl.mean() / pnl.std() * np.sqrt(252)) if pnl.std() > 0 else 0.0

        # ── Sortino (annualised, downside deviation only) — from SRL ──
        downside = pnl[pnl < 0]
        sortino = float(
            pnl.mean() / downside.std() * np.sqrt(252)
        ) if len(downside) > 1 and downside.std() > 0 else 0.0

        # ── Max Drawdown ──
        cum = (1 + pnl / 100).cumprod()
        dd = float(((cum - cum.cummax()) / cum.cummax()).min() * 100)

        # ── Confidence-weighted equity curve — from SRL ──
        # Scales position size by signal confidence (higher confidence → bigger bet)
        cap = self.initial_capital
        cap_hist = [cap]
        for _, row in df.iterrows():
            sized_pct = self.position_pct * max(0.25, float(row.get("confidence", 0.5)))
            cap += cap * sized_pct * (row["pnl_pct"] / 100)
            cap_hist.append(cap)

        final_cap = float(cap)
        cap_growth = float((final_cap - self.initial_capital) / self.initial_capital * 100)

        # ── CAGR — from SRL ──
        if "timestamp" in df.columns and len(df) >= 2:
            elapsed_days = max(
                (df["timestamp"].max() - df["timestamp"].min()).total_seconds() / 86400, 1
            )
            cagr = float(
                ((final_cap / self.initial_capital) ** (365.0 / elapsed_days) - 1) * 100
            )
        else:
            cagr = 0.0

        # ── Rolling Sharpe (126-trade window) — from SRL comparison_dashboard ──
        rolling_sharpe: list = []
        window = 126
        if len(pnl) >= window:
            rs = pnl.rolling(window).apply(
                lambda x: x.mean() / x.std() * np.sqrt(252) if x.std() > 0 else 0.0,
                raw=True,
            ).dropna()
            rolling_sharpe = [round(v, 4) for v in rs.tolist()]

        return {
            "total_trades": n,
            "wins": wins,
            "losses": n - wins,
            "win_rate": float(wr),
            "total_return_pct": float(pnl.sum()),
            "avg_return_pct": float(pnl.mean()),
            "sharpe_ratio": round(sharpe, 4),
            "sortino_ratio": round(sortino, 4),       # NEW — SRL
            "max_drawdown_pct": round(dd, 4),
            "cagr_pct": round(cagr, 4),               # NEW — SRL
            "final_capital": round(final_cap, 2),
            "capital_growth_pct": round(cap_growth, 4),
            "rolling_sharpe": rolling_sharpe,          # NEW — SRL
            "slippage_pct": SLIPPAGE_PCT * 100,        # transparency
            "commission_pct": COMMISSION_PCT * 100,
            "trades": df.drop(columns=["timestamp"], errors="ignore").to_dict("records"),
            "capital_history": [round(v, 2) for v in cap_hist],
        }

    def run_full_backtest(self, days: int = 30) -> dict:
        session = get_session()
        coins = [r[0] for r in session.query(Signal.coin).distinct().all()]
        session.close()
        return {c: self.evaluate(c, days=days) for c in coins}


# ──────────────────────────────────────────────────────
#  Backward compatibility for existing app.py
# ──────────────────────────────────────────────────────
def backtest(df: pd.DataFrame) -> float:
    """Quick accuracy check — unchanged for backward compatibility."""
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
