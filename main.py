"""
OpenClaw — Personal Automation Agent
Entry point: starts the Discord bot and all background services.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")

# Ensure data/ directory exists for SQLite DB
(ROOT / "data").mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Init core modules (task_db auto-creates tables on import)
# ---------------------------------------------------------------------------
from core import task_db  # noqa: F401

# ---------------------------------------------------------------------------
# Start bot
# ---------------------------------------------------------------------------
from bot.discord_bot import bot

if __name__ == "__main__":
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        print("ERROR: DISCORD_TOKEN not set. Check your .env file.")
        sys.exit(1)
    bot.run(token)