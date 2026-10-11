# landscape_ai_vision

Photo-based landscaping estimates. A customer uploads photos of their yard; a
vision model finds and **measures** mulch beds, flower beds, shrubs, hedges,
trees, weeds, debris, hardscape (patios, pavers, tile) and edges. The quote is
then **priced only from the contractor's rate table** (roadmap rule R20): the
model never sets a price.

```
photos ──► images.py ──► analyze.py ──► pricing.py ──► quote JSON
          rotate, resize   vision model     contractor's
          strip GPS/EXIF   measures items   rate table
```

## Setup (on the AWS machine or a laptop)

```bash
cd landscape_ai_vision
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # defaults: Bedrock, us-east-2, AWS profile "lawn"
python -m pytest -q         # 10 tests, no AWS needed
```

### Turn on Bedrock (one time, in the AWS console)

1. **Bedrock → Model access** (region us-east-2): request access to the Claude
   models. Sonnet 5.5 is the default; Haiku 5.5 is cheaper for bulk testing.
2. **Permissions:** the user or instance role running this needs
   `bedrock-mantle:CreateInference` on those models. On an EC2 machine, attach it
   to the instance role and drop `LAV_AWS_PROFILE` from `.env`.
3. Check it, for well under a cent:

```bash
python -m landscape_ai_vision.check_bedrock
```

It prints your AWS identity and which models answer. Put a working one in `LAV_MODEL`.

## Try it

```bash
# No AWS, fake results: checks the whole pipeline end to end
python -m landscape_ai_vision.cli samples/ --mock

# Real analysis on Bedrock (uses 8 evenly spaced photos by default)
python -m landscape_ai_vision.cli "../data_test/4219_Greywood_Drive_York_PA_17402/House Images" \
    --note "Want the front beds mulched and the bushes trimmed"

# Cheaper while iterating: fewer photos, smaller model
python -m landscape_ai_vision.cli samples/my_yard --max-photos 4 --model anthropic.claude-haiku-5-5
```

The summary prints to the terminal with the token count for that run; the full
result goes to `outputs/<name>.json`. Each run is one request, so spend scales
with photos per run (roughly 1,500 input tokens per photo at full size).

## Using it from the backend

```python
from landscape_ai_vision import analyze_photos, build_quote, load_rates

analysis = analyze_photos(["/path/photo1.jpg", "/path/photo2.jpg"], customer_note="...")  # Bedrock by default
quote = build_quote(analysis, contractor_rates_dict)
payload = {"analysis": analysis.to_dict(), "quote": quote.to_dict()}
```

`contractor_rates_dict` should come from the contractor's published pricing
version; `config/rates.example.json` shows the shape.

## What the output means

- **Items** are deduplicated across photos (the same shrub seen twice counts once).
- **Areas and lengths are ranges.** Photos have no ruler; the model sizes against
  doors, bricks, pavers, fences and says what it used in `scale_reference`.
- **`needs_confirmation`** marks lines the contractor should check before the
  job is booked (any low-confidence item, and any area or length not rated high).
- **`unpriced`** lists services the model suggested that the contractor doesn't
  offer, or that lacked the measurement the rate needs.

## Rules this module follows

- **R20:** the model measures, the contractor's table prices.
- **R19:** photos are customer data. GPS and all EXIF metadata are stripped
  before upload, and `samples/` and `outputs/` are git-ignored.
- **R6:** quotes are estimates (ranges plus confirmation flags), not contracts.

## Known limits and next steps

- Areas from ground-level photos are rough. Options to test: tie beds to the
  satellite outline the customer already traced, ask for a known object in frame,
  or keep ranges and have the contractor confirm.
- Compare models on cost and accuracy with `--model` (or `LAV_MODEL` in `.env`).
- To serve it: the repo's API is TypeScript Lambdas, so the production call
  probably moves into `services/lambdas` with the same prompt and tool schema,
  and pricing goes through `packages/pricing`. This Python module is the
  prototype that settles the prompt, the schema and the model choice first.
- Add an HTTP endpoint (upload photos, return quote JSON) once the backend's
  framework is settled.
