
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
from src.transformation.station_transform import transformer
from src.load.db import charger_donnees

BASE_DIR = Path(__file__).resolve().parent.parent
chemin = sorted((BASE_DIR / "data" / "raw").glob("prix-carburants_*.csv"))[-1]
df = pd.read_csv(chemin, dtype=str)
resultat = transformer(df)

print(f"Début du chargement en base pour {len(resultat.stations)} stations...")
charger_donnees(resultat, datetime.now(timezone.utc))
print("Chargement terminé avec succès !")
