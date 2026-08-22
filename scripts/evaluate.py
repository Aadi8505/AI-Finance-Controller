"""Empirical Evaluation Harness (Experiment A — Deterministic Baseline).

Grades the deterministic reconciliation engine against the isolated ground truth dataset.
Uses strict holdout partitioning via CRC32 hashing to eliminate any chance of data leakage.

Computes exact mathematical metrics:
  - Match Rate
  - Overall Reconciliation Accuracy
  - Auto-Resolution Precision
  - False-Resolution Rate
  - Exception Rate
  - Throughput (records / sec)
  - Per-scenario confusion & accuracy breakdown
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import zlib
from decimal import Decimal

# Ensure backend is in python path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
from app.reconciliation.engine import run_deterministic_reconciliation
from app.reconciliation.normalizer import (
    NormalizedPayment,
    NormalizedSettlement,
    normalize_payment_row,
    normalize_settlement_row,
)

DATA_DIR = os.path.join(BASE_DIR, "data")
GEN_DIR = os.path.join(DATA_DIR, "generated")
GT_DIR = os.path.join(DATA_DIR, "ground_truth")


def load_dataset() -> tuple[list[NormalizedPayment], list[NormalizedSettlement], dict[str, dict]]:
    payments_path = os.path.join(GEN_DIR, "payments.csv")
    settlements_path = os.path.join(GEN_DIR, "settlements.csv")
    gt_path = os.path.join(GT_DIR, "ground_truth.csv")

    if not (os.path.exists(payments_path) and os.path.exists(settlements_path) and os.path.exists(gt_path)):
        raise FileNotFoundError("Dataset files not found in data/. Run `python scripts/generate_data.py` first.")

    payments: list[NormalizedPayment] = []
    with open(payments_path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            payments.append(normalize_payment_row(r))

    settlements: list[NormalizedSettlement] = []
    with open(settlements_path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            settlements.append(normalize_settlement_row(r))

    ground_truth: dict[str, dict] = {}
    with open(gt_path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            ground_truth[r["payment_id"]] = r

    return payments, settlements, ground_truth


def is_test_record(payment_id: str, test_fraction: float = 0.50) -> bool:
    """Deterministic, reproducible split using CRC32 hash."""
    return (zlib.crc32(payment_id.encode("utf-8")) % 100) < int(test_fraction * 100)


def evaluate_baseline(
    test_fraction: float = 0.50,
    t_high: Decimal = Decimal("0.90"),
    t_low: Decimal = Decimal("0.50"),
    eval_all: bool = False,
) -> dict:
    payments, settlements, ground_truth = load_dataset()

    if eval_all:
        eval_payments = payments
    else:
        eval_payments = [p for p in payments if is_test_record(p.payment_id, test_fraction=test_fraction)]

    # Run deterministic engine
    run_result = run_deterministic_reconciliation(
        payments=eval_payments,
        settlements=settlements,
        t_high=t_high,
        t_low=t_low,
    )

    matched_by_payment = {m.payment_id: m for m in run_result.matched}
    exceptions_by_payment = {e.payment_id: e for e in run_result.exceptions}

    total_evaluated = len(eval_payments)
    correct_matches = 0
    incorrect_matches = 0
    correct_exceptions = 0
    incorrect_exceptions = 0

    scenario_stats: dict[str, dict[str, int]] = {}

    for p in eval_payments:
        pid = p.payment_id
        truth = ground_truth[pid]
        scenario = truth["scenario_type"]
        expected_status = truth["expected_status"]
        expected_settle_id = truth["expected_settlement_id"] or None

        if scenario not in scenario_stats:
            scenario_stats[scenario] = {"total": 0, "auto_matched": 0, "correct_match": 0, "exception_raised": 0}
        scenario_stats[scenario]["total"] += 1

        if pid in matched_by_payment:
            pred_match = matched_by_payment[pid]
            scenario_stats[scenario]["auto_matched"] += 1

            if expected_status == "MATCH" and pred_match.settlement_id == expected_settle_id:
                correct_matches += 1
                scenario_stats[scenario]["correct_match"] += 1
            else:
                incorrect_matches += 1

        elif pid in exceptions_by_payment:
            scenario_stats[scenario]["exception_raised"] += 1
            if expected_status in {"UNMATCHED", "AMBIGUOUS_REVIEW"}:
                correct_exceptions += 1
            else:
                # Expected to match, but engine flagged as exception (safe abstention)
                incorrect_exceptions += 1

    # Exact metrics computations
    auto_resolved_total = len(run_result.matched)
    resolvable_true_matches = sum(1 for p in eval_payments if ground_truth[p.payment_id]["expected_status"] == "MATCH")

    accuracy = (correct_matches + correct_exceptions) / total_evaluated if total_evaluated else 0.0
    match_rate = correct_matches / resolvable_true_matches if resolvable_true_matches else 0.0
    auto_precision = correct_matches / auto_resolved_total if auto_resolved_total else 0.0
    false_resolution_rate = incorrect_matches / auto_resolved_total if auto_resolved_total else 0.0
    exception_rate = len(run_result.exceptions) / total_evaluated if total_evaluated else 0.0

    report = {
        "experiment": "Experiment A — Deterministic Baseline",
        "dataset_evaluated": {
            "total_evaluated": total_evaluated,
            "test_split_fraction": 1.0 if eval_all else test_fraction,
            "t_high": str(t_high),
            "t_low": str(t_low),
        },
        "performance_metrics": {
            "overall_accuracy_pct": round(accuracy * 100, 2),
            "match_rate_pct": round(match_rate * 100, 2),
            "auto_resolution_precision_pct": round(auto_precision * 100, 2),
            "false_resolution_rate_pct": round(false_resolution_rate * 100, 2),
            "exception_rate_pct": round(exception_rate * 100, 2),
            "throughput_records_per_sec": run_result.throughput_per_second,
            "elapsed_seconds": round(run_result.elapsed_seconds, 4),
        },
        "counts": {
            "auto_resolved_count": auto_resolved_total,
            "correct_matches": correct_matches,
            "incorrect_matches": incorrect_matches,
            "exceptions_generated": len(run_result.exceptions),
            "correct_exceptions": correct_exceptions,
            "safe_unmatched_abstained": incorrect_exceptions,
        },
        "scenario_breakdown": scenario_stats,
    }

    # Save to data/generated/baseline_metrics.json
    out_path = os.path.join(GEN_DIR, "baseline_metrics.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    return report


def print_evaluation_summary(report: dict):
    m = report["performance_metrics"]
    c = report["counts"]
    d = report["dataset_evaluated"]

    print("\n" + "=" * 70)
    print(f"  {report['experiment']}")
    print("=" * 70)
    print(f"Evaluated Records : {d['total_evaluated']} (Threshold T_high={d['t_high']})")
    print(f"Elapsed Time      : {m['elapsed_seconds']}s ({m['throughput_records_per_sec']:,} records/sec)")
    print("-" * 70)
    print(f"[*] Match Rate               : {m['match_rate_pct']:.1f}% ({c['correct_matches']} true matches resolved)")
    print(f"[*] Overall Accuracy         : {m['overall_accuracy_pct']:.1f}%")
    print(f"[*] Auto-Resolution Precision: {m['auto_resolution_precision_pct']:.1f}% (Honest precision)")
    print(f"[*] False-Resolution Rate    : {m['false_resolution_rate_pct']:.1f}% (Must be kept near 0%)")
    print(f"[*] Exception Rate           : {m['exception_rate_pct']:.1f}% ({c['exceptions_generated']} exceptions routed)")
    print("-" * 70)
    print("  SCENARIO PERFORMANCE BREAKDOWN")
    print("-" * 70)
    print(f"{'Scenario Tier':<16} | {'Total':<6} | {'Matched':<8} | {'Correct':<8} | {'Exceptions':<10}")
    print("-" * 70)
    for sc, stats in report["scenario_breakdown"].items():
        print(f"{sc:<16} | {stats['total']:<6} | {stats['auto_matched']:<8} | {stats['correct_match']:<8} | {stats['exception_raised']:<10}")
    print("=" * 70)
    print(f"Detailed JSON report saved to: data/generated/baseline_metrics.json\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate Deterministic Baseline Engine")
    parser.add_argument("--all", action="store_true", help="Evaluate across entire 100% dataset")
    parser.add_argument("--split", type=float, default=0.50, help="Test holdout fraction (default: 0.50)")
    parser.add_argument("--thigh", type=str, default="0.90", help="T_high threshold (default: 0.90)")
    args = parser.parse_args()

    res = evaluate_baseline(
        test_fraction=args.split,
        t_high=Decimal(args.thigh),
        eval_all=args.all,
    )
    print_evaluation_summary(res)
