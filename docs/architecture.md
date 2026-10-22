# Architecture and quality strategy

## Layers

| Layer | Purpose | Example output |
| --- | --- | --- |
| Bronze | Preserve raw source structure and ingestion metadata. | `bronze_orders` |
| Quarantine | Retain rejected rows with a machine-readable failure reason. | `quarantine_orders` |
| Silver | Standardize types, remove invalid records, and deduplicate. | `silver_orders` |
| Gold | Business-facing, documented aggregates. | `gold_daily_sales`, `gold_delivery_performance` |

## Data-quality policy

Critical violations (`order_id` missing or duplicated, missing customer, invalid status, or missing purchase timestamp) prevent a row from entering Silver. A delivery timestamp before purchase time is a warning: it stays visible in quality metrics for investigation but does not stop the entire run.

The pipeline fails the run only when the valid-row rate falls below the configured 95% threshold. This is the circuit breaker: it protects downstream consumers without discarding evidence of bad source data. The ordering matters — Bronze, quarantine, and the quality report are always written first, and Silver and Gold are published only after every threshold has passed, so a failed run can never overwrite the tables a dashboard is already reading.

Warning-level rows stay in Silver and stay visible in quality metrics, but they are excluded from delivery measurements in Gold: `average_delivery_days` and `late_delivery_rate` aggregate only records whose delivery timestamp is at or after the purchase timestamp, so an impossible date can never distort a business metric. Row counts are untouched; only the measurement is guarded.

## Contract ownership

`contracts/odcs/*.odcs.yaml` are versioned Open Data Contract Standard (ODCS) contracts for the Silver data products. Data Contract CLI runs `lint` in CI and tests the local Silver Parquet output after a pipeline run. The separate Python contract evaluator is deliberately retained at the raw boundary because it adds an operational behavior that validation alone does not provide: row-level quarantine with failure reasons.

## Dashboard specification

The first dashboard has two views:

1. **Data operations:** latest run, freshness, valid-row rate, failed rules, and quarantine trend. Source: `quality_report.json`, `quality_report.csv`, and the quarantine tables.
2. **Business outcomes:** daily GMV, orders, average order value, delivery lead time, and delivery-status breakdown. Source: `gold_daily_sales` (time series) and `gold_delivery_performance` (per-status breakdown).

This makes the project demonstrably useful to both Data Engineering and business stakeholders.
