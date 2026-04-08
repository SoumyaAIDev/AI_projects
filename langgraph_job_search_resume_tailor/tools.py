from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import psycopg
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from psycopg.rows import dict_row


def get_postgres_connection() -> psycopg.Connection:
    """Create a PostgreSQL connection from environment variables."""
    database_url = os.getenv("DATABASE_URL")

    if database_url:
        return psycopg.connect(database_url, row_factory=dict_row)

    pg_host = os.getenv("PGHOST")
    pg_port = os.getenv("PGPORT", "5432")
    pg_database = os.getenv("PGDATABASE")
    pg_user = os.getenv("PGUSER")
    pg_password = os.getenv("PGPASSWORD")

    if not all([pg_host, pg_database, pg_user, pg_password]):
        raise ValueError(
            "Missing PostgreSQL credentials. Set DATABASE_URL or PGHOST, PGPORT, "
            "PGDATABASE, PGUSER, and PGPASSWORD."
        )

    return psycopg.connect(
        host=pg_host,
        port=pg_port,
        dbname=pg_database,
        user=pg_user,
        password=pg_password,
        row_factory=dict_row,
    )


def insert_jobs_to_postgres(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Insert job records into PostgreSQL and return inserted rows with database IDs."""
    if not jobs:
        return []

    query = """
        insert into public.jobs (title, company, url, full_jd)
        values (%(title)s, %(company)s, %(url)s, %(full_jd)s)
        on conflict (url) do update
        set
            title = excluded.title,
            company = excluded.company,
            full_jd = excluded.full_jd
        returning id, title, company, url, full_jd, created_at;
    """

    with get_postgres_connection() as connection:
        with connection.cursor() as cursor:
            cursor.executemany(query, jobs, returning=True)
            inserted_rows = []
            while True:
                row = cursor.fetchone()
                if row is None:
                    break
                inserted_rows.append(row)

        connection.commit()

    rows_by_url = {str(row["url"]): row for row in inserted_rows}

    merged_jobs: list[dict[str, Any]] = []
    for job in jobs:
        db_row = rows_by_url.get(job["url"], {})
        merged_jobs.append({**job, **db_row})

    return merged_jobs


def mock_search_jobs(keywords: list[str]) -> list[dict[str, Any]]:
    """Mock job scraper used so graph logic can be developed without live scraping."""
    keyword_text = ", ".join(keywords[:5]) if keywords else "Python, LangChain, LangGraph"

    return [
        {
            "title": "Senior AI Engineer",
            "company": "Nimbus Labs",
            "url": "https://jobs.example.com/nimbus-senior-ai-engineer",
            "full_jd": (
                "We are hiring a Senior AI Engineer to build multi-agent systems using Python, "
                "LangChain, LangGraph, retrieval pipelines, and production LLM integrations. "
                f"Strong fit areas include: {keyword_text}. Experience with PostgreSQL, "
                "API design, evaluation, and resume/domain-specific workflow automation is preferred."
            ),
        },
        {
            "title": "Applied LLM Engineer",
            "company": "VertexWorks",
            "url": "https://jobs.example.com/vertexworks-applied-llm-engineer",
            "full_jd": (
                "Looking for an Applied LLM Engineer who can design job-matching agents, build "
                "robust orchestration graphs, integrate vector and relational stores, and ship "
                "candidate-facing resume tailoring features. Must be strong in Python, prompt "
                "engineering, structured outputs, and backend architecture."
            ),
        },
        {
            "title": "AI Automation Developer",
            "company": "BrightPath Careers",
            "url": "https://jobs.example.com/brightpath-ai-automation-developer",
            "full_jd": (
                "Seeking an AI Automation Developer to create workflows that ingest resumes, "
                "search relevant jobs, persist job data, and generate polished PDF resumes. "
                "Experience with tool calling, SQL-backed apps, and candidate personalization "
                "is highly valued."
            ),
        },
    ]


def generate_pdf_from_markdown(markdown_text: str, output_path: str) -> str:
    """Render simple resume markdown into a clean PDF using ReportLab."""
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    styles = getSampleStyleSheet()
    base_style = ParagraphStyle(
        name="ResumeBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=10.5,
        leading=14,
        alignment=TA_LEFT,
        spaceAfter=8,
        textColor=colors.HexColor("#1A1A1A"),
    )
    heading_style = ParagraphStyle(
        name="ResumeHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#0F172A"),
        spaceBefore=10,
        spaceAfter=8,
        borderPadding=0,
    )
    title_style = ParagraphStyle(
        name="ResumeTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#111827"),
        spaceAfter=14,
    )

    story = []
    lines = [line.rstrip() for line in markdown_text.splitlines()]

    bullet_buffer: list[str] = []

    def flush_bullets() -> None:
        nonlocal bullet_buffer
        for bullet in bullet_buffer:
            safe_bullet = _escape_text(bullet)
            story.append(Paragraph(f"&bull; {safe_bullet}", base_style))
        bullet_buffer = []

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            flush_bullets()
            story.append(Spacer(1, 0.08 * inch))
            continue

        if line.startswith("# "):
            flush_bullets()
            story.append(Paragraph(_escape_text(line[2:].strip()), title_style))
            continue

        if line.startswith("## "):
            flush_bullets()
            story.append(Paragraph(_escape_text(line[3:].strip()), heading_style))
            continue

        if line.startswith("- "):
            bullet_buffer.append(_inline_markdown_to_reportlab(line[2:].strip()))
            continue

        flush_bullets()
        story.append(Paragraph(_inline_markdown_to_reportlab(line), base_style))

    flush_bullets()

    doc = SimpleDocTemplate(
        str(output_file),
        pagesize=LETTER,
        rightMargin=0.7 * inch,
        leftMargin=0.7 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.7 * inch,
    )
    doc.build(story)
    return str(output_file.resolve())


def _escape_text(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _inline_markdown_to_reportlab(text: str) -> str:
    """Translate a minimal markdown subset into ReportLab paragraph markup."""
    escaped = _escape_text(text)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"\*(.+?)\*", r"<i>\1</i>", escaped)
    escaped = re.sub(r"`(.+?)`", r"<font name='Courier'>\1</font>", escaped)
    return escaped
