"""
Read each configured query
-> call GET https://api.github.com/search/repositories
-> discard repos below min_stars
-> convert results into ContentItem objects
"""

import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import requests

from models import ContentItem

def collect_github_items(
        config: dict, lookback_days: int
) -> list[ContentItem]:
    """Collect GitHub repositories based on the provided configuration."""
    if not config.get("enabled", True):
        return []

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    github_token = os.getenv("GITHUB_TOKEN")

    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    api_url = config.get(
        "api_url",
        "https://api.github.com/search/repositories"
    )
    min_stars = config.get("min_stars", 0)
    max_results = config.get("max_results_per_query", 5)
    cutoff_time = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    items = []

    for query in config.get("queries", []):
        print(f"Collecting GitHub repositories for query: {query}")

        parameters = {
            "q": f"{query} stars:>={min_stars}",
            "sort": "updated",
            "order": "desc",
            "per_page": max_results,
        }

        response = requests.get(
            f"{api_url}?{urlencode(parameters)}",
            headers=headers,
            timeout=20,
        )
        #print(f"GitHub API response status: {response.status_code}")
        response.raise_for_status()

        for repository in response.json().get("items", []):
            updated_at = datetime.strptime(
                repository["updated_at"], "%Y-%m-%dT%H:%M:%SZ"
            ).replace(tzinfo=timezone.utc)

            if updated_at < cutoff_time:
                continue

            item = ContentItem(
                title=repository["full_name"],
                url=repository["html_url"],
                source_name="GitHub",
                published=repository["updated_at"],
                summary=repository.get("description", "") or "No description available",
                source_type="github_repo",
                branch="development",
                source_priority=config.get("priority", "medium"),
                authors_or_org=repository["owner"]["login"],
                metadata={
                    "stars": repository["stargazers_count"],
                    "forks": repository["forks_count"],
                    "language": repository.get("language", ""),
                },
            )
            items.append(item)
    return items
