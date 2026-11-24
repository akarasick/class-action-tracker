import json
from datetime import datetime, timezone
from pathlib import Path

FEED_PATH = Path("data/claims_feed.json")


def fetch_new_claims() -> list[dict]:
    """Replace or extend this with your existing scheduled task's source logic."""
    return []


def main() -> None:
    if FEED_PATH.exists():
        payload = json.loads(FEED_PATH.read_text(encoding="utf-8"))
    else:
        payload = {"last_updated": "", "claims": []}

    existing_claims = payload.get("claims", [])
    by_id = {c["id"]: c for c in existing_claims if "id" in c}
    now_iso = datetime.now(timezone.utc).isoformat()

    for item in fetch_new_claims():
        claim_id = item.get("id")
        if not claim_id:
            continue
        if claim_id not in by_id:
            item.setdefault("first_seen_at", now_iso)
            by_id[claim_id] = item
        else:
            by_id[claim_id].update({k: v for k, v in item.items() if v is not None})

    payload["last_updated"] = now_iso
    payload["claims"] = list(by_id.values())
    FEED_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
