def add_features(df):
    df["returns"] = df["price"].pct_change()
    df["momentum"] = df["price"].diff()
    df["rolling_mean"] = df["price"].rolling(3).mean()
    return df.dropna()