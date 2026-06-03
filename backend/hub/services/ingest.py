import json
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from backend.models import Reading, ReadingDefinition


def get_definition_by_slug(db: Session, slug: str) -> ReadingDefinition | None:
    return db.query(ReadingDefinition).filter(ReadingDefinition.slug == slug).first()


def insert_reading(
    db: Session,
    *,
    user_id: int,
    slug: str,
    value_numeric: float | None = None,
    value_json: dict | None = None,
    recorded_at: datetime | None = None,
    session_id: int | None = None,
    source_device: str | None = None,
    client_event_id: str | None = None,
) -> Reading:
    defn = get_definition_by_slug(db, slug)
    if not defn:
        raise ValueError(f"Unknown reading definition: {slug}")

    if client_event_id:
        existing = (
            db.query(Reading)
            .filter(Reading.user_id == user_id, Reading.client_event_id == client_event_id)
            .first()
        )
        if existing:
            return existing

    row = Reading(
        user_id=user_id,
        definition_id=defn.id,
        value_numeric=value_numeric,
        value_json=json.dumps(value_json) if value_json else None,
        recorded_at=recorded_at or datetime.now(UTC),
        session_id=session_id,
        source_device=source_device,
        client_event_id=client_event_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def insert_readings_batch(db: Session, user_id: int, items: list[dict]) -> list[Reading]:
    out: list[Reading] = []
    for item in items:
        out.append(
            insert_reading(
                db,
                user_id=user_id,
                slug=item["slug"],
                value_numeric=item.get("value_numeric"),
                value_json=item.get("value_json"),
                recorded_at=item.get("recorded_at"),
                session_id=item.get("session_id"),
                source_device=item.get("source_device"),
                client_event_id=item.get("client_event_id"),
            )
        )
    return out
