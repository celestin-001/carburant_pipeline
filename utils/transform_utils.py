"""Utilitaires de lecture et de validation partagés par les transformations."""
import math
import re
from enum import StrEnum
from typing import Any, NamedTuple, Optional

import pandas as pd

from src.transformation.station import Station

COORDONNEES_ECHELLE = 100_000
BORNE_LATITUDE = (41.0, 52.0)
BORNE_LONGITUDE = (-5.5, 10.0)

# Entier décimal ASCII, signe moins facultatif : refuse "123.0", "1_000", "+5", "12 3"
_ENTIER = re.compile(r"-?[0-9]+")


class Motifs(StrEnum):
    IDENTIFIANT_INVALIDE = "IDENTIFIANT INVALIDE"
    IDENTIFIANT_DUPLIQUE = "IDENTIFIANT DUPLIQUE"
    POSITION_MANQUANTE = "POSITION MANQUANTE"
    POSITION_HORS_PLAGE = "POSITION HORS PLAGE"
    CODE_POSTAL_INVALIDE = "CODE POSTAL INVALIDE"
    VILLE_MANQUANTE = "VILLE MANQUANTE"
    DEPARTEMENT_MANQUANT = "DEPARTEMENT MANQUANT"
    POP_INVALIDE = "POP INVALIDE"


class LigneInvalide(Exception):
    def __init__(self, motif: Motifs):
        super().__init__(motif)
        self.motif = motif


class Position(NamedTuple):
    latitude: float
    longitude: float


def nettoyer(valeur: Any) -> Optional[str]:
    """Texte sans espaces autour, ou None si la valeur est absente ou vide.

    Gère None, NaN et pd.NA (une cellule vide lue avec dtype=str donne un NaN).
    """
    if pd.isna(valeur):
        return None
    texte = str(valeur).strip()
    return texte or None


def lire_entier(valeur: Any) -> Optional[int]:
    """Entier, ou None si la valeur est vide ou n'est pas un entier décimal."""
    texte = nettoyer(valeur)
    if texte is None or not _ENTIER.fullmatch(texte):
        return None
    return int(texte)


def lire_position(latitude: Any, longitude: Any) -> Position:
    """Convertit des coordonnées source (degrés x 100 000) en degrés.

    Lève LigneInvalide si une valeur est absente ou illisible (POSITION_MANQUANTE)
    ou si la position sort de la boîte autour de la France (POSITION_HORS_PLAGE).
    """
    lat_txt = nettoyer(latitude)
    lon_txt = nettoyer(longitude)
    if lat_txt is None or lon_txt is None:
        raise LigneInvalide(Motifs.POSITION_MANQUANTE)

    try:
        lat = float(lat_txt) / COORDONNEES_ECHELLE
        lon = float(lon_txt) / COORDONNEES_ECHELLE
    except ValueError:
        raise LigneInvalide(Motifs.POSITION_MANQUANTE) from None

    # float("nan") et float("inf") sont acceptés par float() : on les écarte explicitement
    if not (math.isfinite(lat) and math.isfinite(lon)):
        raise LigneInvalide(Motifs.POSITION_MANQUANTE)

    dans_la_plage = (
        BORNE_LATITUDE[0] <= lat <= BORNE_LATITUDE[1]
        and BORNE_LONGITUDE[0] <= lon <= BORNE_LONGITUDE[1]
    )
    if not dans_la_plage:
        raise LigneInvalide(Motifs.POSITION_HORS_PLAGE)

    return Position(latitude=lat, longitude=lon)

def _construire_station(row)->Station:
    pass