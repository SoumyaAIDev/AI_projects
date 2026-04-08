from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from state import JobSearchState
from tools import generate_pdf_from_markdown, insert_jobs_to_postgres, mock_search_jobs


class ResumeAnalysis(BaseModel):
    top_skills: list[str] = Field(description="Most important skills extracted from the resume")
    search_keywords: list[str] = Field(description="Job-search keywords derived from the candidate profile")


def _get_llm() -> ChatOpenAI:
    """Centralized LLM factory so all nodes share the same model settings."""
    return ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=0.2,
    )


def analyze_resume_node(state: JobSearchState) -> dict[str, Any]:
    """Extract top skills and job-search keywords from the master resume."""
    llm = _get_llm().with_structured_output(ResumeAnalysis)

    prompt = f"""
    You are an expert technical recruiter and AI career strategist.

    Analyze the candidate's master resume and return:
    1. The strongest technical and domain skills.
    2. High-signal search keywords for job discovery.

    Keep the keywords specific, recruiter-friendly, and optimized for AI/LLM roles.

    Master resume:
    {state["master_resume_text"]}
    """

    analysis = llm.invoke(prompt)
    deduped_keywords = list(dict.fromkeys(analysis.search_keywords))

    # We keep only the fields declared in graph state to avoid accidental state drift.
    return {"search_keywords": deduped_keywords}


def search_jobs_node(state: JobSearchState) -> dict[str, Any]:
    """Search for relevant jobs using extracted keywords."""
    jobs = mock_search_jobs(state["search_keywords"])
    return {"scraped_jobs": jobs}


def save_to_postgres_node(state: JobSearchState) -> dict[str, Any]:
    """Persist scraped jobs to PostgreSQL and keep DB-generated IDs in state."""
    saved_jobs = insert_jobs_to_postgres(state["scraped_jobs"])

    selected_jd_id = state.get("selected_jd_id")
    if not selected_jd_id and saved_jobs:
        selected_jd_id = saved_jobs[0].get("id")

    return {
        "scraped_jobs": saved_jobs,
        "selected_jd_id": selected_jd_id,
    }


def tailor_resume_node(state: JobSearchState) -> dict[str, Any]:
    """Generate a job-specific tailored resume in markdown format."""
    target_job = _select_target_job(state["scraped_jobs"], state.get("selected_jd_id"))
    llm = _get_llm()

    prompt = f"""
    You are a world-class resume writer for technical AI roles.

    Rewrite the candidate's resume to align strongly with the target job description while staying truthful.
    Do not fabricate employers, projects, dates, metrics, or credentials.
    Emphasize relevant experience, tools, and accomplishments already supported by the master resume.

    Output requirements:
    - Return markdown only.
    - Use this structure exactly:
      # Full Name
      Contact line
      ## Professional Summary
      ## Core Skills
      ## Professional Experience
      ## Projects
      ## Education
    - Use concise, high-impact bullets under experience and projects.
    - Optimize wording for ATS matching using the JD terminology naturally.

    Master resume:
    {state["master_resume_text"]}

    Target job title: {target_job["title"]}
    Target company: {target_job["company"]}
    Target job description:
    {target_job["full_jd"]}
    """

    tailored_resume_markdown = llm.invoke(prompt).content
    return {"tailored_resume_markdown": tailored_resume_markdown}


def generate_pdf_node(state: JobSearchState) -> dict[str, Any]:
    """Generate a PDF file from the tailored resume markdown."""
    target_job = _select_target_job(state["scraped_jobs"], state.get("selected_jd_id"))
    safe_company = _slugify(target_job["company"])
    safe_title = _slugify(target_job["title"])

    output_dir = Path(os.getenv("OUTPUT_DIR", "output"))
    output_path = output_dir / f"tailored_resume_{safe_company}_{safe_title}.pdf"

    pdf_file_path = generate_pdf_from_markdown(
        markdown_text=state["tailored_resume_markdown"],
        output_path=str(output_path),
    )
    return {"pdf_file_path": pdf_file_path}


def _select_target_job(jobs: list[dict[str, Any]], selected_jd_id: str | None) -> dict[str, Any]:
    if not jobs:
        raise ValueError("No jobs are available in state. Run the search and save nodes first.")

    if selected_jd_id:
        for job in jobs:
            if str(job.get("id")) == str(selected_jd_id):
                return job

    return jobs[0]


def _slugify(value: str) -> str:
    sanitized = "".join(char.lower() if char.isalnum() else "_" for char in value)
    return "_".join(part for part in sanitized.split("_") if part)
