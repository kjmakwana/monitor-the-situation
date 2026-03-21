# config/feeds.py

RSS_FEEDS = [
    {
        "name": "BBC World",
        "url": "http://feeds.bbci.co.uk/news/world/rss.xml",
        "region": "global",
        "source_id": "bbc",
    },
    {
        "name": "Al Jazeera",
        "url": "https://www.aljazeera.com/xml/rss/all.xml",
        "region": "middle_east",
        "source_id": "aljazeera",
    },
    {
        "name": "Deutsche Welle",
        "url": "https://rss.dw.com/xml/rss-en-all",
        "region": "europe",
        "source_id": "dw",
    },
    {
        "name": "Channel NewsAsia",
        "url": "https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml",
        "region": "se_asia",
        "source_id": "cna",
    },
    {
        "name": "Dawn Pakistan",
        "url": "https://www.dawn.com/feeds/home",
        "region": "s_asia",
        "source_id": "dawn",
    },
    {
        "name": "EUCOM",
        "url": "https://www.eucom.mil/syndication-feed/rss/press-releases",
        "region": "europe",
        "source_id": "eucom",
        "is_military": True,
    },
    
]