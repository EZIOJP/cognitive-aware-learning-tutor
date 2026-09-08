"""Daily devotion blocks — prayers, notes, Proverbs/Psalms afternoon, praise hymns."""

from __future__ import annotations

import hashlib
from datetime import date
from typing import Any

LORDS_PRAYER = """Our Father in heaven, may your name be kept holy.
Let your Kingdom come. Let your will be done on earth as it is in heaven.
Give us today our daily bread.
Forgive us our debts, as we also forgive our debtors.
Bring us not into temptation, but deliver us from the evil one.
For yours is the Kingdom, the power, and the glory forever. Amen."""

MORNING_NOTE = (
    "Read today's chapter slowly — one verse at a time. After reading, pray the Lord's Prayer "
    "(Matthew 6:9–13). This chapter unlocks the morning gate and counts toward reward days."
)

AFTERNOON_NOTE = (
    "Afternoon: pray first for wisdom, health, healing, and work — then read today's Proverbs chapter slowly."
)

AFTERNOON_PRAYER = """Father, You promise wisdom to all who ask (James 1:5).

Grant me wisdom for decisions today — at study, at work, and at home.
Guide my steps; correct my motives; teach me to listen before I speak.
Bring healing where my body or spirit is weary — health, strength, and restoration.
Prosper the work of my hands; open doors for meaningful labor and steady income.
Protect my job, my relationships, and my peace.

Let Your Word in Proverbs shape how I think and speak this afternoon. Amen."""

EVENING_NOTE = (
    "Evening: read today's Psalms chapter, then worship — sing or read the hymn slowly. "
    "Turn from the day's noise to who God is, not only what you accomplished."
)

# Curated praise hymns — titles + opening lines for your rotation (add lyrics you use locally).
PRAISE_HYMNS: list[dict[str, str]] = [
    {
        "id": "how-great-thou-art",
        "title": "How Great Thou Art",
        "opening": "O Lord my God, when I in awesome wonder consider all the worlds Thy hands have made…",
        "theme": "Creation · majesty",
    },
    {
        "id": "amazing-grace",
        "title": "Amazing Grace",
        "opening": "Amazing grace! how sweet the sound, that saved a wretch like me…",
        "theme": "Grace · redemption",
    },
    {
        "id": "great-is-thy-faithfulness",
        "title": "Great Is Thy Faithfulness",
        "opening": "Great is Thy faithfulness, O God my Father; there is no shadow of turning with Thee…",
        "theme": "Faithfulness · morning mercies",
    },
    {
        "id": "blessed-be-your-name",
        "title": "Blessed Be Your Name",
        "opening": "Blessed be Your name in the land that is plentiful…",
        "theme": "Worship in all seasons",
    },
    {
        "id": "10000-reasons",
        "title": "10,000 Reasons (Bless the Lord)",
        "opening": "Bless the Lord, O my soul, O my soul; worship His holy name…",
        "theme": "Gratitude · praise",
    },
    {
        "id": "holy-holy-holy",
        "title": "Holy, Holy, Holy",
        "opening": "Holy, holy, holy! Lord God Almighty! Early in the morning our song shall rise to Thee…",
        "theme": "Holiness · Trinity",
    },
    {
        "id": "it-is-well",
        "title": "It Is Well with My Soul",
        "opening": "When peace like a river attendeth my way, when sorrows like sea billows roll…",
        "theme": "Peace · trust",
    },
    {
        "id": "in-christ-alone",
        "title": "In Christ Alone",
        "opening": "In Christ alone my hope is found; He is my light, my strength, my song…",
        "theme": "Christ · cornerstone",
    },
    {
        "id": "revelation-song",
        "title": "Revelation Song",
        "opening": "Worthy is the Lamb who was slain; holy, holy is He…",
        "theme": "Worship · Revelation",
    },
    {
        "id": "what-a-beautiful-name",
        "title": "What a Beautiful Name",
        "opening": "You were the Word at the beginning, one with God the Lord Most High…",
        "theme": "Name of Jesus",
    },
    {
        "id": "shout-to-the-lord",
        "title": "Shout to the Lord",
        "opening": "My Jesus, my Savior, Lord, there is none like You…",
        "theme": "Joyful praise",
    },
    {
        "id": "how-deep-the-fathers-love",
        "title": "How Deep the Father's Love for Us",
        "opening": "How deep the Father's love for us, how vast beyond all measure…",
        "theme": "Cross · love",
    },
    {
        "id": "be-thou-my-vision",
        "title": "Be Thou My Vision",
        "opening": "Be Thou my vision, O Lord of my heart; naught be all else to me, save that Thou art…",
        "theme": "Surrender · guidance",
    },
    {
        "id": "crown-him",
        "title": "Crown Him with Many Crowns",
        "opening": "Crown Him with many crowns, the Lamb upon His throne…",
        "theme": "Kingship of Christ",
    },
    {
        "id": "joyful-joyful",
        "title": "Joyful, Joyful, We Adore Thee",
        "opening": "Joyful, joyful, we adore Thee, God of glory, Lord of love…",
        "theme": "Joy · adoration",
    },
    {
        "id": "here-i-am-to-worship",
        "title": "Here I Am to Worship",
        "opening": "Light of the world, You stepped down into darkness, opened my eyes, let me see…",
        "theme": "Worship · humility",
    },
    {
        "id": "good-good-father",
        "title": "Good Good Father",
        "opening": "I've heard a thousand stories of what they think You're like…",
        "theme": "Fatherhood of God",
    },
    {
        "id": "build-my-life",
        "title": "Build My Life",
        "opening": "Worthy of every song we could ever sing; worthy of all the praise we could ever bring…",
        "theme": "Devotion · foundation",
    },
]

_PROVERBS_CHAPTERS = 31
_PSALMS_CHAPTERS = 150


def _parse_day(day_iso: str | None) -> date:
    if day_iso:
        try:
            return date.fromisoformat(day_iso)
        except ValueError:
            pass
    return date.today()


def _day_seed(day_iso: str) -> int:
    return int(hashlib.md5(day_iso.encode()).hexdigest()[:8], 16)


def resolve_afternoon_reading(day_iso: str | None = None) -> dict[str, Any]:
    """Daily Proverbs chapter + afternoon prayer (wisdom, health, healing, work)."""
    d = _parse_day(day_iso)
    day_s = d.isoformat()
    doy = d.timetuple().tm_yday
    chapter = (doy % _PROVERBS_CHAPTERS) + 1
    book = "Proverbs"
    key = f"{book}|{chapter}"
    return {
        "book": book,
        "chapter": chapter,
        "key": key,
        "label": f"{book} {chapter}",
        "slot": "afternoon",
        "day": day_s,
        "note": AFTERNOON_NOTE,
        "prayer": AFTERNOON_PRAYER,
    }


def resolve_evening_hymn(day_iso: str | None = None) -> dict[str, Any]:
    d = _parse_day(day_iso)
    day_s = d.isoformat()
    idx = _day_seed(day_s) % len(PRAISE_HYMNS)
    hymn = dict(PRAISE_HYMNS[idx])
    hymn["slot"] = "evening"
    hymn["day"] = day_s
    hymn["note"] = EVENING_NOTE
    return hymn


def resolve_evening_reading(day_iso: str | None = None) -> dict[str, Any]:
    """Evening Psalms chapter + worship hymn rotation."""
    d = _parse_day(day_iso)
    day_s = d.isoformat()
    doy = d.timetuple().tm_yday
    chapter = (doy % _PSALMS_CHAPTERS) + 1
    book = "Psalms"
    key = f"{book}|{chapter}"
    hymn = resolve_evening_hymn(day_s)
    return {
        "book": book,
        "chapter": chapter,
        "key": key,
        "label": f"{book} {chapter}",
        "slot": "evening",
        "day": day_s,
        "note": EVENING_NOTE,
        "hymn": hymn,
        "worship_title": str(hymn.get("title") or ""),
        "worship_opening": str(hymn.get("opening") or ""),
        "worship_theme": str(hymn.get("theme") or ""),
        "hymn_id": str(hymn.get("id") or ""),
    }


def list_praise_hymns() -> list[dict[str, str]]:
    return [dict(h) for h in PRAISE_HYMNS]


def morning_devotion() -> dict[str, Any]:
    return {
        "slot": "morning",
        "lords_prayer": LORDS_PRAYER,
        "note": MORNING_NOTE,
    }
