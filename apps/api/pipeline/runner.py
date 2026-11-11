"""Pipeline runner entry point discovered by main.py at startup."""

from main import app
from pipeline.github_client import client_for, default_client
from pipeline.sandbox import clone_and_test_async

NEED_MORE_INFO = (
    "Thanks for reporting. To reproduce this automatically I need concrete "
    "reproduction steps (input, expected vs actual). Could you add them?"
)
NOT_AVAILABLE = "diagnosis not available in this build"

from uuid import UUID

from data.run_repo import RunRepo
from schemas import PipelineStep, RunStatus, RunStep, StepStatus


def _repo() -> RunRepo:
    return app.state.run_repo


async def handle_run(run_id: UUID) -> None:
    repo = _repo()
    run = repo.get_by_id(run_id)
    if run is None:
        return

    # Read step
    read_step = RunStep(run_id=run.id, step=PipelineStep.read, status=StepStatus.running)
    repo.add_step(read_step)

    thin = "Steps to reproduce" not in (run.issue_body or "")
    if thin:
        try:
            client = client_for(run.installation_id, run.repository_full_name)
            await client.add_issue_comment(run.issue_number, NEED_MORE_INFO)
            read_step = read_step.model_copy(update={"status": StepStatus.completed, "output": "comment posted"})
        except Exception as exc:
            read_step = read_step.model_copy(update={"status": StepStatus.completed, "output": f"comment not posted ({type(exc).__name__})"})
        repo.update_step(read_step)
        repo.update_status(run.id, RunStatus.could_not_reproduce)
        return

    read_step = read_step.model_copy(update={"status": StepStatus.completed, "output": "issue fetched"})
    repo.update_step(read_step)

    # Reproduce step
    repro_step = RunStep(run_id=run.id, step=PipelineStep.reproduce, status=StepStatus.running)
    repo.add_step(repro_step)
    from pipeline.sandbox import repository_url, SandboxConfig

    try:
        result, _ = await clone_and_test_async(
            repository_url(run.repository_full_name),
            SandboxConfig(timeout_seconds=300),
            f"bfa-{run.issue_number}-repro",
        )
    except Exception as exc:
        repro_step = repro_step.model_copy(update={"status": StepStatus.failed, "error": "reproduction failed - environment issue"})
        repo.update_step(repro_step)
        repo.update_status(run.id, RunStatus.failed)
        return

    if getattr(result, "environment_error", False) or getattr(result, "timed_out", False):
        repro_step = repro_step.model_copy(update={"status": StepStatus.failed, "error": "reproduction failed - environment issue"})
        repo.update_step(repro_step)
        repo.update_status(run.id, RunStatus.failed)
        return

    repo.update_status(run.id, RunStatus.pending)  # noop-ish
    repo.update_step(repro_step.model_copy(update={"status": StepStatus.completed}))
    # store test output on run via update_status fields? Run has test_output
    try:
        repo.update_status(run.id, RunStatus.reproducing, test_output=result.stdout)
    except Exception:
        pass

    # Diagnose step (not available)
    diag_step = RunStep(run_id=run.id, step=PipelineStep.diagnose, status=StepStatus.running)
    repo.add_step(diag_step)
    diag_step = diag_step.model_copy(update={"status": StepStatus.failed, "error": NOT_AVAILABLE})
    repo.update_step(diag_step)
    repo.update_status(run.id, RunStatus.failed)
    return
