from backend.db.migrate import get_revision_state, is_at_head


def test_database_at_alembic_head():
    current, head = get_revision_state()
    assert head is not None
    assert current == head, f"Run alembic upgrade head (at {current}, need {head})"
    assert is_at_head()
