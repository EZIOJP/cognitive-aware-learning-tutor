from transcript_studio.live_captions import LiveCaptionsScraper, extract_caption_delta


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


class _FakeBlock:
    def __init__(self, texts: list[str]):
        self._texts = list(texts)
        self._i = 0

    def window_text(self) -> str:
        if self._i < len(self._texts):
            text = self._texts[self._i]
            self._i += 1
            return text
        return self._texts[-1] if self._texts else ""


def test_seed_baseline_does_not_record_existing_buffer():
    """Starting mid-lecture must not dump the whole Live Captions panel."""
    scraper = LiveCaptionsScraper(poll_interval=0.01)
    block = _FakeBlock(
        [
            "Old buffer line one.\nOld buffer line two.",
            "Old buffer line one.\nOld buffer line two.",
            "Old buffer line one.\nOld buffer line two.\nBrand new speech.",
        ]
    )
    seeded = scraper.seed_baseline(block)
    assert "Old buffer" in seeded
    assert scraper.segments == []

    assert scraper.poll_once(block) is False  # unchanged after seed read advance
    assert scraper.segments == []

    # Force next poll to see growth: reset fake to serve growth text
    block._texts = ["Old buffer line one.\nOld buffer line two.\nBrand new speech."]
    block._i = 0
    scraper._last_block = "Old buffer line one.\nOld buffer line two."
    scraper._seeded = True
    assert scraper.poll_once(block) is True
    assert scraper.segments == ["Brand new speech."]
    assert "Old buffer" not in "\n".join(scraper.segments)


def test_poll_once_auto_seeds_before_recording():
    scraper = LiveCaptionsScraper()
    block = _FakeBlock(["Already on screen", "Already on screen more words"])
    assert scraper.poll_once(block) is False
    assert scraper.segments == []
    assert scraper._seeded is True
    assert scraper.poll_once(block) is True
    assert scraper.segments == ["more words"]
