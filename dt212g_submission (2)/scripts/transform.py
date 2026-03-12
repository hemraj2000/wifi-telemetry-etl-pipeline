import argparse
from pathlib import Path
import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--in-root", default="/home/thehemraj/dt212g_project/artifacts")
    args = ap.parse_args()

    run_dir = Path(args.in_root) / args.run_id
    req_csv = run_dir / "raw_requests.csv"
    wifi_csv = run_dir / "wifi_link.csv"
    out_csv = run_dir / "analytics.csv"

    req = pd.read_csv(req_csv)
    wifi = pd.read_csv(wifi_csv)

    req["ts_ms"] = pd.to_numeric(req["ts_ms"], errors="coerce")
    wifi["ts_ms"] = pd.to_numeric(wifi["ts_ms"], errors="coerce")
    req = req.dropna(subset=["ts_ms", "sta"])
    wifi = wifi.dropna(subset=["ts_ms", "sta"])

    req["ts_s"] = (req["ts_ms"] // 1000).astype(int)
    wifi["ts_s"] = (wifi["ts_ms"] // 1000).astype(int)

    # keep last wifi sample per sta+second
    wifi = (
        wifi.sort_values(["sta", "ts_s", "ts_ms"])
            .groupby(["sta", "ts_s"], as_index=False)
            .last()
    )

    merged = req.merge(
        wifi[["sta", "ts_s", "ap", "rssi_dbm"]],
        on=["sta", "ts_s"],
        how="left",
    )

    merged = merged[["ts_ms", "sta", "status_code", "latency_ms", "ap", "rssi_dbm"]]
    merged.to_csv(out_csv, index=False)
    print(f"Wrote {out_csv}")


if __name__ == "__main__":
    main()
