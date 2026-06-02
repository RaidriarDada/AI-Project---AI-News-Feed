import json
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from models import ContentItem
from tools.text_utils import normalize_title, normalize_url


ARTICLE_COLUMNS = {
    "normalized_title": "TEXT NOT NULL DEFAULT ''",
    "summary": "TEXT NOT NULL DEFAULT ''",
    "source_type": "TEXT NOT NULL DEFAULT 'rss'",
    "branch": "TEXT NOT NULL DEFAULT 'news'",
    "source_priority": "TEXT NOT NULL DEFAULT 'low'",
    "topics_json": "TEXT NOT NULL DEFAULT '[]'",
    "score": "REAL NOT NULL DEFAULT 0",
    "authors_or_org": "TEXT NOT NULL DEFAULT ''",
    "tags_json": "TEXT NOT NULL DEFAULT '[]'",
    "metadata_json": "TEXT NOT NULL DEFAULT '{}'",
    "score_reasons_json": "TEXT NOT NULL DEFAULT '[]'",
}

RUN_COLUMNS = {
    "num_github": "INTEGER NOT NULL DEFAULT 0",
    "num_huggingface": "INTEGER NOT NULL DEFAULT 0",
    "num_shortlisted": "INTEGER NOT NULL DEFAULT 0",
    "num_selected": "INTEGER NOT NULL DEFAULT 0",
}


def initialize_database() -> Path:
    """Initialize storage tables and migrate older local databases."""
    data_directory = Path("data")
    data_directory.mkdir(exist_ok=True)
    database_path = data_directory / "news_agent.db"

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS articles (
                link TEXT PRIMARY KEY,
                normalized_title TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL,
                source_name TEXT NOT NULL,
                published TEXT NOT NULL,
                collected_at TEXT NOT NULL,
                summary TEXT NOT NULL DEFAULT '',
                source_type TEXT NOT NULL DEFAULT 'rss',
                branch TEXT NOT NULL DEFAULT 'news',
                source_priority TEXT NOT NULL DEFAULT 'low',
                topics_json TEXT NOT NULL DEFAULT '[]',
                score REAL NOT NULL DEFAULT 0,
                authors_or_org TEXT NOT NULL DEFAULT '',
                tags_json TEXT NOT NULL DEFAULT '[]',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                score_reasons_json TEXT NOT NULL DEFAULT '[]'
            )
            """
        )
        existing_columns = {
            column[1]
            for column in connection.execute("PRAGMA table_info(articles)").fetchall()
        }

        for column_name, column_definition in ARTICLE_COLUMNS.items():
            if column_name not in existing_columns:
                connection.execute(
                    f"ALTER TABLE articles ADD COLUMN {column_name} {column_definition}"
                )

        rows = connection.execute(
            "SELECT link, title FROM articles WHERE normalized_title = ''"
        ).fetchall()

        for link, title in rows:
            connection.execute(
                "UPDATE articles SET normalized_title = ? WHERE link = ?",
                (normalize_title(title), link),
            )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                lookback_days INTEGER NOT NULL,
                status TEXT NOT NULL,
                num_collected INTEGER NOT NULL DEFAULT 0,
                num_unique INTEGER NOT NULL DEFAULT 0,
                num_new INTEGER NOT NULL DEFAULT 0,
                num_rss INTEGER NOT NULL DEFAULT 0,
                num_arxiv INTEGER NOT NULL DEFAULT 0,
                num_github INTEGER NOT NULL DEFAULT 0,
                num_huggingface INTEGER NOT NULL DEFAULT 0,
                num_shortlisted INTEGER NOT NULL DEFAULT 0,
                num_selected INTEGER NOT NULL DEFAULT 0,
                digest_path TEXT,
                error_count INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        existing_run_columns = {
            column[1]
            for column in connection.execute("PRAGMA table_info(runs)").fetchall()
        }

        for column_name, column_definition in RUN_COLUMNS.items():
            if column_name not in existing_run_columns:
                connection.execute(
                    f"ALTER TABLE runs ADD COLUMN {column_name} {column_definition}"
                )

        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_articles_normalized_title "
            "ON articles(normalized_title)"
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS item_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                item_link TEXT NOT NULL,
                stage TEXT NOT NULL,
                decision TEXT NOT NULL,
                score REAL NOT NULL,
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS digest_selections (
                digest_date TEXT NOT NULL,
                item_link TEXT NOT NULL,
                run_id TEXT NOT NULL,
                section TEXT NOT NULL,
                position INTEGER NOT NULL,
                selected_at TEXT NOT NULL,
                PRIMARY KEY (digest_date, item_link)
            )
            """
        )

    return database_path


def create_run(database_path: Path, lookback_days: int) -> str:
    """Create a run-history row and return its ID."""
    run_id = str(uuid4())

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO runs (run_id, started_at, lookback_days, status)
            VALUES (?, ?, ?, ?)
            """,
            (
                run_id,
                datetime.now().isoformat(timespec="seconds"),
                lookback_days,
                "running",
            ),
        )

    return run_id


def save_new_items(items: list[ContentItem], database_path: Path) -> list[ContentItem]:
    """Store unseen items and return only newly inserted records."""
    new_items = []

    with sqlite3.connect(database_path) as connection:
        for item in items:
            canonical_url = normalize_url(item.url)
            normalized_title = normalize_title(item.title)
            existing_item = connection.execute(
                """
                SELECT 1
                FROM articles
                WHERE link = ? OR normalized_title = ?
                LIMIT 1
                """,
                (canonical_url, normalized_title),
            ).fetchone()

            if existing_item:
                continue

            connection.execute(
                """
                INSERT INTO articles (
                    link,
                    normalized_title,
                    title,
                    source_name,
                    published,
                    collected_at,
                    summary,
                    source_type,
                    branch,
                    source_priority,
                    topics_json,
                    score,
                    authors_or_org,
                    tags_json,
                    metadata_json,
                    score_reasons_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    canonical_url,
                    normalized_title,
                    item.title,
                    item.source_name,
                    item.published,
                    datetime.now().isoformat(timespec="seconds"),
                    item.summary,
                    item.source_type,
                    item.branch,
                    item.source_priority,
                    json.dumps(item.topics),
                    item.score,
                    item.authors_or_org,
                    json.dumps(item.tags),
                    json.dumps(item.metadata),
                    json.dumps(item.score_reasons),
                ),
            )
            new_items.append(item)

    return new_items


def update_stored_item_rankings(items: list[ContentItem], database_path: Path) -> None:
    """Refresh ranking fields for items that are already in storage."""
    with sqlite3.connect(database_path) as connection:
        for item in items:
            connection.execute(
                """
                UPDATE articles
                SET topics_json = ?,
                    score = ?,
                    score_reasons_json = ?,
                    source_priority = ?,
                    branch = ?,
                    source_type = ?
                WHERE link = ? OR normalized_title = ?
                """,
                (
                    json.dumps(item.topics),
                    item.score,
                    json.dumps(item.score_reasons),
                    item.source_priority,
                    item.branch,
                    item.source_type,
                    normalize_url(item.url),
                    normalize_title(item.title),
                ),
            )


def finish_run(
    database_path: Path,
    run_id: str,
    status: str,
    stats: dict,
    digest_path: Path | None,
    error_count: int = 0,
) -> None:
    """Finish a run-history row with summary statistics."""
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            UPDATE runs
            SET finished_at = ?,
                status = ?,
                num_collected = ?,
                num_unique = ?,
                num_new = ?,
                num_rss = ?,
                num_arxiv = ?,
                num_github = ?,
                num_huggingface = ?,
                num_shortlisted = ?,
                num_selected = ?,
                digest_path = ?,
                error_count = ?
            WHERE run_id = ?
            """,
            (
                datetime.now().isoformat(timespec="seconds"),
                status,
                stats.get("num_collected", 0),
                stats.get("num_unique", 0),
                stats.get("num_new", 0),
                stats.get("num_rss", 0),
                stats.get("num_arxiv", 0),
                stats.get("num_github", 0),
                stats.get("num_huggingface", 0),
                stats.get("num_shortlisted", 0),
                stats.get("num_selected", 0),
                str(digest_path) if digest_path else None,
                error_count,
                run_id,
            ),
        )


def _row_to_item(row: sqlite3.Row) -> ContentItem:
    metadata = json.loads(row["metadata_json"])

    if "digest_section" in row.keys():
        metadata["digest_section"] = row["digest_section"]

    return ContentItem(
        title=row["title"],
        url=row["link"],
        source_name=row["source_name"],
        published=row["published"],
        summary=row["summary"],
        source_type=row["source_type"],
        branch=row["branch"],
        source_priority=row["source_priority"],
        authors_or_org=row["authors_or_org"],
        tags=json.loads(row["tags_json"]),
        metadata=metadata,
        topics=json.loads(row["topics_json"]),
        score=row["score"],
        score_reasons=json.loads(row["score_reasons_json"]),
    )


def load_recent_items(database_path: Path, lookback_days: int) -> list[ContentItem]:
    """Load recently collected candidates so reruns can rebuild a digest."""
    cutoff_time = datetime.now() - timedelta(days=lookback_days)

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT *
            FROM articles
            WHERE collected_at >= ?
            ORDER BY score DESC
            """,
            (cutoff_time.isoformat(timespec="seconds"),),
        ).fetchall()

    return [_row_to_item(row) for row in rows]


def record_item_decisions(
    database_path: Path,
    run_id: str,
    items: list[ContentItem],
    stage: str,
    promoted_items: list[ContentItem],
) -> None:
    """Record whether items moved forward at one pipeline stage."""
    promoted_urls = {normalize_url(item.url) for item in promoted_items}
    created_at = datetime.now().isoformat(timespec="seconds")

    with sqlite3.connect(database_path) as connection:
        for item in items:
            promoted = normalize_url(item.url) in promoted_urls
            score_reason = "; ".join(item.score_reasons) or "No scoring signals."

            if promoted:
                reason = f"Promoted. {score_reason}"
            else:
                reason = (
                    "Skipped: below score threshold or outside branch limit. "
                    f"{score_reason}"
                )

            connection.execute(
                """
                INSERT INTO item_decisions (
                    run_id,
                    item_link,
                    stage,
                    decision,
                    score,
                    reason,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    normalize_url(item.url),
                    stage,
                    "promoted" if promoted else "skipped",
                    item.score,
                    reason,
                    created_at,
                ),
            )


def replace_daily_digest_selections(
    database_path: Path,
    run_id: str,
    items: list[ContentItem],
    top_pick_count: int,
) -> None:
    """Replace today's digest selections so reruns stay deterministic."""
    digest_date = date.today().isoformat()
    selected_at = datetime.now().isoformat(timespec="seconds")

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "DELETE FROM digest_selections WHERE digest_date = ?",
            (digest_date,),
        )

        for position, item in enumerate(items, start=1):
            if position <= top_pick_count:
                section = "Top Picks"
            elif item.branch == "research":
                section = "Research Papers"
            elif item.branch == "development":
                section = "Repos, Tools & Models"
            else:
                section = "News & Model Releases"

            connection.execute(
                """
                INSERT INTO digest_selections (
                    digest_date,
                    item_link,
                    run_id,
                    section,
                    position,
                    selected_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    digest_date,
                    normalize_url(item.url),
                    run_id,
                    section,
                    position,
                    selected_at,
                ),
            )


def load_daily_digest_items(database_path: Path) -> list[ContentItem]:
    """Load today's stored digest selection in display order."""
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT articles.*, digest_selections.section AS digest_section
            FROM digest_selections
            JOIN articles ON articles.link = digest_selections.item_link
            WHERE digest_selections.digest_date = ?
            ORDER BY digest_selections.position
            """,
            (date.today().isoformat(),),
        ).fetchall()

    return [_row_to_item(row) for row in rows]
