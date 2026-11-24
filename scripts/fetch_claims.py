import csv
import io
import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

FEED_PATH = Path("data/claims_feed.json")

# Optional: set ONE of these if you have a public feed URL.
# Leave both empty ("") to keep existing claims in data/claims_feed.json and update last_updated.
SOURCE_CSV_URL = ""
SOURCE_JSON_URL = ""


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug[:80] or "claim-item"


def fetch_url_text(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "class-action-tracker/1.0",
            "Accept": "application/json, text/csv, */*;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def normalize_claim(raw: dict) -> dict | None:
    title = str(
        raw.get("title")
        or raw.get("settlement")
        or raw.get("settlement_name")
        or raw.get("name")
        or ""
    ).strip()
    if not title:
        return None

    claim_id = str(raw.get("id") or slugify(title)).strip()
    if not claim_id:
        return None

    eligibility = str(
        raw.get("eligibility_summary")
        or raw.get("eligibility")
        or raw.get("summary")
        or raw.get("description")
        or ""
    ).strip()

    deadline = str(
        raw.get("claim_deadline")
        or raw.get("deadline")
        or ""
    ).strip()

    claim_url = str(
        raw.get("claim_url")
        or raw.get("url")
        or raw.get("link")
        or ""
    ).strip()

    return {
        "id": claim_id,
        "title": title,
        "eligibility_summary": eligibility,
        "claim_deadline": deadline,
        "claim_url": claim_url,
    }


def fetch_from_csv(url: str) -> list[dict]:
    raw_text = fetch_url_text(url)
    reader = csv.DictReader(io.StringIO(raw_text))
    claims: list[dict] = []
    for row in reader:
        normalized = normalize_claim(dict(row))
        if normalized:
            claims.append(normalized)
    return claims


def fetch_from_json(url: str) -> list[dict]:
    raw_text = fetch_url_text(url)
    data = json.loads(raw_text)
    if isinstance(data, dict):
        items = data.get("claims") or data.get("settlements") or data.get("items") or []
    elif isinstance(data, list):
        items = data
    else:
        items = []

    claims: list[dict] = []
    for item in items:
        if isinstance(item, dict):
            normalized = normalize_claim(item)
            if normalized:
                claims.append(normalized)
    return claims


def fetch_new_claims() -> list[dict]:
    """Pull claims from a configured CSV or JSON feed, or return [] if none configured."""
    collected: list[dict] = []

    if SOURCE_CSV_URL.strip():
        collected.extend(fetch_from_csv(SOURCE_CSV_URL.strip()))

    if SOURCE_JSON_URL.strip():
        collected.extend(fetch_from_json(SOURCE_JSON_URL.strip()))

    return collected


def load_existing_feed(path: Path) -> dict:
    if not path.exists():
        return {"last_updated": "", "claims": []}
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(parsed, dict):
            claims = parsed.get("claims")
            return {
                "last_updated": parsed.get("last_updated", ""),
                "claims": claims if isinstance(claims, list) else [],
            }
    except json.JSONDecodeError:
        pass
    return {"last_updated": "", "claims": []}


def main() -> None:
    payload = load_existing_feed(FEED_PATH)
    by_id: dict[str, dict] = {
        c["id"]: c for c in payload["claims"] if isinstance(c, dict) and c.get("id")
    }
    now_iso = datetime.now(timezone.utc).isoformat()

    try:
        fetched = fetch_new_claims()
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"Warning: feed fetch failed ({exc}). Keeping existing claims.")
        fetched = []

    for item in fetched:
        claim_id = item.get("id")
        if not claim_id:
            continue

        if claim_id not in by_id:
            entry = dict(item)
            entry.setdefault("first_seen_at", now_iso)
            by_id[claim_id] = entry
        else:
            existing = by_id[claim_id]
            existing.setdefault("first_seen_at", now_iso)
            for k, v in item.items():
                if v not in (None, ""):
                    existing[k] = v

    FEED_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload["last_updated"] = now_iso
    payload["claims"] = list(by_id.values())
    FEED_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Updated {FEED_PATH} with {len(payload['claims'])} total claims.")


if __name__ == "__main__":
    main()
