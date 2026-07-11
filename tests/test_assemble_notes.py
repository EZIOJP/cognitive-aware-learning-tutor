"""Unit tests for lecture-first assemble helpers."""

from __future__ import annotations

from backend.transcripts.assemble_notes import _cite_blocks, _extractive_bullets, _strip_heading_blocks
import re


def test_extractive_bullets_skips_logistics_keeps_numpy() -> None:
    chunk = (
        "Please give a thumbs up if you can hear me. "
        "NumPy arrays store homogeneous data in contiguous memory for fast vectorized math. "
        "Any questions before we continue?"
    )
    bullets = _extractive_bullets(chunk, max_bullets=5)
    assert bullets
    joined = " ".join(bullets).lower()
    assert "thumbs" not in joined
    assert "numpy" in joined


def test_strip_image_captioning_heading() -> None:
    md = """# Title

## Introduction to Image Captioning
Bogus AI textbook dump.

## Overview of Numpy
Arrays and shape.
"""
    out = _strip_heading_blocks(md, title_re=re.compile(r"(?i)image\s+caption"))
    assert "Image Captioning" not in out
    assert "Overview of Numpy" in out


def test_cite_blocks_format() -> None:
    hits = [
        {
            "chunk_id": "c1",
            "citation": "MML ch1",
            "raw_payload": "A matrix is a rectangular array of numbers.",
        }
    ]
    blocks = _cite_blocks(hits)
    assert len(blocks) == 1
    assert "cite: c1" in blocks[0]
    assert "rectangular array" in blocks[0]
