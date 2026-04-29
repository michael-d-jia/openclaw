# OpenClaw

A personal Discord bot for task management, daily planning, and technical interview prep — powered by Google Gemini.

## What it does

- **Task management** — add and track tasks via natural language, bulk import, or PDF syllabi
- **Daily planning** — AI-generated time-blocked schedules that respect your fixed weekly schedule
- **LeetCode prep** — automated daily problem generation with Java starter files pushed to GitHub
- **Academic workflows** — extract deadlines from course syllabi (PDF upload → tasks)

Runs continuously with scheduled morning prep (8:00 AM) and daily briefings (8:05 AM).

## Setup

**Prerequisites:** Python 3.13, a Discord bot token, a Google Gemini API key.

```bash
# Clone and install
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Fill in DISCORD_TOKEN, GEMINI_API_KEY, BRIEFING_CHANNEL_ID, SYLLABUS_CHANNEL_ID

# Run
python main.py
```

The bot will auto-create the `data/` directory and initialize the SQLite database on first run.

## Environment variables

| Variable | Description |
|---|---|
| `DISCORD_TOKEN` | Discord bot token |
| `GEMINI_API_KEY` | Google Gemini API key |
| `BRIEFING_CHANNEL_ID` | Channel for morning prep and daily briefings |
| `SYLLABUS_CHANNEL_ID` | Channel for PDF syllabus uploads |

## Bot commands

| Command | Description |
|---|---|
| `!add <text>` | Parse natural language and add a task |
| `!bulk <text>` | Add multiple tasks at once (shows preview, confirm with reaction) |
| `!tasks [pending\|done\|all]` | List tasks |
| `!today` | Tasks due today |
| `!week` | Tasks due within 7 days |
| `!done <id>` | Mark a task complete |
| `!edit <id> <field> <value>` | Edit a task field |
| `!delete <id>` | Delete a task |
| `!plan` | Generate an AI daily schedule |
| `!prep` | Manually trigger morning LeetCode prep |
| `!push` | Mark current LeetCode problem as complete |
| `!roadmap` | Show LeetCode roadmap progress |
| `!hint` | Show video hint for current problem |

Upload a PDF to the syllabus channel to auto-extract deadlines into tasks.

## Project structure

```
openclaw/
├── main.py                  # Entry point
├── core/
│   ├── llm.py               # Gemini API wrapper
│   └── task_db.py           # SQLite task storage
├── bot/
│   └── discord_bot.py       # Bot commands and scheduled jobs
├── workflows/
│   ├── prep_pipeline.py     # LeetCode fetching, file gen, Git push
│   └── academic_parser.py   # PDF syllabus extraction
├── prompts/                 # AI prompt templates
└── data/
    ├── openclaw.db          # SQLite database (auto-created)
    ├── prep_roadmap.csv     # LeetCode problem list
    └── leetcode_solutions/  # Generated Java starter files
```

## LeetCode pipeline

The prep pipeline reads `data/prep_roadmap.csv` (columns: `date`, `topic`, `leetcode_url`, `status`, `video_url`). Each morning it:

1. Picks the next pending problem
2. Fetches the problem description from LeetCode's GraphQL API
3. Generates a Java starter file via Gemini
4. Saves it to `data/leetcode_solutions/` and pushes to GitHub

Mark a problem done with `!push` after solving it.

## Tech stack

- [discord.py](https://discordpy.readthedocs.io/) — bot framework
- [google-genai](https://ai.google.dev/) — Gemini 2.5 Flash for all LLM tasks
- [APScheduler](https://apscheduler.readthedocs.io/) — cron-like scheduling
- [pdfplumber](https://github.com/jsvine/pdfplumber) — PDF text extraction
- SQLite — task persistence
