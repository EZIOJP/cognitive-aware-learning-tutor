from backend.transcripts.live_captions import extract_caption_delta


def test_extract_delta_growing_text():
    assert extract_caption_delta("Hello", "Hello world") == "world"


def test_extract_delta_new_sentence():
    assert extract_caption_delta("First sentence.", "Second sentence.") == "Second sentence."


def test_extract_delta_unchanged():
    assert extract_caption_delta("Same text", "Same text") is None


def test_extract_delta_empty():
    assert extract_caption_delta("", "") is None
    assert extract_caption_delta("prev", "") is None


def test_panel_scroll_one_new_line():
    prev = "Line one.\nLine two."
    curr = "Line two.\nLine three."
    assert extract_caption_delta(prev, curr) == "Line three."


def test_panel_scroll_full_rotation():
    prev = "The instructor explains arrays.\nWe will cover reversal."
    curr = "We will cover reversal.\nFirst, pick two pointers."
    assert extract_caption_delta(prev, curr) == "First, pick two pointers."


def test_growing_last_line_on_scroll():
    prev = "Hello"
    curr = "Hello everyone.\nWelcome to class."
    result = extract_caption_delta(prev, curr)
    assert result is not None
    assert "Welcome to class" in result


def test_no_duplicate_on_repeated_panel():
    prev = "Same line.\nAnother line."
    curr = "Same line.\nAnother line."
    assert extract_caption_delta(prev, curr) is None
