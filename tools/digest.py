from datetime import date, datetime
from pathlib import Path

from models import ContentItem


def _render_item(item: ContentItem) -> list[str]:
    topics = ", ".join(item.topics) or "Other"
    lines = [
        f"### {item.title}",
        f"Source: {item.source_name}",
        f"Published: {item.published}",
        f"Topics: {topics}",
        f"Relevance score: {item.score:g}",
    ]

    if item.authors_or_org:
        lines.append(f"Authors: {item.authors_or_org}")

    lines.extend(
        [
            f"Summary: {item.summary[:500]}",
            f"Link: {item.url}",
            "",
        ]
    )
    return lines


def _render_section(title: str, items: list[ContentItem]) -> list[str]:
    if not items:
        return []

    lines = [f"## {title}", ""]

    for item in items:
        lines.extend(_render_item(item))

    return lines


def save_digest(items: list[ContentItem]) -> Path:
    """Rebuild today's Markdown digest from stored selections."""
    output_directory = Path("outputs/digests")
    output_directory.mkdir(parents=True, exist_ok=True)
    output_path = output_directory / f"ai_digest_{date.today().isoformat()}.md"

    digest_lines = [
        f"# AI News Digest - {date.today().isoformat()}",
        "",
        f"Generated at {datetime.now().strftime('%H:%M')}",
        "",
    ]

    if not items:
        digest_lines.append("No items met the configured digest threshold.")
    else:
        section_order = [
            "Top Picks",
            "News & Model Releases",
            "Research Papers",
            "Repos, Tools & Models",
        ]

        for section in section_order:
            section_items = [
                item
                for item in items
                if item.metadata.get("digest_section") == section
            ]
            digest_lines.extend(_render_section(section, section_items))

    output_path.write_text("\n".join(digest_lines), encoding="utf-8")
    print(f"\nDigest rebuilt from stored selections: {output_path}")
    return output_path
