from datetime import UTC, datetime

from backend.quiz import srs as srs_mod


def test_schedule_after_correct_answer():
    state = srs_mod.SrsState(mastery=2, stability=1.0)
    next_state = srs_mod.schedule_after_answer(state, correct=True)
    assert next_state.mastery == 3
    assert next_state.times_asked == 1
    assert next_state.due_date is not None
    assert next_state.interval_days >= 1
    assert next_state.stability >= 1.0


def test_schedule_after_wrong_answer():
    state = srs_mod.SrsState(mastery=4, consecutive_correct=2, stability=5.0)
    next_state = srs_mod.schedule_after_answer(state, correct=False)
    assert next_state.mastery == 2
    assert next_state.consecutive_correct == 0
    assert next_state.lapses == 1
    assert next_state.stability < 5.0


def test_is_due_new_item():
    state = srs_mod.SrsState(mastery=0)
    assert srs_mod.is_due(state) is True


def test_is_due_future():
    state = srs_mod.SrsState(
        mastery=5,
        due_date=datetime.now(UTC).replace(year=datetime.now(UTC).year + 1),
    )
    assert srs_mod.is_due(state) is False


def test_calc_interval_from_stability():
    state = srs_mod.SrsState(stability=10.0, difficulty=5.0)
    days = srs_mod.calc_interval_days(state)
    assert 1 <= days <= 180
