"""Life-clock litmus segments — overlap paint + micro coalesce."""

from backend.hub.services.rollup import _coalesce_micro_segments, _paint_timeline


def test_paint_timeline_resolves_overlaps_to_solid_blocks():
    raw = [
        {
            "type": "distraction",
            "label": "Distraction",
            "startHour": 10.0,
            "endHour": 12.0,
            "color": "#f43f5e",
        },
        {
            "type": "productive",
            "label": "Productive",
            "startHour": 10.5,
            "endHour": 11.0,
            "color": "#14b8a6",
        },
        {
            "type": "distraction",
            "label": "Distraction",
            "startHour": 10.2,
            "endHour": 10.4,
            "color": "#f43f5e",
        },
    ]
    painted = _paint_timeline(raw, bin_minutes=5.0)
    # No overlapping ranges
    for i in range(len(painted) - 1):
        assert painted[i]["endHour"] <= painted[i + 1]["startHour"] + 1e-9
    # Productive wins the overlapping 10.5–11.0 window
    mid = next(s for s in painted if s["startHour"] <= 10.6 < s["endHour"])
    assert mid["type"] == "productive"
    # Far fewer than raw micro-stripes
    assert len(painted) <= 4


def test_coalesce_absorbs_flecks():
    segs = [
        {
            "type": "distraction",
            "label": "Distraction",
            "startHour": 8.0,
            "endHour": 9.0,
            "color": "#f43f5e",
        },
        {
            "type": "productive",
            "label": "Productive",
            "startHour": 9.0,
            "endHour": 9.03,  # ~2 min fleck
            "color": "#14b8a6",
        },
        {
            "type": "distraction",
            "label": "Distraction",
            "startHour": 9.03,
            "endHour": 10.0,
            "color": "#f43f5e",
        },
    ]
    out = _coalesce_micro_segments(segs, min_minutes=4.0)
    assert len(out) == 1
    assert out[0]["type"] == "distraction"
    assert out[0]["endHour"] >= 10.0
