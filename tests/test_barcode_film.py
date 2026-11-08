"""Filmtitel aus einer fremden EAN-Datenbank bereinigen (seit 2026-11-07)."""
from app.services.barcode import filmtitel_bereinigen


def test_zusaetze_fallen_weg():
    assert filmtitel_bereinigen("Inception (DVD, 2010) [Widescreen]") == "Inception"
    assert filmtitel_bereinigen("Der Pate - Blu-ray") == "Der Pate"
    assert filmtitel_bereinigen("Amelie [Blu-ray] [2001]") == "Amelie"
    assert filmtitel_bereinigen("Matrix 4K UHD") == "Matrix"
    assert filmtitel_bereinigen("Herr der Ringe: Die Gefährten (Special Edition)") == "Herr der Ringe: Die Gefährten"


def test_klammer_ohne_zusatz_bleibt():
    assert filmtitel_bereinigen("Up (Pixar)") == "Up (Pixar)"
