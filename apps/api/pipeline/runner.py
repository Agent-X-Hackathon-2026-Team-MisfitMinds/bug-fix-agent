"""Pipeline runner entry point discovered by main.py at startup."""

from uuid import UUID

from main import app
from data.run_repo import RunRepo
from pipeline.github_client import client_for
from pipeline.sandbox import clone_and_test_async
from schemas import PipelineStep, RunStatus, RunStep, StepStatus

NEED_MORE_INFO = (
    "Thanks for reporting. To reproduce this automatically I need concrete "
    "reproduction steps (input, expected vs actual). Could you add them?"
)
NOT_AVAILABLE = "diagnosis not available in this build"


def _repo() -> RunRepo:
    return app.state.run_repo


async def handle_run(run_id: UUID) -> None:
    repo = _repo()
    run = repo.get_by_id(run_id)
    if run is None:
        return

    read_step = RunStep(run_id=run.id, step=PipelineStep.read, status=StepStatus.running)
    repo.add_step(read_step)

    thin = "Steps to reproduce" not in (run.issue_body or "")
    if thin:
        try:
            client = client_for(run.installation_id, run.repository_full_name)
            await client.add_issue_comment(run.issue_number, NEED_MORE_INFO)
            read_step = read_step.model_copy(update={"status": StepStatus.completed, "output": "comment posted"})
        except Exception:
            read_step = read_step.model_copy(update={"status": StepStatus.completed, "output": "comment not posted (RuntimeError)"})
        repo.update_step(read_step)
        repo.update_status(run.id, RunStatus.could_not_reproduce)
        return

    read_step = read_step.model_copy(update={"status": StepStatus.completed, "output": "issue fetched"})
    repo.update_step(read_step)

    repro_step = RunStep(run_id=run.id, step=PipelineStep.reproduce, status=StepStatus.running)
    repo.add_step(repro_step)

    from pipeline.sandbox import repository_url, SandboxConfig

    try:
        result, _ = await clone_and_test_async(
            repository_url(run.repository_full_name),
            SandboxConfig(timeout_seconds=300),
            f"bfa-{run.issue_number}-repro",
        )
    except Exception:
        repro_step = repro_step.model_copy(update={"status": StepStatus.failed, "error": "reproduction failed - environment issue"})
        repo.update_step(repro_step)
        repo.update_status(run.id, RunStatus.failed)
        return

    if getattr(result, "environment_error", False) or getattr(result, "timed_out", False):
        repro_step = repro_step.model_copy(update={"status": StepStatus.failed, "error": "reproduction failed - environment issue"})
        repo.update_step(repro_step)
        repo.update_status(run.id, RunStatus.failed)
        return

    repro_step = repro_step.model_copy(update={"status": StepStatus.completed})
    repo.update_step(repro_step)
    try:
        repo.update_status(run.id, RunStatus.reproducing, test_output=result.stdout)
    except Exception:
        pass

    diag_step = RunStep(run_id=run.id, step=PipelineStep.diagnose, status=StepStatus.running)
    repo.add_step(diag_step)
    diag_step = diag_step.model_copy(update={"status": StepStatus.failed, "error": NOT_AVAILABLE})
    repo.update_step(diag_step)
    repo.update_status(run.id, RunStatus.failed)
    return
