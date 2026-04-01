def generate_signal(prediction, sentiment_score):
    if sentiment_score > 0.7 and prediction == 1:
        return "BUY"
    elif sentiment_score < 0.3 and prediction == 0:
        return "SELL"
    else:
        return "HOLD"