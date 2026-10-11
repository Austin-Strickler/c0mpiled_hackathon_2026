"""Data shapes shared by the analyzer, the pricer and the CLI.

The vision model only fills in *measurements* (what is there, how many, how
big). Prices are computed afterwards from the contractor's rate table
(roadmap rule R20), never by the model.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional

# What the model is allowed to report. Keep this list in sync with
# prompts.py and with the services in config/rates.example.json.
ITEM_TYPES = {
    "mulch_bed": "Bed covered (or to be covered) with mulch or bark",
    "flower_bed": "Bed of flowers or perennials",
    "shrub": "Individual bush or shrub",
    "hedge": "Continuous row of shrubs trimmed as one hedge",
    "tree": "Tree (trunk visible or clearly a tree canopy)",
    "weeds": "Area overgrown with weeds that needs pulling",
    "leaf_debris": "Leaves, sticks or yard debris to clean up",
    "hardscape": "Patio, pavers, tile, walkway or stone that needs cleaning",
    "edging": "Bed or walkway edge that needs edging",
    "other": "Anything landscaping-related that fits none of the above",
}

SIZES = ("small", "medium", "large")
CONFIDENCE = ("low", "medium", "high")


@dataclass
class DetectedItem:
    """One thing in the yard, deduplicated across all photos."""

    id: str
    type: str
    description: str
    photos: list[int]  # indexes into the photo list this item appears in
    count: int = 1
    size: Optional[str] = None  # small / medium / large, for shrubs and trees
    area_sqft_low: Optional[float] = None  # for beds, weeds, hardscape
    area_sqft_high: Optional[float] = None
    length_ft_low: Optional[float] = None  # for hedges and edging
    length_ft_high: Optional[float] = None
    condition: Optional[str] = None  # e.g. "overgrown", "mulch faded"
    suggested_services: list[str] = field(default_factory=list)
    confidence: str = "low"
    scale_reference: Optional[str] = None  # what the model used to judge size

    def needs_confirmation(self) -> bool:
        """Areas and lengths from photos are rough; flag them for the contractor."""
        has_measure = self.area_sqft_high is not None or self.length_ft_high is not None
        return self.confidence == "low" or (has_measure and self.confidence != "high")


@dataclass
class PropertyAnalysis:
    items: list[DetectedItem]
    photo_notes: list[str]  # one short note per photo (what it shows, quality issues)
    warnings: list[str] = field(default_factory=list)
    model: Optional[str] = None
    photos: list[str] = field(default_factory=list)  # file names, in photo-index order
    usage: Optional[dict] = None  # input/output tokens, to keep an eye on Bedrock spend

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class QuoteLine:
    item_id: str
    service: str
    label: str
    quantity_low: float
    quantity_high: float
    unit: str
    unit_price: float
    price_low: float
    price_high: float
    needs_confirmation: bool


@dataclass
class Quote:
    lines: list[QuoteLine]
    subtotal_low: float
    subtotal_high: float
    minimum_applied: bool
    unpriced: list[str]  # services the model suggested that the contractor doesn't offer

    def to_dict(self) -> dict:
        return asdict(self)
