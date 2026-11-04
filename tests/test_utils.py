from contextlib import nullcontext
from datetime import timezone, datetime
from decimal import Decimal

import pytest

from utils.transform_utils import nettoyer, lire_entier, lire_position, LigneInvalide, Motifs, lire_noms_services, \
    lire_prix, lire_date_utc


# ==============================================================================
# 1. TESTS POUR LA FONCTION : nettoyer()
# ==============================================================================
@pytest.mark.parametrize(
    "entree, attendu",
    [
        ("  45.0  ", "45.0"),  # Supprime les espaces au début et à la fin
        ("Calais", "Calais"),  # Une chaîne propre reste inchangée
        ("", None),  # Une chaîne vide reste vide
        (42, "42"),  # Convertit un entier en chaîne de caractères
    ]
)
def test_nettoyer(entree, attendu):
    assert nettoyer(entree) == attendu


# ==============================================================================
# 2. TESTS POUR LA FONCTION : lire_entier()
# ==============================================================================
@pytest.mark.parametrize(
    "valeur_nettoyee, attendu",
    [
        ("42", 42),  # Conversion nominale réussie
        ("-5", -5),  # Nombre négatif géré
        ("0", 0),  # Le zéro est correctement géré
    ]
)
def test_lire_entier_valide(monkeypatch, valeur_nettoyee, attendu):
    monkeypatch.setattr("utils.transform_utils.nettoyer", lambda x: valeur_nettoyee)
    assert lire_entier("brut") == attendu


@pytest.mark.parametrize(
    "valeur_nettoyee",
    [
        "",  # Chaîne vide -> None
        "abc",  # Texte -> ValueError capturée -> None
        "12.34",  # Flottant -> ValueError capturée -> None
    ]
)
def test_lire_entier_invalide(monkeypatch, valeur_nettoyee):
    monkeypatch.setattr("utils.transform_utils.nettoyer", lambda x: valeur_nettoyee)
    assert lire_entier("brut") is None


# ==============================================================================
# 3. TESTS POUR LA FONCTION : lire_position()
# ==============================================================================
@pytest.mark.parametrize(
    "lat_brute, long_brute, lat_attendue, long_attendue",
    [
        ("5095000", "185000", 50.95, 1.85),
    ]
)
def test_lire_position_valide(monkeypatch, lat_brute, long_brute, lat_attendue, long_attendue):
    monkeypatch.setattr("utils.transform_utils.nettoyer", lambda x: str(x).strip() if x is not None else "")
    assert lire_position(lat_brute, long_brute) == (pytest.approx(lat_attendue), pytest.approx(long_attendue))


@pytest.mark.parametrize(
    "lat_brute, long_brute",
    [
        ("abc", "2.0"),
        ("", "2.0"),
        ("45.0", "   "),
    ]
)
def test_lire_position_manquante_ou_texte(monkeypatch, lat_brute, long_brute):
    monkeypatch.setattr("utils.transform_utils.nettoyer", lambda x: str(x).strip() if x is not None else "")

    with pytest.raises(LigneInvalide) as exc_info:
        lire_position(lat_brute, long_brute)
    assert exc_info.value.motif == Motifs.POSITION_MANQUANTE


@pytest.mark.parametrize(
    "lat_brute, long_brute",
    [
        ("0", "0"),  # Cas spécifique (0,0)
        ("99.0", "2.0"),  # Latitude hors plage
        ("48.183", "3.309"),  # Votre cas spécifique à Sens imposé hors plage
    ]
)
def test_lire_position_hors_plage(monkeypatch, lat_brute, long_brute):
    """Vérifie que le point (0,0) et les valeurs hors bornes lèvent POSITION_HORS_PLAGE."""
    monkeypatch.setattr("utils.transform_utils.nettoyer", lambda x: str(x).strip())

    with pytest.raises(LigneInvalide) as exc_info:
        lire_position(lat_brute, long_brute)
    assert exc_info.value.motif == Motifs.POSITION_HORS_PLAGE




@pytest.mark.parametrize("cellule, attendu", [
    ('{"service": ["Wifi", "Toilettes publiques"]}', ["Wifi", "Toilettes publiques"]),
    ('{"service": "Wifi"}', ["Wifi"]),                       # un seul service, sans liste
    ('{"service": ["Wifi", "Wifi"]}', ["Wifi"]),             # doublon
    ('{"service": ["Vente de gaz domestique (Butane, Propane)"]}',
     ["Vente de gaz domestique (Butane, Propane)"]),         # virgule dans le nom
    ('{"service": [" Wifi ", ""]}', ["Wifi"]),               # espaces et vide
    ('{"service": [1, null, "Wifi"]}', ["Wifi"]),            # éléments qui ne sont pas du texte
    (float("nan"), []),                                      # cellule vide du CSV
    ("", []),
    ("pas du json", []),
    ('["Wifi"]', []),                                        # JSON qui n'est pas un objet
    ('{"autre": 1}', []),                                    # clé absente
    ('{"service": null}', []),
])
def test_lire_noms_services(cellule, attendu):
    assert lire_noms_services(cellule) == attendu


@pytest.mark.parametrize(
     "valeur, attendu, exception, motif_attendu",
    [
        ("1.849", Decimal("1.849"), None, None),
        ("5.0", Decimal("5.0"), None, None),

        ("0.1", None, LigneInvalide, Motifs.PRIX_HORS_PLAGE),
        ("6", None, LigneInvalide, Motifs.PRIX_HORS_PLAGE),


        ("nan", None, LigneInvalide, Motifs.PRIX_INVALIDE),
        ("abc", None, LigneInvalide, Motifs.PRIX_INVALIDE),
        ("", None, LigneInvalide, Motifs.PRIX_INVALIDE),
    ]
)
def test_lire_prix(valeur, attendu, exception, motif_attendu):
    gestionnaire_contexte = pytest.raises(exception) if exception else nullcontext()

    with gestionnaire_contexte as exc_info:
        prix_obtenu = lire_prix(valeur)

        if exception is None:
            assert isinstance(prix_obtenu, Decimal)
            assert prix_obtenu == attendu

    if exception is not None:
        assert exc_info.value.motif == motif_attendu


def test_lire_date_utc_conversion_valide():

    date_brute = "2026-10-07 08:56:19+02"
    date_traitee = lire_date_utc(date_brute)

    # 18h00 à Paris (+02:00) doit devenir 16h00 en UTC
    assert date_traitee == datetime(2026, 10, 7, 6, 56, 19, tzinfo=timezone.utc)


# 2. LE TEST D'ÉCHEC : Vérifie qu'une date "naïve" (sans fuseau) lève bien une ValueError
def test_lire_date_utc_rejette_sans_fuseau():
    date_naive = "2026-10-20T18:00:00"  # Pas de 'Z', pas de '+02:00'

    with pytest.raises(ValueError) as exc_info:
        lire_date_utc(date_naive)

    assert "Aucun fuseau horaire" in str(exc_info.value)



