"""One-click UniMERNet-T ONNX setup for CALT math OCR."""

from __future__ import annotations

import os
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS = ROOT / "data" / "math" / "unimernet" / "artifacts"
TOKENIZER = ROOT / "data" / "math" / "unimernet" / "models" / "unimernet_tiny"
WEIGHTS = TOKENIZER / "unimernet_tiny.pth"
PURE_PY = ROOT / "backend" / "math" / "pure_onnx_unimernet.py"
PURE_URL = "https://raw.githubusercontent.com/torvexlabs/unimernet-onnx/main/pure_onnx_unimernet.py"
GITHUB_TOK_BASE = "https://raw.githubusercontent.com/torvexlabs/unimernet-onnx/main/models/unimernet_tiny"
HF_WEIGHTS_REPO = "wanderkid/unimernet_tiny"

ONNX_FILES = ("encoder_model.onnx", "decoder_model.onnx", "decoder_with_past_model.onnx")
TOKENIZER_FILES = ("tokenizer.json", "tokenizer_config.json", "config.json", "preprocessor_config.json")


def _download_url(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and dest.stat().st_size > 100:
        print(f"  skip (exists): {dest.name}")
        return
    print(f"  download: {dest.name} ...")
    urllib.request.urlretrieve(url, dest)  # noqa: S310
    print(f"  ok: {dest.name}")


def step_pip() -> None:
    print("\n[1/5] Python packages")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "tokenizers", "ftfy", "huggingface_hub", "--quiet"])
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "--no-deps", "unimernet-onnx", "--quiet"],
        stderr=subprocess.DEVNULL,
    )
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--no-deps", "unimernet==0.2.3", "omegaconf", "iopath", "--quiet"]
        )
    except subprocess.CalledProcessError:
        pass


def step_pure_module() -> None:
    print("\n[2/5] Inference module")
    _download_url(PURE_URL, PURE_PY)


def step_tokenizer() -> None:
    print("\n[3/5] Tokenizer + config (GitHub)")
    TOKENIZER.mkdir(parents=True, exist_ok=True)
    for name in TOKENIZER_FILES:
        _download_url(f"{GITHUB_TOK_BASE}/{name}", TOKENIZER / name)


def step_weights() -> None:
    print("\n[4/5] Model weights (~250MB, Hugging Face public)")
    if WEIGHTS.is_file() and WEIGHTS.stat().st_size > 1_000_000:
        print("  skip (exists): unimernet_tiny.pth")
        return
    from huggingface_hub import hf_hub_download

    hf_hub_download(repo_id=HF_WEIGHTS_REPO, filename="unimernet_tiny.pth", local_dir=str(TOKENIZER))


def step_onnx() -> None:
    print("\n[5/5] ONNX export (CPU, ~2 min first time)")
    if all((ARTIFACTS / n).is_file() and (ARTIFACTS / n).stat().st_size > 1_000_000 for n in ONNX_FILES):
        print("  skip (exists): all ONNX artifacts")
        return
    subprocess.check_call([sys.executable, str(ROOT / "scripts" / "convert_unimernet_onnx.py")])


def verify() -> bool:
    print("\n[verify]")
    sys.path.insert(0, str(ROOT))
    from backend.math.unimernet_onnx import unimernet_available

    ok = unimernet_available()
    print("  UniMERNet ready:" if ok else "  UniMERNet NOT ready:", ok)
    return ok


def main() -> int:
    print("=== CALT UniMERNet auto-installer ===")
    step_pip()
    step_pure_module()
    step_tokenizer()
    step_weights()
    step_onnx()
    return 0 if verify() else 1


if __name__ == "__main__":
    raise SystemExit(main())

