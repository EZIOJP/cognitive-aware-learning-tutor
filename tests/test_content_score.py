from backend.behavior.content_score import (
    CONTENT_SCORE_WEIGHTS,
    decide_content_action,
    score_haystack,
)


def test_score_clusters_beat_single_repeat():
    score_repeat, _ = score_haystack("porn porn porn porn porn")
    score_cluster, terms = score_haystack("porn blowjob cumshot gangbang")
    assert score_cluster > score_repeat
    assert len(terms) >= 3


def test_stop_when_low_and_flat():
    assert (
        decide_content_action(
            score=0, prev_score=0, sample_index=1, warned=False, mode="free"
        )
        == "stop"
    )


def test_warn_then_lock_when_rising_study():
    assert (
        decide_content_action(
            score=6, prev_score=0, sample_index=0, warned=False, mode="study"
        )
        == "warn"
    )
    assert (
        decide_content_action(
            score=9, prev_score=6, sample_index=1, warned=True, mode="study"
        )
        == "lock"
    )


def test_immediate_lock_above_threshold():
    assert (
        decide_content_action(
            score=20, prev_score=0, sample_index=0, warned=False, mode="free"
        )
        == "lock"
    )


def test_js_weight_keys_covered_in_python():
    for k in ("porn", "blowjob", "live sex", "erome"):
        assert k in CONTENT_SCORE_WEIGHTS
