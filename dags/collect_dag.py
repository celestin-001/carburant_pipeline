import logging
from datetime import datetime,timedelta,timezone
from pathlib import Path
import pandas as pd

from airflow.decorators import dag, task

from src.load.db import charger_donnees
from src.ingestion.ingestion import build_destination , download_csv_file
from src.transformation.station_transform import transformer

logger = logging.getLogger(__name__)

DEFAULT_ARGS = {
    "owner": "celestin",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=3),
}

@dag(
    dag_id="collect_carburant_dag",
    default_args=DEFAULT_ARGS,
    description="Inclusion et transformation du flux temps réel des prix des carburants",
    schedule="*/30 * * * *",  # Exécution toutes les 30 minutes
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["carburants", "ingestion"],
)

def pipeline_collecte_carburants():

    @task()
    def executer_pipeline_carburants():
        date_collecte = datetime.now(timezone.utc)
        logger.info("Début de l'exécution du pipeline à %s", date_collecte)

        #Telechargement
        url_csv = "https://tabular-api.data.gouv.fr/api/resources/edd67f5b-46d0-4663-9de9-e5db1c880160/data/csv/"
        destination = build_destination(Path("data/raw"))
        fichier_csv = download_csv_file(url_csv, destination)

        #Lecture avec panda
        df =  pd.read_csv(fichier_csv,dtype=str)
        logger.info("Fichier chargé : %d lignes lues", len(df))

        #Transformer
        res = transformer(df)
        logger.info(
            "Transformation réussie : %d stations valides, %d prix, %d ruptures temporaires",
            len(res.stations),
            len(res.prix),
            len(res.ruptures),
        )
        # 4. Chargement idempotent en base PostgreSQL
        charger_donnees(res, date_collecte)
        logger.info("Chargement en base PostgreSQL terminé avec succès")
    executer_pipeline_carburants()

pipeline_collecte_carburants()