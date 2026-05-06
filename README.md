# DT023G WiFi Telemetry ETL Pipeline Extension

Students: Hem Raj & Mohit Kumar

This repository contains the final DT023G WiFi Telemetry ETL Pipeline output and documentation.

## Final Refined Output

| Metric | Value |
|---|---:|
| Total Requests | 8000 |
| Successful Requests | 8000 |
| Failed Requests | 0 |
| Success Rate | 100.0% |
| Mean Latency | 12.32 ms |
| P95 Latency | 18.87 ms |
| Roaming Events | 1 |
| Access Points | 4 |
| Stations | 4 |
| Requests per Station | 2000 |

## Main Improvement

The DT023G project extends the previous DT212G prototype by increasing the topology from 2 APs / 2 stations to 4 APs / 4 stations and increasing the workload to 8000 total HTTP requests.

The final refined run achieved 100.0% success rate with 0 failed requests.

## Important Files

- `docs/DT023G_Final_Comparison_Report_Hem_Raj_Mohit_Kumar.docx`
- `docs/DT023G_Final_Comparison_Presentation_Hem_Raj_Mohit_Kumar.pptx`
- `artifacts/final_refined_output/report.txt`
- `artifacts/final_refined_output/final_metrics.csv`
- `artifacts/final_refined_output/comparison_dt212g_dt023g.csv`
- `artifacts/final_refined_output/dt023g_refinement_comparison.csv`
- `artifacts/final_refined_output/roaming_events.csv`

## Project Workflow

```text
Mininet-WiFi Experiment
        ↓
Raw Telemetry Logs
        ↓
Pandas Transform
        ↓
Graph Generation
        ↓
KPI Report
        ↓
Airflow Evidence
```

## Conclusion

The final DT023G project is larger, more reliable, and easier to explain than the previous DT212G version. It provides better workflow evidence, stronger reporting, and clearer comparison results.
