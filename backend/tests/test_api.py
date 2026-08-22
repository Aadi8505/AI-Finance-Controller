"""Unit tests for FastAPI REST Endpoints."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import init_db


@pytest.fixture(scope="module")
def client():
    init_db()
    with TestClient(app) as c:
        yield c


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "HEALTHY"


def test_api_status(client):
    response = client.get("/api/status")
    assert response.status_code == 200
    assert response.json()["status"] == "OPERATIONAL"


def test_batch_reconciliation_endpoint(client):
    response = client.post("/api/reconcile/batch?t_high=0.90&t_low=0.50")
    assert response.status_code == 200
    data = response.json()
    assert "run_id" in data
    assert data["total_processed"] > 0
    assert "auto_resolved_count" in data


def test_list_reconciliation_runs(client):
    response = client.get("/api/reconcile/runs")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_list_exceptions_endpoint(client):
    response = client.get("/api/exceptions")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_get_baseline_benchmarks(client):
    response = client.get("/api/benchmarks/baseline")
    assert response.status_code == 200
    data = response.json()
    assert data["experiment"] == "Experiment A — Deterministic Baseline"
