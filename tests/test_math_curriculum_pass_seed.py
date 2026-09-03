import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.base import Base
from backend.math.curriculum_pass.seed import seed_mapped_questions
from backend.models.review_card import ReviewCard
from backend.models.user import User


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    session.add(User(id=1, username="curriculum_pass_seed", password_hash="x"))
    session.commit()
    yield session
    session.close()


def test_one_card_per_question_not_per_mt(db_session):
    pack = {
        "topic": {
            "topic_id": "math.aptitude.sat-data",
            "title": "SAT",
            "note_topic_ids": ["MT1-T05", "MT1-T07"],
        },
        "questions": [
            {
                "id": "math.sat.99",
                "source": "sat",
                "source_id": "99",
                "problem": "Mean of 1,2,3?",
                "answer": "2",
                "tags": ["MT1-T05", "MT1-T07", "sat"],
            }
        ],
    }
    n = seed_mapped_questions(db_session, user_id=1, packs=[pack])
    assert n == 1
    rows = db_session.query(ReviewCard).filter(ReviewCard.user_id == 1).all()
    assert len(rows) == 1
    assert "math.sat.99" in rows[0].item_key
