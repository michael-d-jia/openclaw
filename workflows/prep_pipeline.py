"""
Technical interview prep pipeline.
Reads from Google Sheets, fetches LeetCode problems, generates starter files,
and pushes to GitHub.
"""
import re
import html
import subprocess
import requests
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.llm import generate_leetcode_file
from workflows.sheets_client import get_next_problem

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DATA_DIR = Path(__file__).parent.parent / "data"
OUTPUT_DIR = DATA_DIR / "leetcode_solutions"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------
def git_commit_and_push(filepath, message):
    """Stage a file, commit, and push from the leetcode_solutions directory."""
    try:
        subprocess.run(["git", "pull", "--rebase"], cwd=OUTPUT_DIR, check=True, capture_output=True)
        subprocess.run(["git", "add", filepath.name], cwd=OUTPUT_DIR, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", message], cwd=OUTPUT_DIR, check=True, capture_output=True)
        subprocess.run(["git", "push", "-u", "origin", "main"], cwd=OUTPUT_DIR, check=True, capture_output=True)
        return True, None
    except subprocess.CalledProcessError as e:
        return False, e.stderr.decode().strip()

# ---------------------------------------------------------------------------
# LeetCode GraphQL fetcher
# ---------------------------------------------------------------------------
LEETCODE_GRAPHQL = "https://leetcode.com/graphql"

def _slug_from_url(url):
    """Extract problem slug from a LeetCode URL.
    e.g. https://leetcode.com/problems/two-sum/ → two-sum"""
    match = re.search(r"/problems/([^/]+)", url)
    return match.group(1) if match else None

def fetch_problem(url):
    """Fetch problem title and description from LeetCode GraphQL API.
    Returns dict with 'title', 'description' (plain text), 'difficulty', 'slug'."""
    slug = _slug_from_url(url)
    if not slug:
        raise ValueError(f"Could not extract problem slug from URL: {url}")

    query = """
    query getQuestionDetail($titleSlug: String!) {
        question(titleSlug: $titleSlug) {
            title
            content
            difficulty
        }
    }
    """
    resp = requests.post(
        LEETCODE_GRAPHQL,
        json={"query": query, "variables": {"titleSlug": slug}},
        headers={"Content-Type": "application/json"},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    question = data.get("data", {}).get("question")
    if not question:
        raise ValueError(f"Problem not found: {slug}")

    raw_html = question["content"] or ""
    clean = re.sub(r"<[^>]+>", "", raw_html)
    clean = html.unescape(clean)

    return {
        "title": question["title"],
        "description": clean.strip(),
        "difficulty": question.get("difficulty", "Unknown"),
        "slug": slug,
    }

# ---------------------------------------------------------------------------
# File generation
# ---------------------------------------------------------------------------
def generate_problem_file(problem, category):
    """Call Gemini to generate a Java starter file. Returns (filepath, content, is_new)."""
    filename = f"{problem['slug'].replace('-', '_')}.java"
    filepath = OUTPUT_DIR / filename

    if filepath.exists():
        return filepath, filepath.read_text(), False

    content = generate_leetcode_file(
        problem_title=problem["title"],
        problem_description=problem["description"],
        topic=category,
    )
    filepath.write_text(content)
    return filepath, content, True

# ---------------------------------------------------------------------------
# Main pipeline — called by cron or manually
# ---------------------------------------------------------------------------
def run_morning_prep():
    """Full morning prep flow. Returns a dict with results for Discord, or None."""
    row = get_next_problem()
    if not row:
        return None

    problem = fetch_problem(row["URL"])
    filepath, _, is_new = generate_problem_file(problem, row["Category"])

    success, error = True, None
    if is_new:
        success, error = git_commit_and_push(
            filepath,
            f"Add starter: {problem['title']} ({row['Category']})"
        )

    return {
        "title": problem["title"],
        "difficulty": problem["difficulty"],
        "category": row["Category"],
        "url": row["URL"].strip(),
        "filepath": str(filepath),
        "slug": problem["slug"],
        "pushed": success,
        "push_error": error,
        "is_new": is_new,
        "video_url": row.get("Video URL", "").strip() or None,
        "why": row.get("Why This Problem", "").strip() or None,
    }
