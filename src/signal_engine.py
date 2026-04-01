"""
Trading Signal Generator
Combines sentiment + prediction + on-chain → BUY / SELL / HOLD
Each signal includes confidence score and human-readable reasoning.
"""

import logging, datetime

logger = logging.getLogger("SignalEngine")

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import BULLISH_THRESHOLD, BEARISH_THRESHOLD, WHALE_ALERT_MIN_USD, COINS
from src.database import get_session, Signal, SentimentSnapshot, WhaleTransaction


class SignalGenerator:
    """
    Signal Logic:
    BUY  = sentiment > 0.7 AND prediction UP AND whales accumulating  (≥2 of 3)
    SELL = sentiment < 0.3 AND prediction DOWN AND whales distributing (≥2 of 3)
    HOLD = everything else
    """

    def __init__(self, prediction_engine=None, sentiment_engine=None):
        self.prediction_engine = prediction_engine
        self.sentiment_engine = sentiment_engine

    def get_whale_activity(self, coin: str, hours: int = 4) -> dict:
        session = get_session()
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=hours)
        txns = session.query(WhaleTransaction).filter(
            WhaleTransaction.coin == coin,
            WhaleTransaction.timestamp >= cutoff,
            WhaleTransaction.value_usd >= WHALE_ALERT_MIN_USD,
        ).all()
        session.close()
        if not txns:
            return {"status": "NEUTRAL", "net_flow_usd": 0, "tx_count": 0,
                    "accumulation_usd": 0, "distribution_usd": 0}
        acc = sum(t.value_usd for t in txns if t.tx_type == "ACCUMULATION")
        dist = sum(t.value_usd for t in txns if t.tx_type == "DISTRIBUTION")
        net = acc - dist
        status = "ACCUMULATING" if net > 500_000 else "DISTRIBUTING" if net < -500_000 else "NEUTRAL"
        return {"status": status, "net_flow_usd": net, "tx_count": len(txns),
                "accumulation_usd": acc, "distribution_usd": dist}

    def get_latest_sentiment(self, coin: str) -> dict:
        session = get_session()
        snap = session.query(SentimentSnapshot).filter(
            SentimentSnapshot.coin == coin
        ).order_by(SentimentSnapshot.timestamp.desc()).first()
        session.close()
        if not snap:
            return {"avg_score": 0.5, "label": "NEUTRAL", "sample_count": 0}
        return {"avg_score": snap.avg_score, "label": snap.label, "sample_count": snap.sample_count}

    def generate_signal(self, coin: str) -> dict:
        sentiment = self.get_latest_sentiment(coin)
        ss = sentiment["avg_score"]

        prediction = (self.prediction_engine.predict(coin, 4)
                      if self.prediction_engine else
                      {"direction": "SIDEWAYS", "confidence": 0.0})
        pd_dir = prediction.get("direction", "SIDEWAYS")
        pd_conf = prediction.get("confidence", 0.0)

        whale = self.get_whale_activity(coin)
        ws = whale["status"]

        bull, bear, reasons = 0, 0, []

        # Sentiment
        if ss >= BULLISH_THRESHOLD:
            bull += 1
            reasons.append(f"Sentiment bullish ({ss:.2f}, {sentiment['sample_count']} samples)")
        elif ss <= BEARISH_THRESHOLD:
            bear += 1
            reasons.append(f"Sentiment bearish ({ss:.2f}, {sentiment['sample_count']} samples)")
        else:
            reasons.append(f"Sentiment neutral ({ss:.2f})")

        # Prediction
        if pd_dir == "UP":
            bull += 1; reasons.append(f"Model → UP ({pd_conf:.0%})")
        elif pd_dir == "DOWN":
            bear += 1; reasons.append(f"Model → DOWN ({pd_conf:.0%})")
        else:
            reasons.append("Model → SIDEWAYS")

        # Whales
        if ws == "ACCUMULATING":
            bull += 1; reasons.append(f"Whales accumulating (+${whale['net_flow_usd']:,.0f})")
        elif ws == "DISTRIBUTING":
            bear += 1; reasons.append(f"Whales distributing (-${abs(whale['net_flow_usd']):,.0f})")
        else:
            reasons.append(f"Whale activity neutral ({whale['tx_count']} txns)")

        # Decision
        if bull >= 2:
            sig_type, conf = "BUY", (ss + pd_conf + (1.0 if ws == "ACCUMULATING" else 0.5)) / 3
        elif bear >= 2:
            sig_type, conf = "SELL", ((1 - ss) + pd_conf + (1.0 if ws == "DISTRIBUTING" else 0.5)) / 3
        else:
            sig_type, conf = "HOLD", 0.5

        signal = {
            "coin": coin, "signal_type": sig_type,
            "confidence": round(conf, 3),
            "sentiment_score": ss,
            "prediction_direction": pd_dir,
            "prediction_confidence": pd_conf,
            "whale_activity": ws,
            "reasoning": " | ".join(reasons),
        }
        self._save(signal)
        return signal

    def _save(self, s: dict):
        session = get_session()
        session.add(Signal(
            coin=s["coin"], signal_type=s["signal_type"], confidence=s["confidence"],
            sentiment_score=s["sentiment_score"], prediction_direction=s["prediction_direction"],
            prediction_confidence=s["prediction_confidence"], whale_activity=s["whale_activity"],
            reasoning=s["reasoning"]))
        session.commit()
        session.close()

    def generate_all_signals(self) -> dict:
        sigs = {}
        for coin in COINS:
            try:
                sigs[coin] = self.generate_signal(coin)
            except Exception as e:
                logger.error(f"[Signal] {coin}: {e}")
                sigs[coin] = {"coin": coin, "signal_type": "ERROR", "reasoning": str(e)}
        return sigs

    def get_signal_history(self, coin: str = None, limit: int = 50) -> list[dict]:
        session = get_session()
        q = session.query(Signal).order_by(Signal.timestamp.desc())
        if coin:
            q = q.filter(Signal.coin == coin)
        sigs = q.limit(limit).all()
        session.close()
        return [{"coin": s.coin, "timestamp": s.timestamp.isoformat(),
                 "signal_type": s.signal_type, "confidence": s.confidence,
                 "reasoning": s.reasoning} for s in sigs]


# Backward compatibility
def generate_signal(prediction: int, sentiment_score: float) -> str:
    """Simple signal for your existing app.py."""
    if prediction == 1 and sentiment_score > 0.6:
        return "🟢 STRONG BUY"
    elif prediction == 1:
        return "🟡 WEAK BUY"
    elif prediction == 0 and sentiment_score < 0.4:
        return "🔴 STRONG SELL"
    elif prediction == 0:
        return "🟡 WEAK SELL"
    return "⚪ HOLD"
