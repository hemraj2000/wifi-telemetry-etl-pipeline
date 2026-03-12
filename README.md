# WiFi Telemetry ETL Pipeline

This project implements a WiFi telemetry ETL pipeline using Mininet-WiFi, Python, pandas, and Apache Airflow.

## Project workflow
1. Run WiFi experiment with two access points, two stations, and one HTTP server
2. Collect raw request logs and WiFi link logs
3. Transform raw data into analytics
4. Generate KPI report

## Main folders
- `dags/` – Airflow DAG
- `scripts/` – experiment, transform, and report scripts
- `artifacts/airflow_final/` – final output files

## Final outputs
- `raw_requests.csv`
- `wifi_link.csv`
- `analytics.csv`
- `report.txt`

## Final result
- Success rate: 99.55%
- Roaming detected for both stations
- Airflow DAG executed successfully
