# Evidence: the circuit breaker refuses to publish

Captured on 2026-10-22, local time UTC+7. This reproduces the scenario the README describes: an input with more than 5% invalid rows must fail the run, while Bronze, quarantine, and the run report are still written as evidence — and the published Silver and Gold tables must be left untouched.

## 1. Build the failing input

```bash
.venv/bin/python scripts/inject_quality_issues.py --circuit-breaker
```

```text
Wrote .../data/raw/olist_breaker
6000 of 99441 order statuses are invalid (expected valid-row rate 93.9663%, below the 95% threshold).
The pipeline must raise `Circuit breaker opened` and leave Silver and Gold untouched.
```

## 2. Run the pipeline against it

```bash
.venv/bin/python -m olist_lakehouse.pipeline --input-dir data/raw/olist_breaker
echo $?    # 1
```

The run exits with code **1**. The final lines of stderr, verbatim:

```text
Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File ".../src/olist_lakehouse/pipeline.py", line 140, in <module>
    main()
    ~~~~^^
  File ".../src/olist_lakehouse/pipeline.py", line 136, in main
    print(json.dumps(run(args.input_dir), indent=2))
  File ".../src/olist_lakehouse/pipeline.py", line 115, in run
    raise RuntimeError(f"Circuit breaker opened: quality threshold failed for {', '.join(failed)}")
RuntimeError: Circuit breaker opened: quality threshold failed for orders
```

## 3. The run report is still written, with the breaker open

`data/processed/quality_report.json` at the moment of failure, verbatim:

```json
{
  "run_at": "2026-10-22T11:04:09.042015+00:00",
  "input_directory": "data/raw/olist_breaker",
  "datasets": [
    {
      "dataset": "orders",
      "total_rows": 99441,
      "valid_rows": 93441,
      "quarantined_rows": 6000,
      "valid_row_rate": 0.939663,
      "quality_threshold": 0.95,
      "threshold_passed": false,
      "warning_count": 0,
      "failure_counts": {
        "invalid_value:order_status": 6000
      }
    },
    {
      "dataset": "payments",
      "total_rows": 103886,
      "valid_rows": 103886,
      "quarantined_rows": 0,
      "valid_row_rate": 1.0,
      "quality_threshold": 0.95,
      "threshold_passed": true,
      "warning_count": 0,
      "failure_counts": {}
    }
  ],
  "circuit_breaker": "open",
  "gold_marts": {},
  "duration_seconds": 1.039
}
```

Two things to read here: `"circuit_breaker": "open"` and `"gold_marts": {}`. Orders fell to **93.9663%**, below the 95% threshold, so nothing was published.

## 4. Published tables were not touched

MD5 of the Silver and Gold tables, taken immediately before and immediately after the failed run:

| file | before the failed run | after the failed run |
| --- | --- | --- |
| `silver/orders.parquet` | `6bb5e907344865e1dd400864b034712d` | `6bb5e907344865e1dd400864b034712d` |
| `silver/payments.parquet` | `4b5b01e0b7d7800dd018214505895bd0` | `4b5b01e0b7d7800dd018214505895bd0` |
| `gold/daily_sales.parquet` | `b79b5884a00416fe5387cbe8dbc0e64d` | `b79b5884a00416fe5387cbe8dbc0e64d` |
| `gold/delivery_performance.parquet` | `0fe125306141dcc789df387bd6d1280b` | `0fe125306141dcc789df387bd6d1280b` |

Byte-identical: a dashboard reading Silver or Gold during the failure sees the last healthy run.

File timestamps confirm which files the failed run wrote:

| file | last written | written by the failed run? |
| --- | --- | --- |
| `bronze/orders.parquet` | 18:04:08 | yes — raw input preserved |
| `quarantine/orders.parquet` | 18:04:08 | yes — 6,000 rejected rows kept |
| `quality_report.json` | 18:04:09 | yes — breaker recorded as `open` |
| `silver/orders.parquet` | 18:03:49 | no — still the healthy run |
| `gold/daily_sales.parquet` | 18:03:49 | no — still the healthy run |

## 5. Quarantine evidence

The rejected rows are queryable after the failure:

```text
quarantine orders rows: 6000
failure reason counts: {'invalid_value:order_status': 6000}
```

## Reproduce it

```bash
.venv/bin/python scripts/inject_quality_issues.py --circuit-breaker   # build the bad input
.venv/bin/python -m olist_lakehouse.pipeline --input-dir data/raw/olist_breaker
.venv/bin/python -m olist_lakehouse.pipeline                          # healthy run restores Silver and Gold
.venv/bin/python -m olist_lakehouse.dashboard                         # rebuild the dashboard from the healthy run
```
