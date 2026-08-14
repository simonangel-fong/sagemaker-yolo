# preprocess.py

import os
import random
import shutil

input_dir = "/opt/ml/processing/input"


images = {}
labels = {}

# read: an image and its label
for name in os.listdir(input_dir):
    stem, suffix = os.path.splitext(name)
    if suffix.lower() in (".jpeg", ".jpg", ".png"):
        images[stem] = name
    elif suffix.lower() == ".txt" and name != "classes.txt":
        labels[stem] = name

# sort
pairs = sorted(images.keys() & labels.keys())

# split
random.Random(42).shuffle(pairs)

# val
n_val = round(len(pairs) * 0.2)

splits = {
    "val": pairs[:n_val],
    "train": pairs[n_val:],
}

# persist
for split, stems in splits.items():
    os.makedirs(f"/opt/ml/processing/split/{split}/images", exist_ok=True)
    os.makedirs(f"/opt/ml/processing/split/{split}/labels", exist_ok=True)

    for stem in stems:
        shutil.copy2(
            f"{input_dir}/{images[stem]}",
            f"/opt/ml/processing/split/{split}/images/{images[stem]}",
        )
        shutil.copy2(
            f"{input_dir}/{labels[stem]}",
            f"/opt/ml/processing/split/{split}/labels/{labels[stem]}",
        )

# data.yaml: show the split
with open(f"{input_dir}/classes.txt") as f:
    names = f.read().split()

os.makedirs("/opt/ml/processing/config", exist_ok=True)

with open("/opt/ml/processing/config/data.yaml", "w") as f:
    f.write(
        "path: /opt/ml/input/data/split\n"
        "train: train/images\n"
        "val: val/images\n"
        f"nc: {len(names)}\n"
        f"names: {names}\n"
    )

print(f"train {len(splits['train'])}, val {len(splits['val'])}")
