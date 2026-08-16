"""Browser extension allow/block policy (source of truth for SelfTracker)."""

from backend.behavior.browser_gate_policy import (
    DEFAULT_ALLOW_DOMAINS,
    classify_browser_host,
    classify_browser_url,
    extension_should_enforce,
    host_matches_domain,
    resolve_browser_redirect,
    build_browser_gate_section,
)


def test_allowlist_beats_block():
    """Productive hosts never classify as block even if they overlap patterns."""
    # githubusercontent could look weird; github.com itself is allow
    d = classify_browser_host("colab.research.google.com")
    assert d["action"] == "allow"
    assert d["category"] == "allow"

    d2 = classify_browser_host("www.scaler.com")
    assert d2["action"] == "allow"

    assert classify_browser_host("app.scaler.com")["action"] == "allow"
    assert classify_browser_host("classroom.scaler.com")["action"] == "allow"
    assert classify_browser_host("interviewbit.com")["action"] == "allow"

    # Scaler lecture PDFs on S3 attachment buckets
    s3 = "scaler-production-new.s3.ap-southeast-1.amazonaws.com"
    assert classify_browser_host(s3)["action"] == "allow"

    d3 = classify_browser_host("stackoverflow.com")
    assert d3["action"] == "allow"

    d4 = classify_browser_host("localhost")
    assert d4["action"] == "allow"


def test_study_mode_scaler_never_restricted():
    """Regression: Scaler must stay allow under study block_other (no Jarvis restricted)."""
    study = build_browser_gate_section(
        enabled=True, locked=False, morning_next="open", mode="study"
    )
    assert study["mode"] == "study"
    assert study["block_other"] is True
    assert "scaler.com" in study["allow_domains"]
    for url in (
        "https://scaler.com/",
        "https://www.scaler.com/",
        "https://app.scaler.com/academy/mentee/dashboard",
        "https://www.scaler.com/academy/mentee-dashboard/todos",
        "https://www.scaler.com/academy/mentee-dashboard/class/504262/session?joinSession=1",
        "https://www.bing.com/search?q=scaler",
        "https://scaler-production-new.s3.ap-southeast-1.amazonaws.com/attachments/x/Numpy_Postread.pdf",
    ):
        out = classify_browser_url(
            url,
            mode="study",
            enforce=True,
            block_watch_sites=True,
            block_porn=True,
            block_social=True,
            block_keywords=True,
            block_other=True,
            allow_domains=study["allow_domains"],
            watch_domains=study["watch_domains"],
            title="Home | Scaler Academy",
        )
        assert out["action"] == "allow", (url, out)

    # Do not open the whole AWS S3 surface — only scaler-* buckets.
    blocked = classify_browser_url(
        "https://my-bucket.s3.us-east-1.amazonaws.com/secret.pdf",
        mode="study",
        enforce=True,
        block_other=True,
        allow_domains=study["allow_domains"],
        watch_domains=study["watch_domains"],
    )
    assert blocked["action"] == "block"


def test_google_drive_and_gemini_on_allowlist():
    """Drive + Gemini stay allowed in study (block_other) so work isn't bounced."""
    for host in (
        "drive.google.com",
        "docs.google.com",
        "gemini.google.com",
        "aistudio.google.com",
        "accounts.google.com",
    ):
        assert host in DEFAULT_ALLOW_DOMAINS or any(
            host == d or host.endswith("." + d) for d in DEFAULT_ALLOW_DOMAINS
        ), host
        d = classify_browser_host(host)
        assert d["action"] == "allow", host

    study = build_browser_gate_section(
        enabled=True, locked=False, morning_next="open", mode="study"
    )
    for url in (
        "https://drive.google.com/drive/my-drive",
        "https://gemini.google.com/app",
        "https://aistudio.google.com/",
        "https://accounts.google.com/signin",
    ):
        out = classify_browser_url(
            url,
            mode="study",
            enforce=True,
            block_watch_sites=True,
            block_porn=True,
            block_social=True,
            block_keywords=True,
            block_other=True,
            allow_domains=study["allow_domains"],
        )
        assert out["action"] == "allow", url


def test_data_science_ai_sites_allowlisted_in_study():
    """NumPy/Pandas/DS/AI learning hosts stay allow under study block_other."""
    ds_hosts = (
        "numpy.org",
        "pandas.pydata.org",
        "scipy.org",
        "scikit-learn.org",
        "matplotlib.org",
        "seaborn.pydata.org",
        "plotly.com",
        "pytorch.org",
        "tensorflow.org",
        "keras.io",
        "huggingface.co",
        "jax.dev",
        "readthedocs.io",
        "polars.tech",
        "docs.python.org",
        "realpython.com",
        "pydata.org",
        "kaggle.com",
        "datacamp.com",
        "towardsdatascience.com",
        "medium.com",
        "fast.ai",
        "course.fast.ai",
        "deeplearning.ai",
        "paperswithcode.com",
        "distill.pub",
        "ocw.mit.edu",
        "cs231n.stanford.edu",
        "statisticsbyjim.com",
        "paperspace.com",
        "gradient.paperspace.com",
        "deepnote.com",
        "databricks.com",
        "stats.stackexchange.com",
        "datascience.stackexchange.com",
    )
    for host in ds_hosts:
        assert host in DEFAULT_ALLOW_DOMAINS or any(
            host == d or host.endswith("." + d) for d in DEFAULT_ALLOW_DOMAINS
        ), host
        assert classify_browser_host(host)["action"] == "allow", host

    study = build_browser_gate_section(
        enabled=True, locked=False, morning_next="open", mode="study"
    )
    for url in (
        "https://numpy.org/doc/stable/",
        "https://pandas.pydata.org/docs/",
        "https://scikit-learn.org/stable/",
        "https://www.kaggle.com/learn",
        "https://huggingface.co/docs",
        "https://pytorch.org/tutorials/",
        "https://colab.research.google.com/",
        "https://jax.readthedocs.io/en/latest/",
        "https://stats.stackexchange.com/questions/1",
    ):
        out = classify_browser_url(
            url,
            mode="study",
            enforce=True,
            block_watch_sites=True,
            block_porn=True,
            block_social=True,
            block_keywords=True,
            block_other=True,
            allow_domains=study["allow_domains"],
        )
        assert out["action"] == "allow", (url, out)

    # Entertainment still blocked
    for bad in (
        "https://www.youtube.com/watch?v=1",
        "https://www.reddit.com/r/MachineLearning/",
        "https://twitter.com/home",
    ):
        out = classify_browser_url(
            bad,
            mode="study",
            enforce=True,
            block_watch_sites=True,
            block_porn=True,
            block_social=True,
            block_keywords=True,
            block_other=True,
            allow_domains=study["allow_domains"],
            watch_domains=study["watch_domains"],
            social_domains=study["social_domains"],
        )
        assert out["action"] == "block", (bad, out)

def test_porn_blocked_under_armed_policy():
    d = classify_browser_host("pornhub.com")
    assert d["action"] == "block"
    assert d["category"] == "porn"

    d2 = classify_browser_host("xxx.example-adult.com")  # suffix pattern
    # only known suffixes — unknown adult-ish host without suffix → other
    assert d2["category"] in ("porn", "other")

    d3 = classify_browser_host("xvideos.com")
    assert d3["action"] == "block"
    assert d3["category"] == "porn"


def test_watch_sites_blocked():
    for host in (
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "youtu.be",
        "netflix.com",
        "www.netflix.com",
        "primevideo.com",
        "hotstar.com",
        "disneyplus.com",
        "twitch.tv",
    ):
        d = classify_browser_host(host)
        assert d["action"] == "block", host
        assert d["category"] == "watch", host


def test_host_matches_domain_suffix():
    assert host_matches_domain("docs.google.com", "docs.google.com")
    assert host_matches_domain("colab.research.google.com", "colab.research.google.com")
    assert host_matches_domain("mail.scaler.com", "scaler.com")
    assert not host_matches_domain("notyoutube.com", "youtube.com")
    assert host_matches_domain("www.youtube.com", "youtube.com")


def test_extension_enforce_when_armed_or_morning_locked():
    assert extension_should_enforce(enabled=True, locked=True, morning_next="open")
    assert extension_should_enforce(enabled=True, locked=False, morning_next="open")
    assert extension_should_enforce(enabled=False, locked=False, morning_next="bible")
    assert extension_should_enforce(enabled=False, locked=False, morning_next="plan")
    assert not extension_should_enforce(enabled=False, locked=False, morning_next="open")
    # Day modes always enforce (free = porn/keywords only)
    assert extension_should_enforce(enabled=False, locked=False, morning_next="open", mode="free")
    assert extension_should_enforce(enabled=False, locked=False, morning_next="open", mode="study")


def test_morning_bible_redirect_preferred():
    r = resolve_browser_redirect(morning_next="bible", locked=True, enabled=True)
    assert r["redirect_url"].endswith("/bible")
    assert r["redirect_reason"] == "morning_bible"

    r2 = resolve_browser_redirect(morning_next="plan", locked=False, enabled=False)
    assert r2["redirect_url"] and "productivity" in r2["redirect_url"]
    assert "tab=plan" in r2["redirect_url"]
    assert r2["redirect_reason"] == "morning_plan"

    r3 = resolve_browser_redirect(morning_next="open", locked=True, enabled=True)
    assert r3["redirect_reason"] == "armed_distraction"
    assert "bible" not in (r3["redirect_url"] or "")


def test_classify_url_allowlist_over_watch_overlap():
    # colab is allow even under enforce
    out = classify_browser_url(
        "https://colab.research.google.com/drive/abc",
        enforce=True,
        block_watch_sites=True,
        block_porn=True,
    )
    assert out["action"] == "allow"

    out2 = classify_browser_url(
        "https://www.youtube.com/watch?v=1",
        enforce=True,
        block_watch_sites=True,
        block_porn=True,
    )
    assert out2["action"] == "block"
    assert out2["category"] == "watch"

    out3 = classify_browser_url(
        "https://www.youtube.com/watch?v=1",
        enforce=True,
        block_watch_sites=False,
        block_porn=True,
    )
    assert out3["action"] == "none"

    out4 = classify_browser_url(
        "https://pornhub.com/",
        enforce=True,
        block_watch_sites=False,
        block_porn=True,
    )
    assert out4["action"] == "block"


def test_build_browser_gate_section_morning_bible():
    section = build_browser_gate_section(
        enabled=False,
        locked=False,
        morning_next="bible",
    )
    assert section["mode"] == "bible"
    assert section["enforce"] is True
    assert section["block_porn"] is True
    assert section["block_watch_sites"] is True
    assert section["block_other"] is True
    assert section["strict_allowlist"] is True
    assert section["morning_next"] == "bible"
    assert section["bible_url"].endswith("/bible")
    assert section["redirect_url"].endswith("/bible")
    assert "localhost" in section["allow_domains"]
    assert "youtube.com" in section["watch_domains"]
    assert any("porn" in s or s.endswith("hub.com") or "xvideos" in s for s in section["porn_domains"])
    assert DEFAULT_ALLOW_DOMAINS  # sanity


def test_build_browser_gate_section_open_disarmed():
    """Day open after plan → study by default (YouTube blocked); porn still on in free."""
    from datetime import datetime, timezone

    day = datetime(2026, 8, 5, 14, 0, tzinfo=timezone.utc)
    section = build_browser_gate_section(
        enabled=False,
        locked=False,
        morning_next="open",
        now=day,
        free_override_active=False,
        free_after_hm="21:00",
    )
    assert section["mode"] == "study"
    assert section["enforce"] is True
    assert section["block_watch_sites"] is True
    assert section["block_social"] is True
    assert section["block_porn"] is True
    assert section["block_keywords"] is True
    assert section["block_other"] is True
    assert section["redirect_url"] is None
    assert section["daytime_default"] == "study"

    free = build_browser_gate_section(
        enabled=False,
        locked=False,
        morning_next="open",
        mode="free",
    )
    assert free["mode"] == "free"
    assert free["block_porn"] is True
    assert free["block_watch_sites"] is False
    assert free["block_other"] is False


def test_compute_gate_includes_browser_section(monkeypatch, tmp_path):
    from backend.behavior import distraction_gate as mod
    from backend.planner import morning_rewards as mr

    monkeypatch.setattr(mr, "_STORE", tmp_path / "morning_rewards.json")

    class FakeQuery:
        def filter(self, *a, **k):
            return self

        def all(self):
            return []

    class FakeDb:
        def query(self, *a, **k):
            return FakeQuery()

    monkeypatch.setattr(
        "backend.behavior.productivity_policy.load_policy_dict",
        lambda db, uid: {
            "hard_block_enabled": True,
            "daily_goal_minutes": 100,
            "threshold": 60,
            "hard_block_gaming": True,
            "hard_block_exes": [],
            "productive_categories": [],
            "blocked_categories": [],
            "app_overrides": {},
        },
    )
    monkeypatch.setattr("backend.behavior.category_scores.load_score_map", lambda db: {})
    monkeypatch.setattr(
        "backend.behavior.productivity_policy.resolve_session_score",
        lambda sess, scores, policy: 0,
    )
    monkeypatch.setenv("MORNING_GATE", "1")
    monkeypatch.setattr(
        "backend.bible.store.summary",
        lambda uid: {
            "bible_minutes": 0,
            "game_bank_remaining_seconds": 0,
            "game_bank_remaining_minutes": 0,
            "day_pass": False,
            "chapter_goal": {"met": False, "target": 1, "completed": 0},
            "chapters_completed_today": [],
            "day_pass_status": {},
        },
    )
    monkeypatch.setattr(
        "backend.planner.morning_plan.count_blocks_today",
        lambda db, uid, day=None: 0,
    )
    monkeypatch.setattr(
        "backend.planner.morning_plan.is_plan_confirmed",
        lambda uid, day=None: False,
    )
    monkeypatch.setattr(
        "backend.behavior.tracker_plan.fetch_plan_context",
        lambda uid, now=None, db=None: type(
            "PC", (), {"current": None, "next": None}
        )(),
    )

    out = mod.compute_distraction_gate(FakeDb(), 1)
    assert out["morning"]["next"] == "bible"
    assert out["browser_mode"] == "bible"
    assert "browser" in out
    assert out["browser"]["mode"] == "bible"
    assert out["browser"]["enforce"] is True
    assert out["browser"]["redirect_url"].endswith("/bible")
    assert out["morning"]["bible_url"].endswith("/bible")
    assert "localhost" in out["browser"]["allow_domains"]


def test_js_gate_policy_consumes_mode():
    from pathlib import Path
    import json

    text = Path("selftracker-extension/gate_policy.js").read_text(encoding="utf-8")
    assert "block_other" in text
    assert "strict_allowlist" in text
    assert "browser.mode" in text or "b.mode" in text
    assert "FORCE_WATCH_HOSTS" in text
    assert "isForceWatchHost" in text
    assert "degraded" in text
    man = json.loads(
        Path("selftracker-extension/manifest.json").read_text(encoding="utf-8")
    )
    parts = [int(x) for x in str(man["version"]).split(".")]
    assert parts >= [1, 5, 16]