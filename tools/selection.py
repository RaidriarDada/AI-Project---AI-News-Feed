from models import ContentItem


def _item_key(item: ContentItem) -> str:
    return item.url


def shortlist_items(
    ranked_items: list[ContentItem], preferences: dict
) -> list[ContentItem]:
    """Keep the strongest candidates within each branch limit."""
    selection_config = preferences.get("selection", {})
    branch_limits = selection_config.get("shortlist_limits", {})
    minimum_score = selection_config.get("minimum_shortlist_score", 0)
    shortlisted_items = []

    for branch, limit in branch_limits.items():
        branch_items = [
            item
            for item in ranked_items
            if item.branch == branch and item.score >= minimum_score
        ]
        shortlisted_items.extend(branch_items[:limit])

    return sorted(shortlisted_items, key=lambda item: item.score, reverse=True)


def select_final_items(
    shortlisted_items: list[ContentItem], preferences: dict
) -> list[ContentItem]:
    """Select a balanced digest with soft branch quotas."""
    selection_config = preferences.get("selection", {})
    max_items = selection_config.get("max_final_items", 12)
    minimum_score = selection_config.get("minimum_final_score", 0)
    branch_quotas = selection_config.get("final_branch_quotas", {})
    eligible_items = [
        item for item in shortlisted_items if item.score >= minimum_score
    ]

    selected_items = []
    selected_keys = set()

    for branch, quota in branch_quotas.items():
        branch_items = [item for item in eligible_items if item.branch == branch]

        for item in branch_items[:quota]:
            selected_items.append(item)
            selected_keys.add(_item_key(item))

    for item in eligible_items:
        if len(selected_items) >= max_items:
            break

        if _item_key(item) not in selected_keys:
            selected_items.append(item)
            selected_keys.add(_item_key(item))

    return sorted(selected_items[:max_items], key=lambda item: item.score, reverse=True)
