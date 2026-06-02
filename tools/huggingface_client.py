from datetime import datetime, timedelta, timezone

from huggingface_hub import HfApi

from models import ContentItem

def collect_huggingface_items(
        config: dict, lookback_days: int
) -> list[ContentItem]:
    """Collect Hugging Face repositories based on the provided configuration."""
    if not config.get("enabled", True):
        return []

    api = HfApi()
    max_results = config.get("max_results_per_query", 10)
    cutoff_time = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    items = []

    for pipeline_filter in config.get("filters", []):
        print(f"Collecting Hugging Face repositories for filter: {pipeline_filter}")

        models = api.list_models(
            pipeline_tag=pipeline_filter,
            sort="trending_score",
            limit=max_results,
            expand=[
                "lastModified",
                "downloads",
                "likes",
                "pipeline_tag",
                "trendingScore",
                "author",
                "tags",
            ],
        )

        for model in models:
            last_modified = model.last_modified

            if not last_modified:
                print(f"Skipping model with missing last_modified: {model.id}")
                continue

            if last_modified < cutoff_time:
                continue

            downloads = model.downloads or 0
            likes = model.likes or 0
            pipeline_tag = model.pipeline_tag or pipeline_filter
            trending_score = model.trending_score or 0

            item = ContentItem(
                title=model.id,
                url=f"https://huggingface.co/{model.id}",
                source_name="Hugging Face",
                published=last_modified.isoformat(),
                summary=(
                    f"Hugging Face model for {pipeline_tag}. "
                    f"Downloads: {downloads}. Likes: {likes}. Trending score: {trending_score}"
                ),
                source_type="huggingface_model",
                branch="development",
                source_priority=config.get("priority", "medium"),
                authors_or_org=model.author or "",
                tags=model.tags or [],
                metadata={
                    "downloads": downloads,
                    "likes": likes,
                    "pipeline_tag": pipeline_tag,
                    "trending_score": trending_score,
                },
            )
            items.append(item)

    return items
