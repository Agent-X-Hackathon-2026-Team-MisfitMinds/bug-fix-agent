"""Main FastAPI application for the bug-fix agent."""

from fastapi import FastAPI

from errors import register_error_handlers, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .schemas import *
from .webhooks.github import router as github_router

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
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(github_router, prefix="/webhooks", tags=["webhooks"])


@app.get("/health", tags=["root"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "bug-fix-agent-api"}


@app.get("/docs", tags=["root"])
async def api_docs():
    """API documentation endpoint."""
    return {
        "message": "See /docs for full OpenAPI specification",
        "endpoints": ["/health", "/webhooks/github", "/runs"],
    }
