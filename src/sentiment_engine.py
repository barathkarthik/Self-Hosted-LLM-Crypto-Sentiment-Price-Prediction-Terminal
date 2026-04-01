"""
Sentiment Analysis Engine
Primary:  Ollama (Mistral 7B) — few-shot prompted
Fallback: FinBERT (Hugging Face) — CPU-friendly, no GPU needed
"""

import json, time, logging, datetime, requests
import numpy as np

logger = logging.getLogger("Sentiment")

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import OLLAMA_BASE_URL, OLLAMA_MODEL, SENTIMENT_TIMEOUT, COINS
from src.database import get_session, RedditPost, NewsArticle, SentimentSnapshot


# ═══════════════════════════════════════════════
#  FEW-SHOT PROMPT (6 examples for ~70-75% accuracy)
# ═══════════════════════════════════════════════
SENTIMENT_PROMPT = """You are a crypto market sentiment classifier. Classify the text below as BULLISH, BEARISH, NEUTRAL, or FUD. Give a confidence score 0.0–1.0.

Examples:
Text: "Bitcoin just broke $70K resistance! Bull run unstoppable 🚀"
{{"classification": "BULLISH", "score": 0.92, "reasoning": "strong positive language + price breakout"}}

Text: "ETH crashing hard, everyone panic selling"
{{"classification": "BEARISH", "score": 0.85, "reasoning": "negative language + selling pressure"}}

Text: "BTC trading sideways at $65K, low volume"
{{"classification": "NEUTRAL", "score": 0.70, "reasoning": "no directional movement"}}

Text: "Major exchange hacked, millions stolen — crypto is dead"
{{"classification": "FUD", "score": 0.88, "reasoning": "fear-inducing claim"}}

Text: "Whale moved 10,000 BTC to cold storage"
{{"classification": "BULLISH", "score": 0.78, "reasoning": "accumulation signal"}}

Text: "SEC delays ETF decision again"
{{"classification": "BEARISH", "score": 0.60, "reasoning": "regulatory uncertainty"}}

Now classify:
Text: "{text}"

Respond ONLY with JSON:
{{"classification": "BULLISH|BEARISH|NEUTRAL|FUD", "score": 0.0-1.0, "reasoning": "brief"}}"""


# ═══════════════════════════════════════════════
#  OLLAMA ANALYZER (Primary)
# ═══════════════════════════════════════════════
class OllamaAnalyzer:
    def __init__(self):
        self.base_url = OLLAMA_BASE_URL
        self.model = OLLAMA_MODEL
        self.available = self._ping()
        if self.available:
            logger.info(f"[Ollama] ✅ Connected: {self.model}")
        else:
            logger.warning("[Ollama] ❌ Not available — will use FinBERT fallback")

    def _ping(self) -> bool:
        try:
            return requests.get(f"{self.base_url}/api/tags", timeout=5).status_code == 200
        except Exception:
            return False

    def analyze(self, text: str) -> dict | None:
        prompt = SENTIMENT_PROMPT.replace("{text}", text[:1000])
        try:
            resp = requests.post(f"{self.base_url}/api/generate",
                                 json={"model": self.model, "prompt": prompt, "stream": False},
                                 timeout=SENTIMENT_TIMEOUT)
            raw = resp.json().get("response", "")
            j_start, j_end = raw.find("{"), raw.rfind("}") + 1
            if j_start >= 0 and j_end > j_start:
                r = json.loads(raw[j_start:j_end])
                return {
                    "label": r.get("classification", "NEUTRAL").upper(),
                    "score": float(r.get("score", 0.5)),
                    "reasoning": r.get("reasoning", ""),
                    "model": f"ollama-{self.model}",
                }
        except Exception as e:
            logger.error(f"[Ollama] {e}")
        return None


# ═══════════════════════════════════════════════
#  FINBERT FALLBACK (CPU)
# ═══════════════════════════════════════════════
class FinBERTAnalyzer:
    def __init__(self):
        self.pipe = None
        try:
            from transformers import pipeline
            self.pipe = pipeline("sentiment-analysis",
                                 model="ProsusAI/finbert",
                                 tokenizer="ProsusAI/finbert", device=-1)
            logger.info("[FinBERT] ✅ Loaded")
        except Exception as e:
            logger.error(f"[FinBERT] {e}")

    def analyze(self, text: str) -> dict:
        if not self.pipe:
            return {"label": "NEUTRAL", "score": 0.5, "reasoning": "model not loaded", "model": "none"}
        try:
            r = self.pipe(text[:512])[0]
            label_map = {"positive": "BULLISH", "negative": "BEARISH", "neutral": "NEUTRAL"}
            return {
                "label": label_map.get(r["label"], "NEUTRAL"),
                "score": r["score"],
                "reasoning": f"FinBERT: {r['label']}",
                "model": "finbert",
            }
        except Exception:
            return {"label": "NEUTRAL", "score": 0.5, "reasoning": "error", "model": "finbert"}


# ═══════════════════════════════════════════════
#  UNIFIED SENTIMENT ENGINE
# ═══════════════════════════════════════════════
class SentimentEngine:
    """Tries Ollama → falls back to FinBERT → scores all unprocessed content."""

    def __init__(self):
        self.ollama = OllamaAnalyzer()
        self._finbert = None

    @property
    def analyzer(self):
        if self.ollama.available:
            return self.ollama
        if self._finbert is None:
            self._finbert = FinBERTAnalyzer()
        return self._finbert

    def analyze_text(self, text: str) -> tuple[float, str, str]:
        """
        Analyze a single text. Returns (score, label, explanation).
        This is the function your existing app.py calls.
        """
        r = self.analyzer.analyze(text)
        if r:
            return r["score"], r["label"], r.get("reasoning", "")
        return 0.5, "NEUTRAL", "analysis failed"

    def process_unscored_posts(self, limit: int = 50) -> int:
        session = get_session()
        posts = session.query(RedditPost).filter(
            RedditPost.sentiment_score.is_(None)
        ).order_by(RedditPost.created_utc.desc()).limit(limit).all()
        scored = 0
        for p in posts:
            r = self.analyzer.analyze(f"{p.title} {p.body or ''}"[:1000])
            if r:
                p.sentiment_score = r["score"]
                p.sentiment_label = r["label"]
                scored += 1
        session.commit()
        session.close()
        return scored

    def process_unscored_news(self, limit: int = 50) -> int:
        session = get_session()
        articles = session.query(NewsArticle).filter(
            NewsArticle.sentiment_score.is_(None)
        ).order_by(NewsArticle.published_at.desc()).limit(limit).all()
        scored = 0
        for a in articles:
            r = self.analyzer.analyze(f"{a.title} {a.description or ''}"[:1000])
            if r:
                a.sentiment_score = r["score"]
                a.sentiment_label = r["label"]
                scored += 1
        session.commit()
        session.close()
        return scored

    def compute_snapshot(self, coin: str) -> dict:
        session = get_session()
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=2)
        reddit_scores = [r.sentiment_score for r in session.query(RedditPost).filter(
            RedditPost.coin == coin, RedditPost.created_utc >= cutoff,
            RedditPost.sentiment_score.isnot(None)).all()]
        news_scores = [a.sentiment_score for a in session.query(NewsArticle).filter(
            NewsArticle.coin == coin, NewsArticle.published_at >= cutoff,
            NewsArticle.sentiment_score.isnot(None)).all()]
        all_s = reddit_scores + news_scores
        if not all_s:
            session.close()
            return {"coin": coin, "avg_score": 0.5, "label": "NEUTRAL", "sample_count": 0}
        avg = float(np.mean(all_s))
        label = "BULLISH" if avg > 0.6 else "BEARISH" if avg < 0.4 else "NEUTRAL"
        session.add(SentimentSnapshot(
            coin=coin, avg_score=avg, label=label,
            sample_count=len(all_s), source="combined",
            model_used=type(self.analyzer).__name__))
        session.commit()
        session.close()
        return {"coin": coin, "avg_score": avg, "label": label, "sample_count": len(all_s)}

    def run_full_cycle(self) -> dict:
        self.process_unscored_posts()
        self.process_unscored_news()
        return {coin: self.compute_snapshot(coin) for coin in COINS}


# Convenience function for backward compatibility with your existing app.py
_engine = None
def analyze_text(text: str) -> tuple[float, str, str]:
    global _engine
    if _engine is None:
        _engine = SentimentEngine()
    return _engine.analyze_text(text)
