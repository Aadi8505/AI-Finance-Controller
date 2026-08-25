"""Utility script to reset reconciliation state in the database.

Clears:
- reconciliation_results
- exceptions
- human_reviews
- reconciliation_runs

Preserves:
- orders (500)
- payments (500)
- settlements (500)
"""

from __future__ import annotations

import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.db.database import get_db_session, init_db
from app.models.entities import (
    ExceptionModel,
    HumanReviewModel,
    PaymentModel,
    ReconciliationResultModel,
    ReconciliationRunModel,
    SettlementModel,
)


def reset_reconciliation_state():
    init_db()
    with get_db_session() as session:
        n_hr = session.query(HumanReviewModel).delete()
        n_rr = session.query(ReconciliationResultModel).delete()
        n_ex = session.query(ExceptionModel).delete()
        n_run = session.query(ReconciliationRunModel).delete()
        session.commit()

        p_count = session.query(PaymentModel).count()
        s_count = session.query(SettlementModel).count()

    print("=" * 60)
    print("  [OK] Reconciliation State Successfully Reset to Clean Initial State")
    print("=" * 60)
    print(f"  - Reconciled Results Cleared : {n_rr}")
    print(f"  - Exceptions Cleared         : {n_ex}")
    print(f"  - Human Reviews Cleared      : {n_hr}")
    print(f"  - Runs Cleared               : {n_run}")
    print(f"  - Raw Payments Available     : {p_count} (ready for reconciliation)")
    print(f"  - Raw Settlements Available  : {s_count} (ready for reconciliation)")
    print("=" * 60)
    print("  You can now open the Streamlit dashboard and start the live demo walkthrough from scratch!")
    print("=" * 60)


if __name__ == "__main__":
    reset_reconciliation_state()
