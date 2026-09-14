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
- Used a 95% valid-record threshold as a circuit breaker.

## Evidence

Include the run summary, a sample quarantined row, before/after record counts, data-quality dashboard, and Gold business dashboard.

## Results

Fill in measured figures after the MVP runs: source rows, valid-row rate, quarantined rows by rule, pipeline duration, and the number of Gold marts produced.
