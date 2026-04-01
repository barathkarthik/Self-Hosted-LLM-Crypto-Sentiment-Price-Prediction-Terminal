"""
Tests — validate all components work.
Run: python -m pytest tests/ -v   OR   python tests/test_components.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_config():
    from config import COINS, BULLISH_THRESHOLD, BEARISH_THRESHOLD, DATABASE_URL
    assert len(COINS) >= 5, "Must track at least 5 coins"
    assert 0 < BEARISH_THRESHOLD < BULLISH_THRESHOLD < 1
    assert "sqlite" in DATABASE_URL or "postgresql" in DATABASE_URL
    print("✅ Config OK")


def test_database():
    from src.database import init_db, get_session, PriceData, Signal
    init_db()
    session = get_session()
    assert session is not None
    # Verify tables exist by running a count query
    count = session.query(PriceData).count()
    assert count >= 0
    sig_count = session.query(Signal).count()
    assert sig_count >= 0
    session.close()
    print("✅ Database OK")


def test_feature_engineering():
    import pandas as pd
    import numpy as np
    from src.feature_engineering import compute_technical_indicators, FEATURE_COLS

    dates = pd.date_range("2025-01-01", periods=200, freq="15min")
    np.random.seed(42)
    base = 65000
    prices = base + np.cumsum(np.random.randn(200) * 100)
    df = pd.DataFrame({
        "timestamp": dates,
        "open": prices + np.random.randn(200) * 50,
        "high": prices + abs(np.random.randn(200) * 200),
        "low": prices - abs(np.random.randn(200) * 200),
        "close": prices,
        "volume": np.random.uniform(100, 1000, 200),
    })

    result = compute_technical_indicators(df)

    # Verify key indicators exist
    for col in ["rsi", "macd", "macd_signal", "bb_upper", "bb_lower",
                 "volume_ratio", "returns_1", "volatility_24", "atr_14",
                 "hour_sin", "dow_cos"]:
        assert col in result.columns, f"Missing: {col}"

    assert len(result) == 200
    assert result["rsi"].dropna().between(0, 100).all(), "RSI out of range"
    print(f"✅ Feature Engineering OK ({len([c for c in FEATURE_COLS if c in result.columns])}/{len(FEATURE_COLS)} features)")


def test_sentiment_prompt():
    from src.sentiment_engine import SENTIMENT_PROMPT
    assert "{text}" in SENTIMENT_PROMPT
    assert "BULLISH" in SENTIMENT_PROMPT
    assert "BEARISH" in SENTIMENT_PROMPT
    assert "NEUTRAL" in SENTIMENT_PROMPT
    assert "FUD" in SENTIMENT_PROMPT
    # Verify it has few-shot examples
    assert SENTIMENT_PROMPT.count('"classification"') >= 4, "Need at least 4 few-shot examples"
    print("✅ Sentiment Prompt OK")


def test_sentiment_backward_compat():
    """Test the analyze_text convenience function."""
    from src.sentiment_engine import SentimentEngine
    engine = SentimentEngine()
    # If Ollama isn't running, this will still work (returns neutral fallback)
    score, label, reason = engine.analyze_text("Bitcoin is going to the moon!")
    assert isinstance(score, float)
    assert 0 <= score <= 1
    assert label in ("BULLISH", "BEARISH", "NEUTRAL", "FUD")
    assert isinstance(reason, str)
    print(f"✅ Sentiment Engine OK (label={label}, score={score:.2f})")


def test_signal_logic():
    """Test signal generation rules."""
    from src.signal_engine import generate_signal
    # Strong buy: UP prediction + bullish sentiment
    assert "BUY" in generate_signal(1, 0.85)
    # Strong sell: DOWN prediction + bearish sentiment
    assert "SELL" in generate_signal(0, 0.15)
    # Weak buy
    assert "BUY" in generate_signal(1, 0.5)
    # Weak sell
    assert "SELL" in generate_signal(0, 0.5)
    print("✅ Signal Logic OK")


def test_backtester_metrics():
    import pandas as pd
    import numpy as np
    from src.backtester import Backtester

    bt = Backtester(initial_capital=10000)

    results_df = pd.DataFrame({
        "coin": ["BTC"] * 10,
        "signal_type": ["BUY"] * 5 + ["SELL"] * 5,
        "entry": [65000] * 10,
        "exit": [66000, 64000, 67000, 63000, 66500,
                  64000, 66000, 63000, 67000, 64500],
        "pnl_pct": [1.54, -1.54, 3.08, -3.08, 2.31, 1.54, -3.08, 3.08, -3.08, 0.77],
        "correct": [True, False, True, False, True, True, False, True, False, True],
        "confidence": [0.8] * 10,
    })

    metrics = bt._metrics(results_df)
    assert metrics["total_trades"] == 10
    assert 0 <= metrics["win_rate"] <= 1
    assert "sharpe_ratio" in metrics
    assert "max_drawdown_pct" in metrics
    assert "capital_history" in metrics
    assert len(metrics["capital_history"]) == 11  # initial + 10 trades
    print(f"✅ Backtester OK (win_rate={metrics['win_rate']:.1%}, sharpe={metrics['sharpe_ratio']:.2f})")


def test_model_backward_compat():
    """Test the train_model convenience function for existing app.py."""
    import pandas as pd
    import numpy as np

    np.random.seed(42)
    n = 300
    df = pd.DataFrame({
        "price": 65000 + np.cumsum(np.random.randn(n) * 100),
        "momentum": np.random.randn(n),
        "rolling_mean": 65000 + np.random.randn(n) * 500,
    })

    from src.model import train_model
    model = train_model(df)
    assert model is not None
    # Test prediction
    pred = model.predict([[0.5, 65000]])[0]
    assert pred in (0, 1)
    print("✅ Model backward compat OK")


def test_price_collector_structure():
    """Test PriceCollector can be instantiated."""
    from src.data_loader import PriceCollector
    pc = PriceCollector()
    assert hasattr(pc, "fetch_klines")
    assert hasattr(pc, "fetch_current_price")
    assert hasattr(pc, "fetch_historical")
    assert hasattr(pc, "collect")
    print("✅ PriceCollector OK")


def test_full_pipeline_dry_run():
    """Verify the full pipeline can be imported and instantiated."""
    from src.database import init_db
    from src.data_loader import PriceCollector, NewsCollector, WhaleCollector
    from src.sentiment_engine import SentimentEngine
    from src.model import PredictionEngine
    from src.signal_engine import SignalGenerator
    from src.backtester import Backtester

    init_db()
    pc = PriceCollector()
    nc = NewsCollector()
    wc = WhaleCollector()
    se = SentimentEngine()
    pe = PredictionEngine()
    sg = SignalGenerator(pe, se)
    bt = Backtester()

    # Verify all objects exist
    assert all([pc, nc, wc, se, pe, sg, bt])
    print("✅ Full Pipeline Instantiation OK")


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("  CRYPTO TERMINAL — COMPONENT TESTS")
    print("=" * 50 + "\n")

    tests = [
        test_config,
        test_database,
        test_feature_engineering,
        test_sentiment_prompt,
        test_signal_logic,
        test_backtester_metrics,
        test_model_backward_compat,
        test_price_collector_structure,
        test_full_pipeline_dry_run,
    ]

    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"❌ {t.__name__}: {e}")
            failed += 1

    # Sentiment engine test (may need Ollama or transformers)
    try:
        test_sentiment_backward_compat()
        passed += 1
    except Exception as e:
        print(f"⚠️  Sentiment engine (optional): {e}")

    print(f"\n{'=' * 50}")
    print(f"  Results: {passed} passed, {failed} failed")
    print(f"{'=' * 50}")

    if failed == 0:
        print("  🎉 All tests passed!")
    else:
        print("  ⚠️  Some tests failed — check errors above")
