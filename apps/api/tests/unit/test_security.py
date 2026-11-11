from fastapi.testclient import TestClient

from main import app
from security import API_CSP

EXPECTED = {
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Content-Security-Policy": API_CSP,
}


def test_headers_on_success() -> None:
    response = TestClient(app).get("/health")

    for header, value in EXPECTED.items():
        assert response.headers[header] == value


def test_headers_on_error_response() -> None:
    response = TestClient(app).get("/runs")

    assert response.status_code == 401
    for header, value in EXPECTED.items():
        assert response.headers[header] == value


def test_csp_blocks_frames_and_inline_scripts() -> None:
    assert "frame-ancestors 'none'" in API_CSP
    assert "default-src 'none'" in API_CSP
    assert "unsafe-eval" not in API_CSP
    assert "unsafe-inline" not in API_CSP
