"""Resource lookup helpers."""

from __future__ import annotations

from typing import Any


def filter_resources_by_query(
    resources: list[dict[str, Any]], query: str
) -> list[dict[str, Any]]:
    """Filter resources by a case-insensitive substring across common fields."""
    if not query:
        return resources

    query_lower = query.lower()
    filtered: list[dict[str, Any]] = []
    for resource in resources:
        fields = (
            resource.get("name") or "",
            resource.get("username") or "",
            resource.get("uri") or "",
            resource.get("description") or "",
        )
        if any(query_lower in field.lower() for field in fields):
            filtered.append(resource)
    return filtered


def match_resources_by_name(
    resources: list[dict[str, Any]], name: str
) -> list[dict[str, Any]]:
    """Match resources by exact name first, then partial name."""
    exact = [
        resource
        for resource in resources
        if (resource.get("name") or "").lower() == name.lower()
    ]
    if exact:
        return exact

    return [
        resource
        for resource in resources
        if name.lower() in (resource.get("name") or "").lower()
    ]