"""
Verify the Gemini API key and find a model it can actually use.

Run once after adding GEMINI_API_KEY to .env:

    python check_gemini.py

The list endpoint reports models a project cannot call — older ones return
404 "no longer available to new users" — so this tries candidates in order,
newest stable Flash first, until one answers, then prints the GEMINI_MODEL
line to paste into .env.
"""

import os
import re
import sys

import requests
from dotenv import load_dotenv

load_dotenv()

API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
def _clean(raw: str) -> str:
    """Strip whitespace and wrappers people paste in by accident: <>, "", ''."""
    value = (raw or "").strip()
    for opening, closing in (("<", ">"), ('"', '"'), ("'", "'")):
        if value.startswith(opening) and value.endswith(closing):
            value = value[1:-1].strip()
    return value


KEY = _clean(os.getenv("GEMINI_API_KEY", ""))

# Model families that don't fit this app's two jobs (describe an image,
# summarise notes), so they're never offered as the default.
SKIP = ("embedding", "aqa", "tts", "image", "lyria", "veo", "robotics",
        "computer-use", "deep-research", "gemma", "omni", "antigravity", "nano-banana")


def _version_of(name: str) -> float:
    match = re.search(r"(\d+(?:\.\d+)?)", name)
    return float(match.group(1)) if match else 0.0


def _rank(name: str):
    """Stable Flash first, then preview Flash, then Lite, then Pro. Newest wins."""
    is_preview = "preview" in name
    if "flash" in name and not is_preview and "lite" not in name:
        tier = 0
    elif "flash" in name and "lite" not in name:
        tier = 1
    elif "flash" in name:
        tier = 2
    else:
        tier = 3
    return (tier, -_version_of(name))


def main() -> int:
    if not KEY:
        print("GEMINI_API_KEY is not set in Backend/.env")
        return 1
    print(f"Key found: {KEY[:8]}...{KEY[-4:]}  (length {len(KEY)})\n")

    # Two key formats are in circulation and both are valid: the legacy
    # 'AIza...' (39 chars) and the newer 'AQ....' that AI Studio now issues.
    # Warn on anything else rather than blocking — let the API decide.
    if not (KEY.startswith("AIza") or KEY.startswith("AQ.")):
        print("Note: this matches neither known Gemini key format "
              "('AIza...' or 'AQ....'). Trying it anyway.\n")

    try:
        response = requests.get(API_BASE, params={"key": KEY}, timeout=30)
    except requests.RequestException as exc:
        print(f"Could not reach Google: {type(exc).__name__}")
        return 1

    if response.status_code != 200:
        print(f"HTTP {response.status_code} listing models\n{response.text[:400]}")
        if response.status_code in (400, 403):
            print("\n-> Key is invalid or restricted, or the Generative Language API "
                  "is not enabled on its project.")
        return 1

    names = [
        m["name"].replace("models/", "")
        for m in response.json().get("models", [])
        if "generateContent" in m.get("supportedGenerationMethods", [])
    ]
    candidates = sorted(
        (n for n in names if not any(s in n for s in SKIP)), key=_rank
    )
    if not candidates:
        print("No suitable text/vision models available to this key.")
        return 1

    print(f"{len(names)} model(s) listed; testing the {min(6, len(candidates))} best fits.\n")

    chosen = None
    for name in candidates[:6]:
        try:
            test = requests.post(
                f"{API_BASE}/{name}:generateContent",
                params={"key": KEY},
                json={"contents": [{"role": "user",
                                    "parts": [{"text": "Reply with the single word OK."}]}]},
                timeout=45,
            )
        except requests.RequestException as exc:
            print(f"  {name:<30} request failed ({type(exc).__name__})")
            continue

        if test.status_code == 200:
            print(f"  {name:<30} WORKS")
            if chosen is None:
                chosen = name
            continue

        detail = ""
        try:
            detail = test.json().get("error", {}).get("message", "")[:70]
        except ValueError:
            pass
        note = "  (rate limited — real model, quota exhausted)" if test.status_code == 429 else ""
        print(f"  {name:<30} HTTP {test.status_code} {detail}{note}")

    if not chosen:
        print("\nNo model responded successfully — see the errors above.")
        return 1

    print("\n" + "=" * 64)
    print("Key works. Add this line to Backend/.env:\n")
    print(f"    GEMINI_MODEL={chosen}")
    print("\nThen restart the backend.")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    sys.exit(main())
