"""
📊 Crypto Trading Intelligence Terminal — Dashboard
Run:  streamlit run app.py
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta

from config import COINS
from src.database import (
    get_session, PriceData, Signal, SentimentSnapshot,
    WhaleTransaction, RedditPost, NewsArticle, init_db,
)
from src.data_loader import PriceCollector
from src.backtester import Backtester
from src.sentiment_engine import SentimentEngine

init_db()

# ═══════════════════════════════════════════════
#  PAGE SETUP
# ═══════════════════════════════════════════════
st.set_page_config(page_title="Crypto Intelligence Terminal", page_icon="📊",
                    layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Inter:wght@400;600;700&display=swap');
    [data-testid="stAppViewContainer"] { font-family: 'Inter', sans-serif; }
    [data-testid="stSidebar"] { background: linear-gradient(180deg, #0a0e1a 0%, #111827 100%); }
    .signal-buy  { background: linear-gradient(135deg,#064e3b,#065f46); border:1px solid #10b981;
                   border-radius:12px; padding:20px; text-align:center; margin:4px; }
    .signal-sell { background: linear-gradient(135deg,#7f1d1d,#991b1b); border:1px solid #ef4444;
                   border-radius:12px; padding:20px; text-align:center; margin:4px; }
    .signal-hold { background: linear-gradient(135deg,#78350f,#92400e); border:1px solid #f59e0b;
                   border-radius:12px; padding:20px; text-align:center; margin:4px; }
    .signal-na   { background: rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.1);
                   border-radius:12px; padding:20px; text-align:center; margin:4px; }
    .signal-type { font-size:1.8em; font-weight:700; font-family:'JetBrains Mono'; }
    .signal-coin { font-size:0.9em; opacity:0.7; }
    .signal-conf { font-size:0.85em; opacity:0.6; margin-top:4px; }
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════
#  SIDEBAR
# ═══════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 📊 Crypto Terminal")
    st.markdown("*Self-Hosted LLM Intelligence*")
    st.markdown("---")
    selected_coins = st.multiselect("🪙 Track Coins", list(COINS.keys()), default=["BTC", "ETH", "SOL"])
    time_window = st.selectbox("⏱ Time Window", ["6h", "12h", "24h", "48h", "7d"], index=2)
    auto_refresh = st.selectbox("🔄 Auto-refresh", [30, 60, 120, 0], index=1,
                                 format_func=lambda x: f"{x}s" if x else "Off")
    st.markdown("---")
    st.markdown("#### 🧠 LLM Sentiment Test")
    test_text = st.text_area("Enter text to analyze",
                              "Bitcoin is showing strong bullish momentum today", height=80)
    if st.button("Analyze Sentiment", use_container_width=True):
        engine = SentimentEngine()
        score, label, reason = engine.analyze_text(test_text)
        emoji = {"BULLISH": "🟢", "BEARISH": "🔴", "NEUTRAL": "🟡", "FUD": "🟠"}.get(label, "⚪")
        st.success(f"{emoji} **{label}** — Score: {score:.2f}")
        st.caption(reason)
    st.markdown("---")
    st.caption("💡 Run `python main.py` for live data")

hours = {"6h": 6, "12h": 12, "24h": 24, "48h": 48, "7d": 168}.get(time_window, 24)


# ═══════════════════════════════════════════════
#  DATA LOADERS (cached)
# ═══════════════════════════════════════════════
@st.cache_data(ttl=30)
def get_signals(coins):
    session = get_session()
    out = {}
    for c in coins:
        s = session.query(Signal).filter(Signal.coin == c).order_by(Signal.timestamp.desc()).first()
        if s:
            out[c] = {"type": s.signal_type, "confidence": s.confidence,
                      "reasoning": s.reasoning, "time": s.timestamp,
                      "sentiment": s.sentiment_score, "prediction": s.prediction_direction,
                      "whale": s.whale_activity}
    session.close()
    return out

@st.cache_data(ttl=30)
def get_prices(coin, hrs):
    session = get_session()
    rows = session.query(PriceData).filter(
        PriceData.coin == coin, PriceData.timestamp >= datetime.utcnow() - timedelta(hours=hrs),
        PriceData.interval == "15m"
    ).order_by(PriceData.timestamp).all()
    session.close()
    if not rows: return pd.DataFrame()
    return pd.DataFrame([{"timestamp": r.timestamp, "open": r.open, "high": r.high,
                           "low": r.low, "close": r.close, "volume": r.volume} for r in rows])

@st.cache_data(ttl=30)
def get_sentiments(coins, hrs):
    session = get_session()
    rows = session.query(SentimentSnapshot).filter(
        SentimentSnapshot.coin.in_(coins),
        SentimentSnapshot.timestamp >= datetime.utcnow() - timedelta(hours=hrs)
    ).order_by(SentimentSnapshot.timestamp).all()
    session.close()
    if not rows: return pd.DataFrame()
    return pd.DataFrame([{"coin": r.coin, "timestamp": r.timestamp,
                           "score": r.avg_score, "label": r.label, "samples": r.sample_count} for r in rows])

@st.cache_data(ttl=60)
def get_whales(hrs):
    session = get_session()
    rows = session.query(WhaleTransaction).filter(
        WhaleTransaction.timestamp >= datetime.utcnow() - timedelta(hours=hrs)
    ).order_by(WhaleTransaction.timestamp.desc()).all()
    session.close()
    if not rows: return pd.DataFrame()
    return pd.DataFrame([{"coin": r.coin, "time": r.timestamp, "value_usd": r.value_usd,
                           "type": r.tx_type, "from": (r.from_address or "")[:12] + "…",
                           "to": (r.to_address or "")[:12] + "…"} for r in rows])

@st.cache_data(ttl=30)
def get_signal_log(limit=100):
    session = get_session()
    rows = session.query(Signal).order_by(Signal.timestamp.desc()).limit(limit).all()
    session.close()
    if not rows: return pd.DataFrame()
    return pd.DataFrame([{"Time": r.timestamp.strftime("%b %d %H:%M"), "Coin": r.coin,
                           "Signal": r.signal_type, "Conf": f"{r.confidence:.0%}",
                           "Reasoning": (r.reasoning or "")[:90]} for r in rows])

@st.cache_data(ttl=30)
def get_stats():
    session = get_session()
    c24 = datetime.utcnow() - timedelta(hours=24)
    s = {"reddit": session.query(RedditPost).filter(RedditPost.created_utc >= c24).count(),
         "news": session.query(NewsArticle).filter(NewsArticle.published_at >= c24).count(),
         "signals": session.query(Signal).filter(Signal.timestamp >= c24).count(),
         "whales": session.query(WhaleTransaction).filter(WhaleTransaction.timestamp >= c24).count(),
         "prices": session.query(PriceData).filter(PriceData.timestamp >= c24).count()}
    session.close()
    return s


# ═══════════════════════════════════════════════
#  HEADER
# ═══════════════════════════════════════════════
st.markdown("# 📊 Crypto Trading Intelligence Terminal")
st.caption(f"Updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC  ·  Window: {time_window}")

stats = get_stats()
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("📝 Reddit", stats["reddit"])
c2.metric("📰 News", stats["news"])
c3.metric("📊 Signals", stats["signals"])
c4.metric("🐋 Whales", stats["whales"])
c5.metric("📈 Candles", stats["prices"])
st.markdown("---")


# ═══════════════════════════════════════════════
#  TABS
# ═══════════════════════════════════════════════
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📈 Dashboard", "🧠 Sentiment", "📊 Predictions", "🐋 Whales", "📉 Backtesting"
])

# ── TAB 1: DASHBOARD ──
with tab1:
    signals = get_signals(selected_coins)
    cols = st.columns(max(len(selected_coins), 1))
    for i, coin in enumerate(selected_coins):
        with cols[i]:
            sig = signals.get(coin, {})
            stype = sig.get("type", "N/A")
            cls = {"BUY": "signal-buy", "SELL": "signal-sell", "HOLD": "signal-hold"}.get(stype, "signal-na")
            emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡"}.get(stype, "⚪")
            conf = sig.get("confidence", 0)
            st.markdown(f'<div class="{cls}"><div class="signal-coin">{coin}</div>'
                        f'<div class="signal-type">{emoji} {stype}</div>'
                        f'<div class="signal-conf">{conf:.0%} confidence</div></div>',
                        unsafe_allow_html=True)
    st.markdown("")

    for coin in selected_coins:
        pdf = get_prices(coin, hours)
        if not pdf.empty:
            fig = go.Figure(data=[go.Candlestick(
                x=pdf["timestamp"], open=pdf["open"], high=pdf["high"],
                low=pdf["low"], close=pdf["close"],
                increasing_line_color="#10b981", decreasing_line_color="#ef4444")])
            sig = signals.get(coin, {})
            if sig.get("time") and not pdf.empty:
                idx = (pdf["timestamp"] - sig["time"]).abs().argsort()[:1]
                cp = pdf.iloc[idx]["close"].iloc[0]
                color = {"BUY": "#10b981", "SELL": "#ef4444"}.get(sig["type"], "#f59e0b")
                sym = "triangle-up" if sig["type"] == "BUY" else "triangle-down"
                fig.add_trace(go.Scatter(x=[sig["time"]], y=[cp], mode="markers+text",
                                          text=[sig["type"]], textposition="top center",
                                          textfont=dict(color=color, size=12),
                                          marker=dict(size=14, color=color, symbol=sym), showlegend=False))
            fig.update_layout(title=f"{coin}/USDT", height=380, template="plotly_dark",
                              xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=40, b=10),
                              plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

    st.subheader("📋 Signal Log")
    log = get_signal_log()
    if not log.empty:
        st.dataframe(log, use_container_width=True, hide_index=True, height=300)
    else:
        st.info("No signals yet. Run `python main.py` to start.")


# ── TAB 2: SENTIMENT ──
with tab2:
    st.subheader("🧠 Sentiment Heatmap")
    sdf = get_sentiments(selected_coins, hours)
    if not sdf.empty:
        latest = sdf.groupby("coin").last().reset_index()
        fig = go.Figure(data=go.Heatmap(
            z=[latest["score"].tolist()], x=latest["coin"].tolist(), y=["Sentiment"],
            colorscale=[[0, "#dc2626"], [0.3, "#dc2626"], [0.5, "#f59e0b"], [0.7, "#10b981"], [1, "#10b981"]],
            zmin=0, zmax=1, text=[[f"{s:.2f}" for s in latest["score"]]],
            texttemplate="%{text}", textfont={"size": 18, "color": "white"}))
        fig.update_layout(height=120, template="plotly_dark", margin=dict(l=20, r=20, t=10, b=10),
                          plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

        fig2 = px.line(sdf, x="timestamp", y="score", color="coin", title="Sentiment Over Time", markers=True)
        fig2.add_hrect(y0=0.7, y1=1.0, fillcolor="#10b981", opacity=0.08, annotation_text="Bullish")
        fig2.add_hrect(y0=0.0, y1=0.3, fillcolor="#dc2626", opacity=0.08, annotation_text="Bearish")
        fig2.update_layout(height=400, template="plotly_dark",
                           plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No sentiment data yet.")


# ── TAB 3: PREDICTIONS ──
with tab3:
    st.subheader("📊 Price Predictions")
    sigs = get_signals(selected_coins)
    for coin in selected_coins:
        sig = sigs.get(coin, {})
        st.markdown(f"### {coin}")
        mc1, mc2, mc3 = st.columns(3)
        mc1.metric("Direction", sig.get("prediction", "N/A"))
        mc2.metric("Sentiment", f"{sig.get('sentiment', 0):.2f}" if sig.get("sentiment") else "N/A")
        mc3.metric("Whales", sig.get("whale", "N/A"))
        pdf = get_prices(coin, hours)
        if not pdf.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=pdf["timestamp"], y=pdf["close"], mode="lines",
                                      line=dict(color="#06b6d4", width=2), fill="tozeroy",
                                      fillcolor="rgba(6,182,212,0.05)", name="Price"))
            fig.add_trace(go.Scatter(x=pdf["timestamp"], y=pdf["close"].rolling(25).mean(),
                                      mode="lines", line=dict(color="#f59e0b", width=1, dash="dot"), name="SMA-25"))
            fig.update_layout(height=320, template="plotly_dark", margin=dict(l=10, r=10, t=10, b=10),
                              plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)
        if sig.get("reasoning"):
            with st.expander("Reasoning"):
                st.write(sig["reasoning"])


# ── TAB 4: WHALES ──
with tab4:
    st.subheader("🐋 Whale Transactions")
    wdf = get_whales(hours)
    if not wdf.empty:
        acc = wdf[wdf["type"] == "ACCUMULATION"]["value_usd"].sum()
        dist = wdf[wdf["type"] == "DISTRIBUTION"]["value_usd"].sum()
        net = acc - dist
        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric("💰 Total", f"${wdf['value_usd'].sum():,.0f}")
        mc2.metric("📥 Accumulation", f"${acc:,.0f}")
        mc3.metric("📤 Distribution", f"${dist:,.0f}")
        mc4.metric("📊 Net Flow", f"${net:+,.0f}", delta="Bullish" if net > 0 else "Bearish")
        tc = wdf.groupby("type")["value_usd"].sum().reset_index()
        fig = px.bar(tc, x="type", y="value_usd", color="type",
                      color_discrete_map={"ACCUMULATION": "#10b981", "DISTRIBUTION": "#ef4444", "TRANSFER": "#6366f1"})
        fig.update_layout(height=300, template="plotly_dark", showlegend=False,
                          plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(wdf, use_container_width=True, hide_index=True, height=400)
    else:
        st.info("No whale data yet.")


# ── TAB 5: BACKTESTING ──
with tab5:
    st.subheader("📉 Backtesting")
    bc1, bc2 = st.columns([3, 1])
    with bc2:
        bt_days = st.number_input("Days", 7, 90, 30)
        run_bt = st.button("▶ Run", use_container_width=True, type="primary")
    if run_bt:
        bt = Backtester()
        with st.spinner("Running..."):
            res = bt.run_full_backtest(days=bt_days)
        if not res:
            st.warning("No signals to backtest.")
        for coin, m in res.items():
            if "error" in m:
                st.warning(f"{coin}: {m['error']}")
                continue
            st.markdown(f"### {coin}")
            rc = st.columns(5)
            rc[0].metric("Trades", m["total_trades"])
            rc[1].metric("Win Rate", f"{m['win_rate']:.1%}")
            rc[2].metric("Sharpe", f"{m['sharpe_ratio']:.2f}")
            rc[3].metric("Return", f"{m['total_return_pct']:.1f}%")
            rc[4].metric("Max DD", f"{m['max_drawdown_pct']:.1f}%")
            if m.get("capital_history"):
                fig = go.Figure()
                fig.add_trace(go.Scatter(y=m["capital_history"], mode="lines",
                                          fill="tozeroy", fillcolor="rgba(6,182,212,0.08)",
                                          line=dict(color="#06b6d4", width=2)))
                fig.add_hline(y=10000, line_dash="dot", line_color="rgba(255,255,255,0.2)",
                              annotation_text="Initial $10K")
                fig.update_layout(height=280, template="plotly_dark", yaxis_title="Capital ($)",
                                  plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                                  margin=dict(l=10, r=10, t=10, b=10))
                st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Click **Run** to evaluate signal history vs actual prices.")

# Auto-refresh
if auto_refresh and auto_refresh > 0:
    import time as _t
    _t.sleep(auto_refresh)
    st.rerun()
