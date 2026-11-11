# Durgesh Pipeline Fix Plan

Working plan for the 10 fixes requested. Each step becomes its own PR (no direct pushes to `main`).
Order matters: earlier steps unblock later ones.

## Step 1 — Make the pipeline runnable (`langgraph.py`)
- **Problem**: crashes on start; uses status names/fields that don't exist.
- **Work**:
  - Align `RunStatus` / `PipelineStep` / `RunState` field names with TS types in `packages/shared`.
  - Fix node registration and edge wiring so graph compiles and runs end-to-end on a no-op path.
  - Replace placeholder status strings with enum values.
- **Files**: `apps/api/pipeline/langgraph.py`, `packages/shared/types.ts`
- **Acceptance**: `python -c "import pipeline.langgraph"` succeeds; graph invokes without crash on empty issue.

## Step 2 — Fix the LLM module (`llm.py`)
- **Problems**: missing Gemini package; fake answers on failure; typo in safety setting; missing `json` import; wrong prompt-template references; cache collisions.
- **Work**:
  - Add `google-generativeai` (or `google-genai`) to `requirements.txt`.
  - `import json` at top.
  - Fix safety setting typo.
  - Change prompt templates to be referenced by name correctly.
  - On LLM failure, raise a clear error (no fabricated answer).
  - Cache key must include both issue id and question text (not just issue id).
- **Files**: `apps/api/pipeline/llm.py`, `apps/api/requirements.txt`
- **Acceptance**: import succeeds; cache returns distinct answers for distinct questions; failure raises.

## Step 3 — Real "reproduce" step
- **Problem**: tests are hardcoded text.
- **Work**: generate a pytest test from issue title/body + repo source; write it into the cloned repo; run it; record pass/fail.
- **Files**: `langgraph.py` (reproduce node), `pipeline/sandbox.py`
- **Acceptance**: reproduced test reflects issue; result stored in `RunState`.

## Step 4 — Real "diagnose" and "fix"
- **Problem**: placeholder file/line values.
- **Work**: parse traceback + source search to locate real file + line; apply minimal patch; record diff.
- **Files**: `langgraph.py` (diagnose/fix nodes)
- **Acceptance**: `diagnosed_file`/`diagnosed_line`/`fix_diff` populated from real data.

## Step 5 — Use Yash's functions correctly
- **Problem**: clone + draft PR calls don't match signatures.
- **Work**: align call sites with `GitHubAPIClient.push_branch_and_open_draft_pr`, `get_issue`, clone helpers in `github/` and `sandbox.py`.
- **Files**: `langgraph.py`, `apps/api/github/__init__.py`, `pipeline/sandbox.py`
- **Acceptance**: clone returns path; draft PR created with correct args.

## Step 6 — Save progress after each step
- **Problem**: dashboard can't show live progress.
- **Work**: call `run_repo` update after every node; emit SSE event.
- **Files**: `langgraph.py`, `data/run_repo.py`, `sse/`
- **Acceptance**: dashboard reflects step changes in real time.

## Step 7 — Comment on the GitHub issue at each step
- **Problem**: no issue comments.
- **Work**: call `add_issue_comment` in each node; post honest "couldn't reproduce" when vague.
- **Files**: `langgraph.py`, `github/__init__.py`
- **Acceptance**: comments appear per step; vague issues get could_not_reproduce comment.

## Step 8 — Build PR description from real results
- **Problem**: PR body is static.
- **Work**: assemble failing test (before), passing test (after), full suite result, confidence level.
- **Files**: `langgraph.py` (pr node)
- **Acceptance**: draft PR body contains all four sections.

## Step 9 — Update/delete old demo bug files
- **Problem**: `apps/api/demo_bugs` doesn't match real demo repo.
- **Work**: audit and either update to real demo bugs or delete; update fixtures/tests accordingly.
- **Files**: `apps/api/demo_bugs/`, `tests/fixtures/conftest_bugs.py`
- **Acceptance**: no stale references; tests pass.

## Step 10 — Add tests for pipeline steps
- **Problem**: no tests for pipeline nodes.
- **Work**: unit tests for each node with mocked LLM/GitHub/sandbox; integration test for full run.
- **Files**: `apps/api/tests/unit/test_pipeline_*.py`, `tests/integration/`
- **Acceptance**: `pytest` green for new tests.

## PR strategy
- One branch per step: `fix/durgesh-step-N-<slug>`.
- Each PR targets `main`, reviewed before merge.
- No direct pushes to `main`.