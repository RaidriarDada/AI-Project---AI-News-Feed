from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import feedparser
import yaml
import sqlite3

@dataclass
class Article:
    title: str
    link: str
    source_name: str
    published: str
    topics: list[str] = field(default_factory=list)
    score: int = 0

TOPIC_KEYWORDS = {
    "LLM": ["llm", "language model", "gpt", "gemini"],
    "AI agents": ["agent", "agentic", "tool use"],
    "Multimodal": ["multimodal", "vision", "video", "image"],
    "Reasoning": ["reasoning", "thinking"],
    "Infrastructure": ["inference", "deployment", "gpu"],
}

def load_feeds() -> dict[str, str]:
    """Load RSS feed URLs from the configuration file."""
    config_path = Path("configs/sources.yaml")

    if not config_path.exists():
        print(f"Config file not found: {config_path}")
        return {}

    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    feeds = {}

    for source in config["rss"]["sources"]:
        if source.get("enabled", True):
            feeds[source["name"]] = source["url"]

    return feeds

def collect_articles(source_name: str, feed_url: str) -> list[Article]:
    """Collect articles from a given RSS feed."""
    print(f"Collecting articles from {source_name}...")
    feed = feedparser.parse(feed_url)

    if feed.bozo:
        print(f"Error parsing feed: {feed.bozo_exception}")
        return []

    articles = []
    for entry in feed.entries[:5]:
        article = Article(
            title=entry.title,
            link=entry.link,
            source_name=source_name,
            published=entry.published
        )
        articles.append(article)
    return articles

def remove_duplicate_articles(articles: list[Article]) -> list[Article]:
    """Remove duplicate articles based on their links."""
    unique_articles = []
    seen_links = set()

    for article in articles:
        normalized_link = article.link.rstrip("/")

        if normalized_link in seen_links:
            print(f"Skipping duplicate: {article.title}")
            continue

        seen_links.add(normalized_link)
        unique_articles.append(article)

    return unique_articles

def initialize_database() -> Path:
    """Initialize the SQLite database and return its path."""
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    database_path = data_dir / "news_agent.db"

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS articles (
                link TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                source_name TEXT NOT NULL,
                published TEXT NOT NULL,
                collected_at TEXT NOT NULL
            )
            """
        )

    return database_path

def classify_and_rank_articles(articles: list[Article]) -> list[Article]:
    for article in articles:
        searchable_text = article.title.lower()

        for topic, keywords in TOPIC_KEYWORDS.items():
            if any(keyword in searchable_text for keyword in keywords):
                article.topics.append(topic)
                article.score += 1

    return sorted(articles, key=lambda article: article.score, reverse=True)

def save_new_articles(
    articles: list[Article], database_path: Path
) -> list[Article]:
    """Save new articles to the database and return the list of newly added articles."""
    new_articles = []

    with sqlite3.connect(database_path) as connection:
        for article in articles:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO articles (
                    link,
                    title,
                    source_name,
                    published,
                    collected_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    article.link.rstrip("/"),
                    article.title,
                    article.source_name,
                    article.published,
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )

            if cursor.rowcount == 1:
                new_articles.append(article)

    return new_articles

def save_digest(articles: list[Article]) -> None:
    output_directory = Path("outputs")
    output_directory.mkdir(exist_ok=True)

    digest_lines = [
        f"# AI News Digest - {date.today().isoformat()}",
        "",
    ]

    for article in articles:
        digest_lines.append(f"## {article.title}")
        digest_lines.append(f"Source: {article.source_name}")
        topics = ", ".join(article.topics) or "Other"
        digest_lines.append(f"Topics: {topics}")
        digest_lines.append(f"Relevance score: {article.score}")
        digest_lines.append(f"Published: {article.published}")
        digest_lines.append(f"Link: {article.link}")
        digest_lines.append("")

    output_path = output_directory / "ai_digest.md"
    output_path.write_text("\n".join(digest_lines), encoding="utf-8")

    print(f"\nDigest saved to: {output_path}")


# Modify the main function to initialize the database and save only new articles
def main() -> None:
    database_path = initialize_database()
    feeds = load_feeds()
    all_articles = []

    for source_name, feed_url in feeds.items():
        all_articles.extend(collect_articles(source_name, feed_url))

    unique_articles = remove_duplicate_articles(all_articles)
    new_articles = save_new_articles(unique_articles, database_path)

    ranked_articles = classify_and_rank_articles(new_articles)

    print(f"\nCollected articles: {len(all_articles)}")
    print(f"Unique articles: {len(unique_articles)}")
    print(f"New articles: {len(new_articles)}")

    save_digest(ranked_articles)

if __name__ == "__main__":
    main()