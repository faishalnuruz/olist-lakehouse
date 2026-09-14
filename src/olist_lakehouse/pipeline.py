"""Local Bronze, Quarantine, Silver, and Gold pipeline for Olist extracts."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pandas as pd
import yaml

from olist_lakehouse.quality import ValidationResult, validate_dataframe

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw"
OUTPUT = ROOT / "data/processed"
QUARANTINE = ROOT / "data/quarantine"


def load_contract(name: str) -> dict:
    with (ROOT / "contracts" / f"{name}.yml").open() as contract_file:
        return yaml.safe_load(contract_file)


def write_parquet(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)


def process_dataset(input_dir: Path, name: str, source_file: str) -> ValidationResult:
    source = input_dir / source_file
    if not source.exists():
        raise FileNotFoundError(f"Missing {source}. See README.md for required Olist source files.")
    raw = pd.read_csv(source)
    raw["_ingested_at"] = pd.Timestamp.now(tz="UTC")
    write_parquet(raw, OUTPUT / "bronze" / f"{name}.parquet")
    result = validate_dataframe(raw, load_contract(name))
    write_parquet(result.quarantine, QUARANTINE / f"{name}.parquet")
    write_parquet(result.valid, OUTPUT / "silver" / f"{name}.parquet")
    return result


def build_gold(orders: pd.DataFrame, payments: pd.DataFrame) -> pd.DataFrame:
    """Build a dashboard-ready daily sales mart using DuckDB SQL."""
    connection = duckdb.connect()
    connection.register("orders", orders)
    connection.register("payments", payments)
    result = connection.execute(
        """
        SELECT CAST(o.order_purchase_timestamp AS DATE) AS order_date,
               COUNT(DISTINCT o.order_id) AS order_count,
               ROUND(SUM(COALESCE(p.payment_value, 0)), 2) AS gross_merchandise_value,
               ROUND(SUM(COALESCE(p.payment_value, 0)) / NULLIF(COUNT(DISTINCT o.order_id), 0), 2) AS average_order_value,
               ROUND(AVG(date_diff('day', o.order_purchase_timestamp, o.order_delivered_customer_date)), 2) AS average_delivery_days
        FROM orders AS o LEFT JOIN payments AS p USING (order_id)
        WHERE o.order_status NOT IN ('canceled', 'unavailable')
        GROUP BY 1 ORDER BY 1
        """
    ).fetchdf()
    connection.close()
    return result


def run(input_dir: Path) -> dict[str, object]:
    orders = process_dataset(input_dir, "orders", "olist_orders_dataset.csv")
    payments = process_dataset(input_dir, "payments", "olist_order_payments_dataset.csv")
    gold_daily_sales = build_gold(orders.valid, payments.valid)
    write_parquet(gold_daily_sales, OUTPUT / "gold" / "daily_sales.parquet")
    report = {
        "run_at": datetime.now(UTC).isoformat(),
        "input_directory": str(input_dir),
        "datasets": [orders.report, payments.report],
        "gold_marts": {"daily_sales_rows": len(gold_daily_sales)},
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "quality_report.json").write_text(json.dumps(report, indent=2))
    pd.json_normalize(report["datasets"]).to_csv(OUTPUT / "quality_report.csv", index=False)
    failed = [item["dataset"] for item in report["datasets"] if not item["threshold_passed"]]
    if failed:
        raise RuntimeError(f"Circuit breaker opened: quality threshold failed for {', '.join(failed)}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=RAW / "olist_demo" if (RAW / "olist_demo").exists() else RAW / "olist")
    args = parser.parse_args()
    print(json.dumps(run(args.input_dir), indent=2))


if __name__ == "__main__":
    main()
