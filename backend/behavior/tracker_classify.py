"""App classification rules for desktop activity sessions."""

from __future__ import annotations

import re

_APP_RULES: list[tuple[str, str, int]] = [
    (r"code|cursor|pycharm|intellij|webstorm|vim|neovim|emacs|sublime|notepad\+\+",
     "IDE / Code Editor", 95),
    (r"terminal|powershell|cmd\.exe|wt\.exe|windowsterminal|bash|conhost",
     "Terminal", 92),
    (r"postman|insomnia|dbeaver|tableplus|datagrip|pgadmin|mongodb compass",
     "Dev Tools", 90),
    (r"anki|quizlet|kindle|calibre|foxit|acrobat|sumatrapdf|okular",
     "Study / Reading", 90),
    (r"notion|obsidian|logseq|roamresearch|onenote|evernote",
     "Knowledge Work", 88),
    (r"word|excel|powerpoint|libreoffice|writer|calc|impress",
     "Office / Docs", 75),
    (r"figma|photoshop|illustrator|inkscape|gimp|blender|canva",
     "Design", 80),
    # Discord is a distraction client for hard-block; keep other chat as Communication.
    (r"discord",
     "Social Media", 15),
    (r"slack|teams|zoom|skype|telegram|whatsapp|signal",
     "Communication", 45),
    (r"chrome|firefox|msedge|brave|opera|arc|zen",
     "Browser", 40),
    (r"explorer\.exe|files\.exe",
     "File Manager", 30),
    (r"spotify|vlc|mpv|wmplayer|groove|musicbee|foobar|"
     r"youtube[\s\-]?music|pear[\s\-]?desktop|pear\.exe",
     "Music / Media", 20),
    (r"netflix|primevideo|hotstar|jiocinema|mxplayer|popcorntime|"
     r"disney\+?|disneyplus|hulu|twitch",
     "Video Streaming", 10),
    (r"steam|epicgameslauncher|battle\.net|origin|eadesktop|ealauncher|"
     r"ubisoft|upc\.exe|rockstar|gog|galaxy.?client|itch\.exe|"
     r"xbox|gamingservices|gamebar|roblox|minecraft|valorant|csgo|dota2|league|"
     r"start_protected_game|gameoverlayui|steamwebhelper|steamservice|"
     r"win64-shipping|win32-shipping",
     "Gaming", 10),
    (r"taskmgr|perfmon|processexplorer|resmon|task manager",
     "System Tools", 30),
]

_STUDY_TITLE = re.compile(
    r"scaler|leetcode|coursera|udemy|khanacademy|edx|tutorial|lecture|course|lesson"
    r"|python|data\s*science|machine\s*learning|gre|algorithm|dsa|arrays|graphs|sort",
    re.I,
)


def classify_app(exe: str, title: str) -> tuple[str, int]:
    # Bible PDF / embedded reader → spiritual (not productive study).
    try:
        from backend.behavior.bible_desktop import looks_like_bible_reader

        if looks_like_bible_reader(exe, title):
            return "Spiritual", 40
    except Exception:  # noqa: BLE001
        pass

    # Browsers must use title/domain rules — never match IDE patterns like
    # "cursor" inside a page title (e.g. Edge tab "Cursor Agents" → false IDE 95).
    from backend.behavior.session_key import is_browser_exe

    if is_browser_exe(exe):
        from backend.behavior.domain_classify import classify_browser_title

        return classify_browser_title(title)

    hay = f"{exe} {title}".lower()
    for pattern, category, score in _APP_RULES:
        if re.search(pattern, hay, re.I):
            if category == "Browser":
                from backend.behavior.domain_classify import classify_browser_title

                return classify_browser_title(title)
            return category, score
    return "Other", 35
