"""Which depots a parcel passes through."""

from collections import deque
from typing import Dict, List, Set

LINKS: Dict[str, Set[str]] = {
    "NBO": {"NKR", "NYR", "MBA", "GAR"},
    "NKR": {"NBO", "ELD", "KSM"},
    "NYR": {"NBO"},
    "ELD": {"NKR", "KSM", "LOD"},
    "KSM": {"NKR", "ELD"},
    "MBA": {"NBO", "LAM"},
    "LAM": {"MBA"},
    "GAR": {"NBO"},
    "LOD": {"ELD"},
}

DRIVING_HOURS: Dict[frozenset, int] = {
    frozenset({"NBO", "NKR"}): 3,
    frozenset({"NBO", "NYR"}): 3,
    frozenset({"NBO", "MBA"}): 9,
    frozenset({"NBO", "GAR"}): 7,
    frozenset({"NKR", "ELD"}): 3,
    frozenset({"NKR", "KSM"}): 4,
    frozenset({"ELD", "KSM"}): 3,
    frozenset({"ELD", "LOD"}): 9,
    frozenset({"MBA", "LAM"}): 6,
}


def route_between(origin: str, destination: str) -> List[str]:
    """The route with the fewest stops, found breadth first. Raises ValueError if none exists."""
    if origin not in LINKS or destination not in LINKS:
        raise ValueError("unknown depot")
    queue = deque([[origin]])
    visited = {origin}
    while queue:
        path = queue.popleft()
        if path[-1] == destination:
            return path
        for neighbour in sorted(LINKS[path[-1]]):
            if neighbour not in visited:
                visited.add(neighbour)
                queue.append(path + [neighbour])
    raise ValueError(f"no route from {origin} to {destination}")


def driving_hours(route: List[str]) -> int:
    return sum(DRIVING_HOURS[frozenset(pair)] for pair in zip(route, route[1:]))


def hubs_on(route: List[str]) -> List[str]:
    """The stops between the first and the last."""
    return route[1:-1]
