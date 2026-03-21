# scheduler.py

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from ingestion.ingestor import ingest_rss

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

    scheduler.start()
    logger.info("Scheduler started — RSS ingest every 15 minutes")

    # Fire immediately so DB is populated before first API request
    ingest_rss()


def stop_scheduler():
    scheduler.shutdown(wait=False)