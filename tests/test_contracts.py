import pandas as pd

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
    })
    result = validate_dataframe(frame, load_contract("orders"))
    assert result.report["valid_rows"] == 1
    assert result.report["quarantined_rows"] == 3
    assert "duplicate:order_id" in result.quarantine["failure_reason"].iloc[0]
    assert "required:order_id" in result.quarantine["failure_reason"].iloc[-1]


def test_pipeline_writes_all_lakehouse_layers(tmp_path, monkeypatch) -> None:
    source = tmp_path / "source"
    source.mkdir()
    pd.DataFrame({
        "order_id": ["o1", "o2"], "customer_id": ["c1", "c2"],
        "order_status": ["delivered", "delivered"],
        "order_purchase_timestamp": ["2018-01-01", "2018-01-02"],
        "order_delivered_customer_date": ["2018-01-03", "2018-01-04"],
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
    assert (tmp_path / "processed/quality_report.json").exists()
