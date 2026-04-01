# Crypto Trading Intelligence Terminal

**Self-Hosted LLM-Powered Crypto Sentiment and Price Prediction System**

NMIMS Innovathon 2026 · Challenge 2 · AI and Data Intelligence Track

---

## Overview

Retail crypto traders lack affordable tools to aggregate sentiment from social media, news, and on-chain data. Professional platforms such as Santiment and Nansen cost upwards of Rs. 2–5 lakh per month. This terminal replicates core institutional-grade capabilities — LLM sentiment analysis, time-series price prediction, whale on-chain tracking, and backtested signal generation — running entirely on local hardware at zero cost.

---

## Architecture

```
Data Sources
  Telegram Channels  |  NewsAPI  |  Whale Alert  |  Binance REST
          |
  Ingestion Pipeline (Async, Scheduled, Retry with Exponential Backoff)
          |
  SQLite / PostgreSQL (7 indexed tables via SQLAlchemy ORM)
     |              |              |
Sentiment        Price          On-Chain
Engine           Predictor      Analytics
Ollama           Prophet +      Whale Alert
Mistral 7B +     XGBoost        Classification
FinBERT fallback
     |              |              |
          Signal Generator
          BUY / SELL / HOLD
          Confidence Score + Reasoning
               |              |
         Backtesting      Streamlit
         Engine           Dashboard
```

---

## Features

**Multi-Source Sentiment Analysis**
Text from Telegram crypto channels and NewsAPI is scored using a locally-hosted Mistral 7B model via Ollama. If Ollama is unavailable, FinBERT (CPU-based) is used as a fallback. Every classification includes a confidence score and produces a BULLISH, BEARISH, or NEUTRAL label.

**Price Prediction**
Facebook Prophet generates 1h, 4h, and 24h directional forecasts using historical OHLCV data. XGBoost produces a secondary prediction using 30 engineered features including technical indicators, sentiment scores, on-chain signals, and microstructure features (volatility regime, return entropy, z-score of 5-bar returns) derived from production-grade research.

**Whale On-Chain Tracking**
Large transactions are collected via the Whale Alert API, covering Bitcoin, Ethereum, Solana, XRP, Dogecoin, and 20+ additional chains. Transactions are classified as accumulation (exchange outflows) or distribution (exchange inflows) based on wallet owner type.

**Signal Generation**
Signals are produced by combining three independent indicators: sentiment score, ML prediction direction, and whale flow classification. A BUY or SELL signal requires at least two of three factors to align. Every signal includes a numeric confidence score and a human-readable reasoning string.

**Backtesting Engine**
Historical signals are replayed against OHLCV data with realistic assumptions: 0.1% slippage per side, 0.1% commission, and confidence-weighted position sizing. Metrics computed include total return, CAGR, Sharpe ratio, Sortino ratio, max drawdown, and a rolling 126-trade Sharpe window.

**Paper Trading**
A simulated order execution engine places paper trades using live Binance market prices (public API, no authentication required). Slippage and commission are applied at fill. All trades are persisted locally and displayed in a trade history table with P&L tracking.

**Dashboard**
A six-tab Streamlit terminal displays market overview with candlestick charts and OHLCV data, sentiment intelligence, ML predictions with signal reasoning, whale transaction feed, backtesting results, and the paper trading interface.

---

## Signal Logic

```
BUY   =  sentiment > 0.70  AND  prediction = UP    AND  whales accumulating   (2 of 3 required)
SELL  =  sentiment < 0.30  AND  prediction = DOWN  AND  whales distributing   (2 of 3 required)
HOLD  =  all other conditions
```

---

## Technology Stack

| Component | Technology |
|---|---|
| LLM Sentiment | Ollama (Mistral 7B Q4) + FinBERT fallback |
| Price Prediction | Facebook Prophet + XGBoost |
| Feature Engineering | 30 features: technical, sentiment, on-chain, microstructure |
| Data Collection | Telethon, Requests, Whale Alert API, Binance REST |
| On-Chain Analytics | Whale Alert API (multi-chain) |
| Signal Engine | Custom multi-factor rule engine |
| Backtesting | Custom simulator with slippage and commission modeling |
| Paper Trading | Local simulation engine with live market prices |
| Dashboard | Streamlit + Plotly |
| Database | SQLAlchemy ORM with SQLite (PostgreSQL-compatible) |
| Resilience | Exponential backoff retry decorator on all API collectors |

---

## Project Structure

```
Hackathon1/
├── src/
│   ├── database.py             SQLAlchemy models (7 tables)
│   ├── data_loader.py          5 data collectors with retry logic
│   ├── feature_engineering.py  30 ML features
│   ├── sentiment_engine.py     Ollama LLM + FinBERT fallback
│   ├── model.py                Prophet + XGBoost with feature manifest
│   ├── signal_engine.py        Multi-factor signal generation
│   ├── backtester.py           Realistic backtesting with risk metrics
│   ├── paper_trader.py         Local paper trading simulation engine
│   └── utils.py                Retry decorator (exponential backoff)
├── scripts/
│   └── seed_paper_trades.py    Demo trade history generator
├── models/                     Trained model artifacts (.pkl, .json)
├── data/                       SQLite database
├── app.py                      Streamlit dashboard (6 tabs)
├── main.py                     Pipeline orchestrator with scheduler
├── config.py                   Centralized configuration and API keys
└── requirements.txt
```

---

## Setup

**Prerequisites**
- Python 3.9 or later
- Minimum 8 GB RAM (16 GB recommended for local LLM)
- Ollama installed (for local sentiment analysis)

**Installation**

```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

**Configuration**

Copy `.env.example` to `.env.local` and populate the following keys:

```
NEWS_API_KEY=
TELEGRAM_API_ID=
TELEGRAM_API_HASH=
WHALE_ALERT_API_KEY=
```

**LLM Model**

```bash
ollama pull mistral:7b-instruct-q4_0
```

**Database**

```bash
python -c "from src.database import init_db; init_db()"
```

**Run**

```bash
# Terminal 1: data pipeline and signal engine
python main.py

# Terminal 2: dashboard
python -m streamlit run app.py
```

**Flags**

```bash
python main.py --skip-history   # Skip initial 90-day historical data fetch
python main.py --train-only     # Train models and exit
```

---

## API Keys

All API keys are loaded from `.env.local` and are never committed to version control. Free-tier access is sufficient for all data sources. The Binance integration uses only the public price endpoint and requires no authentication.

| Key | Source | Required |
|---|---|---|
| NEWS_API_KEY | newsapi.org | Yes |
| TELEGRAM_API_ID / HASH | my.telegram.org | Yes |
| WHALE_ALERT_API_KEY | whale-alert.io | Yes |
| ETHERSCAN_API_KEY | etherscan.io | No (superseded by Whale Alert) |

---

## Disclaimer

This system is built for educational and research purposes as part of an academic hackathon. It does not constitute financial advice. No real money is traded at any point. All trading signals, backtesting results, and paper trades are simulations and should not be used to make real investment decisions.

---

## Event

NMIMS Innovathon 2026 — AI and Data Intelligence Track
