"""Resource lookup helpers."""

from __future__ import annotations

from typing import Any


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