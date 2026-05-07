import argparse
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt


def find_col(df, possible_names):
    cols = {c.lower().strip(): c for c in df.columns}
    for name in possible_names:
        if name.lower() in cols:
            return cols[name.lower()]
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="input_dir", required=True)
    parser.add_argument("--out", dest="output_dir", required=True)
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_file = input_dir / "raw_requests.csv"
    wifi_file = input_dir / "wifi_link.csv"

    if not raw_file.exists():
        print(f"Missing file: {raw_file}")
        return

    raw = pd.read_csv(raw_file)

    time_col = find_col(raw, ["timestamp", "time", "ts"])
    latency_col = find_col(raw, ["latency_ms", "latency", "response_time_ms"])
    status_col = find_col(raw, ["status_code", "status", "http_status"])
    station_col = find_col(raw, ["station", "sta", "client"])
    ap_col = find_col(raw, ["ap", "access_point", "ap_name"])

    if time_col:
        raw[time_col] = pd.to_datetime(raw[time_col], errors="coerce")

    # 1. Latency over time
    if latency_col:
        plt.figure(figsize=(10, 5))
        if time_col:
            plt.plot(raw[time_col], raw[latency_col], marker="o", linewidth=1)
            plt.xlabel("Time")
        else:
            plt.plot(raw.index, raw[latency_col], marker="o", linewidth=1)
            plt.xlabel("Request Number")

        plt.ylabel("Latency (ms)")
        plt.title("Latency Over Time")
        plt.xticks(rotation=30)
        plt.tight_layout()
        plt.savefig(output_dir / "latency_over_time.png", dpi=200)
        plt.close()

    # 2. Latency by station
    if latency_col and station_col:
        latency_station = raw.groupby(station_col)[latency_col].mean().reset_index()

        plt.figure(figsize=(8, 5))
        plt.bar(latency_station[station_col], latency_station[latency_col])
        plt.xlabel("Station")
        plt.ylabel("Mean Latency (ms)")
        plt.title("Mean Latency by Station")
        plt.tight_layout()
        plt.savefig(output_dir / "latency_by_station.png", dpi=200)
        plt.close()

    # 3. Success rate by station
    if status_col and station_col:
        raw["success"] = raw[status_col].astype(str).str.startswith("2")
        success_station = raw.groupby(station_col)["success"].mean().reset_index()
        success_station["success_rate"] = success_station["success"] * 100

        plt.figure(figsize=(8, 5))
        plt.bar(success_station[station_col], success_station["success_rate"])
        plt.xlabel("Station")
        plt.ylabel("Success Rate (%)")
        plt.title("Success Rate by Station")
        plt.ylim(0, 100)
        plt.tight_layout()
        plt.savefig(output_dir / "success_rate_by_station.png", dpi=200)
        plt.close()

    # 4. RSSI over time
    if wifi_file.exists():
        wifi = pd.read_csv(wifi_file)

        wifi_time_col = find_col(wifi, ["timestamp", "time", "ts"])
        wifi_rssi_col = find_col(wifi, ["rssi", "signal", "signal_strength"])
        wifi_station_col = find_col(wifi, ["station", "sta", "client"])

        if wifi_time_col:
            wifi[wifi_time_col] = pd.to_datetime(wifi[wifi_time_col], errors="coerce")

        if wifi_rssi_col:
            plt.figure(figsize=(10, 5))

            if wifi_station_col:
                for sta, group in wifi.groupby(wifi_station_col):
                    if wifi_time_col:
                        plt.plot(group[wifi_time_col], group[wifi_rssi_col], marker="o", linewidth=1, label=str(sta))
                    else:
                        plt.plot(group.index, group[wifi_rssi_col], marker="o", linewidth=1, label=str(sta))
                plt.legend()
            else:
                if wifi_time_col:
                    plt.plot(wifi[wifi_time_col], wifi[wifi_rssi_col], marker="o", linewidth=1)
                else:
                    plt.plot(wifi.index, wifi[wifi_rssi_col], marker="o", linewidth=1)

            plt.xlabel("Time" if wifi_time_col else "Sample Number")
            plt.ylabel("RSSI")
            plt.title("RSSI Over Time")
            plt.xticks(rotation=30)
            plt.tight_layout()
            plt.savefig(output_dir / "rssi_over_time.png", dpi=200)
            plt.close()

    # 5. AP distribution
    if ap_col:
        ap_counts = raw[ap_col].value_counts()

        plt.figure(figsize=(7, 5))
        plt.bar(ap_counts.index.astype(str), ap_counts.values)
        plt.xlabel("Access Point")
        plt.ylabel("Number of Requests")
        plt.title("Requests Per Access Point")
        plt.tight_layout()
        plt.savefig(output_dir / "requests_per_ap.png", dpi=200)
        plt.close()

    print(f"Graphs generated in: {output_dir}")


if __name__ == "__main__":
    main()
