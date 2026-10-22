import json

import pandas as pd
import pytest

from olist_lakehouse import dashboard, pipeline


def _seed_artifacts(tmp_path, monkeypatch) -> None:
    source = tmp_path / "source"
    source.mkdir()
    pd.DataFrame({
        "order_id": ["o1", "o2"], "customer_id": ["c1", "c2"],
        "order_status": ["delivered", "delivered"],
        "order_purchase_timestamp": ["2018-01-01", "2018-01-02"],
        "order_delivered_customer_date": ["2018-01-03", None],
        "order_estimated_delivery_date": ["2018-01-05", "2018-01-06"],
    }).to_csv(source / "olist_orders_dataset.csv", index=False)
    pd.DataFrame({
        "order_id": ["o1", "o2"], "payment_sequential": [1, 1],
        "payment_type": ["credit_card", "voucher"], "payment_value": [100, 50],
    }).to_csv(source / "olist_order_payments_dataset.csv", index=False)
    for module in (pipeline, dashboard):
        monkeypatch.setattr(module, "OUTPUT", tmp_path / "processed")
        monkeypatch.setattr(module, "QUARANTINE", tmp_path / "quarantine")
    pipeline.run(source)


def test_dashboard_renders_run_report_and_gold_marts(tmp_path, monkeypatch) -> None:
    _seed_artifacts(tmp_path, monkeypatch)

    output = dashboard.render(dashboard.build_payload(), tmp_path / "dashboard.html")
    html = output.read_text()

    assert "__PAYLOAD__" not in html
    assert 'id="gmv-chart"' in html
    assert 'id="scores"' in html

    prefix, remainder = html.split("window.__DASHBOARD__ = ", 1)
    payload = json.loads(
        remainder.split(";\n", 1)[0],
        parse_constant=lambda value: pytest.fail(f"non-standard JSON constant in payload: {value}"),
    )
    assert prefix  # the payload is embedded inside the template
    assert payload["run"]["circuit_breaker"] == "closed"
    assert payload["datasets"][0]["valid_row_rate"] == 1.0
    assert payload["daily_sales"] and payload["delivery"]
    assert payload["daily_sales"][0]["order_date"] == "2018-01-01"
    # A day whose only order has no delivery date must serialize as JSON null,
    # never as NaN.
    assert payload["daily_sales"][1]["average_delivery_days"] is None
    assert payload["quarantine_samples"]["payments"] == []


def test_dashboard_explains_missing_artifacts(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(dashboard, "OUTPUT", tmp_path / "processed")
    with pytest.raises(FileNotFoundError, match="Run the pipeline"):
        dashboard.build_payload()
