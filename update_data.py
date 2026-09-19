#!/usr/bin/env python3
"""
Refreshes data.json for the G10 macro dashboard using the Claude API with
web search enabled. Run manually (`python scripts/update_data.py`) or via
the daily GitHub Actions workflow in .github/workflows/update-dashboard.yml.

Requires:
    pip install -r requirements.txt
    export ANTHROPIC_API_KEY=sk-ant-...
"""

import json
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path

from anthropic import Anthropic

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data.json"
MODEL = "claude-sonnet-5"

REQUIRED_TOP_KEYS = {
    "meta", "market", "gates", "components", "currencies",
    "order", "macro", "week", "later",
}
REQUIRED_ORDER = ["USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD", "NOK", "SEK"]


def build_prompt(current_data: dict, today: str) -> str:
    schema_example = json.dumps(current_data, indent=2)[:6000]
    return f"""You maintain a G10 FX macro dashboard. Today's date is {today}.

Use web search to refresh every field below with today's real, current data.
Do not invent numbers. If you cannot verify something after searching,
keep the string "update" (or "update: <what's missing>") in that field
exactly like the current file already does in places.

STEPS
1. Search for current: VIX, S&P 500, US dollar index (DXY), US 10-year
   Treasury yield, WTI crude, Brent crude, gold, copper. Note any major
   geopolitical development affecting risk sentiment or energy.
2. For each of USD, EUR, GBP, JPY, CHF, CAD, AUD, NZD, NOK, SEK, check:
   central bank policy rate and stance, date and size of the last rate
   change, next scheduled meeting date, latest CPI print and surprise
   vs expectations, latest jobs data and surprise, latest GDP print,
   and any relevant fiscal/trade/intervention news.
3. Get the newest CFTC Traders in Financial Futures report (leveraged
   funds and asset managers, net position and weekly change) for the
   currencies that trade CME futures (typically EUR, GBP, JPY, CHF,
   CAD, AUD, NZD; USD/NOK/SEK usually have no CFTC line, in which case
   keep "cot": null).
4. Re-score the nine rating components (cb, rate, cpi, jobs, gdp,
   energy, risk, cot, other) from -2 to +2 in 0.5 steps for each
   currency, using the same rubric implied by the current data (central
   bank hawkishness, rate level vs G10 average, inflation vs target and
   surprise, jobs strength and surprise, growth trend, energy/commodity
   exposure given current oil/gas prices, fit with the current
   risk-on/risk-off regime, positioning extremity and direction, and
   fiscal/trade/intervention factors). Write a fresh 2-4 sentence "why"
   for each currency explaining what changed or what's still driving it.
5. Update the "week" (the 5 trading days starting from the most recent
   Monday on or after today) and "later" (6-8 notable dates after that)
   calendars with real scheduled events for those currencies.
6. Update market gates: risk-on/off tone and text, whether a geopolitical
   shock gate applies, and the "thin session" note (market holidays,
   quarterly expiries, etc. for the relevant days).

OUTPUT FORMAT — CRITICAL
Return ONLY a single JSON object, no markdown fences, no commentary
before or after. It MUST have exactly this shape (types, keys, and
nesting) as the current file, just with refreshed values:

{schema_example}
... (truncated example — keep ALL 10 currencies in "currencies", ALL 10
keys in "macro", and the full "components" list; do not drop entries)

Set meta.asOf to "{today}" and meta.cotDate to the date of the CFTC
report you actually used (CFTC data is reported with a lag, usually
3-5 days behind, and is only released on Fridays for the prior Tuesday).
"""


def extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in model output")
    return json.loads(text[start:end + 1])


def validate(data: dict) -> None:
    missing = REQUIRED_TOP_KEYS - set(data.keys())
    if missing:
        raise ValueError(f"Missing top-level keys: {missing}")
    if sorted(data["order"]) != sorted(REQUIRED_ORDER):
        raise ValueError(f"order must contain exactly {REQUIRED_ORDER}, got {data['order']}")
    cur_codes = {c["c"] for c in data["currencies"]}
    if cur_codes != set(REQUIRED_ORDER):
        raise ValueError(f"currencies must cover exactly {REQUIRED_ORDER}, got {sorted(cur_codes)}")
    if set(data["macro"].keys()) != set(REQUIRED_ORDER):
        raise ValueError(f"macro must cover exactly {REQUIRED_ORDER}, got {sorted(data['macro'].keys())}")
    for c in data["currencies"]:
        if "v" not in c or "why" not in c:
            raise ValueError(f"currency {c.get('c')} missing 'v' or 'why'")
    try:
        datetime.strptime(data["meta"]["asOf"], "%Y-%m-%d")
    except Exception as e:
        raise ValueError(f"meta.asOf is not a valid YYYY-MM-DD date: {e}")


def main() -> int:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY is not set.", file=sys.stderr)
        return 1

    if not DATA_PATH.exists():
        print(f"ERROR: {DATA_PATH} not found.", file=sys.stderr)
        return 1

    current_data = json.loads(DATA_PATH.read_text())
    today = date.today().isoformat()

    client = Anthropic(api_key=api_key)
    prompt = build_prompt(current_data, today)

    print(f"Calling {MODEL} with web search to refresh data for {today}...")
    response = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 25}],
        messages=[{"role": "user", "content": prompt}],
    )

    text_parts = [block.text for block in response.content if getattr(block, "type", None) == "text"]
    full_text = "\n".join(text_parts)
    if not full_text.strip():
        print("ERROR: model returned no text content.", file=sys.stderr)
        return 1

    try:
        new_data = extract_json(full_text)
        validate(new_data)
    except Exception as e:
        print(f"ERROR: model output failed validation, keeping old data.json: {e}", file=sys.stderr)
        debug_path = ROOT / "scripts" / "last_failed_output.txt"
        debug_path.write_text(full_text)
        print(f"Raw output saved to {debug_path} for inspection.", file=sys.stderr)
        return 1

    DATA_PATH.write_text(json.dumps(new_data, indent=2) + "\n")
    print(f"data.json updated successfully. asOf={new_data['meta']['asOf']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
