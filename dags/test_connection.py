from datetime import datetime

from airflow.sdk import dag, task
from airflow.providers.postgres.hooks.postgres import PostgresHook


@dag(
    dag_id="test_connection",
    start_date=datetime(2025, 1, 1),
    schedule=None,
    catchup=False,
    tags=["test"],
)

def test_connection():
    @task
    def lire_version():
        hook = PostgresHook(postgres_conn_id="bdd_metiers")
        version = hook.get_first("SELECT version();")
        postgis = hook.get_first("SELECT PostGIS_VERSION();")
        print(f"Postgres : {version[0]}")
        print(f"PostGIS  : {postgis[0]}")

    lire_version()

test_connection()