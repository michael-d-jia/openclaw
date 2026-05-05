# OpenClaw

A personal Discord bot for LeetCode interview prep — powered by Google Gemini and Google Sheets.

## What it does

- **Daily problem delivery** — sends the next LeetCode problem every morning at 7:00 AM with a Java starter file pushed to GitHub
- **Google Sheets tracking** — mark problems complete directly in a spreadsheet using a dropdown; the bot reads it as the source of truth
- **REDO queue** — flag problems to revisit later; they get pushed to the back of the queue automatically

## Setup

**Prerequisites:** Python 3.13, a Discord bot token, a Google Gemini API key, a Google Cloud service account with Sheets API enabled.

```bash
# Clone and install
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Fill in all variables (see below)

# Run
python main.py
```

To keep the bot running after closing your SSH session:
```bash
nohup python main.py > ~/openclaw.log 2>&1 &
```

## Environment variables

| Variable | Description |
|---|---|
| `DISCORD_TOKEN` | Discord bot token |
| `GEMINI_API_KEY` | Google Gemini API key |
| `BRIEFING_CHANNEL_ID` | Channel for morning prep messages |
| `GOOGLE_SHEETS_ID` | ID from your Google Sheet URL (`/d/<ID>/edit`) |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Path to service account JSON key file |

## Google Sheets setup

1. Create a Google Cloud project and enable the **Sheets API**
2. Create a **Service Account** and download the JSON key
3. Create a Google Sheet with these columns:
   `Week | Day | Category | Problem | Difficulty | URL | Why This Problem | Status | Video URL`
4. Share the sheet with the service account email (Editor access)
5. Set up a **Data validation dropdown** on the Status column with these values:
   - `Solved cold` — got it within 25 min
   - `Solved with hint` — needed a nudge but finished
   - `Studied solution` — couldn't get the approach, learned from editorial
   - `REDO` — studied but couldn't rewrite from scratch

## Bot commands

| Command | Description |
|---|---|
| `!prep` | Manually trigger today's LeetCode problem |
| `!roadmap` | Show progress — done / remaining / REDO counts |
| `!hint` | Show the video link for the current problem |
| `!redo` | Mark the current problem as REDO and push it to the back of the queue |

The bot also posts automatically every morning at **7:00 AM ET**.

## Project structure

```
openclaw/
├── main.py                  # Entry point
├── core/
│   ├── llm.py               # Gemini API wrapper
│   └── task_db.py           # SQLite (unused, kept for reference)
├── bot/
│   └── discord_bot.py       # Bot commands and scheduled jobs
├── workflows/
│   ├── prep_pipeline.py     # LeetCode fetching, file gen, Git push
│   └── sheets_client.py     # Google Sheets read/write
├── prompts/                 # AI prompt templates
└── data/
    ├── prep_roadmap.csv     # Static reference copy of the problem list
    └── leetcode_solutions/  # Generated Java starter files
```

## LeetCode pipeline

Each morning the bot:

1. Reads the Google Sheet to find the next problem (first blank Status row; falls back to REDO rows after all blank rows are done)
2. Fetches the full problem description from LeetCode's GraphQL API
3. Generates a Java starter file via Gemini
4. Saves it to `data/leetcode_solutions/` and pushes to GitHub

Mark a problem complete by selecting a status in the Google Sheet dropdown.

## Tech stack

- [discord.py](https://discordpy.readthedocs.io/) — bot framework
- [google-genai](https://ai.google.dev/) — Gemini 2.5 Flash for Java file generation
- [gspread](https://docs.gspread.org/) — Google Sheets API client
- [APScheduler](https://apscheduler.readthedocs.io/) — cron-like scheduling
