"""Turn measured items into a quote using ONLY the contractor's rate table (R20).

Rate table format (see config/rates.example.json):

    {
      "minimum_charge": 75,
      "mulch_depth_in": 2,
      "services": {
        "mulch":      {"label": "Mulch install", "unit": "cubic_yard", "price": 85},
        "shrub_trim": {"label": "Shrub trimming", "unit": "each",
                       "price_by_size": {"small": 8, "medium": 15, "large": 30}},
        ...
      }
    }

Units: "sqft", "linear_ft", "each", "cubic_yard" (mulch only; converted from
bed area and depth), "flat" (one charge per item).
Prices are given as low/high ranges because photo measurements are ranges;
the contractor confirms anything flagged before the job is booked.
"""

from __future__ import annotations

import json
from pathlib import Path

from .schema import DetectedItem, PropertyAnalysis, Quote, QuoteLine

CUBIC_FT_PER_YARD = 27.0


def load_rates(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _quantity(item: DetectedItem, unit: str, rates: dict) -> tuple[float, float] | None:
    if unit == "each":
        return float(item.count), float(item.count)
    if unit == "flat":
        return 1.0, 1.0
    if unit == "sqft" and item.area_sqft_low is not None:
        return item.area_sqft_low, item.area_sqft_high
    if unit == "linear_ft" and item.length_ft_low is not None:
        return item.length_ft_low, item.length_ft_high
    if unit == "cubic_yard" and item.area_sqft_low is not None:
        depth_ft = rates.get("mulch_depth_in", 2) / 12.0
        return (item.area_sqft_low * depth_ft / CUBIC_FT_PER_YARD,
                item.area_sqft_high * depth_ft / CUBIC_FT_PER_YARD)
    return None  # the item has no measurement in the unit this service needs


def _unit_price(service: dict, item: DetectedItem) -> float | None:
    if "price_by_size" in service:
        return service["price_by_size"].get(item.size or "medium")
    return service.get("price")


def build_quote(analysis: PropertyAnalysis, rates: dict) -> Quote:
    services = rates.get("services", {})
    lines: list[QuoteLine] = []
    unpriced: set[str] = set()

    for item in analysis.items:
        for name in item.suggested_services:
            svc = services.get(name)
            if svc is None:
                unpriced.add(name)
                continue
            qty = _quantity(item, svc["unit"], rates)
            price = _unit_price(svc, item)
            if qty is None or price is None:
                unpriced.add(f"{name} ({item.id}: no {svc['unit']} measurement)")
                continue
            lo, hi = qty
            lines.append(QuoteLine(
                item_id=item.id, service=name, label=svc.get("label", name),
                quantity_low=round(lo, 2), quantity_high=round(hi, 2), unit=svc["unit"],
                unit_price=price, price_low=round(lo * price, 2), price_high=round(hi * price, 2),
                needs_confirmation=item.needs_confirmation(),
            ))

    sub_lo = round(sum(l.price_low for l in lines), 2)
    sub_hi = round(sum(l.price_high for l in lines), 2)
    minimum = float(rates.get("minimum_charge", 0))
    applied = sub_lo < minimum
    if applied:
        sub_lo, sub_hi = max(sub_lo, minimum), max(sub_hi, minimum)
    return Quote(lines=lines, subtotal_low=sub_lo, subtotal_high=sub_hi,
                 minimum_applied=applied, unpriced=sorted(unpriced))
