import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
import joblib

def train_model():
    df = pd.read_csv("trades.csv")

    df.columns = ["time", "symbol", "entry", "exit", "profit", "result"]

    # 🔥 Prediction Feature
    df["change"] = (df["exit"] - df["entry"]) / df["entry"]

    df["target"] = (df["change"] > 0).astype(int)

# 🔥 Feature جديد
    df["volume"] = df["exit"] - df["entry"]

    X = df[["entry", "change", "volume"]]
    y = df["target"]

    

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)

    model = RandomForestClassifier(n_estimators=150)
    model.fit(X_train, y_train)

    acc = model.score(X_test, y_test)
    print("🔥 Prediction Accuracy:", acc)

    joblib.dump(model, "model.pkl")


if __name__ == "__main__":
    train_model()