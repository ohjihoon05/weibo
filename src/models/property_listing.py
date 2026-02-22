"""Data model for a Japanese real-estate property listing.

Provides a ``PropertyListing`` dataclass with serialisation helpers and
area-unit conversion utilities.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime

# 1 tsubo ≈ 3.306 m²
_TSUBO_TO_SQM: float = 3.306


@dataclass
class PropertyListing:
    """A single Japanese property listing with bilingual metadata.

    Required fields
    ----------------
    original_text : str
        The raw listing text as received (e.g. from a Telegram message).
    original_language : str
        ISO-639-1 code of *original_text* (``"ja"``, ``"zh"``, …).

    All other fields default to ``None`` and are populated during the
    parsing / enrichment pipeline.
    """

    # --- required --------------------------------------------------------
    original_text: str
    original_language: str

    # --- auto-generated --------------------------------------------------
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # --- property details (all optional) ---------------------------------
    name: str | None = None
    location: str | None = None
    price_jpy: int | None = None
    price_cny: float | None = None
    exchange_rate: float | None = None
    exchange_rate_date: str | None = None
    area_sqm: float | None = None
    area_tsubo: float | None = None
    layout: str | None = None
    year_built: int | None = None
    structure: str | None = None
    nearest_station: str | None = None
    management_fee: int | None = None
    repair_reserve: int | None = None
    yield_gross: float | None = None
    yield_net: float | None = None
    occupancy_status: str | None = None
    ownership_type: str | None = None
    land_area_sqm: float | None = None
    highlights: str | None = None
    contact_info: str | None = None

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Return a plain ``dict`` representation of this listing."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> PropertyListing:
        """Construct a ``PropertyListing`` from a plain ``dict``.

        Unknown keys in *data* are silently ignored so the method is
        forward-compatible with schema additions.
        """
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)

    # ------------------------------------------------------------------
    # Area conversion utilities
    # ------------------------------------------------------------------

    @staticmethod
    def area_sqm_to_tsubo(sqm: float) -> float:
        """Convert square metres to *tsubo* (1 tsubo ≈ 3.306 m²)."""
        return sqm / _TSUBO_TO_SQM

    @staticmethod
    def area_tsubo_to_sqm(tsubo: float) -> float:
        """Convert *tsubo* to square metres (1 tsubo ≈ 3.306 m²)."""
        return tsubo * _TSUBO_TO_SQM
