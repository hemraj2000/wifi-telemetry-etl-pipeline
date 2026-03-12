#!/usr/bin/env python3
import argparse
from pathlib import Path
import pandas as pd


def asof_merge_per_sta(raw: pd.DataFrame, wifi: pd.DataFrame) -> pd.DataFrame:
    out = []
    for sta, r in raw.groupby("sta", sort=False):
        w = wifi[wifi["sta"] == sta].copy()

        r = r.sort_values("ts_ms").reset_index(drop=True)
        w = w.sort_values("ts_ms").reset_index(drop=True)

        merged = pd.merge_asof(
            r,
            w.drop(columns=["sta"]),
            on="ts_ms",
            direction="backward",
            tolerance=2000,  # ms tolerance
        )
        out.append(merged)

    return pd.concat(out, ignore_index=True) if out else raw


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--run-id", required=True)
    p.add_argument("--in-root", default="artifacts")
    args = p.parse_args()

    run_dir = Path(args.in_root) / args.run_id
    raw_path = run_dir / "raw_requests.csv"
    wifi_path = run_dir / "wifi_link.csv"
    out_path = run_dir / "analytics.csv"

    if not raw_path.exists():
        raise SystemExit(f"Missing {raw_path}")
    if not wifi_path.exists():
        raise SystemExit(f"Missing {wifi_path}")

    raw = pd.read_csv(raw_path)
    wifi = pd.read_csv(wifi_path)

    # Ensure types
    raw["ts_ms"] = pd.to_numeric(raw["ts_ms"], errors="coerce")
    wifi["ts_ms"] = pd.to_numeric(wifi["ts_ms"], errors="coerce")
    raw = raw.dropna(subset=["ts_ms", "sta"]).copy()
    wifi = wifi.dropna(subset=["ts_ms", "sta"]).copy()

    merged = asof_merge_per_sta(raw, wifi)
    merged.to_csv(out_path, index=False)
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
