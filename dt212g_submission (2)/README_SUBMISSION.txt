DT212G WiFi Telemetry Pipeline – Submission

Included files:
1) roam17_artifacts.zip
   - raw_requests.csv: HTTP request logs (status + latency)
   - wifi_link.csv: WiFi link telemetry (AP + RSSI)
   - analytics.csv: merged dataset used for KPI calculation
   - report.txt: KPI report (success rate, mean latency, p95 latency, RSSI-based handover trigger)

2) dt212g_submission.zip
   - scripts/run_experiment.py: Mininet-WiFi experiment (two APs, two stations, one server)
   - scripts/transform.py: merges request logs + wifi telemetry into analytics.csv
   - scripts/report.py: generates report.txt

How to reproduce (Ubuntu):
sudo mn -c
sudo /usr/bin/python3 scripts/run_experiment.py --run-id roam17 --requests-per-sta 300 --move-after-sec 5 --sample-interval 1 --warmup-sec 10 --post_roam_hold_sec 20
python scripts/transform.py --run-id roam17
python scripts/report.py --run-id roam17
