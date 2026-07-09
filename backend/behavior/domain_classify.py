"""Domain & browser-title classification rules for web activity.

Mirrors the pattern-match approach of tracker_classify.py but for websites.
When the desktop tracker detects a browser foreground, this module inspects
the window title (which contains the page title) to produce a finer category
and productivity score than the generic "Browser: 40".

Also works on raw domains from the Chrome extension.
"""

from __future__ import annotations

import re
from functools import lru_cache

# ── (pattern, category, score) — first match wins ──────────────────────────

_DOMAIN_RULES: list[tuple[str, str, int]] = [
    # Study & coursework
    (r"coursera|udemy|edx|khanacademy|khan\s*academy|brilliant|codecademy"
     r"|datacamp|pluralsight|skillshare|educative|scaler|simplilearn"
     r"|mit\.edu|stanford\.edu|\.edu/",
     "Coursework (Browser)", 92),
    (r"leetcode|hackerrank|codeforces|codechef|topcoder|exercism|neetcode"
     r"|algoexpert|interviewbit|geeksforgeeks",
     "Coding Practice", 90),
    (r"arxiv\.org|scholar\.google|researchgate|pubmed|jstor|ieee|acm\.org"
     r"|semanticscholar|sciencedirect",
     "Research", 90),
    (r"anki|quizlet|remnote|brainscape|flashcard",
     "Study / Reading", 90),

    # Dev & documentation
    (r"github\.com|gitlab\.com|bitbucket|codeberg|sourcehut",
     "Dev / Code", 92),
    (r"stackoverflow|stackexchange|askubuntu|serverfault|superuser",
     "Dev / Code", 88),
    (r"docs\.python|docs\.rust|developer\.mozilla|devdocs\.io|readthedocs"
     r"|man7\.org|cppreference|learn\.microsoft|docs\.microsoft"
     r"|docs\.google\.com/document|docs\.oracle|api\.flutter",
     "Documentation", 88),
    (r"pypi\.org|npmjs\.com|crates\.io|packagist|rubygems|maven"
     r"|hub\.docker\.com|registry\.terraform",
     "Dev / Code", 85),
    (r"vercel\.com|netlify\.com|railway\.app|render\.com|heroku|supabase"
     r"|firebase\.google|aws\.amazon|console\.cloud\.google|portal\.azure",
     "Dev / Cloud", 85),

    # AI & tools
    (r"chat\.openai|chatgpt|claude\.ai|bard\.google|gemini\.google"
     r"|copilot\.microsoft|poe\.com|perplexity",
     "AI Tools", 80),
    (r"huggingface\.co|kaggle\.com|colab\.research\.google|jupyter|wandb\.ai"
     r"|mlflow|tensorboard",
     "AI / ML", 88),

    # Knowledge & productivity
    (r"notion\.so|obsidian\.md|roamresearch|logseq|coda\.io|airtable",
     "Knowledge Work", 85),
    (r"wikipedia\.org|wikimedia|wiktionary",
     "Reference", 70),
    (r"medium\.com|dev\.to|hashnode|substack|towardsdatascience"
     r"|hackernoon|freecodecamp|css-tricks",
     "Tech Reading", 75),
    (r"docs\.google\.com|sheets\.google|slides\.google|drive\.google"
     r"|onedrive\.live|dropbox\.com|box\.com",
     "Office / Docs", 75),
    (r"figma\.com|canva\.com|miro\.com|whimsical|excalidraw|draw\.io",
     "Design", 80),
    (r"trello\.com|asana\.com|monday\.com|linear\.app|jira|clickup|todoist",
     "Project Management", 80),
    (r"calendar\.google|outlook\.live|outlook\.office|mail\.google|proton\.me",
     "Email / Calendar", 55),

    # Communication — moderate
    (r"slack\.com|teams\.microsoft|discord\.com|element\.io|matrix\.org",
     "Communication", 45),
    (r"zoom\.us|meet\.google|whereby\.com|webex",
     "Communication", 50),

    # Social media — low
    (r"twitter\.com|(?<!\w)x\.com|facebook\.com|instagram\.com|threads\.net"
     r"|tiktok\.com|snapchat\.com|pinterest\.com|tumblr\.com|mastodon",
     "Social Media", 15),
    (r"reddit\.com",
     "Social / Forum", 25),
    (r"linkedin\.com",
     "Professional Social", 45),

    # Shopping — low
    (r"amazon\.|flipkart|myntra|ajio|ebay|etsy|aliexpress|shopify"
     r"|walmart|target\.com|bestbuy",
     "Shopping", 10),

    # Entertainment — low
    (r"youtube\.com|youtu\.be",
     "Video (YouTube)", 25),
    (r"netflix\.com|primevideo|hotstar|disneyplus|hulu|hbomax|crunchyroll"
     r"|jiocinema|sonyliv|zee5|mxplayer|peacock",
     "Video Streaming", 8),
    (r"twitch\.tv|kick\.com",
     "Live Streaming", 10),
    (r"spotify\.com|music\.youtube|soundcloud|deezer|pandora|gaana|jiosaavn",
     "Music / Media", 20),
    (r"steam\b|epicgames|gog\.com|itch\.io|roblox|miniclip",
     "Gaming", 8),

    # News — medium-low
    (r"bbc\.|cnn\.|reuters|apnews|nytimes|washingtonpost|theguardian"
     r"|aljazeera|ndtv|thehindu|indianexpress|moneycontrol|livemint"
     r"|news\.google|news\.yahoo|bloomberg",
     "News", 30),

    # Finance
    (r"bank|razorpay|paytm|phonepe|gpay|paypal|stripe|wise\.com"
     r"|zerodha|groww|upstox|kite\.zerodha|tradingview",
     "Finance", 40),

    # Food & delivery
    (r"swiggy|zomato|ubereats|doordash|grubhub|dominos|pizzahut",
     "Food Delivery", 10),
    (r"ola\.com|uber\.com|rapido|lyft",
     "Ride / Travel", 15),
]

_TITLE_STUDY_BOOST = re.compile(
    r"lecture|tutorial|course|lesson|assignment|homework|exam|quiz"
    r"|documentation|api\s*reference|getting\s*started|how\s*to"
    r"|python|javascript|typescript|react|algorithm|data\s*struct"
    r"|machine\s*learning|deep\s*learning|gre\s|gre\b|math|calculus"
    r"|linear\s*algebra|statistics|probability",
    re.I,
)

_TITLE_ENTERTAINMENT_DROP = re.compile(
    r"gameplay|walkthrough|let'?s\s*play|unboxing|reaction|drama"
    r"|movie|trailer|clip|episode|vlog|prank|challenge|meme"
    r"|tiktok|shorts|reels|stories",
    re.I,
)


@lru_cache(maxsize=512)
def classify_domain(domain: str, title: str = "") -> tuple[str, int]:
    """Classify a website domain + optional page title.

    Returns (category, productivity_score).
    """
    hay = domain.lower()
    title_lower = title.lower() if title else ""

    for pattern, category, score in _DOMAIN_RULES:
        if re.search(pattern, hay, re.I):
            if _TITLE_STUDY_BOOST.search(title):
                score = max(score, 82)
            elif _TITLE_ENTERTAINMENT_DROP.search(title):
                score = min(score, 20)
            return category, score

    if title:
        if _TITLE_STUDY_BOOST.search(title):
            return "Study (Browser)", 78
        if _TITLE_ENTERTAINMENT_DROP.search(title):
            return "Entertainment", 15

    return "Other (Browser)", 35


_BROWSER_SUFFIX = re.compile(
    r"\s*[-–—]\s*(Microsoft\s*Edge|Google\s*Chrome|Mozilla\s*Firefox"
    r"|Brave|Opera|Arc|Safari)\s*$",
    re.I,
)

# Quick site-name lookup from browser title fragments
_TITLE_SITE_HINTS: list[tuple[str, str]] = [
    (r"\byoutube\b", "youtube.com"),
    (r"\bgithub\b", "github.com"),
    (r"\bgitlab\b", "gitlab.com"),
    (r"\bstack\s*overflow\b", "stackoverflow.com"),
    (r"\breddit\b", "reddit.com"),
    (r"\btwitter\b|\bx\.com\b", "twitter.com"),
    (r"\blinkedin\b", "linkedin.com"),
    (r"\bchatgpt\b|chat\.openai", "chat.openai.com"),
    (r"\bclaude\b", "claude.ai"),
    (r"\bperplexity\b", "perplexity.ai"),
    (r"\bnotion\b", "notion.so"),
    (r"\bfigma\b", "figma.com"),
    (r"\bcoursera\b", "coursera.org"),
    (r"\budemy\b", "udemy.com"),
    (r"\bedx\b", "edx.org"),
    (r"\bkhan\s*academy\b", "khanacademy.org"),
    (r"\bleetcode\b", "leetcode.com"),
    (r"\bhackerrank\b", "hackerrank.com"),
    (r"\bgeeksforgeeks\b", "geeksforgeeks.org"),
    (r"\bnetflix\b", "netflix.com"),
    (r"\bspotify\b", "spotify.com"),
    (r"\btwitch\b", "twitch.tv"),
    (r"\bamazon\b", "amazon.com"),
    (r"\bflipkart\b", "flipkart.com"),
    (r"\binstagram\b", "instagram.com"),
    (r"\bfacebook\b", "facebook.com"),
    (r"\bwhatsapp\b", "whatsapp.com"),
    (r"\btelegram\b", "telegram.org"),
    (r"\bdiscord\b", "discord.com"),
    (r"\bslack\b", "slack.com"),
    (r"\btrello\b", "trello.com"),
    (r"\bwikipedia\b", "wikipedia.org"),
    (r"\bmedium\b", "medium.com"),
    (r"\bdev\.to\b", "dev.to"),
    (r"\bGoogle\s*Docs\b", "docs.google.com"),
    (r"\bGoogle\s*Sheets\b", "sheets.google.com"),
    (r"\bGoogle\s*Slides\b", "slides.google.com"),
    (r"\bGmail\b", "mail.google.com"),
    (r"\bGoogle\s*Calendar\b", "calendar.google.com"),
    (r"\bscaler\b", "scaler.com"),
]


def classify_browser_title(window_title: str) -> tuple[str, int]:
    """Classify from a browser window title (desktop tracker path).

    Browser window titles usually look like:
      "Page Title - Site Name — Microsoft Edge"
      "Page Title - Google Chrome"
    """
    cleaned = _BROWSER_SUFFIX.sub("", window_title).strip()

    # Try to detect a known site name anywhere in the title
    for pattern, fake_domain in _TITLE_SITE_HINTS:
        if re.search(pattern, cleaned, re.I):
            return classify_domain(fake_domain, cleaned)

    parts = re.split(r"\s*[-–—]\s*", cleaned)
    site_hint = parts[-1].strip() if len(parts) > 1 else ""
    page_title = parts[0].strip() if parts else cleaned

    domain_guess = site_hint.lower().replace(" ", "")
    combined_hay = f"{domain_guess} {page_title}"

    return classify_domain(combined_hay, page_title)


BROWSER_CATEGORIES = sorted({cat for _, cat, _ in _DOMAIN_RULES} | {
    "Study (Browser)", "Entertainment", "Other (Browser)"
})
