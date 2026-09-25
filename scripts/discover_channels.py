"""Find real small and mid-size channels per niche to balance subscriber tiers.

The seed list in channel_list.csv is 85/91 channels above 1M subscribers, which
makes "does subscriber count predict engagement?" close to untestable. This
script searches recent videos per niche, looks up the channels behind them,
and keeps those in the under-represented tiers.

Selection rules (report these in the methodology):
  - found via search.list on niche keywords, videos published in the last
    180 days, regionCode=US, relevanceLanguage=en
  - subscriber count visible, and within the tier bounds below
  - at least MIN_VIDEOS uploads, so ~150 videos per channel is achievable
  - has an @handle, not already in the list, not an auto-generated "- Topic"
  - taken in search-relevance order until the per-niche quota is filled

Quota: search.list costs 100 units per page, so this is the expensive step.
The script stops searching a niche as soon as its targets are met.

Usage:
    python scripts/discover_channels.py --dry-run     # print, don't write
    python scripts/discover_channels.py
"""
import argparse
import csv
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_youtube import ApiError, Quota, get, load_key  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CHANNELS = ROOT / "data" / "channel_list.csv"

TIERS = {"<200K": (10_000, 200_000), "200K-1M": (200_000, 1_000_000)}
PER_TIER = 3
MIN_VIDEOS = 100

QUERIES = {
    "tech": ["tech review", "smartphone review", "pc build"],
    "gaming": ["gameplay walkthrough", "video game review", "lets play"],
    "beauty": ["makeup tutorial", "skincare routine", "makeup review"],
    "fitness": ["home workout", "gym training tips", "weight loss workout"],
    "food": ["easy recipe", "cooking at home", "baking recipe"],
    "finance": ["personal finance", "investing for beginners", "budgeting tips"],
    "travel": ["travel vlog", "travel guide", "backpacking"],
    "education": ["science explained", "history explained", "math explained"],
    "fashion": ["fashion haul", "mens style tips", "outfit ideas"],
    "lifestyle": ["day in my life", "productivity tips", "minimalism"],
}


def tier_of(subs):
    for name, (lo, hi) in TIERS.items():
        if lo <= subs < hi:
            return name
    return None


def channel_stats(ids, key):
    out = {}
    for i in range(0, len(ids), 50):
        j = get("channels", key, part="snippet,statistics", id=",".join(ids[i:i + 50]))
        for c in j.get("items", []):
            out[c["id"]] = c
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--pages", type=int, default=2, help="max search pages per query")
    a = p.parse_args()
    key = load_key()

    with open(CHANNELS, encoding="utf-8-sig", newline="") as f:
        existing = list(csv.DictReader(f))
    known_handles = {r["channel_handle"].lower() for r in existing}
    after = (datetime.now(timezone.utc) - timedelta(days=180)).strftime("%Y-%m-%dT%H:%M:%SZ")

    found, seen_ids = [], set()
    for niche, queries in QUERIES.items():
        need = {t: PER_TIER for t in TIERS}
        for q in queries:
            token = None
            for _ in range(a.pages):
                if not any(need.values()):
                    break
                try:
                    j = get("search", key, cost=100, part="snippet", type="video", q=q,
                            maxResults=50, regionCode="US", relevanceLanguage="en",
                            publishedAfter=after, pageToken=token)
                except ApiError as e:
                    print(f"  search failed for {q!r}: {e}")
                    break
                # keep relevance order, first appearance only
                order = []
                for it in j.get("items", []):
                    cid = it["snippet"]["channelId"]
                    if cid not in seen_ids and cid not in order:
                        order.append(cid)
                stats = channel_stats(order, key) if order else {}
                for cid in order:
                    seen_ids.add(cid)
                    c = stats.get(cid)
                    if not c:
                        continue
                    st, sn = c["statistics"], c["snippet"]
                    handle = sn.get("customUrl", "")
                    if (st.get("hiddenSubscriberCount") or not handle.startswith("@")
                            or handle.lower() in known_handles
                            or sn["title"].endswith("- Topic")
                            or int(st.get("videoCount", 0)) < MIN_VIDEOS):
                        continue
                    subs = int(st.get("subscriberCount", 0))
                    t = tier_of(subs)
                    if t is None or need[t] == 0:
                        continue
                    need[t] -= 1
                    known_handles.add(handle.lower())
                    found.append({"niche": niche, "channel_name": sn["title"],
                                  "channel_handle": handle,
                                  "approx_subscribers": subs,
                                  "source": f"api_search:{q}"})
                    print(f"  {niche:10} {t:8} {handle:32} {subs:>9,}  "
                          f"videos {int(st['videoCount']):>5}  [{q}]")
                token = j.get("nextPageToken")
                if not token:
                    break
            if not any(need.values()):
                break
        short = {t: n for t, n in need.items() if n}
        if short:
            print(f"  {niche:10} still short: {short}")

    print(f"\n{len(found)} channels found, quota used {Quota.used}")
    if a.dry_run or not found:
        return

    for r in existing:
        r.setdefault("source", "seed")
        if not r.get("source"):
            r["source"] = "seed"
    fields = ["niche", "channel_name", "channel_handle", "approx_subscribers", "source"]
    with open(CHANNELS, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(existing + found)
    print(f"appended to {CHANNELS.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
