import sys
from pathlib import Path

# Add project root to path so we can import from app
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from app.sentiment_analyzer import llm_aspect_sentiment, nli_aspect_sentiment
from app.config import DEFAULT_ASPECTS

df = pd.read_csv('data/gold_dataset_aspect_level - gold_dataset_aspect_level.csv')

def results_to_dict(results_list: list) -> dict:
    return {r["aspect"]: r["sentiment"] for r in results_list}

grouped = df.groupby('review_id')
total = len(grouped)

for i, (review_id, group) in enumerate(grouped):
    print(f"[{i}/{total}] Processing review {review_id}...")
    review_text = group.iloc[0]['review']
    aspects = DEFAULT_ASPECTS

    # save every 10 reviews
    if i % 10 == 0:
        df.to_csv("predictions.csv", index=False)
        print(f"Saved predictions for {i} reviews...")

    try:
        llm_results = results_to_dict(llm_aspect_sentiment(review_text, aspects))
    except Exception as e:
        print(f"Error in LLM inference for review {review_id}: {e}")
        llm_results = {aspect: "error" for aspect in aspects}

    try:
        nli_results = results_to_dict(nli_aspect_sentiment(review_text, aspects))
    except Exception as e:
        print(f"Error in NLI inference for review {review_id}: {e}")
        nli_results = {aspect: "error" for aspect in aspects}

    for idx in group.index:
        aspect = df.loc[idx, "aspect"]
        df.loc[idx, "llm_sentiment"] = llm_results[aspect]
        df.loc[idx, "nli_sentiment"] = nli_results[aspect]

df.to_csv("predictions.csv", index=False)
