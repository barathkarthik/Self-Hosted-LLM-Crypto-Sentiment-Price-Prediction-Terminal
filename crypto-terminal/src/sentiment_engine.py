def analyze_text(text):
    text = text.lower()

    if "bull" in text or "rise" in text:
        score = 0.8
        label = "BULLISH"
    elif "crash" in text or "fall" in text:
        score = 0.2
        label = "BEARISH"
    else:
        score = 0.5
        label = "NEUTRAL"

    explanation = f"LLM Insight: The text indicates {label.lower()} sentiment based on market tone."

    return score, label, explanation