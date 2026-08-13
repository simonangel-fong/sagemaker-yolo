# preprocess.py

import os
from pathlib import Path
import pandas as pd
from sklearn.model_selection import train_test_split

# read
input_path = "/opt/ml/processing/input/iris.csv"

df = pd.read_csv(input_path)

# split
train, validation = train_test_split(
    df,
    test_size=0.2,
    random_state=42,
    stratify=df["target"],
)

# persist
os.makedirs("/opt/ml/processing/train", exist_ok=True)
os.makedirs("/opt/ml/processing/validation", exist_ok=True)

train.to_csv(
    "/opt/ml/processing/train/train.csv",
    index=False,
)

validation.to_csv(
    "/opt/ml/processing/validation/validation.csv",
    index=False,
)