"""Command-line test harness.

    python -m landscape_ai_vision.cli samples/my_yard                  # Claude on Bedrock
    python -m landscape_ai_vision.cli samples/my_yard --max-photos 6   # fewer photos, cheaper
    python -m landscape_ai_vision.cli samples/my_yard --mock           # no AWS, no cost

Writes the full result to outputs/<folder or photo name>.json and prints a summary.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .analyze import DEFAULT_BACKEND, DEFAULT_REGION, analyze_photos
from .pricing import build_quote, load_rates


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Estimate landscaping items from yard photos")
    ap.add_argument("photos", nargs="+", help="Photo files or a folder of photos")
    ap.add_argument("--rates", default="config/rates.example.json", help="Contractor rate table JSON")
    ap.add_argument("--note", default="", help="Customer's note, e.g. 'want beds mulched and weeded'")
    ap.add_argument("--mock", action="store_true", help="Use fake results instead of a model")
    ap.add_argument("--backend", default=DEFAULT_BACKEND, choices=["bedrock", "claude", "mock"])
    ap.add_argument("--model", default=None, help="Model id (default depends on backend)")
    ap.add_argument("--region", default=DEFAULT_REGION, help="AWS region for Bedrock")
    ap.add_argument("--max-photos", type=int, default=8,
                    help="Use at most this many photos, evenly spaced (default 8)")
    ap.add_argument("--out", default="outputs")
    args = ap.parse_args(argv)

    try:
        from dotenv import load_dotenv

        load_dotenv()  # picks up LAV_* settings (and ANTHROPIC_API_KEY if used) from .env
    except ImportError:
        pass

    backend = "mock" if args.mock else args.backend
    analysis = analyze_photos(args.photos, args.note, backend, args.model, args.region, args.max_photos)
    quote = build_quote(analysis, load_rates(args.rates))

    print(f"Model: {analysis.model}  ({len(analysis.photos)} photos)")
    for i, note in enumerate(analysis.photo_notes):
        name = Path(analysis.photos[i]).name if i < len(analysis.photos) else "?"
        print(f"Photo {i} ({name}): {note}")
    print("\nItems found:")
    for it in analysis.items:
        size = f"{it.area_sqft_low:.0f}-{it.area_sqft_high:.0f} sq ft" if it.area_sqft_low is not None else (
            f"{it.length_ft_low:.0f}-{it.length_ft_high:.0f} ft" if it.length_ft_low is not None else
            f"x{it.count}" + (f" {it.size}" if it.size else ""))
        flag = "  [confirm]" if it.needs_confirmation() else ""
        print(f"  {it.id:<12} {it.type:<11} {size:<18} {it.confidence:<6} {it.description}{flag}")
    print("\nQuote (contractor's rates):")
    for l in quote.lines:
        flag = " *" if l.needs_confirmation else ""
        print(f"  {l.label:<26} {l.quantity_low:g}-{l.quantity_high:g} {l.unit:<10} "
              f"${l.price_low:,.2f} - ${l.price_high:,.2f}{flag}")
    print(f"  {'Subtotal':<26} {'':<20} ${quote.subtotal_low:,.2f} - ${quote.subtotal_high:,.2f}"
          + ("  (minimum charge applied)" if quote.minimum_applied else ""))
    if quote.unpriced:
        print("  Not priced (no matching service or measurement): " + ", ".join(quote.unpriced))
    for w in analysis.warnings:
        print("Warning: " + w)
    if analysis.usage:
        print(f"Tokens: {analysis.usage['input_tokens']:,} in, {analysis.usage['output_tokens']:,} out")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    first = Path(args.photos[0])
    name = (first.name if first.is_dir() else first.stem) if len(args.photos) == 1 else "batch"
    name = name.replace(" ", "_")
    out = out_dir / f"{name}.json"
    out.write_text(json.dumps({"analysis": analysis.to_dict(), "quote": quote.to_dict()}, indent=2))
    print(f"\nSaved {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
