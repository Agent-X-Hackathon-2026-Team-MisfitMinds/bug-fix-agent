"""Main FastAPI application for the bug-fix agent."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Bug-Fix Agent API",
    description="API for the bug-fix agent system",
    version="0.1.0",
)

# CORS - configure for production as needed
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Idempotency-Key"],
)


@app.get("/health", tags=["root"])
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}
