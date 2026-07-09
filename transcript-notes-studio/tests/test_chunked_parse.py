from transcript_studio.chunked_parse import parse_transcript_auto, parse_transcript_chunked


def test_chunked_parse_prefix_dedup():
    raw = (
        "Hey welcome\n"
        "Hey welcome everyone\n"
        "Hey welcome everyone today we cover numpy"
    )
    result = parse_transcript_chunked(
        raw,
        aggressive=True,
        chunk_lines=2,
        pause_sec=0,
        on_progress=None,
    )
    assert "numpy" in result
    assert "Hey welcome everyone today" in result


def test_chunked_parse_preserves_line_breaks():
    raw = "First topic here\nSecond topic there\nThird topic ends"
    result = parse_transcript_chunked(
        raw,
        aggressive=False,
        chunk_lines=10,
        pause_sec=0,
        on_progress=None,
    )
    assert "\n" in result
    assert result.splitlines() == [
        "First topic here",
        "Second topic there",
        "Third topic ends",
    ]


def test_fast_parse_small_file():
    raw = "short line one\nshort line two"
    result = parse_transcript_auto(raw, aggressive=False, thorough=False)
    assert "short" in result


def test_auto_detect_live_captions_without_aggressive_flag():
    raw = "\n".join(
        [
            "Hello everyone",
            "Hello everyone welcome",
            "Hello everyone welcome to numpy",
            "Other line",
            "Hello everyone welcome to numpy arrays",
        ]
        * 30
    )
    result = parse_transcript_auto(raw, aggressive=False, thorough=True, pause_sec=0)
    assert result.count("Hello everyone") < 10
    assert "numpy arrays" in result
