"""Check each channel before finalising the dataset.

Flags:
  NON_ENGLISH  mostly non-English videos
  SHORTS_ONLY  over 80% of videos are 180 s or shorter
  FEW_VIDEOS   fewer than 50 videos
  CATEGORY?    main YouTube category does not fit the niche

Usage:
    python scripts/audit_channels.py
"""
import unicodedata
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "youtube_api.csv"
LANG = ROOT / "data" / "raw" / "video_language.csv"
CHANNELS = ROOT / "data" / "channel_list.csv"
OUT = ROOT / "report" / "channel_audit.csv"

PLAUSIBLE = {
    "tech": {"Science & Technology", "Howto & Style", "Education", "People & Blogs"},
    "gaming": {"Gaming", "Entertainment"},
    "beauty": {"Howto & Style", "People & Blogs", "Entertainment"},
    "fitness": {"Sports", "Howto & Style", "People & Blogs", "Education"},
    "food": {"Howto & Style", "People & Blogs", "Entertainment", "Travel & Events"},
    "finance": {"Education", "People & Blogs", "News & Politics", "Entertainment"},
    "travel": {"Travel & Events", "People & Blogs", "Entertainment"},
    "education": {"Education", "Science & Technology", "Entertainment"},
    "fashion": {"Howto & Style", "People & Blogs", "Entertainment"},
    "lifestyle": {"People & Blogs", "Howto & Style", "Entertainment", "Education"},
}


def non_latin(title):
    letters = [c for c in str(title) if c.isalpha()]
    if not letters:
        return False
    other = sum(not unicodedata.name(c, "").startswith("LATIN") for c in letters)
    return other / len(letters) > 0.5


def tier(s):
    if s < 200_000:
        return "<200K"
    if s < 1_000_000:
        return "200K-1M"
    if s < 5_000_000:
        return "1M-5M"
    return "5M+"


def main():
    df = pd.read_csv(RAW)
    cl = pd.read_csv(CHANNELS)
    df = df[df.channelHandle.isin(cl.channel_handle)].merge(
        cl[["channel_handle", "source"]], left_on="channelHandle", right_on="channel_handle")
    if LANG.exists():
        df = df.merge(pd.read_csv(LANG, dtype=str), on="id", how="left")
    else:
        print("video_language.csv not found - language check uses titles only\n")
        df["defaultAudioLanguage"] = pd.NA

    df["is_short"] = df.duration <= 180
    df["non_latin"] = df.title.map(non_latin)
    lang = df.defaultAudioLanguage.fillna("").str.lower()
    df["lang_known"] = lang != ""
    df["lang_en"] = lang.str.startswith("en")

    rows = []
    for h, g in df.groupby("channelHandle"):
        known = g[g.lang_known]
        cats = g.category.value_counts(normalize=True)
        top_lang = known.defaultAudioLanguage.str.lower().value_counts()
        r = {
            "channel": h, "niche": g.niche.iloc[0], "source": g.source.iloc[0].split(":")[0],
            "subs": int(g.subscriberCount.iloc[0]), "tier": tier(g.subscriberCount.iloc[0]),
            "videos": len(g), "share_short": round(g.is_short.mean(), 2),
            "top_category": cats.index[0] if len(cats) else "",
            "top_lang": top_lang.index[0] if len(top_lang) else "",
            "lang_known": round(g.lang_known.mean(), 2),
            "share_en": round(known.lang_en.mean(), 2) if len(known) else None,
            "share_non_latin_titles": round(g.non_latin.mean(), 2),
        }
        flags = []
        if (r["lang_known"] >= 0.3 and r["share_en"] is not None and r["share_en"] < 0.5) \
                or r["share_non_latin_titles"] > 0.5:
            flags.append("NON_ENGLISH")
        if r["share_short"] > 0.8:
            flags.append("SHORTS_ONLY")
        if r["videos"] < 50:
            flags.append("FEW_VIDEOS")
        if r["top_category"] not in PLAUSIBLE.get(r["niche"], set()):
            flags.append("CATEGORY?")
        r["flags"] = " ".join(flags)
        rows.append(r)

    a = pd.DataFrame(rows).sort_values(["niche", "subs"])
    OUT.parent.mkdir(exist_ok=True)
    a.to_csv(OUT, index=False)

    pd.set_option("display.width", 200)
    flagged = a[a["flags"] != ""]
    print(f"{len(a)} channels audited, {len(flagged)} flagged\n")
    cols = ["channel", "niche", "source", "subs", "videos", "share_short",
            "top_category", "top_lang", "share_en", "share_non_latin_titles", "flags"]
    print(flagged[cols].to_string(index=False))

    hard = a[a["flags"].str.contains("NON_ENGLISH|SHORTS_ONLY|FEW_VIDEOS")]
    keep = a[~a.index.isin(hard.index)]
    print(f"\nif hard flags are dropped: {len(keep)} channels, "
          f"{keep.videos.sum():,} videos")
    print(keep.groupby("tier").agg(channels=("channel", "size"),
                                   videos=("videos", "sum")).to_string())
    print(f"\nwritten {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
