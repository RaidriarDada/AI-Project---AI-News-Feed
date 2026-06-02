import feedparser

from models import ContentItem
from tools.text_utils import clean_html, is_recent_entry


def collect_rss_items(source: dict, lookback_days: int) -> list[ContentItem]:
    """Collect recent items from one RSS feed."""
    source_name = source["name"]
    feed_url = source["url"]

    print(f"Collecting RSS articles from {source_name}...")
    feed = feedparser.parse(feed_url)

    if feed.bozo and not feed.entries:
        print(f"Error parsing feed: {feed.bozo_exception}")
        return []

    items = []

    for entry in feed.entries:
        if not is_recent_entry(entry, lookback_days):
            continue

        items.append(
            ContentItem(
                title=entry.get("title", "Untitled article"),
                url=entry.get("link", ""),
                source_name=source_name,
                published=entry.get("published", "Date unavailable"),
                summary=clean_html(entry.get("summary", "No summary available")),
                source_type="rss",
                branch="news",
                source_priority=source.get("priority", "low"),
                metadata={"category": source.get("category", "")},
            )
        )

    return items
