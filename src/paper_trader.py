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
import pandas as pd

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
from src.database import get_session, PaperTrade, PriceData, SentimentSnapshot, WhaleTransaction, init_db

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

    # ── XGBoost prediction from live DB features ────────────────
    def _get_feature_rows(self, coin: str):
        """
        Shared helper — fetches latest candles + sentiment + whale data
        and returns (feature_dataframe, avail_cols) ready for both models.
        """
        from src.feature_engineering import (
            compute_technical_indicators, add_sentiment_features,
            add_onchain_features, FEATURE_COLS,
        )
        session = get_session()
        prices = (session.query(PriceData)
                  .filter(PriceData.coin == coin, PriceData.interval == "15m")
                  .order_by(PriceData.timestamp.desc())
                  .limit(200).all())
        if len(prices) < 50:
            session.close()
            return None, []

        pdf = pd.DataFrame([{
            "timestamp": p.timestamp, "open": p.open, "high": p.high,
            "low": p.low, "close": p.close, "volume": p.volume,
        } for p in reversed(prices)])

        sents = (session.query(SentimentSnapshot)
                 .filter(SentimentSnapshot.coin == coin)
                 .order_by(SentimentSnapshot.timestamp.desc()).limit(50).all())
        sdf = pd.DataFrame([{"timestamp": s.timestamp, "avg_score": s.avg_score,
                              "sample_count": s.sample_count} for s in sents]) if sents else None

        whales = (session.query(WhaleTransaction)
                  .filter(WhaleTransaction.coin == coin)
                  .order_by(WhaleTransaction.timestamp.desc()).limit(50).all())
        wdf = pd.DataFrame([{"timestamp": w.timestamp, "value_usd": w.value_usd,
                              "tx_hash": w.tx_hash, "tx_type": w.tx_type} for w in whales]) if whales else None
        session.close()

        fdf = compute_technical_indicators(pdf)
        fdf = add_sentiment_features(fdf, sdf)
        fdf = add_onchain_features(fdf, wdf)
        avail = [c for c in FEATURE_COLS if c in fdf.columns]
        fdf = fdf.dropna(subset=avail)
        return fdf, avail

    def _get_xgb_prediction(self, coin: str) -> dict:
        """XGBoost direction prediction using the latest single-row feature vector."""
        try:
            from src.model import XGBoostPredictor
            fdf, avail = self._get_feature_rows(coin)
            if fdf is None or fdf.empty:
                return {"direction": "SIDEWAYS", "confidence": 0.5}
            last_row = fdf.tail(1)
            features = {c: float(last_row[c].iloc[0]) for c in avail}
            result = XGBoostPredictor().predict(coin, features)
            return result if "error" not in result else {"direction": "SIDEWAYS", "confidence": 0.5}
        except Exception as e:
            logger.warning(f"[PaperTrader] XGBoost prediction failed: {e}")
            return {"direction": "SIDEWAYS", "confidence": 0.5}

    def _get_lstm_prediction(self, coin: str) -> dict:
        """LSTM direction prediction using the last SEQ_LEN rows as a proper sequence."""
        try:
            from src.model import LSTMPredictor
            import numpy as np
            fdf, avail = self._get_feature_rows(coin)
            if fdf is None or fdf.empty:
                return {"direction": "SIDEWAYS", "confidence": 0.5}
            seq = fdf[avail].values.astype(np.float32)  # (n_rows, n_feat)
            result = LSTMPredictor().predict_sequence(coin, seq)
            return result if "error" not in result else {"direction": "SIDEWAYS", "confidence": 0.5}
        except Exception as e:
            logger.warning(f"[PaperTrader] LSTM prediction failed: {e}")
            return {"direction": "SIDEWAYS", "confidence": 0.5}

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

            # XGBoost prediction (single-row, fast)
            _xgb = self._get_xgb_prediction(coin)
            pred_dir  = _xgb.get("direction", "SIDEWAYS")
            pred_conf = _xgb.get("confidence", 0.5)

            # LSTM prediction (sequence-based, richer context)
            _lstm = self._get_lstm_prediction(coin)
            lstm_dir  = _lstm.get("direction", "SIDEWAYS")
            lstm_conf = _lstm.get("confidence", 0.5)

            agree = "✓" if pred_dir == lstm_dir else "✗"
            logger.info(f"[PaperTrader] SIM {side} {qty:.6f} {symbol} "
                        f"@ ${fill_price:,.4f} | "
                        f"XGB={pred_dir}({pred_conf:.0%}) "
                        f"LSTM={lstm_dir}({lstm_conf:.0%}) agree={agree}")

            self._save_trade(coin, symbol, side, qty, fill_price,
                             net_notional, confidence, order_id,
                             prediction=pred_dir, pred_confidence=pred_conf,
                             lstm_prediction=lstm_dir, lstm_pred_confidence=lstm_conf)

            return {
                "status":               "FILLED",
                "side":                 side,
                "symbol":               symbol,
                "quantity":             qty,
                "price":                fill_price,
                "market_price":         market_price,
                "notional":             notional,
                "commission":           commission,
                "orderId":              order_id,
                "prediction":           pred_dir,
                "pred_confidence":      pred_conf,
                "lstm_prediction":      lstm_dir,
                "lstm_pred_confidence": lstm_conf,
            }
        except Exception as e:
            logger.error(f"[PaperTrader] {coin} {side} failed: {e}")
            return {"status": "ERROR", "reason": str(e)}

    def _save_trade(self, coin, symbol, side, qty, price, notional, confidence, order_id,
                    prediction=None, pred_confidence=None,
                    lstm_prediction=None, lstm_pred_confidence=None):
        try:
            init_db()
            session = get_session()
            session.add(PaperTrade(
                coin=coin, symbol=symbol, side=side, quantity=qty,
                entry_price=price, notional_usd=notional,
                confidence=confidence, order_id=order_id,
                signal_source="MANUAL", status="OPEN",
                prediction=prediction, pred_confidence=pred_confidence,
                lstm_prediction=lstm_prediction, lstm_pred_confidence=lstm_pred_confidence,
            ))
            session.commit()
            session.close()
        except Exception as e:
            logger.warning(f"[PaperTrader] DB save failed: {e}")

    def auto_close_open_trades(self, hold_hours: int = 4) -> int:
        """
        Close any open trade older than hold_hours at the current live price.
        Returns number of trades closed.
        """
        try:
            init_db()
            session = get_session()
            cutoff = datetime.datetime.now() - datetime.timedelta(hours=hold_hours)
            open_trades = session.query(PaperTrade).filter(
                PaperTrade.status == "OPEN",
                PaperTrade.timestamp <= cutoff,
            ).all()

            closed = 0
            for trade in open_trades:
                try:
                    symbol = trade.symbol or f"{trade.coin}USDT"
                    exit_price = self.get_price(symbol)

                    # Apply slippage on exit (adverse direction)
                    slip = SLIPPAGE_PCT
                    if trade.side == "BUY":
                        exit_fill = exit_price * (1 - slip)
                        pnl_usd = (exit_fill - trade.entry_price) * trade.quantity
                    else:  # SELL
                        exit_fill = exit_price * (1 + slip)
                        pnl_usd = (trade.entry_price - exit_fill) * trade.quantity

                    # Deduct exit commission
                    pnl_usd -= (trade.notional_usd * COMMISSION_PCT)
                    pnl_pct = (pnl_usd / trade.notional_usd) * 100 if trade.notional_usd else 0

                    trade.exit_price = round(exit_fill, 6)
                    trade.pnl_usd    = round(pnl_usd, 4)
                    trade.pnl_pct    = round(pnl_pct, 4)
                    trade.status     = "CLOSED"
                    closed += 1
                    logger.info(f"[PaperTrader] Auto-closed {trade.side} {trade.coin} "
                                f"entry={trade.entry_price:.4f} exit={exit_fill:.4f} "
                                f"pnl=${pnl_usd:.2f} ({pnl_pct:.2f}%)")
                except Exception as e:
                    logger.warning(f"[PaperTrader] Failed to close trade {trade.id}: {e}")

            session.commit()
            session.close()
            return closed
        except Exception as e:
            logger.error(f"[PaperTrader] auto_close failed: {e}")
            return 0

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
                "time":            t.timestamp.strftime("%m/%d %H:%M"),
                "coin":            t.coin,
                "side":            t.side,
                "qty":             t.quantity,
                "entry":           t.entry_price,
                "exit":            t.exit_price,
                "notional":        t.notional_usd,
                "pnl_usd":         t.pnl_usd,
                "pnl_pct":         t.pnl_pct,
                "confidence":      t.confidence,
                "source":          t.signal_source,
                "status":          t.status,
                "prediction":           t.prediction,
                "pred_confidence":      t.pred_confidence,
                "lstm_prediction":      t.lstm_prediction,
                "lstm_pred_confidence": t.lstm_pred_confidence,
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
