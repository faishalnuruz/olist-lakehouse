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

Include the run summary (`data/processed/quality_report.json`), a sample quarantined row with its `failure_reason`, before/after record counts, the ODCS HTML contract export, and the Gold business dashboard. Screenshots still to capture: the terminal run report, the quarantined-row table, and the dashboard.

## Results

Measured on the full Kaggle extract (99,441 orders, 103,886 payments) plus six deliberately injected defects:

- **Source rows read:** 99,446 orders and 103,887 payments (10 rows total are injected defects).
- **Valid-row rate:** orders 99.9909%, payments 99.9990% — both above the 95% circuit-breaker threshold, so the run completed.
- **Quarantined rows by rule:** orders — `duplicate:order_id` 6, `required:order_id` 1, `duplicate:order_id;invalid_value:order_status` 1, `duplicate:order_id;required:order_purchase_timestamp` 1; payments — `below_minimum:payment_value` 1.
- **Warnings (non-blocking):** 1 order with a delivery timestamp before purchase, retained in Silver and excluded from delivery measurements.
- **Pipeline duration:** 1.3–2.1 seconds end to end on a laptop (ingest → contract evaluation → quarantine → Silver → two Gold marts → run report).
- **Gold marts produced:** 2 — `daily_sales` (614 daily rows, 2016-09-04 to 2018-09-03, R$ 15,738,749 GMV) and `delivery_performance` (8 rows, one per order status; 12.5 average delivery days, 8.1% late-delivery rate for delivered orders).
- **Contract verification:** ODCS lint passes on both contracts; 39 automated checks pass against the Silver Parquet outputs.

Still missing before publishing: dashboard screenshots, and the circuit-breaker demo run above the 5% defect rate.
