import pytest

from utils.transform_utils import nettoyer, lire_entier, lire_position, LigneInvalide, Motifs


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
