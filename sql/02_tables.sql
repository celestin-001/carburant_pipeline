-- 02_tables.sql — Schéma de la base métier (projet carburants)
-- Prérequis : 01_init_postgis.sql (CREATE EXTENSION postgis;)

CREATE TABLE IF NOT EXISTS station (
    id                INTEGER PRIMARY KEY,
    adresse           TEXT,
    cp                TEXT NOT NULL,
    ville             TEXT NOT NULL,
    code_departement  VARCHAR(3) NOT NULL,                        -- ex. '62', '2A', '971'
    code_region       VARCHAR(3),
    pop               CHAR(1) NOT NULL CHECK (pop IN ('R', 'A')),  -- R = route, A = autoroute
    categorie         VARCHAR(15)                                  -- NULL = pas encore classée (J5)
                      CHECK (categorie IN ('grande_surface', 'classique', 'autoroute')),
    geom              GEOGRAPHY(Point, 4326) NOT NULL,             -- WGS 84, ordre : longitude, latitude
    active            BOOLEAN NOT NULL DEFAULT TRUE,               -- FALSE si la station a fermé
    derniere_vue      TIMESTAMPTZ,                                 -- dernière apparition dans le flux
    -- une station d'autoroute est forcément classée 'autoroute' (ou pas encore classée)
    CHECK (pop <> 'A' OR categorie IS NULL OR categorie = 'autoroute')
);

CREATE TABLE IF NOT EXISTS carburant (
    id   SMALLINT PRIMARY KEY,
    nom  VARCHAR(10) NOT NULL UNIQUE
);

-- Identifiants officiels de la source
INSERT INTO carburant (id, nom) VALUES
    (1, 'Gazole'), (2, 'SP95'), (3, 'E85'), (4, 'GPLc'), (5, 'E10'), (6, 'SP98')
ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS service (
    id   INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nom  TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS prix (
    station_id     INTEGER  REFERENCES station(id),
    carburant_id   SMALLINT REFERENCES carburant(id),
    valeur         NUMERIC(5,3) NOT NULL CHECK (valeur > 0),       -- en euros par litre
    maj            TIMESTAMPTZ NOT NULL,                           -- date de mise à jour fournie par la source
    origine        VARCHAR(10) NOT NULL
                   CHECK (origine IN ('backfill', 'temps_reel')),
    date_collecte  TIMESTAMPTZ NOT NULL DEFAULT now(),             -- date d'insertion par le pipeline
    PRIMARY KEY (station_id, carburant_id, maj)
);

CREATE TABLE IF NOT EXISTS rupture (
    station_id    INTEGER  REFERENCES station(id),
    carburant_id  SMALLINT REFERENCES carburant(id),
    debut         TIMESTAMPTZ,
    fin           TIMESTAMPTZ,                                     -- NULL = rupture en cours
    type_rup      VARCHAR(12) CHECK (type_rup IN ('temporaire', 'definitive')),
    PRIMARY KEY (station_id, carburant_id, debut),
    CHECK (fin IS NULL OR fin >= debut)
);

CREATE TABLE IF NOT EXISTS station_service (
    station_id  INTEGER REFERENCES station(id),
    service_id  INTEGER REFERENCES service(id),
    PRIMARY KEY (station_id, service_id)
);

-- Index pour les requêtes du projet
CREATE INDEX IF NOT EXISTS idx_station_geom      ON station USING GIST (geom);  -- recherche par distance
CREATE INDEX IF NOT EXISTS idx_station_dep       ON station (code_departement); -- agrégats par département
CREATE INDEX IF NOT EXISTS idx_station_categorie ON station (categorie);        -- comparaisons par type
CREATE INDEX IF NOT EXISTS idx_prix_maj          ON prix (maj);                 -- fenêtres 7 / 30 jours
CREATE INDEX IF NOT EXISTS idx_rupture_en_cours  ON rupture (station_id)
    WHERE fin IS NULL;                                                          -- ruptures actives