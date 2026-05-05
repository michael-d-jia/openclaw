import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import discord
from discord.ext import commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from workflows.prep_pipeline import run_morning_prep
from workflows.sheets_client import get_next_problem, get_roadmap_summary, mark_redo

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BRIEFING_CHANNEL_ID = int(os.environ.get("BRIEFING_CHANNEL_ID", 0))

# ---------------------------------------------------------------------------
# Bot setup
# ---------------------------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
scheduler = AsyncIOScheduler(timezone="America/New_York")

# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------
@bot.event
async def on_ready():
    print(f"OpenClaw online as {bot.user} (id: {bot.user.id})")
    scheduler.start()

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing argument: `{error.param.name}`.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Bad argument — check the command syntax.")
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        await ctx.send(f"❌ Something went wrong: {error}")
        print(f"[ERROR] {ctx.command}: {error}")

# ---------------------------------------------------------------------------
# Scheduled jobs
# ---------------------------------------------------------------------------
async def morning_prep():
    ch = bot.get_channel(BRIEFING_CHANNEL_ID)
    if not ch:
        return
    try:
        result = run_morning_prep()
        if not result:
            await ch.send("☀️ **Morning Prep** — No pending problems. Roadmap complete!")
            return
        if result["is_new"]:
            push_status = "✅ Pushed to GitHub" if result["pushed"] else f"⚠️ Git push failed: {result['push_error']}"
        else:
            push_status = "📌 File already on GitHub"
        why = f"\n> {result['why']}" if result.get("why") else ""
        video = f"\n📺 {result['video_url']}" if result.get("video_url") else ""
        msg = (
            f"☀️ **Morning Prep**\n\n"
            f"**{result['title']}** ({result['difficulty']}) · {result['category']}\n"
            f"{result['url']}{why}\n\n"
            f"{push_status}{video}"
        )
        await ch.send(msg)
    except Exception as e:
        await ch.send(f"☀️ **Morning Prep** — Error: {e}")

scheduler.add_job(morning_prep, "cron", hour=7, minute=0, misfire_grace_time=7200)

# ---------------------------------------------------------------------------
# LeetCode commands
# ---------------------------------------------------------------------------
@bot.command()
async def prep(ctx):
    """Manually trigger today's LeetCode problem."""
    await ctx.send("🧠 Fetching...")
    try:
        result = run_morning_prep()
        if not result:
            await ctx.send("✅ No pending problems — roadmap complete!")
            return
        if result["is_new"]:
            push_status = "✅ Pushed to GitHub" if result["pushed"] else f"⚠️ Git push failed: {result['push_error']}"
        else:
            push_status = "📌 File already on GitHub"
        why = f"\n> {result['why']}" if result.get("why") else ""
        video = f"\n📺 {result['video_url']}" if result.get("video_url") else ""
        msg = (
            f"☀️ **Prep**\n\n"
            f"**{result['title']}** ({result['difficulty']}) · {result['category']}\n"
            f"{result['url']}{why}\n\n"
            f"{push_status}{video}"
        )
        await ctx.send(msg)
    except Exception as e:
        await ctx.send(f"❌ Failed: {e}")

@bot.command()
async def redo(ctx):
    """Mark the current problem as REDO — pushes it to the back of the queue."""
    try:
        row = get_next_problem()
        if not row:
            await ctx.send("✅ No pending problems — roadmap complete!")
            return
        found = mark_redo(row["URL"])
        if found:
            await ctx.send(f"🔁 Marked **{row['Problem']}** as REDO — it'll come back after the current queue.")
        else:
            await ctx.send("❌ Couldn't find that problem in the sheet.")
    except Exception as e:
        await ctx.send(f"❌ Failed: {e}")

@bot.command()
async def roadmap(ctx):
    """Show roadmap progress from the Google Sheet."""
    try:
        summary = get_roadmap_summary()
        complete = summary["complete"]
        pending = summary["pending"]
        redo = summary["redo"]
        lines = [f"🗺️ **Roadmap** — {len(complete)} done, {len(pending)} remaining, {len(redo)} to redo\n"]
        if pending:
            lines.append("**Up next:**")
            for row in pending[:8]:
                lines.append(f"⬜ **{row['Problem']}** ({row['Category']})")
            if len(pending) > 8:
                lines.append(f"...and {len(pending) - 8} more.")
        if redo:
            lines.append("\n**REDO queue:**")
            for row in redo:
                lines.append(f"🔁 **{row['Problem']}** ({row['Category']})")
        if complete:
            lines.append("\n**Last completed:**")
            for row in complete[-5:]:
                lines.append(f"✅ **{row['Problem']}** — {row.get('Status', '')}")
        await ctx.send("\n".join(lines))
    except Exception as e:
        await ctx.send(f"❌ Failed: {e}")

@bot.command(name="hint")
async def hint(ctx):
    """Show the video hint for the current problem."""
    try:
        row = get_next_problem()
        if not row:
            await ctx.send("✅ No pending problems — roadmap complete!")
            return
        video_url = row.get("Video URL", "").strip()
        if video_url:
            await ctx.send(
                f"📺 **{row['Problem']}** ({row['Category']})\n{video_url}"
            )
        else:
            await ctx.send(
                f"📺 **{row['Problem']}** ({row['Category']})\n"
                f"No video linked. LeetCode: {row['URL']}"
            )
    except Exception as e:
        await ctx.send(f"❌ Failed: {e}")
