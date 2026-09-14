"""Create a local test input with deterministic bad records.

The original Olist files remain untouched. This script will be run after the
source dataset is placed in data/raw/olist/.
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "data/raw/olist"
TARGET_DIR = ROOT / "data/raw/olist_demo"


def main() -> None:
    source = SOURCE_DIR / "olist_orders_dataset.csv"
    if not source.exists():
        raise FileNotFoundError(
            f"Missing {source}. Download the Olist dataset before running this script."
        )

    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    for source_file in SOURCE_DIR.glob("*.csv"):
        pd.read_csv(source_file).to_csv(TARGET_DIR / source_file.name, index=False)

    orders = pd.read_csv(source)
    corrupted = orders.head(5).copy()
    corrupted.loc[corrupted.index[0], "order_id"] = None
    corrupted.loc[corrupted.index[1], "order_status"] = "teleported"
    corrupted.loc[corrupted.index[2], "order_purchase_timestamp"] = None
    corrupted.loc[corrupted.index[3], "order_id"] = orders.iloc[0]["order_id"]
    corrupted.loc[corrupted.index[4], "order_delivered_customer_date"] = "2010-01-01 00:00:00"

    target = TARGET_DIR / "olist_orders_dataset.csv"
    pd.concat([orders, corrupted], ignore_index=True).to_csv(target, index=False)

    payments_file = SOURCE_DIR / "olist_order_payments_dataset.csv"
    if payments_file.exists():
        payments = pd.read_csv(payments_file)
        corrupt_payment = payments.head(1).copy()
        corrupt_payment.loc[corrupt_payment.index[0], "payment_value"] = -50
        pd.concat([payments, corrupt_payment], ignore_index=True).to_csv(
            TARGET_DIR / payments_file.name, index=False
        )
    print(f"Wrote intentionally bad records to {TARGET_DIR}")


if __name__ == "__main__":
    main()
