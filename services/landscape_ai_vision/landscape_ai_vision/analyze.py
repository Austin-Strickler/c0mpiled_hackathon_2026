"""Send a property's photos to a vision model and get back measured items.

Backends:
- "bedrock": Claude on Amazon Bedrock in our AWS account (default). Uses the
             normal AWS credential chain: AWS_PROFILE, ~/.aws, or the EC2 /
             Lambda role. Region from LAV_AWS_REGION (default us-east-2).
- "claude":  the Anthropic API directly (needs ANTHROPIC_API_KEY).
- "mock":    fixed fake result, so the pipeline, pricing and UI can be built
             and tested with no credentials and no cost.
"""

from __future__ import annotations

import os
from pathlib import Path

from .images import find_photos, prepare, to_api_block
from .prompts import REPORT_TOOL, SYSTEM, USER_TEMPLATE
from .schema import ITEM_TYPES, DetectedItem, PropertyAnalysis

DEFAULT_BACKEND = os.environ.get("LAV_BACKEND", "bedrock")
DEFAULT_REGION = os.environ.get("LAV_AWS_REGION", "us-east-2")
# Bedrock and the direct API name the same model differently.
DEFAULT_MODELS = {
    "bedrock": os.environ.get("LAV_MODEL", "anthropic.claude-sonnet-5-5"),
    "claude": os.environ.get("LAV_MODEL", "claude-sonnet-5-5"),
}
DEFAULT_MODEL = DEFAULT_MODELS.get(DEFAULT_BACKEND, DEFAULT_MODELS["bedrock"])

_FIELDS = set(DetectedItem.__dataclass_fields__)


def parse_report(report: dict, n_photos: int) -> PropertyAnalysis:
    """Validate the model's tool output and turn it into dataclasses.

    Anything malformed is dropped with a warning rather than crashing, because
    one bad item shouldn't lose the rest of the quote.
    """
    warnings: list[str] = []
    items: list[DetectedItem] = []
    seen_ids: set[str] = set()

    for raw in report.get("items", []):
        data = {k: v for k, v in raw.items() if k in _FIELDS}
        if data.get("type") not in ITEM_TYPES:
            warnings.append(f"Dropped item with unknown type {data.get('type')!r}")
            continue
        data["photos"] = sorted({p for p in data.get("photos", []) if 0 <= p < n_photos})
        # Keep low <= high even if the model swapped them.
        for lo, hi in (("area_sqft_low", "area_sqft_high"), ("length_ft_low", "length_ft_high")):
            a, b = data.get(lo), data.get(hi)
            if a is not None and b is None:
                data[hi] = a
            elif b is not None and a is None:
                data[lo] = b
            elif a is not None and b is not None and a > b:
                data[lo], data[hi] = b, a
        base, n = data.get("id") or data["type"], 2
        while data.get("id") in seen_ids or not data.get("id"):
            data["id"] = f"{base}-{n}"
            n += 1
        seen_ids.add(data["id"])
        try:
            items.append(DetectedItem(**data))
        except TypeError as e:
            warnings.append(f"Dropped malformed item {data.get('id')}: {e}")

    notes = list(report.get("photo_notes", []))
    if len(notes) != n_photos:
        warnings.append(f"Model gave {len(notes)} photo notes for {n_photos} photos")
    return PropertyAnalysis(items=items, photo_notes=notes, warnings=warnings)


def make_client(backend: str, region: str = DEFAULT_REGION):
    """Build the SDK client for a backend. AWS credentials come from the usual chain."""
    import anthropic  # imported here so the mock backend works without it

    if backend == "bedrock":
        profile = os.environ.get("LAV_AWS_PROFILE") or os.environ.get("AWS_PROFILE")
        return anthropic.AnthropicBedrockMantle(aws_region=region, aws_profile=profile)
    if backend == "claude":
        return anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    raise ValueError(f"No client for backend {backend!r}")


def _build_content(jpegs: list[bytes], customer_note: str) -> list[dict]:
    content: list[dict] = []
    for i, jpg in enumerate(jpegs):
        content.append({"type": "text", "text": f"Photo {i}:"})
        content.append(to_api_block(jpg))
    note = f"Customer's note: {customer_note.strip()}\n" if customer_note.strip() else ""
    content.append(
        {"type": "text", "text": USER_TEMPLATE.format(n=len(jpegs), last=len(jpegs) - 1, customer_note=note)}
    )
    return content


def _call_model(client, jpegs: list[bytes], customer_note: str, model: str) -> tuple[dict, dict]:
    """Return (report, usage). Forces the report_yard tool; falls back to asking
    for it if the endpoint rejects tool_choice."""
    import anthropic

    kwargs = dict(
        model=model,
        max_tokens=4096,
        system=SYSTEM,
        tools=[REPORT_TOOL],
        messages=[{"role": "user", "content": _build_content(jpegs, customer_note)}],
    )
    try:
        resp = client.messages.create(tool_choice={"type": "tool", "name": "report_yard"}, **kwargs)
    except anthropic.BadRequestError as e:
        if "tool_choice" not in str(e):
            raise
        resp = client.messages.create(**kwargs)  # the system prompt + user text still ask for the tool
    usage = {"input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens}
    for block in resp.content:
        if block.type == "tool_use" and block.name == "report_yard":
            return block.input, usage
    raise RuntimeError(f"Model did not return a report_yard result (stop_reason={resp.stop_reason})")


def _mock(n: int) -> dict:
    return {
        "photo_notes": [f"Mock note for photo {i}" for i in range(n)],
        "items": [
            {"id": "bed-1", "type": "mulch_bed", "description": "Front bed along the porch",
             "photos": [0], "count": 1, "area_sqft_low": 80, "area_sqft_high": 120,
             "condition": "mulch faded and thin", "suggested_services": ["mulch", "edging"],
             "confidence": "medium", "scale_reference": "front door, ~3 ft wide"},
            {"id": "shrub-1", "type": "shrub", "description": "Boxwoods in the front bed",
             "photos": [0], "count": 4, "size": "medium", "condition": "overgrown",
             "suggested_services": ["shrub_trim"], "confidence": "high"},
            {"id": "hedge-1", "type": "hedge", "description": "Privet hedge on the side yard",
             "photos": [min(1, n - 1)], "count": 1, "length_ft_low": 25, "length_ft_high": 35,
             "suggested_services": ["hedge_trim"], "confidence": "medium",
             "scale_reference": "fence panels, ~8 ft each"},
            {"id": "weeds-1", "type": "weeds", "description": "Weeds between patio pavers",
             "photos": [min(1, n - 1)], "count": 1, "area_sqft_low": 150, "area_sqft_high": 200,
             "suggested_services": ["weeding", "hardscape_clean"], "confidence": "low"},
        ],
    }


def analyze_photos(
    paths: list[str | Path],
    customer_note: str = "",
    backend: str = DEFAULT_BACKEND,
    model: str | None = None,
    region: str = DEFAULT_REGION,
    max_photos: int | None = None,
    client=None,
) -> PropertyAnalysis:
    photos = find_photos(paths, max_photos=max_photos)
    jpegs = [prepare(p)[0] for p in photos]
    usage = None
    if backend == "mock":
        report, model = _mock(len(jpegs)), "mock"
    elif backend in ("bedrock", "claude"):
        model = model or DEFAULT_MODELS[backend]
        report, usage = _call_model(client or make_client(backend, region), jpegs, customer_note, model)
    else:
        raise ValueError(f"Unknown backend {backend!r} (use 'bedrock', 'claude' or 'mock')")
    result = parse_report(report, len(jpegs))
    result.model = model
    result.photos = [str(p) for p in photos]
    result.usage = usage
    return result
