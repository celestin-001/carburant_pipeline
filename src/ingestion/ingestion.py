"""Téléchargement du flux instantané des prix des carburants (CSV)."""
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

logger = logging.getLogger(__name__)

# À vérifier avec `curl -I <url>` avant de s'y fier (domaine, identifiant, fraîcheur).
DEFAULT_CSV_URL = (
    "https://tabular-api.data.gouv.fr"
    "/api/resources/edd67f5b-46d0-4663-9de9-e5db1c880160/data/csv/"
)
RAW_DIR = Path(os.getenv("RAW_DATA_DIR", "data/raw"))
CHUNK_SIZE = 64 * 1024            # octets lus par morceau
TIMEOUT = (10, 60)                # (connexion, attente entre deux réceptions) en secondes


def build_session() -> requests.Session:
    """Session HTTP avec relances (backoff) sur les erreurs serveur."""
    retries = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504],
        raise_on_status=False,   # c'est raise_for_status() qui lèvera l'erreur
    )
    adapter = HTTPAdapter(max_retries=retries)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def build_destination(raw_dir: Path = RAW_DIR) -> Path:
    """Nom de fichier horodaté en UTC, ex. data/raw/prix-carburants_20261009T083000Z.csv"""
    horodatage = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return raw_dir / f"prix-carburants_{horodatage}.csv"


def download_csv_file(
    url: str,
    destination: Path,
    session: requests.Session | None = None,
) -> Path:
    """Télécharge `url` vers `destination` de façon atomique et renvoie le chemin.

    Le fichier final n'existe que si le téléchargement est complet et plausible.
    """
    session = session or build_session()
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.with_name(destination.name + ".part")

    logger.info("Début du téléchargement : %s", url)
    try:
        with session.get(url, stream=True, timeout=TIMEOUT) as r:
            r.raise_for_status()
            expected_size = r.headers.get("Content-Length")
            compressed = "Content-Encoding" in r.headers  # la taille annoncée n'est alors pas comparable

            written = 0
            with open(temp_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
                    if chunk:
                        f.write(chunk)
                        written += len(chunk)

        _check_file(temp_path, written, expected_size, compressed)
        os.replace(temp_path, destination)  # atomique : le fichier final est complet ou absent
    except (requests.exceptions.RequestException, OSError, ValueError) as err:
        logger.error("Échec du téléchargement : %s", err)
        raise
    finally:
        temp_path.unlink(missing_ok=True)   # sans effet si le renommage a réussi

    logger.info("Téléchargement terminé : %s (%.1f Mo)", destination, written / 1_048_576)
    return destination


def _check_file(path: Path, written: int, expected_size: str | None, compressed: bool) -> None:
    """Vérifie qu'un statut 200 a bien livré un CSV exploitable."""
    if written == 0:
        raise ValueError("fichier vide")
    if expected_size and not compressed and int(expected_size) != written:
        raise ValueError(f"fichier tronqué : {written} octets reçus sur {expected_size} annoncés")
    with open(path, encoding="utf-8", errors="replace") as f:
        first_line = f.readline().strip()
    if first_line.startswith("<"):
        raise ValueError("la réponse ressemble à une page HTML, pas à un CSV")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    csv_url = os.getenv("CARBURANTS_CSV_URL", DEFAULT_CSV_URL)
    download_csv_file(csv_url, build_destination())


