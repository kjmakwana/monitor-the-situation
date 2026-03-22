# routes/news.py

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database import get_db
from models import Article

router = APIRouter()


@router.get("/api/news")
def get_news(
    region: str | None   = Query(None, description="Filter by region e.g. europe, middle_east"),
    source: str | None   = Query(None, description="Filter by source_id e.g. bbc, eucom"),
    military: bool | None = Query(None, description="Filter military sources only"),
    limit: int           = Query(20, ge=1, le=100),
    offset: int          = Query(0, ge=0),
    db: Session          = Depends(get_db),
):
    query = db.query(Article)

    if region:
        query = query.filter(Article.region == region)
    if source:
        query = query.filter(Article.source == source)
    if military is not None:
        query = query.filter(Article.is_military == military)

    total = query.count()
    articles = (
        query
        .order_by(desc(Article.published_at))
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "articles": [
            {
                "id":           a.id,
                "title":        a.title,
                "url":          a.url,
                "source":       a.source,
                "source_name":  a.source_name,
                "region":       a.region,
                "is_military":  a.is_military,
                "summary":      a.summary,
                "published_at": a.published_at.isoformat(),
            }
            for a in articles
        ],
    }