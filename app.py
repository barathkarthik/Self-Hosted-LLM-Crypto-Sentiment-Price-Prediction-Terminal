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

from config import COINS, WHALE_ALERT_API_KEY
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
@import url('https://fonts.googleapis.com/css2?family=Inter:ital,wght@0,300;0,400;0,500;0,600;0,700;1,400&family=JetBrains+Mono:wght@300;400;500;600;700&display=swap');

/* ═══════════════════════════════
   CSS VARIABLES
═══════════════════════════════ */
:root {
  --bg:          #04080f;
  --bg-card:     #070d1a;
  --bg-card2:    #090f1c;
  --bg-raised:   #0c1424;
  --border:      #0e1d32;
  --border-hi:   #162a47;
  --text-1:      #dce8ff;
  --text-2:      #6b85a8;
  --text-3:      #374e6e;
  --text-4:      #1e3050;
  --cyan:        #00d4ff;
  --blue:        #1a6aff;
  --buy:         #00e676;
  --buy-bg:      rgba(0,230,118,0.08);
  --buy-border:  rgba(0,230,118,0.3);
  --sell:        #ff3352;
  --sell-bg:     rgba(255,51,82,0.08);
  --sell-border: rgba(255,51,82,0.3);
  --hold:        #ffb300;
  --hold-bg:     rgba(255,179,0,0.08);
  --hold-border: rgba(255,179,0,0.3);
  --purple:      #7c5cfc;
}

/* ═══════════════════════════════
   BASE
═══════════════════════════════ */
html, body, [class*="css"] {
  font-family: 'Inter', sans-serif;
  background: var(--bg) !important;
  color: var(--text-1);
  font-size: 13px;
}
[data-testid="stAppViewContainer"] {
  background: var(--bg) !important;
}
[data-testid="stHeader"] { background: transparent !important; }
.block-container { padding: 0.7rem 1.2rem 1rem !important; max-width: 100% !important; }
#MainMenu, footer, header { visibility: hidden; }
div[data-testid="stVerticalBlock"] > div { gap: 0.4rem; }

/* ═══════════════════════════════
   SCROLLBARS
═══════════════════════════════ */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: var(--bg-card); }
::-webkit-scrollbar-thumb { background: var(--border-hi); border-radius: 2px; }

/* ═══════════════════════════════
   SIDEBAR
═══════════════════════════════ */
[data-testid="stSidebar"] {
  background: linear-gradient(175deg, #060c1a 0%, #04080f 100%) !important;
  border-right: 1px solid var(--border) !important;
  min-width: 230px !important;
  max-width: 230px !important;
}
[data-testid="stSidebar"] .block-container { padding: 0.75rem 0.75rem !important; }
[data-testid="stSidebar"] label { color: var(--text-2) !important; font-size: 0.7rem !important; letter-spacing: 0.3px; }

/* ═══════════════════════════════
   TERMINAL HEADER
═══════════════════════════════ */
.terminal-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 0.55rem 0 0.65rem;
  border-bottom: 1px solid var(--border);
  margin-bottom: 0.6rem;
}
.terminal-logo {
  font-family: 'JetBrains Mono', monospace;
  font-size: 1.08rem; font-weight: 700; letter-spacing: 0.5px;
  color: var(--text-1);
}
.terminal-logo .logo-accent {
  background: linear-gradient(90deg, var(--blue), var(--cyan));
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  background-clip: text;
}
.terminal-logo .logo-dim { font-size: 0.52rem; color: var(--text-3); font-weight: 400; -webkit-text-fill-color: var(--text-3); }
.terminal-status { display: flex; gap: 6px; align-items: center; }
.status-pill {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.58rem; font-weight: 600; letter-spacing: 1px;
  padding: 2px 8px; border-radius: 20px; text-transform: uppercase;
}
.pill-live  { background: rgba(0,230,118,0.1);  border: 1px solid rgba(0,230,118,0.35); color: var(--buy); }
.pill-ai    { background: rgba(26,106,255,0.12); border: 1px solid rgba(0,212,255,0.3);  color: var(--cyan); }
.pill-local { background: rgba(255,179,0,0.1);   border: 1px solid rgba(255,179,0,0.3);  color: var(--hold); }
.pill-srl   { background: rgba(124,92,252,0.12); border: 1px solid rgba(124,92,252,0.35);color: var(--purple); }
.terminal-time {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.65rem; color: var(--text-3); letter-spacing: 0.5px;
}

/* ═══════════════════════════════
   TICKER STRIP
═══════════════════════════════ */
.ticker-strip {
  display: flex; gap: 0; margin-bottom: 0.6rem;
  border: 1px solid var(--border); border-radius: 8px; overflow: hidden;
  background: var(--bg-card);
}
.ticker-cell {
  flex: 1; padding: 0.55rem 0.85rem;
  border-right: 1px solid var(--border);
  transition: background 0.15s;
  position: relative;
}
.ticker-cell::before {
  content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
  background: linear-gradient(90deg, var(--blue), var(--cyan));
  opacity: 0; transition: opacity 0.15s;
}
.ticker-cell:hover { background: var(--bg-raised); }
.ticker-cell:hover::before { opacity: 1; }
.ticker-cell:last-child { border-right: none; }
.ticker-coin {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.62rem; font-weight: 700; color: var(--text-2);
  letter-spacing: 1.5px; margin-bottom: 3px;
}
.ticker-price {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.95rem; font-weight: 600; color: var(--text-1);
}
.ticker-chg-pos { color: var(--buy);  font-size: 0.66rem; font-family: 'JetBrains Mono', monospace; font-weight: 600; }
.ticker-chg-neg { color: var(--sell); font-size: 0.66rem; font-family: 'JetBrains Mono', monospace; font-weight: 600; }
.ticker-signal {
  font-size: 0.58rem; font-weight: 700; letter-spacing: 0.8px;
  padding: 2px 6px; border-radius: 3px; margin-top: 3px; display: inline-block;
}
.sig-buy  { background: var(--buy-bg);  border: 1px solid var(--buy-border);  color: var(--buy); }
.sig-sell { background: var(--sell-bg); border: 1px solid var(--sell-border); color: var(--sell); }
.sig-hold { background: var(--hold-bg); border: 1px solid var(--hold-border); color: var(--hold); }
.sig-na   { background: rgba(107,133,168,0.08); border: 1px solid rgba(107,133,168,0.2); color: var(--text-2); }

/* ═══════════════════════════════
   SECTION LABEL
═══════════════════════════════ */
.sec-label {
  font-size: 0.58rem; font-weight: 600; letter-spacing: 2px;
  color: var(--text-3); text-transform: uppercase;
  padding: 0 0 0.32rem; margin-bottom: 0.4rem;
  border-bottom: 1px solid var(--border);
}

/* ═══════════════════════════════
   DATA CARDS
═══════════════════════════════ */
.data-card {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 8px; padding: 0.75rem 0.9rem;
  position: relative; overflow: hidden;
}
.data-card::before {
  content: ''; position: absolute; top: 0; left: 0; right: 0; height: 1px;
  background: linear-gradient(90deg, transparent, var(--border-hi), transparent);
}
.data-card-accent-green { border-left: 2px solid var(--buy); }
.data-card-accent-red   { border-left: 2px solid var(--sell); }
.data-card-accent-blue  { border-left: 2px solid var(--cyan); }
.data-card-accent-yellow{ border-left: 2px solid var(--hold); }
.dc-label { font-size: 0.58rem; color: var(--text-3); font-weight: 600; letter-spacing: 1.2px; text-transform: uppercase; margin-bottom: 4px; }
.dc-value { font-family: 'JetBrains Mono', monospace; font-size: 1.12rem; font-weight: 600; color: var(--text-1); }
.dc-sub   { font-size: 0.62rem; color: var(--text-3); margin-top: 3px; }

/* ═══════════════════════════════
   SIGNAL PANEL  (the right column cards)
═══════════════════════════════ */
.signal-panel {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 10px; padding: 1rem 1rem 0.85rem;
  text-align: center; position: relative; overflow: hidden;
}
.signal-panel::before {
  content: ''; position: absolute; top: 0; left: 0; right: 0; height: 1px;
  background: linear-gradient(90deg, transparent, var(--border-hi), transparent);
}
.sp-coin { font-size: 0.58rem; color: var(--text-2); font-weight: 600;
  letter-spacing: 3px; text-transform: uppercase; margin-bottom: 0.5rem; }

/* Signal text with glow */
.sp-signal-buy {
  font-family: 'JetBrains Mono', monospace; font-size: 1.65rem; font-weight: 700;
  color: var(--buy); letter-spacing: 5px;
  text-shadow: 0 0 24px rgba(0,230,118,0.6), 0 0 8px rgba(0,230,118,0.4);
}
.sp-signal-sell {
  font-family: 'JetBrains Mono', monospace; font-size: 1.65rem; font-weight: 700;
  color: var(--sell); letter-spacing: 5px;
  text-shadow: 0 0 24px rgba(255,51,82,0.6), 0 0 8px rgba(255,51,82,0.4);
}
.sp-signal-hold {
  font-family: 'JetBrains Mono', monospace; font-size: 1.65rem; font-weight: 700;
  color: var(--hold); letter-spacing: 5px;
  text-shadow: 0 0 24px rgba(255,179,0,0.5), 0 0 8px rgba(255,179,0,0.3);
}
.sp-signal-na {
  font-family: 'JetBrains Mono', monospace; font-size: 1.65rem; font-weight: 700;
  color: var(--text-3); letter-spacing: 5px;
}
.sp-conf { font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; color: var(--text-2); margin-top: 4px; }
.sp-row  { display: flex; justify-content: space-between; align-items: center;
  padding: 0.3rem 0; border-top: 1px solid var(--border); }
.sp-key  { font-size: 0.65rem; color: var(--text-3); font-weight: 500; }
.sp-val  { font-family: 'JetBrains Mono', monospace; font-size: 0.67rem; color: var(--text-2); font-weight: 500; }

/* ═══════════════════════════════
   STATS BAR
═══════════════════════════════ */
.stats-bar {
  display: flex; gap: 1px; background: var(--border);
  border: 1px solid var(--border); border-radius: 8px; overflow: hidden;
  margin-bottom: 0.6rem;
}
.stats-cell {
  flex: 1; background: var(--bg-card); padding: 0.5rem 0.85rem;
  display: flex; align-items: center; gap: 0.65rem;
  transition: background 0.15s;
}
.stats-cell:hover { background: var(--bg-raised); }
.stats-icon {
  width: 26px; height: 26px; border-radius: 6px;
  background: var(--bg-raised); border: 1px solid var(--border-hi);
  display: flex; align-items: center; justify-content: center;
  font-family: 'JetBrains Mono', monospace; font-size: 0.6rem;
  color: var(--cyan); font-weight: 700; flex-shrink: 0;
}
.stats-label { font-size: 0.58rem; color: var(--text-3); letter-spacing: 0.8px; text-transform: uppercase; margin-bottom: 2px; }
.stats-val   { font-family: 'JetBrains Mono', monospace; font-size: 0.9rem; font-weight: 600; color: var(--text-1); }

/* ═══════════════════════════════
   TABLE
═══════════════════════════════ */
.stDataFrame { border: 1px solid var(--border) !important; border-radius: 8px; }
.stDataFrame [data-testid="stDataFrameResizable"] { background: var(--bg-card) !important; }

/* ═══════════════════════════════
   TABS
═══════════════════════════════ */
[data-testid="stTabs"] [role="tablist"] {
  background: var(--bg-card); border-bottom: 1px solid var(--border);
  gap: 0; padding: 0 0.5rem; border-radius: 8px 8px 0 0;
}
[data-testid="stTabs"] [role="tab"] {
  font-family: 'Inter', sans-serif !important;
  font-size: 0.68rem !important; font-weight: 600 !important;
  letter-spacing: 0.6px; text-transform: uppercase;
  color: var(--text-3) !important;
  padding: 0.6rem 1rem !important;
  border-radius: 0 !important;
  border-bottom: 2px solid transparent !important;
  transition: color 0.15s !important;
}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
  color: var(--cyan) !important;
  border-bottom: 2px solid var(--blue) !important;
  background: transparent !important;
}
[data-testid="stTabs"] [role="tab"]:hover {
  color: var(--text-1) !important;
}
[data-testid="stTabs"] [data-baseweb="tab-panel"] {
  background: var(--bg-card); border: 1px solid var(--border);
  border-top: none; border-radius: 0 0 8px 8px;
  padding: 0.75rem !important;
}

/* ═══════════════════════════════
   REASONING BLOCK
═══════════════════════════════ */
.reason-block {
  background: #030609; border: 1px solid var(--border);
  border-radius: 6px; padding: 0.65rem 0.8rem;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem; color: var(--text-2); line-height: 1.65;
}

/* ═══════════════════════════════
   SENTIMENT GAUGE
═══════════════════════════════ */
.sent-track  { background: var(--border-hi); border-radius: 4px; height: 6px; margin: 5px 0; position: relative; overflow: hidden; }
.sent-fill   { height: 6px; border-radius: 4px; }
.sent-labels { display: flex; justify-content: space-between; font-size: 0.56rem; color: var(--text-3); margin-top: 2px; }

/* ═══════════════════════════════
   ORDERBOOK TABLE
═══════════════════════════════ */
.ob-row { display: flex; justify-content: space-between; align-items: center;
  padding: 0.25rem 0.5rem; border-radius: 4px; transition: background 0.1s; }
.ob-row:hover { background: var(--bg-raised); }
.ob-coin    { font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; font-weight: 700; color: var(--text-1); width: 40px; }
.ob-price   { font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; color: var(--text-1); flex: 1; text-align: right; }
.ob-chg-pos { font-family: 'JetBrains Mono', monospace; font-size: 0.68rem; color: var(--buy);  width: 55px; text-align: right; font-weight: 600; }
.ob-chg-neg { font-family: 'JetBrains Mono', monospace; font-size: 0.68rem; color: var(--sell); width: 55px; text-align: right; font-weight: 600; }
.ob-vol     { font-size: 0.62rem; color: var(--text-3); width: 70px; text-align: right; }

/* ═══════════════════════════════
   BUTTONS
═══════════════════════════════ */
.stButton button {
  font-family: 'JetBrains Mono', monospace !important;
  font-size: 0.7rem !important; font-weight: 600 !important;
  letter-spacing: 1px !important; text-transform: uppercase !important;
  border-radius: 6px !important; height: 2rem !important;
  border: 1px solid var(--border-hi) !important;
  background: var(--bg-raised) !important;
  color: var(--text-1) !important;
  transition: all 0.15s !important;
}
.stButton button:hover {
  border-color: var(--cyan) !important;
  color: var(--cyan) !important;
  background: rgba(0,212,255,0.06) !important;
}

/* ═══════════════════════════════
   METRICS
═══════════════════════════════ */
[data-testid="stMetric"] {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 8px; padding: 0.65rem 0.8rem;
}
[data-testid="stMetricLabel"]  { font-size: 0.58rem !important; color: var(--text-3) !important; letter-spacing: 1px; text-transform: uppercase; }
[data-testid="stMetricValue"]  { font-family: 'JetBrains Mono', monospace !important; font-size: 1.05rem !important; color: var(--text-1) !important; }
[data-testid="stMetricDelta"]  { font-size: 0.67rem !important; }

/* ═══════════════════════════════
   SELECTBOX / MULTISELECT
═══════════════════════════════ */
[data-testid="stSelectbox"] > div > div,
[data-testid="stMultiSelect"] > div > div {
  background: var(--bg-card) !important; border-color: var(--border-hi) !important;
  font-size: 0.75rem !important; color: var(--text-1) !important;
}

/* ═══════════════════════════════
   SIGNAL PILL BADGES
═══════════════════════════════ */
.pill-buy  { background: var(--buy-bg);  color: var(--buy);  padding:2px 8px; border-radius:4px; font-size:11px; font-family:'JetBrains Mono',monospace; font-weight:700; letter-spacing:0.5px; border:1px solid var(--buy-border); }
.pill-sell { background: var(--sell-bg); color: var(--sell); padding:2px 8px; border-radius:4px; font-size:11px; font-family:'JetBrains Mono',monospace; font-weight:700; letter-spacing:0.5px; border:1px solid var(--sell-border); }
.pill-hold { background: var(--hold-bg); color: var(--hold); padding:2px 8px; border-radius:4px; font-size:11px; font-family:'JetBrains Mono',monospace; font-weight:700; letter-spacing:0.5px; border:1px solid var(--hold-border); }

/* ═══════════════════════════════
   COMPARISON TABLE
═══════════════════════════════ */
.term-table { width:100%; border-collapse:collapse; font-family:'JetBrains Mono',monospace; font-size:12px; }
.term-table th { color: var(--cyan); border-bottom:1px solid var(--border-hi); padding:7px 10px; text-align:left; font-size:10px; letter-spacing:1.2px; text-transform:uppercase; background: var(--bg-card2); }
.term-table td { padding:6px 10px; border-bottom:1px solid var(--border); color: var(--text-1); }
.term-table tr:hover td { background: var(--bg-raised); }
.score-bull { color: var(--buy);  font-weight:700; }
.score-bear { color: var(--sell); font-weight:700; }
.score-neut { color: var(--hold); font-weight:700; }

/* ═══════════════════════════════
   FEAR & GREED BAR
═══════════════════════════════ */
.fg-bar-wrap { background: var(--border-hi); height:10px; border-radius:4px; margin:4px 0 2px; overflow:hidden; }
.fg-bar-fill { height:10px; border-radius:4px; }
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
        PriceData.timestamp >= datetime.now() - timedelta(hours=hrs),
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
        SentimentSnapshot.timestamp >= datetime.now() - timedelta(hours=hrs)
    ).order_by(SentimentSnapshot.timestamp).all()
    session.close()
    if not rows: return pd.DataFrame()
    return pd.DataFrame([{"coin": r.coin, "timestamp": r.timestamp,
                          "score": r.avg_score, "label": r.label, "samples": r.sample_count} for r in rows])

@st.cache_data(ttl=60)
def get_whales(hrs):
    session = get_session()
    rows = session.query(WhaleTransaction).filter(
        WhaleTransaction.timestamp >= datetime.now() - timedelta(hours=hrs)
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
    c24 = datetime.now() - timedelta(hours=24)
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

@st.cache_data(ttl=60)
def get_model_stats() -> dict:
    """Load accuracy + variance from models/model_stats.json written by training."""
    import json, os
    path = os.path.join("models", "model_stats.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}

@st.cache_data(ttl=300)
def get_price_forecast(coin: str, current_price: float):
    """Use Prophet model to generate multi-horizon price forecasts."""
    from src.model import ProphetPredictor
    predictor = ProphetPredictor()
    forecasts = {}
    for hrs in [1, 4, 6, 24]:
        try:
            result = predictor.predict(coin, horizon_hours=hrs)
            if "error" not in result and current_price:
                chg = result.get("change_pct", 0)
                forecasts[hrs] = {
                    "direction": result["direction"],
                    "change_pct": chg,
                    "predicted_price": current_price * (1 + chg / 100),
                    "confidence": result.get("confidence", 0),
                }
            else:
                forecasts[hrs] = None
        except Exception:
            forecasts[hrs] = None
    return forecasts


# ═══════════════════════════════════════════════════════════════
#  SIDEBAR
# ═══════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("""
    <div style="padding:0.25rem 0 0.8rem;border-bottom:1px solid var(--border);margin-bottom:0.75rem;">
      <div style="font-family:'JetBrains Mono',monospace;font-size:0.95rem;font-weight:700;color:var(--text-1);">
        ▲ CRYPTO<span style="background:linear-gradient(90deg,#1a6aff,#00d4ff);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;">TERMINAL</span>
      </div>
      <div style="font-size:0.58rem;color:var(--text-3);letter-spacing:1.5px;margin-top:3px;text-transform:uppercase;">Intelligence Platform v1.0</div>
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
    if st.button("REFRESH NOW", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    # Pipeline status
    try:
        _sess = get_session()
        _latest = _sess.query(Signal).order_by(Signal.timestamp.desc()).first()
        _sess.close()
        if _latest:
            _age = (datetime.now() - _latest.timestamp).total_seconds() / 60
            if _age > 10:
                st.markdown(f'<div style="font-size:0.62rem;color:#e3b341;font-family:\'JetBrains Mono\',monospace;padding:2px 0;">Pipeline idle {_age:.0f}m — run python main.py</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div style="font-size:0.62rem;color:#3fb950;font-family:\'JetBrains Mono\',monospace;padding:2px 0;">Pipeline active ({_age:.0f}m ago)</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div style="font-size:0.62rem;color:#f85149;font-family:\'JetBrains Mono\',monospace;padding:2px 0;">No signals — run python main.py</div>', unsafe_allow_html=True)
    except Exception:
        pass

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


hours = {"6h": 6, "12h": 12, "24h": 24, "48h": 48, "7d": 168}.get(time_window, 24)

# ═══════════════════════════════════════════════════════════════
#  TOP HEADER BAR
# ═══════════════════════════════════════════════════════════════
now_str = datetime.now().strftime("%Y-%m-%d  %H:%M:%S IST")
st.markdown(f"""
<div class="terminal-header">
  <div style="display:flex;align-items:center;gap:14px;">
    <div class="terminal-logo">
      ▲ CRYPTO<span class="logo-accent">TERMINAL</span><span class="logo-dim">&nbsp;PRO</span>
    </div>
    <div class="terminal-status">
      <span class="status-pill pill-live">● LIVE</span>
      <span class="status-pill pill-ai">AI</span>
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
    <div class="stats-icon">N</div>
    <div><div class="stats-label">News 24h</div><div class="stats-val">{stats['news']}</div></div>
  </div>
  <div class="stats-cell">
    <div class="stats-icon">TG</div>
    <div><div class="stats-label">Telegram 24h</div><div class="stats-val">{stats['reddit']}</div></div>
  </div>
  <div class="stats-cell">
    <div class="stats-icon" style="color:var(--buy);">SIG</div>
    <div><div class="stats-label">Signals 24h</div><div class="stats-val">{stats['signals']}</div></div>
  </div>
  <div class="stats-cell">
    <div class="stats-icon" style="color:var(--purple);">WH</div>
    <div><div class="stats-label">Whale Txns</div><div class="stats-val">{stats['whales']}</div></div>
  </div>
  <div class="stats-cell">
    <div class="stats-icon">CV</div>
    <div><div class="stats-label">Candles</div><div class="stats-val">{stats['candles']}</div></div>
  </div>
  <div class="stats-cell">
    <div class="stats-icon" style="color:var(--hold);">TW</div>
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
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "MARKET OVERVIEW", "SENTIMENT INTEL", "PREDICTIONS", "WHALE TRACKER", "BACKTESTING", "PAPER TRADING"
])


# ────────────────────────────────────────────────────────────────
#  TAB 1 — MARKET OVERVIEW
# ────────────────────────────────────────────────────────────────
with tab1:
    # ── Mini coin sparkline cards (one per selected coin) ──────────
    _display_coins = selected_coins if selected_coins else list(COINS.keys())[:4]
    _mini_cols = st.columns(len(_display_coins), gap="small")
    for _mi, _mc in enumerate(_display_coins):
        with _mini_cols[_mi]:
            _spark_df = get_prices(_mc, 24)
            _cp = live_prices.get(_mc)
            _ms_sig = all_signals.get(_mc, {})
            _ms_type = _ms_sig.get("type", "N/A")
            _sig_hex = {"BUY": "#00e676", "SELL": "#ff3352", "HOLD": "#ffb300"}.get(_ms_type, "#374e6e")

            if not _spark_df.empty and _cp:
                # Remove outliers: keep only prices within 3 std of the median
                _prices = _spark_df["close"]
                _med, _std = _prices.median(), _prices.std()
                _clean_df = _spark_df[(_prices - _med).abs() <= 3 * (_std if _std > 0 else _med * 0.05)]
                if _clean_df.empty:
                    _clean_df = _spark_df

                _old_p = _clean_df["close"].iloc[0]
                _chg24 = (_cp - _old_p) / _old_p * 100 if _old_p else 0
                _lc = "#00e676" if _chg24 >= 0 else "#ff3352"
                _fc = "rgba(0,230,118,0.08)" if _chg24 >= 0 else "rgba(255,51,82,0.08)"
                _sym = "▲" if _chg24 >= 0 else "▼"

                # Tight y-axis: 0.3% padding around actual price range
                _ymin = _clean_df["close"].min()
                _ymax = _clean_df["close"].max()
                _ypad = (_ymax - _ymin) * 0.15 or _ymin * 0.003
                _yrange = [_ymin - _ypad, _ymax + _ypad * 4]  # extra top room for labels

                _fig_spark = go.Figure()
                _fig_spark.add_trace(go.Scatter(
                    x=_clean_df["timestamp"], y=_clean_df["close"],
                    mode="lines", fill="tozeroy",
                    fillcolor=_fc,
                    line=dict(color=_lc, width=1.5), showlegend=False,
                    hovertemplate="%{y:$,.2f}<extra></extra>",
                ))
                _fig_spark.update_layout(
                    height=150,
                    margin=dict(l=6, r=6, t=8, b=4),
                    paper_bgcolor="rgba(7,13,26,1)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    xaxis=dict(visible=False, fixedrange=True),
                    yaxis=dict(visible=False, fixedrange=True, range=_yrange),
                )
                # Header info rendered above the chart via markdown (no annotation overlap)
                _sig_badge_bg = {"BUY": "rgba(0,230,118,0.12)", "SELL": "rgba(255,51,82,0.12)",
                                 "HOLD": "rgba(255,179,0,0.12)"}.get(_ms_type, "rgba(255,255,255,0.04)")
                st.markdown(f"""
                <div style="background:#070d1a;border:1px solid #0e1d32;border-radius:8px;
                            padding:0.55rem 0.75rem 0.2rem;margin-bottom:-6px;">
                  <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                    <div>
                      <div style="font-family:'JetBrains Mono',monospace;font-size:0.6rem;
                                  color:#6b85a8;letter-spacing:1.5px;font-weight:700;">{_mc}/USDT</div>
                      <div style="font-family:'JetBrains Mono',monospace;font-size:1.05rem;
                                  font-weight:700;color:#dce8ff;line-height:1.2;">{fmt_price(_cp)}</div>
                      <div style="font-family:'JetBrains Mono',monospace;font-size:0.7rem;
                                  font-weight:600;color:{_lc};">{_sym} {abs(_chg24):.2f}%</div>
                    </div>
                    <span style="font-family:'JetBrains Mono',monospace;font-size:0.6rem;
                                 font-weight:700;color:{_sig_hex};background:{_sig_badge_bg};
                                 border:1px solid {_sig_hex};padding:2px 7px;border-radius:4px;
                                 letter-spacing:0.5px;">{_ms_type}</span>
                  </div>
                </div>""", unsafe_allow_html=True)
                st.plotly_chart(_fig_spark, use_container_width=True, config={"displayModeBar": False})
            else:
                st.markdown(f"""
                <div style="height:145px;background:#070d1a;border:1px solid #0e1d32;border-radius:8px;
                     display:flex;align-items:center;justify-content:center;">
                  <span style="font-family:'JetBrains Mono',monospace;font-size:0.65rem;color:#374e6e;">{_mc} — NO DATA</span>
                </div>""", unsafe_allow_html=True)

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
        _ctab_hdr_col, _ctab_toggle_col = st.columns([2, 1], gap="small")
        with _ctab_hdr_col:
            st.markdown(f'<div class="sec-label">{chart_coin}/USDT · {time_window} · 15m candles</div>', unsafe_allow_html=True)
        with _ctab_toggle_col:
            _chart_mode = st.radio(
                "Chart Mode", ["PLOTLY", "TRADINGVIEW"],
                horizontal=True, key="chart_mode_radio",
                label_visibility="collapsed",
            )

        # ── TradingView Advanced Chart ──
        if _chart_mode == "TRADINGVIEW":
            _tv_sym_map = {"BTC": "BINANCE:BTCUSDT", "ETH": "BINANCE:ETHUSDT",
                           "SOL": "BINANCE:SOLUSDT", "XRP": "BINANCE:XRPUSDT",
                           "DOGE": "BINANCE:DOGEUSDT"}
            _tv_int_map = {"6h": "15", "12h": "30", "24h": "60", "48h": "240", "7d": "D"}
            _tv_sym = _tv_sym_map.get(chart_coin, f"BINANCE:{chart_coin}USDT")
            _tv_int = _tv_int_map.get(time_window, "60")
            import streamlit.components.v1 as _stc
            _stc.html(f"""
            <div id="tv_chart_container" style="height:520px;background:#060a12;border-radius:6px;overflow:hidden;border:1px solid #161b22;">
              <div class="tradingview-widget-container" style="height:100%;width:100%;">
                <div class="tradingview-widget-container__widget" style="height:100%;width:100%;"></div>
                <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js" async>
                {{
                  "autosize": true,
                  "symbol": "{_tv_sym}",
                  "interval": "{_tv_int}",
                  "timezone": "Asia/Kolkata",
                  "theme": "dark",
                  "style": "1",
                  "locale": "en",
                  "backgroundColor": "rgba(6,10,18,1)",
                  "gridColor": "rgba(22,27,34,1)",
                  "hide_top_toolbar": false,
                  "hide_legend": false,
                  "save_image": false,
                  "allow_symbol_change": false,
                  "studies": ["STD;RSI","STD;MACD"],
                  "support_host": "https://www.tradingview.com"
                }}
                </script>
              </div>
            </div>
            """, height=530)
            pdf = pd.DataFrame()  # skip plotly block when TradingView is active

        else:
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

            # ── Market Regime row (SRL microstructure features) ──
            try:
                if "vol_regime" not in pdf.columns:
                    pdf["vol_regime"] = pdf["volatility_24"] / (pdf["volatility_96"] + 1e-10) if "volatility_24" in pdf.columns and "volatility_96" in pdf.columns else float("nan")
                if "zscore_ret5" not in pdf.columns:
                    ret5 = pdf["close"].pct_change(5)
                    pdf["zscore_ret5"] = (ret5 - ret5.rolling(100).mean()) / (ret5.rolling(100).std() + 1e-10)

                vr = pdf["vol_regime"].iloc[-1] if "vol_regime" in pdf.columns else float("nan")
                zr = pdf["zscore_ret5"].iloc[-1] if "zscore_ret5" in pdf.columns else float("nan")

                import math
                vr_ok = not (math.isnan(vr) if isinstance(vr, float) else False)
                zr_ok = not (math.isnan(zr) if isinstance(zr, float) else False)

                vr_label = "HIGH" if vr_ok and vr > 1.2 else "LOW" if vr_ok and vr < 0.8 else "NORMAL"
                vr_color = "#f85149" if vr_label == "HIGH" else "#3fb950" if vr_label == "LOW" else "#e3b341"
                zr_label = "MEAN-REV" if zr_ok and abs(zr) > 2 else "TRENDING" if zr_ok and abs(zr) < 0.5 else "RANGING"
                zr_color = "#bc8cff" if zr_label == "MEAN-REV" else "#58a6ff" if zr_label == "TRENDING" else "#8b949e"

                st.markdown(f"""
                <div style="display:flex;gap:1px;background:#161b22;border-radius:4px;overflow:hidden;margin-top:3px;">
                  <div style="flex:1.2;background:#070b14;padding:0.3rem 0.6rem;display:flex;align-items:center;">
                    <span style="font-size:0.55rem;color:#484f58;text-transform:uppercase;letter-spacing:1px;font-family:'JetBrains Mono',monospace;">MARKET REGIME</span>
                  </div>
                  <div style="flex:1;background:#0d1117;padding:0.3rem 0.5rem;text-align:center;">
                    <div style="font-size:0.55rem;color:#484f58;letter-spacing:1px;">VOL REGIME</div>
                    <div style="font-family:'JetBrains Mono',monospace;font-size:0.75rem;font-weight:600;color:{vr_color};">{vr_label} <span style="color:#484f58;font-size:0.6rem;">({vr:.2f})</span></div>
                  </div>
                  <div style="flex:1;background:#0d1117;padding:0.3rem 0.5rem;text-align:center;">
                    <div style="font-size:0.55rem;color:#484f58;letter-spacing:1px;">Z-SCORE RET5</div>
                    <div style="font-family:'JetBrains Mono',monospace;font-size:0.75rem;font-weight:600;color:{zr_color};">{zr_label} <span style="color:#484f58;font-size:0.6rem;">({zr:+.2f})</span></div>
                  </div>
                  <div style="flex:1;background:#0d1117;padding:0.3rem 0.5rem;text-align:center;">
                    <div style="font-size:0.55rem;color:#484f58;letter-spacing:1px;">FEATURES</div>
                    <div style="font-family:'JetBrains Mono',monospace;font-size:0.75rem;font-weight:600;color:#a78bfa;">27 ACTIVE</div>
                  </div>
                </div>
                """, unsafe_allow_html=True)
            except Exception:
                pass

        else:
            st.markdown("""
            <div style="height:400px;display:flex;align-items:center;justify-content:center;
                 background:#0d1117;border:1px solid #161b22;border-radius:6px;color:#484f58;font-size:0.75rem;font-family:'JetBrains Mono',monospace;letter-spacing:1px;">
              -- NO DATA -- [ START PIPELINE: python main.py --skip-history ]
            </div>""", unsafe_allow_html=True)

    # ── Right: Signal + Sentiment ──
    with col_signal:
        _mstats = get_model_stats()
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

            # Pull best available model stats (xgboost preferred over prophet)
            _ms = _mstats.get(f"{coin}_xgboost") or _mstats.get(f"{coin}_prophet") or {}
            _acc = _ms.get("accuracy")
            _var = _ms.get("variance")
            _acc_html = f"{_acc:.1%}" if _acc is not None else "—"
            _var_html = f"{_var:.4f}" if _var is not None else "—"
            _acc_color = "#3fb950" if (_acc or 0) >= 0.6 else "#e3b341" if (_acc or 0) >= 0.5 else "#f85149"

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
              <div class="sp-row"><span class="sp-key">Model Accuracy</span><span class="sp-val" style="color:{_acc_color};font-weight:600;">{_acc_html}</span></div>
              <div class="sp-row"><span class="sp-key">Model Variance</span><span class="sp-val" style="color:#8b949e;">{_var_html}</span></div>
              <div class="sp-row"><span class="sp-key">Updated</span><span class="sp-val" style="color:#484f58;font-size:0.6rem;">{sig.get('time').strftime('%H:%M:%S') if sig.get('time') else '—'}</span></div>
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

    # ── Crypto Market Heatmap (treemap) ────────────────────────────
    st.markdown('<div class="sec-label" style="margin-top:0.5rem;">Crypto Market Heatmap — 24h Performance</div>', unsafe_allow_html=True)
    _hm_rows = []
    for _hc in list(COINS.keys()):
        _hp = live_prices.get(_hc)
        _hpdf = get_prices(_hc, 24)
        if _hp and not _hpdf.empty:
            _ho = _hpdf["close"].iloc[0]
            _hchg = (_hp - _ho) / _ho * 100 if _ho else 0
            _hsig = all_signals.get(_hc, {}).get("type", "—")
            _hm_rows.append({"Coin": _hc, "chg": round(_hchg, 2), "size": 1,
                              "label": f"<b>{_hc}</b><br>{_hchg:+.2f}%", "sig": _hsig})
    if _hm_rows:
        _hm_df = pd.DataFrame(_hm_rows)
        _fig_hm = px.treemap(
            _hm_df, path=["Coin"], values="size", color="chg",
            color_continuous_scale=[[0, "#7f0a20"], [0.35, "#ff3352"],
                                     [0.5, "#0c1424"],
                                     [0.65, "#00e676"], [1, "#005c32"]],
            color_continuous_midpoint=0,
            custom_data=["Coin", "chg", "sig"],
        )
        _fig_hm.update_traces(
            texttemplate="<b>%{customdata[0]}</b><br>%{customdata[1]:+.2f}%",
            textfont=dict(size=14, family="JetBrains Mono", color="white"),
            hovertemplate="<b>%{customdata[0]}</b><br>24h: %{customdata[1]:+.2f}%<br>Signal: %{customdata[2]}<extra></extra>",
            marker=dict(line=dict(width=1.5, color="#04080f")),
        )
        _fig_hm.update_layout(
            height=200, margin=dict(l=0, r=0, t=0, b=0),
            paper_bgcolor="rgba(0,0,0,0)",
            coloraxis_showscale=False,
        )
        st.plotly_chart(_fig_hm, use_container_width=True, config={"displayModeBar": False})
    else:
        st.markdown('<div style="height:160px;background:#070d1a;border:1px solid #0e1d32;border-radius:8px;display:flex;align-items:center;justify-content:center;font-family:\'JetBrains Mono\',monospace;font-size:0.65rem;color:#374e6e;">No price data — run python main.py</div>', unsafe_allow_html=True)


# ────────────────────────────────────────────────────────────────
#  TAB 2 — SENTIMENT INTEL
# ────────────────────────────────────────────────────────────────
with tab2:
    sdf = get_sentiments(selected_coins, hours)

    # ── Sentiment Gauge Row ──────────────────────────────────────
    _sg_cols = st.columns([1, 2], gap="small")
    with _sg_cols[0]:
        st.markdown('<div class="sec-label">Market Sentiment Gauge</div>', unsafe_allow_html=True)
        if not sdf.empty:
            _sg_latest = sdf.groupby("coin").last().reset_index()
            _sg_avg = float(_sg_latest["score"].mean())
        else:
            _sg_avg = 0.5
        _sg_pct = _sg_avg * 100
        _sg_color = "#00e676" if _sg_avg > 0.6 else "#ff3352" if _sg_avg < 0.4 else "#ffb300"
        _sg_label = "GREED" if _sg_avg > 0.6 else "FEAR" if _sg_avg < 0.4 else "NEUTRAL"
        _fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=_sg_pct,
            number={"suffix": "%", "font": {"size": 22, "color": _sg_color, "family": "JetBrains Mono"}},
            domain={"x": [0, 1], "y": [0, 1]},
            title={"text": f"<b>{_sg_label}</b>", "font": {"size": 11, "color": _sg_color, "family": "JetBrains Mono"}},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 0, "tickcolor": "#162a47",
                         "tickfont": {"size": 8, "color": "#374e6e", "family": "JetBrains Mono"}},
                "bar": {"color": _sg_color, "thickness": 0.25},
                "bgcolor": "rgba(0,0,0,0)",
                "borderwidth": 0,
                "steps": [
                    {"range": [0, 33],  "color": "rgba(255,51,82,0.12)"},
                    {"range": [33, 66], "color": "rgba(255,179,0,0.08)"},
                    {"range": [66, 100],"color": "rgba(0,230,118,0.12)"},
                ],
                "threshold": {"line": {"color": "#00d4ff", "width": 2},
                              "thickness": 0.75, "value": 50},
            },
        ))
        _fig_gauge.update_layout(
            height=180, margin=dict(l=10, r=10, t=30, b=10),
            paper_bgcolor="rgba(7,13,26,1)",
            font=dict(color="#dce8ff", family="JetBrains Mono"),
        )
        st.plotly_chart(_fig_gauge, use_container_width=True, config={"displayModeBar": False})

    with _sg_cols[1]:
        st.markdown('<div class="sec-label">Per-Coin Sentiment</div>', unsafe_allow_html=True)
        if not sdf.empty:
            _sg_latest2 = sdf.groupby("coin").last().reset_index()
            _fig_bars = go.Figure()
            for _, _sgr in _sg_latest2.iterrows():
                _bc = "#00e676" if _sgr["score"] > 0.6 else "#ff3352" if _sgr["score"] < 0.4 else "#ffb300"
                _fig_bars.add_trace(go.Bar(
                    x=[_sgr["coin"]], y=[_sgr["score"] * 100],
                    marker_color=_bc, marker_opacity=0.85,
                    name=_sgr["coin"], showlegend=False,
                    text=[f"{_sgr['score']:.2f}"], textposition="outside",
                    textfont=dict(size=10, color=_bc, family="JetBrains Mono"),
                ))
            _fig_bars.add_hline(y=50, line_dash="dot", line_color="#374e6e", line_width=1)
            _fig_bars.update_layout(
                height=180, margin=dict(l=0, r=0, t=10, b=0),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(tickfont=dict(size=10, color="#6b85a8", family="JetBrains Mono"),
                           gridcolor="rgba(0,0,0,0)"),
                yaxis=dict(range=[0, 110], tickfont=dict(size=9, color="#374e6e"),
                           gridcolor="#0e1d32", gridwidth=1, zeroline=False),
                bargap=0.35,
            )
            st.plotly_chart(_fig_bars, use_container_width=True, config={"displayModeBar": False})
        else:
            st.markdown('<div style="height:150px;display:flex;align-items:center;justify-content:center;color:#374e6e;font-size:0.68rem;font-family:\'JetBrains Mono\',monospace;">No sentiment data</div>', unsafe_allow_html=True)

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
                for coin, pub, src, title, _raw_lbl, score in all_news_rows:
                    try:
                        _s = float(score)
                        sent_lbl = "BULLISH" if _s > 0.70 else "BEARISH" if _s < 0.30 else "NEUTRAL"
                    except (ValueError, TypeError):
                        sent_lbl = _raw_lbl
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

    # ── Price Forecast Cards (1h / 4h / 6h / 24h) ─────────────
    st.markdown("""
    <style>
    .forecast-header {
      display:flex; align-items:center; justify-content:space-between;
      margin-bottom:0.6rem;
    }
    .forecast-coin-select { font-size:0.6rem; color:#484f58; letter-spacing:1.5px; text-transform:uppercase; }
    .fc-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:6px; margin-bottom:0.75rem; }
    .fc-card {
      background:#0d1117; border:1px solid #161b22; border-radius:6px;
      padding:0.75rem 0.85rem; position:relative; overflow:hidden;
    }
    .fc-card::before {
      content:''; position:absolute; top:0; left:0; right:0; height:2px;
    }
    .fc-card-up::before   { background:linear-gradient(90deg,#3fb950,#1a7f37); }
    .fc-card-down::before { background:linear-gradient(90deg,#f85149,#b91c1c); }
    .fc-card-side::before { background:linear-gradient(90deg,#e3b341,#92400e); }
    .fc-horizon { font-size:0.58rem; color:#484f58; letter-spacing:1.5px; text-transform:uppercase; margin-bottom:0.4rem; font-weight:600; }
    .fc-price { font-family:'JetBrains Mono',monospace; font-size:1.1rem; font-weight:700; color:#f0f6fc; margin-bottom:2px; }
    .fc-chg-up   { font-family:'JetBrains Mono',monospace; font-size:0.72rem; color:#3fb950; font-weight:600; }
    .fc-chg-down { font-family:'JetBrains Mono',monospace; font-size:0.72rem; color:#f85149; font-weight:600; }
    .fc-chg-side { font-family:'JetBrains Mono',monospace; font-size:0.72rem; color:#e3b341; font-weight:600; }
    .fc-dir { font-size:0.65rem; font-weight:700; letter-spacing:1px; margin-top:4px; display:inline-flex; align-items:center; gap:4px; }
    .fc-dir-up   { color:#3fb950; }
    .fc-dir-down { color:#f85149; }
    .fc-dir-side { color:#e3b341; }
    .fc-conf { font-size:0.6rem; color:#484f58; margin-top:3px; }
    .fc-conf-bar { height:3px; background:#161b22; border-radius:2px; margin-top:3px; }
    .fc-conf-fill { height:3px; border-radius:2px; }
    .fc-no-model {
      display:flex; flex-direction:column; align-items:center; justify-content:center;
      height:90px; color:#484f58; font-size:0.7rem; font-family:'JetBrains Mono',monospace;
      letter-spacing:1px;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="sec-label">Price Forecast — ML Multi-Horizon Predictions</div>', unsafe_allow_html=True)

    _fc_coins = selected_coins or list(COINS.keys())
    _fc_col1, _fc_col2 = st.columns([1, 4], gap="small")
    with _fc_col1:
        forecast_coin = st.selectbox("Forecast Coin", _fc_coins, key="forecast_coin_sel", label_visibility="collapsed")
    with _fc_col2:
        _cur_p = live_prices.get(forecast_coin)
        if _cur_p:
            _cur_sig = all_signals.get(forecast_coin, {})
            _cur_dir = _cur_sig.get("prediction", "—") or "—"
            _dir_c = "#3fb950" if _cur_dir == "UP" else "#f85149" if _cur_dir == "DOWN" else "#e3b341"
            st.markdown(f"""
            <div style="display:flex;align-items:center;gap:16px;height:100%;padding:0.25rem 0;">
              <span style="font-family:'JetBrains Mono',monospace;font-size:1.2rem;font-weight:700;color:#f0f6fc;">{fmt_price(_cur_p)}</span>
              <span style="font-size:0.65rem;color:#484f58;font-family:'JetBrains Mono',monospace;">CURRENT · {forecast_coin}/USDT</span>
              <span style="font-size:0.68rem;font-weight:700;color:{_dir_c};font-family:'JetBrains Mono',monospace;letter-spacing:1px;">ML → {_cur_dir}</span>
            </div>""", unsafe_allow_html=True)

    _cur_price = live_prices.get(forecast_coin)
    if _cur_price:
        with st.spinner("Loading forecasts..."):
            _forecasts = get_price_forecast(forecast_coin, _cur_price)

        _horizon_labels = {1: "1 HOUR", 4: "4 HOURS", 6: "6 HOURS", 24: "24 HOURS"}
        _fc_cards = ""
        for hrs in [1, 4, 6, 24]:
            fc = _forecasts.get(hrs)
            lbl = _horizon_labels[hrs]
            if fc:
                d   = fc["direction"]
                chg = fc["change_pct"]
                pp  = fc["predicted_price"]
                conf = fc["confidence"]
                card_cls = "fc-card-up" if d == "UP" else "fc-card-down" if d == "DOWN" else "fc-card-side"
                chg_cls  = "fc-chg-up"  if d == "UP" else "fc-chg-down"  if d == "DOWN" else "fc-chg-side"
                dir_cls  = "fc-dir-up"  if d == "UP" else "fc-dir-down"  if d == "DOWN" else "fc-dir-side"
                arrow    = "▲" if d == "UP" else "▼" if d == "DOWN" else "◆"
                conf_bar_color = "#3fb950" if d == "UP" else "#f85149" if d == "DOWN" else "#e3b341"
                conf_pct = int(conf * 100)
                _fc_cards += f"""
                <div class="fc-card {card_cls}">
                  <div class="fc-horizon">{lbl}</div>
                  <div class="fc-price">{fmt_price(pp)}</div>
                  <div class="{chg_cls}">{'+'if chg>=0 else ''}{chg:.2f}%</div>
                  <div class="fc-dir {dir_cls}">{arrow} {d}</div>
                  <div class="fc-conf">Confidence: {conf_pct}%</div>
                  <div class="fc-conf-bar"><div class="fc-conf-fill" style="width:{conf_pct}%;background:{conf_bar_color};"></div></div>
                </div>"""
            else:
                _fc_cards += f"""
                <div class="fc-card fc-card-side">
                  <div class="fc-horizon">{lbl}</div>
                  <div class="fc-no-model">— NO MODEL —<br><span style="font-size:0.58rem;margin-top:3px;">run main.py to train</span></div>
                </div>"""
        st.markdown(f'<div class="fc-grid">{_fc_cards}</div>', unsafe_allow_html=True)

        # ── Model Accuracy & Variance panel ──────────────────────
        _all_ms = get_model_stats()
        _model_rows = ""
        for _mn in ["xgboost", "lstm", "prophet"]:
            _mk = f"{forecast_coin}_{_mn}"
            _ms = _all_ms.get(_mk)
            if not _ms:
                continue
            _a = _ms.get("accuracy", 0)
            _v = _ms.get("variance", 0)
            _a_c = "#3fb950" if _a >= 0.6 else "#e3b341" if _a >= 0.5 else "#f85149"
            _trained = _ms.get("trained_at", "")[:16].replace("T", " ") if _ms.get("trained_at") else "—"
            _model_rows += f"""
            <div style="display:grid;grid-template-columns:90px 1fr 1fr 1fr;gap:6px;align-items:center;
                        padding:0.4rem 0.6rem;border-bottom:1px solid #161b22;">
              <span style="font-family:'JetBrains Mono',monospace;font-size:0.62rem;color:#8b949e;font-weight:600;text-transform:uppercase;">{_mn}</span>
              <div>
                <div style="font-size:0.55rem;color:#484f58;letter-spacing:0.8px;margin-bottom:2px;">ACCURACY</div>
                <span style="font-family:'JetBrains Mono',monospace;font-size:0.85rem;font-weight:700;color:{_a_c};">{_a:.1%}</span>
                <div style="height:3px;background:#161b22;border-radius:2px;margin-top:3px;">
                  <div style="height:3px;width:{int(_a*100)}%;background:{_a_c};border-radius:2px;"></div>
                </div>
              </div>
              <div>
                <div style="font-size:0.55rem;color:#484f58;letter-spacing:0.8px;margin-bottom:2px;">VARIANCE</div>
                <span style="font-family:'JetBrains Mono',monospace;font-size:0.85rem;font-weight:700;color:#58a6ff;">{_v:.4f}</span>
                <div style="font-size:0.55rem;color:#484f58;margin-top:2px;">{'LOW' if _v < 0.05 else 'MED' if _v < 0.15 else 'HIGH'} volatility</div>
              </div>
              <div style="font-size:0.58rem;color:#484f58;">Trained<br>{_trained} UTC</div>
            </div>"""
        if _model_rows:
            st.markdown(f"""
            <div style="background:#0d1117;border:1px solid #161b22;border-radius:6px;margin-bottom:0.75rem;">
              <div style="padding:0.45rem 0.6rem;border-bottom:1px solid #161b22;">
                <span style="font-size:0.6rem;color:#484f58;letter-spacing:1.5px;text-transform:uppercase;font-weight:600;">Model Performance — {forecast_coin}</span>
              </div>
              {_model_rows}
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="font-size:0.68rem;color:#484f58;padding:0.5rem 0;">
              No model stats yet — run <code style="color:#58a6ff;">python main.py</code> to train models.
            </div>""", unsafe_allow_html=True)

        # Forecast sparkline — show Prophet's predicted trajectory
        try:
            from src.model import ProphetPredictor as _PP
            _pm = _PP()
            _pm_model = _pm.models.get(forecast_coin)
            if not _pm_model:
                import os, pickle
                _pm_path = os.path.join("models", f"prophet_{forecast_coin}.pkl")
                if os.path.exists(_pm_path):
                    with open(_pm_path, "rb") as _pf:
                        _pm_model = pickle.load(_pf)
            if _pm_model:
                _future = _pm_model.make_future_dataframe(periods=96, freq="15min")
                _fcast  = _pm_model.predict(_future)
                _last96 = _fcast.tail(96)
                _hist96 = _fcast.iloc[-200:-96] if len(_fcast) > 200 else _fcast.iloc[:-96]

                _colors_map = {"BTC":"#f7931a","ETH":"#627eea","SOL":"#9945ff","XRP":"#346aa9","DOGE":"#c2a633"}
                _coin_color = _colors_map.get(forecast_coin, "#58a6ff")

                fig_fc = go.Figure()
                fig_fc.add_trace(go.Scatter(
                    x=_hist96["ds"], y=_hist96["yhat"],
                    mode="lines", name="History",
                    line=dict(color="#484f58", width=1),
                    showlegend=False,
                ))
                fig_fc.add_trace(go.Scatter(
                    x=pd.concat([_hist96["ds"].tail(1), _last96["ds"]]),
                    y=pd.concat([_hist96["yhat"].tail(1), _last96["yhat"]]),
                    mode="lines", name="Forecast",
                    line=dict(color=_coin_color, width=2, dash="dot"),
                    showlegend=False,
                ))
                fig_fc.add_trace(go.Scatter(
                    x=pd.concat([_last96["ds"], _last96["ds"].iloc[::-1]]),
                    y=pd.concat([_last96["yhat_upper"], _last96["yhat_lower"].iloc[::-1]]),
                    fill="toself", fillcolor=f"rgba{tuple(int(_coin_color.lstrip('#')[i:i+2],16) for i in (0,2,4))+(0.08,)}",
                    line=dict(color="rgba(0,0,0,0)"), showlegend=False, name="CI"
                ))
                # Vertical line at now
                fig_fc.add_vline(
                    x=_hist96["ds"].iloc[-1], line_dash="dot",
                    line_color="#30363d", line_width=1,
                    annotation_text="NOW", annotation_font=dict(size=8, color="#484f58"),
                )
                fig_fc.update_layout(
                    height=200, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    margin=dict(l=0, r=0, t=4, b=0), showlegend=False,
                    xaxis=dict(showgrid=False, color="#484f58", tickfont=dict(size=8), zeroline=False),
                    yaxis=dict(gridcolor="#161b22", color="#484f58", tickfont=dict(size=8, family="JetBrains Mono"),
                               zeroline=False, side="right"),
                    hovermode="x unified",
                    hoverlabel=dict(bgcolor="#161b22", bordercolor="#30363d",
                                    font=dict(family="JetBrains Mono", size=10)),
                )
                st.markdown('<div class="sec-label">Forecast Trajectory — Prophet Model (next 24h)</div>', unsafe_allow_html=True)
                st.plotly_chart(fig_fc, use_container_width=True, config={"displayModeBar": False})
        except Exception:
            pass
    else:
        st.markdown('<div style="font-size:0.7rem;color:#484f58;padding:0.5rem 0;">No live price — start pipeline: python main.py</div>', unsafe_allow_html=True)

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

    # ── ML Intelligence Panel ────────────────────────────────────
    st.markdown('<div class="sec-label" style="margin-top:0.75rem;">ML Intelligence</div>', unsafe_allow_html=True)
    st.markdown("""
    <div style="display:grid;grid-template-columns:1fr;gap:6px;margin-top:4px;">
      <div style="background:#070b14;border:1px solid #161b22;border-radius:4px;padding:0.6rem 0.8rem;">
        <div style="font-size:0.58rem;color:#484f58;letter-spacing:1px;margin-bottom:0.4rem;">FEATURE GROUPS</div>
        <div style="display:flex;flex-direction:column;gap:4px;">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <span style="font-size:0.65rem;color:#8b949e;">Technical Indicators</span>
            <span style="font-family:'JetBrains Mono',monospace;font-size:0.68rem;color:#58a6ff;">22</span>
          </div>
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <span style="font-size:0.65rem;color:#8b949e;">Sentiment Signals</span>
            <span style="font-family:'JetBrains Mono',monospace;font-size:0.68rem;color:#3fb950;">3</span>
          </div>
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <span style="font-size:0.65rem;color:#8b949e;">On-Chain / Whale</span>
            <span style="font-family:'JetBrains Mono',monospace;font-size:0.68rem;color:#e3b341;">2</span>
          </div>
          <div style="border-top:1px solid #161b22;margin-top:2px;padding-top:4px;display:flex;justify-content:space-between;align-items:center;">
            <span style="font-size:0.65rem;color:#c9d1d9;font-weight:600;">Total Features</span>
            <span style="font-family:'JetBrains Mono',monospace;font-size:0.75rem;color:#a78bfa;font-weight:700;">27</span>
          </div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

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
    # Data source badge
    _wa_active = bool(WHALE_ALERT_API_KEY)
    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:0.5rem;">
      <span style="font-size:0.6rem;color:#484f58;text-transform:uppercase;letter-spacing:1px;">Data Source</span>
      {'<span style="font-family:\'JetBrains Mono\',monospace;font-size:0.65rem;padding:2px 8px;background:rgba(63,185,80,0.15);border:1px solid rgba(63,185,80,0.4);border-radius:3px;color:#3fb950;">● WHALE ALERT — MULTI-CHAIN</span>' if _wa_active else '<span style="font-family:\'JetBrains Mono\',monospace;font-size:0.65rem;padding:2px 8px;background:rgba(88,166,255,0.1);border:1px solid rgba(88,166,255,0.3);border-radius:3px;color:#58a6ff;">● ETHERSCAN — ETH ONLY</span>'}
      {'<span style="font-size:0.6rem;color:#484f58;margin-left:4px;">BTC · ETH · SOL · XRP · DOGE · USDT · USDC · 20+ chains</span>' if _wa_active else '<span style="font-size:0.6rem;color:#484f58;margin-left:4px;">Set WHALE_ALERT_API_KEY for multi-chain coverage</span>'}
    </div>
    """, unsafe_allow_html=True)

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
          No whale transactions detected in the selected window.<br>
          <span style="color:#8b949e;">Etherscan API key is configured ✓ — pipeline may need more blocks or threshold adjustment</span><br>
          <span style="font-family:'JetBrains Mono',monospace;font-size:0.7rem;color:#30363d;margin-top:0.5rem;display:block;">
            [ python main.py --skip-history ]
          </span>
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
            ● Slippage 0.1% per side + 0.1% commission<br>
            ● Confidence-weighted position sizing<br>
            ● Metrics: Sharpe, Sortino, CAGR, Max DD
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
                    r1, r2, r3, r4, r5, r6, r7, r8 = st.columns(8, gap="small")
                    r1.metric("Trades",    m["total_trades"])
                    r2.metric("Win Rate",  f"{m['win_rate']:.1%}")
                    r3.metric("Sharpe",    f"{m['sharpe_ratio']:.2f}")
                    r4.metric("Sortino",   f"{m['sortino_ratio']:.2f}")
                    r5.metric("Return",    f"{m['total_return_pct']:.1f}%")
                    r6.metric("CAGR",      f"{m['cagr_pct']:.1f}%")
                    r7.metric("Max DD",    f"{m['max_drawdown_pct']:.1f}%")
                    r8.metric("Capital",   f"${m['final_capital']:,.0f}")
                    st.markdown(
                        f'<div style="font-size:0.62rem;color:#484f58;padding:0.25rem 0 0.5rem;">'
                        f'⚡ Slippage {m["slippage_pct"]:.1f}% per side &nbsp;|&nbsp; '
                        f'Commission {m["commission_pct"]:.1f}% &nbsp;|&nbsp; '
                        f'Position: confidence-weighted</div>',
                        unsafe_allow_html=True,
                    )

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

                    # Rolling Sharpe chart (126-trade window) — ported from SRL comparison_dashboard
                    if m.get("rolling_sharpe"):
                        fig_rs = go.Figure()
                        fig_rs.add_trace(go.Scatter(
                            y=m["rolling_sharpe"], mode="lines",
                            line=dict(color="#58a6ff", width=1.5),
                            name="Rolling Sharpe (126)",
                        ))
                        fig_rs.add_hline(y=0, line_dash="dot",
                                         line_color="rgba(255,255,255,0.1)", line_width=1)
                        fig_rs.add_hline(y=1, line_dash="dot",
                                         line_color="rgba(63,185,80,0.3)", line_width=1,
                                         annotation_text="Sharpe = 1",
                                         annotation_font=dict(size=8, color="#3fb950"))
                        fig_rs.update_layout(
                            height=140,
                            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                            margin=dict(l=0, r=0, t=20, b=0), showlegend=False,
                            title=dict(text="Rolling Sharpe (126-trade window)",
                                       font=dict(size=9, color="#484f58"), x=0),
                            xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
                            yaxis=dict(gridcolor="#161b22", zeroline=False,
                                       tickfont=dict(size=9, family="JetBrains Mono"),
                                       color="#484f58", side="right"),
                        )
                        st.plotly_chart(fig_rs, use_container_width=True,
                                        config={"displayModeBar": False})

                    if m.get("trades"):
                        # Select only display columns — backtester now returns extra slip cols
                        trade_df = pd.DataFrame(m["trades"])[
                            ["coin", "signal_type", "entry", "exit", "pnl_pct", "correct", "confidence"]
                        ]
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


# ────────────────────────────────────────────────────────────────
#  TAB 6 — PAPER TRADING
# ────────────────────────────────────────────────────────────────
with tab6:
    from src.paper_trader import PaperTrader
    from config import BINANCE_TESTNET_API_KEY

    pt = PaperTrader()
    _pt_active = True

    st.markdown("""
    <div style="padding:0.5rem 0.8rem;background:rgba(63,185,80,0.1);border:1px solid rgba(63,185,80,0.3);
         border-radius:4px;margin-bottom:0.75rem;display:flex;align-items:center;gap:12px;">
      <span style="color:#3fb950;font-family:'JetBrains Mono',monospace;font-size:0.7rem;">● PAPER TRADING ACTIVE</span>
      <span style="color:#484f58;font-size:0.65rem;">Live Binance prices · Simulated fills · Slippage + commission applied · Zero real money</span>
    </div>""", unsafe_allow_html=True)

    c_pt_left, c_pt_right = st.columns([1, 2], gap="small")

    with c_pt_left:
        st.markdown('<div class="sec-label">Execute Signal</div>', unsafe_allow_html=True)
        pt_coin     = st.selectbox("Coin", list(COINS.keys()), key="pt_coin")
        pt_signal   = st.selectbox("Signal", ["BUY", "SELL"], key="pt_signal")
        pt_conf     = st.slider("Confidence", 0.50, 1.00, 0.70, 0.01, key="pt_conf")
        pt_amount   = st.number_input("Trade Amount (USDT)", min_value=10.0,
                                      max_value=10000.0, value=100.0, step=10.0, key="pt_amount")
        pt_run      = st.button("▶  EXECUTE PAPER TRADE", use_container_width=True,
                                type="primary", disabled=not _pt_active)

        if pt_run:
            with st.spinner("Placing order on Binance Testnet..."):
                result = pt.execute_signal(pt_coin, pt_signal, pt_conf, notional_override=pt_amount)
            status = result.get("status", "ERROR")
            if status == "FILLED":
                st.success(f"Order filled — {result['side']} {result['quantity']:.6f} "
                           f"{result['symbol']} @ ~${result['price']:,.2f} "
                           f"(notional ${result['notional']:.2f})")
            elif status == "SKIPPED":
                st.warning(f"Skipped: {result['reason']}")
            else:
                st.error(f"{status}: {result.get('reason', 'unknown error')}")

        st.markdown('<div class="sec-label" style="margin-top:1rem;">Live Prices</div>', unsafe_allow_html=True)
        if st.button("Fetch Current Prices", key="pt_refresh"):
            price_rows = []
            for c in list(COINS.keys()):
                try:
                    sym = COINS[c]["binance"]
                    px = pt.get_price(sym)
                    price_rows.append(f'<div style="display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid #161b22;"><span style="font-size:0.7rem;color:#8b949e;">{c}/USDT</span><span style="font-family:\'JetBrains Mono\',monospace;font-size:0.7rem;color:#c9d1d9;">${px:,.4f}</span></div>')
                except Exception:
                    pass
            st.markdown("".join(price_rows), unsafe_allow_html=True)

    with c_pt_right:
        # ── Auto-close trades older than 4h ─────────────────────
        try:
            _closed_now = pt.auto_close_open_trades(hold_hours=4)
            if _closed_now:
                st.toast(f"{_closed_now} trade(s) auto-closed at current price", icon="✓")
        except Exception:
            pass
        # ── P&L Summary from local DB ────────────────────────────
        history = pt.get_trade_history(50)
        closed  = [t for t in history if t["status"] == "CLOSED"]
        open_t  = [t for t in history if t["status"] == "OPEN"]

        if history:
            total_pnl  = sum(t["pnl_usd"] or 0 for t in closed)
            wins       = sum(1 for t in closed if (t["pnl_pct"] or 0) > 0)
            win_rate   = wins / len(closed) if closed else 0
            avg_pnl    = total_pnl / len(closed) if closed else 0
            pnl_color  = "var(--buy)" if total_pnl >= 0 else "var(--sell)"

            # Prediction accuracy: for closed trades that have a prediction,
            # check if predicted direction matched the actual price movement
            def _actual_dir(t):
                if t["exit"] and t["entry"]:
                    if t["side"] == "BUY":
                        return "UP" if t["exit"] >= t["entry"] else "DOWN"
                    else:
                        return "DOWN" if t["exit"] <= t["entry"] else "UP"
                return None

            pred_closed   = [t for t in closed if t.get("prediction") and _actual_dir(t)]
            xgb_hits      = sum(1 for t in pred_closed if t["prediction"] == _actual_dir(t))
            lstm_closed   = [t for t in closed if t.get("lstm_prediction") and _actual_dir(t)]
            lstm_hits     = sum(1 for t in lstm_closed if t["lstm_prediction"] == _actual_dir(t))
            pred_acc      = xgb_hits  / len(pred_closed)  if pred_closed  else None
            lstm_acc      = lstm_hits / len(lstm_closed)   if lstm_closed  else None
            pred_acc_str  = f"XGB {pred_acc:.0%}" if pred_acc is not None else "—"
            lstm_acc_str  = f"LSTM {lstm_acc:.0%}" if lstm_acc is not None else "—"
            pred_acc_color = "var(--buy)" if (pred_acc or 0) >= 0.5 else "var(--sell)"
            lstm_acc_color = "var(--buy)" if (lstm_acc or 0) >= 0.5 else "var(--sell)"

            st.markdown(f"""
            <div style="display:grid;grid-template-columns:repeat(6,1fr);gap:4px;margin-bottom:0.6rem;">
              <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:6px;padding:0.45rem 0.6rem;text-align:center;">
                <div style="font-size:0.55rem;color:var(--text-3);letter-spacing:1px;text-transform:uppercase;">Total P&L</div>
                <div style="font-family:'JetBrains Mono',monospace;font-size:0.9rem;font-weight:700;color:{pnl_color};">
                  {"+" if total_pnl>=0 else ""}${total_pnl:,.2f}
                </div>
              </div>
              <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:6px;padding:0.45rem 0.6rem;text-align:center;">
                <div style="font-size:0.55rem;color:var(--text-3);letter-spacing:1px;text-transform:uppercase;">Win Rate</div>
                <div style="font-family:'JetBrains Mono',monospace;font-size:0.9rem;font-weight:700;color:var(--buy);">{win_rate:.0%}</div>
              </div>
              <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:6px;padding:0.45rem 0.6rem;text-align:center;">
                <div style="font-size:0.55rem;color:var(--text-3);letter-spacing:1px;text-transform:uppercase;">Trades</div>
                <div style="font-family:'JetBrains Mono',monospace;font-size:0.9rem;font-weight:700;color:var(--text-1);">{len(closed)}</div>
              </div>
              <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:6px;padding:0.45rem 0.6rem;text-align:center;">
                <div style="font-size:0.55rem;color:var(--text-3);letter-spacing:1px;text-transform:uppercase;">Avg P&L</div>
                <div style="font-family:'JetBrains Mono',monospace;font-size:0.9rem;font-weight:700;color:{pnl_color};">
                  {"+" if avg_pnl>=0 else ""}${avg_pnl:,.2f}
                </div>
              </div>
              <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:6px;padding:0.45rem 0.6rem;text-align:center;position:relative;overflow:hidden;">
                <div style="position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,var(--blue),var(--cyan));"></div>
                <div style="font-size:0.55rem;color:var(--cyan);letter-spacing:1px;text-transform:uppercase;">XGB Accuracy</div>
                <div style="font-family:'JetBrains Mono',monospace;font-size:0.85rem;font-weight:700;color:{pred_acc_color};">{pred_acc_str}</div>
                <div style="font-size:0.5rem;color:var(--text-3);">{len(pred_closed)} trades</div>
              </div>
              <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:6px;padding:0.45rem 0.6rem;text-align:center;position:relative;overflow:hidden;">
                <div style="position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,var(--purple),#a78bfa);"></div>
                <div style="font-size:0.55rem;color:var(--purple);letter-spacing:1px;text-transform:uppercase;">LSTM Accuracy</div>
                <div style="font-family:'JetBrains Mono',monospace;font-size:0.85rem;font-weight:700;color:{lstm_acc_color};">{lstm_acc_str}</div>
                <div style="font-size:0.5rem;color:var(--text-3);">{len(lstm_closed)} trades</div>
              </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown('<div class="sec-label">Trade History — Predicted vs Actual</div>', unsafe_allow_html=True)
        if history:
            rows = []
            for t in history:
                pnl = t["pnl_pct"]
                pnl_str = f'{"+" if pnl and pnl>=0 else ""}{pnl:.2f}%' if pnl is not None else "OPEN"

                # Actual direction from price movement
                actual_dir = _actual_dir(t) if t["status"] == "CLOSED" else "—"

                def _hit(pred):
                    if pred and pred != "—" and actual_dir != "—":
                        return "✓" if pred == actual_dir else "✗"
                    return "·"

                xgb_pred  = t.get("prediction") or "—"
                xgb_conf  = t.get("pred_confidence")
                lstm_pred = t.get("lstm_prediction") or "—"
                lstm_conf = t.get("lstm_pred_confidence")

                xgb_str  = f"{xgb_pred} {xgb_conf:.0%}"  if xgb_pred  != "—" and xgb_conf  else xgb_pred
                lstm_str = f"{lstm_pred} {lstm_conf:.0%}" if lstm_pred != "—" and lstm_conf else lstm_pred

                # Models agree?
                agree = "✓" if (xgb_pred != "—" and lstm_pred != "—" and xgb_pred == lstm_pred) else (
                        "✗" if (xgb_pred != "—" and lstm_pred != "—") else "·")

                rows.append({
                    "Time":      t["time"],
                    "Coin":      t["coin"],
                    "Side":      t["side"],
                    "Entry":     fmt_price(t["entry"]) if t["entry"] else "—",
                    "Exit":      fmt_price(t["exit"])  if t["exit"]  else "—",
                    "XGB":       xgb_str,
                    "XGB Hit":   _hit(xgb_pred),
                    "LSTM":      lstm_str,
                    "LSTM Hit":  _hit(lstm_pred),
                    "Agree":     agree,
                    "Actual":    actual_dir,
                    "P&L %":     pnl_str,
                    "P&L $":     f'{"+" if (t["pnl_usd"] or 0)>=0 else ""}${t["pnl_usd"]:,.2f}' if t["pnl_usd"] is not None else "—",
                    "Conf":      f'{t["confidence"]:.0%}',
                    "Status":    t["status"],
                })
            _trade_df = pd.DataFrame(rows)

            def _style_hit(v):
                if v == "✓": return "color:#00e676;font-weight:700"
                if v == "✗": return "color:#ff3352;font-weight:700"
                return "color:#374e6e"

            _style_cols = [c for c in ["XGB Hit", "LSTM Hit", "Agree"] if c in _trade_df.columns]
            st.dataframe(
                _trade_df.style.map(_style_hit, subset=_style_cols) if _style_cols else _trade_df,
                use_container_width=True, hide_index=True, height=420,
            )

            # Show mini accuracy chart for trades that have predictions
            _pred_rows = [r for r in rows if r.get("XGB Hit") in ("✓", "✗")]
            if _pred_rows:
                _cum_acc = []
                _hits = 0
                for i, r in enumerate(_pred_rows, 1):
                    if r.get("XGB Hit") == "✓": _hits += 1
                    _cum_acc.append({"Trade #": i, "Cumulative Accuracy": _hits / i * 100})
                _fig_acc = go.Figure()
                _fig_acc.add_trace(go.Scatter(
                    x=[r["Trade #"] for r in _cum_acc],
                    y=[r["Cumulative Accuracy"] for r in _cum_acc],
                    mode="lines+markers",
                    line=dict(color="#00d4ff", width=2),
                    marker=dict(size=5, color="#00d4ff"),
                    fill="tozeroy", fillcolor="rgba(0,212,255,0.06)",
                    name="Cumulative ML Accuracy",
                ))
                _fig_acc.add_hline(y=50, line_dash="dot", line_color="#374e6e",
                                   annotation_text="50% baseline",
                                   annotation_font=dict(size=9, color="#374e6e"))
                _fig_acc.update_layout(
                    height=160, margin=dict(l=0, r=0, t=20, b=0),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    title=dict(text="ML Prediction Accuracy Over Trades",
                               font=dict(size=10, color="#6b85a8", family="JetBrains Mono"), x=0),
                    xaxis=dict(tickfont=dict(size=9, color="#374e6e"),
                               gridcolor="#0e1d32", title=""),
                    yaxis=dict(tickfont=dict(size=9, color="#374e6e"),
                               gridcolor="#0e1d32", range=[0, 105], title=""),
                    showlegend=False,
                )
                st.plotly_chart(_fig_acc, use_container_width=True, config={"displayModeBar": False})
        else:
            st.markdown('<div style="font-size:0.7rem;color:var(--text-3);padding:1rem;">No trade history yet. Execute a paper trade above.</div>',
                        unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════
#  AUTO REFRESH
# ═══════════════════════════════════════════════════════════════
if auto_refresh and auto_refresh > 0:
    import time as _t
    _t.sleep(auto_refresh)
    st.cache_data.clear()
    st.rerun()
