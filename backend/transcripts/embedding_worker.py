"""Isolated subprocess entrypoint for sentence-transformer encoding."""

from __future__ import annotations

import pickle
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: embedding_worker.py <input.pkl> <output.npy>", file=sys.stderr)
        return 2

    inpath = Path(sys.argv[1])
    outpath = Path(sys.argv[2])
    with inpath.open("rb") as handle:
        payload = pickle.load(handle)

    texts = payload["texts"]
    model_name = payload.get("model_name", "all-MiniLM-L6-v2")

    from backend.transcripts.embedding import _encode_texts_inprocess

    vectors = _encode_texts_inprocess(texts, model_name=model_name)
    if vectors is None:
        print("encode returned None", file=sys.stderr)
        return 1

    import numpy as np

    np.save(outpath, vectors)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
