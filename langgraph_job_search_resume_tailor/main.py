from __future__ import annotations

from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

from nodes import (
    analyze_resume_node,
    generate_pdf_node,
    save_to_postgres_node,
    search_jobs_node,
    tailor_resume_node,
)
from state import JobSearchState


def build_graph():
    """Build and compile the sequential LangGraph workflow."""
    graph = StateGraph(JobSearchState)

    graph.add_node("analyze_resume", analyze_resume_node)
    graph.add_node("search_jobs", search_jobs_node)
    graph.add_node("save_to_postgres", save_to_postgres_node)
    graph.add_node("tailor_resume", tailor_resume_node)
    graph.add_node("generate_pdf", generate_pdf_node)

    graph.add_edge(START, "analyze_resume")
    graph.add_edge("analyze_resume", "search_jobs")
    graph.add_edge("search_jobs", "save_to_postgres")
    graph.add_edge("save_to_postgres", "tailor_resume")
    graph.add_edge("tailor_resume", "generate_pdf")
    graph.add_edge("generate_pdf", END)

    return graph.compile()


def create_initial_state(
    master_resume_text: str,
    selected_jd_id: str | None = None,
) -> JobSearchState:
    """Create a valid initial state object for the workflow."""
    return {
        "master_resume_text": master_resume_text,
        "search_keywords": [],
        "scraped_jobs": [],
        "selected_jd_id": selected_jd_id,
        "tailored_resume_markdown": "",
        "pdf_file_path": "",
    }


def run_job_discovery(state: JobSearchState) -> JobSearchState:
    """Run the discovery portion of the workflow for interactive frontends."""
    working_state = dict(state)
    working_state.update(analyze_resume_node(working_state))
    working_state.update(search_jobs_node(working_state))
    working_state.update(save_to_postgres_node(working_state))
    return working_state  # type: ignore[return-value]


def run_tailoring_and_pdf(state: JobSearchState) -> JobSearchState:
    """Run the tailoring and PDF generation steps for a selected job."""
    working_state = dict(state)
    working_state.update(tailor_resume_node(working_state))
    working_state.update(generate_pdf_node(working_state))
    return working_state  # type: ignore[return-value]


def run_full_workflow(state: JobSearchState) -> JobSearchState:
    """Run the end-to-end compiled graph."""
    return build_graph().invoke(state)


if __name__ == "__main__":
    load_dotenv()
    sample_resume = """
    Alex Morgan
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
    B.S. in Computer Science
    """

    initial_state = create_initial_state(master_resume_text=sample_resume)
    final_state = run_full_workflow(initial_state)

    print("Search keywords:", final_state["search_keywords"])
    print("Saved jobs:", len(final_state["scraped_jobs"]))
    print("Selected job ID:", final_state["selected_jd_id"])
    print("PDF generated at:", final_state["pdf_file_path"])
