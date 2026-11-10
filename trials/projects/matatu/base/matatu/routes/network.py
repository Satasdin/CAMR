"""How stages sit along a route."""

from typing import List

from ..errors import StageNotOnRoute
from ..models import Route
from ..store.repositories import save_route


def add_route(store, route_id: str, name: str, stage_ids: List[str]) -> Route:
    return save_route(store, Route(id=route_id, name=name, stage_ids=list(stage_ids)))


def position(route: Route, stage_id: str) -> int:
    try:
        return route.stage_ids.index(stage_id)
    except ValueError:
        raise StageNotOnRoute(stage_id, route.id) from None


def stages_between(route: Route, from_stage: str, to_stage: str) -> int:
    """How many stages a passenger travels, in either direction along the route."""
    return abs(position(route, to_stage) - position(route, from_stage))


def serves(route: Route, stage_id: str) -> bool:
    return stage_id in route.stage_ids


def routes_through(store, stage_id: str) -> List[Route]:
    return [route for route in store.routes.values() if route.active and serves(route, stage_id)]
