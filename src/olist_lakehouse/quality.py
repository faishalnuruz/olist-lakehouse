"""Versioned, row-level data contract evaluation."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class ValidationResult:
    valid: pd.DataFrame
    quarantine: pd.DataFrame
    report: dict[str, object]


def _blank(series: pd.Series) -> pd.Series:
    return series.isna() | series.astype("string").str.strip().eq("")


def validate_dataframe(frame: pd.DataFrame, contract: dict) -> ValidationResult:
    """Evaluate critical column rules and retain every failed-rule reason."""
    frame = frame.copy()
    reasons = pd.Series("", index=frame.index, dtype="string")
    warning_count = 0

    def add_reason(mask: pd.Series, reason: str) -> None:
        nonlocal reasons
        was_empty = reasons.eq("")
        reasons = reasons.mask(mask & was_empty, reason)
        reasons = reasons.mask(mask & ~was_empty, reasons + ";" + reason)

    for column, rules in contract["columns"].items():
        if column not in frame.columns:
            add_reason(pd.Series(True, index=frame.index), f"missing_column:{column}")
            continue
        series = frame[column]
        if rules.get("required"):
            add_reason(_blank(series), f"required:{column}")
        if rules.get("unique"):
            add_reason(series.notna() & series.duplicated(keep=False), f"duplicate:{column}")
        if "allowed_values" in rules:
            add_reason(series.notna() & ~series.isin(set(rules["allowed_values"])), f"invalid_value:{column}")
        if rules.get("type") == "timestamp":
            parsed = pd.to_datetime(series, errors="coerce")
            add_reason(~_blank(series) & parsed.isna(), f"invalid_timestamp:{column}")
            frame[column] = parsed
        if "min_value" in rules:
            numeric = pd.to_numeric(series, errors="coerce")
            add_reason(~_blank(series) & (numeric.isna() | numeric.lt(rules["min_value"])) , f"below_minimum:{column}")
            frame[column] = numeric

    if {"order_delivered_customer_date", "order_purchase_timestamp"}.issubset(frame.columns):
        delivery = pd.to_datetime(frame["order_delivered_customer_date"], errors="coerce")
        purchase = pd.to_datetime(frame["order_purchase_timestamp"], errors="coerce")
        warning_count = int((delivery.notna() & purchase.notna() & delivery.lt(purchase)).sum())
        frame["order_delivered_customer_date"] = delivery

    valid_mask = reasons.eq("")
    quarantine = frame.loc[~valid_mask].copy()
    quarantine["failure_reason"] = reasons.loc[~valid_mask]
    valid = frame.loc[valid_mask].copy()
    total = len(frame)
    valid_rate = len(valid) / total if total else 0.0
    report = {
        "dataset": contract["dataset"], "total_rows": total, "valid_rows": len(valid),
        "quarantined_rows": len(quarantine), "valid_row_rate": round(valid_rate, 6),
        "quality_threshold": contract["quality_threshold"],
        "threshold_passed": valid_rate >= contract["quality_threshold"],
        "warning_count": warning_count,
        "failure_counts": quarantine["failure_reason"].value_counts().to_dict(),
    }
    return ValidationResult(valid=valid, quarantine=quarantine, report=report)
