from pathlib import Path
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

import yaml

from tools.arxiv_client import collect_arxiv_items
from tools.database import (
    create_run,
    finish_run,
    initialize_database,
    load_daily_digest_items,
    load_recent_items,
    record_item_decisions,
    replace_daily_digest_selections,
    save_new_items,
    update_stored_item_rankings,
)
from tools.digest import save_digest
from tools.rss_client import collect_rss_items
from tools.scoring import classify_and_rank_items
from tools.selection import select_final_items, shortlist_items
from tools.text_utils import remove_duplicate_items
from tools.github_client import collect_github_items
from tools.huggingface_client import collect_huggingface_items


def load_yaml_config(path: str) -> dict:
    """Load a YAML configuration file."""
    config_path = Path(path)

    if not config_path.exists():
        print(f"Config file not found: {config_path}")
        return {}

    return yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}


def get_enabled_rss_sources(sources_config: dict) -> list[dict]:
    """Return enabled RSS source settings."""
    return [
        source
        for source in sources_config.get("rss", {}).get("sources", [])
        if source.get("enabled", True)
    ]


def main() -> None:
    sources_config = load_yaml_config("configs/sources.yaml")
    preferences = load_yaml_config("configs/preferences.yaml")
    lookback_days = preferences.get("collection", {}).get("lookback_days", 3)

    database_path = initialize_database()
    run_id = create_run(database_path, lookback_days)

    try:
        rss_items = []
        for source in get_enabled_rss_sources(sources_config):
            rss_items.extend(collect_rss_items(source, lookback_days))

        arxiv_items = collect_arxiv_items(
            sources_config.get("arxiv", {}),
            lookback_days,
        )

        github_items = collect_github_items(
            sources_config.get("github", {}),
            lookback_days,
        )

        huggingface_items = collect_huggingface_items(
            sources_config.get("huggingface", {}),
            lookback_days,
        )

        collected_items = rss_items + arxiv_items + github_items + huggingface_items
        unique_items = remove_duplicate_items(collected_items)
        ranked_items = classify_and_rank_items(unique_items, preferences)
        new_items = save_new_items(ranked_items, database_path)
        update_stored_item_rankings(ranked_items, database_path)

        recent_items = load_recent_items(database_path, lookback_days)
        ranked_recent_items = classify_and_rank_items(recent_items, preferences)
        update_stored_item_rankings(ranked_recent_items, database_path)

        shortlisted_items = shortlist_items(ranked_recent_items, preferences)
        selected_items = select_final_items(shortlisted_items, preferences)

        record_item_decisions(
            database_path,
            run_id,
            ranked_recent_items,
            "shortlist",
            shortlisted_items,
        )
        record_item_decisions(
            database_path,
            run_id,
            shortlisted_items,
            "final_selection",
            selected_items,
        )

        top_pick_count = preferences.get("selection", {}).get("top_pick_count", 3)
        replace_daily_digest_selections(
            database_path,
            run_id,
            selected_items,
            top_pick_count,
        )
        digest_items = load_daily_digest_items(database_path)
        digest_path = save_digest(digest_items)

        stats = {
            "num_collected": len(collected_items),
            "num_unique": len(unique_items),
            "num_new": len(new_items),
            "num_rss": len(rss_items),
            "num_arxiv": len(arxiv_items),
            "num_github": len(github_items),
            "num_huggingface": len(huggingface_items),
            "num_shortlisted": len(shortlisted_items),
            "num_selected": len(selected_items),
        }
        finish_run(database_path, run_id, "completed", stats, digest_path)

        print(f"\nRSS collected: {len(rss_items)}")
        print(f"arXiv collected: {len(arxiv_items)}")
        print(f"GitHub collected: {len(github_items)}")
        print(f"Hugging Face collected: {len(huggingface_items)}")
        print(f"Total collected: {len(collected_items)}")
        print(f"Unique items: {len(unique_items)}")
        print(f"New items: {len(new_items)}")
        print(f"Shortlisted items: {len(shortlisted_items)}")
        print(f"Selected digest items: {len(selected_items)}")
    except Exception:
        finish_run(database_path, run_id, "failed", {}, None, error_count=1)
        raise


if __name__ == "__main__":
    main()
