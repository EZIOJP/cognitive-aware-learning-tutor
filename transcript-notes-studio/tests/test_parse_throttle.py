"""Tests for parse speed slider mapping and estimates."""

from transcript_studio.parse_throttle import (
    estimate_cpu_load_pct,
    estimate_parse_seconds,
    format_parse_estimate,
    speed_to_throttle,
    throttle_labels,
)


def test_speed_to_throttle_bounds():
    fast = speed_to_throttle(0)
    slow = speed_to_throttle(100)
    assert fast.chunk_lines > slow.chunk_lines
    assert fast.pause_ms < slow.pause_ms
    assert fast.chunk_lines >= 80


def test_slower_speed_increases_eta():
    lines = 4000
    fast = estimate_parse_seconds(lines, 0, thorough=True)
    cool = estimate_parse_seconds(lines, 65, thorough=True)
    assert cool > fast


def test_thorough_off_is_faster_estimate():
    lines = 2000
    quick = estimate_parse_seconds(lines, 50, thorough=False)
    thorough = estimate_parse_seconds(lines, 50, thorough=True)
    assert thorough > quick


def test_cpu_load_decreases_with_speed():
    assert estimate_cpu_load_pct(90, thorough=True) < estimate_cpu_load_pct(10, thorough=True)


def test_format_parse_estimate_includes_eta_and_chunk():
    text = format_parse_estimate(1200, 65, thorough=True, aggressive=False, temp_c=52.0)
    assert "Est." in text
    assert "chunk" in text
    assert "52°C" in text


def test_throttle_labels():
    assert throttle_labels(10)[0] == "Fast"
    assert throttle_labels(60)[0] == "Cool"
