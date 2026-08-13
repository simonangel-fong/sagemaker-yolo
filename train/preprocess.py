import os
import pandas as pd
from sklearn.model_selection import train_test_split


# suffixes
IMAGE_SUFFIXES = {".jpeg", ".jpg", ".png"}

# class name file: have label name
CLASSES_FILENAME = "classes.txt"

# input
INPUT_DIR = "/opt/ml/processing/input"





files = os.listdir(INPUT_DIR)
df = pd.read_csv(os.path.join(input_dir, files[0]))

# Example preprocessing
df = df.dropna()

train_df, test_df = train_test_split(
    df,
    test_size=0.2,
    random_state=42
)

os.makedirs("/opt/ml/processing/train", exist_ok=True)
os.makedirs("/opt/ml/processing/test", exist_ok=True)

train_df.to_csv(
    "/opt/ml/processing/train/train.csv",
    index=False
)

test_df.to_csv(
    "/opt/ml/processing/test/test.csv",
    index=False
)