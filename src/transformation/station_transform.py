from src.transformation.station import Station, LigneInvalide, Motifs, POP_VALIDES, ResultTransformation, Rejet,COLONNES_OBLIGATOIRES
from utils.transform_utils import *


def _verifier_colonnes(df: pd.DataFrame) -> None:

    manquantes = COLONNES_OBLIGATOIRES - set(df.columns)
    if manquantes:
        raise ValueError(
            f"Colonnes obligatoires absentes de la source : {sorted(manquantes)}"
        )

def _construire_station(raw)->Station:
    try:
        id_station = lire_entier(raw['id'])
        if id_station is None:
            raise LigneInvalide(Motifs.IDENTIFIANT_INVALIDE)

        cp =nettoyer(raw['Code postal'])
        if not cp:
            raise LigneInvalide(Motifs.CODE_POSTAL_INVALIDE)

        ville = nettoyer(raw['Ville'])
        if not ville:
            raise LigneInvalide(Motifs.VILLE_MANQUANTE)

        pop = raw['pop']
        if pop not in POP_VALIDES:
            raise LigneInvalide(Motifs.POP_INVALIDE)

        cd = raw['code_departement']
        if not cd:
            raise LigneInvalide(Motifs.DEPARTEMENT_MANQUANT)
        adresse = raw['Adresse']
        pos = lire_position(raw['latitude'], raw['longitude'])
        code_region = raw['code_region']

        return Station(
            id=id_station,
            code_postal=cp,
            ville=ville,
            code_departement=cd,
            code_region=code_region,
            adresse=adresse,
            pop=pop,
            longitude=pos.longitude,
            latitude=pos.latitude,
        )
    except LigneInvalide:
        raise


def transformer(df: pd.DataFrame) -> ResultTransformation:

    resultat = ResultTransformation()
    if df.empty:
        return resultat

    _verifier_colonnes(df)
    identifiants_vus: set[int] = set()

    for ligne in df.to_dict(orient="records"):
        try:
            station = _construire_station(ligne)
            if station.id in identifiants_vus:
                raise LigneInvalide(Motifs.IDENTIFIANT_DUPLIQUE)
            identifiants_vus.add(station.id)
            resultat.stations.append(station)
        except LigneInvalide as exc:
            resultat.rejets.append(Rejet(lire_entier(ligne["id"]), exc.motif))

    return resultat

