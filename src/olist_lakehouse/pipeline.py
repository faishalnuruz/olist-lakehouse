"""Local Bronze, Quarantine, Silver, and Gold pipeline for Olist extracts."""

from __future__ import annotations

import argparse
import json
import time
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


def build_delivery_performance(orders: pd.DataFrame) -> pd.DataFrame:
    """Build per-status delivery metrics, excluding physically impossible timestamps."""
    connection = duckdb.connect()
    connection.register("orders", orders)
    result = connection.execute(
        """
        SELECT o.order_status,
               COUNT(*) AS order_count,
               COUNT(*) FILTER (WHERE o.order_delivered_customer_date IS NOT NULL
                                  AND o.order_delivered_customer_date >= o.order_purchase_timestamp) AS measured_deliveries,
               ROUND(AVG(CASE WHEN o.order_delivered_customer_date >= o.order_purchase_timestamp
                              THEN date_diff('day', o.order_purchase_timestamp, o.order_delivered_customer_date)
                         END), 2) AS average_delivery_days,
               ROUND(AVG(CASE WHEN o.order_delivered_customer_date >= o.order_purchase_timestamp
                              THEN (o.order_delivered_customer_date > CAST(o.order_estimated_delivery_date AS TIMESTAMP))::INT
                         END), 4) AS late_delivery_rate
        FROM orders AS o
        GROUP BY 1
        ORDER BY 2 DESC
        """
    ).fetchdf()
    connection.close()
    return result


def write_report(report: dict[str, object]) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "quality_report.json").write_text(json.dumps(report, indent=2))
    pd.json_normalize(report["datasets"]).to_csv(OUTPUT / "quality_report.csv", index=False)


def run(input_dir: Path) -> dict[str, object]:
    started = time.perf_counter()
    orders = process_dataset(input_dir, "orders", "olist_orders_dataset.csv")
    payments = process_dataset(input_dir, "payments", "olist_order_payments_dataset.csv")
    report: dict[str, object] = {
        "run_at": datetime.now(UTC).isoformat(),
        "input_directory": str(input_dir),
        "datasets": [orders.report, payments.report],
        "circuit_breaker": "closed",
        "gold_marts": {},
    }
    failed = [item["dataset"] for item in report["datasets"] if not item["threshold_passed"]]
    if failed:
        # Keep Bronze, quarantine, and the run report as evidence, but never
        # overwrite the Silver and Gold tables published by the last healthy run.
        report["circuit_breaker"] = "open"
        report["duration_seconds"] = round(time.perf_counter() - started, 3)
        write_report(report)
        raise RuntimeError(f"Circuit breaker opened: quality threshold failed for {', '.join(failed)}")

    write_parquet(orders.valid, OUTPUT / "silver" / "orders.parquet")
    write_parquet(payments.valid, OUTPUT / "silver" / "payments.parquet")
    gold_daily_sales = build_gold(orders.valid, payments.valid)
    gold_delivery_performance = build_delivery_performance(orders.valid)
    write_parquet(gold_daily_sales, OUTPUT / "gold" / "daily_sales.parquet")
    write_parquet(gold_delivery_performance, OUTPUT / "gold" / "delivery_performance.parquet")
    report["gold_marts"] = {
        "daily_sales_rows": len(gold_daily_sales),
        "delivery_performance_rows": len(gold_delivery_performance),
    }
    report["duration_seconds"] = round(time.perf_counter() - started, 3)
    write_report(report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=RAW / "olist_demo" if (RAW / "olist_demo").exists() else RAW / "olist")
    args = parser.parse_args()
    print(json.dumps(run(args.input_dir), indent=2))


if __name__ == "__main__":
    main()
