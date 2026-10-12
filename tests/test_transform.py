
import pandas as pd
from joblib.testing import raises, fixture

from src.ingestion.transform import transformer, Station
from src.ingestion.transform import ResultTransformation
from dataclasses import FrozenInstanceError

@fixture
def station_valide():
    """Fixture qui fournit une station de test de base."""
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


    with raises(FrozenInstanceError):
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
    stations = ResultTransformation().stations
    assert transformer(df) == ResultTransformation()
    assert len(stations) == 0


