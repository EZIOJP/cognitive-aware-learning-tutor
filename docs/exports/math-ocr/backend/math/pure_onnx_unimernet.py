"""
pure_onnx_unimernet.py
======================
Drop-in formula recognizer using only onnxruntime + tokenizers.
No PyTorch. No unimernet package. No transformers.

Dependencies:
    pip install onnxruntime numpy pillow opencv-python-headless tokenizers ftfy

Usage:
    from pure_onnx_unimernet import OnnxUnimerNet

    model = OnnxUnimerNet(
        artifacts_dir="artifacts",
        tokenizer_path="models/unimernet_tiny",
    )
    latex = model.predict(PIL.Image.open("formula.png"))

File layout expected:
    artifacts/
        encoder_model.onnx
        decoder_model.onnx
        decoder_with_past_model.onnx
    models/unimernet_tiny/
        tokenizer.json
        tokenizer_config.json
"""

from __future__ import annotations


import os
import site
import time
import numpy as np
import onnxruntime as ort
from pathlib import Path
from PIL import Image, ImageOps
from typing import Any, List, Optional, Union


# ---------------------------------------------------------------------------
# Constants - must match what was used during export
# ---------------------------------------------------------------------------
IMAGE_H       = 192
IMAGE_W       = 672
MEAN          = 0.7931
STD           = 0.1738
NUM_LAYERS    = 8
MAX_NEW_TOKENS = 1534
DEFAULT_MAX_BATCH_SIZE = 8
_DLL_DIRECTORY_HANDLES: list[Any] = []


def _provider_name(provider: object) -> str:
    if isinstance(provider, tuple) and provider:
        return str(provider[0])
    return str(provider)


def _cuda_requested(providers: list[object]) -> bool:
    return any(_provider_name(provider) == "CUDAExecutionProvider" for provider in providers)


def _cuda_device_id(providers: list[object]) -> int:
    for provider in providers:
        if not isinstance(provider, tuple) or _provider_name(provider) != "CUDAExecutionProvider":
            continue
        if len(provider) < 2 or not isinstance(provider[1], dict):
            continue
        return int(provider[1].get("device_id", 0))
    return 0


def _nvidia_bin_dirs() -> list[Path]:
    roots: list[Path] = []

    try:
        import nvidia

        roots.append(Path(nvidia.__file__).resolve().parent)
    except Exception:
        pass

    for site_dir in site.getsitepackages():
        roots.append(Path(site_dir) / "nvidia")

    try:
        roots.append(Path(site.getusersitepackages()) / "nvidia")
    except Exception:
        pass

    component_order = (
        "cudnn",
        "cublas",
        "cuda_runtime",
        "cuda_nvrtc",
        "cufft",
        "curand",
        "nvjitlink",
    )

    seen: set[Path] = set()
    bin_dirs: list[Path] = []
    for root in roots:
        for component in component_order:
            bin_dir = root / component / "bin"
            if bin_dir.exists() and bin_dir not in seen:
                seen.add(bin_dir)
                bin_dirs.append(bin_dir)

    return bin_dirs


def _prepare_cuda_runtime(providers: list[object]) -> None:
    if not _cuda_requested(providers):
        return

    if "CUDAExecutionProvider" not in ort.get_available_providers():
        raise RuntimeError(
            "CUDAExecutionProvider was requested, but this ONNX Runtime build does "
            "not expose CUDA. Install onnxruntime-gpu[cuda,cudnn] or use CPU."
        )

    if os.name == "nt":
        existing_path = os.environ.get("PATH", "")
        existing_parts = set(existing_path.split(os.pathsep))
        new_parts: list[str] = []

        for bin_dir in _nvidia_bin_dirs():
            bin_dir_str = str(bin_dir)
            if hasattr(os, "add_dll_directory"):
                try:
                    _DLL_DIRECTORY_HANDLES.append(os.add_dll_directory(bin_dir_str))
                except OSError:
                    pass
            if bin_dir_str not in existing_parts:
                new_parts.append(bin_dir_str)

        if new_parts:
            os.environ["PATH"] = os.pathsep.join(new_parts + [existing_path])

    preload_dlls = getattr(ort, "preload_dlls", None)
    if preload_dlls is not None:
        try:
            preload_dlls(directory="")
        except TypeError:
            preload_dlls()


def _disable_ort_fallback_if_cuda_requested(
    providers: list[object],
    sessions: list[ort.InferenceSession],
) -> None:
    if not _cuda_requested(providers):
        return

    for session in sessions:
        if "CUDAExecutionProvider" not in session.get_providers():
            raise RuntimeError(
                "CUDAExecutionProvider was requested, but ONNX Runtime did not "
                "activate it for the UniMERNet session."
            )
        if hasattr(session, "disable_fallback"):
            session.disable_fallback()


def _onnx_float_type_to_numpy(type_name: str) -> type[np.floating]:
    if type_name == "tensor(float16)":
        return np.float16
    if type_name == "tensor(float)":
        return np.float32
    raise TypeError(f"Unsupported ONNX float tensor type: {type_name}")


def _session_input_dtype(session: ort.InferenceSession, input_name: str) -> type[np.floating]:
    for session_input in session.get_inputs():
        if session_input.name == input_name:
            return _onnx_float_type_to_numpy(session_input.type)
    raise KeyError(f"ONNX input not found: {input_name}")



# ---------------------------------------------------------------------------
# Preprocessor
# Replicates FormulaImageEvalProcessor exactly - same as convert_to_onnx.py
# ---------------------------------------------------------------------------
def _preprocess(img: Image.Image) -> np.ndarray:
    """
    Returns float32 numpy array [1, 1, 192, 672].
    The encoder ONNX handles the 1-to-3 channel repeat internally.
    """
    import cv2

    # crop margins
    data = np.array(img.convert("L")).astype(np.uint8)
    max_val, min_val = data.max(), data.min()
    if max_val != min_val:
        data_norm = (data - min_val) / (max_val - min_val) * 255
        gray = 255 * (data_norm < 200).astype(np.uint8)
        coords = cv2.findNonZero(gray)
        if coords is not None:
            a, b, w, h = cv2.boundingRect(coords)
            img = img.crop((a, b, w + a, h + b))

    img = img.convert("RGB")

    # Scale shortest side to min(192, 672) = 192
    w, h = img.size
    short = min(h, w)
    scale = min(IMAGE_H, IMAGE_W) / short
    new_w = int(round(w * scale))
    new_h = int(round(h * scale))
    img = img.resize((new_w, new_h), Image.BICUBIC)
    img.thumbnail((IMAGE_W, IMAGE_H), Image.BICUBIC)

    # center pad to exactly 192x672
    delta_w = IMAGE_W - img.width
    delta_h = IMAGE_H - img.height
    pad_w   = delta_w // 2
    pad_h   = delta_h // 2
    img = ImageOps.expand(img, (pad_w, pad_h, delta_w - pad_w, delta_h - pad_h))

    # grayscale -> normalize -> [1, 1, H, W]
    arr = np.array(img.convert("L")).astype(np.float32) / 255.0
    arr = (arr - MEAN) / STD
    return arr[np.newaxis, np.newaxis, :, :]  # [1, 1, 192, 672]


def _preprocess_batch(imgs: List[Image.Image]) -> np.ndarray:
    if not imgs:
        raise ValueError("imgs must contain at least one image")
    return np.concatenate([_preprocess(img) for img in imgs], axis=0)


def _image_batch_sort_key(img: Image.Image) -> tuple[int, int, float]:
    width, height = img.size
    area = int(width * height)
    aspect = float(width) / max(float(height), 1.0)
    return (area, int(width), aspect)


# ---------------------------------------------------------------------------
# Tokenizer wrapper - uses tokenizers library directly, no transformers
# ---------------------------------------------------------------------------
class _Tokenizer:
    def __init__(self, tokenizer_path: str):
        from tokenizers import Tokenizer
        path = Path(tokenizer_path) / "tokenizer.json"
        if not path.exists():
            raise FileNotFoundError(f"tokenizer.json not found at {path}")
        self._tok = Tokenizer.from_file(str(path))

        # Resolve special token ids
        self.bos_token_id = self._get_id("<s>")
        self.eos_token_id = self._get_id("</s>")
        self.pad_token_id = self._get_id("<pad>")

    def _get_id(self, token: str) -> int:
        id_ = self._tok.token_to_id(token)
        if id_ is None:
            raise ValueError(f"Token {token!r} not found in tokenizer vocabulary")
        return id_

    def decode(self, token_ids: List[int]) -> str:
        # Filter special tokens
        filtered = [t for t in token_ids
                    if t not in (self.bos_token_id, self.eos_token_id, self.pad_token_id)]
        text = self._tok.decode(filtered)
        try:
            from ftfy import fix_text
            text = fix_text(text)
        except ImportError:
            pass
        return text


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------
class OnnxUnimerNet:
    """
    Pure ONNX formula recognizer. Drop-in replacement for pytorch_unimernet_mfr.py.

    Args:
        artifacts_dir:   Path to folder containing the three .onnx files.
        tokenizer_path:  Path to folder containing tokenizer.json.
        providers:       onnxruntime execution providers.
                         Default: ["CPUExecutionProvider"]
                         GPU:     ["CUDAExecutionProvider", "CPUExecutionProvider"]
        max_new_tokens:  Hard cap on generated tokens. Default: 1534 (model limit).
        num_threads:     onnxruntime intra/inter op thread count. Default: 0 (auto).
        use_iobinding:   Keep decoder KV cache on CUDA between steps. CUDA only.
    """

    def __init__(
        self,
        artifacts_dir: Union[str, Path] = "artifacts",
        tokenizer_path: Union[str, Path] = "models/unimernet_tiny",
        providers: Optional[List[object]] = None,
        max_new_tokens: int = MAX_NEW_TOKENS,
        num_threads: int = 0,
        use_iobinding: bool = False,
    ):
        artifacts_dir = Path(artifacts_dir)
        self.max_new_tokens = max_new_tokens

        # Session options
        opts = ort.SessionOptions()
        if num_threads > 0:
            opts.inter_op_num_threads = num_threads
            opts.intra_op_num_threads = num_threads
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        if providers is None:
            providers = ["CPUExecutionProvider"]
        _prepare_cuda_runtime(providers)
        self._cuda_device_id = _cuda_device_id(providers)

        # Load ONNX sessions
        enc_path      = artifacts_dir / "encoder_model.onnx"
        dec_path      = artifacts_dir / "decoder_model.onnx"
        dec_past_path = artifacts_dir / "decoder_with_past_model.onnx"

        for p in [enc_path, dec_path, dec_past_path]:
            if not p.exists():
                raise FileNotFoundError(f"ONNX file not found: {p}")

        self._enc_sess      = ort.InferenceSession(str(enc_path),      opts, providers=providers)
        self._dec_sess      = ort.InferenceSession(str(dec_path),      opts, providers=providers)
        self._dec_past_sess = ort.InferenceSession(str(dec_past_path), opts, providers=providers)
        _disable_ort_fallback_if_cuda_requested(
            providers,
            [self._enc_sess, self._dec_sess, self._dec_past_sess],
        )
        self._pixel_dtype = _session_input_dtype(self._enc_sess, "pixel_values")
        self._dec_output_names = [output.name for output in self._dec_sess.get_outputs()]
        self._dec_past_output_names = [
            output.name for output in self._dec_past_sess.get_outputs()
        ]
        self._use_iobinding = bool(use_iobinding)
        if self._use_iobinding and "CUDAExecutionProvider" not in self._enc_sess.get_providers():
            raise ValueError("use_iobinding=True requires CUDAExecutionProvider to be active.")

        # Load tokenizer
        self._tok = _Tokenizer(str(tokenizer_path))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def predict(self, img: Image.Image) -> str:
        return self.recognize(img)["latex"]

    def recognize(self, img: Image.Image) -> dict:
        started = time.perf_counter()

        pixel_values = _preprocess(img)
        token_ids = self._decode(pixel_values)

        elapsed_ms = (time.perf_counter() - started) * 1000.0
        last_token = token_ids[-1] if token_ids else None
        eos_reached = last_token == self._tok.eos_token_id

        return {
            "latex": self._tok.decode(token_ids),
            "tokens": token_ids,
            "token_count": len(token_ids),
            "last_token": last_token,
            "eos_reached": eos_reached,
            "truncated": (not eos_reached and len(token_ids) >= self.max_new_tokens),
            "elapsed_ms": round(elapsed_ms, 3),
            "ms_per_token": round(elapsed_ms / max(len(token_ids), 1), 3),
            "active_providers": {
                "encoder": self._enc_sess.get_providers(),
                "decoder": self._dec_sess.get_providers(),
                "decoder_with_past": self._dec_past_sess.get_providers(),
            },
            "io_binding": self._use_iobinding,
        }


    def recognize_batch(
        self,
        imgs: List[Image.Image],
        *,
        max_batch_size: int = DEFAULT_MAX_BATCH_SIZE,
        sort_by_size: bool = True,
    ) -> List[dict]:
        """
        Recognize formula images in bounded, optionally size-bucketed batches.
        """
        if not imgs:
            return []
        if max_batch_size < 1:
            raise ValueError("max_batch_size must be >= 1")

        indexed_imgs = list(enumerate(imgs))
        if sort_by_size:
            indexed_imgs.sort(key=lambda item: _image_batch_sort_key(item[1]))

        results: list[dict | None] = [None] * len(imgs)
        total_started = time.perf_counter()
        group_index = 0

        for start in range(0, len(indexed_imgs), max_batch_size):
            chunk = indexed_imgs[start:start + max_batch_size]
            chunk_imgs = [img for _, img in chunk]

            chunk_started = time.perf_counter()
            pixel_values = _preprocess_batch(chunk_imgs)
            token_lists = self._decode_batch(pixel_values)
            chunk_elapsed_ms = (time.perf_counter() - chunk_started) * 1000.0
            elapsed_ms = chunk_elapsed_ms / max(len(token_lists), 1)

            for (original_index, _), token_ids in zip(chunk, token_lists):
                last_token = token_ids[-1] if token_ids else None
                eos_reached = last_token == self._tok.eos_token_id

                results[original_index] = {
                    "latex": self._tok.decode(token_ids),
                    "tokens": token_ids,
                    "token_count": len(token_ids),
                    "last_token": last_token,
                    "eos_reached": eos_reached,
                    "truncated": (not eos_reached and len(token_ids) >= self.max_new_tokens),
                    "elapsed_ms": round(elapsed_ms, 3),
                    "ms_per_token": round(elapsed_ms / max(len(token_ids), 1), 3),
                    "batch_size": len(token_lists),
                    "batch_group_index": group_index,
                    "batch_elapsed_ms": round(chunk_elapsed_ms, 3),
                    "max_batch_size": max_batch_size,
                    "sort_by_size": sort_by_size,
                    "active_providers": {
                        "encoder": self._enc_sess.get_providers(),
                        "decoder": self._dec_sess.get_providers(),
                        "decoder_with_past": self._dec_past_sess.get_providers(),
                    },
                    "io_binding": self._use_iobinding,
                }

            group_index += 1

        total_elapsed_ms = (time.perf_counter() - total_started) * 1000.0
        for result in results:
            if result is not None:
                result["total_batch_elapsed_ms"] = round(total_elapsed_ms, 3)

        return [result for result in results if result is not None]


    def predict_batch(
        self,
        imgs: List[Image.Image],
        *,
        max_batch_size: int = DEFAULT_MAX_BATCH_SIZE,
        sort_by_size: bool = True,
    ) -> List[str]:
        return [
            result["latex"]
            for result in self.recognize_batch(
                imgs,
                max_batch_size=max_batch_size,
                sort_by_size=sort_by_size,
            )
        ]

    # ------------------------------------------------------------------
    # Internal decode loop
    # ------------------------------------------------------------------

    def _decode(self, pixel_values: np.ndarray) -> List[int]:
        """
        Full greedy decode: encoder -> decoder step 1 -> decoder with past N times.

        Args:
            pixel_values: [1, 1, 192, 672] float32 numpy array.

        Returns:
            List of token ids (including EOS if reached).
        """
        if self._use_iobinding:
            return self._decode_batch_iobinding(pixel_values)[0]

        # 1. Encode
        pixel_values = pixel_values.astype(self._pixel_dtype, copy=False)
        enc_hs = self._enc_sess.run(
            ["encoder_hidden_states"],
            {"pixel_values": pixel_values},
        )[0]  # [1, 126, 512]

        # 2. Decoder step 1 (no past KV)
        input_ids = np.array([[self._tok.bos_token_id]], dtype=np.int64)
        dec_out   = self._dec_sess.run(None, {
            "input_ids":              input_ids,
            "encoder_hidden_states":  enc_hs,
        })
        logits = dec_out[0]          # [1, 1, 50000]
        flat_pkv = dec_out[1:]       # 16 tensors: key_0, value_0, ..., key_7, value_7

        tokens: List[int] = []

        # 3. Greedy decode loop
        for _ in range(self.max_new_tokens):
            next_id = int(np.argmax(logits[0, -1]))
            tokens.append(next_id)

            if next_id == self._tok.eos_token_id:
                break

            input_ids = np.array([[next_id]], dtype=np.int64)

            # Build past KV feed
            past_feed: dict = {
                "input_ids":             input_ids,
                "encoder_hidden_states": enc_hs,
            }
            for i in range(NUM_LAYERS):
                past_feed[f"past_key_{i}"]   = flat_pkv[i * 2]
                past_feed[f"past_value_{i}"] = flat_pkv[i * 2 + 1]

            dec_past_out = self._dec_past_sess.run(None, past_feed)
            logits = dec_past_out[0]
            flat_pkv = dec_past_out[1:]

        return tokens


    def _bind_decoder_outputs(
        self,
        io_binding: ort.IOBinding,
        output_names: List[str],
    ) -> None:
        # Keep KV cache on CUDA, but return logits to CPU for Python argmax.
        io_binding.bind_output(output_names[0], device_type="cpu")
        for output_name in output_names[1:]:
            io_binding.bind_output(
                output_name,
                device_type="cuda",
                device_id=self._cuda_device_id,
            )


    def _encode_iobinding(self, pixel_values: np.ndarray) -> ort.OrtValue:
        pixel_values = np.ascontiguousarray(
            pixel_values.astype(self._pixel_dtype, copy=False)
        )
        pixel_values_ort = ort.OrtValue.ortvalue_from_numpy(
            pixel_values,
            device_type="cuda",
            device_id=self._cuda_device_id,
        )

        io_binding = self._enc_sess.io_binding()
        io_binding.bind_ortvalue_input("pixel_values", pixel_values_ort)
        io_binding.bind_output(
            "encoder_hidden_states",
            device_type="cuda",
            device_id=self._cuda_device_id,
        )
        self._enc_sess.run_with_iobinding(io_binding)

        outputs = io_binding.get_outputs()
        if len(outputs) != 1:
            raise RuntimeError(f"Expected one encoder output, got {len(outputs)}.")
        return outputs[0]


    def _decode_first_iobinding(
        self,
        input_ids: np.ndarray,
        encoder_hidden_states: ort.OrtValue,
    ) -> tuple[np.ndarray, List[ort.OrtValue]]:
        input_ids = np.ascontiguousarray(input_ids)

        io_binding = self._dec_sess.io_binding()
        io_binding.bind_cpu_input("input_ids", input_ids)
        io_binding.bind_ortvalue_input("encoder_hidden_states", encoder_hidden_states)
        self._bind_decoder_outputs(io_binding, self._dec_output_names)
        self._dec_sess.run_with_iobinding(io_binding)

        outputs = io_binding.get_outputs()
        if len(outputs) != 1 + NUM_LAYERS * 2:
            raise RuntimeError(f"Unexpected decoder output count: {len(outputs)}.")
        return outputs[0].numpy(), outputs[1:]


    def _decode_past_iobinding(
        self,
        input_ids: np.ndarray,
        encoder_hidden_states: ort.OrtValue,
        flat_pkv: List[ort.OrtValue],
    ) -> tuple[np.ndarray, List[ort.OrtValue]]:
        input_ids = np.ascontiguousarray(input_ids)

        io_binding = self._dec_past_sess.io_binding()
        io_binding.bind_cpu_input("input_ids", input_ids)
        io_binding.bind_ortvalue_input("encoder_hidden_states", encoder_hidden_states)
        for i in range(NUM_LAYERS):
            io_binding.bind_ortvalue_input(f"past_key_{i}", flat_pkv[i * 2])
            io_binding.bind_ortvalue_input(f"past_value_{i}", flat_pkv[i * 2 + 1])
        self._bind_decoder_outputs(io_binding, self._dec_past_output_names)
        self._dec_past_sess.run_with_iobinding(io_binding)

        outputs = io_binding.get_outputs()
        if len(outputs) != 1 + NUM_LAYERS * 2:
            raise RuntimeError(
                f"Unexpected decoder-with-past output count: {len(outputs)}."
            )
        return outputs[0].numpy(), outputs[1:]


    def _decode_batch_iobinding(self, pixel_values: np.ndarray) -> List[List[int]]:
        batch_size = int(pixel_values.shape[0])

        enc_hs = self._encode_iobinding(pixel_values)
        input_ids = np.full(
            (batch_size, 1),
            self._tok.bos_token_id,
            dtype=np.int64,
        )

        logits, flat_pkv = self._decode_first_iobinding(input_ids, enc_hs)

        tokens: List[List[int]] = [[] for _ in range(batch_size)]
        finished = np.zeros((batch_size,), dtype=bool)

        for _ in range(self.max_new_tokens):
            next_ids = np.argmax(logits[:, -1, :], axis=-1).astype(np.int64)

            for i, next_id in enumerate(next_ids.tolist()):
                if finished[i]:
                    continue
                tokens[i].append(int(next_id))
                if int(next_id) == self._tok.eos_token_id:
                    finished[i] = True

            if bool(np.all(finished)):
                break

            feed_ids = next_ids.copy()
            feed_ids[finished] = self._tok.eos_token_id
            input_ids = feed_ids.reshape(batch_size, 1)

            logits, flat_pkv = self._decode_past_iobinding(
                input_ids,
                enc_hs,
                flat_pkv,
            )

        return tokens


    def _decode_batch(self, pixel_values: np.ndarray) -> List[List[int]]:
        if self._use_iobinding:
            return self._decode_batch_iobinding(pixel_values)

        batch_size = int(pixel_values.shape[0])
        pixel_values = pixel_values.astype(self._pixel_dtype, copy=False)

        enc_hs = self._enc_sess.run(
            ["encoder_hidden_states"],
            {"pixel_values": pixel_values},
        )[0]

        input_ids = np.full(
            (batch_size, 1),
            self._tok.bos_token_id,
            dtype=np.int64,
        )

        dec_out = self._dec_sess.run(None, {
            "input_ids": input_ids,
            "encoder_hidden_states": enc_hs,
        })

        logits = dec_out[0]
        flat_pkv = dec_out[1:]

        tokens: List[List[int]] = [[] for _ in range(batch_size)]
        finished = np.zeros((batch_size,), dtype=bool)

        for _ in range(self.max_new_tokens):
            next_ids = np.argmax(logits[:, -1, :], axis=-1).astype(np.int64)

            for i, next_id in enumerate(next_ids.tolist()):
                if finished[i]:
                    continue
                tokens[i].append(int(next_id))
                if int(next_id) == self._tok.eos_token_id:
                    finished[i] = True

            if bool(np.all(finished)):
                break

            feed_ids = next_ids.copy()
            feed_ids[finished] = self._tok.eos_token_id
            input_ids = feed_ids.reshape(batch_size, 1)

            past_feed = {
                "input_ids": input_ids,
                "encoder_hidden_states": enc_hs,
            }
            for i in range(NUM_LAYERS):
                past_feed[f"past_key_{i}"] = flat_pkv[i * 2]
                past_feed[f"past_value_{i}"] = flat_pkv[i * 2 + 1]

            dec_past_out = self._dec_past_sess.run(None, past_feed)
            logits = dec_past_out[0]
            flat_pkv = dec_past_out[1:]

        return tokens


# ---------------------------------------------------------------------------
# CLI - quick sanity check
# Usage: python pure_onnx_unimernet.py path/to/formula.png
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    import time

    if len(sys.argv) < 2:
        print("Usage: python pure_onnx_unimernet.py <image_path> [artifacts_dir] [tokenizer_path]")
        sys.exit(1)

    img_path       = sys.argv[1]
    artifacts_dir  = sys.argv[2] if len(sys.argv) > 2 else "artifacts"
    tokenizer_path = sys.argv[3] if len(sys.argv) > 3 else "models/unimernet_tiny"

    print(f"Loading model from {artifacts_dir}...")
    model = OnnxUnimerNet(
        artifacts_dir=artifacts_dir,
        tokenizer_path=tokenizer_path,
    )

    img = Image.open(img_path)
    print(f"Running inference on {img_path}...")

    t0     = time.perf_counter()
    result = model.predict(img)
    elapsed = time.perf_counter() - t0

    print(f"\nLatex: {result}")
    print(f"Time:  {elapsed*1000:.0f}ms")
