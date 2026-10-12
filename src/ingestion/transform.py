from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Set, Optional, Literal
import pandas as pd
from decimal import Decimal
from enum import StrEnum

CARBURANTS = {
    1: {"id": 1,"nom": "Gazole","prix": "Prix Gazole","date": "Prix Gazole mis à jour le",},
    2: {"id": 2, "nom": "SP95", "prix": "Prix SP95", "date": "Prix SP95 mis à jour le"},
    3: {"id": 3, "nom": "E85", "prix": "Prix E85", "date": "Prix E85 mis à jour le"},
    4: {"id": 4, "nom": "GPLc", "prix": "Prix GPLc", "date": "Prix GPLc mis à jour le"},
    5: {"id": 5, "nom": "E10", "prix": "Prix E10", "date": "Prix E10 mis à jour le"},
    6: {"id": 6, "nom": "SP98", "prix": "Prix SP98", "date": "Prix SP98 mis à jour le"},
}


class Motifs(StrEnum):
    IDENTIFIANT_INVALIDE = "IDENTIFIANT INVALIDE"
    IDENTIFIANT_DUPLIQUE = "IDENTIFIANT DUPLIQUE"
    POSITION_MANQUANTE = "POSITION MANQUANTE"
    POSITION_HORS_PLAGE = "POSITION HORS PLAGE"
    CODE_POSTAL_INVALIDE = "CODE POSTAL INVALIDE"
    VILLE_MANQUANTE = "VILLE MANQUANTE"
    DEPARTEMENT_MANQUANT = "DEPARTEMENT MANQUANT"
    POP_INVALIDE = "POP INVALIDE"


COORDONNEES_ECHELLE = 100000
BORNE_PRIX = (Decimal("0.3"), Decimal("5.0"))
BORNE_LATITUDE = (41.0, 52.0)
BORNE_LONGITUDE = (-5.5, 10.0)
POP_VALIDES = {"R", "A"}


@dataclass(frozen=True)
class Station:
    id: int
    code_postal: str
    ville: str
    code_departement: str
    pop: str
    latitude: float
    longitude: float
    adresse: Optional[str] = None
    code_region: Optional[str] = None


@dataclass(frozen=True)
class Service:
    station_id: int
    nom: str


@dataclass(frozen=True)
class Prix:
    station_id: int
    carburant_id: int
    valeur: Decimal
    origine: Literal["backfill", "temps_reel"]
    maj: datetime


@dataclass(frozen=True)
class Rupture:
    station_id: int
    carburant_id: int
    debut: datetime


@dataclass(frozen=True)
class Rejet:
    station_id: Optional[int]
    motif: Motifs


@dataclass
class ResultTransformation:
    stations: List[Station] = field(default_factory=list)
    rejets: List[Rejet] = field(default_factory=list)
    services: List[Service] = field(default_factory=list)
    ruptures: List[Rupture] = field(default_factory=list)
    prix: List[Prix] = field(default_factory=list)


class LigneInvalide(Exception):
    def __init__(self, motif: Motifs):
        super().__init__(motif)
        self.motif = motif


def transformer(df: pd.DataFrame) -> ResultTransformation:
    return ResultTransformation()
