"""Unit tests for locked-screen suggested links helper."""

from __future__ import annotations

from backend.behavior.locked_screen import (
    _dedupe_links,
    _links_from_allow_domains,
    _links_from_plan,
    build_locked_screen_extras,
)


def test_dedupe_links_keeps_order_and_limit():
    raw = [
        {"title": "A", "url": "https://a.com/", "source": "x"},
        {"title": "A2", "url": "https://a.com", "source": "x"},
        {"title": "B", "url": "https://b.com/", "source": "y"},
    ]
    out = _dedupe_links(raw, limit=2)
    assert len(out) == 2
    assert out[0]["url"] == "https://a.com/"
    assert out[1]["url"] == "https://b.com/"


def test_links_from_plan_maps_scaler_title():
    links = _links_from_plan("Scaler numpy lecture", "study", {"scaler.com", "github.com"})
    assert any("scaler.com" in (x["url"] or "") for x in links)
    assert all(x["source"] == "goal" for x in links)


def test_links_from_allow_priority_subset():
    links = _links_from_allow_domains(["scaler.com", "github.com", "example.com"])
    hosts = " ".join(x["url"] for x in links)
    assert "scaler.com" in hosts
    assert "github.com" in hosts
    assert "example.com" not in hosts  # not in priority list


def test_build_locked_screen_extras_calt_fallbacks(monkeypatch):
    class FakeQ:
        def filter(self, *a, **k):
            return self

        def order_by(self, *a, **k):
            return self

        def limit(self, *a, **k):
            return self

        def all(self):
            return []

    class FakeDb:
        def query(self, *a, **k):
            return FakeQ()

    out = build_locked_screen_extras(
        FakeDb(),
        1,
        bible_url="http://localhost:5173/bible",
        plan_url="http://localhost:5173/productivity?tab=plan",
        allow_domains=["scaler.com", "github.com"],
        planner_title="Colab practice",
        planner_category="study",
        planner_minutes_left=25,
        morning_next="open",
    )
    urls = [x["url"] for x in out["suggested_links"]]
    assert "http://localhost:5173/bible" in urls
    assert any("/lecture-notes" in u for u in urls)
    assert any("colab.research.google.com" in u for u in urls)
    assert out["current_block"]["title"] == "Colab practice"
    assert out["current_block"]["minutes_left"] == 25
