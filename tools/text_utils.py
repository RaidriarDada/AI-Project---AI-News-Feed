import re
from calendar import timegm
from datetime import datetime, timedelta, timezone
from html import unescape
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from models import ContentItem


def clean_html(text: str) -> str:
    """Remove simple HTML tags from feed summaries."""
    text_without_tags = re.sub(r"<[^>]+>", "", text)
    return unescape(text_without_tags).strip()


def is_recent_entry(entry: dict, lookback_days: int) -> bool:
    """Return True when a feed entry is recent or has no usable date."""
    published_time = entry.get("published_parsed")

    if not published_time:
        return True

    published_at = datetime.fromtimestamp(timegm(published_time), tz=timezone.utc)
    cutoff_time = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    return published_at >= cutoff_time


def normalize_url(url: str) -> str:
    """Remove common tracking details so equivalent URLs match."""
    tracking_parameters = {
        "fbclid",
        "gclid",
        "mc_cid",
        "mc_eid",
        "ref",
        "source",
    }

    parsed_url = urlsplit(url.strip())
    filtered_query = [
        (key, value)
        for key, value in parse_qsl(parsed_url.query, keep_blank_values=True)
        if not key.lower().startswith("utm_")
        and key.lower() not in tracking_parameters
    ]
    normalized_path = parsed_url.path.rstrip("/") or "/"

    return urlunsplit(
        (
            parsed_url.scheme.lower(),
            parsed_url.netloc.lower(),
            normalized_path,
            urlencode(filtered_query),
            "",
        )
    )


def normalize_title(title: str) -> str:
    """Normalize a title for exact cross-source duplicate detection."""
    lowercase_title = title.lower()
    title_without_punctuation = re.sub(r"[^\w\s]", " ", lowercase_title)
    return " ".join(title_without_punctuation.split())


def remove_duplicate_items(items: list[ContentItem]) -> list[ContentItem]:
    """Remove items with repeated canonical URLs or normalized titles."""
    unique_items = []
    seen_urls = set()
    seen_titles = set()

    for item in items:
        normalized_url = normalize_url(item.url)
        normalized_title = normalize_title(item.title)

        if normalized_url in seen_urls or normalized_title in seen_titles:
            print(f"Skipping duplicate: {item.title}")
            continue

        seen_urls.add(normalized_url)
        seen_titles.add(normalized_title)
        unique_items.append(item)

    return unique_items
