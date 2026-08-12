"""
Workaround for a Windows-only bug in the sagemaker v3 SDK.

`ModelTrainer._prepare_train_script` writes the generated sm_train.sh with a
plain `open(path, "w")`. On Windows that translates every "\n" to "\r\n", so
the shell script reaches the Linux training container with CRLF endings and
bash refuses it:

    sm_train.sh: line 1: $'\r': command not found
    sm_train.sh: line 6: syntax error near unexpected token `$'{\r''

The training job then dies with "AlgorithmError: , exit code: 2" and an empty
log stream, because nothing ever got as far as running Python.

Verified against sagemaker 3.19.0 / sagemaker-train 1.19.0. `apply()` rewrites
the file in place after the SDK generates it; it is a no-op off Windows, and it
leaves everything else about the upload alone.
"""

from __future__ import annotations

import os


def apply() -> bool:
    """Normalise sm_train.sh to LF. Returns True if the patch was installed."""
    if os.name != "nt":
        return False

    from sagemaker.train.constants import TRAIN_SCRIPT
    from sagemaker.train.model_trainer import ModelTrainer

    if getattr(ModelTrainer, "_sm_train_lf_patched", False):
        return True

    original = ModelTrainer._prepare_train_script

    def patched(self, tmp_dir, *args, **kwargs):
        result = original(self, tmp_dir, *args, **kwargs)

        path = os.path.join(tmp_dir.name, TRAIN_SCRIPT)
        if os.path.exists(path):
            with open(path, "rb") as f:
                content = f.read()
            # rewrite only if the SDK actually introduced CRLF, so a fixed
            # future version quietly stops needing this
            if b"\r\n" in content:
                with open(path, "wb") as f:
                    f.write(content.replace(b"\r\n", b"\n"))

        return result

    ModelTrainer._prepare_train_script = patched
    ModelTrainer._sm_train_lf_patched = True
    return True
