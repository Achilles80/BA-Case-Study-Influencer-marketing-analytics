"""Collect YouTube video data via the official Data API v3.

Replaces the Apify actor, which caps Free Plan accounts at 10 items per run.

Quota: 1 unit per channels/playlistItems/videos request, so roughly 7 units
per channel at 150 videos. The free daily allowance is 10,000 units.
search.list is the exception at 100 units - see discover_channels.py.

Usage:
    python scripts/collect_youtube.py                  # 46 videos/channel
    python scripts/collect_youtube.py --videos 150
    python scripts/collect_youtube.py --limit 3        # try 3 channels first
"""
import argparse
import csv
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CHANNELS = ROOT / "data" / "channel_list.csv"
OUT = ROOT / "data" / "raw" / "youtube_api.csv"
LOG = ROOT / "scrape_log.csv"
API = "https://www.googleapis.com/youtube/v3"

COLUMNS = ["id", "title", "description", "duration", "views", "likes", "comments",
           "publishDate", "category", "keywords", "channelName", "channelHandle",
           "channelId", "subscriberCount", "channelVideoCount", "madeForKids",
           "niche", "type", "url"]

ISO_DUR = re.compile(r"P(?:(\d+)D)?T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")


def load_key():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    key = os.environ.get("YOUTUBE_API_KEY")
    if not key or "XXXX" in key:
        sys.exit("YOUTUBE_API_KEY missing. Put it in .env - see .env.example")
    return key


class Quota:
    used = 0


class ApiError(Exception):
    """A per-channel failure. Skip that channel, keep the run going."""


def get(endpoint, key, cost=1, **params):
    """GET one API endpoint. `cost` is its quota price - 1 for most, 100 for search."""
    params["key"] = key
    last = ""
    for attempt in range(4):
        r = requests.get(f"{API}/{endpoint}", params=params, timeout=30)
        Quota.used += cost
        if r.status_code == 200:
            return r.json()
        last = r.text[:200]
        if r.status_code in (403, 429):
            if "quotaExceeded" in last:
                sys.exit(f"\nDAILY QUOTA EXHAUSTED after {Quota.used} units. "
                         f"Resets at midnight Pacific. Re-run to continue - "
                         f"already-collected channels are skipped.")
            # Key disabled, API not enabled, referrer blocked - affects every
            # channel, so there is no point continuing.
            sys.exit(f"\nAPI refused the request ({r.status_code}): {last}")
        if r.status_code == 404:
            break
        time.sleep(2 ** attempt)
    raise ApiError(f"{endpoint} failed: {last}")


def log_run(batch, channels, rows, notes=""):
    """Append one line to scrape_log.csv - the collection evidence for the report."""
    with open(LOG, "a", encoding="utf-8", newline="") as f:
        csv.writer(f).writerow([datetime.now(timezone.utc).date(), "youtube-data-api-v3",
                                batch, channels, rows, f"{Quota.used} units", notes])


def dur_seconds(iso):
    m = ISO_DUR.match(iso or "")
    if not m:
        return None
    d, h, mi, s = (int(x) if x else 0 for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def category_map(key):
    j = get("videoCategories", key, part="snippet", regionCode="US")
    return {it["id"]: it["snippet"]["title"] for it in j.get("items", [])}


def resolve_channel(handle, key):
    """handle -> (channelId, name, subs, videoCount, uploadsPlaylistId)"""
    j = get("channels", key, part="snippet,statistics,contentDetails",
            forHandle=handle)
    items = j.get("items") or []
    if not items:
        return None
    c = items[0]
    return (c["id"], c["snippet"]["title"],
            int(c["statistics"].get("subscriberCount", 0)),
            int(c["statistics"].get("videoCount", 0)),
            c["contentDetails"]["relatedPlaylists"]["uploads"])


def video_ids(playlist, want, key):
    ids, token = [], None
    while len(ids) < want:
        j = get("playlistItems", key, part="contentDetails", playlistId=playlist,
                maxResults=min(50, want - len(ids)), pageToken=token)
        ids += [it["contentDetails"]["videoId"] for it in j.get("items", [])]
        token = j.get("nextPageToken")
        if not token:
            break
    return ids[:want]


def video_rows(ids, key, cats, meta, niche):
    cid, cname, subs, vcount, _ = meta
    rows = []
    for i in range(0, len(ids), 50):
        j = get("videos", key, part="snippet,statistics,contentDetails,status",
                id=",".join(ids[i:i + 50]))
        for v in j.get("items", []):
            st, sn = v.get("statistics", {}), v["snippet"]
            rows.append({
                "id": v["id"],
                "title": sn.get("title"),
                "description": sn.get("description"),
                "duration": dur_seconds(v.get("contentDetails", {}).get("duration")),
                "views": st.get("viewCount"),
                "likes": st.get("likeCount"),
                "comments": st.get("commentCount"),
                "publishDate": sn.get("publishedAt"),
                "category": cats.get(sn.get("categoryId"), ""),
                "keywords": "|".join(sn.get("tags", []) or []),
                "channelName": cname,
                "channelHandle": None,  # filled by caller
                "channelId": cid,
                "subscriberCount": subs,
                "channelVideoCount": vcount,
                "madeForKids": v.get("status", {}).get("madeForKids"),
                "niche": niche,
                "type": "video",
                "url": f"https://www.youtube.com/watch?v={v['id']}",
            })
    return rows


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--videos", type=int, default=46, help="videos per channel")
    p.add_argument("--limit", type=int, help="only process first N channels")
    a = p.parse_args()

    key = load_key()
    with open(CHANNELS, encoding="utf-8-sig", newline="") as f:
        channels = [r for r in csv.DictReader(f) if r.get("channel_handle", "").strip()]
    if a.limit:
        channels = channels[:a.limit]

    done, seen_ids = set(), set()
    if OUT.exists():
        with open(OUT, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                done.add(r["channelHandle"])
                seen_ids.add(r["id"])
        print(f"resuming - {len(done)} channels, {len(seen_ids)} videos already collected")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    new = not OUT.exists()
    out_f = open(OUT, "a", encoding="utf-8", newline="")
    w = csv.DictWriter(out_f, fieldnames=COLUMNS)
    if new:
        w.writeheader()

    cats = category_map(key)
    total, collected, failed = 0, 0, []
    for n, row in enumerate(channels, 1):
        handle = row["channel_handle"].strip()
        if handle in done:
            continue
        try:
            meta = resolve_channel(handle, key)
            if meta is None:
                failed.append((handle, "handle not found"))
                print(f"[{n}/{len(channels)}] {handle:28} NOT FOUND - skipped")
                continue
            ids = [i for i in video_ids(meta[4], a.videos, key) if i not in seen_ids]
            rows = video_rows(ids, key, cats, meta, row.get("niche", ""))
        except ApiError as e:
            failed.append((handle, str(e)[:80]))
            print(f"[{n}/{len(channels)}] {handle:28} ERROR - skipped ({e})"[:120])
            continue
        for r in rows:
            r["channelHandle"] = handle
            w.writerow(r)
            seen_ids.add(r["id"])
        out_f.flush()
        total += len(rows)
        collected += 1
        print(f"[{n}/{len(channels)}] {handle:28} {len(rows):3d} videos  "
              f"subs {meta[2]:>11,}  total {total:,}  quota {Quota.used}")

    out_f.close()
    if collected or failed:
        log_run("api", collected, total, f"{len(failed)} skipped" if failed else "")

    print(f"\ncollected {total:,} videos from {collected} channels -> {OUT.relative_to(ROOT)}")
    print(f"quota used {Quota.used} of 10,000 daily units")
    if failed:
        print(f"\n{len(failed)} channels skipped (fix or drop in channel_list.csv):")
        for h, why in failed:
            print(f"   {h:28} {why}")


if __name__ == "__main__":
    main()
