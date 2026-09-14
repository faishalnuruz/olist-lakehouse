# Olist Lakehouse: Data Quality Contracts

An end-to-end local data engineering project using the public Olist Brazilian E-Commerce dataset. The pipeline turns raw CSV extracts into governed Bronze, Silver, and Gold tables while isolating invalid records instead of silently loading them.

## Portfolio story

E-commerce source data changes and degrades in production: required values are missing, keys are duplicated, and monetary values are invalid. This project applies a data contract before downstream transformations so that unreliable records are quarantined, healthy records continue to flow, and the data team can measure trust in the platform.

```text
Olist CSV extracts
      |
      v
Bronze: immutable raw tables
      |
      +--> data contract checks --> quarantine table + quality metrics
      |
      v
Silver: cleaned, typed, deduplicated tables
      |
      v
Gold: daily sales and delivery-performance marts --> BI dashboard
```

## Stack

- Python/Pandas for the local MVP; PySpark is included for the distributed-processing milestone
- Delta Lake / Parquet tables for the lakehouse layers
- Great Expectations-compatible YAML contracts (initially evaluated by project code)
- DuckDB for local inspection and dashboard-ready marts
- Metabase (planned) for the operations and business dashboard

## Data source

Download **Brazilian E-Commerce Public Dataset by Olist** from Kaggle and place the CSV files in `data/raw/olist/`. Do not commit the full source dataset. The raw data is used for learning and portfolio demonstration only; see the source dataset's terms before redistribution.

Expected files for the first MVP:

```text
data/raw/olist/
├── olist_orders_dataset.csv
├── olist_order_items_dataset.csv
├── olist_order_payments_dataset.csv
├── olist_customers_dataset.csv
└── olist_products_dataset.csv
```

## How to run

### 1. Install the project

```bash
git clone https://github.com/<your-github-username>/olist-lakehouse.git
cd olist-lakehouse
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

### 2. Download the source data

Download the Olist CSV archive from [Kaggle](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce), extract it, and copy the five CSV files listed above into `data/raw/olist/`.

### 3. Make the demo input

```bash
.venv/bin/python scripts/inject_quality_issues.py
```

This creates `data/raw/olist_demo/` and deliberately adds missing keys, duplicate order IDs, an invalid order status, a missing timestamp, a delivery-date warning, and a negative payment. The original download remains unchanged.

### 4. Run the lakehouse pipeline

```bash
.venv/bin/python -m olist_lakehouse.pipeline
```

### 5. Validate the trusted data product contract

```bash
./scripts/validate_contracts.sh
```

## Expected result

The pipeline should exit successfully because the injected defects are well below the 95% circuit-breaker threshold. It prints a JSON run report and writes these ignored local artifacts:

```text
data/processed/
├── bronze/orders.parquet
├── bronze/payments.parquet
├── silver/orders.parquet
├── silver/payments.parquet
├── gold/daily_sales.parquet
├── quality_report.csv
└── quality_report.json

data/quarantine/
├── orders.parquet        # failed rows and failure_reason
└── payments.parquet
```

With the current deterministic demo mutation, expect quarantined order records for missing/duplicate IDs, an invalid status, and a missing purchase time; one negative payment is quarantined. The delivery date before purchase is reported as a warning rather than blocking the record. `validate_contracts.sh` first lints both ODCS YAML files and then reports that both Silver data products comply with their contracts.

To prove the circuit breaker, temporarily increase the injected bad-record volume above 5% and re-run the pipeline. It will still preserve Bronze and quarantine evidence, but raises `Circuit breaker opened` and prevents a successful downstream run.

## MVP success criteria

- Raw source files are ingested into a Bronze layer without overwriting inputs.
- The orders contract catches null keys, invalid statuses, invalid timestamps, negative payment values, and duplicated order IDs.
- Invalid records are written to quarantine with a clear failure reason.
- Silver orders preserve only valid records and standardize timestamps/types.
- Gold marts answer daily sales and delivery-performance questions.
- Dashboard exposes freshness, quality score, failed-rule counts, quarantine volume, and core sales metrics.

## Repository map

```text
contracts/       Data-quality rules and expected schemas
docs/            Architecture, decisions, and Notion-ready project narrative
scripts/         Dataset preparation utilities
src/             Pipeline source code
tests/           Automated checks
data/             Ignored local inputs and generated outputs
```

## Data-contract workflow

The formal data product contracts are the ODCS files in `contracts/odcs/`. The free, open-source Data Contract CLI lints them and validates the resulting Silver Parquet tables. The Python validator remains responsible for row-level quarantine at ingestion, while ODCS documents and verifies the trusted output contract.

```bash
./scripts/validate_contracts.sh
.venv/bin/datacontract export html contracts/odcs/orders.odcs.yaml --output docs/generated/orders-contract.html
```

The HTML document can be committed and hosted with the repository or linked from the Notion case study.

## Roadmap

1. Local batch MVP with Olist orders and payments.
2. Add the remaining Olist dimensions, Gold marts, and a PySpark implementation.
3. Schedule runs with Airflow and send an alert when a quality threshold is breached.
4. Publish the dashboard and write the Notion case study.
