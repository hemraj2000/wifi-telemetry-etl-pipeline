import argparse
from pathlib import Path
import numpy as np
import pandas as pd


def pct(x: float) -> str:
    if pd.isna(x):
        return "nan%"
    return f"{x:.2f}%"


def ms(x: float) -> str:
    if pd.isna(x):
        return "nan ms"
    return f"{x:.2f} ms"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--in-root", default="/home/thehemraj/dt212g_project/artifacts")
    args = ap.parse_args()

    run_dir = Path(args.in_root) / args.run_id
    analytics_path = run_dir / "analytics.csv"
    out_path = run_dir / "report.txt"

    df = pd.read_csv(analytics_path)

    # Basic cleanup
    df["status_code"] = df["status_code"].astype(str)
    df["latency_ms"] = pd.to_numeric(df["latency_ms"], errors="coerce")
    df["rssi_dbm"] = pd.to_numeric(df.get("rssi_dbm"), errors="coerce") if "rssi_dbm" in df.columns else np.nan

    ok = df["status_code"].str.fullmatch(r"2\d\d")  # 200-299
    success_rate = 100.0 * ok.mean() if len(df) else np.nan

    latency_mean = df.loc[ok, "latency_ms"].mean()
    latency_p95 = df.loc[ok, "latency_ms"].quantile(0.95)

    lines = []
    lines.append("WiFi Telemetry KPI Report")
    lines.append(f"Run: {args.run_id}")
    lines.append("")
    lines.append(f"Success rate: {pct(success_rate)}")
    lines.append(f"Latency mean: {ms(latency_mean)}")
    lines.append(f"Latency p95 : {ms(latency_p95)}")
    lines.append("")
    lines.append("Roaming indicator:")

    # --- Per-station roaming analysis ---
    for sta, g in df.groupby("sta"):
        g = g.copy()
        g = g.sort_values("ts_ms")

        # 1) AP-based roaming if we actually have AP labels and changes
        ap_col = g["ap"] if "ap" in g.columns else pd.Series([], dtype=str)
        ap_changes = 0
        if "ap" in g.columns:
            ap_clean = ap_col.fillna("").astype(str)
            ap_clean = ap_clean[ap_clean != ""]
            if len(ap_clean) > 1:
                ap_changes = int((ap_clean != ap_clean.shift(1)).sum() - 1)  # number of switches

        if ap_changes > 0:
            lines.append(f"- {sta}: roaming detected (AP switches = {ap_changes})")
            continue

        # 2) RSSI-based trigger (for environments where AP doesn't switch)
        if "rssi_dbm" not in g.columns or g["rssi_dbm"].dropna().empty:
            lines.append(f"- {sta}: no roaming detected (no RSSI data)")
            continue

        # Create 1-second bins for stability
        g["ts_s"] = (g["ts_ms"] // 1000).astype(int)
        rssi_s = g.groupby("ts_s")["rssi_dbm"].median().dropna()

        if len(rssi_s) < 6:
            lines.append(f"- {sta}: no roaming detected (insufficient RSSI samples)")
            continue

        # Detect "move moment" as max absolute RSSI delta between consecutive seconds
        delta = (rssi_s - rssi_s.shift(1)).abs().dropna()
        move_ts_s = int(delta.idxmax())
        move_mag = float(delta.loc[move_ts_s])

        # Compare RSSI before vs after move
        before = rssi_s[rssi_s.index < move_ts_s].tail(3)
        after = rssi_s[rssi_s.index >= move_ts_s].head(3)

        rssi_before = float(before.mean()) if not before.empty else np.nan
        rssi_after = float(after.mean()) if not after.empty else np.nan

        # Heuristic: consider "roaming event" if RSSI shifts by >= 6 dB around move
        if not pd.isna(rssi_before) and not pd.isna(rssi_after) and abs(rssi_after - rssi_before) >= 6:
            lines.append(
                f"- {sta}: AP did not change; RSSI-based handover trigger at ~{move_ts_s} (Δ≈{abs(rssi_after - rssi_before):.1f} dB, "
                f"before≈{rssi_before:.1f} dBm, after≈{rssi_after:.1f} dBm)"
            )
        else:
            lines.append(f"- {sta}: no roaming detected")

    lines.append("")
    lines.append("Note: If AP never changes, this Mininet-WiFi environment may not support programmatic reassociation; RSSI-based trigger is used.")

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
