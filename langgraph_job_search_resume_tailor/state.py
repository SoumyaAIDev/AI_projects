from __future__ import annotations

from typing import Any, TypedDict


class JobSearchState(TypedDict):
    """Shared LangGraph state for the job-search and resume-tailoring flow."""

    master_resume_text: str
    search_keywords: list[str]
    scraped_jobs: list[dict[str, Any]]
    selected_jd_id: str | None
    tailored_resume_markdown: str
    pdf_file_path: str
