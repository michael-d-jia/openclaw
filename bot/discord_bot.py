import os
import sys
import json
from pathlib import Path

# Ensure project root is on the path for cross-folder imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import discord
from discord.ext import commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from core.task_db import (
    add_task, add_tasks_bulk, get_pending, get_due_within,
    get_completed, complete_task, edit_task, delete_task,
)
from core.llm import parse_task, parse_tasks_bulk, generate_daily_plan
from workflows.prep_pipeline import run_morning_prep, mark_complete, get_roadmap_summary
from workflows.academic_parser import ingest_syllabus

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SYLLABUS_CHANNEL_ID = int(os.environ.get("SYLLABUS_CHANNEL_ID", 0))
BRIEFING_CHANNEL_ID = int(os.environ.get("BRIEFING_CHANNEL_ID", 0))

# ---------------------------------------------------------------------------
# Bot setup
# ---------------------------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
scheduler = AsyncIOScheduler(timezone="America/New_York")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def format_task(t):
    """One-line summary of a task for Discord."""
    due = t["due_date"] or "no date"
    mins = f"{t['estimated_minutes']}m" if t.get("estimated_minutes") else "?"
    pri = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(t["priority"], "⚪")
    return f"`#{t['id']}` {pri} **{t['title']}** — {t['category']} | due {due} | ~{mins}"

# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------
@bot.event
async def on_ready():
    print(f"OpenClaw online as {bot.user} (id: {bot.user.id})")
    scheduler.start()

@bot.event
async def on_command_error(ctx, error):
    """Global error handler for all commands."""
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing argument: `{error.param.name}`. Check `!help {ctx.command}` for usage.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"❌ Bad argument — make sure you're passing the right type (e.g. a number for task ID).")
    elif isinstance(error, commands.CommandNotFound):
        pass  # silently ignore typos
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
            await ch.send("☀️ **Morning Prep** — No pending problems. You're all caught up!")
            return
        push_status = "✅ Pushed to GitHub" if result["pushed"] else f"⚠️ Git push failed: {result['push_error']}"
        msg = (
            f"☀️ **Morning Prep**\n\n"
            f"**{result['title']}** ({result['difficulty']})\n"
            f"Topic: {result['topic']}\n"
            f"Link: {result['url']}\n"
            f"{push_status}\n\n"
            f"Run `git pull` to get the starter file, then `!push` when you're done."
        )
        await ch.send(msg)
    except Exception as e:
        await ch.send(f"☀️ **Morning Prep** — Error: {e}")

async def daily_briefing():
    ch = bot.get_channel(BRIEFING_CHANNEL_ID)
    if not ch:
        return
    try:
        tasks = get_due_within(days=2)
        if not tasks:
            await ch.send("📋 **Daily Briefing** — Nothing due in the next 48 hours. Chill day.")
            return
        lines = [format_task(t) for t in tasks]
        plan = generate_daily_plan(tasks)
        msg = "📋 **Daily Briefing**\n\n"
        msg += "**Upcoming (next 48h):**\n" + "\n".join(lines)
        msg += f"\n\n**Suggested Plan:**\n{plan}"
        if len(msg) > 2000:
            await ch.send(msg[:2000])
        else:
            await ch.send(msg)
    except Exception as e:
        await ch.send(f"📋 **Daily Briefing** — Error: {e}")

scheduler.add_job(morning_prep, "cron", hour=8, minute=0)
scheduler.add_job(daily_briefing, "cron", hour=8, minute=5)

# ---------------------------------------------------------------------------
# Task commands
# ---------------------------------------------------------------------------
@bot.command()
async def add(ctx, *, text: str):
    """Add a task from natural language. Usage: !add finish essay by Friday"""
    await ctx.send("🧠 Parsing...")
    try:
        parsed = parse_task(text)
        t = add_task(
            title=parsed.get("title", text),
            category=parsed.get("category", "personal"),
            priority=parsed.get("priority", "medium"),
            due_date=parsed.get("due_date"),
            estimated_minutes=parsed.get("estimated_minutes"),
            source="discord",
        )
        await ctx.send(f"✅ Added: {format_task(t)}")
    except Exception as e:
        await ctx.send(f"❌ Failed to parse task: {e}")

@bot.command()
async def bulk(ctx, *, text: str):
    """Add multiple tasks. Usage: !bulk then paste your list"""
    await ctx.send("🧠 Parsing bulk tasks...")
    try:
        parsed_list = parse_tasks_bulk(text)
        # Show preview and ask for confirmation
        preview = "\n".join(
            f"• **{t.get('title')}** — {t.get('category', '?')} | "
            f"{t.get('priority', '?')} | due {t.get('due_date') or 'none'} | "
            f"~{t.get('estimated_minutes') or '?'}m"
            for t in parsed_list
        )
        msg = f"📋 **Parsed {len(parsed_list)} tasks:**\n{preview}\n\nReact ✅ to confirm or ❌ to cancel."
        confirm_msg = await ctx.send(msg[:2000])
        await confirm_msg.add_reaction("✅")
        await confirm_msg.add_reaction("❌")

        def check(reaction, user):
            return (
                user == ctx.author
                and str(reaction.emoji) in ("✅", "❌")
                and reaction.message.id == confirm_msg.id
            )

        reaction, _ = await bot.wait_for("reaction_add", timeout=60, check=check)

        if str(reaction.emoji) == "✅":
            tasks = add_tasks_bulk(parsed_list)
            await ctx.send(f"✅ Added {len(tasks)} tasks.")
        else:
            await ctx.send("❌ Cancelled.")
    except TimeoutError:
        await ctx.send("⏰ Timed out — bulk add cancelled.")
    except Exception as e:
        await ctx.send(f"❌ Failed: {e}")

@bot.command()
async def done(ctx, task_id: int):
    """Mark a task complete. Usage: !done 3"""
    t = complete_task(task_id)
    if t:
        await ctx.send(f"✅ Completed: **{t['title']}**")
    else:
        await ctx.send(f"❌ No task found with ID {task_id}")

@bot.command(name="edit")
async def edit_cmd(ctx, task_id: int, field: str, *, value: str):
    """Edit a task field. Usage: !edit 3 priority high"""
    t = edit_task(task_id, **{field: value})
    if t:
        await ctx.send(f"✏️ Updated: {format_task(t)}")
    else:
        await ctx.send(f"❌ Couldn't update. Check the task ID and field name.")

@bot.command(name="delete")
async def delete_cmd(ctx, task_id: int):
    """Delete a task. Usage: !delete 3"""
    if delete_task(task_id):
        await ctx.send(f"🗑️ Deleted task #{task_id}")
    else:
        await ctx.send(f"❌ No task found with ID {task_id}")

@bot.command()
async def tasks(ctx, filter_type: str = "pending"):
    """Show tasks. Usage: !tasks, !tasks done, !tasks all"""
    if filter_type == "done":
        items = get_completed()
        label = "Completed Tasks"
    elif filter_type == "all":
        items = get_pending(include_past=True)
        label = "All Pending Tasks (including past-due)"
    else:
        items = get_pending()
        label = "Pending Tasks"

    if not items:
        await ctx.send(f"📋 **{label}** — None!")
        return

    lines = [format_task(t) for t in items]
    header = f"📋 **{label} ({len(items)}):**\n"

    # Split into multiple messages to stay under 2000 char limit
    current_msg = header
    for line in lines:
        if len(current_msg) + len(line) + 1 > 1900:
            await ctx.send(current_msg)
            current_msg = ""
        current_msg += line + "\n"
    if current_msg.strip():
        await ctx.send(current_msg)

@bot.command()
async def today(ctx):
    """Show tasks due today."""
    items = get_due_within(days=1)
    if not items:
        await ctx.send("📋 **Today** — Nothing due. Nice.")
        return
    lines = [format_task(t) for t in items]
    await ctx.send("📋 **Due Today:**\n" + "\n".join(lines))

@bot.command()
async def week(ctx):
    """Show tasks due within 7 days."""
    items = get_due_within(days=7)
    if not items:
        await ctx.send("📋 **This Week** — All clear.")
        return
    lines = [format_task(t) for t in items]
    header = f"📋 **Due This Week ({len(items)}):**\n"
    current_msg = header
    for line in lines:
        if len(current_msg) + len(line) + 1 > 1900:
            await ctx.send(current_msg)
            current_msg = ""
        current_msg += line + "\n"
    if current_msg.strip():
        await ctx.send(current_msg)

@bot.command()
async def plan(ctx):
    """Generate a time-blocked daily schedule."""
    await ctx.send("🧠 Generating your plan...")
    try:
        items = get_pending()
        if not items:
            await ctx.send("📋 No pending tasks to plan around.")
            return
        schedule = generate_daily_plan(items)
        msg = f"📅 **Today's Plan:**\n{schedule}"
        if len(msg) > 2000:
            await ctx.send(msg[:2000])
        else:
            await ctx.send(msg)
    except Exception as e:
        await ctx.send(f"❌ Failed to generate plan: {e}")

# ---------------------------------------------------------------------------
# Git push (stub)
# ---------------------------------------------------------------------------
@bot.command()
async def push(ctx):
    """Mark current LeetCode problem as complete."""
    try:
        from workflows.prep_pipeline import get_next_pending
        row = get_next_pending()
        if not row:
            await ctx.send("❌ No pending problem to mark complete.")
            return
        mark_complete(row["leetcode_url"])
        await ctx.send(f"✅ Marked **{row['topic']}** problem as complete. Nice work!")
    except Exception as e:
        await ctx.send(f"❌ Failed: {e}")

@bot.command()
async def status(ctx):
    """Show today's prep problem + upcoming deadlines."""
    # TODO: read from prep_roadmap.csv
    items = get_due_within(days=2)
    if items:
        lines = [format_task(t) for t in items]
        await ctx.send("📊 **Status — Upcoming:**\n" + "\n".join(lines))
    else:
        await ctx.send("📊 **Status** — Nothing urgent.")

@bot.command()
async def roadmap(ctx):
    """Show remaining problems in the CSV."""
    summary = get_roadmap_summary()
    if not summary:
        await ctx.send("🗺️ **Roadmap** — No `prep_roadmap.csv` found in data/.")
        return
    pending = summary["pending"]
    complete = summary["complete"]
    lines = [f"🗺️ **Roadmap** — {len(complete)} done, {len(pending)} remaining\n"]
    for row in pending[:10]:  # show next 10
        lines.append(f"⬜ **{row['topic']}** — {row['leetcode_url'].strip()}")
    for row in complete[-5:]:  # show last 5 completed
        lines.append(f"✅ **{row['topic']}** — {row['leetcode_url'].strip()}")
    if len(pending) > 10:
        lines.append(f"\n...and {len(pending) - 10} more pending.")
    await ctx.send("\n".join(lines))
@bot.command()
async def testprep(ctx):
    """Manually trigger morning prep for testing."""
    await ctx.send("🧪 Running morning prep...")
    await morning_prep()
    await ctx.send("🧪 Done.")
# ---------------------------------------------------------------------------
# Attachment handler — syllabus PDF ingestion
# ---------------------------------------------------------------------------
@bot.event
async def on_message(msg):
    await bot.process_commands(msg)

    if msg.author == bot.user:
        return

    if msg.channel.id != SYLLABUS_CHANNEL_ID:
        return

    for attachment in msg.attachments:
        if not attachment.filename.lower().endswith(".pdf"):
            continue

        await msg.channel.send(f"📄 Received **{attachment.filename}** — parsing syllabus...")
        try:
            pdf_bytes = await attachment.read()
            result = ingest_syllabus(pdf_bytes)
            tasks = result["tasks"]
            lines = [
                f"• **{t['title']}** — due {t.get('due_date') or 'TBD'} | "
                f"~{t.get('estimated_minutes') or '?'}m"
                for t in tasks[:15]  # show first 15 to stay under char limit
            ]
            summary = f"✅ Extracted **{result['raw_count']}** tasks from **{attachment.filename}**\n\n"
            summary += "\n".join(lines)
            if result["raw_count"] > 15:
                summary += f"\n\n...and {result['raw_count'] - 15} more. Use `!tasks` to see all."
            if len(summary) > 2000:
                await msg.channel.send(summary[:2000])
            else:
                await msg.channel.send(summary)
        except Exception as e:
            await msg.channel.send(f"❌ Failed to parse syllabus: {e}")
