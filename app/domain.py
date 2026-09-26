"""Core domain primitives: errors, unit helpers, FIFO ordering."""

from __future__ import annotations


class DomainError(Exception):
    """Raised for business-rule violations. Carries machine-readable details."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


# ---------------------------------------------------------------------------
# Unit helpers (MVP: g, ml, piece)
# ---------------------------------------------------------------------------

VALID_UNITS = {"g", "ml", "piece"}

UNIT_ALIASES: dict[str, str] = {
    "gram": "g",
    "grams": "g",
    "gramm": "g",
    "kg": "g",
    "milliliter": "ml",
    "milliliters": "ml",
    "liter": "ml",
    "l": "ml",
    "stueck": "piece",
    "stk": "piece",
    "stück": "piece",
    "pcs": "piece",
}

# Aliase, die nicht 1:1 auf die Basiseinheit abbilden: Mengen müssen mitskaliert
# werden (1 kg = 1000 g). Ohne diesen Faktor würde "1 kg" als "1 g" gespeichert.
UNIT_SCALE: dict[str, float] = {
    "kg": 1000.0,
    "l": 1000.0,
    "liter": 1000.0,
}


def normalise_unit(raw: str) -> str:
    low = raw.strip().lower()
    return UNIT_ALIASES.get(low, low)


def normalise_amount(amount: float, raw_unit: str) -> tuple[float, str]:
    """Menge + Einheit gemeinsam auf die Basiseinheit bringen (1 kg → 1000 g)."""
    low = raw_unit.strip().lower()
    return amount * UNIT_SCALE.get(low, 1.0), UNIT_ALIASES.get(low, low)


def assert_unit_compatible(a: str, b: str) -> None:
    na, nb = normalise_unit(a), normalise_unit(b)
    if na != nb:
        raise DomainError(
            f"Einheiten inkompatibel: {a!r} vs {b!r}",
            {"unit_a": a, "unit_b": b},
        )


# ---------------------------------------------------------------------------
# FIFO sort key for stock entries
# ---------------------------------------------------------------------------

_FAR_FUTURE = "9999-12-31"


def fifo_sort_key(entry) -> tuple:
    """Sort key: MHD ASC (NULLs last), purchase_date ASC, id ASC."""
    mhd = str(entry.mhd) if entry.mhd else _FAR_FUTURE
    pur = str(entry.purchase_date) if entry.purchase_date else _FAR_FUTURE
    return (mhd, pur, entry.id)
