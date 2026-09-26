"""Regressionstests fuer den SPA-Fallback (Pfad-Traversal).

Hintergrund: der Fallback lieferte jede Datei aus, die der Prozess lesen kann.
`GET /..%2f..%2fdata%2fapp.db` gab die komplette SQLite-DB heraus, also alle
Mandanten auf einmal, am owner_sub-Scoping vorbei. Der Saganta-app-Proxy reicht
die prozentkodierte Form unveraendert durch (JS `new URL()` normalisiert nur den
unkodierten Fall), der Weg war also nicht auf 127.0.0.1 beschraenkt.

Die Tests gehen bewusst ueber `resolve_spa_path` statt ueber den TestClient:
`app/static` entsteht erst im Image-Build (COPY --from=frontend), auf dem Host
existiert es nicht, ein Client-Test wuerde hier still nichts pruefen.
"""

import pytest

from app.main import resolve_spa_path


@pytest.fixture
def spa_root(tmp_path):
    """Static-Wurzel mit index.html, daneben (ausserhalb) ein Geheimnis."""
    root = tmp_path / "static"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text("<!doctype html>ok")
    (root / "assets" / "app.js").write_text("console.log(1)")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "app.db").write_text("SQLite format 3")
    return root


@pytest.mark.parametrize(
    "path",
    [
        "../data/app.db",
        "../../etc/passwd",
        "assets/../../data/app.db",
        "../main.py",
        "./../data/app.db",
    ],
)
def test_traversal_wird_abgewiesen(spa_root, path):
    assert resolve_spa_path(spa_root, path) is None


def test_symlink_aus_der_wurzel_heraus_wird_abgewiesen(spa_root, tmp_path):
    link = spa_root / "leak.db"
    link.symlink_to(tmp_path / "data" / "app.db")
    assert resolve_spa_path(spa_root, "leak.db") is None


def test_echte_datei_wird_weiter_ausgeliefert(spa_root):
    assert resolve_spa_path(spa_root, "index.html") == spa_root / "index.html"
    assert resolve_spa_path(spa_root, "assets/app.js") == spa_root / "assets" / "app.js"


def test_unbekannte_route_faellt_auf_index_zurueck(spa_root):
    # Client-Routen wie /bestand sind keine Dateien -> None -> Aufrufer liefert index.html
    assert resolve_spa_path(spa_root, "bestand") is None
    assert resolve_spa_path(spa_root, "") is None
