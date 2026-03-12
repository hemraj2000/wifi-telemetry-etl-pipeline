import argparse
import csv
import os
import re
import time
import threading
from pathlib import Path
from datetime import datetime, timezone

from mininet.log import setLogLevel, info
from mininet.node import Controller
from mn_wifi.net import Mininet_wifi


def utc_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def parse_iw_link(text: str):
    ap_mac = None
    rssi = None
    m = re.search(r"Connected to ([0-9a-f:]{17})", text, re.I)
    if m:
        ap_mac = m.group(1).lower()
    m = re.search(r"signal:\s*(-?\d+)\s*dBm", text, re.I)
    if m:
        rssi = int(m.group(1))
    return ap_mac, rssi


def chown_recursive(path: Path, user: str):
    try:
        import pwd
        pw = pwd.getpwnam(user)
        uid, gid = pw.pw_uid, pw.pw_gid
        for root, dirs, files in os.walk(path):
            os.chown(root, uid, gid)
            for d in dirs:
                os.chown(os.path.join(root, d), uid, gid)
            for f in files:
                os.chown(os.path.join(root, f), uid, gid)
    except Exception:
        pass


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run-id", required=True)
    p.add_argument("--out-root", default="/home/thehemraj/dt212g_project/artifacts")
    p.add_argument("--requests-per-sta", type=int, default=300)
    p.add_argument("--sample-interval", type=float, default=1.0)
    p.add_argument("--move-after-sec", type=float, default=5.0)
    p.add_argument("--warmup-sec", type=float, default=10.0)
    p.add_argument("--post_roam_hold_sec", type=float, default=20.0)
    args = p.parse_args()

    run_dir = Path(args.out_root) / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    req_csv = run_dir / "raw_requests.csv"
    wifi_csv = run_dir / "wifi_link.csv"
    crash_log = run_dir / "crash.txt"

    with req_csv.open("w", newline="") as f:
        csv.writer(f).writerow(["ts_ms", "sta", "status_code", "latency_ms"])
    with wifi_csv.open("w", newline="") as f:
        csv.writer(f).writerow(["ts_ms", "sta", "ap", "rssi_dbm"])

    setLogLevel("info")
    info(f"*** Writing artifacts to: {run_dir}\n")

    net = None
    stop_event = threading.Event()
    file_lock = threading.Lock()

    def log_request(sta_name: str, code: str, latency_ms: float):
        with file_lock:
            with req_csv.open("a", newline="") as f:
                csv.writer(f).writerow([utc_ms(), sta_name, code, f"{latency_ms:.3f}"])

    def log_wifi(sta_name: str, ap: str, rssi):
        with file_lock:
            with wifi_csv.open("a", newline="") as f:
                csv.writer(f).writerow([utc_ms(), sta_name, ap, "" if rssi is None else rssi])

    try:
        net = Mininet_wifi(controller=Controller)
        c0 = net.addController("c0")

        # Same SSID, different channels
        ap1 = net.addAccessPoint("ap1", ssid="ssid-ap", mode="g", channel="1", position="10,50,0")
        ap2 = net.addAccessPoint("ap2", ssid="ssid-ap", mode="g", channel="6", position="90,50,0")

        sta1 = net.addStation("sta1", ip="10.0.0.1/24", position="15,50,0")
        sta2 = net.addStation("sta2", ip="10.0.0.2/24", position="15,55,0")
        srv1 = net.addStation("srv1", ip="10.0.0.5/24", position="50,50,0")

        net.configureWifiNodes()
        net.build()
        c0.start()
        ap1.start([c0])
        ap2.start([c0])

        # thread safety locks for node.cmd
        sta1_lock = threading.Lock()
        sta2_lock = threading.Lock()
        srv1_lock = threading.Lock()

        def cmd_safe(node, node_lock, cmd: str) -> str:
            with node_lock:
                return node.cmd(cmd)

        info(f"*** Waiting {args.warmup_sec:.0f}s for auto-association...\n")
        time.sleep(args.warmup_sec)

        # Start HTTP server
        cmd_safe(
            srv1, srv1_lock,
            "cat > /tmp/http_srv.py <<'PY'\n"
            "from http.server import BaseHTTPRequestHandler, HTTPServer\n"
            "class H(BaseHTTPRequestHandler):\n"
            "    def do_GET(self):\n"
            "        body = b'ok\\n'\n"
            "        self.send_response(200)\n"
            "        self.send_header('Content-Type','text/plain')\n"
            "        self.send_header('Content-Length', str(len(body)))\n"
            "        self.end_headers()\n"
            "        self.wfile.write(body)\n"
            "    def log_message(self, format, *args):\n"
            "        return\n"
            "HTTPServer(('0.0.0.0', 8000), H).serve_forever()\n"
            "PY\n"
        )
        cmd_safe(srv1, srv1_lock, "python3 /tmp/http_srv.py > /tmp/http_srv.out 2>&1 & echo $! > /tmp/http_srv.pid")
        time.sleep(1)

        url = f"http://{srv1.IP()}:8000/"

        info("*** Connectivity check sta1 -> srv1\n")
        info(cmd_safe(sta1, sta1_lock, "iw dev sta1-wlan0 link 2>/dev/null || true") + "\n")
        info("sta1 curl code: " + cmd_safe(sta1, sta1_lock, f"curl -s -o /dev/null -w '%{{http_code}}' {url} || echo 000").strip() + "\n")

        info("*** Connectivity check sta2 -> srv1\n")
        info(cmd_safe(sta2, sta2_lock, "iw dev sta2-wlan0 link 2>/dev/null || true") + "\n")
        info("sta2 curl code: " + cmd_safe(sta2, sta2_lock, f"curl -s -o /dev/null -w '%{{http_code}}' {url} || echo 000").strip() + "\n")

        # AP MAC -> name map for wifi_link.csv
        ap1_mac = ap1.cmd("cat /sys/class/net/ap1-wlan1/address 2>/dev/null || true").strip().lower()
        ap2_mac = ap2.cmd("cat /sys/class/net/ap2-wlan1/address 2>/dev/null || true").strip().lower()

        ap_mac_map = {}
        if ap1_mac:
            ap_mac_map[ap1_mac] = "ap1"
        if ap2_mac:
            ap_mac_map[ap2_mac] = "ap2"

        sta1_if = "sta1-wlan0"
        sta2_if = "sta2-wlan0"

        def requester(sta, sta_lock, sta_name: str, n: int):
            for i in range(n):
                if stop_event.is_set():
                    break
                t0 = time.time()
                code = cmd_safe(sta, sta_lock, f"curl -s -o /dev/null -w '%{{http_code}}' {url} || echo 000").strip()
                latency_ms = (time.time() - t0) * 1000.0
                if not code.isdigit():
                    code = "000"
                log_request(sta_name, code, latency_ms)
                if i % 50 == 0:
                    info(f"*** {sta_name} requests done: {i}/{n}\n")
                time.sleep(0.05)

        def sampler():
            while not stop_event.is_set():
                txt1 = cmd_safe(sta1, sta1_lock, f"iw dev {sta1_if} link 2>/dev/null || true")
                mac1, rssi1 = parse_iw_link(txt1)
                log_wifi("sta1", ap_mac_map.get(mac1, mac1 if mac1 else ""), rssi1)

                txt2 = cmd_safe(sta2, sta2_lock, f"iw dev {sta2_if} link 2>/dev/null || true")
                mac2, rssi2 = parse_iw_link(txt2)
                log_wifi("sta2", ap_mac_map.get(mac2, mac2 if mac2 else ""), rssi2)

                time.sleep(args.sample_interval)

        t_s = threading.Thread(target=sampler, daemon=False)
        t1 = threading.Thread(target=requester, args=(sta1, sta1_lock, "sta1", args.requests_per_sta), daemon=False)
        t2 = threading.Thread(target=requester, args=(sta2, sta2_lock, "sta2", args.requests_per_sta), daemon=False)

        t_s.start()
        start = time.time()
        t1.start()
        t2.start()

        moved = False
        while t1.is_alive() or t2.is_alive():
            if (not moved) and (time.time() - start >= args.move_after_sec):
                info("*** Moving sta1/sta2 near ap2 and forcing RSSI shift via TxPower\n")
                sta1.setPosition("85,50,0")
                sta2.setPosition("85,55,0")

                # ✅ Guaranteed RSSI change (even if AP never switches)
                try:
                    ap1.setTxPower(1)    # make AP1 weak
                    ap2.setTxPower(14)   # make AP2 stronger
                except Exception:
                    pass

                time.sleep(args.post_roam_hold_sec)
                moved = True

            time.sleep(0.5)

        stop_event.set()
        t_s.join(timeout=3)
        t1.join(timeout=3)
        t2.join(timeout=3)

        cmd_safe(srv1, srv1_lock, "kill $(cat /tmp/http_srv.pid) 2>/dev/null || true")

        info("*** Done.\n")
        info(f"  - {req_csv}\n")
        info(f"  - {wifi_csv}\n")

    except Exception:
        import traceback
        crash_log.write_text(traceback.format_exc())
        raise
    finally:
        try:
            if net is not None:
                net.stop()
        except Exception:
            pass

        sudo_user = os.environ.get("SUDO_USER")
        if sudo_user:
            chown_recursive(run_dir, sudo_user)


if __name__ == "__main__":
    main()
