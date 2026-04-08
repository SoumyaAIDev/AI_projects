from __future__ import annotations

from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from main import create_initial_state, run_job_discovery, run_tailoring_and_pdf
from state import JobSearchState


load_dotenv()

st.set_page_config(
    page_title="ResumePilot AI",
    page_icon=":briefcase:",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _default_resume() -> str:
    return """Alex Morgan
alex.morgan@email.com | linkedin.com/in/alexmorgan | github.com/alexmorgan

SUMMARY
Python AI Engineer with 7+ years of experience building production ML platforms,
LLM applications, retrieval systems, and workflow automation products.

EXPERIENCE
Senior Machine Learning Engineer, InnovateAI
- Built multi-agent orchestration pipelines in Python for internal knowledge automation.
- Developed LLM applications using LangChain, vector databases, PostgreSQL, and FastAPI.
- Improved document retrieval quality through prompt iteration and evaluation loops.

AI Solutions Engineer, DataCloud Labs
- Created resume parsing and job matching services for recruiting workflows.
- Integrated external APIs, SQL databases, and analytics dashboards.
- Shipped production backend services with strong observability and testing practices.

PROJECTS
- Built an autonomous research assistant using LangGraph and OpenAI models.
- Created PDF reporting workflows for business users using Python automation.

EDUCATION
B.S. in Computer Science"""


def _bootstrap_session_state() -> None:
    st.session_state.setdefault("workflow_state", None)
    st.session_state.setdefault("selected_job_label", None)


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(222, 244, 228, 0.9), transparent 28%),
                radial-gradient(circle at top right, rgba(255, 236, 214, 0.85), transparent 30%),
                linear-gradient(180deg, #f8faf7 0%, #eef3ea 100%);
        }
        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 2.5rem;
            max-width: 1240px;
        }
        .hero-card {
            padding: 1.6rem 1.8rem;
            border-radius: 24px;
            background: linear-gradient(135deg, #0f3d2e 0%, #1f6b4f 58%, #d9a441 100%);
            color: #f9fbf8;
            box-shadow: 0 18px 45px rgba(25, 60, 41, 0.18);
            margin-bottom: 1rem;
        }
        .hero-kicker {
            text-transform: uppercase;
            letter-spacing: 0.12em;
            font-size: 0.78rem;
            opacity: 0.88;
            margin-bottom: 0.55rem;
            font-weight: 600;
        }
        .hero-title {
            font-size: 2.2rem;
            font-weight: 800;
            line-height: 1.1;
            margin-bottom: 0.65rem;
        }
        .hero-copy {
            font-size: 1rem;
            max-width: 720px;
            opacity: 0.94;
        }
        .panel {
            background: rgba(255, 255, 255, 0.82);
            border: 1px solid rgba(15, 61, 46, 0.08);
            border-radius: 20px;
            padding: 1.1rem 1.1rem 0.7rem 1.1rem;
            box-shadow: 0 10px 30px rgba(31, 57, 43, 0.06);
            backdrop-filter: blur(10px);
        }
        .section-title {
            font-size: 1.05rem;
            font-weight: 700;
            color: #123524;
            margin-bottom: 0.35rem;
        }
        .muted {
            color: #4d6659;
            font-size: 0.95rem;
        }
        .metric-card {
            background: rgba(255, 255, 255, 0.88);
            border: 1px solid rgba(18, 53, 36, 0.08);
            border-radius: 18px;
            padding: 0.9rem 1rem;
            box-shadow: 0 10px 25px rgba(31, 57, 43, 0.05);
        }
        .metric-label {
            color: #5b6f64;
            font-size: 0.82rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 0.35rem;
        }
        .metric-value {
            color: #102f22;
            font-size: 1.45rem;
            font-weight: 800;
        }
        .job-card {
            background: rgba(255, 255, 255, 0.92);
            border: 1px solid rgba(18, 53, 36, 0.09);
            border-radius: 20px;
            padding: 1rem 1.1rem;
            box-shadow: 0 12px 28px rgba(31, 57, 43, 0.06);
        }
        .job-title {
            font-size: 1.25rem;
            font-weight: 800;
            color: #112f21;
            margin-bottom: 0.2rem;
        }
        .job-meta {
            color: #567062;
            margin-bottom: 0.85rem;
        }
        .chip-wrap {
            display: flex;
            flex-wrap: wrap;
            gap: 0.45rem;
            margin-top: 0.55rem;
            margin-bottom: 0.35rem;
        }
        .chip {
            display: inline-block;
            padding: 0.28rem 0.58rem;
            border-radius: 999px;
            background: #e8f1eb;
            color: #234b36;
            font-size: 0.84rem;
            font-weight: 600;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _job_label(job: dict) -> str:
    job_id = str(job.get("id", "pending"))
    return f'{job["title"]} at {job["company"]} [{job_id[:8]}]'


def _job_id_from_label(jobs: list[dict], label: str) -> str | None:
    for job in jobs:
        if _job_label(job) == label:
            return str(job.get("id"))
    return None


def _render_hero() -> None:
    st.markdown(
        """
        <div class="hero-card">
            <div class="hero-kicker">Multi-Agent Job Search Studio</div>
            <div class="hero-title">ResumePilot AI</div>
            <div class="hero-copy">
                Turn a master resume into a targeted application flow: extract search intent,
                discover matching AI roles, save job data to PostgreSQL, and generate a polished
                tailored PDF resume for the role you actually want.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_metric_card(label: str, value: str) -> None:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_job_card(job: dict) -> None:
    st.markdown(
        f"""
        <div class="job-card">
            <div class="job-title">{job['title']}</div>
            <div class="job-meta">{job['company']} | <a href="{job['url']}" target="_blank">Open listing</a></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write(job["full_jd"])


def _render_keyword_chips(keywords: list[str]) -> None:
    chips = "".join(f'<span class="chip">{keyword}</span>' for keyword in keywords)
    st.markdown(f'<div class="chip-wrap">{chips}</div>', unsafe_allow_html=True)


def _render_download(path: str) -> None:
    pdf_path = Path(path)
    if not pdf_path.exists():
        st.warning("The PDF path was generated, but the file could not be found on disk.")
        return

    with pdf_path.open("rb") as pdf_file:
        st.download_button(
            label="Download tailored PDF resume",
            data=pdf_file.read(),
            file_name=pdf_path.name,
            mime="application/pdf",
            use_container_width=True,
            type="primary",
        )


def _render_sidebar(workflow_state: JobSearchState | None) -> None:
    with st.sidebar:
        st.markdown("## Control Center")
        st.caption("Guided workflow for resume analysis, job matching, and resume export.")
        st.markdown("---")
        st.markdown("### Flow")
        st.write("1. Add the master resume")
        st.write("2. Discover matching jobs")
        st.write("3. Select a target role")
        st.write("4. Generate and download the PDF")
        st.markdown("---")
        st.markdown("### Status")
        if workflow_state:
            st.success(f"{len(workflow_state['scraped_jobs'])} jobs in session")
            st.info(f"{len(workflow_state['search_keywords'])} search keywords extracted")
            if workflow_state.get("pdf_file_path"):
                st.success("Tailored PDF ready")
        else:
            st.warning("No active session yet")


def main() -> None:
    _bootstrap_session_state()
    _inject_styles()

    workflow_state: JobSearchState | None = st.session_state.workflow_state
    _render_sidebar(workflow_state)
    _render_hero()

    top_left, top_right = st.columns([1.45, 0.8], gap="large")

    with top_left:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Candidate Workspace</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="muted">Paste the full master resume so the tailoring step stays accurate and truthful.</div>',
            unsafe_allow_html=True,
        )
        resume_text = st.text_area(
            "Master Resume",
            value=_default_resume(),
            height=380,
            label_visibility="collapsed",
            help="Include your full resume content, including experience, projects, and education.",
        )
        discover_clicked = st.button(
            "Discover matching jobs",
            type="primary",
            use_container_width=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

    with top_right:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">What This App Does</div>', unsafe_allow_html=True)
        st.markdown(
            """
            <div class="muted">
                This frontend sits on top of your LangGraph workflow and turns it into an
                interactive recruiter-style cockpit.
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("")
        st.write("Resume analysis extracts high-signal search keywords.")
        st.write("Job discovery uses the current mock search layer.")
        st.write("PostgreSQL stores each job and returns a database ID.")
        st.write("Resume tailoring rewrites the profile for a selected role.")
        st.write("PDF export produces a clean downloadable resume file.")
        st.markdown("</div>", unsafe_allow_html=True)

    if discover_clicked:
        if not resume_text.strip():
            st.error("Add the master resume text before running the workflow.")
        else:
            with st.spinner("Analyzing the resume, discovering jobs, and saving them to PostgreSQL..."):
                initial_state = create_initial_state(master_resume_text=resume_text)
                st.session_state.workflow_state = run_job_discovery(initial_state)
                refreshed_state = st.session_state.workflow_state
                if refreshed_state["scraped_jobs"]:
                    st.session_state.selected_job_label = _job_label(refreshed_state["scraped_jobs"][0])
                workflow_state = refreshed_state

    workflow_state = st.session_state.workflow_state
    if not workflow_state:
        return

    st.markdown("")
    metric_cols = st.columns(3, gap="medium")
    with metric_cols[0]:
        _render_metric_card("Jobs Found", str(len(workflow_state["scraped_jobs"])))
    with metric_cols[1]:
        _render_metric_card("Keywords", str(len(workflow_state["search_keywords"])))
    with metric_cols[2]:
        export_status = "Ready" if workflow_state.get("pdf_file_path") else "Pending"
        _render_metric_card("PDF Export", export_status)

    st.markdown("")
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Search Signals</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="muted">These are the keywords your analysis node extracted from the master resume.</div>',
        unsafe_allow_html=True,
    )
    _render_keyword_chips(workflow_state["search_keywords"])
    st.markdown("</div>", unsafe_allow_html=True)

    jobs = workflow_state["scraped_jobs"]
    if not jobs:
        st.warning("No jobs were returned by the search step.")
        return

    st.markdown("")
    browse_col, details_col = st.columns([0.95, 1.35], gap="large")

    with browse_col:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Target Role</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="muted">Choose the role you want the system to optimize for.</div>',
            unsafe_allow_html=True,
        )
        job_options = [_job_label(job) for job in jobs]
        selected_label = st.radio(
            "Choose a target job",
            options=job_options,
            index=job_options.index(st.session_state.selected_job_label)
            if st.session_state.selected_job_label in job_options
            else 0,
            label_visibility="collapsed",
        )
        st.session_state.selected_job_label = selected_label
        selected_job_id = _job_id_from_label(jobs, selected_label)
        generate_clicked = st.button(
            "Generate tailored resume PDF",
            use_container_width=True,
            type="primary",
        )
        st.markdown("</div>", unsafe_allow_html=True)

        if generate_clicked:
            with st.spinner("Tailoring the resume and generating the PDF..."):
                workflow_state["selected_jd_id"] = selected_job_id
                st.session_state.workflow_state = run_tailoring_and_pdf(workflow_state)
                workflow_state = st.session_state.workflow_state

    with details_col:
        selected_job = next(
            job for job in jobs if _job_label(job) == st.session_state.selected_job_label
        )
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Job Brief</div>', unsafe_allow_html=True)
        _render_job_card(selected_job)
        st.markdown("</div>", unsafe_allow_html=True)

    if workflow_state.get("tailored_resume_markdown"):
        st.markdown("")
        preview_col, export_col = st.columns([1.45, 0.8], gap="large")

        with preview_col:
            st.markdown('<div class="panel">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">Tailored Resume Preview</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="muted">Review the rewritten markdown before you send the application.</div>',
                unsafe_allow_html=True,
            )
            st.markdown(workflow_state["tailored_resume_markdown"])
            st.markdown("</div>", unsafe_allow_html=True)

        with export_col:
            st.markdown('<div class="panel">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">Export Center</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="muted">Your PDF has been generated locally and is ready to download.</div>',
                unsafe_allow_html=True,
            )
            st.code(workflow_state["pdf_file_path"], language="text")
            _render_download(workflow_state["pdf_file_path"])
            st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
