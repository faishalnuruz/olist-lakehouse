# Architecture and quality strategy

## Layers

| Layer | Purpose | Example output |
| --- | --- | --- |
| Bronze | Preserve raw source structure and ingestion metadata. | `bronze_orders` |
| Quarantine | Retain rejected rows with a machine-readable failure reason. | `quarantine_orders` |
| Silver | Standardize types, remove invalid records, and deduplicate. | `silver_orders` |
| Gold | Business-facing, documented aggregates. | `gold_daily_sales` |

## Data-quality policy

Critical violations (`order_id` missing or duplicated, missing customer, invalid status, or missing purchase timestamp) prevent a row from entering Silver. A delivery timestamp before purchase time is a warning: it stays visible in quality metrics for investigation but does not stop the entire run.

The pipeline fails the run only when the valid-row rate falls below the configured 95% threshold. This is the circuit breaker: it protects downstream consumers without discarding evidence of bad source data.

## Contract ownership

`contracts/odcs/*.odcs.yaml` are versioned Open Data Contract Standard (ODCS) contracts for the Silver data products. Data Contract CLI runs `lint` in CI and tests the local Silver Parquet output after a pipeline run. The separate Python contract evaluator is deliberately retained at the raw boundary because it adds an operational behavior that validation alone does not provide: row-level quarantine with failure reasons.

## Dashboard specification

The first dashboard has two views:

1. **Data operations:** latest run, freshness, valid-row rate, failed rules, and quarantine trend.
2. **Business outcomes:** daily GMV, orders, average order value, delivery lead time, and delivery-status breakdown.

This makes the project demonstrably useful to both Data Engineering and business stakeholders.
