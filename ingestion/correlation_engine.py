# ingestion/correlation_engine.py

import re
from collections import Counter

from config.geo_map import MILITARY_KEYWORDS, REGION_GEO_MAP
from config.tickers import KEYWORD_TICKER_MAP

TITLE_WEIGHT = 3


def _build_corpus(title: str, summary: str) -> str:
    return ((title + " ") * TITLE_WEIGHT + summary).lower()


def classify_region(title: str, summary: str, fallback: str) -> str:
    corpus = _build_corpus(title, summary)
    scores: Counter = Counter()
    for phrase, region in REGION_GEO_MAP.items():
        count = len(re.findall(r"\b" + re.escape(phrase) + r"\b", corpus))
        if count:
            scores[region] += count
    if not scores:
        return fallback
    top = scores.most_common(2)
    if len(top) > 1 and top[0][1] == top[1][1]:
        return fallback  # genuine tie — keep source-feed region
    return top[0][0]


def classify_military(title: str, summary: str, fallback: bool) -> bool:
    if fallback:
        return True  # never demote a military-feed article
    corpus = _build_corpus(title, summary)
    return any(re.search(r"\b" + re.escape(kw) + r"\b", corpus) for kw in MILITARY_KEYWORDS)


def classify_tickers(title: str, summary: str) -> list[str]:
    corpus = _build_corpus(title, summary)
    seen: set[str] = set()
    result: list[str] = []
    for keyword, tickers in KEYWORD_TICKER_MAP.items():
        if keyword in corpus:
            for t in tickers:
                if t not in seen:
                    seen.add(t)
                    result.append(t)
    return result


def enrich_article(article: dict) -> dict:
    title = article.get("title", "")
    summary = article.get("summary", "")
    article["region"] = classify_region(title, summary, article["region"])
    article["is_military"] = classify_military(title, summary, article.get("is_military", False))
    tickers = classify_tickers(title, summary)
    article["tickers"] = tickers if tickers else None
    return article
