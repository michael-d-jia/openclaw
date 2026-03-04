"""
Academic workflow — PDF syllabus ingestion.
Extracts text from PDFs, sends to Gemini for parsing, saves tasks to SQLite.
"""
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pdfplumber
from core.llm import parse_syllabus
from core.task_db import add_tasks_bulk


def extract_text_from_pdf(pdf_bytes):
    """Extract all text from a PDF given its raw bytes."""
    text_pages = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_pages.append(page_text)
    return "\n\n".join(text_pages)


def ingest_syllabus(pdf_bytes):
    """Full pipeline: PDF bytes → text → Gemini parsing → SQLite.
    Returns a dict with 'tasks' (list of saved tasks) and 'raw_count'."""
    # Step 1: Extract text
    text = extract_text_from_pdf(pdf_bytes)
    if not text.strip():
        raise ValueError("Could not extract any text from the PDF.")

    # Step 2: Send to Gemini for structured extraction
    parsed = parse_syllabus(text)
    if not parsed:
        raise ValueError("Gemini did not extract any tasks from the syllabus.")

    # Step 3: Save to database
    for t in parsed:
        t["source"] = "syllabus"

    saved = add_tasks_bulk(parsed)

    return {
        "tasks": saved,
        "raw_count": len(parsed),
    }