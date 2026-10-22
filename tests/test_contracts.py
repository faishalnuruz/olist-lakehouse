import json

import pandas as pd
import pytest

from olist_lakehouse import pipeline
from olist_lakehouse.pipeline import load_contract
from olist_lakehouse.quality import validate_dataframe


def test_orders_contract_declares_required_primary_key() -> None:
    contract = load_contract("orders")
    assert contract["primary_key"] == "order_id"
    assert contract["columns"]["order_id"]["required"] is True


def test_orders_contract_quarantines_multiple_failure_types() -> None:
    frame = pd.DataFrame({
        "order_id": ["valid", "duplicate", "duplicate", None],
        "customer_id": ["c1", "c2", "c3", "c4"],
        "order_status": ["delivered", "delivered", "teleported", "delivered"],
        "order_purchase_timestamp": ["2018-01-01", "2018-01-01", "2018-01-01", "bad-date"],
        "order_delivered_customer_date": [None, None, None, None],
        "order_estimated_delivery_date": ["2018-01-05", "2018-01-05", "2018-01-05", "2018-01-05"],
    })
    result = validate_dataframe(frame, load_contract("orders"))
    assert result.report["valid_rows"] == 1
    assert result.report["quarantined_rows"] == 3
    # Each reason appears exactly once; distinct rules are joined in contract order.
    assert result.quarantine["failure_reason"].tolist() == [
        "duplicate:order_id",
        "duplicate:order_id;invalid_value:order_status",
        "required:order_id;invalid_timestamp:order_purchase_timestamp",
    ]


def test_orders_contract_quarantines_every_row_when_a_declared_column_is_absent() -> None:
    frame = pd.DataFrame({
        "order_id": ["o1"],
        "customer_id": ["c1"],
        "order_status": ["delivered"],
        "order_purchase_timestamp": ["2018-01-01"],
        "order_delivered_customer_date": [None],
    })
    result = validate_dataframe(frame, load_contract("orders"))
    assert result.report["valid_rows"] == 0
    assert result.quarantine["failure_reason"].iloc[0].endswith(
        "missing_column:order_estimated_delivery_date"
    )


def test_pipeline_writes_all_lakehouse_layers(tmp_path, monkeypatch) -> None:
    source = tmp_path / "source"
    source.mkdir()
    pd.DataFrame({
        "order_id": ["o1", "o2"], "customer_id": ["c1", "c2"],
        "order_status": ["delivered", "delivered"],
        "order_purchase_timestamp": ["2018-01-01", "2018-01-02"],
        "order_delivered_customer_date": ["2018-01-03", "2018-01-04"],
        "order_estimated_delivery_date": ["2018-01-05", "2018-01-06"],
    }).to_csv(source / "olist_orders_dataset.csv", index=False)
    pd.DataFrame({
        "order_id": ["o1", "o2"], "payment_sequential": [1, 1],
        "payment_type": ["credit_card", "voucher"], "payment_value": [100, 50],
    }).to_csv(source / "olist_order_payments_dataset.csv", index=False)
    monkeypatch.setattr(pipeline, "OUTPUT", tmp_path / "processed")
    monkeypatch.setattr(pipeline, "QUARANTINE", tmp_path / "quarantine")

    report = pipeline.run(source)

    assert report["datasets"][0]["threshold_passed"] is True
    assert (tmp_path / "processed/bronze/orders.parquet").exists()
    assert (tmp_path / "processed/silver/orders.parquet").exists()
    assert (tmp_path / "processed/gold/daily_sales.parquet").exists()
    assert (tmp_path / "processed/gold/delivery_performance.parquet").exists()
    assert (tmp_path / "processed/quality_report.json").exists()

    delivery = pd.read_parquet(tmp_path / "processed/gold/delivery_performance.parquet")
    assert list(delivery["order_status"]) == ["delivered"]
    assert delivery["average_delivery_days"].iloc[0] == 2.0


def test_circuit_breaker_preserves_evidence_but_blocks_downstream_writes(tmp_path, monkeypatch) -> None:
    source = tmp_path / "source"
    source.mkdir()
    pd.DataFrame({
        "order_id": [f"o{i}" for i in range(10)],
        "customer_id": [f"c{i}" for i in range(10)],
        "order_status": ["delivered"] * 8 + ["teleported", "teleported"],
        "order_purchase_timestamp": ["2018-01-01"] * 10,
        "order_delivered_customer_date": ["2018-01-03"] * 10,
        "order_estimated_delivery_date": ["2018-01-05"] * 10,
    }).to_csv(source / "olist_orders_dataset.csv", index=False)
    pd.DataFrame({
        "order_id": ["o0", "o1"], "payment_sequential": [1, 1],
        "payment_type": ["credit_card", "voucher"], "payment_value": [100, 50],
    }).to_csv(source / "olist_order_payments_dataset.csv", index=False)
    monkeypatch.setattr(pipeline, "OUTPUT", tmp_path / "processed")
    monkeypatch.setattr(pipeline, "QUARANTINE", tmp_path / "quarantine")

    # 8 of 10 orders are valid: 80% is below the 95% threshold, so the run must fail.
    with pytest.raises(RuntimeError, match="Circuit breaker opened"):
        pipeline.run(source)

    # Evidence is preserved for investigation...
    assert (tmp_path / "processed/bronze/orders.parquet").exists()
    assert (tmp_path / "quarantine/orders.parquet").exists()
    report = json.loads((tmp_path / "processed/quality_report.json").read_text())
    assert report["circuit_breaker"] == "open"
    assert report["datasets"][0]["threshold_passed"] is False

    # ...but no Silver or Gold table is published from a failed run.
    assert not (tmp_path / "processed/silver/orders.parquet").exists()
    assert not (tmp_path / "processed/gold/daily_sales.parquet").exists()
