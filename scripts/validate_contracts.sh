#!/usr/bin/env bash
set -euo pipefail

CONTRACTS=(contracts/odcs/orders.odcs.yaml contracts/odcs/payments.odcs.yaml)

for contract in "${CONTRACTS[@]}"; do
  .venv/bin/datacontract lint "$contract"
done

if [[ -f data/processed/silver/orders.parquet && -f data/processed/silver/payments.parquet ]]; then
  for contract in "${CONTRACTS[@]}"; do
    .venv/bin/datacontract test "$contract" --include-failed-samples
  done
else
  echo "Contracts linted. Run the pipeline first to test Silver Parquet data."
fi
