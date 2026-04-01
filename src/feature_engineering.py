"""
Feature Engineering — transforms raw price + sentiment + on-chain data
into 27 ML-ready features for the prediction model.
"""

import pandas as pd
import numpy as np
import logging

logger = logging.getLogger("FeatureEng")


def compute_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add 20+ technical indicators to price OHLCV data."""
    df = df.copy().sort_values("timestamp").reset_index(drop=True)

    # Moving Averages
    df["sma_7"] = df["close"].rolling(7).mean()
    df["sma_25"] = df["close"].rolling(25).mean()
    df["sma_99"] = df["close"].rolling(99).mean()
    df["ema_12"] = df["close"].ewm(span=12).mean()
    df["ema_26"] = df["close"].ewm(span=26).mean()

    # MACD
    df["macd"] = df["ema_12"] - df["ema_26"]
    df["macd_signal"] = df["macd"].ewm(span=9).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]

    # RSI (14-period)
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df["rsi"] = 100 - (100 / (1 + gain / (loss + 1e-10)))

    # Bollinger Bands
    bb_mid = df["close"].rolling(20).mean()
    bb_std = df["close"].rolling(20).std()
    df["bb_upper"] = bb_mid + 2 * bb_std
    df["bb_lower"] = bb_mid - 2 * bb_std
    df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / (bb_mid + 1e-10)
    df["bb_position"] = (df["close"] - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"] + 1e-10)

    # Volume
    df["volume_sma"] = df["volume"].rolling(20).mean()
    df["volume_ratio"] = df["volume"] / (df["volume_sma"] + 1e-10)

    # Returns
    df["returns_1"] = df["close"].pct_change(1)
    df["returns_4"] = df["close"].pct_change(4)
    df["returns_24"] = df["close"].pct_change(24)
    df["returns_96"] = df["close"].pct_change(96)

    # Volatility
    df["volatility_24"] = df["returns_1"].rolling(24).std()
    df["volatility_96"] = df["returns_1"].rolling(96).std()

    # ATR
    tr = pd.DataFrame({
        "hl": df["high"] - df["low"],
        "hc": abs(df["high"] - df["close"].shift(1)),
        "lc": abs(df["low"] - df["close"].shift(1)),
    }).max(axis=1)
    df["atr_14"] = tr.rolling(14).mean()

    # Time features (cyclical)
    if pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
        h = df["timestamp"].dt.hour
        df["hour_sin"] = np.sin(2 * np.pi * h / 24)
        df["hour_cos"] = np.cos(2 * np.pi * h / 24)
        d = df["timestamp"].dt.dayofweek
        df["dow_sin"] = np.sin(2 * np.pi * d / 7)
        df["dow_cos"] = np.cos(2 * np.pi * d / 7)

    return df


def add_sentiment_features(df: pd.DataFrame, sentiment_df: pd.DataFrame) -> pd.DataFrame:
    """Merge sentiment scores into price data (time-aligned)."""
    df = df.copy()
    if sentiment_df is None or sentiment_df.empty:
        df["sentiment_avg"] = 0.5
        df["sentiment_momentum"] = 0.0
        df["sentiment_volume"] = 0
        return df

    df = df.sort_values("timestamp")
    sentiment_df = sentiment_df.sort_values("timestamp")

    df = pd.merge_asof(
        df, sentiment_df[["timestamp", "avg_score", "sample_count"]],
        on="timestamp", direction="backward",
    )
    df.rename(columns={"avg_score": "sentiment_avg", "sample_count": "sentiment_volume"}, inplace=True)
    df["sentiment_momentum"] = df["sentiment_avg"].diff(4)
    df[["sentiment_avg", "sentiment_momentum", "sentiment_volume"]] = \
        df[["sentiment_avg", "sentiment_momentum", "sentiment_volume"]].fillna(
            {"sentiment_avg": 0.5, "sentiment_momentum": 0.0, "sentiment_volume": 0})
    return df


def add_onchain_features(df: pd.DataFrame, whale_df: pd.DataFrame) -> pd.DataFrame:
    """Add whale net-flow and tx count features."""
    df = df.copy()
    if whale_df is None or whale_df.empty:
        df["whale_net_flow"] = 0.0
        df["whale_tx_count"] = 0
        return df

    wdf = whale_df.copy()
    wdf["hour"] = wdf["timestamp"].dt.floor("H")
    wdf["signed"] = wdf.apply(
        lambda r: r["value_usd"] if r["tx_type"] == "ACCUMULATION"
        else -r["value_usd"] if r["tx_type"] == "DISTRIBUTION" else 0, axis=1)
    hourly = wdf.groupby("hour").agg(
        whale_net_flow=("signed", "sum"), whale_tx_count=("tx_hash", "count")
    ).reset_index().rename(columns={"hour": "timestamp"})

    df["_hr"] = df["timestamp"].dt.floor("H")
    df = df.merge(hourly, left_on="_hr", right_on="timestamp",
                  how="left", suffixes=("", "_wh"))
    df.drop(columns=["_hr", "timestamp_wh"], errors="ignore", inplace=True)
    df["whale_net_flow"] = df["whale_net_flow"].fillna(0)
    df["whale_tx_count"] = df["whale_tx_count"].fillna(0).astype(int)
    return df


def create_targets(df: pd.DataFrame) -> pd.DataFrame:
    """Create UP/DOWN targets for 1h, 4h, 24h horizons."""
    df = df.copy()
    for label, periods in {"target_1h": 4, "target_4h": 16, "target_24h": 96}.items():
        future = df["close"].shift(-periods)
        df[f"{label}_return"] = (future - df["close"]) / (df["close"] + 1e-10)
        df[label] = (future > df["close"]).astype(int)
    return df


FEATURE_COLS = [
    "sma_7", "sma_25", "ema_12", "ema_26",
    "macd", "macd_signal", "macd_hist",
    "rsi", "bb_width", "bb_position", "volume_ratio",
    "returns_1", "returns_4", "returns_24", "returns_96",
    "volatility_24", "volatility_96", "atr_14",
    "hour_sin", "hour_cos", "dow_sin", "dow_cos",
    "sentiment_avg", "sentiment_momentum", "sentiment_volume",
    "whale_net_flow", "whale_tx_count",
]


def prepare_training_data(price_df, sentiment_df=None, whale_df=None):
    """Full pipeline: raw → features + targets."""
    df = compute_technical_indicators(price_df)
    df = add_sentiment_features(df, sentiment_df)
    df = add_onchain_features(df, whale_df)
    df = create_targets(df)
    avail = [c for c in FEATURE_COLS if c in df.columns]
    df = df.dropna(subset=avail + ["target_1h"]).reset_index(drop=True)
    logger.info(f"Training data: {len(df)} rows, {len(avail)} features")
    return df, avail
