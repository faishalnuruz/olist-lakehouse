"""Create local test inputs with deliberate data defects.

Two modes:

* Default: small, deterministic defects in ``data/raw/olist_demo`` for the
  normal demo run. The original download remains untouched.
* ``--circuit-breaker``: an input in ``data/raw/olist_breaker`` with enough
  invalid rows to fall below the 95% threshold, used to demonstrate that the
  pipeline refuses to publish Silver and Gold when quality collapses.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "data/raw/olist"
DEMO_DIR = ROOT / "data/raw/olist_demo"
BREAKER_DIR = ROOT / "data/raw/olist_breaker"

# Above 5% of the 99,441 source orders, so the 95% threshold must trip.
BREAKER_INVALID_ROWS = 6_000


def require_source() -> Path:
    source = SOURCE_DIR / "olist_orders_dataset.csv"
    if not source.exists():
        raise FileNotFoundError(
            f"Missing {source}. Download the Olist dataset before running this script."
        )
    return source


def build_demo_input() -> None:
    source = require_source()
    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    for source_file in SOURCE_DIR.glob("*.csv"):
        pd.read_csv(source_file).to_csv(DEMO_DIR / source_file.name, index=False)

    orders = pd.read_csv(source)
    corrupted = orders.head(5).copy()
    corrupted.loc[corrupted.index[0], "order_id"] = None
    corrupted.loc[corrupted.index[1], "order_status"] = "teleported"
    corrupted.loc[corrupted.index[2], "order_purchase_timestamp"] = None
    corrupted.loc[corrupted.index[3], "order_id"] = orders.iloc[0]["order_id"]
    corrupted.loc[corrupted.index[4], "order_delivered_customer_date"] = "2010-01-01 00:00:00"

    target = DEMO_DIR / "olist_orders_dataset.csv"
    pd.concat([orders, corrupted], ignore_index=True).to_csv(target, index=False)

    payments_file = SOURCE_DIR / "olist_order_payments_dataset.csv"
    if payments_file.exists():
        payments = pd.read_csv(payments_file)
        corrupt_payment = payments.head(1).copy()
        corrupt_payment.loc[corrupt_payment.index[0], "payment_value"] = -50
        pd.concat([payments, corrupt_payment], ignore_index=True).to_csv(
            DEMO_DIR / payments_file.name, index=False
        )
    print(f"Wrote intentionally bad records to {DEMO_DIR}")


def build_breaker_input() -> None:
    source = require_source()
    BREAKER_DIR.mkdir(parents=True, exist_ok=True)
    for source_file in SOURCE_DIR.glob("*.csv"):
        if source_file.name != source.name:
            shutil.copyfile(source_file, BREAKER_DIR / source_file.name)

    orders = pd.read_csv(source)
    total_rows = len(orders)
    orders.loc[orders.index[:BREAKER_INVALID_ROWS], "order_status"] = "teleported"
    orders.to_csv(BREAKER_DIR / source.name, index=False)

    expected_rate = 1 - BREAKER_INVALID_ROWS / total_rows
    print(f"Wrote {BREAKER_DIR}")
    print(
        f"{BREAKER_INVALID_ROWS} of {total_rows} order statuses are invalid "
        f"(expected valid-row rate {expected_rate:.4%}, below the 95% threshold)."
    )
    print("The pipeline must raise `Circuit breaker opened` and leave Silver and Gold untouched.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--circuit-breaker",
        action="store_true",
        help="build an input that fails the 95%% threshold instead of the small demo defects",
    )
    args = parser.parse_args()
    if args.circuit_breaker:
        build_breaker_input()
    else:
        build_demo_input()


if __name__ == "__main__":
    main()
