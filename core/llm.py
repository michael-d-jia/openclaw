"""
Gemini API wrapper — all LLM calls go through here.
Loads prompt templates from prompts/ and exposes one function per use case.
Uses the new google-genai SDK.
"""
import os
import json
import time
from datetime import date, datetime
from pathlib import Path
from google import genai
from google.genai import types

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
MODEL = "gemini-2.5-flash"

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

def _load_prompt(name):
    text = (PROMPTS_DIR / name).read_text().strip()
    return text.replace("{{TODAY}}", date.today().isoformat())

def _call(prompt, temperature=0.3, retries=3):
    """Low-level call with retry. Returns raw text response."""
    for attempt in range(retries):
        try:
            resp = client.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=temperature),
            )
            return resp.text.strip()
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)  # 1s, 2s, 4s backoff
                continue
            raise RuntimeError(f"Gemini API failed after {retries} attempts: {e}")

def _call_json(prompt, temperature=0.2):
    """Call Gemini and parse the response as JSON.
    Strips markdown fences if Gemini wraps them. Retries once on parse failure."""
    for attempt in range(2):
        raw = _call(prompt, temperature=temperature)
        clean = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            if attempt == 0:
                continue  # retry — Gemini sometimes adds stray text
            raise ValueError(f"Gemini returned invalid JSON after 2 attempts. Raw response:\n{raw[:500]}")

# ---------------------------------------------------------------------------
# Use case: Parse a single task from natural language
# ---------------------------------------------------------------------------
def parse_task(user_input):
    """Takes a raw string like 'finish essay by Friday, pretty important'
    and returns a dict with: title, category, priority, due_date,
    estimated_minutes."""
    template = _load_prompt("parse_task.txt")
    prompt = template.replace("{{USER_INPUT}}", user_input)
    return _call_json(prompt)

# ---------------------------------------------------------------------------
# Use case: Parse bulk tasks
# ---------------------------------------------------------------------------
def parse_tasks_bulk(user_input):
    """Takes a pasted block of multiple tasks and returns a list of dicts."""
    template = _load_prompt("parse_task_bulk.txt")
    prompt = template.replace("{{USER_INPUT}}", user_input)
    return _call_json(prompt)

# ---------------------------------------------------------------------------
# Use case: Generate daily plan
# ---------------------------------------------------------------------------
def generate_daily_plan(tasks):
    """Takes a list of task dicts, returns a formatted daily schedule string."""
    template = _load_prompt("daily_plan.txt")
    now = datetime.now()
    prompt = (
        template
        .replace("{{TASKS_JSON}}", json.dumps(tasks, indent=2))
        .replace("{{CURRENT_TIME}}", now.strftime("%I:%M %p"))
        .replace("{{DAY_OF_WEEK}}", now.strftime("%A"))
    )
    return _call(prompt, temperature=0.4)

# ---------------------------------------------------------------------------
# Use case: Parse syllabus PDF text into tasks
# ---------------------------------------------------------------------------
def parse_syllabus(pdf_text):
    """Takes extracted PDF text and returns a list of task dicts."""
    template = _load_prompt("syllabus_extract.txt")
    prompt = template.replace("{{PDF_TEXT}}", pdf_text)
    return _call_json(prompt)

# ---------------------------------------------------------------------------
# Use case: Generate LeetCode problem file
# ---------------------------------------------------------------------------
def generate_leetcode_file(problem_title, problem_description, topic):
    """Takes a LeetCode problem and returns a Python file string with
    docstring, function signature, and test boilerplate."""
    template = _load_prompt("leetcode_gen.txt")
    prompt = (
        template
        .replace("{{TITLE}}", problem_title)
        .replace("{{DESCRIPTION}}", problem_description)
        .replace("{{TOPIC}}", topic)
    )
    return _call(prompt, temperature=0.2)