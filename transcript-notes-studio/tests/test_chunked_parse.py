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


def test_fast_parse_small_file():
    raw = "short line one\nshort line two"
    result = parse_transcript_auto(raw, aggressive=False, thorough=False)
    assert "short" in result
