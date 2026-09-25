"""Collect older long-form videos for channels whose recent uploads are mostly Shorts.

Saved to data/raw/youtube_api_deep.csv so the main file is not changed.

Usage:
    python scripts/deepen_long_form.py --dry-run   # list channels, no API calls
    python scripts/deepen_long_form.py
"""
import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_youtube import (COLUMNS, ApiError, Quota, category_map, get,  # noqa: E402
                             load_key, log_run, resolve_channel, video_rows)

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "youtube_api.csv"
OUT = ROOT / "data" / "raw" / "youtube_api_deep.csv"
CHANNELS = ROOT / "data" / "channel_list.csv"

TARGET_LONG = 40      # raw long-form videos wanted per channel, before cleaning
MAX_UPLOADS = 600     # how far back to page before giving up
SHORT_MAX = 180       # seconds; <= this is treated as a Short

# removed later by the language filter, so skip them
NON_ENGLISH = {"@jrstudiomalayalam", "@mrsyumtum", "@parulmahaajan1", "@reshmifit-od3nw"}

FIELDS = COLUMNS + ["defaultAudioLanguage", "collectedAt"]


def languages(ids, key):
    out = {}
    for i in range(0, len(ids), 50):
        j = get("videos", key, part="snippet", id=",".join(ids[i:i + 50]),
                fields="items(id,snippet(defaultAudioLanguage))")
        for it in j.get("items", []):
            out[it["id"]] = it.get("snippet", {}).get("defaultAudioLanguage", "")
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()

    frame = pd.read_csv(CHANNELS)
    raw = pd.read_csv(RAW, usecols=["id", "channelHandle", "duration"])
    seen = set(raw.id)
    have = raw[raw.duration > SHORT_MAX].groupby("channelHandle").size()
    if OUT.exists():
        deep = pd.read_csv(OUT, usecols=["id", "channelHandle"])
        seen |= set(deep.id)
        have = have.add(deep.groupby("channelHandle").size(), fill_value=0)

    todo = [(r.channel_handle, r.niche, int(have.get(r.channel_handle, 0)))
            for r in frame.itertuples()
            if r.channel_handle not in NON_ENGLISH
            and have.get(r.channel_handle, 0) < TARGET_LONG]
    print(f"{len(todo)} channels below {TARGET_LONG} long-form videos:")
    for h, _, n in sorted(todo, key=lambda t: t[2]):
        print(f"   {h:30} {n:3d}")
    if a.dry_run or not todo:
        return

    key = load_key()
    cats = category_map(key)
    new = not OUT.exists()
    today = datetime.now(timezone.utc).date().isoformat()
    total, done = 0, 0
    with open(OUT, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        for handle, niche, count in todo:
            try:
                meta = resolve_channel(handle, key)
                if meta is None:
                    print(f"   {handle:30} not found - skipped")
                    continue
                token, scanned, added = None, 0, 0
                while scanned < MAX_UPLOADS and count < TARGET_LONG:
                    j = get("playlistItems", key, part="contentDetails", playlistId=meta[4],
                            maxResults=50, pageToken=token)
                    ids = [it["contentDetails"]["videoId"] for it in j.get("items", [])]
                    scanned += len(ids)
                    unseen = [i for i in ids if i not in seen]
                    if unseen:
                        rows = video_rows(unseen, key, cats, meta, niche)
                        longs = [r for r in rows if (r["duration"] or 0) > SHORT_MAX]
                        seen.update(r["id"] for r in rows)
                        lang = languages([r["id"] for r in longs], key) if longs else {}
                        for r in longs[:TARGET_LONG - count]:
                            r.update(channelHandle=handle, collectedAt=today,
                                     defaultAudioLanguage=lang.get(r["id"], ""))
                            w.writerow(r)
                            count += 1
                            added += 1
                    token = j.get("nextPageToken")
                    if not token:
                        break
                f.flush()
            except ApiError as e:
                print(f"   {handle:30} ERROR - skipped ({str(e)[:60]})")
                continue
            total += added
            done += 1
            print(f"   {handle:30} +{added:3d} long-form  now {count:3d}  "
                  f"scanned {scanned:3d} uploads  quota {Quota.used}")

    log_run("deep_long_form", done, total,
            f"long-form only; up to {MAX_UPLOADS} uploads back; target {TARGET_LONG}/channel")
    print(f"\nadded {total:,} long-form videos -> {OUT.relative_to(ROOT)}  ({Quota.used} units)")


if __name__ == "__main__":
    main()
