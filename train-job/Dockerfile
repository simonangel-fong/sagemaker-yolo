# TrainJob image
# runs trainjob/train.py in the cluster.
#   docker build -f trainjob/Dockerfile -t simonangelfong/kubeflow-yolo-train:v0.1.1-cpu .

FROM python:3.12-slim

# install os packages 
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# install Python libraries (CPU-only torch)
COPY trainjob/requirements.cpu.txt ./requirements.cpu.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.cpu.txt

# Writable by the arbitrary UID the restricted PSS namespace assigns.
ENV YOLO_CONFIG_DIR=/tmp/ultralytics
ENV MPLCONFIGDIR=/tmp/matplotlib

# data_loader lives in src/ and is shared with the notebooks
COPY src/ ./src/
COPY trainjob/train.py ./trainjob/train.py
COPY configs/train.yaml ./configs/train.yaml

# copy pretrained model
COPY yolo11n.pt ./yolo11n.pt

ENTRYPOINT ["python", "-m", "trainjob.train"]
