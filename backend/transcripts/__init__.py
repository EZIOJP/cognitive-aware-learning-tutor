"""Transcript capture utilities (Windows Live Captions, etc.)."""

from backend.transcripts.cleanup import clean_transcript, normalize_segment
from backend.transcripts.live_captions import LiveCaptionsScraper, extract_caption_delta

__all__ = [
    "LiveCaptionsScraper",
    "clean_transcript",
    "extract_caption_delta",
    "normalize_segment",
    "generate_notes_from_file",
    "generate_notes_from_text",
]


def __getattr__(name: str):
    if name == "generate_notes_from_file":
        from backend.transcripts.notes_generator import generate_notes_from_file

        return generate_notes_from_file
    if name == "generate_notes_from_text":
        from backend.transcripts.notes_generator import generate_notes_from_text

        return generate_notes_from_text
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
