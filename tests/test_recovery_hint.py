"""Tests for recovery capacity hint."""

from __future__ import annotations

from backend.behavior.recovery_hint import compute_recovery_hint


def test_full_capacity_high_score():
    hint = compute_recovery_hint(sleep_score=90, base_focus_hours=4.0)
    assert hint["factor"] == 1.0
    assert hint["suggested_focus_hours"] == 4.0
    assert "Full" in hint["label"]


def test_low_recovery():
    hint = compute_recovery_hint(sleep_score=40, base_focus_hours=4.0)
    assert hint["factor"] == 0.6
    assert hint["suggested_focus_hours"] == 2.4


def test_short_sleep_without_score():
    hint = compute_recovery_hint(sleep_hours=5.0, base_focus_hours=4.0)
    assert hint["factor"] == 0.7
    assert hint["suggested_focus_hours"] == 2.8


def test_no_data_defaults():
    hint = compute_recovery_hint(base_focus_hours=4.0)
    assert hint["factor"] == 1.0
    assert hint["suggested_focus_hours"] == 4.0
