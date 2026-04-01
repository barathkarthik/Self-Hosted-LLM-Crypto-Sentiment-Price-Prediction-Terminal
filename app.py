"""
Crypto Trading Intelligence Terminal — Professional Dashboard
Run:  streamlit run app.py
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
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

# ═══════════════════════════════════════════════════════════════
#  PAGE CONFIG
# ═══════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="CryptoTerminal Pro",
    page_icon="▲",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ═══════════════════════════════════════════════════════════════
#  GLOBAL CSS  — Bloomberg / AvaTrade terminal aesthetic
# ═══════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700&family=IBM+Plex+Sans:wght@300;400;500;600;700&display=swap');

/* ── Base ── */
html, body, [class*="css"] {
  font-family: 'IBM Plex Sans', sans-serif;
  background: #060a12;
  color: #c9d1d9;
  font-size: 13px;
}
[data-testid="stAppViewContainer"] { background: #060a12; }
[data-testid="stHeader"] { background: transparent; }
.block-container { padding: 0.75rem 1.25rem 1rem !important; max-width: 100% !important; }
#MainMenu, footer, header { visibility: hidden; }
div[data-testid="stVerticalBlock"] > div { gap: 0.4rem; }

/* ── Scrollbars ── */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: #0d1117; }
::-webkit-scrollbar-thumb { background: #21262d; border-radius: 2px; }

/* ── Sidebar ── */
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #070b14 0%, #0a0f1a 100%);
  border-right: 1px solid #161b22;
  min-width: 230px !important;
  max-width: 230px !important;
}
[data-testid="stSidebar"] .block-container { padding: 0.75rem 0.75rem !important; }
[data-testid="stSidebar"] label { color: #8b949e !important; font-size: 0.72rem !important; letter-spacing: 0.5px; }

/* ── Terminal header ── */
.terminal-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 0.5rem 0 0.6rem;
  border-bottom: 1px solid #161b22;
  margin-bottom: 0.65rem;
}
.terminal-logo {
  font-family: 'JetBrains Mono', monospace;
  font-size: 1.05rem; font-weight: 700; letter-spacing: -0.3px;
  color: #f0f6fc;
}
.terminal-logo span { color: #1f6feb; }
.terminal-status {
  display: flex; gap: 8px; align-items: center;
}
.status-pill {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.6rem; font-weight: 600; letter-spacing: 1.2px;
  padding: 2px 7px; border-radius: 3px; text-transform: uppercase;
}
.pill-live   { background: rgba(35,134,54,0.2);  border: 1px solid rgba(35,134,54,0.5);  color: #3fb950; }
.pill-ai     { background: rgba(31,111,235,0.2); border: 1px solid rgba(31,111,235,0.5); color: #58a6ff; }
.pill-local  { background: rgba(187,128,9,0.2);  border: 1px solid rgba(187,128,9,0.5);  color: #e3b341; }
.terminal-time {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.68rem; color: #484f58; letter-spacing: 0.5px;
}

/* ── Ticker strip ── */
.ticker-strip {
  display: flex; gap: 2px; margin-bottom: 0.65rem;
  border: 1px solid #161b22; border-radius: 6px; overflow: hidden;
  background: #0d1117;
}
.ticker-cell {
  flex: 1; padding: 0.5rem 0.75rem;
  border-right: 1px solid #161b22;
  transition: background 0.2s;
}
.ticker-cell:last-child { border-right: none; }
.ticker-cell:hover { background: #161b22; }
.ticker-coin {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.65rem; font-weight: 700; color: #8b949e;
  letter-spacing: 1px; margin-bottom: 2px;
}
.ticker-price {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.95rem; font-weight: 600; color: #f0f6fc;
}
.ticker-chg-pos { color: #3fb950; font-size: 0.68rem; font-family: 'JetBrains Mono', monospace; }
.ticker-chg-neg { color: #f85149; font-size: 0.68rem; font-family: 'JetBrains Mono', monospace; }
.ticker-signal {
  font-size: 0.6rem; font-weight: 700; letter-spacing: 0.8px;
  padding: 1px 5px; border-radius: 2px; margin-top: 2px; display: inline-block;
}
.sig-buy  { background: rgba(35,134,54,0.25);  color: #3fb950; }
.sig-sell { background: rgba(248,81,73,0.25);  color: #f85149; }
.sig-hold { background: rgba(187,128,9,0.25);  color: #e3b341; }
.sig-na   { background: rgba(139,148,158,0.15); color: #8b949e; }

/* ── Section label ── */
.sec-label {
  font-size: 0.6rem; font-weight: 600; letter-spacing: 1.8px;
  color: #484f58; text-transform: uppercase;
  padding: 0 0 0.35rem; margin-bottom: 0.4rem;
  border-bottom: 1px solid #161b22;
}

/* ── Data card ── */
.data-card {
  background: #0d1117; border: 1px solid #161b22;
  border-radius: 6px; padding: 0.7rem 0.85rem;
  position: relative;
}
.data-card-accent-green::after {
  content: ''; position: absolute; top: 0; left: 0; bottom: 0;
  width: 2px; background: #3fb950; border-radius: 6px 0 0 6px;
}
.data-card-accent-red::after {
  content: ''; position: absolute; top: 0; left: 0; bottom: 0;
  width: 2px; background: #f85149; border-radius: 6px 0 0 6px;
}
.data-card-accent-blue::after {
  content: ''; position: absolute; top: 0; left: 0; bottom: 0;
  width: 2px; background: #58a6ff; border-radius: 6px 0 0 6px;
}
.data-card-accent-yellow::after {
  content: ''; position: absolute; top: 0; left: 0; bottom: 0;
  width: 2px; background: #e3b341; border-radius: 6px 0 0 6px;
}
.dc-label { font-size: 0.6rem; color: #484f58; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 3px; }
.dc-value { font-family: 'JetBrains Mono', monospace; font-size: 1.15rem; font-weight: 600; color: #f0f6fc; }
.dc-sub   { font-size: 0.65rem; color: #484f58; margin-top: 2px; }

/* ── Signal panel ── */
.signal-panel {
  background: #0d1117; border: 1px solid #161b22;
  border-radius: 6px; padding: 1rem 1rem 0.85rem;
  text-align: center;
}
.sp-coin  { font-size: 0.6rem; color: #8b949e; font-weight: 600; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 0.35rem; }
.sp-signal-buy  { font-family: 'JetBrains Mono', monospace; font-size: 1.6rem; font-weight: 700; color: #3fb950; letter-spacing: 4px; }
.sp-signal-sell { font-family: 'JetBrains Mono', monospace; font-size: 1.6rem; font-weight: 700; color: #f85149; letter-spacing: 4px; }
.sp-signal-hold { font-family: 'JetBrains Mono', monospace; font-size: 1.6rem; font-weight: 700; color: #e3b341; letter-spacing: 4px; }
.sp-signal-na   { font-family: 'JetBrains Mono', monospace; font-size: 1.6rem; font-weight: 700; color: #484f58; letter-spacing: 4px; }
.sp-conf  { font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; color: #8b949e; margin-top: 4px; }
.sp-row   { display: flex; justify-content: space-between; padding: 0.3rem 0; border-top: 1px solid #161b22; margin-top: 0.5rem; }
.sp-key   { font-size: 0.68rem; color: #484f58; }
.sp-val   { font-family: 'JetBrains Mono', monospace; font-size: 0.68rem; color: #8b949e; font-weight: 500; }

/* ── Stats row ── */
.stats-bar {
  display: flex; gap: 1px; background: #161b22;
  border: 1px solid #161b22; border-radius: 6px; overflow: hidden;
  margin-bottom: 0.65rem;
}
.stats-cell {
  flex: 1; background: #0d1117; padding: 0.45rem 0.75rem;
  display: flex; align-items: center; gap: 0.6rem;
}
.stats-icon { font-size: 0.85rem; opacity: 0.7; }
.stats-label { font-size: 0.6rem; color: #484f58; letter-spacing: 0.8px; text-transform: uppercase; }
.stats-val { font-family: 'JetBrains Mono', monospace; font-size: 0.88rem; font-weight: 600; color: #c9d1d9; }

/* ── Table ── */
.stDataFrame { border: 1px solid #161b22 !important; border-radius: 6px; }
.stDataFrame [data-testid="stDataFrameResizable"] { background: #0d1117 !important; }

/* ── Tabs ── */
[data-testid="stTabs"] [role="tablist"] {
  background: #0d1117; border-bottom: 1px solid #161b22;
  gap: 0; padding: 0 0.5rem;
  border-radius: 6px 6px 0 0;
}
[data-testid="stTabs"] [role="tab"] {
  font-size: 0.7rem !important; font-weight: 600 !important;
  letter-spacing: 0.8px; text-transform: uppercase;
  color: #484f58 !important;
  padding: 0.55rem 1rem !important;
  border-radius: 0 !important;
  border-bottom: 2px solid transparent !important;
}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
  color: #58a6ff !important;
  border-bottom: 2px solid #1f6feb !important;
  background: transparent !important;
}
[data-testid="stTabs"] [data-baseweb="tab-panel"] {
  background: #0d1117; border: 1px solid #161b22;
  border-top: none; border-radius: 0 0 6px 6px;
  padding: 0.75rem !important;
}

/* ── Reasoning block ── */
.reason-block {
  background: #070b14; border: 1px solid #161b22;
  border-radius: 4px; padding: 0.6rem 0.75rem;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.72rem; color: #8b949e; line-height: 1.6;
}

/* ── Sentiment gauge ── */
.sent-track { background: #161b22; border-radius: 4px; height: 6px; margin: 5px 0; position: relative; overflow: visible; }
.sent-fill  { height: 6px; border-radius: 4px; position: relative; }
.sent-labels { display: flex; justify-content: space-between; font-size: 0.58rem; color: #484f58; margin-top: 2px; }

/* ── Orderbook-style table ── */
.ob-row { display: flex; justify-content: space-between; align-items: center;
  padding: 0.22rem 0.4rem; border-radius: 3px; }
.ob-row:hover { background: #161b22; }
.ob-coin { font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; font-weight: 600; color: #f0f6fc; width: 40px; }
.ob-price { font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; color: #c9d1d9; flex: 1; text-align: right; }
.ob-chg-pos { font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; color: #3fb950; width: 55px; text-align: right; }
.ob-chg-neg { font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; color: #f85149; width: 55px; text-align: right; }
.ob-vol { font-size: 0.65rem; color: #484f58; width: 70px; text-align: right; }

/* ── Buy/Sell buttons style ── */
.stButton button {
  font-family: 'JetBrains Mono', monospace !important;
  font-size: 0.72rem !important; font-weight: 600 !important;
  letter-spacing: 1px !important; text-transform: uppercase !important;
  border-radius: 4px !important; height: 2rem !important;
}

/* ── Metric override ── */
[data-testid="stMetric"] { background: #0d1117; border: 1px solid #161b22; border-radius: 6px; padding: 0.6rem 0.75rem; }
[data-testid="stMetricLabel"] { font-size: 0.6rem !important; color: #484f58 !important; letter-spacing: 1px; text-transform: uppercase; }
[data-testid="stMetricValue"] { font-family: 'JetBrains Mono', monospace !important; font-size: 1.05rem !important; color: #f0f6fc !important; }
[data-testid="stMetricDelta"] { font-size: 0.68rem !important; }

/* ── Selectbox / Multiselect ── */
[data-testid="stSelectbox"] > div > div,
[data-testid="stMultiSelect"] > div > div {
  background: #0d1117 !important; border-color: #30363d !important;
  font-size: 0.75rem !important;
}

/* ── Signal pill badges ── */
.pill-buy  { background:#0d3d22; color:#3fb950; padding:2px 8px; border-radius:3px; font-size:11px; font-family:'JetBrains Mono',monospace; font-weight:700; letter-spacing:0.5px; border:1px solid #1a5c32; }
.pill-sell { background:#3d0d0d; color:#f85149; padding:2px 8px; border-radius:3px; font-size:11px; font-family:'JetBrains Mono',monospace; font-weight:700; letter-spacing:0.5px; border:1px solid #5c1a1a; }
.pill-hold { background:#1a1a0d; color:#e3b341; padding:2px 8px; border-radius:3px; font-size:11px; font-family:'JetBrains Mono',monospace; font-weight:700; letter-spacing:0.5px; border:1px solid #5c4a1a; }

/* ── Terminal comparison table ── */
.term-table { width:100%; border-collapse:collapse; font-family:'JetBrains Mono',monospace; font-size:12px; }
.term-table th { color:#4fc3f7; border-bottom:1px solid #1e3a5f; padding:7px 10px; text-align:left; font-size:10px; letter-spacing:1.2px; text-transform:uppercase; background:#070b14; }
.term-table td { padding:6px 10px; border-bottom:1px solid #0d1b2a; color:#cfd8dc; }
.term-table tr:hover td { background:#0d1b2a; }
.score-bull { color:#3fb950; font-weight:700; }
.score-bear { color:#f85149; font-weight:700; }
.score-neut { color:#e3b341; font-weight:700; }

/* ── Fear & Greed gauge bar ── */
.fg-bar-wrap { background:#161b22; height:10px; border-radius:3px; margin:4px 0 2px; overflow:hidden; }
.fg-bar-fill { height:10px; border-radius:3px; }
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════
def fmt_price(v):
    if v is None: return "—"
    if v >= 10000: return f"{v:,.0f}"
    if v >= 100:   return f"{v:,.2f}"
    return f"{v:,.4f}"

def fmt_usd(v):
    if v is None: return "—"
    if abs(v) >= 1e9: return f"${v/1e9:.2f}B"
    if abs(v) >= 1e6: return f"${v/1e6:.2f}M"
    if abs(v) >= 1e3: return f"${v/1e3:.1f}K"
    return f"${v:.2f}"

def signal_css(s):
    return {"BUY": "sig-buy", "SELL": "sig-sell", "HOLD": "sig-hold"}.get(s, "sig-na")

def sp_css(s):
    return {"BUY": "sp-signal-buy", "SELL": "sp-signal-sell", "HOLD": "sp-signal-hold"}.get(s, "sp-signal-na")

# ═══════════════════════════════════════════════════════════════
#  CACHED DATA LOADERS
# ═══════════════════════════════════════════════════════════════
@st.cache_data(ttl=20)
def get_signals(coins):
    session = get_session()
    out = {}
    for c in coins:
        s = session.query(Signal).filter(Signal.coin == c).order_by(Signal.timestamp.desc()).first()
        if s:
            out[c] = {"type": s.signal_type, "confidence": s.confidence,
                      "reasoning": s.reasoning, "time": s.timestamp,
                      "sentiment": s.sentiment_score, "prediction": s.prediction_direction,
                      "whale": s.whale_activity, "pred_conf": s.prediction_confidence}
    session.close()
    return out

@st.cache_data(ttl=20)
def get_prices(coin, hrs):
    session = get_session()
    rows = session.query(PriceData).filter(
        PriceData.coin == coin,
        PriceData.timestamp >= datetime.utcnow() - timedelta(hours=hrs),
        PriceData.interval == "15m"
    ).order_by(PriceData.timestamp).all()
    session.close()
    if not rows: return pd.DataFrame()
    return pd.DataFrame([{"timestamp": r.timestamp, "open": r.open, "high": r.high,
                          "low": r.low, "close": r.close, "volume": r.volume} for r in rows])

@st.cache_data(ttl=20)
def get_latest_prices(coins):
    pc = PriceCollector()
    out = {}
    for c in coins:
        try:
            p = pc.fetch_current_price(c)
            out[c] = p
        except Exception:
            out[c] = None
    return out

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
                          "type": r.tx_type,
                          "from": (r.from_address or "")[:10] + "…",
                          "to":   (r.to_address or "")[:10] + "…"} for r in rows])

@st.cache_data(ttl=20)
def get_signal_log(limit=80):
    session = get_session()
    rows = session.query(Signal).order_by(Signal.timestamp.desc()).limit(limit).all()
    session.close()
    if not rows: return pd.DataFrame()
    return pd.DataFrame([{
        "Time":      r.timestamp.strftime("%m/%d %H:%M"),
        "Coin":      r.coin,
        "Signal":    r.signal_type,
        "Conf %":    f"{(r.confidence or 0):.0%}",
        "Direction": r.prediction_direction or "—",
        "Sentiment": f"{(r.sentiment_score or 0):.2f}",
        "Whale":     r.whale_activity or "—",
        "Reasoning": (r.reasoning or "")[:70],
    } for r in rows])

@st.cache_data(ttl=30)
def get_news(coin, limit=10):
    session = get_session()
    rows = session.query(NewsArticle).filter(
        NewsArticle.coin == coin
    ).order_by(NewsArticle.published_at.desc()).limit(limit).all()
    session.close()
    return rows

@st.cache_data(ttl=30)
def get_stats():
    session = get_session()
    c24 = datetime.utcnow() - timedelta(hours=24)
    s = {
        "reddit":  session.query(RedditPost).filter(RedditPost.created_utc >= c24).count(),
        "news":    session.query(NewsArticle).filter(NewsArticle.published_at >= c24).count(),
        "signals": session.query(Signal).filter(Signal.timestamp >= c24).count(),
        "whales":  session.query(WhaleTransaction).filter(WhaleTransaction.timestamp >= c24).count(),
        "candles": session.query(PriceData).filter(PriceData.timestamp >= c24).count(),
    }
    session.close()
    return s

@st.cache_data(ttl=120)
def get_fear_greed():
    session = get_session()
    row = session.query(SentimentSnapshot).filter(
        SentimentSnapshot.source == "fear_greed"
    ).order_by(SentimentSnapshot.timestamp.desc()).first()
    session.close()
    if row:
        return {"score": row.avg_score, "label": row.label, "time": row.timestamp}
    return None


# ═══════════════════════════════════════════════════════════════
#  SIDEBAR
# ═══════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("""
    <div style="padding:0.25rem 0 0.75rem; border-bottom:1px solid #161b22; margin-bottom:0.75rem;">
      <div style="font-family:'JetBrains Mono',monospace;font-size:0.95rem;font-weight:700;color:#f0f6fc;">
        ▲ CRYPTO<span style="color:#1f6feb;">TERMINAL</span>
      </div>
      <div style="font-size:0.6rem;color:#484f58;letter-spacing:1px;margin-top:2px;">INTELLIGENCE PLATFORM v1.0</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="sec-label">Watchlist</div>', unsafe_allow_html=True)
    selected_coins = st.multiselect(
        "Track Coins", list(COINS.keys()),
        default=["BTC", "ETH", "SOL"],
        label_visibility="collapsed"
    )

    st.markdown('<div class="sec-label" style="margin-top:0.75rem;">Chart Settings</div>', unsafe_allow_html=True)
    time_window = st.selectbox("Time Window", ["6h", "12h", "24h", "48h", "7d"],
                                index=2, label_visibility="collapsed")
    chart_coin = st.selectbox("Chart Coin", selected_coins if selected_coins else list(COINS.keys()),
                               label_visibility="collapsed")

    st.markdown('<div class="sec-label" style="margin-top:0.75rem;">Refresh</div>', unsafe_allow_html=True)
    auto_refresh = st.selectbox("Auto-refresh", [30, 60, 120, 0], index=1,
                                 format_func=lambda x: f"Every {x}s" if x else "Manual",
                                 label_visibility="collapsed")

    st.markdown('<div class="sec-label" style="margin-top:0.75rem;">Sentiment Test</div>', unsafe_allow_html=True)
    test_text = st.text_area("Sentiment Input", "Bitcoin bulls push for new highs as institutional demand rises",
                              height=65, label_visibility="collapsed")
    if st.button("ANALYZE", use_container_width=True):
        engine = SentimentEngine()
        score, label, reason = engine.analyze_text(test_text)
        color = {"BULLISH": "#3fb950", "BEARISH": "#f85149", "FUD": "#e3b341"}.get(label, "#8b949e")
        st.markdown(f"""
        <div style="background:#070b14;border:1px solid #30363d;border-radius:4px;padding:0.5rem 0.6rem;margin-top:0.3rem;">
          <div style="font-family:'JetBrains Mono',monospace;font-size:0.8rem;font-weight:700;color:{color};">{label}</div>
          <div style="font-family:'JetBrains Mono',monospace;font-size:0.7rem;color:#8b949e;">Score: {score:.3f}</div>
          <div style="font-size:0.65rem;color:#484f58;margin-top:3px;">{reason}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("""
    <div style="margin-top:auto;padding-top:1rem;border-top:1px solid #161b22;">
      <div style="font-size:0.6rem;color:#484f58;line-height:1.7;">
        ● Run <code style="color:#8b949e;">python main.py</code> for live feed<br>
        ● Data: Binance · NewsAPI · Etherscan<br>
        ● LLM: Ollama Mistral 7B (local)
      </div>
    </div>
    """, unsafe_allow_html=True)

hours = {"6h": 6, "12h": 12, "24h": 24, "48h": 48, "7d": 168}.get(time_window, 24)

# ═══════════════════════════════════════════════════════════════
#  TOP HEADER BAR
# ═══════════════════════════════════════════════════════════════
now_str = datetime.utcnow().strftime("%Y-%m-%d  %H:%M:%S UTC")
st.markdown(f"""
<div class="terminal-header">
  <div style="display:flex;align-items:center;gap:12px;">
    <div class="terminal-logo">▲ CRYPTO<span>TERMINAL</span> <span style="font-size:0.55rem;color:#484f58;font-weight:400;">PRO</span></div>
    <div class="terminal-status">
      <span class="status-pill pill-live">● LIVE</span>
      <span class="status-pill pill-ai">AI-POWERED</span>
      <span class="status-pill pill-local">LOCAL LLM</span>
    </div>
  </div>
  <div class="terminal-time">{now_str}</div>
</div>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
#  STATS BAR
# ═══════════════════════════════════════════════════════════════
stats = get_stats()
st.markdown(f"""
<div class="stats-bar">
  <div class="stats-cell">
    <span class="stats-icon" style="font-family:'JetBrains Mono',monospace;font-size:0.7rem;color:#484f58;">[N]</span>
    <div><div class="stats-label">News (24h)</div><div class="stats-val">{stats['news']}</div></div>
  </div>
  <div class="stats-cell">
    <span class="stats-icon" style="font-family:'JetBrains Mono',monospace;font-size:0.7rem;color:#484f58;">[TG]</span>
    <div><div class="stats-label">Telegram (24h)</div><div class="stats-val">{stats['reddit']}</div></div>
  </div>
  <div class="stats-cell">
    <span class="stats-icon" style="font-family:'JetBrains Mono',monospace;font-size:0.7rem;color:#484f58;">[SIG]</span>
    <div><div class="stats-label">Signals (24h)</div><div class="stats-val">{stats['signals']}</div></div>
  </div>
  <div class="stats-cell">
    <span class="stats-icon" style="font-family:'JetBrains Mono',monospace;font-size:0.7rem;color:#484f58;">[W]</span>
    <div><div class="stats-label">Whale Txns</div><div class="stats-val">{stats['whales']}</div></div>
  </div>
  <div class="stats-cell">
    <span class="stats-icon" style="font-family:'JetBrains Mono',monospace;font-size:0.7rem;color:#484f58;">[C]</span>
    <div><div class="stats-label">Candles</div><div class="stats-val">{stats['candles']}</div></div>
  </div>
  <div class="stats-cell">
    <span class="stats-icon" style="font-family:'JetBrains Mono',monospace;font-size:0.7rem;color:#484f58;">[T]</span>
    <div><div class="stats-label">Window</div><div class="stats-val">{time_window}</div></div>
  </div>
</div>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
#  TICKER STRIP — all coins
# ═══════════════════════════════════════════════════════════════
all_signals = get_signals(list(COINS.keys()))
live_prices = get_latest_prices(tuple(COINS.keys()))

ticker_cells = ""
for coin in COINS:
    sig  = all_signals.get(coin, {})
    stype = sig.get("type", "N/A")
    conf  = sig.get("confidence", 0) or 0
    price = live_prices.get(coin)

    # compute 24h change from DB
    pdf24 = get_prices(coin, 24)
    if not pdf24.empty and price:
        old_p = pdf24["close"].iloc[0]
        chg   = ((price - old_p) / old_p * 100) if old_p else 0
        chg_html = (f'<span class="ticker-chg-pos">▲ {chg:.2f}%</span>' if chg >= 0
                    else f'<span class="ticker-chg-neg">▼ {abs(chg):.2f}%</span>')
    else:
        chg_html = '<span style="color:#484f58;font-size:0.65rem;">—</span>'

    sig_cls = signal_css(stype)
    ticker_cells += f"""
    <div class="ticker-cell">
      <div class="ticker-coin">{coin}/USDT</div>
      <div class="ticker-price">{fmt_price(price)}</div>
      {chg_html}
      <div><span class="ticker-signal {sig_cls}">{stype} {conf:.0%}</span></div>
    </div>"""

st.markdown(f'<div class="ticker-strip">{ticker_cells}</div>', unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
#  MAIN TABS
# ═══════════════════════════════════════════════════════════════
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "MARKET OVERVIEW", "SENTIMENT INTEL", "PREDICTIONS", "WHALE TRACKER", "BACKTESTING"
])


# ────────────────────────────────────────────────────────────────
#  TAB 1 — MARKET OVERVIEW
# ────────────────────────────────────────────────────────────────
with tab1:
    col_watch, col_chart, col_signal = st.columns([1, 2.4, 1], gap="small")

    # ── Left: Watchlist / order-book style ──
    with col_watch:
        st.markdown('<div class="sec-label">Watchlist</div>', unsafe_allow_html=True)
        # Header row
        st.markdown("""
        <div class="ob-row" style="border-bottom:1px solid #161b22;margin-bottom:2px;">
          <span class="ob-coin" style="color:#484f58;font-size:0.6rem;">PAIR</span>
          <span class="ob-price" style="color:#484f58;font-size:0.6rem;">PRICE</span>
          <span class="ob-chg-pos" style="color:#484f58;font-size:0.6rem;">CHG%</span>
          <span class="ob-vol" style="color:#484f58;font-size:0.6rem;">SIGNAL</span>
        </div>""", unsafe_allow_html=True)

        for coin in selected_coins:
            sig   = all_signals.get(coin, {})
            stype = sig.get("type", "N/A")
            price = live_prices.get(coin)
            pdf24 = get_prices(coin, 24)
            if not pdf24.empty and price:
                old_p = pdf24["close"].iloc[0]
                chg   = (price - old_p) / old_p * 100 if old_p else 0
                chg_html = (f'<span class="ob-chg-pos">+{chg:.2f}%</span>' if chg >= 0
                            else f'<span class="ob-chg-neg">{chg:.2f}%</span>')
            else:
                chg_html = '<span class="ob-vol">—</span>'

            sig_cls = signal_css(stype)
            st.markdown(f"""
            <div class="ob-row">
              <span class="ob-coin">{coin}</span>
              <span class="ob-price">{fmt_price(price)}</span>
              {chg_html}
              <span class="ob-vol"><span class="ticker-signal {sig_cls}">{stype}</span></span>
            </div>""", unsafe_allow_html=True)

        # Latest news feed
        st.markdown('<div class="sec-label" style="margin-top:0.9rem;">News Feed</div>', unsafe_allow_html=True)
        if selected_coins:
            news = get_news(selected_coins[0], limit=6)
            if news:
                for n in news:
                    sent_color = {"BULLISH": "#3fb950", "BEARISH": "#f85149"}.get(
                        n.sentiment_label or "", "#484f58")
                    ts = n.published_at.strftime("%m/%d %H:%M") if n.published_at else "—"
                    st.markdown(f"""
                    <div style="padding:0.35rem 0;border-bottom:1px solid #161b22;">
                      <div style="font-size:0.65rem;color:#c9d1d9;line-height:1.4;">{(n.title or '')[:65]}…</div>
                      <div style="display:flex;justify-content:space-between;margin-top:2px;">
                        <span style="font-size:0.58rem;color:#484f58;">{n.source or '—'} · {ts}</span>
                        <span style="font-size:0.58rem;font-weight:600;color:{sent_color};">{n.sentiment_label or '—'}</span>
                      </div>
                    </div>""", unsafe_allow_html=True)
            else:
                st.markdown('<div style="font-size:0.7rem;color:#484f58;padding:0.5rem 0;">No news data. Run main.py.</div>', unsafe_allow_html=True)

    # ── Center: Chart ──
    with col_chart:
        st.markdown(f'<div class="sec-label">{chart_coin}/USDT · {time_window} · 15m candles</div>', unsafe_allow_html=True)
        pdf = get_prices(chart_coin, hours)

        if not pdf.empty:
            # Compute indicators
            pdf["sma25"]   = pdf["close"].rolling(25).mean()
            pdf["sma99"]   = pdf["close"].rolling(99).mean()
            pdf["ema12"]   = pdf["close"].ewm(span=12).mean()
            pdf["ema26"]   = pdf["close"].ewm(span=26).mean()
            pdf["macd"]    = pdf["ema12"] - pdf["ema26"]
            pdf["signal_line"] = pdf["macd"].ewm(span=9).mean()
            pdf["macd_hist"]   = pdf["macd"] - pdf["signal_line"]
            delta = pdf["close"].diff()
            gain  = delta.where(delta > 0, 0).rolling(14).mean()
            loss  = (-delta.where(delta < 0, 0)).rolling(14).mean()
            pdf["rsi"] = 100 - (100 / (1 + gain / (loss + 1e-10)))

            fig = make_subplots(
                rows=3, cols=1,
                shared_xaxes=True,
                row_heights=[0.58, 0.22, 0.20],
                vertical_spacing=0.02,
            )

            # Candlestick
            fig.add_trace(go.Candlestick(
                x=pdf["timestamp"], open=pdf["open"], high=pdf["high"],
                low=pdf["low"], close=pdf["close"], name="OHLC",
                increasing=dict(line=dict(color="#3fb950", width=1), fillcolor="#1a3a22"),
                decreasing=dict(line=dict(color="#f85149", width=1), fillcolor="#3a1a1a"),
            ), row=1, col=1)
            fig.add_trace(go.Scatter(x=pdf["timestamp"], y=pdf["sma25"], mode="lines",
                                      line=dict(color="#e3b341", width=1, dash="dot"),
                                      name="SMA25", showlegend=False), row=1, col=1)
            fig.add_trace(go.Scatter(x=pdf["timestamp"], y=pdf["sma99"], mode="lines",
                                      line=dict(color="#58a6ff", width=1, dash="dot"),
                                      name="SMA99", showlegend=False), row=1, col=1)

            # Signal marker
            sig_data = all_signals.get(chart_coin, {})
            if sig_data.get("time") and not pdf.empty:
                idx = (pdf["timestamp"] - sig_data["time"]).abs().argsort()[:1]
                if len(idx):
                    cp   = pdf.iloc[idx]["close"].iloc[0]
                    sig_type = sig_data["type"]
                    sc   = {"BUY": "#3fb950", "SELL": "#f85149"}.get(sig_type, "#e3b341")
                    sym  = {"BUY": "triangle-up", "SELL": "triangle-down"}.get(sig_type, "circle")
                    fig.add_trace(go.Scatter(
                        x=[sig_data["time"]], y=[cp], mode="markers+text",
                        text=[f" {sig_type}"], textposition="top center",
                        textfont=dict(color=sc, size=10, family="JetBrains Mono"),
                        marker=dict(size=12, color=sc, symbol=sym,
                                    line=dict(color="#060a12", width=1)),
                        showlegend=False,
                    ), row=1, col=1)

            # Volume bars
            vol_colors = ["#3fb950" if pdf["close"].iloc[i] >= pdf["open"].iloc[i] else "#f85149"
                          for i in range(len(pdf))]
            fig.add_trace(go.Bar(x=pdf["timestamp"], y=pdf["volume"],
                                  marker_color=vol_colors, marker_opacity=0.6,
                                  name="Volume", showlegend=False), row=2, col=1)

            # RSI
            fig.add_trace(go.Scatter(x=pdf["timestamp"], y=pdf["rsi"], mode="lines",
                                      line=dict(color="#bc8cff", width=1.2),
                                      name="RSI", showlegend=False), row=3, col=1)
            fig.add_hline(y=70, line_dash="dot", line_color="rgba(248,81,73,0.4)",
                          line_width=1, row=3, col=1)
            fig.add_hline(y=30, line_dash="dot", line_color="rgba(63,185,80,0.4)",
                          line_width=1, row=3, col=1)
            fig.add_hrect(y0=70, y1=100, fillcolor="rgba(248,81,73,0.04)",
                          line_width=0, row=3, col=1)
            fig.add_hrect(y0=0, y1=30, fillcolor="rgba(63,185,80,0.04)",
                          line_width=0, row=3, col=1)

            _layout = dict(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=440,
                margin=dict(l=0, r=0, t=4, b=0),
                xaxis=dict(showgrid=False, zeroline=False, color="#484f58",
                           rangeslider_visible=False, showticklabels=False),
                xaxis2=dict(showgrid=False, zeroline=False, color="#484f58", showticklabels=False),
                xaxis3=dict(showgrid=False, zeroline=False, color="#484f58",
                            tickfont=dict(size=9, color="#484f58")),
                yaxis=dict(gridcolor="#161b22", zeroline=False, color="#8b949e",
                           tickfont=dict(size=9, family="JetBrains Mono"), side="right"),
                yaxis2=dict(gridcolor="#161b22", zeroline=False, color="#8b949e",
                            tickfont=dict(size=9, family="JetBrains Mono"), side="right",
                            title=dict(text="VOL", font=dict(size=8, color="#484f58"))),
                yaxis3=dict(gridcolor="#161b22", zeroline=False, color="#8b949e",
                            tickfont=dict(size=9, family="JetBrains Mono"), side="right",
                            range=[0, 100],
                            title=dict(text="RSI", font=dict(size=8, color="#484f58"))),
                font=dict(family="IBM Plex Sans", color="#8b949e"),
                showlegend=False,
                hovermode="x unified",
                hoverlabel=dict(bgcolor="#161b22", bordercolor="#30363d",
                                font=dict(family="JetBrains Mono", size=11)),
            )
            fig.update_layout(**_layout)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

            # OHLCV summary row
            last = pdf.iloc[-1]
            prev = pdf.iloc[-2] if len(pdf) > 1 else last
            chg_pct = (last["close"] - prev["close"]) / prev["close"] * 100 if prev["close"] else 0
            chg_c = "#3fb950" if chg_pct >= 0 else "#f85149"
            rsi_v = pdf["rsi"].iloc[-1]
            rsi_c = "#f85149" if rsi_v > 70 else "#3fb950" if rsi_v < 30 else "#8b949e"
            st.markdown(f"""
            <div style="display:flex;gap:1px;background:#161b22;border-radius:4px;overflow:hidden;margin-top:4px;">
              {''.join([
                f'<div style="flex:1;background:#0d1117;padding:0.3rem 0.5rem;text-align:center;">'
                f'<div style="font-size:0.55rem;color:#484f58;text-transform:uppercase;letter-spacing:1px;">{lbl}</div>'
                f'<div style="font-family:JetBrains Mono,monospace;font-size:0.78rem;font-weight:600;color:{col};">{val}</div>'
                f'</div>'
                for lbl, val, col in [
                    ("Open",   fmt_price(last["open"]),   "#c9d1d9"),
                    ("High",   fmt_price(last["high"]),   "#3fb950"),
                    ("Low",    fmt_price(last["low"]),    "#f85149"),
                    ("Close",  fmt_price(last["close"]),  "#f0f6fc"),
                    ("Change", f"{'+'if chg_pct>=0 else ''}{chg_pct:.2f}%", chg_c),
                    ("RSI",    f"{rsi_v:.1f}",            rsi_c),
                    ("Volume", fmt_usd(last["volume"]),   "#8b949e"),
                ]
              ])}
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="height:400px;display:flex;align-items:center;justify-content:center;
                 background:#0d1117;border:1px solid #161b22;border-radius:6px;color:#484f58;font-size:0.75rem;font-family:'JetBrains Mono',monospace;letter-spacing:1px;">
              -- NO DATA -- [ START PIPELINE: python main.py --skip-history ]
            </div>""", unsafe_allow_html=True)

    # ── Right: Signal + Sentiment ──
    with col_signal:
        for coin in selected_coins[:3]:
            sig   = all_signals.get(coin, {})
            stype = sig.get("type", "N/A")
            conf  = sig.get("confidence") or 0
            sent  = sig.get("sentiment") or 0.5
            pred  = sig.get("prediction") or "—"
            whale = sig.get("whale") or "—"
            pred_conf = sig.get("pred_conf") or 0
            sp_class = sp_css(stype)
            sent_color = "#3fb950" if sent > 0.6 else "#f85149" if sent < 0.4 else "#e3b341"
            sent_label = "BULLISH" if sent > 0.6 else "BEARISH" if sent < 0.4 else "NEUTRAL"
            sent_pct = int(sent * 100)

            st.markdown(f"""
            <div class="signal-panel" style="margin-bottom:0.5rem;">
              <div class="sp-coin">{coin}/USDT</div>
              <div class="{sp_class}">{stype}</div>
              <div class="sp-conf">{conf:.0%} confidence</div>
              <div style="margin:0.5rem 0 0.3rem;">
                <div style="font-size:0.58rem;color:#484f58;margin-bottom:3px;">SENTIMENT — <span style="color:{sent_color};">{sent_label}</span></div>
                <div class="sent-track">
                  <div class="sent-fill" style="width:{sent_pct}%;background:linear-gradient(90deg,{'#f85149' if sent<0.4 else '#e3b341' if sent<0.6 else '#3fb950'},{sent_color});"></div>
                </div>
                <div class="sent-labels"><span>0.0</span><span style="color:{sent_color};">{sent:.2f}</span><span>1.0</span></div>
              </div>
              <div class="sp-row"><span class="sp-key">ML Direction</span><span class="sp-val" style="color:{'#3fb950' if pred=='UP' else '#f85149' if pred=='DOWN' else '#8b949e'};">{pred}</span></div>
              <div class="sp-row"><span class="sp-key">Whale Activity</span><span class="sp-val">{whale}</span></div>
              <div class="sp-row"><span class="sp-key">Pred Confidence</span><span class="sp-val">{pred_conf:.0%}</span></div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown('<div class="sec-label" style="margin-top:0.6rem;">Signal Log</div>', unsafe_allow_html=True)
        log = get_signal_log(20)
        if not log.empty:
            for _, r in log.head(8).iterrows():
                sc = {"BUY": "#3fb950", "SELL": "#f85149", "HOLD": "#e3b341"}.get(r["Signal"], "#484f58")
                st.markdown(f"""
                <div style="display:flex;align-items:center;gap:6px;padding:0.25rem 0;border-bottom:1px solid #161b22;">
                  <span style="font-family:'JetBrains Mono',monospace;font-size:0.65rem;font-weight:700;color:{sc};width:30px;">{r['Signal']}</span>
                  <span style="font-family:'JetBrains Mono',monospace;font-size:0.62rem;color:#8b949e;width:25px;">{r['Coin']}</span>
                  <span style="font-size:0.6rem;color:#484f58;">{r['Time']}</span>
                  <span style="font-family:'JetBrains Mono',monospace;font-size:0.6rem;color:#484f58;margin-left:auto;">{r['Conf %']}</span>
                </div>""", unsafe_allow_html=True)
        else:
            st.markdown('<div style="font-size:0.68rem;color:#484f58;">No signals yet.</div>', unsafe_allow_html=True)


# ────────────────────────────────────────────────────────────────
#  TAB 2 — SENTIMENT INTEL
# ────────────────────────────────────────────────────────────────
with tab2:
    sdf = get_sentiments(selected_coins, hours)
    c_heat, c_trend = st.columns([1, 2], gap="small")

    with c_heat:
        st.markdown('<div class="sec-label">Sentiment Scores — Latest</div>', unsafe_allow_html=True)
        if not sdf.empty:
            latest_s = sdf.groupby("coin").last().reset_index()
            for _, row in latest_s.iterrows():
                sc = "#3fb950" if row["score"] > 0.6 else "#f85149" if row["score"] < 0.4 else "#e3b341"
                lbl = "BULLISH" if row["score"] > 0.6 else "BEARISH" if row["score"] < 0.4 else "NEUTRAL"
                pct = int(row["score"] * 100)
                st.markdown(f"""
                <div class="data-card" style="margin-bottom:0.4rem;">
                  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
                    <div style="font-family:'JetBrains Mono',monospace;font-size:0.82rem;font-weight:600;color:#f0f6fc;">{row['coin']}</div>
                    <div style="font-size:0.68rem;font-weight:600;color:{sc};">{lbl}</div>
                  </div>
                  <div class="sent-track">
                    <div class="sent-fill" style="width:{pct}%;background:linear-gradient(90deg,#f85149,#e3b341,#3fb950);"></div>
                  </div>
                  <div style="display:flex;justify-content:space-between;margin-top:3px;">
                    <span style="font-family:'JetBrains Mono',monospace;font-size:0.7rem;color:{sc};">{row['score']:.3f}</span>
                    <span style="font-size:0.62rem;color:#484f58;">{int(row['samples'])} samples</span>
                  </div>
                </div>""", unsafe_allow_html=True)

            # Heatmap — full height
            st.markdown('<div class="sec-label" style="margin-top:0.75rem;">Sentiment Heatmap</div>', unsafe_allow_html=True)
            fig_h = go.Figure(go.Heatmap(
                z=[latest_s["score"].tolist()],
                x=latest_s["coin"].tolist(), y=["Score"],
                colorscale=[[0, "#7f1d1d"], [0.3, "#f85149"],
                            [0.5, "#e3b341"], [0.7, "#3fb950"], [1, "#064e3b"]],
                zmin=0, zmax=1,
                text=[[f"{s:.2f}" for s in latest_s["score"]]],
                texttemplate="%{text}",
                textfont=dict(size=15, family="JetBrains Mono", color="white"),
                showscale=True,
                colorbar=dict(
                    thickness=10, len=0.8,
                    tickfont=dict(size=9, color="#484f58", family="JetBrains Mono"),
                    outlinecolor="#161b22", outlinewidth=1,
                ),
            ))
            fig_h.update_layout(
                height=160, margin=dict(l=0, r=0, t=0, b=0),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(color="#8b949e", tickfont=dict(size=11, family="JetBrains Mono", color="#c9d1d9")),
                yaxis=dict(color="#8b949e", showticklabels=False),
            )
            st.plotly_chart(fig_h, use_container_width=True, config={"displayModeBar": False})

            # Fear & Greed gauge
            fg = get_fear_greed()
            if fg:
                fg_pct = int(fg["score"] * 100)
                fg_color = "#f85149" if fg_pct < 25 else "#e3b341" if fg_pct < 45 else "#3fb950" if fg_pct >= 55 else "#8b949e"
                fg_label = {"BEARISH": "FEAR", "BULLISH": "GREED", "NEUTRAL": "NEUTRAL"}.get(fg["label"], fg["label"])
                st.markdown(f"""
                <div style="margin-top:0.6rem;">
                  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:2px;">
                    <span style="font-size:0.6rem;color:#484f58;letter-spacing:1px;font-weight:600;text-transform:uppercase;">Fear &amp; Greed Index</span>
                    <span style="font-family:'JetBrains Mono',monospace;font-size:0.75rem;font-weight:700;color:{fg_color};">{fg_pct}/100 — {fg_label}</span>
                  </div>
                  <div class="fg-bar-wrap">
                    <div class="fg-bar-fill" style="width:{fg_pct}%;background:linear-gradient(90deg,#f85149,#e3b341 45%,#3fb950);"></div>
                  </div>
                  <div style="display:flex;justify-content:space-between;font-size:0.55rem;color:#30363d;font-family:'JetBrains Mono',monospace;">
                    <span>EXTREME FEAR</span><span>NEUTRAL</span><span>EXTREME GREED</span>
                  </div>
                </div>""", unsafe_allow_html=True)
        else:
            st.markdown('<div style="font-size:0.7rem;color:#484f58;padding:0.5rem 0;">-- NO DATA -- [ START PIPELINE: python main.py --skip-history ]</div>', unsafe_allow_html=True)

    with c_trend:
        st.markdown('<div class="sec-label">Sentiment Trend Over Time</div>', unsafe_allow_html=True)
        if not sdf.empty:
            fig_s = go.Figure()
            colors_map = {"BTC": "#f7931a", "ETH": "#627eea", "SOL": "#9945ff",
                          "XRP": "#346aa9", "DOGE": "#c2a633"}
            for coin in selected_coins:
                cdf = sdf[sdf["coin"] == coin]
                if not cdf.empty:
                    fig_s.add_trace(go.Scatter(
                        x=cdf["timestamp"], y=cdf["score"],
                        mode="lines+markers", name=coin,
                        line=dict(color=colors_map.get(coin, "#8b949e"), width=1.5),
                        marker=dict(size=4),
                    ))
            fig_s.add_hrect(y0=0.7, y1=1.0, fillcolor="rgba(63,185,80,0.06)",
                             line_width=0, annotation_text="BULLISH ZONE",
                             annotation_font=dict(size=9, color="#3fb950"))
            fig_s.add_hrect(y0=0.0, y1=0.3, fillcolor="rgba(248,81,73,0.06)",
                             line_width=0, annotation_text="BEARISH ZONE",
                             annotation_font=dict(size=9, color="#f85149"))
            fig_s.add_hline(y=0.5, line_dash="dot", line_color="#30363d", line_width=1)
            fig_s.update_layout(
                height=360, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=0, r=0, t=8, b=0),
                xaxis=dict(showgrid=False, color="#484f58", tickfont=dict(size=9)),
                yaxis=dict(gridcolor="#161b22", color="#484f58", range=[0, 1],
                           tickfont=dict(size=9, family="JetBrains Mono")),
                legend=dict(orientation="h", yanchor="bottom", y=1.02,
                            font=dict(size=10, color="#8b949e"), bgcolor="rgba(0,0,0,0)"),
                hovermode="x unified",
                hoverlabel=dict(bgcolor="#161b22", bordercolor="#30363d",
                                font=dict(family="JetBrains Mono", size=11)),
            )
            st.plotly_chart(fig_s, use_container_width=True, config={"displayModeBar": False})
        else:
            st.markdown('<div style="height:360px;display:flex;align-items:center;justify-content:center;background:#070b14;border:1px solid #161b22;border-radius:4px;color:#484f58;font-size:0.8rem;">No sentiment data yet.</div>', unsafe_allow_html=True)

        # Latest news — styled HTML table
        st.markdown('<div class="sec-label" style="margin-top:0.65rem;">Recent News with Sentiment</div>', unsafe_allow_html=True)
        if selected_coins:
            all_news_rows = []
            for c in selected_coins:
                for n in get_news(c, limit=4):
                    all_news_rows.append((
                        c,
                        n.published_at.strftime("%m/%d %H:%M") if n.published_at else "—",
                        (n.source or "—")[:15],
                        (n.title or "")[:85],
                        n.sentiment_label or "—",
                        f"{n.sentiment_score:.2f}" if n.sentiment_score else "—",
                    ))
            if all_news_rows:
                rows_html = ""
                for coin, pub, src, title, sent_lbl, score in all_news_rows:
                    sc = "score-bull" if sent_lbl == "BULLISH" else "score-bear" if sent_lbl == "BEARISH" else ""
                    rows_html += f"""<tr>
                      <td style="color:#8b949e;font-size:10px;">{coin}</td>
                      <td style="color:#484f58;font-size:10px;white-space:nowrap;">{pub}</td>
                      <td style="color:#484f58;font-size:10px;">{src}</td>
                      <td style="color:#c9d1d9;">{title}</td>
                      <td class="{sc}" style="white-space:nowrap;">{sent_lbl}</td>
                      <td style="text-align:right;">{score}</td>
                    </tr>"""
                st.markdown(f"""
                <div style="max-height:220px;overflow-y:auto;">
                <table class="term-table">
                  <thead><tr>
                    <th>Coin</th><th>Time</th><th>Source</th>
                    <th>Headline</th><th>Sentiment</th><th>Score</th>
                  </tr></thead>
                  <tbody>{rows_html}</tbody>
                </table></div>""", unsafe_allow_html=True)
            else:
                st.markdown('<div style="font-size:0.7rem;color:#484f58;">-- NO DATA -- [ START PIPELINE: python main.py --skip-history ]</div>', unsafe_allow_html=True)


# ────────────────────────────────────────────────────────────────
#  TAB 3 — PREDICTIONS
# ────────────────────────────────────────────────────────────────
with tab3:
    sigs = get_signals(selected_coins)

    # ── Comparison grid table ──────────────────────────────────
    st.markdown('<div class="sec-label">Prediction Summary — All Tracked Coins</div>', unsafe_allow_html=True)
    if selected_coins:
        rows_html = ""
        for coin in selected_coins:
            sig   = sigs.get(coin, {})
            pred  = sig.get("prediction", "—") or "—"
            pc    = sig.get("pred_conf") or 0
            sent  = sig.get("sentiment") or 0.5
            whale = sig.get("whale") or "—"
            stype = sig.get("type", "N/A")
            price = live_prices.get(coin)

            pred_arrow = "▲" if pred == "UP" else "▼" if pred == "DOWN" else "—"
            pred_cls   = "score-bull" if pred == "UP" else "score-bear" if pred == "DOWN" else "score-neut"
            sent_cls   = "score-bull" if sent > 0.6 else "score-bear" if sent < 0.4 else "score-neut"
            sig_cls    = "score-bull" if stype == "BUY" else "score-bear" if stype == "SELL" else "score-neut"
            whale_cls  = "score-bull" if whale == "ACCUMULATION" else "score-bear" if whale == "DISTRIBUTION" else ""

            rows_html += f"""<tr>
              <td style="font-weight:700;color:#f0f6fc;letter-spacing:1px;">{coin}</td>
              <td style="font-family:'JetBrains Mono',monospace;">{fmt_price(price) if price else "—"}</td>
              <td class="{pred_cls}">{pred_arrow} {pred}</td>
              <td style="font-family:'JetBrains Mono',monospace;">{pc:.0%}</td>
              <td class="{sent_cls}">{sent:.3f}</td>
              <td class="{whale_cls}">{whale}</td>
              <td class="{sig_cls}">{stype}</td>
            </tr>"""

        st.markdown(f"""
        <table class="term-table">
          <thead><tr>
            <th>Coin</th><th>Price (USDT)</th><th>Direction</th>
            <th>ML Confidence</th><th>Sentiment Score</th><th>Whale Activity</th><th>Signal</th>
          </tr></thead>
          <tbody>{rows_html}</tbody>
        </table>""", unsafe_allow_html=True)

    # ── Chart + Reasoning for selected coin ────────────────────
    st.markdown('<div class="sec-label" style="margin-top:0.9rem;">Detail View</div>', unsafe_allow_html=True)
    pred_detail_coin = st.selectbox(
        "Select coin for chart", selected_coins or list(COINS.keys()),
        key="pred_detail_coin", label_visibility="collapsed"
    )
    sig_d     = sigs.get(pred_detail_coin, {})
    pred_d    = sig_d.get("prediction", "—") or "—"
    pred_col  = "#3fb950" if pred_d == "UP" else "#f85149" if pred_d == "DOWN" else "#e3b341"
    pdf_d = get_prices(pred_detail_coin, hours)
    if not pdf_d.empty:
        fig_pd = go.Figure()
        fig_pd.add_trace(go.Scatter(
            x=pdf_d["timestamp"], y=pdf_d["close"], mode="lines",
            line=dict(color=pred_col, width=1.5),
            fill="tozeroy",
            fillcolor=f"rgba({'63,185,80' if pred_d=='UP' else '248,81,73' if pred_d=='DOWN' else '227,179,65'},0.05)",
            name="Price"
        ))
        fig_pd.add_trace(go.Scatter(
            x=pdf_d["timestamp"], y=pdf_d["close"].rolling(25).mean(),
            mode="lines", line=dict(color="#58a6ff", width=1, dash="dot"), name="SMA25"
        ))
        fig_pd.update_layout(
            height=240, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=0, r=0, t=4, b=0), showlegend=False,
            xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
            yaxis=dict(gridcolor="#161b22", tickfont=dict(size=8, family="JetBrains Mono"),
                       color="#484f58", zeroline=False, side="right"),
        )
        st.plotly_chart(fig_pd, use_container_width=True, config={"displayModeBar": False})
    else:
        st.markdown('<div style="height:180px;display:flex;align-items:center;justify-content:center;background:#0d1117;border:1px solid #161b22;border-radius:4px;color:#484f58;font-size:0.75rem;">-- NO DATA -- [ START PIPELINE: python main.py --skip-history ]</div>', unsafe_allow_html=True)

    if sig_d.get("reasoning"):
        st.markdown(f'<div class="reason-block" style="margin-top:0.4rem;">{sig_d["reasoning"]}</div>', unsafe_allow_html=True)

    # ── Full signal log ─────────────────────────────────────────
    st.markdown('<div class="sec-label" style="margin-top:0.75rem;">Full Signal History</div>', unsafe_allow_html=True)
    log = get_signal_log(100)
    if not log.empty:
        st.dataframe(log, use_container_width=True, hide_index=True, height=280)
    else:
        st.markdown('<div style="font-size:0.7rem;color:#484f58;padding:0.5rem;">-- NO DATA -- [ START PIPELINE: python main.py --skip-history ]</div>', unsafe_allow_html=True)


# ────────────────────────────────────────────────────────────────
#  TAB 4 — WHALE TRACKER
# ────────────────────────────────────────────────────────────────
with tab4:
    wdf = get_whales(hours)
    if not wdf.empty:
        acc  = wdf[wdf["type"] == "ACCUMULATION"]["value_usd"].sum()
        dist = wdf[wdf["type"] == "DISTRIBUTION"]["value_usd"].sum()
        net  = acc - dist
        tot  = wdf["value_usd"].sum()
        txn  = len(wdf)

        m1, m2, m3, m4, m5 = st.columns(5, gap="small")
        m1.metric("Total Volume",    fmt_usd(tot))
        m2.metric("Accumulation",    fmt_usd(acc))
        m3.metric("Distribution",    fmt_usd(dist))
        m4.metric("Net Flow",        fmt_usd(net),   delta="Bullish" if net > 0 else "Bearish")
        m5.metric("Transactions",    str(txn))

        c_bar, c_table = st.columns([1, 2], gap="small")
        with c_bar:
            st.markdown('<div class="sec-label">Flow Breakdown</div>', unsafe_allow_html=True)
            tc = wdf.groupby("type")["value_usd"].sum().reset_index()
            fig_w = go.Figure(go.Bar(
                x=tc["type"], y=tc["value_usd"],
                marker_color=[{"ACCUMULATION": "#3fb950", "DISTRIBUTION": "#f85149",
                                "TRANSFER": "#6e76e5"}.get(t, "#8b949e") for t in tc["type"]],
                text=[fmt_usd(v) for v in tc["value_usd"]],
                textposition="outside",
                textfont=dict(size=10, family="JetBrains Mono"),
            ))
            fig_w.update_layout(
                height=280, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=0, r=0, t=8, b=0), showlegend=False,
                xaxis=dict(color="#8b949e", tickfont=dict(size=10)),
                yaxis=dict(gridcolor="#161b22", color="#484f58",
                           tickfont=dict(size=9, family="JetBrains Mono")),
                bargap=0.35,
            )
            st.plotly_chart(fig_w, use_container_width=True, config={"displayModeBar": False})

            # Net flow over time
            wdf_time = wdf.copy()
            wdf_time["signed"] = wdf_time.apply(
                lambda r: r["value_usd"] if r["type"] == "ACCUMULATION"
                else -r["value_usd"] if r["type"] == "DISTRIBUTION" else 0, axis=1)
            wdf_time = wdf_time.sort_values("time")
            wdf_time["cumulative"] = wdf_time["signed"].cumsum()
            fig_cum = go.Figure(go.Scatter(
                x=wdf_time["time"], y=wdf_time["cumulative"], mode="lines",
                fill="tozeroy",
                line=dict(color="#3fb950" if net >= 0 else "#f85149", width=1.5),
                fillcolor=f"rgba({'63,185,80' if net>=0 else '248,81,73'},0.06)",
            ))
            fig_cum.update_layout(
                height=160, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=0, r=0, t=4, b=0), showlegend=False,
                xaxis=dict(showgrid=False, color="#484f58", tickfont=dict(size=8), showticklabels=False),
                yaxis=dict(gridcolor="#161b22", color="#484f58",
                           tickfont=dict(size=8, family="JetBrains Mono"), side="right"),
                title=dict(text="CUMULATIVE FLOW", font=dict(size=8, color="#484f58")),
            )
            st.plotly_chart(fig_cum, use_container_width=True, config={"displayModeBar": False})

        with c_table:
            st.markdown('<div class="sec-label">Transaction Feed</div>', unsafe_allow_html=True)
            display_wdf = wdf.copy()
            display_wdf["value_usd"] = display_wdf["value_usd"].apply(fmt_usd)
            display_wdf["time"] = pd.to_datetime(display_wdf["time"]).dt.strftime("%m/%d %H:%M")
            display_wdf.columns = ["Coin", "Time", "Value USD", "Type", "From", "To"]
            st.dataframe(display_wdf, use_container_width=True, hide_index=True, height=460)
    else:
        st.markdown("""
        <div style="padding:3rem;text-align:center;color:#484f58;font-size:0.8rem;">
          No whale transactions in the selected window.<br>
          <span style="color:#8b949e;">Etherscan API key required — set ETHERSCAN_API_KEY in .env.local</span>
        </div>""", unsafe_allow_html=True)


# ────────────────────────────────────────────────────────────────
#  TAB 5 — BACKTESTING
# ────────────────────────────────────────────────────────────────
with tab5:
    c_cfg, c_res = st.columns([1, 3], gap="small")
    with c_cfg:
        st.markdown('<div class="sec-label">Configuration</div>', unsafe_allow_html=True)
        bt_days   = st.number_input("Lookback (days)", 7, 90, 30, label_visibility="visible")
        bt_coin   = st.selectbox("Coin", ["ALL"] + (selected_coins or list(COINS.keys())))
        bt_cap    = st.number_input("Initial Capital ($)", 1000, 100000, 10000, step=1000)
        run_bt    = st.button("▶  RUN BACKTEST", use_container_width=True, type="primary")

        st.markdown("""
        <div style="margin-top:1rem;padding:0.75rem;background:#070b14;border:1px solid #161b22;border-radius:4px;">
          <div style="font-size:0.6rem;color:#484f58;font-weight:600;letter-spacing:1px;margin-bottom:0.4rem;">METHODOLOGY</div>
          <div style="font-size:0.65rem;color:#8b949e;line-height:1.7;">
            ● Replays BUY/SELL signals on 15m OHLCV<br>
            ● 4-hour exit horizon per trade<br>
            ● 10% position size per signal<br>
            ● Long-only (BUY) and short (SELL)<br>
            ● Metrics: Sharpe, Win Rate, Max DD
          </div>
        </div>""", unsafe_allow_html=True)

    with c_res:
        if run_bt:
            bt = Backtester(initial_capital=float(bt_cap))
            with st.spinner("Running backtest…"):
                if bt_coin == "ALL":
                    results = bt.run_full_backtest(days=bt_days)
                else:
                    results = {bt_coin: bt.evaluate(bt_coin, days=bt_days)}

            if not results:
                st.warning("No signal data to backtest.")
            else:
                for coin, m in results.items():
                    if "error" in m:
                        st.markdown(f'<div style="padding:0.5rem;color:#f85149;font-size:0.75rem;">{coin}: {m["error"]}</div>', unsafe_allow_html=True)
                        continue
                    st.markdown(f'<div class="sec-label">{coin} — Backtest Results</div>', unsafe_allow_html=True)
                    r1, r2, r3, r4, r5, r6 = st.columns(6, gap="small")
                    r1.metric("Trades",    m["total_trades"])
                    r2.metric("Win Rate",  f"{m['win_rate']:.1%}")
                    r3.metric("Wins",      m["wins"])
                    r4.metric("Sharpe",    f"{m['sharpe_ratio']:.2f}")
                    r5.metric("Return",    f"{m['total_return_pct']:.1f}%")
                    r6.metric("Max DD",    f"{m['max_drawdown_pct']:.1f}%")

                    if m.get("capital_history"):
                        fig_bt = go.Figure()
                        cap_hist = m["capital_history"]
                        final = cap_hist[-1]
                        line_color = "#3fb950" if final >= bt_cap else "#f85149"
                        fig_bt.add_trace(go.Scatter(
                            y=cap_hist, mode="lines",
                            line=dict(color=line_color, width=2),
                            fill="tozeroy",
                            fillcolor=f"rgba({'63,185,80' if final>=bt_cap else '248,81,73'},0.07)",
                            name="Capital",
                        ))
                        fig_bt.add_hline(y=bt_cap, line_dash="dot",
                                          line_color="rgba(255,255,255,0.15)", line_width=1,
                                          annotation_text=f"Initial ${bt_cap:,}",
                                          annotation_font=dict(size=9, color="#484f58"))
                        fig_bt.update_layout(
                            height=220, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                            margin=dict(l=0, r=0, t=4, b=0), showlegend=False,
                            xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
                            yaxis=dict(gridcolor="#161b22", tickfont=dict(size=9, family="JetBrains Mono"),
                                       color="#484f58", side="right",
                                       tickprefix="$", tickformat=",.0f"),
                        )
                        st.plotly_chart(fig_bt, use_container_width=True, config={"displayModeBar": False})

                    if m.get("trades"):
                        trade_df = pd.DataFrame(m["trades"])
                        trade_df["pnl_pct"] = trade_df["pnl_pct"].apply(lambda x: f"{'+'if x>=0 else ''}{x:.2f}%")
                        trade_df["entry"]   = trade_df["entry"].apply(fmt_price)
                        trade_df["exit"]    = trade_df["exit"].apply(fmt_price)
                        trade_df["correct"] = trade_df["correct"].apply(lambda x: "✓" if x else "✗")
                        trade_df.columns = ["Coin", "Signal", "Entry", "Exit", "P&L %", "Result", "Confidence"]
                        st.dataframe(trade_df, use_container_width=True, hide_index=True, height=220)
        else:
            st.markdown("""
            <div style="height:400px;display:flex;align-items:center;justify-content:center;
                 flex-direction:column;gap:0.6rem;color:#484f58;background:#0d1117;border:1px solid #161b22;border-radius:6px;">
              <div style="font-family:'JetBrains Mono',monospace;font-size:1.2rem;color:#30363d;letter-spacing:4px;">[ BACKTEST ]</div>
              <div style="font-size:0.78rem;">Configure parameters and click <strong style="color:#8b949e;">RUN BACKTEST</strong></div>
              <div style="font-size:0.65rem;color:#30363d;font-family:'JetBrains Mono',monospace;">Requires signal history in database</div>
            </div>""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════
#  AUTO REFRESH
# ═══════════════════════════════════════════════════════════════
if auto_refresh and auto_refresh > 0:
    import time as _t
    _t.sleep(auto_refresh)
    st.rerun()
