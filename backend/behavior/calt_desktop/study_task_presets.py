"""Study task presets and block templates for Plan goals."""

from __future__ import annotations

import uuid
from typing import Any


def scaler_study_task(*, minutes: int = 90) -> dict[str, Any]:
    return {
        "id": "scaler-deep-work",
        "title": "Scaler / coursework",
        "minutes": int(minutes),
        "allowHosts": [
            "scaler.com",
            "scaleracademy.com",
            "colab.research.google.com",
            "github.com",
            "stackoverflow.com",
        ],
        "blockCategories": [
            "Gaming",
            "Video Streaming",
            "Social Media",
            "Entertainment",
            "Live Streaming",
        ],
    }


def deep_read_task(*, minutes: int = 90) -> dict[str, Any]:
    return {
        "id": f"deep-read-{uuid.uuid4().hex[:6]}",
        "title": "Deep read (notes + PDF)",
        "minutes": int(minutes),
        "allowHosts": [
            "localhost",
            "127.0.0.1",
            "notion.so",
            "drive.google.com",
            "arxiv.org",
        ],
        "blockCategories": ["Gaming", "Video Streaming", "Social Media", "Entertainment"],
    }


def daily_review_task(*, minutes: int = 35) -> dict[str, Any]:
    return {
        "id": "daily-srs-review",
        "title": "Daily review (vocab + math + notes)",
        "minutes": int(minutes),
        "allowHosts": ["localhost", "127.0.0.1"],
        "blockCategories": [
            "Gaming",
            "Video Streaming",
            "Social Media",
            "Entertainment",
            "Live Streaming",
        ],
    }


def gre_cycle_task(*, minutes: int = 45) -> dict[str, Any]:
    return {
        "id": f"gre-{uuid.uuid4().hex[:6]}",
        "title": "GRE vocab — Review Hub due queue",
        "minutes": int(minutes),
        "allowHosts": ["localhost", "127.0.0.1"],
        "blockCategories": ["Gaming", "Video Streaming", "Social Media", "Entertainment"],
    }


def admin_task(*, minutes: int = 30) -> dict[str, Any]:
    return {
        "id": f"admin-{uuid.uuid4().hex[:6]}",
        "title": "Admin / email",
        "minutes": int(minutes),
        "allowHosts": [
            "mail.google.com",
            "calendar.google.com",
            "outlook.com",
        ],
        "blockCategories": ["Gaming", "Video Streaming"],
    }


BLOCK_TEMPLATES: list[tuple[str, str, Any]] = [
    ("Daily SRS", "Review Hub — vocab + math + notes due queue", daily_review_task),
    ("Scaler block", "Coursework — Scaler + docs only", scaler_study_task),
    ("Deep read", "Notes + PDF — 90m", deep_read_task),
    ("GRE / vocab", "Review Hub due queue — 45m", gre_cycle_task),
    ("Admin", "Email + calendar — gate relaxed", admin_task),
]
