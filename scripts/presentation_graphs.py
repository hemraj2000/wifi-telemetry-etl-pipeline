import argparse
import re
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt


def find_col(df, names):
    cols = {c.lower().strip(): c for c in df.columns}
    for name in names:
        if name.lower() in cols:
            return cols[name.lower()]

    for c in df.columns:
        low = c.lower()
        for name in names:
            if name.lower() in low:
                return c
    return None


def to_num(value):
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"-?\d+\.?\d*", str(value))
    return float(match.group()) if match else None


def style_graph(ax):
    ax.grid(axis="y", alpha=0.25)
    for side in ["top", "right"]:
        ax.spines[side].set_visible(False)
    ax.tick_params(axis="x", labelrotation=20)


def add_labels(ax, suffix=""):
    for bar in ax.patches:
        height = bar.get_height()
        if height is not None:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                height,
                f"{height:.2f}{suffix}",
                ha="center",
                va="bottom",
                fontsize=10,
            )


def save(fig, out_path):
    fig.tight_layout()
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out_path}")


def success_from_status(series):
    s = series.astype(str).str.lower()
    return (
        s.str.startswith("2")
        | s.isin(["success", "true", "ok", "200"])
    )


def plot_success_by_station(raw, out_dir):
    station_col = find_col(raw, ["station", "sta", "client"])
    status_col = find_col(raw, ["status_code", "status", "http_status"])

    if not station_col or not status_col:
        return

    raw["success_flag"] = success_from_status(raw[status_col])
    data = raw.groupby(station_col)["success_flag"].mean().mul(100).reset_index()
    data.columns = ["Station", "Success Rate"]

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(data["Station"], data["Success Rate"])
    ax.set_title("Success Rate by Station", fontsize=18, weight="bold")
    ax.set_xlabel("Station", fontsize=13)
    ax.set_ylabel("Success Rate (%)", fontsize=13)
    ax.set_ylim(0, 105)
    style_graph(ax)
    add_labels(ax, "%")
    save(fig, out_dir / "01_success_rate_by_station.png")


def plot_latency_over_time(raw, out_dir):
    latency_col = find_col(raw, ["latency_ms", "latency", "response_time_ms"])
    time_col = find_col(raw, ["timestamp", "time", "ts"])
    station_col = find_col(raw, ["station", "sta", "client"])

    if not latency_col:
        return

    raw[latency_col] = pd.to_numeric(raw[latency_col], errors="coerce")
    raw = raw.dropna(subset=[latency_col]).copy()

    if time_col:
        raw[time_col] = pd.to_datetime(raw[time_col], errors="coerce")
        raw = raw.sort_values(time_col)

    fig, ax = plt.subplots(figsize=(12, 6))

    if station_col:
        for station, group in raw.groupby(station_col):
            group = group.copy()
            group["rolling_latency"] = group[latency_col].rolling(10, min_periods=1).mean()

            if time_col:
                ax.plot(group[time_col], group["rolling_latency"], linewidth=2, label=str(station))
            else:
                ax.plot(group.index, group["rolling_latency"], linewidth=2, label=str(station))

        ax.legend(title="Station")
    else:
        raw["rolling_latency"] = raw[latency_col].rolling(10, min_periods=1).mean()
        x = raw[time_col] if time_col else raw.index
        ax.plot(x, raw["rolling_latency"], linewidth=2)

    ax.set_title("Latency Trend During WiFi Telemetry Experiment", fontsize=18, weight="bold")
    ax.set_xlabel("Time" if time_col else "Request Number", fontsize=13)
    ax.set_ylabel("Latency (ms)", fontsize=13)
    style_graph(ax)
    save(fig, out_dir / "02_latency_trend_presentation.png")


def plot_rssi_over_time(wifi, out_dir):
    rssi_col = find_col(wifi, ["rssi", "signal", "signal_strength"])
    time_col = find_col(wifi, ["timestamp", "time", "ts"])
    station_col = find_col(wifi, ["station", "sta", "client"])

    if not rssi_col:
        return

    wifi[rssi_col] = pd.to_numeric(wifi[rssi_col], errors="coerce")
    wifi = wifi.dropna(subset=[rssi_col]).copy()

    if time_col:
        wifi[time_col] = pd.to_datetime(wifi[time_col], errors="coerce")
        wifi = wifi.sort_values(time_col)

    fig, ax = plt.subplots(figsize=(12, 6))

    if station_col:
        for station, group in wifi.groupby(station_col):
            x = group[time_col] if time_col else group.index
            ax.plot(x, group[rssi_col], linewidth=2, marker="o", markersize=3, label=str(station))
        ax.legend(title="Station")
    else:
        x = wifi[time_col] if time_col else wifi.index
        ax.plot(x, wifi[rssi_col], linewidth=2, marker="o", markersize=3)

    ax.set_title("RSSI Signal Strength During Roaming Experiment", fontsize=18, weight="bold")
    ax.set_xlabel("Time" if time_col else "Sample Number", fontsize=13)
    ax.set_ylabel("RSSI / Signal Strength", fontsize=13)
    style_graph(ax)
    save(fig, out_dir / "03_rssi_roaming_trend.png")


def plot_requests_per_ap(raw, wifi, out_dir):
    ap_col = find_col(raw, ["ap", "access_point", "ap_name"])

    data_source = raw
    if not ap_col and wifi is not None:
        ap_col = find_col(wifi, ["ap", "access_point", "ap_name"])
        data_source = wifi

    if not ap_col:
        return

    counts = data_source[ap_col].astype(str).value_counts()

    fig, ax = plt.subplots(figsize=(9, 6))
    ax.bar(counts.index, counts.values)
    ax.set_title("Traffic Distribution Across Access Points", fontsize=18, weight="bold")
    ax.set_xlabel("Access Point", fontsize=13)
    ax.set_ylabel("Number of Records / Requests", fontsize=13)
    style_graph(ax)
    add_labels(ax)
    save(fig, out_dir / "04_requests_per_access_point.png")


def plot_roaming_events(wifi, out_dir):
    station_col = find_col(wifi, ["station", "sta", "client"])
    ap_col = find_col(wifi, ["ap", "access_point", "ap_name"])
    time_col = find_col(wifi, ["timestamp", "time", "ts"])

    if not station_col or not ap_col:
        return

    data = wifi.copy()

    if time_col:
        data[time_col] = pd.to_datetime(data[time_col], errors="coerce")
        data = data.sort_values([station_col, time_col])
    else:
        data = data.sort_values([station_col])

    roaming_counts = {}

    for station, group in data.groupby(station_col):
        ap_change = group[ap_col].astype(str).ne(group[ap_col].astype(str).shift())
        count = max(int(ap_change.sum()) - 1, 0)
        roaming_counts[str(station)] = count

    result = pd.DataFrame(
        {
            "Station": list(roaming_counts.keys()),
            "Roaming Events": list(roaming_counts.values()),
        }
    )

    fig, ax = plt.subplots(figsize=(9, 6))
    ax.bar(result["Station"], result["Roaming Events"])
    ax.set_title("Detected Roaming Events by Station", fontsize=18, weight="bold")
    ax.set_xlabel("Station", fontsize=13)
    ax.set_ylabel("Roaming Events", fontsize=13)
    style_graph(ax)
    add_labels(ax)
    save(fig, out_dir / "05_roaming_events_by_station.png")


def plot_comparison(input_dir, out_dir):
    comparison_file = input_dir / "comparison_dt212g_dt023g.csv"

    if not comparison_file.exists():
        comparison_file = input_dir / "dt023g_refinement_comparison.csv"

    if not comparison_file.exists():
        return

    df = pd.read_csv(comparison_file)

    metric_col = find_col(df, ["metric", "kpi", "name"])
    if not metric_col:
        metric_col = df.columns[0]

    old_col = None
    new_col = None

    for col in df.columns:
        low = col.lower()
        if any(x in low for x in ["dt212g", "previous", "old", "before"]):
            old_col = col
        if any(x in low for x in ["dt023g", "extended", "new", "after", "current", "refined"]):
            new_col = col

    numeric_cols = [c for c in df.columns if c != metric_col]

    if not old_col and len(numeric_cols) >= 2:
        old_col = numeric_cols[0]
    if not new_col and len(numeric_cols) >= 2:
        new_col = numeric_cols[1]

    if not old_col or not new_col:
        return

    rows = []
    for _, row in df.iterrows():
        metric = str(row[metric_col])
        old_val = to_num(row[old_col])
        new_val = to_num(row[new_col])

        if old_val is not None and new_val is not None:
            rows.append((metric, old_val, new_val))

    if not rows:
        return

    selected = []
    for metric, old_val, new_val in rows:
        low = metric.lower()
        if any(x in low for x in ["success", "latency", "p95", "roam"]):
            selected.append((metric, old_val, new_val))

    if not selected:
        selected = rows[:5]

    labels = [x[0] for x in selected]
    old_values = [x[1] for x in selected]
    new_values = [x[2] for x in selected]

    x = range(len(labels))
    width = 0.35

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.bar([i - width / 2 for i in x], old_values, width, label="Previous DT212G")
    ax.bar([i + width / 2 for i in x], new_values, width, label="Extended DT023G")

    ax.set_title("Previous Project vs Extended Project Comparison", fontsize=18, weight="bold")
    ax.set_xlabel("Metric", fontsize=13)
    ax.set_ylabel("Value", fontsize=13)
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, ha="right")
    ax.legend()
    style_graph(ax)
    save(fig, out_dir / "00_dt212g_vs_dt023g_comparison.png")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="input_dir", required=True)
    parser.add_argument("--out", dest="output_dir", required=True)
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    raw_file = input_dir / "raw_requests.csv"
    wifi_file = input_dir / "wifi_link.csv"

    raw = pd.read_csv(raw_file) if raw_file.exists() else None
    wifi = pd.read_csv(wifi_file) if wifi_file.exists() else None

    plot_comparison(input_dir, out_dir)

    if raw is not None:
        plot_success_by_station(raw.copy(), out_dir)
        plot_latency_over_time(raw.copy(), out_dir)
        plot_requests_per_ap(raw.copy(), wifi.copy() if wifi is not None else None, out_dir)

    if wifi is not None:
        plot_rssi_over_time(wifi.copy(), out_dir)
        plot_roaming_events(wifi.copy(), out_dir)

    print("\nPresentation graphs created successfully.")


if __name__ == "__main__":
    main()
