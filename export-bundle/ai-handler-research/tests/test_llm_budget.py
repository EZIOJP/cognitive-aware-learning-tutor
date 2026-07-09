"""Tests for heavy-tier LLM budget guard."""

from pathlib import Path

import pytest

from backend.core import llm_budget
from backend.core.llm_budget import heavy_budget_allows, heavy_budget_status, record_heavy_cloud_call


@pytest.fixture(autouse=True)
def _isolate_usage_dir(tmp_path, monkeypatch):
    usage_dir = tmp_path / "llm_usage"
    usage_dir.mkdir()
    monkeypatch.setattr(llm_budget, "LLM_USAGE_DIR", usage_dir)
    monkeypatch.setattr(
        llm_budget,
        "_usage_path",
        lambda day=None: usage_dir / f"{(day or __import__('datetime').date.today()).isoformat()}.json",
    )


def test_budget_increment_and_status(monkeypatch):
    monkeypatch.setattr(
        "backend.core.llm_budget.get_settings",
        lambda: type("S", (), {"llm_heavy_daily_soft_cap": 50})(),
    )
    assert heavy_budget_status()["used"] == 0
    record_heavy_cloud_call()
    record_heavy_cloud_call()
    status = heavy_budget_status()
    assert status["used"] == 2
    assert status["cap"] == 50
    assert status["exceeded"] is False


def test_budget_soft_cap_blocks_without_confirm(monkeypatch):
    monkeypatch.setattr(
        "backend.core.llm_budget.get_settings",
        lambda: type("S", (), {"llm_heavy_daily_soft_cap": 2})(),
    )
    record_heavy_cloud_call()
    record_heavy_cloud_call()
    assert heavy_budget_allows(confirm=False) is False
    assert heavy_budget_allows(confirm=True) is True


def test_budget_disabled_when_cap_zero(monkeypatch):
    monkeypatch.setattr(
        "backend.core.llm_budget.get_settings",
        lambda: type("S", (), {"llm_heavy_daily_soft_cap": 0})(),
    )
    for _ in range(5):
        record_heavy_cloud_call()
    assert heavy_budget_allows(confirm=False) is True
