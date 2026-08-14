# SageMaker training image:
# AWS PyTorch DLC + Ultralytics + pretrained YOLO weights

ARG DEVICE=gpu
ARG ULTRALYTICS_VERSION=8.4.120

FROM 763104351884.dkr.ecr.ca-central-1.amazonaws.com/pytorch-training:2.6-${DEVICE}-py312

# System dependencies.
# Explicitly install curl because it is required during image build.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# PyTorch already comes from the AWS DLC.
# Pin Ultralytics for reproducible builds.
ARG ULTRALYTICS_VERSION
RUN python -m pip install --no-cache-dir \
    "ultralytics==${ULTRALYTICS_VERSION}"

# Bake pretrained weights into the image because
# SageMaker training jobs do not require internet access.
ENV YOLO_WEIGHTS=/opt/ml/weights/yolo26n.pt

RUN mkdir -p /opt/ml/weights \
    && curl --fail --location --show-error \
        --retry 3 \
        --output "${YOLO_WEIGHTS}" \
        https://github.com/ultralytics/assets/releases/latest/download/yolo26n.pt \
    && test -s "${YOLO_WEIGHTS}"

# Runtime-only caches/configuration.
ENV YOLO_CONFIG_DIR=/tmp/ultralytics \
    MPLCONFIGDIR=/tmp/matplotlib

RUN mkdir -p "${YOLO_CONFIG_DIR}" "${MPLCONFIGDIR}"