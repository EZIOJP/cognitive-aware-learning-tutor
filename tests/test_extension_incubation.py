"""Extension gate_policy must honor incubation (never free during break)."""

from pathlib import Path


def _assert_incubation_helpers(text: str, path: str) -> None:
    assert "function isIncubationActive" in text, path
    assert "if (isIncubationActive(gateCache)) return false" in text, path
    assert "Boolean(isIncubationActive(gateCache))" in text, path


def test_calt_gate_policy_has_incubation():
    path = Path("calt-gate-extension/gate_policy.js")
    text = path.read_text(encoding="utf-8")
    _assert_incubation_helpers(text, str(path))


def test_selftracker_gate_policy_has_incubation():
    path = Path("selftracker-extension/gate_policy.js")
    text = path.read_text(encoding="utf-8")
    _assert_incubation_helpers(text, str(path))


def test_browser_section_exposes_incubation_active_key():
    """Source contract: build_browser_gate_section sets incubation_active."""
    text = Path("backend/behavior/browser_gate_policy.py").read_text(encoding="utf-8")
    assert '"incubation_active": incubating' in text
