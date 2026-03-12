#!/usr/bin/env python3
import argparse
from pathlib import Path
import numpy as np
import pandas as pd


def pct(x: float) -> str:
    return f"{x*100:.2f}%"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--run-id", required=True)
    p.add_argument("--in-root", default="artifacts")
    args = p.parse_args()

    run_dir = Path(args.in_root) / args.run_id
    analytics_path = run_dir / "analytics.csv"
    out_path = run_dir / "report.txt"

    if not analytics_path.exists():
        raise SystemExit(f"Missing {analytics_path}")

    df = pd.read_csv(analytics_path)

    # success = HTTP 200
    df["status_code"] = pd.to_numeric(df["status_code"], errors="coerce")
    df["latency_ms"] = pd.to_numeric(df["latency_ms"], errors="coerce")

    total = len(df)
    ok = int((df["status_code"] == 200).sum()) if total else 0
    success_rate = (ok / total) if total else 0.0

    lat_ok = df.loc[df["status_code"] == 200, "latency_ms"].dropna()
    if len(lat_ok) > 0:
        lat_mean = float(lat_ok.mean())
        lat_p95 = float(np.percentile(lat_ok, 95))
        lat_mean_s = f"{lat_mean:.2f} ms"
        lat_p95_s = f"{lat_p95:.2f} ms"
    else:
        lat_mean_s = "N/A"
        lat_p95_s = "N/A"

    # Roaming indicator from analytics (ap changes)
    roaming_lines = []
    if "ap" in df.columns and "sta" in df.columns:
        for sta in sorted(df["sta"].dropna().unique()):
            s = df[df["sta"] == sta]["ap"].dropna()
            uniq = list(s.unique())
            if len(uniq) >= 2:
                roaming_lines.append(f"- {sta}: AP changed ({uniq})")
            elif len(uniq) == 1:
                roaming_lines.append(f"- {sta}: AP did not change ({uniq[0]})")
            else:
                roaming_lines.append(f"- {sta}: Not enough RSSI/AP data")
    else:
        roaming_lines.append("- Not enough RSSI/AP data")

    text = []
    text.append("WiFi Telemetry KPI Report")
    text.append(f"Run: {args.run_id}")
    text.append("")
    text.append(f"Success rate: {pct(success_rate)}")
    text.append(f"Latency mean: {lat_mean_s}")
    text.append(f"Latency p95 : {lat_p95_s}")
    text.append("")
    text.append("Roaming indicator:")
    text.extend(roaming_lines)
    text.append("")
    text.append("Note: If AP never changes, this Mininet-WiFi environment may not support programmatic reassociation; RSSI/AP data may be missing.")
    out_path.write_text("\n".join(text), encoding="utf-8")

    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
