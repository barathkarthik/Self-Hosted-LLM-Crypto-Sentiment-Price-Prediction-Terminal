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

_MODEL_STATS_FILE = os.path.join(MODEL_SAVE_PATH, "model_stats.json")


def _save_model_stats(coin: str, model_type: str, accuracy: float, variance: float):
    """Persist accuracy and variance to models/model_stats.json for dashboard display."""
    try:
        stats = {}
        if os.path.exists(_MODEL_STATS_FILE):
            with open(_MODEL_STATS_FILE) as f:
                stats = json.load(f)
        key = f"{coin}_{model_type}"
        stats[key] = {
            "coin": coin, "model": model_type,
            "accuracy": round(accuracy, 4),
            "variance": round(variance, 4),
            "trained_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        with open(_MODEL_STATS_FILE, "w") as f:
            json.dump(stats, f, indent=2)
    except Exception as e:
        logger.warning(f"[stats] could not save model stats: {e}")


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
        variance = float(np.var(fcast.iloc[split:]["yhat"].pct_change().dropna().values))
        self.models[coin] = m
        with open(os.path.join(MODEL_SAVE_PATH, f"prophet_{coin}.pkl"), "wb") as f:
            pickle.dump(m, f)
        _save_model_stats(coin, "prophet", acc, variance)
        logger.info(f"[Prophet] {coin}: {acc:.1%} acc, var={variance:.6f}")
        return {"coin": coin, "directional_accuracy": acc, "variance": variance, "model": "prophet", "train_size": split}

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

    def _fit_one(self, X_train, y_train, X_val, y_val):
        m = self.xgb.XGBClassifier(
            n_estimators=500,
            max_depth=4,
            learning_rate=0.03,
            subsample=0.8,
            colsample_bytree=0.8,
            min_child_weight=5,
            gamma=0.1,
            reg_alpha=0.1,
            reg_lambda=1.5,
            eval_metric="logloss",
            early_stopping_rounds=30,
        )
        m.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
        proba_val = m.predict_proba(X_val)[:, 1]
        return m, float(m.score(X_val, y_val)), float(np.var(proba_val))

    def train(self, coin: str, df: pd.DataFrame, feat_cols: list, target: str = "target_4h") -> dict:
        if not self.available:
            return {"error": "xgboost not installed"}

        best_m, best_acc, best_var, best_target = None, 0.0, 0.0, target
        for t in ["target_1h", "target_4h", "target_24h"]:
            if t not in df.columns:
                continue
            clean = df.dropna(subset=feat_cols + [t])
            if len(clean) < 200:
                continue
            X, y = clean[feat_cols].values, clean[t].values
            s = int(len(X) * 0.8)
            m, acc, var = self._fit_one(X[:s], y[:s], X[s:], y[s:])
            logger.info(f"[XGBoost] {coin} {t}: {acc:.1%} acc, var={var:.4f}")
            if acc > best_acc:
                best_acc, best_var, best_m, best_target = acc, var, m, t

        if best_m is None:
            return {"error": "training failed for all targets"}

        self.models[coin] = {"model": best_m, "features": feat_cols}
        with open(os.path.join(MODEL_SAVE_PATH, f"xgb_{coin}.pkl"), "wb") as f:
            pickle.dump(self.models[coin], f)
        with open(FEATURE_MANIFEST_PATH, "w") as f:
            json.dump(feat_cols, f, indent=2)
        _save_model_stats(coin, "xgboost", best_acc, best_var)
        logger.info(f"[XGBoost] {coin}: best={best_target} {best_acc:.1%} var={best_var:.4f} | manifest saved ({len(feat_cols)} cols)")
        return {"coin": coin, "directional_accuracy": best_acc, "variance": best_var, "model": "xgboost", "best_target": best_target}

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
#  LSTM (Sequential Deep Learning)
# ═══════════════════════════════════════════════
class LSTMPredictor:
    SEQ_LEN = 20    # 20 × 15min candles = 5 hours of context
    HIDDEN  = 64
    LAYERS  = 2
    DROPOUT = 0.2
    EPOCHS  = 60
    LR      = 1e-3
    PATIENCE = 8

    def __init__(self):
        try:
            import torch
            import torch.nn as nn
            self._torch = torch
            self._nn    = nn
            self.available = True
        except ImportError:
            self.available = False
            logger.warning("[LSTM] torch not installed — pip install torch")
        self.models = {}

    def _build_net(self, n_feat):
        nn = self._nn
        class _Net(nn.Module):
            def __init__(self, n, hidden, layers, drop):
                super().__init__()
                self.lstm = nn.LSTM(n, hidden, num_layers=layers,
                                    batch_first=True, dropout=drop if layers > 1 else 0)
                self.drop = nn.Dropout(drop)
                self.fc   = nn.Linear(hidden, 2)
            def forward(self, x):
                _, (h, _) = self.lstm(x)
                return self.fc(self.drop(h[-1]))
        return _Net(n_feat, self.HIDDEN, self.LAYERS, self.DROPOUT)

    def train(self, coin: str, df: pd.DataFrame, feat_cols: list, target: str = "target_4h") -> dict:
        if not self.available:
            return {"error": "torch not installed"}
        torch = self._torch

        best_m, best_acc, best_var, best_target = None, 0.0, 0.0, target
        best_mean = best_std = None

        for t in ["target_1h", "target_4h", "target_24h"]:
            if t not in df.columns:
                continue
            clean = df.dropna(subset=feat_cols + [t])
            if len(clean) < self.SEQ_LEN + 60:
                continue

            X_all = clean[feat_cols].values.astype(np.float32)
            y_all = clean[t].values.astype(np.int64)

            # Per-feature normalisation (stored for inference)
            mean = X_all.mean(axis=0)
            std  = X_all.std(axis=0) + 1e-8
            X_norm = (X_all - mean) / std

            # Build rolling-window sequences
            Xs = np.array([X_norm[i - self.SEQ_LEN:i] for i in range(self.SEQ_LEN, len(X_norm))],
                          dtype=np.float32)
            ys = np.array(y_all[self.SEQ_LEN:], dtype=np.int64)

            s = int(len(Xs) * 0.8)
            X_tr = torch.tensor(Xs[:s]);  y_tr = torch.tensor(ys[:s])
            X_val= torch.tensor(Xs[s:]); y_val= torch.tensor(ys[s:])

            net  = self._build_net(len(feat_cols))
            opt  = torch.optim.Adam(net.parameters(), lr=self.LR, weight_decay=1e-4)
            crit = self._nn.CrossEntropyLoss()
            sched= torch.optim.lr_scheduler.StepLR(opt, step_size=20, gamma=0.5)

            best_val, patience_cnt = float("inf"), 0
            best_state, best_epoch_acc = None, 0.0

            for _ in range(self.EPOCHS):
                net.train()
                opt.zero_grad()
                crit(net(X_tr), y_tr).backward()
                torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0)
                opt.step(); sched.step()

                net.eval()
                with torch.no_grad():
                    val_loss = crit(net(X_val), y_val).item()
                    val_acc  = float((net(X_val).argmax(1) == y_val).float().mean())
                if val_loss < best_val:
                    best_val, patience_cnt = val_loss, 0
                    best_state     = {k: v.clone() for k, v in net.state_dict().items()}
                    best_epoch_acc = val_acc
                else:
                    patience_cnt += 1
                    if patience_cnt >= self.PATIENCE:
                        break

            net.load_state_dict(best_state)
            net.eval()
            with torch.no_grad():
                proba_val = torch.softmax(net(X_val), dim=1).numpy()
                var = float(np.var(proba_val[:, 1]))

            logger.info(f"[LSTM] {coin} {t}: {best_epoch_acc:.1%} acc, var={var:.4f}")
            if best_epoch_acc > best_acc:
                best_acc, best_var, best_m, best_target = best_epoch_acc, var, net, t
                best_mean, best_std = mean, std

        if best_m is None:
            return {"error": "training failed — insufficient data"}

        save_path = os.path.join(MODEL_SAVE_PATH, f"lstm_{coin}.pth")
        torch.save({
            "state_dict": best_m.state_dict(),
            "features":   feat_cols,
            "mean":       best_mean,
            "std":        best_std,
            "n_feat":     len(feat_cols),
        }, save_path)
        self.models[coin] = {"net": best_m, "features": feat_cols,
                             "mean": best_mean, "std": best_std}
        _save_model_stats(coin, "lstm", best_acc, best_var)
        logger.info(f"[LSTM] {coin}: best={best_target} {best_acc:.1%} | saved {save_path}")
        return {"coin": coin, "directional_accuracy": best_acc, "variance": best_var,
                "model": "lstm", "best_target": best_target}

    def _load(self, coin: str) -> dict | None:
        data = self.models.get(coin)
        if not data:
            p = os.path.join(MODEL_SAVE_PATH, f"lstm_{coin}.pth")
            if os.path.exists(p):
                ckpt = self._torch.load(p, map_location="cpu", weights_only=False)
                net  = self._build_net(ckpt["n_feat"])
                net.load_state_dict(ckpt["state_dict"])
                net.eval()
                data = {"net": net, "features": ckpt["features"],
                        "mean": ckpt["mean"], "std": ckpt["std"]}
                self.models[coin] = data
        return data

    def predict(self, coin: str, features: dict) -> dict:
        """Single-row predict — tiles the row to form a minimal sequence."""
        if not self.available:
            return {"error": "torch not installed"}
        data = self._load(coin)
        if not data:
            return {"error": f"no LSTM model for {coin}"}
        feat_cols = data["features"]
        row = np.array([[features.get(c, 0.0) for c in feat_cols]], dtype=np.float32)
        row_norm = (row - data["mean"]) / data["std"]
        seq = np.tile(row_norm, (self.SEQ_LEN, 1))[np.newaxis]  # (1, SEQ_LEN, n_feat)
        return self._infer(coin, data, seq)

    def predict_sequence(self, coin: str, feature_rows: np.ndarray) -> dict:
        """Proper sequential predict — feature_rows shape: (≥SEQ_LEN, n_feat)."""
        if not self.available:
            return {"error": "torch not installed"}
        data = self._load(coin)
        if not data:
            return {"error": f"no LSTM model for {coin}"}
        feat_cols = data["features"]
        n = min(len(feature_rows), self.SEQ_LEN)
        rows = feature_rows[-n:] if n == self.SEQ_LEN else np.pad(
            feature_rows, ((self.SEQ_LEN - n, 0), (0, 0)), mode="edge")
        rows_norm = (rows.astype(np.float32) - data["mean"]) / data["std"]
        seq = rows_norm[np.newaxis]  # (1, SEQ_LEN, n_feat)
        return self._infer(coin, data, seq)

    def _infer(self, coin, data, seq_np):
        torch = self._torch
        with torch.no_grad():
            proba = torch.softmax(data["net"](torch.tensor(seq_np)), dim=1).numpy()[0]
        d = "UP" if proba[1] > 0.55 else "DOWN" if proba[0] > 0.55 else "SIDEWAYS"
        return {"coin": coin, "direction": d, "confidence": float(max(proba)), "model": "lstm"}


# ═══════════════════════════════════════════════
#  UNIFIED PREDICTION ENGINE
# ═══════════════════════════════════════════════
class PredictionEngine:
    def __init__(self):
        self.prophet = ProphetPredictor()
        self.xgboost = XGBoostPredictor()
        self.lstm    = LSTMPredictor()

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
        if self.xgboost.available or self.lstm.available:
            fdf = compute_technical_indicators(pdf)
            fdf = add_sentiment_features(fdf, sdf)
            fdf = add_onchain_features(fdf, wdf)
            fdf = create_targets(fdf)
            avail = [c for c in FEATURE_COLS if c in fdf.columns]
            fdf = fdf.dropna(subset=avail + ["target_4h"])
            if self.xgboost.available:
                results["xgboost"] = self.xgboost.train(coin, fdf, avail)
            if self.lstm.available:
                results["lstm"] = self.lstm.train(coin, fdf, avail)
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
