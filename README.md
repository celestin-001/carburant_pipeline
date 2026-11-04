# Pipeline Data: Prix des carburants en temps réel (France)

Ce projet est un pipeline de données automatisé développé en Python, SQL et Docker. Il permet de collecter, nettoyer, transformer et historiser les données des prix des carburants et des ruptures de stock en France métropolitaine (~9 800 stations) depuis les flux officiels de `data.gouv.fr`.

##  Objectif du projet

Les API officielles ne fournissent qu'un instantané des prix à un instant T. L'objectif de ce pipeline est de constituer un **historique spatio-temporel complet** en ne conservant que les **changements réels** de prix et en détectant la durée des ruptures temporaires de stock.

---

## 🛠️ Stack technique actuelle

* **Langage & Traitement :** Python 3.11+, Pandas, Dataclasses (immuables), Decimal (précision monétaire), `zoneinfo` (gestion UTC).
* **Base de données :** PostgreSQL / PostGIS (Geographic Points WGS84, indexation GiST).
* **Validation & Tests :** Pytest (démarche TDD, 67 tests unitaires et d'intégration au vert).
* **Infrastructure :** Docker Compose (Services `db` PostGIS & Apache Airflow LocalExecutor).

---

## 📌 Fonctionnalités implémentées (État d'avancement)

### 1. Ingestion & Collecte (`src/ingestion/flux_instantane.py`)
* Téléchargement atomique et résilient du flux CSV instantané depuis l'API tabulaire de `data.gouv.fr`.
* Gestion des relances HTTP (backoff) et vérification d'intégrité du fichier.

### 2. Transformation & Nettoyage (`src/ingestion/utils.py` & `transform.py`)
* **Parsing géographique :** Normalisation des coordonnées de géolocalisation ($\div 100\,000$) et vérification des bornes métropolitaines.
* **Dates & Prix :** Alignment strict sur le fuseau UTC avec détection des fuseaux locaux (Europe/Paris), validation par `Decimal`.
* **Services & Ruptures :** Extraction des services par station (JSON) et conversion des ruptures temporaires avec typage des dates de début.
* **Gestion fine des rejets :** Isolation des données invalides (motif précis par ligne) sans interrompre le pipeline global (invariant `stations_valides + rejets_stations == total_lignes` respecté).

### 3. Chargement idempotent en base (`src/db.py`)
* **Transaction unique & atomique :** Tout le chargement s'exécute en un seul bloc (`with conn:`).
* **Bulk insertion :** Utilisation de `execute_values` de `psycopg2` pour des performances optimales.
* **Idempotence :** Dédoublonnage strict (`ON CONFLICT (station_id, carburant_id, maj) DO NOTHING`). La ré-exécution immédiate d'un même flux insère exactement 0 nouveau prix.
* **Gestion dynamique des ruptures :** Ouverture des nouvelles ruptures temporaires (`fin IS NULL`) et fermeture automatique (`UPDATE fin = NOW()`) lorsque le carburant est réapprovisionné sur le terrain.

---

## 📁 Architecture du projet

```text
carburants-pipeline/
├── data/
│   └── raw/                   # Stockage local des CSV bruts horodatés
├── sql/
│   ├── 01_init_postgis.sql    # Extension PostGIS
│   └── 02_tables.sql          # Modèle de données (station, prix, service, rupture)
├── src/
│   ├── db.py                  # Connexion PostgreSQL et fonctions de chargement
│   └── ingestion/
│       ├── flux_instantane.py # Ingestion HTTP
│       ├── utils.py           # Fonctions de nettoyage et parsing
│       └── transform.py       # Logique métier et transformation pure
├── tests/                     # 67 tests unitaires et d'intégration (Pytest)
├── docker-compose.yml         # Conteneurs PostGIS & Airflow
├── requirements.txt
└── README.md
```

---

## 🧪 Lancer les tests unitaires

Depuis la racine du projet :

```bash
# Activer l'environnement virtuel
source .venv/bin/activate

# Lancer la suite complet des tests
python -m pytest tests/ -v
```

---

## 🚀 Lancer la base de données & tester le chargement

1. Démarrer la base de données PostgreSQL / PostGIS avec Docker :
```bash
docker compose up -d db
```

2. Exécuter la collecte et le chargement en base :
```bash
python -m src.db
```

3. Vérifier les données chargées via `psql` :
```sql
docker compose exec db psql -U carburants_user -d carburants_db

-- Nombre de stations valides chargées
SELECT COUNT(*) FROM station;

-- Nombre de prix enregistrés
SELECT COUNT(*) FROM prix;

-- Ruptures temporaires en cours
SELECT COUNT(*) FROM rupture WHERE fin IS NULL;
```

---

## 🔄 Prochaines étapes

* [ ] **Orchestration Airflow:** Automatisation du DAG d'exécution toutes les 30 minutes.
* [ ] **Vues Analytiques SQL:** Calcul des moyennes mobiles 7/30 jours et comparatifs par type de station.
* [ ] **Dashboard Streamlit :** Visualisation cartographique et graphiques d'évolution des prix.
