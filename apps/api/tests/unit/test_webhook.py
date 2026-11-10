import hashlib
import hmac
import json
from typing import Any

from fastapi.testclient import TestClient

from main import app
from schemas import GitHubWebhookPayload
from webhooks.github import extract_run_fields, verify_webhook_signature

SECRET = "test-webhook-secret"
client = TestClient(app)


def sign(body: bytes, secret: str = SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def payload(*, action: str = "labeled", labels: list[str] | None = None) -> dict[str, Any]:
    return {
        "action": action,
        "issue": {
            "number": 1,
            "title": "Off-by-one in calculate_discount",
            "body": "Quantity 10 gives 10% instead of 15%.",
            "labels": [{"name": name} for name in (labels or ["agent-fix"])],
        },
        "repository": {"full_name": "fixie-demo/seeded-repo"},
        "sender": {"login": "octocat"},
        "installation": {"id": 123},
    }


def post(body: dict[str, Any], *, delivery: str, signature: str | None = None) -> Any:
    raw = json.dumps(body).encode()
    headers = {
        "X-GitHub-Delivery": delivery,
        "X-GitHub-Event": "issues",
        "X-Hub-Signature-256": signature if signature is not None else sign(raw),
    }
    return client.post("/webhooks/github", content=raw, headers=headers)


def test_signature_verification() -> None:
    body = b'{"action":"labeled"}'
    assert verify_webhook_signature(body, sign(body), SECRET)
    assert not verify_webhook_signature(body, sign(body, "wrong"), SECRET)
    assert not verify_webhook_signature(body, "md5=abc", SECRET)


def test_missing_headers_returns_400() -> None:
    response = client.post("/webhooks/github", content=b"{}")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_invalid_signature_returns_401(monkeypatch: Any) -> None:
    monkeypatch.setenv("GITHUB_APP_WEBHOOK_SECRET", SECRET)
    response = post(payload(), delivery="delivery-bad", signature="sha256=deadbeef")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_valid_delivery_accepted(monkeypatch: Any) -> None:
    monkeypatch.setenv("GITHUB_APP_WEBHOOK_SECRET", SECRET)
    response = post(payload(), delivery="delivery-ok")
    assert response.status_code == 200
    assert response.json() == {"status": "accepted", "delivery_id": "delivery-ok"}


def test_duplicate_delivery_returns_409(monkeypatch: Any) -> None:
    monkeypatch.setenv("GITHUB_APP_WEBHOOK_SECRET", SECRET)
    first = post(payload(), delivery="delivery-dup")
    second = post(payload(), delivery="delivery-dup")
    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "CONFLICT"


def test_extract_only_agent_fix_labeled() -> None:
    agent_fix = GitHubWebhookPayload.model_validate(payload())
    assert extract_run_fields(agent_fix) == {
        "installation_id": 123,
        "repository_full_name": "fixie-demo/seeded-repo",
        "issue_number": 1,
        "issue_title": "Off-by-one in calculate_discount",
        "issue_body": "Quantity 10 gives 10% instead of 15%.",
        "triggered_by": "octocat",
    }

    other_label = GitHubWebhookPayload.model_validate(payload(labels=["bug"]))
    assert extract_run_fields(other_label) is None

    opened = GitHubWebhookPayload.model_validate(payload(action="opened"))
    assert extract_run_fields(opened) is None
