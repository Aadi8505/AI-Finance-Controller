"""FastAPI Application Entrypoint for AI Finance Controller."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    benchmarks_router,
    exceptions_router,
    investigation_router,
    reconciliation_router,
)
from app.db.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Initialize DB tables on startup
    try:
        init_db()
    except Exception as e:
        print(f"Warning during DB init on startup: {e}")
    yield


app = FastAPI(
    title="AI Finance Controller API",
    description="Autonomous Reconciliation & Audit Platform (Track 04 Razorpay Buildathon)",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(reconciliation_router)
app.include_router(exceptions_router)
app.include_router(investigation_router)
app.include_router(benchmarks_router)


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "HEALTHY", "service": "ai-finance-controller", "version": "1.0.0"}


@app.get("/api/status", tags=["Health"])
def api_status() -> dict[str, str]:
    return {"status": "OPERATIONAL", "database": "CONNECTED"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
