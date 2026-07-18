# Google Calendar → Amazfit

Zepp Mini Programs **cannot** create events in Amazfit’s stock Calendar. Use this path instead:

```text
CALT web (Productivity) → Google Calendar → phone calendar sync → Amazfit Calendar
```

## 1. Google Cloud OAuth (one-time)

**Easiest:** use the form on **Productivity → Calendar → Google Calendar → Amazfit** — open the credentials link, create a Web client, paste Client ID + Secret, Save, then Connect.

Or put them in `.env` (restart backend):

```env
GOOGLE_OAUTH_CLIENT_ID=....apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=GOCSPX-...
GOOGLE_OAUTH_REDIRECT_URI=http://127.0.0.1:8000/api/planner/google-calendar/callback
GOOGLE_CALENDAR_ID=primary
```

Manual Cloud Console steps:

1. Open [Google Cloud Console](https://console.cloud.google.com/) → create/select a project.
2. **APIs & Services → Library** → enable **Google Calendar API**.
3. **Credentials → Create credentials → OAuth client ID**
   - Application type: **Web application**
   - Authorized redirect URI:
     `http://127.0.0.1:8000/api/planner/google-calendar/callback`
4. Paste into the web UI form (or `.env` as above).

If the OAuth consent screen is in **Testing**, add your Google account as a test user
(**APIs & Services → OAuth consent screen → Test users → Add users**).
Otherwise Connect shows `403: access_denied` / “has not completed the Google verification process”.

We need the **calendar.events** scope. If Push returns 403, enable
[Google Calendar API](https://console.cloud.google.com/apis/library/calendar-json.googleapis.com)
for the same Cloud project, then **Connect Google** again and Push.

## 2. Connect from the web app

1. Open **Productivity → Calendar**.
2. Click **Connect Google** → sign in → allow calendar access.
3. Click **Push to Google** (or apply a plan — apply also tries a push when connected).
4. Optional: **Download .ics** and import into Google Calendar if you skip OAuth.

Tokens are stored locally at `data/google_calendar_oauth.json` (not committed).

## 3. Phone → Amazfit

1. On your phone, ensure the same Google account syncs Calendar (Settings → Accounts → Google → Calendar).
2. In **Zepp** (or Amazfit app): enable **Google Calendar** / calendar sync for the watch.
3. Wait a few minutes or force a sync; events titled like your CALT blocks should appear on the watch Calendar.

Exact Zepp menus vary by firmware; look for Calendar permissions / Google Calendar under Device or App settings.

## APIs

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/planner/google-calendar/status` | Connected? Client configured? |
| POST | `/api/planner/google-calendar/credentials` | Save Client ID/Secret from UI |
| GET | `/api/planner/google-calendar/auth-url` | Start OAuth |
| GET | `/api/planner/google-calendar/callback` | OAuth redirect |
| POST | `/api/planner/google-calendar/sync?days=14` | Push planner blocks |
| POST | `/api/planner/google-calendar/disconnect` | Clear local tokens |
| GET | `/api/planner/calendar.ics?days=14` | ICS download |

Events are keyed by planner block id (`extendedProperties.private.caltBlockId`) so re-push updates instead of duplicating.
