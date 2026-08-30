"""Export UniMERNet-tiny .pth to ONNX artifacts for CALT (one-time setup)."""

from __future__ import annotations

import sys
from pathlib import Path

import onnx
import torch

ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = ROOT / "data" / "math" / "unimernet" / "models" / "unimernet_tiny"
WEIGHTS_PATH = MODEL_DIR / "unimernet_tiny.pth"
ARTIFACTS_DIR = ROOT / "data" / "math" / "unimernet" / "artifacts"

IMAGE_H = 192
IMAGE_W = 672
ENC_SEQ = 126
D_MODEL = 512
NUM_LAYERS = 8
NUM_HEADS = 16
KEY_DIM = 16
VALUE_DIM = 32
OPSET = 18


class EncoderWrapper(torch.nn.Module):
    def __init__(self, encoder):
        super().__init__()
        self.encoder = encoder

    def forward(self, pixel_values):
        if pixel_values.shape[1] == 1:
            pixel_values = pixel_values.repeat(1, 3, 1, 1)
        return self.encoder(pixel_values, return_dict=True).last_hidden_state


class DecoderWrapper(torch.nn.Module):
    def __init__(self, decoder):
        super().__init__()
        self.decoder = decoder

    def forward(self, input_ids, encoder_hidden_states):
        out = self.decoder(
            input_ids=input_ids,
            encoder_hidden_states=encoder_hidden_states,
            use_cache=True,
            return_dict=True,
        )
        flat = []
        for layer_pkv in out.past_key_values:
            flat.append(layer_pkv[0])
            flat.append(layer_pkv[1])
        return (out.logits, *flat)


class DecoderWithPastWrapper(torch.nn.Module):
    def __init__(self, decoder, num_layers):
        super().__init__()
        self.decoder = decoder
        self.num_layers = num_layers

    def forward(self, input_ids, encoder_hidden_states, *flat_pkv):
        pkv = tuple((flat_pkv[i * 2], flat_pkv[i * 2 + 1]) for i in range(self.num_layers))
        out = self.decoder(
            input_ids=input_ids,
            encoder_hidden_states=encoder_hidden_states,
            past_key_values=pkv,
            use_cache=True,
            return_dict=True,
        )
        flat_new = []
        for layer_pkv in out.past_key_values:
            flat_new.append(layer_pkv[0])
            flat_new.append(layer_pkv[1])
        return (out.logits, *flat_new)


def load_model():
    import importlib.util
    import site
    import sys
    import types
    from pathlib import Path

    import transformers.modeling_utils as mu

    if not hasattr(mu, "apply_chunking_to_forward"):

        def apply_chunking_to_forward(forward_fn, chunk_size, chunk_dim, *input_tensors):
            return forward_fn(*input_tensors)

        mu.apply_chunking_to_forward = apply_chunking_to_forward  # type: ignore[attr-defined]

    pkg_root: Path | None = None
    for sp in site.getsitepackages():
        candidate = Path(sp) / "unimernet"
        if candidate.is_dir():
            pkg_root = candidate
            break
    if pkg_root is None:
        raise RuntimeError("unimernet package not found in site-packages")

    for name, rel in (
        ("unimernet", pkg_root),
        ("unimernet.models", pkg_root / "models"),
        ("unimernet.models.unimernet", pkg_root / "models" / "unimernet"),
    ):
        if name not in sys.modules:
            mod = types.ModuleType(name)
            mod.__path__ = [str(rel)]  # type: ignore[attr-defined]
            sys.modules[name] = mod

    ed_path = pkg_root / "models" / "unimernet" / "encoder_decoder.py"
    spec = importlib.util.spec_from_file_location(
        "unimernet.models.unimernet.encoder_decoder",
        ed_path,
        submodule_search_locations=[str(ed_path.parent)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {ed_path}")
    ed_mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = ed_mod
    spec.loader.exec_module(ed_mod)
    DonutEncoderDecoder = ed_mod.DonutEncoderDecoder
    DonutTokenizer = ed_mod.DonutTokenizer

    tok = DonutTokenizer(str(MODEL_DIR))
    model = DonutEncoderDecoder(
        str(MODEL_DIR),
        num_tokens=len(tok),
        bos_token_id=tok.bos_token_id,
        pad_token_id=tok.pad_token_id,
        eos_token_id=tok.eos_token_id,
    )
    sd = torch.load(str(WEIGHTS_PATH), map_location="cpu", weights_only=True)
    sd = sd.get("model", sd)
    sd = {k.removeprefix("model.model.") if k.startswith("model.model.") else k: v for k, v in sd.items()}
    model.model.load_state_dict(sd, strict=False)
    model.eval()
    return model, tok


def main() -> int:
    import os

    os.environ.setdefault("TRANSFORMERS_ATTN_IMPLEMENTATION", "eager")

    if not WEIGHTS_PATH.is_file():
        print(f"Missing weights: {WEIGHTS_PATH}")
        return 1

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    enc_path = ARTIFACTS_DIR / "encoder_model.onnx"
    dec_path = ARTIFACTS_DIR / "decoder_model.onnx"
    dec_past_path = ARTIFACTS_DIR / "decoder_with_past_model.onnx"

    print("Loading UniMERNet-tiny (CPU)...")
    model, tok = load_model()

    print("[1/3] encoder...")
    enc_wrap = EncoderWrapper(model.model.encoder).eval()
    torch.onnx.export(
        enc_wrap,
        torch.zeros(1, 1, IMAGE_H, IMAGE_W),
        str(enc_path),
        dynamo=False,
        input_names=["pixel_values"],
        output_names=["encoder_hidden_states"],
        dynamic_axes={"pixel_values": {0: "batch", 3: "width"}, "encoder_hidden_states": {0: "batch", 1: "enc_seq"}},
        opset_version=OPSET,
        do_constant_folding=True,
    )

    print("[2/3] decoder...")
    dec_wrap = DecoderWrapper(model.model.decoder).eval()
    dummy_ids = torch.tensor([[tok.bos_token_id]])
    dummy_enc = torch.zeros(1, ENC_SEQ, D_MODEL)
    dec_out_names = ["logits"] + [
        f"present_{'key' if j == 0 else 'value'}_{i}" for i in range(NUM_LAYERS) for j in range(2)
    ]
    dec_dyn = {
        "input_ids": {0: "batch", 1: "dec_seq"},
        "encoder_hidden_states": {0: "batch", 1: "enc_seq"},
        "logits": {0: "batch", 1: "dec_seq"},
    }
    for i in range(NUM_LAYERS):
        dec_dyn[f"present_key_{i}"] = {0: "batch", 2: "dec_seq"}
        dec_dyn[f"present_value_{i}"] = {0: "batch", 2: "dec_seq"}
    torch.onnx.export(
        dec_wrap,
        (dummy_ids, dummy_enc),
        str(dec_path),
        dynamo=False,
        input_names=["input_ids", "encoder_hidden_states"],
        output_names=dec_out_names,
        dynamic_axes=dec_dyn,
        opset_version=OPSET,
        do_constant_folding=True,
    )

    print("[3/3] decoder_with_past...")
    dec_past_wrap = DecoderWithPastWrapper(model.model.decoder, NUM_LAYERS).eval()
    dummy_pkv = []
    for _ in range(NUM_LAYERS):
        dummy_pkv.append(torch.zeros(1, NUM_HEADS, 1, KEY_DIM))
        dummy_pkv.append(torch.zeros(1, NUM_HEADS, 1, VALUE_DIM))
    past_in = ["input_ids", "encoder_hidden_states"] + [
        f"past_{'key' if j == 0 else 'value'}_{i}" for i in range(NUM_LAYERS) for j in range(2)
    ]
    past_dyn = {
        "input_ids": {0: "batch", 1: "dec_seq"},
        "encoder_hidden_states": {0: "batch", 1: "enc_seq"},
        "logits": {0: "batch", 1: "dec_seq"},
    }
    for i in range(NUM_LAYERS):
        past_dyn[f"past_key_{i}"] = {0: "batch", 2: "past_seq"}
        past_dyn[f"past_value_{i}"] = {0: "batch", 2: "past_seq"}
        past_dyn[f"present_key_{i}"] = {0: "batch", 2: "present_seq"}
        past_dyn[f"present_value_{i}"] = {0: "batch", 2: "present_seq"}
    torch.onnx.export(
        dec_past_wrap,
        (dummy_ids, dummy_enc, *dummy_pkv),
        str(dec_past_path),
        dynamo=False,
        input_names=past_in,
        output_names=dec_out_names,
        dynamic_axes=past_dyn,
        opset_version=OPSET,
        do_constant_folding=True,
    )

    for p in (enc_path, dec_path, dec_past_path):
        onnx.checker.check_model(str(p))
        print(f"OK {p.name}: {p.stat().st_size // 1_000_000} MB")

    print("Done — UniMERNet ONNX ready.")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    raise SystemExit(main())
