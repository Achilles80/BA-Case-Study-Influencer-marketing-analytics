"""Mask email addresses and phone numbers in the raw data files.

Each match is replaced with asterisks of the same length, so the text features
used in the notebook stay the same.

Usage:
    python scripts/anonymize_raw.py            # dry run
    python scripts/anonymize_raw.py --write    # mask the files in place
"""
import argparse
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ANALYSIS_FILES = [ROOT / "data" / "raw" / "youtube_api.csv", ROOT / "data" / "raw" / "youtube_api_deep.csv"]
ARCHIVE_FILES = [ROOT / "archive" / "apify_attempt" / "data" / "raw" / "pilot_batch_00.csv",
                 ROOT / "archive" / "apify_attempt" / "data" / "raw" / "batch_00_probe.csv"]
SUMMARY = ROOT / "report" / "anonymization_summary.csv"
TEXT_COLUMNS = ["description", "title", "keywords"]

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE = re.compile(r"(?:\+\d{1,3}[\s-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b")
SPONSOR = re.compile(r"\b(?:sponsor(?:ed)?|use (?:my )?code|promo code|discount code|affiliate|paid partnership)\b",
                     re.IGNORECASE)
EMOJI = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF]")
csv.field_size_limit(10 ** 9)


def mask(text):
    text = EMAIL.sub(lambda m: "*" * len(m.group(0)), text)
    return PHONE.sub(lambda m: "*" * len(m.group(0)), text)


def features(column, text):
    """Text features computed in the notebook."""
    if column == "description":
        return (len(text), len(re.findall(r"https?://", text)), bool(re.search(r"#\w+", text)),
                bool(SPONSOR.search(text)))
    if column == "title":
        return (len(text), bool(re.search(r"\d", text)), "?" in text, "!" in text,
                sum(w.isupper() for w in re.findall(r"[A-Za-z]{2,}", text)), len(EMOJI.findall(text)))
    return (len(text.split("|")) if text else 0,)


def process(path, columns, check):
    raw = path.read_bytes()
    encoding = "utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8"
    quote_all = raw.lstrip(b"\xef\xbb\xbf").startswith(b'"')
    with open(path, encoding=encoding, newline="") as f:
        rows = list(csv.reader(f))
    header, body = rows[0], rows[1:]
    targets = [i for i, h in enumerate(header) if columns is None or h in columns]
    cells = rows_hit = 0
    for row in body:
        hit = False
        for i in targets:
            if i >= len(row) or not row[i]:
                continue
            new = mask(row[i])
            if new == row[i]:
                continue
            if check and features(header[i], row[i]) != features(header[i], new):
                sys.exit(f"refusing: masking would change a model feature in {path.name}, column {header[i]}")
            row[i] = new
            cells += 1
            hit = True
        rows_hit += hit
    return encoding, quote_all, header, body, cells, rows_hit


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--write", action="store_true")
    a = p.parse_args()

    summary = []
    for path, scope, columns, check in ([(f, "analysis", TEXT_COLUMNS, True) for f in ANALYSIS_FILES]
                                        + [(f, "archive", None, False) for f in ARCHIVE_FILES]):
        if not path.exists():
            print(f"skip (missing): {path.relative_to(ROOT)}")
            continue
        encoding, quote_all, header, body, cells, rows_hit = process(path, columns, check)
        print(f"{path.relative_to(ROOT)}: {cells:,} cells in {rows_hit:,} rows to mask")
        summary.append({"file": path.relative_to(ROOT).as_posix(), "scope": scope,
                        "cells_masked": cells, "rows_masked": rows_hit})
        if a.write and cells:
            with open(path, "w", encoding=encoding, newline="") as f:
                w = csv.writer(f, quoting=csv.QUOTE_ALL if quote_all else csv.QUOTE_MINIMAL)
                w.writerow(header)
                w.writerows(body)

    if a.write:
        if sum(s["cells_masked"] for s in summary) == 0:
            print("nothing left to mask - summary left unchanged")
            return
        with open(SUMMARY, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["file", "scope", "cells_masked", "rows_masked"])
            w.writeheader()
            w.writerows(summary)
        print(f"written {SUMMARY.relative_to(ROOT)}")
    else:
        print("dry run - nothing written (use --write)")


if __name__ == "__main__":
    main()
