import streamlit as st

from src.data_loader import load_data
from src.feature_engineering import add_features
from src.sentiment_engine import analyze_text
from src.model import train_model
from src.signal_engine import generate_signal
from src.backtester import backtest

st.title("Crypto LLM Intelligence Terminal")

# Load data
df = load_data()
df = add_features(df)

# Train model
model = train_model(df)

# Latest data
latest = df.iloc[-1]
X_latest = [[latest["momentum"], latest["rolling_mean"]]]
prediction = model.predict(X_latest)[0]

# Sample text (simulate Reddit/news)
sample_text = st.text_input("Enter Market News", "Bitcoin is expected to rise strongly")

# LLM sentiment
sentiment_score, sentiment_label, explanation = analyze_text(sample_text)

# Signal
signal = generate_signal(prediction, sentiment_score)

# Backtest
accuracy = backtest(df)

# UI
st.subheader("Market Overview")
st.write(f"Price: {latest['price']}")

st.subheader("Sentiment Analysis (LLM)")
st.write(f"{sentiment_label} ({round(sentiment_score,2)})")
st.write(explanation)

st.subheader("Prediction")
st.write("UP" if prediction == 1 else "DOWN")

st.subheader("Trading Signal")
st.write(signal)

st.subheader("Backtest Accuracy")
st.write(f"{accuracy}%")

st.subheader("Reasoning")
st.write(f"""
- Sentiment Score: {round(sentiment_score,2)}
- Prediction: {"UP" if prediction==1 else "DOWN"}
- Momentum: {round(latest["momentum"],2)}
""")