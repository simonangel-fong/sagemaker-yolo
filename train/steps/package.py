# package.py
#
# Injects the serving handler into the trained model artifact.
#
# The training job emits a model.tar.gz holding the weights and the metadata
# sidecar, and nothing else. SageMaker's inference toolkit looks for the handler
# at code/inference.py inside that archive, so this step unpacks it, adds code/,
# and retars. Keeping it out of the training job means the handler can change
# without retraining.

import os
import shutil
import tarfile
import tempfile

model_dir = "/opt/ml/processing/model"
handler_dir = "/opt/ml/processing/handler"
output_dir = "/opt/ml/processing/packaged"

# ##############################
# Locate the trained artifact
# ##############################
archives = sorted(
    name for name in os.listdir(model_dir) if name.endswith(".tar.gz")
)
if not archives:
    raise RuntimeError(f"no .tar.gz under {model_dir}, found {os.listdir(model_dir)}")

source_archive = f"{model_dir}/{archives[0]}"

# ##############################
# Unpack
# ##############################
staging = tempfile.mkdtemp()

with tarfile.open(source_archive) as tar:
    try:
        tar.extractall(staging, filter="data")
    except TypeError:
        tar.extractall(staging)

print(f"unpacked   {source_archive}")
for name in sorted(os.listdir(staging)):
    print(f"  {name}")

# ##############################
# Inject the handler
# ##############################
# SAGEMAKER_SUBMIT_DIRECTORY: point to path /opt/ml/model/code
# SAGEMAKER_PROGRAM: names inference.py within it; both are set in terraform.
code_dir = f"{staging}/code"
os.makedirs(code_dir, exist_ok=True)

for source, destination in (
    ("inference.py", "inference.py"),
    ("requirements.txt", "requirements.txt"),
):
    path = f"{handler_dir}/{source}"
    if not os.path.exists(path):
        raise RuntimeError(f"handler file missing: {path}")
    shutil.copy2(path, f"{code_dir}/{destination}")

# ##############################
# Retar
# ##############################
os.makedirs(output_dir, exist_ok=True)
target_archive = f"{output_dir}/model.tar.gz"

# arcname is set on every member: a path leaking in from the staging directory
# would put the weights somewhere the toolkit does not look
with tarfile.open(target_archive, "w:gz") as tar:
    for root, dirs, files in os.walk(staging):
        # the handler channel mirrors a local directory, so a stray __pycache__
        # can ride along; it has no business in the artifact
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in files:
            if name.endswith((".pyc", ".pyo")):
                continue
            absolute = os.path.join(root, name)
            arcname = os.path.relpath(absolute, staging).replace(os.sep, "/")
            tar.add(absolute, arcname=arcname)

print(f"\npacked     {target_archive}")
with tarfile.open(target_archive) as tar:
    for name in sorted(tar.getnames()):
        print(f"  {name}")
