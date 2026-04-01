from sklearn.ensemble import RandomForestClassifier

def train_model(df):
    df["target"] = (df["returns"].shift(-1) > 0).astype(int)
    df = df.dropna()

    X = df[["momentum", "rolling_mean"]]
    y = df["target"]

    model = RandomForestClassifier()
    model.fit(X, y)

    return model