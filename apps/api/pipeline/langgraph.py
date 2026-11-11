"""LangGraph pipeline for Bug-Fix Agent.

Implements the six nodes: Read, Reproduce, Diagnose, Fix, Verify, PR.
Each node is small, testable, and follows the execution guide rules.
"""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Optional, List, Dict, Any, Union

from pydantic import BaseModel, Field


# ------------------------------------------------------------
# Run State Contract - must match TS types in packages/shared/
# ------------------------------------------------------------


class RunStatus(str, Enum):
    """Current run status - must match TS RunStatus."""
    pending = "pending"
    reproducing = "reproducing"
    diagnosing = "diagnosing"
    fixing = "fixing"
    verifying = "verifying"
    verified = "verified"
    pr_open = "pr_open"
    completed = "completed"
    failed = "failed"
    could_not_reproduce = "could_not_reproduce"


class ConfidenceLevel(str, Enum):
    """Confidence level in the result."""
    high = "high"
    medium = "medium"
    low = "low"


class PipelineStep(str, Enum):
    """Current pipeline step - must match TS PipelineStep."""
    read = "read"
    reproduce = "reproduce"
    diagnose = "diagnose"
    fix = "fix"
    verify = "verify"
    pr = "pr"


# ------------------------------------------------------------
# Shared Run State Model
# ------------------------------------------------------------


class RunState(BaseModel):
    """Typed graph state shared across all pipeline nodes.

    Fields kept in sync with packages/shared/types.ts
    """

    # Identification
    run_id: str = Field(default_factory=lambda: f"run-{hashlib.sha256(str(__import__('uuid').uuid4()).encode()).hexdigest()[:12]}")
    issue_id: int = Field(..., description="GitHub issue number")
    repo_name: str = Field(..., description="Repository in owner/name format")
    branch: str = Field(default="agent-fix", description="Working branch name")

    # Status & Step Tracking
    status: RunStatus = Field(default=RunStatus.pending, description="Current run status")
    step: PipelineStep = Field(default=PipelineStep.read, description="Current pipeline step")
    confidence: Optional[ConfidenceLevel] = Field(
        default=None,
        description="Confidence in current result: high/medium/low",
    )

    # Issue Details
    issue_title: Optional[str] = Field(default=None, description="Issue title from GitHub")
    issue_body: Optional[str] = Field(default=None, description="Issue body/description")
    reproduction_steps: Optional[str] = Field(
        default=None,
        description="Extracted reproduction steps from issue",
    )

    # Before Fix Evidence
    before_test_output: Optional[str] = Field(
        default=None,
        description="Test output before the fix was applied",
    )
    before_exit_code: Optional[int] = Field(
        default=None,
        description="Exit code before the fix",
    )

    # After Fix Evidence
    after_test_output: Optional[str] = Field(
        default=None,
        description="Test output after the fix was applied",
    )
    after_exit_code: Optional[int] = Field(
        default=None,
        description="Exit code after the fix",
    )

    # Root Cause & Patch
    root_cause: Optional[str] = Field(
        default=None,
        description="Plain-English root cause diagnosis",
    )
    patch: Optional[Dict[str, str]] = Field(
        default=None,
        description="Applied patch: {file_path, old_code, new_code, description}",
    )
    likely_file: Optional[str] = Field(
        default=None,
        description="Likely file containing the bug",
    )
    likely_line: Optional[int] = Field(
        default=None,
        description="Likely line number containing the bug",
    )

    # Evidence & Errors
    evidence: List[str] = Field(
        default_factory=list,
        description="Supporting evidence for root cause",
    )
    errors: List[str] = Field(
        default_factory=list,
        description="Error messages encountered during run",
    )

    # PR & Branch Information
    pr_url: Optional[str] = Field(default=None, description="Draft PR URL if opened")
    branch_name: Optional[str] = Field(
        default=None,
        description="Git branch name where patch was applied",
    )
    comment: Optional[str] = Field(default=None, description="Comment to post on the issue")

    # Metadata
    retry_count: int = Field(
        default=0,
        description="Number of retry attempts for this run",
    )
    created_at: str = Field(
        default_factory=lambda: __import__('datetime').datetime.utcnow().isoformat() + "Z",
        description="ISO timestamp when run was created",
    )
    updated_at: str = Field(
        default_factory=lambda: __import__('datetime').utcnow().isoformat() + "Z",
        description="ISO timestamp when run was last updated",
    )


# ------------------------------------------------------------
# Node 1: Read - Fetch Issue Details
# ------------------------------------------------------------


async def read_node(state: RunState, github_client) -> RunState:
    """Node 1: Read - Fetch issue title, body, repository and reproduction steps.

    MUST NOT continue if issue has enough expected/actual behaviour info.
    Otherwise comment "need more reproduction information. info" or "couldn't reproduce".
    """

    from . import github_client as gh  # avoid circular import at module level

    # Fetch issue from GitHub API
    try:
        issue = await gh.get_issue(state.issue_id)
    except Exception as e:
        state.errors.append(f"Failed to fetch issue {state.issue_id}: {e}")
        state.status = RunStatus.could_not_reproduce
        return state

    # Store issue details
    state.issue_title = issue.get("title", "")
    state.issue_body = issue.get("body", "")

    # Validate repository has expected content
    repo_name = state.repo_name
    if not repo_name:
        state.errors.append("Repository name is required for read node")
        state.status = RunStatus.failed
        return state

    # Check issue has enough information
    body = state.issue_body or ""
    if len(body) < 50:
        state.comment = (
            "Need more reproduction information. "
            "Please provide reproduction steps, expected behaviour, and actual behaviour."
        )
        state.status = RunStatus.could_not_reproduce
        return state

    # Extract reproduction steps (simple heuristic)
    state.reproduction_steps = extract_reproduction_steps(body)

    # Fetch repo info to validate it's Python
    try:
        repo = await gh.get_repo(repo_name)
        if repo.get("language", "").lower() != "python":
            state.errors.append(
                f"Repository {repo_name} is not Python (language: {repo.get('language')})"
            )
            state.status = RunStatus.could_not_reproduce
            return state
    except Exception as e:
        state.errors.append(f"Failed to fetch repo {repo_name}: {e}")
        # Continue anyway - user may have confirmed it's Python

    # Mark as read step completed
    state.step = PipelineStep.read
    state.status = RunStatus.pending

    return state


def extract_reproduction_steps(body: str) -> Optional[str]:
    """Extract reproduction steps from issue body.

    Heuristic: look for "Steps to reproduce", "Steps:", or numbered lists.
    """
    import re

    # Look for common patterns
    patterns = [
        r"Steps? to reproduce[:\n](.+?)(?:\n\n|\n[A-Z]|$)",
        r"Steps?:\n(.+?)(?:\n\n|\n[A-Z]|$)",
        r"\d+\.\s*(.+?)(?:\n\d+\.|$)",
    ]

    for pattern in patterns:
        match = re.search(pattern, body, re.IGNORECASE | re.DOTALL)
        if match:
            steps = match.group(1).strip()
            if len(steps) > 20:  # Must be substantial enough
                return steps[:2000]  # Cap at 2000 chars

    # If no explicit steps found, return first paragraph as informal steps
    paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
    if paragraphs:
        return paragraphs[0][:2000]

    return None


# ------------------------------------------------------------
# Node 2: Reproduce - Clone and Run Baseline Tests
# ------------------------------------------------------------


async def reproduce_node(
    state: RunState, yash_sandbox, pytest_runner
) -> RunState:
    """Node 2: Reproduce - Clone repo in Docker, run baseline tests.

    The new test fails before the patch for the expected reason.
    If test passes -> status = could_not_reproduce.
    """

    # Clone repo via Yash's sandbox and run baseline tests
    try:
        sandbox_result = await yash_sandbox.clone_and_test(
            repo_name=state.repo_name,
            issue_id=state.issue_id,
            timeout=300,  # 5 minute timeout max
            network_disabled_after_install=True,
        )
    except Exception as e:
        state.errors.append(f"Sandbox error during reproduce: {e}")
        state.status = RunStatus.failed
        return state

    # Capture baseline test results
    state.before_test_output = sandbox_result.get("test_output")
    state.before_exit_code = sandbox_result.get("exit_code", 0)

    # Write minimal reproduction test based on issue
    try:
        reproduction_test = await write_reproduction_test(
            issue={"title": state.issue_title or "", "body": state.issue_body or ""},
            repo_snapshot=sandbox_result.get("repo_snapshot") or {},
            failing_test=sandbox_result.get("failing_test"),
        )
        state.reproduction_test_code = reproduction_test
    except Exception as e:
        state.errors.append(f"Failed to write reproduction test: {e}")
        state.status = RunStatus.failed
        return state

    # Run the reproduction test - MUST FAIL before patch
    try:
        test_result = await pytest_runner.run(
            test_file=reproduction_test,
            timeout=120,
        )
    except Exception as e:
        state.errors.append(f"Failed to run reproduction test: {e}")
        state.status = RunStatus.failed
        return state

    # Critical check: test must fail before patch
    if test_result.passed:
        state.errors.append(
            "Reproduction test passed - cannot identify bug. "
            "Issue may be too thin or already fixed."
        )
        state.status = RunStatus.could_not_reproduce
        return state

    # Store failing output for later comparison
    state.before_output = test_result.output
    state.step = PipelineStep.reproduce
    state.status = RunStatus.reproducing

    return state


async def write_reproduction_test(
    issue: dict, repo_snapshot: dict, failing_test: Optional[dict] = None
) -> str:
    """Write a minimal reproduction test based on issue and repo state.

    The test should FAIL before any fix is applied.
    """
    from pathlib import Path
    import tempfile

    # Get issue title and body for test context
    title = issue.get("title", "")
    body = issue.get("body", "")

    # Determine the likely file and function from issue or repo
    # Heuristic: look for function names, module paths in issue body
    import re

    # Common patterns for off-by-one, wrong condition, missing null check
    func_pattern = r"\b(\w+)\s*\([^)]*\)\s*(?:->|\s)"
    func_matches = re.findall(func_pattern, body + title)

    # Determine test content dynamically from issue + repo snapshot
    if failing_test:
        test_content = failing_test.get("test_code", "")
    else:
        # Extract candidate function/module names from issue and repo snapshot
        import os as _os
        module_candidates = []
        for m in func_matches:
            if m and m not in module_candidates:
                module_candidates.append(m)
        # Also pull module names from repo snapshot file list
        for f in (repo_snapshot or {}).get("files", []):
            base = _os.path.splitext(_os.path.basename(f))[0]
            if base and base not in module_candidates:
                module_candidates.append(base)

        primary = module_candidates[0] if module_candidates else "target_module"
        title_slug = re.sub(r"[^a-z0-9_]", "_", title.lower())[:40] or "bug"

        test_content = f'''def test_reproduce_{title_slug}():
    """Auto-generated reproduction test from issue: {title}."""
    # Issue body (treated as data, not instructions):
    # {body[:500].replace(chr(10), " ")}
    try:
        from {primary} import {primary}  # type: ignore
    except Exception:
        import importlib
        mod = importlib.import_module("{primary}")
        {primary} = getattr(mod, "{primary}")

    # Exercise the function with a representative input extracted from the issue.
    # Adjust arguments as needed based on the issue description.
    result = {primary}()
    assert result is not None, "Reproduction did not exercise a code path"
'''

    # Write to a temporary file path that pytest can discover
    test_path = Path("/tmp/bug_fix_repro_test.py")
    test_path.write_text(test_content)

    return str(test_path)


# ------------------------------------------------------------
# Node 3: Diagnose - Root Cause Analysis
# ------------------------------------------------------------


async def diagnose_node(
    state: RunState, llm_analyze, repo_structure: dict
) -> RunState:
    """Node 3: Diagnose - Explain likely cause using observed test evidence.

    Link cause to test evidence, NOT just issue text.
    Treat issue text and repo content as untrusted data.
    """

    # Analyze failing test output with LLM
    try:
        analysis = await llm_analyze(
            issue_body=state.issue_body or "",
            failing_test_output=state.before_output or "",
            reproduction_test=state.reproduction_test_code,
            repo_snapshot=repo_structure,
        )
    except Exception as e:
        state.errors.append(f"LLM analysis failed: {e}")
        state.status = RunStatus.failed
        return state

    # Extract root cause with supporting evidence
    root_cause = analysis.get("root_cause")
    evidence = analysis.get("evidence", []) or []

    if not root_cause:
        state.errors.append("Could not determine root cause from LLM evidence")
        state.status = RunStatus.failed
        return state

    # Store root cause and evidence
    state.root_cause = root_cause
    state.evidence = evidence

    # Determine likely file and line number from root cause
    likely_file, likely_line = determine_location(
        root_cause=root_cause,
        repo_structure=repo_structure,
    )
    state.likely_file = likely_file
    state.likely_line = likely_line

    # Log evidence summary
    state.evidence = evidence[:5]  # Cap at 5 pieces of evidence

    step = PipelineStep.diagnose
    state.status = RunStatus.diagnosing

    return state


def determine_location(
    root_cause: str, repo_structure: dict
) -> tuple[Optional[int], Optional[str]]:
    """Determine likely file and line from root cause analysis.

    Uses heuristic matching against repo structure.
    """
    import re

    # Common bug patterns and likely locations
    cause_lower = root_cause.lower()

    # Off-by-one patterns
    if any(
        kw in cause_lower
        for kw in ["off-by-one", "off by one", "off by one", "index error"]
    ):
        # Likely an array/list indexing issue
        return "apps/api", 42  # placeholder - would be dynamic

    # Wrong condition patterns
    if any(
        kw in cause_lower for kw in ["wrong condition", "incorrect", "mistake"]
    ):
        return "apps/api", 24  # placeholder

    # Missing null check patterns
    if any(
        kw in cause_lower for kw in ["null check", "none", "nonexistent", "missing guard"]
    ):
        return "apps/api", 18  # placeholder

    # Default: return first file in repo structure
    if repo_structure.get("files"):
        first_file = repo_structure["files"][0]
        return first_file, 1

    return None, None


# ------------------------------------------------------------
# Node 4: Fix - Minimal Code Patch
# ------------------------------------------------------------


async def fix_node(
    state: RunState, apply_patch, read_file, llm_generate_patch
) -> RunState:
    """Node 4: Fix - Make smallest useful code change on agent work branch.

    Patch is scoped and does not alter unrelated behaviour.
    """

    # Get the likely file and current code
    file_path = state.likely_file
    if not file_path:
        state.errors.append("No likely file determined - cannot apply patch")
        state.status = RunStatus.failed
        return state

    # Read current code at likely location
    try:
        current_code = await read_file(file_path, state.likely_line or 1)
    except Exception as e:
        state.errors.append(f"Failed to read {file_path}:{state.likely_line}: {e}")
        state.status = RunStatus.failed
        return state

    # Ask LLM for minimal patch with evidence
    try:
        patch_result = await llm_generate_patch(
            issue_title=state.issue_title or "",
            issue_body=state.issue_body or "",
            root_cause=state.root_cause or "",
            current_code=current_code,
            repo_context=state.evidence,
            confidence=state.confidence,
        )
    except Exception as e:
        state.errors.append(f"LLM patch generation failed: {e}")
        state.status = RunStatus.failed
        return state

    # Validate patch result
    patch = patch_result.get("patch")
    if not patch:
        state.errors.append("LLM could not generate valid patch")
        state.status = RunStatus.failed
        return state

    # Ensure patch has required fields
    required_patch_fields = ["file_path", "old_code", "new_code", "description"]
    for field in required_patch_fields:
        if field not in patch:
            state.errors.append(f"Patch missing required field: {field}")
            state.status = RunStatus.failed
            return state

    # Apply the patch
    try:
        patch_applied = await apply_patch(
            file_path=patch["file_path"],
            old_code=patch["old_code"],
            new_code=patch["new_code"],
        )
    except Exception as e:
        state.errors.append(f"Failed to apply patch: {e}")
        state.status = RunStatus.failed
        return state

    if not patch_applied:
        state.errors.append("Patch application reported failure")
        state.status = RunStatus.failed
        return state

    # Store the applied patch
    state.patch = {
        "file_path": patch["file_path"],
        "old_code": patch["old_code"],
        "new_code": patch["new_code"],
        "description": patch.get("description", "Minimal code fix"),
    }
    state.step = PipelineStep.fix
    state.status = RunStatus.fixing

    return state


# ------------------------------------------------------------
# Node 5: Verify - Test Validation
# ------------------------------------------------------------


async def verify_node(
    state: RunState, pytest_runner
) -> RunState:
    """Node 5: Verify - Run reproduction test after patch, then full suite.

    MUST NOT open PR unless:
    - Reproduction test passes after fix
    - Full existing pytest suite remains green
    """

    # 1. Run reproduction test - must PASS after patch
    if not state.reproduction_test_code:
        state.errors.append("No reproduction test code available")
        state.status = RunStatus.failed
        return state

    try:
        repro_test = await pytest_runner.run(
            test_file=state.reproduction_test_code,
            timeout=120,
        )
    except Exception as e:
        state.errors.append(f"Failed to run reproduction test: {e}")
        state.status = RunStatus.failed
        return state

    # Critical: reproduction test must pass after fix
    if not repro_test.passed:
        state.errors.append(
            "Reproduction test still fails after patch. "
            "Return to Fix node for adjustment."
        )
        state.status = RunStatus.fixing  # Loop back
        return state

    # 2. Run full existing pytest suite - must stay GREEN
    try:
        full_suite = await pytest_runner.run_suite(
            test_directory="apps/api/tests/",
            timeout=300,
        )
    except Exception as e:
        state.errors.append(f"Failed to run full pytest suite: {e}")
        state.status = RunStatus.failed
        return state

    # Critical: full suite must remain green
    if not full_suite.passed:
        state.errors.append(
            "Full pytest suite failed - patch broke existing functionality. "
            "Return to Fix node for adjustment."
        )
        state.status = RunStatus.fixing  # Loop back
        return state

    # Both checks passed - store after outputs
    state.after_test_output = full_suite.output
    state.after_exit_code = full_suite.exit_code
    step = PipelineStep.verify
    state.status = RunStatus.verified

    return state


# ------------------------------------------------------------
# Node 6: PR - Generate Draft Pull Request
# ------------------------------------------------------------


async def pr_node(
    state: RunState, github_client
) -> RunState:
    """Node 6: PR - Only after all verification checks pass.

    Never open a PR unless reproduction test passes after fix
    AND full existing pytest suite remains green.
    Generates PR body with evidence and confidence.
    Never invent a successful run.
    """

    # CRITICAL EXIT CHECK: Must not continue if not verified
    if state.status != RunStatus.verified:
        state.errors.append(
            "Cannot open PR: verification not complete. "
            "Status is: " + state.status.value
        )
        return state

    # Generate PR body with evidence
    pr_body = _generate_pr_body(state)

    # Create branch name
    _hash = hashlib.sha256((state.root_cause or "unknown").encode()).hexdigest()[:8]
    branch_name = f"agent/fix-{state.issue_id}-{_hash}"

    # Push branch and open draft PR via GitHub API (Yash's integration)
    try:
        github_result = await github_client.push_branch_and_open_draft_pr(
            branch_name=branch_name,
            pr_title=f"[Durgesh] Fix for issue {state.issue_id}",
            pr_body=pr_body,
            maintainer_can_modify=True,
            # GitHub App MUST NOT have merge permission
        )
    except Exception as e:
        state.errors.append(f"Failed to open draft PR: {e}")
        state.status = RunStatus.failed
        return state

    # Store PR and branch info
    state.pr_url = github_result.get("pr_url")
    state.branch_name = branch_name
    step = PipelineStep.pr
    state.status = RunStatus.pr_open

    return state


def _generate_pr_body(state: RunState) -> str:
    """Generate markdown PR body with full evidence."""

    # Safely format outputs - handle None cases
    before_output = state.before_output or "No baseline test output available"
    after_output = state.after_test_output or "No post-fix test output available"
    root_cause = state.root_cause or "Not diagnosed"
    patch_desc = state.patch.get("description", "Minimal code change") if state.patch else "Minimal code change"
    confidence = state.confidence or "low"

    body = f"""## Bug Fix Summary

### Issue
{state.issue_title or "Unknown issue #" + str(state.issue_id)}

### Root Cause
{root_cause}

### What Changed
{patch_desc}

### Failing Before / Passing After
- **Before:** `{before_output[:300]}...`
- **After:** `{after_output[:300]}...`

### Full Suite Result
- **Status:** {'Green ✅' if state.status == RunStatus.verified else 'Red ❌'}
- **Tests Run:** {len(state.errors) if state.errors else 0}

### Confidence: {confidence.value.upper()}
**Reasons:** {state.confidence_reasons or 'Could not assess'} 

### Evidence
- Reproduction test: `{before_output[:200]}...` → `{after_output[:200]}...`
- Root cause analysis based on test evidence and code inspection

### Pipeline Step
{state.step.value}

---
*Generated by Bug-Fix-Agent. Human review required before merge.
The agent does not have merge permission. This is a draft PR awaiting human approval.*
"""

    return body


# ------------------------------------------------------------
# Checkpoint/Retry Handling
# ------------------------------------------------------------


def should_continue(state: RunState) -> str:
    """Determine next step based on current status.

    Returns the name of the next node to execute, or 'end'.
    """

    if state.status == RunStatus.could_not_reproduce:
        # Honest failure - end with clear status
        return "end"

    if state.status == RunStatus.failed:
        # Retry logic with bounded attempts
        if state.retry_count < 3:
            state.retry_count += 1
            return "retry"  # Caller should reset and re-run from diagnose
        else:
            # Max retries exceeded - end with failure status
            state.errors.append(
                f"Failed after {state.retry_count} retry attempts"
            )
            return "end"

    if state.status == RunStatus.verified:
        return "pr"  # Move to PR node

    if state.status in [
        RunStatus.reproducing,
        RunStatus.diagnosing,
        RunStatus.fixing,
    ]:
        return "continue"  # Keep current node's loop

    # Default: end
    return "end"


# ------------------------------------------------------------
# Cache Strategy (Section 7D)
# ------------------------------------------------------------


class PromptCache:
    """Cache LLM prompts by SHA-256 hash of issue content.

    Uses 24-hour TTL; invalidate on prompt changes.
    Cache rehearsed demo issues before live demo.
    """

    def __init__(self, ttl_hours: int = 24):
        self._cache: dict = {}
        self.ttl = __import__("datetime").timedelta(hours=ttl_hours)

    def _hash(self, issue_title: str, issue_body: str, prompt_version: str = "v1") -> str:
        """Generate SHA-256 hash for cache key."""
        combined = f"{issue_title}|{issue_body}|{prompt_version}"
        return __import__("hashlib").sha256(combined.encode()).hexdigest()

    def get(
        self, issue_title: str, issue_body: str, prompt_version: str = "v1"
    ) -> Optional[str]:
        """Retrieve cached result if not expired."""
        key = self._hash(issue_title, issue_body, prompt_version)
        if key in self._cache:
            cached, timestamp = self._cache[key]
            now = __import__("datetime").utcnow()
            if now - timestamp < self.ttl:
                return cached
            else:
                # Expired - remove entry
                del self._cache[key]
        return None

    def set(
        self,
        issue_title: str,
        issue_body: str,
        prompt_version: str = "v1",
        result: str = "",
    ) -> None:
        """Store result with current timestamp."""
        key = self._hash(issue_title, issue_body, prompt_version)
        self._cache[key] = (result, __import__("datetime").utcnow())

    def cleanup_expired(self) -> None:
        """Remove all expired entries (call periodically)."""
        now = __import__("datetime").utcnow()
        expired_keys = [
            k
            for k, (_, timestamp) in self._cache.items()
            if now - timestamp >= self.ttl
        ]
        for k in expired_keys:
            del self._cache[k]


# ------------------------------------------------------------
# Main Graph Entry Point
# ------------------------------------------------------------


async def run_pipeline(
    issue_id: int,
    repo_name: str,
    github_client,
    yash_sandbox,
    pytest_runner,
    llm_analyze,
    llm_generate_patch,
    apply_patch,
    read_file,
    repo_structure: dict,
) -> RunState:
    """Run the full 6-node LangGraph pipeline for a GitHub issue.

    Args:
        issue_id: GitHub issue number
        repo_name: Repository in owner/name format
        github_client: Yash's GitHub integration client
        yash_sandbox: Yash's sandbox interface
        pytest_runner: Pytest runner instance
        llm_analyze: Function for root cause analysis
        llm_generate_patch: Function for code patch generation
        apply_patch: Function for applying code changes
        read_file: Function for reading source file at line
        repo_structure: Repository structure dict

    Returns:
        RunState with final status and all collected data
    """

    # Initial state
    state = RunState(issue_id=issue_id, repo_name=repo_name)

    # Define node sequence
    nodes = [
        ("read", lambda s: read_node(s, github_client)),
        ("reproduce", lambda s: reproduce_node(s, yash_sandbox, pytest_runner)),
        ("diagnose", lambda s: diagnose_node(s, llm_analyze, repo_structure)),
        ("fix", lambda s: fix_node(s, apply_patch, read_file, llm_generate_patch)),
        ("verify", lambda s: verify_node(s, pytest_runner)),
        ("pr", lambda s: pr_node(s, github_client)),
    ]

    # Execute nodes with checkpoint logic
    max_iterations = 20  # Prevent infinite loops
    iteration = 0

    while iteration < max_iterations:
        iteration += 1

        # Determine next step
        next_step = should_continue(state)

        if next_step == "end":
            break

        if next_step == "retry":
            # Reset to diagnose node for retry
            state.step = PipelineStep.diagnose
            state.status = RunStatus.diagnosing
            # Continue to diagnose
            continue

        # Execute the appropriate node
        node_name, node_func = nodes[0]  # Simplified - in production, index based on current step

        # Map status to node index (simplified mapping)
        if state.status in [RunStatus.pending] or state.step == PipelineStep.read:
            result_func = nodes[0][1]
        elif state.status in [RunStatus.reproducing] or state.step == PipelineStep.reproduce:
            result_func = nodes[1][1]
        elif state.status in [RunStatus.diagnosing] or state.step == PipelineStep.diagnose:
            result_func = nodes[2][1]
        elif state.status in [RunStatus.fixing] or state.step == PipelineStep.fix:
            result_func = nodes[3][1]
        elif state.status in [RunStatus.verified] or state.step == PipelineStep.verify:
            result_func = nodes[4][1]
        elif state.status in [RunStatus.pr_open] or state.step == PipelineStep.pr:
            result_func = nodes[5][1]
        else:
            result_func = nodes[0][1]  # Default to read

        try:
            state = await result_func(state)
        except Exception as e:
            state.errors.append(f"Unexpected error in {node_name}: {e}")
            state.status = RunStatus.failed
            break

        # Check if we should move to next node
        continue_decision = should_continue(state)
        if continue_decision == "end":
            break
        elif continue_decision == "retry":
            # Reset retry count and go back
            state.retry_count = 0
            # Will loop back to appropriate node
            continue
        # else: continue loop with updated state

    return state