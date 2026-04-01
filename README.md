# 📊 Crypto Trading Intelligence Terminal

**Self-Hosted LLM-Powered Crypto Sentiment & Price Prediction System**

> NMIMS Innovathon 2026 · Challenge 2 · AI & Data Intelligence Track

---

## 🎯 Problem

Retail crypto traders lack affordable tools to aggregate sentiment from social media, news, and on-chain data. Professional APIs (Santiment, LumiBot) cost ₹2–5L/month. This terminal runs **100% locally and free** — combining LLM sentiment analysis, time-series prediction, and whale tracking into actionable trading signals.

---

## 🏗️ Architecture

```
┌────────────────────────────────────────────────────┐
│                  DATA SOURCES                       │
│  Reddit API  │ NewsAPI  │ Etherscan  │ Binance     │
└──────┬───────┴────┬─────┴─────┬──────┴──────┬──────┘
       └────────────┴───────────┴─────────────┘
                         │
              ┌──────────▼──────────┐
              │  Ingestion Pipeline │
              │  Async + Scheduled  │
              └──────────┬──────────┘
                         │
              ┌──────────▼──────────┐
              │  SQLite/PostgreSQL   │
              └──┬─────┬──────┬─────┘
                 │     │      │
       ┌─────────▼┐ ┌─▼──────▼──┐ ┌──────────┐
       │Sentiment │ │  Price     │ │ On-Chain  │
       │Engine    │ │ Predictor  │ │ Analytics │
       │Ollama/   │ │ Prophet/   │ │  Whale    │
       │FinBERT   │ │ XGBoost    │ │ Tracking  │
       └────┬─────┘ └─────┬─────┘ └────┬──────┘
            └──────────────┼────────────┘
                    ┌──────▼──────┐
                    │   Signal    │
                    │ Generator   │
                    │ BUY/SELL/   │
                    │ HOLD        │
                    └──┬───────┬──┘
              ┌────────▼┐  ┌──▼──────────┐
              │Backtest │  │  Streamlit   │
              │Engine   │  │  Dashboard   │
              └─────────┘  └─────────────┘
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- 8 GB RAM minimum (16 GB recommended)
- [Ollama](https://ollama.ai) installed (for local LLM)

### Setup

```bash
cd HACKATHON1

# Virtual environment
python -m venv venv
source venv/bin/activate        # Linux/Mac
# venv\Scripts\activate          # Windows

# Dependencies
pip install -r requirements.txt

# API keys
cp .env.example .env.local
# Edit .env.local with your Reddit, NewsAPI, Etherscan keys

# Pull LLM model (~4 GB)
ollama pull mistral:7b-instruct-q4_0

# Initialize database
python -c "from src.database import init_db; init_db()"
```

### Run

```bash
# Terminal 1: Start data pipeline + signal engine
python main.py

# Terminal 2: Launch dashboard
streamlit run app.py
```

### Quick flags

```bash
python main.py --skip-history   # Skip 90-day data fetch
python main.py --train-only     # Just train models, then exit
```

### Optional: PostgreSQL

```bash
docker-compose up -d
# Set DATABASE_URL=postgresql://crypto:crypto@localhost:5432/cryptodb in .env.local
```

---

## 📁 Project Structure

```
HACKATHON1/
├── src/
│   ├── __init__.py
│   ├── database.py            # 7 SQLAlchemy tables + init
│   ├── data_loader.py         # 4 collectors (Reddit, News, Binance, Etherscan)
│   ├── feature_engineering.py # 27 ML features (technical + sentiment + on-chain)
│   ├── sentiment_engine.py    # Ollama LLM + FinBERT fallback
│   ├── model.py               # Prophet + XGBoost predictors
│   ├── signal_engine.py       # BUY/SELL signal generation + reasoning
│   └── backtester.py          # P&L, Sharpe ratio, win rate
├── data/                      # CSV files + SQLite database
├── models/                    # Trained model artifacts (.pkl)
├── tests/
│   └── test_components.py     # 10 component tests
├── app.py                     # Streamlit dashboard (5 tabs)
├── main.py                    # Orchestrator (scheduler + threading)
├── config.py                  # All settings + API key management
├── requirements.txt
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

---

## 🔧 Core Components

| Component | Technology | Purpose |
|---|---|---|
| LLM Sentiment | Ollama (Mistral 7B) + FinBERT | Classify text BULLISH/BEARISH/NEUTRAL/FUD |
| Price Prediction | Facebook Prophet + XGBoost | Predict 1h/4h/24h direction |
| Data Ingestion | PRAW, Requests | Reddit, NewsAPI, Binance, Etherscan |
| On-Chain Analytics | Etherscan API | Whale transaction tracking & classification |
| Signal Generator | Custom rule engine | Combine 3 signals with confidence + reasoning |
| Backtesting | Custom simulator | Win rate, Sharpe ratio, max drawdown, P&L |
| Dashboard | Streamlit + Plotly | 5-tab real-time terminal |
| Database | SQLAlchemy (SQLite/PostgreSQL) | 7 indexed tables |

---

## 📊 Signal Logic

```
BUY  = (sentiment > 0.7) + (prediction = UP) + (whales accumulating)   → ≥2 of 3
SELL = (sentiment < 0.3) + (prediction = DOWN) + (whales distributing) → ≥2 of 3
HOLD = all other conditions
```

Every signal includes:
- Confidence score (0–1)
- Human-readable reasoning explaining WHY it was generated
- Breakdown of sentiment, prediction, and whale components

---

## 📈 Model Performance

| Metric | Target | Measurement |
|---|---|---|
| Directional Accuracy | >55% | Prophet on 3-month history |
| Sentiment Classification | ~70–75% | Few-shot prompted Mistral 7B |
| Backtest Win Rate | >50% | Evaluated on 30-day signal history |
| Sharpe Ratio | >0 | Risk-adjusted returns |

---

## 🔑 Feature Highlights

1. **Self-hosted LLM** — Ollama runs Mistral 7B locally, no cloud dependency
2. **Automatic fallback** — If Ollama fails, FinBERT (CPU) takes over seamlessly
3. **27 engineered features** — Technical indicators + sentiment + on-chain combined
4. **Real-time pipeline** — 6 scheduled collectors running in parallel threads
5. **Explainable signals** — Every BUY/SELL includes reasoning, not just a number
6. **5-coin coverage** — BTC, ETH, SOL, XRP, DOGE tracked simultaneously
7. **Full backtesting** — Historical P&L, Sharpe ratio, max drawdown
8. **Zero cost** — All free-tier APIs, open-source models, no paid dependencies

---

## ⚠️ Important Notices

- **Educational Use Only** — Simulation tool. NO real money trading.
- **API Keys** — Never commit to GitHub. Use `.env.local` only.
- **All Free Tier** — Total cost: ₹0.

---

## 🧪 Run Tests

```bash
python tests/test_components.py
# or
python -m pytest tests/ -v
```

---

## 👥 Team

NMIMS Innovathon 2026 — AI & Data Intelligence Track

---

*Built with Ollama, Prophet, Streamlit, FinBERT, and open-source tools.*
