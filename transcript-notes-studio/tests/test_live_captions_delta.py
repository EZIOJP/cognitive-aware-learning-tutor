from transcript_studio.live_captions import extract_caption_delta


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
