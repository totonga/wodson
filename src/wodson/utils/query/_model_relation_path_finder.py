import heapq
from copy import deepcopy

from odsbox.model_cache import ModelCache
from odsbox.proto import ods

_Edge = tuple[str, str, int]
_JoinTypeEnum = ods.SelectStatement.JoinItem.JoinTypeEnum


class ModelRelationPathFinder:
    def __init__(self, mc: ModelCache) -> None:
        self._mc = mc
        self._graph: dict[str, list[_Edge]] | None = None

    def find_path(
        self,
        source_entity: str | ods.Model.Entity,
        target_entity: str | ods.Model.Entity,
    ) -> list[str]:
        """Find the shortest weighted path between two entities.

        Uses Dijkstra's algorithm to compute the cheapest relation path,
        preferring children relations (weight 1) over base relations (weight 3),
        then regular relations (weight 13), while heavily penalizing n:m
        relations (weight 33).

        Args:
            source_entity: Starting entity (name or object).
            target_entity: Target entity (name or object).

        Returns:
            Ordered list of relation names forming the shortest path.

        Raises:
            ValueError: If *target_entity* is unreachable from *source_entity*.

        Example::

            path = ft.find_path("Project", "MeaResult")
            # Returns: ["StructureLevel", "Tests", "TestSteps", "MeaResults"]
        """
        source_e = self._resolve_entity(source_entity)
        target_e = self._resolve_entity(target_entity)
        return self._find_path(source_e.name, target_e.name)

    # ------------------------------------------------------------------
    # Graph building
    # ------------------------------------------------------------------

    @staticmethod
    def _relation_weight(relation: ods.Model.Relation) -> int:
        """Compute edge weight for a relation.

        Children relations (RS_CHILD) get the lowest weight so that Dijkstra
        prefers following the hierarchy downward.
        """
        if relation.relationship == ods.Model.RS_CHILD:
            return 1
        if relation.base_name:
            return 3
        if relation.range_max == -1 and relation.inverse_range_max == -1:
            return 33  # n:m relations are very expensive to join — avoid if possible
        return 13

    def _resolve_entity(self, entity: str | ods.Model.Entity) -> ods.Model.Entity:
        """Resolve an entity name or object to an Entity."""
        if isinstance(entity, str):
            return self._mc.entity(entity)
        return entity

    def _ensure_graph(self) -> dict[str, list[_Edge]]:
        """Lazily build and cache the directed relation graph."""
        if self._graph is None:
            self._graph = self._build_graph()
        return self._graph

    def _build_graph(self) -> dict[str, list[_Edge]]:
        """Build a directed weighted graph from all model entity relations."""
        graph: dict[str, list[_Edge]] = {}
        for entity_name, entity in self._mc.model().entities.items():
            edges: list[_Edge] = []
            for relation in entity.relations.values():
                if not relation.entity_name:
                    continue
                weight = self._relation_weight(relation)
                edges.append((relation.name, relation.entity_name, weight))
            graph[entity_name] = edges
        return graph

    # ------------------------------------------------------------------
    # Path finding (Dijkstra)
    # ------------------------------------------------------------------

    def _find_path(self, source: str, target: str) -> list[str]:
        """Find the shortest weighted path from *source* to *target*.

        Returns:
            Ordered list of relation names forming the path.

        Raises:
            ValueError: If *target* is unreachable from *source*.
        """
        if source == target:
            return []

        graph = self._ensure_graph()

        # dist[entity] = (total_weight, [relation_names...])
        dist: dict[str, tuple[int, list[str]]] = {source: (0, [])}
        # priority queue: (weight, entity_name)
        heap: list[tuple[int, str]] = [(0, source)]
        visited: set[str] = set()

        while heap:
            cost, current = heapq.heappop(heap)
            if current in visited:
                continue
            visited.add(current)

            if current == target:
                return dist[target][1]

            for rel_name, neighbor, weight in graph.get(current, []):
                new_cost = cost + weight
                if neighbor not in dist or new_cost < dist[neighbor][0]:
                    dist[neighbor] = (new_cost, dist[current][1] + [rel_name])
                    heapq.heappush(heap, (new_cost, neighbor))

        raise ValueError(f"No path from '{source}' to '{target}' in the model.")


def ensure_required_joins(mc: ModelCache, select_statement: ods.SelectStatement) -> ods.SelectStatement:
    """Return a copy of *select_statement* with joins connecting all used entities.

    ASAM ODS queries may omit joins; the required relation paths are then derived
    from the data model. This collects every entity referenced by the columns,
    conditions, order-by and group-by items, picks the first as the root, and uses
    :class:`ModelRelationPathFinder` to add the cheapest relation path from the root to each
    other entity. Existing joins are preserved and never duplicated. Each added
    join is OUTER when the relation's minimum cardinality is 0 (some root-side
    instances may have no related instance), otherwise it is a plain (inner) join.

    Args:
        mc: Model cache wrapping the application model used for the statement.
        select_statement: The ODS select statement to extend.

    Returns:
        A new :class:`SelectStatement` with the necessary joins added.

    Raises:
        ValueError: If a referenced entity is unreachable from the root entity.
    """
    result = deepcopy(select_statement)

    # Conditions usually sit on or navigate from the root, so collect them first.
    aids: list[int] = []
    seen: set[int] = set()
    for item in result.where:
        if item.HasField("condition"):
            aid = item.condition.aid
            if aid not in seen:
                seen.add(aid)
                aids.append(aid)
    for column in result.columns:
        if column.aid not in seen:
            seen.add(column.aid)
            aids.append(column.aid)
    for order in result.order_by:
        if order.aid not in seen:
            seen.add(order.aid)
            aids.append(order.aid)
    for group in result.group_by:
        if group.aid not in seen:
            seen.add(group.aid)
            aids.append(group.aid)

    if len(aids) <= 1:
        return result

    existing: set[tuple[int, int, str]] = {(join.aid_from, join.aid_to, join.relation) for join in result.joins}

    # Undirected connectivity of the entities already linked by existing joins.
    adjacency: dict[int, set[int]] = {}
    for join in result.joins:
        adjacency.setdefault(join.aid_from, set()).add(join.aid_to)
        adjacency.setdefault(join.aid_to, set()).add(join.aid_from)

    def _reachable(start: int) -> set[int]:
        seen = {start}
        stack = [start]
        while stack:
            node = stack.pop()
            for neighbour in adjacency.get(node, ()):
                if neighbour not in seen:
                    seen.add(neighbour)
                    stack.append(neighbour)
        return seen

    finder = ModelRelationPathFinder(mc)
    root_aid = aids[0]
    root_entity = mc.entity_by_aid(root_aid)
    connected = _reachable(root_aid)

    for target_aid in aids[1:]:
        # Entities already linked through existing joins need no extra path.
        if target_aid in connected:
            continue

        target_entity = mc.entity_by_aid(target_aid)
        relation_names = finder.find_path(root_entity, target_entity)

        current_entity = root_entity
        for relation_name in relation_names:
            relation = mc.relation(current_entity, relation_name)
            next_entity = mc.entity_by_aid(relation.entity_aid)

            # A relation with minimum cardinality 0 means some current_entity
            # instances have no related next_entity instance. Joining it as
            # INNER would silently drop those rows, so it must be OUTER.
            optional = relation.range_min == 0
            join_type = _JoinTypeEnum.JT_OUTER if optional else _JoinTypeEnum.JT_DEFAULT

            if optional:
                # jaquel_to_ods addresses OUTER joins exactly as navigated (the
                # direction of an OUTER join determines which side is
                # preserved), so the canonical flip below must not apply.
                join_from, join_to, join_rel = (current_entity, next_entity, relation.name)
            elif relation.range_max == -1 and relation.inverse_range_max == 1:
                # jaquel_to_ods stores father->child navigation as a canonical
                # child->father join (mandatory auto-added joins are inner,
                # where the direction is interchangeable).
                inverse_relation = mc.relation(next_entity, relation.inverse_name)
                join_from, join_to, join_rel = (
                    next_entity,
                    current_entity,
                    inverse_relation.name,
                )
            else:
                join_from, join_to, join_rel = (
                    current_entity,
                    next_entity,
                    relation.name,
                )

            key = (join_from.aid, join_to.aid, join_rel)
            if key not in existing:
                existing.add(key)
                adjacency.setdefault(join_from.aid, set()).add(join_to.aid)
                adjacency.setdefault(join_to.aid, set()).add(join_from.aid)
                result.joins.append(
                    ods.SelectStatement.JoinItem(
                        aid_from=join_from.aid,
                        aid_to=join_to.aid,
                        relation=join_rel,
                        join_type=join_type,
                    )
                )
            current_entity = next_entity

        connected = _reachable(root_aid)

    return result
