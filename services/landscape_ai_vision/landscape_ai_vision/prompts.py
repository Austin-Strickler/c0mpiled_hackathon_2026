"""Instructions and the structured-output tool for the vision model."""

from .schema import CONFIDENCE, ITEM_TYPES, SIZES

SYSTEM = """You inspect homeowners' photos of their yard for a landscaping contractor.
Your job is to MEASURE and DESCRIBE, never to price. Report every landscaping item
a crew would quote: mulch beds, flower beds, shrubs, hedges, trees, weeds, leaf
and debris cleanup, hardscape (patios, pavers, tile, walkways) that needs cleaning,
and edges that need edging.

Rules:
- Several photos may show the same item from different angles. Report each
  physical item ONCE and list every photo index it appears in.
- Count shrubs and trees individually when you can. Use `count` > 1 only for a
  tight group of near-identical plants you cannot separate.
- Photos have no ruler. For areas and lengths give a LOW and HIGH estimate, and
  say in `scale_reference` what you sized against (a door is ~3 ft wide and
  ~6.7 ft tall, a brick ~8 in, a standard paver ~12 in, a downspout, a person, a
  car ~15 ft long). If nothing in the frame gives scale, still estimate but set
  confidence to "low".
- Use confidence "high" only for counts you are sure of. Areas from photos are
  rarely better than "medium".
- `suggested_services` uses only these names: mulch, weeding, shrub_trim,
  hedge_trim, tree_trim, cleanup, hardscape_clean, edging, planting.
- Do not invent items you cannot see. If a photo is blurry, dark, or not a yard,
  say so in that photo's note.
"""

USER_TEMPLATE = """There are {n} photos, indexed 0 to {last}, in the order shown.
{customer_note}Report the yard's landscaping items with the report_yard tool."""

_item_schema = {
    "type": "object",
    "properties": {
        "id": {"type": "string", "description": "Short unique id, e.g. shrub-1, bed-2"},
        "type": {"type": "string", "enum": list(ITEM_TYPES)},
        "description": {"type": "string", "description": "Where it is and what it looks like"},
        "photos": {"type": "array", "items": {"type": "integer"}},
        "count": {"type": "integer", "minimum": 1},
        "size": {"type": "string", "enum": list(SIZES)},
        "area_sqft_low": {"type": "number"},
        "area_sqft_high": {"type": "number"},
        "length_ft_low": {"type": "number"},
        "length_ft_high": {"type": "number"},
        "condition": {"type": "string"},
        "suggested_services": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "string", "enum": list(CONFIDENCE)},
        "scale_reference": {"type": "string"},
    },
    "required": ["id", "type", "description", "photos", "count", "confidence", "suggested_services"],
}

REPORT_TOOL = {
    "name": "report_yard",
    "description": "Report every landscaping item seen across the photos.",
    "input_schema": {
        "type": "object",
        "properties": {
            "photo_notes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "One short note per photo, in photo order",
            },
            "items": {"type": "array", "items": _item_schema},
        },
        "required": ["photo_notes", "items"],
    },
}
