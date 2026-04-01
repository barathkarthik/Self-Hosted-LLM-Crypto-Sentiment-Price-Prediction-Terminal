"""
Price Prediction Module
Primary:     Facebook Prophet — fast (~30s train), CPU-friendly
Alternative: XGBoost classifier — uses all 27 engineered features
"""

import os, pickle, logging, datetime, json
import pandas as pd
import numpy as np

logger = logging.getLogger("Model")

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import MODEL_SAVE_PATH, COINS, FEATURE_MANIFEST_PATH
from src.database import get_session, PriceData, SentimentSnapshot, WhaleTransaction
from src.feature_engineering import (
    compute_technical_indicators, add_sentiment_features,
    add_onchain_features, create_targets, FEATURE_COLS,
)

os.makedirs(MODEL_SAVE_PATH, exist_ok=True)


# ═══════════════════════════════════════════════
#  PROPHET (Time-Series)
# ═══════════════════════════════════════════════
class ProphetPredictor:
    def __init__(self):
        self.models = {}
        try:
            from prophet import Prophet  # noqa
            self._Prophet = Prophet
            self.available = True
        except ImportError:
            self.available = False
            logger.warning("[Prophet] not installed — pip install prophet")

    def train(self, coin: str, df: pd.DataFrame) -> dict:
        if not self.available:
            return {"error": "prophet not installed"}
        pdf = df[["timestamp", "close"]].rename(columns={"timestamp": "ds", "close": "y"}).dropna()
        if len(pdf) < 100:
            return {"error": f"only {len(pdf)} rows"}
        split = int(len(pdf) * 0.8)
        m = self._Prophet(daily_seasonality=True, weekly_seasonality=True, changepoint_prior_scale=0.05)
        m.fit(pdf.iloc[:split])
        fcast = m.predict(m.make_future_dataframe(periods=len(pdf) - split, freq="15min"))
        pred_d = np.sign(np.diff(fcast.iloc[split:]["yhat"].values))
        act_d = np.sign(np.diff(pdf.iloc[split:]["y"].values))
        n = min(len(pred_d), len(act_d))
        acc = float(np.mean(pred_d[:n] == act_d[:n]))
        self.models[coin] = m
        with open(os.path.join(MODEL_SAVE_PATH, f"prophet_{coin}.pkl"), "wb") as f:
            pickle.dump(m, f)
        logger.info(f"[Prophet] {coin}: {acc:.1%} directional accuracy")
        return {"coin": coin, "directional_accuracy": acc, "model": "prophet", "train_size": split}

    def predict(self, coin: str, horizon_hours: int = 4) -> dict:
        m = self.models.get(coin)
        if not m:
            p = os.path.join(MODEL_SAVE_PATH, f"prophet_{coin}.pkl")
            if os.path.exists(p):
                with open(p, "rb") as f:
                    m = pickle.load(f)
                self.models[coin] = m
        if not m:
            return {"error": f"no model for {coin}"}
        periods = horizon_hours * 4
        fcast = m.predict(m.make_future_dataframe(periods=periods, freq="15min"))
        last = fcast.iloc[-(periods + 1)]["yhat"]
        pred = fcast.iloc[-1]["yhat"]
        chg = ((pred - last) / last) * 100
        d = "UP" if chg > 0.5 else "DOWN" if chg < -0.5 else "SIDEWAYS"
        return {"coin": coin, "direction": d, "change_pct": float(chg),
                "confidence": min(abs(chg) / 5, 1.0), "horizon": f"{horizon_hours}h", "model": "prophet"}


# ═══════════════════════════════════════════════
#  XGBOOST (Feature-based classifier)
# ═══════════════════════════════════════════════
class XGBoostPredictor:
    def __init__(self):
        self.models = {}
        try:
            import xgboost  # noqa
            self.xgb = xgboost
            self.available = True
        except ImportError:
            self.available = False
            logger.warning("[XGBoost] not installed — pip install xgboost")

    def train(self, coin: str, df: pd.DataFrame, feat_cols: list, target: str = "target_4h") -> dict:
        if not self.available:
            return {"error": "xgboost not installed"}
        clean = df.dropna(subset=feat_cols + [target])
        if len(clean) < 200:
            return {"error": f"only {len(clean)} rows"}
        X, y = clean[feat_cols].values, clean[target].values
        s = int(len(X) * 0.8)
        m = self.xgb.XGBClassifier(n_estimators=200, max_depth=6, learning_rate=0.05,
                                     eval_metric="logloss", use_label_encoder=False)
        m.fit(X[:s], y[:s], eval_set=[(X[s:], y[s:])], verbose=False)
        acc = float(m.score(X[s:], y[s:]))
        self.models[coin] = {"model": m, "features": feat_cols}
        with open(os.path.join(MODEL_SAVE_PATH, f"xgb_{coin}.pkl"), "wb") as f:
            pickle.dump(self.models[coin], f)
        # Save feature manifest for alignment at inference time (ported from SRL)
        with open(FEATURE_MANIFEST_PATH, "w") as f:
            json.dump(feat_cols, f, indent=2)
        logger.info(f"[XGBoost] {coin}: {acc:.1%} accuracy | manifest saved ({len(feat_cols)} cols)")
        return {"coin": coin, "directional_accuracy": acc, "model": "xgboost"}

    def predict(self, coin: str, features: dict) -> dict:
        data = self.models.get(coin)
        if not data:
            p = os.path.join(MODEL_SAVE_PATH, f"xgb_{coin}.pkl")
            if os.path.exists(p):
                with open(p, "rb") as f:
                    data = pickle.load(f)
                self.models[coin] = data
        if not data:
            return {"error": f"no model for {coin}"}
        fc = data["features"]
        # Align to feature manifest if available (prevents shape mismatch — ported from SRL)
        if FEATURE_MANIFEST_PATH.exists():
            try:
                with open(FEATURE_MANIFEST_PATH) as mf:
                    expected = json.load(mf)
                # Use manifest columns: fill missing with 0, drop extras, reorder
                aligned = {c: features.get(c, 0.0) for c in expected}
                X = np.array([[aligned[c] for c in expected]])
            except Exception as e:
                logger.warning(f"[XGBoost] manifest alignment failed ({e}), using model features")
                X = np.array([[features.get(c, 0) for c in fc]])
        else:
            X = np.array([[features.get(c, 0) for c in fc]])
        proba = data["model"].predict_proba(X)[0]
        d = "UP" if proba[1] > 0.55 else "DOWN" if proba[0] > 0.55 else "SIDEWAYS"
        return {"coin": coin, "direction": d, "confidence": float(max(proba)), "model": "xgboost"}


# ═══════════════════════════════════════════════
#  UNIFIED PREDICTION ENGINE
# ═══════════════════════════════════════════════
class PredictionEngine:
    def __init__(self):
        self.prophet = ProphetPredictor()
        self.xgboost = XGBoostPredictor()

    def train_all(self, coin: str) -> dict:
        session = get_session()
        prices = session.query(PriceData).filter(
            PriceData.coin == coin, PriceData.interval == "15m"
        ).order_by(PriceData.timestamp).all()
        if not prices:
            session.close()
            return {"error": "no price data"}
        pdf = pd.DataFrame([{"timestamp": p.timestamp, "open": p.open, "high": p.high,
                             "low": p.low, "close": p.close, "volume": p.volume} for p in prices])
        sents = session.query(SentimentSnapshot).filter(SentimentSnapshot.coin == coin).all()
        sdf = pd.DataFrame([{"timestamp": s.timestamp, "avg_score": s.avg_score,
                              "sample_count": s.sample_count} for s in sents]) if sents else None
        whales = session.query(WhaleTransaction).filter(WhaleTransaction.coin == coin).all()
        wdf = pd.DataFrame([{"timestamp": w.timestamp, "value_usd": w.value_usd,
                              "tx_hash": w.tx_hash, "tx_type": w.tx_type} for w in whales]) if whales else None
        session.close()
        results = {}
        if self.prophet.available:
            results["prophet"] = self.prophet.train(coin, pdf)
        if self.xgboost.available:
            fdf = compute_technical_indicators(pdf)
            fdf = add_sentiment_features(fdf, sdf)
            fdf = add_onchain_features(fdf, wdf)
            fdf = create_targets(fdf)
            avail = [c for c in FEATURE_COLS if c in fdf.columns]
            fdf = fdf.dropna(subset=avail + ["target_4h"])
            results["xgboost"] = self.xgboost.train(coin, fdf, avail)
        return results

    def predict(self, coin: str, horizon_hours: int = 4) -> dict:
        if self.prophet.available and coin in self.prophet.models:
            return self.prophet.predict(coin, horizon_hours)
        return {"coin": coin, "direction": "UNKNOWN", "confidence": 0.0}


# ═══════════════════════════════════════════════
#  Backward compatibility for your existing app.py
# ═══════════════════════════════════════════════
def train_model(df: pd.DataFrame):
    """Simple sklearn model for quick demo — works with your btc_data.csv."""
    from sklearn.ensemble import GradientBoostingClassifier
    feature_cols = [c for c in ["momentum", "rolling_mean", "rsi", "macd",
                                 "bb_position", "volume_ratio", "returns_1"]
                    if c in df.columns]
    if not feature_cols:
        feature_cols = ["momentum", "rolling_mean"]
    target = "target" if "target" in df.columns else "target_4h"
    if target not in df.columns:
        df["target"] = (df["price"].shift(-1) > df["price"]).astype(int) \
            if "price" in df.columns else (df["close"].shift(-1) > df["close"]).astype(int)
        target = "target"
    clean = df.dropna(subset=feature_cols + [target])
    X, y = clean[feature_cols].values, clean[target].values
    m = GradientBoostingClassifier(n_estimators=100, max_depth=4)
    m.fit(X, y)
    return m
