from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

DAG_ID = "wifi_telemetry_pipeline"
PROJECT_DIR = "/home/thehemraj/dt212g_project"
ARTIFACTS_DIR = f"{PROJECT_DIR}/artifacts"
VENV_PY = f"{PROJECT_DIR}/.venv/bin/python"
RUN_ID = "airflow_final"

with DAG(
    dag_id=DAG_ID,
    start_date=datetime(2026, 3, 7),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    dagrun_timeout=timedelta(minutes=30),
    tags=["wifi", "telemetry", "etl"],
) as dag:

    run_experiment = BashOperator(
        task_id="run_experiment",
        execution_timeout=timedelta(minutes=20),
        bash_command=f"""
        set -e
        sudo -n /home/thehemraj/dt212g_project/scripts/run_airflow_experiment.sh
        sudo -n chown -R thehemraj:thehemraj {ARTIFACTS_DIR}/{RUN_ID}
        """,
    )

    transform = BashOperator(
        task_id="transform",
        execution_timeout=timedelta(minutes=5),
        bash_command=f"""
        set -e
        cd {PROJECT_DIR}
        {VENV_PY} scripts/transform.py --run-id {RUN_ID} --in-root {ARTIFACTS_DIR}
        """,
    )

    report = BashOperator(
        task_id="report",
        execution_timeout=timedelta(minutes=5),
        bash_command=f"""
        set -e
        cd {PROJECT_DIR}
        {VENV_PY} scripts/report.py --run-id {RUN_ID} --in-root {ARTIFACTS_DIR}
        """,
    )

    run_experiment >> transform >> report
