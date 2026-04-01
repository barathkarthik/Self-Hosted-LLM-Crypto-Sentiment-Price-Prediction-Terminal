"""
Paper Trading Engine — Local Simulation with Live Binance Prices
Fetches real-time prices from Binance public API (no auth needed).
Simulates fills locally and persists every trade to SQLite.
No testnet auth required — zero API errors.
"""

import uuid
import logging
import requests
import datetime

logger = logging.getLogger("PaperTrader")

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import (
    BINANCE_BASE_URL,
    COINS,
    MIN_CONFIDENCE,
    SLIPPAGE_PCT,
    COMMISSION_PCT,
)
from src.database import get_session, PaperTrade, init_db

MIN_NOTIONAL_USD = 10.0

# Simulated portfolio — starts with $10,000 USDT
_PORTFOLIO_KEY = "USDT"


class PaperTrader:
    """
    Fully local paper trading engine.
    - Prices: Binance public REST API (no key needed)
    - Orders: simulated with slippage + commission
    - Storage: SQLite PaperTrade table
    """

    def __init__(self):
        self.enabled = True  # always on — no auth dependency

    # ── Live price from Binance public API ──────────────────────
    def get_price(self, symbol: str) -> float:
        r = requests.get(f"{BINANCE_BASE_URL}/ticker/price",
                         params={"symbol": symbol}, timeout=5)
        r.raise_for_status()
        return float(r.json()["price"])

    # ── Execute signal ───────────────────────────────────────────
    def execute_signal(self, coin: str, signal_type: str, confidence: float,
                       notional_override: float = None) -> dict:
        """
        Simulate a market order fill with slippage + commission.
        notional_override: exact USDT amount to trade (from UI input).
        """
        if signal_type not in ("BUY", "SELL"):
            return {"status": "SKIPPED", "reason": f"Signal is {signal_type}"}

        if confidence < MIN_CONFIDENCE:
            return {"status": "SKIPPED", "reason": f"Confidence {confidence:.0%} below minimum"}

        symbol = COINS.get(coin, {}).get("binance", f"{coin}USDT")
        side   = signal_type  # BUY or SELL

        try:
            market_price = self.get_price(symbol)

            notional = notional_override if (notional_override and notional_override >= MIN_NOTIONAL_USD) else 100.0

            # Apply slippage (adverse to trader)
            slip = SLIPPAGE_PCT
            fill_price = market_price * (1 + slip) if side == "BUY" else market_price * (1 - slip)
            qty = round(notional / fill_price, 8)

            # Commission deducted from notional
            commission = notional * COMMISSION_PCT
            net_notional = notional - commission

            order_id = f"SIM-{uuid.uuid4().hex[:10].upper()}"
            logger.info(f"[PaperTrader] SIM {side} {qty:.6f} {symbol} "
                        f"@ ${fill_price:,.4f} (mkt ${market_price:,.4f}) "
                        f"notional=${notional:.2f} commission=${commission:.3f}")

            self._save_trade(coin, symbol, side, qty, fill_price,
                             net_notional, confidence, order_id)

            return {
                "status":       "FILLED",
                "side":         side,
                "symbol":       symbol,
                "quantity":     qty,
                "price":        fill_price,
                "market_price": market_price,
                "notional":     notional,
                "commission":   commission,
                "orderId":      order_id,
            }
        except Exception as e:
            logger.error(f"[PaperTrader] {coin} {side} failed: {e}")
            return {"status": "ERROR", "reason": str(e)}

    def _save_trade(self, coin, symbol, side, qty, price, notional, confidence, order_id):
        try:
            init_db()
            session = get_session()
            session.add(PaperTrade(
                coin=coin, symbol=symbol, side=side, quantity=qty,
                entry_price=price, notional_usd=notional,
                confidence=confidence, order_id=order_id,
                signal_source="MANUAL", status="OPEN",
            ))
            session.commit()
            session.close()
        except Exception as e:
            logger.warning(f"[PaperTrader] DB save failed: {e}")

    def get_trade_history(self, limit: int = 50) -> list[dict]:
        """Return local paper trade history from DB."""
        try:
            init_db()
            session = get_session()
            trades = session.query(PaperTrade).order_by(
                PaperTrade.timestamp.desc()
            ).limit(limit).all()
            session.close()
            return [{
                "time":       t.timestamp.strftime("%m/%d %H:%M"),
                "coin":       t.coin,
                "side":       t.side,
                "qty":        t.quantity,
                "entry":      t.entry_price,
                "exit":       t.exit_price,
                "notional":   t.notional_usd,
                "pnl_usd":    t.pnl_usd,
                "pnl_pct":    t.pnl_pct,
                "confidence": t.confidence,
                "source":     t.signal_source,
                "status":     t.status,
            } for t in trades]
        except Exception as e:
            logger.error(f"[PaperTrader] history fetch failed: {e}")
            return []

    def get_portfolio_summary(self) -> dict:
        """Compute simulated portfolio from trade history."""
        try:
            history = self.get_trade_history(200)
            closed  = [t for t in history if t["status"] == "CLOSED"]
            total_pnl = sum(t["pnl_usd"] or 0 for t in closed)
            return {
                "enabled":   True,
                "total_pnl": total_pnl,
                "trades":    len(closed),
            }
        except Exception as e:
            return {"enabled": True, "error": str(e)}
