"""Synthetic financial dataset generator for Razorpay-style reconciliation.

Generates realistic, messy transaction data across the finance lifecycle:
  Orders -> Payments -> Settlements

Along with an isolated held-out ground truth file (never shown to the inference agent).

Difficulty Scenarios Produced:
  1. Exact Matches (1:1 clean IDs and amounts)
  2. Formatting Variations (delimiter noise, mixed casing, whitespace)
  3. Fee Deductions (gross payment - 2% standard fee = net settlement)
  4. Settlement Lag (settlement occurs T+2 days after payment)
  5. Partial / Split Settlements (partial net amount settled)
  6. Missing / Unsettled Payments (payment succeeded, no settlement exists)
  7. Adversarial / False Leads (identical amounts/dates for different orders)

Deterministic seed ensures fully reproducible datasets.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

SEED = 42
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
GEN_DIR = os.path.join(DATA_DIR, "generated")
GT_DIR = os.path.join(DATA_DIR, "ground_truth")

START_DATE = date(2026, 1, 1)

# Payment methods and their typical fee percentages
PAYMENT_METHODS = [
    ("UPI", Decimal("0.00")),            # 0% standard UPI
    ("CARD", Decimal("0.02")),           # 2.0% card processing fee
    ("NETBANKING", Decimal("0.015")),    # 1.5% netbanking fee
    ("WALLET", Decimal("0.018")),        # 1.8% wallet fee
]

CUSTOMERS = [f"CUST_{i:04d}" for i in range(1, 101)]


@dataclass
class OrderRecord:
    order_id: str
    customer_id: str
    amount: Decimal
    currency: str
    order_date: date
    status: str


@dataclass
class PaymentRecord:
    payment_id: str
    order_id: str
    amount: Decimal
    payment_date: date
    payment_method: str
    status: str
    reference: str


@dataclass
class SettlementRecord:
    settlement_id: str
    payment_reference: str
    gross_amount: Decimal
    fee: Decimal
    refund: Decimal
    net_amount: Decimal
    settlement_date: date
    status: str


@dataclass
class GroundTruthRecord:
    payment_id: str
    expected_settlement_id: str | None
    expected_status: str  # "MATCH", "UNMATCHED", "AMBIGUOUS_REVIEW"
    scenario_type: str    # "EXACT", "FORMATTING", "FEE", "DELAY", "PARTIAL", "MISSING", "ADVERSARIAL"
    expected_net: Decimal | None
    notes: str


def _dec_money(val: float | int | str) -> Decimal:
    """Format as 2-decimal place exact Decimal."""
    return Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _d(offset_days: int) -> date:
    return START_DATE + timedelta(days=offset_days)


def generate_dataset(num_records: int = 500, seed: int = SEED) -> dict:
    random.seed(seed)

    orders: list[OrderRecord] = []
    payments: list[PaymentRecord] = []
    settlements: list[SettlementRecord] = []
    ground_truth: list[GroundTruthRecord] = []

    # Scenario counts based on target distribution
    n_exact = int(num_records * 0.40)
    n_format = int(num_records * 0.15)
    n_fee = int(num_records * 0.15)
    n_delay = int(num_records * 0.10)
    n_partial = int(num_records * 0.10)
    n_missing = int(num_records * 0.05)
    n_adversarial = num_records - (n_exact + n_format + n_fee + n_delay + n_partial + n_missing)

    scenario_plan = (
        [("EXACT", "clean 1:1 match")] * n_exact
        + [("FORMATTING", "raw reference format discrepancy")] * n_format
        + [("FEE", "standard merchant processing fee deducted")] * n_fee
        + [("DELAY", "T+2 settlement delay within allowed policy")] * n_delay
        + [("PARTIAL", "partial reserve / incomplete payout")] * n_partial
        + [("MISSING", "payment exists without corresponding settlement")] * n_missing
        + [("ADVERSARIAL", "conflicting candidates with similar metadata")] * n_adversarial
    )
    random.shuffle(scenario_plan)

    order_counter = 1000
    payment_counter = 5000
    settlement_counter = 9000

    for idx, (scenario, note) in enumerate(scenario_plan, start=1):
        order_counter += 1
        payment_counter += 1
        
        ord_id = f"ORD_{order_counter}"
        pay_id = f"PAY_{payment_counter}"
        cust_id = random.choice(CUSTOMERS)
        raw_amt = _dec_money(random.randint(200, 50000) / 1.0)
        
        day_offset = random.randint(0, 60)
        pay_date = _d(day_offset)
        ord_date = pay_date  # order placed same day
        
        method, default_fee_rate = random.choice(PAYMENT_METHODS)
        curr = "INR"

        # Canonical reference format
        canonical_ref = f"RZP_REF_{order_counter}"

        # -------------------------------------------------------------
        # SCENARIO 1: EXACT MATCH (40%)
        # -------------------------------------------------------------
        if scenario == "EXACT":
            settlement_counter += 1
            set_id = f"SET_{settlement_counter}"
            
            # In exact scenario: clean reference, 0 fee, settled T+0 or T+1
            ref_str = canonical_ref
            gross = raw_amt
            fee = Decimal("0.00")
            refund = Decimal("0.00")
            net = gross - fee - refund
            settle_date = pay_date + timedelta(days=random.choice([0, 1]))

            orders.append(OrderRecord(ord_id, cust_id, raw_amt, curr, ord_date, "PAID"))
            payments.append(PaymentRecord(pay_id, ord_id, raw_amt, pay_date, method, "SUCCESS", ref_str))
            settlements.append(SettlementRecord(set_id, ref_str, gross, fee, refund, net, settle_date, "SETTLED"))
            ground_truth.append(GroundTruthRecord(pay_id, set_id, "MATCH", scenario, net, "Clean 1:1 match"))

        # -------------------------------------------------------------
        # SCENARIO 2: FORMATTING VARIATION (15%)
        # -------------------------------------------------------------
        elif scenario == "FORMATTING":
            settlement_counter += 1
            set_id = f"SET_{settlement_counter}"
            
            # Add delimiter variations, lowercase, or extra spaces
            format_type = random.choice(["dash", "slash", "lower", "spaces", "raw_num"])
            if format_type == "dash":
                pay_ref = f"RZP-REF-{order_counter}"
                set_ref = f"RZP_REF_{order_counter}"
            elif format_type == "slash":
                pay_ref = f"RZP/REF/{order_counter}"
                set_ref = f"RZPREF{order_counter}"
            elif format_type == "lower":
                pay_ref = f"rzp_ref_{order_counter}"
                set_ref = f"RZP_REF_{order_counter}"
            elif format_type == "spaces":
                pay_ref = f" RZP REF {order_counter} "
                set_ref = f"RZP_REF_{order_counter}"
            else:
                pay_ref = f"REF{order_counter}"
                set_ref = f"RZP_REF_{order_counter}"

            gross = raw_amt
            fee = Decimal("0.00")
            refund = Decimal("0.00")
            net = gross
            settle_date = pay_date + timedelta(days=1)

            orders.append(OrderRecord(ord_id, cust_id, raw_amt, curr, ord_date, "PAID"))
            payments.append(PaymentRecord(pay_id, ord_id, raw_amt, pay_date, method, "SUCCESS", pay_ref))
            settlements.append(SettlementRecord(set_id, set_ref, gross, fee, refund, net, settle_date, "SETTLED"))
            ground_truth.append(GroundTruthRecord(pay_id, set_id, "MATCH", scenario, net, f"Matched via format normalization ({format_type})"))

        # -------------------------------------------------------------
        # SCENARIO 3: FEE DEDUCTION (15%)
        # -------------------------------------------------------------
        elif scenario == "FEE":
            settlement_counter += 1
            set_id = f"SET_{settlement_counter}"
            
            # Exact fee computation: e.g. 2.0% card processing fee
            fee_rate = Decimal("0.02") if method == "CARD" else (Decimal("0.015") if method == "NETBANKING" else Decimal("0.018"))
            fee = _dec_money(raw_amt * fee_rate)
            if fee == Decimal("0.00"):
                fee = Decimal("15.00")  # Minimum flat fee
            gross = raw_amt
            refund = Decimal("0.00")
            net = gross - fee
            settle_date = pay_date + timedelta(days=1)

            orders.append(OrderRecord(ord_id, cust_id, raw_amt, curr, ord_date, "PAID"))
            payments.append(PaymentRecord(pay_id, ord_id, raw_amt, pay_date, method, "SUCCESS", canonical_ref))
            settlements.append(SettlementRecord(set_id, canonical_ref, gross, fee, refund, net, settle_date, "SETTLED"))
            ground_truth.append(GroundTruthRecord(pay_id, set_id, "MATCH", scenario, net, f"Net matched with fee {fee} ({fee_rate*100}%)"))

        # -------------------------------------------------------------
        # SCENARIO 4: SETTLEMENT LAG (T+2 DAYS) (10%)
        # -------------------------------------------------------------
        elif scenario == "DELAY":
            settlement_counter += 1
            set_id = f"SET_{settlement_counter}"
            
            lag_days = random.choice([2, 3])  # T+2 or T+3 within policy
            fee = _dec_money(raw_amt * Decimal("0.02")) if method == "CARD" else Decimal("0.00")
            gross = raw_amt
            refund = Decimal("0.00")
            net = gross - fee
            settle_date = pay_date + timedelta(days=lag_days)

            orders.append(OrderRecord(ord_id, cust_id, raw_amt, curr, ord_date, "PAID"))
            payments.append(PaymentRecord(pay_id, ord_id, raw_amt, pay_date, method, "SUCCESS", canonical_ref))
            settlements.append(SettlementRecord(set_id, canonical_ref, gross, fee, refund, net, settle_date, "SETTLED"))
            ground_truth.append(GroundTruthRecord(pay_id, set_id, "MATCH", scenario, net, f"Settlement delay T+{lag_days} days (valid by policy)"))

        # -------------------------------------------------------------
        # SCENARIO 5: PARTIAL / SPLIT SETTLEMENT (10%)
        # -------------------------------------------------------------
        elif scenario == "PARTIAL":
            settlement_counter += 1
            set_id = f"SET_{settlement_counter}"
            
            # Settlement only covers a percentage (e.g. 70% to 90% reserve holdback)
            partial_factor = Decimal(str(random.choice([0.70, 0.80, 0.85, 0.90])))
            gross = _dec_money(raw_amt * partial_factor)
            fee = Decimal("0.00")
            refund = Decimal("0.00")
            net = gross
            settle_date = pay_date + timedelta(days=1)

            orders.append(OrderRecord(ord_id, cust_id, raw_amt, curr, ord_date, "PAID"))
            payments.append(PaymentRecord(pay_id, ord_id, raw_amt, pay_date, method, "SUCCESS", canonical_ref))
            settlements.append(SettlementRecord(set_id, canonical_ref, gross, fee, refund, net, settle_date, "PARTIAL_SETTLED"))
            ground_truth.append(GroundTruthRecord(pay_id, set_id, "AMBIGUOUS_REVIEW", scenario, net, f"Partial settlement ({partial_factor*100}% of gross)"))

        # -------------------------------------------------------------
        # SCENARIO 6: MISSING SETTLEMENT (5%)
        # -------------------------------------------------------------
        elif scenario == "MISSING":
            orders.append(OrderRecord(ord_id, cust_id, raw_amt, curr, ord_date, "PAID"))
            payments.append(PaymentRecord(pay_id, ord_id, raw_amt, pay_date, method, "SUCCESS", canonical_ref))
            # No settlement created!
            ground_truth.append(GroundTruthRecord(pay_id, None, "UNMATCHED", scenario, None, "Unsettled transaction / Missing settlement record"))

        # -------------------------------------------------------------
        # SCENARIO 7: ADVERSARIAL / DUPLICATE LEADS (5%)
        # -------------------------------------------------------------
        elif scenario == "ADVERSARIAL":
            settlement_counter += 1
            set_id_1 = f"SET_{settlement_counter}"
            settlement_counter += 1
            set_id_2 = f"SET_{settlement_counter}"
            
            # Create two settlement candidates with identical amounts and same/near reference
            gross = raw_amt
            net = raw_amt
            settle_date = pay_date + timedelta(days=1)

            orders.append(OrderRecord(ord_id, cust_id, raw_amt, curr, ord_date, "PAID"))
            payments.append(PaymentRecord(pay_id, ord_id, raw_amt, pay_date, method, "SUCCESS", canonical_ref))
            
            # Candidate 1: Genuine
            settlements.append(SettlementRecord(set_id_1, canonical_ref, gross, Decimal("0.00"), Decimal("0.00"), net, settle_date, "SETTLED"))
            # Candidate 2: Ambiguous duplicate candidate
            settlements.append(SettlementRecord(set_id_2, f"{canonical_ref}_DUP", gross, Decimal("0.00"), Decimal("0.00"), net, settle_date, "SETTLED"))

            ground_truth.append(GroundTruthRecord(pay_id, set_id_1, "AMBIGUOUS_REVIEW", scenario, net, "Conflicting duplicate candidate requires investigation / human review"))

    return {
        "orders": orders,
        "payments": payments,
        "settlements": settlements,
        "ground_truth": ground_truth,
    }


def write_dataset_to_csv(data: dict) -> dict:
    os.makedirs(GEN_DIR, exist_ok=True)
    os.makedirs(GT_DIR, exist_ok=True)

    # 1. Write Orders CSV
    orders_path = os.path.join(GEN_DIR, "orders.csv")
    with open(orders_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["order_id", "customer_id", "amount", "currency", "order_date", "status"])
        for o in data["orders"]:
            writer.writerow([o.order_id, o.customer_id, str(o.amount), o.currency, o.order_date.isoformat(), o.status])

    # 2. Write Payments CSV
    payments_path = os.path.join(GEN_DIR, "payments.csv")
    with open(payments_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["payment_id", "order_id", "amount", "payment_date", "payment_method", "status", "reference"])
        for p in data["payments"]:
            writer.writerow([p.payment_id, p.order_id, str(p.amount), p.payment_date.isoformat(), p.payment_method, p.status, p.reference])

    # 3. Write Settlements CSV
    settlements_path = os.path.join(GEN_DIR, "settlements.csv")
    with open(settlements_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["settlement_id", "payment_reference", "gross_amount", "fee", "refund", "net_amount", "settlement_date", "status"])
        for s in data["settlements"]:
            writer.writerow([s.settlement_id, s.payment_reference, str(s.gross_amount), str(s.fee), str(s.refund), str(s.net_amount), s.settlement_date.isoformat(), s.status])

    # 4. Write Ground Truth CSV (Isolated)
    gt_path = os.path.join(GT_DIR, "ground_truth.csv")
    with open(gt_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["payment_id", "expected_settlement_id", "expected_status", "scenario_type", "expected_net", "notes"])
        for gt in data["ground_truth"]:
            writer.writerow([
                gt.payment_id,
                gt.expected_settlement_id or "",
                gt.expected_status,
                gt.scenario_type,
                str(gt.expected_net) if gt.expected_net is not None else "",
                gt.notes,
            ])

    # 5. Summary Statistics JSON
    scenario_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    for gt in data["ground_truth"]:
        scenario_counts[gt.scenario_type] = scenario_counts.get(gt.scenario_type, 0) + 1
        status_counts[gt.expected_status] = status_counts.get(gt.expected_status, 0) + 1

    summary = {
        "total_orders": len(data["orders"]),
        "total_payments": len(data["payments"]),
        "total_settlements": len(data["settlements"]),
        "total_ground_truth_records": len(data["ground_truth"]),
        "scenarios_breakdown": scenario_counts,
        "expected_statuses": status_counts,
        "seed": SEED,
    }

    summary_path = os.path.join(GEN_DIR, "_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic Razorpay reconciliation dataset")
    parser.add_argument("--records", type=int, default=500, help="Number of payment records to generate (default: 500)")
    parser.add_argument("--seed", type=int, default=SEED, help="Random seed for reproducibility")
    args = parser.parse_args()

    print(f"Generating synthetic dataset with {args.records} records (seed={args.seed})...")
    dataset = generate_dataset(num_records=args.records, seed=args.seed)
    summary_stats = write_dataset_to_csv(dataset)
    print("\nDataset Generation Complete!")
    print(json.dumps(summary_stats, indent=2))
