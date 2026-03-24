# scheduler.py

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from ingestion.ingestor import ingest_rss
from ingestion.market_fetcher import fetch_all_prices

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def start_scheduler():
    scheduler.add_job(
        func=ingest_rss,
        trigger=IntervalTrigger(minutes=15),
        id="rss_ingest",
        name="RSS feed ingest",
        replace_existing=True,
        max_instances=1,           # never overlap if a run runs long
        misfire_grace_time=60,     # tolerate up to 60s of lateness
    )
    scheduler.add_job(
        func=fetch_all_prices,
        trigger=IntervalTrigger(minutes=2),
        id="market_fetch",
        name="Market price fetch",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=30,
    )

    scheduler.start()
    logger.info("Scheduler started — RSS ingest every 15 minutes")
    logger.info("Market prices fetch every 1 minute")

    # Fire immediately so DB is populated before first API request
    ingest_rss()
    fetch_all_prices()


def stop_scheduler():
    scheduler.shutdown(wait=False)