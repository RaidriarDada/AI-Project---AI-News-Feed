from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from models import ContentItem


def _add_score(item: ContentItem, points: float, reason: str) -> None:
    if points == 0:
        return

    item.score += points
    item.score_reasons.append(f"{reason}: {points:+g}")


def _parse_datetime(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            return parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None


def _apply_threshold_score(
    item: ContentItem,
    value: int | float,
    thresholds: list[dict],
    reason: str,
) -> None:
    for threshold in sorted(
        thresholds,
        key=lambda entry: entry.get("minimum", 0),
        reverse=True,
    ):
        if value >= threshold.get("minimum", 0):
            _add_score(item, threshold.get("score", 0), reason)
            return


def classify_and_rank_items(
    items: list[ContentItem], preferences: dict
) -> list[ContentItem]:
    """Apply configurable topic and branch-aware deterministic scoring."""
    ranking_config = preferences.get("ranking", {})
    topic_keywords = ranking_config.get("topic_keywords", {})
    source_priority_scores = ranking_config.get("source_priority_scores", {})
    branch_base_scores = ranking_config.get("branch_base_scores", {})
    research_category_scores = ranking_config.get("research_category_scores", {})
    practical_keywords = ranking_config.get("practical_keywords", [])
    penalty_keywords = ranking_config.get("penalty_keywords", {})
    maturity_scores = ranking_config.get("maturity_scores", {})

    for item in items:
        item.topics = []
        item.score = 0.0
        item.score_reasons = []

        _add_score(
            item,
            source_priority_scores.get(item.source_priority, 0),
            f"{item.source_priority} source priority",
        )
        _add_score(
            item,
            branch_base_scores.get(item.branch, 0),
            f"{item.branch} branch",
        )

        searchable_text = " ".join(
            [item.title, item.summary, *item.tags]
        ).lower()

        for topic, keywords in topic_keywords.items():
            if any(keyword.lower() in searchable_text for keyword in keywords):
                item.topics.append(topic)
                _add_score(item, 1, f"topic match: {topic}")

        if any(keyword.lower() in searchable_text for keyword in practical_keywords):
            _add_score(item, 1, "practical relevance")

        for penalty_name, penalty_config in penalty_keywords.items():
            keywords = penalty_config.get("keywords", [])

            if any(keyword.lower() in searchable_text for keyword in keywords):
                _add_score(
                    item,
                    penalty_config.get("score", 0),
                    f"penalty: {penalty_name}",
                )

        if item.branch == "research":
            category_score = max(
                (research_category_scores.get(tag, 0) for tag in item.tags),
                default=0,
            )
            _add_score(item, category_score, "research category")

        if item.source_type == "github_repo":
            _apply_threshold_score(
                item,
                item.metadata.get("stars", 0),
                maturity_scores.get("github_stars", []),
                "GitHub stars",
            )

        if item.source_type == "huggingface_model":
            _apply_threshold_score(
                item,
                item.metadata.get("downloads", 0),
                maturity_scores.get("huggingface_downloads", []),
                "Hugging Face downloads",
            )
            _apply_threshold_score(
                item,
                item.metadata.get("likes", 0),
                maturity_scores.get("huggingface_likes", []),
                "Hugging Face likes",
            )
            _apply_threshold_score(
                item,
                item.metadata.get("trending_score", 0),
                maturity_scores.get("huggingface_trending", []),
                "Hugging Face trending score",
            )

        published_at = _parse_datetime(item.published)

        if published_at and published_at.tzinfo:
            age_days = (datetime.now(timezone.utc) - published_at).days
            recency_scores = ranking_config.get("recency_scores", [])

            for recency_score in sorted(
                recency_scores,
                key=lambda entry: entry.get("max_age_days", 0),
            ):
                if age_days <= recency_score.get("max_age_days", 0):
                    _add_score(item, recency_score.get("score", 0), "recency")
                    break

    return sorted(items, key=lambda item: item.score, reverse=True)
