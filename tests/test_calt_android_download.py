"""Tests for CALT Android APK distribution endpoints."""

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_calt_android_latest_when_apk_present():
    res = client.get("/api/app/calt-android/latest")
    assert res.status_code == 200
    data = res.json()
    assert data["app_id"] == "calt-android"
    assert data["package"] == "com.calt.timetable"
    assert data["version_code"] >= 1
    assert data["size_bytes"] > 0
    assert data["download_url"].endswith("/api/app/calt-android/download")


def test_calt_android_download_serves_apk():
    res = client.get("/api/app/calt-android/download")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("application/vnd.android.package-archive")
    assert len(res.content) > 1_000_000
