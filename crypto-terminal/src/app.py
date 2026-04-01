import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.data_loader import load_data
from src.feature_engineering import add_features
from src.sentiment_engine import analyze_text
from src.model import train_model
from src.signal_engine import generate_signal
from src.backtester import backtest

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Crypto Intelligence Terminal",
    page_icon="₿",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Inter:wght@400;500;600;700&display=swap');

  html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
    background-color: #080c14;
    color: #e2e8f0;
  }

  /* Hide default streamlit chrome */
  #MainMenu, footer, header { visibility: hidden; }
  .block-container { padding: 1.5rem 2.5rem 2rem; max-width: 1400px; }

  /* ── Top bar ── */
  .topbar {
    display: flex; align-items: center; justify-content: space-between;
    padding: 0.75rem 0 1.25rem;
    border-bottom: 1px solid #1e2d40;
    margin-bottom: 1.5rem;
  }
  .topbar-logo {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.35rem; font-weight: 700;
    background: linear-gradient(135deg, #f7931a 0%, #ffcd3c 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    letter-spacing: -0.5px;
  }
  .topbar-tag {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem; color: #4a9eff;
    background: rgba(74,158,255,0.1); border: 1px solid rgba(74,158,255,0.25);
    border-radius: 4px; padding: 2px 8px; letter-spacing: 1px;
  }
  .topbar-time {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem; color: #4a5568;
  }

  /* ── Metric card ── */
  .metric-card {
    background: linear-gradient(145deg, #0d1520, #111a27);
    border: 1px solid #1e2d40;
    border-radius: 12px;
    padding: 1.1rem 1.3rem;
    position: relative; overflow: hidden;
  }
  .metric-card::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, #f7931a, #ffcd3c);
  }
  .metric-label {
    font-size: 0.65rem; font-weight: 600; letter-spacing: 1.5px;
    color: #4a5568; text-transform: uppercase; margin-bottom: 0.4rem;
  }
  .metric-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.55rem; font-weight: 700; color: #f0f4f8; line-height: 1;
  }
  .metric-sub {
    font-size: 0.72rem; color: #4a5568; margin-top: 0.35rem;
  }

  /* ── Signal badge ── */
  .signal-buy {
    background: rgba(16,185,129,0.15); border: 1px solid rgba(16,185,129,0.4);
    color: #10b981; border-radius: 8px; padding: 0.6rem 1.4rem;
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.8rem; font-weight: 700; display: inline-block;
    letter-spacing: 3px;
  }
  .signal-sell {
    background: rgba(239,68,68,0.15); border: 1px solid rgba(239,68,68,0.4);
    color: #ef4444; border-radius: 8px; padding: 0.6rem 1.4rem;
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.8rem; font-weight: 700; display: inline-block;
    letter-spacing: 3px;
  }
  .signal-hold {
    background: rgba(234,179,8,0.15); border: 1px solid rgba(234,179,8,0.4);
    color: #eab308; border-radius: 8px; padding: 0.6rem 1.4rem;
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.8rem; font-weight: 700; display: inline-block;
    letter-spacing: 3px;
  }

  /* ── Sentiment bar ── */
  .sent-bar-wrap { background: #1a2236; border-radius: 8px; height: 8px; margin: 0.5rem 0; }
  .sent-bar-fill { height: 8px; border-radius: 8px; transition: width 0.5s ease; }

  /* ── Section header ── */
  .section-header {
    font-size: 0.65rem; font-weight: 600; letter-spacing: 2px;
    color: #4a9eff; text-transform: uppercase;
    border-left: 3px solid #4a9eff;
    padding-left: 0.6rem; margin-bottom: 0.9rem; margin-top: 0.2rem;
  }

  /* ── Panel ── */
  .panel {
    background: #0d1520; border: 1px solid #1e2d40;
    border-radius: 12px; padding: 1.2rem 1.4rem;
  }

  /* ── Reasoning row ── */
  .reason-row {
    display: flex; justify-content: space-between; align-items: center;
    padding: 0.45rem 0; border-bottom: 1px solid #1a2236;
    font-size: 0.8rem;
  }
  .reason-row:last-child { border-bottom: none; }
  .reason-key { color: #4a5568; font-weight: 500; }
  .reason-val {
    font-family: 'JetBrains Mono', monospace;
    color: #a0aec0; font-weight: 600;
  }

</style>
""", unsafe_allow_html=True)

# ── Data & Model ──────────────────────────────────────────────────────────────
df = load_data()
df = add_features(df)
model = train_model(df)
latest = df.iloc[-1]

X_latest = pd.DataFrame([[latest["momentum"], latest["rolling_mean"]]],
                        columns=["momentum", "rolling_mean"])
prediction = model.predict(X_latest)[0]
accuracy = backtest(df)

# ── Top bar ───────────────────────────────────────────────────────────────────
st.markdown("""
<div class="topbar">
  <div>
    <span class="topbar-logo">₿ CRYPTO INTELLIGENCE TERMINAL</span>
  </div>
  <div style="display:flex;gap:12px;align-items:center;">
    <span class="topbar-tag">LIVE</span>
    <span class="topbar-tag">AI-POWERED</span>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Auto-generate headline from price momentum ────────────────────────────────
def _auto_headline(df):
    last_ret = df["returns"].iloc[-1] * 100
    mom = df["momentum"].iloc[-1]
    price = df["price"].iloc[-1]
    if last_ret > 1.5:
        return f"Bitcoin surges {last_ret:.1f}% — bulls push BTC past ${price:,.0f} amid strong demand"
    elif last_ret > 0:
        return f"Bitcoin inches higher, up {last_ret:.1f}% as momentum remains positive at {mom:,.0f}"
    elif last_ret < -1.5:
        return f"Bitcoin crashes {abs(last_ret):.1f}% — bears take control, BTC falls below ${price:,.0f}"
    else:
        return f"Bitcoin flat near ${price:,.0f}, market awaits direction as momentum softens"

auto_headline = _auto_headline(df)
sentiment_score, sentiment_label, explanation = analyze_text(auto_headline)
signal = generate_signal(prediction, sentiment_score)

# ── Read-only news ticker ─────────────────────────────────────────────────────
sent_dot_color = "#10b981" if sentiment_score > 0.6 else ("#ef4444" if sentiment_score < 0.4 else "#eab308")
st.markdown(f"""
<div style="background:#0d1520; border:1px solid #1e2d40; border-radius:10px;
     padding:0.65rem 1rem; margin-bottom:1.25rem;
     display:flex; align-items:center; gap:0.75rem;">
  <span style="width:8px;height:8px;border-radius:50%;background:{sent_dot_color};
        display:inline-block;flex-shrink:0;box-shadow:0 0 6px {sent_dot_color};"></span>
  <span style="font-size:0.65rem;font-weight:600;letter-spacing:1.5px;
        color:#4a5568;text-transform:uppercase;flex-shrink:0;">Market Signal</span>
  <span style="color:#a0aec0;font-size:0.82rem;">{auto_headline}</span>
</div>
""", unsafe_allow_html=True)

# ── Row 1: KPI Metrics ────────────────────────────────────────────────────────
st.markdown('<div class="section-header">Market Snapshot</div>', unsafe_allow_html=True)

price_change = latest["returns"] * 100
price_color = "#10b981" if price_change >= 0 else "#ef4444"
price_arrow = "▲" if price_change >= 0 else "▼"

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.markdown(f"""
    <div class="metric-card">
      <div class="metric-label">BTC Price</div>
      <div class="metric-value">${latest['price']:,.0f}</div>
      <div class="metric-sub" style="color:{price_color};">{price_arrow} {abs(price_change):.2f}% change</div>
    </div>""", unsafe_allow_html=True)

with c2:
    st.markdown(f"""
    <div class="metric-card">
      <div class="metric-label">Momentum</div>
      <div class="metric-value" style="color:{'#10b981' if latest['momentum']>=0 else '#ef4444'};">
        {'▲' if latest['momentum']>=0 else '▼'} {abs(latest['momentum']):,.0f}
      </div>
      <div class="metric-sub">Price delta vs prev</div>
    </div>""", unsafe_allow_html=True)

with c3:
    st.markdown(f"""
    <div class="metric-card">
      <div class="metric-label">Rolling Mean (3)</div>
      <div class="metric-value">${latest['rolling_mean']:,.0f}</div>
      <div class="metric-sub">3-period average</div>
    </div>""", unsafe_allow_html=True)

with c4:
    st.markdown(f"""
    <div class="metric-card">
      <div class="metric-label">Backtest Accuracy</div>
      <div class="metric-value">{accuracy}%</div>
      <div class="metric-sub">Historical win rate</div>
    </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Row 2: Chart | Signal + Sentiment ────────────────────────────────────────
col_chart, col_right = st.columns([2, 1], gap="medium")

with col_chart:
    st.markdown('<div class="section-header">Price Chart</div>', unsafe_allow_html=True)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        row_heights=[0.7, 0.3], vertical_spacing=0.04)

    colors = ["#10b981" if df["returns"].iloc[i] >= 0 else "#ef4444"
              for i in range(len(df))]

    fig.add_trace(go.Scatter(
        x=df.index, y=df["price"],
        mode="lines",
        line=dict(color="#4a9eff", width=2),
        name="Price",
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=df.index, y=df["rolling_mean"],
        mode="lines",
        line=dict(color="#f7931a", width=1.5, dash="dot"),
        name="MA(3)",
    ), row=1, col=1)

    fig.add_trace(go.Bar(
        x=df.index, y=df["momentum"],
        marker=dict(color=colors),
        name="Momentum",
    ), row=2, col=1)

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=10, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    font=dict(color="#4a5568", size=11),
                    bgcolor="rgba(0,0,0,0)"),
        height=320,
        xaxis2=dict(showgrid=False, color="#1e2d40", zeroline=False),
        xaxis=dict(showgrid=False, color="#1e2d40", zeroline=False),
        yaxis=dict(gridcolor="#1a2236", color="#4a5568", zeroline=False),
        yaxis2=dict(gridcolor="#1a2236", color="#4a5568", zeroline=False),
        font=dict(family="Inter", color="#4a5568"),
        showlegend=True,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

with col_right:
    # Trading Signal
    st.markdown('<div class="section-header">Trading Signal</div>', unsafe_allow_html=True)
    signal_class = f"signal-{signal.lower()}"
    pred_label = "UP  ▲" if prediction == 1 else "DOWN  ▼"
    pred_color = "#10b981" if prediction == 1 else "#ef4444"

    st.markdown(f"""
    <div class="panel" style="text-align:center; padding: 1.5rem 1rem;">
      <div class="metric-label" style="margin-bottom:0.8rem;">Recommended Action</div>
      <div class="{signal_class}">{signal}</div>
      <div style="margin-top:1.1rem; font-size:0.75rem; color:#4a5568;">
        ML Prediction &nbsp;→&nbsp;
        <span style="color:{pred_color}; font-family:'JetBrains Mono',monospace; font-weight:700;">
          {pred_label}
        </span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Sentiment
    st.markdown('<div class="section-header">Sentiment Analysis</div>', unsafe_allow_html=True)
    sent_pct = int(sentiment_score * 100)
    sent_color = "#10b981" if sentiment_score > 0.6 else ("#ef4444" if sentiment_score < 0.4 else "#eab308")
    sent_label_color = sent_color

    st.markdown(f"""
    <div class="panel">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.5rem;">
        <span style="font-family:'JetBrains Mono',monospace; font-weight:700; font-size:1.1rem; color:{sent_label_color};">
          {sentiment_label}
        </span>
        <span style="font-family:'JetBrains Mono',monospace; font-size:0.95rem; color:{sent_label_color};">
          {sentiment_score:.2f}
        </span>
      </div>
      <div class="sent-bar-wrap">
        <div class="sent-bar-fill" style="width:{sent_pct}%; background:{sent_color};"></div>
      </div>
      <div style="font-size:0.75rem; color:#4a5568; margin-top:0.6rem; line-height:1.5;">
        {explanation}
      </div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Row 3: Reasoning breakdown ────────────────────────────────────────────────
st.markdown('<div class="section-header">Signal Reasoning</div>', unsafe_allow_html=True)

r1, r2 = st.columns(2, gap="medium")
with r1:
    st.markdown(f"""
    <div class="panel">
      <div class="reason-row"><span class="reason-key">Sentiment Score</span><span class="reason-val">{sentiment_score:.2f}</span></div>
      <div class="reason-row"><span class="reason-key">Sentiment Label</span><span class="reason-val" style="color:{sent_color};">{sentiment_label}</span></div>
      <div class="reason-row"><span class="reason-key">ML Prediction</span>
        <span class="reason-val" style="color:{'#10b981' if prediction==1 else '#ef4444'};">
          {'UP' if prediction==1 else 'DOWN'}
        </span>
      </div>
    </div>""", unsafe_allow_html=True)

with r2:
    st.markdown(f"""
    <div class="panel">
      <div class="reason-row"><span class="reason-key">Momentum</span><span class="reason-val">{latest['momentum']:,.2f}</span></div>
      <div class="reason-row"><span class="reason-key">Rolling Mean</span><span class="reason-val">${latest['rolling_mean']:,.2f}</span></div>
      <div class="reason-row"><span class="reason-key">Backtest Accuracy</span><span class="reason-val">{accuracy}%</span></div>
    </div>""", unsafe_allow_html=True)
