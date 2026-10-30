"""Utilitaires de lecture et de validation partagés par les transformations."""
import decimal
import math
import re
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from decimal import Decimal

from enum import StrEnum
from typing import Any, NamedTuple, Optional
import json
logger = logging.getLogger(__name__)


import pandas as pd

from src.transformation.station import Station, Prix, Rejet, CARBURANTS, BORNE_PRIX, ORIGINE_TEMPS_REEL, Rupture

COORDONNEES_ECHELLE = 100_000
BORNE_LATITUDE = (41.0, 52.0)
BORNE_LONGITUDE = (-5.5, 10.0)


# Entier décimal ASCII, signe moins facultatif : refuse "123.0", "1_000", "+5", "12 3"
_ENTIER = re.compile(r"-?[0-9]+")


class Motifs(StrEnum):
    DATE_INVALIDE = "DATE INVALIDE"
    IDENTIFIANT_INVALIDE = "IDENTIFIANT INVALIDE"
    IDENTIFIANT_DUPLIQUE = "IDENTIFIANT DUPLIQUE"
    POSITION_MANQUANTE = "POSITION MANQUANTE"
    POSITION_HORS_PLAGE = "POSITION HORS PLAGE"
    CODE_POSTAL_INVALIDE = "CODE POSTAL INVALIDE"
    VILLE_MANQUANTE = "VILLE MANQUANTE"
    DEPARTEMENT_MANQUANT = "DEPARTEMENT MANQUANT"
    POP_INVALIDE = "POP INVALIDE"
    PRIX_INVALIDE = "PRIX INVALIDE"
    PRIX_MANQUANT = "PRIX MANQUANT"
    DATE_MANQUANTE = "DATE MANQUANTE"
    PRIX_HORS_PLAGE = "PRIX HORS PLAGE"


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



def lire_noms_services(cellule: Any) -> list[str]:

    texte = nettoyer(cellule)              # couvre NaN, None et chaîne vide
    if texte is None:
        return []

    try:
        donnees = json.loads(texte)
    except json.JSONDecodeError:
        logger.warning("Cellule services illisible : %r")
        return []

    if not isinstance(donnees, dict):      # ex. une liste JSON
        return []

    brut = donnees.get("service")
    if isinstance(brut, str):              # un seul service : la source n'envoie pas de liste
        brut = [brut]
    if not isinstance(brut, list):         # clé absente, null, nombre...
        return []

    noms = (nettoyer(x) for x in brut if isinstance(x, str))
    return list(dict.fromkeys(n for n in noms if n))   # sans vides, sans doublons, ordre conservé


def lire_prix(val:str)->Decimal:
    prix = nettoyer(val)
    try:
        prix = Decimal(str(prix))
        if BORNE_PRIX[0] <= prix <= BORNE_PRIX[1]:
            return Decimal(prix)
        else:
            raise LigneInvalide(Motifs.PRIX_HORS_PLAGE)
    except decimal.InvalidOperation:
        raise LigneInvalide(Motifs.PRIX_INVALIDE)

def lire_date_utc(date_str:str)->datetime:

    try:
        dt = datetime.fromisoformat(date_str)

    except:
        raise LigneInvalide(Motifs.DATE_INVALIDE)

    tz = dt.tzinfo

    if tz is None or tz.utcoffset(dt) is None:
        raise ValueError(f"Date rejetée : Aucun fuseau horaire ou décalage détecté pour '{date_str}'")
    return dt.astimezone(timezone.utc)

def _construire_prix(ligne, station_id: int) -> tuple[list[Prix], list[Rejet]]:

    prix: list[Prix] = []
    rejets: list[Rejet] = []

    for carburant_id, colonnes in CARBURANTS.items():
        valeur = nettoyer(ligne.get(colonnes["prix"]))
        date = nettoyer(ligne.get(colonnes["date"]))

        if valeur is None and date is None:
            continue
        if valeur is None or date is None:
            motif = Motifs.PRIX_MANQUANT if valeur is None else Motifs.DATE_MANQUANTE
            rejets.append(Rejet(station_id, motif, carburant_id))
            continue

        try:
            valeur_lue = lire_prix(valeur)
            date_lue = lire_date_utc(date)
        except LigneInvalide as exc:
            rejets.append(Rejet(station_id, exc.motif, carburant_id))
            continue

        prix.append(Prix(
            station_id=station_id,
            carburant_id=carburant_id,
            valeur=valeur_lue,
            origine=ORIGINE_TEMPS_REEL,
            maj=date_lue,
        ))

    return prix, rejets


def _construire_ruptures(ligne: dict, station_id: int) -> list[Rupture]:
    ruptures: list[Rupture] = []


    cellule = nettoyer(ligne.get("rupture"))
    if cellule == "" or cellule is None:
        return []
    try:
        donnees = json.loads(cellule)
        if isinstance(donnees, dict):
            donnees = [donnees]
        for elt in donnees:
            if elt.get("@type") == "temporaire":

                carb_id = lire_entier(elt.get("@id"))
                rup_deb = nettoyer(elt.get("@debut"))
                if carb_id is not None:

                    try:
                        date_naive = datetime.fromisoformat(rup_deb if rup_deb is not None else "")
                        date_paris = date_naive.replace(tzinfo=ZoneInfo("Europe/Paris"))
                        date_utc = date_paris.astimezone(timezone.utc)
                        ruptures.append(
                            Rupture(station_id=station_id, carburant_id=carb_id, debut=date_utc)
                        )
                    except (ValueError, TypeError):
                        logger.warning("Date de début de rupture invalide '%s' pour station %s", rup_deb, station_id)



    except json.JSONDecodeError:
        logger.warning("Cellule rupture illisible pour la station %s", station_id)
        return []
    return ruptures
