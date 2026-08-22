"""Threshold Tuning & Pareto Frontier Analysis Script.

Sweeps T_high in [0.80, 0.85, 0.90, 0.95] and T_low in [0.40, 0.50, 0.60] to map
the trade-off between Precision, Recall, Auto-Resolution Rate, and Exception Volume.
"""

from __future__ import annotations

import csv
import json
import os
import sys
from decimal import Decimal

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.reconciliation.engine import run_deterministic_reconciliation
from app.reconciliation.normalizer import (
    NormalizedPayment,
    NormalizedSettlement,
    normalize_payment_row,
    normalize_settlement_row,
)

DATA_DIR = os.path.join(BASE_DIR, "data", "generated")
GROUND_TRUTH_PATH = os.path.join(BASE_DIR, "data", "ground_truth", "ground_truth.csv")
OUTPUT_PATH = os.path.join(DATA_DIR, "pareto_frontier.json")


def sweep_thresholds() -> list[dict]:
    payments_csv = os.path.join(DATA_DIR, "payments.csv")
    settlements_csv = os.path.join(DATA_DIR, "settlements.csv")

    with open(payments_csv, newline="", encoding="utf-8") as f:
        payments = [normalize_payment_row(r) for r in csv.DictReader(f)]

    with open(settlements_csv, newline="", encoding="utf-8") as f:
        settlements = [normalize_settlement_row(r) for r in csv.DictReader(f)]

    ground_truth = {}
    with open(GROUND_TRUTH_PATH, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            exp_sid = r.get("expected_settlement_id", "")
            ground_truth[r["payment_id"]] = {
                "settlement_id": exp_sid if exp_sid else None,
                "is_match": r.get("expected_status") == "MATCH",
            }

    total_true_matches = sum(1 for gt in ground_truth.values() if gt["is_match"])

    t_high_values = [0.80, 0.85, 0.90, 0.95]
    t_low_values = [0.40, 0.50, 0.60]

    sweep_results = []

    for th in t_high_values:
        for tl in t_low_values:
            if tl >= th:
                continue

            res = run_deterministic_reconciliation(
                payments=payments,
                settlements=settlements,
                t_high=Decimal(str(th)),
                t_low=Decimal(str(tl)),
                window_days=7,
            )

            matched_dict = {m.payment_id: m.settlement_id for m in res.matched}
            true_positives = 0
            false_positives = 0

            for pid, gt in ground_truth.items():
                if pid in matched_dict:
                    if matched_dict[pid] == gt["settlement_id"]:
                        true_positives += 1
                    else:
                        false_positives += 1

            precision = (true_positives / len(res.matched) * 100.0) if res.matched else 100.0
            recall = min(100.0, (true_positives / total_true_matches * 100.0)) if total_true_matches else 100.0
            match_rate = (len(res.matched) / len(payments) * 100.0) if payments else 0.0

            sweep_results.append({
                "t_high": th,
                "t_low": tl,
                "auto_resolved": len(res.matched),
                "exceptions": len(res.exceptions),
                "match_rate_pct": round(match_rate, 2),
                "precision_pct": round(precision, 2),
                "recall_pct": round(recall, 2),
                "throughput_rec_sec": round(res.throughput_per_second, 1),
            })

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(sweep_results, f, indent=2)

    return sweep_results


if __name__ == "__main__":
    print("=" * 70)
    print("  CONFIDENCE THRESHOLD GRID SEARCH & PARETO FRONTIER")
    print("=" * 70)
    results = sweep_thresholds()
    print(f"{'T_high':<8} | {'T_low':<8} | {'Auto-Resolved':<14} | {'Match Rate':<12} | {'Precision':<10} | {'Recall':<8}")
    print("-" * 70)
    for r in results:
        print(f"{r['t_high']:<8.2f} | {r['t_low']:<8.2f} | {r['auto_resolved']:<14} | {r['match_rate_pct']:>6.1f}%     | {r['precision_pct']:>6.1f}%   | {r['recall_pct']:>5.1f}%")
    print("=" * 70)
    print(f"Sweep results written to: {OUTPUT_PATH}\n")
