"""Check that Bedrock is reachable and which Claude models this account can call.

    python -m landscape_ai_vision.check_bedrock
    python -m landscape_ai_vision.check_bedrock --region us-east-2 --models anthropic.claude-haiku-5-5

Each check is a one-word text request (about 20 tokens), so this costs well
under a cent. No photos are sent.
"""

from __future__ import annotations

import argparse
import os

from .analyze import DEFAULT_REGION, make_client

CANDIDATES = [
    "anthropic.claude-sonnet-5-5",
    "anthropic.claude-haiku-5-5",
    "anthropic.claude-opus-5-5",
    "anthropic.claude-fable-5-1",
]


def who_am_i(region: str) -> str:
    try:
        import boto3

        profile = os.environ.get("LAV_AWS_PROFILE") or os.environ.get("AWS_PROFILE")
        session = boto3.Session(profile_name=profile, region_name=region)
        return session.client("sts").get_caller_identity()["Arn"]
    except Exception as e:  # noqa: BLE001 - report anything, this is a diagnostic
        return f"unknown ({type(e).__name__}: {str(e)[:120]})"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--region", default=DEFAULT_REGION)
    ap.add_argument("--models", nargs="+", default=CANDIDATES)
    args = ap.parse_args(argv)

    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    print(f"AWS identity: {who_am_i(args.region)}")
    print(f"Region:       {args.region}\n")
    client = make_client("bedrock", args.region)
    ok = []
    for model in args.models:
        try:
            r = client.messages.create(
                model=model, max_tokens=5,
                messages=[{"role": "user", "content": "Reply with the word ok."}],
            )
            print(f"  OK       {model}")
            ok.append(model)
        except Exception as e:  # noqa: BLE001
            msg = str(e).replace("\n", " ")[:160]
            print(f"  NO       {model}  ({type(e).__name__}: {msg})")
    print()
    if ok:
        print(f"Use one with: LAV_MODEL={ok[0]}  (in .env, or --model on the command line)")
        return 0
    print("No model worked. Check: credentials (`aws sts get-caller-identity`), the region,\n"
          "and model access in the Bedrock console (Model access page).")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
