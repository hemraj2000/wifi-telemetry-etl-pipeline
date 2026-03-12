from __future__ import annotations

import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.trigger_rule import TriggerRule


PROJECT_DIR = Path("/home/thehemraj/dt212g_project")
ARTIFACTS_ROOT = PROJECT_DIR / "artifacts"
SCRIPTS_DIR = PROJECT_DIR / "scripts"

RUN_EXPERIMENT_TIMEOUT_SEC = 30 * 60
TRANSFORM_TIMEOUT_SEC = 5 * 60
REPORT_TIMEOUT_SEC = 5 * 60
TEARDOWN_TIMEOUT_SEC = 5 * 60


def _run_cmd(cmd, timeout: int, cwd: Path | None = None):
    res = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if res.stdout:
        print("STDOUT:\n", res.stdout)
    if res.stderr:
        print("STDERR:\n", res.stderr)
    if res.returncode != 0:
        raise subprocess.CalledProcessError(res.returncode, cmd, output=res.stdout, stderr=res.stderr)


def _run_id_dir(context) -> Path:
    run_id = context["run_id"]
    out_dir = ARTIFACTS_ROOT / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Artifact dir: {out_dir}")
    return out_dir


def run_experiment_fn(**context):
    out_dir = _run_id_dir(context)

    cmd = [
        "sudo", "-n", "bash",
        str(SCRIPTS_DIR / "run_experiment_root.sh"),
        str(out_dir),
    ]
    _run_cmd(cmd, timeout=RUN_EXPERIMENT_TIMEOUT_SEC, cwd=PROJECT_DIR)

    # take ownership back (so transform/report can read)
    _run_cmd(["sudo", "-n", "chown", "-R", f"{os.getlogin()}:{os.getlogin()}", str(out_dir)], timeout=60)
    return str(out_dir)


def transform_fn(**context):
    run_id = context["run_id"]
    cmd = [
        str(PROJECT_DIR / ".venv" / "bin" / "python3"),
        "-u",
        str(SCRIPTS_DIR / "transform.py"),
        "--run-id", run_id,
        "--in-root", str(ARTIFACTS_ROOT),
    ]
    _run_cmd(cmd, timeout=TRANSFORM_TIMEOUT_SEC, cwd=PROJECT_DIR)
    return str(ARTIFACTS_ROOT / run_id)


def report_fn(**context):
    run_id = context["run_id"]
    cmd = [
        str(PROJECT_DIR / ".venv" / "bin" / "python3"),
        "-u",
        str(SCRIPTS_DIR / "report.py"),
        "--run-id", run_id,
        "--in-root", str(ARTIFACTS_ROOT),
    ]
    _run_cmd(cmd, timeout=REPORT_TIMEOUT_SEC, cwd=PROJECT_DIR)
    return str(ARTIFACTS_ROOT / run_id)


def teardown_fn(**context):
    # Always cleanup mininet even if experiment fails
    _run_cmd(["sudo", "-n", "mn", "-c"], timeout=TEARDOWN_TIMEOUT_SEC)
    _run_cmd(["sudo", "-n", "pkill", "-f", "mn_wifi"], timeout=60)
    _run_cmd(["sudo", "-n", "pkill", "-f", "mininet"], timeout=60)
    _run_cmd(["sudo", "-n", "ovs-vsctl", "--if-exists", "del-br", "ap1"], timeout=60)
    _run_cmd(["sudo", "-n", "ovs-vsctl", "--if-exists", "del-br", "ap2"], timeout=60)


default_args = {"owner": "thehemraj", "retries": 0}

with DAG(
    dag_id="wifi_telemetry_pipeline",
    default_args=default_args,
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    dagrun_timeout=timedelta(minutes=45),
    tags=["dt212g", "wifi", "etl"],
) as dag:

    run_experiment = PythonOperator(
        task_id="run_experiment",
        python_callable=run_experiment_fn,
        execution_timeout=timedelta(seconds=RUN_EXPERIMENT_TIMEOUT_SEC),
    )

    transform = PythonOperator(
        task_id="transform",
        python_callable=transform_fn,
        execution_timeout=timedelta(seconds=TRANSFORM_TIMEOUT_SEC),
    )

    report = PythonOperator(
        task_id="report",
        python_callable=report_fn,
        execution_timeout=timedelta(seconds=REPORT_TIMEOUT_SEC),
    )

    teardown = PythonOperator(
        task_id="teardown",
        python_callable=teardown_fn,
        trigger_rule=TriggerRule.ALL_DONE,
        execution_timeout=timedelta(seconds=TEARDOWN_TIMEOUT_SEC),
    )

    run_experiment >> transform >> report >> teardown
    run_experiment >> teardown
