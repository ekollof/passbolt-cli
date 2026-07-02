"""Resource lookup helpers."""

from __future__ import annotations

from typing import Any


def _text_field(resource: dict[str, Any], field: str, *, default: str = "") -> str:
    """Return a string field from a resource, treating JSON null as missing."""
    value = resource.get(field)
    if value is None:
        return default
    return str(value)


def sanitize_resource_for_display(resource: dict[str, Any]) -> dict[str, Any]:
    """Normalize nullable API fields so UI layers never see JSON nulls."""
    sanitized = dict(resource)
    for field in ("name", "username", "uri", "description"):
        sanitized[field] = _text_field(sanitized, field)
    if not sanitized["name"]:
        sanitized["name"] = "Unknown"
    return sanitized


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
            _text_field(resource, "name"),
            _text_field(resource, "username"),
            _text_field(resource, "uri"),
            _text_field(resource, "description"),
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
        if _text_field(resource, "name").lower() == name.lower()
    ]
    if exact:
        return exact

    return [
        resource
        for resource in resources
        if name.lower() in _text_field(resource, "name").lower()
    ]