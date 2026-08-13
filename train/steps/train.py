import os
import joblib
import pandas as pd

from sklearn.ensemble import RandomForestClassifier

train_path = "/opt/ml/input/data/train/train.csv"

df = pd.read_csv(train_path)

X = df.drop(columns=["target"])
y = df["target"]

model = RandomForestClassifier(
    n_estimators=100,
    max_depth=5,
    random_state=42,
)

model.fit(X, y)

os.makedirs("/opt/ml/model", exist_ok=True)

joblib.dump(
    model,
    "/opt/ml/model/model.joblib",
)