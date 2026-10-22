# Evidence: healthy end-to-end run

Captured on 2026-10-22, local time UTC+7, after `scripts/inject_quality_issues.py` in its default demo mode. This is the run the README numbers are taken from, and the run the committed dashboard screenshots show.

## Pipeline

```bash
.venv/bin/python -m olist_lakehouse.pipeline --input-dir data/raw/olist_demo
```

Exit code **0**. Verbatim run report:

```json
{
  "run_at": "2026-10-22T11:08:09.852266+00:00",
  "input_directory": "data/raw/olist_demo",
  "datasets": [
    {
      "dataset": "orders",
      "total_rows": 99446,
      "valid_rows": 99437,
      "quarantined_rows": 9,
      "valid_row_rate": 0.999909,
      "quality_threshold": 0.95,
      "threshold_passed": true,
      "warning_count": 1,
      "failure_counts": {
        "duplicate:order_id": 6,
        "required:order_id": 1,
        "duplicate:order_id;invalid_value:order_status": 1,
        "duplicate:order_id;required:order_purchase_timestamp": 1
      }
    },
    {
      "dataset": "payments",
      "total_rows": 103887,
      "valid_rows": 103886,
      "quarantined_rows": 1,
      "valid_row_rate": 0.99999,
      "quality_threshold": 0.95,
      "threshold_passed": true,
      "warning_count": 0,
      "failure_counts": {
        "below_minimum:payment_value": 1
      }
    }
  ],
  "circuit_breaker": "closed",
  "gold_marts": {
    "daily_sales_rows": 614,
    "delivery_performance_rows": 8
  },
  "duration_seconds": 1.211
}
```

Ten injected defects are held out of Silver (nine orders, one payment), the breaker stays `closed` because 99.99% is far above the 95% threshold, and both Gold marts are published.

## Contract validation

```bash
./scripts/validate_contracts.sh
```

Exit code **0**. Verbatim:

```text
🟢 data contract is valid. Run 1 checks. Took 0.158219 seconds.
🟢 data contract is valid. Run 1 checks. Took 0.162424 seconds.
🟢 data contract is valid. Run 22 checks. Took 0.86145 seconds.
🟢 data contract is valid. Run 17 checks. Took 0.750287 seconds.
```

The first two lines lint the ODCS YAML contracts; the last two run 22 checks against `silver/orders.parquet` and 17 against `silver/payments.parquet`.

## Artifacts written by this run

```text
data/processed/bronze/{orders,payments}.parquet
data/processed/silver/{orders,payments}.parquet
data/processed/gold/daily_sales.parquet          614 rows, 2016-09-04 → 2018-09-03, R$ 15,738,749 GMV
data/processed/gold/delivery_performance.parquet 8 rows, one per order status
data/processed/quality_report.{json,csv}
data/quarantine/{orders,payments}.parquet        9 + 1 rejected rows with failure_reason
```

## Dashboard

```bash
.venv/bin/python -m olist_lakehouse.dashboard
```

Writes `docs/generated/dashboard.html` from exactly these artifacts. Screenshots of the result are committed at `docs/screenshots/dashboard-quality.png` and `docs/screenshots/dashboard-full.png`.

## Tests

```text
7 passed in ~1s  (.venv/bin/python -m pytest -q)
```
