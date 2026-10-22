# Notion case study outline

## Title

Building a trustworthy e-commerce lakehouse with data contracts

## Problem

Source e-commerce extracts may be structurally valid files while containing missing keys, duplicate orders, invalid statuses, and implausible values. Without controls, those defects quietly reach dashboards.

## What I built

Describe the Bronze, Quarantine, Silver, and Gold flow; link to the repository; embed the architecture diagram and dashboard screenshots.

## Key engineering decisions

- Kept Bronze immutable for traceability and replay.
- Treated data contracts as versioned YAML in Git.
- Quarantined invalid rows rather than dropping them.
- Used a 95% valid-record rate as a circuit breaker, and publish Silver/Gold only after every threshold passes, so a failed run never overwrites healthy tables.
- Kept warning-level rows in Silver for investigation but excluded them from Gold delivery measurements, so an impossible timestamp cannot distort a business metric.

## Evidence

All of this is committed and reproducible:

- [`evidence/pipeline-run.md`](evidence/pipeline-run.md) — healthy run report, verbatim; contract-test output; artifacts produced.
- [`evidence/circuit-breaker.md`](evidence/circuit-breaker.md) — the deliberate >5% failure, with the report that recorded `"circuit_breaker": "open"` and MD5 proof that Silver and Gold were untouched.
- `screenshots/terminal-run-report.png` and `screenshots/terminal-circuit-breaker.png` — terminal transcripts of both runs (rendered from the verbatim transcripts above).
- `screenshots/dashboard-quality.png` and `screenshots/dashboard-full.png` — the two dashboard views.
- The ODCS HTML contract exports in `docs/generated/`.

Embed the terminal screenshot beside the run summary, and the quality dashboard screenshot beside the quarantine discussion.

## Results

Measured on the full Kaggle extract (99,441 orders, 103,886 payments) plus six deliberately injected defects:

- **Source rows read:** 99,446 orders and 103,887 payments (10 rows total are injected defects).
- **Valid-row rate:** orders 99.9909%, payments 99.9990% — both above the 95% circuit-breaker threshold, so the run completed.
- **Quarantined rows by rule:** orders — `duplicate:order_id` 6, `required:order_id` 1, `duplicate:order_id;invalid_value:order_status` 1, `duplicate:order_id;required:order_purchase_timestamp` 1; payments — `below_minimum:payment_value` 1.
- **Warnings (non-blocking):** 1 order with a delivery timestamp before purchase, retained in Silver and excluded from delivery measurements.
- **Pipeline duration:** 1.3–2.1 seconds end to end on a laptop (ingest → contract evaluation → quarantine → Silver → two Gold marts → run report).
- **Gold marts produced:** 2 — `daily_sales` (614 daily rows, 2016-09-04 to 2018-09-03, R$ 15,738,749 GMV) and `delivery_performance` (8 rows, one per order status; 12.5 average delivery days, 8.1% late-delivery rate for delivered orders).
- **Contract verification:** ODCS lint passes on both contracts; 39 automated checks pass against the Silver Parquet outputs.
- **Circuit breaker:** a 6,000-row failing input (93.9663% valid) exits with code 1 and records `"circuit_breaker": "open"` with an empty `gold_marts`, keeps all 6,000 rows in quarantine as evidence, and leaves the published Silver and Gold tables byte-identical (MD5 compared before and after the failed run).

Remaining before publishing: writing the Notion page itself from this outline.
