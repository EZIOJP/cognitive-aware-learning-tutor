"""User-defined features and custom metrics."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from backend.hub.services.catalog import SYSTEM_FEATURE_CATALOG, catalog_for_ui
from backend.models import ReadingDefinition, UserFeature, UserPlugin

_SLUG_RE = re.compile(r"^[a-z][a-z0-9_]{1,48}$")


def _user_metric_slug(user_id: int, slug: str) -> str:
    clean = slug.strip().lower().replace("-", "_")
    return f"u{user_id}_{clean}"


def _feature_id_from_slug(user_id: int, slug: str) -> str:
    clean = slug.strip().lower().replace(" ", "-").replace("_", "-")
    return f"custom-{user_id}-{clean}"[:80]


def ensure_user_plugins_seeded(db: Session, user_id: int) -> None:
    from backend.hub.services.seed import seed_user_plugins

    seed_user_plugins(db, user_id)


def list_user_plugin_state(db: Session, user_id: int) -> list[dict]:
    ensure_user_plugins_seeded(db, user_id)
    rows = db.query(UserPlugin).filter(UserPlugin.user_id == user_id).all()
    by_id = {r.plugin_id: r for r in rows}
    out = []
    for entry in catalog_for_ui():
        pid = entry["plugin_id"]
        row = by_id.get(pid)
        out.append(
            {
                "plugin_id": pid,
                "enabled": row.enabled if row else entry["default_enabled"],
                "config": json.loads(row.config_json or "{}") if row else {},
                "kind": entry["kind"],
                "is_core": entry["is_core"],
            }
        )
    return out


def set_user_plugin(
    db: Session, user_id: int, plugin_id: str, enabled: bool, config: dict | None = None
) -> dict:
    entry = next((e for e in SYSTEM_FEATURE_CATALOG if e["plugin_id"] == plugin_id), None)
    if entry and entry.get("is_core") and not enabled:
        raise ValueError("Core features cannot be disabled")
    row = (
        db.query(UserPlugin)
        .filter(UserPlugin.user_id == user_id, UserPlugin.plugin_id == plugin_id)
        .first()
    )
    if not row:
        row = UserPlugin(user_id=user_id, plugin_id=plugin_id, enabled=enabled)
        db.add(row)
    else:
        row.enabled = enabled
    if config is not None:
        row.config_json = json.dumps(config)
    db.commit()
    return {"plugin_id": row.plugin_id, "enabled": row.enabled}


def list_metrics_for_user(db: Session, user_id: int) -> list[dict]:
    """System metrics for enabled coded plugins + all user custom metrics."""
    ensure_user_plugins_seeded(db, user_id)
    enabled_plugins = {
        r.plugin_id
        for r in db.query(UserPlugin).filter(UserPlugin.user_id == user_id, UserPlugin.enabled.is_(True)).all()
    }
    allowed_system_slugs: set[str] = set()
    for entry in SYSTEM_FEATURE_CATALOG:
        if entry["plugin_id"] in enabled_plugins:
            for m in entry.get("metrics", []):
                allowed_system_slugs.add(m["slug"])

    out: list[dict] = []
    for defn in db.query(ReadingDefinition).order_by(ReadingDefinition.label).all():
        if defn.user_id == user_id:
            out.append(_metric_payload(defn, owned=True))
        elif defn.is_system and defn.slug in allowed_system_slugs:
            out.append(_metric_payload(defn, owned=False))
    return out


def _metric_payload(defn: ReadingDefinition, *, owned: bool) -> dict:
    return {
        "slug": defn.slug,
        "label": defn.label,
        "unit": defn.unit,
        "source_type": defn.source_type,
        "feature_id": defn.feature_id,
        "is_system": defn.is_system,
        "is_custom": not defn.is_system or owned,
        "user_owned": owned,
    }


def list_custom_features(db: Session, user_id: int) -> list[dict]:
    rows = db.query(UserFeature).filter(UserFeature.user_id == user_id).order_by(UserFeature.created_at.desc()).all()
    result = []
    for f in rows:
        metrics = [
            _metric_payload(d, owned=True)
            for d in db.query(ReadingDefinition)
            .filter(ReadingDefinition.user_id == user_id, ReadingDefinition.feature_id == f.feature_id)
            .all()
        ]
        result.append(
            {
                "feature_id": f.feature_id,
                "name": f.name,
                "description": f.description,
                "enabled": f.enabled,
                "config": json.loads(f.config_json or "{}"),
                "metrics": metrics,
                "created_at": f.created_at.isoformat() if f.created_at else None,
            }
        )
    return result


def create_custom_feature(
    db: Session,
    user_id: int,
    *,
    name: str,
    description: str | None,
    feature_slug: str,
    metrics: list[dict],
) -> dict:
    if not name.strip():
        raise ValueError("Feature name is required")
    if not metrics:
        raise ValueError("Add at least one metric")
    clean_slug = feature_slug.strip().lower().replace(" ", "-").replace("_", "-")
    if not re.match(r"^[a-z][a-z0-9-]{1,32}$", clean_slug):
        raise ValueError("Feature slug: lowercase letters, numbers, hyphens (2–33 chars)")

    feature_id = _feature_id_from_slug(user_id, clean_slug)
    existing = (
        db.query(UserFeature)
        .filter(UserFeature.user_id == user_id, UserFeature.feature_id == feature_id)
        .first()
    )
    if existing:
        raise ValueError("You already have a feature with this slug")

    feature = UserFeature(
        user_id=user_id,
        feature_id=feature_id,
        name=name.strip(),
        description=(description or "").strip() or None,
        enabled=True,
        config_json="{}",
        created_at=datetime.now(UTC),
    )
    db.add(feature)

    plugin_row = UserPlugin(user_id=user_id, plugin_id=feature_id, enabled=True, config_json="{}")
    db.add(plugin_row)

    created_metrics = []
    for m in metrics:
        mslug = m.get("slug", "").strip().lower().replace("-", "_")
        if not _SLUG_RE.match(mslug):
            raise ValueError(f"Invalid metric slug: {mslug}")
        full_slug = _user_metric_slug(user_id, mslug)
        if db.query(ReadingDefinition).filter(ReadingDefinition.slug == full_slug).first():
            raise ValueError(f"Metric slug already exists: {mslug}")
        defn = ReadingDefinition(
            user_id=user_id,
            slug=full_slug,
            label=m.get("label", mslug).strip()[:160],
            unit=(m.get("unit") or "count").strip()[:40],
            source_type=(m.get("source_type") or "manual").strip()[:20],
            feature_id=feature_id,
            is_system=False,
        )
        db.add(defn)
        created_metrics.append(mslug)

    db.commit()
    db.refresh(feature)
    return list_custom_features(db, user_id)[0]


def update_custom_feature(
    db: Session,
    user_id: int,
    feature_id: str,
    *,
    name: str | None = None,
    description: str | None = None,
    enabled: bool | None = None,
) -> dict:
    feature = (
        db.query(UserFeature)
        .filter(UserFeature.user_id == user_id, UserFeature.feature_id == feature_id)
        .first()
    )
    if not feature:
        raise ValueError("Feature not found")
    if name is not None:
        feature.name = name.strip()[:160]
    if description is not None:
        feature.description = description.strip() or None
    if enabled is not None:
        feature.enabled = enabled
        row = (
            db.query(UserPlugin)
            .filter(UserPlugin.user_id == user_id, UserPlugin.plugin_id == feature_id)
            .first()
        )
        if row:
            row.enabled = enabled
    db.commit()
    for f in list_custom_features(db, user_id):
        if f["feature_id"] == feature_id:
            return f
    raise ValueError("Feature not found after update")


def delete_custom_feature(db: Session, user_id: int, feature_id: str) -> None:
    feature = (
        db.query(UserFeature)
        .filter(UserFeature.user_id == user_id, UserFeature.feature_id == feature_id)
        .first()
    )
    if not feature:
        raise ValueError("Feature not found")
    db.query(ReadingDefinition).filter(
        ReadingDefinition.user_id == user_id, ReadingDefinition.feature_id == feature_id
    ).delete()
    db.query(UserPlugin).filter(UserPlugin.user_id == user_id, UserPlugin.plugin_id == feature_id).delete()
    db.delete(feature)
    db.commit()


def add_metric_to_feature(
    db: Session, user_id: int, feature_id: str, *, label: str, slug: str, unit: str, source_type: str
) -> dict:
    feature = (
        db.query(UserFeature)
        .filter(UserFeature.user_id == user_id, UserFeature.feature_id == feature_id)
        .first()
    )
    if not feature:
        raise ValueError("Feature not found")
    mslug = slug.strip().lower().replace("-", "_")
    if not _SLUG_RE.match(mslug):
        raise ValueError("Invalid metric slug")
    full_slug = _user_metric_slug(user_id, mslug)
    if db.query(ReadingDefinition).filter(ReadingDefinition.slug == full_slug).first():
        raise ValueError("Metric slug already exists")
    defn = ReadingDefinition(
        user_id=user_id,
        slug=full_slug,
        label=label.strip()[:160],
        unit=unit.strip()[:40],
        source_type=source_type.strip()[:20],
        feature_id=feature_id,
        is_system=False,
    )
    db.add(defn)
    db.commit()
    db.refresh(defn)
    return _metric_payload(defn, owned=True)
