# Influencer Marketing Analytics: Predicting High-Engagement YouTube Campaigns for Marketing Investment Optimization

23CSE452 - Business Analytics | Individual Case Study

Adithya Ajay | Roll No: CB.SC.U4CSE23102 | CSE-B

Business domain: Social Media Marketing

## Problem Statement

Businesses increasingly invest substantial marketing budgets in YouTube influencer campaigns, yet predicting
campaign success before investing remains a significant challenge. Organizations often choose influencers based
on subscriber count or popularity, overlooking content characteristics and historical engagement patterns that
better indicate campaign effectiveness.

This study analyses YouTube video and channel data that I collected myself, to identify the factors that
influence audience engagement and to build a model that estimates whether a video is likely to achieve high
engagement before the investment decision is made.

## Objectives

1. To identify the channel, content and timing factors that influence audience engagement on YouTube, using
   only information that is available before investing.
2. To develop a classification model that predicts whether a video is likely to achieve high engagement, and
   to compare it with the common practice of selecting influencers by subscriber count.
3. To use the results to support influencer selection and marketing budget allocation, and to give practical
   recommendations for campaign planning.

## Data Collection

- **Source:** public YouTube channel and video data, collected through the official
  [YouTube Data API v3](https://developers.google.com/youtube/v3/docs). No ready-made dataset (Kaggle, UCI,
  GitHub or similar) was used.
- **Change from the proposal:** the proposal planned to use the Apify actor apidojo/youtube-scraper. On the free
  plan it returned only 10 records per run, so collection moved to the official API.
- **Procedure:** for each channel, [scripts/collect_youtube.py](scripts/collect_youtube.py) calls `channels.list`
  (subscriber count and uploads playlist), `playlistItems.list` (the 150 most recent uploads) and `videos.list`
  (statistics and details, in batches of 50).
- **Channels:** 150 channels in 10 niches. 90 were chosen by hand and 60 were found through the API search to
  cover smaller channels (under 200K and 200K–1M subscribers).
- **Size:** 22,807 video records collected; 11,877 long-form videos from 143 channels after cleaning.
- **Privacy:** only public channel and video information was collected. Email addresses and phone numbers that
  some creators post in their descriptions were masked with
  [scripts/anonymize_raw.py](scripts/anonymize_raw.py) before submission.

## Analytics Methods

- **Target:** engagement rate = (likes + comments) / views. A video is "high engagement" if it is in the top
  30% (engagement rate of 4.52% or more).
- **Classification:** logistic regression and random forest, both with balanced class weights, plus a
  logistic regression that uses subscriber count only, as a baseline for how brands choose influencers today.
- **Evaluation:** stratified 80/20 train–test split (random_state = 42), 5-fold cross-validation for tuning,
  and a second cross-validation grouped by channel to test the models on creators they have never seen.
  Metrics: accuracy, precision, recall, F1-score and ROC-AUC.
- **Avoiding leakage:** views, likes and comments are not used as predictors, and the channel's past
  engagement is calculated only from videos published before the one being predicted.

## Key Results

| Model | Test ROC-AUC | Precision | Recall | ROC-AUC on unseen channels |
| --- | --- | --- | --- | --- |
| Subscriber count only | 0.569 | 0.332 | 0.453 | 0.554 |
| Logistic regression | 0.897 | 0.647 | 0.842 | 0.885 |
| Random forest | 0.919 | 0.719 | 0.808 | 0.879 |

- Subscriber count on its own is a poor predictor of engagement (ROC-AUC 0.569), and channels with more than
  5 million subscribers have the lowest share of high-engagement videos (17%, against 42% for 1–5 million).
- The creator's past engagement is by far the most important predictor. Without it, the random forest's
  ROC-AUC on unseen channels drops from 0.879 to 0.635.
- 72% of the videos the random forest selects are high engagement, compared with a 30% base rate.
- Engagement also depends on niche (60% high engagement in fashion against 13% in fitness), and 8–15 minute
  videos perform best.

## Repository Structure

| Path | Contents |
| --- | --- |
| [Case_Study_Report.pdf](Case_Study_Report.pdf) | Final case study report |
| [analysis.ipynb](analysis.ipynb) | Preprocessing, visualisation, modelling, evaluation and outputs |
| `data/raw/` | Collected data: `youtube_api.csv`, `youtube_api_deep.csv`, `video_language.csv` |
| `data/processed/` | `videos_clean.csv`, the cleaned dataset used in the analysis |
| `data/channel_list.csv` | The list of channels that were collected |
| `scripts/` | Data collection and anonymisation scripts |

## How to Run

1. Install the packages: `pip install pandas numpy scikit-learn matplotlib jupyterlab requests`
2. Open `analysis.ipynb` and run all cells (about 3 minutes). It only needs the files already in `data/`.
3. Collecting the data again is optional and needs a YouTube Data API key, set as `YOUTUBE_API_KEY` in a `.env` file.
   The API returns current statistics, so a new collection will not match this snapshot exactly.

## References

1. Nisa, M. U., Mahmood, D., Ahmed, G., Khan, S., Mohammed, M. A., & Damaševičius, R. (2021). Optimizing
   prediction of YouTube video popularity using XGBoost. *Electronics, 10*(23), 2962.
   https://doi.org/10.3390/electronics10232962
2. Ziyada, M., & Shamoi, P. (2024). Video popularity in social media: Impact of emotions, raw features and viewer
   comments. In *2024 Joint 13th International Conference on Soft Computing and Intelligent Systems and 25th
   International Symposium on Advanced Intelligent Systems (SCIS&ISIS)* (pp. 1–7). IEEE.
   https://doi.org/10.1109/SCISISIS61014.2024.10759978
3. Sourya, J. S., Kankaria, V. N., & Angayarkanni, S. A. (2025). Predicting the success of influencer marketing
   campaigns using machine learning. In *Proceedings of Data Analytics and Management (ICDAM 2024)*, Lecture
   Notes in Networks and Systems. Springer Nature Singapore. https://doi.org/10.1007/978-981-96-3361-6_39
4. Chang, S.-C., & Chien, Y.-T. (2025). Predicting YouTube video popularity using machine learning: A
   comprehensive analysis of engagement metrics. In *2025 IEEE Gaming, Entertainment, and Media Conference
   (GEM)*. IEEE. https://doi.org/10.1109/GEM66882.2025.11155646
5. Gui, H., Bertaglia, T., Goanta, C., & Spanakis, G. (2025). Computational studies in influencer marketing: A
   systematic literature review. *arXiv preprint* arXiv:2506.14602. https://arxiv.org/abs/2506.14602
6. Google Developers. *YouTube Data API v3 reference*. https://developers.google.com/youtube/v3/docs
7. Pedregosa, F., et al. (2011). Scikit-learn: Machine learning in Python. *Journal of Machine Learning
   Research, 12*, 2825–2830.
8. Apify. *Youtube Scraper (Pay Per Result)* [apidojo/youtube-scraper]. https://apify.com/apidojo/youtube-scraper
