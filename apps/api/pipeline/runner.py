"""Pipeline runner entry point discovered by main.py at startup."""

from uuid import UUID

from data.run_repo import get_by_id
from pipeline.langgraph import run_pipeline


async def handle_run(run_id: UUID) -> None:
    """Execute the full pipeline for a given run id."""
    run = await get_by_id(run_id)
    if run is None:
        return
    # Best-effort: delegate to run_pipeline using run metadata.
    await run_pipeline(
        issue_id=run.issue_id,
        repo_name=run.repo_name,
        github_client=None,
        yash_sandbox=None,
        pytest_runner=None,
        llm_analyze=None,
        llm_generate_patch=None,
        apply_patch=None,
        read_file=None,
        repo_structure={},
    )
    return None
