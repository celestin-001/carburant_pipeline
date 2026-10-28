from collections import Counter
from pathlib import Path
import pandas as pd
from src.transformation.station_transform import transformer


raw_dir = Path("data/raw")
fichiers = sorted(raw_dir.glob("prix-carburants_*.csv"))
if not fichiers:
    print("Aucun fichier CSV n'existe dans data/raw")
    exit()
dernier_fichier = fichiers[-1]
print(f"Chargement du fichier {dernier_fichier.name}")

df = pd.read_csv(dernier_fichier, dtype=str)

res = transformer(df)

# 1. Vérification de l'invariant principal
rejets_stations = [r for r in res.rejets if r.carburant_id is None]
total_traite = len(res.stations) + len(rejets_stations)

print("\n--- Métriques des Stations ---")
print(f"Lignes lues dans le CSV : {len(df)}")
print(f"Stations valides        : {len(res.stations)}")
print(f"Rejets de stations      : {len(rejets_stations)}")
print(f"Invariant respecté ?    : {total_traite == len(df)}")

# 2. Métriques sur les prix par carburant
print("\n--- Nombre de prix extraits par carburant_id ---")
comptes_prix = Counter(p.carburant_id for p in res.prix)
noms = {1: "Gazole", 2: "SP95", 3: "E85", 4: "GPLc", 5: "E10", 6: "SP98"}
for cid in range(1, 7):
    print(f"  - {noms[cid]} (id {cid}) : {comptes_prix[cid]}")

# 3. Distribution des rejets (stations + prix)
print("\n--- Distribution des motifs de rejets ---")
motifs_count = Counter(r.motif for r in res.rejets)
for motif, count in motifs_count.items():
    print(f"  - {motif} : {count}")

# 4. Métriques sur les ruptures temporaires
print("\n--- Ruptures temporaires ---")
print(f"Nombre total de ruptures temporaires : {len(res.ruptures)}")
comptes_ruptures = Counter(r.carburant_id for r in res.ruptures)
for cid in range(1, 7):
    print(f"  - {noms[cid]} (id {cid}) : {comptes_ruptures[cid]}")