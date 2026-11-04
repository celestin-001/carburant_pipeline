
import pandas as pd
import pytest
import glob

from src.transformation.station import Station
from src.transformation.station_transform  import transformer
from pathlib import Path

DIR = Path.cwd().parent

chemin = str(DIR/ "carburant-pipeline" / "data" / "raw" / "prix-carburants_*.csv")
files = sorted(glob.glob(chemin))
dernier_fichier = files[-1]
print(dernier_fichier)
@pytest.fixture
def station_valide():
    return Station(
        id=1,
        code_postal="62100",
        ville="Calais",
        code_departement="62",
        pop="R",
        latitude=50.9513,
        longitude=1.8563
    )

def test_creation_station_avec_valeurs_par_defaut(station_valide):
    assert station_valide.id == 1
    assert station_valide.ville == "Calais"
    assert station_valide.adresse is None
    assert station_valide.code_region is None

def test_immutabilite_station(station_valide):
    """
       :type station_valide: object
    """
    with pytest.raises(AttributeError):
        station_valide.ville = "Dunkerque"

def test_creation_station_avec_valeurs_optionnelles():
    station_complete = Station(
        id=2,
        code_postal="75001",
        ville="Paris",
        code_departement="75",
        pop="R",
        latitude=48.8566,
        longitude=2.3522,
        adresse="1 Rue de Rivoli",
        code_region="11"
    )
    assert station_complete.adresse == "1 Rue de Rivoli"
    assert station_complete.code_region == "11"

def test_egalite_stations(station_valide):
    station_identique = Station(
        id=1,
        code_postal="62100",
        ville="Calais",
        code_departement="62",
        pop="R",
        latitude=50.9513,
        longitude=1.8563
    )
    assert station_valide == station_identique

def test_transform():

    df = pd.DataFrame()
    result = transformer(df)
    assert len(result.stations) == 0

def test_transformer_valid():
    df = pd.read_csv(dernier_fichier,dtype="str")
    result = transformer(df)
    assert len(result.stations) + len(result.rejets) == len(df)

import json
from datetime import datetime, timezone
from decimal import Decimal
NAN = float("nan")  # ce que read_csv(dtype=str) produit pour une cellule vide
NOMS_CARBURANTS = ["Gazole", "SP95", "E85", "GPLc", "E10", "SP98"]


def _json_services(*noms):
    return json.dumps({"service": list(noms)}, ensure_ascii=False)


LIGNE_VALIDE = {
    "id": "1000001",
    "latitude": "5095000",
    "longitude": "185000",
    "Code postal": "62100",
    "Ville": "Calais",
    "code_departement": "62",
    "pop": "R",
    "Adresse": "1 rue de Test",
    "code_region": "32",
    "services": json.dumps({"service": ["Toilettes publiques", "Wifi", "Boutique alimentaire"]}, ensure_ascii=False),
    "Prix Gazole mis à jour le": "",
    "Prix Gazole": "5",
    "Prix SP95 mis à jour le": "",
    "Prix SP95": "",
    "Prix E85 mis à jour le": "",
    "Prix E85": "",
    "Prix GPLc mis à jour le": "",
    "Prix GPLc": "",
    "Prix E10 mis à jour le": "",
    "Prix E10": "",
    "Prix SP98 mis à jour le": "",
    "Prix SP98": ""
}

# Aucun prix par défaut, sauf le gazole
for nom in NOMS_CARBURANTS:
    LIGNE_VALIDE[f"Prix {nom}"] = NAN
    LIGNE_VALIDE[f"Prix {nom} mis à jour le"] = NAN
LIGNE_VALIDE["Prix Gazole"] = "2.25"
LIGNE_VALIDE["Prix Gazole mis à jour le"] = "2026-10-09 04:15:00+02"


def ligne(modifs=None):
    return {**LIGNE_VALIDE, **(modifs or {})}


def faire_df(*lignes):
    return pd.DataFrame(list(lignes))


# =============================== SERVICES ====================================

def test_trois_services():
    r = transformer(faire_df(ligne()))
    assert {s.nom for s in r.services} == {
        "Toilettes publiques", "Wifi", "Boutique alimentaire",
    }
    assert all(s.station_id == 1000001 for s in r.services)
    assert len(r.services) == 3


def test_cellule_vide_ne_rejette_pas_la_station():
    r = transformer(faire_df(ligne({"services": NAN})))
    assert len(r.services) == 0
    assert len(r.stations) == 1
    assert len(r.rejets) == 0


def test_json_invalide_ne_rejette_pas_la_station():
    r = transformer(faire_df(ligne({"services": "ceci n'est pas du json"})))
    assert len(r.services) == 0
    assert len(r.stations) == 1


def test_un_seul_service_sans_liste():
    r = transformer(faire_df(ligne({"services": '{"service": "Wifi"}'})))
    assert [s.nom for s in r.services] == ["Wifi"]


def test_service_en_double_dans_une_station():
    r = transformer(faire_df(ligne({"services": _json_services("Wifi", "Wifi")})))
    assert [s.nom for s in r.services] == ["Wifi"]


def test_virgule_dans_un_nom_de_service():
    nom = "Vente de gaz domestique (Butane, Propane)"
    r = transformer(faire_df(ligne({"services": _json_services(nom)})))
    assert [s.nom for s in r.services] == [nom]


def test_station_rejetee_sans_service_ni_prix():
    r = transformer(faire_df(ligne({"pop": "X"})))
    assert len(r.stations) == 0
    assert len(r.services) == 0
    assert len(r.prix) == 0


# ================================= PRIX ======================================

def test_prix_valide():
    r = transformer(faire_df(ligne()))
    assert len(r.prix) == 1
    p = r.prix[0]
    assert p.station_id == 1000001
    assert p.carburant_id == 1  # Gazole
    assert p.valeur == Decimal("2.25")
    assert p.origine == "temps_reel"
    assert p.maj.tzinfo is not None  # jamais de date sans fuseau
    assert p.maj == datetime(2026, 10, 9, 2, 15, tzinfo=timezone.utc)


def test_carburant_non_vendu_ne_produit_rien():
    # les cinq autres carburants sont vides : ni prix, ni rejet
    r = transformer(faire_df(ligne()))
    assert [p.carburant_id for p in r.prix] == [1]
    assert len(r.rejets) == 0


@pytest.mark.parametrize("source, attendu", [
    ("2026-10-09 04:15:00+02", datetime(2026, 10, 9, 2, 15, tzinfo=timezone.utc)),  # heure d'été
    ("2026-12-09 04:15:00+01", datetime(2026, 12, 9, 3, 15, tzinfo=timezone.utc)),  # heure d'hiver
])
def test_date_convertie_en_utc(source, attendu):
    r = transformer(faire_df(ligne({"Prix Gazole mis à jour le": source})))
    assert r.prix[0].maj == attendu


def test_prix_sans_date_est_rejete_mais_la_station_reste():
    r = transformer(faire_df(ligne({"Prix Gazole mis à jour le": NAN})))
    assert len(r.prix) == 0
    assert len(r.stations) == 1
    assert len(r.rejets) == 1


def test_date_sans_prix_est_rejetee_mais_la_station_reste():
    r = transformer(faire_df(ligne({"Prix Gazole": NAN})))
    assert len(r.prix) == 0
    assert len(r.stations) == 1
    assert len(r.rejets) == 1


@pytest.mark.parametrize("valeur", ["0", "9", "abc", "nan"])  # "nan" : piège de Decimal
def test_prix_invalide_est_rejete_mais_la_station_reste(valeur):
    r = transformer(faire_df(ligne({"Prix Gazole": valeur})))
    assert len(r.prix) == 0
    assert len(r.stations) == 1
    assert len(r.rejets) == 1


def test_date_illisible_est_rejetee():
    r = transformer(faire_df(ligne({"Prix Gazole mis à jour le": "pas une date"})))
    assert len(r.prix) == 0
    assert len(r.rejets) == 1

def test_carburant_non_vendu_ne_produit_aucun_rejet():
    # tous les carburants sauf le gazole sont vides dans LIGNE_VALIDE
    r = transformer(faire_df(ligne()))
    assert len(r.rejets) == 0

def test_rupture_temporaire_valide():
    json_rup = '[{"@nom": "SP95", "@id": "2", "@debut": "2026-03-12 17:02:34", "@type": "temporaire"}]'
    r = transformer(faire_df(ligne({"rupture": json_rup})))
    assert len(r.ruptures) == 1
    rup = r.ruptures[0]
    assert rup.station_id == 1000001
    assert rup.carburant_id == 2
    assert rup.debut == datetime(2026, 3, 12, 16, 2, 34, tzinfo=timezone.utc)

def test_rupture_definitive_ignoree():
    json_rup = '[{"@nom": "Gazole", "@id": "1", "@debut": "2020-01-01 10:00:00", "@type": "definitive"}]'
    r = transformer(faire_df(ligne({"rupture": json_rup})))
    assert r.ruptures == []

def test_rupture_json_invalide_ne_rejette_pas_la_station():
    r_vide = transformer(faire_df(ligne({"rupture": NAN})))
    assert r_vide.ruptures == []
    assert len(r_vide.stations) == 1

    r_invalide = transformer(faire_df(ligne({"rupture": "pas du json"})))
    assert r_invalide.ruptures == []
    assert len(r_invalide.stations) == 1


def test_rupture_unique_dict_sans_liste():
    """La source envoie parfois un objet dict unique au lieu d'une liste JSON."""
    json_rup = '{"@nom": "E85", "@id": "3", "@debut": "2026-03-12 17:02:34", "@type": "temporaire"}'
    r = transformer(faire_df(ligne({"rupture": json_rup})))

    assert len(r.ruptures) == 1
    assert r.ruptures[0].carburant_id == 3