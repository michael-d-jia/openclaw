"""
Technical interview prep pipeline.
Reads the roadmap CSV, fetches LeetCode problems, generates starter files,
and pushes to GitHub.
"""
import csv
import re
import html
import subprocess
import requests
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.llm import generate_leetcode_file

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DATA_DIR = Path(__file__).parent.parent / "data"
CSV_PATH = DATA_DIR / "prep_roadmap.csv"
OUTPUT_DIR = DATA_DIR / "leetcode_solutions"

# Ensure output dir exists
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------
def git_commit_and_push(filepath, message):
    """Stage a file, commit, and push. Runs from the project root."""
    root = Path(__file__).parent.parent
    try:
        subprocess.run(["git", "add", str(filepath)], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", message], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "push"], cwd=root, check=True, capture_output=True)
        return True, None
    except subprocess.CalledProcessError as e:
        return False, e.stderr.decode().strip()

# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------
def get_next_pending():
    """Return the first row where status == 'Pending', or None."""
    if not CSV_PATH.exists():
        return None
    with open(CSV_PATH, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["status"].strip().lower() == "pending":
                return row
    return None

def mark_complete(leetcode_url):
    """Set status to 'Complete' for the row matching this URL."""
    if not CSV_PATH.exists():
        return
    rows = []
    with open(CSV_PATH, newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            if row["leetcode_url"].strip() == leetcode_url.strip():
                row["status"] = "Complete"
            rows.append(row)
    with open(CSV_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

def get_roadmap_summary():
    """Return a summary of pending/complete counts and next few problems."""
    if not CSV_PATH.exists():
        return None
    pending, complete = [], []
    with open(CSV_PATH, newline="") as f:
        for row in csv.DictReader(f):
            if row["status"].strip().lower() == "complete":
                complete.append(row)
            else:
                pending.append(row)
    return {"pending": pending, "complete": complete}

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
    Returns dict with 'title', 'description' (plain text), 'slug'."""
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

    # Convert HTML content to plain text (strip tags)
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
def generate_problem_file(problem, topic):
    """Call Gemini to generate a Python starter file. Returns (filepath, content)."""
    content = generate_leetcode_file(
        problem_title=problem["title"],
        problem_description=problem["description"],
        topic=topic,
    )
    filename = f"{problem['slug'].replace('-', '_')}.py"
    filepath = OUTPUT_DIR / filename
    filepath.write_text(content)
    return filepath, content

# ---------------------------------------------------------------------------
# Main pipeline — called by cron or manually
# ---------------------------------------------------------------------------
def run_morning_prep():
    """Full morning prep flow. Returns a dict with results for Discord, or None."""
    row = get_next_pending()
    if not row:
        return None

    problem = fetch_problem(row["leetcode_url"])
    filepath, _ = generate_problem_file(problem, row["topic"])

    # Auto-commit and push the generated file to GitHub
    success, error = git_commit_and_push(
        filepath,
        f"Add starter: {problem['title']} ({row['topic']})"
    )

    return {
        "title": problem["title"],
        "difficulty": problem["difficulty"],
        "topic": row["topic"],
        "url": row["leetcode_url"].strip(),
        "filepath": str(filepath),
        "slug": problem["slug"],
        "pushed": success,
        "push_error": error,
    }