# Pipeline des prix des carburants (France)

Ce projet collecte le flux public des prix des carburants, le transforme et l'historise dans PostgreSQL/PostGIS. Airflow orchestre le pipeline toutes les 30 minutes.

## Objectif

Le flux source est un instantané. Le pipeline conserve les relevés horodatés afin de constituer un historique des prix et des ruptures de stock, avec les stations géolocalisées et leurs services.

## Fonctionnement actuel

1. **Orchestration** — `dags/collect_dag.py` définit le DAG `collect_carburant_dag`, planifié toutes les 30 minutes, avec deux tentatives de reprise.
2. **Ingestion** — `src/ingestion/ingestion.py` télécharge le CSV public avec des reprises HTTP et un fichier temporaire renommé atomiquement dans `data/raw/`.
3. **Transformation** — `src/transformation/station_transform.py` et `utils/transform_utils.py` valident les lignes et construisent stations, prix, services et ruptures; les éléments rejetés sont conservés avec leur motif.
4. **Chargement** — `src/load/db.py` écrit dans PostgreSQL/PostGIS. Les stations sont mises à jour, les prix déjà présents (clé station/carburant/date de mise à jour) ne sont pas réinsérés, et les ruptures ouvertes sont rapprochées du flux courant.

La connexion Airflow à la base métier doit porter l'identifiant `bdd_metiers`. Le code du chargeur l'utilise via `PostgresHook`.

## Architecture

```text
.
├── dags/collect_dag.py                 # DAG Airflow
├── src/
│   ├── ingestion/ingestion.py          # Téléchargement du CSV
│   ├── transformation/
│   │   ├── station.py                  # Objets métier et rejets
│   │   └── station_transform.py        # Transformation du CSV
│   └── load/db.py                      # Chargement PostgreSQL
├── utils/transform_utils.py            # Parsers et validations
├── sql/
│   ├── 01_init_postgis.sql             # Extension PostGIS
│   └── 02_tables.sql                   # Schéma métier et index
├── tests/                              # Tests unitaires
├── tests_integration/                  # Scripts d'intégration avec effets de bord
├── data/raw/                           # CSV téléchargés
├── docker-compose.yml
└── requirements.txt
```

## Démarrage avec Docker Compose

Prérequis : Docker Compose, accès Internet depuis les conteneurs Airflow et un fichier `.env` à la racine.

1. Créer le fichier local à partir du modèle et remplacer les valeurs d'exemple par des secrets adaptés :

   ```bash
   cp .env.example .env
   ```

   Ajouter également à `.env` une valeur `FERNET_KEY` valide pour Airflow. Une clé peut être générée avec Python :

   ```bash
   python -c 'import base64, secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())'
   ```

   Ne pas publier le fichier `.env` ni les clés générées.

2. Démarrer les services et vérifier leur état :

   ```bash
   docker compose up -d
   docker compose ps
   ```

3. Dans Airflow (`http://localhost:8080`), vérifier ou créer la connexion `bdd_metiers` (**Admin → Connections**) : type `Postgres`, hôte `db`, port `5432`, base/utilisateur/mot de passe correspondant à `POSTGRES_DB`, `POSTGRES_USER` et `POSTGRES_PASSWORD` du `.env`.

4. Le DAG étant créé en pause par défaut, le dé-pauser dans l'interface, puis utiliser **Trigger DAG** pour lancer une collecte. Vérifier l'état `success` dans **Grid** et le journal de la tâche `executer_pipeline_carburants`.

Le port `5433` (par défaut) est le port publié sur l'hôte pour la base métier; entre conteneurs, utiliser le service `db` sur le port `5432`. Si les journaux montrent une erreur de résolution DNS, définir `DOCKER_DNS_SERVER` dans `.env` avec un résolveur joignable depuis Docker, puis recréer les services Airflow :

```bash
docker compose up -d --force-recreate airflow-webserver airflow-scheduler airflow-triggerer
```

## Tests

Depuis la racine du dépôt, lancer les tests unitaires :

```bash
python -m pytest -q tests/
```

Les scripts de `tests_integration/` ne font pas partie de cette commande : ils lisent le dernier CSV de `data/raw/` et `test_chargement.py` écrit dans la base métier. Ne les lancer que lorsque ces prérequis et les effets sur la base sont voulus.

## Vérifier les données en base

Cette commande ouvre `psql` dans le conteneur de la base métier avec les variables du `.env` :

```bash
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

Requêtes de contrôle en lecture seule :

```sql
SELECT COUNT(*) FROM station;
SELECT COUNT(*) FROM prix;
SELECT COUNT(*) FROM service;
SELECT COUNT(*) FROM rupture;
SELECT COUNT(*) FROM rupture WHERE fin IS NULL;
```

Il n'existe pas de commande autonome `python -m src.db` : le chargement s'exécute depuis le DAG et dépend de la connexion Airflow `bdd_metiers`.

## État et prochaines étapes

- **En place :** ingestion, transformation, chargement PostGIS et orchestration Airflow.
- **À faire :** vues/requêtes analytiques (par exemple moyennes mobiles sur 7/30 jours) et tableau de bord cartographique/évolutif. Aucun fichier SQL de vues analytiques ni application dans `app/` n'est présent actuellement.

### Validation locale du 24 novembre 2026

- `python -m pytest -q tests/` : **67 tests réussis**.
- Le run manuel Airflow `collect_carburant_dag` de **21:04 UTC** a terminé en `success` : téléchargement de 18,7 Mo, 9 825 lignes lues, 9 821 stations valides, 32 986 prix et 2 944 ruptures transformés; le journal confirme la fin du chargement PostgreSQL.
- Lors du contrôle en lecture seule de la base, elle contenait 9 848 stations, 87 678 prix, 27 services et 6 405 ruptures, dont 2 943 ouvertes. Ces nombres décrivent l'état observé à cette date et évolueront avec les collectes.
