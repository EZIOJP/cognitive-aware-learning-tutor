"""Phase 2 SoftLand policy store — writers, migrator, incubation mirror."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.behavior.softland_policy import (
    default_softland_policy,
    load_softland_policy,
    migrate_from_legacy,
    patch_softland_policy,
    save_softland_policy,
    softland_enabled_from_policy,
)


def test_defaults_and_save_load(tmp_path, monkeypatch):
    path = tmp_path / "softland_policy.json"
    monkeypatch.setattr("backend.behavior.softland_policy._PATH", path)
    monkeypatch.setattr("backend.behavior.softland_policy._LEGACY_SITE", tmp_path / "site.json")
    monkeypatch.setattr("backend.behavior.softland_policy._LEGACY_SCHEDULES", tmp_path / "sched.json")

    d = default_softland_policy()
    assert d["schema_version"] == 1
    assert d["softland_enabled"] is False

    saved = save_softland_policy({
        **d,
        "softland_enabled": True,
        "site_rules": {"allow_extra": ["Example.COM"], "watch_extra": [], "block_extra": []},
    })
    assert path.is_file()
    assert saved["softland_enabled"] is True
    assert saved["site_rules"]["allow_extra"] == ["example.com"]
    assert "hard_block_armed" not in saved

    loaded = load_softland_policy(migrate_if_missing=False)
    assert loaded["softland_enabled"] is True
    assert softland_enabled_from_policy() is True


def test_migrate_from_legacy_files(tmp_path, monkeypatch):
    policy_path = tmp_path / "softland_policy.json"
    site = tmp_path / "softland_site_rules.json"
    sched = tmp_path / "gate_schedules.json"
    monkeypatch.setattr("backend.behavior.softland_policy._PATH", policy_path)
    monkeypatch.setattr("backend.behavior.softland_policy._LEGACY_SITE", site)
    monkeypatch.setattr("backend.behavior.softland_policy._LEGACY_SCHEDULES", sched)
    monkeypatch.setattr(
        "backend.behavior.softland_policy._read_softland_enabled_from_sqlite",
        lambda: True,
    )

    site.write_text(
        '{"allow_extra":["foo.org"],"watch_extra":["reddit.com"],"block_extra":[]}\n',
        encoding="utf-8",
    )
    sched.write_text(
        '{"enabled":true,"windows":[{"id":"w1","label":"Focus","days":[0],"start":"09:00","end":"12:00","mode":"study"}]}\n',
        encoding="utf-8",
    )

    data = migrate_from_legacy(force=True)
    assert policy_path.is_file()
    assert data["softland_enabled"] is True
    assert data["site_rules"]["allow_extra"] == ["foo.org"]
    assert data["schedules"]["enabled"] is True
    assert data["schedules"]["windows"][0]["id"] == "w1"


def test_site_rules_save_writes_sot(tmp_path, monkeypatch):
    policy_path = tmp_path / "softland_policy.json"
    monkeypatch.setattr("backend.behavior.softland_policy._PATH", policy_path)
    monkeypatch.setattr("backend.behavior.softland_policy._LEGACY_SITE", tmp_path / "site.json")
    monkeypatch.setattr("backend.behavior.softland_policy._LEGACY_SCHEDULES", tmp_path / "sched.json")

    from backend.behavior.softland_site_rules import load_site_rules, merge_allow, save_site_rules

    save_site_rules({"allow_extra": ["Bar.COM"], "watch_extra": [], "block_extra": ["tiktok.com"]})
    assert load_site_rules()["allow_extra"] == ["bar.com"]
    assert merge_allow(["a.com"]) == ["a.com", "bar.com"]
    raw = policy_path.read_text(encoding="utf-8")
    assert "bar.com" in raw
    assert "tiktok.com" in raw


def test_incubation_mirror_does_not_arm(tmp_path, monkeypatch):
    policy_path = tmp_path / "softland_policy.json"
    enf = tmp_path / "enforcer_policy.json"
    monkeypatch.setattr("backend.behavior.softland_policy._PATH", policy_path)
    monkeypatch.setattr("backend.behavior.softland_policy._LEGACY_SITE", tmp_path / "site.json")
    monkeypatch.setattr("backend.behavior.softland_policy._LEGACY_SCHEDULES", tmp_path / "sched.json")
    monkeypatch.setattr("backend.behavior.enforcer_files.POLICY_PATH", enf)
    monkeypatch.setattr("backend.behavior.enforcer_files.BEHAVIOR_DIR", tmp_path)

    enf.write_text(
        '{"hard_block_armed":false,"gate_locked":false,"incubation_active":false,'
        '"exes":["steam.exe"],"lock_mode":"none","lock_until_unix":0,'
        '"unlock_password":"","unlock_phrase":"","anti_tamper":true,"note":""}\n',
        encoding="utf-8",
    )

    until = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    save_softland_policy({
        **default_softland_policy(),
        "runtime": {**default_softland_policy()["runtime"], "incubation_until": until},
    })

    import json

    mirrored = json.loads(enf.read_text(encoding="utf-8"))
    assert mirrored["incubation_active"] is True
    assert mirrored["hard_block_armed"] is False


def test_patch_runtime(tmp_path, monkeypatch):
    path = tmp_path / "softland_policy.json"
    monkeypatch.setattr("backend.behavior.softland_policy._PATH", path)
    monkeypatch.setattr("backend.behavior.softland_policy._LEGACY_SITE", tmp_path / "site.json")
    monkeypatch.setattr("backend.behavior.softland_policy._LEGACY_SCHEDULES", tmp_path / "sched.json")
    save_softland_policy(default_softland_policy())
    out = patch_softland_policy({"softland_enabled": True, "goals": {"bible_done": True}})
    assert out["softland_enabled"] is True
    assert out["goals"]["bible_done"] is True
