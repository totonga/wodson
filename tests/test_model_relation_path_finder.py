from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import cast

import pytest
from google.protobuf.json_format import Parse
from odsbox.jaquel import jaquel_to_ods
from odsbox.model_cache import ModelCache
from odsbox.proto import ods

from wodson.utils.query import ModelRelationPathFinder, ensure_required_joins


class _FakeRelation:
    def __init__(
        self,
        *,
        name: str,
        entity_name: str,
        relationship: int = 0,
        base_name: str = "",
        range_max: int = 1,
        inverse_range_max: int = 1,
    ) -> None:
        self.name = name
        self.entity_name = entity_name
        self.relationship = relationship
        self.base_name = base_name
        self.range_max = range_max
        self.inverse_range_max = inverse_range_max


class _FakeEntity:
    def __init__(self, name: str, relations: dict[str, _FakeRelation]) -> None:
        self.name = name
        self.relations = relations


class _FakeModel:
    def __init__(self, entities: dict[str, _FakeEntity]) -> None:
        self.entities = entities


class _FakeModelCache:
    def __init__(self, model: _FakeModel) -> None:
        self._model = model

    def model(self) -> _FakeModel:
        return self._model

    def entity(self, name: str) -> _FakeEntity:
        return self._model.entities[name]


@pytest.fixture(scope="module")
def model() -> ods.Model:
    model_file = Path(__file__).parent / "data" / "application_model.json"
    return Parse(model_file.read_text(encoding="utf-8"), ods.Model())


def _referenced_aids(select_statement: ods.SelectStatement) -> list[int]:
    aids: list[int] = []
    seen: set[int] = set()

    for column in select_statement.columns:
        if column.aid not in seen:
            seen.add(column.aid)
            aids.append(column.aid)
    for item in select_statement.where:
        if item.HasField("condition") and item.condition.aid not in seen:
            seen.add(item.condition.aid)
            aids.append(item.condition.aid)
    for order in select_statement.order_by:
        if order.aid not in seen:
            seen.add(order.aid)
            aids.append(order.aid)
    for group in select_statement.group_by:
        if group.aid not in seen:
            seen.add(group.aid)
            aids.append(group.aid)

    return aids


def _connected_component(select_statement: ods.SelectStatement, start_aid: int) -> set[int]:
    graph: dict[int, set[int]] = {}
    for join in select_statement.joins:
        graph.setdefault(join.aid_from, set()).add(join.aid_to)
        graph.setdefault(join.aid_to, set()).add(join.aid_from)

    seen = {start_aid}
    stack = [start_aid]
    while stack:
        current = stack.pop()
        for neighbor in graph.get(current, set()):
            if neighbor not in seen:
                seen.add(neighbor)
                stack.append(neighbor)
    return seen


def test_find_path_prefers_cheapest_weighted_route() -> None:
    # A->B is cheap for the first edge (child), but A->C->D is cheaper overall.
    model = _FakeModel(
        {
            "A": _FakeEntity(
                "A",
                {
                    "to_b": _FakeRelation(
                        name="to_b",
                        entity_name="B",
                        relationship=ods.Model.RS_CHILD,
                    ),
                    "to_c": _FakeRelation(
                        name="to_c",
                        entity_name="C",
                        base_name="to_c_base",
                    ),
                    "to_d_nm": _FakeRelation(
                        name="to_d_nm",
                        entity_name="D",
                        range_max=-1,
                        inverse_range_max=-1,
                    ),
                },
            ),
            "B": _FakeEntity(
                "B",
                {
                    "to_d_from_b": _FakeRelation(name="to_d_from_b", entity_name="D"),
                },
            ),
            "C": _FakeEntity(
                "C",
                {
                    "to_d": _FakeRelation(name="to_d", entity_name="D", base_name="to_d_base"),
                },
            ),
            "D": _FakeEntity("D", {}),
        }
    )
    finder = ModelRelationPathFinder(cast(ModelCache, _FakeModelCache(model)))

    assert finder.find_path("A", "D") == ["to_c", "to_d"]


def test_find_path_raises_for_unreachable_entity() -> None:
    model = _FakeModel(
        {
            "A": _FakeEntity("A", {"to_b": _FakeRelation(name="to_b", entity_name="B")}),
            "B": _FakeEntity("B", {}),
            "C": _FakeEntity("C", {}),
        }
    )
    finder = ModelRelationPathFinder(cast(ModelCache, _FakeModelCache(model)))

    with pytest.raises(ValueError, match="No path"):
        finder.find_path("A", "C")


def test_find_path_same_source_and_target_is_empty(model: ods.Model) -> None:
    mc = ModelCache(model)
    finder = ModelRelationPathFinder(mc)

    assert finder.find_path("AoUnit", "AoUnit") == []


def test_find_path_output_is_navigable_in_real_model(model: ods.Model) -> None:
    mc = ModelCache(model)
    finder = ModelRelationPathFinder(mc)

    source = mc.entity("AoLocalColumn")
    target = mc.entity("AoMeasurement")
    relation_names = finder.find_path(source, target)

    assert relation_names

    current = source
    for relation_name in relation_names:
        relation = mc.relation(current, relation_name)
        current = mc.entity_by_aid(relation.entity_aid)

    assert current.name == target.name


def test_ensure_required_joins_does_not_mutate_input_statement(model: ods.Model) -> None:
    mc = ModelCache(model)
    query = {
        "AoMeasurementQuantity": {},
        "$attributes": {"name": 1, "unit.name": 1, "quantity.name": 1},
    }
    _entity, select_statement = jaquel_to_ods(mc.model(), query)
    original = deepcopy(select_statement)

    complemented = ensure_required_joins(mc, select_statement)

    assert complemented is not select_statement
    assert select_statement == original


def test_ensure_required_joins_connects_all_referenced_entities(model: ods.Model) -> None:
    mc = ModelCache(model)
    query = {
        "AoLocalColumn": {"submatrix.measurement": 153},
        "$attributes": {"id": 1, "flags": 1, "generation_parameters": 1},
    }
    _entity, select_statement = jaquel_to_ods(mc.model(), query)

    select_statement.joins.clear()
    complemented = ensure_required_joins(mc, select_statement)

    aids = _referenced_aids(complemented)
    assert len(aids) > 1

    root_aid = aids[0]
    connected = _connected_component(complemented, root_aid)
    assert set(aids).issubset(connected)
