import json
from pathlib import Path

import pytest
from PIL import Image

from landscape_ai_vision.analyze import analyze_photos, parse_report
from landscape_ai_vision.cli import main
from landscape_ai_vision.images import find_photos, prepare
from landscape_ai_vision.pricing import build_quote, load_rates

RATES = Path(__file__).resolve().parents[1] / "config" / "rates.example.json"


@pytest.fixture
def photos(tmp_path):
    for i in range(2):
        im = Image.new("RGB", (4000, 3000), (40, 120 + i * 20, 40))
        exif = Image.Exif()
        exif[0x010F] = "PhoneMaker"  # any tag; we only check it's gone
        im.save(tmp_path / f"yard{i}.jpg", exif=exif)
    (tmp_path / "notes.txt").write_text("not a photo")
    return tmp_path


def test_find_photos_skips_non_images(photos):
    assert [p.name for p in find_photos([photos])] == ["yard0.jpg", "yard1.jpg"]


def test_prepare_resizes_and_strips_metadata(photos):
    jpeg, size = prepare(photos / "yard0.jpg")
    assert max(size) == 1568
    out = photos / "clean.jpg"
    out.write_bytes(jpeg)
    assert len(Image.open(out).getexif()) == 0


def test_parse_report_cleans_bad_output():
    report = {
        "photo_notes": ["a"],
        "items": [
            {"id": "x", "type": "spaceship", "description": "", "photos": [0], "count": 1,
             "confidence": "low", "suggested_services": []},
            {"id": "bed", "type": "mulch_bed", "description": "", "photos": [0, 7], "count": 1,
             "area_sqft_low": 200, "area_sqft_high": 100, "confidence": "medium",
             "suggested_services": ["mulch"], "made_up_field": 1},
            {"id": "bed", "type": "shrub", "description": "", "photos": [0], "count": 2,
             "confidence": "high", "suggested_services": []},
        ],
    }
    a = parse_report(report, n_photos=1)
    assert [i.id for i in a.items] == ["bed", "bed-2"]  # unknown type dropped, dup id renamed
    bed = a.items[0]
    assert (bed.area_sqft_low, bed.area_sqft_high) == (100, 200)  # swapped back
    assert bed.photos == [0]  # out-of-range photo index removed
    assert any("spaceship" in w for w in a.warnings)


def test_quote_uses_only_contractor_rates(photos):
    a = analyze_photos([photos], backend="mock")
    rates = load_rates(RATES)
    q = build_quote(a, rates)
    by = {(l.item_id, l.service): l for l in q.lines}
    # 4 medium shrubs at $15
    assert by[("shrub-1", "shrub_trim")].price_low == 60
    # 80-120 sq ft at 2 in deep = 0.49-0.74 cu yd at $85
    mulch = by[("bed-1", "mulch")]
    assert mulch.quantity_low == pytest.approx(80 * 2 / 12 / 27, abs=0.01)
    assert mulch.price_high == pytest.approx(120 * 2 / 12 / 27 * 85, abs=0.01)
    # every price comes from the table: unit_price matches a rate
    for l in q.lines:
        svc = rates["services"][l.service]
        assert l.unit_price in ([svc["price"]] if "price" in svc else svc["price_by_size"].values())
    assert q.subtotal_low <= q.subtotal_high


def test_unoffered_service_is_listed_not_priced(photos):
    a = analyze_photos([photos], backend="mock")
    rates = load_rates(RATES)
    del rates["services"]["hedge_trim"]
    q = build_quote(a, rates)
    assert "hedge_trim" in q.unpriced
    assert all(l.service != "hedge_trim" for l in q.lines)


def test_minimum_charge(photos):
    a = analyze_photos([photos], backend="mock")
    a.items = a.items[1:2]  # just the shrubs: $60
    q = build_quote(a, load_rates(RATES))
    assert q.minimum_applied and q.subtotal_low == 75


def test_cli_mock_run(photos, tmp_path, capsys):
    out = tmp_path / "out"
    assert main([str(photos), "--mock", "--rates", str(RATES), "--out", str(out)]) == 0
    data = json.loads((out / photos.stem).with_suffix(".json").read_text())
    assert data["analysis"]["items"] and data["quote"]["lines"]
    assert "Subtotal" in capsys.readouterr().out


class _FakeMessages:
    """Stands in for client.messages; rejects tool_choice once if asked to."""

    def __init__(self, reject_tool_choice=False):
        self.reject = reject_tool_choice
        self.calls = []

    def create(self, **kw):
        import anthropic
        from types import SimpleNamespace as NS

        self.calls.append(kw)
        if self.reject and "tool_choice" in kw:
            from anthropic._base_client import httpx2 as httpx
            req = httpx.Request("POST", "https://example.invalid")
            raise anthropic.BadRequestError("tool_choice is not supported", response=httpx.Response(400, request=req), body=None)
        report = {"photo_notes": ["front yard", "side yard"], "items": [
            {"id": "shrub-1", "type": "shrub", "description": "boxwood", "photos": [0], "count": 3,
             "size": "small", "confidence": "high", "suggested_services": ["shrub_trim"]}]}
        return NS(content=[NS(type="tool_use", name="report_yard", input=report)],
                  usage=NS(input_tokens=3200, output_tokens=180), stop_reason="tool_use")


def test_bedrock_path_sends_photos_and_reports_usage(photos):
    fake = _FakeMessages()
    client = type("C", (), {"messages": fake})()
    a = analyze_photos([photos], backend="bedrock", client=client)
    call = fake.calls[0]
    assert call["model"] == "anthropic.claude-sonnet-5-5"
    assert call["tool_choice"]["name"] == "report_yard"
    images = [b for b in call["messages"][0]["content"] if b["type"] == "image"]
    assert len(images) == 2 and images[0]["source"]["media_type"] == "image/jpeg"
    assert a.usage == {"input_tokens": 3200, "output_tokens": 180}
    assert a.items[0].count == 3 and len(a.photos) == 2


def test_falls_back_when_tool_choice_rejected(photos):
    fake = _FakeMessages(reject_tool_choice=True)
    client = type("C", (), {"messages": fake})()
    a = analyze_photos([photos], backend="bedrock", client=client)
    assert len(fake.calls) == 2 and "tool_choice" not in fake.calls[1]
    assert a.items[0].id == "shrub-1"


def test_max_photos_samples_evenly(tmp_path):
    for i in range(20):
        Image.new("RGB", (10, 10)).save(tmp_path / f"p{i:02d}.jpg")
    picked = [p.name for p in find_photos([tmp_path], max_photos=5)]
    assert picked == ["p00.jpg", "p04.jpg", "p08.jpg", "p12.jpg", "p16.jpg"]
