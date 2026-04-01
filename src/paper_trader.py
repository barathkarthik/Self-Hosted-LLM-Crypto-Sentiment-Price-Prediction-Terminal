"""
Paper Trading Executor — Binance Testnet
Executes BUY/SELL signals as real orders on Binance Testnet (zero real money).
Keys: testnet.binance.vision → "Generate HMAC_SHA256 Key"
"""

import time
import hmac
import hashlib
import logging
import requests

logger = logging.getLogger("PaperTrader")

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import (
    BINANCE_TESTNET_API_KEY,
    BINANCE_TESTNET_API_SECRET,
    BINANCE_TESTNET_BASE_URL,
    COINS,
    MIN_CONFIDENCE,
    POSITION_SIZE_PCT,
)
from src.utils import retry_with_backoff
from src.database import get_session, PaperTrade, init_db

_RETRY = dict(max_retries=3, base_delay=1.0, backoff=2.0, exceptions=(requests.RequestException,))

# Minimum notional value Binance testnet accepts per order (USD)
MIN_NOTIONAL_USD = 10.0


class PaperTrader:

    def __init__(self):
        self.api_key    = BINANCE_TESTNET_API_KEY
        self.api_secret = BINANCE_TESTNET_API_SECRET
        self.base_url   = BINANCE_TESTNET_BASE_URL
        self.enabled    = bool(self.api_key and self.api_secret)

    # ── Auth helpers ────────────────────────────────────────────
    def _sign(self, params: dict) -> dict:
        params["timestamp"] = int(time.time() * 1000)
        query = "&".join(f"{k}={v}" for k, v in params.items())
        sig = hmac.new(
            self.api_secret.encode("utf-8"),
            query.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        params["signature"] = sig
        return params

    def _headers(self) -> dict:
        return {"X-MBX-APIKEY": self.api_key}

    # ── Testnet API calls ────────────────────────────────────────
    @retry_with_backoff(**_RETRY)
    def get_account(self) -> dict:
        params = self._sign({})
        r = requests.get(f"{self.base_url}/account", params=params,
                         headers=self._headers(), timeout=10)
        r.raise_for_status()
        return r.json()

    @retry_with_backoff(**_RETRY)
    def get_price(self, symbol: str) -> float:
        r = requests.get(f"{self.base_url}/ticker/price",
                         params={"symbol": symbol}, timeout=5)
        r.raise_for_status()
        return float(r.json()["price"])

    @retry_with_backoff(**_RETRY)
    def _place_order(self, symbol: str, side: str, quantity: float) -> dict:
        params = self._sign({
            "symbol":    symbol,
            "side":      side,          # BUY or SELL
            "type":      "MARKET",
            "quantity":  f"{quantity:.6f}",
        })
        r = requests.post(f"{self.base_url}/order", params=params,
                          headers=self._headers(), timeout=10)
        r.raise_for_status()
        return r.json()

    @retry_with_backoff(**_RETRY)
    def get_open_orders(self, symbol: str = None) -> list:
        params = self._sign({"symbol": symbol} if symbol else {})
        r = requests.get(f"{self.base_url}/openOrders", params=params,
                         headers=self._headers(), timeout=10)
        r.raise_for_status()
        return r.json()

    @retry_with_backoff(**_RETRY)
    def get_order_history(self, symbol: str, limit: int = 20) -> list:
        params = self._sign({"symbol": symbol, "limit": limit})
        r = requests.get(f"{self.base_url}/allOrders", params=params,
                         headers=self._headers(), timeout=10)
        r.raise_for_status()
        return r.json()

    # ── USDT balance ────────────────────────────────────────────
    def get_usdt_balance(self) -> float:
        try:
            acc = self.get_account()
            for b in acc.get("balances", []):
                if b["asset"] == "USDT":
                    return float(b["free"])
        except Exception as e:
            logger.error(f"[PaperTrader] balance fetch failed: {e}")
        return 0.0

    # ── Execute signal ───────────────────────────────────────────
    def execute_signal(self, coin: str, signal_type: str, confidence: float) -> dict:
        """
        Execute a BUY or SELL signal on Binance Testnet.
        Position size = POSITION_SIZE_PCT * confidence-weight of USDT balance.
        Returns order dict or error dict.
        """
        if not self.enabled:
            return {"status": "DISABLED", "reason": "Testnet keys not configured"}

        if signal_type not in ("BUY", "SELL"):
            return {"status": "SKIPPED", "reason": f"Signal is {signal_type}"}

        if confidence < MIN_CONFIDENCE:
            return {"status": "SKIPPED", "reason": f"Confidence {confidence:.0%} below minimum"}

        symbol = COINS.get(coin, {}).get("binance", f"{coin}USDT")
        side   = "BUY" if signal_type == "BUY" else "SELL"

        try:
            price        = self.get_price(symbol)
            usdt_balance = self.get_usdt_balance()
            # Confidence-weighted position: 25%–100% of base size
            weight       = max(0.25, min(1.0, confidence))
            notional     = usdt_balance * POSITION_SIZE_PCT * weight

            if notional < MIN_NOTIONAL_USD:
                return {"status": "SKIPPED", "reason": f"Notional ${notional:.2f} below min ${MIN_NOTIONAL_USD}"}

            qty = round(notional / price, 6)
            order = self._place_order(symbol, side, qty)

            order_id = str(order.get("orderId", ""))
            logger.info(f"[PaperTrader] {side} {qty:.6f} {symbol} @ ~${price:,.2f} | "
                        f"notional=${notional:.2f} | orderId={order_id}")

            # Persist to local DB
            self._save_trade(coin, symbol, side, qty, price, notional, confidence, order_id)

            return {
                "status":   "FILLED",
                "side":     side,
                "symbol":   symbol,
                "quantity": qty,
                "price":    price,
                "notional": notional,
                "orderId":  order_id,
                "raw":      order,
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
        """Returns USDT balance + non-zero coin balances from testnet account."""
        if not self.enabled:
            return {"enabled": False}
        try:
            acc = self.get_account()
            balances = {
                b["asset"]: float(b["free"]) + float(b["locked"])
                for b in acc.get("balances", [])
                if float(b["free"]) + float(b["locked"]) > 0
            }
            return {"enabled": True, "balances": balances}
        except Exception as e:
            return {"enabled": True, "error": str(e)}
