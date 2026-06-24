from backend.behavior.coach_activity import _infer_intent, _normalize_event


def test_normalize_youtube_event():
    raw = {
        "type": "BEHAVIORAL_UPDATE",
        "domain": "music.youtube.com",
        "page_title": "Koyila | YouTube Music",
        "site": "youtube",
        "video_title": "Koyila | YouTube Music",
        "video_watched_percent": 38,
        "channel_name": "An Artist",
    }
    entry = _normalize_event(raw)
    assert entry is not None
    assert entry["site"] == "youtube"
    assert entry["video_title"] == "Koyila | YouTube Music"
    assert entry["channel"] == "An Artist"


def test_infer_study_video_from_title():
    entry = {"domain": "youtube.com", "site": "youtube", "video_title": "Python data analysis tutorial"}
    assert _infer_intent(entry) == "study_video"


def test_skips_new_tab():
    assert _normalize_event({"domain": "newtab", "title": "New tab"}) is None
