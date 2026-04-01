def backtest(df):
    wins = (df["returns"] > 0).sum()
    total = len(df)

    return round((wins / total) * 100, 2)