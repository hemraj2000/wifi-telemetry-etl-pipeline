#!/usr/bin/env python3
import argparse
import csv
import os
import re
import sys
import threading
import time
from pathlib import Path

from mininet.log import info, setLogLevel
from mininet.node import Controller, OVSKernelSwitch
from mn_wifi.link import wmediumd
from mn_wifi.net import Mininet_wifi
from mn_wifi.node import OVSKernelAP
from mn_wifi.wmediumdConnector import interference


def now_ms():
    return int(time.time() * 1000)


def ensure_root():
    if os.geteuid() != 0:
        print("*** Mininet must run as root.")
        sys.exit(1)


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True, help="Output directory")
    p.add_argument("--requests-per-sta", type=int, default=1000,
                   help="HTTP requests per station (>=800 required)")
    p.add_argument("--server-port", type=int, default=8000)
    p.add_argument("--sample-interval", type=float, default=1.0)
    p.add_argument("--roam-after", type=float, default=90.0,
                   help="Seconds after start to move stations toward ap2")
    return p.parse_args()


def run_cmd(node, cmd, lock=None):
    if lock is None:
        return node.cmd(cmd)
    with lock:
        return node.cmd(cmd)


def parse_iw_link(text):
    ap = ""
    rssi = ""

    if "Not connected." in text:
        return "", ""

    m_ap = re.search(r"Connected to\s+([0-9a-fA-F:]{17})", text)
    if m_ap:
        ap = m_ap.group(1)

    m_rssi = re.search(r"signal:\s*(-?\d+)\s*dBm", text)
    if m_rssi:
        rssi = m_rssi.group(1)

    return ap, rssi


def parse_curl_result(text):
    text = text.strip()
    m = re.search(r"(\d{3})\s+([0-9.]+)", text)
    if not m:
        return 0, 3000.0
    status = int(m.group(1))
    latency_ms = float(m.group(2)) * 1000.0
    return status, latency_ms


def wait_for_association(sta, sta_name, lock, seconds=10):
    info("*** Waiting for %s association\n" % sta_name)
    for _ in range(seconds):
        out = run_cmd(sta, "iw dev %s-wlan0 link" % sta_name, lock)
        if "Connected to" in out:
            info("*** %s associated\n" % sta_name)
            return
        time.sleep(1)
    info("*** %s not clearly associated yet\n" % sta_name)


def start_http_server(srv, port):
    srv.cmd("pkill -f 'python3 -m http.server' >/dev/null 2>&1 || true")
    srv.cmd("python3 -m http.server %s >/tmp/srv_http.log 2>&1 &" % port)
    time.sleep(2)


def connectivity_check(sta1, sta2, srv_ip, port, sta_locks):
    info("*** Checking connectivity: ping srv from sta1/sta2\n")
    print(run_cmd(sta1, "ping -c 1 %s" % srv_ip, sta_locks["sta1"]))
    print(run_cmd(sta2, "ping -c 1 %s" % srv_ip, sta_locks["sta2"]))

    info("*** Checking HTTP HEAD from sta1/sta2\n")
    print(run_cmd(sta1, "curl -I -m 5 http://%s:%s/ | head -n 1" % (srv_ip, port),
                  sta_locks["sta1"]))
    print(run_cmd(sta2, "curl -I -m 5 http://%s:%s/ | head -n 1" % (srv_ip, port),
                  sta_locks["sta2"]))


def wifi_sampler(stop_event, wifi_csv_path, sta_nodes, sta_locks, sample_interval):
    with wifi_csv_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["ts_ms", "sta", "ap", "rssi_dbm"])

        while not stop_event.is_set():
            ts = now_ms()
            for sta_name, sta in sta_nodes.items():
                out = run_cmd(sta, "iw dev %s-wlan0 link" % sta_name, sta_locks[sta_name])
                ap, rssi = parse_iw_link(out)
                writer.writerow([ts, sta_name, ap, rssi])
            f.flush()
            time.sleep(sample_interval)


def workload_worker(sta_name, sta, server_url, requests_per_sta,
                    req_csv_path, file_lock, sta_lock):
    i = 1
    while i <= requests_per_sta:
        ts = now_ms()
        curl_cmd = (
            "curl -s -o /dev/null "
            "-w '%{http_code} %{time_total}' "
            "--max-time 3 "
            + server_url
        )

        try:
            out = run_cmd(sta, curl_cmd, sta_lock)
            status_code, latency_ms = parse_curl_result(out)
        except Exception:
            status_code, latency_ms = 0, 3000.0
            time.sleep(0.2)

        with file_lock:
            with req_csv_path.open("a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([ts, sta_name, status_code, "%.3f" % latency_ms])

        if i % 50 == 0:
            info("*** %s requests done: %s/%s\n" % (sta_name, i, requests_per_sta))

        i += 1
        time.sleep(0.12)

def force_roam_after_delay(sta1, sta2, sta_locks, delay_s):
    time.sleep(delay_s)
    info("*** Moving stations closer to ap2 for roaming demo\n")

    try:
        sta1.setPosition("138,30,0")
        sta2.setPosition("142,40,0")
    except Exception as e:
        info("*** Position update warning: %s\n" % e)

    time.sleep(8)

    try:
        print(run_cmd(sta1, "iw dev sta1-wlan0 link", sta_locks["sta1"]))
        print(run_cmd(sta2, "iw dev sta2-wlan0 link", sta_locks["sta2"]))
    except Exception as e:
        info("*** Link check warning: %s\n" % e)


def main():
    args = parse_args()
    ensure_root()
    setLogLevel("info")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    raw_requests_csv = out_dir / "raw_requests.csv"
    wifi_link_csv = out_dir / "wifi_link.csv"

    print("*** Output dir: %s" % out_dir)
    print("*** requests-per-sta=%s" % args.requests_per_sta)

    if args.requests_per_sta < 800:
        print("*** requests-per-sta must be at least 800 for project requirement")
        sys.exit(2)

    net = None
    stop_event = threading.Event()
    req_file_lock = threading.Lock()

    sta_locks = {
        "sta1": threading.Lock(),
        "sta2": threading.Lock(),
    }

    try:
        net = Mininet_wifi(
            controller=Controller,
            switch=OVSKernelSwitch,
            accessPoint=OVSKernelAP,
            link=wmediumd,
            wmediumd_mode=interference,
        )

        info("*** Creating nodes\n")
        c0 = net.addController("c0")
        s1 = net.addSwitch("s1")

        ap1 = net.addAccessPoint(
            "ap1",
            ssid="ssid-ap1",
            mode="g",
            channel="1",
            position="20,30,0",
            range=30,
        )
        ap2 = net.addAccessPoint(
            "ap2",
            ssid="ssid-ap2",
            mode="g",
            channel="6",
            position="140,30,0",
            range=30,
        )

        sta1 = net.addStation(
            "sta1",
            ip="10.0.0.11/8",
            position="18,30,0",
            range=20,
        )
        sta2 = net.addStation(
            "sta2",
            ip="10.0.0.12/8",
            position="22,40,0",
            range=20,
        )

        srv = net.addHost("srv", ip="10.0.0.3/8")

        net.setPropagationModel(model="logDistance", exp=3.5)
        net.configureWifiNodes()

        info("*** Creating links\n")
        net.addLink(ap1, s1)
        net.addLink(ap2, s1)
        net.addLink(s1, srv)

        info("*** Starting network\n")
        net.build()
        c0.start()
        s1.start([c0])
        ap1.start([c0])
        ap2.start([c0])

        time.sleep(5)
        wait_for_association(sta1, "sta1", sta_locks["sta1"], seconds=8)
        wait_for_association(sta2, "sta2", sta_locks["sta2"], seconds=8)

        with raw_requests_csv.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["ts_ms", "sta", "status_code", "latency_ms"])

        start_http_server(srv, args.server_port)
        server_url = "http://10.0.0.3:%s/" % args.server_port
        info("*** HTTP server URL: %s\n" % server_url)

        connectivity_check(sta1, sta2, "10.0.0.3", args.server_port, sta_locks)

        sta_nodes = {"sta1": sta1, "sta2": sta2}

        sampler_thread = threading.Thread(
            target=wifi_sampler,
            args=(stop_event, wifi_link_csv, sta_nodes, sta_locks, args.sample_interval),
            daemon=True,
        )
        sampler_thread.start()

        roam_thread = threading.Thread(
            target=force_roam_after_delay,
            args=(sta1, sta2, sta_locks, args.roam_after),
            daemon=True,
        )
        roam_thread.start()

        t1 = threading.Thread(
            target=workload_worker,
            args=("sta1", sta1, server_url, args.requests_per_sta,
                  raw_requests_csv, req_file_lock, sta_locks["sta1"]),
        )
        t2 = threading.Thread(
            target=workload_worker,
            args=("sta2", sta2, server_url, args.requests_per_sta,
                  raw_requests_csv, req_file_lock, sta_locks["sta2"]),
        )

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        info("*** Requests completed.\n")
        time.sleep(2)

    finally:
        stop_event.set()
        time.sleep(1)

        if net is not None:
            try:
                srv = net.get("srv")
                srv.cmd("pkill -f 'python3 -m http.server' >/dev/null 2>&1 || true")
            except Exception:
                pass

            try:
                net.stop()
            except Exception as e:
                print("Cleanup warning: %s" % e)

    print("*** Wrote: %s" % raw_requests_csv)
    print("*** Wrote: %s" % wifi_link_csv)


if __name__ == "__main__":
    main()
