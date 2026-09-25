# Datasets

This folder holds two things: the data exactly as it was collected, and the cleaned dataset used for the
analysis.

| File | Rows | What it is |
| --- | --- | --- |
| `raw/youtube_api.csv` | 22,442 | **Main collection.** Up to 150 recent uploads for each channel in the sampling frame, as returned by the YouTube Data API. Never edited by the analysis. |
| `raw/youtube_api_deep.csv` | 365 | **Second pass.** Older long-form videos for 21 channels whose recent uploads were almost all Shorts. Same columns, plus `defaultAudioLanguage` and `collectedAt`. |
| `raw/video_language.csv` | 22,442 | **Third pass.** The audio language each creator declared for each video. Joins to the files above on `id`. |
| `processed/videos_clean.csv` | 11,877 | **The final cleaned dataset used for the analysis.** 39 columns: identifiers, the 20 predictors, helper columns for the charts, and the target. |
| `channel_list.csv` | 150 | The sampling frame: which channels were collected, their niche, and whether each was hand-picked or found through the API search. |

Collected in total: 22,442 + 365 = **22,807 videos** from 150 channels across 10 niches.

## Why the collected data is in three files

Collection ran in three passes, and each file is kept as its own record rather than merged, so the process
stays auditable:

1. `youtube_api.csv` is the main pass over every channel.
2. `youtube_api_deep.csv` was needed because some channels post mostly Shorts, and the study analyses
   long-form videos. This pass went further back through those channels' uploads.
3. `video_language.csv` was a separate pass, because the language field is not returned by the same call.

The notebook reads all three, joins them on the video `id`, and writes the single cleaned file in
`processed/`. The full collection method is described in Section 2 of `../Case_Study_Report.pdf`.

## Privacy

Only public channel and video information was collected. No viewer data or comment text is included. Email
addresses and phone numbers that some creators put in their video descriptions were replaced with asterisks
by `../scripts/anonymize_raw.py` before submission.

## Field descriptions

Every column of the collected data is described in Section 2 of
`../Case_Study_Report.pdf`. The columns created during cleaning are described in Section 3.2 of the same
report and in the data dictionary printed in `../analysis.ipynb` (Section 5).
