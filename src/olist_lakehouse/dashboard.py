"""Render the static data-operations and business-outcomes dashboard.

Reads the artifacts written by a successful pipeline run and produces one
self-contained HTML file. It depends only on the base project dependencies so
it can run anywhere the pipeline runs.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from olist_lakehouse.pipeline import OUTPUT, QUARANTINE, ROOT

TEMPLATE = Path(__file__).with_name("dashboard.html")
DEFAULT_OUTPUT = ROOT / "docs/generated/dashboard.html"


def _records(
    frame: pd.DataFrame, columns: list[str], limit: int, money_columns: tuple[str, ...] = ()
) -> list[dict]:
    """Return the first rows as JSON-ready strings, dropping absent columns."""
    present = [column for column in columns if column in frame.columns]
    sample = frame.loc[:, present].head(limit).copy()
    for column in money_columns:
        if column in sample.columns:
            values = pd.to_numeric(sample[column], errors="coerce")
            sample[column] = values.map(lambda value: "—" if pd.isna(value) else f"{value:.2f}")
    return sample.astype("string").fillna("—").to_dict(orient="records")


def _json_records(frame: pd.DataFrame) -> list[dict]:
    """Convert a frame to records, mapping missing values to JSON null."""
    return frame.astype(object).where(pd.notna(frame), None).to_dict(orient="records")


def _quarantine_samples(name: str, columns: list[str], money_columns: tuple[str, ...] = ()) -> list[dict]:
    path = QUARANTINE / f"{name}.parquet"
    if not path.exists():
        return []
    return _records(pd.read_parquet(path), columns, limit=6, money_columns=money_columns)


def _gold_frame(name: str) -> pd.DataFrame:
    path = OUTPUT / "gold" / f"{name}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}. Run the pipeline before building the dashboard.")
    return pd.read_parquet(path)


def build_payload() -> dict:
    """Collect the run report, quarantine evidence, and Gold marts."""
    report_path = OUTPUT / "quality_report.json"
    if not report_path.exists():
        raise FileNotFoundError(f"Missing {report_path}. Run the pipeline before building the dashboard.")
    report = json.loads(report_path.read_text())

    daily_sales = _gold_frame("daily_sales").assign(
        order_date=lambda frame: pd.to_datetime(frame["order_date"]).dt.strftime("%Y-%m-%d")
    )
    delivery = _gold_frame("delivery_performance")

    return {
        "run": {
            "run_at": report["run_at"],
            "duration_seconds": report.get("duration_seconds"),
            "circuit_breaker": report.get("circuit_breaker", "unknown"),
            "input_directory": Path(report["input_directory"]).name,
            "threshold": report["datasets"][0]["quality_threshold"],
            "gold_marts": report.get("gold_marts", {}),
        },
        "datasets": report["datasets"],
        "quarantine_samples": {
            "orders": _quarantine_samples(
                "orders", ["order_id", "order_status", "failure_reason"]
            ),
            "payments": _quarantine_samples(
                "payments", ["order_id", "payment_value", "failure_reason"],
                money_columns=("payment_value",),
            ),
        },
        "daily_sales": _json_records(daily_sales),
        "delivery": _json_records(delivery),
    }


def render(payload: dict, output: Path = DEFAULT_OUTPUT) -> Path:
    """Inject the payload into the packaged template and write the page."""
    document = TEMPLATE.read_text()
    # Guard against any data value closing the embedding <script> element.
    serialized = json.dumps(payload, default=str).replace("</", "<\\/")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document.replace("__PAYLOAD__", serialized))
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    path = render(build_payload(), args.output)
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
