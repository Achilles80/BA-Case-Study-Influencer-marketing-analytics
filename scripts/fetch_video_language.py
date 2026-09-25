"""Get the audio language of each collected video.

Saved to data/raw/video_language.csv and joined on id in the notebook.

Usage:
    python scripts/fetch_video_language.py
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_youtube import ApiError, Quota, get, load_key  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "raw" / "youtube_api.csv"
OUT = ROOT / "data" / "raw" / "video_language.csv"
FIELDS = ["id", "defaultAudioLanguage", "defaultLanguage"]


def main():
    key = load_key()
    with open(SRC, encoding="utf-8", newline="") as f:
        ids = list(dict.fromkeys(r["id"] for r in csv.DictReader(f)))

    done = set()
    if OUT.exists():
        with open(OUT, encoding="utf-8", newline="") as f:
            done = {r["id"] for r in csv.DictReader(f)}
    todo = [i for i in ids if i not in done]
    print(f"{len(ids):,} videos, {len(done):,} already fetched, {len(todo):,} to go")
    if not todo:
        return

    new = not OUT.exists()
    with open(OUT, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        for i in range(0, len(todo), 50):
            chunk = todo[i:i + 50]
            try:
                j = get("videos", key, part="snippet", id=",".join(chunk),
                        fields="items(id,snippet(defaultAudioLanguage,defaultLanguage))")
            except ApiError as e:
                print(f"  chunk {i // 50} failed, re-run to retry: {e}")
                continue
            got = {it["id"]: it.get("snippet", {}) for it in j.get("items", [])}
            # save every id, including deleted ones, so a re-run skips them
            for vid in chunk:
                sn = got.get(vid, {})
                w.writerow({"id": vid,
                            "defaultAudioLanguage": sn.get("defaultAudioLanguage", ""),
                            "defaultLanguage": sn.get("defaultLanguage", "")})
            f.flush()
    print(f"done -> {OUT.relative_to(ROOT)}  ({Quota.used} units)")


if __name__ == "__main__":
    main()
