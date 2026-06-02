from urllib.parse import urlencode

import feedparser

from models import ContentItem
from tools.text_utils import clean_html, is_recent_entry


def collect_arxiv_items(config: dict, lookback_days: int) -> list[ContentItem]:
    """Collect recent research papers from the arXiv Atom API."""
    if not config.get("enabled", False):
        return []

    categories = config.get("categories", [])

    if not categories:
        print("Skipping arXiv: no categories configured.")
        return []

    search_query = " OR ".join(f"cat:{category}" for category in categories)
    query_parameters = {
        "search_query": search_query,
        "start": 0,
        "max_results": config.get("max_results", 40),
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    api_url = config.get("api_url", "https://export.arxiv.org/api/query")
    feed_url = f"{api_url}?{urlencode(query_parameters)}"

    print("Collecting recent papers from arXiv...")
    feed = feedparser.parse(feed_url)

    if feed.bozo and not feed.entries:
        print(f"Error parsing arXiv feed: {feed.bozo_exception}")
        return []

    items = []

    for entry in feed.entries:
        if not is_recent_entry(entry, lookback_days):
            continue

        tags = [tag.get("term", "") for tag in entry.get("tags", [])]
        authors = ", ".join(
            author.get("name", "") for author in entry.get("authors", [])
        )

        items.append(
            ContentItem(
                title=entry.get("title", "Untitled paper").replace("\n", " "),
                url=entry.get("link", entry.get("id", "")),
                source_name="arXiv",
                published=entry.get("published", "Date unavailable"),
                summary=clean_html(entry.get("summary", "No abstract available")),
                source_type="arxiv",
                branch="research",
                source_priority=config.get("priority", "medium"),
                authors_or_org=authors,
                tags=tags,
                metadata={"arxiv_id": entry.get("id", "")},
            )
        )

    return items
