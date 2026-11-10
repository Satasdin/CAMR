"""The places where matatus stop."""

from typing import List

from ..models import Route, Stage
from ..store.repositories import get_stage, save_stage


def add_stage(store, stage_id: str, name: str, zone: str = "central") -> Stage:
    return save_stage(store, Stage(id=stage_id, name=name, zone=zone))


def stage_names(store, route: Route) -> List[str]:
    return [get_stage(store, stage_id).name for stage_id in route.stage_ids]


def stages_in_zone(store, zone: str) -> List[Stage]:
    return [stage for stage in store.stages.values() if stage.zone == zone]


def termini(route: Route) -> tuple:
    if not route.stage_ids:
        raise ValueError(f"route {route.id} has no stages")
    return route.stage_ids[0], route.stage_ids[-1]
