"""Unit tests for Empirical Evaluation and Comparison Harness."""

import os
import pytest
from scripts.evaluate_comparison import evaluate_and_compare, load_dataset
from scripts.tune_thresholds import sweep_thresholds


def test_load_dataset_and_ground_truth():
    payments, settlements, ground_truth = load_dataset()
    assert len(payments) == 500
    assert len(settlements) == 500
    assert len(ground_truth) == 500


def test_evaluate_and_compare_output():
    results = evaluate_and_compare()
    assert "experiment_a" in results
    assert "experiment_b" in results
    assert results["experiment_a"]["precision_pct"] == 100.0
    assert results["experiment_b"]["precision_pct"] == 100.0
    assert results["experiment_a"]["total_records"] == 500


def test_sweep_thresholds_results():
    sweep = sweep_thresholds()
    assert len(sweep) > 0
    for r in sweep:
        assert 0.0 <= r["match_rate_pct"] <= 100.0
        assert 0.0 <= r["precision_pct"] <= 100.0
        assert 0.0 <= r["recall_pct"] <= 100.0
