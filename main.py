from pathlib import Path
from typing import Any, TypedDict

from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

load_dotenv()  # Load environment variables from .env file

import yaml

from models import ContentItem
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


class DigestState(TypedDict, total=False):
    """Shared state that LangGraph passes from node to node."""

    sources_config: dict[str, Any]
    preferences: dict[str, Any]
    lookback_days: int
    database_path: str
    run_id: int
    rss_items: list[ContentItem]
    arxiv_items: list[ContentItem]
    github_items: list[ContentItem]
    huggingface_items: list[ContentItem]
    collected_items: list[ContentItem]
    unique_items: list[ContentItem]
    ranked_items: list[ContentItem]
    new_items: list[ContentItem]
    recent_items: list[ContentItem]
    ranked_recent_items: list[ContentItem]
    shortlisted_items: list[ContentItem]
    selected_items: list[ContentItem]


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


def load_configs_node(state: DigestState) -> DigestState:
    """Load project configuration into the graph state."""
    preferences = load_yaml_config("configs/preferences.yaml")

    return {
        "sources_config": load_yaml_config("configs/sources.yaml"),
        "preferences": preferences,
        "lookback_days": preferences.get("collection", {}).get("lookback_days", 3),
    }


def start_run_node(state: DigestState) -> DigestState:
    """Initialize the database and create a run record."""
    if "database_path" in state and "run_id" in state:
        return {}

    lookback_days = state["lookback_days"]
    database_path = initialize_database()

    return {
        "database_path": str(database_path),
        "run_id": create_run(database_path, lookback_days),
    }


def collect_rss_node(state: DigestState) -> DigestState:
    """Collect RSS items from enabled RSS sources."""
    rss_items = []
    sources_config = state["sources_config"]
    lookback_days = state["lookback_days"]

    for source in get_enabled_rss_sources(sources_config):
        rss_items.extend(collect_rss_items(source, lookback_days))

    return {"rss_items": rss_items}


def collect_arxiv_node(state: DigestState) -> DigestState:
    """Collect ArXiv items from enabled ArXiv sources."""
    arxiv_items = collect_arxiv_items(
        state["sources_config"].get("arxiv", {}),
        state["lookback_days"],
    )
    return {"arxiv_items": arxiv_items}


def collect_github_node(state: DigestState) -> DigestState:
    """Collect Github repos"""
    github_items = collect_github_items(
        state["sources_config"].get("github", {}),
        state["lookback_days"],
    )
    return {"github_items": github_items}


def collect_huggingface_node(state: DigestState) -> DigestState:
    """Collect Huggingface projects"""
    huggingface_items = collect_huggingface_items(
        state["sources_config"].get("huggingface", {}),
        state["lookback_days"],
    )
    return {"huggingface_items": huggingface_items}


def merge_items_node(state: DigestState) -> DigestState:
    collected_items = (
        state["rss_items"]
        + state["arxiv_items"]
        + state["github_items"]
        + state["huggingface_items"]
    )

    return {"collected_items": collected_items}


def deduplicate_items_node(state: DigestState) -> DigestState:
    unique_items = remove_duplicate_items(state["collected_items"])
    return {"unique_items": unique_items}


def rank_items_node(state: DigestState) -> DigestState:
    ranked_items = classify_and_rank_items(
        state["unique_items"],
        state["preferences"],
    )
    return {"ranked_items": ranked_items}


def save_ranked_items_node(state: DigestState) -> DigestState:
    new_items = save_new_items(
        state["ranked_items"],
        state["database_path"],
    )

    update_stored_item_rankings(
        state["ranked_items"],
        state["database_path"],
    )

    return {"new_items": new_items}


def load_recent_items_node(state: DigestState) -> DigestState:
    recent_items = load_recent_items(
        state["database_path"],
        state["lookback_days"],
    )

    return {"recent_items": recent_items}


def rank_recent_items_node(state: DigestState) -> DigestState:
    ranked_recent_items = classify_and_rank_items(
        state["recent_items"],
        state["preferences"],
    )

    update_stored_item_rankings(
        ranked_recent_items,
        state["database_path"],
    )

    return {"ranked_recent_items": ranked_recent_items}


def shortlist_items_node(state: DigestState) -> DigestState:
    shortlisted_items = shortlist_items(
        state["ranked_recent_items"],
        state["preferences"],
    )

    return {"shortlisted_items": shortlisted_items}


def select_final_items_node(state: DigestState) -> DigestState:
    selected_items = select_final_items(
        state["shortlisted_items"],
        state["preferences"],
    )

    return {"selected_items": selected_items}


def build_digest_graph():
    """Build the first LangGraph slice of the digest workflow."""
    graph_builder = StateGraph(DigestState)

    graph_builder.add_node("load_configs", load_configs_node)
    graph_builder.add_node("start_run", start_run_node)
    graph_builder.add_node("collect_rss", collect_rss_node)
    graph_builder.add_node("collect_arxiv", collect_arxiv_node)
    graph_builder.add_node("collect_github", collect_github_node)
    graph_builder.add_node("collect_huggingface", collect_huggingface_node)
    graph_builder.add_node("merge_items", merge_items_node)
    graph_builder.add_node("deduplicate_items", deduplicate_items_node)
    graph_builder.add_node("rank_items", rank_items_node)
    graph_builder.add_node("save_new_items", save_ranked_items_node)
    graph_builder.add_node("load_recent_items", load_recent_items_node)
    graph_builder.add_node("rank_recent_items", rank_recent_items_node)
    graph_builder.add_node("shortlist_items", shortlist_items_node)
    graph_builder.add_node("select_final_items", select_final_items_node)

    graph_builder.add_edge(START, "load_configs")
    graph_builder.add_edge("load_configs", "start_run")
    graph_builder.add_edge("start_run", "collect_rss")
    graph_builder.add_edge("collect_rss", "collect_arxiv")
    graph_builder.add_edge("collect_arxiv", "collect_github")
    graph_builder.add_edge("collect_github", "collect_huggingface")
    graph_builder.add_edge("collect_huggingface", "merge_items")
    graph_builder.add_edge("merge_items", "deduplicate_items")
    graph_builder.add_edge("deduplicate_items", "rank_items")
    graph_builder.add_edge("rank_items", "save_new_items")
    graph_builder.add_edge("save_new_items", "load_recent_items")
    graph_builder.add_edge("load_recent_items", "rank_recent_items")
    graph_builder.add_edge("rank_recent_items", "shortlist_items")
    graph_builder.add_edge("shortlist_items", "select_final_items")
    graph_builder.add_edge("select_final_items", END)

    return graph_builder.compile()


def main() -> None:
    sources_config = load_yaml_config("configs/sources.yaml")
    preferences = load_yaml_config("configs/preferences.yaml")
    lookback_days = preferences.get("collection", {}).get("lookback_days", 3)
    database_path = initialize_database()
    run_id = create_run(database_path, lookback_days)

    try:
        state = build_digest_graph().invoke(
            {
                "sources_config": sources_config,
                "preferences": preferences,
                "lookback_days": lookback_days,
                "database_path": str(database_path),
                "run_id": run_id,
            }
        )

        rss_items = state["rss_items"]
        arxiv_items = state["arxiv_items"]
        github_items = state["github_items"]
        huggingface_items = state["huggingface_items"]

        collected_items = state["collected_items"]
        unique_items = state["unique_items"]
        ranked_items = state["ranked_items"]
        new_items = state["new_items"]

        recent_items = state["recent_items"]
        ranked_recent_items = state["ranked_recent_items"]
        shortlisted_items = state["shortlisted_items"]
        selected_items = state["selected_items"]

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
