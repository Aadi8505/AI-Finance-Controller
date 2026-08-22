"""Benchmark & Metrics API Endpoints."""

from __future__ import annotations

import json
import os
from typing import Any
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/benchmarks", tags=["Benchmarks & Evaluation"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
METRICS_PATH = os.path.join(BASE_DIR, "data", "generated", "baseline_metrics.json")


@router.get("/baseline")
def get_baseline_metrics() -> dict[str, Any]:
    """Fetch latest evaluated Experiment A baseline metrics."""
    if not os.path.exists(METRICS_PATH):
        raise HTTPException(status_code=404, detail="Baseline metrics not generated yet. Run evaluation first.")
    with open(METRICS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)
