# scripts/backfill_enrichment.py
# One-time script to re-classify all existing articles using content-based enrichment.
# Run from the project root: python -m scripts.backfill_enrichment

from collections import Counter

from database import SessionLocal
from ingestion.correlation_engine import enrich_article
from models import Article


def backfill():
    db = SessionLocal()
    try:
        articles = db.query(Article).all()
        region_counts: Counter = Counter()
        military_promoted = 0
        ticker_populated = 0

        for a in articles:
            old_region = a.region
            enriched = enrich_article({
                "title": a.title,
                "summary": a.summary or "",
                "region": a.region,
                "is_military": a.is_military,
            })
            a.region = enriched["region"]
            a.is_military = enriched["is_military"]
            a.tickers = enriched["tickers"]

            if a.region != old_region:
                region_counts[f"{old_region} -> {a.region}"] += 1
            if a.is_military and not enriched.get("_was_military"):
                military_promoted += 1
            if a.tickers:
                ticker_populated += 1

        db.commit()
        print(f"Backfilled {len(articles)} articles.")
        print(f"  Tickers populated: {ticker_populated}")
        if region_counts:
            print("  Region changes:")
            for transition, count in region_counts.most_common():
                print(f"    {transition}: {count}")
    finally:
        db.close()


if __name__ == "__main__":
    backfill()
