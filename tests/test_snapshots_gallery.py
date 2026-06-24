from backend.transcripts.snapshots import append_snapshot_gallery


def test_append_snapshot_gallery_adds_missing(tmp_path, monkeypatch):
    from backend.transcripts import snapshots as mod

    stem = "live_captions_test"
    snap_dir = tmp_path / stem
    snap_dir.mkdir()
    (snap_dir / "1.png").write_bytes(b"fake")
    monkeypatch.setattr(mod, "SNAPSHOTS_DIR", tmp_path)
    monkeypatch.setattr(mod, "snapshot_dir_for_transcript", lambda _: snap_dir)

    body = "# Notes\n\nSome content."
    out = append_snapshot_gallery(body, stem)
    assert "## Slide captures" in out
    assert f"/api/transcripts/snapshots/{stem}/1.png" in out
