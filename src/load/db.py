import datetime
import os
from sqlalchemy import create_engine
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime
from datetime import timezone

from src.transformation.station import Station, Service, Prix, Rupture


def get_connection():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT_HOST", "5433"),
        dbname=os.getenv("POSTGRES_DB", "carburants"),
        user=os.getenv("POSTGRES_USER", "user"),
        password=os.getenv("POSTGRES_PASSWORD","user"),
    )


def load_stations(conn, stations: list[Station]):
    if not stations:
        return

    # Tuple : id, adresse, code_postal, ville, code_departement, code_region, pop, longitude, latitude
    stations_tuples = [
        (
            s.id,
            s.adresse,
            s.code_postal,
            s.ville,
            s.code_departement,
            s.code_region,
            s.pop,
            s.longitude,  # Longitude d'abord pour ST_MakePoint
            s.latitude,   # Latitude ensuite
        )
        for s in stations
    ]

    query_sql = """
    INSERT INTO station (id, adresse, cp, ville, code_departement, code_region, pop, geom, active, derniere_vue)
    VALUES %s
    ON CONFLICT (id) DO UPDATE SET
        adresse = EXCLUDED.adresse,
        cp = EXCLUDED.cp,
        ville = EXCLUDED.ville,
        code_departement = EXCLUDED.code_departement,
        code_region = EXCLUDED.code_region,
        pop = EXCLUDED.pop,
        geom = EXCLUDED.geom,
        active = TRUE,
        derniere_vue = NOW();
    """

    template = """(
        %s, %s, %s, %s, %s, %s, %s, 
        ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, 
        TRUE, 
        NOW()
    )"""

    with conn.cursor() as cur:
        execute_values(cur, query_sql, stations_tuples, template=template)


def load_services(conn, services: list[Service]):
    if not services:
        return

    noms_uniques = list({(s.nom,) for s in services if s.nom})
    query_sql = "INSERT INTO service (nom) VALUES %s ON CONFLICT (nom) DO NOTHING;"

    with conn.cursor() as cur:
        execute_values(cur, query_sql, noms_uniques)


def load_station_services(conn, services: list[Service]):
    if not services:
        return

    station_services_tuples = [
        (s.station_id, s.nom) for s in services if s.station_id and s.nom
    ]

    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TEMP TABLE temp_station_service (
                station_id INTEGER, 
                nom TEXT
            ) ON COMMIT DROP;
            """
        )
        execute_values(
            cur,
            "INSERT INTO temp_station_service (station_id, nom) VALUES %s",
            station_services_tuples,
        )
        query = """
            INSERT INTO station_service (station_id, service_id)
            SELECT t.station_id, ser.id
            FROM temp_station_service t
            JOIN service ser ON ser.nom = t.nom
            ON CONFLICT (station_id, service_id) DO NOTHING;
        """
        cur.execute(query)


def load_prices(conn, prices: list[Prix]):
    if not prices:
        return

    prices_tuples = [
        (p.station_id, p.carburant_id, p.valeur, p.maj, p.origine) for p in prices
    ]
    query_sql = """
    INSERT INTO prix (station_id, carburant_id, valeur, maj, origine)
    VALUES %s
    ON CONFLICT (station_id, carburant_id, maj) DO NOTHING;
    """

    with conn.cursor() as cur:
        execute_values(cur, query_sql, prices_tuples)


def load_ruptures(conn, ruptures: list[Rupture], date_collecte: datetime):
    with conn.cursor() as cur:
        # 1. Lire les ruptures actuellement ouvertes en base
        cur.execute("SELECT station_id, carburant_id FROM rupture WHERE fin IS NULL;")
        rows = cur.fetchall()
        ruptures_bases = {(r[0], r[1]) for r in rows}

        # 2. Ensemble des ruptures dans le flux courant
        ruptures_new = {(r.station_id, r.carburant_id): r.debut for r in ruptures}

        # 3. Ruptures à ouvrir (présentes dans le flux, absentes de la base)
        a_inserer = [
            (sid, cid, debut)
            for (sid, cid), debut in ruptures_new.items()
            if (sid, cid) not in ruptures_bases
        ]

        if a_inserer:
            query_insert = """
                INSERT INTO rupture (station_id, carburant_id, debut)
                VALUES %s 
                ON CONFLICT (station_id, carburant_id, debut) DO NOTHING;
            """
            execute_values(cur, query_insert, a_inserer)

        # 4. Ruptures à fermer (ouvertes en base, mais absentes du flux)
        a_fermer = [(sid, cid) for (sid, cid) in ruptures_bases if (sid, cid) not in ruptures_new]

        if a_fermer:
            cur.execute(
                """
                CREATE TEMP TABLE temp_ruptures_fermer (
                    station_id INTEGER,
                    carburant_id INTEGER
                ) ON COMMIT DROP;
                """
            )
            execute_values(
                cur,
                "INSERT INTO temp_ruptures_fermer (station_id, carburant_id) VALUES %s",
                a_fermer,
            )
            cur.execute(
                """
                UPDATE rupture r
                SET fin = %s
                FROM temp_ruptures_fermer t
                WHERE r.station_id = t.station_id 
                  AND r.carburant_id = t.carburant_id 
                  AND r.fin IS NULL;
                """,
                (date_collecte,),
            )


def charger_donnees(res, date_collecte: datetime):
    with get_connection() as conn:
        load_stations(conn, res.stations)
        load_services(conn, res.services)
        load_station_services(conn, res.services)
        load_prices(conn, res.prix)
        load_ruptures(conn, res.ruptures, date_collecte)
