"""Windows-robust atomic_write_text retries."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from backend.quiz import atomic_io


def test_atomic_write_retries_permission_error_then_succeeds(tmp_path: Path):
    target = tmp_path / "flags.json"
    calls = {"n": 0}
    real_replace = atomic_io.os.replace

    def flaky_replace(src, dst):
        calls["n"] += 1
        if calls["n"] < 3:
            raise PermissionError(5, "Access is denied")
        return real_replace(src, dst)

    with patch.object(atomic_io.os, "replace", side_effect=flaky_replace):
        with patch("time.sleep"):
            atomic_io.atomic_write_text(target, '{"ok": true}\n')

    assert calls["n"] == 3
    assert target.read_text(encoding="utf-8") == '{"ok": true}\n'
    assert not target.with_suffix(target.suffix + ".tmp").exists()


def test_atomic_write_raises_after_retries_exhausted(tmp_path: Path):
    target = tmp_path / "flags.json"

    def always_fail(src, dst):
        raise PermissionError(5, "Access is denied")

    with patch.object(atomic_io.os, "replace", side_effect=always_fail):
        with patch("time.sleep"):
            with pytest.raises(PermissionError):
                atomic_io.atomic_write_text(target, "x\n")
