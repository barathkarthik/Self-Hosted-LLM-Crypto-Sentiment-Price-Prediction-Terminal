"""
Database models and initialization.
Uses SQLAlchemy ORM with SQLite.
"""
import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, DateTime,
    Text, Boolean, Index
)
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///crypto_terminal.db"
Base = declarative_base()
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)

class RedditPost(Base):
    __tablename__ = "reddit_posts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(String(20), unique=True, nullable=False)
    coin = Column(String(10), nullable=False)
    subreddit = Column(String(50))
    title = Column(Text)
    body = Column(Text)
    score = Column(Integer, default=0)
    num_comments = Column(Integer, default=0)
    created_utc = Column(DateTime)
    fetched_at = Column(DateTime, default=datetime.datetime.now)
    sentiment_score = Column(Float, nullable=True)
    sentiment_label = Column(String(20), nullable=True)
    __table_args__ = (Index("idx_reddit_coin_time", "coin", "created_utc"),)

class NewsArticle(Base):
    __tablename__ = "news_articles"
    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(String(64), unique=True, nullable=False)
    coin = Column(String(10), nullable=False)
    source = Column(String(100))
    title = Column(Text, nullable=False)
    description = Column(Text)
    url = Column(Text)
    published_at = Column(DateTime)
    fetched_at = Column(DateTime, default=datetime.datetime.now)
    sentiment_score = Column(Float, nullable=True)
    sentiment_label = Column(String(20), nullable=True)
    __table_args__ = (Index("idx_news_coin_time", "coin", "published_at"),)

class PriceData(Base):
    __tablename__ = "price_data"
    id = Column(Integer, primary_key=True, autoincrement=True)
    coin = Column(String(10), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)
    interval = Column(String(10), default="15m")
    __table_args__ = (Index("idx_price_coin_time", "coin", "timestamp"),)

class WhaleTransaction(Base):
    __tablename__ = "whale_transactions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tx_hash = Column(String(100), unique=True, nullable=False)
    coin = Column(String(10), nullable=False)
    from_address = Column(String(100))
    to_address = Column(String(100))
    value_usd = Column(Float)
    value_token = Column(Float)
    block_number = Column(Integer)
    timestamp = Column(DateTime)
    tx_type = Column(String(20))
    fetched_at = Column(DateTime, default=datetime.datetime.now)
    __table_args__ = (Index("idx_whale_coin_time", "coin", "timestamp"),)

class SentimentSnapshot(Base):
    __tablename__ = "sentiment_snapshots"
    id = Column(Integer, primary_key=True, autoincrement=True)
    coin = Column(String(10), nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.now)
    avg_score = Column(Float)
    label = Column(String(20))
    sample_count = Column(Integer)
    source = Column(String(20))
    model_used = Column(String(50))
    __table_args__ = (Index("idx_sentiment_coin_time", "coin", "timestamp"),)

class Signal(Base):
    __tablename__ = "signals"
    id = Column(Integer, primary_key=True, autoincrement=True)
    coin = Column(String(10), nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.now)
    signal_type = Column(String(10), nullable=False)
    confidence = Column(Float)
    sentiment_score = Column(Float)
    prediction_direction = Column(String(10))
    prediction_confidence = Column(Float)
    whale_activity = Column(String(20))
    reasoning = Column(Text)
    outcome_price_1h = Column(Float, nullable=True)
    outcome_price_4h = Column(Float, nullable=True)
    outcome_price_24h = Column(Float, nullable=True)
    was_correct = Column(Boolean, nullable=True)
    __table_args__ = (Index("idx_signal_coin_time", "coin", "timestamp"),)

class PredictionLog(Base):
    __tablename__ = "prediction_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    coin = Column(String(10), nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.now)
    horizon = Column(String(10))
    predicted_direction = Column(String(10))
    predicted_change_pct = Column(Float)
    confidence = Column(Float)
    model_used = Column(String(50))
    actual_direction = Column(String(10), nullable=True)
    actual_change_pct = Column(Float, nullable=True)

class PaperTrade(Base):
    __tablename__ = "paper_trades"
    id              = Column(Integer, primary_key=True, autoincrement=True)
    timestamp       = Column(DateTime, default=datetime.datetime.now)
    coin            = Column(String(10), nullable=False)
    symbol          = Column(String(20))
    side            = Column(String(10))           # BUY / SELL
    quantity        = Column(Float)
    entry_price     = Column(Float)
    exit_price      = Column(Float, nullable=True) # filled when closed
    notional_usd    = Column(Float)
    pnl_usd         = Column(Float, nullable=True)
    pnl_pct         = Column(Float, nullable=True)
    confidence      = Column(Float)
    signal_source   = Column(String(30), default="MANUAL")  # MANUAL / AUTO
    status          = Column(String(20), default="OPEN")    # OPEN / CLOSED
    order_id        = Column(String(50), nullable=True)
    prediction      = Column(String(20), nullable=True)  # XGBoost: UP / DOWN / SIDEWAYS
    pred_confidence = Column(Float,      nullable=True)  # XGBoost probability at entry
    lstm_prediction      = Column(String(20), nullable=True)  # LSTM: UP / DOWN / SIDEWAYS
    lstm_pred_confidence = Column(Float,      nullable=True)  # LSTM probability at entry
    __table_args__ = (Index("idx_papertrade_coin_time", "coin", "timestamp"),)


def init_db():
    Base.metadata.create_all(engine)
    # Migrate existing DBs: add prediction columns if missing
    from sqlalchemy import text
    with engine.connect() as conn:
        for col, typedef in [("prediction", "VARCHAR(20)"), ("pred_confidence", "FLOAT"),
                              ("lstm_prediction", "VARCHAR(20)"), ("lstm_pred_confidence", "FLOAT")]:
            try:
                conn.execute(text(f"ALTER TABLE paper_trades ADD COLUMN {col} {typedef}"))
                conn.commit()
            except Exception:
                pass  # column already exists

def get_session():
    return SessionLocal()

if __name__ == "__main__":
    init_db()
    print("Database initialized.")
